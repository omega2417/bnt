#!/usr/bin/env bash
# S4 reference driver. Isolated lab only. Requires the per-run operator kubeconfig.
set -euo pipefail
: "${KUBECONFIG:?provide the per-run operator kubeconfig}"
echo "attack_onset_s=$(date +%s.%N)" | tee -a run.log
kubectl -n dtcr patch deployment analytics-core --type merge \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/hostname":"edge-04"}}}}}' \
  2>&1 | tee -a run.log || true
echo "attack_end_s=$(date +%s.%N)" | tee -a run.log
