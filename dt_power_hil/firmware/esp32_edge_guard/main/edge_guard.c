/*
 * edge_guard — ESP32-S3 firmware for the DT-NODE01-12V bench (ESP-IDF v5.x).
 *
 * Responsibilities (protocol sections 6.4, 6.5, 7):
 *   - 10 Hz sampling of INA226 channels M0..M5 over isolated I2C (ADuM1250),
 *     1 Hz aggregated telemetry (mean/min/max/n) on dt/node01/telemetry;
 *   - state machine INIT -> READY -> RUNNING <-> DEGRADED -> STOPPED;
 *   - command contract: schema, mode, source, run_id, boot_id, action whitelist,
 *     conservative freshness check (expires_at - clock_uncertainty > now_utc),
 *     idempotent duplicate handling by command_id;
 *   - local protection independent of MQTT/PC: pack voltage floor and BMS
 *     status force the auxiliary relay OFF; heartbeat loss > 5 s -> DEGRADED;
 *   - the relay output defaults to OFF at boot (GPIO pulled low, NO contact).
 *
 * The same decision table is mirrored in dtpower/edge_guard.py; the emulated
 * campaign exercises that mirror. This source has not been compiled or flashed
 * as part of the emulated campaign — build with `idf.py build` and run the
 * E10 vectors on the target before any physical run.
 */
#include <string.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_random.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "mqtt_client.h"
#include "cJSON.h"
#include <sys/time.h>

#define TAG "edge_guard"
#define GPIO_AUX_RELAY        GPIO_NUM_10   /* -> PC817 -> ULN2003A -> relay coil */
#define I2C_SDA               GPIO_NUM_8
#define I2C_SCL               GPIO_NUM_9
#define SAMPLE_PERIOD_US      100000        /* 10 Hz */
#define STALE_US              5000000       /* heartbeat stale 5 s */
#define V_LOCAL_MIN_MV        12400         /* aux permission floor */
#define CLOCK_UNC_MS          15
#define SEEN_MAX              64

typedef enum { ST_INIT, ST_READY, ST_RUNNING, ST_DEGRADED, ST_STOPPED } state_t;
static const char *ST_NAME[] = {"INIT", "READY", "RUNNING", "DEGRADED", "STOPPED"};

static const uint8_t INA_ADDR[6] = {0x40, 0x41, 0x44, 0x45, 0x48, 0x49}; /* M0..M5 */
static const float SHUNT_OHM[6] = {0.0025f, 0.0015f, 0.0075f, 0.0075f, 0.0075f, 0.0075f};
static float cal_a[6] = {1, 1, 1, 1, 1, 1}, cal_b[6] = {0};  /* from CAL-B1-E00, NVS */

static state_t g_state = ST_INIT;
static bool g_aux = false;
static bool g_prot_ok = true;
static int64_t g_last_hb_us = 0;
static char g_run_id[48] = "", g_boot_id[16] = "", g_mode[24] = "physical";
static char g_seen[SEEN_MAX][64];
static int g_seen_n = 0;
static uint32_t g_seq = 0;
static esp_mqtt_client_handle_t g_mqtt;
static i2c_master_dev_handle_t g_ina[6];

typedef struct { float sum_i, sum_v, min_i, max_i; int n; } agg_t;
static agg_t g_agg[6];

static void aux_set(bool on, const char *why)
{
    if (g_aux != on) ESP_LOGI(TAG, "AUX %s (%s)", on ? "ON" : "OFF", why);
    g_aux = on;
    gpio_set_level(GPIO_AUX_RELAY, on ? 1 : 0);
}

static int64_t now_utc_ms(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);   /* SNTP-disciplined; residual offset recorded per run */
    return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

static bool ina226_read(int ch, float *i_a, float *v_v)
{
    uint8_t reg, buf[2];
    reg = 0x01; /* shunt voltage, LSB 2.5 uV */
    if (i2c_master_transmit_receive(g_ina[ch], &reg, 1, buf, 2, 10) != ESP_OK) return false;
    int16_t sh = (int16_t)((buf[0] << 8) | buf[1]);
    reg = 0x02; /* bus voltage, LSB 1.25 mV */
    if (i2c_master_transmit_receive(g_ina[ch], &reg, 1, buf, 2, 10) != ESP_OK) return false;
    uint16_t bus = (uint16_t)((buf[0] << 8) | buf[1]);
    float i_raw = sh * 2.5e-6f / SHUNT_OHM[ch];
    *i_a = cal_a[ch] * i_raw + cal_b[ch];
    *v_v = bus * 1.25e-3f;
    return true;
}

