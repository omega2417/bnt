#!/usr/bin/env bash
set -euo pipefail
BUILD=/home/user/bnt/ustfuse_appendix/build
OUT=/home/user/bnt/ustfuse_appendix/runs/ablation
mkdir -p "$OUT"
echo "seed,config,pd,far,precision,recall,macro_f1,ece,mce,brier,mota,motp,idf1,fragmentation,id_switches,rmse" > "$OUT/ablation_agg.csv"
declare -A CFG=(
 [full]="none"
 [no_quality]="no_quality"
 [no_cross_attn]="no_cross_attn"
 [no_ensemble]="no_ensemble"
 [no_temp]="no_temp"
 [no_semantic]="no_semantic"
 [no_covinfl]="no_covinfl"
 [no_uncertainty]="no_ensemble no_temp"
)
ORDER=(full no_quality no_cross_attn no_ensemble no_temp no_semantic no_covinfl no_uncertainty)
WORK=$(mktemp -d); cd "$WORK"
for seed in $(seq 20260730 20260759); do
  "$BUILD/radartwin" "$seed" 400 >/dev/null
  for name in "${ORDER[@]}"; do
    "$BUILD/ustfuse_ablate" radartwin_measurements.csv "${CFG[$name]}" >/dev/null
    "$BUILD/fusemetrics" >/dev/null
    python3 - "$seed" "$name" "$OUT/ablation_agg.csv" <<'PY'
import sys,csv
seed,name,agg=sys.argv[1],sys.argv[2],sys.argv[3]
d={r['metric']:r['point_estimate'] for r in csv.DictReader(open('fusemetrics_summary.csv'))}
line=[seed,name,d['probability_of_detection'],d['false_alarm_rate'],d['precision'],d['recall'],
 d['macro_f1'],d['ece'],d['mce'],d['brier'],d['mota'],d['motp_m'],d['idf1'],
 d['fragmentation'],d['id_switches'],d['rmse_m']]
open(agg,'a').write(','.join(line)+'\n')
PY
  done
  echo "seed $seed ablations done"
done
rm -rf "$WORK"; echo "ABLATIONS ALL DONE"
