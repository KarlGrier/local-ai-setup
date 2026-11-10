#!/usr/bin/env python3
"""followup652.py BASE LABEL [MODE...] — round 11 Phase 0.3 (#652's question): does a follow-up turn re-read the previous
answer?  Multi-turn conversations over the OpenAI endpoint; every turn sends the whole history back with the previous
answers verbatim (and their reasoning_content, which the template keeps: preserve_thinking).  After each request the
server's /metrics?requests=all record gives prompt_total, reused, output tokens.  A follow-up "resumed" when it reused at
least what the engine held after the previous turn (its prompt + answer less the uncommitted last token, -2 for the
end-of-turn token); a "miss" falls back further (the turn-boundary checkpoint: the answer is read again).
MODES: plain (no thinking; max_tokens alternating short caps / a natural end), think (your xhigh thinking, natural ends,
one cap).  Output: a line per turn + a summary; JSON to bringup/out/results/followup-LABEL.json."""
import json
import sys
import urllib.request

BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
MODES = sys.argv[3:] or ["plain", "think"]
TOPICS = {
    "plain": [["Write a Python function that checks whether a string is a palindrome, ignoring case and punctuation.",
               "Now add type hints and a docstring.", "Write three unit tests for it with unittest.",
               "Explain in two sentences how the function handles Unicode.", "Make it work on a stream of characters.",
               "What is the time complexity?", "Rewrite it in Rust.", "Summarize the conversation in one line."],
              ["List five facts about the Moon, one per line.", "Expand the third fact into a paragraph.",
               "Give a short quiz of three questions on these facts.", "Answer the quiz.",
               "Translate the first fact into French.", "Write a haiku about it.", "Which fact is least known?",
               "Thank you. One last line about tides."]],
    "think": [["How many positive divisors does 360 have? Show the method briefly.",
               "And how many of them are even?", "What is the sum of all divisors of 360?",
               "Is 360 a highly composite number? Justify in a few lines.", "Name the next highly composite number after 360.",
               "Give one everyday reason 360 is used for degrees."]],
}
CAPS = {"plain": [48, None, 96, None, 30, None, 64, None], "think": [None, None, None, None, 200, None]}


def post(body):
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=1800).read())


def last_record():
    with urllib.request.urlopen(BASE + "/metrics?requests=all", timeout=30) as r:
        return json.loads(r.read())["requests"][0]


out, summary = [], {}
for mode in MODES:
    resumed = misses = 0
    for ci, conv in enumerate(TOPICS[mode]):
        msgs, prev = [], None
        for ti, q in enumerate(conv):
            msgs.append({"role": "user", "content": q})
            body = {"model": "x", "messages": msgs, "stream": False}
            if mode == "plain":
                body["reasoning_effort"] = "none"
            cap = CAPS[mode][ti % len(CAPS[mode])]
            if cap:
                body["max_tokens"] = cap
            d = post(body)
            m = d["choices"][0]["message"]
            rec = last_record()
            row = {"mode": mode, "conv": ci, "turn": ti, "cap": cap, "finish": d["choices"][0].get("finish_reason"),
                   "prompt_total": rec.get("prompt_total"), "reused": rec.get("reused"), "read": rec.get("prompt_read"),
                   "output": rec.get("output_tokens"), "engine_generated": rec.get("engine_generated"),
                   "prompt_ms": rec.get("prompt_ms")}
            if prev is not None:
                held = prev["prompt_total"] + (prev["engine_generated"] or prev["output"]) - 2
                row["held_prev_est"] = held
                row["resumed"] = (rec.get("reused") or 0) >= held
                row["fell_back_to"] = None if row["resumed"] else rec.get("reused")
                resumed += row["resumed"]
                misses += not row["resumed"]
            out.append(row)
            print(json.dumps(row), flush=True)
            a = {"role": "assistant", "content": m.get("content") or ""}
            if m.get("reasoning_content"):
                a["reasoning_content"] = m["reasoning_content"]
            msgs.append(a)
            prev = row
    summary[mode] = {"follow-ups": resumed + misses, "resumed": resumed, "misses": misses}
    print(f"followup {LABEL} {mode}: {resumed} of {resumed + misses} follow-ups resumed, {misses} re-read the answer", flush=True)
json.dump({"rows": out, "summary": summary}, open(f"/home/USER/ai-speed-testing/strata-compare/bringup/out/results/followup-{LABEL}.json", "w"), indent=1)
