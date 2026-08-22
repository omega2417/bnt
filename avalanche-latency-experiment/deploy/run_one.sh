#!/usr/bin/env bash
# Execute one run of the campaign end to end (protocol section 9).
# Usage: RUN_ID=RUN-0001 CONFIG=C3 TOPOLOGY=T1_vpn LOAD_TPS=100 REPEAT=1 \
#        TRACE_ID=L100-R01 ./run_one.sh
set -euo pipefail

: "${RUN_ID:?}" "${CONFIG:?}" "${TOPOLOGY:?}" "${LOAD_TPS:?}" "${REPEAT:?}" "${TRACE_ID:?}"
WARMUP_S="${WARMUP_S:-60}"
MEASURE_S="${MEASURE_S:-300}"
DRAIN_S="${DRAIN_S:-60}"
OUT_ROOT="${OUT_ROOT:-data/raw}"

mkdir -p "$OUT_ROOT"/{tx,nodes,network,manifests}

echo "[1/8] preflight"
./deploy/preflight.sh

echo "[2/8] passport"
python3 - "$RUN_ID" "$CONFIG" "$TOPOLOGY" "$LOAD_TPS" "$REPEAT" "$TRACE_ID" <<'PY' > "$OUT_ROOT/manifests/$RUN_ID.json"
import hashlib, json, os, platform, subprocess, sys
run_id, config, topology, load_tps, repeat, trace_id = sys.argv[1:7]
def sha(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except OSError:
        return None
def git():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None
print(json.dumps({
    "run_id": run_id, "config": config, "topology": topology,
    "load_tps": int(load_tps), "repeat": int(repeat), "trace_id": trace_id,
    "provenance": "MEASURED",
    "git_commit": git(),
    "host": platform.node(), "platform": platform.platform(),
    "warmup_s": int(os.environ.get("WARMUP_S", 60)),
    "measure_s": int(os.environ.get("MEASURE_S", 300)),
    "drain_s": int(os.environ.get("DRAIN_S", 60)),
    "genesis_sha256": sha(os.environ.get("GENESIS_PATH", "")),
    "chain_config_sha256": sha(os.environ.get("CHAIN_CONFIG_PATH", "")),
    "abi_sha256": sha("contracts/VisibilityProbe.abi.json"),
    "contract_address": os.environ.get("PROBE_CONTRACT"),
    "chain_id": os.environ.get("CHAIN_ID"),
    "subnet_id": os.environ.get("SUBNET_ID"),
    "blockchain_id": os.environ.get("BLOCKCHAIN_ID"),
    "vpn_protocol": os.environ.get("VPN_PROTOCOL"),
    "clock_source": os.environ.get("CLOCK_SOURCE"),
    "data_required": "fill every null before reporting results",
}, indent=2, sort_keys=True))
PY

echo "[3/8] apply configuration profile $CONFIG on every validator"
echo "      (install deploy/chain-configs/${CONFIG}_*.json and restart per your runbook)"

echo "[4/8] topology"
if [ "$TOPOLOGY" = "T2_three_region_emulated" ]; then
  DEV="${NETEM_DEV:?set NETEM_DEV for T2}" DELAY_MS="${NETEM_DELAY_MS:-50}" ./deploy/netem.sh
else
  echo "      no netem for $TOPOLOGY"
fi

echo "[5/8] network probes before the run"
python3 scripts/probe_network.py --phase before --out "$OUT_ROOT/network/${RUN_ID}_probes.json"

echo "[6/8] warm-up ${WARMUP_S}s, measurement ${MEASURE_S}s, drain ${DRAIN_S}s"
scripts/collect_node_metrics.sh "$OUT_ROOT/nodes/${RUN_ID}_resources.csv" \
  $((WARMUP_S + MEASURE_S + DRAIN_S)) &
COLLECTOR=$!
RUN_ID="$RUN_ID" CONFIG="$CONFIG" TOPOLOGY="$TOPOLOGY" LOAD_TPS="$LOAD_TPS" \
  REPEAT="$REPEAT" TRACE_ID="$TRACE_ID" \
  OUT_JSONL="$OUT_ROOT/tx/${RUN_ID}.jsonl" \
  python3 -m alp.client "traces/${TRACE_ID}/${CLIENT_ID:-K00}.csv" --warmup-s "$WARMUP_S"
wait $COLLECTOR

echo "[7/8] network probes after the run, clear shaping"
python3 scripts/probe_network.py --phase after --out "$OUT_ROOT/network/${RUN_ID}_probes.json" --append
if [ "$TOPOLOGY" = "T2_three_region_emulated" ]; then
  sudo tc qdisc del dev "${NETEM_DEV}" root || true
fi

echo "[8/8] hash the artefacts"
python3 -m alp manifest "$OUT_ROOT" --provenance MEASURED
echo "run $RUN_ID complete"
