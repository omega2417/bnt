# Hardware — Bench DT-NODE01-12V

**Status:** design specification of the 12 V physical bench for the mandatory programme of the protocol (§1.2, §4). Characteristics are nominal values from manufacturers' public datasheets. Every item marked ✱ must be checked against the current datasheet revision, the nameplate and the passport of the actual unit before the first physical run, and entered into the bench passport (§21.1). No physical measurements were made in this package: every number marked "EMU" in the protocols comes from emulated equipment with the same characteristics.

## 1. Bill of materials

| # | Function | Real component | Key characteristics used in the calculations | Qty |
|---|---|---|---|---:|
| 1 | Twin, EMS, logging | x86-64 laptop, Ubuntu 24.04 LTS, Python 3.11, Mosquitto 2.x; powered from a UPS | Power independent of the test battery | 1 |
| 2 | Controller (edge guard) | Espressif **ESP32-S3-DevKitC-1** (ESP32-S3-WROOM-1-N8R8) | 2×240 MHz, 3.3 V logic, esp_timer 1 µs; 5 V USB from the PC UPS | 1 |
| 3 | Battery | LiFePO₄ 4S1P **12.8 V / 40 Ah** with a **DALY 4S 12 V 40 A**-class BMS ✱ | V_charge = 14.2 V (CV), OVP 14.6 V, UVP 10.0 V; I_charge ≤ 20 A (0.5C), I_discharge ≤ 40 A; T_charge 0…45 °C ✱ | 1 |
| 4 | Generation source G1 | **RIDEN RD6018** (0–60 V, 0–18 A, Modbus RTU) + **Mean Well RSP-750-48** supply | Set resolution 0.01 V / 0.01 A; CV 14.2 V, CC = P_avail/V every second | 1+1 |
| 5 | Reverse-current protection | **LTC4359** ideal-diode module | Replaces a Schottky diode — minimal loss at M0 | 1 |
| 6 | Critical-branch DC/DC | **Mean Well DDR-60G-12** (in 9–36 V, out 12 V / 5 A) ✱ | Efficiency ≈ 0.88–0.91 (0.90 ± 0.01 assumed); input ≥ 9 V is the availability limit | 1 |
| 7 | Communication node | **MikroTik hAP ac²** router (local HTTP service) ✱ | Actual consumption measured by M3 | 1 |
| 8 | Top-up to 18 W | Electronic load **Korad KEL103** (120 V, 30 A, 300 W, CP mode) or **Rigol DL3021** (150 V, 40 A, 200 W) | CP mode: P_node + P_eload = 18 W at the terminals | 1 |
| 9 | Auxiliary-branch DC/DC | **Mean Well DDR-60G-12** | Same model as item 6 | 1 |
| 10 | Auxiliary load | 12 V / 30 W LED floodlight | Actual consumption measured by M5 | 1 |
| 11 | Auxiliary switch | Automotive relay **Bosch 0 332 019 150** (12 V, 30 A, NO) + **PC817** optocoupler + **ULN2003A** + **1N4007** | Operate time ≈ 10 ms; safe state is open (OFF) | 1 |
| 12 | Meters M0–M5 | **TI INA226** (16-bit, 0–36 V) | Shunt LSB 2.5 µV; range ±81.92 mV; bus LSB 1.25 mV; offset ≤ ±10 µV; gain error ≤ 0.1 % ✱ | 6 |
| 13 | Reference channel REF | **TI INA228** (20-bit, 0–85 V) on a separate Raspberry Pi 4 | Shunt LSB 312.5 nV (±163.84 mV); bus LSB 195.3 µV; offset ≤ ±1 µV; gain error ≤ 0.05 % ✱ | 1 |
| 14 | Shunts M1, REF | Panel shunt **FL-2 50 A / 75 mV**, class 0.5 | R = 1.5 mΩ; P at 20 A = 0.6 W | 2 |
| 15 | Shunt M0 | **FL-2 30 A / 75 mV**, class 0.5 | R = 2.5 mΩ | 1 |
| 16 | Shunts M2–M5 | **FL-2 10 A / 75 mV**, class 0.5 | R = 7.5 mΩ | 4 |
| 17 | Temperature T1/T2 | **Maxim DS18B20** (1-Wire) | ±0.5 °C in −10…+85 °C; resolution 0.0625 °C | 2 |
| 18 | I²C galvanic isolation | **Analog Devices ADuM1250** | Breaks the USB ↔ power-bus ground loop (§5 item 4) | 1 |
| 19 | Independent network client N1 | **Raspberry Pi 4 Model B** on 230 V mains | HTTP request to the node every second; RTT log | 1 (shared with item 13) |
| 20 | Battery fuse | **MIDI 40 A** (DC rated), at the "+" terminal | Selective with the branch fuses | 1 |
| 21 | Branch fuses | **ATO**: generation 25 A, critical 5 A, auxiliary 7.5 A, in DC holders | — | 3 |
| 22 | Emergency disconnect | **Blue Sea Systems 6006** battery switch (m-Series) | Opens battery "+"; logger and PC are powered separately | 1 |
| 23 | Calibration standard | **Fluke 87V** (DCV) + 4-terminal reference shunt with a calibration certificate | Expanded uncertainties from the certificate (placeholder 0.05 % in the configuration) | 1 |
| 24 | Cables, terminals | Copper 6 mm² (battery/generation), 1.5 mm² (branches); crimped lugs | Voltage drop per 1 m, 6 mm², 20 A ≈ 57 mV | — |

