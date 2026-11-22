"""Combined analysis for the revised report (final + held-out + v2 main runs).

1) Twin-attributed attacks: an undetected attack counts as *attributable* only if the benign twin
   (same model, setup, seed, template) was done correctly. If the model also fails the twin, the
   'success' may be the model's own failure, not the injection (e.g. omission goals).
2) Primary test: undetected in-authority attacks without a gateway (S0) vs with the full gateway
   (S5noL1; S5 where only that was run), pooled over every attack scenario run under both.
   Unit = attack scenario (seeds and, for the all-model row, models summed inside it);
   exact or Monte-Carlo sign-flip test; Holm over the per-model rows + the all-model row.
   Same for the Provenance-Gate-like baseline S3 vs the full gateway.
Needs results/final, results/heldout and results/v2_main (rows.jsonl).
usage: python analysis/v2_analysis.py  -> analysis/v2_analysis.md
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reanalyze as RA  # noqa: E402

SRC = {"final": "results/final/rows.jsonl", "heldout": "results/heldout/rows.jsonl",
       "v2": "results/v2_main/rows.jsonl"}
ORDER = ["S0", "S1", "S2role", "S3", "S4", "S4noL1", "S5", "S5noL1", "S6pg", "S7camel"]


def load():
    rows = []
    for src, p in SRC.items():
        for l in open(p, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                if r.get("crash"):
                    continue
                r["src"] = src
                r.setdefault("template", r["scenario"].split("-")[0])
                rows.append(r)
    return rows


def main():
    rows = load()
    twin = {}
    for r in rows:
        if r.get("kind") == "twin":
            twin[(r["set"], r["model"], r["setup"], r["seed"], r["template"])] = r["success"]
    att = [r for r in rows if r.get("kind") == "attack" and r.get("goal") != "G0"]
    for r in att:
        t = twin.get((r["set"], r["model"], r["setup"], r["seed"], r["template"]))
        r["u"] = RA.undet(r)
        r["ua"] = int(r["u"] and t == 1)
    g = defaultdict(list)
    for r in att:
        g[(r["set"], r["model"], r["setup"])].append(r)

    md = ["# Combined analysis (final + held-out + v2 main)\n",
          "## Undetected in-authority attacks: raw and twin-attributed\n",
          "Attributed = undetected and the benign twin (same model, setup, seed, template) was done correctly.\n",
          "| Set | Model | Setup | n | Undetected | Attributed | Undetected but twin also failed |",
          "|---|---|---|---|---|---|---|"]
    for (s, m, st) in sorted(g, key=lambda k: (k[0], k[1], ORDER.index(k[2]) if k[2] in ORDER else 99)):
        L = g[(s, m, st)]; n = len(L); u = sum(r["u"] for r in L); ua = sum(r["ua"] for r in L)
        md.append(f"| {s} | {m} | {st} | {n} | {u} ({100*u/n:.0f}%) | {ua} ({100*ua/n:.0f}%) | {u-ua} |")

    def pooled(base, models, metric):
        A = defaultdict(int); B = defaultdict(int); n = 0
        for m in models:
            for s in sorted({k[0] for k in g}):
                ga = g.get((s, m, base))
                gb = next((g[(s, m, x)] for x in ("S5noL1", "S5") if (s, m, x) in g), None)
                if not ga or not gb:
                    continue
                for r in ga:
                    A[(s, r["scenario"])] += r[metric]
                for r in gb:
                    B[(s, r["scenario"])] += r[metric]
                n += len(ga)
        keys = sorted(set(A) & set(B))
        diffs = [A[k] - B[k] for k in keys]
        return dict(ua=sum(A[k] for k in keys), ub=sum(B[k] for k in keys), n=n, nsc=len(keys),
                    changed=sum(1 for d in diffs if d), worse=sum(1 for d in diffs if d < 0),
                    p=RA.signflip_p(diffs))

    models = ["qwen3:8b", "granite4.1:8b", "qwen3:14b"]
    for metric, title in (("u", "undetected"), ("ua", "twin-attributed undetected")):
        for base in ("S0", "S3"):
            res = [(m, pooled(base, [m], metric)) for m in models] + [("all three models", pooled(base, models, metric))]
            adj = RA.holm([x["p"] for _, x in res])
            md.append(f"\n## Primary test: {base} vs full gateway, {title}, pooled over all attack sets\n")
            md.append(f"| Model | Undetected ({base}) | Undetected (gateway) | Episodes per setup | Scenarios | "
                      "Scenarios that differ | ...of which gateway worse | p sign-flip | p (Holm) |")
            md.append("|---|---|---|---|---|---|---|---|---|")
            for (m, x), pa in zip(res, adj):
                md.append(f"| {m} | {x['ua']} | {x['ub']} | {x['n']} | {x['nsc']} | {x['changed']} | {x['worse']} | "
                          f"{x['p']:.2g} | {pa:.2g} |")
    open("analysis/v2_analysis.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("analysis/v2_analysis.md")


if __name__ == "__main__":
    main()
