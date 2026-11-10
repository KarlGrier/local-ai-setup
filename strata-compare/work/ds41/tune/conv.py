#!/usr/bin/env python3
"""conv.py PHASE BASE OUTDIR ENGINE_LOG SLOT_DIR STATEFILE - 10-24 DeepSeek-V4.1 tuning round, the conversation-cache
pass/fail test (the user: "STRATA_DS4_SLOT_KEEP=1, STRATA_DS4_AUTO_PIN=1, a larger STRATA_DS4_SLOT_GB. Test: a ~20K
conversation, then a different conversation, then back to the first with a 300-token follow-up, then the same after an
engine restart. Report reused tokens, time to first token and disk writes per turn"), plus C.10 (how long DS4.1 thinks
at the default effort on W1-W3).
  phase 1 (engine run 1): conversation A in 5 turns growing to ~20K tokens (each turn ~4K tokens of Strata's public docs
          plus a question; answers at the template's default effort, 1,200 tokens); conversation B (1 turn, ~2K tokens);
          back to A with a ~300-token follow-up. A's messages -> STATEFILE.
  phase 2 (engine run 2, after a restart, slots on): A's ~300-token follow-up as the engine's first request (seed 4242,
          256 tokens) - resumed from the disk slot.
  phase 3 (engine run 3, slots off, no slot folder): the same request, again the engine's first - a fresh prefill of the
          ~20K conversation. Same prompt, seed and sampling counter as phase 2, so the texts match exactly unless the
          resumed state's numbers differ from a fresh read (the engine's prompt and decode paths round differently);
          conv.jsonl records both texts. Then C.10: W1, W2, W3 once each at the default effort ("high" = 75) with
          8,192 tokens (the server leaves 6,144 for thinking). (LDR add-on, 10-24: "resume a ~20K chat from a slot vs
          a fresh prefill. Record exact match, time to first token, RAM used and bytes written to disk".)
Per turn: TTFT, prompt tokens, the engine's "N tokens = X reused + Y read" line, the engine's write_bytes and RSS, the
slot folder's size -> OUTDIR/conv.jsonl; C.10 -> OUTDIR/think.jsonl.
"""
import json
import os
import re
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402

DOCS = "/home/USER/ai-speed-testing/strata-compare/strata-v024/docs"
SYS = "You are a helpful assistant. Answer clearly and concisely."
QS = ["Here is part of a document about my inference engine. Summarise what it says, in five bullet points.",
      "Here is the next part. How does it relate to what you summarised before?",
      "Next part. Which of the settings mentioned so far would matter most on a PC with a 16 GB and an 8 GB GPU?",
      "Next part. List the numbers (speeds, sizes) given across all the parts so far, with what they refer to.",
      "Last part. Give me a one-paragraph summary of all five parts and the three most useful tips."]
FOLLOW = ("Thanks. A follow-up on everything above: I am deciding between keeping long prompts on two GPUs or moving to "
          "one GPU with a bigger RAM store. Based only on the parts I gave you, list the trade-offs you can find, say which "
          "statements in the parts support each one (quote a few words), and tell me what you would measure first to decide, "
          "in order, with the reason for each step. Keep it under 300 words and do not repeat the earlier summaries. "
          "If the parts say nothing about one of these points, say so plainly rather than guessing. ")


def text(n_chars):
    t = ""
    for name in sorted(os.listdir(DOCS)):
        if name.endswith(".md"):
            t += open(os.path.join(DOCS, name), encoding="utf-8", errors="replace").read() + "\n\n"
        if len(t) > n_chars:
            break
    return t


def engine_pid():
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if os.path.basename(os.readlink(f"/proc/{p}/exe")) == "strata-dsv41":
                    return int(p)
            except OSError:
                pass


def wbytes(pid):
    try:
        return int(next(l for l in open(f"/proc/{pid}/io") if l.startswith("write_bytes:")).split()[1])
    except (OSError, StopIteration, TypeError):
        return None


def du(d):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs) if os.path.isdir(d) else 0


def rss_mb(pid):
    try:
        return int(next(l for l in open(f"/proc/{pid}/status") if l.startswith("VmRSS:")).split()[1]) // 1024
    except (OSError, StopIteration, TypeError):
        return None


def chat(base, messages, max_tokens=1200, seed=None):
    body = {"model": "x", "messages": messages, "max_tokens": max_tokens, "stream": True,
            "stream_options": {"include_usage": True}, "reasoning_effort": "high", **abrun.NORMAL}
    if seed is not None:
        body["seed"] = seed
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic(); t1 = None; content = []; rtext = []; usage = None; finish = None
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            usage = ev.get("usage") or usage
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if (d.get("content") or d.get("reasoning_content") or d.get("reasoning")) and t1 is None:
                    t1 = time.monotonic()
                content.append(d.get("content") or "")
                rtext.append(d.get("reasoning_content") or d.get("reasoning") or "")
                finish = ch.get("finish_reason") or finish
    return {"ttft_s": round(t1 - t0, 2) if t1 else None, "total_s": round(time.monotonic() - t0, 1),
            "answer": "".join(content), "text": "".join(rtext) + "\n</think>\n" + "".join(content), "usage": usage or {}, "finish": finish}