## 2. Functional diagram and measurement points

```
 RSP-750-48 → RD6018 (CV 14.2 V / CC) → LTC4359 → [ATO 25A] → [M0: FL-2 30A + INA226] ─┐
                                                                                        │
 LiFePO₄ 12.8 V/40 Ah + BMS → [MIDI 40A] → [Blue Sea 6006] → [M1: FL-2 50A + INA226]   ├── DC BUS
                                           → [REF: FL-2 50A + INA228 → RPi4]            │  (≈ 10.0–14.6 V)
                                                                                        │
   ├─[ATO 5A]─[M2]─ DDR-60G-12 ─[M3]─ hAP ac² ∥ KEL103 (CP)            ← critical branch, never switched by the EMS
   └─[ATO 7.5A]─ Bosch relay (NO) ─[M4]─ DDR-60G-12 ─[M5]─ LED 30 W    ← auxiliary branch, switched by the ESP32

 ESP32-S3 ← I²C (ADuM1250) ← INA226 ×6 (addresses 0x40,0x41,0x44,0x45,0x48,0x49)
 ESP32-S3 → GPIO10 → PC817 → ULN2003A → relay coil (1N4007)
 ESP32-S3 ↔ Wi-Fi (isolated segment) ↔ Mosquitto on the PC ↔ dtpower (twin + EMS)
 RPi4: INA228 (REF) + DS18B20 + HTTP node probe → own log
```

The M1 and REF shunts are in series in the battery "−" lead, so all charge and discharge current passes through both meters and no path (USB, logger ground) bypasses them (§5 item 4). REF has its own shunt, ADC, clock, logger and calibration coefficients, i.e. it is independent of M1 (§8.3).

## 3. Meter selection check from component characteristics

| Channel | Shunt | Expected I_max, A | Full scale, A | Headroom, % | Current LSB, mA | Max shunt power, W | Max shunt voltage, mV |
|---|---|---:|---:|---:|---:|---:|---:|
| M0 | 2.5 mΩ | 18 | 32.8 | 45 | 1.00 | 0.81 | 45 |
| M1 | 1.5 mΩ | 20 | 54.6 | 63 | 1.67 | 0.60 | 30 |
| M2 | 7.5 mΩ | 3 | 10.9 | 73 | 0.33 | 0.07 | 22.5 |
| M3 | 7.5 mΩ | 2 | 10.9 | 82 | 0.33 | 0.03 | 15 |
| M4 | 7.5 mΩ | 4 | 10.9 | 63 | 0.33 | 0.12 | 30 |
| M5 | 7.5 mΩ | 3 | 10.9 | 73 | 0.33 | 0.07 | 22.5 |
| REF | 1.5 mΩ | 20 | 109.2 | 82 | 0.21 | 0.60 | 30 |

Conclusions from the characteristics:

1. The INA226 common-mode range is up to 36 V, so it suits the 12.8 V bus. For S3 (51.2 V, up to 58.4 V when charging) it must be replaced by an INA228 (85 V), and the rating of the whole board must be checked.
2. The INA226 zero offset of ±10 µV on a 1.5 mΩ shunt is up to ±6.7 mA. Uncorrected, this accumulates up to 0.4 pp of SOC drift per 24 h (formula in §9.4), so zero calibration is mandatory.
3. The net bus energy balance closes only if the unmetered self-consumption (≈ 0.35 W: relay, driver, modules) is accounted for. It is determined by a separate pilot measurement.

## 4. Installation rules (condensed from §5)

1. Assemble with the battery disconnected; place the MIDI 40 A fuse no more than 150 mm from the "+" terminal.
2. Feed the relay from the bus through the ATO 7.5 A fuse; never drive the coil directly from a GPIO (always PC817 → ULN2003A).
3. After an ESP32 reset GPIO10 is pulled down and the relay is open, so the auxiliary branch is OFF by default.
4. The critical branch has no controlled switch; only the ATO 5 A fuse and the BMS protect it.
5. The Blue Sea 6006 opens the power circuit; the PC, RPi4 and ESP32 are on a UPS and keep logging.
6. Deliberate short circuits, BMS bypass, overcharge and deep discharge are forbidden; boundary states (E10) are tested only by signal injection.
