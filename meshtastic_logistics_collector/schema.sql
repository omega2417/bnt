-- Metadata store for the Meshtastic logistics layer (SQLite >= 3.35; portable to PostgreSQL/TimescaleDB)
-- Schema version 2 (collector 1.1.0). No field database was ever produced with schema 1, so no migration is provided.
PRAGMA journal_mode = WAL;

-- Provenance. Every ingest run declares where its packets come from, so that numbers computed from
-- generated test data can never be presented as measurements (see kpi.py, key "provenance").
CREATE TABLE IF NOT EXISTS collector_session (
  session_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  started_ts   REAL NOT NULL,             -- wall clock of the machine that ran the collector
  source       TEXT NOT NULL,             -- 'serial' / 'tcp' / 'replay' / 'api'
  data_origin  TEXT NOT NULL CHECK (data_origin IN ('synthetic','recorded_live','live_radio','unlabelled')),
  detail       TEXT,                      -- device path, host, replay file name, generator name
  collector_version TEXT
);

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
  is_duplicate INTEGER DEFAULT 0,         -- same from_node + pkt_id seen again within 10 min
  session_id   INTEGER,
  UNIQUE (from_node, pkt_id, gw_rx_ts)
);
CREATE INDEX IF NOT EXISTS ix_rx_from_ts ON rx_packet(from_node, gw_rx_ts);

-- L2. Node / device state (telemetry: battery, channel utilization, airtime)
CREATE TABLE IF NOT EXISTS node_metric (
  node         INTEGER NOT NULL,
  gw_rx_ts     REAL    NOT NULL,
  battery_pct  INTEGER,
  voltage      REAL,
  channel_util REAL,                      -- % (as reported by the node, not computed here)
  air_util_tx  REAL,                      -- % of own airtime in the last hour (as reported by the node)
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
  priority     INTEGER,                   -- 3 = critical
  t_created    INTEGER,                   -- sender clock (may be 0 or wrong)
  t_rx_gw      REAL NOT NULL,             -- first reception at gateway
  hops_taken   INTEGER,
  value        INTEGER,
  deadline_ts  REAL,                      -- deadline start + deadline_min
  deadline_basis TEXT,                    -- 'sender_clock' (t_created plausible) or 'gateway_rx' (fallback)
  t_accept     REAL,                      -- dispatcher/driver accepted (first ACCEPT)
  t_done       REAL,                      -- operation completed or rejected (first DONE/REJECT)
  status       TEXT DEFAULT 'RECEIVED',   -- RECEIVED/ACCEPTED/DONE/REJECTED
  outage_id    INTEGER                    -- link to outage window if any (filled manually)
);

CREATE TABLE IF NOT EXISTS logi_event_log (   -- append-only audit trail (also keeps replies to unknown events)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT, msg_type INTEGER, from_node INTEGER, gw_rx_ts REAL, rx_id INTEGER
);

-- Planned critical operations (denominator of A_op), filled from TMS/ERP before an outage or daily
CREATE TABLE IF NOT EXISTS planned_operation (
  operation_id INTEGER PRIMARY KEY,
  route_id     TEXT, vehicle_node INTEGER, cargo_class TEXT,
  critical     INTEGER DEFAULT 1,
  due_ts       REAL,                       -- deadline of the operation
  loss_if_failed REAL                      -- assumed loss if not completed on time; one currency for all rows
                                           -- (the article uses constant EUR). An input assumption, not a measurement.
);

-- Outage windows of external connectivity and grid power (entered manually or from monitoring;
-- the collector itself does not detect outages)
CREATE TABLE IF NOT EXISTS outage (
  outage_id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT CHECK (kind IN ('INTERNET','CELLULAR','GRID_POWER','RELAY')),
  t_start REAL NOT NULL, t_end REAL, note TEXT
);

-- Outbox for synchronisation with ERP/cloud when Internet is back (store-and-forward).
-- Rows are queued only: no sender is implemented in this release, sent_ts stays NULL.
CREATE TABLE IF NOT EXISTS sync_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity TEXT, entity_id TEXT, payload_json TEXT, created_ts REAL, sent_ts REAL
);
