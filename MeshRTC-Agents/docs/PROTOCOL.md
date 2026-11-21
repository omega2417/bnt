# Short-command protocol over Meshtastic — specification v1.0

Every command is a single Meshtastic packet. Two equivalent encodings:

* **text** (port `TEXT_MESSAGE_APP`): `OP field field ...`, ASCII, upper case, space-separated,
  readable and typable on any Meshtastic handset;
* **binary** (port `PRIVATE_APP`): `opcode (1 B) | fields (little-endian) | CRC-16/CCITT-FALSE (2 B)`.

Channel: private Meshtastic channel with AES-256 pre-shared key; addressing (`to`, `from`,
`want_ack`, `hop_limit = 3`, `priority`) is carried by the Meshtastic header (16 B), not by the payload.
Times are clock minutes `HHMM`; `z` is the risk level ×100; sites `R1..R8`; recovery points `H0, P1..P3`;
units `U1..U15` (`U0` = crisis-coordination centre).

| Op | Opcode | Direction | ACK | Priority | Text template | Fields (binary type) |
|---|---|---|---|---|---|---|
| TSK | 0x01 | CC → robot | yes | RELIABLE | `TSK T17 R3 FB R5 DL1420 Z128 OW0` | task u16, site u8, alt u8, deadline u16, z u8, oneway u8 |
| RS | 0x02 | robot → all | no | BACKGROUND | `RS U3 N217 S41 E182 M2` | unit u8, node u16, SoC % u8, usable Wh u16, regime u8 |
| DEC | 0x03 | robot → CC | yes | RELIABLE | `DEC U3 RET P1 S27` | unit u8, action u8 {CMP,RTG,RET,HLD,STP,DCL,DRP}, target u8, SoC u8 |
| BLK | 0x04 | robot ↔ CC | yes | RELIABLE | `BLK U3 E447` | unit u8, edge u16 |
| RCP | 0x05 | robot/site → CC | yes | RELIABLE | `RCP T17 R3 1342 PIN+ U3` | task u16, site u8, time u16, pin u8, unit u8 |
| CLS | 0x06 | CC → all | no | DEFAULT | `CLS R3 ALT R5` | site u8, alt u8 |
| REQ | 0x07 | site → CC | yes | RELIABLE | `REQ T21 R4 Q1 C2 PR1` | task u16, site u8, qty u8, cargo u8, prio u8 |
| BID | 0x08 | robot → robots | no | DEFAULT | `BID T21 U2 ETA1405` | task u16, unit u8, eta u16 |
| LSE | 0x09 | robot/CC → all | yes | RELIABLE | `LSE T21 U2 TTL30` | task u16, unit u8, ttl u8 |
| RTB | 0x0A | CC → robot | yes | MAX | `RTB U3 P1` | unit u8, point u8 |
| RLY | 0x0B | CC → relay | yes | RELIABLE | `RLY U9 N133` | unit u8, node u16 |
| ZSET | 0x0C | CC → all | no | DEFAULT | `ZSET 233` | z u8 |
| RPT | 0x0D | steward → all | no | DEFAULT | `RPT 0` | period u8 (0 = event-driven) |
| ACK | 0x0E | any | no | ACK | `ACK 77` | ref u16 |
| HLD | 0x0F | CC → robot | yes | RELIABLE | `HLD U3 MIN30` | unit u8, minutes u8 |

Cargo codes: 1 medicine, 2 water, 3 food, 4 infant formula, 5 fuel cell.

## Rules

1. **Event-driven reporting** is the default: `RS` is an unacknowledged broadcast every 10 min;
   only contracts, decisions, blockages, receipts, requests and leases are acknowledged.
2. A robot keeps unsent uplink packets (store-carry-forward) and flushes them at the next contact
   or at a recovery point (`dock`).
3. Receipts are dual-path: the recipient node forwards a co-signed copy independently of the robot.
4. Every command produced by a neural or language component passes `meshrtc.protocol.validate()`
   before transmission; low confidence or missing slots → the operator is asked to confirm.
5. The comms steward defers downlink below `RELIABLE` priority when the gateway has used its
   36 s / h duty-cycle budget (868 MHz, 1 %).

## Airtime (SHORT_FAST, 16-symbol preamble, CR 4/5)

| Packet | Text | Binary |
|---|---|---|
| TSK | 32 B → 52.9 ms | 11 B → 37.5 ms |
| RCP | 23 B → 45.2 ms | 10 B → 34.9 ms |
| routing ACK | — | 37.5 ms (130 ms MEDIUM_FAST, 477 ms LONG_FAST) |
