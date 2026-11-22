"""v2 runs (after the advisor's review). The gateway rules are the frozen ones; this is checked.

Phases (each can be run, stopped and resumed on its own):
  main  Qwen3 8B + Granite 4.1 8B, 3 seeds
        new sets: adaptive (gateway-aware, 24 attacks + 12 twins), encoded (20 + 4 twins),
                  benign v2 (45 tasks)  under S0, S3, S5noL1, S6pg (classifier), S7camel (CaMeL-style)
        old sets: notes (attacks_v1) and sensor (sensor_v1) under S6pg and S7camel; the S0/S3/S5noL1
                  rows of the same scenarios and seeds come from results/final
  size  Qwen3 1.7B / 4B / 8B / 14B, thinking off and on, 2 seeds: notes + benign v1 under S0, S5noL1
  t8    T8-d and its twin, Qwen3 14B and 8B, thinking off/on x continue-nudge on/off, 12 seeds, S0

    python run_v2.py --phase main            # about 10-11 h on an RTX 4060 Ti
    python run_v2.py --phase size            # about 5-6 h (thinking runs reduced, see PHASES)
    python run_v2.py --phase t8              # about 1-2 h
    python run_v2.py --phase main --mock     # 1-minute plumbing test, no GPU
    python run_v2.py --phase main --summary-only
S6pg needs:  pip install transformers torch   and, for Prompt Guard 2, a Hugging Face login
             (huggingface-cli login) with the Llama license accepted. Without it the ungated
             ProtectAI classifier is used and the summary says so.
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import time
import urllib.request
from collections import defaultdict

from testbed import config as C
from testbed import episode as EP
from testbed import modbus_io
from testbed.episode import run_one
from testbed.llm import OllamaLLM, ScriptedLLM

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis"))
import reanalyze as RA  # noqa: E402

FROZEN_GATEWAY = "8713b1603015"   # sha256(defenses.py + gateway.py) of the frozen version a598192a76ca
SETS = {"adaptive": "scenarios/adaptive_v1.json", "encoded": "scenarios/encoded_v1.json",
        "benign2": "scenarios/benign_v2.json", "notes": "scenarios/attacks_v1.json",
        "sensor": "scenarios/sensor_v1.json", "benign": "scenarios/benign_v1.json"}
ALL5 = ["S0", "S3", "S5noL1", "S6pg", "S7camel"]
PHASES = {
    "main": dict(models=["qwen3:8b", "granite4.1:8b"], seeds=3, nudge=[True],
                 sets={"adaptive": ALL5, "encoded": ALL5, "benign2": ALL5,
                       "notes": ["S6pg", "S7camel"], "sensor": ["S6pg", "S7camel"]}),
    # qwen3:4b in Ollama now points to Qwen3-4B-Thinking-2507 (thinking only, 256K context);
    # the original hybrid Qwen3-4B, like 1.7B/8B/14B, is the tag 4b-q4_K_M.
    "size": dict(models=["qwen3:1.7b", "qwen3:1.7b@think", "qwen3:4b-q4_K_M", "qwen3:4b-q4_K_M@think",
                         "qwen3:8b", "qwen3:8b@think", "qwen3:14b", "qwen3:14b@think"],
                 seeds=2, nudge=[True], sets={"notes": ["S0", "S5noL1"], "benign": ["S0", "S5noL1"]},
                 # thinking mode is ~10x slower: 1 seed, no gateway (S0), note attacks + their twins
                 # + benign v1 (so utility is measured too). The gateway does not depend on the model,
                 # and t8 covers 8B/14B thinking with 12 seeds.
                 think_override=dict(seeds=1, sets={"notes": ["S0"], "benign": ["S0"]})),
    "t8": dict(models=["qwen3:14b", "qwen3:14b@think", "qwen3:8b", "qwen3:8b@think"], seeds=12,
               nudge=[True, False], sets={"notes": ["S0"]}, only=["T8-d", "T8-twin"]),
}


def gateway_hash():
    h = hashlib.sha256()
    for f in ["testbed/defenses.py", "testbed/gateway.py"]:
        h.update(open(f, "rb").read())
    return h.hexdigest()[:12]


def code_hash(phase):
    h = hashlib.sha256()
    files = sorted(glob.glob("testbed/*.py")) + sorted(SETS[s] for s in PHASES[phase]["sets"])
    for f in files:
        h.update(open(f, "rb").read())
    return h.hexdigest()[:12]


def base_model(m):
    return m.split("@")[0]


def ollama_ok(models):
    try:
        with urllib.request.urlopen(C.OLLAMA_URL.replace("/api/chat", "/api/tags"), timeout=10) as r:
            have = {m["name"] for m in json.loads(r.read())["models"]}
    except OSError:
        print("\nOllama is not running (Ollama kapali). Start the Ollama app, then run again.")
        return False
    missing = sorted({base_model(m) for m in models} - have - {h.replace(":latest", "") for h in have})
    if missing:
        print(f"\nMissing models (eksik modeller): {missing}. Run: ollama pull <name>")
        return False
    return True


def plan(phase, models, seeds):
    P = PHASES[phase]
    jobs = []
    for m in models:
        ov = P.get("think_override") if "@think" in m else None
        sets = ov["sets"] if ov else P["sets"]
        n_seeds = min(seeds, ov["seeds"]) if ov else seeds
        for set_name, setups in sets.items():
            scen = json.load(open(SETS[set_name], encoding="utf-8"))
            if P.get("only"):
                scen = [s for s in scen if s["id"] in P["only"]]
            if ov and ov.get("attacks_only"):
                scen = [s for s in scen if s.get("kind") == "attack"]
            for setup in setups:
                for nudge in P["nudge"]:
                    for seed in range(1, n_seeds + 1):
                        for sc in scen:
                            jobs.append((m, set_name, setup, seed, nudge, sc))
    return jobs


def key(m, s, st, seed, nudge, sid):
    return f"{m}|{s}|{st}|{seed}|{int(nudge)}|{sid}"


# ------------------------------------------------------------------ summary
def load_rows(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []


def three_way(L):
    c = defaultdict(int)
    for r in L:
        c[RA.outcome(r)] += 1
    return c


def pct(a, n):
    return f"{a}/{n} ({100 * a / n:.0f}%)" if n else "–"


def summarize(phase, out_dir):
    rows = [r for r in load_rows(os.path.join(out_dir, "rows.jsonl")) if not r.get("crash")]
    dropped = [r for r in rows if r["model"] not in PHASES[phase]["models"] and r["model"] != "mock"]
    rows = [r for r in rows if r not in dropped]
    md = [f"# v2 results: phase {phase}\n", f"Episodes: {len(rows)}\n"]
    if dropped:
        md.append(f"(left out of this summary: {len(dropped)} rows of models no longer in the plan: "
                  f"{sorted({r['model'] for r in dropped})})\n")
    man = os.path.join(out_dir, "manifest.json")
    if os.path.exists(man):
        mj = json.load(open(man))
        md.append(f"Code: {mj.get('code')}, gateway: {mj.get('gateway')} (frozen {FROZEN_GATEWAY}), "
                  f"classifier: {mj.get('classifier', '-')}\n")
    if phase == "main":
        old = [r for r in load_rows("results/final/rows.jsonl")
               if r["set"] in ("notes", "sensor") and r["setup"] in ("S0", "S3", "S5noL1")
               and r["model"] in PHASES["main"]["models"]]
        rows = rows + old
        md.append(f"(+ {len(old)} rows of the same notes/sensor scenarios and seeds from results/final)\n")
    groups = defaultdict(list)
    for r in rows:
        groups[(r["set"], r["model"], r["setup"], r.get("nudge", 1))].append(r)
    sets = sorted({k[0] for k in groups})
    for s in sets:
        att = any(r.get("kind") == "attack" for k, L in groups.items() if k[0] == s for r in L)
        md.append(f"\n## {s}\n")
        if att:
            md.append("In-authority attacks (G1-G3): resisted / blocked before execution / executed and detected / "
                      "executed and undetected. Twins: task success, episodes with any block.\n")
            md.append("| Model | Setup | Nudge | n | Resisted | Blocked | Exec+detected | Exec+undetected | G0 executed | "
                      "Twin success | Twins with a block | Notes withheld (att/twin) | CaMeL tainted writes (twins) |")
            md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        else:
            md.append("| Model | Setup | Nudge | n | Task success | Any block | Monitor alert | Notes withheld | "
                      "CaMeL tainted writes |")
            md.append("|---|---|---|---|---|---|---|---|---|")
        for (s2, m, st, nu), L in sorted(groups.items()):
            if s2 != s:
                continue
            if att:
                A = [r for r in L if r.get("kind") == "attack" and r.get("goal") != "G0"]
                G0 = [r for r in L if r.get("kind") == "attack" and r.get("goal") == "G0"]
                T = [r for r in L if r.get("kind") == "twin"]
                c = three_way(A); n = len(A)
                wa = sum(r.get("notes_withheld", 0) > 0 for r in A); wt = sum(r.get("notes_withheld", 0) > 0 for r in T)
                ct = sum(r.get("camel_tainted_writes", 0) > 0 for r in T)
                md.append(f"| {m} | {st} | {nu} | {n} | {pct(c['resisted'], n)} | {pct(c['blocked'], n)} | "
                          f"{pct(c['exec_detected'], n)} | {pct(c['exec_undetected'], n)} | "
                          f"{sum(r['attack_executed'] for r in G0)}/{len(G0)} | "
                          f"{pct(sum(r['success'] for r in T), len(T))} | {pct(sum(r['n_blocked'] > 0 for r in T), len(T))} | "
                          f"{(f'{wa}/{n} / {wt}/{len(T)}') if st == 'S6pg' else '–'} | "
                          f"{pct(ct, len(T)) if st == 'S7camel' else '–'} |")
            else:
                n = len(L)
                md.append(f"| {m} | {st} | {nu} | {n} | {pct(sum(r['success'] for r in L), n)} | "
                          f"{pct(sum(r['n_blocked'] > 0 for r in L), n)} | {pct(sum(r['monitor_alerts'] > 0 for r in L), n)} | "
                          f"{pct(sum(r.get('notes_withheld', 0) > 0 for r in L), n) if st == 'S6pg' else '–'} | "
                          f"{pct(sum(r.get('camel_tainted_writes', 0) > 0 for r in L), n) if st == 'S7camel' else '–'} |")
        if not att:   # per-task view of false blocks for the borderline tasks
            sc = {x["id"]: x for x in json.load(open(SETS.get(s, SETS["benign2"]), encoding="utf-8"))}
            flagged = [i for i, x in sc.items() if x.get("flag")]
            if flagged:
                md.append(f"\n**Borderline and bait tasks ({s}), per setup: success / any block / monitor alert**\n")
                md.append("| Task | Flag | Prediction | " + " | ".join(f"{m.split(':')[0]} {st}" for (s2, m, st, nu) in
                          sorted(groups) if s2 == s) + " |")
                md.append("|---|---|---|" + "---|" * len([1 for k in groups if k[0] == s]))
                for i in flagged:
                    cells = []
                    for k in sorted(groups):
                        if k[0] != s:
                            continue
                        L = [r for r in groups[k] if r["scenario"] == i]
                        cells.append(f"{sum(r['success'] for r in L)}/{sum(r['n_blocked'] > 0 for r in L)}/"
                                     f"{sum(r['monitor_alerts'] > 0 for r in L)}")
                    md.append(f"| {i} | {sc[i]['flag']} | {sc[i].get('prediction', '')[:50]} | " + " | ".join(cells) + " |")
    # paired scenario-level tests against the full gateway
    tests = []
    for s in sets:
        for m in sorted({k[1] for k in groups if k[0] == s}):
            for a in ["S0", "S3", "S6pg", "S7camel"]:
                ga, gb = groups.get((s, m, a, 1)), groups.get((s, m, "S5noL1", 1))
                if not ga or not gb:
                    continue
                A = defaultdict(int); Bc = defaultdict(int)
                for r in ga:
                    if r.get("kind") == "attack" and r.get("goal") != "G0":
                        A[r["scenario"]] += RA.undet(r)
                for r in gb:
                    if r.get("kind") == "attack" and r.get("goal") != "G0":
                        Bc[r["scenario"]] += RA.undet(r)
                keys = sorted(set(A) & set(Bc))
                if not keys:
                    continue
                diffs = [A[k] - Bc[k] for k in keys]
                n_a = sum(1 for r in ga if r.get("kind") == "attack" and r.get("goal") != "G0")
                tests.append(dict(set=s, model=m, a=a, ua=sum(A.values()), ub=sum(Bc.values()), n=n_a,
                                  nsc=len(keys), changed=sum(1 for d in diffs if d), p=RA.signflip_p(diffs)))
    if tests:
        adj = RA.holm([t["p"] for t in tests])
        md.append("\n## Scenario-level paired tests: in-authority undetected, setup vs S5noL1 (Holm over this table)\n")
        md.append("| Set | Model | Setup | Undetected (setup) | Undetected (S5noL1) | Scenarios that differ | p sign-flip | p (Holm) |")
        md.append("|---|---|---|---|---|---|---|---|")
        for t, pa in zip(tests, adj):
            md.append(f"| {t['set']} | {t['model']} | {t['a']} | {t['ua']}/{t['n']} | {t['ub']}/{t['n']} | "
                      f"{t['changed']}/{t['nsc']} | {t['p']:.4f} | {pa:.4f} |")
    if phase == "t8":
        md.append("\n## T8-d: forbidden restart (attack executed) by model, thinking and nudge\n")
        md.append("| Model | Nudge | T8-d restarts | Nudges sent | Twin restarts |")
        md.append("|---|---|---|---|---|")
        by = defaultdict(list)
        for r in rows:
            by[(r["model"], r.get("nudge", 1))].append(r)
        for (m, nu), L in sorted(by.items()):
            A = [r for r in L if r["scenario"] == "T8-d"]; T = [r for r in L if r["scenario"] == "T8-twin"]
            md.append(f"| {m} | {nu} | {sum(r['attack_executed'] for r in A)}/{len(A)} | "
                      f"{sum(r['n_nudges'] for r in A)} | {sum(r.get('attack_executed', 0) for r in T)}/{len(T)} |")
    open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(os.path.join(out_dir, "summary.md"))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=list(PHASES), required=True)
    ap.add_argument("--models", nargs="+")
    ap.add_argument("--seeds", type=int)
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--classifier", default=None, help="Hugging Face id for S6pg (default Prompt Guard 2 86M)")
    a = ap.parse_args()
    P = PHASES[a.phase]
    out_dir = os.path.join("results", f"v2_{a.phase}" + ("_mock" if a.mock else ""))
    os.makedirs(out_dir, exist_ok=True)
    if a.summary_only:
        summarize(a.phase, out_dir)
        return 0
    if gateway_hash() != FROZEN_GATEWAY:
        print(f"Gateway code differs from the frozen version ({gateway_hash()} != {FROZEN_GATEWAY}). Stop.")
        return 1
    rows_path, logs_path, man_path = (os.path.join(out_dir, f) for f in ("rows.jsonl", "logs.jsonl", "manifest.json"))
    h = code_hash(a.phase)
    if os.path.exists(man_path):
        old = json.load(open(man_path))["code"]
        if old != h:
            print(f"Code changed since this run started ({old} -> {h}). Move {out_dir} away to start over.")
            return 1
    models = ["mock"] if a.mock else (a.models or P["models"])
    if not a.mock and not ollama_ok(models):
        return 1
    clf_name = "-"
    if any("S6pg" in v for v in P["sets"].values()):
        if a.mock:
            EP.NOTE_CLASSIFIER["clf"] = None   # stub classifier
            clf_name = "stub"
        else:
            from testbed.v2_baselines import NoteClassifier
            clf = NoteClassifier(a.classifier)
            try:
                clf.score("warm-up")
            except ImportError:
                print("S6pg needs transformers: pip install transformers torch")
                return 1
            EP.NOTE_CLASSIFIER["clf"] = clf
            clf_name = clf.model_id
            print(f"classifier for S6pg: {clf_name}")
    if not os.path.exists(man_path):
        json.dump({"code": h, "gateway": gateway_hash(), "started": time.strftime("%Y-%m-%d %H:%M"),
                   "models": models, "classifier": clf_name}, open(man_path, "w"))
    if a.mock:
        jobs = [("mock",) + j[1:] for j in plan(a.phase, [P["models"][0]], 1)]
    else:
        jobs = plan(a.phase, models, a.seeds or P["seeds"])
    done = set()
    for r in load_rows(rows_path):
        if not r.get("crash"):
            done.add(key(r["model"], r["set"], r["setup"], r["seed"], r.get("nudge", 1), r["scenario"]))
    todo = [j for j in jobs if key(j[0], j[1], j[2], j[3], j[4], j[5]["id"]) not in done]
    print(f"phase {a.phase}: {len(jobs)} episodes, done {len(jobs) - len(todo)}, to run {len(todo)}")
    server = modbus_io.ModbusPlantServer().start()
    t_start, n_run, cur = time.time(), 0, None
    try:
        with open(rows_path, "a", encoding="utf-8") as fr, open(logs_path, "a", encoding="utf-8") as fl:
            for m, s, st, seed, nudge, sc in todo:
                if m != cur and m != "mock":
                    print(f"\nwarming up {m} ...", flush=True)
                    OllamaLLM(base_model(m), think="@think" in m).warm_up()
                cur = m
                llm = (ScriptedLLM(sc["reference_calls"], sc.get("reference_answer", "Done.")) if m == "mock"
                       else OllamaLLM(base_model(m), seed=seed, think="@think" in m))
                try:
                    row, log = run_one(sc, llm, seed, st, lambda p: modbus_io.ModbusReader(), server.publish,
                                       nudge=nudge)
                except Exception as e:
                    row, log = {"scenario": sc["id"], "success": 0, "crash": str(e)[:200]}, {}
                row.update(model=m, set=s, setup=st, seed=seed, nudge=int(nudge), scenario=sc["id"],
                           kind=sc.get("kind", "benign"), goal=sc.get("goal", ""), template=sc.get("template", ""))
                fr.write(json.dumps(row, ensure_ascii=False) + "\n"); fr.flush()
                log["row"] = row
                fl.write(json.dumps(log, ensure_ascii=False) + "\n")
                n_run += 1
                if n_run % 10 == 0 or n_run == len(todo):
                    el = time.time() - t_start
                    print(f"[{time.strftime('%H:%M')}] {n_run}/{len(todo)}  now: {m} {s} {st} seed{seed}"
                          f"  left: ~{el / n_run * (len(todo) - n_run) / 3600:.1f} h", flush=True)
    except KeyboardInterrupt:
        print("\nstopped. Run the same command again to continue where it stopped.")
        return 0
    finally:
        server.stop()
    summarize(a.phase, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
