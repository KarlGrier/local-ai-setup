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
# The save line's rule (save_rule), with the stored band PARK_REF_1107 from the 872 stored r22/r23 saves (only the
# 1238 MiB save has two levels, 102-113 / 123-137 ms):
#   - Save index: each save divided by the stored median of its level, over the sizes whose levels are 20 ms or more;
#     the geometric mean per pass, then over the passes.
#   - FAIL when the arm's index is above the base's by more than the larger pass spread (at least 2 %), or when the
#     arm has saves above the stored band (z > 6 over the size's top level) in 2 or more passes and more of them than
#     the base. The level mix per arm is INFO.
#   - A size with no stored band is compared with the base arm's median in that screen. A shift there is NOT DECIDED,
#     because a real slowdown and a two-level draw cannot be told apart without the band.
"""g17_rules.py - gap 17 (the Strata v0.2.10 port, Karl 11-02 "approved as written", results/PORT-V0210-PLAN.md):
the decision rules, written down BEFORE the gap ran (11-03), in g16_rules.py's form. NOTHING SWITCHES (Karl 11-02: the
served build stays P028x until item 7 is done): gap 17 is a test with its gates and pricing. A switch that passes here is
a candidate for after item 7, and the switch itself is Karl's call then.

Arms (configs/, made by results/r22/gap17-prep/scratch/make_configs17.py): B = x28h (P028x's test form, engine-r22p028x),
P = P0210x-h (the port with the 14 new-default pins, our switches on), and on top of P one gated switch each:
L = P0210x-h-L12 (lookup windows up to 12), F = P0210x-h-pf133 (GR_V3_PF=133 with GR_FORK=1), R = P0210x-h-hcr
(PF_HC_REGION=1), G = P0210x-h-gdn (GDN_TC=1 + GDN_CONVL2=2), T = P0210x-h-gdntc (GDN_TC alone), V = P0210x-h-gdncv
(GDN_CONVL2 alone). Basalt's fixtures keep gap 16's file names: cold-M = B, cold-H = P, cold-G / -T / -V. Part B's twins: P0210t-* (engine-r22p0210m) and s0210t-hnospec (engine-r22s0210t).

THE BASELINE - "the pinned-off port = P028x" (every item required; INFO only where it says so):
  builds    build_x (engine-r22p0210 = the built port: SHA256 file matches, SOURCE names the head gap 17 was written for),
            build_tests, build_stock (plain v0.2.10), build8 (every configure log: "windows hold up to 8 rows")
  pins      the 14 pins of results/r22/port-0210-review.md section 0 in P0210x.json and P0210x-h.json, exact values
  tests     ours (patch_guard_test, cost_gate_test, draft_cum_test) rc 0; v2_unit (prefill_fused_iq_test --v2) rc 0;
            sampler_tests (upstream's spec_prob_test, gated_proposal_test, spec_verify_parity, spec_proposal_parity) rc 0;
            servetests (strata-r22p0210/serve, unittest discover): failures only in KNOWN_SERVE_FAILS (test_hip_ordinal
            reads this PC's KFD iGPU; failed on stock 0.2.7 / 0.2.8 too); fence4 (port-0210.md item 7: a four-backtick
            fence holding a three-backtick example and a </think> stays reasoning until the outer fence closes)
  guards    "strata patch guards: 7 checked, 0 off" in the port's exact7 run
  exact7    at pin 2500, slots MATCHED: e7_repeat (P twice, 7/7); e7_release (P0210x-h-off = s0210-h, 7/7: "patched, every
            switch off = the release", port-0210.md: the first check); e7_v2 (v2 on = off, 7/7); e7_vs_p028x (P = x28h):
            7/7 = bit-identical to P028x. Not 7/7: the diagnostic e7_upstream (stock 0.2.8 = stock 0.2.10, both pinned)
            decides - upstream moved too (not 7/7) -> INFO (a cross-version difference as gaps 15/16 had; the KL rules and
            checks decide); upstream did not move (7/7) -> FAIL (our port changed bits where upstream did not)
  KL        kl2_p210 + kl3_p210: kernel_rule2.py AND kernel_rule3.py (with the NLL check) on pf_yardstick long40 against
            gap 8's references (ref; rounding references unfused, cpushare); logits_vs_p028x (P vs gap 16's x28h files)
            is INFO
  start     startlines_P: the doorbell Q8_K, exact-sampling, cumulative-draft, cost-gate and v2 lines present; none of
            "short of GPU memory", "PCIe share: start", "--lookup-max-t", "no VRAM for the", "fatal GPU error", "drafting:
            DFlash2"; every baseline arm's env check passed (env_* gates of B, P, bpM, bpH, tc, rt, sp: the engine
            process found by /proc/PID/exe has the config's env exactly, on v0.2.10 no unpinned new default set behind
            it, STRATA_ROUTE_TAIL_SKIP=0, 2 GPUs, --kv-resident 32768 last); no fatal_* gate (a sticky CUDA error ends
            the v0.2.10 engine and the server restarts it: such an arm is void)
  cont_P    the answer_room continuations in P's screen requests: >= 1, all resumed (read <= 64 tokens)
  served    chatcache (ALL PASS) and vision (2 answers) on P0210x-RTpin-vision
  toolcalls the live tool-call test, P vs B: P's responses with a spurious call <= B's, with a lost call <= B's, no errors
  lossless  bringup/patchtest.sh lossless on P0210x-h with P's engine log
  speed     the 9-workload screen, 3 passes in turned order (client clock): per pass the geometric mean over the 9 of
            decode and of prompt tok/s; an arm = the geometric mean of its passes; noise = the larger arm's pass spread.
            P >= B - 1.0 % on decode and on prompt and no workload's prompt (mean of its passes) more than 3 % below B's
            -> PASS; between -1.0 % and -noise -> BORDERLINE; below -noise -> FAIL (g16's rule)
  bp90      Basalt's community-1 fixtures, cold, 3 passes, H (= P) vs M (= B): each decode fixture (conv, struct,
            prose) >= M - that fixture's spread (the larger build's); the token-weighted blend >= M - 1.0 %; 16K and 64K
            prompt >= M - 1.0 % (g16's rule; Karl's 10-30 long-prompt exception was for P028x vs P021m and is NOT carried)
  part B    build_twin; chk2_p210 (check (2), speculation off, the twin's own 1-token-window reference: p >= 0.05 and
            nothing outside the allowed set); chk1_p210_ess + chk2_p210_ess (the speculative path). INFO: chk2diag_p210
            (the 3-token reference), hashpair_*, chk2_s210 (stock v0.2.10's own check (2), as s28t in gap 16).
  BASELINE = PASS when all of it holds; BORDERLINE when only the speed screen is borderline; INCOMPLETE when a part
  was not run (or its twin could not be built); FAIL otherwise.

THE GATED SWITCHES (each against P, the same build; reported with the baseline's verdict beside it):
  (0) GDN_TC + GDN_CONVL2 as ONE stack (G; Karl 11-03): kl2_gdn + kl3_gdn PASS (the full KL rule); priced on the cold
      16K / 64K prompts (bp90 pp16k / pp64k, 3 passes in turned order, G vs H) and on the 9-workload screen (3 passes,
      G vs P): change = mean G / mean H - 1, noise = the larger build's spread. CANDIDATE = KL PASS, neither long prompt
      below -noise, at least one above +max(noise, 1.0 %), AND the per-workload no-loss condition (below) on the screen;
      NO GAIN = KL PASS without that; FAIL = a KL rule fails. G vs M (P028x) is reported (the long-prompt cost of 10-30).
      Each path alone (T, V): the stack passes KL -> each is priced alone, SPEED ONLY (no KL), on the same 16K / 64K
      prompts and the screen, by the same gain rule against P -> ADDS (CANDIDATE) or ADDS NOTHING (it can stay off);
      the stack fails KL -> each path is KL-gated alone (kl2_gdntc / kl3_gdntc, kl2_gdncv / kl3_gdncv) and priced only
      if it passes.
  (1) lookup windows up to 12 (L):
      exactness  lookup_e7: the 7 exact7 items through the CLI with --suffix-draft 3 (the served default), windows on
                 (--lookup-max-t 12) vs off (0), the same pin and flags: the 5 greedy items must be identical and the on
                 runs must have used windows of 9+ rows (else UNEXERCISED -> NOT DECIDED); the 2 sampled items are
                 reported (with exact speculative sampling a different proposal draws differently: not comparable).
                 Greedy items DIFFER -> the control pair (the same with STRATA_GR_FORK=0) decides: the control differs
                 too -> WINDOW-VARIANT (the engine is not window-invariant, gap 14; not a fork defect) and the
                 distribution checks decide alone; the control is identical -> FAIL (the fork's 12-row path).
      start      startlines_L: "--lookup-max-t 12: MTP windows up to 7 tokens" present; no "no VRAM for the N-token
                 window graph" line in any L engine log (VRAM against the 713 MiB reserve)
      cont_L     as cont_P
      distrib.   chk1_p210_essL + chk2_p210_essL (part B; arith-j3: windows <= 8 at the tie, so this checks the 12-row
                 default's machinery, not a 12-row window's draws - see GAP17-README.md, "not writable yet")
      speed      no loss on the 9 workloads: decode and prompt >= P - noise (g18's rule)
      price      E1-rewrite (prompts/edit.json's frozen file rewrite, thinking on, medium): decode change vs P, noise =
                 the larger arm's E1 spread; GAIN = above +max(noise, 2.0 %) AND the per-workload no-loss condition (below).
                 E2 (thinking off), A-edit, B-write reported.
      CANDIDATE = everything above holds + GAIN; NO GAIN = it holds without the gain; FAIL / NOT DECIDED otherwise.
  PER-WORKLOAD NO-LOSS (Karl 11-03): a GDN or lookup-window gain only counts if no workload of the 9-workload screen
      gets slower beyond the noise: per workload, decode and prompt tok/s each, the arm's pass mean >= the base's (P's)
      pass mean x (1 - the larger of the two arms' pass-to-pass spreads for that workload and number, max / min - 1).
  (2) GR_V3_PF=133 with GR_FORK=1 (F): e7_pf133 7/7 MATCHED + no loss on the screen (3 passes) -> IDENTITY CONFIRMED
      (FAIL otherwise; only then would Karl's fork-off arms be considered).
  (3) PF_HC_REGION=1 (R): e7_hcr 7/7 MATCHED + hcr_logits (pf_yardstick long40, 0 of 40 first-token logit files differ)
      + one quick screen pass with no loss against P's mean (noise = P's spread) -> PASS.

Subcommands (the gap script calls them; decide writes OUTDIR/decision.txt):
  envcheck EXE CONFIG [--ngpu 2] [--pins] [--gate NAME --gates FILE]   the running engine's environment (inside
                                        with_server.sh; --pins: also no new-default pin set behind the config)
  pins CONFIG [--gate --gates]          the 14 pins in a config
  startlines KIND STARTLOG [SERVERLOG...] [--gate --gates]   KIND base | lookup
  e7gate SUMMARY LABEL [--gate --gates] [--info]   exact7's "N/7" and slots line from the summary
  e7pair ON OFF [--gate --gates] [--control]       the lookup pair (bringup/out/logs/prof/<label>-<item>.out)
  servetests FILE / fence4 TREE / chk2 FILE [--info] / chk1 FILE / toolcalls M.jsonl X.jsonl   [--gate --gates]
  decide OUTDIR                          the verdicts; exit 0 = the baseline PASSES
"""
import argparse
import json
import math
import os
import re
import statistics as st
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
PROF = WS / "bringup/out/logs/prof"
Z = 1.959964 + 0.841621
Z95 = 1.959964
PINS = {   # results/r22/port-0210-review.md section 0 (Karl 11-02: the port applies them)
    "STRATA_LOOKUP_MAX_T": "0", "STRATA_GDN_TC": "0", "STRATA_GDN_CONVL2": "0", "STRATA_GR_V3_PF": "0", "STRATA_GR_R2": "0",
    "STRATA_SMALL_UNR": "0", "STRATA_QSA_FUSE_NR": "0", "STRATA_IL_PAD": "0", "STRATA_DF_PDL": "0",
    "STRATA_PCIE_START": "old", "STRATA_ARENA_RAM_FALLBACK": "0", "STRATA_MTP_KEEP": "1", "STRATA_SPILL_OFF": "1",
    "STRATA_PENALTY_PROMPT": "1"}
