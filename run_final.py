"""Final runs: every number in the paper comes from this script and one frozen code version.

    python run_final.py                 # full plan (about 6-7 h); safe to stop and restart
    python run_final.py --summary-only  # rebuild the tables from what is already done
    python run_final.py --mock          # 1-minute plumbing test without a GPU

Resume: every finished episode is appended to results/final/rows.jsonl. On restart the script
skips finished episodes and continues. If the code changed in between, it stops and says so.
Output: results/final/summary.md and summary.csv (rates with 95% CIs and Holm-corrected tests).
"""
import argparse
import glob
import hashlib
import json
import math
import os
import random
import sys
import time
import urllib.request
from collections import defaultdict

from testbed import config as C
from testbed import modbus_io
from testbed.episode import run_one
from testbed.llm import OllamaLLM, ScriptedLLM

SETS = {"benign": "scenarios/benign_v1.json",
        "notes": "scenarios/attacks_v1.json",
        "sensor": "scenarios/sensor_v1.json"}
MAIN_MODELS = ["qwen3:8b", "granite4.1:8b"]
BIG_MODELS = ["qwen3:14b"]
SETUPS_MAIN = {"benign": ["S0", "S5", "S5noL1"],
               "notes": ["S0", "S1", "S3", "S4", "S5", "S5noL1"],
               "sensor": ["S0", "S3", "S4", "S5", "S5noL1"]}
SETUPS_BIG = {"benign": ["S0", "S5"], "notes": ["S0", "S3", "S5"], "sensor": ["S0", "S3", "S5"]}
SEEDS = 3
COMPARE = [("S0", "S5"), ("S3", "S5"), ("S5noL1", "S5")]   # tested pairs, in-authority undetected ASR

# Held-out check (run after the final runs): new attacks, defense code must be unchanged.
FROZEN_FINAL = "a598192a76ca"            # code version of the final runs
SETS_HO = {"heldout": "scenarios/heldout_v1.json"}
SETUPS_MAIN_HO = {"heldout": ["S0", "S3", "S5noL1"]}
SETUPS_BIG_HO = {"heldout": ["S0", "S5noL1"]}
SEEDS_HO = 2
COMPARE_HO = [("S0", "S5noL1"), ("S3", "S5noL1")]


# ------------------------------------------------------------------ helpers
def code_hash(sets=None):
    h = hashlib.sha256()
    for f in sorted(glob.glob("testbed/*.py") + list((sets or SETS).values())):
        h.update(open(f, "rb").read())
    return h.hexdigest()[:12]


def ollama_ok(models):
    try:
        with urllib.request.urlopen(C.OLLAMA_URL.replace("/api/chat", "/api/tags"), timeout=10) as r:
            have = {m["name"] for m in json.loads(r.read())["models"]}
    except OSError:
        print("\nOllama is not running (Ollama kapali). Start the Ollama app, then run again.")
        return False
    missing = [m for m in models if m not in have and m + ":latest" not in have]
    if missing:
        print(f"\nMissing models (eksik modeller): {missing}. Run: ollama pull <name>")
        return False
    return True


def plan(models, seeds, heldout=False):
    jobs = []
    sets = SETS_HO if heldout else SETS
    for m in models:
        if heldout:
            table = SETUPS_BIG_HO if m in BIG_MODELS else SETUPS_MAIN_HO
        else:
            table = SETUPS_BIG if m in BIG_MODELS else SETUPS_MAIN
        for set_name, path in sets.items():
            scen = json.load(open(path, encoding="utf-8"))
            for setup in table[set_name]:
                for seed in range(1, seeds + 1):
                    for sc in scen:
                        jobs.append((m, set_name, setup, seed, sc))
    return jobs


def key(m, s, st, seed, sid):
    return f"{m}|{s}|{st}|{seed}|{sid}"


