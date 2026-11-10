#!/usr/bin/env python3
"""conc.py - 2026-10-14 D: N simultaneous requests against a Strata server, for N in --levels, --reps repetitions.

  run    --endpoint URL --arm NAME --kind decode|agent [--levels 1,2,4,8] [--reps 2] [--greedy] [--max-tokens 4096]
         For each repetition (rep 1 in the given level order, rep 2 in reverse) and level N: the first N prompts of
         the set (results/r20/conc/prompts.json), all sent at the same instant (a barrier), streamed.  Each request:
         the user's sampling (T 1.0, top_p 0.95, top_k 20, min_p 0.05; --greedy: temperature 0), reasoning_effort
         xhigh as the suite sends it, seed = 4242 + prompt index, a nonce line [session <kind> L<N>-R<rep>] so no
         request reuses another's cached prompt (with --same-nonce: one nonce for every level, for the output
         comparison).  Recorded per request: time to the first streamed token (reasoning or content), end, the
         server's usage (prompt / completion tokens), finish reason, the generated text.  Per level: total tok/s
         (all completion tokens / the set's wall time), per-request tok/s (completion tokens / (end - first token)),
         TTFT median and worst, the set's wall time, and the lowest MemAvailable sampled every 0.25 s.
         -> results/r20/conc/<arm>-<kind>.jsonl (one line per request) and <arm>-<kind>-levels.json
  table  ARM[,ARM...] --kind K: the per-level table (median of the repetitions).
  match  ARM_SOLO ARM_BATCH --kind K: each request's text against the same prompt's level-1 text: equal, or the
         first character / token where they part."""
import argparse
import json
import re
import statistics as st
import sys
import threading
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = WS / "results/r20/conc"
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}


def meminfo_avail():
    with open("/proc/meminfo") as f:
        for ln in f:
            if ln.startswith("MemAvailable:"):
                return int(ln.split()[1]) / 1024 / 1024
    return None


