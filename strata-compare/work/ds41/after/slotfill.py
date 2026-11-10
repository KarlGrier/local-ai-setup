#!/usr/bin/env python3
"""slotfill.py BASE OUTDIR ENGINE_LOG SLOT_DIR [N_CHATS] - 10-26 (the user, item 1: "Daily DeepSeek launcher: slot keep on with
a cap of 16 ... Report how much RAM the 16 slots use at their largest, and confirm it still keeps 14 GB free with everything
up"). N_CHATS (17) separate chats, each one request of ~31,000 prompt tokens (a unique first line, then a slice of the long
speed texts; max_tokens 64, so the thinking budget ends the thinking at once), so each chat's state is about as large as --max-context 32768 allows: the 17th
request sets the 16th aside, leaving 16 conversations in RAM (STRATA_DS4_SLOT_CAP 16). Per chat: prompt tokens, TTFT, the
engine's RSS, MemAvailable, the slot folder, and the engine's "ds4 slots: saved a N-token conversation (X GB in RAM ...)"
lines. Then the usual speed requests on top (W1-W3, P4K, P20K; speed3.py, 1 pass) with the 16 slots held, so the lowest
MemAvailable covers both. -> OUTDIR/slotfill.jsonl, OUTDIR/slotfill.json"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import conv  # noqa: E402  (chat(), engine_pid(), rss_mb(), du())

SC = "/home/USER/ai-speed-testing/strata-compare"
TARGET = 31000


def memavail_gb():
    return round(int(next(l for l in open("/proc/meminfo") if l.startswith("MemAvailable")).split()[1]) / 1048576, 2)


def main():
    base, out, elog, sdir = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], sys.argv[4]
    n = int(sys.argv[5]) if len(sys.argv) > 5 else 17
    sp = json.load(open(f"{SC}/prompts/speed.json"))
    src = max((p["messages"][0]["content"] for p in sp if p["size"] in ("64k", "120k")), key=len)
    pid = conv.engine_pid()
    off = os.path.getsize(elog) if os.path.exists(elog) else 0
    chars = 100000   # (~3.25 characters a token on these texts; corrected after the first chat)
    recs = []
    for i in range(n):
        start = (i * 37000) % max(1, len(src) - chars)
        body = f"[chat {i + 1} of {n}, {uuid.uuid4().hex[:8]}] Summarise the text below in one sentence.\n\n" + src[start:start + chars]
        r = conv.chat(base, [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": body}], 64)
        time.sleep(2.0)
        new = open(elog, errors="replace").read()[off:] if os.path.exists(elog) else ""
        off = os.path.getsize(elog) if os.path.exists(elog) else off
        saved = re.findall(r"ds4 slots: saved a (\d+)-token conversation \(([\d.]+) GB in RAM[^)]*\); (\d+) in RAM", new)
        pt = r["usage"].get("prompt_tokens")
        rec = {"chat": i + 1, "prompt_tokens": pt, "completion_tokens": r["usage"].get("completion_tokens"), "ttft_s": r["ttft_s"],
               "engine_rss_mb": conv.rss_mb(pid), "memavail_gb": memavail_gb(), "slot_dir_mb": round(conv.du(sdir) / 1e6, 1),
               "saved": [{"tokens": int(a), "gb": float(b), "in_ram": int(c)} for a, b, c in saved],
               "slot_lines": [l[:220] for l in new.splitlines() if l.startswith("ds4 slots")][-4:]}
        recs.append(rec)
        with open(f"{out}/slotfill.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"chat {i + 1}: prompt {pt} tokens, TTFT {r['ttft_s']} s, engine RSS {rec['engine_rss_mb']} MB, MemAvailable "
              f"{rec['memavail_gb']} GB, slot folder {rec['slot_dir_mb']} MB; " +
              "; ".join(f"saved {s['tokens']} tokens = {s['gb']} GB in RAM ({s['in_ram']} in RAM)" for s in rec["saved"]), flush=True)
        if i == 0 and pt:
            chars = int(chars * TARGET / pt)
    sv = [s for r in recs for s in r["saved"]]
    big = max(sv, key=lambda s: s["tokens"]) if sv else None
    res = {"chats": n, "saved": len(sv), "in_ram_last": sv[-1]["in_ram"] if sv else 0,
           "slot_gb_sum": round(sum(s["gb"] for s in sv[-16:]), 2),
           "largest_slot": big, "gb_per_1k_tokens": round(big["gb"] / big["tokens"] * 1000, 4) if big else None,
           "at_32768_x16_gb": round(big["gb"] / big["tokens"] * 32768 * 16, 2) if big else None,
           "rss_growth_mb": recs[-1]["engine_rss_mb"] - recs[0]["engine_rss_mb"] if recs[0]["engine_rss_mb"] else None,
           "memavail_after_fill_gb": recs[-1]["memavail_gb"]}
    json.dump(res, open(f"{out}/slotfill.json", "w"), indent=1)
    print(f"slots: {res['in_ram_last']} in RAM after {n} chats, the last 16 saved = {res['slot_gb_sum']} GB "
          f"(largest {big['tokens'] if big else '-'} tokens = {big['gb'] if big else '-'} GB; 16 x 32,768 tokens = "
          f"{res['at_32768_x16_gb']} GB); engine RSS +{res['rss_growth_mb']} MB from chat 1 to chat {n}; MemAvailable "
          f"after the fill {res['memavail_after_fill_gb']} GB", flush=True)
    rc = subprocess.run([f"{SC}/.venv/bin/python", f"{SC}/work/ds41/tune/speed3.py", base, out, "1", "1"]).returncode
    print(f"speed requests on top of the 16 slots: rc {rc}", flush=True)


if __name__ == "__main__":
    main()
