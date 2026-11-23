"""Run the 13 conditions and write the primary logs (Section 4).

Per condition ``results/logs/<Cx>/`` receives

* ``hidden_states.csv.gz`` - reference log: x_j(t) for every replicate and day
* ``notices.csv.gz``       - reference log: every notice, incl. kind and new state
* ``checks.csv.gz``        - every check: policy, day, slot, component, result, ...
* ``verdicts.csv.gz``      - one row per (replicate, policy, day, service)
* ``trace_summary.csv``    - the evaluator's per-trajectory outcome counts

Files are byte-reproducible: rows are written in a fixed order, numbers with a
fixed format, and gzip members carry no file name and a zero time stamp.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from . import __version__
from .conditions import Condition, load_conditions, load_raw
from .generator import generate
from .policies import POLICIES
from .simulation import evaluate, reference_labels, run_policy

LOG_FILES = ("hidden_states.csv.gz", "notices.csv.gz", "checks.csv.gz", "verdicts.csv.gz", "trace_summary.csv")
SUMMARY_COLUMNS = (
    "condition", "replicate", "policy", "service_days", "false_assured", "false_rejected",
    "correct", "assured_days", "unready_days", "spells", "censored_spells", "max_spell",
    "checks", "FASD", "FUSD",
)


class _GzCsv:
    """Deterministic gzip CSV writer (no file name, mtime = 0, fixed level)."""

    def __init__(self, path: Path, header: Sequence[str]):
        self._raw = open(path, "wb")
        self._gz = gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0, compresslevel=6)
        self._text = io.TextIOWrapper(self._gz, encoding="utf-8", newline="")
        self.writer = csv.writer(self._text, lineterminator="\n")
        self.writer.writerow(header)

    def close(self) -> None:
        self._text.flush()
        self._text.detach()
        self._gz.close()
        self._raw.close()


def run_condition(cond: Condition, out_dir: Path, replicates: Optional[int] = None,
                  write_logs: bool = True) -> List[dict]:
    """Run one condition; returns the trace-summary rows (also written to disk)."""
    R = cond.R if replicates is None else replicates
    op_map, ev_map = cond.maps()
    comps, services = op_map.components, ev_map.service_names
    cdir = Path(out_dir) / "logs" / cond.name
    cdir.mkdir(parents=True, exist_ok=True)

    hidden = notices = checks = verdicts = None
    if write_logs:
        hidden = _GzCsv(cdir / "hidden_states.csv.gz", ("replicate", "day", *comps))
        notices = _GzCsv(cdir / "notices.csv.gz", (
            "replicate", "component", "occurred_day", "delivered_day", "kind", "new_state",
            "delivered_to_operator", "beyond_horizon"))
        checks = _GzCsv(cdir / "checks.csv.gz", (
            "replicate", "policy", "day", "slot", "component", "result", "evidence_age",
            "notice_flag", "influence", "priority"))
        verdicts = _GzCsv(cdir / "verdicts.csv.gz", ("replicate", "policy", "day", "service", "verdict", "reference"))

    rows: List[dict] = []
    for r in range(R):
        traj = generate(cond, r, comps)
        labels = reference_labels(traj, ev_map)
        if write_logs:
            for t in range(1, cond.T + 1):
                hidden.writer.writerow((r, t, *traj.states[t]))
            for n in traj.notices:
                notices.writer.writerow((
                    r, comps[n.component], n.occurred, n.delivered, n.kind,
                    "" if n.new_state is None else n.new_state,
                    int(not n.suppressed and not n.beyond_horizon), int(n.beyond_horizon)))
        for policy in POLICIES:
            log = run_policy(traj, policy, op_map, cond.b, cond.w)
            summ = evaluate(log.verdicts, labels, len(log.checks))
            if write_logs:
                for c in log.checks:
                    checks.writer.writerow((r, policy, c.day, c.slot, comps[c.component], c.result,
                                            c.age, c.notice_flag, c.influence, c.priority))
                for t, (vh, y) in enumerate(zip(log.verdicts, labels), start=1):
                    for s, name in enumerate(services):
                        verdicts.writer.writerow((r, policy, t, name, vh[s], y[s]))
            rows.append({
                "condition": cond.name, "replicate": r, "policy": policy,
                "service_days": summ.service_days, "false_assured": summ.false_assured,
                "false_rejected": summ.false_rejected, "correct": summ.correct,
                "assured_days": summ.assured_days, "unready_days": summ.unready_days,
                "spells": summ.spells, "censored_spells": summ.censored_spells,
                "max_spell": summ.max_spell, "checks": summ.checks,
                "FASD": f"{summ.fasd:.6f}", "FUSD": f"{summ.fusd:.6f}",
            })
    for w in (hidden, notices, checks, verdicts):
        if w is not None:
            w.close()
    with open(cdir / "trace_summary.csv", "w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, SUMMARY_COLUMNS, lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)
    return rows


def _worker(args):
    cond, out_dir, replicates, write_logs = args
    t0 = time.time()
    run_condition(cond, Path(out_dir), replicates, write_logs)
    return cond.name, time.time() - t0


def environment() -> dict:
    import numpy

    return {
        "package": "recovery-evidence",
        "package_version": __version__,
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "numpy": numpy.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def run_experiment(out_dir: Path, conditions: Optional[Iterable[str]] = None,
                   replicates: Optional[int] = None, jobs: Optional[int] = None,
                   write_logs: bool = True, quiet: bool = False) -> None:
    """Run the selected conditions (all by default) and write the run manifest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(conditions) if conditions else None
    conds = [c for c in load_conditions() if wanted is None or c.name in wanted]
    if wanted and len(conds) != len(wanted):
        raise SystemExit(f"unknown condition in {sorted(wanted)}")
    jobs = jobs or min(len(conds), os.cpu_count() or 1)
    started = time.time()
    tasks = [(c, str(out_dir), replicates, write_logs) for c in conds]
    if jobs <= 1:
        done = [_worker(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            done = list(pool.map(_worker, tasks))
    if not quiet:
        for name, secs in done:
            print(f"  {name:<4} done in {secs:5.1f} s")
    # resolved configuration (deterministic) and run manifest (holds the UTC time)
    resolved = {"schema": load_raw()["schema"], "conditions": [c.to_dict() for c in load_conditions()]}
    (out_dir / "parameters.json").write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "wall_seconds": round(time.time() - started, 1),
        "conditions": [c.name for c in conds],
        "replicates_override": replicates,
        "logs_written": write_logs,
        "environment": environment(),
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
