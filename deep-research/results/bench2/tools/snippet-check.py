#!/usr/bin/env python3
"""snippet-check.py - the hard set's difficulty filter (2026-10-18, the user's rule): one plain web search for the
question (its text as the query, SearXNG 127.0.0.1:8889 with its default categories - the instance both profiles
search), top 10 results; the question passes only if no answer variant appears in their titles + snippets.
Matching = bench2.py's grader (normalised text; numbers within the stored tolerance).

  snippet-check.py ID           ID's question from hard-build/candidates.jsonl, answer from hard-build/answers.jsonl
  snippet-check.py SPEC.json    a draft (add-candidate.py's spec format), checked before its sources are confirmed
Appends the verdict and the 10 results to hard-build/snippet-checks.jsonl.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path
sys.path.insert(0, "/home/USER/ai/deep-research/tools")
import importlib.util
spec = importlib.util.spec_from_file_location("bench2", "/home/USER/ai/deep-research/tools/bench2.py")
b2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b2)
H = Path("/home/USER/ai/deep-research/results/bench2/hard-build")
qid = sys.argv[1]
if qid.endswith(".json"):                            # a draft spec (add-candidate.py's format): check before confirming sources
    q = ans = json.loads(Path(qid).read_text())
    qid = q["id"]
else:
    q = next(x for x in b2.load_jsonl(H / "candidates.jsonl") if x["id"] == qid)
    ans = next(x for x in b2.load_jsonl(H / "answers.jsonl") if x["id"] == qid)
url = "http://127.0.0.1:8889/search?" + urllib.parse.urlencode({"q": q["question"], "format": "json"})
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
res = json.load(op.open(url, timeout=60)).get("results", [])[:10]
hits = []
for i, r in enumerate(res, 1):
    h = b2.matches(f"{r.get('title', '')} {r.get('content', '')}", ans)
    if h:
        hits.append({"rank": i, "url": r.get("url"), "hit": h})
rec = {"id": qid, "question": q["question"], "time": time.strftime("%F %T"), "n_results": len(res), "pass": not hits and len(res) >= 5,
       "hits": hits, "results": [{"url": r.get("url"), "title": r.get("title"), "content": r.get("content")} for r in res]}
with open(H / "snippet-checks.jsonl", "a") as f:
    f.write(json.dumps(rec) + "\n")
print(f"{qid}: {'PASS' if rec['pass'] else 'FAIL'} ({len(res)} results)" + (f" - answer in snippet(s): {hits}" if hits else ""))
