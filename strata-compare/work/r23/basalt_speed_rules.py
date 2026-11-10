#!/usr/bin/env python3
"""basalt_speed_rules.py - r23 (written 2026-11-08, NOT RUN): the rules of THE SPEED GAP for the Basalt prompt-path parts
(work/r23/gap-basalt-speed.sh; results/BACKLOG-1027.md section H; Karl 11-07: "yes, after Phase 5's queue, P028x as the
reference"). Written before any run; the driver freezes this text into the gap's rules.txt, and `decide` flags a change.
NOTHING SWITCHES: P028x stays served. A CANDIDATE is listed for backlog H; adopting it is Karl's call at the next config
change (after item 7 and Phase 5, under his 5 switch conditions).

THE ARMS (configs written by `arms` at run time into results/r23/basalt-prompt/gap-speed/configs/, checked by `cfgcheck`;
each arm has its own engine log logs/engine-r23sp-NAME.log):
  On engine-r23basalt-fix (branch r23-basalt-prompt b8128327d, the build gap fix gated; base configs/P0210x-h.json with
  exe -> engine-r23basalt-fix/strata, server -> strata-r23basalt/serve/server.py):
    B    nothing                  the same-build base (= P0210x-h bit for bit: gap fix's BASELINE)
    A    STRATA_PF_AHEAD=1        class from gap fix (EXACT)
    T    STRATA_PF_TAIL_SPLIT=1   class from gap fix (ROUNDING-LEVEL)
    U    STRATA_HC_UPMIX=1        class from gap a (EXACT; the three fix commits touch only A / T / C)
    C    the C-stack as gap fix decided it: C_PARTS (A,T,U,K,KP) + STRATA_PF_FIRST_CHUNK=1 at --prefill auto:32768. That
         is the serve-mode form whose scan gave the gated chunk C_CHUNK (22528, a 512-slot ring) in gap fix's Cscan start.
         auto:22528 would be auto:16384 (generate.cpp rounds auto:N's ceiling to 8192 / 16384 / 32768); an explicit
         --prefill 22528 is the operator's number, lent without the auto cap: another layout than the one gated
    Bc / Tc / Cc = B / T / C + STRATA_TRACE=1, for B4 only
  On engine-r22p028x (P028x, f4c4f654fb24, the served build; base configs/x28h.json = P028x as served without vision):
    P    nothing                  the serving reference
    PU   STRATA_HC_UPMIX=1        upstream's opt-in switch (cffe31d43), already in P028x's engine
  A fix-build part is priced only when its class is EXACT or ROUNDING-LEVEL; C only when gap fix says ROUNDING-LEVEL
  with C_PARTS and a C_CHUNK above 16384 (`pre`, which also needs gap fix's BUILD PASS and BASELINE PASS).

PU's EXACTNESS ON P028x (run first; it gates PU's speed arms; gap a's form for U):
  e7_P          exact7 P at pin 2500 against P028x's stored exact7 x28h-e7a (10-30; g17-x28h 11-03 and g23p-x28h 11-07
                gave the same 7 hashes and slots): 7/7 MATCHED. INFO for PU (a FAIL is a FLAG: P028x moved since).
  e7_PU         exact7 PU against THIS gap's P: 7/7, slots MATCHED.
  logits_PU40   pf_yardstick long40 PU40 against P028x's stored long40 (results/r22/gap16/pfy/x28h): 0 of 40 differ.
  If e7_P or logits_PU40 is not PASS, P40 (this gap's own P long40) runs when it fits: logits_P40 = P40 vs the stored one
  (INFO, a FAIL is a FLAG), and logits_PU40_P40 = PU40 vs P40 then decides the long40 half.
  PU EXACT = e7_PU PASS and the deciding long40 gate PASS; FAIL = either FAILs; VOID = an env gate of PU's runs failed;
  NOT DECIDED = something missing, or P's own exact7 / P40 engine did not check out. Only EXACT lets PU's speed arms run.
  A not-exact PU is not priced (it would need the KL rule, which this gap does not run).

THE MEASUREMENTS (Basalt gap b's B1 / B2 / B3, plus its B4 as information; every start a fresh test server through
with_server.sh, its engine's environment checked by basalt_rules.py envcheck before it measures):
  B1  Basalt's cold pp16k / pp64k (bp90_client.py), a fresh engine per measurement, 3 passes in turned order (the arms,
      reversed, the arms) over B A T U C P PU. One file per start: bp90/ARM-SET-PASS.jsonl.
  B2  Basalt's decode fixtures (conv, struct, prose), 1 pass, on B C P PU: bp90/ARM-decode-1.jsonl.
  B3  the 9-workload screen (work/r22/abarm.sh: W1-W3, agent x2, research4 x4; T 1.0 / 0.95 / 20 / min-p 0.05, effort
      medium; a warm-up first), 3 passes in turned order (B C P PU / PU P C B / P B PU C) on B C P PU: speed/ARMkS.*.
  B4  the chat-cache trade of T and C (round-11 #693; basalt_rules.py chat3 / chatrep) on Bc Tc Cc: REPORTED only.

WHICH STARTS COUNT:
  - An arm is VOID when one of its B1 / B2 / B3 starts failed its env gate (env_ARM_STEP) or showed a fatal line
    (fatal_ARM_STEP: a fatal GPU error, a stall, an engine restart, a non-finite value): gap b's rule. A void base (B, or
    P for the P028x comparisons) makes every verdict against it VOID.
  - A start is left out (the arm stays judged on the others) when a foreign GPU user was seen before or during it
    (foreign_ARM_STEP FAIL: an engine process by exact name, or an NVIDIA compute process of 512 MiB or more, whose binary
    is not in engine-r23basalt-fix/ or engine-r22p028x/), or, for C, when its engine's "prompt chunk auto: N tokens" line
    does not say C_CHUNK (chunk_C_STEP FAIL: not the gated layout; a FLAG names how often). The driver moves such a
    start's files to void/; a FAIL gate whose files are still in place is left out too (B1 / B2) or makes the screen NOT
    DECIDED (B3).
  - The other arms' chunk lines are INFO.

THE RULES (gap b's thresholds, unchanged):
  B1 gain of X against a reference R (R = B for A T U C; R = P for PU; and R = P for every fix-build arm as "vs P028x"):
     change = mean_X / mean_R - 1 per fixture; noise = the larger of the two arms' pass spreads (max / min - 1).
     Targets (basalt_rules.TARGETS): A, T -> pp16k; C -> pp64k; U, PU -> either. GAIN = a target fixture above
     +max(noise, 1.0 %) and no fixture below -noise. Each fixture needs 2 or more counted passes of both arms, else NOT
     DECIDED.
  B2 decode (gap b's): each fixture's decode of X >= R's x (1 - noise), noise = gap 17's 3-pass spread of that fixture on
     R's build (results/r22/gap17/bp90/cold-H = P0210x-h for B, cold-M = P028x for P; 3 % when missing).
  B3 screen (gap b's B3 under the 11-07 measurement amendment, work/r22/g17_rules.py "11-07 park amendment", applied
     here explicitly - this gap starts after 2026-11-07 14:00):
     - per-workload no-loss (Karl 11-03; g17 wl_noloss): per workload, decode and prompt tok/s each, X's pass mean >= R's
       x (1 - the larger of the two arms' spreads there); the per-workload prompt is the engine clock minus the
       chat-cache save (prompt tokens / (engine prompt ms - the `chat cache: parked` ms before that request));
     - the screen's prompt geomean over the passes not below R's (gap b's strict form), on the client clock minus the save;
     - the chat-cache save as its own line (g17 save_rule: its own noise, its two levels taken into account): FAIL is a
       loss, NOT DECIDED leaves B3 undecided, NOT JUDGED (no save) is INFO;
     - the outside-engine flag (INFO, on the no-loss line): a workload whose client TTFT - engine prompt ms is above R's
       mean by more than the spread in every pass of X. It never changes a verdict;
     - 3 complete passes of both arms, every record paired with its engine-log line, else NOT DECIDED.
  VRAM (C): vram_C = every C start's guard line: 5080 free >= 300 MiB and MemAvailable >= 12 GiB throughout.

VERDICTS (decide writes OUTDIR/decision.txt and decision.json):
  A, T, U (fix build, vs B)  CANDIDATE = class EXACT / ROUNDING-LEVEL + B1 GAIN; NO GAIN = without the gain; VOID; NOT
                             DECIDED; NOT PRICED (class).
  C (fix build, vs B)        gap b's stack rule: CANDIDATE = B1 GAIN + B2 PASS + B3 PASS + vram_C PASS; NO GAIN = B2, B3,
                             VRAM pass without the gain; FAIL (screen / decode / VRAM); VOID; NOT DECIDED; NOT PRICED.
  PU (P028x, vs P)           NOT PRICED unless EXACT; then as U: CANDIDATE = B1 GAIN (gap b's single-part rule). Its B2 and
                             B3 against P are REPORTED beside it (Karl's switch conditions need the screen at the switch).
  vs P028x, every fix-build arm (A T U C, and B as INFO): B1 against P with the same threshold -> GAIN OVER P028x /
                             NOT ABOVE P028x / BELOW P028x (a fixture below -noise) / NOT DECIDED / VOID; C also B3 vs P
                             (reported) and B2 vs P (INFO).
  SPEED CANDIDATES FOR BACKLOG H = the arms whose verdict is CANDIDATE, each with its vs-P028x line. A fix-build part's
  CANDIDATE is its own effect on its build; backlog H also needs a priced gain over P028x before adoption (the vs-P028x
  line) and the port-base conditions there.

Subcommands: pre, arms, cfgcheck, chunk, puexact, rules, decide, selftest. Python: .venv/bin/python -I -B.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import statistics as st
import sys
from pathlib import Path

sys.dont_write_bytecode = True     # it loads modules from trees it must not write to (work/r22, work/r23)
WS = Path("/home/USER/ai-speed-testing/strata-compare")
FR = WS / "work/r23/basalt_fix_rules.py"
G17 = WS / "work/r22/g17_rules.py"
E_FIX = WS / "engine-r23basalt-fix/strata"
SRV_FIX = WS / "strata-r23basalt/serve/server.py"
E28 = WS / "engine-r22p028x/strata"
SRV28 = WS / "strata-r22p028x/serve/server.py"
BASE_FIX = WS / "configs/P0210x-h.json"
BASE_28 = WS / "configs/x28h.json"
DECISION_FIX = WS / "results/r23/basalt-prompt/gap-fix/decision-fix.txt"
DECISION_A = WS / "results/r23/basalt-prompt/gap-a/decision-a.txt"
G17_BP90 = {"fix": WS / "results/r22/gap17/bp90/cold-H.jsonl", "p028x": WS / "results/r22/gap17/bp90/cold-M.jsonl"}
C_PREFILL = "auto:32768"
SERVED_CHUNK = 16384
FIX_ARMS = ("B", "A", "T", "U", "C")
P28_ARMS = ("P", "PU")
BUILD_OF = {**{a: "fix" for a in FIX_ARMS + ("Bc", "Tc", "Cc")}, **{a: "p028x" for a in P28_ARMS}}
REF_OF = {"A": "B", "T": "B", "U": "B", "C": "B", "PU": "P"}
NAMES = {"A": "A (STRATA_PF_AHEAD=1)", "T": "T (STRATA_PF_TAIL_SPLIT=1)", "U": "U (STRATA_HC_UPMIX=1, fix build)",
         "C": "the C-stack", "PU": "U on P028x (P028x + STRATA_HC_UPMIX=1)"}
CHUNK_RE = re.compile(r"prompt chunk auto: (\d+) tokens, a (\d+)-slot ring")
BORROW_RE = re.compile(r"the prompt path borrows (\d+) CUDA0 cache slots \(([\d.]+) GiB\)")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


fx = load("basalt_fix_rules", FR)       # read-only; it loads basalt_rules.py with the fix engine as its default exe
br = fx.br
g17 = load("g17_rules", G17)
gs, read_gates = br.gs, br.read_gates
TARGETS = {**br.TARGETS, "PU": ["pp16k", "pp64k"]}
SPREAD = br.spread


def gate(a, status, detail):
    br.gate(a, status, detail)


def rules_text():
    return __doc__.strip() + "\n"


# ================================================================================================ before the gap
def read_pre(dfix, da):
    """(ok, why, info) from gap fix's and gap a's decision files"""
    df = br.read_decision(dfix) if Path(dfix).exists() else {}
    dd = br.read_decision(da) if Path(da).exists() else {}
    info = {}
    if not df:
        return False, f"{dfix} missing", info
    if not str(df.get("BUILD", "")).startswith("PASS") or not str(df.get("BASELINE", "")).startswith("PASS"):
        return False, f"gap fix: BUILD {str(df.get('BUILD', 'missing'))[:40]}, BASELINE {str(df.get('BASELINE', 'missing'))[:40]}", info
    m = re.search(r"engine-r23basalt-fix ([0-9a-f]{12})", str(df.get("BUILD", "")))
    info["FIX_SHA"] = m[1] if m else ""
    if not info["FIX_SHA"]:
        return False, "gap fix's BUILD line names no engine-r23basalt-fix sha", info
    for p in ("A", "T", "C"):
        info[f"CLASS_{p}"] = df.get(f"PART {p}", "missing")
    info["CLASS_U"] = dd.get("PART U", "missing")
    cp = [x for x in str(df.get("C_PARTS", "")).strip().split(",") if x]
    cc = str(df.get("C_CHUNK", "")).strip()
    bad_cp = [x for x in cp if x not in br.ARMS or x == "B"]
    info["C_PARTS"] = ",".join(cp)
    info["C_CHUNK"] = cc
    arms = ["B"] + [p for p in ("A", "T", "U") if info[f"CLASS_{p}"] in ("EXACT", "ROUNDING-LEVEL")]
    if info["CLASS_C"] == "ROUNDING-LEVEL" and cp and not bad_cp and cc.isdigit() and int(cc) > SERVED_CHUNK:
        arms.append("C")
    info["ARMS_FIX"] = " ".join(arms)
    if len(arms) == 1:
        return False, "no Basalt part to price (A, T, U, C all without an EXACT / ROUNDING-LEVEL class)", info
    return True, "gap fix passed BUILD and BASELINE", info


def cmd_pre(a):
    ok, why, info = read_pre(a.decision_fix, a.decision_a)
    print(("PRE OK: " if ok else "PRE REFUSED: ") + why + (f"; priced on the fix build: {info.get('ARMS_FIX')}"
                                                           f" (A {info.get('CLASS_A')}, T {info.get('CLASS_T')}, U {info.get('CLASS_U')}, "
                                                           f"C {info.get('CLASS_C')} {info.get('C_PARTS') or '-'} @ {info.get('C_CHUNK') or '-'})"
                                                           if info.get("ARMS_FIX") else ""))
    for k, v in info.items():
        print(f"{k}={v}")
    return 0 if ok else 1


# ================================================================================================ arm configs
def arm_spec(name, cparts):
    """(build, env delta, --prefill or None, note)"""
    cenv = {}
    for x in cparts:
        cenv.update(br.ARMS[x])
    cenv.update(br.FIRST_ENV)
    spec = {"B": ({}, None, "the same-build base"), "A": (dict(br.ARMS["A"]), None, "part A"),
            "T": (dict(br.ARMS["T"]), None, "part T"), "U": (dict(br.ARMS["U"]), None, "part U"),
            "C": (dict(cenv), C_PREFILL, f"the C-stack {'+'.join(cparts)} + FIRST_CHUNK at {C_PREFILL} (the scan's serve form)"),
            "Bc": (dict(br.TRACE_ENV), None, "B4 chat-cache trade (trace)"),
            "Tc": ({**br.ARMS["T"], **br.TRACE_ENV}, None, "B4 chat-cache trade (trace)"),
            "Cc": ({**cenv, **br.TRACE_ENV}, C_PREFILL, "B4 chat-cache trade (trace)"),
            "P": ({}, None, "the serving reference (P028x as served, without vision)"),
            "PU": ({"STRATA_HC_UPMIX": "1"}, None, "U on P028x")}[name]
    return (BUILD_OF[name],) + spec


def base_of(build):
    return (BASE_FIX, E_FIX, SRV_FIX) if build == "fix" else (BASE_28, E28, SRV28)


def cmd_arms(a):
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    cparts = [x for x in (a.cparts or "").split(",") if x]
    if any(x not in br.ARMS or x == "B" for x in cparts):
        print(f"unknown C part(s) in {a.cparts!r}")
        return 2
    names = list(a.names.split(",")) if a.names else ["B", "A", "T", "U", "Bc", "Tc", "P", "PU"] + (["C", "Cc"] if cparts else [])
    man = {}
    for n in names:
        build, env_add, pf, note = arm_spec(n, cparts)
        base_p, exe, srv = base_of(build)
        c = json.loads(base_p.read_text())
        c["_comment"] = (f"r23 Basalt speed gap (work/r23/basalt_speed_rules.py arms, from {base_p.relative_to(WS)}): arm {n}, "
                         f"{note}; exe {exe.parent.name}; adds {env_add or 'nothing'}" + (f", --prefill {pf}" if pf else "")
                         + ". Measurement only, never served.")
        c["exe"], c["server"] = str(exe), str(srv)
        c["log"] = str(WS / f"logs/engine-r23sp-{n}.log")
        c["env"].update(env_add)
        if pf:
            c["args"][c["args"].index("--prefill") + 1] = pf
        (out / f"{n}.json").write_text(json.dumps(c, indent=1) + "\n")
        man[n] = {"build": build, "env": env_add, "prefill": pf, "base": str(base_p),
                  "base_sha256": hashlib.sha256(base_p.read_bytes()).hexdigest()}
        if n in ("C", "Cc"):
            man[n]["parts"] = cparts
            man[n]["chunk"] = a.cchunk
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(f"arm configs in {out}: {', '.join(names)}")
    return cmd_cfgcheck(argparse.Namespace(outdir=str(out), gate=a.gate, gates=a.gates))


def cmd_cfgcheck(a):
    """every arm config = its base (P0210x-h or x28h) + exactly its manifest delta (exe, server, log, comment, env keys,
    --prefill); no base sets a part's or a diagnostic's switch; the deltas are the arm's own"""
    out = Path(a.outdir)
    man = json.loads((out / "manifest.json").read_text())
    bad = []
    for n, m in man.items():
        cparts = m.get("parts", [])
        build, env_add, pf, _ = arm_spec(n, cparts)
        base_p, exe, srv = base_of(build)
        if m["build"] != build or m["env"] != env_add or m.get("prefill") != pf:
            bad.append(f"{n}: manifest is not the arm's own delta")
        base = json.loads(base_p.read_text())
        if hashlib.sha256(base_p.read_bytes()).hexdigest() != m.get("base_sha256"):
            bad.append(f"{n}: {base_p.name} changed since the configs were written")
        try:
            c = json.loads((out / f"{n}.json").read_text())
        except (OSError, ValueError):
            bad.append(f"{n}: config missing")
            continue
        if c.get("exe") != str(exe) or c.get("server") != str(srv):
            bad.append(f"{n}: exe/server")
        if c.get("log") != str(WS / f"logs/engine-r23sp-{n}.log"):
            bad.append(f"{n}: log")
        if c.get("env") != {**base["env"], **env_add}:
            bad.append(f"{n}: env differs from {base_p.name} + {env_add}")
        aw = list(base["args"])
        if pf:
            aw[aw.index("--prefill") + 1] = pf
        if c.get("args") != aw:
            bad.append(f"{n}: args")
        for k in set(base) | set(c):
            if k not in ("_comment", "exe", "server", "log", "env", "args") and base.get(k) != c.get(k):
                bad.append(f"{n}: {k}")
        stray = [k for k in base["env"] if k in br.R23_OWN]   # (P0210x-h pins STRATA_GDN_TC / _CONVL2 = 0 itself)
        if stray:
            bad.append(f"{base_p.name} itself sets {stray}")
        if build == "p028x" and base.get("exe") != str(E28):
            bad.append(f"{base_p.name} does not name engine-r22p028x")
    line = ("CONFIG CHECK OK: " + ", ".join(sorted(man)) + " = P0210x-h (fix build) / x28h (P028x) + their switches only"
            if not bad else "CONFIG CHECK FAILED: " + "; ".join(sorted(set(bad))))
    print(line)
    gate(a, "FAIL" if bad else "PASS", line[:300])
    return 1 if bad else 0


