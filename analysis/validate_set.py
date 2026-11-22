"""Scripted check of a scenario set (no GPU): reference calls on every scenario must succeed with
no block; compromised calls show what the gateway does with the attack as written.
usage: python analysis/validate_set.py scenarios/adaptive_v1.json [setups...]"""
import json, sys
from testbed import modbus_io
from testbed.episode import run_one
from testbed.llm import ScriptedLLM

def run(sc, calls, setup, final):
    cur = {}
    return run_one(sc, ScriptedLLM(json.loads(json.dumps(calls)), final), 1, setup,
                   lambda p: modbus_io.DirectReader(lambda: cur["p"]), lambda p: cur.__setitem__("p", p))

path = sys.argv[1]; setups = sys.argv[2:] or ["S0", "S4noL1", "S5noL1"]
S = json.load(open(path, encoding="utf-8")); bad = 0
for sc in S:
    ans = sc.get("reference_answer", "Done.")
    for st in setups:
        r, _ = run(sc, sc["reference_calls"], st, ans)
        if not r["success"] or r["n_blocked"]:
            bad += 1; print("REF FAIL", sc["id"], st, r["reason"], r["blocked_by"])
    if sc["kind"] == "attack":
        out = []
        for st in setups:
            r, log = run(sc, sc["compromised_calls"], st, ans)
            o = ("EXEC" if r["attack_executed"] else "BLOCK" if r["attack_proposed"] else "none")
            if r["attack_executed"]:
                o += "+DET" if r.get("attack_detected") else "+undet"
            reasons = [a.get("reason", "")[:70] for a in log["audit"] if a["decision"] == "blocked"]
            out.append(f"{st}:{o}" + (f" [{r['blocked_by']}]" if r["blocked_by"] else ""))
        print(f"{sc['id']:8s} " + "  ".join(out) + f"   pred: {sc.get('prediction','')[:60]}")
print("reference failures:", bad)
