#!/usr/bin/env python3
"""speed_sweep.py - Karl's upgrade-pricing sweep (11-03; work/sweep/): a copy of work/ds41/tune/speed3.py with
(1) the engine found by SWEEP_EXE (its executable's basename; default strata-dsv41; "strata" for the Qwen engine), and
(2) SWEEP_LOG (the engine log): per request, the log lines the request added are parsed - DeepSeek's "CPU lane N% of the
experts" and Strata's "decode expert cache hit rate: ... (H hits / L lookups); P more read" - into disk.jsonl
(tier_lines). Everything else as speed3.py:

speed3.py BASE OUTDIR [PASSES [NPROMPT]] - 10-24 DeepSeek-V4.1 tuning round (the user: "Measure every arm the same way: W1-W3
decode at T 1.0 with thinking on, at least 3 passes, 4K and 20K prompt reading, SSD GB read per token and per prompt").
work/ds41/speed.py's requests (basalt-ab abrun.py's request code and workloads; a fresh nonce line in every request, so
no prompt prefix is reused), in this order: warm-up; P4K x3 and P20K x3 (prompt reading, thinking off, 8 tokens:
prompts/speed.json's three 4k prompts, and its three 32k prompts cut to 78,000 characters); a decode warm-up (W1, 1,024
tokens, not measured); then PASSES passes of
W1, W2, W3 (thinking on, effort medium, T 1.0 / 0.95 / 20 / min-p 0.05; W1 think 3,072 tokens, W2 code 3,072, W3
research ~23.5K-token prompt 2,048). Per request the engine's disk reads and writes (/proc/<pid>/io read_bytes,
write_bytes), the drive's own bytes read (/sys/block/nvme0n1/stat: readahead included - the Engram readahead check)
and the wall-clock start/end -> OUTDIR/ds41.jsonl (abrun's records, rep = pass) and OUTDIR/disk.jsonl. NPROMPT (default 3)
= how many P4K and P20K prompts; the screening runs use PASSES 1, NPROMPT 1.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402

SC = "/home/USER/ai-speed-testing/strata-compare"


def engine_pid():
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if os.path.basename(os.readlink(f"/proc/{p}/exe")) == os.environ.get("SWEEP_EXE", "strata-dsv41"):
                    return int(p)
            except OSError:
                pass
    return None


def io(pid):
    r = {}
    try:
        for line in open(f"/proc/{pid}/io"):
            k, v = line.split(":")
            r[k] = int(v)
    except (OSError, ValueError):
        return None, None
    return r.get("read_bytes"), r.get("write_bytes")


# 11-03: the drive holding the model files, from the mount (NVMe names change between boots; nvme0 is not it since 10-31)
import subprocess as _sp
MODEL_DISK = _sp.run(["lsblk", "-no", "PKNAME", _sp.run(["df", "--output=source", "/home/USER/ai-speed-testing/strata-compare/models"],
                     capture_output=True, text=True).stdout.split()[-1]], capture_output=True, text=True).stdout.split()[0]


def dev_read():
    try:
        return int(open(f"/sys/block/{MODEL_DISK}/stat").read().split()[2]) * 512
    except (OSError, ValueError, IndexError):
        return None


LOG = os.environ.get("SWEEP_LOG")
LANE = re.compile(r"CPU lane ([0-9.]+)% of the experts")
HIT = re.compile(r"decode expert cache hit rate: [0-9.]+% \((\d+) hits / (\d+) lookups\); (\d+) more read")


def log_size():
    try:
        return os.path.getsize(LOG) if LOG else None
    except OSError:
        return None


def tier_lines(o0, o1):
    if LOG is None or o0 is None or o1 is None or o1 <= o0:
        return None
    with open(LOG, "rb") as f:
        f.seek(o0)
        t = f.read(o1 - o0).decode("utf-8", "replace")
    return {"cpu_lane_pct": [float(x) for x in LANE.findall(t)], "hits": [[int(v) for v in m] for m in HIT.findall(t)]}


def main():
    base, out = sys.argv[1], sys.argv[2]
    passes = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    nprompt = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    os.makedirs(out, exist_ok=True)
    wl = json.load(open(abrun.WL))
    sp = json.load(open(f"{SC}/prompts/speed.json"))
    p4 = [p for p in sp if p["size"] == "4k"]
    p32 = [p for p in sp if p["size"] == "32k"]
    cut = lambda m: [dict(m[0], content=m[0]["content"][:78000])] + m[1:]
    jobs = [(dict(wl["normal"][1], id="warmup", max_tokens=384), 0)]
    jobs += [({"id": "P4K", "messages": p4[i % len(p4)]["messages"], "max_tokens": 8, "thinking": False}, i) for i in range(nprompt)]
    jobs += [({"id": "P20K", "messages": cut(p32[i % len(p32)]["messages"]), "max_tokens": 8, "thinking": False}, i) for i in range(nprompt)]
    ws = [w for w in wl["normal"] if w["id"].startswith(("W1", "W2", "W3"))]
    # decode warm-up after the long prompts (not measured): last night the first W1 after P20K ran ~20 % slower than the
    # second (the VRAM expert cache re-adapting), which would show up as pass-to-pass noise
    jobs.append((dict(ws[0], id="warmup-decode", max_tokens=1024), 0))
    for r in range(passes):
        jobs += [(w, r) for w in ws]
    pid = engine_pid()
    print(f"engine pid {pid}; {len(jobs)} requests", flush=True)
    for w, rep in jobs:
        r0, w0 = io(pid); d0 = dev_read(); t0 = time.time(); o0 = log_size()
        rec = abrun.one(base, "ds41", w, abrun.NORMAL, {}, rep, f"{out}/ds41.jsonl")
        time.sleep(2)   # the request's engine lines follow its last streamed token
        r1, w1 = io(pid); d1 = dev_read(); t1 = time.time(); o1 = log_size()
        d = {"id": w["id"], "rep": rep,
             "disk_read_gb": round((r1 - r0) / 1e9, 3) if r0 is not None and r1 is not None else None,
             "disk_write_gb": round((w1 - w0) / 1e9, 4) if w0 is not None and w1 is not None else None,
             "device_read_gb": round((d1 - d0) / 1e9, 3) if d0 is not None and d1 is not None else None,
             "t_start": round(t0, 1), "t_end": round(t1, 1),
             "completion_tokens": rec.get("completion_tokens"), "prompt_tokens": rec.get("prompt_tokens"),
             "tier_lines": tier_lines(o0, o1)}
        if d["disk_read_gb"] is not None and rec.get("completion_tokens") and w.get("thinking", True):
            d["disk_gb_per_token"] = round(d["disk_read_gb"] / rec["completion_tokens"], 4)
        with open(f"{out}/disk.jsonl", "a") as f:
            f.write(json.dumps(d) + "\n")
        print(f"  disk {d['disk_read_gb']} GB read, {d['disk_write_gb']} GB written", flush=True)


if __name__ == "__main__":
    main()