# ================================================================================================ evidence per start
def cmd_chunk(a):
    """an engine start's prompt chunk: its 'prompt chunk auto: N tokens, a R-slot ring' line; PASS when N = --want (C);
    with --info only reported"""
    t = Path(a.log).read_text(errors="replace") if Path(a.log).exists() else ""
    m, b = CHUNK_RE.findall(t), BORROW_RE.findall(t)
    if not m:
        line = f"{Path(a.log).name}: no 'prompt chunk auto' line (want {a.want})"
        status = "INFO" if a.info else "FAIL"
    else:
        n = int(m[-1][0])
        line = (f"{Path(a.log).name}: prompt chunk {n} tokens, a {m[-1][1]}-slot ring; borrows {b[-1][0] if b else '?'} slots "
                f"({b[-1][1] if b else '?'} GiB) (want {a.want})")
        status = "INFO" if a.info else ("PASS" if n == a.want else "FAIL")
    print(f"{line} -> {status}")
    gate(a, status, line[:300])
    return 0


def pu_exact(g):
    """(verdict, text, flags) of PU's exactness on P028x from the gates"""
    flags = []
    if gs(g, "e7_P") == "FAIL":
        flags.append(f"P028x's exact7 today differs from its stored x28h-e7a (e7_P FAIL): {g['e7_P'][1][:100]}")
    if gs(g, "logits_P40") == "FAIL":
        flags.append(f"P028x's long40 today differs from gap 16's stored one (logits_P40): {g['logits_P40'][1][:100]}")
    void = [k for k in ("env_PU_e7", "env_PU_pfy-PU40") if gs(g, k) == "FAIL"]
    if void:
        return "VOID", f"{', '.join(void)} failed (PU's engine was not as configured)", flags
    if gs(g, "env_P_e7") != "PASS":
        return "NOT DECIDED", f"the reference exact7 P did not check out (env_P_e7 {gs(g, 'env_P_e7') or 'missing'})", flags
    e7 = gs(g, "e7_PU")
    if "logits_PU40_P40" in g:
        if gs(g, "env_P_pfy-P40") != "PASS":
            return "NOT DECIDED", f"P40's engine did not check out (env_P_pfy-P40 {gs(g, 'env_P_pfy-P40') or 'missing'})", flags
        lk, src = "logits_PU40_P40", "this gap's P40"
    else:
        lk, src = "logits_PU40", "gap 16's stored x28h long40"
    l40 = gs(g, lk)
    txt = (f"exact7 PU vs this gap's P {e7 or 'missing'} ({g.get('e7_PU', ('', ''))[1][:60]}); long40 PU40 vs {src} "
           f"{l40 or 'missing'} ({g.get(lk, ('', ''))[1][:70]})")
    if "FAIL" in (e7, l40):
        return "FAIL", txt, flags
    if e7 == "PASS" and l40 == "PASS":
        return "EXACT", txt, flags
    return "NOT DECIDED", txt, flags


