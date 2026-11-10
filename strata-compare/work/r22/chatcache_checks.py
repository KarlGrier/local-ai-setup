#!/usr/bin/env python3
"""chatcache_checks.py URL ENGINE_LOG - the chat-cache checks before deep-research's parking policy is switched on
(2026-10-19, the user's item 3: "a resumed conversation must give the same output as a fresh one").

Run against a server started with STRATA_STATE_HASH=1 (the engine logs a fingerprint of the whole session after each
request) and nothing else using it. Greedy (temperature 0) and seeded sampled (1.0 / 0.95 / 20 / min-p 0.05, seed 7)
requests, 48 tokens each. A, B, R are three unrelated conversations of a few thousand tokens.

  1 fresh      A's question on an empty cache (after a long unrelated B, so A is read from scratch)  -> X_fresh, hash
  2 resumed    A, then B (A is parked), then A's question again (A restored from the chat cache)  -> X_res, hash
  3 ckpt=0     A's question with "strata_checkpoint": false  -> same output as the plain request
  4 drop       R tagged "research" (parked by B), a "strata_chat_drop": "research" request: the log says R was dropped;
               A (untagged, parked) is still restored afterwards

PASS = the identical reply text, and for the resume check also the identical STATE_HASH line (the whole session's
fingerprint, generated tokens included). Exit 1 on any FAIL.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request

URL, LOG = sys.argv[1].rstrip("/"), sys.argv[2]
SAMPLED = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "seed": 7}


def filler(topic: str, n: int) -> str:
    return " ".join(f"{topic} note {i}: the value recorded for item {i} is {i * 37 % 101}." for i in range(n))


A = [{"role": "user", "content": "Here are my notes on the garden:\n" + filler("garden", 220) +
      "\nWhich item has the value 36? Answer briefly."}]
B = [{"role": "user", "content": "Summarise this log in one line:\n" + filler("server", 260)}]
R = [{"role": "user", "content": "Research notes:\n" + filler("survey", 240) + "\nWhat is item 12's value?"}]


def chat(messages, sampling, **extra) -> str:
    body = {"model": "x", "messages": messages, "max_tokens": 48, "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}, **sampling, **extra}
    req = urllib.request.Request(URL + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=600) as r:
        d = json.loads(r.read())
    return d["choices"][0]["message"].get("content") or ""


def log_tail(start: int) -> str:
    with open(LOG, "rb") as f:
        f.seek(start)
        return f.read().decode("utf-8", "replace")


def log_size() -> int:
    with open(LOG, "rb") as f:
        f.seek(0, 2)
        return f.tell()


def last_hash(text: str) -> str | None:
    h = re.findall(r"STATE_HASH (L=\d+ .*)", text)
    return h[-1] if h else None


fails = 0


def check(cond: bool, what: str) -> None:
    global fails
    print(("PASS " if cond else "FAIL ") + what, flush=True)
    fails += 0 if cond else 1


for name, sp in (("greedy", {"temperature": 0}), ("sampled seed 7", SAMPLED)):
    # 1 fresh: B first (so nothing of A is cached), then A
    chat(B, sp)
    p = log_size()
    x_fresh = chat(A, sp)
    h_fresh = last_hash(log_tail(p))
    # 2 resumed: B again (A parked), then A again (restored)
    chat(B, sp)
    p = log_size()
    x_res = chat(A, sp)
    t = log_tail(p)
    check("chat cache: restored" in t, f"{name}: A was restored from the chat cache")
    check(x_res == x_fresh, f"{name}: resumed output = fresh output ({len(x_fresh)} chars)")
    check(h_fresh is not None and last_hash(t) == h_fresh, f"{name}: the session's STATE_HASH after it = fresh")
    # 3 ckpt=0: the same question without a checkpoint
    chat(B, sp)
    check(chat(A, sp, strata_checkpoint=False) == x_fresh, f"{name}: strata_checkpoint=false gives the same output")

# 4 drop: R tagged research and parked, A untagged and parked, then chat_drop=research
chat(R, {"temperature": 0}, strata_owner="research")
chat(A, {"temperature": 0})                     # R parked (tagged), A live
chat(B, {"temperature": 0})                     # A parked (untagged), B live
p = log_size()
chat(B, {"temperature": 0}, strata_chat_drop="research")
t = log_tail(p)
check(bool(re.search(r"chat cache: dropped 1 parked conversation of 'research'", t)), "drop: R (research) dropped")
p = log_size()
x = chat(A, {"temperature": 0})
check("chat cache: restored" in log_tail(p), "drop: A (untagged) still parked and restored after the drop")
p = log_size()
chat(R, {"temperature": 0}, strata_owner="research")
check("chat cache: restored" not in log_tail(p), "drop: R is read from scratch afterwards (not restored)")
print("ALL PASS" if fails == 0 else f"{fails} FAILED")
sys.exit(1 if fails else 0)
