#!/usr/bin/env bash
# S2 reference driver. Isolated lab only. Runs the four sub-cases in sequence,
# logging a separate onset per sub-case so each is scored independently.
set -euo pipefail
BROKER=mosquitto.lab; TOPIC="dtcr/sensor-07/telemetry"
log(){ echo "$1=$(date +%s.%N)" | tee -a run.log; }
log subcase_replay_onset_s
mosquitto_pub -h "$BROKER" -p 8883 --cafile ca.crt -t "$TOPIC" -f captured_valid_record.bin
log subcase_injection_onset_s
mosquitto_pub -h "$BROKER" -p 8883 -t "$TOPIC" -m '{"temp":21.4,"seq":99999}'  # no client cert
log subcase_modification_onset_s
python3 tamper_in_transit.py --stream "$TOPIC" --flip-bytes 8
log subcase_semantic_onset_s
python3 semantic_falsify.py --sensor sensor-07 --value 21.4 --true-value 63.9 --count 60 --interval 2
log attack_end_s