def cmd_puexact(a):
    g = read_gates(Path(a.outdir) / "gates.txt")
    v, t, fl = pu_exact(g)
    line = f"PU on P028x: {v}: {t}" + (f"; FLAG {' | '.join(fl)}" if fl else "")
    print(line)
    gate(a, "PASS" if v == "EXACT" else v.replace(" ", "-"), line[:300])
    print(v)
    return 0


# ================================================================================================ the numbers
def excluded(g, arm, step):
    """a start left out: a foreign GPU user, or (C) not the gated chunk"""
    why = [k for k in (f"foreign_{arm}_{step}", f"chunk_{arm}_{step}") if gs(g, k) == "FAIL"]
    return why


def arm_void(g, arm):
    return [k for k, (s_, _) in g.items() if s_ == "FAIL" and re.match(rf"(env|fatal)_{re.escape(arm)}_(bp|scr)", k)]


def bp_vals(o, g, arm, set_, test, key):
    """the counted starts' values: [(pass, value)]"""
    out = []
    for k in (1, 2, 3):
        p = Path(o) / "bp90" / f"{arm}-{set_}-{k}.jsonl"
        if not p.exists() or excluded(g, arm, f"bp{k}{set_}"):
            continue
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("test") == test and r.get(key):
                    out.append((k, r[key]))
    return out


