#!/usr/bin/env bash
# 30-repetition harness: S1 -> S2 -> S3 across fixed seeds 20260730..20260759.
# Keeps per-seed metric CSVs + checksums; big raw CSVs kept only for the reference seed.
set -euo pipefail
BUILD=/home/user/bnt/ustfuse_appendix/build
OUT=/home/user/bnt/ustfuse_appendix/runs
REF=20260730
NSCEN=400
WORK=$(mktemp -d)
cd "$WORK"
echo "seed,pd,far,precision,recall,macro_f1,ece,mce,brier,mota,motp,idf1,fragmentation,id_switches,rmse,lat_mean,lat_p95,pd_ci_lo,pd_ci_hi,f1_ci_lo,f1_ci_hi,ece_ci_lo,ece_ci_hi,mota_ci_lo,mota_ci_hi" > "$OUT/aggregate_summary.csv"
: > "$OUT/checksums.csv"
echo "seed,file,md5,rows" >> "$OUT/checksums.csv"
for seed in $(seq 20260730 20260759); do
  "$BUILD/radartwin" "$seed" "$NSCEN" >/dev/null
  "$BUILD/ustfuse" radartwin_measurements.csv >/dev/null
  "$BUILD/fusemetrics" >/dev/null
  # checksums + row counts
  for fj in radartwin_measurements.csv radartwin_truth.csv ustfuse_classifications.csv ustfuse_tracks.csv fusemetrics_summary.csv; do
    md5=$(md5sum "$fj" | awk '{print $1}')
    rows=$(wc -l < "$fj")
    echo "$seed,$fj,$md5,$rows" >> "$OUT/checksums.csv"
  done
  # extract metrics from summary.csv
  python3 - "$seed" "$OUT/aggregate_summary.csv" <<'PY'
import sys,csv
seed=sys.argv[1]; agg=sys.argv[2]
d={}
with open('fusemetrics_summary.csv') as f:
    r=csv.DictReader(f)
    for row in r: d[row['metric']]=row
def pe(m): return d[m]['point_estimate']
def ci(m):
    return (d[m]['ci95_low'], d[m]['ci95_high']) if d[m]['ci95_low'] else ('','')
pdlo,pdhi=ci('probability_of_detection'); f1lo,f1hi=ci('macro_f1')
elo,ehi=ci('ece'); mlo,mhi=ci('mota')
line=[seed,pe('probability_of_detection'),pe('false_alarm_rate'),pe('precision'),pe('recall'),
 pe('macro_f1'),pe('ece'),pe('mce'),pe('brier'),pe('mota'),pe('motp_m'),pe('idf1'),
 pe('fragmentation'),pe('id_switches'),pe('rmse_m'),pe('latency_mean_ms'),pe('latency_p95_ms'),
 pdlo,pdhi,f1lo,f1hi,elo,ehi,mlo,mhi]
with open(agg,'a') as f: f.write(','.join(map(str,line))+'\n')
PY
  # keep reference seed's full outputs + per-seed small files
  if [ "$seed" = "$REF" ]; then
    mkdir -p "$OUT/reference_$seed"
    cp radartwin_measurements.csv radartwin_truth.csv radartwin_scenarios.json \
       ustfuse_classifications.csv ustfuse_tracks.csv \
       fusemetrics_summary.csv fusemetrics_comparison.csv fusemetrics_ablation.csv \
       fusemetrics_significance.csv fusemetrics_table.tex fusemetrics_f1_vs_snr.svg \
       "$OUT/reference_$seed/"
  fi
  mkdir -p "$OUT/seed_$seed"
  cp fusemetrics_summary.csv fusemetrics_comparison.csv fusemetrics_ablation.csv fusemetrics_significance.csv "$OUT/seed_$seed/"
  echo "seed $seed done: $(grep '^macro_f1' fusemetrics_summary.csv)"
done
rm -rf "$WORK"
echo "ALL DONE"
