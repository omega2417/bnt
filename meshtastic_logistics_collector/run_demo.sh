#!/bin/sh
# End-to-end software check on GENERATED test input (no radio hardware, no measurements).
# The numbers printed at the end describe make_replay.py, not a Meshtastic network.
set -e
cd "$(dirname "$0")"
rm -f test.db test.db-wal test.db-shm
python3 make_replay.py
python3 collector.py --replay packets.jsonl --db test.db
python3 import_plan.py --db test.db --plan ops.json --loss 1000
python3 kpi.py --db test.db --from 1800000000 --to 1800021600
echo "NOTE: synthetic software check only - see \"provenance\" above. Not a measurement." >&2
