#!/usr/bin/env python3
"""gate0213_rules.py - r23 (written 2026-11-10 at the desk, NOT RUN on gate data; only its selftest ran, on stored and
synthetic data): THE v0.2.13 PORT'S BASELINE GATE. Karl 11-10, verbatim: "Baseline gate on the v0.2.13 port: yes, run it
next (exactness on the command-line path, long40, the 3-pass screen and Basalt's speed rule). If the -2.5% decode turns
out real beyond noise, find the cause desk-first, the same way as the 1.4% hunt, and note any pin for the Qwen4 port. Add
the single-card fallback config only if it's cheap."
The driver: work/r23/gate-0213/gap-gate0213.sh (started by gate-start.sh); the configs: make_configs0213.py. The model:
the v0.2.11 port's gate (work/r23/port0211_rules.py, ran 11-07, re-judged BASELINE PASS under the 11-07 amendment by the
confirmation gap) - its pieces are IMPORTED (port0211_rules.py, work/r22/g17_rules.py with the "11-07 park amendment"
section, work/r23/switch-gap/switch_rules.py), not copied. Written down BEFORE any run; the driver freezes this text (and
the sha256 of every file the gap runs) into the gate's rules.txt before the gap opens; `decide` flags a later change.
NOTHING SWITCHES: 8080 stays the daily (P028x on the fetch build); the verdict is a report to Karl.

THE BUILD UNDER TEST: engine-r23p0213 (639dfb1b7042; r23-port0213 6dd81ecd1 = v0.2.13 + 36 commits), its release
reference engine-v0213stock (stock v0.2.13 d2f096475, build-port0213.sh stock), the daily engine-r23afetch (153ce47d3ef0)
and P028x's CLI reference engine-r22p028x (f4c4f654fb24).

TAKEN FROM TODAY'S SWITCH GAP (results/r23/port-0213/switch-gap, 11-10; the same engine sha and tree), NOT RE-RUN - exactly
what it covered: C1 the C++ parity / unit tests (CPU and GPU), the server test suite and the node tests, the read-back
start; C2 the served outputs against the daily (EXACT, 8 requests); C3 the sampled test; C4 web search end to end (3
search prompts); C5 how often the lost-answer guard fires. NOT COVERED by the switch gap NOR by this gate (port0211 had
them): the live tool-call test (B vs P), the picture / vision and the chat-cache served-form checks. fence4 (CPU, seconds)
runs here before the gap, as port0211 ran it. switchref (REQUIRED, before the gap): its verdict.txt
is "SWITCH CHECKS PASS", its result.txt starts DONE, its summary.txt records P = engine-r23p0213 at sha S and the port
tree at head H; S = engine-r23p0213/strata's sha now (= 639dfb1b7042) and the worktree strata-r23p0213 is at H now; the
source configs (P028x.json, P0213x-af2.json, P0213x.json, x28h.json) have the sha256 its configs/manifest.json recorded.
Not so: the gate does not open (the results it stands on are not this build's).

ARMS (make_configs0213.py's RECIPES; written at run time into OUTDIR/configs):
  B    the daily as served, test form (switch_rules.py arm B: x28h + U + STRATA_ADAPT_FETCH=2 on engine-r23afetch)
  P    the port in the same form (switch_rules.py arm P: P0213x-af2's test form on engine-r23p0213)
  PH   the port's CLI form (P0213x's test form, no STRATA_ADAPT_FETCH); OFF (PH, our six switches off); ST (OFF on stock
       v0.2.13); NOV2 (PH without v2); x28h (configs/x28h.json, P028x's CLI reference); s028-h (stock 0.2.8, only when
       needed); SG (P0213x-single's test form: the single-card fallback, INFO)
  B / P run the screen and Basalt (the served form); the CLI parts (exact7, long40) run the CLI forms WITHOUT
  STRATA_ADAPT_FETCH, where bit identity is expected.

THE VERDICT - "the pinned-off v0.2.13 port = P028x" (every item required; INFO only where it says so):
  switchref  as above
  builds     build_x (engine-r23p0213 = its SHA256 file, SOURCE names r23-port0213 at the switch gap's head), build_stock
             (engine-v0213stock = its SHA256 file = strata-v0213stock/build/strata; SOURCE names stock v0.2.13's commit;
             the worktree there and clean), build8 (both configure logs: "windows hold up to 8 rows")
  cfg        make_configs0213.py check (its CHECKS)
  pins       pins / pins_h: the port's 19 env pins (port0211_rules.py's 18 + STRATA_ARENA_FILE_CACHE=0, Karl 11-09) with
             exact values and both keys ("drafting": "mtp", user_args ["--kv-resident", "32768"]) in configs/P0213x.json
             and in PH
  guards     "strata patch guards: 7 checked, 0 off" in PH's exact7 run (x-math)
  exact7     at pin 2500, slots MATCHED (bringup/lib/exact7.sh; port0211_rules.py e7gate): e7_release (OFF = ST, 7/7,
             FIRST); e7_vs_p028x (PH = x28h, 7/7). Not 7/7: e7_upstream (stock 0.2.8 = stock v0.2.13, both pinned)
             decides as in gap 17 / port0211 - upstream moved too (not 7/7) -> INFO, the KL rules decide; upstream did not
             move (7/7) -> FAIL ("our port changed bits"); not run -> INCOMPLETE. e7_repeat (PH twice, 7/7); e7_v2 (NOV2 =
             PH, 7/7). (So PH vs x28h is 7/7 EXPECTED, not required: not 7/7 with upstream moved too is INFO and the KL
             rules decide - gap 16 / 17's T1 rule, port0211's.) Every exact7 item's engine is checked as it starts
             (basalt_rules.py envcli --mode e7 --kill: env_NAME_e7); a pair runs only against a clean reference run. A
             pair whose slot counts are not MATCHED is NOT DECIDED (INCOMPLETE), never a FAIL and never "upstream moved"
             (the 10-22 slot-pin rule: exact7 compares builds only at matched slots). INFO: e7_vs_p0211 (PH against the
             stored g23p-p211a, the v0.2.11 port), e7_af2_stored (P's form against B's at pin 2500, both with
             STRATA_ADAPT_FETCH=2: the stored runs r23sw11101048-P / r23aa11091954-S2, read at the desk before the gap),
             e7_af2 (the same pair in the gap: only with P0213G_AF2_E7=1, default 0, and never in the time the required
             parts need)
  fence4     port0211_rules.py fence4 (gap 17's) on strata-r23p0213's own parser, before the gap: a four-backtick fence
             holding a three-backtick example and a </think> stays reasoning until it closes
  KL         kl2_p213 + kl3_p213: work/r22/kernel_rule2.py AND kernel_rule3.py on pf_yardstick long40 of PH against gap
             8's references (ref; rounding references unfused, cpushare), as port0211; env_pfy (envcli --mode pfy). INFO:
             logits_vs_p028x (PH's 40 first-token logit files against gap 16's x28h), logits_vs_p0211 (against the v0.2.11
             gate's p211)
  start      startlines_P (port0211_rules.py startlines on P's first clean screen start: its BASE_PRESENT lines present,
             BASE_ABSENT absent - #3961's lost-answer line and the no-drafter retry among them); every server start's
             env_TAG (port0211_rules.py envcheck --ngpu 2 --pins: the engine by /proc/PID/exe with the config's env
             exactly, none of the pins behind it, STRATA_ROUTE_TAIL_SKIP=0, 2 GPUs, --kv-resident 32768 last; its parent
             the config's server.py with the server pins), fenv_TAG (switch_rules.py armenv: one engine of the arm's
             binary sha, the fetch keys in the engine and its server, the parent's --config), line_TAG (switch_rules.py
             startline: "STRATA_ADAPT_FETCH=2: the PCIe share takes", no "is off"), no fatal_TAG (a fatal GPU error /
             stall / engine restart / non-finite line). A FAIL of one of these = FAIL (named).
             foreign_TAG (another GPU user before 60 s / during the start), void_TAG (the run left its test server or an
             engine behind), swap_TAG (THE SWAP RULE, standing: an engine of this gate with VmSwap > 0 in
             /proc/PID/status, read every GW_S s during every server start AND every CLI run - exact7, long40 - fails its
             run) and rc_TAG (the client chain ended rc != 0, or wrote no rc line): the start is LEFT OUT (its screen /
             Basalt records moved to void/; a CLI run's pair is not judged) -> INCOMPLETE (named), not FAIL [11-10: as
             the switch gap's machinery leaves such a start out; port0211 counted foreign as FAIL]
             THE KERNEL-ERROR STOP: when kfail is FAIL (a kernel error / kernel check failure stopped the gap), every start
             gate (env_, fenv_, line_, fatal_, foreign_, void_, swap_, rc_) written at or after the first kstop / kfail
             line of gates.txt, or belonging to the step the stop names ("during TAG" / "after TAG"), is "seen at the
             stop": INCOMPLETE (stopped, ranked first), never a FAIL reason
  lost       lost_answers: #3961's line in no server log of the port's arms (port0211_rules.py lost)
  cont_P     the answer_room continuations in P's screen requests: >= 1, all resumed (work/r22/gap9_verdicts.py cont)
  lossless   bringup/patchtest.sh lossless on P with this gate's P engine-log slices
  speed      the 9-workload screen, 3 passes in turned order (B P / P B / B P), port0211_rules.py speed(): g16's rule
             (g17.baseline_speed: per pass the geometric mean over the 9 of decode and of prompt tok/s, an arm = the
             geometric mean of its passes, noise = the larger arm's pass spread; P >= B - 1.0 % on decode and on prompt
             and no workload's prompt more than 3 % below B's -> PASS; between -1.0 % and -noise -> BORDERLINE; below
             -noise -> FAIL) PLUS Karl 11-03's per-workload no-loss (g17.wl_noloss, P against B), BOTH UNDER THE 11-07
             AMENDMENT (g17.park_amended: this gate starts after 2026-11-07 14:00 and has the screen's engine logs):
             per-workload prompt numbers on the engine clock minus the chat-cache save, the aggregate on the client
             clock minus the save, the outside-engine INFO flag; and the "chat-cache save" line (port0211_rules.py
             save() = g17.save_rule, P vs B): FAIL fails the baseline, NOT DECIDED leaves it INCOMPLETE, NOT JUDGED is INFO
  bp90       Basalt's community-1 fixtures, cold (a fresh engine per measurement), 3 passes in turned order (M H / H M /
             M H), M = B, H = P, g17.bp90_baseline (g16's rule as port0211): each decode fixture (conv, struct, prose)
             >= M - that fixture's spread (the larger build's); the token-weighted blend >= M - 1.0 %; 16K and 64K prompt
             >= M - 1.0 %. No P10 arm. Every fixture (conv, struct, prose, pp16k, pp64k) needs 3 records on each build
             (one a pass): fewer -> NOT DECIDED (INCOMPLETE, the short ones named), unless a fixture that has all 3
             FAILs. (bp90_client.py sends Basalt's own request keys - T 0.6 / T 0, min_p 0 - on the decode fixtures, as
             in every Basalt gate since 10-30; the servers' configs carry the standard sampling.)
  BASELINE = PASS when all of it holds; BORDERLINE when only g16's speed rule is borderline; INCOMPLETE (named) when a
  part was not run / not decided / left out, or a kernel error or the priority rule stopped the gap; FAIL (named)
  otherwise.

THE DECODE LINE (Karl 11-10: "If the -2.5% decode turns out real beyond noise ..."; the switch gap's INFO line, one pass
each: screen decode geomean P 166.1 vs B 170.4 tok/s, -2.5 %). Its rule, fixed here before any run:
  the statistic g16 uses: per complete screen pass (all 9 workloads with a decode rate, the client's decode_tps) the
  geometric mean over the 9 workloads; an arm's decode = the geometric mean of its passes; d = P / B - 1; noise = the
  larger of the two arms' pass spreads (max / min - 1 over the pass means; 3 passes each).
    REAL LOSS     d < -noise (P's decode below B's by more than the noise of the 3 passes)
    WITHIN NOISE  d >= -noise (a gain included)
    NOT DECIDED   fewer than 3 complete passes on an arm (a left-out pass included)
  The line answers Karl's question and does not change the BASELINE class (g16's rule above does). INFO with it: per
  workload, P's pass mean against B's (each workload's own noise = the larger arm's spread there), the workloads beyond
  their noise named; the switch gap's one-pass figure. REAL LOSS -> next: the desk hunt, the 1.4 % hunt's way (the
  decode-path changes v0.2.8 -> v0.2.13 and every new default our pins do not cover), and a pin note for the Qwen4 port.

INFO, never a verdict: the single-card fallback (configs/P0213x-single.json, one start of its test form on the RTX 5080
alone, only if 5 min fit before the deadline: its env (1 GPU) / armenv / start lines / fatal / lost-answer / lossless
checks and 3 short requests - conv, struct, prose at 512 tokens, the standard sampling, fixtures_client.py - with their
decode tok/s; every gate of that start ends in _SG); pcie_TAG (the settled PCIe share per screen pass); the switch gap's
C1-C5 and its one-pass speed line; skip_* lines (a part the deadline cut).

Subcommands (the driver calls them; Python: .venv/bin/python -I -B, nice 19):
  switchref SWDIR --sha S --head H [--gate --gates]   the switch gap's results and the build under test (exit 0 = PASS)
  pins CONFIG [--gate --gates]                        the 19 pins and the two keys
  singleplan IN OUT                                   the single-card start's 3 requests from switch_rules.py's fixtures plan
  single OUTDIR [--gate --gates]                      the single-card start's INFO line
  decode OUTDIR                                       the decode line
  rules OUT                                           the frozen rules (this text + the files' sha256)
  decide OUTDIR [--quiet]                             verdict.txt, decision.txt / .json, result-line.txt
  selftest SCRATCH                                    the rules on stored gate data + synthetic gates (no GPU, no engine)
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import re
import shutil
import statistics as stt
import sys
from pathlib import Path

sys.dont_write_bytecode = True
WS = Path("/home/USER/ai-speed-testing/strata-compare")
GD = WS / "work/r23/gate-0213"
SWO = WS / "results/r23/port-0213/switch-gap"
RU = WS / "work/r23/port0211_rules.py"
SWR = WS / "work/r23/switch-gap/switch_rules.py"
MK = GD / "make_configs0213.py"
P_SHA = "639dfb1b7042"
SRC_CONFIGS = ("P028x.json", "P0213x-af2.json", "P0213x.json", "x28h.json")
SINGLE_MAX_TOKENS = 512
RULE_FILES = [GD / "gap-gate0213.sh", GD / "gate0213_rules.py", GD / "make_configs0213.py", GD / "gate-start.sh",
              SWR, RU, WS / "work/r22/g17_rules.py", WS / "work/r23/afetch-gap/afetch_rules.py",
              WS / "work/r23/basalt_rules.py", WS / "work/r23/basalt_fix_rules.py", WS / "work/r23/sampled-qwen/sq.py",
              WS / "work/r23/switch-gap/fixtures_client.py", WS / "bringup/lib/exact7.sh", WS / "bringup/lib/run.sh",
              WS / "bringup/lib/with_server.sh", WS / "bringup/lib/srv.sh", WS / "bringup/lib/guard.py",
              WS / "bringup/lib/kcheck.sh", WS / "bringup/lib/p0_table.py", WS / "bringup/patchtest.sh",
              WS / "work/r22/abarm.sh", WS / "work/r22/pf_yardstick.py", WS / "work/r22/kernel_rule2.py",
              WS / "work/r22/kernel_rule3.py", WS / "work/r22/gap9_verdicts.py", WS / "work/r22/port_gap4.sh",
              WS / "work/r22/basalt-pr90/bp90_client.py", WS / "work/r22/basalt-pr90/bp90_report.py",
              WS / "work/r23/build-port0213.sh"] + [WS / "configs" / n for n in SRC_CONFIGS + ("s028-h.json", "P0213x-single.json")]
REQUIRED = ["switchref", "build_x", "build_stock", "build8", "cfg", "pins", "pins_h", "fence4", "guards", "e7_release", "e7_repeat",
            "e7_v2", "kl2_p213", "kl3_p213", "env_pfy", "startlines_P", "lost_answers", "cont_P", "lossless"]
START_FAIL = ("env_", "fenv_", "line_", "fatal_")     # a start's evidence: FAIL = FAIL (named)
START_VOID = ("foreign_", "void_", "swap_", "rc_")    # the start is left out: INCOMPLETE (named)
STOP_KEYS = ("kstop", "kfail")                        # the kernel-error stop's lines in gates.txt
INFO_KEYS = ["kstop", "e7_vs_p0211", "e7_af2", "e7_af2_stored", "e7_upstream", "logits_vs_p028x", "logits_vs_p0211", "c1_ref",
             "swref_speed", "priority_override", "kcheck_after", "lock_sweep"]
SW_SPEED_ONE_PASS = None    # (filled from the switch gap's folder when it exists: the INFO figure of the decode line)
_M = {}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def ru():
    """port0211_rules.py (it imports g17_rules.py): speed / save / startlines / lost / e7cmp / PINS / KEYS"""
    if "ru" not in _M:
        _M["ru"] = load("port0211_rules_g13", RU)
    return _M["ru"]


def g17():
    return ru().g17


def swr():
    if "swr" not in _M:
        _M["swr"] = load("switch_rules_g13", SWR)
    return _M["swr"]


def mk():
    if "mk" not in _M:
        _M["mk"] = load("make_configs0213_g13", MK)
    return _M["mk"]


def sha(p, n=None):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return h[:n] if n else h


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def read_gates(o):
    g = {}
    p = Path(o) / "gates.txt"
    for line in p.read_text(errors="replace").splitlines() if p.exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        if k:
            g[k] = (s, re.sub(r" \[g13 \d\d-\d\d \d\d:\d\d\]$", "", det))   # the last line of a gate counts
    return g


def is_info(k):
    """a gate that is information only: the single-card start's (*_SG), an INFO run's (info* tags), skips, starts"""
    return k.endswith("_SG") or k.startswith("info") or "_info" in k or k.startswith(("skip_", "start_", "pcie_"))


def read_jsonl(p):
    out = []
    for x in Path(p).read_text(errors="replace").splitlines() if Path(p).exists() else []:
        x = x.strip()
        if x:
            try:
                out.append(json.loads(x))
            except ValueError:
                pass
    return out


# ------------------------------------------------------------------------------------------------ before the gap
def switchref(swdir, sha_now, head_now, cfg_dir=WS / "configs"):
    """(ok, line, info): today's switch gap stands for the parts this gate leaves out (see the docstring)"""
    d = Path(swdir)
    bad, info = [], {}
    rd = lambda n: (d / n).read_text(errors="replace") if (d / n).exists() else ""   # noqa: E731
    v = rd("verdict.txt").strip()
    if v != "SWITCH CHECKS PASS":
        bad.append(f"its verdict is {v!r}, not 'SWITCH CHECKS PASS'")
    res = rd("result.txt").splitlines()
    if not res or not res[0].startswith("DONE"):
        bad.append(f"its result.txt does not start DONE ({(res[0] if res else 'missing')[:80]})")
    m = re.search(r"engines \(B ([0-9a-f]{12}), P ([0-9a-f]{12})\), the port tree at ([0-9a-f]{7,40})", rd("summary.txt"))
    md = re.search(r"\(engine-r23p0213 ([0-9a-f]{12}),", rd("decision.txt"))
    if not m:
        bad.append("its summary.txt records no engine / tree line")
    else:
        info["b_sha"], info["p_sha"], info["head"] = m.group(1), m.group(2), m.group(3)
        if md and md.group(1) != m.group(2):
            bad.append(f"its decision.txt names P {md.group(1)}, its summary {m.group(2)}")
        if m.group(2) != P_SHA:
            bad.append(f"it measured P {m.group(2)}, not {P_SHA}")
        if sha_now != m.group(2):
            bad.append(f"engine-r23p0213/strata is {sha_now} now, the switch gap measured {m.group(2)}")
        if not head_now or not head_now.startswith(m.group(3)):
            bad.append(f"strata-r23p0213 is at {(head_now or '?')[:12]} now, the switch gap at {m.group(3)}")
    if "VERDICT: SWITCH CHECKS PASS" not in rd("decision.txt"):
        bad.append("its decision.txt has no 'VERDICT: SWITCH CHECKS PASS'")
    try:
        shas = json.loads(rd("configs/manifest.json"))["_shas"]
        for n in SRC_CONFIGS:
            p = Path(cfg_dir) / n
            if not p.exists() or sha(p) != shas.get(n):
                bad.append(f"configs/{n} changed since the switch gap ({shas.get(n, '?')[:12]} then)")
    except (ValueError, KeyError, TypeError):
        bad.append("its configs/manifest.json is missing or has no _shas")
    dec = rd("decision.txt")
    info["checks"] = [x for x in dec.splitlines() if re.match(r"^C[1-5] ", x)]
    info["speed"] = next((x for x in dec.splitlines() if x.startswith("INFO screen speed")), "")
    info["result"] = rd("result-line.txt").strip()
    line = (f"the switch gap ({d.name}): {v or '?'}, P {info.get('p_sha', '?')} at {info.get('head', '?')} = the build "
            f"under test, the 4 source configs unchanged; it covers the GPU unit / parity tests, the CPU / server / node "
            f"suites, the served form, web search, the sampled test ({info['result'][:160]})" if not bad else
            "the switch gap's results do not stand for this build: " + "; ".join(bad))
    return not bad, line, info


