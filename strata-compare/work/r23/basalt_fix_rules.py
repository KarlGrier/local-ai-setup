#!/usr/bin/env python3
"""basalt_fix_rules.py - r23 (11-05): the rules of the RERUN gap for the three Basalt prompt-path switches that never
engaged in gap a (work/r23/gap-basalt-fix.sh; results/r23/basalt-prompt/FIX-1105.md): STRATA_PF_AHEAD (A, exact),
STRATA_PF_TAIL_SPLIT (T, rounding-level), STRATA_PF_FIRST_CHUNK (C, the cap arm, rounding-level), on engine-r23basalt-fix
(branch r23-basalt-prompt + the three "r23 fix:" commits: the same switches, plus a line on every prompt saying what each
did or why not, and the layout each worked in). Written 11-05, NOT RUN. NOTHING SWITCHES: P028x stays served.

It reuses work/r23/basalt_rules.py (loaded read-only; that file is gap b's and is not edited) for everything that does
not change: the yardstick runs (pfy), the env checks (envcli / envcheck), exact7 gates (e7gate), byte identity (same),
the copy-ahead count (ahead), the KL rule (kl), the VRAM guard lines (vram). What is new, and why:
  1. THE CHUNK. Gap a's yardstick engine has one expert-cache slot, nothing is lendable, and generate.cpp then lays
     the prompt path out for 1024-token chunks for ANY --prefill auto[:N] (`o.prefill_chunk = 1024; // nothing
     lendable`). Every tail24 arm of gap a read in 1024-token chunks, not the served 16384. Here the tail24 arms pass an
     EXPLICIT --prefill 16384 (an explicit chunk is the operator's number: with nothing lendable the prompt path
     allocates its own buffers for it), and C's arms an explicit --prefill N. `chunk` checks it: every r23 layout line
     ("strata prefill: r23 switches: a layout for C-token chunks") of a switch arm must say the chunk asked for; an arm
     without an r23 switch (B16, B16s, unfused16) prints none and is checked by its index.json args (the same engine
     and args as the switch arms, whose lines show what explicit 16384 gives).
  2. THE PLAN LINES' FORMULA. The yardstick reads cut - 1 tokens in a batch (the last token goes through the first
     decode window), so the engine's n is tokens - 1: tail24's cuts 16640 and 49408 leave a 255-token rest, under
     STRATA_PF_TAIL_SPLIT=1's 256. `planlines` computes the plan with r23_plan.hpp's formulas (tail_split, first_chunk:
     ported below, checked against the C++ test's numbers) on n = tokens - 1 and requires the engine's plan lines to be
     exactly those prompts with exactly those chunk lengths (T16 at 16384: 22 of 24).
  3. THE CAP ARM'S SCAN. --prefill auto:N sets the auto scan's ceiling to 8192 / 16384 / 32768 (generate.cpp: N >= 32768
     -> 32768, >= 16384 -> 16384): gap a's auto:24576 was auto:16384 (c_lend FAIL). The scan arm (Cscan) here starts at
     --prefill auto:32768: the scan then picks the largest chunk on the 256 grid that the 90 % lend with a full ring
     allows (~20-22K expected on the 5080, 4,585 slots). C's arms then read at an explicit --prefill N.
  4. NLL IS INFORMATION ONLY (Karl 11-05: the many-positions bound is revoked): the KL rule is kernel_rule2 + kernel_rule3
     with its point NLL check printed as INFO (basalt_rules.py kl --mode new) and no score.py arm.
DECISION (decide; writes OUTDIR/decision-fix.txt), the same as gap a's for these three parts:
  BUILD     build_fix PASS (engine-r23basalt-fix: SHA256 matches, SOURCE = branch r23-basalt-prompt at FIX_HEAD, its GATES
            warnings PASS + strings PASS, its TESTS all PASS - written before the gap by gap-basalt-fix.sh)
  BASELINE  e7_B (exact7 at pin 2500, B on the fix engine vs gap 17's g17-p210a: 7/7, slots MATCHED) AND logits_B40
            (long40 B: 0 of 40 differ from gap 17's p210). Else nothing below is decided.
  A  EXACT when same_A16 + same_A16s (tail24 at 16384, int8, share 0 / the served share: 24/24 byte-identical), e7_A
     (7/7 MATCHED vs this gap's B), ahead_A16 + ahead_A16s (M > 0 read in place) AND chunk_A16 + chunk_A16s (the layout
     lines say 16384) and chunk_B16 + chunk_B16s (args 16384) - else NOT DECIDED (UNEXERCISED / not at the served
     chunk); differs -> rounding-level by the KL rule (tail24 A16, long40 A40), else FAIL
  T  ROUNDING-LEVEL when plan_T16 and plan_T40 (the plan lines = the formula's, n = tokens - 1, chunk 16384,
     stream-all 1024: 22 of tail24's 24, 1 of long40's 40 - tf-long64k-17408 -> 8704 + 8703), chunk_T16 / chunk_T40
     (16384) with chunk_B16 / chunk_B40_16 (args 16384), and the KL rule pass: tail24 T16 vs B16 / unfused16 /
     cpushare16 and long40 T40_16 vs B40_16 / unfused40_16 / cpushare40_16, all at an explicit --prefill 16384 (Karl
     11-05: long40 at the yardstick's bare auto is a 1024 chunk, where T cannot fire - gap a's T40 vs gap 8's
     references was vacuous; the bare-auto T40 is dropped). A KL check fails -> FAIL; plan or chunk evidence missing ->
     NOT DECIDED
  C  ROUNDING-LEVEL when c_lend (the scan's chunk N > 16384), plan_C16 (FIRST_CHUNK lines at N), chunk_C16 (N), vram_C
     (5080 free >= 300 MiB, MemAvailable >= 12 GiB in the scan and both C runs) and the KL rule (tail24 C16 and long40
     C40, both at an explicit --prefill N) pass; C = the stack S (gap a's S_PARTS + this gap's A / T where they passed)
     + N + STRATA_PF_FIRST_CHUNK=1, as gap a's A7. C40's KL rule is judged against the 16384 references of step T
     (B40_16, unfused40_16, cpushare40_16; Karl 11-05 "yes, use the 16384 references"): gates kl2_C_long40 /
     kl3_C_long40. Without them (T's long40 arms skipped by the deadline) C's long40 part is NOT DECIDED - never judged
     against the 1024 ones. The comparison against gap 8's bare-auto (1024-chunk) references is reported beside it as
     INFORMATION ONLY ("report the 1024 comparison beside it as information only"): gates kl2_Cinfo1024_long40 /
     kl3_Cinfo1024_long40, which never decide.
  An arm whose env / fatal gate failed is void, a reference's voids every part that compares with it (as gap a).

Subcommands: arms, chunk, planlines, lend, stack, buildcheck, decide (+ every basalt_rules.py subcommand through
`br SUBCOMMAND ...`). Python: .venv/bin/python -I -B.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
WS = Path("/home/USER/ai-speed-testing/strata-compare")
RU = WS / "work/r23/basalt_rules.py"
E_FIX = WS / "engine-r23basalt-fix"
TREE = WS / "strata-r23basalt"
BRANCH = "r23-basalt-prompt"
FIX_HEAD = "b8128327d"          # the third "r23 fix:" commit (STRATA_PF_FIRST_CHUNK)
DECISION_A = WS / "results/r23/basalt-prompt/gap-a/decision-a.txt"
SERVED_CHUNK, F0, TMIN = 16384, 16384, 256
PARTS = ("A", "T", "C")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


br = load("basalt_rules", RU)
br.E23 = E_FIX / "strata"        # every config, cfgcheck and the defaults point at the fix engine
gate, read_gates, gs = br.gate, br.read_gates, br.gs


# ================================================================================================ r23_plan.hpp, in Python
def tail_split(n, C, smin, tmin=TMIN):
    """r23::tail_split: (on, a, b, last, why)"""
    if tmin <= 0:
        return False, 0, 0, 0, "off"
    if C <= 0 or n <= C:
        return False, 0, 0, 0, "the prompt is one chunk"
    k = (n + C - 1) // C
    last = n - (k - 1) * C
    r = C + last
    a = min(C, ((r + 1) // 2 + 255) // 256 * 256)
    if last >= smin:
        return False, a, r - a, last, "the last chunk streams every expert"
    if last < tmin:
        return False, a, r - a, last, "the rest is shorter than the switch's minimum"
    if a < smin or r - a < smin:
        return False, a, r - a, last, "the two chunks would be below the stream-all size"
    return True, a, r - a, last, None


def first_chunk(n, C, f0=F0, smin=1024):
    """r23::first_chunk: (on, k, e, rest, why)"""
    if f0 <= 0:
        return False, 0, 0, 0, "off"
    if C <= f0:
        return False, 0, 0, 0, "the chunk is not above the first chunk"
    if n <= C:
        return False, 0, 0, 0, "the prompt is one chunk"
    rest = n - f0
    k = (rest + C - 1) // C
    e = min(C, ((rest + k - 1) // k + 255) // 256 * 256)
    if not (k > 1 or rest >= smin):
        return False, k, e, rest, "the rest would be one staged chunk"
    return True, k, e, rest, None


def selftest():
    # the C++ test's numbers (tests/prefill/r23_plan_test.cpp)
    assert tail_split(16669, 16384, 1792)[:3] == (True, 8448, 8221)
    assert tail_split(16683, 16384, 1024)[:3] == (True, 8448, 8235)
    assert tail_split(66609, 16384, 1792)[:3] == (True, 8960, 8497)
    assert tail_split(33416, 16384, 1792)[:3] == (True, 8704, 8328)
    assert not tail_split(16639, 16384, 1024)[0] and tail_split(16639, 16384, 1024, 255)[0]
    assert tail_split(16683, 1024, 1024)[:4] == (False, 768, 555, 299)
    assert not any(tail_split(n, 1024, 1024)[0] for n in range(1025, 70000, 97))
    assert not first_chunk(66609, 16384)[0]
    assert first_chunk(66616, 20480, smin=1792)[:4] == (True, 3, 16896, 50232)
    assert first_chunk(33187, 21504)[:4] == (True, 1, 16896, 16803)
    assert not first_chunk(17000, 16640, smin=1792)[0] and first_chunk(17000, 16640, smin=512)[0]
    tl = [n - 1 for _, cuts in br.TAIL24 for n in cuts]
    assert sum(tail_split(n, 16384, 1024)[0] for n in tl) == 22, "tail24 at 16384: 22 plan lines"
    assert sum(tail_split(n, 16384, 1792)[0] for n in tl) == 22
    assert sum(tail_split(n, 1024, 1024)[0] for n in tl) == 0, "tail24 at the yardstick's 1024: none (gap a)"
    py = br.load("pf_yardstick", br.PFY)
    l40 = [(p["name"], len(p["ids"]) - 1) for p in br.prompt_set(py, "long40")]
    on40 = [(nm, tail_split(n, 16384, 1024)[1:3]) for nm, n in l40 if tail_split(n, 16384, 1024)[0]]
    assert on40 == [("tf-long64k-17408", (8704, 8703))], on40          # long40 at 16384: one plan line (Karl 11-05 arms)
    assert sum(tail_split(n, 1024, 1024)[0] for _, n in l40) == 0, "long40 at the yardstick's bare auto: none"
    # C40: the 16384 references decide, the 1024 comparison never does (Karl 11-05) - two cases where they disagree
    g = {k: ("PASS", "x") for k in ("build_fix", "e7_B", "logits_B40", "c_lend", "plan_C16", "chunk_C16", "vram_C",
                                    "kl2_C_tail24", "kl3_C_tail24", "kl2_C_long40", "kl3_C_long40")}
    g["c_lend"] = ("PASS", "auto:32768 -> prompt chunk 21504 tokens, a 512-slot ring")
    g["kl2_Cinfo1024_long40"] = g["kl3_Cinfo1024_long40"] = ("FAIL", "[new form] C40 vs ref (1024)")
    pc = lambda gg: [x for x in decide_lines(gg) if x.startswith("PART C ")][0]
    assert pc(g).startswith("PART C ROUNDING-LEVEL"), pc(g)
    g2 = dict(g, kl3_C_long40=("FAIL", "[new form] C40 vs B40_16"), kl2_Cinfo1024_long40=("PASS", "x"),
              kl3_Cinfo1024_long40=("PASS", "x"))
    assert pc(g2).startswith("PART C FAIL") and "kl3_C_long40 FAIL" in pc(g2), pc(g2)
    g3 = {k: v for k, v in g2.items() if k not in ("kl2_C_long40", "kl3_C_long40")}   # the 16384 refs did not run
    assert pc(g3).startswith("PART C NOT DECIDED"), pc(g3)
    assert any(x.startswith("INFO C40") and "FAIL" in x for x in decide_lines(g)), "the 1024 comparison is reported"
    return 0


# ================================================================================================ arm configs
def cfg_fix(out, name, env_add, prefill=None, note=""):
    p, man = br.write_cfg(out, name, json.loads(br.BASE_CFG.read_text()), dict(env_add), prefill=prefill,
                          note=(note + "; " if note else "") + "the r23 fix rerun (engine-r23basalt-fix)")
    c = json.loads(p.read_text())
    c["log"] = str(WS / f"logs/engine-r23fx-{name}.log")     # not gap a's / b's engine-r23-*.log
    p.write_text(json.dumps(c, indent=1) + "\n")
    return man


def cmd_arms(a):
    """the rerun's arms in OUTDIR (= configs/P0210x-h.json + each arm's switches, exe engine-r23basalt-fix): B A T U K KP,
    and with --stack: S; --scan: Cscan (S + FIRST_CHUNK at --prefill auto:32768); --cap N: C (S + FIRST_CHUNK at an
    explicit --prefill N). Then cfgcheck (basalt_rules.py's, against the fix engine)."""
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    man = {n: cfg_fix(out, n, br.ARMS[n]) for n in ("B", "A", "T", "U", "K", "KP")}
    if a.stack is not None:
        parts = [x for x in a.stack.split(",") if x]
        if any(x not in br.ARMS or x == "B" for x in parts):
            print(f"unknown stack part(s) in {a.stack!r}")
            return 2
        env = {}
        for x in parts:
            env.update(br.ARMS[x])
        man["S"] = cfg_fix(out, "S", env, note=f"the stack {'+'.join(parts) or '(empty)'}")
        man["S"]["parts"] = parts
        if a.scan:
            man["Cscan"] = cfg_fix(out, "Cscan", {**env, **br.FIRST_ENV}, prefill="auto:32768",
                                   note="the scan: one start at auto:32768 (auto:N's ceiling is 8192 / 16384 / 32768)")
        if a.cap:
            man["C"] = cfg_fix(out, "C", {**env, **br.FIRST_ENV}, prefill=str(a.cap),
                               note=f"the cap arm on {'+'.join(parts) or 'B'} at an explicit --prefill {a.cap}")
            man["C"]["parts"] = parts
    mp = out / "manifest.json"
    old = json.loads(mp.read_text()) if mp.exists() else {}
    old.update(man)
    old["_base"] = {"path": str(br.BASE_CFG), "sha256": hashlib.sha256(br.BASE_CFG.read_bytes()).hexdigest()}
    mp.write_text(json.dumps(old, indent=1) + "\n")
    print(f"arm configs in {out}: {', '.join(sorted(man))}")
    return br.cmd_cfgcheck(argparse.Namespace(outdir=str(out), gate=a.gate, gates=a.gates))


# ================================================================================================ evidence
LAYOUT_RE = re.compile(r"strata prefill: r23 switches: a layout for (\d+)-token chunks \(stream-all from (\d+) tokens, "
                       r"(\d+) staging slots, a (\d+)-slot ring")


def cmd_chunk(a):
    """the chunk an arm's prompt path was laid out for: its r23 layout lines (a switch arm), else its index.json args"""
    d = Path(a.dir)
    t = (d / "stderr.txt").read_text(errors="replace") if (d / "stderr.txt").exists() else ""
    lay = LAYOUT_RE.findall(t)
    if lay:
        chunks = sorted({int(x[0]) for x in lay})
        ok = chunks == [a.want]
        line = (f"{d.name}: {len(lay)} r23 layout line(s): chunk(s) {chunks}, stream-all {sorted({int(x[1]) for x in lay})}, "
                f"ring {sorted({int(x[3]) for x in lay})} (want chunk {a.want})")
    else:
        try:
            args = json.loads((d / "index.json").read_text())["args"]
        except (OSError, ValueError, KeyError):
            args = []
        pf = br.last_val(args, "--prefill") if args else None
        ok = pf == str(a.want)
        line = (f"{d.name}: no r23 layout line (no r23 switch); --prefill {pf or 'missing'} in its args (want {a.want}; "
                f"the switch arms' layout lines show what it gives)")
        if "auto" in str(pf):
            line += " - an auto chunk on the one-slot yardstick engine is 1024 (nothing lendable)"
            ok = False
    print(line + (" -> PASS" if ok else " -> FAIL"))
    gate(a, "PASS" if ok else "FAIL", line[:300])
    return 0


PLAN_T = re.compile(r"STRATA_PF_TAIL_SPLIT: (\d+) tokens from (\d+): the last (\d+) \(a (\d+)-token chunk and a (\d+)-token "
                    r"rest\) read as chunks of (\d+) and (\d+) tokens")
PLAN_C = re.compile(r"STRATA_PF_FIRST_CHUNK: (\d+) tokens from (\d+): a first chunk of (\d+), then (\d+) chunk\(s\) of at "
                    r"most (\d+) \(the chunk is (\d+)\)")


def cmd_planlines(a):
    """the plan lines of a T or C arm against r23_plan.hpp's formula on n = tokens - 1 (the yardstick's batched read)"""
    d = Path(a.dir)
    t = (d / "stderr.txt").read_text(errors="replace") if (d / "stderr.txt").exists() else ""
    idx = json.loads((d / "index.json").read_text())["requests"] if (d / "index.json").exists() else []
    ns = [r["tokens"] - 1 for r in idx]
    if a.kind == "tail":
        exp = sorted((n, *tail_split(n, a.chunk, a.smin, a.tmin)[1:3]) for n in ns if tail_split(n, a.chunk, a.smin, a.tmin)[0])
        got = sorted((int(m[0]), int(m[5]), int(m[6])) for m in PLAN_T.findall(t) if int(m[3]) == a.chunk and int(m[1]) == 0)
        nall = len(PLAN_T.findall(t))
        na = t.count("STRATA_PF_TAIL_SPLIT not applied")
    else:
        exp = sorted((n, first_chunk(n, a.chunk, a.f0, a.smin)[1], first_chunk(n, a.chunk, a.f0, a.smin)[2]) for n in ns
                     if first_chunk(n, a.chunk, a.f0, a.smin)[0])
        got = sorted((int(m[0]), int(m[3]), int(m[4])) for m in PLAN_C.findall(t) if int(m[5]) == a.chunk and int(m[1]) == 0)
        nall = len(PLAN_C.findall(t))
        na = t.count("STRATA_PF_FIRST_CHUNK not applied")
    ok = bool(idx) and len(exp) > 0 and got == exp and nall == len(got)
    miss = sorted(set(exp) - set(got))
    extra = sorted(set(got) - set(exp))
    line = (f"{d.name}: {len(got)} {a.kind} plan line(s) at chunk {a.chunk} ({nall} in all), the formula (n = tokens - 1, "
            f"stream-all {a.smin}) expects {len(exp)} of {len(idx)} prompts; {na} 'not applied' line(s)"
            + (f"; missing {miss[:4]}" if miss else "") + (f"; not expected {extra[:4]}" if extra else ""))
    print(line + (" -> PASS" if ok else " -> FAIL"))
    gate(a, "PASS" if ok else "FAIL", line[:300])
    return 0


def cmd_lend(a):
    """the scan's chunk: 'prompt chunk auto: N tokens, a R-slot ring' at auto:32768; PASS (prints N) when N > 16384"""
    t = Path(a.log).read_text(errors="replace") if Path(a.log).exists() else ""
    m = re.findall(r"prompt chunk auto: (\d+) tokens, a (\d+)-slot ring", t)
    b = re.findall(r"the prompt path borrows (\d+) CUDA0 cache slots \(([\d.]+) GiB\)", t)
    cs = re.findall(r"expert cache (\d+) slots, ([\d.]+) GiB of VRAM", t)
    lay = LAYOUT_RE.findall(t)
    if not m:
        print(0)
        gate(a, "FAIL", "no 'prompt chunk auto: N tokens' line in the scan's engine log")
        return 1
    n = int(m[-1][0])
    line = (f"auto:32768 -> prompt chunk {n} tokens, a {m[-1][1]}-slot ring; borrows {b[-1][0] if b else '?'} slots "
            f"({b[-1][1] if b else '?'} GiB) of {cs[-1][0] if cs else '?'}; r23 layout lines {[int(x[0]) for x in lay]}")
    ok = n > SERVED_CHUNK
    print(n if ok else 0)
    gate(a, "PASS" if ok else "FAIL", line + ("" if ok else " (no chunk above 16384: FIRST_CHUNK would plan nothing)"))
    return 0


def cmd_stack(a):
    """C's stack: gap a's S_PARTS (decision-a.txt) + this gap's A / T where they passed (decision-fix-provisional.txt)"""
    da = br.read_decision(DECISION_A) if DECISION_A.exists() else {}
    sa = [x for x in str(da.get("S_PARTS", "")).split(",") if x]
    df = Path(a.outdir) / "decision-fix-provisional.txt"
    passed = []
    if df.exists():
        for line in df.read_text().splitlines():
            m = re.match(r"PART (A|T) (EXACT|ROUNDING-LEVEL) ", line)
            if m:
                passed.append(m[1])
    parts = [x for x in ("A", "T", "U", "K", "KP", "G") if x in sa or x in passed]
    print(",".join(parts))
    return 0


def cmd_buildcheck(a):
    """engine-r23basalt-fix as built by work/r23/build-basalt-fix.sh: SHA256, SOURCE at FIX_HEAD on the branch, GATES, TESTS"""
    bad, info = [], []
    exe, sha, src, gts, tst = (E_FIX / x for x in ("strata", "SHA256", "SOURCE", "GATES", "TESTS"))
    if not exe.exists() or not sha.exists():
        bad.append("engine-r23basalt-fix/strata or SHA256 missing")
    else:
        h = hashlib.sha256(exe.read_bytes()).hexdigest()
        if sha.read_text().split()[0] != h:
            bad.append("SHA256 does not match the binary")
        info.append(h[:12])
    s = src.read_text() if src.exists() else ""
    m = re.search(rf"branch {BRANCH} ([0-9a-f]{{40}})", s)
    if not m or not m[1].startswith(FIX_HEAD):
        bad.append(f"SOURCE is not branch {BRANCH} at {FIX_HEAD} ({s.strip()[:120] or 'missing'})")
    g = gts.read_text() if gts.exists() else ""
    for k in ("warnings", "strings"):
        if not re.search(rf"^{k} PASS", g, re.M):
            bad.append(f"GATES {k} not PASS")
    tt = tst.read_text() if tst.exists() else ""
    rows = re.findall(r"^(\S+_test) (PASS|FAIL|MISSING)", tt, re.M)
    if not rows or any(v != "PASS" for _, v in rows) or "r23_plan_test" not in dict(rows):
        bad.append(f"TESTS not all PASS ({', '.join(f'{k} {v}' for k, v in rows) or 'missing'})")
    else:
        info.append(f"{len(rows)} CPU tests PASS")
    line = (f"engine-r23basalt-fix {' '.join(info)} = {s.strip()[:110]}" if not bad else "; ".join(bad))
    print(("BUILD CHECK OK: " if not bad else "BUILD CHECK FAILED: ") + line)
    gate(a, "FAIL" if bad else "PASS", line[:300])
    return 0 if not bad else 1


# ================================================================================================ decision
KL_SETS = {"A": ("tail24", "long40"), "T": ("tail24", "long40"), "C": ("tail24", "long40")}
FORM = "kernel_rule2 + kernel_rule3 (point NLL as INFO; the many-positions bound revoked) on tail24 + long40"
FORM_T = ("kernel_rule2 + kernel_rule3 (point NLL as INFO) on tail24 (T16 vs B16) and long40 (T40_16 vs B40_16), both at "
          "--prefill 16384")


def kl_verdict(g, part):
    form = FORM_T if part == "T" else FORM
    need, miss, fail = [], [], []
    for s_ in KL_SETS[part]:
        need += [f"kl2_{part}_{s_}", f"kl3_{part}_{s_}"]
    for k in need:
        v = gs(g, k)
        if v != "PASS":
            (fail if v == "FAIL" else miss).append(f"{k} {v or 'missing'}")
    if fail:
        return "FAIL", f"{form}: " + "; ".join(fail)
    if miss:
        return "NOT DECIDED", f"{form}: " + "; ".join(miss)
    return "PASS", form


def cmd_decide(a):
    o = Path(a.outdir)
    out = decide_lines(read_gates(o / "gates.txt"), a.provisional)
    (o / ("decision-fix-provisional.txt" if a.provisional else "decision-fix.txt")).write_text("\n".join(out) + "\n")
    print("\n".join(out))
    return 0


def decide_lines(g, provisional=False):
    out = []
    bld = gs(g, "build_fix") == "PASS"
    out.append(f"BUILD {'PASS' if bld else 'FAIL'} (build_fix {gs(g, 'build_fix') or '-'}): {g.get('build_fix', ('', ''))[1][:140]}")
    if "e7_B" not in g and "logits_B40" not in g:
        base = "NOT RUN"
    else:
        base = "PASS" if gs(g, "e7_B") == "PASS" and gs(g, "logits_B40") == "PASS" else "FAIL"
    out.append(f"BASELINE {base} (B on engine-r23basalt-fix = P0210x-h: exact7 vs g17-p210a {gs(g, 'e7_B') or '-'}; long40 vs "
               f"gap 17's p210 {gs(g, 'logits_B40') or '-'}: {g.get('logits_B40', ('', ''))[1][:80]})")
    out.append("NLL information only (Karl 11-05: the many-positions bound is revoked; kernel_rule3's point NLL printed as INFO)")
    void = [k for k, (s_, _) in g.items() if re.match(r"(env|fatal)_", k) and s_ == "FAIL"]
    void_ref = [k for k in void if re.match(r"(env|fatal)_(ref_|B_(pfy|e7))", k)]
    cls = {}
    if not bld or base != "PASS":
        for p in PARTS:
            cls[p] = ("NOT DECIDED", "the build check did not pass" if not bld else
                      ("the baseline did not pass" if base == "FAIL" else "the baseline was not run"))
    else:
        # A: exact, exercised at the served chunk
        ex = [gs(g, k) for k in ("same_A16", "same_A16s", "e7_A")]
        un = [gs(g, k) for k in ("ahead_A16", "ahead_A16s")]
        ch = {k: gs(g, k) for k in ("chunk_A16", "chunk_A16s", "chunk_B16", "chunk_B16s")}
        chunk_ok = all(v == "PASS" for v in ch.values())
        if all(x == "PASS" for x in ex) and all(x == "PASS" for x in un) and chunk_ok:
            cls["A"] = ("EXACT", "tail24 at 16384 24/24 twice (share 0 and the served share), copies read in place in both, "
                                 "exact7 7/7")
        elif all(x == "PASS" for x in ex) and (any(x != "PASS" for x in un) or not chunk_ok):
            cls["A"] = ("NOT DECIDED", "identical, but " + ", ".join(
                [f"{k} {gs(g, k) or 'missing'}" for k in ("ahead_A16", "ahead_A16s") if gs(g, k) != "PASS"] +
                [f"{k} {v or 'missing'}" for k, v in ch.items() if v != "PASS"]) +
                " (UNEXERCISED or not at the served chunk)")
        elif any(x == "FAIL" for x in ex):
            v, t = kl_verdict(g, "A")
            cls["A"] = ("ROUNDING-LEVEL" if v == "PASS" else v,
                        f"not exact ({', '.join(f'{k} {gs(g, k)}' for k in ('same_A16', 'same_A16s', 'e7_A'))}); {t}")
        else:
            cls["A"] = ("NOT DECIDED", ", ".join(f"{k} {gs(g, k) or 'missing'}" for k in
                                                 ("same_A16", "same_A16s", "e7_A", "ahead_A16", "ahead_A16s")))
        # T
        v, t = kl_verdict(g, "T")
        pre = [f"{k} {gs(g, k) or 'missing'}" for k in ("plan_T16", "plan_T40", "chunk_T16", "chunk_T40", "chunk_B16",
                                                         "chunk_B40_16") if gs(g, k) != "PASS"]
        if v == "FAIL":
            cls["T"] = ("FAIL", "; ".join(pre + [t]))
        elif pre or v != "PASS":
            cls["T"] = ("NOT DECIDED", "; ".join(pre + [t]))
        else:
            cls["T"] = ("ROUNDING-LEVEL", f"{g['plan_T16'][1][:70]}; {g['plan_T40'][1][:70]}; {t}")
        # C
        v, t = kl_verdict(g, "C")
        pre = [f"{k} {gs(g, k) or 'missing'}" for k in ("c_lend", "plan_C16", "chunk_C16", "vram_C") if gs(g, k) != "PASS"]
        if any(gs(g, k) == "FAIL" for k in ("c_lend", "vram_C")) or v == "FAIL":
            cls["C"] = ("FAIL", "; ".join(pre + [t]))
        elif pre or v != "PASS":
            cls["C"] = ("NOT DECIDED", "; ".join(pre + [t]))
        else:
            mm = re.search(r"prompt chunk \d+ tokens[^;]*", g["c_lend"][1])
            cls["C"] = ("ROUNDING-LEVEL", f"the scan's {mm[0] if mm else 'chunk ?'}; {t}")
    for p in PARTS:
        vv = [k for k in void if k.split("_")[1] == p] + void_ref
        if vv and cls[p][0] in ("EXACT", "ROUNDING-LEVEL"):
            cls[p] = ("VOID", f"{', '.join(vv)} failed; was {cls[p][0]}")
    claim = {"A": "exact", "T": "rounding", "C": "rounding"}
    for p in PARTS:
        out.append(f"PART {p} {cls[p][0]} ({claim[p]} claimed): {cls[p][1]}")
    out.append(f"FIX_PARTS {','.join(p for p in ('A', 'T') if cls[p][0] in ('EXACT', 'ROUNDING-LEVEL'))}")
    cp = g.get("c_parts", ("", "none"))[1].split(" ")[0]
    out.append(f"C_PARTS {'' if cp in ('none', '-') else cp}")
    m = re.search(r"prompt chunk (\d+) tokens", g.get("c_lend", ("", ""))[1])
    out.append(f"C_CHUNK {m[1] if m and cls['C'][0] == 'ROUNDING-LEVEL' else ''}")
    info = [f"{k} {gs(g, k)} ({g[k][1][:110]})" for k in ("kl2_Cinfo1024_long40", "kl3_Cinfo1024_long40") if k in g]
    out.append("INFO C40 vs gap 8's 1024-chunk long40 references (information only, never decides): " +
               ("; ".join(info) if info else "not run"))
    if void:
        out.append("VOID GATES " + ", ".join(void))
    if provisional:
        out.insert(0, "PROVISIONAL (before C) - not the decision")
    return out


# ================================================================================================ main
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "br":      # basalt_rules.py's own subcommands, with the fix engine set
        sys.argv = [str(RU)] + sys.argv[2:]
        return br.main()
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name, *pos, gates=True):
        p = sp.add_parser(name)
        for x in pos:
            p.add_argument(x)
        if gates:
            p.add_argument("--gate")
            p.add_argument("--gates")
        return p
    p = sub("arms", "outdir")
    p.add_argument("--stack")
    p.add_argument("--scan", action="store_true")
    p.add_argument("--cap", type=int)
    p = sub("chunk", "dir")
    p.add_argument("--want", type=int, required=True)
    p = sub("planlines", "dir")
    p.add_argument("--kind", required=True, choices=["tail", "first"])
    p.add_argument("--chunk", type=int, required=True)
    p.add_argument("--smin", type=int, default=1024)
    p.add_argument("--tmin", type=int, default=TMIN)
    p.add_argument("--f0", type=int, default=F0)
    sub("lend", "log")
    sub("stack", "outdir", gates=False)
    sub("buildcheck")
    sub("selftest", gates=False)
    p = sub("decide", "outdir", gates=False)
    p.add_argument("--provisional", action="store_true")
    a = ap.parse_args()
    f = {"arms": cmd_arms, "chunk": cmd_chunk, "planlines": cmd_planlines, "lend": cmd_lend, "stack": cmd_stack,
         "buildcheck": cmd_buildcheck, "selftest": lambda _: selftest(), "decide": cmd_decide}[a.cmd]
    return f(a)


if __name__ == "__main__":
    sys.exit(main())
