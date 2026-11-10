#!/usr/bin/env python3
"""stoptest.py BASE LABEL — round 11 Phase 0.3: does the server honor OpenAI `stop` and Anthropic `stop_sequences`, streamed
and not, including a stop string that spans several tokens / streamed chunks?  The model counts 1..40 (no thinking, so the
text is predictable); each case checks: the text ends right before the stop string (nothing of it sent, in no chunk),
the finish reason (OpenAI "stop"; Anthropic stop_reason "stop_sequence" + stop_sequence), and that the engine stopped
early (completion tokens well below a full count).  One case with your xhigh thinking checks that a stop string is
matched in the answer only.  Prints one line per case and a verdict; JSON lines to results/r11/stoptest-LABEL.jsonl."""
import json
import sys
import time
import urllib.request

BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
PROMPT = "Count from 1 to 40 in digits, separated by a comma and a space, on one line. Output nothing else."
FULL = ", ".join(str(i) for i in range(1, 41))


def post(path, body, stream):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
                                                                                     "anthropic-version": "2023-06-01"})
    r = urllib.request.urlopen(req, timeout=600)
    if not stream:
        return json.loads(r.read()), []
    chunks = []
    for raw in r:
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("data:"):
            d = line[5:].strip()
            if d and d != "[DONE]":
                chunks.append(json.loads(d))
    return None, chunks


def openai(stop, stream, effort="none", max_tokens=400):
    body = {"model": "x", "messages": [{"role": "user", "content": PROMPT}], "max_tokens": max_tokens, "stream": stream,
            "reasoning_effort": effort}
    if stop is not None:
        body["stop"] = stop
    d, ch = post("/v1/chat/completions", body, stream)
    if not stream:
        c = d["choices"][0]
        return {"text": c["message"].get("content") or "", "finish": c.get("finish_reason"),
                "tokens": d["usage"]["completion_tokens"], "pieces": [c["message"].get("content") or ""]}
    pieces, finish, tokens = [], None, None
    for x in ch:
        if x.get("choices"):
            dl = x["choices"][0].get("delta", {})
            if dl.get("content"):
                pieces.append(dl["content"])
            finish = x["choices"][0].get("finish_reason") or finish
        if x.get("usage"):
            tokens = x["usage"].get("completion_tokens")
    return {"text": "".join(pieces), "finish": finish, "tokens": tokens, "pieces": pieces}


def anthropic(stops, stream, think=False, max_tokens=400):
    body = {"model": "x", "max_tokens": max_tokens, "stream": stream, "messages": [{"role": "user", "content": PROMPT}]}
    if think:
        body["thinking"] = {"type": "enabled", "budget_tokens": 4000}
        body["max_tokens"] = 6000
    if stops is not None:
        body["stop_sequences"] = stops
    d, ch = post("/v1/messages", body, stream)
    if not stream:
        text = "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
        return {"text": text, "finish": d.get("stop_reason"), "stop_sequence": d.get("stop_sequence"),
                "tokens": d["usage"]["output_tokens"], "pieces": [text]}
    pieces, finish, seq, tokens = [], None, None, None
    for x in ch:
        if x.get("type") == "content_block_delta" and x["delta"].get("type") == "text_delta":
            pieces.append(x["delta"]["text"])
        elif x.get("type") == "message_delta":
            finish = x["delta"].get("stop_reason")
            seq = x["delta"].get("stop_sequence")
            tokens = x.get("usage", {}).get("output_tokens")
    return {"text": "".join(pieces), "finish": finish, "stop_sequence": seq, "tokens": tokens, "pieces": pieces}


cases = [
    ("openai  no stop (control)", lambda: openai(None, False), None),
    ("openai  stop list ', 13'", lambda: openai([", 13"], False), ", 13"),
    ("openai  stop str '13,' stream", lambda: openai("13,", True), "13,"),
    ("openai  multi-token '11, 12, 13' stream", lambda: openai(["zzz", "11, 12, 13"], True), "11, 12, 13"),
    ("openai  near miss '13.' stream", lambda: openai(["13."], True), None),
    ("anthropic near miss stream", lambda: anthropic(["40!"], True), None),
    ("anthropic stop_sequences ['13'] ", lambda: anthropic(["13"], False), "13"),
    ("anthropic multi-token stream", lambda: anthropic(["21, 22, 23"], True), "21, 22, 23"),
    ("openai  xhigh thinking, stop '13'", lambda: openai(["13"], False, effort="high", max_tokens=6000), "13"),
]
ok_all = True
CONTROL = {}
with open(f"/home/USER/ai-speed-testing/strata-compare/results/r11/stoptest-{LABEL}.jsonl", "w") as f:
    for name, fn, stop in cases:
        t0 = time.time()
        r = fn()
        txt = r["text"].strip()
        if stop is None:
            ok = r["finish"] in ("stop", "end_turn") and "40" in txt
            why = "full text, natural end"
        else:
            i = FULL.find(stop)
            want = FULL[:i].strip()
            leaked = any(stop in "".join(r["pieces"][:k + 1]) for k in range(len(r["pieces"])))
            fin_ok = r["finish"] == "stop" if name.startswith("openai") else (r["finish"] == "stop_sequence" and r.get("stop_sequence") == stop)
            # 13:00 fix: compare with the same API's full count (its control). The Anthropic path thinks by default
            # (anthropic_think_unasked), so its counts include ~50-60 thinking tokens and a fixed "< 60" failed it
            # although the engine stopped (0.1.38 and 0.1.39: 93-135 tokens with a stop vs 209-214 without).
            ctl = CONTROL.get("openai" if name.startswith("openai") else "anthropic")
            early = "high" in name or (r["tokens"] or 999) < (0.75 * ctl if ctl else 60)
            ok = txt == want and not leaked and fin_ok and early
            why = f"want text ending '{want[-12:]}' got '{txt[-12:]}', leaked={leaked}, finish ok={fin_ok}, stopped early={early}"
        if stop is None and ok:
            CONTROL.setdefault("openai" if name.startswith("openai") else "anthropic", r["tokens"] or 0)
        ok_all &= ok
        rec = {"case": name, "ok": ok, "finish": r["finish"], "stop_sequence": r.get("stop_sequence"), "tokens": r["tokens"],
               "chunks": len(r["pieces"]), "text_tail": txt[-60:], "secs": round(time.time() - t0, 2)}
        f.write(json.dumps(rec) + "\n")
        print(f"{'PASS' if ok else 'FAIL'}  {name:40s} finish={r['finish']} seq={r.get('stop_sequence')} tokens={r['tokens']} "
              f"chunks={len(r['pieces'])} | {why}", flush=True)
print(f"stoptest {LABEL}: {'ALL PASS' if ok_all else 'FAILURES'}")
