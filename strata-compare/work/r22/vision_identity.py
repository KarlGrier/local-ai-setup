#!/usr/bin/env python3
"""vision_identity.py run URL OUT.json | compare A.json B.json - round 22 pictures step 1 (the user, 10-19: "check that
text outputs stay bitwise identical with it loaded").

Run on the fixed-computation twin (configs/r22portRT.json, and the same with the vision section: the CPU picture reader
loaded, the engine started with --vision): eleven replies - six short prompts greedy (256 tokens), the same three of them
seeded (1.0 / 0.95 / 20 / min-p 0.05, seed 7), and a ~4K- and a ~20K-token slice of the port's docs/DETAILS.md (64 tokens) - each
on a fresh conversation. `compare` passes when every reply text is identical.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

LONG_TEXT = Path("/home/USER/ai-speed-testing/strata-compare/strata-r22port/docs/DETAILS.md")   # fixed text (the port's tree)
SHORT = [
    "What is 17 * 23? Show the steps briefly.",
    "Write a Python function that returns the n-th Fibonacci number iteratively.",
    "Explain in three sentences why the sky is blue.",
    "Translate into German: 'The train leaves at seven, so we have to get up early.'",
    "List four differences between TCP and UDP.",
    "A farmer has 3 fields of 12 rows with 40 plants each; 15% die. How many plants are left?",
]
SAMPLED = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "seed": 7}


def chat(url: str, content: str, max_tokens: int, sampling: dict) -> str:
    body = {"model": "x", "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}, **sampling}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=900) as r:
        return json.loads(r.read())["choices"][0]["message"].get("content") or ""


def long_prompt(chars: int) -> str:
    return LONG_TEXT.read_text(errors="replace")[:chars] + "\n\nSummarise the text above in two sentences."


def run(url: str, out: Path) -> None:
    res = []
    for i, p in enumerate(SHORT):
        res.append({"case": f"greedy-{i}", "text": chat(url, p, 256, {"temperature": 0})})
    for i in (0, 1, 4):
        res.append({"case": f"seeded-{i}", "text": chat(url, SHORT[i], 256, SAMPLED)})
    for n, chars in (("4k", 16000), ("20k", 80000)):
        t = time.time()
        res.append({"case": f"long-{n}", "text": chat(url, long_prompt(chars), 64, {"temperature": 0}),
                    "secs": round(time.time() - t, 1)})
    out.write_text(json.dumps(res, indent=1))
    print(f"{len(res)} replies -> {out}")


def compare(a: Path, b: Path) -> int:
    ra, rb = json.loads(a.read_text()), json.loads(b.read_text())
    same = 0
    for x, y in zip(ra, rb):
        ok = x["text"] == y["text"]
        same += ok
        print(f"{'SAME' if ok else 'DIFF'} {x['case']:10s} {len(x['text'])} / {len(y['text'])} chars")
    print(f"identity: {same}/{len(ra)} replies identical with the picture reader loaded")
    return 0 if same == len(ra) == len(rb) else 1


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], Path(sys.argv[3]))
    else:
        sys.exit(compare(Path(sys.argv[2]), Path(sys.argv[3])))