# ------------------------------------------------------------------ statistics (no extra packages)
def boot_ci(rows, val, n_boot=2000, rng=None):
    """Cluster bootstrap over scenarios (seeds of one scenario stay together)."""
    if not rows:
        return None, None, None
    rng = rng or random.Random(0)
    by = defaultdict(list)
    for r in rows:
        by[r["scenario"]].append(val(r))
    groups = list(by.values())
    point = sum(sum(g) for g in groups) / sum(len(g) for g in groups)
    stats = []
    for _ in range(n_boot):
        pick = [groups[rng.randrange(len(groups))] for _ in groups]
        stats.append(sum(sum(g) for g in pick) / sum(len(g) for g in pick))
    stats.sort()
    return point, stats[int(0.025 * n_boot)], stats[int(0.975 * n_boot) - 1]


def fisher(a, n1, b, n2):
    """Two-sided Fisher exact test for a/n1 vs b/n2."""
    k, n = a + b, n1 + n2

    def p(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    obs = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, k - n2), min(k, n1) + 1) if p(x) <= obs * (1 + 1e-9)))


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, run = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = run
    return adj


def fmt(ci):
    p, lo, hi = ci
    return "-" if p is None else f"{100 * p:.0f}% [{100 * lo:.0f}-{100 * hi:.0f}]"


