"""Compact binary protocol for logistics events over Meshtastic PRIVATE_APP (portnum 256).

Frame layout (big-endian, 24 bytes, fits easily into one LoRa frame):
  B  version (=1)
  B  msg_type   1=EVENT 2=ACCEPT 3=DONE 4=REJECT 5=HEARTBEAT
  6s event_id   (random, unique per event; the same id is reused by ACCEPT/DONE)
  I  operation_id  (id of the logistics operation / waybill line in TMS/ERP)
  B  event_code    (see EVENT_CODES)
  B  priority      0..3 (3 = critical)
  I  t_created     unix time, s (sender clock; may be 0 if the node has no GNSS/time)
  h  value         signed, scaled (e.g. temperature x10, minutes of delay)
  H  deadline_min  minutes from t_created for completion (0 = none)
  H  crc16         CRC-16/CCITT over all preceding bytes
"""
import os, struct, time
from dataclasses import dataclass

FMT = ">BB6sIBBIhH"
HDR_LEN = struct.calcsize(FMT)  # 22
FRAME_LEN = HDR_LEN + 2         # 24
VERSION = 1
MSG_TYPES = {1: "EVENT", 2: "ACCEPT", 3: "DONE", 4: "REJECT", 5: "HEARTBEAT"}
EVENT_CODES = {
    1: "TEMP_EXCURSION", 2: "DOOR_OPEN", 3: "DELAY", 4: "ROUTE_CHANGE_REQ",
    5: "DELIVERY_DONE", 6: "INCIDENT", 7: "LOADING_DONE", 8: "HANDOVER",
}

def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc

@dataclass
class LogiMsg:
    msg_type: int
    event_id: bytes
    operation_id: int
    event_code: int
    priority: int = 3
    t_created: int = 0
    value: int = 0
    deadline_min: int = 0
    version: int = VERSION

    def encode(self) -> bytes:
        body = struct.pack(FMT, self.version, self.msg_type, self.event_id, self.operation_id,
                           self.event_code, self.priority, self.t_created, self.value, self.deadline_min)
        return body + struct.pack(">H", crc16_ccitt(body))

    @classmethod
    def decode(cls, raw: bytes) -> "LogiMsg":
        if len(raw) != FRAME_LEN:
            raise ValueError(f"bad length {len(raw)}")
        body, (crc,) = raw[:HDR_LEN], struct.unpack(">H", raw[HDR_LEN:])
        if crc16_ccitt(body) != crc:
            raise ValueError("crc mismatch")
        v, mt, eid, op, code, pr, tc, val, dl = struct.unpack(FMT, body)
        if v != VERSION:
            raise ValueError(f"unsupported version {v}")
        return cls(mt, eid, op, code, pr, tc, val, dl, v)

    @property
    def event_hex(self) -> str:
        return self.event_id.hex()

def new_event(operation_id: int, event_code: int, value: int = 0, deadline_min: int = 30, priority: int = 3) -> LogiMsg:
    return LogiMsg(1, os.urandom(6), operation_id, event_code, priority, int(time.time()), value, deadline_min)

def reply(ev: LogiMsg, msg_type: int) -> LogiMsg:
    """ACCEPT / DONE / REJECT for an existing event (same event_id)."""
    return LogiMsg(msg_type, ev.event_id, ev.operation_id, ev.event_code, ev.priority, int(time.time()), 0, 0)
