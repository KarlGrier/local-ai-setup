#!/usr/bin/env python3
"""weblive.py --base URL --label L — round 9 Phase 0.6: three LIVE questions with the Web search switch on (strata_web),
your settings (effort high = xhigh, T 1.0 / 0.95 / 20 / min-p 0.05), one fresh chat each. Records the tool calls, whether
the answer cites a URL, the content keywords found, TTFT / total / finish -> results/r10/weblive.jsonl (+ the answers)."""
import argparse, json, re, sys, time
from pathlib import Path
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r6")
from webreplay import stream, USER
WS = Path("/home/USER/ai-speed-testing/strata-compare")
QS = [("What is the latest stable release of the Linux kernel right now, and when was it released? Cite your source.", ["7."]),
      ("What is the newest stable Python 3 release right now, and on what date was it released? Cite your source.", ["3.1"]),
      ("Who won the 2026 FIFA World Cup final, and what was the score? Cite your source.", ["2026"])]
ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--label", required=True)
a = ap.parse_args()
ok_all = 0
for q, keys in QS:
    r = stream(a.base, [{"role": "user", "content": q}], {**USER, "strata_web": True, "max_tokens": 6144})
    names = [t.get("name") for t in sorted(r["tools"].values(), key=lambda t: t["order"])]
    urls = re.findall(r"https?://[^\s)\]>\"']+", r["text"])
    found = [k for k in keys if k in r["text"]]
    searched_ok = [t for t in r["tools"].values() if t.get("name") == "web_search" and len(t.get("full") or "") > 300]
    ok = bool(r["text"].strip()) and bool(urls) and len(found) == len(keys) and r["error"] is None and bool(searched_ok)
    ok_all += ok
    rec = {"label": a.label, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "question": q, "tools": names,
           "web_search_with_results": len(searched_ok), "urls": urls[:5], "keys_found": found, "finish": r["finish"],
           "error": r["error"], "ttft": r["ttft"], "total": r["total"], "usage": r["usage"], "pass": ok,
           "answer": r["text"][-1500:]}
    with open(WS / "results/r10/weblive.jsonl", "a") as f: f.write(json.dumps(rec) + "\n")
    print(f"{'PASS' if ok else 'FAIL'} tools={names} results-searches={len(searched_ok)} urls={urls[:2]} keys={found} "
          f"finish={r['finish']} err={r['error']} total={r['total']:.1f}s\n   answer: {r['text'][-300:]!r}")
print(f"weblive {a.label}: {ok_all}/{len(QS)} pass")