def gain(o, g, arm, ref, targets=None):
    """gap b's B1 gain of ARM against REF: (have, hit, floor_ok, text, nums)"""
    tg = TARGETS.get(arm, ["pp16k", "pp64k"]) if targets is None else targets
    out, hit, floor_ok, have, nums = [], False, True, True, {}
    for fx_ in ("pp16k", "pp64k"):
        b = [v for _, v in bp_vals(o, g, ref, fx_, fx_, "prompt_tps")]
        x = [v for _, v in bp_vals(o, g, arm, fx_, fx_, "prompt_tps")]
        if len(b) < 2 or len(x) < 2:
            have = False
            out.append(f"{fx_}: {arm} {len(x)} / {ref} {len(b)} counted passes - not priced")
            continue
        d = st.mean(x) / st.mean(b) - 1
        noise = max(SPREAD(b), SPREAD(x))
        t = fx_ in tg
        above, below = d > max(noise, 0.010), d < -noise
        hit |= t and above
        floor_ok &= not below
        nums[fx_] = {"x": round(st.mean(x), 1), "ref": round(st.mean(b), 1), "change": round(d, 5), "noise": round(noise, 5),
                     "passes": [len(x), len(b)], "target": t}
        out.append(f"{fx_}{'*' if t else ''}: {st.mean(x):,.1f} vs {ref} {st.mean(b):,.1f} tok/s ({100 * d:+.1f} %; noise "
                   f"{100 * noise:.1f} %; {len(x)}/{len(b)} passes)" + (" above +max(noise, 1 %)" if above else "")
                   + (" BELOW -noise" if below else ""))
    return have, hit, floor_ok, "; ".join(out), nums


def decode_check(o, g, arm, ref):
    """gap b's B2: each decode fixture of ARM >= REF's x (1 - gap 17's 3-pass spread on REF's build)"""
    src = G17_BP90["p028x" if BUILD_OF.get(ref) == "p028x" else "fix"]
    h = [json.loads(x) for x in src.read_text().splitlines() if x.strip()] if src.exists() else []
    out, ok, have = [], True, True
    for t in ("conv", "struct", "prose"):
        b = [v for _, v in bp_vals(o, g, ref, "decode", t, "decode_tps")]
        x = [v for _, v in bp_vals(o, g, arm, "decode", t, "decode_tps")]
        hv = [r["decode_tps"] for r in h if r.get("test") == t and r.get("decode_tps")]
        noise = SPREAD(hv) if len(hv) > 1 else 0.03
        if not b or not x:
            have = False
            out.append(f"{t}: missing")
            continue
        d = st.mean(x) / st.mean(b) - 1
        ok &= d >= -noise
        out.append(f"{t} {100 * d:+.1f} % (noise {100 * noise:.1f} %{'' if len(hv) > 1 else ', default'})")
    return have, ok, "; ".join(out)


def screen(o, g, arm, ref):
    """gap b's B3 (basalt_rules.screen) against REF, under the 11-07 amendment (forced: this gap starts after it):
    (True / False / None, text)"""
    o = Path(o)
    left = [f"{a_}{k}" for a_ in (arm, ref) for k in (1, 2, 3) if excluded(g, a_, f"scr{k}")
            and (o / "speed" / f"{a_}{k}n.jsonl").exists()]
    if left:
        return None, f"screen: void pass(es) {', '.join(left)} still in speed/ - not decided"
    r, x = g17.screen_passes(o, ref, amended=True), g17.screen_passes(o, arm, amended=True)
    if len(r) < 3 or len(x) < 3:
        prob = g17.pair_problems(o, arm) + g17.pair_problems(o, ref)
        return None, (f"screen: {ref} {len(r)} / {arm} {len(x)} complete passes of 3"
                      + (f" (engine-log pairing: {'; '.join(prob[:3])})" if prob else ""))
    wl_ok, wl_line = g17.wl_noloss(o, arm, ref=ref, amended=True)
    pb, px = br.gm([v[1] for v in r.values()]), br.gm([v[1] for v in x.values()])
    db, dx = br.gm([v[0] for v in r.values()]), br.gm([v[0] for v in x.values()])
    txt = (f"screen prompt geomean {100 * (px / pb - 1):+.2f} % vs {ref} ({'not below' if px >= pb else 'BELOW'}; client clock "
           f"minus the save), decode {100 * (dx / db - 1):+.2f} %; {wl_line}")
    if wl_ok is None:
        return None, txt
    ok = bool(wl_ok) and px >= pb
    sv, sl = g17.save_rule(o, arm, ref, amended=True)
    if sv is not None:
        txt += "; " + sl[0]
        if sv == "FAIL":
            ok = False
        elif sv == "NOT DECIDED":
            return None, txt
    return ok, txt


def vs_status(have, hit, floor_ok, void):
    if void:
        return "VOID"
    if not have:
        return "NOT DECIDED"
    return "GAIN OVER P028x" if hit and floor_ok else ("BELOW P028x" if not floor_ok else "NOT ABOVE P028x")