class MemWatch(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.low = None
        self.stop_ev = threading.Event()

    def run(self):
        while not self.stop_ev.is_set():
            v = meminfo_avail()
            self.low = v if self.low is None else min(self.low, v)
            time.sleep(0.25)


def one(endpoint, body, rec, barrier):
    req = urllib.request.Request(endpoint.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
    barrier.wait()
    t0 = time.time()
    rec["t_send"] = t0
    first = None
    parts, reas, calls = [], [], []
    usage, finish = None, None
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            for raw in r:
                ln = raw.decode("utf-8", "replace").strip()
                if not ln.startswith("data:"):
                    continue
                d = ln[5:].strip()
                if d == "[DONE]":
                    break
                try:
                    j = json.loads(d)
                except ValueError:
                    continue
                if j.get("usage"):
                    usage = j["usage"]
                for ch in j.get("choices") or []:
                    delta = ch.get("delta") or {}
                    got = False
                    for k, sink in (("reasoning_content", reas), ("reasoning", reas), ("content", parts)):
                        v = delta.get(k)
                        if v:
                            sink.append(v)
                            got = True
                    if delta.get("tool_calls"):
                        calls.append(json.dumps(delta["tool_calls"]))
                        got = True
                    if got and first is None:
                        first = time.time()
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
    t1 = time.time()
    rec.update({"t_first": first, "t_end": t1, "ttft_s": (first - t0) if first else None, "wall_s": t1 - t0,
                "usage": usage, "finish": finish, "reasoning": "".join(reas), "content": "".join(parts),
                "tool_calls": "".join(calls)})
    ct = (usage or {}).get("completion_tokens")
    rec["decode_tps"] = ct / (t1 - first) if ct and first and t1 > first else None


def build(kind, prompts, i, nonce, greedy, max_tokens):
    if kind == "decode":
        p = prompts["decode"][i]
        msgs = [dict(m) for m in p["messages"]]
        msgs[-1]["content"] = nonce + "\n" + msgs[-1]["content"]
        body = {"messages": msgs}
    else:
        sys.path.insert(0, str(WS / "work/r20"))
        import conc_prompts as CP
        a = prompts["agent"][i]
        task = next(t for t in CP.TASKS if t[0] == a["id"])
        body = {"messages": CP.agent_messages(task, nonce, a["budget_chars"]),
                "tools": [{"type": "function", "function": t} for t in prompts["tools"]]}
    body.update({"model": "x", "stream": True, "stream_options": {"include_usage": True}, "max_tokens": max_tokens,
                 "reasoning_effort": "xhigh", "seed": 4242 + i, **SAMPLING})
    if greedy:
        body["temperature"] = 0.0
    return body


def run(a):
    prompts = json.loads((OUT / "prompts.json").read_text())
    levels = [int(x) for x in a.levels.split(",")]
    OUT.mkdir(parents=True, exist_ok=True)
    jl = OUT / f"{a.arm}-{a.kind}.jsonl"
    summ = []
    for rep in range(1, a.reps + 1):
        order = levels if rep % 2 == 1 else list(reversed(levels))
        for n in order:
            nonce = f"[session {a.kind} same]" if a.same_nonce else f"[session {a.kind} L{n}-R{rep}]"
            if n == 1 and a.solo_n > 1:             # the output check: each of the first solo_n prompts alone, in turn
                for i in range(a.solo_n):
                    rec = {"arm": a.arm, "kind": a.kind, "level": 1, "rep": rep, "idx": i, "solo_seq": True,
                           "id": (prompts["decode"][i]["id"] if a.kind == "decode" else prompts["agent"][i]["id"])}
                    one(a.endpoint, build(a.kind, prompts, i, nonce, a.greedy, a.max_tokens), rec, threading.Barrier(1))
                    with jl.open("a") as f:
                        f.write(json.dumps(rec) + "\n")
                    print(json.dumps({k: rec.get(k) for k in ("level", "idx", "id", "ttft_s", "decode_tps", "finish")}), flush=True)
                continue
            bodies = [build(a.kind, prompts, i, nonce, a.greedy, a.max_tokens) for i in range(n)]
            recs = [{"arm": a.arm, "kind": a.kind, "level": n, "rep": rep, "idx": i,
                     "id": (prompts["decode"][i]["id"] if a.kind == "decode" else prompts["agent"][i]["id"])}
                    for i in range(n)]
            barrier = threading.Barrier(n)
            mw = MemWatch()
            mw.start()
            ths = [threading.Thread(target=one, args=(a.endpoint, bodies[i], recs[i], barrier)) for i in range(n)]
            t0 = time.time()
            for t in ths:
                t.start()
            for t in ths:
                t.join()
            mw.stop_ev.set()
            mw.join()
            wall = max(r["t_end"] for r in recs) - min(r["t_send"] for r in recs)
            toks = sum(((r.get("usage") or {}).get("completion_tokens") or 0) for r in recs)
            ttfts = [r["ttft_s"] for r in recs if r.get("ttft_s") is not None]
            tps = [r["decode_tps"] for r in recs if r.get("decode_tps")]
            s = {"arm": a.arm, "kind": a.kind, "level": n, "rep": rep, "wall_s": round(wall, 2),
                 "completion_tokens": toks, "total_tps": round(toks / wall, 2) if wall > 0 else None,
                 "per_request_tps_median": round(st.median(tps), 2) if tps else None,
                 "per_request_tps_min": round(min(tps), 2) if tps else None,
                 "ttft_median_s": round(st.median(ttfts), 2) if ttfts else None,
                 "ttft_worst_s": round(max(ttfts), 2) if ttfts else None,
                 "prompt_tokens": [((r.get("usage") or {}).get("prompt_tokens")) for r in recs],
                 "finish": [r.get("finish") for r in recs], "errors": [r.get("error") for r in recs if r.get("error")],
                 "mem_available_min_gib": round(mw.low, 2) if mw.low is not None else None, "t_start": t0}
            summ.append(s)
            with jl.open("a") as f:
                for r in recs:
                    f.write(json.dumps(r) + "\n")
            print(json.dumps({k: s[k] for k in ("arm", "kind", "level", "rep", "wall_s", "total_tps",
                                                 "per_request_tps_median", "ttft_median_s", "ttft_worst_s",
                                                 "mem_available_min_gib", "finish", "errors")}), flush=True)
    lv = OUT / f"{a.arm}-{a.kind}-levels.json"
    old = json.loads(lv.read_text()) if lv.exists() else []
    if not summ:
        return
    lv.write_text(json.dumps(old + summ, indent=1))


def table(a):
    for arm in a.arms.split(","):
        lv = json.loads((OUT / f"{arm}-{a.kind}-levels.json").read_text())
        print(f"\n{arm} ({a.kind}):")
        print("| N | total tok/s | per request tok/s | TTFT median / worst s (median of reps) | wall s (median of reps) | min MemAvailable GiB |")
        print("|---|---|---|---|---|---|")
        for n in sorted({x["level"] for x in lv}):
            xs = [x for x in lv if x["level"] == n]
            m = lambda k: st.median([x[k] for x in xs if x.get(k) is not None]) if any(x.get(k) is not None for x in xs) else None  # noqa: E731
            print(f"| {n} | {m('total_tps'):.1f} | {m('per_request_tps_median'):.1f} | {m('ttft_median_s'):.2f} / "
                  f"{m('ttft_worst_s'):.2f} | {m('wall_s'):.1f} | {min(x['mem_available_min_gib'] for x in xs):.1f} |")


def match(a):
    def load(arm):
        return [json.loads(ln) for ln in open(OUT / f"{arm}-{a.kind}.jsonl")]
    solo = {(r["idx"], r["rep"]): r for r in load(a.solo) if r["level"] == 1}
    solo_any = {r["idx"]: r for r in load(a.solo) if r["level"] == 1}
    out = []
    for r in load(a.batch):
        s = solo.get((r["idx"], r["rep"])) or solo_any.get(r["idx"])
        if not s:
            continue
        ids = re.compile(r'"id": "call_[0-9a-f]+"')   # the server's random tool-call ids are not model output
        x = r["reasoning"] + "\x00" + r["content"] + "\x00" + ids.sub('"id": ""', r["tool_calls"])
        y = s["reasoning"] + "\x00" + s["content"] + "\x00" + ids.sub('"id": ""', s["tool_calls"])
        k = next((i for i, (c1, c2) in enumerate(zip(x, y)) if c1 != c2), min(len(x), len(y)))
        same = x == y
        out.append({"level": r["level"], "rep": r["rep"], "id": r["id"], "equal": same, "first_diff_char": None if same else k,
                    "len": [len(x), len(y)]})
    for o in out:
        print(json.dumps(o))
    eq = sum(o["equal"] for o in out)
    print(f"equal {eq} of {len(out)}")


ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["run", "table", "match"])
ap.add_argument("--endpoint", default="http://127.0.0.1:8081")
ap.add_argument("--arm")
ap.add_argument("--arms")
ap.add_argument("--kind", choices=["decode", "agent"])
ap.add_argument("--levels", default="1,2,4,8")
ap.add_argument("--reps", type=int, default=2)
ap.add_argument("--greedy", action="store_true")
ap.add_argument("--same-nonce", action="store_true")
ap.add_argument("--max-tokens", type=int, default=4096)
ap.add_argument("--solo-n", type=int, default=1, help="level 1 runs each of the first N prompts alone, in turn")
ap.add_argument("--solo")
ap.add_argument("--batch")
a = ap.parse_args()
{"run": run, "table": table, "match": match}[a.cmd](a)
