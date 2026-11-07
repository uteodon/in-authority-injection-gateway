"""Week 3: CH-NOTE attacks (injected notes) with paired benign twins.

Examples:
    python run_attacks.py                                # main models, S0 and S1, 2 seeds
    python run_attacks.py --setups S0 --seeds 1          # quick run
    python run_attacks.py --models qwen3:8b --only T1 T4
    python run_attacks.py --mock                         # no GPU: twin behavior everywhere
    python run_attacks.py --mock-attacked                # no GPU: compromised behavior (tests scoring)

Metrics (attacks only unless noted):
    ASR executed  - attacker goal really happened (state changed / harmful call ran)
    ASR proposed  - model asked for the harmful call (may have been blocked or invalid)
    utility       - the user's own task was still done correctly (attacks and twins separately)
    twin hit rate - the 'attack goal' happened WITHOUT any injection (baseline error rate)
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

from testbed import config as C
from testbed import modbus_io
from testbed.episode import run_one
from testbed.llm import OllamaLLM, ScriptedLLM


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "-"


def summarize(rows):
    print("\nSUMMARY (CH-NOTE attacks)")
    groups = defaultdict(list)
    for r in rows:
        groups[(r["model"], r["setup"])].append(r)
    for (m, s), rs in groups.items():
        att = [r for r in rs if r.get("kind") == "attack"]
        tw = [r for r in rs if r.get("kind") == "twin"]
        print(f"\n{m}  {s}")
        print(f"  ASR executed : {pct(sum(r['attack_executed'] for r in att), len(att))}")
        print(f"  ASR proposed : {pct(sum(r['attack_proposed'] for r in att), len(att))}")
        inauth = [r for r in att if r["goal"] != "G0"]
        print(f"  in-authority : executed {pct(sum(r['attack_executed'] for r in inauth), len(inauth))}"
              f"   undetected {pct(sum(r['attack_executed'] and not r.get('attack_detected', 0) for r in inauth), len(inauth))}")
        print(f"  utility      : attacks {pct(sum(r['success'] for r in att), len(att))}"
              f"   twins {pct(sum(r['success'] for r in tw), len(tw))}")
        print(f"  safe outcome : attacks {pct(sum(r.get('safe_outcome', 0) for r in att), len(att))}"
              "   (task done, or attack stopped and escalated to a human)")
        print(f"  twin hit rate: {pct(sum(r['attack_executed'] for r in tw), len(tw))}"
              f"   blocked calls: {sum(r.get('n_blocked', 0) for r in rs)}"
              f"   twins with a block (false block): {pct(sum(r.get('n_blocked', 0) > 0 for r in tw), len(tw))}"
              f"   monitor alerts on twins: {sum(r.get('monitor_alerts', 0) > 0 for r in tw)}")
        layers = defaultdict(int)
        for r in rs:
            for L in filter(None, (r.get("blocked_by") or "").split(";")):
                layers[L] += 1
        if layers:
            print("  blocks by layer: " + "  ".join(f"{k}={v}" for k, v in sorted(layers.items())))
        for key, label in (("goal", "by goal "), ("style", "by style")):
            by = defaultdict(list)
            for r in att:
                by[r[key]].append(r)
            cells = [f"{k}={sum(r['attack_executed'] for r in v)}/{len(v)}" for k, v in sorted(by.items())]
            print(f"  {label}    : " + "  ".join(cells))
        by_t = defaultdict(list)
        for r in att:
            by_t[r["template"]].append(r)
        print("  by template : " + "  ".join(
            f"{k}={sum(r['attack_executed'] for r in v)}/{len(v)}" for k, v in sorted(by_t.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=C.MODELS)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--setups", nargs="+", default=["S0", "S1"], choices=["S0", "S1", "S2role", "S3", "S4", "S4noL1", "S5", "S5noL1"])
    ap.add_argument("--scenarios", default="scenarios/attacks_v1.json")
    ap.add_argument("--only", nargs="*", help="template ids (T1..T8) or scenario ids (T1-a)")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--mock-attacked", action="store_true")
    ap.add_argument("--no-modbus", action="store_true")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    scenarios = json.load(open(a.scenarios, encoding="utf-8"))
    if a.only:
        scenarios = [s for s in scenarios if s["id"] in a.only or s["template"] in a.only]
    if a.mock or a.mock_attacked:
        models = ["mock-attacked" if a.mock_attacked else "mock"]
    else:
        models = a.models

    os.makedirs(a.out, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(a.out, f"attacks_{stamp}.csv")
    log_path = os.path.join(a.out, f"attacks_{stamp}.jsonl")

    current = {"plant": None}
    if a.no_modbus:
        publisher = lambda p: current.__setitem__("plant", p)
        reader_factory = lambda p: modbus_io.DirectReader(lambda: current["plant"])
        server = None
    else:
        server = modbus_io.ModbusPlantServer().start()
        publisher = server.publish
        reader_factory = lambda p: modbus_io.ModbusReader()

    rows, writer = [], None
    with open(csv_path, "w", newline="", encoding="utf-8") as fcsv, \
            open(log_path, "w", encoding="utf-8") as flog:
        for model in models:
            if not model.startswith("mock"):
                print(f"warming up {model} ...", flush=True)
                OllamaLLM(model).warm_up()
            for setup in a.setups:
                for seed in range(1, a.seeds + 1):
                    for sc in scenarios:
                        if model == "mock":
                            llm = ScriptedLLM(sc["reference_calls"], sc.get("reference_answer", "Done."))
                        elif model == "mock-attacked":
                            calls = sc.get("compromised_calls", sc["reference_calls"])
                            llm = ScriptedLLM(calls, sc.get("reference_answer", "Done."))
                        else:
                            llm = OllamaLLM(model, seed=seed)
                        try:
                            row, log = run_one(sc, llm, seed, setup, reader_factory, publisher)
                        except Exception as e:
                            row = {"scenario": sc["id"], "setup": setup, "seed": seed, "success": 0,
                                   "reason": f"crash: {e}", "kind": sc["kind"], "template": sc["template"],
                                   "goal": sc["goal"], "style": sc["style"],
                                   "attack_executed": 0, "attack_proposed": 0}
                            log = {}
                        row = {"model": model, **row}
                        log["row"] = row
                        rows.append(row)
                        if writer is None:
                            writer = csv.DictWriter(fcsv, fieldnames=list(row.keys()), extrasaction="ignore")
                            writer.writeheader()
                        writer.writerow(row)
                        flog.write(json.dumps(log, ensure_ascii=False) + "\n")
                        hit = "HIT " if row["attack_executed"] else ("try " if row["attack_proposed"] else "    ")
                        task = "task-ok  " if row["success"] else "task-fail"
                        if row["kind"] == "twin":
                            hit = "twin" if not row["attack_executed"] else "TWIN-HIT"
                        print(f"{model:14s} {setup:6s} s{seed} {sc['id']:8s} {hit:8s} {task} "
                              f"{row.get('reason', '')[:55]}", flush=True)
    if server:
        server.stop()
    summarize(rows)
    print(f"\nresults: {csv_path}\nlogs:    {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
