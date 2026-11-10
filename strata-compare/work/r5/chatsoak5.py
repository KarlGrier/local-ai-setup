#!/usr/bin/env python3
"""chatsoak5.py — round 5 (chatsoak4.py + web-search chats in bigsoak: strata_web, tool rounds sent back like the page).
chatsoak4.py — round 4 (round 3's chatsoak.py + mode bigsoak): traffic shaped like Strata's own chat page (serve/web/app.js), several chats at once.

Every request is what the page sends with its built-in settings: the chat's whole history (user messages and the
assistant replies WITHOUT their thinking; an assistant message stopped before it had any answer text is left out,
like the page does), stream=true, reasoning_effort "high" (= xhigh), temperature 0.6, top_p 0.95, top_k 20, no
min_p (the server's config supplies 0.05), NO max_tokens. The Stop button = closing the stream.

  switch  a fixed sequence for the time-to-first-token of going back to a chat: chat A grows to ~40K tokens
          (the multiturn prompts), then B (a new short chat), back to A, C (a new chat with a pasted 64K document),
          back to A, D (long reasoning), back to A, back to B, back to C.
  soak    a timed mix over 4-5 chats: new messages, a pasted big document in a new chat, long reasoning, Stop
          mid-answer, regenerate (the last message sent again), switching between chats at random.

Each request -> results/runs.jsonl (config LABEL, scenario chat_*), with the engine's reused/read counts from its
log.   chatsoak.py MODE --base URL --label L --engine-log PATH [--minutes M] [--seed S]
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/scripts")
from common import PROMPTS, RESULTS, append_jsonl, meminfo, now_iso  # noqa: E402

ENGINE_RE = re.compile(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms")
PAGE = {"stream": True, "reasoning_effort": "high", "temperature": 1.0, "top_p": 0.95, "top_k": 20}   # your chat settings (temperature 1.0 since 2026-09-28 18:29)


def load(n):
    return json.loads((PROMPTS / f"{n}.json").read_text(encoding="utf-8"))


def gpu_used():
    import subprocess
    try:
        return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                  capture_output=True, text=True, timeout=10).stdout.split()[0])
    except Exception:
        return -1


def engine_rss_mib():
    import subprocess
    best = -1                                   # the engine = the largest process matching (not the monitor)
    for pid in subprocess.run(["pgrep", "-f", "strata --serve"], capture_output=True, text=True).stdout.split():
        try:
            for line in open(f"/proc/{pid}/status"):
                if line.startswith("VmRSS"):
                    best = max(best, int(line.split()[1]) // 1024)
        except Exception:
            pass
    return best


class Page:
    def __init__(self, base, model, log_path, label, session):
        self.base, self.model, self.log, self.label, self.session = base.rstrip("/"), model, log_path, label, session
        self.log_pos = Path(log_path).stat().st_size if log_path and Path(log_path).exists() else 0
        self.errors = 0

    def engine_line(self):
        if not self.log or not Path(self.log).exists():
            return {}
        with open(self.log, "rb") as f:
            f.seek(self.log_pos)
            data = f.read().decode("utf-8", "replace")
            self.log_pos = f.tell()
        m = None
        for m in ENGINE_RE.finditer(data):
            pass
        extra = {"chat_cache": [ln.split("chat cache: ", 1)[1] for ln in data.splitlines() if "chat cache: " in ln]}
        if not m:
            return extra
        return {"prompt": int(m[1]), "reused": int(m[2]), "read": int(m[3]), "prompt_ms": float(m[4]), **extra}

    def send(self, chat, scen, item, stop_after=None, stop_on_content=None, extra=None):
        """one page request for `chat` (a list of {role, text, stopped}); appends the assistant message like the page.
        stop_after: seconds after the first token to press Stop; stop_on_content: seconds after the first answer
        (content) token."""
        msgs = []
        for m in chat:
            if m["role"] == "user":
                msgs.append({"role": "user", "content": m["text"]})
            elif m.get("tools") and not m.get("error"):
                ran = [t for t in m["tools"] if t.get("round") is not None and t.get("result") is not None]
                for rnd in sorted({t["round"] for t in ran}):
                    calls = [t for t in ran if t["round"] == rnd]
                    msgs.append({"role": "assistant", "content": "", "tool_calls": [
                        {"id": t["id"], "type": "function", "function": {"name": t["name"],
                                                                         "arguments": json.dumps(t.get("arguments") or {})}}
                        for t in calls]})
                    msgs += [{"role": "tool", "tool_call_id": t["id"], "content": t["result"]} for t in calls]
                if m.get("text"):
                    msgs.append({"role": "assistant", "content": m["text"]})
            elif m.get("text") and not m.get("error"):
                msgs.append({"role": "assistant", "content": m["text"]})
        body = {"model": self.model, "messages": msgs, **PAGE, **(extra or {})}
        t0 = time.perf_counter()
        t_first = t_content = None
        reasoning, content, finish, err, usage, stopped = [], [], None, None, None, False
        tools = {}
        try:
            with requests.post(self.base + "/v1/chat/completions", json=body, stream=True, timeout=7200) as r:
                if r.status_code != 200:
                    err = f"HTTP {r.status_code}: {r.text[:300]}"
                else:
                    for raw in r.iter_lines():
                        if not raw.startswith(b"data: "):
                            continue
                        if raw[6:] == b"[DONE]":
                            break
                        c = json.loads(raw[6:])
                        if c.get("error"):
                            err = str(c["error"])[:300]
                        if c.get("usage"):
                            usage = c["usage"]
                        x = c.get("strata_mcp")
                        if x and x.get("id"):
                            t = tools.setdefault(x["id"], {"id": x["id"], "name": x.get("name")})
                            if x.get("event") == "call":
                                t.update(name=x["name"], arguments=x.get("arguments"), round=x.get("round"))
                            elif x.get("event") == "result" and not x.get("skipped"):
                                t.update(result=x.get("text"), ok=x.get("ok"))
                        for ch in c.get("choices") or []:
                            d = ch.get("delta") or {}
                            now = time.perf_counter()
                            if d.get("reasoning_content"):
                                reasoning.append(d["reasoning_content"])
                                t_first = t_first or now
                            if d.get("content"):
                                content.append(d["content"])
                                t_first = t_first or now
                                t_content = t_content or now
                            if ch.get("finish_reason"):
                                finish = ch["finish_reason"]
                        now = time.perf_counter()
                        if (stop_after is not None and t_first and now - t_first > stop_after) or \
                                (stop_on_content is not None and t_content and now - t_content > stop_on_content):
                            stopped = True
                            break                                   # the Stop button: the page aborts the fetch
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:300]
        t_end = time.perf_counter()
        chat.append({"role": "assistant", "text": "".join(content), "stopped": stopped, "error": err,
                     "tools": list(tools.values())})
        time.sleep(0.3)                                             # the engine log line lands after DONE
        eng = self.engine_line()
        mem = meminfo()
        n_out = (usage or {}).get("completion_tokens")
        row = {"config": self.label, "session": self.session, "scenario": scen, "item": item, "started": now_iso(),
               "ttft_s": (t_first - t0) if t_first else None, "t_total_s": t_end - t0, "finish_reason": finish,
               "stopped": stopped, "error": err, "reasoning_chars": sum(map(len, reasoning)),
               "content_chars": sum(map(len, content)), "usage": usage, "engine": eng, "history_msgs": len(msgs),
               "memavail_mib_after": mem["MemAvailable"] // 1024, "gpu_used_mib_after": gpu_used(),
               "engine_rss_mib": engine_rss_mib(), "completion_tokens": n_out,
               "tool_calls": [(t.get("name"), t.get("ok")) for t in tools.values()],
               "decode_tps": (n_out - 1) / (t_end - t_first) if n_out and t_first and t_end - t_first > 0.5 else None}
        append_jsonl(RESULTS / "runs.jsonl", row)
        bad = bool(err) or (not stopped and not finish)
        self.errors += bad
        print(f"{time.strftime('%H:%M:%S')} {scen:16s} {item:14s} prompt {eng.get('prompt')} reused {eng.get('reused')} "
              f"ttft {row['ttft_s'] or 0:6.2f}s total {row['t_total_s']:6.1f}s {'STOP' if stopped else finish} "
              f"{' | ' + '; '.join(eng.get('chat_cache', [])) if eng.get('chat_cache') else ''}"
              f"{' | tools ' + ','.join(f'{n}:{o}' for n, o in row['tool_calls']) if row['tool_calls'] else ''}"
              f" | rss {row['engine_rss_mib']} memavail {row['memavail_mib_after']} gpu {row['gpu_used_mib_after']}"
              f"{' ERROR ' + str(err) if bad else ''}", flush=True)
        return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["switch", "soak", "bigsoak"])
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--model", default="x")
    ap.add_argument("--label", required=True)
    ap.add_argument("--engine-log", default="")
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()
    session = f"{a.label}-{a.mode}-{time.strftime('%m%dT%H%M')}"
    pg = Page(a.base, a.model, a.engine_log, a.label, session)
    mt, speed, lr, corr = load("multiturn"), load("speed"), load("longreason"), load("correctness")
    doc64 = next(p for p in speed if (p["size"], p["rep"]) == ("64k", 1))
    doc32 = next(p for p in speed if (p["size"], p["rep"]) == ("32k", 1))
    short_q = [c["messages"][-1]["content"] for c in corr]

    def user(chat, text):
        chat.append({"role": "user", "text": text})

    def mt_turn(chat, k, tag):
        user(chat, mt["turns"][k]["user"].replace("[Chat mt-7f3a]", f"[Chat {tag}]"))

    def fix_last(chat, k):               # the fixed assistant reply of the multiturn set (a deterministic history)
        chat[-1]["text"] = mt["turns"][k]["assistant"]

    if a.mode == "switch":
        A, B, C, D = [], [], [], []
        tag = f"sw-{int(time.time()) % 100000}"
        for k in range(7):                                         # chat A to 39.6K tokens
            mt_turn(A, k, tag)
            pg.send(A, "chat_build", f"A{k + 1}", stop_after=4)
            fix_last(A, k)
        user(B, short_q[0]); pg.send(B, "chat_other", "B1 short", stop_on_content=3)
        user(A, "Summarize the discussion so far in three bullet points."); pg.send(A, "chat_back", "A8 after B", stop_after=3)
        user(C, doc64["messages"][-1]["content"]); pg.send(C, "chat_other", "C1 64K paste", stop_after=4)
        user(A, "Which of the points above matters most, and why?"); pg.send(A, "chat_back", "A9 after C 64K", stop_after=3)
        user(D, lr[0]["messages"][-1]["content"]); pg.send(D, "chat_other", "D1 reasoning", stop_after=45)
        user(A, "Give one concrete next step."); pg.send(A, "chat_back", "A10 after D", stop_after=3)
        user(B, short_q[1]); pg.send(B, "chat_back", "B2", stop_on_content=3)
        user(C, "What is the main topic of that document, in one sentence?"); pg.send(C, "chat_back", "C2 64K", stop_after=3)
        user(A, "Thanks. One more: what would you check first?"); pg.send(A, "chat_back", "A11", stop_after=3)
    elif a.mode == "bigsoak":
        # Round 4 soak: many BIG chats (a pasted 32K / 64K / 120K document each) so the chat cache (6 slots, 16 GiB)
        # is always full and least-recently-used drops happen often; going back to old chats, follow-ups, Stop,
        # regenerate, long reasoning, short new chats; every ~10 min a fixed probe (a new chat with the same 32K
        # document, 512 tokens) to see slowdowns over time.
        rng = random.Random(a.seed)
        t_end = time.time() + a.minutes * 60
        docs = [p for p in speed if p["size"] in ("32k", "64k", "120k")]
        probe_doc = next(p for p in speed if (p["size"], p["rep"]) == ("32k", 2))
        chats = {}
        n = 0
        next_probe = time.time()
        web_q = ["What is the latest stable Linux kernel version today, and when was it released?",
                 "What are the top technology news stories today? Three bullet points with sources.",
                 "What is the current weather forecast for Chicago for the next two days?",
                 "What is the newest version of the Firefox browser and what changed in it?",
                 "Look up the current exchange rate from US dollars to euros and cite where it comes from.",
                 "What happened in the most recent SpaceX launch? Cite a source.",
                 "What is the latest release of Python 3 and when did it come out?",
                 "Find the current population estimate of Iceland and cite the source."]
        follow = ["What is the main purpose of the third file in that collection?", "Summarize the license terms mentioned, briefly.",
                  "Which file looks the most complex, and why?", "List two functions defined near the end.",
                  "Is there anything unusual in the material? One paragraph.", "Give me a one-sentence summary again."]

        def new_chat(kind):
            nonlocal n
            n += 1
            name = f"{kind}{n}"
            chats[name] = {"msgs": []}
            return name

        cur = None
        while time.time() < t_end:
            if time.time() >= next_probe:
                probe = [{"role": "user", "text": probe_doc["messages"][-1]["content"]}]
                pg.send(probe, "soak_probe", "probe 32k", extra={"max_tokens": 512})
                next_probe = time.time() + 600
                continue
            big = [c for c in chats if c.startswith("d")]
            web = [c for c in chats if c.startswith("w")]
            act = rng.choices(["back", "newdoc", "followup", "stop", "regen", "reason", "short", "web", "webback"],
                              weights=[30, 14, 10, 10, 7, 7, 8, 9, 5])[0]
            if act == "back" and len(big) > 1:
                cur = rng.choice([c for c in big if c != cur])
                user(chats[cur]["msgs"], rng.choice(follow))
                pg.send(chats[cur]["msgs"], "soak_back", cur, stop_on_content=3)
            elif act == "newdoc" or not big:
                d = rng.choice(docs)
                cur = new_chat("d")
                user(chats[cur]["msgs"], d["messages"][-1]["content"])
                pg.send(chats[cur]["msgs"], "soak_doc", f"{cur} {d['size']}", stop_after=4)
            elif act == "followup" and cur in chats:
                user(chats[cur]["msgs"], rng.choice(follow))
                pg.send(chats[cur]["msgs"], "soak_follow", cur, stop_on_content=4)
            elif act == "stop" and cur in chats:
                user(chats[cur]["msgs"], rng.choice(["Write a detailed plan for this.", "Go through it step by step."]))
                pg.send(chats[cur]["msgs"], "soak_stop", cur, stop_after=rng.uniform(1.0, 8.0))
            elif act == "regen" and cur in chats and chats[cur]["msgs"] and chats[cur]["msgs"][-1]["role"] == "assistant":
                chats[cur]["msgs"].pop()
                pg.send(chats[cur]["msgs"], "soak_regen", cur, stop_on_content=3)
            elif act == "reason":
                c = new_chat("r")
                p = rng.choice(lr)
                user(chats[c]["msgs"], p["messages"][-1]["content"])
                pg.send(chats[c]["msgs"], "soak_reason", f"{c} {p['id']}", stop_after=rng.choice([45, 90, 180]))
            elif act == "web":
                c = new_chat("w")
                user(chats[c]["msgs"], rng.choice(web_q))
                stop = rng.random() < 0.25                        # sometimes Stop while it searches / reads
                pg.send(chats[c]["msgs"], "soak_web", c, stop_after=rng.uniform(5, 40) if stop else None,
                        extra={"strata_web": True})
            elif act == "webback" and web:
                c = rng.choice(web)
                user(chats[c]["msgs"], rng.choice(["Can you check one more source for that?",
                                                   "Summarize what you found in two sentences, with the links.",
                                                   "Is any of that older than a month? Say which."]))
                pg.send(chats[c]["msgs"], "soak_webback", c, extra={"strata_web": True})
            elif act == "short":
                c = new_chat("s")
                user(chats[c]["msgs"], rng.choice(short_q))
                pg.send(chats[c]["msgs"], "soak_short", c, stop_on_content=4)
            # forget the oldest small chats; keep up to 12 big ones (the page would keep them all)
            for kind, keep in (("r", 2), ("s", 3), ("d", 12), ("w", 4)):
                ks = [c for c in chats if c.startswith(kind)]
                for c in ks[:-keep] if len(ks) > keep else []:
                    chats.pop(c)
            if cur not in chats:
                cur = None
    else:
        rng = random.Random(a.seed)
        t_end = time.time() + a.minutes * 60
        chats = {}                                                 # name -> {"msgs": [...], "k": next multiturn turn}
        n = 0

        def new_chat():
            nonlocal n
            n += 1
            name = f"c{n}"
            chats[name] = {"msgs": [], "k": 0, "tag": f"sk-{n}-{int(time.time()) % 10000}"}
            return name

        cur = new_chat()
        while time.time() < t_end:
            act = rng.choices(["turn", "turn_other", "doc", "reason", "stop", "regen", "new"],
                              weights=[30, 20, 6, 5, 12, 8, 6])[0]
            if act == "turn_other" and len(chats) > 1:
                cur = rng.choice([c for c in chats if c != cur])
                act = "turn"
            ch = chats[cur]
            if act == "new" or (act == "doc"):
                cur = new_chat(); ch = chats[cur]
                if act == "doc":
                    d = rng.choice([doc64, doc32])
                    user(ch["msgs"], d["messages"][-1]["content"])
                    pg.send(ch["msgs"], "chat_doc", f"{cur} {d['size']}", stop_after=5)
                else:
                    user(ch["msgs"], rng.choice(short_q))
                    pg.send(ch["msgs"], "chat_new", cur, stop_on_content=4)
            elif act == "turn":
                if ch["k"] < len(mt["turns"]) and rng.random() < 0.7:
                    mt_turn(ch["msgs"], ch["k"], ch["tag"])
                    pg.send(ch["msgs"], "chat_turn", f"{cur} mt{ch['k'] + 1}", stop_after=5)
                    fix_last(ch["msgs"], ch["k"]); ch["k"] += 1
                else:
                    user(ch["msgs"], rng.choice(["Explain that more simply.", "Give me a short example.",
                                                 "What could go wrong here?", "Summarize in two sentences."]))
                    pg.send(ch["msgs"], "chat_turn", f"{cur} short", stop_on_content=4)
            elif act == "reason":
                cur = new_chat(); ch = chats[cur]
                p = rng.choice(lr)
                user(ch["msgs"], p["messages"][-1]["content"])
                pg.send(ch["msgs"], "chat_reason", f"{cur} {p['id']}", stop_after=rng.choice([60, 120, 240]))
            elif act == "stop":
                user(ch["msgs"], rng.choice(["Write a detailed plan for this.", "Go through it step by step."]))
                pg.send(ch["msgs"], "chat_stop", cur, stop_after=rng.uniform(1.0, 8.0))
            elif act == "regen" and ch["msgs"] and ch["msgs"][-1]["role"] == "assistant":
                ch["msgs"].pop()                                   # the page's regenerate: same history again
                pg.send(ch["msgs"], "chat_regen", cur, stop_on_content=3)
            if len(chats) > 6:                                     # the user deletes an old chat now and then
                chats.pop(next(iter(chats)))
                if cur not in chats:
                    cur = next(iter(chats))
    h = requests.get(pg.base + "/health", timeout=10).text[:200]
    print(f"CHATSOAK DONE {a.label} {a.mode}: request errors {pg.errors}, health {h}")


if __name__ == "__main__":
    main()
