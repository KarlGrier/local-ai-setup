#!/usr/bin/env python3
"""add-candidate.py - add a hard-set candidate (2026-10-18): fetch each source page, find the phrase that carries the
answer, save the page text (hard-build/sources/<sha1>.txt) and the quote; the question goes to hard-build/candidates.jsonl
and the answer (with its sources) to hard-build/answers.jsonl - kept apart, as for the first set.

  add-candidate.py SPEC.json      {"id", "type", "question", "answer", "accept": [...], "number": {...} (optional),
                                   "sources": [{"url", "phrase"}, ...], "note": "..." (optional)}
Refuses (writes nothing) unless every source page has its phrase.
"""
import hashlib, json, os, sys
from pathlib import Path
import importlib.util
H = Path("/home/USER/ai/deep-research/results/bench2/hard-build")
spec = importlib.util.spec_from_file_location("v", "/home/USER/ai/deep-research/results/bench2/tools/verify.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)


def fetch(url: str) -> str:
    """verify.fetch, plus PDFs (pypdf; run with the deep-research venv's python)."""
    if url.lower().split("?")[0].endswith(".pdf"):
        import io, urllib.request, pypdf
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": v.UA}), timeout=30) as r:
            data = r.read()
        return " ".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages)
    return v.fetch(url)


s = json.loads(Path(sys.argv[1]).read_text())
srcs = []
for src in s["sources"]:
    t = fetch(src["url"])
    i = t.find(src["phrase"])
    if i < 0:
        sys.exit(f"{s['id']}: phrase {src['phrase']!r} not on {src['url']} - nothing written")
    name = hashlib.sha1(src["url"].encode()).hexdigest()[:12] + ".txt"
    (H / "sources").mkdir(parents=True, exist_ok=True)
    (H / "sources" / name).write_text(src["url"] + "\n\n" + t)
    srcs.append({"url": src["url"], "quote": "..." + t[max(0, i - 200):i + len(src["phrase"]) + 200] + "...", "saved": name})
for f in ("candidates.jsonl", "answers.jsonl"):
    p = H / f
    if p.exists() and any(json.loads(l)["id"] == s["id"] for l in p.read_text().splitlines() if l.strip()):
        sys.exit(f"{s['id']} is already in {f}")
q = {"id": s["id"], "kind": "checkable", "question": s["question"], "files": []}
a = {"id": s["id"], "type": s["type"], "answer": s["answer"], "accept": s.get("accept", []), "sources": srcs}
if s.get("number"):
    a["number"] = s["number"]
if s.get("note"):
    a["note"] = s["note"]
with open(H / "candidates.jsonl", "a") as f:
    f.write(json.dumps(q, ensure_ascii=False) + "\n")
with open(H / "answers.jsonl", "a") as f:
    f.write(json.dumps(a, ensure_ascii=False) + "\n")
print(f"{s['id']}: added ({len(srcs)} sources confirmed)")