# ================================================================================================ the decision
def cmd_decide(a):
    o = Path(a.outdir)
    g = read_gates(o / "gates.txt")
    ok_pre, why_pre, info = read_pre(a.decision_fix, a.decision_a)
    flags, res = [], {}
    rp = o / "rules.txt"
    rsha = hashlib.sha256(rp.read_bytes()).hexdigest()[:12] if rp.exists() else "missing"
    if not rp.exists() or rp.read_text() != rules_text():
        flags.append("the rule text differs from the one frozen at the gap's start (rules.txt " + rsha + ")")
    if not ok_pre:
        flags.append(f"gap fix's decision no longer passes pre: {why_pre}")
    priced = info.get("ARMS_FIX", "").split()
    cc = int(info["C_CHUNK"]) if str(info.get("C_CHUNK", "")).isdigit() else None
    pux, pux_t, pux_fl = pu_exact(g)
    flags += pux_fl
    if gs(g, "pu_exact") and (gs(g, "pu_exact") == "PASS") != (pux == "EXACT"):
        flags.append(f"the driver's pu_exact gate ({gs(g, 'pu_exact')}) differs from the rules' verdict ({pux})")
    cbad = sorted(k for k, (s_, _) in g.items() if k.startswith("chunk_C_") and s_ == "FAIL")
    if cbad:
        flags.append(f"C's served form did not give the gated chunk {cc} in {len(cbad)} start(s): {', '.join(cbad)} - left out")
    fgn = sorted(k for k, (s_, _) in g.items() if k.startswith("foreign_") and s_ == "FAIL")
    if fgn:
        flags.append(f"start(s) left out for a foreign GPU user: {', '.join(fgn)}")
    void_b, void_p = arm_void(g, "B"), arm_void(g, "P")
    lines = []
    for arm in ("A", "T", "U", "C", "PU"):
        ref = REF_OF[arm]
        if arm == "PU":
            cls = f"exactness on P028x {pux}"
            if pux != "EXACT":
                res[arm] = {"verdict": "NOT PRICED", "why": f"PU's exactness on P028x: {pux}: {pux_t}"}
                lines.append(f"PRICE PU NOT PRICED (exactness on P028x {pux}: {pux_t})")
                continue
        else:
            cls = info.get(f"CLASS_{arm}", "missing")
            if arm not in priced:
                why = f"gap fix / gap a class {cls}" + (f", C_PARTS {info.get('C_PARTS') or '-'}, C_CHUNK "
                                                         f"{info.get('C_CHUNK') or '-'}" if arm == "C" else "")
                res[arm] = {"verdict": "NOT PRICED", "why": why}
                lines.append(f"PRICE {arm} NOT PRICED ({why})")
                continue
        vv = arm_void(g, arm) + (void_b if ref == "B" else void_p)
        have, hit, floor_ok, gl, nums = gain(o, g, arm, ref)
        extra, extra_ok = [], True
        rec = {"class": cls, "ref": ref, "b1": nums, "b1_text": gl}
        if arm == "C":
            h2, ok2, l2 = decode_check(o, g, "C", "B")
            ok3, l3 = screen(o, g, "C", "B")
            vr = gs(g, "vram_C")
            extra += [f"B2 decode {('PASS' if ok2 else 'FAIL') if h2 else 'MISSING'}: {l2}",
                      f"B3 {('PASS' if ok3 else 'FAIL') if ok3 is not None else 'NOT DECIDED'}: {l3}",
                      f"vram/mem in every C start {vr or 'missing'}"]
            extra_ok = h2 and ok2 and bool(ok3) and vr == "PASS"
            have &= h2 and ok3 is not None and vr in ("PASS", "FAIL")
            rec.update({"b2": [h2, ok2, l2], "b3": [ok3, l3], "vram_C": vr})
        if vv:
            v = "VOID"
        elif not have:
            v = "NOT DECIDED"
        elif arm == "C":
            v = "CANDIDATE" if hit and floor_ok and extra_ok else ("NO GAIN" if extra_ok else "FAIL (screen / decode / VRAM)")
        else:
            v = "CANDIDATE" if hit and floor_ok else "NO GAIN"
        if arm == "PU":   # reported beside PU's verdict (gap b's single-part rule decides it on B1)
            h2, ok2, l2 = decode_check(o, g, "PU", "P")
            ok3, l3 = screen(o, g, "PU", "P")
            extra += [f"(reported) B2 decode vs P {('PASS' if ok2 else 'FAIL') if h2 else 'MISSING'}: {l2}",
                      f"(reported) B3 vs P {('PASS' if ok3 else 'FAIL') if ok3 is not None else 'NOT DECIDED'}: {l3}"]
            rec.update({"b2": [h2, ok2, l2], "b3": [ok3, l3]})
        vsp = ""
        if arm != "PU":   # the fix-build arms against the serving reference
            h_, hit_, fl_, gl_, nums_ = gain(o, g, arm, "P")
            vs = vs_status(h_, hit_, fl_, arm_void(g, arm) + void_p)
            vsp = f"; vs P028x {vs}: B1 {gl_}"
            rec.update({"vs_p028x": vs, "vs_p028x_b1": nums_})
            if arm == "C":
                ok3p, l3p = screen(o, g, "C", "P")
                h2p, ok2p, l2p = decode_check(o, g, "C", "P")
                vsp += (f"; (reported) B3 vs P {('PASS' if ok3p else 'FAIL') if ok3p is not None else 'NOT DECIDED'}: {l3p}"
                        f"; (info) B2 decode vs P {('PASS' if ok2p else 'FAIL') if h2p else 'MISSING'}: {l2p}")
                rec.update({"vs_p028x_b3": [ok3p, l3p]})
        rec["verdict"] = v
        res[arm] = rec
        lines.append(f"PRICE {arm} {v} ({cls}; vs {ref}): B1 {gl}" + ("; " + "; ".join(extra) if extra else "")
                     + (f"; void: {', '.join(vv)}" if vv else "") + vsp)
    # INFO: the build difference, B (fix build) against P028x
    h_, hit_, fl_, gl_, nums_ = gain(o, g, "B", "P", targets=[])
    ok3b, l3b = screen(o, g, "B", "P")
    info_b = (f"INFO B (engine-r23basalt-fix, no switch) vs P028x: B1 {gl_}; B3 "
              f"{('PASS' if ok3b else 'FAIL') if ok3b is not None else 'NOT DECIDED'}: {l3b}")
    chat = o / "chat" / "chat-trade.txt"
    b4 = ("B4 chat-cache trade (reported, Karl decides): " + " | ".join(chat.read_text().splitlines())) if chat.exists() \
        else "B4 chat-cache trade: not run"
    cands = []
    for arm in ("A", "T", "U", "C", "PU"):
        if res.get(arm, {}).get("verdict") == "CANDIDATE":
            r_ = res[arm]
            tg = ", ".join(f"{k} {100 * v['change']:+.1f} %" for k, v in r_["b1"].items() if v["target"])
            extra_ = (f"; vs P028x {r_['vs_p028x']}" if "vs_p028x" in r_ else "")
            if arm == "PU":
                extra_ += f"; B3 vs P (reported) {'PASS' if r_['b3'][0] else ('FAIL' if r_['b3'][0] is False else 'NOT DECIDED')}"
            cands.append(f"{NAMES[arm]} ({tg} vs {r_['ref']}{extra_})")
    head = [f"SPEED GAP for backlog H (work/r23/gap-basalt-speed.sh; rules work/r23/basalt_speed_rules.py, frozen {rsha}): "
            f"B1 / B2 / B3 of Basalt gap b with its thresholds, under the 11-07 measurement amendment",
            "SPEED CANDIDATES FOR BACKLOG H: " + ("; ".join(cands) if cands else "none"),
            f"fix build engine-r23basalt-fix {info.get('FIX_SHA') or '?'}: A {info.get('CLASS_A')}, T {info.get('CLASS_T')}, "
            f"U {info.get('CLASS_U')} (gap a), C {info.get('CLASS_C')} (C_PARTS {info.get('C_PARTS') or '-'}, chunk "
            f"{info.get('C_CHUNK') or '-'}, served as {C_PREFILL}); P028x f4c4f654fb24",
            f"PU EXACTNESS on P028x: {pux}: {pux_t}"]
    tail = [info_b, b4] + ([f"FLAG {x}" for x in flags]) + [
        "NOTHING SWITCHES: P028x stays served. A CANDIDATE joins backlog H; adopting it is Karl's call at the next config "
        "change (after item 7 and Phase 5, his 5 switch conditions; A, T, C also need the port-base steps of section H)."]
    txt = "\n".join(head + lines + tail) + "\n"
    (o / "decision.txt").write_text(txt)
    (o / "decision.json").write_text(json.dumps({"rules_sha": rsha, "pre": info, "pu_exact": [pux, pux_t],
                                                 "arms": res, "candidates": cands, "flags": flags,
                                                 "info_b_vs_p": [nums_, ok3b, l3b]}, indent=1, default=str) + "\n")
    if not getattr(a, "quiet", False):
        print(txt, end="")
    return 0


def cmd_rules(a):
    Path(a.out).write_text(rules_text())
    print(f"rules frozen: {a.out} sha {hashlib.sha256(rules_text().encode()).hexdigest()[:12]}")
    return 0


