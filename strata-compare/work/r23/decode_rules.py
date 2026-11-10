#!/usr/bin/env python3
# AMENDMENT 2026-11-07 (Karl) - it applies from now on, not to finished gates; recorded before the confirmation gap
# (work/r23/gap-confirm0211.sh). Karl, 11-07, on results/r23/port-0211/HUNT-1107.md:
#   "Measurement rule: yes, as a dated amendment applying from now on. Per-workload prompt numbers exclude the
#   chat-cache save. Time the save as its own line in every screen, and judge it separately against its own noise,
#   taking its two-speed pattern into account, so a real regression in saving still shows."
#   "Prompt clock: engine clock for the per-workload prompt numbers, as you recommend. The overall screen rule stays on
#   the client clock minus the save, at -1%. Add one INFO flag, not a fail: if a workload's outside-engine time is worse
#   in all 3 passes by more than its own spread, flag it for review, so a server-side slowdown hitting one workload
#   can't hide under the overall rule. Record the amendment as dated before the confirmation gap."
# The rule as implemented (work/r22/g17_rules.py, section "11-07 park amendment"):
#   - Per-workload prompt numbers exclude the chat-cache save and are taken on the engine clock: prompt tokens / (the
#     engine's prompt ms - the `chat cache: parked ... in N ms` line logged just before that request). They feed Karl
#     11-03's no-loss rule (wl_noloss) and g16's "no workload more than 3 % below".
#   - The overall screen rule (g16's geometric mean, -1 %) stays on the client clock minus the save: prompt tokens /
#     (TTFT - save).
#   - The save is judged as its own "chat-cache save" line (save_rule), against its own noise and with its two levels
#     taken into account. The level mix is INFO.
#   - The outside-engine INFO flag (outside_flags). It is INFO and never changes a verdict.
#     - A workload's outside-engine time per request = client TTFT - the engine's prompt ms. The save is inside the
#       engine figure, so it cancels.
#     - Its spread = the larger of the two arms' half-ranges over their passes.
#     - Flag: every pass of the arm is above the base's mean by more than that spread -> "outside-engine time worse in
#       every pass - for review (INFO)".
# A gate that started before 2026-11-07 14:00 keeps the rules it ran under; so does screen data without engine logs.
# This file's own screen code is the pre-amendment client clock of its finished gate(s) and is kept as it ran. A new
# gate takes the amended numbers, the save line and the INFO flag from work/r22/g17_rules.py, not from a copy of this
# file's code.
"""decode_rules.py - round 23, the exact decode items (results/r23/decode-timing/GATE-PLAN.md): the rules of gaps
decode-a and decode-b (work/r23/gap-decode-a.sh, gap-decode-b.sh), written BEFORE either ran (11-04). Measurement only:
nothing is served or switched (Karl: P028x stays served until item 7 is done).

The items, each behind its own switch on branch r23-decode-exact (= r22-port0210 fdd2fffa8 + 2 commits, both off by
default), built into engine-r23decode/ in gap a:
  L  STRATA_REMOTE_LATE_LAUNCH=1  the helper GPU's staging and launches after the CPU pool's batch is published (2 cards)
  O  STRATA_POOL_ONE_BATCH=1      a layer's gate/up rows and down rows in one CPU-pool batch
Both are scheduling-only: the output must be bit-identical. Every arm is compared with the same build, both switches off
(B on two cards, Bs on the 5080 alone).

EXACT (GATE-PLAN section 6; decided in gap a, decide-a -> results/r23/decode-timing/gap-a/decision.{txt,json}):
  build   build_x (configure + build with tests ON, installed: engine-r23decode/strata + SOURCE (branch, HEAD, v0.2.10..HEAD
          = 30) + SHA256), build8 (configure: "windows hold up to 8 rows", the port's 8-row build), build_src (the tree
          built is the one reviewed: begin() is just claim() && launch(); LateLaunch with its static run; pool.hpp's
          aligned ObExpert / ExitStamp; generate.cpp's drive.d.pool / copy_before), build_warn (no warning in the 7
          files the 2 commits touch beyond what the port's own build logs have)
  tests   every step-2 test rc 0: pool_tasks_test (synthetic Q4_0, then one real blob of each of the pack's 7 type pairs),
          pool_test --selftest, numa_pool_test, pool_stress 20 (nothing set; STRATA_POOL_ONE_BATCH=1), patch_guard_test,
          the serve tests (gap 17's form: failures only in g17_rules.KNOWN_SERVE_FAILS)
  exact7  at pin 2500, 7/7 identical AND slots MATCHED: e7_B (r23-B vs g17-p210a: switches off = the port = P028x bit for
          bit), e7_B2 (r23-B again vs r23-B); item L: e7_L (vs r23-B), item O: e7_O (vs r23-B) and e7_Os (one card, vs
          r23-Bs); both: e7_LO (vs r23-B). e7_Bs (the solo base) must have run all 7 items (INFO otherwise: no solo
          reference exists at pin 2500). Every exact7 engine's environment checked (env_e7-*), and each run's start
          lines: the switch's line present in its arm (else UNEXERCISED -> NOT DECIDED), absent in B / B2 / Bs
  logits  pf_yardstick long40: pfy_B_LO (0 of 40 first-token logit files differ, B vs LO) and pfy_B_p210 (0 of 40, B vs
          gap 17's P0210x-h dir), both engines' environment checked (env_pfy-*)
  item L EXACT = build + tests + e7_B + e7_B2 + e7_L + e7_LO + both logit checks (and their env / line gates)
  item O EXACT = build + tests + e7_B + e7_B2 + e7_O + e7_Os (e7_Bs ran) + e7_LO + both logit checks
  A missing gate (not run: deadline, build failed, ...) = NOT DECIDED; a failed one = FAIL.
  The timing arms (Bt, LOt, Bst, Ost; t2_report.py) and the two-card timing pass (t2pass.sh dv) are INFO: the mechanism,
  not the gate.

PART B MAY RUN (check-a): part a's decision.json exists; build PASS; e7_B and e7_B2 PASS; at least one item EXACT (with
  R23B_SCREEN_ANYWAY=1 in the environment: at least one item whose exact7 rows passed). Arms screened: B and LO always;
  L when item L qualifies; O, Bs, Os when item O qualifies. Anything else: part b refuses (exit 1).

PASS / GAIN (GATE-PLAN sections 3.4, 3.5, 6; decided in gap b, decide-b -> results/r23/decode-timing/gap-b/decision.*):
  screen  the 9 workloads (warm-up, W1-W3, agent x2, research4 x4), 3 passes in turned order (client clock). For an arm X
          against its base (L, O, LO vs B; Os vs Bs), 3 complete passes each (else NOT DECIDED):
          - per workload, decode and prompt tok/s each: mean_X >= mean_base x (1 - the larger of the two arms'
            pass-to-pass spreads there, max / min - 1)                                                  (Karl 11-03)
          - overall: per pass the geometric mean over the 9 of decode and of prompt tok/s; an arm = the geometric mean
            of its passes; noise = the larger arm's pass spread (max / min - 1); X >= base x (1 - noise), decode and
            prompt
          - GAIN: decode X / base - 1 > max(noise, 1.0 %)
          An arm pass counts only with its env check PASS, its start line(s) right (the switch line present in L / O /
          LO / Os, absent in B / Bs; else NOT DECIDED) and no fatal line (fatal GPU error / stall / engine restart /
          non-finite: in an item's arm -> FAIL, in a base arm -> NOT DECIDED).
  bp90    Basalt's community-1 fixtures, cold, 3 passes, LO vs B: conv / struct / prose decode tok/s and pp16k / pp64k
          prompt tok/s: mean_LO >= mean_B x (1 - B's pass spread), B's spread = (max - min) / mean (gap 17's bp90 form)
  item L  PASS = EXACT + L and LO no loss + bp90 PASS; GAIN = PASS + L's decode gain
  item O  PASS = EXACT + O, Os and LO no loss + bp90 PASS; GAIN = PASS + O's decode gain (two cards, the served form);
          Os's gain on one card is reported beside it
  L + O   PASS = both items EXACT + LO no loss + bp90 PASS; GAIN = PASS + LO's decode gain
  GATE-PLAN section 5: the screen's decode noise has been 2.6-5.6 % per arm, so "PASS, no measured gain" is a likely
  outcome for one item; Karl decides whether mechanism + no loss is enough. Each arm's settled PCIe share (its "PCIe
  share:" lines) is reported (serve mode re-derives it from the pool's speed, a placement change that is not the item).

Subcommands (the drivers call them; --gate NAME --gates FILE appends "NAME STATUS detail"):
  blobs PACK GGUF OUTDIR          one real expert blob per (gate/up, down) type pair of the pack -> "GU D FILE" lines
  srccheck TREE                   build_src's source checks
  warncheck BUILDLOG --tree T --base REV --port LOG...   build_warn
  envcli EXE CONFIG --job PID --mode e7|pfy --ngpu N [--set K=V] [--kill]   an exact7 / pf_yardstick engine's
                                  environment as it starts (by /proc/PID/exe in the job's tree, never a command line)
  e7gate SUMMARY LABEL [--info]   exact7's "N/7" and slots lines (+ the 7 items' outputs present)
  lines --want late,one|none FILES...   the switches' start lines
  decide-a OUTDIR_A / check-a OUTDIR_A / decide-b OUTDIR_B --a OUTDIR_A / selftest [--dir D]
"""
import argparse
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import statistics as st
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
WS = Path("/home/USER/ai-speed-testing/strata-compare")
PROF = WS / "bringup/out/logs/prof"
ITEMS7 = ("x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k")
WL9 = ("W1-think", "W2-code", "W3-research", "A-edit", "B-write", "R1-verify20k", "R2-report54k", "R3-extract5k",
       "R4-agent33k")
