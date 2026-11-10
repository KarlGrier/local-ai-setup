#!/usr/bin/env python3
"""think_client.py BASE OUTDIR EFFORTS PASSES [MAX_TOKENS] - 10-26 (the user, item 5: "at effort 75, all three prompts hit the
8,192-token limit, about 5 minutes of thinking at ~27 tok/s. Measure thinking tokens and time to the first answer token at
efforts 25, 50 and 75 on the same prompts, so Karl can choose a daily default for chat"). EFFORTS: comma list of numeric
efforts (62 = what "medium" renders on this engine, the current default, added for reference). The C.10 prompts (W1-think,
W2-code, W3-research, each with a fresh nonce as abrun sends them), max_tokens 8192 as in C.10, the user's sampling.
Per request: thinking tokens (stream deltas before the first answer delta; the server's reasoning_tokens when it reports
it), answer tokens, time to the first thinking token, time to the first ANSWER token, total time, finish, and whether the
thinking ended on its own or answer_room's budget ended it (a second engine pass in the engine log) -> OUTDIR/think.jsonl.
Order: pass by pass, effort by effort, prompt by prompt (so a slow drift does not land on one effort)."""
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402


def ask(base, w, effort, cap):
    body = {"model": "x", "messages": abrun.with_nonce(w["messages"]), "max_tokens": cap, "stream": True,
            "stream_options": {"include_usage": True}, "reasoning_effort": effort, **abrun.NORMAL}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic(); t_r = t_a = None; nr = na = 0; usage = {}; finish = None; last = {}
    with urllib.request.urlopen(req, timeout=7200) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            last = ev
            usage = ev.get("usage") or usage
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("reasoning_content") or d.get("reasoning"):
                    nr += 1
                    t_r = t_r or time.monotonic()
                if d.get("content"):
                    na += 1
                    t_a = t_a or time.monotonic()
                finish = ch.get("finish_reason") or finish
    t1 = time.monotonic()
    rt = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or last.get("reasoning_tokens")
    return {"thinking_deltas": nr, "answer_deltas": na, "reasoning_tokens": rt, "completion_tokens": usage.get("completion_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"), "t_first_thinking_s": round(t_r - t0, 2) if t_r else None,
            "t_first_answer_s": round(t_a - t0, 2) if t_a else None, "total_s": round(t1 - t0, 1), "finish": finish}


def main():
    base, out, efforts, passes = sys.argv[1].rstrip("/"), sys.argv[2], [int(x) for x in sys.argv[3].split(",")], int(sys.argv[4])
    cap = int(sys.argv[5]) if len(sys.argv) > 5 else 8192
    elog = sys.argv[6] if len(sys.argv) > 6 else None
    wl = [w for w in json.load(open(abrun.WL))["normal"] if w["id"].startswith(("W1", "W2", "W3"))]
    for p in range(passes):
        for e in efforts:
            for w in wl:
                off = os.path.getsize(elog) if elog and os.path.exists(elog) else 0
                r = ask(base, w, e, cap)
                time.sleep(1.0)
                new = open(elog, errors="replace").read()[off:] if elog and os.path.exists(elog) else ""
                npass = len(re.findall(r"(\d+) tokens = (\d+) reused \+ (\d+) read", new))
                r.update(id=w["id"], effort=e, rep=p, max_tokens=cap, engine_passes=npass,
                         thinking_ended="by the budget (answer_room's second pass)" if npass >= 2 else "on its own")
                with open(f"{out}/think.jsonl", "a") as f:
                    f.write(json.dumps(r) + "\n")
                print(f"think effort {e} {w['id']} pass {p + 1}: thinking {r['thinking_deltas']} deltas"
                      f"{' (' + str(r['reasoning_tokens']) + ' tokens)' if r['reasoning_tokens'] else ''}, answer {r['answer_deltas']}, "
                      f"first answer token {r['t_first_answer_s']} s, total {r['total_s']} s, finish {r['finish']}, "
                      f"thinking ended {r['thinking_ended']}", flush=True)


if __name__ == "__main__":
    main()
