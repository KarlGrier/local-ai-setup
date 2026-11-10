#!/usr/bin/env python3
"""conc21_prompts.py - 2026-10-20, the user's concurrency test on 0.2.1: the two prompt sets, 4 different requests each.

  chat   a short chat turn (one line asking for a long answer), so every request runs to its fixed max_tokens
  agent  a coding agent's turn (round 20's builder, work/r20/conc_prompts.py: system prompt, seven tool definitions,
         read_file / search results from the Python 3.12 standard library), cut to ~20K tokens, then a user line asking
         for a long written review before any tool call, so the reply runs to its fixed max_tokens as well
Thinking is off in the driver (answer_room only acts on thinking), so the length is the max_tokens cap every time.
Writes results/r22/conc/prompts.json (token counts by the model's own tokenizer, an estimate; the server's usage is the
measured count)."""
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "work/r20"))
import conc_prompts as CP  # noqa: E402

OUT = WS / "results/r22/conc"
TARGET = 20000
AGENT_IDS = ("argparse", "json", "configparser", "logging")
REVIEW = ("Before you change anything: do not call a tool in this reply. Write a detailed review of the code you have "
          "read for this task - the functions involved, how the data flows through them, every caller you found, the "
          "edge cases and the risks of the change - and then your step-by-step plan with the exact edits you will "
          "make. Be thorough: at least 1,500 words.")
CHAT = [
    ("hash", "Explain in detail how a hash table works - hashing, collision handling, resizing and load factors - with "
             "worked examples. Write at least 1,500 words."),
    ("story", "Write a long short story (at least 2,000 words) about a lighthouse keeper who finds a message in a "
              "bottle addressed to her."),
    ("tcp", "Compare TCP and UDP in depth: header fields, connection handling, congestion control, typical uses and "
            "common pitfalls. At least 1,500 words."),
    ("todo", "Write a step-by-step beginner tutorial for a Python command-line to-do app with argparse and JSON "
             "storage, with the full code and an explanation of every part. At least 1,500 words."),
]


def agent_messages(task, nonce, budget_chars):
    return CP.agent_messages(task, nonce, budget_chars) + [{"role": "user", "content": REVIEW}]


def main():
    tok = CP.load_tok(json.loads((WS / "configs/P021.json").read_text())["tokenizer"])
    count = lambda msgs: len(tok.encode(json.dumps(msgs, ensure_ascii=False))) + 40 * len(msgs)   # noqa: E731
    tools_tokens = len(tok.encode(json.dumps(CP.TOOLS)))
    agent = []
    for t in (x for x in CP.TASKS if x[0] in AGENT_IDS):
        lo, hi = 10000, 400000                    # chars of file content; bisect to ~TARGET tokens
        for _ in range(14):
            mid = (lo + hi) // 2
            if count(agent_messages(t, "[session L0-R0]", mid)) + tools_tokens < TARGET:
                lo = mid
            else:
                hi = mid
        agent.append({"id": t[0], "budget_chars": lo,
                      "est_tokens": count(agent_messages(t, "[session L0-R0]", lo)) + tools_tokens})
    chat = [{"id": i, "messages": [{"role": "user", "content": p}], "est_tokens": len(tok.encode(p))} for i, p in CHAT]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "prompts.json").write_text(json.dumps({"tools": CP.TOOLS, "agent": agent, "chat": chat}, indent=1))
    for x in agent + chat:
        print(x["id"], x["est_tokens"])


if __name__ == "__main__":
    main()
