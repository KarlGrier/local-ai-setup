#!/usr/bin/env python3
"""speed.py BASE OUTDIR [REPS] - 10-23 (the user, DS4.1 step 4): the speed requests against a running DeepSeek-V4.1 server.
abrun.py's own request code and workloads (basalt-ab/scripts, the W1-W3 decode screen: W1 think 3,072 tokens, W2 code
3,072, W3 research ~19K-token prompt 2,048; thinking on, effort medium; T 1.0 / 0.95 / 20 / min-p 0.05; a fresh nonce
line in every request, so no prompt prefix is reused), plus prompt reading at 4K and 20K tokens (prompts/speed.json's
4k prompts, and its 32k prompts cut to 78,000 characters; thinking off, 8 tokens). Order: warm-up, P4K x REPS, P20K x
REPS, then W1, W2, W3 x REPS. Per request also the engine's disk reads (/proc/<pid>/io read_bytes: the RAM store's
direct reads and the Engram rows) -> OUTDIR/ds41.jsonl (abrun's records) and OUTDIR/disk.jsonl.
"""
import json
import os
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402

SC = "/home/USER/ai-speed-testing/strata-compare"
ENG = f"{SC}/engine-v024-ds41/strata-dsv41"


def engine_pid():
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if os.readlink(f"/proc/{p}/exe") == ENG:
                    return int(p)
            except OSError:
                pass
    return None


def read_bytes(pid):
    try:
        for line in open(f"/proc/{pid}/io"):
            if line.startswith("read_bytes:"):
                return int(line.split()[1])
    except OSError:
        return None


def main():
    base, out = sys.argv[1], sys.argv[2]
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    os.makedirs(out, exist_ok=True)
    wl = json.load(open(abrun.WL))
    sp = json.load(open(f"{SC}/prompts/speed.json"))
    p4 = [p for p in sp if p["size"] == "4k"][:reps]
    p32 = [p for p in sp if p["size"] == "32k"][:reps]
    cut = lambda m: [dict(m[0], content=m[0]["content"][:78000])] + m[1:]
    jobs = [(dict(wl["normal"][1], id="warmup", max_tokens=384), 0)]   # abrun.py's warm-up (built at run time, not in the file)
    jobs += [({"id": "P4K", "messages": p["messages"], "max_tokens": 8, "thinking": False}, i) for i, p in enumerate(p4)]
    jobs += [({"id": "P20K", "messages": cut(p["messages"]), "max_tokens": 8, "thinking": False}, i) for i, p in enumerate(p32)]
    for w in wl["normal"]:
        if w["id"].startswith(("W1", "W2", "W3")):
            jobs += [(w, r) for r in range(reps)]
    pid = engine_pid()
    print(f"engine pid {pid}; {len(jobs)} requests", flush=True)
    for w, rep in jobs:
        b0 = read_bytes(pid)
        rec = abrun.one(base, "ds41", w, abrun.NORMAL, {}, rep, f"{out}/ds41.jsonl")
        b1 = read_bytes(pid)
        d = {"id": w["id"], "rep": rep, "disk_read_gb": round((b1 - b0) / 1e9, 3) if b0 is not None and b1 is not None else None,
             "completion_tokens": rec.get("completion_tokens"), "prompt_tokens": rec.get("prompt_tokens")}
        if d["disk_read_gb"] is not None and rec.get("completion_tokens") and w.get("thinking", True):   # decode requests
            d["disk_gb_per_token"] = round(d["disk_read_gb"] / rec["completion_tokens"], 4)
        with open(f"{out}/disk.jsonl", "a") as f:
            f.write(json.dumps(d) + "\n")
        print(f"  disk {d['disk_read_gb']} GB", flush=True)


if __name__ == "__main__":
    main()
