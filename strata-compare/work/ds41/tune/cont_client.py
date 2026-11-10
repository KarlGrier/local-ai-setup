#!/usr/bin/env python3
"""cont_client.py BASE OUTDIR ENGINE_LOG [exact] - 10-25 (the user, B.3: "Continuation fix: replay the follow-up cases our fix
covered, using Jan's request format. Confirm the DS slots actually get reused (check the 'reused' count) and the output is
exact"). The answer_room continuation: when the thinking reaches its budget the server stops the pass and sends the prompt +
what was generated + the wrap-up again, so the engine should go on from the state it holds. P021m's fix (keep=1 + the
STOP race fix, tcap/tend) is Qwen-engine code; dsv41 has no tcap/tend and ignores ckpt=0, so this measures it as it is.
Cases (P021m's, work/r22/contarm.sh + toolcall_check.py):
  jan1024  Jan's search question with Jan's two MCP tools as Jan sends them, max_tokens 1024: answer_room closes the
           thinking at 768 and the call is written in the continuation pass                                  x3
  jan4096  the same at Jan's usual cap 4096                                                                     x2
  w1       W1 at its cap 3072 (budget 2,304)                                                                    x3
  w1k      W1 with "strata_checkpoint": false, as deep-research's one-shot calls                                x2
Normal mode: a fresh request line each time (no prompt reuse across requests). A request's second engine pass is its
continuation: a hit reads <= 64 tokens, a miss re-reads the thinking (the engine's "N tokens = X reused + Y read" lines).
"exact": every case twice in a row with no request line and seed 4242 - run it with placement frozen (--no-expert-cache),
so no VRAM swap can move a near-tie between the two: the two texts (thinking, answer, tool calls) must be identical.
-> OUTDIR/cont.jsonl + OUTDIR/cont.json
"""
import json
import os
import re
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/r22")
import abrun  # noqa: E402
import toolcall_check  # noqa: E402

LINE = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read .*?, (\d+) generated")


def ask(base, msgs, tools, cap, extra, nonce, seed):
    if nonce:
        msgs = [dict(msgs[0], content=f"[request {uuid.uuid4().hex[:8]}]\n" + msgs[0]["content"])] + msgs[1:]
    body = {"model": "x", "messages": msgs, "max_tokens": cap, "stream": True, "reasoning_effort": "medium", **abrun.NORMAL,
            **extra}
    if tools:
        body["tools"] = tools
    if seed is not None:
        body["seed"] = seed
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    reasoning, content, calls, finish = [], [], {}, None
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                reasoning.append(d.get("reasoning_content") or d.get("reasoning") or "")
                content.append(d.get("content") or "")
                for tc in d.get("tool_calls") or []:
                    c = calls.setdefault(tc.get("index", 0), {"name": "", "args": ""})
                    f = tc.get("function") or {}
                    c["name"] += f.get("name") or ""
                    c["args"] += f.get("arguments") or ""
                finish = ch.get("finish_reason") or finish
    return {"reasoning": "".join(reasoning), "content": "".join(content), "calls": [calls[k] for k in sorted(calls)],
            "finish": finish, "s": round(time.monotonic() - t0, 1)}


def main():
    base, out, elog = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    exact = len(sys.argv) > 4 and sys.argv[4] == "exact"
    w1 = next(w for w in json.load(open(abrun.WL))["normal"] if w["id"].startswith("W1"))
    jan_q = [{"role": "user", "content": "What is the newest stable Linux kernel release right now, and when did it come out? "
                                         "Look it up, don't answer from memory."}]
    jt = toolcall_check.jan_tools()
    cases = [("jan1024", jan_q, jt, 1024, {}, 3), ("jan4096", jan_q, jt, 4096, {}, 2),
             ("w1", w1["messages"], None, 3072, {}, 3), ("w1k", w1["messages"], None, 3072, {"strata_checkpoint": False}, 2)]
    recs = []
    for name, msgs, tools, cap, extra, reps in cases:
        for rep in range(2 if exact else reps):
            off = os.path.getsize(elog)
            r = ask(base, msgs, tools, cap, extra, nonce=not exact, seed=4242 if exact else None)
            time.sleep(1.5)
            passes = [tuple(map(int, m.groups())) for m in LINE.finditer(open(elog, errors="replace").read()[off:])]
            cont = passes[1] if len(passes) > 1 else None
            rec = {"case": name, "rep": rep + 1, "cap": cap, "passes": passes, "continuation": None if cont is None else
                   ("hit" if cont[2] <= 64 else "MISS"), "finish": r["finish"], "s": r["s"], "thinking_chars": len(r["reasoning"]),
                   "answer_chars": len(r["content"]), "calls": [c["name"] for c in r["calls"]], "text": r}
            recs.append(rec)
            with open(f"{out}/cont.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"{name} #{rep + 1}: passes {[(p[0], p[1], p[2], p[3]) for p in passes]} (prompt, reused, read, generated) -> "
                  f"continuation {rec['continuation']}; finish {r['finish']}, calls {rec['calls']}, {r['s']} s", flush=True)
    hits = sum(1 for x in recs if x["continuation"] == "hit")
    miss = sum(1 for x in recs if x["continuation"] == "MISS")
    res = {"mode": "exact" if exact else "normal", "requests": len(recs), "hits": hits, "misses": miss,
           "no_continuation": sum(1 for x in recs if x["continuation"] is None)}
    if exact:
        pairs = {}
        for x in recs:
            pairs.setdefault(x["case"], []).append(x["text"])
        res["identical"] = {k: v[0] == v[1] for k, v in pairs.items() if len(v) == 2}
    json.dump(res, open(f"{out}/cont.json", "w"), indent=1)
    print(f"continuations ({res['mode']}): {hits} hits, {miss} misses, {res['no_continuation']} requests without one (the "
          f"thinking ended before the budget)" + (f"; identical pairs: {res['identical']}" if exact else ""), flush=True)


if __name__ == "__main__":
    main()