def cmd_switchref(a):
    ok, line, info = switchref(a.swdir, a.sha, a.head)
    print(("SWITCHREF OK: " if ok else "SWITCHREF FAILED: ") + line)
    gate(a, "PASS" if ok else "FAIL", line[:400])
    if ok and getattr(a, "gates", None):
        with open(a.gates, "a") as f:
            f.write(f"c1_ref INFO {'; '.join(c[:110] for c in info['checks'])[:600]}\n")
            f.write(f"swref_speed INFO {info['speed'][:300]}\n")
    return 0 if ok else 1


def cmd_pins(a):
    c = json.loads(Path(a.config).read_text())
    e = c.get("env", {})
    pins = swr().port_pins()
    keys = ru().KEYS
    bad = [f"{k}={e.get(k, 'unset')} (want {v})" for k, v in pins.items() if e.get(k) != v]
    bad += [f"{k}={c.get(k)!r} (want {v!r})" for k, v in keys.items() if c.get(k) != v]
    line = f"{Path(a.config).name}: " + (f"all {len(pins)} pins and both keys" if not bad else "; ".join(bad))
    print(line + (" -> PASS" if not bad else " -> FAIL"))
    gate(a, "FAIL" if bad else "PASS", line[:300])
    return 0


def cmd_singleplan(a):
    """the single-card start's requests: switch_rules.py fixtures' plan (conv, struct, prose; the standard sampling),
    each cut to SINGLE_MAX_TOKENS"""
    p = json.loads(Path(a.inp).read_text())
    std = swr().STANDARD
    if any(p.get("fields", {}).get(k) != v for k, v in std.items()):
        raise SystemExit(f"the plan's fields {p.get('fields')} are not the standard sampling")
    reqs = []
    for r in p["requests"]:
        r = copy.deepcopy(r)
        r["max_tokens"] = min(r["max_tokens"], SINGLE_MAX_TOKENS)
        reqs.append(r)
    out = {"plan": "v0.2.13 gate: the single-card start (INFO)", "fields": p["fields"], "requests": reqs}
    Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    print(f"single-card plan: {', '.join(f'{r['name']} {r['max_tokens']} tokens' for r in reqs)} -> {a.out}")
    return 0


