#!/usr/bin/env python3
"""longprompt.py BASE OUTDIR ENGINE_LOG SLOT_DIR - 10-26 (Karl: "Run one real long prompt on the daily config at 128K: ~100K
tokens of text plus a short question. Report read time, decode speed at that length, peak memory (it must keep >= 14 GB
free with everything up), and the size of the conversation slot it leaves, in RAM and on disk.")
Four requests on the daily settings (the server's default effort; sampling from the config):
  L1  ~100K tokens of the long speed text (prompts/speed.json, the 120k text, a unique first line) + a short question,
      max_tokens 4,096 (the thinking closes at 3,072): read time and decode speed at that length (the engine's own
      "prompt N tokens = R reused + X read in T ms, G generated in T ms" lines), TTFT, MemAvailable sampled every 0.5 s
  S1  a short unrelated chat: the long conversation is set aside -> "saved a N-token conversation (X GB in RAM ...)"
  L2  L1 continued (its answer + one more question): taken back from RAM, only the new tokens read
  S2  another short chat: the continued conversation is set aside (the largest slot of the run)
The slot on disk: the engine writes its RAM slots to SLOT_DIR when it stops (after this client) - the driver reads the
folder then. -> OUTDIR/longprompt.json, OUTDIR/longprompt.jsonl"""
import json
import os
import re
import sys
import threading
import time
import urllib.request
import uuid

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import conv  # noqa: E402  (engine_pid(), rss_mb(), du())

SC = "/home/USER/ai-speed-testing/strata-compare"
CHARS_PER_TOKEN = 3.51   # (the daily fill, 10-26: 100,000 characters of this text = 28,467 tokens)
TARGET = 100000
SEED = 4242


def memavail_gb():
    return round(int(next(l for l in open("/proc/meminfo") if l.startswith("MemAvailable")).split()[1]) / 1048576, 2)


class Low:
    """the lowest MemAvailable while a request runs (sampled every 0.5 s)"""
    def __init__(self):
        self.low, self.run = 999.0, True
        self.t = threading.Thread(target=self.loop, daemon=True)
        self.t.start()

    def loop(self):
        while self.run:
            self.low = min(self.low, memavail_gb())
            time.sleep(0.5)

    def stop(self):
        self.run = False
        self.t.join()
        return round(self.low, 2)


def chat(base, messages, max_tokens):
    """stream one request; times of the first token, the first answer token and the end; the reply text"""
    body = {"model": "x", "messages": messages, "max_tokens": max_tokens, "stream": True, "seed": SEED,
            "stream_options": {"include_usage": True}}
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    t1 = ta = None
    content, reasoning, usage, finish = [], [], None, None
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
                rt = d.get("reasoning_content") or d.get("reasoning") or ""
                if (d.get("content") or rt) and t1 is None:
                    t1 = time.monotonic()
                if d.get("content") and ta is None:
                    ta = time.monotonic()
                content.append(d.get("content") or "")
                reasoning.append(rt)
                finish = ch.get("finish_reason") or finish
    t2 = time.monotonic()
    return {"ttft_s": round(t1 - t0, 2) if t1 else None, "t_first_answer_s": round(ta - t0, 2) if ta else None,
            "total_s": round(t2 - t0, 2), "answer": "".join(content), "reasoning_chars": len("".join(reasoning)),
            "usage": usage or {}, "finish": finish}


