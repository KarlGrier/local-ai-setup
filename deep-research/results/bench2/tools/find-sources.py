#!/usr/bin/env python3
"""find-sources.py - for a hard-set draft, fetch candidate pages (the ones given + the 10 results of its snippet check)
and show where the answer (or a variant) occurs, so two confirming pages can be picked by hand (2026-10-18).
PDFs are read with pypdf (run with the deep-research venv's python).

  find-sources.py DRAFT.json [URL ...]
"""
import io, json, sys, time, urllib.request
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("v", "/home/USER/ai/deep-research/results/bench2/tools/verify.py")
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
H = Path("/home/USER/ai/deep-research/results/bench2/hard-build")


def fetch(url: str) -> str:
    if url.lower().split("?")[0].endswith(".pdf"):
        import pypdf
        req = urllib.request.Request(url, headers={"User-Agent": v.UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        return " ".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages)
    return v.fetch(url)


d = json.loads(Path(sys.argv[1]).read_text())
urls = list(sys.argv[2:])
for l in (H / "snippet-checks.jsonl").read_text().splitlines():
    r = json.loads(l)
    if r["id"] == d["id"]:
        urls += [x["url"] for x in r["results"] if x["url"] not in urls]
variants = d.get("find") or [d["answer"], *d.get("accept", [])]   # "find": phrases for numbers ("27 layers")
ok = 0
for u in urls:
    try:
        t = fetch(u)
    except Exception as e:  # noqa: BLE001
        continue
    hit = next(((x, t.find(x)) for x in variants if x and t.find(x) >= 0), None)
    if hit:
        x, i = hit
        print(f"  OK {u[:110]}\n     [{x}] ...{t[max(0, i - 130):i + len(x) + 80]}...".replace("\n", " "))
        ok += 1
        if ok >= int(d.get("max_ok", 4)):
            break