LINE = {"late": "the helper GPUs' staging and launches follow the CPU pool's publish",
        "one": "a layer's gate/up and down rows in one batch, no barrier between"}
GAIN_MIN = 0.010
# ggml types of the pack (native_experts.txt): (elements, bytes) per block
TYPE_BLOCK = {18: (256, 98), 20: (32, 18), 21: (256, 110), 22: (256, 82), 23: (256, 136), 42: (64, 18)}
TYPE_NAME = {18: "IQ3_XXS", 20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 42: "Q2_0"}
PAIRS = ((22, 20), (22, 42), (21, 20), (21, 42), (18, 20), (18, 42), (23, 20))   # GATE-PLAN section 2
N_EMBD, N_FF, N_EXPERT = 2560, 640, 512
# the gates of part a, by role
BUILD = ("build_x", "build8", "build_src", "build_warn")
TESTS = ("t_pooltasks",) + tuple(f"t_pooltasks_{TYPE_NAME[g]}_{TYPE_NAME[d]}" for g, d in PAIRS) + (
    "t_pool", "t_numa", "t_stress", "t_stress_ob", "t_guard", "servetests")
E7 = {"B": "r23-B", "B2": "r23-B2", "L": "r23-L", "O": "r23-O", "LO": "r23-LO", "Bs": "r23-Bs", "Os": "r23-Os"}
E7_WANT = {"B": "none", "B2": "none", "L": "late", "O": "one", "LO": "late,one", "Bs": "none", "Os": "one"}
ITEM_E7 = {"L": ("B", "B2", "L", "LO"), "O": ("B", "B2", "O", "Os", "LO")}
PFY = ("pfy_B_LO", "pfy_B_p210")
SCREEN = {"L": "B", "O": "B", "LO": "B", "Os": "Bs"}   # arm -> its base
ARM_WANT = {"B": "none", "Bs": "none", "L": "late", "O": "one", "LO": "late,one", "Os": "one"}


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def read_gates(o):
    g = {}
    p = Path(o) / "gates.txt"
    for line in p.read_text().splitlines() if p.exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)     # the last line of a gate counts
    return g


def gm(v):
    return math.exp(sum(math.log(x) for x in v) / len(v))


def spread(v):
    return max(v) / min(v) - 1 if len(v) > 1 else 0.0


# ------------------------------------------------------------------------------------------------ build and tests
def row_bytes(t, n):
    be, bs = TYPE_BLOCK[t]
    if n % be:
        raise SystemExit(f"type {t}: {n} is not whole blocks")
    return n // be * bs


