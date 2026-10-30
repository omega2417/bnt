-- Metadata store for the Meshtastic logistics layer (SQLite >= 3.35; portable to PostgreSQL/TimescaleDB)
PRAGMA journal_mode = WAL;

-- L1. Every received radio packet (raw radio metadata)
CREATE TABLE IF NOT EXISTS rx_packet (
  rx_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  gw_rx_ts     REAL    NOT NULL,          -- gateway clock, unix s (authoritative time)
  pkt_id       INTEGER,                   -- Meshtastic packet id
  from_node    INTEGER NOT NULL,
  to_node      INTEGER,
  channel      INTEGER,
  portnum      TEXT,
  rx_time      INTEGER,                   -- rxTime reported by the radio
  rx_snr       REAL,
  rx_rssi      INTEGER,
  hop_limit    INTEGER,
  hop_start    INTEGER,
  hops_taken   INTEGER,                   -- hop_start - hop_limit, NULL if unknown
  via_mqtt     INTEGER DEFAULT 0,
  payload_len  INTEGER,
  is_duplicate INTEGER DEFAULT 0,
  UNIQUE (from_node, pkt_id, gw_rx_ts)
);
CREATE INDEX IF NOT EXISTS ix_rx_from_ts ON rx_packet(from_node, gw_rx_ts);

-- L2. Node / device state (telemetry: battery, channel utilization, airtime)
CREATE TABLE IF NOT EXISTS node_metric (
  node         INTEGER NOT NULL,
  gw_rx_ts     REAL    NOT NULL,
  battery_pct  INTEGER,
  voltage      REAL,
  channel_util REAL,                      -- % (as reported by the node)
  air_util_tx  REAL,                      -- % of own airtime in the last hour
  uptime_s     INTEGER,
  temperature  REAL,                      -- environment sensor, if present
  PRIMARY KEY (node, gw_rx_ts)
);

CREATE TABLE IF NOT EXISTS position (
  node         INTEGER NOT NULL,
  gw_rx_ts     REAL    NOT NULL,
  lat          REAL, lon REAL, alt REAL,
  fix_time     INTEGER,                   -- GNSS time of fix
  sats         INTEGER,
  precision_bits INTEGER,
  rx_snr       REAL, hops_taken INTEGER,
  PRIMARY KEY (node, gw_rx_ts)
);

-- Node registry and configuration snapshot (L4 context)
CREATE TABLE IF NOT EXISTS node_registry (
  node         INTEGER PRIMARY KEY,
  node_id      TEXT, long_name TEXT, short_name TEXT, hw_model TEXT,
  role         TEXT,                      -- CLIENT_MUTE / ROUTER / CLIENT ...
  asset_type   TEXT,                      -- vehicle / relay / sensor / dispatcher / gateway
  asset_ref    TEXT,                      -- plate number, site code ... (pseudonymised)
  firmware     TEXT, modem_preset TEXT, region TEXT, antenna TEXT,
  first_seen   REAL, last_seen REAL
);

-- L3. Logistics events and their life cycle
CREATE TABLE IF NOT EXISTS logi_event (
  event_id     TEXT PRIMARY KEY,          -- hex of 6-byte id
  operation_id INTEGER NOT NULL,
  origin_node  INTEGER NOT NULL,
  event_code   INTEGER NOT NULL,
  priority     INTEGER,
  t_created    INTEGER,                   -- sender clock (may be 0)
  t_rx_gw      REAL NOT NULL,             -- first reception at gateway
  hops_taken   INTEGER,
  value        INTEGER,
  deadline_ts  REAL,                      -- t_rx_gw (or t_created) + deadline
  t_accept     REAL,                      -- dispatcher/driver accepted
  t_done       REAL,                      -- operation completed
  status       TEXT DEFAULT 'RECEIVED',   -- RECEIVED/ACCEPTED/DONE/REJECTED/EXPIRED
  outage_id    INTEGER                    -- link to outage window if any
);

CREATE TABLE IF NOT EXISTS logi_event_log (   -- append-only audit trail
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT, msg_type INTEGER, from_node INTEGER, gw_rx_ts REAL, rx_id INTEGER
);

-- Planned critical operations (denominator of A_op), filled from TMS/ERP before an outage or daily
CREATE TABLE IF NOT EXISTS planned_operation (
  operation_id INTEGER PRIMARY KEY,
  route_id     TEXT, vehicle_node INTEGER, cargo_class TEXT,
  critical     INTEGER DEFAULT 1,
  due_ts       REAL,                       -- deadline of the operation
  loss_if_failed_uah REAL                  -- expected loss if not completed on time
);

-- Outage windows of external connectivity and grid power (manual or from monitoring)
CREATE TABLE IF NOT EXISTS outage (
  outage_id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT CHECK (kind IN ('INTERNET','CELLULAR','GRID_POWER','RELAY')),
  t_start REAL NOT NULL, t_end REAL, note TEXT
);

-- Outbox for synchronisation with ERP/cloud when Internet is back (store-and-forward)
CREATE TABLE IF NOT EXISTS sync_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity TEXT, entity_id TEXT, payload_json TEXT, created_ts REAL, sent_ts REAL
);
