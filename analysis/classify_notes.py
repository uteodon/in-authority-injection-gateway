"""Score every note text in every scenario set with the S6pg classifier (no LLM, CPU, ~1-2 min).
Reports how many injected notes are flagged and how many genuine/neutral notes are flagged.
usage: python analysis/classify_notes.py [--classifier HF_ID]"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from testbed.v2_baselines import NoteClassifier

ap = argparse.ArgumentParser(); ap.add_argument("--classifier"); a = ap.parse_args()
clf = NoteClassifier(a.classifier)
rows = []
for path in sorted(glob.glob("scenarios/*_v*.json")):
    S = json.load(open(path, encoding="utf-8")); name = os.path.basename(path)
    twins = {s.get("template"): s for s in S if s.get("kind") == "twin"}
    for s in S:
        notes = s.get("setup", {}).get("notes", [])
        if s.get("kind") == "attack":
            base = {n["text"] for n in twins.get(s.get("template"), {}).get("setup", {}).get("notes", [])}
            for n in notes:
                rows.append((name, "injected" if n["text"] not in base else "genuine", s["id"], clf.score(n["text"]), n["text"]))
        else:
            for n in notes:
                rows.append((name, "genuine", s["id"], clf.score(n["text"]), n["text"]))
seen = set(); uniq = []
for r in rows:
    if (r[0], r[4]) not in seen:
        seen.add((r[0], r[4])); uniq.append(r)
md = [f"# Classifier {clf.model_id}, threshold {clf.threshold}\n",
      "| Set | Injected notes flagged | Genuine/neutral notes flagged |", "|---|---|---|"]
for name in sorted({r[0] for r in uniq}):
    inj = [r for r in uniq if r[0] == name and r[1] == "injected"]
    gen = [r for r in uniq if r[0] == name and r[1] == "genuine"]
    f = lambda L: f"{sum(r[3] >= clf.threshold for r in L)}/{len(L)}" if L else "–"
    md.append(f"| {name} | {f(inj)} | {f(gen)} |")
md.append("\n## Every note\n\n| Set | Kind | Scenario | Score | Text |\n|---|---|---|---|---|")
for r in uniq:
    md.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.3f} | {r[4][:120].replace('|', '/').replace(chr(10), ' ')} |")
os.makedirs("results/v2_classifier", exist_ok=True)
open("results/v2_classifier/notes_scored.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md[:12])); print("-> results/v2_classifier/notes_scored.md")