def blobs(a):
    pack, gguf, out = Path(a.pack), Path(a.gguf), Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [l.split() for l in (pack / "native_experts.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
    bad = []
    for gu, dt in PAIRS:
        r = next((x for x in rows if int(x[1]) == gu and int(x[2]) == dt), None)
        if r is None:
            bad.append(f"{TYPE_NAME[gu]}/{TYPE_NAME[dt]}: no layer of the pack has it")
            continue
        layer, blob, go, uo, do = int(r[0]), int(r[4]), int(r[5]), int(r[6]), int(r[7])
        f = gguf.parent / r[8] if len(r) > 8 else gguf
        G, D = row_bytes(gu, N_EMBD) * N_FF, row_bytes(dt, N_FF) * N_EMBD
        if 2 * G + D != blob:
            bad.append(f"layer {layer}: 2 x {G} + {D} != the pack's blob size {blob}")
            continue
        spans = sorted([(go, go + N_EXPERT * G), (uo, uo + N_EXPERT * G), (do, do + N_EXPERT * D)])
        if any(spans[i][1] > spans[i + 1][0] for i in range(2)) or spans[-1][1] > f.stat().st_size:
            bad.append(f"layer {layer}: the gate / up / down tensors overlap or run past {f.name}")
            continue
        e = 0                                    # expert 0 of the first layer with this pair
        parts = []
        with open(f, "rb") as h:
            for off, n in ((go + e * G, G), (uo + e * G, G), (do + e * D, D)):
                h.seek(off)
                parts.append(h.read(n))
        b = b"".join(parts)
        if len(b) != blob or not any(b[:4096]) or not any(b[-4096:]):
            bad.append(f"layer {layer}: short or empty read")
            continue
        p = out / f"blob-{TYPE_NAME[gu]}-{TYPE_NAME[dt]}-L{layer}.bin"
        p.write_bytes(b)
        print(f"{gu} {dt} {p} {TYPE_NAME[gu]}_{TYPE_NAME[dt]} layer {layer} expert {e} ({blob} bytes)")
    for x in bad:
        print("BLOB PROBLEM:", x, file=sys.stderr)
    return 1 if bad else 0


def srccheck(a):
    t = Path(a.tree)
    rd = lambda p: (t / p).read_text(errors="replace") if (t / p).exists() else ""
    bad = []
    rc = rd("src/core/remote_experts.cpp")
    m = re.search(r"bool RemoteExperts::begin\([^)]*\)\s*\{(.*?)\n\}", rc, re.S)
    body = re.sub(r"//[^\n]*", "", m[1]) if m else ""
    body = " ".join(body.split())
    if body != "return claim(layer, ids, n_tok, k, kind, primary_res, err) && launch(layer, x, n_tok, k, err);":
        bad.append(f"begin() is not just claim() && launch(): {body[:120]!r}")
    hp = rd("include/strata/core/remote_experts.hpp")
    if not (re.search(r"bool claim\(", hp) and re.search(r"bool launch\(", hp)):
        bad.append("remote_experts.hpp: claim() / launch() not declared")
    es = rd("src/core/expert_source.cpp")
    m = re.search(r"struct LateLaunch \{(.*?)\n    \}", es, re.S)
    if not m or "static void run(" not in m[1]:
        bad.append("expert_source.cpp: struct LateLaunch with a static run member not found")
    ph = rd("include/strata/kernels/cpu/pool.hpp")
    for x in ("ObExpert", "ExitStamp"):
        if not re.search(rf"struct alignas\(\d+\) {x}\b|alignas\([^)]*\)[^;\n]*{x}|struct {x}[^\n]*alignas", ph):
            bad.append(f"pool.hpp: an aligned {x} not found")
    gc = rd("src/program/generate.cpp")
    for x in ("drive.d.pool", "copy_before"):
        if x not in gc:
            bad.append(f"generate.cpp: {x} not found")
    line = ("begin() = claim() && launch(); LateLaunch::run; aligned ObExpert / ExitStamp; generate.cpp's drive.d.pool / "
            "copy_before - all in the tree built" if not bad else "; ".join(bad))
    print(line + (" -> PASS" if not bad else " -> FAIL"))
    gate(a, "FAIL" if bad else "PASS", line[:400])
    return 1 if bad else 0


WARN_RE = re.compile(r"(?P<f>[^\s:()\"']+\.(?:c|cc|cpp|cu|cuh|h|hpp))(?::\d+(?::\d+)?:|\(\d+\)[:,]?)\s*warning\b[:#]?\s*(?P<m>.*)$")


def warnings_of(text, files):
    out = set()
    for line in text.splitlines():
        m = WARN_RE.search(line)
        if not m:
            continue
        f = m["f"]
        hit = next((x for x in files if f.endswith(x)), None)
        if hit:
            out.add((hit, re.sub(r"\d+", "N", m["m"].strip())[:200]))
    return out


def warncheck(a):
    files = [x for x in (a.files or []) if x]
    if not files:
        import subprocess
        files = subprocess.run(["git", "-C", a.tree, "diff", "--name-only", f"{a.base}..HEAD"], capture_output=True,
                               text=True).stdout.split()
    ours = warnings_of(Path(a.buildlog).read_text(errors="replace"), files)
    port = set()
    for p in a.port or []:
        if Path(p).exists():
            port |= warnings_of(Path(p).read_text(errors="replace"), files)
    new = sorted(ours - port)
    line = (f"{len(ours)} distinct warning(s) in the {len(files)} files the r23 commits touch, {len(new)} not in the port's "
            "own build logs" + (": " + "; ".join(f"{f}: {m}" for f, m in new[:4]) if new else ""))
    print(line + (" -> PASS" if not new else " -> FAIL"))
    gate(a, "FAIL" if new else "PASS", line[:400])
    return 1 if new else 0


# ------------------------------------------------------------------------------------------------ engine environment
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def proc_tree(root):
    kids = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            f = Path(f"/proc/{d}/stat").read_text().rsplit(")", 1)[1].split()
            kids.setdefault(int(f[1]), []).append(int(d))
        except (OSError, IndexError, ValueError):
            continue
    out, todo = set(), [root]
    while todo:
        p = todo.pop()
        for c in kids.get(p, []):
            if c not in out:
                out.add(c)
                todo.append(c)
    return out


def alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return False


def last_val(argv, flag):
    v = [argv[i + 1] for i, x in enumerate(argv[:-1]) if x == flag]
    return v[-1] if v else None


def env_want(cfg, mode, sets):
    want, allowed = dict(cfg.get("env", {})), {"STRATA_MON_GPU"}
    if mode == "pfy":
        qq = load("pf_yardstick", WS / "work/r22/pf_yardstick.py").tool()
        want.update(qq.FIXED_ENV)
        allowed.add("STRATA_DUMP_FIRST_LOGITS")
        fx = dict(zip(qq.FIXED[0::2], qq.FIXED[1::2]))
        fx.update({"--prefill": "auto", "--kv": "fp16"})          # pf_yardstick's own replacements
        args_want = {k: fx[k] for k in ("--expert-cache", "--pcie-frac", "--kv", "--prefill", "--adapt-every",
                                        "--suffix-draft", "--prompt-cache")}
    else:
        args_want = {"--expert-cache": "2500", "--adapt-swaps": "0", "--suffix-draft": "0"}
        if "--kv-resident" in cfg.get("user_args", []):
            args_want["--kv-resident"] = "32768"
    for kv in sets or []:
        k, _, v = kv.partition("=")
        want[k] = v
    return want, allowed, args_want


def env_bad(env, argv, want, allowed, args_want, ngpu, mode):
    bad = [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]
    bad += [f"{k}={env[k]} (not in the config)" for k in sorted(env) if k.startswith("STRATA_") and k not in want
            and k not in allowed]
    if env.get("STRATA_ROUTE_TAIL_SKIP") != "0":
        bad.append(f"STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}")
    n = len([x for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
    if n != ngpu:
        bad.append(f"{n} GPU(s) in CUDA_VISIBLE_DEVICES (want {ngpu})")
    if mode == "pfy" and (len(argv) < 2 or argv[1] != "--serve"):
        bad.append("not the --serve engine")
    bad += [f"{k} {last_val(argv, k)} (want {v})" for k, v in args_want.items() if last_val(argv, k) != v]
    return bad


def envcli(a):
    cfg = json.loads(Path(a.config).read_text())
    want, allowed, args_want = env_want(cfg, a.mode, a.set)
    exe = os.path.realpath(a.exe)
    seen = {}
    t_end = time.time() + a.max_s
    while time.time() < t_end:
        done = not alive(a.job)
        for pid in sorted(proc_tree(a.job) | {a.job}):
            if pid in seen:
                continue
            try:
                if os.readlink(f"/proc/{pid}/exe") != exe:
                    continue
                env = dict(x.split("=", 1) for x in Path(f"/proc/{pid}/environ").read_bytes().decode("utf-8", "replace")
                           .split("\0") if "=" in x)
                argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace").split("\0")
            except OSError:
                continue
            bad = env_bad(env, argv, want, allowed, args_want, a.ngpu, a.mode)
            seen[pid] = bad
            killed = ""
            if bad and a.kill:
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed = "; STOPPED (by pid) before it measures"
                except OSError:
                    killed = "; could not stop it"
            print(f"engine pid {pid}: {len(want)} env keys, STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}, "
                  f"{len([x for x in env.get('CUDA_VISIBLE_DEVICES', '').split(',') if x])} GPU(s), "
                  f"{' '.join(f'{k} {last_val(argv, k)}' for k in args_want)}"
                  + (f" -> ENV MISMATCH {', '.join(bad)}{killed}" if bad else " -> ENV OK"), flush=True)
        if done:
            break
        time.sleep(0.3)
    bad_all = [b for v in seen.values() for b in v]
    if not seen:
        line = f"no engine {exe} started in job {a.job}"
    elif bad_all:
        line = f"{sum(1 for v in seen.values() if v)} of {len(seen)} engine start(s) not as configured: " + "; ".join(sorted(set(bad_all)))
    else:
        line = (f"{len(seen)} engine start(s) ({a.mode}, {a.ngpu} GPU(s)), {len(want)} env keys as configured"
                + (f" + {' '.join(a.set)}" if a.set else "") + ", no other STRATA_*, harness args as expected")
    ok = bool(seen) and not bad_all
    print(("ENV CHECK OK: " if ok else "ENV CHECK FAILED - the arm is void: ") + line, flush=True)
    gate(a, "PASS" if ok else "FAIL", line[:400])
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ exact7 and start lines
def e7_of(summary, label):
    s = Path(summary).read_text(errors="replace") if Path(summary).exists() else ""
    m = re.findall(rf"^exact7 {re.escape(label)}: (\d)/7 identical to (\S+)", s, re.M)
    sl = re.findall(rf"^exact7-slots {re.escape(label)}: (.*)-> (MATCHED|DIFFER)", s, re.M)
    return (int(m[-1][0]) if m else None), (m[-1][1] if m else None), (sl[-1][1] if sl else None), (sl[-1][0].strip() if sl else "")


def items_present(label):
    n = 0
    for it in ITEMS7:
        p = PROF / f"{label}-{it}.out"
        if p.exists() and re.search(r"^output\s*:", p.read_text(errors="replace"), re.M):
            n += 1
    return n


def e7gate(a):
    n, ref, sl, slots = e7_of(a.summary, a.label)
    have = items_present(a.label)
    ok = n == 7 and sl == "MATCHED" and have == 7
    line = f"exact7 {a.label}: {n if n is not None else '?'}/7 vs {ref or '?'}, slots {sl or '?'} ({slots}), {have}/7 item outputs"
    status = ("INFO" if have == 7 else "FAIL") if a.info else ("PASS" if ok else "FAIL")
    print(f"{line} -> {status}")
    gate(a, status, line)
    return 0


def lines(a):
    want = [w for w in a.want.split(",") if w and w != "none"]
    txt = ""
    for f in a.files:
        try:
            txt += Path(f).read_text(errors="replace")
        except OSError:
            pass
    have = {k: (v in txt) for k, v in LINE.items()}
    miss = [k for k in want if not have[k]]
    extra = [k for k in LINE if k not in want and have[k]]
    ok = bool(txt) and not miss and not extra
    line = (f"start lines (want {a.want}): " + ", ".join(f"{k} {'present' if have[k] else 'absent'}" for k in LINE)
            + (f"; MISSING {', '.join(miss)} (the switch's path did not run: UNEXERCISED)" if miss else "")
            + (f"; UNWANTED {', '.join(extra)} (a switch reached an arm without it)" if extra else "")
            + ("" if txt else "; no log text"))
    print(line + (" -> PASS" if ok else " -> FAIL"))
    gate(a, "PASS" if ok else "FAIL", line[:400])
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ part a's decision
def need(g, keys, why):
    """FAIL if any key failed, NOT DECIDED if any is missing, else PASS (INFO counts as present)"""
    worst = "PASS"
    for k in keys:
        s = g.get(k, ("MISSING", ""))[0]
        if s in ("PASS", "INFO"):
            continue
        if s == "MISSING":
            why.append(f"{k}: not run")
            worst = "NOT DECIDED" if worst == "PASS" else worst
        else:
            why.append(f"{k}: {s} {g[k][1]}".strip()[:240])
            worst = "FAIL"
    return worst


def combine(*v):
    return "FAIL" if "FAIL" in v else ("NOT DECIDED" if "NOT DECIDED" in v else "PASS")


def decide_a(a):
    o = Path(a.outdir)
    g = read_gates(o)
    s = lambda k: g.get(k, ("MISSING", ""))[0]
    L, out = [], {"written": time.strftime("%F %T"), "items": {}, "gates": {k: v[0] for k, v in g.items()}}
    L.append(f"decode items, gap a - decision ({out['written']}; rules: work/r23/decode_rules.py, written before the gap)")
    wb, wt = [], []
    out["build"] = need(g, BUILD, wb)
    out["tests"] = need(g, TESTS, wt)
    L.append(f"build: {out['build']}" + (f" ({'; '.join(wb)})" if wb else f" - {g.get('build_x', ('', ''))[1][:160]}"))
    L.append(f"tests: {out['tests']}" + (f" ({'; '.join(wt)})" if wt else " - every step-2 test rc 0"))
    e7s = {}
    for k, lab in E7.items():
        keys = [f"e7_{k}", f"env_e7-{lab}", f"e7lines_{k}"]
        w = []
        e7s[k] = need(g, keys, w)
        L.append(f"exact7 {lab}: {e7s[k]} - {g.get(f'e7_{k}', ('', 'not run'))[1][:150]}" + (f" ({'; '.join(w)})" if e7s[k] != "PASS" else ""))
    out["exact7"] = e7s
    out["exact7_base"] = combine(e7s["B"], e7s["B2"])
    wp = []
    out["logits"] = need(g, PFY + ("env_pfy-B", "env_pfy-LO"), wp)
    L.append(f"logits (pf_yardstick long40): {out['logits']} - " + "; ".join(f"{k} {g.get(k, ('MISSING', ''))[0]} {g.get(k, ('', ''))[1][:80]}" for k in PFY))
    for it, rows in ITEM_E7.items():
        why = []
        if out["build"] != "PASS":
            why.append(f"build {out['build']}")
        if out["tests"] != "PASS":
            why.append(f"tests {out['tests']}")
        e7v = combine(*(e7s[r] for r in rows))
        if it == "O" and "e7_Bs" not in g:
            e7v = combine(e7v, "NOT DECIDED")
            why.append("the solo base r23-Bs did not run")
        if e7v != "PASS":
            why.append("exact7 " + ", ".join(f"{E7[r]} {e7s[r]}" for r in rows if e7s[r] != "PASS"))
        if out["logits"] != "PASS":
            why.append(f"logits {out['logits']}")
        v = combine(out["build"], out["tests"], e7v, out["logits"])
        out["items"][it] = {"exact": v, "exact7": e7v, "why": why}
        L.append(f"=> item {it} ({'STRATA_REMOTE_LATE_LAUNCH=1' if it == 'L' else 'STRATA_POOL_ONE_BATCH=1'}): EXACT {v}"
                 + (f" ({'; '.join(why)})" if why else ""))
    # INFO: the mechanism (timing arms, the two-card pass)
    for n in ("Bt", "LOt", "Bst", "Ost"):
        p = o / "timing" / f"report-{n}.txt"
        if p.exists():
            first = [x for x in p.read_text(errors="replace").splitlines() if x.strip()][:2]
            L.append(f"timing {n} (INFO): " + " | ".join(first)[:300])
    for k, v in g.items():
        if k.startswith(("lines_t-", "env_t-", "t2pass")):
            L.append(f"{k} (INFO): {v[0]} {v[1][:160]}")
    if g.get("kfail"):
        L.append("a kernel check FAILED: the gap stays open - Karl decides")
    out["engine"] = g.get("build_x", ("", ""))[1]
    out["engine_sha"] = (re.search(r"engine-r23decode ([0-9a-f]{12})", out["engine"]) or [None, None])[1]
    (o / "decision.txt").write_text("\n".join(L) + "\n")
    (o / "decision.json").write_text(json.dumps(out, indent=1))
    print("\n".join(L))
    return 0


def plan_b(da, anyway=False):
    """from part a's decision.json: (may_run, arms, why)"""
    if da.get("build") != "PASS":
        return False, [], f"part a's build is {da.get('build')}"
    if da.get("exact7_base") != "PASS":
        return False, [], f"part a's exact7 base (r23-B vs g17-p210a, r23-B2 vs r23-B) is {da.get('exact7_base')}"
    it = da.get("items", {})
    ok = {k: (v.get("exact7") == "PASS" if anyway else v.get("exact") == "PASS") for k, v in it.items()}
    if not any(ok.values()):
        return False, [], ("no item's exact7 rows passed" if anyway else "no item is EXACT in part a: " + "; ".join(
            f"{k} {v.get('exact')} ({'; '.join(v.get('why', []))[:160]})" for k, v in it.items()))
    if da.get("exact7", {}).get("LO") != "PASS":
        return False, [], "r23-LO (both switches) did not pass exact7: no item can PASS"
    arms = ["B", "LO"] + (["L"] if ok.get("L") else []) + (["O", "Bs", "Os"] if ok.get("O") else [])
    return True, arms, "items " + ", ".join(k for k, v in ok.items() if v)


def check_a(a):
    p = Path(a.outdir) / "decision.json"
    if not p.exists():
        print(f"part a's decision file {p} is missing: part b refuses")
        return 1
    da = json.loads(p.read_text())
    may, arms, why = plan_b(da, anyway=os.environ.get("R23B_SCREEN_ANYWAY") == "1")
    if not may:
        print(f"part b refuses: {why}")
        return 1
    print(f"ARMS {' '.join(arms)}")
    print(f"SHA {da.get('engine_sha') or '-'}")
    print(f"WHY {why}")
    return 0


# ------------------------------------------------------------------------------------------------ part b's decision
def screen_rows(o, arm, k):
    rows = {}
    for s in "nar":
        p = Path(o) / "speed" / f"{arm}{k}{s}.jsonl"
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    rows[r["id"]] = r
    return rows


def pass_ok(g, arm, k):
    """an arm pass counts: env PASS, start lines PASS, no fatal gate"""
    n = f"{arm}{k}"
    return g.get(f"env_{n}", ("MISSING",))[0] == "PASS" and g.get(f"lines_{n}", ("MISSING",))[0] == "PASS" \
        and f"fatal_{n}" not in g


def passes(o, g, arm):
    out = {}
    for k in (1, 2, 3):
        if not pass_ok(g, arm, k):
            continue
        rows = screen_rows(o, arm, k)
        if all(w in rows and rows[w].get("decode_tps") and rows[w].get("prompt_tps") for w in WL9):
            out[k] = {w: (rows[w]["decode_tps"], rows[w]["prompt_tps"]) for w in WL9}
    return out


def screen_cmp(o, g, arm, base):
    """no-loss (per workload + overall) and the decode gain of ARM against BASE: (status, gain, lines)"""
    x, b = passes(o, g, arm), passes(o, g, base)
    if len(x) < 3 or len(b) < 3:
        return "NOT DECIDED", False, [f"{arm} vs {base}: {len(x)} / {len(b)} complete clean passes of 3"]
    L, ok, gain = [], True, False
    for idx, name in ((0, "decode"), (1, "prompt")):
        px = [gm([v[w][idx] for w in WL9]) for v in x.values()]
        pb = [gm([v[w][idx] for w in WL9]) for v in b.values()]
        mx, mb = gm(px), gm(pb)
        noise = max(spread(px), spread(pb))
        d = mx / mb - 1
        good = mx >= mb * (1 - noise)
        ok &= good
        if idx == 0:
            gain = d > max(noise, GAIN_MIN)
        L.append(f"{arm} vs {base} {name}: {100 * d:+.2f} % ({mx:,.1f} vs {mb:,.1f} tok/s; noise {100 * noise:.1f} %) -> "
                 + ("no loss" if good else "LOSS") + (f"; GAIN (> max(noise, 1 %))" if idx == 0 and gain else ""))
    slower = []
    for w in WL9:
        for idx, name in ((0, "decode"), (1, "prompt")):
            xa, ba = [v[w][idx] for v in x.values()], [v[w][idx] for v in b.values()]
            noise = max(spread(xa), spread(ba))
            d = st.mean(xa) / st.mean(ba) - 1
            if d < -noise:
                slower.append(f"{w} {name} {100 * d:+.1f} % (noise {100 * noise:.1f} %)")
    ok &= not slower
    L.append(f"{arm} vs {base} per workload: " + ("none of the 9 slower beyond its noise" if not slower else
                                                  "SLOWER " + "; ".join(slower)))
    return ("PASS" if ok else "FAIL"), gain, L


def bp90_cmp(o, g):
    def load_(n):
        p = Path(o) / "bp90" / f"cold-{n}.jsonl"
        recs = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        return [r for r in recs if f"fatal_bp{n}-{'decode' if r['test'] in ('conv', 'struct', 'prose') else r['test']}-{r['pass']}" not in g]
    B, X = load_("B"), load_("LO")
    L, ok, have = [], True, True
    for t, key in (("conv", "decode_tps"), ("struct", "decode_tps"), ("prose", "decode_tps"), ("pp16k", "prompt_tps"),
                   ("pp64k", "prompt_tps")):
        b = [r[key] for r in B if r["test"] == t and r.get(key)]
        x = [r[key] for r in X if r["test"] == t and r.get(key)]
        if len(b) < 3 or len(x) < 3:
            have = False
            L.append(f"bp90 {t}: B {len(b)} / LO {len(x)} passes of 3 - not decided")
            continue
        sp = (max(b) - min(b)) / st.mean(b)
        d = st.mean(x) / st.mean(b) - 1
        good = st.mean(x) >= st.mean(b) * (1 - sp)
        ok &= good
        L.append(f"bp90 {t} ({key[:-4]}): LO {st.mean(x):,.1f} vs B {st.mean(b):,.1f} ({100 * d:+.1f} %; B's spread "
                 f"{100 * sp:.1f} %) -> " + ("no loss" if good else "LOSS"))
    return ("NOT DECIDED" if not have else ("PASS" if ok else "FAIL")), L


def decide_b(a):
    o, oa = Path(a.outdir), Path(a.a)
    g = read_gates(o)
    da = json.loads((oa / "decision.json").read_text()) if (oa / "decision.json").exists() else {"items": {}}
    L = [f"decode items, gap b - decision ({time.strftime('%F %T')}; rules: work/r23/decode_rules.py, written before the gaps)"]
    out = {"written": time.strftime("%F %T"), "arms": {}, "items": {}}
    fatal = {k for k in g if k.startswith("fatal_")}
    res = {}
    for arm, base in SCREEN.items():
        if not (o / "speed").exists() or not any((o / "speed").glob(f"{arm}[123]n.jsonl")):
            res[arm] = ("NOT RUN", False, [f"{arm}: not screened"])
            continue
        res[arm] = screen_cmp(o, g, arm, base)
        ff = sorted(k for k in fatal if re.fullmatch(rf"fatal_{arm}\d", k))
        fb = sorted(k for k in fatal if re.fullmatch(rf"fatal_{base}\d", k))
        st_, gn, ln = res[arm]
        if ff:
            st_, ln = "FAIL", ln + [f"{arm}: fatal line(s) in {', '.join(ff)}"]
        elif fb and st_ != "FAIL":
            st_, ln = "NOT DECIDED", ln + [f"{base} (the base): fatal line(s) in {', '.join(fb)}"]
        res[arm] = (st_, gn, ln)
        for x in ln:
            L.append("  " + x)
        out["arms"][arm] = {"noloss": st_, "gain": gn}
    bp, bl = bp90_cmp(o, g)
    L += ["  " + x for x in bl]
    out["bp90"] = bp
    for k, v in g.items():
        if (k.startswith(("env_", "lines_")) and v[0] != "PASS") or k.startswith("fatal_"):
            L.append(f"  gate {k}: {v[0]} {v[1][:160]}")
    pcie = {k: v[1] for k, v in g.items() if k.startswith("pcie_")}
    if pcie:
        L.append("  settled PCIe share per arm pass (INFO): " + "; ".join(f"{k[5:]} {v[:60]}" for k, v in sorted(pcie.items())))

    def item(name, exact, arms, gain_arm):
        why = [] if exact == "PASS" else [f"EXACT {exact} (gap a)"]
        v = [exact]
        for x in arms:
            s_ = res.get(x, ("NOT RUN",))[0]
            v.append("NOT DECIDED" if s_ == "NOT RUN" else s_)
            if s_ != "PASS":
                why.append(f"{x} screen {s_}")
        v.append(bp)
        if bp != "PASS":
            why.append(f"bp90 {bp}")
        verdict = combine(*v)
        if verdict == "PASS" and res.get(gain_arm, (None, False))[1]:
            verdict = "GAIN"
        return verdict, why
    ex = {k: da.get("items", {}).get(k, {}).get("exact", "NOT DECIDED") for k in ("L", "O")}
    for name, exact, arms, ga, txt in (("L", ex["L"], ("L", "LO"), "L", "STRATA_REMOTE_LATE_LAUNCH=1"),
                                       ("O", ex["O"], ("O", "Os", "LO"), "O", "STRATA_POOL_ONE_BATCH=1"),
                                       ("L+O", combine(ex["L"], ex["O"]), ("LO",), "LO", "both")):
        verdict, why = item(name, exact, arms, ga)
        out["items"][name] = {"verdict": verdict, "why": why}
        extra = ""
        if name == "O" and "Os" in res:
            extra = f"; one card (Os vs Bs): {'GAIN' if res['Os'][1] else 'no gain beyond max(noise, 1 %)'}"
        L.append(f"=> item {name} ({txt}): {verdict}" + (f" ({'; '.join(why)})" if why else "") + extra)
    L.append("Nothing is switched or served: a PASS / GAIN item is a candidate for after item 7 (Karl decides; GATE-PLAN "
             "section 5: mechanism + no loss may be enough for one item, Karl's call).")
    (o / "decision.txt").write_text("\n".join(L) + "\n")
    (o / "decision.json").write_text(json.dumps(out, indent=1))
    print("\n".join(L))
    return 0


# ------------------------------------------------------------------------------------------------ dry runs
def selftest(a):
    d = Path(a.dir)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    bad = []

    def chk(name, ok, detail=""):
        print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + detail) if detail else ''}")
        if not ok:
            bad.append(name)

    def ns(**k):
        return argparse.Namespace(**k)
    # 1 past data: gap 17's summary (exact7 lines), gap 17's exact7 runs (start lines: the port has neither switch)
    S17 = WS / "results/r22/gap17/summary.txt"
    gf = d / "g.txt"
    e7gate(ns(summary=str(S17), label="g17-p210a", info=False, gate="e7_x", gates=str(gf)))
    chk("e7gate on gap 17's g17-p210a: PASS", read_gates_file(gf).get("e7_x", ("",))[0] == "PASS", read_gates_file(gf).get("e7_x", ("", ""))[1])
    e7gate(ns(summary=str(S17), label="g17-hcr", info=False, gate="e7_h", gates=str(gf)))
    chk("e7gate on gap 17's g17-hcr (3/7): FAIL", read_gates_file(gf).get("e7_h", ("",))[0] == "FAIL")
    errs = [str(PROF / f"g17-p210a-{i}.err") for i in ITEMS7]
    chk("lines none on the port's exact7 logs: PASS", lines(ns(want="none", files=errs, gate=None, gates=None)) == 0)
    chk("lines late on the port's logs: FAIL (UNEXERCISED)", lines(ns(want="late", files=errs, gate=None, gates=None)) == 1)
    # 2 the source and warning checks on the real tree / the port's logs (read only)
    chk("srccheck on strata-r23decode: PASS", srccheck(ns(tree=str(WS / "strata-r23decode"), gate=None, gates=None)) == 0)
    files = ["include/strata/core/remote_experts.hpp", "include/strata/kernels/cpu/pool.hpp", "src/core/expert_source.cpp",
             "src/core/remote_experts.cpp", "src/kernels/cpu/pool.cpp", "src/kernels/cpu/pool_tasks_test.cpp",
             "src/program/generate.cpp"]
    plog = WS / "strata-r22p0210/build.log"
    chk("warncheck: the port's own log against itself: PASS", warncheck(ns(buildlog=str(plog), files=files, tree="", base="",
        port=[str(plog), str(WS / "strata-r22p0210/build-tests.log")], gate=None, gates=None)) == 0)
    fake = d / "build.log"
    fake.write_text(plog.read_text(errors="replace") + "\n/x/strata-r23decode/src/kernels/cpu/pool.cpp:1544:12: warning: unused variable 'nb' [-Wunused-variable]\n")
    chk("warncheck: one new warning in pool.cpp: FAIL", warncheck(ns(buildlog=str(fake), files=files, tree="", base="",
        port=[str(plog)], gate=None, gates=None)) == 1)
    # 3 the blobs: offsets / sizes from the pack, a real read of 7 x ~2 MB into the scratch folder
    rc = blobs(ns(pack=str(WS / "bringup/out/r20a/pack"), gguf=str(WS / "models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"),
                  outdir=str(d / "blobs")))
    chk("blobs: 7 pairs cut", rc == 0 and len(list((d / "blobs").glob("blob-*.bin"))) == 7)
    # 4 envcli's check on synthetic environments (no process)
    cfg = json.loads((WS / "results/r23/decode-timing/gate-configs/r23-B.json").read_text())
    want, allowed, aw = env_want(cfg, "e7", ["STRATA_POOL_ONE_BATCH=1"])
    env = dict(want, STRATA_MON_GPU="x")
    argv = [cfg["exe"]] + cfg["args"] + ["--adapt-swaps", "0", "--suffix-draft", "0", "--expert-cache", "2500"]
    chk("envcli e7: r23-B + ONE_BATCH on 2 GPUs passes", env_bad(env, argv, want, allowed, aw, 2, "e7") == [])
    chk("envcli e7: 1 GPU expected -> fails", bool(env_bad(env, argv, want, allowed, aw, 1, "e7")))
    chk("envcli e7: LATE_LAUNCH leaked -> fails", bool(env_bad(dict(env, STRATA_REMOTE_LATE_LAUNCH="1"), argv, want, allowed, aw, 2, "e7")))
    w2, al2, aw2 = env_want(cfg, "pfy", [])
    argv2 = [cfg["exe"], "--serve", "--expert-cache", "1", "--adapt-every", "100000", "--pcie-frac", "0", "--suffix-draft",
             "0", "--prompt-cache", "0", "--kv", "fp16", "--prefill", "auto"]
    chk("envcli pfy: r23-B under pf_yardstick's fixed env passes", env_bad(dict(w2, STRATA_DUMP_FIRST_LOGITS="/x"), argv2,
        w2, al2, aw2, 2, "pfy") == [])
    # 5 part a's decision tree (synthetic gates)
    oa = d / "gap-a"
    oa.mkdir()
    allg = [(k, "PASS", "x") for k in BUILD + TESTS + PFY + ("env_pfy-B", "env_pfy-LO")]
    allg[0] = ("build_x", "PASS", "engine-r23decode 0123456789ab = v0.2.10 + 30 commits")
    for k, lab in E7.items():
        allg += [(f"e7_{k}", "INFO" if k == "Bs" else "PASS", "x"), (f"env_e7-{lab}", "PASS", "x"), (f"e7lines_{k}", "PASS", "x")]

    def run_a(gs):
        (oa / "gates.txt").write_text("".join(f"{k} {s_} {t}\n" for k, s_, t in gs))
        decide_a(ns(outdir=str(oa)))
        return json.loads((oa / "decision.json").read_text())
    da = run_a(allg)
    chk("part a all good: L and O EXACT", da["items"]["L"]["exact"] == "PASS" and da["items"]["O"]["exact"] == "PASS"
        and da["engine_sha"] == "0123456789ab")
    chk("part b may run with all 6 arms", plan_b(da) == (True, ["B", "LO", "L", "O", "Bs", "Os"], "items L, O"), str(plan_b(da)))
    da = run_a([x if x[0] != "e7_O" else ("e7_O", "FAIL", "6/7") for x in allg])
    chk("e7_O FAIL -> O FAIL, L EXACT; part b screens B LO L", da["items"]["O"]["exact"] == "FAIL"
        and da["items"]["L"]["exact"] == "PASS" and plan_b(da)[1] == ["B", "LO", "L"])
    da = run_a([x for x in allg if x[0] != "e7lines_L"])
    chk("L's start line not checked -> L NOT DECIDED", da["items"]["L"]["exact"] == "NOT DECIDED")
    da = run_a([x if x[0] != "build_x" else ("build_x", "FAIL", "build.log") for x in allg])
    chk("build FAIL -> part b refuses", plan_b(da)[0] is False and "build" in plan_b(da)[2])
    da = run_a([x if x[0] != "e7_B2" else ("e7_B2", "FAIL", "5/7") for x in allg])
    chk("e7_B2 FAIL -> part b refuses (exact7 base)", plan_b(da)[0] is False and "exact7 base" in plan_b(da)[2])
    da = run_a([x if x[0] != "t_stress_ob" else ("t_stress_ob", "FAIL", "rc 1") for x in allg])
    chk("a test fails -> no item EXACT -> part b refuses; R23B_SCREEN_ANYWAY screens both", plan_b(da)[0] is False
        and plan_b(da, anyway=True)[0] is True)
    da = run_a(allg)
    # 6 part b's decision on gap 17's screen and bp90 data, relabelled (B -> B, P -> L, L -> O, F -> LO; B -> Bs, P -> Os)
    ob = d / "gap-b"
    (ob / "speed").mkdir(parents=True)
    (ob / "bp90").mkdir()
    S17D = WS / "results/r22/gap17/speed"
    gb = []
    for src, dst in (("B", "B"), ("P", "L"), ("L", "O"), ("F", "LO"), ("B", "Bs"), ("P", "Os")):
        for k in (1, 2, 3):
            for s_ in "nar":
                f = S17D / f"{src}{k}{s_}.jsonl"
                if f.exists():
                    (ob / "speed" / f"{dst}{k}{s_}.jsonl").write_text(f.read_text())
            gb += [(f"env_{dst}{k}", "PASS", "x"), (f"lines_{dst}{k}", "PASS", "x")]
    shutil.copy(WS / "results/r22/gap17/bp90/cold-M.jsonl", ob / "bp90/cold-B.jsonl")
    shutil.copy(WS / "results/r22/gap17/bp90/cold-H.jsonl", ob / "bp90/cold-LO.jsonl")

    def run_b(gs):
        (ob / "gates.txt").write_text("".join(f"{k} {s_} {t}\n" for k, s_, t in gs))
        decide_b(ns(outdir=str(ob), a=str(oa)))
        return json.loads((ob / "decision.json").read_text())
    db = run_b(gb)
    chk("part b on gap 17's data: every arm decided (no NOT DECIDED from missing data)",
        all(v["noloss"] in ("PASS", "FAIL") for v in db["arms"].values()) and db["bp90"] in ("PASS", "FAIL"), json.dumps(db["arms"]))
    db = run_b([x for x in gb if x[0] != "lines_O2"])
    chk("O pass 2's start line missing -> the O arm NOT DECIDED (item O: LO's loss on this data makes it FAIL)",
        db["arms"]["O"]["noloss"] == "NOT DECIDED" and "O screen NOT DECIDED" in db["items"]["O"]["why"]
        and db["items"]["O"]["verdict"] == "FAIL")
    db = run_b(gb + [("fatal_LO3", "FAIL", "1 line")])
    chk("a fatal line in LO -> LO FAIL, every item FAIL", db["arms"]["LO"]["noloss"] == "FAIL"
        and all(v["verdict"] == "FAIL" for v in db["items"].values()))
    # synthetic screen: the arm equal to the base x 1.03 decode everywhere, +-0.5 % pass noise -> GAIN
    sy = d / "gap-b-syn"
    (sy / "speed").mkdir(parents=True)
    (sy / "bp90").mkdir()
    gs = []
    for arm, fac in (("B", 1.0), ("L", 1.03), ("O", 1.0), ("LO", 0.95), ("Bs", 1.0), ("Os", 1.02)):
        for k in (1, 2, 3):
            jit = 1 + 0.005 * (k - 2)
            for s_, ws in (("n", WL9[:3]), ("a", WL9[3:5]), ("r", WL9[5:])):
                (sy / "speed" / f"{arm}{k}{s_}.jsonl").write_text("".join(json.dumps(
                    {"id": w, "decode_tps": 150 * fac * jit, "prompt_tps": 3000 * jit}) + "\n" for w in ws))
            gs += [(f"env_{arm}{k}", "PASS", "x"), (f"lines_{arm}{k}", "PASS", "x")]
    for n, fac in (("B", 1.0), ("LO", 1.0)):
        recs = [{"test": t, "pass": k, key: v * (1 + 0.01 * (k - 2))} for k in (1, 2, 3) for t, key, v in
                (("conv", "decode_tps", 150), ("struct", "decode_tps", 160), ("prose", "decode_tps", 140),
                 ("pp16k", "prompt_tps", 4000), ("pp64k", "prompt_tps", 3000))]
        (sy / "bp90" / f"cold-{n}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    (sy / "gates.txt").write_text("".join(f"{k} {s_} {t}\n" for k, s_, t in gs))
    decide_b(ns(outdir=str(sy), a=str(oa)))
    db = json.loads((sy / "decision.json").read_text())
    chk("synthetic: L +3 % (noise 1 %) -> L arm GAIN; LO -5 % -> LO LOSS -> L FAIL (needs LO), O FAIL, L+O FAIL",
        db["arms"]["L"] == {"noloss": "PASS", "gain": True} and db["arms"]["LO"]["noloss"] == "FAIL"
        and db["items"]["L"]["verdict"] == "FAIL" and db["items"]["L+O"]["verdict"] == "FAIL", json.dumps(db["items"]))
    for k in (1, 2, 3):   # LO = the base again
        for s_, ws in (("n", WL9[:3]), ("a", WL9[3:5]), ("r", WL9[5:])):
            (sy / "speed" / f"LO{k}{s_}.jsonl").write_text("".join(json.dumps(
                {"id": w, "decode_tps": 150 * (1 + 0.005 * (k - 2)), "prompt_tps": 3000 * (1 + 0.005 * (k - 2))}) + "\n" for w in ws))
    decide_b(ns(outdir=str(sy), a=str(oa)))
    db = json.loads((sy / "decision.json").read_text())
    chk("synthetic: LO level -> L GAIN, O PASS (no gain), L+O PASS", db["items"]["L"]["verdict"] == "GAIN"
        and db["items"]["O"]["verdict"] == "PASS" and db["items"]["L+O"]["verdict"] == "PASS", json.dumps(db["items"]))
    print(f"selftest: {len(bad)} failure(s)" + (": " + ", ".join(bad) if bad else ""))
    return 1 if bad else 0


def read_gates_file(p):
    g = {}
    for line in Path(p).read_text().splitlines() if Path(p).exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name, *pos):
        p = sp.add_parser(name)
        for x in pos:
            p.add_argument(x)
        p.add_argument("--gate")
        p.add_argument("--gates")
        return p
    sub("blobs", "pack", "gguf", "outdir")
    sub("srccheck", "tree")
    p = sub("warncheck", "buildlog")
    p.add_argument("--tree", default=str(WS / "strata-r23decode"))
    p.add_argument("--base", default="fdd2fffa8")
    p.add_argument("--files", nargs="*")
    p.add_argument("--port", nargs="*")
    p = sub("envcli", "exe", "config")
    p.add_argument("--job", type=int, required=True)
    p.add_argument("--mode", choices=["e7", "pfy"], required=True)
    p.add_argument("--ngpu", type=int, required=True)
    p.add_argument("--set", action="append")
    p.add_argument("--kill", action="store_true")
    p.add_argument("--max-s", type=float, default=5400)
    p = sub("e7gate", "summary", "label")
    p.add_argument("--info", action="store_true")
    p = sub("lines")
    p.add_argument("--want", required=True)
    p.add_argument("files", nargs="*")
    sp.add_parser("decide-a").add_argument("outdir")
    sp.add_parser("check-a").add_argument("outdir")
    p = sp.add_parser("decide-b")
    p.add_argument("outdir")
    p.add_argument("--a", required=True)
    sp.add_parser("selftest").add_argument("--dir", default=str(WS / "work/r23/scratch-gaps/decode-selftest"))
    a = ap.parse_args()
    return {"blobs": blobs, "srccheck": srccheck, "warncheck": warncheck, "envcli": envcli, "e7gate": e7gate,
            "lines": lines, "decide-a": decide_a, "check-a": check_a, "decide-b": decide_b, "selftest": selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
