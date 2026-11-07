"""Week 2: clean (no attack) task success for each model.

Examples:
    python run_benign.py                                  # both main models, 3 seeds
    python run_benign.py --models qwen3:8b --seeds 1
    python run_benign.py --mock                            # no GPU: replay reference calls
    python run_benign.py --no-modbus                       # read sensors directly (debug)
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

from testbed import config as C
from testbed.episode import run_one
from testbed.llm import OllamaLLM, ScriptedLLM
from testbed import modbus_io


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=C.MODELS)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--setup", default="S0", choices=["S0", "S1", "S2role", "S3", "S4", "S4noL1", "S5", "S5noL1"])
    ap.add_argument("--scenarios", default="scenarios/benign_v1.json")
    ap.add_argument("--only", nargs="*", help="scenario ids to run, e.g. B03 B07")
    ap.add_argument("--mock", action="store_true", help="replay reference calls instead of a model")
    ap.add_argument("--no-modbus", action="store_true")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    scenarios = json.load(open(a.scenarios, encoding="utf-8"))
    if a.only:
        scenarios = [s for s in scenarios if s["id"] in a.only]
    models = ["mock"] if a.mock else a.models

    os.makedirs(a.out, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(a.out, f"benign_{a.setup}_{stamp}.csv")
    log_path = os.path.join(a.out, f"benign_{a.setup}_{stamp}.jsonl")

    current = {"plant": None}
    if a.no_modbus:
        publisher = lambda p: current.__setitem__("plant", p)
        reader_factory = lambda p: modbus_io.DirectReader(lambda: current["plant"])
        server = None
    else:
        server = modbus_io.ModbusPlantServer().start()
        publisher = server.publish
        reader_factory = lambda p: modbus_io.ModbusReader()

    rows = []
    with open(csv_path, "w", newline="", encoding="utf-8") as fcsv, \
            open(log_path, "w", encoding="utf-8") as flog:
        writer = None
        for model in models:
            if model != "mock":
                print(f"warming up {model} ...", flush=True)
                OllamaLLM(model).warm_up()
            for seed in range(1, a.seeds + 1):
                for sc in scenarios:
                    llm = (ScriptedLLM(sc["reference_calls"], sc.get("reference_answer", "Done.")) if model == "mock"
                           else OllamaLLM(model, seed=seed))
                    try:
                        row, log = run_one(sc, llm, seed, a.setup, reader_factory, publisher)
                    except Exception as e:
                        row = {"scenario": sc["id"], "category": sc.get("category", ""),
                               "setup": a.setup, "seed": seed, "success": 0,
                               "reason": f"crash: {e}"}
                        log = {"row": row}
                    row = {"model": model, **row}
                    log["row"] = row
                    rows.append(row)
                    if writer is None:
                        writer = csv.DictWriter(fcsv, fieldnames=list(row.keys()), extrasaction="ignore")
                        writer.writeheader()
                    writer.writerow(row)
                    flog.write(json.dumps(log, ensure_ascii=False) + "\n")
                    mark = "OK  " if row["success"] else "FAIL"
                    print(f"{model:15s} seed{seed} {sc['id']} {mark} {row.get('reason','')[:70]}"
                          f"  ({row.get('steps','-')} steps, {row.get('wall_s','-')}s)", flush=True)
    if server:
        server.stop()

    print("\nSUMMARY (clean task success)")
    by = defaultdict(list)
    for r in rows:
        by[r["model"]].append(r)
    for m, rs in by.items():
        n = len(rs)
        succ = sum(r["success"] for r in rs)
        inval = sum(r.get("n_invalid", 0) for r in rs)
        fixes = sum(r.get("n_fixes", 0) for r in rs)
        skipped = sum(r.get("n_skipped", 0) for r in rs)
        wall = sum(r.get("wall_s", 0) or 0 for r in rs) / n
        print(f"{m:15s} {succ}/{n} ({100*succ/n:.0f}%)  invalid calls: {inval}  format fixes: {fixes}  skipped parallel calls: {skipped}"
              f"  mean time/task: {wall:.1f}s")
        fails = [f"{r['scenario']}:{r['reason'][:40]}" for r in rs if not r["success"]]
        if fails:
            print("   failures:", "; ".join(fails[:12]))
    print(f"\nresults: {csv_path}\nlogs:    {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