def summarize(out_dir, compare=None):
    compare = compare or COMPARE
    rows = [json.loads(l) for l in open(os.path.join(out_dir, "rows.jsonl"), encoding="utf-8")
            if l.strip()]
    rows = [r for r in rows if not r.get("crash")]
    rng = random.Random(0)
    md, csv = [], ["set,model,setup,metric,rate,ci_low,ci_high,n"]

    def add_csv(s, m, st, name, ci, n):
        if ci[0] is not None:
            csv.append(f"{s},{m},{st},{name},{ci[0]:.4f},{ci[1]:.4f},{ci[2]:.4f},{n}")

    groups = defaultdict(list)
    for r in rows:
        groups[(r["set"], r["model"], r["setup"])].append(r)
    models = sorted({r["model"] for r in rows}, key=lambda m: (m in BIG_MODELS, m))
    order = ["S0", "S1", "S3", "S4", "S5", "S5noL1"]

    md.append(f"# Final results\n\ncode version `{json.load(open(os.path.join(out_dir, 'manifest.json')))['code']}`,"
              f" {len(rows)} episodes. Rates with 95% cluster-bootstrap CIs (scenarios resampled).\n")
    md.append("## Clean tasks (benign set)\n\n| Model | Setup | Task success | Episodes with a block | n |\n|---|---|---|---|---|")
    for m in models:
        for st in order:
            rs = groups.get(("benign", m, st))
            if not rs:
                continue
            a, b = boot_ci(rs, lambda r: r["success"], rng=rng), boot_ci(rs, lambda r: int(r.get("n_blocked", 0) > 0), rng=rng)
            md.append(f"| {m} | {st} | {fmt(a)} | {fmt(b)} | {len(rs)} |")
            add_csv("benign", m, st, "success", a, len(rs)); add_csv("benign", m, st, "blocked", b, len(rs))

    tests = []
    attack_sets = [x for x in ("notes", "sensor", "heldout") if any(r["set"] == x for r in rows)]
    for s in attack_sets:
        md.append(f"\n## Attacks: {s}\n\n| Model | Setup | In-authority executed | In-authority undetected | "
                  "G0 executed | Safe outcome (attacks) | Utility (attacks) | Utility (twins) | Twins with a block | n attacks |\n"
                  "|---|---|---|---|---|---|---|---|---|---|")
        for m in models:
            for st in order:
                rs = groups.get((s, m, st))
                if not rs:
                    continue
                att = [r for r in rs if r["kind"] == "attack"]
                ina = [r for r in att if r["goal"] != "G0"]
                g0 = [r for r in att if r["goal"] == "G0"]
                tw = [r for r in rs if r["kind"] == "twin"]
                c = {"ina_exec": boot_ci(ina, lambda r: r["attack_executed"], rng=rng),
                     "ina_undet": boot_ci(ina, lambda r: int(r["attack_executed"] and not r.get("attack_detected", 0)), rng=rng),
                     "g0_exec": boot_ci(g0, lambda r: r["attack_executed"], rng=rng),
                     "safe": boot_ci(att, lambda r: r.get("safe_outcome", r["success"]), rng=rng),
                     "util_att": boot_ci(att, lambda r: r["success"], rng=rng),
                     "util_twin": boot_ci(tw, lambda r: r["success"], rng=rng),
                     "twin_block": boot_ci(tw, lambda r: int(r.get("n_blocked", 0) > 0), rng=rng)}
                md.append(f"| {m} | {st} | " + " | ".join(fmt(c[k]) for k in c) + f" | {len(att)} |")
                for k, v in c.items():
                    add_csv(s, m, st, k, v, len(att))
        for m in models:
            for a_st, b_st in compare:
                A, B = groups.get((s, m, a_st)), groups.get((s, m, b_st))
                if not A or not B:
                    continue
                f = lambda rs: [int(r["attack_executed"] and not r.get("attack_detected", 0))
                                for r in rs if r["kind"] == "attack" and r["goal"] != "G0"]
                xa, xb = f(A), f(B)
                tests.append((s, m, a_st, b_st, sum(xa), len(xa), sum(xb), len(xb),
                              fisher(sum(xa), len(xa), sum(xb), len(xb))))
    if "heldout" in attack_sets:
        scen = {x["id"]: x for x in json.load(open(SETS_HO["heldout"], encoding="utf-8"))}
        md.append("\n## Held-out: pre-registered prediction vs. observed (attacks, per template)\n\n"
                  "| Template | Prediction (S5noL1) | Model | S0 executed | S5noL1 executed | S5noL1 undetected | S5noL1 blocked calls |\n"
                  "|---|---|---|---|---|---|---|")
        for tid in sorted({x["template"] for x in scen.values()}):
            pred = next(x["prediction"] for x in scen.values() if x["template"] == tid)
            for m in models:
                a0 = [r for r in groups.get(("heldout", m, "S0"), []) if r["kind"] == "attack" and r["scenario"].startswith(tid + "-")]
                a5 = [r for r in groups.get(("heldout", m, "S5noL1"), []) if r["kind"] == "attack" and r["scenario"].startswith(tid + "-")]
                if not a5:
                    continue
                md.append(f"| {tid} | {pred} | {m} | {sum(r['attack_executed'] for r in a0)}/{len(a0)} | "
                          f"{sum(r['attack_executed'] for r in a5)}/{len(a5)} | "
                          f"{sum(r['attack_executed'] and not r.get('attack_detected', 0) for r in a5)}/{len(a5)} | "
                          f"{sum(r.get('n_blocked', 0) for r in a5)} |")
    if tests:
        adj = holm([t[-1] for t in tests])
        md.append("\n## Tests: in-authority undetected ASR (Fisher exact, Holm-corrected over all rows)\n\n"
                  "| Set | Model | Comparison | A | B | p | p (Holm) |\n|---|---|---|---|---|---|---|")
        for t, pa in zip(tests, adj):
            s, m, a_st, b_st, xa, na, xb, nb, p = t
            md.append(f"| {s} | {m} | {a_st} vs {b_st} | {xa}/{na} | {xb}/{nb} | {p:.3g} | {pa:.3g} |")
        md.append("\nNote: seeds of one scenario are correlated, so the Fisher p-values are optimistic; "
                  "the cluster-bootstrap CIs above are the more conservative view.")
    nud = sum(r.get("n_nudges", 0) for r in rows)
    md.append(f"\nContinue-nudges used: {nud} in {len(rows)} episodes. "
              f"Crashed episodes excluded: see rows.jsonl.")
    open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    open(os.path.join(out_dir, "summary.csv"), "w", encoding="utf-8").write("\n".join(csv) + "\n")
    print("\n".join(md))
    print(f"\nwritten: {out_dir}/summary.md and summary.csv")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=MAIN_MODELS + BIG_MODELS)
    ap.add_argument("--seeds", type=int, default=SEEDS)
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--mock", action="store_true", help="plumbing test with scripted model, no GPU")
    ap.add_argument("--heldout", action="store_true", help="held-out attack check (after the final runs)")
    ap.add_argument("--mock-attacked", action="store_true", help="held-out plumbing test with compromised calls")
    a = ap.parse_args()

    if a.heldout:
        if code_hash() != FROZEN_FINAL:
            print(f"Defense code differs from the final runs ({code_hash()} != {FROZEN_FINAL}). "
                  "The held-out check must use the frozen code.")
            return 1
        if a.seeds == SEEDS:
            a.seeds = SEEDS_HO
    mock = a.mock or a.mock_attacked
    name = ("heldout" if a.heldout else "final") + ("_mock" if mock else "")
    out_dir = os.path.join("results", name)
    compare = COMPARE_HO if a.heldout else COMPARE
    os.makedirs(out_dir, exist_ok=True)
    rows_path, logs_path = os.path.join(out_dir, "rows.jsonl"), os.path.join(out_dir, "logs.jsonl")
    man_path = os.path.join(out_dir, "manifest.json")

    if a.summary_only:
        summarize(out_dir, compare)
        return 0

    h = code_hash(SETS_HO if a.heldout else None)
    if os.path.exists(man_path):
        old = json.load(open(man_path))["code"]
        if old != h:
            print(f"Code changed since this run started ({old} -> {h}). Results would mix versions.\n"
                  f"Move or delete {out_dir} to start over, or restore the old code.")
            return 1
    else:
        json.dump({"code": h, "started": time.strftime("%Y-%m-%d %H:%M"), "models": a.models,
                   "seeds": a.seeds}, open(man_path, "w"))

    models = ["mock"] if mock else a.models
    if not mock and not ollama_ok(models):
        return 1
    if mock:
        jobs = [("mock", s, st, seed, sc) for (_, s, st, seed, sc) in plan(["qwen3:8b"], 1, a.heldout)]
    else:
        jobs = plan(models, a.seeds, a.heldout)

    done = set()
    if os.path.exists(rows_path):
        for l in open(rows_path, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                if not r.get("crash"):
                    done.add(key(r["model"], r["set"], r["setup"], r["seed"], r["scenario"]))
    todo = [j for j in jobs if key(j[0], j[1], j[2], j[3], j[4]["id"]) not in done]
    print(f"plan: {len(jobs)} episodes, already done: {len(jobs) - len(todo)}, to run: {len(todo)}")

    server = modbus_io.ModbusPlantServer().start()
    reader_factory = lambda p: modbus_io.ModbusReader()
    t_start, n_run, current_model = time.time(), 0, None
    try:
        with open(rows_path, "a", encoding="utf-8") as fr, open(logs_path, "a", encoding="utf-8") as fl:
            for m, s, st, seed, sc in todo:
                if m != current_model and m != "mock":
                    print(f"\nwarming up {m} ...", flush=True)
                    OllamaLLM(m).warm_up()
                current_model = m
                if m == "mock":
                    calls = sc.get("compromised_calls", sc["reference_calls"]) if a.mock_attacked else sc["reference_calls"]
                    llm = ScriptedLLM(calls, sc.get("reference_answer", "Done."))
                else:
                    llm = OllamaLLM(m, seed=seed)
                try:
                    row, log = run_one(sc, llm, seed, st, reader_factory, server.publish, nudge=True)
                except Exception as e:  # keep going; crashed episodes are retried on the next start
                    row, log = {"scenario": sc["id"], "success": 0, "crash": str(e)[:200]}, {}
                row.update(model=m, set=s, setup=st, seed=seed, scenario=sc["id"],
                           kind=sc.get("kind", "benign"), goal=sc.get("goal", ""))
                fr.write(json.dumps(row, ensure_ascii=False) + "\n"); fr.flush()
                log["row"] = row
                fl.write(json.dumps(log, ensure_ascii=False) + "\n")
                n_run += 1
                if n_run % 10 == 0 or n_run == len(todo):
                    el = time.time() - t_start
                    eta = el / n_run * (len(todo) - n_run)
                    print(f"[{time.strftime('%H:%M')}] {n_run}/{len(todo)}  now: {m} {s} {st} seed{seed}"
                          f"  left: ~{eta / 3600:.1f} h", flush=True)
    except KeyboardInterrupt:
        print("\nstopped. Run the same command again to continue where it stopped.")
        return 0
    finally:
        server.stop()
    summarize(out_dir, compare)
    return 0


if __name__ == "__main__":
    sys.exit(main())