def single_line(o):
    recs = read_jsonl(Path(o) / "single" / "single.jsonl")
    if not recs:
        return "the single-card start: no request answered (see start_SG / env_SG)"
    dec = [r["decode_tps"] for r in recs if r.get("decode_tps")]
    ok = sum(1 for r in recs if r.get("finish") in ("stop", "length") and not r.get("error"))
    return (f"the single-card start (P0213x-single, the RTX 5080 alone): {ok} of {len(recs)} requests answered; decode "
            + ", ".join(f"{r.get('name')} {r.get('decode_tps')} tok/s ({r.get('completion_tokens')} tokens, {r.get('finish')})"
                        for r in recs)
            + (f"; mean {stt.mean(dec):.1f} tok/s" if dec else ""))


def cmd_single(a):
    line = single_line(a.outdir)
    print(line)
    gate(a, "INFO", line[:400])
    return 0


# ------------------------------------------------------------------------------------------------ the decode line
def decode_passes(o, arm):
    """{pass: (geometric mean over the 9, {workload: decode_tps})} of ARM's complete screen passes (client numbers)"""
    G = g17()
    out = {}
    for k in (1, 2, 3):
        rows = G.screen_rows(o, arm, k, amended=False)
        if all(rows.get(w, {}).get("decode_tps") for w in G.WL9):
            v = {w: rows[w]["decode_tps"] for w in G.WL9}
            out[k] = (G.gm(list(v.values())), v)
    return out


