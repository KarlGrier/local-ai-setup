#!/usr/bin/env python3
"""profile_decode.py - round 22 (the user, 10-21: "Profile our P021 decode on the 5080: how much of the card's memory
bandwidth do our GPU-side decode kernels achieve, and what share of each decode step is GPU time vs CPU expert time?").
Profile only: no code changes. Run INSIDE a gap (8080 down, test lock held).

  profile_decode.py run CONFIG OUTDIR LABEL [--prompt FILE] [--max-new N] [--mode stats|nsys|gpufloor]
      the engine CLI with the config's exe, args and env (server-only flags dropped, as basalt-ab/scripts/strata_dump.py),
      the prompt's tokens, N new tokens sampled at T 1.0 / top-p 0.95 / top-k 20, seed 1234, --stats:
        stats     the engine's own per-round breakdown (verify window: wait for rings / pool / host ms per round, CPU
                  experts per layer, decode tok/s) - no profiler
        nsys      the same run under Nsight Systems (CUDA trace incl. graph nodes; no CPU sampling: perf is locked) ->
                  LABEL.nsys-rep + the kernel summary and the GPU trace as CSV
        gpufloor  --gpu-only-full: all 48 layers + the LM head per token, no CPU pool (the engine's GPU floor)
  profile_decode.py summary OUTDIR LABEL [--dense-bytes B] [--peak-gbs 960]
      from LABEL's logs: ms per round and its split (GPU-side wait vs the CPU pool), and from the nsys CSVs: GPU kernel
      time per round, the GPU's busy share of the decode wall time (union of kernel intervals), the top kernels, and the
      dense weights' achieved bandwidth (dense bytes per round / the dense kernels' time per round).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SC = Path("/home/USER/ai-speed-testing/strata-compare")
NSYS = "/opt/nvidia/nsight-systems/2026.1.3/bin/nsys"
SERVER_ONLY = {"--chat-cache": 1, "--chat-cache-mib": 1, "--side-stash": 1, "--vision": 0}


def engine_cmd(cfg, a, extra):
    args, i = [], 0
    while i < len(cfg["args"]):
        x = cfg["args"][i]
        if x in SERVER_ONLY:
            i += 1 + SERVER_ONLY[x]; continue
        args.append(x); i += 1
    return [cfg["exe"], *args, "--tokens-file", a.prompt, "--max-new", str(a.max_new), "--seed", "1234",
            "--temperature", "1.0", "--top-p", "0.95", "--top-k", "20", "--stats", *extra]


def run(a):
    cfg = json.load(open(a.config)); out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, **cfg.get("env", {}))
    env["LD_LIBRARY_PATH"] = ":".join(cfg.get("lib_dirs", [])) + ":" + env.get("LD_LIBRARY_PATH", "")
    extra = ["--gpu-only-full"] if a.mode == "gpufloor" else []
    cmd = engine_cmd(cfg, a, extra)
    if a.mode == "nsys":
        rep = out / f"{a.label}"
        cmd = [NSYS, "profile", "--trace=cuda", "--cuda-graph-trace=node", "--sample=none", "--cpuctxsw=none",
               "--force-overwrite=true", "-o", str(rep), *cmd]
    log = out / f"{a.label}.log"
    print(f"{a.label}: {a.mode}, {a.max_new} tokens, prompt {a.prompt}", flush=True)
    r = subprocess.run(cmd, cwd=cfg.get("cwd"), env=env, stdout=open(log, "w"), stderr=subprocess.STDOUT)
    print(f"{a.label}: rc {r.returncode}; log {log}", flush=True)
    if a.mode == "nsys" and r.returncode == 0:
        for rp in ("cuda_gpu_kern_sum", "cuda_gpu_trace"):
            subprocess.run([NSYS, "stats", "--force-export=true", "--report", rp, "--format", "csv", "--output",
                            str(out / f"{a.label}"), str(out / f"{a.label}.nsys-rep")], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    return r.returncode


def num(pat, text, cast=float, default=None):
    m = re.search(pat, text)
    return cast(m.group(1)) if m else default


def summary(a):
    out = Path(a.outdir); t = (out / f"{a.label}.log").read_text(errors="replace")
    rounds = num(r"speculation\s+(\d+) rounds", t, int)
    res = {"label": a.label, "rounds": rounds,
           "decode_tok_s": num(r"decode\s+\d+ tokens in [\d.]+ ms\s+->\s+([\d.]+) tok/s", t),
           "decode_ms": num(r"decode\s+\d+ tokens in ([\d.]+) ms", t),
           "tokens_per_round": num(r"([\d.]+) tokens per round", t),
           "wait_rings_ms": num(r"wait for rings ([\d.]+)", t), "pool_ms": num(r"pool ([\d.]+)\s+host", t),
           "host_ms": num(r"host ([\d.]+)\s+commit", t),
           "cpu_experts_distinct": num(r"CPU experts ([\d.]+) distinct", t)}
    if res["decode_ms"] and rounds:
        res["ms_per_round"] = round(res["decode_ms"] / rounds, 3)
    ks = out / f"{a.label}_cuda_gpu_kern_sum.csv"; tr = out / f"{a.label}_cuda_gpu_trace.csv"
    if ks.exists() and tr.exists():
        kern = list(csv.DictReader(open(ks)))
        tot_ns = sum(float(k["Total Time (ns)"]) for k in kern)
        res["gpu_kernel_ms_total"] = round(tot_ns / 1e6, 1)
        ivals = []
        for row in csv.DictReader(open(tr)):
            if row.get("Start (ns)") and row.get("Duration (ns)") and "[CUDA mem" not in (row.get("Name") or ""):
                s = float(row["Start (ns)"]); ivals.append((s, s + float(row["Duration (ns)"])))
        ivals.sort()
        # the decode phase: the last 85 % of kernel activity by time (the prompt read and load come first)
        if ivals:
            t0, t1 = ivals[0][0], ivals[-1][1]; cut = t0 + 0.15 * (t1 - t0)
            dec = [(max(s, cut), e) for s, e in ivals if e > cut]
            busy, cur_s, cur_e = 0.0, None, None
            for s, e in dec:
                if cur_e is None or s > cur_e:
                    if cur_e is not None:
                        busy += cur_e - cur_s
                    cur_s, cur_e = s, e
                else:
                    cur_e = max(cur_e, e)
            if cur_e is not None:
                busy += cur_e - cur_s
            res["gpu_busy_share_decode"] = round(busy / max(1.0, t1 - cut), 3)
        if rounds:
            res["gpu_kernel_ms_per_round"] = round(tot_ns / 1e6 / rounds, 3)
        res["top_kernels"] = [(k["Name"][:90], round(float(k["Total Time (ns)"]) / 1e6, 1), int(k["Instances"]))
                              for k in sorted(kern, key=lambda k: -float(k["Total Time (ns)"]))[:15]]
        if a.dense_bytes and rounds:
            dense = [k for k in kern if re.search(a.dense_regex, k["Name"])]
            d_ns = sum(float(k["Total Time (ns)"]) for k in dense)
            if d_ns:
                gbs = a.dense_bytes * rounds / (d_ns / 1e9) / 1e9
                res["dense_kernels"] = len(dense)
                res["dense_ms_per_round"] = round(d_ns / 1e6 / rounds, 3)
                res["dense_achieved_gbs"] = round(gbs, 1)
                res["dense_share_of_peak"] = round(gbs / a.peak_gbs, 3)
    print(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("config"); r.add_argument("outdir"); r.add_argument("label")
    r.add_argument("--prompt", default=str(SC / "bringup/out/r20a/prompts/math.tokens"))
    r.add_argument("--max-new", type=int, default=512)
    r.add_argument("--mode", choices=["stats", "nsys", "gpufloor"], default="stats")
    s = sub.add_parser("summary")
    s.add_argument("outdir"); s.add_argument("label")
    s.add_argument("--dense-bytes", type=float, default=0.0, help="dense weights read per round (bytes)")
    s.add_argument("--dense-regex", default=r"mmvq|mul_mat_vec|dense|gemv", help="kernel names that read the dense weights")
    s.add_argument("--peak-gbs", type=float, default=960.0)
    a = ap.parse_args()
    sys.exit(run(a) if a.cmd == "run" else summary(a))


if __name__ == "__main__":
    main()
