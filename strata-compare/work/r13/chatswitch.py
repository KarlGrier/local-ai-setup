#!/usr/bin/env python3
"""chatswitch.py --config LABEL --engine-log LOG [--session S] — round 13 Phase 0 item 4: decode after a CHAT SWITCH.
Two research chats from the LDR pool (prompts/r10/ldr-pool.json, never a holdout): A = windblade-synthesis (~20K
tokens), B = gnss-synthesis (~18K); then A's follow-up (A's messages + A's answer + a new question) after B, and B's
follow-up after A's: the follow-ups resume a parked chat from the chat cache, and their decode blocks are the
"after a chat switch" case.  Same streaming client and records as ldrbench.py (scenario "chatswitch", results/runs.jsonl);
no sampling fields: the config's shared settings apply (yours)."""
import argparse
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from bench import Runner  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--base", default="http://127.0.0.1:8081")
ap.add_argument("--engine-log", default="")
ap.add_argument("--session", default="")
ap.add_argument("--max-tokens", type=int, default=2048)
a = ap.parse_args()
a.model, a.extra = "x", ""
pool = {r["id"]: r for r in json.loads((WS / "prompts/r10/ldr-pool.json").read_text(encoding="utf-8"))}
A, B = pool["windblade-synthesis"], pool["gnss-synthesis"]
FOLLOW = ("Thanks. Now take the two weakest claims in your answer, explain exactly which of the sources above they "
          "rest on, and rewrite those two sections so that every sentence is supported by a cited source.")
R = Runner(a)
R.extra = {}
answers = {}
for name, req in (("A", A), ("B", B)):
    rec = R.call("chatswitch", f"{name}-first", 0, req["messages"], a.max_tokens, save_text=True, note="first")
    out = json.loads((WS / rec["output_file"]).read_text(encoding="utf-8"))
    answers[name] = out.get("content") or ""
for name, req in (("A", A), ("B", B)):
    msgs = list(req["messages"]) + [{"role": "assistant", "content": answers[name]}, {"role": "user", "content": FOLLOW}]
    R.call("chatswitch", f"{name}-switchback", 0, msgs, a.max_tokens, save_text=True, note="switchback")
print("chatswitch done")
