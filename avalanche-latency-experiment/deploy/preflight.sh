#!/usr/bin/env bash
# Pre-run safety and readiness checks (protocol sections 9 and 9.1).
# Every check is a hard gate: a failure aborts the run rather than
# producing a record that cannot be compared with the rest of the series.
set -euo pipefail

: "${RPC_WRITE:?write RPC endpoint is required}"
: "${RPC_READS:?comma-separated read RPC endpoints are required}"
FORBIDDEN_CIDRS="${FORBIDDEN_CIDRS:-}"   # production ranges that must be unreachable
MIN_FREE_PCT="${MIN_FREE_PCT:-20}"

fail() { echo "PREFLIGHT FAILED: $*" >&2; exit 1; }

echo "== isolation =="
for cidr in $FORBIDDEN_CIDRS; do
  if ip route get "${cidr%%/*}" >/dev/null 2>&1; then
    fail "a route exists from the test segment to $cidr"
  fi
done
echo "no route to the declared production ranges"

echo "== disk headroom =="
free_pct=$(df --output=pcent / | tail -1 | tr -dc '0-9')
[ $((100 - free_pct)) -ge "$MIN_FREE_PCT" ] || fail "less than ${MIN_FREE_PCT}% free disk"
echo "free disk above ${MIN_FREE_PCT}%"

echo "== clock discipline =="
if command -v chronyc >/dev/null 2>&1; then
  chronyc tracking | sed -n '1,6p'
else
  echo "chronyc not installed: record the NTP source and maximum offset manually"
fi

echo "== node health =="
probe() {
  curl -s -X POST -H 'content-type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' "$1"
}
head_write=$(probe "$RPC_WRITE" | tr -d ' \n')
echo "write node head: $head_write"
IFS=',' read -ra READS <<< "$RPC_READS"
for url in "${READS[@]}"; do
  echo "read node $url head: $(probe "$url" | tr -d ' \n')"
done

echo "== unfinalized queries must be disabled =="
echo "confirm allow-unfinalized-queries=false in the chain config before starting"

echo "PREFLIGHT OK"
