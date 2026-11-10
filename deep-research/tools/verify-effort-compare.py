#!/usr/bin/env python3
"""verify-effort-compare.py DEEP_RUN_DIR EFFORT [joint|per_source] — re-run a finished deep run's citation check at another reasoning
effort (same claims, same stored page text, same prompt) and compare the verdicts with the run's own (xhigh).
Writes DEEP_RUN_DIR/verification-EFFORT.json and prints agreement, verdict counts and generated tokens."""
import json, os, sys, time
from pathlib import Path
d, effort = Path(sys.argv[1]), sys.argv[2]
design = sys.argv[3] if len(sys.argv) > 3 else "per_source"
os.environ["LDR_DEEP"] = "1"
os.environ["LDR_DEEP_VERIFY_EFFORT"] = effort
os.environ.setdefault("LDR_DEEP_TOKENIZER_DIR", "/home/USER/ai/deep-research/deep/tokenizer")
import requests
from langchain_openai import ChatOpenAI
from local_deep_research.deep.evidence import EvidenceStore
from local_deep_research.deep.report import ReportWriter
st = EvidenceStore("", None)
for l in open(d / "evidence.jsonl"):
    r = json.loads(l)
    if r["type"] == "start":
        st.query = r["query"]
    elif r["type"] == "search":
        st.add_search(r["query"], [{"index": x["idx"], "link": x["url"], "title": x["title"], "snippet": x["snippet"]}
                                   for x in r["results"]])
    elif r["type"] == "fetch":
        st.add_fetch(r["idx"], r["url"], r["title"], r["focus"], r.get("page_text", ""), r["extraction"])
ref = json.loads((d / "verification.json").read_text())
model = ChatOpenAI(model=requests.get("http://127.0.0.1:8080/v1/models").json()["data"][0]["id"], api_key="x",
                   base_url="http://127.0.0.1:8090/v1", temperature=0.6, max_tokens=30000, streaming=True)
w = ReportWriter(st.query, st, model, "")
t = time.time()
new = (w.verify if design == "joint" else w.verify_per_source)("", claims=ref)
secs = time.time() - t
(d / f"verification-{effort}-{design}.json").write_text(json.dumps(new, indent=1, ensure_ascii=False))
pairs = [(a["verdict"], b["verdict"]) for a, b in zip(ref, new)]
agree = sum(a == b for a, b in pairs)
flag = lambda v: v in ("unsupported", "partial")
agree_flag = sum(flag(a) == flag(b) for a, b in pairs)
from collections import Counter
multi = [i for i, a in enumerate(ref) if len(a["sources"]) > 1]
print(json.dumps({"design": design, "effort": effort, "claims": len(pairs),
                  "multi_source_partial": f"{sum(new[i]['verdict'] == 'partial' for i in multi)}/{len(multi)}", "exact_agreement": round(agree / len(pairs), 3),
                  "flag_agreement": round(agree_flag / len(pairs), 3),
                  "ref_verdicts": Counter(a for a, _ in pairs), f"{effort}_verdicts": Counter(b for _, b in pairs),
                  "confusion": Counter(f"{a}->{b}" for a, b in pairs if a != b),
                  "seconds": round(secs), "calls": len(w.calls)}, indent=1, default=dict))
