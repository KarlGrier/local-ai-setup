#!/usr/bin/env python3
"""extract-tasks-extra.py OUT_DIR — add 12 extraction tasks in other domains to OUT_DIR/tasks.jsonl (replacing 12 of
the telegraph-heavy ones): 4 questions x 3 long pages found with LDR's SearXNG (general+science), fetched with
LDR's ContentFetcher at 120,000 chars, each with a specific focus. None of these topics is in the benchmark."""
import json, random, sys
from pathlib import Path
import requests
from local_deep_research.content_fetcher import ContentFetcher
OUT = Path(sys.argv[1])
Q = [
    ("What are the efficacy and safety results of GLP-1 receptor agonists (semaglutide, liraglutide) for obesity in adolescents?",
     "semaglutide adolescents obesity randomized trial STEP TEENS results",
     "mean BMI or body-weight change versus placebo, trial size and duration, and gastrointestinal or serious adverse event rates"),
    ("How does the EU AI Act classify high-risk AI systems, and what obligations apply to providers?",
     "EU AI Act high-risk AI systems obligations providers Article 6 Annex III",
     "which systems count as high-risk (Article 6, Annex III) and the specific obligations of providers, with article numbers"),
    ("What caused the August 2003 Northeast blackout in North America, and what changed afterwards?",
     "2003 Northeast blackout causes final report FirstEnergy tree contact alarm failure",
     "the sequence of causes (line trips, tree contact, alarm software failure) with times, and the resulting reliability standards"),
    ("How does PostgreSQL implement MVCC, and what causes table bloat and transaction ID wraparound?",
     "PostgreSQL MVCC tuple visibility xmin xmax vacuum bloat transaction wraparound",
     "how xmin/xmax visibility works, why dead tuples cause bloat, and how VACUUM/freezing prevents transaction ID wraparound"),
]
tasks = [json.loads(l) for l in open(OUT / "tasks.jsonl")]
random.seed(5)
# drop 12 of the old ones, preferring repeated pages
by_url = {}
for t in tasks:
    by_url.setdefault(t["url"].split("#")[0], []).append(t)
drop = []
for url, ts in sorted(by_url.items(), key=lambda kv: -len(kv[1])):
    for t in ts[1:]:
        if len(drop) < 12:
            drop.append(t["id"])
tasks = [t for t in tasks if t["id"] not in drop]
new = []
for question, query, focus in Q:
    d = requests.get("http://127.0.0.1:8889/search", params={"q": query, "format": "json", "language": "en",
                     "categories": "general,science"}, timeout=60).json()
    n = 0
    for r in d.get("results", []):
        if n >= 3:
            break
        url = r.get("url", "")
        if any(x in url for x in ("youtube.", "reddit.", "linkedin.")):
            continue
        try:
            with ContentFetcher(timeout=30) as f:
                res = f.fetch(url, max_length=120000)
        except Exception:
            continue
        txt = (res or {}).get("content") or ""
        if res.get("status") != "success" or len(txt) < 12000:
            continue
        new.append({"url": url, "focus": focus, "query": question, "title": res.get("title") or r.get("title", ""),
                    "page_text": txt, "cap": 120000, "src": "extra"})
        n += 1
        print(f"  {len(txt):7d} chars  {url[:100]}", flush=True)
next_id = max(t["id"] for t in tasks) + 1
for t in new:
    t["id"] = next_id; next_id += 1
tasks += new
with open(OUT / "tasks.jsonl", "w", encoding="utf-8") as f:
    for t in tasks:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")
print(f"dropped {len(drop)} repeated-page tasks, added {len(new)}; {len(tasks)} tasks, "
      f"{sum(1 for t in tasks if len(t['page_text']) > 12000)} long")