KNOWN_SERVE_FAILS = {"test_hip_ordinal"}
WL9 = ("W1-think", "W2-code", "W3-research", "A-edit", "B-write", "R1-verify20k", "R2-report54k", "R3-extract5k",
       "R4-agent33k")
ITEMS = ("x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k")
GREEDY = tuple(i for i in ITEMS if i.startswith("x-"))
BASE_PRESENT = ["the doorbell writes the CPU pool's Q8_K rows", "EXACT speculative sampling on",
                "cumulative draft length ON", "the cost gate prices draft steps", "prompt experts: v2 kernels"]
BASE_ABSENT = ["short of GPU memory", "PCIe share: start", "--lookup-max-t", "no VRAM for the", "fatal GPU error",
               "drafting: DFlash2"]
LOOKUP_PRESENT = ["--lookup-max-t 12: MTP windows up to 7 tokens"]
# the switch arms' env / fatal gates (L1-3, F1-3, R2 screens; bpG Basalt runs; spessL the lookup ess arm) are judged
# with their switch, not with the baseline
SWITCH_ENV_RE = r"env_(L\d|F\d|R\d|G\d|T\d|V\d|bpG|bpT|bpV|spessL)"
SWITCH_FATAL_RE = r"fatal_(L\d|F\d|R\d|G\d|T\d|V\d|bpG|bpT|bpV|spessL)"


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def gm(v):
    return math.exp(sum(math.log(x) for x in v) / len(v))


def spread(v):
    return max(v) / min(v) - 1 if len(v) > 1 else 0.0