def one_pass_figure(swdir=SWO):
    try:
        b, p = decode_passes(swdir, "B"), decode_passes(swdir, "P")
    except Exception:  # noqa: BLE001 - information only
        return None
    if 1 in b and 1 in p:
        return b[1][0], p[1][0]
    return None


def decode_line(o, swdir=SWO):
    """(verdict, [lines], data) - the docstring's THE DECODE LINE"""
    G = g17()
    b, p = decode_passes(o, "B"), decode_passes(o, "P")
    one = one_pass_figure(swdir)
    ref = (f"; the switch gap's one pass: P {one[1]:.1f} vs B {one[0]:.1f} tok/s ({100 * (one[1] / one[0] - 1):+.1f} %)"
           if one else "")
    if len(b) < 3 or len(p) < 3:
        return "NOT DECIDED", [f"DECODE (Karl 11-10: is the switch gap's -2.5 % real beyond noise?): NOT DECIDED - B {len(b)} "
                               f"/ P {len(p)} complete screen passes of 3{ref}"], {"b": len(b), "p": len(p)}
    gb, gp = [v[0] for v in b.values()], [v[0] for v in p.values()]
    mb, mp = G.gm(gb), G.gm(gp)
    noise = max(G.spread(gb), G.spread(gp))
    d = mp / mb - 1
    v = "REAL LOSS" if d < -noise else "WITHIN NOISE"
    small = " (beyond the noise but within g16's 1 %)" if v == "REAL LOSS" and d >= -0.010 else ""
    lines = [f"DECODE (Karl 11-10: is the switch gap's -2.5 % real beyond noise?): P {100 * d:+.2f} % vs B (B {mb:,.1f}, P "
             f"{mp:,.1f} tok/s, geometric means of 3 passes; noise {100 * noise:.2f} % = the larger arm's pass spread; passes "
             f"B {', '.join(f'{x:.1f}' for x in gb)} / P {', '.join(f'{x:.1f}' for x in gp)}) -> {v}{small}{ref}"]
    per, beyond = [], []
    for w in G.WL9:
        xb, xp = [b[k][1][w] for k in b], [p[k][1][w] for k in p]
        nz = max(G.spread(xb), G.spread(xp))
        dw = stt.mean(xp) / stt.mean(xb) - 1
        per.append(f"{w} {100 * dw:+.1f} % (noise {100 * nz:.1f} %)")
        if abs(dw) > nz:
            beyond.append(f"{w} {100 * dw:+.1f} %")
    lines.append("  (info) decode per workload, P vs B: " + "; ".join(per))
    lines.append("  (info) beyond their own noise: " + (", ".join(beyond) if beyond else "none"))
    if v == "REAL LOSS":
        lines.append("  NEXT (Karl 11-10): find the cause desk-first, the 1.4 % hunt's way (the decode-path changes v0.2.8 -> "
                     "v0.2.13, every new default the pins do not cover), and note any pin for the Qwen4 port")
    return v, lines, {"d": d, "noise": noise, "b": gb, "p": gp, "beyond": beyond}


def cmd_decode(a):
    v, lines, _ = decode_line(a.outdir)
    print("\n".join(lines))
    return 0


# ------------------------------------------------------------------------------------------------ the rules text
def rules_text():
    shas = "\n".join(f"  {p.relative_to(WS)} {sha(p, 16) if p.exists() else 'MISSING'}" for p in RULE_FILES)
    return (__doc__.strip() + "\n\nThe files this gate runs, imports or reads as configs (sha256, first 16 hex, at the freeze; "
            "this file's own sha covers its code, not only this text):\n" + shas + "\n")


def cmd_rules(a):
    t = rules_text()
    Path(a.out).write_text(t)
    print(f"rules frozen: {a.out} sha {hashlib.sha256(t.encode()).hexdigest()[:12]}")
    return 0


# ------------------------------------------------------------------------------------------------ the decision
BP_FIX = (("conv", "decode_tps"), ("struct", "decode_tps"), ("prose", "decode_tps"), ("pp16k", "prompt_tps"),
          ("pp64k", "prompt_tps"))


def gate_lines(o):
    """[(index, key, status, detail)] of gates.txt in file order (every line, not only the last of a gate)"""
    p = Path(o) / "gates.txt"
    out = []
    for i, line in enumerate(p.read_text(errors="replace").splitlines() if p.exists() else []):
        k, _, rest = line.partition(" ")
        st, _, det = rest.partition(" ")
        out.append((i, k, st, det))
    return out


def gate_tag(k):
    """the step a start gate belongs to: fatal_P1 -> P1, env_bpH-decode-1 -> bpH-decode-1, env_p213a_e7 -> e7p213a"""
    t = k.split("_", 1)[1] if "_" in k else k
    return "e7" + t[:-3] if t.endswith("_e7") else t


def stop_scope(o, g):
    """(the first kstop / kfail line, {the steps the stop names}, {gate: its last line}) when kfail is FAIL, else None"""
    if g.get("kfail", ("", ""))[0] != "FAIL":
        return None
    gl = gate_lines(o)
    first = min((i for i, k, _, _ in gl if k in STOP_KEYS), default=None)
    tags = set()
    for _, k, _, det in gl:
        m = re.search(r"during (\S+)", det) if k == "kstop" else re.search(r"after (\S+)", det) if k == "kfail" else None
        if m:
            tags.add(m.group(1).rstrip(".,;)"))
    last = {k: i for i, k, _, _ in gl}
    return first, tags, last


def bp_short(d):
    """[(build, fixture, records)] of the Basalt fixtures with fewer than 3 records (one a pass) on a build"""
    G = g17()
    out = []
    for b in ("M", "H"):
        recs = G.bp90_load(d, b)
        for t, key in BP_FIX:
            n = len(G.bp90_vals(recs, t, key))
            if n < 3:
                out.append((b, t, n))
    return out


