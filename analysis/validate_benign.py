"""Reference calls of every benign task under S0 and S5noL1, several seeds: success, blocks, monitor alerts."""
import json, sys
from testbed import modbus_io
from testbed.episode import run_one
from testbed.llm import ScriptedLLM
S = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "scenarios/benign_v2.json", encoding="utf-8"))
seeds = range(1, 11)
for sc in S:
    res = {}
    for st in ["S0", "S5noL1"]:
        ok = blk = mon = 0; why = set()
        for sd in seeds:
            cur = {}
            r, log = run_one(sc, ScriptedLLM(json.loads(json.dumps(sc["reference_calls"])), sc.get("reference_answer", "Done.")),
                             sd, st, lambda p: modbus_io.DirectReader(lambda: cur["p"]), lambda p: cur.__setitem__("p", p))
            ok += r["success"]; blk += r["n_blocked"] > 0; mon += r["monitor_alerts"] > 0
            for a in log["audit"]:
                if a["decision"] == "blocked":
                    why.add(a["reason"].split(":")[0][:30] + "|" + ",".join(sorted(set(x.split(":")[0].strip() for x in a["reason"].split("|") if x.strip().startswith(("I", "the record"))))))
            if not r["success"]:
                why.add("FAIL:" + r["reason"][:60])
        res[st] = f"ok {ok}/10 blk {blk} mon {mon}"
    print(f"{sc['id']:4s} {sc.get('flag',''):6s} S0[{res['S0']}]  S5noL1[{res['S5noL1']}]  pred: {sc.get('prediction','')[:55]}")
