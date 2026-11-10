#!/usr/bin/env python3
"""guard_loopcheck.py - 2026-10-13: does a Strata server's repeat guard still stop a real single-token loop, and does
it let a legitimate long digit run through?  Three requests to --endpoint (OpenAI chat, non-streamed):
  loop_0     a forced loop: logit_bias +100 on the token "0" from the first token (the model can write nothing else)
  loop_bang  the same on "!" (the broken-state case #606 was written for: an issue saw 36,689 tokens of "!")
  legit_600  "write 10^600 in full" (a 1 and 600 zeros): an answer that needs one token 600 times in a row
Pass for a guard of N (--expect): both loops end as "length" after exactly N tokens (N-1 visible: the guard drops the
Nth), within --max-s seconds; legit_600 is reported (complete / cut) - with N > 600 it should be complete, with the
256 default it is cut.  Writes --out (JSON) and prints one line per request."""
import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--endpoint", default="http://127.0.0.1:8081")
ap.add_argument("--tokenizer", required=True)
ap.add_argument("--expect", type=int, required=True, help="the server's repeat_stop_tokens")
ap.add_argument("--max-s", type=float, default=120)
ap.add_argument("--out", required=True)
ap.add_argument("--legit-only", action="store_true", help="only legit_600 (its text saved)")
ap.add_argument("--legit-max-tokens", type=int, default=16384)
a = ap.parse_args()
vocab = json.loads((Path(a.tokenizer) / "vocab.json").read_text(encoding="utf-8"))
ids = {"0": vocab["0"], "!": vocab["!"]}
model = json.loads(urllib.request.urlopen(a.endpoint + "/v1/models", timeout=10).read())["data"][0]["id"]
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}


def post(body):
    req = urllib.request.Request(a.endpoint + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=1800) as r:
        out = json.loads(r.read())
    return out, round(time.monotonic() - t0, 1)


res = {"endpoint": a.endpoint, "model": model, "expect": a.expect, "checks": {}}
ok = True
for name, tid, ch in (() if a.legit_only else (("loop_0", ids["0"], "0"), ("loop_bang", ids["!"], "!"))):
    body = {"model": model, "messages": [{"role": "user", "content": "Say hello."}], "max_tokens": 4 * a.expect + 512,
            "stream": False, "logit_bias": {str(tid): 100}, **SAMPLING}
    out, s = post(body)
    ch0 = out["choices"][0]
    text = (ch0["message"].get("reasoning_content") or ch0["message"].get("reasoning") or "") + (ch0["message"].get("content") or "")
    trail = len(text) - len(text.rstrip(ch))
    n = (out.get("usage") or {}).get("completion_tokens")
    passed = ch0["finish_reason"] == "length" and n == a.expect and trail == a.expect - 1 and s <= a.max_s
    ok &= passed
    res["checks"][name] = {"finish": ch0["finish_reason"], "completion_tokens": n, "visible_run": trail, "wall_s": s,
                           "pass": passed}
    print(f"{name}: finish {ch0['finish_reason']}, {n} tokens, {trail} visible {ch!r}, {s} s -> {'PASS' if passed else 'FAIL'}")
body = {"model": model, "max_tokens": a.legit_max_tokens, "stream": False, **SAMPLING,
        "messages": [{"role": "user", "content": "Write the number 10^600 as a plain integer: the digit 1 followed by "
                                                 "600 zeros, every digit written out, on one line, and nothing else."}]}
out, s = post(body)
ch0 = out["choices"][0]
c = ch0["message"].get("content") or ""
m = max((len(x) for x in re.findall(r"10+", c)), default=0)
res["checks"]["legit_600"] = {"finish": ch0["finish_reason"], "completion_tokens": (out.get("usage") or {}).get("completion_tokens"),
                              "longest_1_then_zeros": m, "complete": "1" + "0" * 600 in c and ch0["finish_reason"] == "stop",
                              "wall_s": s}
z = ch0["message"].get("reasoning_content") or ch0["message"].get("reasoning") or ""
runs = [(x.group(1), len(x.group(0))) for x in re.finditer(r"(\d)\1{63,}", z + c)]
res["checks"]["legit_600"].update({"reasoning_chars": len(z), "content": c[:2000], "reasoning_head": z[:1500],
                                   "reasoning_tail": z[-1500:], "digit_runs_64plus": runs})
print(f"legit_600: finish {ch0['finish_reason']}, longest '10...0' in the answer {m} chars (601 = complete), {s} s")
res["loops_stopped_at_expect"] = ok
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(res, indent=1))
print("loops stopped at", a.expect, ":", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