def decide(o, swdir=SWO):
    """-> (base, names, lines, decode verdict, result line, json)"""
    o = Path(o)
    R = ru()
    g = read_gates(o)
    s = lambda k: g.get(k, ("MISSING", ""))[0]   # noqa: E731
    out, reasons, missing, flags = [], [], [], []
    rp = o / "rules.txt"
    rsha = hashlib.sha256(rp.read_bytes()).hexdigest()[:12] if rp.exists() else "missing"
    if not rp.exists() or rp.read_text() != rules_text():
        flags.append(f"the rule text (or a file it names) differs from the one frozen at the gap's start (rules.txt {rsha})")
    unmatched = lambda k: k.startswith("e7_") and s(k) == "FAIL" and "slots MATCHED" not in g[k][1]   # noqa: E731
    sc = stop_scope(o, g)
    seen_stop = []      # start gates the kernel-error stop caused or cut: INCOMPLETE (stopped), never FAIL reasons

    def at_stop(k):
        return bool(sc) and k.startswith(START_FAIL + START_VOID) and (
            (sc[0] is not None and sc[2].get(k, -1) >= sc[0]) or gate_tag(k) in sc[1])
    for k in REQUIRED:
        if s(k) == "MISSING":
            missing.append(k)
        elif unmatched(k):
            missing.append(f"{k} (not decided: {g[k][1][:80]} - exact7 compares builds only at MATCHED slots)")
        elif s(k) != "PASS" and at_stop(k):
            seen_stop.append(f"{k} {s(k)}")
        elif s(k) != "PASS":
            reasons.append((k, f"{k}: {s(k)} {g[k][1]}".strip()[:300]))
    for k in sorted(g):
        if is_info(k) or k in REQUIRED:
            continue
        bad = (k.startswith(START_FAIL) and s(k) != "PASS") or (k.startswith(START_VOID) and s(k) == "FAIL")
        if bad and at_stop(k):
            seen_stop.append(f"{k} {s(k)}")
        elif k.startswith(START_FAIL) and s(k) != "PASS":
            reasons.append((k, f"{k}: {g[k][0]} {g[k][1]}"[:300]))
        elif k.startswith(START_VOID) and s(k) == "FAIL":
            missing.append(f"{k} (left out: {g[k][1][:120]})")
    v = s("e7_vs_p028x")
    if v == "MISSING":
        missing.append("e7_vs_p028x")
    elif unmatched("e7_vs_p028x"):
        missing.append(f"e7_vs_p028x (not decided: {g['e7_vs_p028x'][1][:80]} - exact7 compares builds only at MATCHED slots)")
    elif v != "PASS":
        u = s("e7_upstream")
        if u == "MISSING":
            missing.append("e7_upstream (needed: the port is not bit-identical to P028x)")
        elif unmatched("e7_upstream"):
            missing.append(f"e7_upstream (not decided: {g['e7_upstream'][1][:80]} - slots not MATCHED)")
        elif u == "PASS":
            reasons.append(("e7_vs_p028x", "e7_vs_p028x: the port differs from P028x while stock 0.2.8 = stock v0.2.13 "
                                           "(e7_upstream 7/7): our port changed bits"))
        else:
            out.append("exact7 vs P028x: not identical, and upstream itself moved from 0.2.8 to 0.2.13 (e7_upstream) - a "
                       "cross-version difference; the KL rules and the checks decide")
    else:
        out.append("exact7 vs P028x: 7/7 identical (the v0.2.13 port's CLI form with the pins is P028x bit for bit on exact7)")
    stopped = []
    if s("kfail") == "FAIL":
        stopped.append(f"a kernel error / kernel check failure stopped the gap ({g['kfail'][1][:160]}"
                       + (f"; {g['kstop'][1][:100]}" if "kstop" in g else "") + ")"
                       + (f"; seen at the stop (not judged as the port's): {', '.join(seen_stop)}" if seen_stop else ""))
    if s("priority") == "FAIL":
        stopped.append(f"the priority rule stopped the gap ({g['priority'][1][:160]})")
    for k, (s_, d_) in sorted(g.items()):
        if k.startswith("priority_") and k != "priority_override" and s_ == "INFO":
            flags.append(f"the priority check could not read the watch state ({k}): {d_[:120]}")
        if k == "kcheck_after" and s_ != "PASS":
            flags.append(f"the kernel check after the daily came back failed ({d_[:120]})")
    sp_v, sp_l = R.speed(o)
    sv_v, sv_l = R.save(o)
    bp_v, bp_l = g17().bp90_baseline(o / "bp90")
    short = bp_short(o / "bp90") if bp_v != "NOT DECIDED" else []
    if short:   # (every fixture needs its 3 records a build; a FAIL stands only on a fixture that has them all)
        st_ = {t for _, t, _ in short}

        def complete(x):
            for t in ("conv", "struct", "prose"):
                if f"Basalt {t} " in x:
                    return t not in st_
            if "Basalt blend" in x:
                return not ({"conv", "struct", "prose"} & st_)
            return ("16K" in x and "pp16k" not in st_) or ("64K" in x and "pp64k" not in st_)
        genuine = any("-> FAIL" in x and complete(x) for x in bp_l)
        bp_v = "FAIL" if genuine else "NOT DECIDED"
        bp_l = bp_l + ["Basalt: fewer than 3 records (one a pass) on " + ", ".join(
            f"{'B' if b == 'M' else 'P'} ({b}) {t} {n} of 3" for b, t, n in short)
            + (" (a complete fixture FAILs)" if genuine else " -> NOT DECIDED")]
    out += sp_l + sv_l + bp_l
    for name, vv in (("speed screen", sp_v), ("chat-cache save", sv_v), ("Basalt fixtures", bp_v)):
        if vv is None or vv == "NOT JUDGED":
            continue
        if vv == "NOT DECIDED":
            missing.append(name)
        elif vv == "FAIL":
            reasons.append((name, f"{name}: FAIL"))
    dv, dl, dd = decode_line(o, swdir)
    if reasons:
        base = "FAIL"
    elif missing or stopped:
        base = "INCOMPLETE"
    elif sp_v == "BORDERLINE":
        base = "BORDERLINE"
    else:
        base = "PASS"
    names = ([k for k, _ in reasons] if base == "FAIL" else
             (["stopped"] if stopped else []) + [m.split(" (")[0] for m in missing] if base == "INCOMPLETE" else [])
    also = " - and the gap was STOPPED (see the STOPPED line)" if stopped and base == "FAIL" else ""
    head = [f"v0.2.13 PORT BASELINE GATE (work/r23/gate-0213/gap-gate0213.sh; rules gate0213_rules.py, frozen {rsha}): the "
            f"pinned-off port (engine-r23p0213 {P_SHA}) against P028x - CLI forms for exactness / long40, the daily's served "
            "form (B) against the port's (P) for the screen and Basalt; measurements only, nothing switches",
            g17().AMENDMENT_1107 if sv_v is not None else "(the 11-07 amendment did not apply: no screen engine logs)",
            f"VERDICT: BASELINE {base}" + (f" ({', '.join(dict.fromkeys(names))})" if names else "") + also]
    head += [f"STOPPED: {x}; the daily was brought back (see result.txt)" for x in stopped]
    head.append(dl[0])
    body = out + dl[1:]
    body.append(f"BASELINE (the pinned-off v0.2.13 port = P028x): {base}")
    body += [f"  - {r}" for _, r in reasons] + [f"  - not run / not decided / left out: {m}" for m in missing]
    for k in INFO_KEYS:
        if k in g:
            body.append(f"  (info) {k}: {g[k][0]} {g[k][1]}"[:600])
    sg = sorted(k for k in g if k.endswith("_SG"))
    if sg or "skip_SG" in g:
        body.append("  (info) THE SINGLE-CARD FALLBACK (configs/P0213x-single.json; INFO, never a verdict): "
                    + "; ".join(f"{k} {g[k][0]} {g[k][1][:140]}" for k in sg)[:900])
    else:
        body.append("  (info) the single-card fallback start did not run")
    for k in sorted(g):
        if k.startswith("pcie_"):
            body.append(f"  (info) {k}: {g[k][1][:160]}")
        if k.startswith("skip_"):
            body.append(f"  (info) {k}: {g[k][1][:160]}")
    body += [f"FLAG {f}" for f in flags]
    body.append("Taken from the switch gap (switchref), not re-run here: C1 the C++ parity / unit tests, the server test "
                "suite, the node tests and the read-back start; C2 the served outputs against the daily (EXACT); C3 the "
                "sampled test; C4 web search end to end (3 search prompts); C5 the lost-answer guard's count.")
    body.append("NOT COVERED by the switch gap nor by this gate: the live tool-call test (B vs P), the picture / vision "
                "and the chat-cache served-form checks (port0211 ran them).")
    body.append("Nothing switches (8080 stays the daily); a PASS makes r23-port0213 the checked base for the Qwen4 port.")
    dshort = (f"DECODE {dv}" + (f" (P {100 * dd['d']:+.2f} % vs B, noise {100 * dd['noise']:.2f} %)" if "d" in dd else ""))
    rl = f"BASELINE {base}" + (f" ({', '.join(dict.fromkeys(names))})" if names else "") + also + f" | {dshort}"
    res = {"rules_sha": rsha, "baseline": base, "names": names, "reasons": [r for _, r in reasons], "missing": missing,
           "stopped": stopped, "seen_at_the_stop": seen_stop, "speed": sp_v, "save": sv_v, "bp90": bp_v, "decode": {"verdict": dv, **dd},
           "flags": flags, "result_line": rl}
    return base, head + body, dv, rl, res