def main():
    base, out, elog, sdir = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], sys.argv[4]
    sp = json.load(open(f"{SC}/prompts/speed.json"))
    src = max((p["messages"][0]["content"] for p in sp if p["size"] == "120k"), key=len)
    text = src[:int(TARGET * CHARS_PER_TOKEN)]
    tag = uuid.uuid4().hex[:8]
    sysm = {"role": "system", "content": "You are a helpful assistant."}
    long_user = {"role": "user", "content": f"[long-context check {tag}] Read the text below, then answer the question after it.\n\n"
                 f"<text>\n{text}\n</text>\n\nQuestion: in two or three sentences, what is this text about, and what does its "
                 "last part cover?"}
    pid = conv.engine_pid()
    off = os.path.getsize(elog) if os.path.exists(elog) else 0
    recs = []

    def turn(name, msgs, max_tokens):
        nonlocal off
        m0, r0 = memavail_gb(), conv.rss_mb(pid)
        lw = Low()
        r = chat(base, msgs, max_tokens)
        time.sleep(2.0)   # (the engine writes its profile and any slot after the reply)
        low = lw.stop()
        new = open(elog, errors="replace").read()[off:] if os.path.exists(elog) else ""
        off = os.path.getsize(elog) if os.path.exists(elog) else off
        passes = [{"prompt": int(a), "reused": int(b), "read": int(c), "read_ms": float(d), "read_tps": float(e),
                   "generated": int(f), "gen_ms": float(g), "gen_tps": float(h)}
                  for a, b, c, d, e, f, g, h in re.findall(
                      r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms \(([\d.]+) tok/s\), (\d+) generated in "
                      r"([\d.]+) ms \(([\d.]+) tok/s\)", new)]
        rec = {"turn": name, "prompt_tokens": r["usage"].get("prompt_tokens"), "completion_tokens": r["usage"].get("completion_tokens"),
               "ttft_s": r["ttft_s"], "t_first_answer_s": r["t_first_answer_s"], "total_s": r["total_s"], "finish": r["finish"],
               "passes": passes, "memavail_before_gb": m0, "memavail_low_gb": low, "memavail_after_gb": memavail_gb(),
               "engine_rss_before_mb": r0, "engine_rss_after_mb": conv.rss_mb(pid),
               "slot_dir_mb": round(conv.du(sdir) / 1e6, 1),
               "saved": [{"tokens": int(a), "gb": float(b), "s": float(c), "in_ram": int(d)} for a, b, c, d in re.findall(
                   r"ds4 slots: saved a (\d+)-token conversation[^(]*\(([\d.]+) GB in RAM in ([\d.]+) s\); (\d+) in RAM", new)],
               "taken": re.findall(r"ds4 slots: (took back a \d+-token conversation[^\n]*)", new),
               "slot_lines": [l[:240] for l in new.splitlines() if l.startswith("ds4 slots")][-6:],
               "engine_lines": [l[:240] for l in new.splitlines() if re.search(r"context|KV|prompt skip|memory|RAM", l)][-6:],
               "answer": r["answer"][:600]}
        recs.append(rec)
        with open(f"{out}/longprompt.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        p0 = passes[0] if passes else {}
        print(f"{name}: prompt {rec['prompt_tokens']} tokens ({p0.get('reused')} reused + {p0.get('read')} read in "
              f"{(p0.get('read_ms') or 0) / 1000:.1f} s = {p0.get('read_tps')} tok/s), {rec['completion_tokens']} generated "
              f"(passes: " + "; ".join(f"{p['generated']} at {p['gen_tps']} tok/s" for p in passes) + f"), TTFT {rec['ttft_s']} s, "
              f"total {rec['total_s']} s, finish {rec['finish']}; MemAvailable {m0} -> low {low} -> {rec['memavail_after_gb']} GB; "
              f"engine RSS {r0} -> {rec['engine_rss_after_mb']} MB; slot folder {rec['slot_dir_mb']} MB; "
              + "; ".join(f"saved {s['tokens']} tokens = {s['gb']} GB in RAM in {s['s']} s ({s['in_ram']} in RAM)" for s in rec["saved"])
              + ("; " + "; ".join(rec["taken"]) if rec["taken"] else ""), flush=True)
        return r

    r1 = turn("L1", [sysm, long_user], 4096)
    turn("S1", [sysm, {"role": "user", "content": f"[short {tag}] In one sentence: why is the sky blue?"}], 256)
    turn("L2", [sysm, long_user, {"role": "assistant", "content": r1["answer"]},
                {"role": "user", "content": "Thanks. Name one person, place or thing the text mentions near its beginning."}], 1024)
    turn("S2", [sysm, {"role": "user", "content": f"[short {tag}-2] In one sentence: why do leaves change colour in autumn?"}], 256)
    L1, L2 = recs[0], recs[2]
    sv = [s for r in recs for s in r["saved"]]
    big = max(sv, key=lambda s: s["tokens"]) if sv else None
    p1 = L1["passes"][0] if L1["passes"] else {}
    res = {"prompt_tokens": L1["prompt_tokens"], "read_s": round((p1.get("read_ms") or 0) / 1000, 1), "read_tps": p1.get("read_tps"),
           "decode_tps": [p["gen_tps"] for p in L1["passes"]], "generated": [p["generated"] for p in L1["passes"]],
           "ttft_s": L1["ttft_s"], "t_first_answer_s": L1["t_first_answer_s"], "total_s": L1["total_s"],
           "followup": {"prompt_tokens": L2["prompt_tokens"], "reused": (L2["passes"][0] if L2["passes"] else {}).get("reused"),
                        "read": (L2["passes"][0] if L2["passes"] else {}).get("read"), "ttft_s": L2["ttft_s"], "taken": L2["taken"]},
           "largest_slot": big, "memavail_low_gb": min(r["memavail_low_gb"] for r in recs),
           "engine_rss_mb": [r["engine_rss_after_mb"] for r in recs], "slot_dir_mb_in_run": recs[-1]["slot_dir_mb"]}
    json.dump(res, open(f"{out}/longprompt.json", "w"), indent=1)
    print("longprompt: " + json.dumps(res), flush=True)


if __name__ == "__main__":
    main()