class Turns:
    def __init__(self, base, out, elog, slots):
        self.base, self.out, self.elog, self.slots, self.pid = base, out, elog, slots, engine_pid()
        self.off = os.path.getsize(elog) if os.path.exists(elog) else 0

    def turn(self, label, msgs, max_tokens=1200, seed=None, keep_text=False):
        w0, s0, m0 = wbytes(self.pid), du(self.slots), rss_mb(self.pid)
        r = chat(self.base, msgs, max_tokens, seed)
        time.sleep(1.5)                                   # the engine writes its profile (and any slot) after the reply
        w1, s1, m1 = wbytes(self.pid), du(self.slots), rss_mb(self.pid)
        new = open(self.elog, encoding="utf-8", errors="replace").read()[self.off:] if os.path.exists(self.elog) else ""
        self.off = os.path.getsize(self.elog) if os.path.exists(self.elog) else self.off
        m = re.findall(r"(\d+) tokens = (\d+) reused \+ (\d+) read", new)
        extra = re.findall(r"[^\n]*(?:slot|restor|checkpoint|pin)[^\n]*", new, re.I)
        rec = {"turn": label, "prompt_tokens": r["usage"].get("prompt_tokens"), "completion_tokens": r["usage"].get("completion_tokens"),
               "ttft_s": r["ttft_s"], "total_s": r["total_s"], "finish": r["finish"],
               # the turn's own prompt is the FIRST pass; a second pass is answer_room's continuation (prompt + thinking +
               # wrap-up, always reused) - m[-1] reported that one as the turn's reuse (fixed 10-25 15:55)
               "reused": int(m[0][1]) if m else None, "read": int(m[0][2]) if m else None,
               "passes": [[int(a), int(b), int(c)] for a, b, c in m],
               "engine_write_mb": round((w1 - w0) / 1e6, 2) if w0 is not None and w1 is not None else None,
               "slot_dir_mb": round(s1 / 1e6, 2), "slot_dir_delta_mb": round((s1 - s0) / 1e6, 2), "engine_rss_mb": m1,
               "engine_rss_delta_mb": m1 - m0 if m0 is not None and m1 is not None else None, "engine_lines": [x[:200] for x in extra[-4:]]}
        if keep_text:
            rec["text"] = r["text"]
        with open(f"{self.out}/conv.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{label}: prompt {rec['prompt_tokens']} = {rec['reused']} reused + {rec['read']} read, TTFT {rec['ttft_s']} s, "
              f"engine wrote {rec['engine_write_mb']} MB, RSS {rec['engine_rss_mb']} MB ({rec['engine_rss_delta_mb']:+} MB), "
              f"slot folder {rec['slot_dir_mb']} MB", flush=True)
        return r


def main():
    phase, base, out, elog, slots, sf = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
    t = Turns(base, out, elog, slots)
    if phase == "1":
        src = text(130000)
        A = [{"role": "system", "content": SYS}]
        for i in range(5):
            A.append({"role": "user", "content": f"{QS[i]}\n\n[part {i + 1}, {uuid.uuid4().hex[:6]}]\n{src[i * 16000:(i + 1) * 16000]}"})
            A.append({"role": "assistant", "content": t.turn(f"A{i + 1}", A)["answer"]})
        B = [{"role": "system", "content": "You are a careful reviewer."},
             {"role": "user", "content": "Different topic. Summarise this text in three bullet points:\n\n" + src[90000:98000]}]
        t.turn("B1", B)
        A.append({"role": "user", "content": FOLLOW})
        A.append({"role": "assistant", "content": t.turn("A6 (back to A after B)", A, 900)["answer"]})
        A.append({"role": "user", "content": FOLLOW.replace("Thanks. A follow-up", "One more follow-up")})
        json.dump(A, open(sf, "w"))
    elif phase == "2":
        A = json.load(open(sf))
        t.turn("A7 (after an engine restart, from the disk slot)", A, 256, seed=4242, keep_text=True)
    else:
        A = json.load(open(sf))
        t.turn("A7 fresh (slots off: a fresh prefill of the whole conversation)", A, 256, seed=4242, keep_text=True)
        wl = json.load(open(abrun.WL))
        for w in wl["normal"]:
            if w["id"].startswith(("W1", "W2", "W3")):
                rec = abrun.one(base, "think", dict(w, effort="high", max_tokens=8192), abrun.NORMAL, {}, 0, f"{out}/think.jsonl")
                print(f"C.10 {w['id']}: {rec.get('completion_tokens')} tokens, thinking {rec.get('reasoning_chars')} chars, "
                      f"answer {rec.get('content_chars')} chars, finish {rec.get('finish')}", flush=True)


if __name__ == "__main__":
    main()