def cmd_decide(a):
    o = Path(a.outdir)
    base, lines, dv, rl, res = decide(o, Path(a.swdir) if a.swdir else SWO)
    txt = "\n".join(lines) + "\n"
    (o / "decision.txt").write_text(txt)
    (o / "decision.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (o / "verdict.txt").write_text(rl.split(" | ")[0] + "\n" + rl.split(" | ")[1] + "\n")
    (o / "result-line.txt").write_text(rl + "\n")
    if not a.quiet:
        print(txt, end="")
    return 0


# ------------------------------------------------------------------------------------------------ selftest
def selftest(scratch):
    """Stored data only (results/r23/port-0211/gap: the v0.2.11 gate's screen + Basalt, judged PASS under the 11-07
    amendment; results/r22/gap17: a Basalt FAIL; results/r23/port-0213/switch-gap: v0.2.13's real start log, today's
    stored exact7 runs) + synthetic gates; everything written under SCRATCH. No GPU, no engine, no server, no lock."""
    root = Path(scratch)
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    R, G = ru(), g17()
    fails, n = [], [0]
    p211 = WS / "results/r23/port-0211/gap"
    g17d = WS / "results/r22/gap17"

    def check(name, cond, txt=""):
        n[0] += 1
        print(f"{'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)
            print("     " + str(txt).replace("\n", "\n     ")[:2000])

    def quiet(f, *x, **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return f(*x, **kw)

    allpass = {k: "PASS" for k in REQUIRED + ["e7_vs_p028x", "env_B1", "env_P1", "fenv_P1", "line_P1"]}

    def mk_dir(name, gates, screen=p211, bp=(p211, "M", "H"), rules=True):
        d = root / name
        (d / "speed").mkdir(parents=True)
        (d / "bp90").mkdir()
        (d / "summary.txt").write_text("=== 2026-11-10 14:00:00 v0.2.13 BASELINE GATE (selftest)\n")
        if screen:
            for f in (screen / "speed").glob("[BP][123][nar].*"):
                if f.suffix in (".jsonl", ".englog"):
                    shutil.copy(f, d / "speed" / f.name)
        if bp:
            shutil.copy(bp[0] / "bp90" / f"cold-{bp[1]}.jsonl", d / "bp90" / "cold-M.jsonl")
            shutil.copy(bp[0] / "bp90" / f"cold-{bp[2]}.jsonl", d / "bp90" / "cold-H.jsonl")
        det = lambda k, v: (f"exact7 synthetic: {7 if v == 'PASS' else 5}/7, slots MATCHED" if k.startswith("e7_")   # noqa: E731
                            else "synthetic")
        (d / "gates.txt").write_text("".join(f"{k} {v} {det(k, v)} [g13 11-10 14:00]\n" for k, v in gates.items()))
        if rules:
            (d / "rules.txt").write_text(rules_text())
        return d

    def run(d):
        a = argparse.Namespace(outdir=str(d), quiet=True, swdir=str(SWO))
        cmd_decide(a)
        return (d / "verdict.txt").read_text(), (d / "decision.txt").read_text(), json.loads((d / "decision.json").read_text())

    def scale(d, arm, f, passes=(1, 2, 3)):
        for k in passes:
            for x in "nar":
                p = d / "speed" / f"{arm}{k}{x}.jsonl"
                rows = [json.loads(y) for y in p.read_text().splitlines() if y.strip()]
                for r in rows:
                    if r.get("decode_tps"):
                        r["decode_tps"] *= f
                p.write_text("".join(json.dumps(r) + "\n" for r in rows))

    # 1. the v0.2.11 gate's real screen + Basalt (amended: PASS) with every required gate PASS -> BASELINE PASS
    v, t, j = run(mk_dir("real", allpass))
    check("v0.2.11's real screen + Basalt, every gate PASS -> BASELINE PASS (under the 11-07 amendment)",
          v.startswith("BASELINE PASS\n") and "VERDICT: BASELINE PASS" in t and "AMENDMENT 2026-11-07" in t
          and "chat-cache save [11-07 amendment]" in t, t)
    check("... the decode line: P +1.34 % (v0.2.11 was faster) -> WITHIN NOISE, with the per-workload INFO",
          j["decode"]["verdict"] == "WITHIN NOISE" and "P +1.34 % vs B" in t and "(info) decode per workload" in t
          and "DECODE WITHIN NOISE" in v, t)
    check("... the switch gap's one-pass figure is quoted (-2.5 %)", "the switch gap's one pass: P 166.1 vs B 170.4 tok/s (-2.5 %)" in t, t)
    check("... exact7 vs P028x 7/7 line", "7/7 identical (the v0.2.13 port's CLI form" in t, t)
    # 2. P's decode -6 % in every pass (d about -4.7 %, beyond the 2.8 % pass spread v0.2.11's P had) -> REAL LOSS + FAIL;
    # -4 % (d -2.7 %) stays within that noise: WITHIN NOISE, g16 BORDERLINE (the per-workload rule fails R1 there)
    d = mk_dir("slow4", allpass)
    scale(d, "P", 0.96)
    v, t, j = run(d)
    check("P decode -4 % in every pass: d -2.72 % vs noise 2.82 % -> DECODE WITHIN NOISE (g16 decode BORDERLINE)",
          j["decode"]["verdict"] == "WITHIN NOISE" and "speed screen decode: P -2.72 % vs B" in t and "-> BORDERLINE" in t, t)
    d = mk_dir("slow6", allpass)
    scale(d, "P", 0.94)
    v, t, j = run(d)
    check("P decode -6 % in every pass -> DECODE REAL LOSS + BASELINE FAIL (speed screen), the NEXT line",
          j["decode"]["verdict"] == "REAL LOSS" and v.startswith("BASELINE FAIL (speed screen)") and "NEXT (Karl 11-10)" in t, t)
    # 3. one P pass 3.5 % slower -> the pass noise covers it: WITHIN NOISE; g16 between -1 % and -noise -> BORDERLINE
    d = mk_dir("onepass", allpass)
    scale(d, "P", 0.955 / 1.0134, passes=(1,))     # (P was +1.34 % over B: about -4.5 % in pass 1, -1 % in 2 and 3)
    scale(d, "P", 0.99 / 1.0134, passes=(2, 3))
    v, t, j = run(d)
    dd = j["decode"]
    check(f"P one pass -4.5 %, two -1 %: d {100 * dd.get('d', 0):+.2f} %, noise {100 * dd.get('noise', 0):.2f} % -> WITHIN NOISE",
          dd["verdict"] == "WITHIN NOISE" and dd["d"] < -0.010 and dd["d"] >= -dd["noise"], t)
    check("... and the BASELINE is BORDERLINE (g16: between -1 % and -noise), unless the per-workload rule fails it",
          v.startswith("BASELINE BORDERLINE") or ("per-workload no-loss (P vs B) [11-07 amendment: prompt = engine prompt ms "
                                                  "minus the chat-cache save] FAILS" in t and v.startswith("BASELINE FAIL")), t)
    # 4. a left-out P pass (its files gone) -> decode NOT DECIDED, INCOMPLETE (speed screen), foreign named
    d = mk_dir("void", dict(allpass, foreign_P2="FAIL"))
    for f in (d / "speed").glob("P2*"):
        f.unlink()
    v, t, j = run(d)
    check("a left-out P pass (foreign_P2) -> DECODE NOT DECIDED, BASELINE INCOMPLETE naming foreign_P2 and the screen",
          j["decode"]["verdict"] == "NOT DECIDED" and v.startswith("BASELINE INCOMPLETE") and "foreign_P2" in v
          and "speed screen" in v, t)
    # 5. a missing required gate, an env / fatal / line FAIL, an INFO arm's FAIL
    g = dict(allpass)
    g.pop("kl3_p213")
    v, t, j = run(mk_dir("missing", g))
    check("missing kl3_p213 -> INCOMPLETE (kl3_p213)", v.startswith("BASELINE INCOMPLETE (kl3_p213)"), t)
    v, t, j = run(mk_dir("envfail", dict(allpass, env_P2="FAIL", **{"fatal_bpH-decode-1": "FAIL", "line_B3": "FAIL"})))
    check("env_P2 / fatal_bpH-decode-1 / line_B3 FAIL -> FAIL, each named",
          v.startswith("BASELINE FAIL") and all(x in v for x in ("env_P2", "fatal_bpH-decode-1", "line_B3")), t)
    v, t, j = run(mk_dir("infofail", dict(allpass, env_SG="FAIL", fatal_SG="FAIL", infoenv_da2_e7="FAIL",
                                          foreign_infoda2="FAIL", skip_SG="INFO")))
    check("the single-card start's and the INFO exact7's FAILs stay INFO: PASS, listed under THE SINGLE-CARD FALLBACK",
          v.startswith("BASELINE PASS") and "THE SINGLE-CARD FALLBACK" in t and "env_SG FAIL" in t, t)
    # 6. exact7 vs P028x: upstream moved / did not / not run
    v, t, j = run(mk_dir("upmoved", dict(allpass, e7_vs_p028x="FAIL", e7_upstream="FAIL")))
    check("e7 differs, upstream moved too -> cross-version INFO, PASS", v.startswith("BASELINE PASS") and "upstream itself moved" in t, t)
    v, t, j = run(mk_dir("ourmove", dict(allpass, e7_vs_p028x="FAIL", e7_upstream="PASS")))
    check("e7 differs, upstream did not move -> FAIL (e7_vs_p028x)", v.startswith("BASELINE FAIL (e7_vs_p028x)") and "our port changed bits" in t, t)
    v, t, j = run(mk_dir("noup", dict(allpass, e7_vs_p028x="FAIL")))
    check("e7 differs, no e7_upstream -> INCOMPLETE", v.startswith("BASELINE INCOMPLETE") and "e7_upstream (needed" in t, t)
    v, t, j = run(mk_dir("slotsdiffer", dict(allpass, e7_v2="FAIL", e7_vs_p028x="FAIL")))
    g_ = mk_dir("slotsdiffer2", dict(allpass))
    (g_ / "gates.txt").write_text((g_ / "gates.txt").read_text() + "e7_v2 FAIL exact7 x: 7/7, slots DIFFER [g13 11-10 14:00]\n"
                                  "e7_vs_p028x FAIL exact7 y: 3/7, slots DIFFER [g13 11-10 14:00]\n")
    v, t, j = run(g_)
    check("exact7 pairs at unmatched slots (e7_v2 7/7 DIFFER, e7_vs_p028x 3/7 DIFFER) -> INCOMPLETE, not FAIL",
          v.startswith("BASELINE INCOMPLETE (e7_v2, e7_vs_p028x)") and "MATCHED slots" in t, t)
    # 7. Basalt: gap 17's real fixtures (struct / blend below M) -> FAIL (Basalt fixtures)
    v, t, j = run(mk_dir("bpfail", allpass, bp=(g17d, "M", "H")))
    check("gap 17's Basalt data (H below M on struct and the blend) -> FAIL (Basalt fixtures)",
          v.startswith("BASELINE FAIL (Basalt fixtures)") and "Basalt struct decode" in t, t)
    d = mk_dir("bpmiss", allpass)
    (d / "bp90/cold-H.jsonl").write_text("".join(x + "\n" for x in (d / "bp90/cold-H.jsonl").read_text().splitlines()
                                                 if '"pp64k"' not in x))
    v, t, j = run(d)
    check("Basalt: H without its 64K records -> NOT DECIDED -> INCOMPLETE (Basalt fixtures), not FAIL",
          v.startswith("BASELINE INCOMPLETE (Basalt fixtures)") and "Basalt 64K prompt: missing" in t, t)
    # 8. a kernel error stop / the priority stop -> INCOMPLETE with the STOPPED line; a changed rules.txt is flagged
    v, t, j = run(mk_dir("kfail", dict(allpass, kfail="FAIL")))
    check("kfail FAIL (everything else PASS) -> INCOMPLETE (stopped), the STOPPED line",
          v.startswith("BASELINE INCOMPLETE (stopped)") and "STOPPED: a kernel error" in t, t)
    # 8b. the kernel-error stop: start gates from the stop on, or of the step it names, are "seen at the stop" (INCOMPLETE,
    # the stop ranked first); a start gate that FAILed before the stop on another step stays a FAIL
    def stopdir(name, extra):
        d_ = mk_dir(name, allpass)
        (d_ / "gates.txt").write_text((d_ / "gates.txt").read_text() + "".join(x + "\n" for x in extra))
        return d_
    v, t, j = run(stopdir("stopP1", ["kstop INFO a kernel-error marker seen during P1 [g13 11-10 14:01:02]",
                                     "kfail FAIL a kernel error is recorded (kwatch not cleared) [g13 11-10 14:01]",
                                     "fatal_P1 FAIL 1 line(s): the engine had stopped [g13 11-10 14:01]",
                                     "rc_P1 FAIL the client chain wrote no rc line [g13 11-10 14:01]",
                                     "kfail FAIL after P1 [g13 11-10 14:01]"]))
    check("a kernel error during P1, its kill leaving fatal_P1 / rc_P1 -> INCOMPLETE (stopped first), not FAIL; named as "
          "seen at the stop", v.startswith("BASELINE INCOMPLETE (stopped") and "fatal_P1" not in j["reasons"].__str__()
          and "seen at the stop (not judged as the port's): fatal_P1 FAIL, rc_P1 FAIL" in t
          and t.index("STOPPED:") < t.index("DECODE ("), t)
    v, t, j = run(stopdir("stopkc", ["fatal_P2 FAIL 1 line(s): fatal GPU error [g13 11-10 14:01]",
                                     "kfail FAIL after P2 [g13 11-10 14:01]"]))
    check("a kernel check failing after P2 (no marker line) with P2's fatal line written before it -> P2's gate is the "
          "stopped step's: INCOMPLETE (stopped)", v.startswith("BASELINE INCOMPLETE (stopped") and "fatal_P2 FAIL" in t, t)
    v, t, j = run(stopdir("stopold", ["fatal_B1 FAIL 1 line(s): fatal GPU error [g13 11-10 13:50]",
                                      "kstop INFO a kernel-error marker seen during P3 [g13 11-10 14:01:02]",
                                      "fatal_P3 FAIL 1 line(s): the engine had stopped [g13 11-10 14:01]",
                                      "kfail FAIL after P3 [g13 11-10 14:01]"]))
    check("a fatal line on B1 BEFORE a stop during P3 stays a FAIL (fatal_B1), the stop noted; P3's is seen at the stop",
          v.startswith("BASELINE FAIL (fatal_B1) - and the gap was STOPPED") and "seen at the stop (not judged as the port's): "
          "fatal_P3 FAIL" in t, t)
    # 8c. the swap rule and the client chain's rc: the start is left out -> INCOMPLETE (named)
    v, t, j = run(mk_dir("swap", dict(allpass, swap_P2="FAIL", swap_e7p213a="FAIL", **{"rc_bpH-pp16k-2": "FAIL"})))
    check("swap_P2 / swap_e7p213a / rc_bpH-pp16k-2 FAIL -> INCOMPLETE naming each, not FAIL",
          v.startswith("BASELINE INCOMPLETE") and all(x in v for x in ("swap_P2", "swap_e7p213a", "rc_bpH-pp16k-2")), t)
    # 8d. Basalt: a fixture with 2 of its 3 records on a build -> NOT DECIDED -> INCOMPLETE (Basalt fixtures), named
    d = mk_dir("bpshort", allpass)
    rows = [json.loads(x) for x in (d / "bp90/cold-H.jsonl").read_text().splitlines() if x.strip()]
    (d / "bp90/cold-H.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows
                                                 if not (r["test"] == "pp16k" and r["pass"] == 2)))
    v, t, j = run(d)
    check("Basalt: P (H) pp16k 2 of 3 records -> INCOMPLETE (Basalt fixtures), the short fixture named",
          v.startswith("BASELINE INCOMPLETE (Basalt fixtures)") and "P (H) pp16k 2 of 3 -> NOT DECIDED" in t, t)
    # 8e. the coverage text and fence4
    v, t, j = run(mk_dir("cover", allpass))
    check("the decision says what the switch gap covered (C1-C5) and that the tool-call / vision / chat-cache checks are "
          "NOT COVERED", "C4 web search end to end (3 search prompts)" in t and "NOT COVERED by the switch gap nor by this "
          "gate: the live tool-call test (B vs P), the picture / vision and the chat-cache served-form checks" in t, t)
    g = dict(allpass)
    g.pop("fence4")
    v, t, j = run(mk_dir("nofence", g))
    check("fence4 missing -> INCOMPLETE (fence4)", v.startswith("BASELINE INCOMPLETE (fence4)"), t)
    d = mk_dir("rules", allpass)
    (d / "rules.txt").write_text("edited\n")
    v, t, j = run(d)
    check("a rules.txt that differs from the rules now -> FLAG", "FLAG the rule text" in t, t)
    # 9. switchref on the real switch gap: PASS with today's engine / head; a wrong sha, head, verdict, config
    import subprocess
    h = subprocess.run(["git", "-C", str(WS / "strata-r23p0213"), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    s_now = sha(WS / "engine-r23p0213/strata", 12)
    ok, line, info = switchref(SWO, s_now, h)
    check(f"switchref on the real switch gap with engine {s_now} at {h[:9]} -> PASS", ok and len(info["checks"]) == 5, line)
    check("switchref: a different engine sha -> FAIL", not switchref(SWO, "000000000000", h)[0])
    check("switchref: another head -> FAIL", not switchref(SWO, s_now, "0123456789abcdef")[0])
    sd = root / "swcopy"
    sd.mkdir()
    for f in ("verdict.txt", "result.txt", "summary.txt", "decision.txt", "result-line.txt"):
        shutil.copy(SWO / f, sd / f)
    (sd / "configs").mkdir()
    shutil.copy(SWO / "configs/manifest.json", sd / "configs/manifest.json")
    check("switchref on a copy -> PASS", switchref(sd, s_now, h)[0])
    (sd / "verdict.txt").write_text("INCOMPLETE (C4 NOT RUN)\n")
    check("switchref: a switch gap that did not PASS -> FAIL", not switchref(sd, s_now, h)[0])
    shutil.copy(SWO / "verdict.txt", sd / "verdict.txt")
    m = json.loads((sd / "configs/manifest.json").read_text())
    m["_shas"]["P0213x.json"] = "0" * 64
    (sd / "configs/manifest.json").write_text(json.dumps(m))
    check("switchref: a source config changed since the switch gap -> FAIL", not switchref(sd, s_now, h)[0])
    # 10. the pins on the real configs; startlines on v0.2.13's real start log; lost
    gf = root / "g.txt"
    for cfgn, want in (("P0213x.json", "PASS"), ("P0213x-af2.json", "PASS"), ("P0211x-h.json", "FAIL"), ("x28h.json", "FAIL")):
        quiet(cmd_pins, argparse.Namespace(config=str(WS / "configs" / cfgn), gate="p", gates=str(gf)))
        last = gf.read_text().splitlines()[-1].split()[1]
        check(f"pins {cfgn} -> {want}", last == want, gf.read_text().splitlines()[-1])
    sl = SWO / "speed/P1.startlog"
    quiet(R.startlines, argparse.Namespace(startlog=str(sl), serverlog=[], gate="s", gates=str(gf)))
    check("port0211's startlines on v0.2.13's real start log (the switch gap's P1) -> PASS",
          gf.read_text().splitlines()[-1].split()[1] == "PASS", gf.read_text().splitlines()[-1])
    # 11. the stored exact7 pair (the port with fetch=2 vs the daily, both stored 11-10 / 11-09): INFO 7/7 MATCHED
    quiet(R.e7cmp, argparse.Namespace(label="r23sw11101048-P", ref="r23aa11091954-S2", info=True, gate="e", gates=str(gf)))
    last = gf.read_text().splitlines()[-1]
    check("e7cmp r23sw11101048-P vs r23aa11091954-S2 (stored) -> INFO 7/7, slots MATCHED",
          last.startswith("e INFO exact7 r23sw11101048-P vs r23aa11091954-S2: 7/7, slots MATCHED"), last)
    # 12. the single-card plan and line
    sp = root / "fx-plan.json"
    sp.write_text(json.dumps({"plan": "C5 fixtures", "fields": dict(swr().FIELDS), "requests": [
        {"name": nm, "messages": [{"role": "user", "content": nm}], "max_tokens": mx, "thinking": False, "seed": 7300001 + i,
         "expect_prompt_tokens": 38} for i, (nm, mx) in enumerate((("conv", 1200), ("struct", 8192), ("prose", 1200)))]}))
    quiet(cmd_singleplan, argparse.Namespace(inp=str(sp), out=str(root / "sg-plan.json")))
    q = json.loads((root / "sg-plan.json").read_text())
    check("singleplan: 3 requests at 512 tokens, the standard sampling kept",
          [r["max_tokens"] for r in q["requests"]] == [512, 512, 512] and q["fields"]["temperature"] == 1.0
          and q["fields"]["min_p"] == 0.05, q)
    bad = json.loads(sp.read_text())
    bad["fields"]["temperature"] = 0.6
    (root / "bad-plan.json").write_text(json.dumps(bad))
    try:
        quiet(cmd_singleplan, argparse.Namespace(inp=str(root / "bad-plan.json"), out=str(root / "x.json")))
        check("singleplan refuses a plan at T 0.6", False)
    except SystemExit:
        check("singleplan refuses a plan at T 0.6", True)
    (root / "sgo" / "single").mkdir(parents=True)
    (root / "sgo/single/single.jsonl").write_text("".join(json.dumps({"name": nm, "decode_tps": x, "completion_tokens": 512,
                                                                      "finish": "length"}) + "\n"
                                                          for nm, x in (("conv", 101.0), ("struct", 120.0), ("prose", 99.0))))
    check("the single-card INFO line", "3 of 3 requests answered" in single_line(root / "sgo") and "mean 106.7 tok/s"
          in single_line(root / "sgo"), single_line(root / "sgo"))
    # 13. the configs (make_configs0213.py make / check into SCRATCH; no engine sha read) and a tampered OFF
    cd = root / "configs"
    quiet(mk().cmd_make, argparse.Namespace(outdir=str(cd), log_dir=str(root / "logs"), no_sha=True, gate="c", gates=str(gf)))
    check("make_configs0213.py make + check -> PASS", gf.read_text().splitlines()[-1].split()[1] == "PASS",
          gf.read_text().splitlines()[-1])
    c = json.loads((cd / "OFF.json").read_text())
    c["env"]["STRATA_GR_FORK"] = "1"
    (cd / "OFF.json").write_text(json.dumps(c))
    quiet(mk().cmd_check, argparse.Namespace(outdir=str(cd), no_sha=True, gate="c", gates=str(gf)))
    check("a tampered OFF.json (GR_FORK back on) -> CONFIG CHECK FAILED", gf.read_text().splitlines()[-1].split()[1] == "FAIL",
          gf.read_text().splitlines()[-1])
    # 14. the frozen rules carry the decode rule and the files' shas
    rt = rules_text()
    check("rules.txt: the decode rule's words and the driver's sha line", "REAL LOSS     d < -noise" in rt
          and "work/r23/gate-0213/gap-gate0213.sh " in rt and "work/r23/switch-gap/switch_rules.py " in rt, rt[-600:])
    print(f"gate0213 selftest: {n[0]} checks, {len(fails)} failure(s)")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name, *pos):
        p = sp.add_parser(name)
        for x in pos:
            p.add_argument(x)
        p.add_argument("--gate")
        p.add_argument("--gates")
        return p
    p = sub("switchref", "swdir")
    p.add_argument("--sha", required=True)
    p.add_argument("--head", required=True)
    sub("pins", "config")
    p = sp.add_parser("singleplan")
    p.add_argument("inp")
    p.add_argument("out")
    sub("single", "outdir")
    sp.add_parser("decode").add_argument("outdir")
    sp.add_parser("rules").add_argument("out")
    p = sp.add_parser("decide")
    p.add_argument("outdir")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--swdir")
    sp.add_parser("selftest").add_argument("scratch")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest(a.scratch)
    return {"switchref": cmd_switchref, "pins": cmd_pins, "singleplan": cmd_singleplan, "single": cmd_single,
            "decode": cmd_decode, "rules": cmd_rules, "decide": cmd_decide}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
