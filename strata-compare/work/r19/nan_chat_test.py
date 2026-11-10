#!/usr/bin/env python3
"""nan_chat_test.py BASE ELOG OUT.json - round 19 Part D 1: v0.1.43's non-finite guard (#879) and our --chat-cache.

The server runs with STRATA_NAN_INJECT=1,60 (the guard reports the 1st and the 60th verify window it checks as non-finite).
  1. chat A, turn 1: window 1 is injected -> the server sends the request again from token 0 -> one normal answer
  2. chat B, turn 1: another conversation takes the session -> A is parked in OUR chat cache
  3. chat A, turn 2: A comes back from our chat cache (prompt tokens reused > 0: the positive control)
  4. chat B, turns 2..: until window 60 is injected mid-reply (that reply ends as "length")
  5. chat A, turn 3: must reuse 0 tokens - the guard drops upstream's parked conversations, and ours with them (the
     engine logs "... N chat-cache conversation(s) ..."); without the fix A would come back from our chat cache
The two documents are ~2,000-token slices of the corpus (prompts/r19/ttft-mid.json, different texts)."""
import json, re, sys, time, urllib.request
from pathlib import Path

base, elog, out = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3])
mid = json.loads(Path("/home/USER/ai-speed-testing/strata-compare/prompts/r19/ttft-mid.json").read_text())
docs = [p["messages"][0]["content"] for p in mid if p.get("size") == "2000"][:2]


def ask(msgs, max_tokens):
    off = elog.stat().st_size
    req = {"model": "x", "messages": msgs, "max_tokens": max_tokens, "reasoning_effort": "low"}
    r = urllib.request.urlopen(urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(req).encode(),
                                                      headers={"Content-Type": "application/json"}), timeout=600)
    j = json.load(r)
    time.sleep(0.5)
    with open(elog, "rb") as f:
        f.seek(off)
        log = f.read().decode("utf-8", "replace")
    reused = [int(m) for m in re.findall(r"prompt \d+ tokens = (\d+) reused", log)]
    m = j["choices"][0]["message"]
    return {"text": (m.get("content") or "")[:120], "finish": j["choices"][0].get("finish_reason"),
            "reused": reused, "inject": re.findall(r"STRATA_NAN_INJECT: window (\d+)", log),
            "flush": re.findall(r"after non-finite logits \(#879\): [^\n]*", log),
            "nonfinite": len(re.findall(r"non-finite logits \(#879\) in a", log))}


res = []
A = [{"role": "user", "content": docs[0] + "\n\nIn one sentence: what is this material about?"}]
B = [{"role": "user", "content": docs[1] + "\n\nIn one sentence: what is this material about?"}]
def step(name, msgs, n):
    r = ask(msgs, n); r["step"] = name; res.append(r)
    print(f"{name}: finish {r['finish']}, reused {r['reused']}, injected {r['inject']}, flush {len(r['flush'])}"
          + (f" -> {r['flush'][0][:160]}" if r["flush"] else ""), flush=True)
    return r
r = step("A1", A, 16); A += [{"role": "assistant", "content": r["text"]}, {"role": "user", "content": "Name one detail from it."}]
r = step("B1", B, 16); B += [{"role": "assistant", "content": r["text"]}, {"role": "user", "content": "Name one detail from it."}]
r = step("A2 (A back from our chat cache)", A, 16); A += [{"role": "assistant", "content": r["text"]}, {"role": "user", "content": "And another one?"}]
fired = False
for k in range(2, 8):
    r = step(f"B{k}", B, 200)
    B += [{"role": "assistant", "content": r["text"]}, {"role": "user", "content": "Go on, in more detail."}]
    if "60" in r["inject"]:
        fired = True
        break
r = step("A3 (after the guard fired in B)", A, 16)
a2_reuse = max(res[2]["reused"] or [0]); a3_reuse = max(r["reused"] or [0])
chat_dropped = any("chat-cache conversation" in f and not re.search(r", 0 chat-cache conversations", f) for f in r["flush"])
verdict = {"window_1_injected_and_answered": "1" in res[0]["inject"] and res[0]["finish"] in ("stop", "length"),
           "a2_reused_from_chat_cache": a2_reuse > 0, "window_60_fired_in_b": fired,
           "a3_reused_0": a3_reuse == 0, "a3_flush_dropped_our_chat_cache": chat_dropped}
print("VERDICT:", "PASS" if all(verdict.values()) else "FAIL", json.dumps(verdict), flush=True)
out.write_text(json.dumps({"steps": res, "verdict": verdict}, indent=1))