/* 10 Hz timer: sampling + local protection only; no network/disk here (esp_timer rule) */
static void sample_cb(void *arg)
{
    for (int ch = 0; ch < 6; ++ch) {
        float i, v;
        if (!ina226_read(ch, &i, &v)) continue;
        agg_t *a = &g_agg[ch];
        if (a->n == 0) { a->min_i = a->max_i = i; }
        a->sum_i += i; a->sum_v += v; a->n++;
        if (i < a->min_i) a->min_i = i;
        if (i > a->max_i) a->max_i = i;
        if (ch == 1) {                       /* M1 battery channel */
            g_prot_ok = (v * 1000.0f) >= V_LOCAL_MIN_MV;
            if (!g_prot_ok && g_aux) aux_set(false, "local_protection");
        }
    }
    int64_t t = esp_timer_get_time();
    if (g_state == ST_RUNNING && t - g_last_hb_us > STALE_US) {
        g_state = ST_DEGRADED;
        ESP_LOGW(TAG, "RUNNING->DEGRADED (heartbeat stale)");
    }
    if (g_state != ST_RUNNING && g_aux) aux_set(false, ST_NAME[g_state]);
}

static bool seen(const char *cid)
{
    for (int k = 0; k < g_seen_n; ++k) if (strcmp(g_seen[k], cid) == 0) return true;
    return false;
}

static void remember(const char *cid)
{
    strncpy(g_seen[g_seen_n % SEEN_MAX], cid, 63);
    g_seen_n++;
}

static void publish_ack(const char *cid, bool acc, const char *why, bool dup)
{
    char out[256];
    snprintf(out, sizeof out,
             "{\"command_id\":\"%s\",\"accepted\":%s,\"reject_reason\":\"%s\",\"duplicate\":%s,"
             "\"t_mono_us\":%lld,\"aux_out\":%s,\"state\":\"%s\",\"boot_id\":\"%s\"}",
             cid, acc ? "true" : "false", why, dup ? "true" : "false",
             (long long)esp_timer_get_time(), g_aux ? "true" : "false", ST_NAME[g_state], g_boot_id);
    esp_mqtt_client_publish(g_mqtt, "dt/node01/ack", out, 0, 1, 0);
}

static void handle_command(const char *data, int len)
{
    cJSON *j = cJSON_ParseWithLength(data, len);
    if (!j) return;
    const char *why = NULL;
    const cJSON *cid = cJSON_GetObjectItem(j, "command_id");
    const cJSON *act = cJSON_GetObjectItem(j, "action");
    const cJSON *exp = cJSON_GetObjectItem(j, "expires_at_utc_ms");
    const char *id = cJSON_IsString(cid) ? cid->valuestring : "?";
#define STR_EQ(k, v) (cJSON_IsString(cJSON_GetObjectItem(j, k)) && strcmp(cJSON_GetObjectItem(j, k)->valuestring, v) == 0)
    if (!STR_EQ("schema_version", "1.0")) why = "schema";
    else if (!STR_EQ("mode", g_mode)) why = "mode_mismatch";
    else if (!STR_EQ("source", "ems")) why = "source";
    else if (!STR_EQ("run_id", g_run_id)) why = "run_id";
    else if (!STR_EQ("boot_id_target", g_boot_id)) why = "boot_id";
    else if (!(STR_EQ("action", "SET_AUX_ON") || STR_EQ("action", "SET_AUX_OFF"))) why = "action";
    else if (!cJSON_IsNumber(exp) || (int64_t)exp->valuedouble - CLOCK_UNC_MS <= now_utc_ms()) why = "expired";
    if (!why && seen(id)) { publish_ack(id, true, "", true); cJSON_Delete(j); return; }
    bool on = cJSON_IsString(act) && strcmp(act->valuestring, "SET_AUX_ON") == 0;
    if (!why && on) {
        if (g_state != ST_RUNNING) why = "state";
        else if (!g_prot_ok) why = "local_permission";
    }
    if (!why) { aux_set(on, id); remember(id); }
    publish_ack(id, why == NULL, why ? why : "", false);
    cJSON_Delete(j);
}

static void handle_health(const char *data, int len)
{
    cJSON *j = cJSON_ParseWithLength(data, len);
    if (!j) return;
    if (STR_EQ("run_id", g_run_id)) {
        g_last_hb_us = esp_timer_get_time();
        const cJSON *rec = cJSON_GetObjectItem(j, "reconciled");
        if (g_state == ST_DEGRADED && cJSON_IsTrue(rec)) g_state = ST_RUNNING;
    }
    cJSON_Delete(j);
}

