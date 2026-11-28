"""Import planned critical operations (denominator of A_op) into the metadata store.

  python import_plan.py --db test.db --plan ops.json --loss 1000

ops.json is a list of [operation_id, due_ts] pairs (as written by make_replay.py) or of objects
{"operation_id", "due_ts", "route_id", "vehicle_node", "cargo_class", "critical", "loss_if_failed"}.

The plan must be imported BEFORE the observation window, so that neither the list of critical operations
nor their due times can be adjusted after the outcomes are known.
`loss_if_failed` is an assumed loss per operation in one currency for all rows (the article uses constant
EUR). It is an input assumption of the analyst, never something this software measures.
"""
import argparse, json, sqlite3
from pathlib import Path

COLS = ("operation_id", "route_id", "vehicle_node", "cargo_class", "critical", "due_ts", "loss_if_failed")

def import_plan(db, plan, default_loss=None):
    db.executescript(Path(__file__).with_name("schema.sql").read_text())
    n = 0
    for row in plan:
        r = dict(zip(("operation_id", "due_ts"), row)) if isinstance(row, (list, tuple)) else dict(row)
        r.setdefault("critical", 1)
        r.setdefault("loss_if_failed", default_loss)
        db.execute(f"INSERT OR REPLACE INTO planned_operation({','.join(COLS)}) VALUES({','.join('?' * len(COLS))})",
                   tuple(r.get(c) for c in COLS))
        n += 1
    db.commit()
    return n

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="logi.db"); ap.add_argument("--plan", required=True)
    ap.add_argument("--loss", type=float, default=None,
                    help="assumed loss per operation, same currency for all rows (article: constant EUR)")
    a = ap.parse_args()
    print(import_plan(sqlite3.connect(a.db), json.load(open(a.plan)), a.loss), "operations imported")
