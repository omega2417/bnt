"""
Short-command protocol for robotic transport platforms over Meshtastic.

The protocol has two equivalent encodings of every command:

* **text**   - human-readable templates such as ``TSK T17 R3 FB R5 DL1420 Z128 OW0``
               that fit the Meshtastic TEXT_MESSAGE_APP port and can be typed or read
               on any Meshtastic handset;
* **binary** - a packed form (opcode + fixed fields + CRC-16) for the PRIVATE_APP port,
               3-4x shorter, so each frame costs less airtime on the 1 % duty-cycle gateway.

The catalogue extends Table 4 of the companion article (task contract, status beacon,
decision report, blockage report, receipt, site closure) with fleet-level commands
(request, bid, lease, recall, relay deployment, risk dial, reporting policy, ACK).

LoRa airtime follows the Semtech SX127x design guide (Eq. 1 of the article).
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- constants
MESH_HEADER_B = 16          # Meshtastic over-the-air header (bytes)
MAX_PAYLOAD_B = 233         # usable Meshtastic payload after header and protobuf overhead
ACK_FRAME_B = 28            # routing ACK frame incl. header (reproduces 37.5 ms at SHORT_FAST)
DEFAULT_HOP_LIMIT = 3       # Meshtastic default hop limit

# Meshtastic MeshPacket.Priority values (subset)
PRIORITY = {"MIN": 1, "BACKGROUND": 10, "DEFAULT": 64, "RELIABLE": 70, "ACK": 120, "MAX": 127}

# Modem presets used in the article (BW in Hz, CR denominator offset: 1 -> 4/5)
PRESETS: Dict[str, dict] = {
    "SHORT_TURBO": dict(sf=7, bw=500e3, cr=1),
    "SHORT_FAST": dict(sf=7, bw=250e3, cr=1),
    "MEDIUM_FAST": dict(sf=9, bw=250e3, cr=1),
    "LONG_FAST": dict(sf=11, bw=250e3, cr=1),
    "LONG_SLOW": dict(sf=12, bw=125e3, cr=4),
}

CARGO = {1: "medicine", 2: "water", 3: "food", 4: "infant", 5: "fuel-cell"}
ACTIONS = ("CMP", "RTG", "RET", "HLD", "STP", "DCL", "DRP")  # decision codes
ACTION_NAMES = {"CMP": "complete", "RTG": "re-target", "RET": "return", "HLD": "hold",
                "STP": "beacon-stop", "DCL": "decline", "DRP": "drop-stop"}


# --------------------------------------------------------------------------- airtime
def lora_airtime(payload_bytes: int, preset: str = "SHORT_FAST", n_preamble: int = 16,
                 crc: bool = True, implicit_header: bool = False) -> float:
    """Time on air (s) of one LoRa frame with ``payload_bytes`` bytes (Eq. 1)."""
    p = PRESETS[preset]
    sf, bw, cr = p["sf"], p["bw"], p["cr"]
    ts = (2 ** sf) / bw
    de = 1 if ts > 0.016 else 0                       # low-data-rate optimisation
    num = 8 * payload_bytes - 4 * sf + 28 + 16 * int(crc) - 20 * int(implicit_header)
    n_payload = 8 + max(math.ceil(num / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (n_preamble + 4.25) * ts + n_payload * ts


def frame_airtime(payload_bytes: int, preset: str = "SHORT_FAST") -> float:
    """Airtime of a Meshtastic frame = LoRa frame of header + payload."""
    return lora_airtime(MESH_HEADER_B + payload_bytes, preset)


def gateway_utilisation(n_robots: int, tau_r: float, u0: float = 0.0, duty: float = 0.01) -> float:
    """Gateway duty-cycle utilisation in % of the legal budget (Eq. 2)."""
    return u0 + n_robots * tau_r / (3600.0 * duty) * 100.0


def tau_per_robot(preset: str, policy: str = "event", status_period_s: float = 60.0,
                  events_per_h: float = 3.0, contracts_per_h: float = 0.6) -> float:
    """Gateway transmit airtime (s/h) caused by one robot.

    periodic: every status beacon is acknowledged by the gateway.
    event   : beacons are unacknowledged broadcasts (heard, not answered); only contracts,
              receipts, blockages and decisions are acknowledged; the gateway also sends
              the contract itself.
    """
    ack = lora_airtime(ACK_FRAME_B, preset)
    tsk = frame_airtime(48, preset)
    if policy == "periodic":
        return (3600.0 / status_period_s) * ack + contracts_per_h * tsk
    return events_per_h * ack + contracts_per_h * (tsk + ack)


# --------------------------------------------------------------------------- messages
@dataclass
class Command:
    """A decoded short command. ``op`` is the opcode, ``f`` the fields."""
    op: str
    f: Dict[str, object] = field(default_factory=dict)

    def text(self) -> str:
        return encode_text(self)

    def binary(self) -> bytes:
        return encode_binary(self)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"Command({self.text()!r})"


def _hhmm(minutes: float) -> str:
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}{m % 60:02d}"


def _from_hhmm(s: str) -> int:
    return int(s[:2]) * 60 + int(s[2:])


# Each spec: opcode -> (binary opcode byte, ordered list of (field, text-format, struct-code))
#   text-format: a prefix string, "" for bare value, or a callable pair handled below.
SPEC: Dict[str, Tuple[int, List[Tuple[str, str, str]]]] = {
    # --- Table 4 of the article -----------------------------------------------------
    "TSK": (0x01, [("task", "T", "H"), ("site", "R", "B"), ("alt", "FB R", "B"),
                   ("deadline", "DL", "H"), ("z", "Z", "B"), ("oneway", "OW", "B")]),
    "RS":  (0x02, [("unit", "U", "B"), ("node", "N", "H"), ("soc", "S", "B"),
                   ("energy", "E", "H"), ("mode", "M", "B")]),
    "DEC": (0x03, [("unit", "U", "B"), ("action", "", "B"), ("target", "", "B"), ("soc", "S", "B")]),
    "BLK": (0x04, [("unit", "U", "B"), ("edge", "E", "H")]),
    "RCP": (0x05, [("task", "T", "H"), ("site", "R", "B"), ("time", "", "H"),
                   ("pin", "PIN", "B"), ("unit", "U", "B")]),
    "CLS": (0x06, [("site", "R", "B"), ("alt", "ALT R", "B")]),
    # --- fleet-level extensions -----------------------------------------------------
    "REQ": (0x07, [("task", "T", "H"), ("site", "R", "B"), ("qty", "Q", "B"), ("cargo", "C", "B"), ("prio", "PR", "B")]),
    "BID": (0x08, [("task", "T", "H"), ("unit", "U", "B"), ("eta", "ETA", "H")]),
    "LSE": (0x09, [("task", "T", "H"), ("unit", "U", "B"), ("ttl", "TTL", "B")]),
    "RTB": (0x0A, [("unit", "U", "B"), ("point", "P", "B")]),
    "RLY": (0x0B, [("unit", "U", "B"), ("node", "N", "H")]),
    "ZSET": (0x0C, [("z", "", "B")]),
    "RPT": (0x0D, [("period", "", "B")]),            # 0 = event-driven, else minutes
    "ACK": (0x0E, [("ref", "", "H")]),
    "HLD": (0x0F, [("unit", "U", "B"), ("minutes", "MIN", "B")]),
}
OPCODES = {v[0]: k for k, v in SPEC.items()}
POINT_CODES = {"H0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
POINT_NAMES = {v: k for k, v in POINT_CODES.items()}

# what each command is for, who sends it and whether the gateway acknowledges it
CATALOGUE = [
    # op, direction, ack, priority, meaning (EN), meaning (UA)
    ("TSK", "CC -> robot", True, "RELIABLE", "contingent task contract", "контракт завдання"),
    ("RS", "robot -> all", False, "BACKGROUND", "status beacon (heartbeat)", "маяк стану"),
    ("DEC", "robot -> CC", True, "RELIABLE", "decision report (RETURN, HOLD, STOP ...)", "звіт про рішення"),
    ("BLK", "robot -> CC", True, "RELIABLE", "sensed blockage of a street segment", "перекриття ділянки"),
    ("RCP", "robot -> CC", True, "RELIABLE", "delivery receipt co-signed by recipient PIN", "квитанція видачі"),
    ("CLS", "CC -> all", False, "DEFAULT", "site closed, alternative site", "закриття пункту"),
    ("REQ", "site -> CC", True, "RELIABLE", "delivery request from a recipient node", "заявка пункту"),
    ("BID", "robot -> robots", False, "DEFAULT", "auction bid (ETA) for a request", "ставка аукціону"),
    ("LSE", "robot/CC -> all", True, "RELIABLE", "lease: request taken by a unit", "оренда заявки"),
    ("RTB", "CC -> robot", True, "MAX", "recall / veto: return to point", "відкликання"),
    ("RLY", "CC -> relay UGV", True, "RELIABLE", "move relay robot with mast to node", "розгортання ретранслятора"),
    ("ZSET", "CC -> all", False, "DEFAULT", "risk dial z x100", "рівень ризику z"),
    ("RPT", "steward -> all", False, "DEFAULT", "reporting policy (0 = event-driven)", "політика звітів"),
    ("ACK", "any", False, "ACK", "application-level acknowledgement", "підтвердження"),
    ("HLD", "CC -> robot", True, "RELIABLE", "hold position for N minutes", "утримання позиції"),
]
CATALOGUE_BY_OP = {c[0]: c for c in CATALOGUE}


def encode_text(cmd: Command) -> str:
    _, fields = SPEC[cmd.op]
    toks = [cmd.op]
    for name, pre, _ in fields:
        v = cmd.f[name]
        if cmd.op == "DEC" and name == "action":
            toks.append(str(v))
        elif cmd.op == "DEC" and name == "target":
            toks.append(v if isinstance(v, str) else POINT_NAMES.get(int(v), f"R{int(v)}"))
        elif name in ("deadline", "time", "eta"):
            toks.append(pre + _hhmm(v))
        elif name == "pin":
            toks.append("PIN+" if v else "PIN-")
        elif pre.startswith("FB ") or pre.startswith("ALT "):
            toks.append(pre.split()[0])
            toks.append(pre.split()[1] + str(v))
        else:
            toks.append(f"{pre}{v}")
    return " ".join(toks)


_TOKEN = re.compile(r"^([A-Z+-]*?)(\d+)$")


def decode_text(s: str) -> Command:
    """Parse a text command. Raises ValueError on malformed input."""
    toks = s.strip().upper().split()
    if not toks or toks[0] not in SPEC:
        raise ValueError(f"unknown opcode in {s!r}")
    op = toks[0]
    _, fields = SPEC[op]
    f: Dict[str, object] = {}
    i = 1
    for name, pre, _ in fields:
        if i >= len(toks):
            raise ValueError(f"missing field {name} in {s!r}")
        if pre.startswith("FB ") or pre.startswith("ALT "):
            if toks[i] != pre.split()[0]:
                raise ValueError(f"expected {pre.split()[0]} in {s!r}")
            i += 1
            tok = toks[i]
            pre2 = pre.split()[1]
        else:
            tok, pre2 = toks[i], pre
        i += 1
        if op == "DEC" and name == "action":
            if tok not in ACTIONS:
                raise ValueError(f"bad action {tok}")
            f[name] = tok
            continue
        if op == "DEC" and name == "target":
            f[name] = tok
            continue
        if name == "pin":
            f[name] = 1 if tok.endswith("+") else 0
            continue
        if pre2 and not tok.startswith(pre2):
            raise ValueError(f"field {name}: expected prefix {pre2!r}, got {tok!r}")
        val = tok[len(pre2):]
        if not val.isdigit():
            raise ValueError(f"field {name}: not a number in {tok!r}")
        f[name] = _from_hhmm(val) if name in ("deadline", "time", "eta") else int(val)
    if i != len(toks):
        raise ValueError(f"trailing tokens in {s!r}")
    return Command(op, f)


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _num(cmd: Command, name: str) -> int:
    v = cmd.f[name]
    if cmd.op == "DEC" and name == "action":
        return ACTIONS.index(v)
    if cmd.op == "DEC" and name == "target":
        if isinstance(v, str):
            return POINT_CODES[v] if v in POINT_CODES else 100 + int(v[1:])
        return int(v)
    return int(round(v)) % 1440 if name in ("deadline", "time", "eta") else int(v)


def encode_binary(cmd: Command) -> bytes:
    code, fields = SPEC[cmd.op]
    fmt = "<B" + "".join(c for _, _, c in fields)
    body = struct.pack(fmt, code, *[_num(cmd, n) for n, _, _ in fields])
    return body + struct.pack("<H", crc16_ccitt(body))


def decode_binary(data: bytes) -> Command:
    if len(data) < 3:
        raise ValueError("frame too short")
    body, crc = data[:-2], struct.unpack("<H", data[-2:])[0]
    if crc16_ccitt(body) != crc:
        raise ValueError("CRC mismatch")
    op = OPCODES.get(body[0])
    if op is None:
        raise ValueError("unknown opcode")
    fields = SPEC[op][1]
    vals = struct.unpack("<B" + "".join(c for _, _, c in fields), body)[1:]
    f: Dict[str, object] = {}
    for (n, _, _), v in zip(fields, vals):
        if op == "DEC" and n == "action":
            f[n] = ACTIONS[v]
        elif op == "DEC" and n == "target":
            f[n] = f"R{v - 100}" if v >= 100 else POINT_NAMES[v]
        else:
            f[n] = v
    return Command(op, f)


# convenient constructors -------------------------------------------------------------
def TSK(task, site, alt, deadline, z=1.28, oneway=False):
    return Command("TSK", dict(task=task, site=site, alt=alt, deadline=deadline,
                               z=int(round(z * 100)), oneway=int(oneway)))


def RS(unit, node, soc, energy, mode):
    return Command("RS", dict(unit=unit, node=node, soc=int(round(soc * 100)), energy=int(energy), mode=mode))


def DEC(unit, action, target, soc):
    return Command("DEC", dict(unit=unit, action=action, target=target, soc=int(round(soc * 100))))


def BLK(unit, edge):
    return Command("BLK", dict(unit=unit, edge=edge))


def RCP(task, site, time, unit, pin=True):
    return Command("RCP", dict(task=task, site=site, time=time, pin=int(pin), unit=unit))


def CLS(site, alt):
    return Command("CLS", dict(site=site, alt=alt))


def REQ(site, qty=1, cargo=1, prio=1, task=0):
    return Command("REQ", dict(task=task, site=site, qty=qty, cargo=cargo, prio=prio))


def BID(task, unit, eta):
    return Command("BID", dict(task=task, unit=unit, eta=eta))


def LSE(task, unit, ttl=30):
    return Command("LSE", dict(task=task, unit=unit, ttl=ttl))


def RTB(unit, point=0):
    return Command("RTB", dict(unit=unit, point=point))


def RLY(unit, node):
    return Command("RLY", dict(unit=unit, node=node))


def ZSET(z):
    return Command("ZSET", dict(z=int(round(z * 100))))


def RPT(period_min=0):
    return Command("RPT", dict(period=period_min))


def ACK(ref):
    return Command("ACK", dict(ref=ref % 65536))


def HLD(unit, minutes):
    return Command("HLD", dict(unit=unit, minutes=minutes))


# --------------------------------------------------------------------------- validator
def validate(cmd: Command, n_sites: int = 8, n_units: int = 16, n_nodes: int = 2000) -> List[str]:
    """Deterministic validator: returns a list of violations (empty = valid).

    Every command produced by a neural or language-model component must pass this
    validator before it is transmitted (runtime assurance)."""
    errs = []
    f = cmd.f
    if cmd.op not in SPEC:
        return [f"unknown op {cmd.op}"]
    for name, _, _ in SPEC[cmd.op][1]:
        if name not in f:
            errs.append(f"missing {name}")
    if errs:
        return errs
    if "site" in f and not 1 <= int(f["site"]) <= n_sites:
        errs.append(f"site R{f['site']} out of range")
    if "alt" in f and not 1 <= int(f["alt"]) <= n_sites:
        errs.append(f"alt R{f['alt']} out of range")
    if "alt" in f and "site" in f and f["alt"] == f["site"]:
        errs.append("fallback equals recipient")
    if "unit" in f and not 0 <= int(f["unit"]) < n_units:
        errs.append("unit out of range")
    if "z" in f and not 0 <= int(f["z"]) <= 300:
        errs.append("risk z outside [0, 3]")
    if "node" in f and not 0 <= int(f["node"]) < n_nodes:
        errs.append("node out of range")
    if cmd.op == "RTB" and int(f["point"]) not in POINT_NAMES:
        errs.append("unknown recovery point")
    if len(encode_text(cmd)) > MAX_PAYLOAD_B:
        errs.append("payload too long")
    return errs


@dataclass
class Packet:
    """One Meshtastic transmission as logged by the simulator."""
    pid: int
    t_send: float                 # min
    src: str
    dst: str                      # agent name or '^all'
    cmd: Command
    want_ack: bool
    priority: str
    encoding: str = "text"
    t_recv: float = math.inf      # min (inf = not delivered yet)
    path: str = ""                # mesh / cell / p2p / dtn / dock / local
    hops: int = 0
    airtime: float = 0.0          # s, total over all hops incl. ACK
    attempts: int = 0
    dropped: bool = False

    @property
    def payload(self) -> bytes:
        return self.cmd.binary() if self.encoding == "binary" else self.cmd.text().encode()

    @property
    def size(self) -> int:
        return len(self.payload)

    @property
    def latency(self) -> float:
        return self.t_recv - self.t_send