# ================================================================================================ the selftest
def selftest(scratch):
    """synthetic data only (no GPU, no engine, no gap component): everything under SCRATCH"""
    sc = Path(scratch)
    if sc.exists():
        shutil.rmtree(sc)
    sc.mkdir(parents=True)
    fails = []

    def check(name, cond, detail=""):
        print(f"{'ok  ' if cond else 'FAIL'} {name}" + (f": {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    def ns(**k):
        return argparse.Namespace(**k)
    # ---- pre on the real decision files, and on synthetic ones
    ok, why, info = read_pre(DECISION_FIX, DECISION_A)
    check("pre real", ok and info["ARMS_FIX"] == "B A T U C" and info["C_PARTS"] == "A,T,U,K,KP" and info["C_CHUNK"] == "22528"
          and info["FIX_SHA"] == "0cb2a597cb14" and info["CLASS_U"] == "EXACT", f"{why} {info}")
    real = DECISION_FIX.read_text()
    (sc / "dfix-basefail.txt").write_text(real.replace("BASELINE PASS", "BASELINE FAIL"))
    check("pre baseline fail refuses", not read_pre(sc / "dfix-basefail.txt", DECISION_A)[0])
    (sc / "dfix-cfail.txt").write_text(real.replace("PART C ROUNDING-LEVEL", "PART C FAIL"))
    okc, _, ic = read_pre(sc / "dfix-cfail.txt", DECISION_A)
    check("pre C FAIL drops C", okc and ic["ARMS_FIX"] == "B A T U", str(ic))
    (sc / "dfix-c16.txt").write_text(real.replace("C_CHUNK 22528", "C_CHUNK 16384"))
    check("pre C_CHUNK 16384 drops C", read_pre(sc / "dfix-c16.txt", DECISION_A)[2]["ARMS_FIX"] == "B A T U")
    check("pre missing file refuses", not read_pre(sc / "nope.txt", DECISION_A)[0])
    # ---- the configs
    cf = sc / "configs"
    rc = cmd_arms(ns(outdir=str(cf), cparts="A,T,U,K,KP", cchunk=22528, names=None, gate="cfg", gates=str(sc / "g-cfg.txt")))
    c = json.loads((cf / "C.json").read_text())
    pu = json.loads((cf / "PU.json").read_text())
    p_ = json.loads((cf / "P.json").read_text())
    x28 = json.loads(BASE_28.read_text())
    fixb = json.loads(BASE_FIX.read_text())
    check("arms + cfgcheck PASS", rc == 0 and gs(read_gates(sc / "g-cfg.txt"), "cfg") == "PASS")
    check("C = P0210x-h + 7 switches at auto:32768", c["args"][c["args"].index("--prefill") + 1] == "auto:32768"
          and set(c["env"]) - set(fixb["env"]) == {"STRATA_PF_AHEAD", "STRATA_PF_TAIL_SPLIT", "STRATA_HC_UPMIX",
                                                    "STRATA_CKPT_POOL", "STRATA_CKPT_POOL_READY", "STRATA_KV_PREFETCH",
                                                    "STRATA_PF_FIRST_CHUNK"} and c["exe"] == str(E_FIX))
    check("PU = x28h + STRATA_HC_UPMIX=1 only", pu["exe"] == str(E28) and pu["server"] == str(SRV28)
          and pu["env"] == {**x28["env"], "STRATA_HC_UPMIX": "1"} and pu["args"] == x28["args"])
    check("P = x28h (env, args, exe)", p_["env"] == x28["env"] and p_["args"] == x28["args"] and p_["exe"] == x28["exe"]
          and {k: v for k, v in p_.items() if k not in ("_comment", "log")} == {k: v for k, v in x28.items() if k not in ("_comment", "log")})
    check("sampling block 1.0 / 0.95 / 20 / 0.05 in every arm",
          all(json.loads((cf / f"{n}.json").read_text())["sampling"] == {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
              for n in ("B", "A", "T", "U", "C", "Bc", "Tc", "Cc", "P", "PU")))
    pu["env"]["STRATA_PF_AHEAD"] = "1"
    (cf / "PU.json").write_text(json.dumps(pu))
    cmd_cfgcheck(ns(outdir=str(cf), gate="cfg2", gates=str(sc / "g-cfg.txt")))
    check("cfgcheck catches a stray switch in PU", gs(read_gates(sc / "g-cfg.txt"), "cfg2") == "FAIL")
    cmd_arms(ns(outdir=str(cf), cparts="A,T,U,K,KP", cchunk=22528, names=None, gate=None, gates=None))
    c["args"][c["args"].index("--prefill") + 1] = "22528"
    (cf / "C.json").write_text(json.dumps(c))
    cmd_cfgcheck(ns(outdir=str(cf), gate="cfg3", gates=str(sc / "g-cfg.txt")))
    check("cfgcheck catches C at an explicit 22528", gs(read_gates(sc / "g-cfg.txt"), "cfg3") == "FAIL")
    # ---- chunk lines
    (sc / "l22528.log").write_text("x\nstrata serve: prompt chunk auto: 22528 tokens, a 512-slot ring\nstrata serve: the prompt "
                                    "path borrows 4122 CUDA0 cache slots (7.85 GiB)\n")
    (sc / "l16384.log").write_text("strata serve: prompt chunk auto: 16384 tokens, a 512-slot ring\n")
    (sc / "lnone.log").write_text("nothing\n")
    gch = sc / "g-chunk.txt"
    for n, lg, inf in (("c1", "l22528", False), ("c2", "l16384", False), ("c3", "lnone", False), ("c4", "l16384", True)):
        cmd_chunk(ns(log=str(sc / f"{lg}.log"), want=22528, info=inf, gate=n, gates=str(gch)))
    gg = read_gates(gch)
    check("chunk 22528 PASS / 16384 FAIL / none FAIL / info INFO",
          [gs(gg, k) for k in ("c1", "c2", "c3", "c4")] == ["PASS", "FAIL", "FAIL", "INFO"], str(gg))
    # ---- PU's exactness
    P_ = ("PASS", "x")
    base_g = {"env_P_e7": P_, "e7_P": P_, "env_PU_e7": P_, "e7_PU": P_, "env_PU_pfy-PU40": P_, "logits_PU40": P_}
    check("puexact EXACT", pu_exact(base_g)[0] == "EXACT")
    check("puexact e7_PU FAIL", pu_exact({**base_g, "e7_PU": ("FAIL", "x")})[0] == "FAIL")
    v_, _, fl_ = pu_exact({**base_g, "logits_PU40": ("FAIL", "x"), "env_P_pfy-P40": P_, "logits_P40": ("FAIL", "x"),
                           "logits_PU40_P40": P_})
    check("puexact drift: PU40 = P40 decides, flagged", v_ == "EXACT" and any("long40 today" in f for f in fl_))
    v_, _, fl_ = pu_exact({**base_g, "logits_PU40": ("FAIL", "x"), "env_P_pfy-P40": P_, "logits_P40": P_,
                           "logits_PU40_P40": ("FAIL", "x")})
    check("puexact PU40 differs from P40 = FAIL", v_ == "FAIL" and not fl_)
    check("puexact env_PU_e7 FAIL = VOID", pu_exact({**base_g, "env_PU_e7": ("FAIL", "x")})[0] == "VOID")
    check("puexact env_P_e7 FAIL = NOT DECIDED", pu_exact({**base_g, "env_P_e7": ("FAIL", "x")})[0] == "NOT DECIDED")
    check("puexact long40 missing = NOT DECIDED", pu_exact({k: v for k, v in base_g.items() if k != "logits_PU40"})[0] == "NOT DECIDED")
    v_, _, fl_ = pu_exact({**base_g, "e7_P": ("FAIL", "exact7 r23sp-P: 5/7")})
    check("puexact e7_P FAIL with PU = P: EXACT + FLAG", v_ == "EXACT" and any("exact7 today" in f for f in fl_))
    # ---- B1 calibration: gap b's own stored data, split into this gap's per-start files, must give gap b's verdicts
    gb = WS / "results/r23/basalt-prompt/gap-b/bp90"
    cal = sc / "cal"
    (cal / "bp90").mkdir(parents=True)
    for arm in ("B", "U", "K", "KP", "S"):
        for line in (gb / f"cold-{arm}.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                with open(cal / "bp90" / f"{arm}-{r['test']}-{r['pass']}.jsonl", "a") as f:
                    f.write(line + "\n")
        dp = gb / f"cold-{arm}d.jsonl"
        if dp.exists():
            (cal / "bp90" / f"{arm}-decode-1.jsonl").write_text(dp.read_text())
    want_b = {"U": (True, "+3.7 %; noise 3.2 %", "+4.2 %; noise 0.6 %"), "K": (False, "+1.2 %; noise 1.6 %", "+0.1 %; noise 0.6 %"),
              "KP": (False, "+0.8 %; noise 1.7 %", "-0.1 %; noise 0.6 %"), "S": (True, "+3.9 %; noise 1.5 %", "+4.4 %; noise 0.6 %")}
    for arm, (wg, w16, w64) in want_b.items():
        have, hit, fl, txt, _ = gain(cal, {}, arm, "B")
        check(f"B1 calibration {arm} = gap b's decision-b ({'GAIN' if wg else 'NO GAIN'})",
              have and (hit and fl) == wg and w16 in txt and w64 in txt, txt)
    h2, ok2, l2 = decode_check(cal, {}, "S", "B")
    check("B2 calibration S = gap b's (FAIL: struct -1.3 %, noise 0.5 %)", h2 and not ok2 and "struct -1.3 % (noise 0.5 %)" in l2, l2)
    # ---- end to end: synthetic B1 / B2, the stored port-0211 screen (B = x28h, engine logs paired) as every arm's screen
    def mk(name, b1, dec=None, scr=None, gates_extra=None):
        o = sc / name
        (o / "bp90").mkdir(parents=True)
        (o / "speed").mkdir()
        (o / "rules.txt").write_text(rules_text())
        (o / "summary.txt").write_text("=== 2026-11-08 20:00:00 selftest\n")
        lines = []
        for arm, d in b1.items():
            for fx_, vals in d.items():
                for k, v in enumerate(vals, 1):
                    if v is None:
                        continue
                    (o / "bp90" / f"{arm}-{fx_}-{k}.jsonl").write_text(json.dumps({"pass": k, "test": fx_, "prompt_tps": v}) + "\n")
                    lines.append(f"env_{arm}_bp{k}{fx_} PASS x")
        for arm, (cv, sv, pv) in (dec or {}).items():
            (o / "bp90" / f"{arm}-decode-1.jsonl").write_text("".join(json.dumps({"pass": 1, "test": t, "decode_tps": v}) + "\n"
                                                                      for t, v in (("conv", cv), ("struct", sv), ("prose", pv))))
        src = WS / "results/r23/port-0211/gap/speed"
        for arm in (scr or []):
            for k in (1, 2, 3):
                for s_ in "nar":
                    for ext in ("jsonl", "englog"):
                        shutil.copy(src / f"B{k}{s_}.{ext}", o / "speed" / f"{arm}{k}{s_}.{ext}")
                lines.append(f"env_{arm}_scr{k} PASS x")
        lines += [f"{k} {v[0]} {v[1]}" for k, v in base_g.items()]
        lines += ["pu_exact PASS x", "vram_C PASS x"]
        lines += [f"chunk_C_bp{k}{fx_} PASS x" for k in (1, 2, 3) for fx_ in ("pp16k", "pp64k")]
        lines += (gates_extra or [])
        (o / "gates.txt").write_text("\n".join(lines) + "\n")
        return o

    def run(o):
        cmd_decide(ns(outdir=str(o), decision_fix=str(DECISION_FIX), decision_a=str(DECISION_A), quiet=True))
        return json.loads((o / "decision.json").read_text()), (o / "decision.txt").read_text()
    B1 = {"B": {"pp16k": [3800, 3810, 3790], "pp64k": [4400, 4405, 4395]},
          "A": {"pp16k": [3870, 3875, 3865], "pp64k": [4410, 4400, 4405]},          # +1.8 % at 16K (noise 0.5 %)
          "T": {"pp16k": [4150, 4140, 4160], "pp64k": [4500, 4510, 4495]},          # +9 %
          "U": {"pp16k": [3815, 3790, 3830], "pp64k": [4410, 4400, 4390]},          # +0.4 % (noise ~1 %): NO GAIN
          "C": {"pp16k": [4400, 4410, 4390], "pp64k": [4720, 4730, 4710]},          # +7.3 % at 64K
          "P": {"pp16k": [3770, 3780, 3760], "pp64k": [4370, 4375, 4365]},
          "PU": {"pp16k": [3900, 3905, 3895], "pp64k": [4520, 4525, 4515]}}         # +3.4 % / +3.4 %
    DEC = {"B": (148, 226, 133), "C": (148, 226, 133), "P": (148, 230, 134), "PU": (148, 230, 134)}
    SCR = ("B", "C", "P", "PU")
    o = mk("e2e", B1, DEC, SCR)
    g17.park_edit(o, "C", prefill=lambda ms: ms * 0.92)          # C reads prompts 8 % faster on every workload
    d, txt = run(o)
    A = d["arms"]
    check("e2e verdicts A T C PU CANDIDATE, U NO GAIN",
          [A[k]["verdict"] for k in ("A", "T", "U", "C", "PU")] == ["CANDIDATE", "CANDIDATE", "NO GAIN", "CANDIDATE", "CANDIDATE"],
          str({k: A[k]["verdict"] for k in A}))
    check("e2e candidates listed", txt.splitlines()[1].startswith("SPEED CANDIDATES FOR BACKLOG H: A (STRATA_PF_AHEAD=1)")
          and "the C-stack" in txt.splitlines()[1] and "U on P028x" in txt.splitlines()[1], txt.splitlines()[1])
    check("e2e vs P028x: A GAIN OVER, U GAIN OVER (+1.1 % > noise), C GAIN OVER",
          A["A"]["vs_p028x"] == "GAIN OVER P028x" and A["C"]["vs_p028x"] == "GAIN OVER P028x", str({k: A[k].get("vs_p028x") for k in A}))
    check("e2e C B3 PASS with the save line and the amendment tag", A["C"]["b3"][0] is True and "11-07 amendment" in A["C"]["b3"][1]
          and "chat-cache save [11-07 amendment]" in A["C"]["b3"][1], A["C"]["b3"][1][:300])
    check("e2e outside-engine flag is INFO on the line", "(info) outside-engine time" in A["C"]["b3"][1])
    check("e2e PU's B3 vs P reported", A["PU"]["b3"][0] is True and "(reported) B3 vs P PASS" in txt)
    check("e2e no flags", not d["flags"], str(d["flags"]))
    # a real per-workload prompt loss in C (R3-extract5k 15 % slower on the engine clock, g17's own case) -> C FAIL (screen)
    o = mk("e2e-r3", B1, DEC, SCR)
    g17.park_edit(o, "C", prefill=lambda ms: ms * 1.15, only={"R3-extract5k"})
    A = run(o)[0]["arms"]
    check("C with R3 15 % slower -> FAIL (screen)", A["C"]["verdict"].startswith("FAIL") and "R3-extract5k prompt" in A["C"]["b3"][1],
          A["C"]["b3"][1][:300])
    # a save regression in C (+15 % on every save) -> the save line FAILs -> C FAIL
    o = mk("e2e-save", B1, DEC, SCR)
    g17.park_edit(o, "C", save=lambda ms, mib, k: ms * 1.15)
    A = run(o)[0]["arms"]
    check("C saves +15 % -> FAIL (save line)", A["C"]["verdict"].startswith("FAIL") and "-> FAIL" in A["C"]["b3"][1], A["C"]["b3"][1][-300:])
    # outside-engine time +15 ms on R3 in every C pass (g17's own case): flagged, verdict unchanged
    o = mk("e2e-out", B1, DEC, SCR)
    g17.park_edit(o, "C", prefill=lambda ms: ms * 0.92)
    g17.park_edit_outside(o, "C", 15, only={"R3-extract5k"})
    A = run(o)[0]["arms"]
    check("outside-engine +15 ms on R3: flagged (INFO), C still CANDIDATE",
          A["C"]["verdict"] == "CANDIDATE" and "for review (INFO): R3-extract5k" in A["C"]["b3"][1], A["C"]["b3"][1][-300:])
    # a C start at the wrong chunk (pass 3, pp64k) is left out and flagged; with 2 left C is still judged
    o = mk("e2e-chunk", B1, DEC, SCR, ["chunk_C_bp3pp64k FAIL x"])
    g17.park_edit(o, "C", prefill=lambda ms: ms * 0.92)
    d, _ = run(o)
    check("C chunk FAIL in one start: left out, flagged, still CANDIDATE",
          d["arms"]["C"]["verdict"] == "CANDIDATE" and d["arms"]["C"]["b1"]["pp64k"]["passes"] == [2, 3]
          and any("gated chunk 22528 in 1 start" in f for f in d["flags"]), str(d["flags"]))
    o = mk("e2e-chunk2", B1, DEC, SCR, ["chunk_C_bp3pp64k FAIL x", "chunk_C_bp2pp64k FAIL x"])
    g17.park_edit(o, "C", prefill=lambda ms: ms * 0.92)
    check("C chunk FAIL in two pp64k starts: NOT DECIDED", run(o)[0]["arms"]["C"]["verdict"] == "NOT DECIDED")
    # a fatal line in a B start voids every fix-build verdict against B (not PU's)
    o = mk("e2e-fatal", B1, DEC, SCR, ["fatal_B_bp2pp16k FAIL x"])
    A = run(o)[0]["arms"]
    check("fatal in B: A T U C VOID, PU not", [A[k]["verdict"] for k in ("A", "T", "U", "C")] == ["VOID"] * 4
          and A["PU"]["verdict"] == "CANDIDATE")
    o = mk("e2e-env", B1, DEC, SCR, ["env_A_bp1pp64k FAIL x"])
    A = run(o)[0]["arms"]
    check("env FAIL in A: A VOID only", A["A"]["verdict"] == "VOID" and A["T"]["verdict"] == "CANDIDATE")
    # a foreign GPU user in one T start: left out, T still judged on 2 passes
    o = mk("e2e-foreign", B1, DEC, SCR, ["foreign_T_bp1pp16k FAIL x"])
    d, _ = run(o)
    check("foreign in a T start: left out, T CANDIDATE on 2 passes, flagged",
          d["arms"]["T"]["verdict"] == "CANDIDATE" and d["arms"]["T"]["b1"]["pp16k"]["passes"] == [2, 3]
          and any("foreign" in f for f in d["flags"]))
    # PU not exact -> not priced
    o = mk("e2e-pu", B1, DEC, SCR, ["e7_PU FAIL exact7 r23sp-PU: 6/7", "pu_exact FAIL x"])
    A = run(o)[0]["arms"]
    check("PU e7 FAIL -> PU NOT PRICED", A["PU"]["verdict"] == "NOT PRICED")
    # the floor: A +2 % at 16K but -3 % at 64K -> NO GAIN
    B1f = json.loads(json.dumps(B1))
    B1f["A"]["pp64k"] = [4270, 4265, 4275]
    o = mk("e2e-floor", B1f, DEC, SCR)
    A = run(o)[0]["arms"]
    check("A below -noise at 64K -> NO GAIN", A["A"]["verdict"] == "NO GAIN" and "BELOW -noise" in A["A"]["b1_text"])
    # one pass of a fixture -> NOT DECIDED; vram_C FAIL -> C FAIL; C's screen pass missing -> NOT DECIDED
    B1m = json.loads(json.dumps(B1))
    B1m["T"]["pp16k"] = [4150, None, None]
    o = mk("e2e-miss", B1m, DEC, SCR, ["vram_C FAIL 5080 free 210 MiB"])
    g17.park_edit(o, "C", prefill=lambda ms: ms * 0.92)
    A = run(o)[0]["arms"]
    check("T with 1 pass -> NOT DECIDED; vram_C FAIL -> C FAIL",
          A["T"]["verdict"] == "NOT DECIDED" and A["C"]["verdict"].startswith("FAIL"), str({k: A[k]["verdict"] for k in A}))
    o = mk("e2e-scr", B1, DEC, SCR, ["foreign_C_scr2 FAIL x"])
    for s_ in "nar":
        for ext in ("jsonl", "englog"):
            (o / "speed" / f"C2{s_}.{ext}").unlink()
    A = run(o)[0]["arms"]
    check("C's screen pass 2 void (moved) -> NOT DECIDED", A["C"]["verdict"] == "NOT DECIDED" and "2 complete passes" in A["C"]["b3"][1],
          A["C"]["b3"][1][:200])
    o = mk("e2e-scr2", B1, DEC, SCR, ["foreign_C_scr2 FAIL x"])
    A = run(o)[0]["arms"]
    check("C's void screen pass still in place -> NOT DECIDED", A["C"]["verdict"] == "NOT DECIDED" and "still in speed/" in A["C"]["b3"][1])
    # the frozen rule text changed -> FLAG
    o = mk("e2e-rules", B1, DEC, SCR)
    (o / "rules.txt").write_text("other\n")
    check("rules.txt changed -> FLAG", any("rule text differs" in f for f in run(o)[0]["flags"]))
    # gap b's stack rule for C: B2 decode loss -> FAIL
    o = mk("e2e-dec", B1, {**DEC, "C": (148, 218, 133)}, SCR)
    g17.park_edit(o, "C", prefill=lambda ms: ms * 0.92)
    A = run(o)[0]["arms"]
    check("C struct decode -3.5 % (noise 0.5 %) -> FAIL", A["C"]["verdict"].startswith("FAIL") and "B2 decode FAIL" in
          (o / "decision.txt").read_text())
    print(f"basalt_speed_rules selftest: {len(fails)} failure(s)" + (f": {', '.join(fails)}" if fails else ""))
    return 1 if fails else 0


# ================================================================================================ main
def main():
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
    p = sub("pre", gates=False)
    p.add_argument("--decision-fix", default=str(DECISION_FIX))
    p.add_argument("--decision-a", default=str(DECISION_A))
    p = sub("arms", "outdir")
    p.add_argument("--cparts", default="")
    p.add_argument("--cchunk", type=int)
    p.add_argument("--names")
    sub("cfgcheck", "outdir")
    p = sub("chunk", "log")
    p.add_argument("--want", type=int, required=True)
    p.add_argument("--info", action="store_true")
    sub("puexact", "outdir")
    sub("rules", "out", gates=False)
    p = sub("decide", "outdir", gates=False)
    p.add_argument("--decision-fix", default=str(DECISION_FIX))
    p.add_argument("--decision-a", default=str(DECISION_A))
    sub("selftest", "scratch", gates=False)
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest(a.scratch)
    f = {"pre": cmd_pre, "arms": cmd_arms, "cfgcheck": cmd_cfgcheck, "chunk": cmd_chunk, "puexact": cmd_puexact,
         "rules": cmd_rules, "decide": cmd_decide}[a.cmd]
    return f(a)


if __name__ == "__main__":
    sys.exit(main())
