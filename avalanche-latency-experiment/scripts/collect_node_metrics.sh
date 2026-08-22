#!/usr/bin/env bash
# One-second node telemetry in the schema the analysis expects
# (run_id, t_s, phase, cpu_pct, mem_mib, disk_p99_ms, queue_depth, blocks_per_s).
#
# This is the fallback collector for hosts without Prometheus. When Prometheus
# is available, export the same columns from deploy/prometheus.yml instead:
# the analysis only cares about the CSV schema, not about its source.
set -euo pipefail

OUT="${1:?output csv path}"
DURATION="${2:?duration in seconds}"
WARMUP_S="${WARMUP_S:-60}"
MEASURE_S="${MEASURE_S:-300}"
RUN_ID="${RUN_ID:-unknown}"
RPC="${RPC_WRITE:-http://127.0.0.1:9650/ext/bc/C/rpc}"

mkdir -p "$(dirname "$OUT")"
echo "run_id,t_s,phase,cpu_pct,mem_mib,disk_p99_ms,queue_depth,blocks_per_s" > "$OUT"

prev_idle=0; prev_total=0; prev_block=0
for ((t = 0; t < DURATION; t++)); do
  read -r _ user nice system idle iowait irq softirq steal _ < /proc/stat
  total=$((user + nice + system + idle + iowait + irq + softirq + steal))
  d_total=$((total - prev_total)); d_idle=$((idle - prev_idle))
  cpu=0
  [ "$d_total" -gt 0 ] && cpu=$(awk "BEGIN{printf \"%.2f\", 100*($d_total-$d_idle)/$d_total}")
  prev_total=$total; prev_idle=$idle

  mem=$(awk '/MemAvailable/{avail=$2} /MemTotal/{tot=$2} END{printf "%.1f", (tot-avail)/1024}' /proc/meminfo)
  disk=$(awk 'NR>2 {if ($10>0) s+=$7/$10} END{printf "%.3f", s}' /proc/diskstats)

  pending=$(curl -s -X POST -H 'content-type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"txpool_status","params":[]}' "$RPC" \
    | grep -o '"pending":"0x[0-9a-f]*"' | grep -o '0x[0-9a-f]*' || true)
  queue=$([ -n "$pending" ] && printf "%d" "$pending" || echo 0)

  block=$(curl -s -X POST -H 'content-type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' "$RPC" \
    | grep -o '0x[0-9a-f]*' || echo 0x0)
  block=$(printf "%d" "$block")
  bps=$((block - prev_block)); [ "$prev_block" -eq 0 ] && bps=0
  prev_block=$block

  if   [ "$t" -lt "$WARMUP_S" ]; then phase=warmup
  elif [ "$t" -lt $((WARMUP_S + MEASURE_S)) ]; then phase=measure
  else phase=drain; fi

  echo "$RUN_ID,$t,$phase,$cpu,$mem,$disk,$queue,$bps" >> "$OUT"
  sleep 1
done