# ------------------------------------------------------------------------------------------------ env and start lines
def envcheck(a):
    cfg = json.loads(Path(a.config).read_text())
    want = cfg.get("env", {})
    exe = os.path.realpath(a.exe)
    procs = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            if os.readlink(d / "exe") != exe:
                continue
            env = dict(x.split("=", 1) for x in (d / "environ").read_bytes().decode("utf-8", "replace").split("\0") if "=" in x)
            argv = (d / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        procs.append((d.name, env, argv))
    if not procs:
        print(f"ENV CHECK FAILED: no running engine {exe}")
        gate(a, "FAIL", f"no running engine {exe}")
        return 1
    bad_all = []
    for pid, env, argv in procs:
        bad = [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]
        if a.pins:
            bad += [f"{k}={env[k]} set behind the config" for k in PINS if k not in want and k in env]
        if env.get("STRATA_ROUTE_TAIL_SKIP") != "0":
            bad.append(f"STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}")
        n = len([x for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
        if n != a.ngpu:
            bad.append(f"{n} GPU(s) in CUDA_VISIBLE_DEVICES (want {a.ngpu})")
        kv = [argv[i + 1] for i, x in enumerate(argv[:-1]) if x == "--kv-resident"]
        if "--kv-resident" in cfg.get("user_args", []) and (not kv or kv[-1] != "32768"):
            bad.append(f"--kv-resident {kv[-1] if kv else 'missing'} (want 32768, user_args)")
        print(f"engine pid {pid}: {len(want)} config env keys checked, STRATA_ROUTE_TAIL_SKIP="
              f"{env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}, {n} GPU(s), --kv-resident {kv[-1] if kv else '-'}"
              + (f"; MISMATCH {', '.join(bad)}" if bad else ""))
        bad_all += bad
    if bad_all:
        print("ENV CHECK FAILED - this arm is not measured")
        gate(a, "FAIL", "; ".join(bad_all)[:300])
        return 1
    print("ENV CHECK OK")
    gate(a, "PASS", f"{len(procs)} engine process(es), {len(want)} env keys as configured")
    return 0


def pins(a):
    e = json.loads(Path(a.config).read_text()).get("env", {})
    bad = [f"{k}={e.get(k, 'unset')} (want {v})" for k, v in PINS.items() if e.get(k) != v]
    line = (f"{Path(a.config).name}: " + ("all 14 pins as section 0" if not bad else "; ".join(bad)))
    print(line + (" -> PASS" if not bad else " -> FAIL"))
    gate(a, "FAIL" if bad else "PASS", line)
    return 0


def startlines(a):
    txt = ""
    for f in [a.startlog] + list(a.serverlog or []):
        try:
            txt += Path(f).read_text(errors="replace")
        except OSError:
            pass
    want = BASE_PRESENT + (LOOKUP_PRESENT if a.kind == "lookup" else [])
    absent = [x for x in BASE_ABSENT if not (a.kind == "lookup" and x == "--lookup-max-t")]
    miss = [x for x in want if x not in txt]
    found = [x for x in absent if x in txt]
    line = (f"{a.kind}: {len(want) - len(miss)}/{len(want)} wanted lines" + (f" (missing: {'; '.join(miss)})" if miss else "")
            + (f"; UNWANTED: {'; '.join(found)}" if found else "; none of the unwanted lines"))
    ok = bool(txt) and not miss and not found
    print(line + (" -> PASS" if ok else " -> FAIL"))
    gate(a, "PASS" if ok else "FAIL", line if txt else "no start log")
    return 0


# ------------------------------------------------------------------------------------------------ exact7
def e7_of(summary, label):
    s = Path(summary).read_text(errors="replace") if Path(summary).exists() else ""
    m = re.findall(rf"^exact7 {re.escape(label)}: (\d)/7 identical", s, re.M)
    sl = re.findall(rf"^exact7-slots {re.escape(label)}: .*-> (MATCHED|DIFFER)", s, re.M)
    return (int(m[-1]) if m else None), (sl[-1] if sl else None)


def e7gate(a):
    n, sl = e7_of(a.summary, a.label)
    ok = n == 7 and sl == "MATCHED"
    line = f"exact7 {a.label}: {n if n is not None else '?'}/7, slots {sl or '?'}"
    status = "INFO" if a.info else ("PASS" if ok else "FAIL")
    print(f"{line} -> {status}")
    gate(a, status, line)
    return 0


def prof(label):
    p = PROF / f"{label}.out"
    t = p.read_text(errors="replace") if p.exists() else ""
    m = re.search(r"^output\s*:\s*(.*)$", t, re.M)
    toks = m[1].split() if m else None
    w = re.search(r"^window sizes\s+(.*?)\s+\(", t, re.M)
    hist = {int(k): int(v) for k, v in re.findall(r"T(\d+):(\d+)", w[1])} if w else {}
    e = (PROF / f"{label}.err").read_text(errors="replace") if (PROF / f"{label}.err").exists() else ""
    s = re.findall(r"expert cache (\d+) slots", e)
    h = re.findall(r"CUDA1: (\d+) additional experts", e)
    return toks, hist, ((int(s[-1]) if s else 0), (int(h[-1]) if h else 0))


def e7pair(a):
    lines, same_g, long_on, slots = [], 0, 0, set()
    for it in ITEMS:
        t1, h1, s1 = prof(f"{a.on}-{it}")
        t0, h0, s0 = prof(f"{a.off}-{it}")
        slots |= {s1, s0}
        lo = sum(v for k, v in h1.items() if k >= 9)
        if it in GREEDY:
            long_on += lo
        if t1 is None or t0 is None:
            lines.append(f"  {it}: missing output")
            continue
        same = t1 == t0
        first = next((i for i, (x, y) in enumerate(zip(t1, t0)) if x != y), min(len(t1), len(t0)) if not same else None)
        if it in GREEDY and same:
            same_g += 1
        lines.append(f"  {it}: {'identical' if same else f'DIFFERENT from token {first}'} ({len(t1)} / {len(t0)} tokens); "
                     f"windows of 9+ rows on {lo}, off {sum(v for k, v in h0.items() if k >= 9)}"
                     + ("" if it in GREEDY else " (sampled: reported only)"))
    print("\n".join(lines))
    if len(slots) != 1:
        v = "INVALID"
        why = f"slot counts differ {sorted(slots)}"
    elif long_on == 0:
        v, why = "UNEXERCISED", "no window of 9+ rows in the greedy on runs"
    elif same_g == len(GREEDY):
        v, why = ("SAME" if a.control else "PASS"), f"greedy {same_g}/{len(GREEDY)} identical"
    else:
        v, why = "DIFFER", f"greedy {same_g}/{len(GREEDY)} identical"
    line = f"{a.on} vs {a.off}: {why}; {long_on} windows of 9+ rows in the greedy on runs; slots {sorted(slots)}"
    print(f"{line} -> {v}")
    gate(a, v, line)
    return 0


# ------------------------------------------------------------------------------------------------ tests
def servetests(a):
    t = Path(a.file).read_text(errors="replace") if Path(a.file).exists() else ""
    ran = re.search(r"^Ran (\d+) tests?", t, re.M)
    bad = re.findall(r"^(?:FAIL|ERROR): (\S+)", t, re.M)
    unknown = sorted(set(bad) - KNOWN_SERVE_FAILS)
    ok = bool(ran) and not unknown
    line = (f"{ran.group(1) if ran else '?'} tests, {len(bad)} failed or erred"
            + (f" (known: {', '.join(sorted(set(bad) & KNOWN_SERVE_FAILS))})" if set(bad) & KNOWN_SERVE_FAILS else "")
            + (f"; NEW: {', '.join(unknown)}" if unknown else ""))
    print(line + (" -> PASS" if ok else " -> FAIL"))
    gate(a, "PASS" if ok else "FAIL", line)
    return 0


def fence4(a):
    sys.path.insert(0, a.tree)
    from serve.frontend import OutputParser  # noqa: E402 - the port's own parser, nothing else is imported
    tools = [{"name": "read_file", "parameters": {"properties": {"path": {"type": "string"}}}}]
    thought = ("The example to quote:\n````markdown\nA test file:\n```python\n"
               "assert out == \"<think>\\n\\n</think>\\n\\nhi\"\n```\nand the closing tag on its own: </think>\n````\n"
               "Now the answer.\n")
    text = thought + "</think>\n\nThe answer is 4."
    bad = []
    for width in (1, 2, 7, 100_000):
        p = OutputParser(thinking=True, tools=tools)
        evs = []
        for i in range(0, len(text), width):
            evs += p.feed(text[i:i + width])
        evs += p.finish()
        r = "".join(e.text for e in evs if e.kind == "reasoning")
        c = "".join(e.text for e in evs if e.kind == "content")
        calls = [e for e in evs if e.kind == "tool_call"]
        if r != thought or c != "The answer is 4." or calls:
            bad.append(f"width {width}: reasoning {r[-80:]!r}, content {c[:80]!r}, {len(calls)} calls")
    line = "four-backtick fence with a three-backtick example and </think>: " + ("reasoning until the outer fence "
           "closed, at widths 1 / 2 / 7 / all" if not bad else "; ".join(bad))
    print(line + (" -> PASS" if not bad else " -> FAIL"))
    gate(a, "FAIL" if bad else "PASS", line[:400])
    return 0


# ------------------------------------------------------------------------------------------------ checks (1) and (2)
def chk2(a):
    row = None
    for line in Path(a.file).read_text().splitlines() if Path(a.file).exists() else []:
        if line.startswith("| arith-j3"):
            row = [c.strip() for c in line.strip().strip("|").split("|")]
            break
    if not row:
        print(f"{a.file}: no arith-j3 row")
        gate(a, "FAIL", "no arith-j3 row")
        return 1
    n = int(row[2].split()[0])
    m = re.match(r"'(.*?)': (\d+) vs ([\d.]+)", row[3])
    obs, exp = int(m.group(2)), float(m.group(3))
    p0 = exp / n
    se = math.sqrt(p0 * (1 - p0) / n)
    pval, outside = float(row[5]), int(row[6])
    ok = pval >= 0.05 and outside == 0
    line = (f"{n} of {row[1]} samples at the tie; '{m.group(1)}' {100 * obs / n:.1f} % vs {100 * p0:.1f} % expected "
            f"({100 * (obs / n - p0):+.1f} points); chi-square {row[4]}, p {pval:.3f}, outside {outside}; 95 % +/- "
            f"{100 * Z95 * se:.1f} points, smallest detectable {100 * Z * se:.1f} points")
    status = "INFO" if a.info else ("PASS" if ok else "FAIL")
    print(f"{line} -> {status}")
    gate(a, status, line)
    return 0


def chk1(a):
    txt = Path(a.file).read_text() if Path(a.file).exists() else ""
    arms = re.findall(r"^(\S+): '.*?' (\d+) of (\d+)", txt, re.M)
    v = re.search(r"([+-][\d.]+) points, z ([-\d.]+), two-sided p ([\d.]+)", txt)
    if len(arms) < 2 or not v:
        print(f"{a.file}: no comparison")
        gate(a, "FAIL", "no comparison")
        return 1
    (l1, e1, n1), (l2, e2, n2) = [(x, int(y), int(z)) for x, y, z in arms[:2]]
    pb = (e1 + e2) / (n1 + n2)
    se = math.sqrt(pb * (1 - pb) * (1 / n1 + 1 / n2))
    pval = float(v.group(3))
    line = (f"{l2} {e2}/{n2} vs {l1} {e1}/{n1} at the tie: {v.group(1)} points, p {pval:.3f}; 95 % +/- "
            f"{100 * Z95 * se:.1f} points, smallest detectable {100 * Z * se:.1f} points")
    status = "PASS" if pval >= 0.05 else "FAIL"
    print(f"{line} -> {status}")
    gate(a, status, line)
    return 0


def tool_counts(path):
    rows = [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    spur = sum(1 for r in rows if r["verdict"].startswith("SPURIOUS") or any(f.startswith("SPURIOUS") for f in r["flags"]))
    lost = sum(1 for r in rows if r["verdict"].startswith("LOST"))
    err = sum(1 for r in rows if r["verdict"] == "ERROR")
    return len(rows), spur, lost, err


def toolcalls(a):
    nm, sm, lm, em = tool_counts(a.m)
    nx, sx, lx, ex = tool_counts(a.x)
    ok = nm == nx and nm > 0 and sx <= sm and lx <= lm and ex == 0 and em == 0
    line = (f"P028x (x28h) {nm} responses: {sm} with a spurious call, {lm} with a lost call, {em} errors; the v0.2.10 port "
            f"{nx}: {sx} spurious, {lx} lost, {ex} errors (rule: port spurious <= P028x's and port lost <= P028x's)")
    print(f"{line} -> {'PASS' if ok else 'FAIL'}")
    gate(a, "PASS" if ok else "FAIL", line)
    return 0


# ------------------------------------------------------------------------------------------------ 11-07 park amendment
# (the AMENDMENT 2026-11-07 block at the top of this file)
AMEND_FROM = "2026-11-07 14:00:00"
AMENDMENT_1107 = ("AMENDMENT 2026-11-07 (Karl; applies from now on, not to finished gates; recorded before the confirmation "
                  "gap): per-workload prompt numbers exclude the chat-cache save and are taken on the engine clock; the "
                  "overall screen rule stays on the client clock minus the save at -1 %; the save is judged as its own line "
                  "(its two levels taken into account); INFO flag: a workload's outside-engine time worse in every pass")
PARK_RE = re.compile(r"chat cache: parked a conversation of (\d+) tokens \((\d+) checkpoints?, (\d+) MiB\) in (\d+) ms")
ENGP_RE = re.compile(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+)(?: of \d+)? read in (\d+) ms")
# The stored band: every `chat cache: parked` line of the r22 / r23 screens up to 11-07 (872 saves; built by
# work/r23/scratch-hunt/park_ref_build.py -> park_ref_1107.json). Per parked size in MiB (with 10 or more saves), its
# levels. A size has two levels only where its sorted times have a gap of 6 ms or more, with 5 or more saves and 10 % or
# more of the size on each side. Each level is (n, median ms, robust sd = 1.4826 x MAD at least 1 ms, min, max).
PARK_REF_1107 = {
    132: [(32, 3.0, 1.0, 2, 4)],
    133: [(132, 3.0, 1.0, 2, 5)],
    150: [(16, 5.0, 1.0, 5, 6)],
    151: [(31, 6.0, 1.0, 5, 8)],
    152: [(120, 6.0, 1.0, 5, 8)],
    186: [(113, 10.0, 1.0, 9, 16)],
    578: [(119, 49.0, 1.48, 45, 81)],
    614: [(167, 54.0, 1.48, 50, 90)],
    824: [(11, 66.0, 1.48, 64, 67)],
    1238: [(44, 106.0, 2.22, 102, 113), (75, 131.0, 2.97, 123, 137)],
}
PARK_JUDGE_MS = 20.0      # saves of a size whose levels are shorter than this (2-10 ms, 1 ms log resolution): INFO only
PARK_BAND_Z = 6.0         # above the stored band: more than 6 robust sd over the size's top level
PARK_NOISE_FLOOR = 0.02   # the save index's noise is at least 2 %


def _gate_start(o):
    """The gate's start: the first timestamp of OUTDIR/summary.txt (or its parent's), else the oldest screen file's
    mtime; None when neither exists."""
    import time
    o = Path(o)
    for s in (o / "summary.txt", o.parent / "summary.txt"):
        if s.is_file():
            with open(s, errors="replace") as f:
                m = re.search(r"20\d\d-\d\d-\d\d \d\d:\d\d:\d\d", f.read(4096))
            if m:
                return m.group(0)
    t = [p.stat().st_mtime for p in (o / "speed").glob("*.jsonl")] if (o / "speed").is_dir() else []
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(min(t))) if t else None


def park_amended(o, amended=None):
    """True = OUTDIR is judged under the 11-07 amendment: a gate that started at or after AMEND_FROM (or undated data)
    AND has the screen's engine logs (speed/*.englog). False = a finished gate, or screen data without engine logs:
    the client clock as before. `amended` True / False forces it (the confirmation gap re-judges port-0211's screen)."""
    if amended is not None:
        return bool(amended)
    t = _gate_start(o)
    if t is not None and t < AMEND_FROM:
        return False
    sp_ = Path(o) / "speed"
    return sp_.is_dir() and any(sp_.glob("*.englog"))


def engine_requests(p):
    """An engine log's requests in order. Each request has its prompt tokens (n), reused, the prompt ms (r0 -> prompt
    read) and the chat-cache save that came before it inside that time ({tokens, ckpts, mib, ms} or None). cont marks an
    answer_room continuation (reused, 64 or fewer read)."""
    out, park = [], None
    with open(p, errors="replace") as f:
        for line in f:
            m = PARK_RE.search(line)
            if m:
                park = {"tokens": int(m.group(1)), "ckpts": int(m.group(2)), "mib": int(m.group(3)), "ms": int(m.group(4))}
                continue
            m = ENGP_RE.search(line)
            if m:
                n, ru = int(m.group(1)), int(m.group(2))
                out.append({"n": n, "reused": ru, "ms": int(m.group(4)), "park": park, "cont": ru > 0 and n - ru <= 64})
                park = None
    return out


def _park_pair(recs, englog):
    """11-07: each screen record gets its request's engine numbers. The englog's non-continuation requests are taken in
    order and must match by prompt tokens. Each matched record gets park_ms, park_mib and engine_prompt_ms; prompt_tps
    becomes the client clock minus the save (prompt tokens / (TTFT - save)); prompt_tps_wl is the per-workload number
    (prompt tokens / (engine prompt ms - save)); the client's own rate stays as prompt_tps_client. A record that cannot
    be matched gets neither rate (pair_error)."""
    reqs = [r for r in engine_requests(englog) if not r["cont"]] if englog.exists() else []
    for i, rec in enumerate(recs):
        rec["prompt_tps_client"] = rec.get("prompt_tps")
        e = reqs[i] if i < len(reqs) else None
        pt, ttft = rec.get("prompt_tokens"), rec.get("ttft_s")
        if e is None or not pt or e["n"] != pt or not ttft:
            rec["prompt_tps"] = rec["prompt_tps_wl"] = None
            rec["pair_error"] = (f"{englog.name}: no engine request {i + 1}" if e is None else
                                 f"{englog.name}: request {i + 1} ({rec.get('id')}) has {e['n']} prompt tokens in the engine "
                                 f"log, {pt} at the client")
            continue
        pk = e["park"]["ms"] if e["park"] else 0
        rec["park_ms"], rec["park_mib"], rec["engine_prompt_ms"] = pk, (e["park"] or {}).get("mib"), e["ms"]
        rec["prompt_tps"] = round(pt / (ttft - pk / 1000), 1) if ttft > pk / 1000 else None
        rec["prompt_tps_wl"] = round(1000 * pt / (e["ms"] - pk), 1) if e["ms"] > pk else None
        rec["outside_ms"] = round(1000 * ttft - e["ms"], 1)   # (the save is inside the engine figure: it cancels)


def outside_flags(x, b):
    """11-07 INFO flag (Karl): X, B = {workload: [the arm's per-pass outside-engine ms]}, for the arm and the base. A
    workload is flagged when every pass of the arm (2 or more) is above the base's mean by more than the spread: the
    larger of the two arms' half-ranges, (max - min) / 2, over their passes. Returns [(workload, arm mean - base mean,
    spread)]. INFO only: it never changes a verdict."""
    out = []
    for w in x:
        xa, ba = x[w], b.get(w, [])
        if len(xa) < 2 or not ba:
            continue
        spread_ms = max((max(xa) - min(xa)) / 2, (max(ba) - min(ba)) / 2)
        mb = st.mean(ba)
        if all(v > mb + spread_ms for v in xa):
            out.append((w, st.mean(xa) - mb, spread_ms))
    return out


def outside_line(flags, arm, ref):
    """The INFO clause of a flag list (outside_flags)."""
    if not flags:
        return f"(info) outside-engine time: no workload of {arm} worse than {ref} in every pass"
    return (f"(info) outside-engine time worse in every pass - for review (INFO): "
            + ", ".join(f"{w} {arm} {d:+.1f} ms vs {ref} (spread {s:.1f} ms)" for w, d, s in flags))


def pair_problems(o, arm, sets="nar"):
    """The 11-07 pairing failures of ARM's screen records (for a NOT DECIDED line)."""
    out = []
    for k in (1, 2, 3):
        for r in screen_rows(o, arm, k, sets, amended=True).values():
            if r.get("pair_error"):
                out.append(r["pair_error"])
    return out


def park_level(mib, ms):
    """(level index, ms / that level's median, z over the size's top level) against PARK_REF_1107; None when the size
    has no stored band."""
    lv = PARK_REF_1107.get(mib)
    if not lv:
        return None
    i = min(range(len(lv)), key=lambda j: abs(ms - lv[j][1]) / lv[j][2])
    return i, ms / lv[i][1], (ms - lv[-1][1]) / lv[-1][2]


def screen_parks(o, arm, sets="nar"):
    """Per pass k (where ARM has an engine log): the chat-cache saves of ARM's screen requests, in order."""
    out = {}
    for k in (1, 2, 3):
        logs = [Path(o) / "speed" / f"{arm}{k}{s}.englog" for s in sets]
        if any(p.exists() for p in logs):
            out[k] = [r["park"] for p in logs if p.exists() for r in engine_requests(p) if r["park"]]
    return out


def save_index(parks_by_pass, local=None):
    """Per pass: the geometric mean of save / its level's median. Without LOCAL: the saves of sizes with a stored band
    of 20 ms or more, each against its level's stored median. With LOCAL ({mib: the base arm's median in this screen}):
    only the saves of those sizes, each against that median."""
    out = {}
    for k, ps in parks_by_pass.items():
        if local is None:
            us = [park_level(p["mib"], p["ms"])[1] for p in ps
                  if p["mib"] in PARK_REF_1107 and PARK_REF_1107[p["mib"]][0][1] >= PARK_JUDGE_MS]
        else:
            us = [p["ms"] / local[p["mib"]] for p in ps if p["mib"] in local]
        if us:
            out[k] = gm(us)
    return out


def save_local(pa, pb):
    """Sizes with no stored band (a new model's): usable against the base arm's median in this screen when both arms
    have 2 or more saves of the size, its median is 20 ms or more, and neither arm's own times show two levels (a gap
    of max(6 ms, 8 % of the median)). Returns ({mib: base median}, {mib: why not})."""
    local, skip = {}, {}
    sizes = {p["mib"] for pp in (pa, pb) for ps in pp.values() for p in ps} - set(PARK_REF_1107)
    for mib in sorted(sizes):
        va = sorted(p["ms"] for ps in pa.values() for p in ps if p["mib"] == mib)
        vb = sorted(p["ms"] for ps in pb.values() for p in ps if p["mib"] == mib)
        if len(va) < 2 or len(vb) < 2 or st.median(va + vb) < PARK_JUDGE_MS:
            continue
        lim = max(6.0, 0.08 * st.median(va + vb))
        if any(y - x >= lim for v in (va, vb) for x, y in zip(v, v[1:])):
            skip[mib] = "one arm shows two levels and there is no stored band - not judged"
            continue
        local[mib] = st.median(vb)
    return local, skip


def save_rule(o, arm="P", ref="B", amended=None, sets="nar"):
    """11-07: the chat-cache save line of a screen, ARM against REF. Returns (verdict, lines); verdict None when OUTDIR is
    not under the amendment (no line).
    - Judged on the sizes with a stored band (PARK_REF_1107): PASS / FAIL as in the AMENDMENT block.
    - With none of those, on the sizes save_local accepts, against REF's median in this screen: PASS when ARM's index
      is not above REF's beyond the noise. A shift there is NOT DECIDED, not FAIL: without a stored band a real
      slowdown and a two-level draw (as the 1238 MiB save's) cannot be told apart - rerun, or build the size's band.
    - NOT JUDGED (INFO) when the screen has no save, or none that can be judged; NOT DECIDED with fewer than 2
      passes of judged saves per arm."""
    if not park_amended(o, amended):
        return None, []
    pa, pb = screen_parks(o, arm, sets), screen_parks(o, ref, sets)
    local, skip = save_local(pa, pb)
    sizes = sorted({p["mib"] for pp in (pa, pb) for ps in pp.values() for p in ps})
    info = []
    for mib in sizes:
        lv = PARK_REF_1107.get(mib)
        parts = []
        for name, pp in ((ref, pb), (arm, pa)):
            v = [p["ms"] for ps in pp.values() for p in ps if p["mib"] == mib]
            if not v:
                parts.append(f"{name} -")
                continue
            if lv and len(lv) == 2:
                lev = [park_level(mib, x)[0] for x in v]
                parts.append(f"{name} {'/'.join(str(x) for x in v)} ms (fast {lev.count(0)}, slow {lev.count(1)})")
            else:
                parts.append(f"{name} {'/'.join(str(x) for x in v)} ms (mean {st.mean(v):.1f})")
        band = (" stored band " + " / ".join(f"{x[3]}-{x[4]}" for x in lv)) if lv else (
            f" no stored band ({skip[mib]})" if mib in skip else
            f" no stored band, against {ref}'s median {local[mib]:g} ms in this screen" if mib in local else
            " no stored band, not judged (fewer than 2 saves an arm, or under 20 ms)")
        info.append(f"(info) save {mib} MiB:{band}; " + ", ".join(parts)
                    + ("; the level mix is not judged" if lv and len(lv) == 2 else ""))
    head = "chat-cache save [11-07 amendment]"
    if not sizes:
        return "NOT JUDGED", [f"{head}: NOT JUDGED - no chat-cache save in this screen"]
    ia, ib = save_index(pa), save_index(pb)
    use_local = not (ia or ib) and bool(local)
    if use_local:
        ia, ib = save_index(pa, local), save_index(pb, local)
    if not ia and not ib:
        return "NOT JUDGED", [f"{head}: NOT JUDGED - no save size of this screen ({', '.join(str(m) for m in sizes)} MiB) "
                              f"has a stored band of 20 ms or more, or one level of 20 ms or more in both arms (extend "
                              f"PARK_REF_1107 from a base arm's saves)"] + info
    if len(ia) < 2 or len(ib) < 2:
        return "NOT DECIDED", [f"{head}: NOT DECIDED - {arm} {len(ia)} / {ref} {len(ib)} passes with judged saves "
                               f"(2 needed)"] + info
    ma, mb = gm(list(ia.values())), gm(list(ib.values()))
    noise = max(spread(list(ia.values())), spread(list(ib.values())), PARK_NOISE_FLOOR)
    d = ma / mb - 1
    if use_local:
        v = "NOT DECIDED" if d > noise else "PASS"
        why = (" - a shift on sizes with no stored band: a real slowdown or a two-level draw; rerun, or build their band"
               if d > noise else "")
        return v, [f"{head}: {arm} {100 * d:+.1f} % vs {ref} (no size with a stored band: save index = each save / "
                   f"{ref}'s median of its size in this screen, geometric mean per pass then over passes; {len(ia)} / "
                   f"{len(ib)} passes; noise {100 * noise:.1f} %) -> {v}{why}"] + info

    def high(pp):
        return {k: [p for p in ps if p["mib"] in PARK_REF_1107 and park_level(p["mib"], p["ms"])[2] > PARK_BAND_Z]
                for k, ps in pp.items()}
    ha, hb = high(pa), high(pb)
    na, nb = sum(len(x) for x in ha.values()), sum(len(x) for x in hb.values())
    ka = sum(1 for x in ha.values() if x)
    shift_fail, band_fail = d > noise, ka >= 2 and na > nb
    v = "FAIL" if shift_fail or band_fail else "PASS"
    hi_txt = ""
    if na or nb:
        hi_txt = (f"; above the stored band: {arm} {na} in {ka} pass(es), {ref} {nb}"
                  + (" -> FAIL (2+ passes, more than the base)" if band_fail else " (INFO: a one-off, or no more than the base)"))
    if local:   # sizes with no stored band beside the judged ones: INFO
        la, lb = save_index(pa, local), save_index(pb, local)
        if len(la) >= 2 and len(lb) >= 2:
            info.append(f"(info) the sizes with no stored band ({', '.join(str(m) for m in sorted(local))} MiB): {arm} "
                        f"{100 * (gm(list(la.values())) / gm(list(lb.values())) - 1):+.1f} % vs {ref} (not judged)")
    return v, [f"{head}: {arm} {100 * d:+.1f} % vs {ref} (save index = each save / the stored median of its level, "
               f"geometric mean per pass then over passes; {len(ia)} / {len(ib)} passes; noise {100 * noise:.1f} %)"
               f"{hi_txt} -> {v}"] + info


def park_edit(d, arm, prefill=None, save=None, only=None):
    """Selftests only (11-07): ARM's engine logs and screen records under D edited - prefill(ms) / save(ms, mib, k)
    give the new numbers; the prompt line's ms and the client's TTFT move by the same amount (ONLY: the workloads to
    touch)."""
    for k in (1, 2, 3):
        for s in "nar":
            jl, eg = d / "speed" / f"{arm}{k}{s}.jsonl", d / "speed" / f"{arm}{k}{s}.englog"
            recs = [json.loads(x) for x in jl.read_text().splitlines() if x.strip()]
            out, park, i, deltas = [], None, 0, []
            for line in eg.read_text().splitlines(keepends=True):
                m = PARK_RE.search(line)
                if m:
                    park = [int(m.group(3)), int(m.group(4)), m, len(out)]
                    out.append(line)
                    continue
                m = ENGP_RE.search(line)
                if m:
                    n, ru, ms = int(m.group(1)), int(m.group(2)), int(m.group(4))
                    cont = ru > 0 and n - ru <= 64
                    wid = recs[i]["id"] if not cont and i < len(recs) else None
                    pk = park[1] if park else 0
                    new_pk, new_pf = pk, ms - pk
                    if wid is not None and (only is None or wid in only):
                        if save and park:
                            new_pk = int(round(save(pk, park[0], k)))
                            pm, j = park[2], park[3]
                            out[j] = out[j][:pm.start(4)] + str(new_pk) + out[j][pm.end(4):]
                        if prefill:
                            new_pf = int(round(prefill(ms - pk)))
                    dlt = (new_pk + new_pf) - ms
                    line = line[:m.start(4)] + str(ms + dlt) + line[m.end(4):]
                    if not cont:
                        deltas.append(dlt)
                        i += 1
                    park = None
                out.append(line)
            eg.write_text("".join(out))
            for r, dlt in zip(recs, deltas):
                if dlt:
                    r["ttft_s"] = round(r["ttft_s"] + dlt / 1000, 3)
                    r["prompt_tps"] = round(r["prompt_tokens"] / r["ttft_s"], 1)
            jl.write_text("".join(json.dumps(r) + "\n" for r in recs))


def park_edit_outside(d, arm, add_ms, only=None, passes=(1, 2, 3)):
    """Selftests only (11-07): ARM's client records under D get ADD_MS more TTFT (the outside-engine time) for the
    workloads in ONLY (all when None) in PASSES; the engine logs are left as they are."""
    for k in passes:
        for s in "nar":
            jl = d / "speed" / f"{arm}{k}{s}.jsonl"
            recs = [json.loads(x) for x in jl.read_text().splitlines() if x.strip()]
            for r in recs:
                if only is None or r["id"] in only:
                    r["ttft_s"] = round(r["ttft_s"] + add_ms / 1000, 3)
                    r["prompt_tps"] = round(r["prompt_tokens"] / r["ttft_s"], 1)
            jl.write_text("".join(json.dumps(r) + "\n" for r in recs))


def park_selftest(a):
    """park-selftest SCRATCH: the 11-07 amendment on a copy of port-0211's stored screen (B fast and P slow on the
    1238 MiB save; equal prefill) and on edited copies of it. No GPU, no engine; writes only under SCRATCH."""
    import shutil
    src = Path("/home/USER/ai-speed-testing/strata-compare/results/r23/port-0211/gap/speed")
    root = Path(a.scratch) / "park-selftest"
    shutil.rmtree(root, ignore_errors=True)
    fails = []

    def check(name, cond, txt=""):
        print(f"{'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)
            print("     " + str(txt)[:1500])

    def mk(name, englogs=True):
        d = root / name
        (d / "speed").mkdir(parents=True)
        for f in src.glob("[BP][123][nar].jsonl"):
            shutil.copy(f, d / "speed" / f.name)
            if englogs:
                shutil.copy(f.with_suffix(".englog"), d / "speed" / f.with_suffix(".englog").name)
        return d

    # 1. the stored screen as it is: B fast, P slow on the 1238 MiB save, equal prefill
    d = mk("real")
    check("a new gate dir with engine logs is amended (auto)", park_amended(d) is True, _gate_start(d))
    check("the same without engine logs keeps the old clock (auto)", park_amended(mk("nolog", englogs=False)) is False)
    v, ls = baseline_speed(d)
    ok, line = wl_noloss(d, "P", ref="B")
    sv, sl = save_rule(d)
    check("B-fast vs P-slow saves, equal prefill: g16 rule PASS", v == "PASS", ls)
    check("B-fast vs P-slow saves, equal prefill: per-workload no-loss PASS", ok is True, line)
    check("B-fast vs P-slow saves, equal prefill: save PASS", sv == "PASS", sl)
    check("the save line names the level mix as INFO", any("1238 MiB" in x and "fast 3" in x and "slow 3" in x for x in sl), sl)
    # 2. the same saves swapped (B slow, P fast) -> PASS
    d = mk("swap")
    park_edit(d, "B", save=lambda ms, mib, k: 131 if mib == 1238 else ms)
    park_edit(d, "P", save=lambda ms, mib, k: 106 if mib == 1238 else ms)
    sv, sl = save_rule(d)
    ok, line = wl_noloss(d, "P", ref="B")
    check("B-slow vs P-fast saves: save PASS, no-loss PASS", sv == "PASS" and ok is True, [sl, line])
    # 3. a real +15 % prefill slowdown on every P request -> per-workload FAIL and the g16 rule FAIL
    d = mk("prefill15")
    park_edit(d, "P", prefill=lambda ms: ms * 1.15)
    v, ls = baseline_speed(d)
    ok, line = wl_noloss(d, "P", ref="B")
    sv, sl = save_rule(d)
    check("+15 % prefill on P: per-workload no-loss FAIL", ok is False and "R3-extract5k prompt" in line, line)
    check("+15 % prefill on P: g16 rule FAIL", v == "FAIL", ls)
    check("+15 % prefill on P: the save line still PASS", sv == "PASS", sl)
    # 4. +15 % prefill on R3 only -> per-workload FAIL on R3
    d = mk("prefill15r3")
    park_edit(d, "P", prefill=lambda ms: ms * 1.15, only={"R3-extract5k"})
    ok, line = wl_noloss(d, "P", ref="B")
    check("+15 % prefill on P's R3 only: per-workload FAIL names R3", ok is False and "R3-extract5k prompt" in line
          and "R2-report54k prompt" not in line, line)
    # 5. a real save slowdown: every P save +15 % (both levels), the prefill unchanged -> the save line FAILs only
    d = mk("save15")
    park_edit(d, "P", save=lambda ms, mib, k: ms * 1.15)
    v, ls = baseline_speed(d)
    ok, line = wl_noloss(d, "P", ref="B")
    sv, sl = save_rule(d)
    check("+15 % save on P (both levels): save FAIL", sv == "FAIL", sl)
    check("+15 % save on P: per-workload no-loss PASS (the save is out of the prompt number)", ok is True, line)
    check("+15 % save on P: g16 rule PASS", v == "PASS", ls)
    # 6. B and P both fast, P's saves +15 % -> FAIL (level for level)
    d = mk("save15same")
    park_edit(d, "P", save=lambda ms, mib, k: (106 if mib == 1238 else ms) * 1.15)
    sv, sl = save_rule(d)
    check("B fast, P fast + 15 %: save FAIL", sv == "FAIL", sl)
    # 7. only the 1238 MiB save regresses, far above the band, in every pass -> FAIL (band)
    d = mk("bigsave")
    park_edit(d, "P", save=lambda ms, mib, k: 175 if mib == 1238 else ms)
    sv, sl = save_rule(d)
    check("P's 1238 MiB save at 175 ms in 3 passes: save FAIL", sv == "FAIL" and "above the stored band" in sl[0], sl)
    # 8. a one-off: one P save of 578 MiB at 81 ms (the band's own outlier) -> PASS
    d = mk("oneoff")
    park_edit(d, "P", save=lambda ms, mib, k: 81 if (mib == 578 and k == 2) else ms)
    sv, sl = save_rule(d)
    check("one 578 MiB save at 81 ms in one P pass: save PASS", sv == "PASS", sl)
    # 9. a new model's sizes (no stored band): one-level sizes judged against B's median, a two-level one INFO only
    def newsizes(name):
        d = mk(name)
        for f in (d / "speed").glob("*.englog"):
            f.write_text(f.read_text().replace("1238 MiB", "4321 MiB").replace("578 MiB", "4322 MiB")
                         .replace("614 MiB", "4323 MiB"))
        return d
    d = newsizes("newsizes")
    park_edit(d, "P", save=lambda ms, mib, k: 105 if mib == 4321 else ms)
    sv, sl = save_rule(d)
    check("new sizes, equal saves: save PASS against B's medians", sv == "PASS"
          and any("4322 MiB" in x and "against B's median" in x for x in sl), sl)
    sv, sl = save_rule(newsizes("newsizes-mix"))
    check("new sizes, B-fast vs P-slow on one of them: NOT DECIDED (no band to tell a draw from a slowdown)",
          sv == "NOT DECIDED" and "two-level draw" in sl[0], sl)
    d = newsizes("newsizes15")
    park_edit(d, "P", save=lambda ms, mib, k: ms * 1.15)
    sv, sl = save_rule(d)
    check("new sizes, every P save +15 %: NOT DECIDED (never PASS)", sv == "NOT DECIDED", sl)
    d = mk("chatoff")
    for f in (d / "speed").glob("*.englog"):
        f.write_text("".join(x for x in f.read_text().splitlines(keepends=True) if "chat cache: parked" not in x))
    sv, sl = save_rule(d)
    check("no save in the screen (chat cache off): NOT JUDGED", sv == "NOT JUDGED" and "no chat-cache save" in sl[0], sl)
    # 9b. only saves under 20 ms -> NOT JUDGED
    d = mk("smallonly")
    for f in (d / "speed").glob("*.englog"):
        f.write_text("".join(x for x in f.read_text().splitlines(keepends=True)
                             if not any(s in x for s in ("1238 MiB", "578 MiB", "614 MiB"))))
    sv, sl = save_rule(d)
    check("only saves under 20 ms: NOT JUDGED", sv == "NOT JUDGED", sl)
    # 10. a pairing failure -> NOT DECIDED with the reason
    d = mk("pairfail")
    eg = d / "speed" / "P2r.englog"
    eg.write_text(eg.read_text().replace("prompt 5011 tokens", "prompt 5099 tokens"))
    v, ls = baseline_speed(d)
    ok, line = wl_noloss(d, "P", ref="B")
    check("a request the engine log does not match: NOT DECIDED, named", v == "NOT DECIDED" and ok is None
          and "pairing failed" in line and "5099" in line, [ls, line])
    # 11. the outside-engine INFO flag (Karl 11-07): never a verdict
    ok0, line0 = wl_noloss(mk("of-real"), "P", ref="B")
    check("outside-engine flag on port-0211's own screen: R4 flagged (its +16 ms in all 3 passes), verdict PASS",
          ok0 is True and "R4-agent33k P +" in line0.split("for review (INFO): ")[-1], line0)
    d = mk("of-r3")
    park_edit_outside(d, "P", 15, only={"R3-extract5k"})
    ok, line = wl_noloss(d, "P", ref="B")
    check("+15 ms outside the engine on R3 in every P pass: R3 flagged, the verdict unchanged",
          ok is True and "R3-extract5k P +" in line.split("for review (INFO): ")[-1], line)
    d = mk("of-r4-1")
    park_edit_outside(d, "P", -16, only={"R4-agent33k"}, passes=(1, 2))
    ok, line = wl_noloss(d, "P", ref="B")
    check("the pause on R4 in one pass only: not flagged", ok is True and "R4-agent33k" not in line.split("outside-engine")[-1],
          line)
    d = mk("of-r4-2")
    park_edit_outside(d, "P", -16, only={"R4-agent33k"}, passes=(1,))
    ok, line = wl_noloss(d, "P", ref="B")
    check("the pause on R4 in two passes: not flagged", ok is True and "R4-agent33k" not in line.split("outside-engine")[-1],
          line)
    d = mk("of-all")
    park_edit_outside(d, "P", 30)
    ok, line = wl_noloss(d, "P", ref="B")
    v, ls = baseline_speed(d)
    flagged = line.split("for review (INFO): ")[-1] if "for review (INFO)" in line else ""
    check("a uniform +30 ms outside the engine: all 9 flagged, still INFO (per-workload no-loss PASS)",
          ok is True and all(w in flagged for w in WL9), [line, v])
    print(f"park-selftest: {len(fails)} failure(s)")
    return 1 if fails else 0


# ------------------------------------------------------------------------------------------------ speed
def screen_rows(o, arm, k, sets="nar", amended=None):
    rows = {}
    am = park_amended(o, amended)
    for s in sets:
        p = Path(o) / "speed" / f"{arm}{k}{s}.jsonl"
        if p.exists():
            recs = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
            if am:   # 11-07 amendment: the engine's numbers and the save of each request
                _park_pair(recs, Path(o) / "speed" / f"{arm}{k}{s}.englog")
            for r in recs:
                rows[r["id"]] = r
    return rows


def screen_passes(o, arm, amended=None):
    """Per complete pass: (decode geometric mean, prompt geometric mean, {workload: per-workload prompt}). Under the
    11-07 amendment the aggregate prompt is the client clock minus the save and the per-workload prompt is the engine's
    prompt ms minus the save; otherwise both are the client's prompt_tps, as before."""
    am = park_amended(o, amended)
    wk = "prompt_tps_wl" if am else "prompt_tps"
    out = {}
    for k in (1, 2, 3):
        rows = screen_rows(o, arm, k, amended=am)
        if all(w in rows and rows[w].get("decode_tps") and rows[w].get("prompt_tps") and rows[w].get(wk) for w in WL9):
            out[k] = (gm([rows[w]["decode_tps"] for w in WL9]), gm([rows[w]["prompt_tps"] for w in WL9]),
                      {w: rows[w][wk] for w in WL9})
    return out


def baseline_speed(o, amended=None):
    am = park_amended(o, amended)
    b, p = screen_passes(o, "B", amended=am), screen_passes(o, "P", amended=am)
    if len(b) < 3 or len(p) < 3:
        why = [f"speed screen: B {len(b)} / P {len(p)} complete passes of 3"]
        if am:
            prob = pair_problems(o, "B") + pair_problems(o, "P")
            if prob:
                why.append("speed screen [11-07 amendment]: engine log pairing failed: " + "; ".join(prob[:4]))
        return "NOT DECIDED", why
    out, worst = [], "PASS"
    if am:
        out.append("speed screen [11-07 amendment]: prompt numbers exclude the chat-cache save (aggregate: client TTFT "
                   "minus the save; per workload: the engine's prompt ms minus the save)")
    for idx, name in ((0, "decode"), (1, "prompt")):
        mb, mp = gm([v[idx] for v in b.values()]), gm([v[idx] for v in p.values()])
        noise = max(spread([v[idx] for v in b.values()]), spread([v[idx] for v in p.values()]))
        d = mp / mb - 1
        v = "PASS" if d >= -0.010 else ("BORDERLINE" if d >= -noise else "FAIL")
        worst = v if (v == "FAIL" or (v == "BORDERLINE" and worst == "PASS")) else worst
        out.append(f"speed screen {name}: P {100 * d:+.2f} % vs B (B {mb:,.1f}, P {mp:,.1f}; noise {100 * noise:.1f} %) -> {v}")
    for w in WL9:
        pb = st.mean(v[2][w] for v in b.values())
        pp = st.mean(v[2][w] for v in p.values())
        if pp < 0.97 * pb:
            worst = "FAIL"
            out.append(f"speed screen prompt {w}: P {100 * (pp / pb - 1):+.1f} % (more than 3 % below B) -> FAIL")
    return worst, out


def noloss(o, arm, ref="P", amended=None):
    r, x = screen_passes(o, ref, amended=amended), screen_passes(o, arm, amended=amended)
    if len(r) < 3 or not x:
        return "NOT DECIDED", f"{arm}: {len(x)} complete passes, {ref}: {len(r)}"
    ok, parts = True, []
    for idx, name in ((0, "decode"), (1, "prompt")):
        mr, mx = gm([v[idx] for v in r.values()]), gm([v[idx] for v in x.values()])
        noise = max(spread([v[idx] for v in r.values()]), spread([v[idx] for v in x.values()]))
        ok &= mx >= mr * (1 - noise)
        parts.append(f"{name} {100 * (mx / mr - 1):+.2f} % (noise {100 * noise:.1f} %, {len(x)} pass(es))")
    return ("PASS" if ok else "FAIL"), f"{arm} vs {ref}: " + ", ".join(parts)


def edit_price(o):
    def per(arm, wid):
        return [screen_rows(o, arm, k, "e").get(wid, {}).get("decode_tps") for k in (1, 2, 3)]
    out, gain = [], None
    for wid in ("E1-rewrite", "E2-rewrite-nothink"):
        p, l = [x for x in per("P", wid) if x], [x for x in per("L", wid) if x]
        if len(p) < 2 or len(l) < 2:
            out.append(f"{wid}: P {len(p)} / L {len(l)} passes - not priced")
            continue
        d = st.mean(l) / st.mean(p) - 1
        noise = max(spread(p), spread(l))
        g = d > max(noise, 0.02)
        if wid == "E1-rewrite":
            gain = g
        out.append(f"{wid} decode: L {st.mean(l):.1f} vs P {st.mean(p):.1f} tok/s ({100 * d:+.1f} %; noise {100 * noise:.1f} %)"
                   + (" -> GAIN" if g else ""))
    for wid in ("A-edit", "B-write"):
        p = [screen_rows(o, "P", k, "a").get(wid, {}).get("decode_tps") for k in (1, 2, 3)]
        l = [screen_rows(o, "L", k, "a").get(wid, {}).get("decode_tps") for k in (1, 2, 3)]
        p, l = [x for x in p if x], [x for x in l if x]
        if p and l:
            out.append(f"{wid} decode (reported): L {st.mean(l):.1f} vs P {st.mean(p):.1f} ({100 * (st.mean(l) / st.mean(p) - 1):+.1f} %)")
    return gain, out


def bp90_load(d, n):
    p = Path(d) / f"cold-{n}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def bp90_vals(recs, test, key):
    return [r[key] for r in recs if r["test"] == test and r.get(key)]


def bp90_blends(recs):
    b = []
    for p in sorted({r["pass"] for r in recs}):
        rs = [r for r in recs if r["pass"] == p and r["test"] in ("conv", "struct", "prose")]
        if len(rs) == 3:
            b.append(sum(r["predicted_n"] for r in rs) / (sum(r["predicted_ms"] for r in rs) / 1000))
    return b


def bp90_baseline(d):
    M, X = bp90_load(d, "M"), bp90_load(d, "H")
    if not M or not X:
        return "NOT DECIDED", ["Basalt fixtures: cold-M / cold-H missing"]
    out, ok = [], True
    for t in ("conv", "struct", "prose"):
        m, x = bp90_vals(M, t, "decode_tps"), bp90_vals(X, t, "decode_tps")
        if not m or not x:
            ok = False
            out.append(f"Basalt {t} decode: missing")
            continue
        sp = max((max(v) - min(v)) / st.mean(v) for v in (m, x))
        dd = st.mean(x) / st.mean(m) - 1
        ok &= dd >= -sp
        out.append(f"Basalt {t} decode: P {st.mean(x):.1f} vs B {st.mean(m):.1f} ({100 * dd:+.1f} %; spread {100 * sp:.1f} %) -> "
                   + ("PASS" if dd >= -sp else "FAIL"))
    for name, m, x in (("blend", bp90_blends(M), bp90_blends(X)),
                       ("16K prompt", bp90_vals(M, "pp16k", "prompt_tps"), bp90_vals(X, "pp16k", "prompt_tps")),
                       ("64K prompt", bp90_vals(M, "pp64k", "prompt_tps"), bp90_vals(X, "pp64k", "prompt_tps"))):
        if not m or not x:
            ok = False
            out.append(f"Basalt {name}: missing")
            continue
        dd = st.mean(x) / st.mean(m) - 1
        ok &= dd >= -0.010
        out.append(f"Basalt {name}: P {st.mean(x):,.1f} vs B {st.mean(m):,.1f} ({100 * dd:+.1f} %) -> " + ("PASS" if dd >= -0.010 else "FAIL"))
    return ("PASS" if ok else "FAIL"), out


def bp90_price(d, arm):
    """GDN pricing on the cold long prompts: ARM (G, T or V) vs H (the port), and vs M (P028x, reported)."""
    H, A, M = bp90_load(d, "H"), bp90_load(d, arm), bp90_load(d, "M")
    out, ok_floor, gain, have = [], True, False, True
    for t, name in (("pp16k", "16K"), ("pp64k", "64K")):
        h, g, m = bp90_vals(H, t, "prompt_tps"), bp90_vals(A, t, "prompt_tps"), bp90_vals(M, t, "prompt_tps")
        if len(h) < 2 or len(g) < 2:
            have = False
            out.append(f"{arm} {name} cold prompt: {arm} {len(g)} / P {len(h)} passes - not priced")
            continue
        dd = st.mean(g) / st.mean(h) - 1
        noise = max(spread(h), spread(g))
        ok_floor &= dd >= -noise
        gain |= dd > max(noise, 0.010)
        vs_m = f"; vs P028x {100 * (st.mean(g) / st.mean(m) - 1):+.1f} %" if m else ""
        out.append(f"{arm} {name} cold prompt: {st.mean(g):,.1f} vs P {st.mean(h):,.1f} tok/s ({100 * dd:+.1f} %; noise "
                   f"{100 * noise:.1f} %){vs_m}" + (" -> above +max(noise, 1 %)" if dd > max(noise, 0.010) else "")
                   + (" -> BELOW -noise" if dd < -noise else ""))
    return have, ok_floor, gain, out


def wl_noloss(o, arm, ref="P", amended=None):
    """Karl 11-03: no workload of the 9-workload screen slower beyond the noise - per workload, decode and prompt each,
    the arm's pass mean >= the base's pass mean x (1 - the larger of the two arms' pass-to-pass spreads there).
    11-07 amendment (park_amended): the prompt number is the engine's prompt ms minus the chat-cache save; the client
    clock minus the save is listed as INFO."""
    am = park_amended(o, amended)
    wk = "prompt_tps_wl" if am else "prompt_tps"

    def per(a):
        v = {}
        for k in (1, 2, 3):
            rows = screen_rows(o, a, k, amended=am)
            for w in WL9:
                r = rows.get(w, {})
                if r.get("decode_tps") and r.get(wk):
                    v.setdefault(w, []).append((r["decode_tps"], r[wk], r.get("prompt_tps")))
        return v
    x, b = per(arm), per(ref)
    tag = " [11-07 amendment: prompt = engine prompt ms minus the chat-cache save]" if am else ""
    prob = (pair_problems(o, arm) + pair_problems(o, ref)) if am else []
    if prob:   # 11-07: a record the engine log does not match leaves the screen undecided (not judged on fewer passes)
        return None, (f"per-workload no-loss{tag}: not decided - engine log pairing failed: " + "; ".join(prob[:4]))
    if any(len(x.get(w, [])) < 2 or len(b.get(w, [])) < 2 for w in WL9):
        return None, f"per-workload no-loss{tag}: {arm} or {ref} has fewer than 2 passes of a workload - not decided"
    slower = []
    for w in WL9:
        for idx, name in ((0, "decode"), (1, "prompt")):
            xa, ba = [v[idx] for v in x[w]], [v[idx] for v in b[w]]
            noise = max(spread(xa), spread(ba))
            d = st.mean(xa) / st.mean(ba) - 1
            if d < -noise:
                slower.append(f"{w} {name} {100 * d:+.1f} % (noise {100 * noise:.1f} %)")
    txt = (f"per-workload no-loss{tag}: none of the 9 slower beyond its noise" if not slower
           else f"per-workload no-loss{tag} FAILS: " + "; ".join(slower))
    if am:
        cl = []
        for w in WL9:
            xa, ba = [v[2] for v in x[w] if v[2]], [v[2] for v in b[w] if v[2]]
            if len(xa) >= 2 and len(ba) >= 2:
                noise = max(spread(xa), spread(ba))
                d = st.mean(xa) / st.mean(ba) - 1
                if d < -noise:
                    cl.append(f"{w} {100 * d:+.2f} % (noise {100 * noise:.2f} %)")
        txt += ("; (info) client clock minus the save, slower beyond its noise: " + ", ".join(cl) if cl
                else "; (info) client clock minus the save: no workload slower beyond its noise")
        # 11-07 (Karl): the outside-engine INFO flag (never a verdict)
        ox, ob = {}, {}
        for d_, a_ in ((ox, arm), (ob, ref)):
            for k in (1, 2, 3):
                rows = screen_rows(o, a_, k, amended=True)
                for w in WL9:
                    if rows.get(w, {}).get("outside_ms") is not None:
                        d_.setdefault(w, []).append(rows[w]["outside_ms"])
        txt += "; " + outside_line(outside_flags(ox, ob), arm, ref)
    return (not slower), txt


# ------------------------------------------------------------------------------------------------ the decision
def read_gates(o):
    g = {}
    p = Path(o) / "gates.txt"
    for line in p.read_text().splitlines() if p.exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)     # the last line of a gate counts
    return g


def decide(a):
    o = Path(a.outdir)
    g = read_gates(o)
    s = lambda k: g.get(k, ("MISSING", ""))[0]
    out, reasons, missing = [], [], []

    def need(keys, ok=("PASS",)):
        for k in keys:
            if s(k) == "MISSING":
                missing.append(k)
            elif s(k) not in ok:
                reasons.append(f"{k}: {s(k)} {g[k][1]}".strip()[:300])

    # ---- the baseline
    need(["build_x", "build_tests", "build_stock", "build8", "pins", "pins_h", "tests", "v2_unit", "sampler_tests",
          "servetests", "fence4", "guards", "e7_repeat", "e7_release", "e7_v2", "kl2_p210", "kl3_p210", "startlines_P",
          "cont_P", "chatcache", "vision", "toolcalls", "lossless"])
    need([k for k in g if re.match(SWITCH_ENV_RE, k) is None and k.startswith("env_")])
    for k in [k for k in g if k.startswith("fatal_") and re.match(SWITCH_FATAL_RE, k) is None]:
        reasons.append(f"{k}: {g[k][0]} {g[k][1]}"[:300])
    v = s("e7_vs_p028x")
    if v == "MISSING":
        missing.append("e7_vs_p028x")
    elif v != "PASS":
        u = s("e7_upstream")
        if u == "MISSING":
            missing.append("e7_upstream (needed: the port is not bit-identical to P028x)")
        elif u == "PASS":
            reasons.append("e7_vs_p028x: the port differs from P028x while stock 0.2.8 = stock 0.2.10 (e7_upstream 7/7): "
                           "our port changed bits")
        else:
            out.append("exact7 vs P028x: not identical, and upstream itself moved from 0.2.8 to 0.2.10 (e7_upstream) - "
                       "a cross-version difference; the KL rules and the checks decide")
    else:
        out.append("exact7 vs P028x: 7/7 identical (the port with the pins is P028x bit for bit on exact7)")
    sp_v, sp_l = baseline_speed(o)
    bp_v, bp_l = bp90_baseline(o / "bp90")
    out += sp_l + bp_l
    for name, vv in (("speed screen", sp_v), ("Basalt fixtures", bp_v)):
        if vv == "NOT DECIDED":
            missing.append(name)
        elif vv == "FAIL":
            reasons.append(f"{name}: FAIL")
    partb = ["build_twin", "chk2_p210", "chk1_p210_ess", "chk2_p210_ess"]
    need(partb)
    if reasons:
        base = "FAIL"
    elif missing:
        base = "INCOMPLETE"
    elif sp_v == "BORDERLINE":
        base = "BORDERLINE"
    else:
        base = "PASS"
    out.append(f"BASELINE (pinned-off port = P028x): {base}")
    out += [f"  - {r}" for r in reasons] + [f"  - not run / missing: {m}" for m in missing]
    for k in ("logits_vs_p028x", "chk2diag_p210", "chk2_s210", "build_stwin", "e7_upstream"):
        if k in g:
            out.append(f"  (info) {k}: {g[k][0]} {g[k][1]}"[:300])

    def armkeys(prefix):   # an arm's env / fatal gates (one per server start); none at all = the arm never ran
        e = [k for k in g if re.match(rf"env_{prefix}", k)]
        return (e or [f"env_{prefix}* (the arm never ran)"]) + [k for k in g if re.match(rf"fatal_{prefix}", k)]

    def verdict(name, req, extra_ok=True, gain=None, notes=()):
        bad = [f"{k}: {s(k)} {g.get(k, ('', ''))[1]}"[:240] for k in req if s(k) not in ("PASS", "MISSING")]
        miss = [k for k in req if s(k) == "MISSING"]
        if bad or extra_ok is False:
            v = "FAIL"
        elif miss or extra_ok is None:
            v = "NOT DECIDED"
        elif gain is None:
            v = "PASS"
        else:
            v = "CANDIDATE" if gain else "NO GAIN"
        out.append(f"{name}: {v}" + (f" (baseline {base})" if base != "PASS" else ""))
        out.extend(f"  {x}" for x in notes)
        out.extend(f"  - {x}" for x in bad)
        out.extend(f"  - not run / missing: {x}" for x in miss)

    # (0) GDN: the stack (G), then each path alone (T, V) - speed only when the stack passes KL, KL-gated when it fails
    def gdn_price(arm):
        have, floor, gain, gl = bp90_price(o / "bp90", arm)
        nl, nl_line = wl_noloss(o, arm)
        g_ok = None if (not have or nl is None) else (gain and floor and nl)
        return g_ok, gl + [nl_line]
    stack_kl = s("kl2_gdn") == "PASS" and s("kl3_gdn") == "PASS"
    g_ok, gnotes = gdn_price("G")
    verdict("(0) GDN_TC + GDN_CONVL2, the stack", ["kl2_gdn", "kl3_gdn"] + armkeys("bpG") + armkeys(r"G\d"),
            extra_ok=(None if g_ok is None else True), gain=g_ok, notes=gnotes)
    for arm, tag, name in (("T", "gdntc", "GDN_TC alone"), ("V", "gdncv", "GDN_CONVL2 alone")):
        req = armkeys(f"bp{arm}") + armkeys(rf"{arm}\d")
        if not stack_kl:
            req = [f"kl2_{tag}", f"kl3_{tag}"] + req
        p_ok, pnotes = gdn_price(arm)
        mode = "speed only (the stack passed KL)" if stack_kl else "KL-gated alone (the stack did not pass KL)"
        verdict(f"(0{arm.lower()}) {name}, {mode}", req, extra_ok=(None if p_ok is None else True), gain=p_ok,
                notes=pnotes + ["CANDIDATE = this path adds a gain; NO GAIN = it adds nothing and can stay off"])
    # (1) lookup windows
    le, lc = s("lookup_e7"), s("lookup_e7_ctl")
    ex_note = f"exactness: lookup_e7 {le}" + (f", control (GR_FORK=0) {lc}" if le == "DIFFER" else "")
    if le == "PASS":
        ex_ok = True
    elif le == "DIFFER" and lc == "DIFFER":
        ex_ok, ex_note = True, ex_note + " -> WINDOW-VARIANT (not the fork; the distribution checks decide)"
    elif le == "DIFFER" and lc == "SAME":
        ex_ok, ex_note = False, ex_note + " -> FAIL (only the fork's path differs with 12-row windows)"
    elif le in ("MISSING", "UNEXERCISED", "INVALID") or (le == "DIFFER" and lc in ("MISSING", "UNEXERCISED", "INVALID")):
        ex_ok = None   # not run, the 12-row path never ran, or the pair's slot counts differ: not decided
    else:
        ex_ok = False
    nl_v, nl_l = noloss(o, "L")
    egain, el = edit_price(o)
    wl_ok, wl_line = wl_noloss(o, "L")
    el.append(wl_line)
    if egain is not None:
        egain = None if wl_ok is None else (egain and wl_ok)
    lok = ex_ok if nl_v == "PASS" else (None if nl_v == "NOT DECIDED" else False)
    if lok and egain is None:
        lok = None     # the edit-turn workload was not priced: not decided
    verdict("(1) lookup windows up to 12", ["startlines_L", "cont_L", "chk1_p210_essL", "chk2_p210_essL"] + armkeys(r"L\d")
            + armkeys("spessL"),
            extra_ok=lok, gain=egain, notes=[ex_note, f"speed (9 workloads, no loss): {nl_l} -> {nl_v}"] + el)
    # (2) GR_V3_PF=133 identity
    nf_v, nf_l = noloss(o, "F")
    verdict("(2) GR_V3_PF=133 with GR_FORK=1 (identity)", ["e7_pf133"] + armkeys(r"F\d"),
            extra_ok={"PASS": True, "NOT DECIDED": None}.get(nf_v, False), notes=[f"speed: {nf_l} -> {nf_v}"])
    # (3) PF_HC_REGION
    nh_v, nh_l = noloss(o, "R")
    verdict("(3) PF_HC_REGION=1 with PREFILL_V2", ["e7_hcr", "hcr_logits"] + armkeys(r"R\d"),
            extra_ok={"PASS": True, "NOT DECIDED": None}.get(nh_v, False), notes=[f"one quick screen: {nh_l} -> {nh_v}"])
    out.append("Nothing switches (Karl 11-02: P028x stays served until item 7 is done); a CANDIDATE / PASS here is a "
               "candidate for after item 7, Karl's call.")
    txt = "\n".join(out) + "\n"
    (o / "decision.txt").write_text(txt)
    print(txt, end="")
    return 0 if base == "PASS" else 1


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name, *pos, info=False):
        p = sp.add_parser(name)
        for x in pos:
            p.add_argument(x)
        p.add_argument("--gate")
        p.add_argument("--gates")
        if info:
            p.add_argument("--info", action="store_true")
        return p
    p = sub("envcheck", "exe", "config")
    p.add_argument("--ngpu", type=int, default=2)
    p.add_argument("--pins", action="store_true")
    sub("pins", "config")
    p = sub("startlines", "kind", "startlog")
    p.add_argument("serverlog", nargs="*")
    sub("e7gate", "summary", "label", info=True)
    p = sub("e7pair", "on", "off")
    p.add_argument("--control", action="store_true")
    sub("servetests", "file")
    sub("fence4", "tree")
    sub("chk2", "file", info=True)
    sub("chk1", "file")
    sub("toolcalls", "m", "x")
    sp.add_parser("decide").add_argument("outdir")
    sp.add_parser("park-selftest").add_argument("scratch")   # 11-07 park amendment
    a = ap.parse_args()
    return {"envcheck": envcheck, "pins": pins, "startlines": startlines, "e7gate": e7gate, "e7pair": e7pair,
            "servetests": servetests, "fence4": fence4, "chk2": chk2, "chk1": chk1, "toolcalls": toolcalls,
            "decide": decide, "park-selftest": park_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