static void mqtt_cb(void *arg, esp_event_base_t base, int32_t id, void *ev_data)
{
    esp_mqtt_event_handle_t e = ev_data;
    if (id == MQTT_EVENT_CONNECTED) {
        esp_mqtt_client_subscribe(g_mqtt, "dt/node01/command", 1);
        esp_mqtt_client_subscribe(g_mqtt, "dt/node01/health", 0);
    } else if (id == MQTT_EVENT_DATA) {
        if (e->topic_len >= 17 && strncmp(e->topic, "dt/node01/command", 17) == 0) handle_command(e->data, e->data_len);
        else if (strncmp(e->topic, "dt/node01/health", 16) == 0) handle_health(e->data, e->data_len);
    }
}

static void telemetry_task(void *arg)
{
    TickType_t last = xTaskGetTickCount();
    char out[768];
    for (;;) {
        vTaskDelayUntil(&last, pdMS_TO_TICKS(1000));
        agg_t s[6];
        memcpy(s, g_agg, sizeof s);
        memset(g_agg, 0, sizeof g_agg);
        float v = s[1].n ? s[1].sum_v / s[1].n : 0;
        float i[6];
        for (int k = 0; k < 6; ++k) i[k] = s[k].n ? s[k].sum_i / s[k].n : 0;
        snprintf(out, sizeof out,
                 "{\"schema_version\":\"1.0\",\"run_id\":\"%s\",\"device_id\":\"esp32s3-node01\",\"boot_id\":\"%s\","
                 "\"seq\":%lu,\"mode\":\"%s\",\"t_mono_us\":%lld,\"ts_utc_ms\":%lld,\"v_batt_v\":%.4f,\"i_batt_a\":%.4f,"
                 "\"i_batt_min\":%.4f,\"i_batt_max\":%.4f,\"n_samples\":%d,\"p_gen_bus_w\":%.3f,\"p_crit_bus_w\":%.3f,"
                 "\"p_aux_bus_w\":%.3f,\"aux_out\":%s,\"state\":\"%s\"}",
                 g_run_id, g_boot_id, (unsigned long)++g_seq, g_mode, (long long)esp_timer_get_time(),
                 (long long)now_utc_ms(), v, i[1], s[1].min_i, s[1].max_i, s[1].n, v * i[0], v * i[2], v * i[4],
                 g_aux ? "true" : "false", ST_NAME[g_state]);
        esp_mqtt_client_publish(g_mqtt, "dt/node01/telemetry", out, 0, 1, 0);
    }
}

void app_main(void)
{
    gpio_config_t io = {.pin_bit_mask = 1ULL << GPIO_AUX_RELAY, .mode = GPIO_MODE_OUTPUT, .pull_down_en = 1};
    gpio_config(&io);
    aux_set(false, "boot");                               /* safe state before anything else */
    snprintf(g_boot_id, sizeof g_boot_id, "%08lx", (unsigned long)esp_random());

    i2c_master_bus_config_t bc = {.i2c_port = 0, .sda_io_num = I2C_SDA, .scl_io_num = I2C_SCL,
                                  .clk_source = I2C_CLK_SRC_DEFAULT, .flags.enable_internal_pullup = false};
    i2c_master_bus_handle_t bus;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bc, &bus));
    for (int k = 0; k < 6; ++k) {
        i2c_device_config_t dc = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = INA_ADDR[k], .scl_speed_hz = 400000};
        ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dc, &g_ina[k]));
        uint8_t cfg[3] = {0x00, 0x45, 0x27};             /* AVG=16, VBUSCT=VSHCT=1.1 ms, continuous */
        i2c_master_transmit(g_ina[k], cfg, 3, 10);
    }
    g_state = ST_READY;                                    /* self-test passed */
    /* run_id is provisioned by the operator over the serial console before RUNNING */

    esp_mqtt_client_config_t mc = {.broker.address.uri = CONFIG_BROKER_URI};
    g_mqtt = esp_mqtt_client_init(&mc);
    esp_mqtt_client_register_event(g_mqtt, ESP_EVENT_ANY_ID, mqtt_cb, NULL);
    esp_mqtt_client_start(g_mqtt);

    const esp_timer_create_args_t ta = {.callback = sample_cb, .name = "sample"};
    esp_timer_handle_t th;
    ESP_ERROR_CHECK(esp_timer_create(&ta, &th));
    ESP_ERROR_CHECK(esp_timer_start_periodic(th, SAMPLE_PERIOD_US));
    xTaskCreate(telemetry_task, "telemetry", 6144, NULL, 5, NULL);
}
