#!/usr/bin/env python3
"""afetch_rules.py - r23 (written 2026-11-09 at the desk, NOT RUN on real data; only its selftest ran, on synthetic data):
the rules of THE ADAPT_FETCH GAP (work/r23/afetch-gap/gap-afetch.sh; results/BACKLOG-1027.md section I; the design and
estimate results/r23/ADAPTFETCH-DESK-1109.md; Karl's decisions of 11-09 in section I / J). Written before any run; the
driver freezes this text (plus the sha256 of every rule file it imports) into the gap's rules.txt before the gap opens,
and `decide` flags a change. NOTHING SWITCHES: P028x stays served; a PASS is a proposal to Karl.

THE ARMS (configs written by `arms` into OUTDIR/configs/, checked by `cfgcheck`; each arm its own engine log
logs/engine-r23af-NAME.log; every arm two GPUs, the helper cache on (--expert-cache-device1 3300), adaptation on, as served):
  P   configs/P028x.json as served for tests: without the picture reader (the --vision flag and the vision / fallback /
      model_not_running keys: sq.py's STRIP_ARGS / STRIP_KEYS, u_adopt.py's form) = configs/x28h.json + STRATA_HC_UPMIX=1
      key by key; engine-r22p028x (f4c4f654fb24), server strata-r22p028x
  F0  P on engine-r23afetch (153ce47d3ef0; branch r23-adaptfetch f381bfdf5 = r22-port028x + 24c6c2f68 + our helper-cache
      patch), STRATA_ADAPT_FETCH unset (build vs switch only)
  F1  F0 + STRATA_ADAPT_FETCH=1     F2  F0 + STRATA_ADAPT_FETCH=2
  P, F1 and F2 are the sampled test's R1, X1 and X2 (sq.py's own build of spec-adaptfetch.json) without the harness's
  STRATA_DEBUG=1 and log: cfgcheck compares them.

STEP 1 BUILD VS SWITCH (with the switch unset, the fetch build must be bitwise P028x; gap-basalt-speed.sh's e7 / pfy40):
  e7_F0          exact7 F0 at pin 2500 against P028x's stored exact7 x28h-e7a: 7/7 identical AND slots MATCHED
                 (basalt_rules e7gate); env_F0_e7 = every exact7 engine's environment as configured (basalt_rules envcli
                 --mode e7: the config's env, no other STRATA_*, the harness args)
  logits_F0L40   pf_yardstick long40 on F0 against gap 16's stored x28h long40 (results/r22/gap16/pfy/x28h): 0 of 40
                 first-token logit files differ (basalt_rules same); env_F0_pfy-F0L40 = its engine as configured
  BUILD VS SWITCH PASS = all four PASS; FAIL = e7_F0 or logits_F0L40 FAIL with its env PASS; NOT DECIDED otherwise (not
  run, or an env gate failed: the run was not the arm). Not PASS -> steps 2 and 3 are NOT RUN, and the decision says so.
  (x28h-e7a and gap 16's long40 are x28h without U; U is exact on P028x: the Basalt speed gap's PU EXACT and the U
  adoption gap of 11-09, exact7 7/7 MATCHED vs x28h-e7a.)

STEP 2 SPEED, THE USUAL RULES (the target is decode: admissions act only in decode, after the first windows; no cold
prompt fixtures are run):
  B2  Basalt's decode fixtures (bp90_client.py --sets decode: conv, struct, prose), a fresh engine per start, 3 passes in
      turned order (a Latin square: P F1 F2 / F2 P F1 / F1 F2 P) -> bp90/ARM-decode-K.jsonl
  B3  the 9-workload screen (work/r22/abarm.sh: warm-up, W1-W3, agent x2, research4 x4; T 1.0 / 0.95 / 20 / min-p 0.05),
      a fresh engine per arm-pass, 3 passes in the same Latin square -> speed/ARMK{n,a,r}.*
  Every start: no foreign GPU user before it (60 s) or during it (a 5 s watch), else it is left out (foreign_ARM_STEP
  FAIL); its engine's environment checked before it measures (basalt_rules envcheck: env_ARM_STEP; and fenv_ARM_STEP:
  the STRATA_ADAPT_FETCH* keys and STRATA_DEBUG exactly as the config has them, the running binary's sha256 the arm's);
  its start line (line_ARM_STEP: F1 / F2 print "STRATA_ADAPT_FETCH=N: the PCIe share takes ..." with their N and no
  "STRATA_ADAPT_FETCH is off"; P prints no STRATA_ADAPT_FETCH line); the fatal-line check (fatal_ARM_STEP); a kernel check.
  WHICH STARTS COUNT (basalt_speed_rules.py excluded / arm_void, imported): a foreign GPU user = the start is left out (the
  driver moves its files to void/); an env or fatal FAIL = the arm VOID (P VOID = every verdict VOID); here also a fenv
  FAIL = the arm VOID, and a line FAIL = UNEXERCISED -> NOT DECIDED (P: VOID).
  THE NUMBERS (gap b's / the Basalt speed gap's thresholds; spread = max / min - 1 over the counted passes, basalt_rules
  spread, imported):
    DECODE GAIN of X (F1, F2) against P, on each decode target:
      - each decode fixture: change = mean_X / mean_P - 1 over the counted passes; noise = the larger of the two arms'
        spreads; it needs 2 or more counted passes of both arms, else NOT DECIDED;
      - the screen's decode geomean: per complete pass the geometric mean of the 9 workloads' decode tok/s (g17_rules
        screen_passes, the 11-07 amendment); an arm = the geometric mean of its passes; noise = the larger arm's pass
        spread; 3 complete passes of both arms, else NOT DECIDED.
      GAIN: by the switch GAIN_FORM (below). "above" = change > +max(noise, 1.0 %); "below" = change < -noise.
    B2 CHECK (gap b's decode check, basalt_speed_rules.decode_check, imported): each fixture's decode of X >= P's x (1 -
      noise), noise = gap 17's 3-pass spread of that fixture on P028x (results/r22/gap17/bp90/cold-M.jsonl; 3 % missing).
    B3 CHECK (the screen under the 11-07 amendment; g17_rules wl_noloss / save_rule / pair_problems, imported):
      - per-workload no-loss (Karl 11-03): per workload, decode and prompt tok/s each, X's pass mean >= P's x (1 - the
        larger of the two arms' spreads there); the per-workload prompt is on the engine clock minus the chat-cache save;
      - the screen's prompt geomean (client clock minus the save) against P's: by the switch B3_PROMPT_FORM (below);
        the other form is reported as INFO;
      - the chat-cache save line (save_rule): FAIL is a loss, NOT DECIDED leaves B3 undecided, NOT JUDGED is INFO;
      - the outside-engine flag: INFO (on the no-loss line), never a verdict;
      - 3 complete passes of both arms, every record paired with its engine-log line, else NOT DECIDED.
  SPEED VERDICT of X against P: CANDIDATE = GAIN + B2 PASS + B3 PASS (+ under GAIN_FORM screen no fixture below -noise);
  NO GAIN = the same without the gain; FAIL (decode / screen) = B2 or B3 FAILS, or (GAIN_FORM screen) a decode fixture
  below -noise; VOID; NOT DECIDED (missing passes, UNEXERCISED); NOT RUN (step 1 not PASS, the read-back mismatch, the
  priority rule, the deadline).
  INFO beside it: the same GAIN with noise = half the range (spread / 2); F2 against F1 (the =2 part's own effect).

STEP 3 QUALITY, THE SAMPLED-DISTRIBUTION TEST (work/r23/sampled-qwen/: sq.py, sq_stat.py, sq_client.py; design
results/r23/SAMPLED-QWEN-DESIGN-1109.md, Karl 11-09 "approved as designed"; its own rule = sq.py rule -> sampled/rule.txt,
written before the gap opens; sq.py decide judges and refuses a changed rule). The fixed plan: R1 = P (K 8 = 32 requests),
X1 = F1 (K 8), X2 = F2 (K 8), R2 = P again with its own seeds (K 4 = 16 requests; always run: the noise bound), VF = X2 +
STRATA_ADAPT_FETCH_VERIFY=1 + STRATA_ADAPT_CHECKRES=1 (K 2, read-back only, not scored). Order (STEPS-adaptfetch.txt):
VF first (sq.py verify; its verdict is read from verify-VF.json: a read-back mismatch skips the served arms and the
scorer: both candidates FAIL overall), then R1 X1 X2 R2, sq.py ids, the scorer (only with R1's samples), sq.py decide.
Where VF runs is set by the switch ORDER_FORM (below).
  The gap's own gates on the sampled starts count: an env FAIL (env_sqARM: basalt_rules envcheck; envsq_ARM: sq.py
  envcheck), a fatal line (fatal_sqARM), a foreign GPU user before or during it (foreign_sqARM) or a start voided for a
  test server left behind (void_sqARM) makes R1 or R2 ->
  both candidates NOT DECIDED; X1 / X2 -> that candidate NOT DECIDED; VF -> a read-back PASS becomes NOT DECIDED (a FAIL
  stays FAIL); the scorer's env FAIL (env_sqscore) -> both NOT DECIDED.
  Per candidate: SAMPLED = sq decision.json candidates[X].verdict; READ-BACK = verify-VF.json (PASS = 0 mismatch lines,
  0 differ, >= 200 admitted slots read back, >= 4 requests finished; FAIL = any mismatch; the VF start covers X1 and X2);
  QUALITY = sq decision.json overall[X]: PASS = SAMPLED PASS and READ-BACK PASS, FAIL = either FAILS, else NOT DECIDED
  (Karl 11-09: "PASS = each candidate passes the sampled test AND the read-back shows 0 mismatches").

REPORTED per arm (INFO, never a verdict): admissions per window, from the engine's per-request line "strata serve: fetch:
N admissions in W windows (X per window)": sum N / sum W over the arm's requests, for B2, B3 and the sampled arms; the
expert placement split of the decode lookups (main / helper / PCIe / CPU over all routed entries: work/r23/scratch-
adaptfetch/agg.py's parsing, copied verbatim and compared by `copycheck` and the selftest: main = H, CPU = L - H, helper
= the CUDA1 entries N, PCIe = O - N); the engine's decode tok/s over those requests.

THE PRIORITY RULE (Karl 11-09): day-one work goes first. A find = work/qwen4-kit/hfwatch/state.json has a repo entry of
kind "Flash" with access private false and gated false and a non-empty weights map. Before the gap opens a find HOLDS
this gap (final; an alert); inside the gap it is checked again after the gap opens and before each long part (each
exactness run, each speed pass, the sampled part and each of its arms): a find stops new steps and the gap ends cleanly
(P028x back); the decision lists what ran. A state file that is missing or cannot be read: before the gap a busy
refusal (retried; the rule cannot be checked), inside it a FLAG (the next check reads it again). THE OVERRIDE: tmp/afetch-priority-done whose first line starts with a
date (YYYY-MM-DD) and gives the reason - Claude writes it only when Karl says the day-one work is done; with it present
the hold no longer applies, and the summary, the decision and the result line name it (a marker without a dated first
line is ignored: the hold applies).

THE QUEUE ORDER (Karl 11-09: after the v0.2.13 shape gap): the shape gap has RUN only when its result.txt's first line
starts "DONE" (and its unit shape-gap0213 is inactive - the driver and the starter check that). Anything else keeps this
gap waiting: "kernel check FAILED ...", "KERNEL ERROR ..." and "port_gap4.sh end FAILED ..." (Karl looks at those first),
"not started ...", "INTERRUPTED ...", "not run: ...", none.

THE SWITCHES (one constant each at the top of the code; their values at the freeze are written into rules.txt). KARL
ANSWERED 11-09 - his forms are the frozen settings, marked [KARL 11-09]; the other forms stay implemented and selftested.
Noise stays the full range (max / min - 1), as the rule files define it.
  B3_PROMPT_FORM  "tol1" [KARL 11-09]: the screen's prompt geomean not below P's x (1 - 1 %), with the per-workload no-loss
                  (no workload slower beyond its noise) and the save line; the strict form is reported as INFO only
                  "strict": not below P's (basalt_speed_rules.screen, gap b's form)
  GAIN_FORM       "screen" [KARL 11-09]: ONE primary target, the screen's decode geomean above +max(noise, 1 %); the 3
                  decode fixtures are no-loss checks only: one below -noise is a decode no-loss FAILURE (the speed
                  verdict FAIL (decode: FIXTURE below -noise)), not "no gain"
                  "any4": a decode target (the 3 fixtures and the screen decode geomean) above, none below
                  (basalt_speed_rules.gain's form with decode as the target)
  ORDER_FORM      "vf-first" [KARL 11-09]: the VF read-back start (=2) right after exact7 + long40, before the speed runs;
                  on a read-back mismatch the speed and sampled parts do not run for either candidate (the decision says
                  why; sq.py decide still writes its decision); otherwise speed, then R1 X1 X2 R2, ids, the scorer, sq.py
                  decide
                  "speed-first": build vs switch, speed, then the sampled part (VF first within it)

THE DECISION (decide -> OUTDIR/decision.txt, decision.json, result-line.txt), per candidate F1 / F2: build vs switch
(shared), the speed verdict with its numbers, SAMPLED, READ-BACK, QUALITY, the admissions per window; then
  PROPOSAL for Karl  = build vs switch PASS + QUALITY PASS + speed CANDIDATE
  QUALITY PASS, NO SPEED GAIN = build vs switch PASS + QUALITY PASS + speed NO GAIN
  FAIL               = build vs switch FAIL, or QUALITY FAIL, or speed FAIL
  NOT DECIDED        = otherwise (what is missing is named)
NOTHING SWITCHES: P028x stays served; Karl decides.

Subcommands: priority, shapecheck, arms, cfgcheck, fetchenv, startline, exact, fetchstats, rules, decide, copycheck,
selftest. Python: .venv/bin/python -I -B at nice 19.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import shutil
import statistics as st
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.dont_write_bytecode = True     # it loads modules from trees it must not write to (work/r22, work/r23, sampled-qwen)

# ======== THE SWITCHES (see the docstring). Karl answered 11-09: tol1, screen, vf-first (frozen into rules.txt); the other
# forms stay implemented and selftested
B3_PROMPT_FORM = "tol1"       # "tol1" [KARL 11-09] | "strict"
GAIN_FORM = "screen"          # "screen" [KARL 11-09] | "any4"
ORDER_FORM = "vf-first"       # "vf-first" [KARL 11-09] | "speed-first"
FORMS = {"B3_PROMPT_FORM": ("strict", "tol1"), "GAIN_FORM": ("any4", "screen"), "ORDER_FORM": ("speed-first", "vf-first")}

WS = Path("/home/USER/ai-speed-testing/strata-compare")
AG = WS / "work/r23/afetch-gap"
SR = WS / "work/r23/basalt_speed_rules.py"
SQD = WS / "work/r23/sampled-qwen"
SPEC = SQD / "spec-adaptfetch.json"
AGG = WS / "work/r23/scratch-adaptfetch/agg.py"
RULE_FILES = (AG / "afetch_rules.py", SR, WS / "work/r23/basalt_fix_rules.py", WS / "work/r23/basalt_rules.py",
              WS / "work/r22/g17_rules.py", SQD / "sq.py", SQD / "sq_stat.py", SQD / "sq_client.py", SQD / "spec-adaptfetch.json")
PRIO_DONE = WS / "tmp/afetch-priority-done"
SHAPE_RAN = ("DONE",)       # (review 11-09 m1 / m9: a kernel error or a failed end keeps this gap waiting for Karl)
E28 = WS / "engine-r22p028x/strata"
E_AF = WS / "engine-r23afetch/strata"
SHA = {str(E28): "f4c4f654fb24", str(E_AF): "153ce47d3ef0"}
SRV28 = WS / "strata-r22p028x/serve/server.py"
P028X_CFG = WS / "configs/P028x.json"
X28H_CFG = WS / "configs/x28h.json"
STATE = WS / "work/qwen4-kit/hfwatch/state.json"
SHAPE_RES = WS / "results/r23/port-0213/shape-gap/result.txt"
G17_COLD_M = WS / "results/r22/gap17/bp90/cold-M.jsonl"
ARMS = ("P", "F0", "F1", "F2")
CANDS = ("F1", "F2")
SQ_ARM = {"P": "R1", "F1": "X1", "F2": "X2"}
NAMES = {"F1": "F1 (STRATA_ADAPT_FETCH=1)", "F2": "F2 (STRATA_ADAPT_FETCH=2)"}
FETCH_ENV = {"P": {}, "F0": {}, "F1": {"STRATA_ADAPT_FETCH": "1"}, "F2": {"STRATA_ADAPT_FETCH": "2"}}
FETCH_KEYS = ("STRATA_ADAPT_FETCH", "STRATA_ADAPT_FETCH_VERIFY", "STRATA_ADAPT_CHECKRES", "STRATA_ADAPT_FETCH_MIN",
              "STRATA_ADAPT_FETCH_MARGIN", "STRATA_DEBUG")
EXE_OF = {"P": E28, "F0": E_AF, "F1": E_AF, "F2": E_AF}
ORDER = {1: ("P", "F1", "F2"), 2: ("F2", "P", "F1"), 3: ("F1", "F2", "P")}
GAIN_MIN = 0.010
SCREEN_PROMPT_TOL = 0.010
FIXTURES = ("conv", "struct", "prose")
STRINGS_AF = (b"STRATA_ADAPT_FETCH\0", b"STRATA_ADAPT_FETCH_VERIFY\0")
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}

# ---- copied verbatim from work/r23/scratch-adaptfetch/agg.py (11-09; `copycheck` and the selftest compare them) ----
hit_re = re.compile(r"decode expert cache hit rate: [\d.]+% \((\d+) hits / (\d+) lookups\); (\d+) more read by the GPU "
                    r"over PCIe or from another GPU \([\d.]+% of all (\d+) routed\)")
cuda1_re = re.compile(r"^strata serve: CUDA1: (\d+) expert entries")
gen_re = re.compile(r"(\d+) generated in (\d+) ms \(([\d.]+) tok/s\)")
start_re = re.compile(r"engine started")
# ---- (end of the copy) ----
FETCH_LINE_RE = re.compile(r"^strata serve: fetch: (\d+) admissions in (\d+) windows \(([\d.]+) per window\)")
FETCH_ON_RE = re.compile(r"^strata serve: STRATA_ADAPT_FETCH=(\d+): the PCIe share takes", re.M)
FETCH_OFF_RE = re.compile(r"^strata serve: STRATA_ADAPT_FETCH is off \(([^)\n]*)\)", re.M)
ANY_FETCH_RE = re.compile(r"STRATA_ADAPT_FETCH")

_MOD = {}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def srm():
    """basalt_speed_rules.py (it loads basalt_fix_rules -> basalt_rules, and g17_rules): read-only, loaded once"""
    if "sr" not in _MOD:
        _MOD["sr"] = load("basalt_speed_rules", SR)
    return _MOD["sr"]


def sqm():
    """sq.py of the sampled harness (build_config / resolve_arm / diff_keys / STRIP_*): read-only, loaded once"""
    if "sq" not in _MOD:
        if str(SQD) not in sys.path:
            sys.path.insert(0, str(SQD))
        _MOD["sq"] = load("sq", SQD / "sq.py")
    return _MOD["sq"]


def sha256_file(p, n=None):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()[:n] if n else h.hexdigest()


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def read_gates(p):
    g = {}
    for line in Path(p).read_text(errors="replace").splitlines() if Path(p).exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        if k:
            g[k] = (s, det)       # the last line of a gate counts (basalt_rules.read_gates' rule)
    return g


def gs(g, k):
    return g.get(k, ("", ""))[0]


def gm(v):
    return math.exp(sum(math.log(x) for x in v) / len(v))


def spread(v):
    return max(v) / min(v) - 1 if len(v) > 1 else 0.0


def forms_bad():
    return [f"{k}={globals()[k]!r} (want one of {v})" for k, v in FORMS.items() if globals()[k] not in v]


def rules_text():
    shas = "\n".join(f"  {p.relative_to(WS)} {sha256_file(p, 16) if p.exists() else 'MISSING'}" for p in RULE_FILES)
    sw = "\n".join(f"  {k} = {globals()[k]}" for k in FORMS)
    return (__doc__.strip() + "\n\nTHE SWITCHES AT THE FREEZE:\n" + sw
            + "\n\nThis file and the rule files it imports or the harness reads (sha256, first 16 hex, at the freeze; this "
              "file's own sha covers its code, not only this text):\n" + shas + "\n")


def cmd_forms(a):
    """KEY=VALUE lines of the switches (the driver reads ORDER_FORM); exit 1 when a value is not one of its forms"""
    for k in FORMS:
        print(f"{k}={globals()[k]}")
    bad = forms_bad()
    if bad:
        print("FORMS BAD: " + "; ".join(bad))
    return 1 if bad else 0


# ================================================================================================ before the gap
def priority(state_path, tries=3, wait=2.0):
    """(status, text): CLEAR / HOLD / UNKNOWN (Karl 11-09's priority rule on the Qwen4 watch's state file)"""
    p = Path(state_path)
    if not p.exists():
        return "UNKNOWN", f"the Qwen4 watch's state file {p} is missing: the priority rule cannot be checked"
    err = None
    for i in range(tries):
        try:
            s = json.loads(p.read_text())
            break
        except (OSError, ValueError) as e:      # (the watcher rewrites the file at each poll: a torn read is retried)
            err = e
            if i < tries - 1:
                time.sleep(wait)
    else:
        return "UNKNOWN", f"{p} could not be read ({str(err)[:120]})"
    repos = s.get("repos") if isinstance(s, dict) else None
    if not isinstance(repos, dict):
        return "UNKNOWN", f"{p} has no repos map"
    finds = []
    for rid, e in repos.items():
        if not isinstance(e, dict):
            continue
        acc = e.get("access") if isinstance(e.get("access"), dict) else {}
        w = e.get("weights")
        if e.get("kind") == "Flash" and not acc.get("private", True) and not acc.get("gated", True) \
                and isinstance(w, dict) and w:
            finds.append(f"{rid} ({len(w)} weight file(s), first seen {e.get('first_seen', '?')})")
    if finds:
        return "HOLD", "open Flash weights on Hugging Face: " + "; ".join(finds) + " - day-one work goes first (Karl 11-09)"
    return "CLEAR", f"{len(repos)} Qwen4 repo(s) in the watch, none an open Flash with weights (last poll {s.get('last_poll', '?')})"


def override_of(path):
    """(valid, text) of the priority override marker: its first line starts with a date YYYY-MM-DD and gives a reason"""
    p = Path(path)
    if not p.exists():
        return False, ""
    first = (p.read_text(errors="replace").strip().splitlines() or [""])[0].strip()
    if re.match(r"^20\d\d-\d\d-\d\d\b.*\S", first) and len(first) > 11:
        return True, first[:200]
    return False, f"{p} has no dated reason line ({first[:80]!r}): ignored, the hold applies"


def cmd_priority(a):
    v, t = priority(a.state)
    if v == "HOLD":
        ok, why = override_of(a.override)
        if ok:
            v, t = "OVERRIDDEN", f"{t}; HOLD OVERRIDDEN by {a.override}: {why}"
        elif why:
            t = f"{t}; {why}"
    print(f"PRIORITY {v}: {t}")
    return {"CLEAR": 0, "OVERRIDDEN": 0, "HOLD": 10}.get(v, 2)


def shape_ran(res_path):
    """(ran, text): the v0.2.13 shape gap has run - its result.txt's first line starts DONE (anything else - a kernel
    error, a failed end, an aborted, refused or not-run attempt - keeps this gap waiting)"""
    p = Path(res_path)
    if not p.exists():
        return False, f"no {p}"
    first = (p.read_text(errors="replace").strip().splitlines() or [""])[0]
    if not first:
        return False, f"{p} is empty"
    if not first.startswith(SHAPE_RAN):
        return False, f"the shape gap has not run to an end yet: {first[:160]}"
    return True, f"the shape gap ran: {first[:200]}"


def cmd_shapecheck(a):
    ok, t = shape_ran(a.result)
    print(("SHAPE GAP RAN: " if ok else "SHAPE GAP NOT RUN: ") + t)
    return 0 if ok else 1


# ================================================================================================ the arm configs
def base_config():
    """P028x.json stripped exactly as the sampled harness strips it (sq.py build_config of an R1-like recipe)"""
    sq = sqm()
    return sq.build_config({"base": str(P028X_CFG), "strip": True, "top": {}, "env": {}, "args_set": {}, "args_drop_value": []})


def arm_config(name, log_dir=None):
    c = base_config()
    c["exe"] = str(EXE_OF[name])
    c["env"] = dict(c["env"], **FETCH_ENV[name])
    c["log"] = str(Path(log_dir or WS / "logs") / f"engine-r23af-{name}.log")
    c["_comment"] = (f"r23 ADAPT_FETCH gap (work/r23/afetch-gap/afetch_rules.py arms, from configs/P028x.json without the "
                     f"picture reader): arm {name}, exe {Path(c['exe']).parent.name}, adds {FETCH_ENV[name] or 'nothing'}. "
                     "Measurement only, never served.")
    return c


def cmd_arms(a):
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    man = {}
    for n in ARMS:
        c = arm_config(n, a.log_dir)
        (out / f"{n}.json").write_text(json.dumps(c, indent=1) + "\n")
        man[n] = {"exe": c["exe"], "env": FETCH_ENV[n], "base": str(P028X_CFG), "base_sha256": sha256_file(P028X_CFG),
                  "x28h_sha256": sha256_file(X28H_CFG), "log_dir": str(Path(c["log"]).parent)}
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(f"arm configs in {out}: {', '.join(ARMS)}")
    return cmd_cfgcheck(a)


def cmd_cfgcheck(a):
    """every arm = P028x.json stripped + exactly its exe / env delta; P stripped = x28h + U; P / F1 / F2 = the sampled
    test's R1 / X1 / X2 (sq.py's own build of the spec) without the harness env and log; the binaries are the arms'"""
    sq = sqm()
    out = Path(a.outdir)
    bad = []
    try:
        man = json.loads((out / "manifest.json").read_text())
    except (OSError, ValueError):
        man = {}
        bad.append("manifest.json missing")
    base = base_config()
    for k in FETCH_KEYS:
        if k in base["env"]:
            bad.append(f"configs/P028x.json itself sets {k}")
    if sha256_file(P028X_CFG) != man.get("P", {}).get("base_sha256"):
        bad.append("configs/P028x.json changed since the configs were written")
    want_p = json.loads(X28H_CFG.read_text())
    want_p["env"] = dict(want_p.get("env", {}), STRATA_HC_UPMIX="1")
    d = sq.diff_keys(base, want_p)
    if d:
        bad.append(f"P028x.json without the picture reader is not x28h.json + STRATA_HC_UPMIX=1 (differs in {d})")
    cfgs = {}
    for n in ARMS:
        try:
            c = json.loads((out / f"{n}.json").read_text())
        except (OSError, ValueError):
            bad.append(f"{n}: config missing")
            continue
        cfgs[n] = c
        w = arm_config(n, man.get(n, {}).get("log_dir"))
        dd = [k for k in set(c) | set(w) if k not in ("_comment",) and c.get(k) != w.get(k)]
        if dd:
            bad.append(f"{n}: differs from P028x.json stripped + its delta in {sorted(dd)}")
        if c.get("server") != str(SRV28):
            bad.append(f"{n}: server {c.get('server')}")
        if c.get("sampling") != SAMPLING:
            bad.append(f"{n}: sampling {c.get('sampling')}")
        ev = {k: v for k, v in c.get("env", {}).items() if k in FETCH_KEYS}
        if ev != FETCH_ENV[n]:
            bad.append(f"{n}: fetch keys {ev} (want {FETCH_ENV[n]})")
        if "--expert-cache-device1" not in c.get("args", []) or len([x for x in c["env"].get("CUDA_VISIBLE_DEVICES", "").split(",") if x]) != 2:
            bad.append(f"{n}: not the two-GPU helper form")
    sp = Path(a.spec) if getattr(a, "spec", None) else SPEC
    try:
        spec = json.loads(sp.read_text())
        for n, r in SQ_ARM.items():
            sc = sq.build_config(sq.resolve_arm(spec, r))
            if n in cfgs:
                dd = sq.diff_keys(cfgs[n], sc)
                ex = {k: v for k, v in cfgs[n].get("env", {}).items()} != {k: v for k, v in sc.get("env", {}).items()}
                if dd or ex:
                    bad.append(f"{n}: is not the sampled test's {r} in {dd}{' (env)' if ex else ''}")
    except (OSError, ValueError, KeyError) as e:
        bad.append(f"the sampled spec {sp}: {e}")
    if not getattr(a, "no_sha", False):
        for exe, want in SHA.items():
            if not os.path.isfile(exe):
                bad.append(f"{exe} missing")
            elif sha256_file(exe, 12) != want:
                bad.append(f"{exe} sha256 {sha256_file(exe, 12)} is not {want}")
        data = E_AF.read_bytes() if E_AF.exists() else b""
        miss = [s.decode().rstrip("\0") for s in STRINGS_AF if s not in data]
        if miss:
            bad.append(f"engine-r23afetch has no {miss}")
        if E28.exists() and b"STRATA_HC_UPMIX\0" not in E28.read_bytes():
            bad.append("engine-r22p028x has no STRATA_HC_UPMIX")
    line = ("CONFIG CHECK OK: P F0 F1 F2 = P028x.json without the picture reader (= x28h + STRATA_HC_UPMIX=1) + their exe / "
            "STRATA_ADAPT_FETCH only; P F1 F2 = the sampled test's R1 X1 X2" + ("" if getattr(a, "no_sha", False) else
                                                                                 "; engine shas f4c4f654fb24 / 153ce47d3ef0")
            if not bad else "CONFIG CHECK FAILED: " + "; ".join(sorted(set(bad))))
    print(line)
    gate(a, "FAIL" if bad else "PASS", line[:300])
    return 1 if bad else 0


# ================================================================================================ evidence per start
def proc_env(pid):
    env = dict(x.split("=", 1) for x in Path(f"/proc/{pid}/environ").read_bytes().decode("utf-8", "replace").split("\0")
               if "=" in x)
    return env


def fetch_env_problems(env, sha12, cfg, want_sha):
    want = {k: v for k, v in cfg.get("env", {}).items() if k in FETCH_KEYS}
    bad = [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]
    bad += [f"{k}={env[k]} set behind the config" for k in FETCH_KEYS if k not in want and k in env]
    if want_sha and sha12 != want_sha:
        bad.append(f"the running binary's sha256 {sha12} is not {want_sha}")
    return bad


def cmd_fetchenv(a):
    """the served arm's engine(s) of EXE (inside with_server.sh, after basalt_rules envcheck): the STRATA_ADAPT_FETCH*
    keys and STRATA_DEBUG exactly as the config has them; the running binary is the arm's (by /proc/PID/exe and its
    sha256). --mock-env FILE (the driver's --mock only): {"procs": [{"pid", "env", "sha12"}]} instead of /proc"""
    cfg = json.loads(Path(a.config).read_text())
    exe = os.path.realpath(a.exe)
    want_sha = SHA.get(exe)
    procs = []
    if a.mock_env:
        procs = [(p.get("pid", "mock"), p.get("env", {}), p.get("sha12")) for p in json.loads(Path(a.mock_env).read_text())["procs"]]
    else:
        for d in Path("/proc").iterdir():
            if d.name.isdigit():
                try:
                    if os.readlink(d / "exe") == exe:
                        procs.append((d.name, proc_env(d.name), sha256_file(d / "exe", 12)))
                except OSError:
                    continue
    bad_all = []
    if not procs:
        bad_all.append(f"no running engine {exe}")
    for pid, env, sha12 in procs:
        bad = fetch_env_problems(env, sha12, cfg, want_sha)
        print(f"engine pid {pid}: fetch keys {({k: env[k] for k in FETCH_KEYS if k in env}) or 'none'}, binary {sha12}"
              + (f"; MISMATCH {', '.join(bad)}" if bad else ""))
        bad_all += bad
    line = ("FETCH ENV OK: " + f"{len(procs)} engine(s), the STRATA_ADAPT_FETCH* keys as configured, binary {want_sha or '?'}"
            if not bad_all else "FETCH ENV FAILED - this arm is not measured: " + "; ".join(bad_all))
    print(line)
    gate(a, "PASS" if not bad_all else "FAIL", line[:300])
    return 0 if not bad_all else 1


def startline_check(text, arm):
    """(ok, line) for an engine start's log slice"""
    want = FETCH_ENV.get(arm, {}).get("STRATA_ADAPT_FETCH")
    on, off = FETCH_ON_RE.findall(text), FETCH_OFF_RE.findall(text)
    if want:
        ok = bool(on) and all(x == want for x in on) and not off
        why = (f"{len(on)} 'STRATA_ADAPT_FETCH={want}' start line(s)" if ok else
               f"UNEXERCISED: start lines ={','.join(on) or 'none'}" + (f", 'is off ({off[0]})'" if off else ""))
    else:
        anyl = [ln for ln in text.splitlines() if ANY_FETCH_RE.search(ln)]
        ok = not anyl
        why = "no STRATA_ADAPT_FETCH line" if ok else f"a STRATA_ADAPT_FETCH line in a no-fetch arm: {anyl[0][:120]!r}"
    return ok, why


def cmd_startline(a):
    t = Path(a.englog).read_text(errors="replace") if Path(a.englog).exists() else ""
    ok, why = startline_check(t, a.arm)
    line = f"{Path(a.englog).name} ({a.arm}): {why}"
    print(f"{line} -> {'PASS' if ok else 'FAIL'}")
    gate(a, "PASS" if ok else "FAIL", line[:300])
    return 0


def exact_verdict(g):
    """(PASS / FAIL / NOT DECIDED, text) of step 1"""
    parts = {k: gs(g, k) for k in ("e7_F0", "env_F0_e7", "logits_F0L40", "env_F0_pfy-F0L40")}
    txt = (f"exact7 F0 vs x28h-e7a {parts['e7_F0'] or 'not run'} ({g.get('e7_F0', ('', ''))[1][:60]}), env "
           f"{parts['env_F0_e7'] or '-'}; long40 F0 vs gap 16's x28h {parts['logits_F0L40'] or 'not run'} "
           f"({g.get('logits_F0L40', ('', ''))[1][:60]}), env {parts['env_F0_pfy-F0L40'] or '-'}")
    if all(v == "PASS" for v in parts.values()):
        return "PASS", txt
    if (parts["e7_F0"] == "FAIL" and parts["env_F0_e7"] == "PASS") or \
            (parts["logits_F0L40"] == "FAIL" and parts["env_F0_pfy-F0L40"] == "PASS"):
        return "FAIL", txt
    return "NOT DECIDED", txt


def cmd_exact(a):
    g = read_gates(Path(a.outdir) / "gates.txt")
    v, t = exact_verdict(g)
    line = f"BUILD VS SWITCH {v}: {t}"
    print(line)
    gate(a, v.replace(" ", "-"), line[:300])
    print(v)
    return 0


# ================================================================================================ engine-log numbers
def requests_of(text):
    """agg.py's per-request accounting (copied: a prompt line opens a request; the hit-rate and CUDA1 lines that follow
    it belong to it; 'engine started' closes it), plus this patch's fetch line"""
    reqs, cur = [], None
    for line in text.splitlines():
        if start_re.search(line):
            cur = None
            continue
        m = gen_re.search(line)
        if m and line.startswith("strata serve: prompt"):
            cur = {"gen": int(m.group(1)), "ms": int(m.group(2))}
            reqs.append(cur)
            continue
        m = hit_re.search(line)
        if m and cur is not None:
            cur.update(H=int(m.group(1)), L=int(m.group(2)), O=int(m.group(3)), R=int(m.group(4)))
            continue
        m = cuda1_re.search(line)
        if m and cur is not None:
            cur["N"] = int(m.group(1))
            continue
        m = FETCH_LINE_RE.search(line)
        if m and cur is not None:
            cur.update(adm=int(m.group(1)), adm_w=int(m.group(2)))
    return reqs


def stats_of(texts):
    """{requests, admissions, windows, per_window, placement {main, helper, pcie, cpu} (% of routed), decode_tps}"""
    reqs = [r for t in texts for r in requests_of(t)]
    rows = [r for r in reqs if "R" in r]
    tot = dict(H=0, C=0, P=0, N=0, R=0)
    for r in rows:
        n = r.get("N", 0)
        tot["H"] += r["H"]
        tot["C"] += r["L"] - r["H"]
        tot["N"] += n
        tot["P"] += r["O"] - n
        tot["R"] += r["R"]
    fr = [r for r in reqs if "adm" in r]
    adm, w = sum(r["adm"] for r in fr), sum(r["adm_w"] for r in fr)
    gen, ms = sum(r["gen"] for r in reqs), sum(r["ms"] for r in reqs)
    R = tot["R"]
    out = {"requests": len(reqs), "fetch_lines": len(fr), "admissions": adm, "windows": w,
           "per_window": round(adm / w, 3) if w else None, "routed": R,
           "placement": ({"main": round(100 * tot["H"] / R, 1), "helper": round(100 * tot["N"] / R, 1),
                          "pcie": round(100 * tot["P"] / R, 1), "cpu": round(100 * tot["C"] / R, 1)} if R else None),
           "decode_tps": round(gen / (ms / 1000), 1) if ms else None}
    return out


EL_RE = {"B2": re.compile(r"^bp-(P|F1|F2)-decode-\d\.englog$"), "B3": re.compile(r"^scr-(P|F1|F2)\d\.englog$")}


def fetch_stats(o, sqo=None):
    """{arm: {part: stats}} over englog/ (B2: bp-ARM-decode-K, B3: scr-ARMK) and the sampled arms' engine.out"""
    o = Path(o)
    texts = {}
    for f in sorted((o / "englog").glob("*.englog")) if (o / "englog").is_dir() else []:
        for part, rx in EL_RE.items():
            m = rx.match(f.name)
            if m:
                texts.setdefault(m.group(1), {}).setdefault(part, []).append(f.read_text(errors="replace"))
    sqo = Path(sqo) if sqo else o / "sampled"
    for arm, r in (("P", "R1"), ("P", "R2"), ("F1", "X1"), ("F2", "X2"), ("F2", "VF")):
        p = sqo / r / "engine.out"
        if p.exists():
            texts.setdefault(arm, {}).setdefault(f"sampled {r}", []).append(p.read_text(errors="replace"))
    return {arm: {part: stats_of(t) for part, t in parts.items()} for arm, parts in texts.items()}


def stats_line(s):
    pl = s.get("placement")
    return (f"{s['requests']} requests, admissions per window "
            + (f"{s['per_window']:.3f} ({s['admissions']:,} in {s['windows']:,} windows, {s['fetch_lines']} fetch lines)"
               if s["per_window"] is not None else "- (no fetch line)")
            + (f"; placement main {pl['main']} % / helper {pl['helper']} % / PCIe {pl['pcie']} % / CPU {pl['cpu']} % of "
               f"{s['routed']:,} routed" if pl else "; placement -")
            + (f"; decode {s['decode_tps']} tok/s (engine)" if s.get("decode_tps") else ""))


def cmd_fetchstats(a):
    fs = fetch_stats(a.outdir, a.sampled)
    for arm, parts in fs.items():
        for part, s in parts.items():
            print(f"{arm} {part}: {stats_line(s)}")
    (Path(a.outdir) / "fetchstats.json").write_text(json.dumps(fs, indent=1) + "\n")
    return 0


def cmd_copycheck(a):
    ag = load("agg_copy_check", AGG)
    same = all(getattr(ag, n).pattern == globals()[n].pattern for n in ("hit_re", "cuda1_re", "gen_re", "start_re"))
    print(f"COPY CHECK {'OK' if same else 'FAILED'}: hit_re, cuda1_re, gen_re, start_re against {AGG}")
    return 0 if same else 1


# ================================================================================================ the speed numbers
def void_of(g, arm):
    sr = srm()
    return sr.arm_void(g, arm) + [k for k, (s_, _) in g.items() if s_ == "FAIL" and re.match(rf"fenv_{re.escape(arm)}_(bp|scr)", k)]


def unexercised(g, arm):
    return [k for k, (s_, _) in g.items() if s_ == "FAIL" and re.match(rf"line_{re.escape(arm)}_(bp|scr)", k)]


def target(name, x, b, nx_min=2):
    """one decode target: (have, above, below, above_half, below_half, text, nums)"""
    if len(x) < nx_min or len(b) < nx_min:
        return False, False, False, False, False, f"{name}: {len(x)} / {len(b)} counted passes - not priced", None
    mx, mb = (gm(x), gm(b)) if name == "screen decode geomean" else (st.mean(x), st.mean(b))
    d = mx / mb - 1
    noise = max(spread(x), spread(b))
    above, below = d > max(noise, GAIN_MIN), d < -noise
    ah, bh = d > max(noise / 2, GAIN_MIN), d < -noise / 2
    txt = (f"{name}: {mx:,.1f} vs {mb:,.1f} tok/s ({100 * d:+.1f} %; noise {100 * noise:.1f} %; {len(x)}/{len(b)} passes)"
           + (" above +max(noise, 1 %)" if above else "") + (" BELOW -noise" if below else ""))
    return True, above, below, ah, bh, txt, {"x": round(mx, 2), "ref": round(mb, 2), "change": round(d, 5),
                                             "noise": round(noise, 5), "passes": [len(x), len(b)]}


def excl(g, arm, step):
    """a start left out: a foreign GPU user / a chunk (basalt_speed_rules.excluded) or a test server left behind (void_)"""
    return srm().excluded(g, arm, step) + ([f"void_{arm}_{step}"] if gs(g, f"void_{arm}_{step}") == "FAIL" else [])


def gain_of(res, form, half=False):
    """GAIN from the targets' (above, below, above_half, below_half) by GAIN_FORM: any4 = a target above and none below;
    screen = the screen decode geomean above and no fixture below"""
    i_ab, i_be = (2, 3) if half else (0, 1)
    if form == "screen":
        sc = res.get("screen")
        return bool(sc) and sc[i_ab] and not any(v[i_be] for k, v in res.items() if k != "screen")
    return any(v[i_ab] for v in res.values()) and not any(v[i_be] for v in res.values())


def decode_gain(o, g, arm, ref="P", form=None):
    """(have, gain, text, nums, gain_half, below) under GAIN_FORM (or FORM); below = the fixtures below -noise"""
    form = form or GAIN_FORM
    sr = srm()
    g17 = sr.g17
    have, out, nums, res = True, [], {}, {}
    for t in FIXTURES:
        b = [v for _, v in sr.bp_vals(o, g, ref, "decode", t, "decode_tps")]
        x = [v for _, v in sr.bp_vals(o, g, arm, "decode", t, "decode_tps")]
        h, ab, be, ah, bh, txt, n = target(t, x, b)
        have &= h
        res[t] = (ab, be, ah, bh)
        out.append(txt + (" [no-loss check]" if form == "screen" else ""))
        nums[t] = n
    o_ = Path(o)
    left = [f"{a_}{k}" for a_ in (arm, ref) for k in (1, 2, 3) if excl(g, a_, f"scr{k}")
            and (o_ / "speed" / f"{a_}{k}n.jsonl").exists()]
    if left:
        have = False
        out.append(f"screen decode geomean: void pass(es) {', '.join(left)} still in speed/ - not priced")
    else:
        r, x = g17.screen_passes(o_, ref, amended=True), g17.screen_passes(o_, arm, amended=True)
        h, ab, be, ah, bh, txt, n = target("screen decode geomean", [v[0] for v in x.values()], [v[0] for v in r.values()], 3)
        have &= h
        res["screen"] = (ab, be, ah, bh)
        out.append(txt + (" [the primary target]" if form == "screen" else ""))
        nums["screen"] = n
    below = [k for k in FIXTURES if res.get(k) and res[k][1]]
    return have, gain_of(res, form), "; ".join(out), nums, gain_of(res, form, half=True), below


def screen_check(o, g, arm, ref="P", form=None):
    """B3: (True / False / None, text) - the per-workload no-loss, the prompt geomean by B3_PROMPT_FORM (or FORM), the
    save line"""
    form = form or B3_PROMPT_FORM
    sr = srm()
    g17 = sr.g17
    o = Path(o)
    left = [f"{a_}{k}" for a_ in (arm, ref) for k in (1, 2, 3) if excl(g, a_, f"scr{k}")
            and (o / "speed" / f"{a_}{k}n.jsonl").exists()]
    if left:
        return None, f"screen: void pass(es) {', '.join(left)} still in speed/ - not decided"
    r, x = g17.screen_passes(o, ref, amended=True), g17.screen_passes(o, arm, amended=True)
    if len(r) < 3 or len(x) < 3:
        prob = g17.pair_problems(o, arm) + g17.pair_problems(o, ref)
        return None, (f"screen: {ref} {len(r)} / {arm} {len(x)} complete passes of 3"
                      + (f" (engine-log pairing: {'; '.join(prob[:3])})" if prob else ""))
    wl_ok, wl_line = g17.wl_noloss(o, arm, ref=ref, amended=True)
    pb, px = gm([v[1] for v in r.values()]), gm([v[1] for v in x.values()])
    db, dx = gm([v[0] for v in r.values()]), gm([v[0] for v in x.values()])
    strict_ok, tol_ok = px >= pb, px >= pb * (1 - SCREEN_PROMPT_TOL)
    p_ok = strict_ok if form == "strict" else tol_ok
    other = (f"(info) the -1 % form: {'within' if tol_ok else 'below'} -1 %" if form == "strict" else
             f"(info) the strict form: {'not below' if strict_ok else 'below'}")
    txt = (f"screen prompt geomean {100 * (px / pb - 1):+.2f} % vs {ref} (B3_PROMPT_FORM {form}: "
           f"{('not below' if p_ok else 'BELOW') if form == 'strict' else ('within -1 %' if p_ok else 'BELOW -1 %')}; client "
           f"clock minus the save; {other}), decode geomean {100 * (dx / db - 1):+.2f} %; {wl_line}")
    if wl_ok is None:
        return None, txt
    ok = bool(wl_ok) and p_ok
    sv, sl = g17.save_rule(o, arm, ref, amended=True)
    if sv is not None:
        txt += "; " + sl[0]
        if sv == "FAIL":
            ok = False
        elif sv == "NOT DECIDED":
            return None, txt
    return ok, txt


def speed_verdict(o, g, arm, ref="P", gain_form=None, prompt_form=None):
    sr = srm()
    rec = {}
    vv = void_of(g, arm) + void_of(g, ref) + unexercised(g, ref)
    ux = unexercised(g, arm)
    have, gain, gl, nums, gain_half, below = decode_gain(o, g, arm, ref, gain_form)
    noloss_bad = below if (gain_form or GAIN_FORM) == "screen" else []   # (Karl 11-09: the fixtures are no-loss checks)
    h2, ok2, l2 = sr.decode_check(o, g, arm, ref)
    ok3, l3 = screen_check(o, g, arm, ref, prompt_form)
    rec.update(gain=gain, gain_text=gl, nums=nums, gain_half_range=gain_half, b2=[h2, ok2, l2], b3=[ok3, l3], void=vv,
               unexercised=ux)
    if vv:
        v = "VOID"
    elif ux:
        v = "NOT DECIDED"
    elif not have or not h2 or ok3 is None:
        v = "NOT DECIDED"
    elif not ok2 or not ok3 or noloss_bad:
        parts = []
        if not ok2 or noloss_bad:
            parts.append("decode" + (f": {', '.join(noloss_bad)} below -noise" if noloss_bad else ""))
        if not ok3:
            parts.append("screen")
        v = "FAIL (" + " / ".join(parts) + ")"
    else:
        v = "CANDIDATE" if gain else "NO GAIN"
    rec["verdict"] = v
    rec["text"] = (f"decode targets (GAIN_FORM {gain_form or GAIN_FORM}): {gl}; B2 check {('PASS' if ok2 else 'FAIL') if h2 else 'MISSING'}: {l2}; B3 "
                   f"{('PASS' if ok3 else 'FAIL') if ok3 is not None else 'NOT DECIDED'}: {l3}"
                   + (f"; void: {', '.join(vv)}" if vv else "") + (f"; UNEXERCISED: {', '.join(ux)}" if ux else "")
                   + f"; (info) with noise = half the range: {'GAIN' if gain_half else 'no gain'}")
    return rec


# ================================================================================================ the sampled part
def sampled_of(sqo):
    """{X1/X2: {sampled, sampled_why, quality, ...}, verify: {...}, verdict, present}"""
    sqo = Path(sqo)
    out = {"present": False}
    dp, vp = sqo / "decision.json", sqo / "verify-VF.json"
    try:
        d = json.loads(dp.read_text()) if dp.exists() else None
    except ValueError:
        d = None
    try:
        v = json.loads(vp.read_text()) if vp.exists() else None
    except ValueError:
        v = None
    out["verify"] = v or {"verdict": "NOT RUN", "why": "no verify-VF.json"}
    if d is None:
        return out
    out["present"] = True
    out["verdict"] = d.get("verdict")
    out["flags"] = d.get("flags") or []
    for x in ("X1", "X2"):
        c = (d.get("candidates") or {}).get(x, {})
        ov = (d.get("overall") or {}).get(x, {})
        out[x] = {"sampled": c.get("verdict", "NOT DECIDED"), "sampled_why": c.get("why", ""),
                  "quality": ov.get("verdict", "NOT DECIDED"), "read_back": ov.get("read_back")}
    return out


# ================================================================================================ the decision
def cmd_decide(a):
    o = Path(a.outdir)
    sqo = Path(a.sampled) if a.sampled else o / "sampled"
    g = read_gates(o / "gates.txt")
    flags, info = [], []
    rp = o / "rules.txt"
    rsha = hashlib.sha256(rp.read_bytes()).hexdigest()[:12] if rp.exists() else "missing"
    if not rp.exists() or rp.read_text() != rules_text():
        flags.append("the rule text (or an imported rule file) differs from the one frozen at the gap's start (rules.txt "
                     + rsha + ")")
    ev, et = exact_verdict(g)
    prio = g.get("priority")
    prio_txt = f"the priority rule stopped the gap ({prio[1][:200]})" if prio and prio[0] == "FAIL" else ""
    for k, (s_, d_) in sorted(g.items()):
        if k.startswith("priority_") and s_ == "INFO":
            flags.append(f"the priority check could not read the watch state ({k}): {d_[:120]}")
    fgn = sorted(k for k, (s_, _) in g.items() if k.startswith("foreign_") and s_ == "FAIL")
    if fgn:
        flags.append(f"start(s) left out for a foreign GPU user: {', '.join(fgn)}")
    vdn = sorted(k for k, (s_, _) in g.items() if k.startswith("void_") and s_ == "FAIL")
    if vdn:
        flags.append(f"start(s) voided - the run left its test server or an engine behind (stopped): {', '.join(vdn)}")
    if forms_bad():
        flags.append("a switch has no valid form: " + "; ".join(forms_bad()))
    ovr = g.get("priority_override", ("", ""))[1]
    bad_sq = {}
    for k, (s_, _) in g.items():
        m = re.match(r"^(?:env_sq|envsq_|fatal_sq|void_sq|foreign_sq)(VF|R1|R2|X1|X2)$", k)
        if m and s_ == "FAIL":
            bad_sq.setdefault(m.group(1), []).append(k)
    score_bad = gs(g, "env_sqscore") == "FAIL"
    skip_speed = g.get("skip_speed", ("", ""))[1]
    skip_sq = g.get("skip_sampled", ("", ""))[1]
    speed_ran = ev == "PASS" and any((o / "bp90").glob("*-decode-*.jsonl")) if (o / "bp90").is_dir() else False
    speed_ran = speed_ran or (ev == "PASS" and (o / "speed").is_dir() and any((o / "speed").glob("*n.jsonl")))
    sq = sampled_of(sqo)
    fs = fetch_stats(o, sqo)
    res = {"rules_sha": rsha, "build_vs_switch": [ev, et], "priority_stop": prio_txt, "candidates": {}, "flags": flags,
           "fetchstats": fs}
    lines = [f"ADAPT_FETCH GAP (work/r23/afetch-gap/gap-afetch.sh; rules afetch_rules.py, frozen {rsha}): P = P028x as "
             "served for tests (x28h + STRATA_HC_UPMIX=1, engine-r22p028x f4c4f654fb24) against F1 / F2 = the same config on "
             "engine-r23afetch (153ce47d3ef0) + STRATA_ADAPT_FETCH=1 / =2; two GPUs, the helper cache on, adaptation on",
             f"rules forms (frozen): B3_PROMPT_FORM {B3_PROMPT_FORM}, GAIN_FORM {GAIN_FORM}, ORDER_FORM {ORDER_FORM}",
             f"BUILD VS SWITCH (the fetch build with the switch unset = P028x bitwise): {ev}: {et}"]
    if ovr:
        lines.append(f"PRIORITY OVERRIDE: {ovr[:300]}")
    if prio_txt:
        lines.append(f"STOPPED: {prio_txt}; P028x was brought back")
    results = []
    for x in CANDS:
        sx = SQ_ARM[x]
        c = {}
        if ev != "PASS":
            sp = {"verdict": "NOT RUN", "text": f"build vs switch {ev}"}
        elif not speed_ran:
            sp = {"verdict": "NOT RUN", "text": skip_speed or prio_txt or "no speed start ran"}
        else:
            sp = speed_verdict(o, g, x)
        c["speed"] = sp
        if ev != "PASS":
            samp, sw, qual, rb = "NOT RUN", f"build vs switch {ev}", "NOT RUN", sq["verify"]
        elif not sq["present"]:
            samp, sw = "NOT RUN", skip_sq or prio_txt or "the sampled part did not run (no sampled/decision.json)"
            rb = sq["verify"]
            qual = "FAIL" if rb.get("verdict") == "FAIL" else "NOT RUN"
        else:
            samp, sw, qual, rb = sq[sx]["sampled"], sq[sx]["sampled_why"], sq[sx]["quality"], dict(sq["verify"])
            nd = [f"{r}: {', '.join(sorted(bad_sq[r]))}" for r in ("R1", "R2", sx) if r in bad_sq]
            if score_bad:
                nd.append("the scorer's env check (env_sqscore FAIL)")
            if nd and samp in ("PASS", "FAIL"):   # a verdict on a start that was not the arm, or was voided, does not stand
                sw = f"sq.py gave {samp} ({sw[:100]}), but the gap's gates on its starts failed: {'; '.join(nd)}"
                samp = "NOT DECIDED"
            if "VF" in bad_sq and rb.get("verdict") == "PASS":
                rb.update(verdict="NOT DECIDED", why=f"{rb.get('why', '')}; but VF's start gates failed: {', '.join(sorted(bad_sq['VF']))}")
            rbv_ = rb.get("verdict")
            mine = "FAIL" if "FAIL" in (samp, rbv_) else ("PASS" if samp == rbv_ == "PASS" else "NOT DECIDED")
            if not nd and "VF" not in bad_sq and mine != qual:
                flags.append(f"{x}: sq.py's overall {qual} differs from sampled {samp} + read-back {rbv_} -> {mine} (used)")
            qual = mine
        c.update(sampled=samp, sampled_why=sw, quality=qual, read_back=rb)
        st_x = fs.get(x, {})
        c["admissions"] = {part: s["per_window"] for part, s in st_x.items()}
        sv = sp["verdict"]
        if ev == "FAIL" or qual == "FAIL" or sv.startswith("FAIL"):
            why = [w for w, bad in ((f"build vs switch {ev}", ev == "FAIL"), ("quality FAIL", qual == "FAIL"),
                                    (f"speed {sv}", sv.startswith("FAIL"))) if bad]
            prop = "FAIL (" + "; ".join(why) + ")"
        elif ev == "PASS" and qual == "PASS" and sv == "CANDIDATE":
            prop = "PROPOSAL for Karl: exact with the switch unset, quality PASS, a decode gain"
        elif ev == "PASS" and qual == "PASS" and sv == "NO GAIN":
            prop = "QUALITY PASS, NO SPEED GAIN"
        else:
            miss = [w for w, ok in ((f"build vs switch {ev}", ev == "PASS"), (f"quality {qual}", qual == "PASS"),
                                    (f"speed {sv}", sv in ("CANDIDATE", "NO GAIN"))) if not ok]
            prop = "NOT DECIDED (" + "; ".join(miss) + ")"
        c["proposal"] = prop
        res["candidates"][x] = c
        tg = ""
        if isinstance(sp.get("nums"), dict):
            tg = ", ".join(f"{k} {100 * v['change']:+.1f} %" for k, v in sp["nums"].items() if v)
        rbv = rb.get("verdict", "NOT RUN") if isinstance(rb, dict) else "NOT RUN"
        lines += [f"{NAMES[x]}: {prop}",
                  f"  speed vs P: {sv} - {sp.get('text', '')}",
                  f"  sampled ({sx} vs R1, noise twin R2): {samp} - {sw}",
                  f"  read-back (VF = X2 + STRATA_ADAPT_FETCH_VERIFY=1 + STRATA_ADAPT_CHECKRES=1): {rbv} - "
                  f"{(rb or {}).get('why', '')}"
                  + (f" (mismatch lines {rb.get('mismatch_lines')}, read back {rb.get('read_back')}, differ {rb.get('differ')})"
                     if isinstance(rb, dict) and rb.get("read_back") is not None else ""),
                  f"  QUALITY (sampled AND read-back): {qual}"]
        for part, s in st_x.items():
            lines.append(f"  {part}: {stats_line(s)}")
        short_sp = sv + (f" ({tg})" if tg else "")
        adm = [f"{s['per_window']:.2f}" for s in st_x.values() if s.get("per_window") is not None]
        results.append(f"{x}: {prop.split(' (')[0] if prop.startswith(('FAIL', 'NOT DECIDED')) else prop.split(':')[0]}; "
                       f"speed {short_sp}; quality {qual} (sampled {samp}, read-back {rbv})"
                       + (f"; admissions/window {'/'.join(adm)}" if adm else ""))
    for part, s in fs.get("P", {}).items():
        info.append(f"INFO P {part}: {stats_line(s)}")
    if ev == "PASS" and speed_ran:
        h, gn, gl, _, _, _ = decode_gain(o, g, "F2", "F1")
        info.append(f"INFO F2 vs F1 (the =2 part's own effect): {'GAIN' if gn else ('no gain' if h else 'not priced')}: {gl}")
    if sq.get("present"):
        info.append(f"INFO the sampled test: {sq.get('verdict')} (sampled/decision.txt)")
        flags += [f"(sampled) {f}" for f in sq.get("flags") or []]
    res["info"] = info
    anyp = any(c_["proposal"].startswith("PROPOSAL") for c_ in res["candidates"].values())
    tail = info + [f"FLAG {f}" for f in flags] + [
        "NOTHING SWITCHES: P028x stays served." + (" A PROPOSAL is Karl's call (and the same patch carries to the v0.2.13 "
                                                   "port)." if anyp else " Karl decides.")]
    txt = "\n".join(lines + tail) + "\n"
    rl = (f"build vs switch {ev}" + (f"; STOPPED by the priority rule" if prio_txt else "")
          + (f"; priority hold OVERRIDDEN ({ovr[:120]})" if ovr else "") + "; " + " | ".join(results))
    res["result_line"] = rl
    (o / "decision.txt").write_text(txt)
    (o / "decision.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    (o / "result-line.txt").write_text(rl + "\n")
    if not getattr(a, "quiet", False):
        print(txt, end="")
    return 0


def cmd_rules(a):
    t = rules_text()
    Path(a.out).write_text(t)
    print(f"rules frozen: {a.out} sha {hashlib.sha256(t.encode()).hexdigest()[:12]}")
    return 0


# ================================================================================================ the selftest
def selftest(scratch):
    """synthetic data only (no GPU, no engine, no server, no gap component run): everything under SCRATCH"""
    sc = Path(scratch)
    if sc.exists():
        shutil.rmtree(sc)
    sc.mkdir(parents=True)
    fails = []

    def check(name, cond, detail=""):
        print(f"{'ok  ' if cond else 'FAIL'} {name}" + (f": {str(detail)[:400]}" if detail and not cond else ""), flush=True)
        if not cond:
            fails.append(name)

    def ns(**k):
        return argparse.Namespace(**k)

    # ---- the priority rule
    def state(repos, raw=None):
        p = sc / f"state-{len(list(sc.glob('state-*')))}.json"
        p.write_text(raw if raw is not None else json.dumps({"repos": repos, "polls": 3, "last_poll": "2026-11-09 15:00"}))
        return p
    W = {"Qwen4-Flash-Q4.gguf": 123}
    ent = lambda kind, priv, gat, w: {"kind": kind, "access": {"private": priv, "gated": gat}, "weights": w,  # noqa: E731
                                      "first_seen": "x"}
    cases = [("empty", {}, "CLEAR"), ("open Flash with weights", {"unsloth/Qwen4-Flash-GGUF": ent("Flash", False, False, W)}, "HOLD"),
             ("gated manual", {"Qwen/Qwen4-Flash": ent("Flash", False, "manual", W)}, "CLEAR"),
             ("private", {"Qwen/Qwen4-Flash": ent("Flash", True, False, W)}, "CLEAR"),
             ("open, no weights", {"Qwen/Qwen4-Flash": ent("Flash", False, False, {})}, "CLEAR"),
             ("open 27B", {"Qwen/Qwen4-27B": ent("27B", False, False, W)}, "CLEAR"),
             ("access missing", {"Qwen/Qwen4-Flash": {"kind": "Flash", "weights": W}}, "CLEAR"),
             ("one of two", {"Qwen/Qwen4-27B": ent("27B", False, False, W), "x/Qwen4-Flash": ent("Flash", False, False, W)}, "HOLD")]
    for name, repos, want in cases:
        v, t = priority(state(repos))
        check(f"priority {name} -> {want}", v == want, t)
    check("priority torn file -> UNKNOWN", priority(state(None, raw="{\"repos\": {"), tries=2, wait=0.01)[0] == "UNKNOWN")
    check("priority no state file -> UNKNOWN (the driver: busy)", priority(sc / "nope.json")[0] == "UNKNOWN"
          and "missing" in priority(sc / "nope.json")[1])
    found = str(state({"a/Qwen4-Flash": ent("Flash", False, False, W)}))
    rc = cmd_priority(ns(state=found, override=str(sc / "no-override")))
    check("priority exit 10 on a find (no override)", rc == 10)
    (sc / "ovr-ok").write_text("2026-11-14: Karl: the Qwen4 day-one work is done (gates passed, served)\n")
    (sc / "ovr-undated").write_text("day-one done\n")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_priority(ns(state=found, override=str(sc / "ovr-ok")))
    check("priority override (dated reason line) -> OVERRIDDEN, exit 0, names the reason", rc == 0
          and "PRIORITY OVERRIDDEN" in buf.getvalue() and "2026-11-14: Karl" in buf.getvalue(), buf.getvalue())
    with redirect_stdout(io.StringIO()):
        rc = cmd_priority(ns(state=found, override=str(sc / "ovr-undated")))
    check("priority override without a dated first line -> ignored, HOLD (exit 10)", rc == 10)
    with redirect_stdout(io.StringIO()):
        rc = cmd_priority(ns(state=str(state({})), override=str(sc / "ovr-ok")))
    check("priority no find + an override -> CLEAR (exit 0)", rc == 0)
    # ---- the shape gap's result: only DONE counts as ran (review 11-09 m1 / m9)
    for name, text, want in (("missing", None, False), ("refused", "not started (busy): x - nothing changed\n", False),
                             ("hard", "not started (hard): missing: x - nothing changed\n", False),
                             ("not open", "INTERRUPTED: the gap was not open; nothing switched\n", False),
                             ("interrupted", "INTERRUPTED: the gap may still be open (tmp/port-gap.lockpid): close it\n", False),
                             ("not run", "not run: engines still running after 8080 stopped (nothing changed)\n", False),
                             ("done", "DONE (information only, nothing switched; ...)\n", True),
                             ("kernel", "kernel check FAILED inside the gap - the gap is left OPEN\n", False),
                             ("kernel error", "KERNEL ERROR during the gap - stopped at once, P028x back on 8080\n", False),
                             ("end failed", "port_gap4.sh end FAILED - 8080 and the research queue need a look\n", False),
                             ("empty", "", False)):
        p = sc / f"shape-{name.replace(' ', '_')}.txt"
        if text is not None:
            p.write_text(text)
        check(f"shapecheck {name} -> {'RAN' if want else 'NOT RUN'}", shape_ran(p)[0] == want)
    # ---- the configs
    cf = sc / "configs"
    rc = cmd_arms(ns(outdir=str(cf), spec=str(SPEC), no_sha=True, log_dir=None, gate="cfg", gates=str(sc / "g-cfg.txt")))
    check("arms + cfgcheck PASS (P F0 F1 F2 = P028x stripped + delta = sampled R1 X1 X2)",
          rc == 0 and gs(read_gates(sc / "g-cfg.txt"), "cfg") == "PASS", read_gates(sc / "g-cfg.txt"))
    cp, c1 = json.loads((cf / "P.json").read_text()), json.loads((cf / "F1.json").read_text())
    x28 = json.loads(X28H_CFG.read_text())
    check("P = x28h + STRATA_HC_UPMIX=1 (env, args), engine-r22p028x", cp["env"] == dict(x28["env"], STRATA_HC_UPMIX="1")
          and cp["args"] == x28["args"] and cp["exe"] == str(E28) and "--vision" not in cp["args"])
    check("F1 = P + engine-r23afetch + STRATA_ADAPT_FETCH=1 only", c1["exe"] == str(E_AF) and c1["args"] == cp["args"]
          and c1["env"] == dict(cp["env"], STRATA_ADAPT_FETCH="1"))
    c1["env"]["STRATA_ADAPT_FETCH_VERIFY"] = "1"
    (cf / "F1.json").write_text(json.dumps(c1))
    cmd_cfgcheck(ns(outdir=str(cf), spec=str(SPEC), no_sha=True, gate="cfg2", gates=str(sc / "g-cfg.txt")))
    check("cfgcheck catches a stray fetch switch in F1", gs(read_gates(sc / "g-cfg.txt"), "cfg2") == "FAIL")
    cmd_arms(ns(outdir=str(cf), spec=str(SPEC), no_sha=True, log_dir=str(sc / "logs"), gate=None, gates=None))
    check("arms --log-dir: the logs elsewhere, cfgcheck still PASS", json.loads((cf / "P.json").read_text())["log"]
          == str(sc / "logs/engine-r23af-P.log") and cmd_cfgcheck(ns(outdir=str(cf), spec=str(SPEC), no_sha=True, gate=None,
                                                                      gates=None)) == 0)
    sp2 = json.loads(SPEC.read_text())
    sp2["arms"]["X2"]["env"]["STRATA_ADAPT_FETCH"] = "1"
    (sc / "spec-x2.json").write_text(json.dumps(sp2))
    cmd_cfgcheck(ns(outdir=str(cf), spec=str(sc / "spec-x2.json"), no_sha=True, gate="cfg3", gates=str(sc / "g-cfg.txt")))
    check("cfgcheck catches a speed arm that is not the sampled arm (X2 at =1)", gs(read_gates(sc / "g-cfg.txt"), "cfg3") == "FAIL")
    # ---- fetchenv (mock env) and the start lines
    gf = sc / "g-fenv.txt"
    for name, arm, env_add, sha, want in (("F1 as configured", "F1", {}, "153ce47d3ef0", "PASS"),
                                          ("F1 + VERIFY behind it", "F1", {"STRATA_ADAPT_FETCH_VERIFY": "1"}, "153ce47d3ef0", "FAIL"),
                                          ("F1 wrong binary", "F1", {}, "f4c4f654fb24", "FAIL"),
                                          ("P with a fetch switch", "P", {"STRATA_ADAPT_FETCH": "2"}, "f4c4f654fb24", "FAIL"),
                                          ("P with STRATA_DEBUG", "P", {"STRATA_DEBUG": "1"}, "f4c4f654fb24", "FAIL"),
                                          ("P as configured", "P", {}, "f4c4f654fb24", "PASS")):
        cfg = json.loads((cf / f"{arm}.json").read_text())
        me = sc / "menv.json"
        me.write_text(json.dumps({"procs": [{"pid": 1, "env": dict(cfg["env"], **env_add), "sha12": sha}]}))
        gn = "fe-" + name.replace(" ", "_")      # (a gate name has no space: the gates file splits on the first one)
        cmd_fetchenv(ns(exe=cfg["exe"], config=str(cf / f"{arm}.json"), mock_env=str(me), gate=gn, gates=str(gf)))
        check(f"fetchenv {name} -> {want}", gs(read_gates(gf), gn) == want)
    ON1 = "strata serve: STRATA_ADAPT_FETCH=1: the PCIe share takes each layer's most-routed misses and admits those routed >= 2.00\n"
    ON2 = ON1.replace("=1:", "=2:")
    OFF = "strata serve: STRATA_ADAPT_FETCH is off (no PCIe share)\n"
    for name, text, arm, want in (("F1 on", ON1, "F1", True), ("F1 off", OFF, "F1", False), ("F1 with =2", ON2, "F1", False),
                                  ("F1 none", "x\n", "F1", False), ("F2 on", ON2, "F2", True), ("P none", "x\n", "P", True),
                                  ("P with a line", ON1, "P", False), ("F2 on + off", ON2 + OFF, "F2", False)):
        check(f"startline {name} -> {'PASS' if want else 'FAIL'}", startline_check(text, arm)[0] == want)
    # ---- engine-log numbers against agg.py (its own code, run on a synthetic log)
    def req(gen, ms, H, L, O, R, N, adm=None, w=400):
        s = (f"strata serve: prompt 38 tokens = 0 reused + 38 read in 120 ms (316.7 tok/s), {gen} generated in {ms} ms "
             f"({1000 * gen / ms:.1f} tok/s), drafts accepted 600 of 1100, 0 checkpoints, {w} windows, 2.75 drafts per window\n")
        if adm is not None:
            s += f"strata serve: fetch: {adm} admissions in {w} windows ({adm / w:.2f} per window)\n"
        s += (f"strata serve: decode expert cache hit rate: {100 * H / L:.1f}% ({H} hits / {L} lookups); {O} more read by the "
              f"GPU over PCIe or from another GPU ({100 * O / R:.1f}% of all {R} routed)\n")
        s += f"strata serve: CUDA1: {N} expert entries, 92 active layer launches, 7.4 MiB returned in this request\n"
        return s
    log = ("strata generate: memory guard: x\nstrata serve: engine started\n" + ON1 + req(1000, 7000, 60000, 80000, 25000, 105000, 18000, 520)
           + req(1100, 7300, 61000, 81000, 24000, 105000, 17500, 480) + "strata serve: engine started\n"
           + req(900, 6500, 50000, 70000, 20000, 90000, 15000, 300))
    (sc / "agg.log").write_text(log)
    s = stats_of([log])
    ag = load("agg_selftest", AGG)
    buf = io.StringIO()
    with redirect_stdout(buf):
        ag.main(str(sc / "agg.log"))
    m = re.search(r"main hits ([\d.]+) %, helper ([\d.]+) %, PCIe ([\d.]+) %, CPU ([\d.]+) %", buf.getvalue())
    check("placement = agg.py's own numbers on the same log", m and [float(x) for x in m.groups()]
          == [s["placement"][k] for k in ("main", "helper", "pcie", "cpu")], (buf.getvalue(), s))
    check("admissions per window = sum / sum (1300 in 1200 windows)", s["admissions"] == 1300 and s["windows"] == 1200
          and s["per_window"] == round(1300 / 1200, 3) and s["fetch_lines"] == 3, s)
    check("copycheck: the copied regexes are agg.py's", cmd_copycheck(ns()) == 0)
    # ---- step 1
    P_ = ("PASS", "x")
    eg = {"e7_F0": P_, "env_F0_e7": P_, "logits_F0L40": P_, "env_F0_pfy-F0L40": P_}
    check("exact all PASS -> PASS", exact_verdict(eg)[0] == "PASS")
    check("exact e7 6/7 -> FAIL", exact_verdict({**eg, "e7_F0": ("FAIL", "6/7")})[0] == "FAIL")
    check("exact long40 differs -> FAIL", exact_verdict({**eg, "logits_F0L40": ("FAIL", "2 of 40")})[0] == "FAIL")
    check("exact env FAIL -> NOT DECIDED", exact_verdict({**eg, "env_F0_e7": ("FAIL", "x"), "e7_F0": ("FAIL", "x")})[0] == "NOT DECIDED")
    check("exact long40 not run -> NOT DECIDED", exact_verdict({k: v for k, v in eg.items() if "40" not in k})[0] == "NOT DECIDED")
    # ---- one decode target (the numbers)
    h, ab, be, ah, bh, txt, _ = target("conv", [145.0, 146.0, 145.5], [140.0, 140.5, 139.8])
    check("target +3.8 % (noise 0.7 %) is above", h and ab and not be, txt)
    h, ab, be, ah, bh, txt, _ = target("conv", [141.0, 140.5, 140.8], [140.0, 140.5, 139.8])
    check("target +0.6 % is not above (1 % floor)", h and not ab and not be, txt)
    h, ab, be, ah, bh, txt, _ = target("conv", [141.5, 137.5, 139.5], [140.0, 136.0, 138.0])
    check("target +1.1 % with noise 2.9 %: not above; with half the range (1.5 %) not above either", h and not ab and not ah, txt)
    h, ab, be, ah, bh, txt, _ = target("conv", [144.0, 140.0, 142.0], [140.0, 136.0, 138.0])
    check("target +2.9 % with noise 2.9 %: not above; half the range: above", h and not ab and ah, txt)
    check("target with 1 pass -> not priced", not target("conv", [140.0], [140.0, 141.0])[0])

    # ---- end to end: synthetic B2, the stored port-0211 screen (engine logs paired) as every arm's screen
    src = WS / "results/r23/port-0211/gap/speed"
    D0 = {"conv": [140.1, 139.6, 140.6], "struct": [225.3, 224.0, 226.1], "prose": [129.1, 128.4, 129.8]}

    def mk(name, dec, scr=None, gates_extra=(), sampled=None, verify="PASS", drop=()):
        o = sc / name
        for d in ("bp90", "speed", "englog", "sampled"):
            (o / d).mkdir(parents=True)
        (o / "rules.txt").write_text(rules_text())
        (o / "summary.txt").write_text("=== 2026-11-09 20:00:00 selftest\n")
        lines = [f"{k} {v[0]} {v[1]}" for k, v in eg.items()] + ["build_switch PASS x"]
        for arm, f in dec.items():
            for k in (1, 2, 3):
                if (arm, f"bp{k}") in drop:
                    continue
                (o / "bp90" / f"{arm}-decode-{k}.jsonl").write_text("".join(
                    json.dumps({"pass": k, "test": t, "decode_tps": round(D0[t][k - 1] * f.get(t, f.get("all", 1.0)), 2)}) + "\n"
                    for t in FIXTURES))
                lines += [f"{g_}_{arm}_bp{k}decode PASS x" for g_ in ("env", "fenv", "line")]
                (o / "englog" / f"bp-{arm}-decode-{k}.englog").write_text(
                    (ON1 if arm == "F1" else ON2 if arm == "F2" else "") + req(1000, 7000, 60000, 80000, 25000, 105000, 18000,
                                                                              None if arm == "P" else (300 if arm == "F1" else 500)))
        for arm, f in (scr if scr is not None else {a_: {k_: v_ for k_, v_ in dec[a_].items() if k_ == "all"} for a_ in dec}).items():
            for k in (1, 2, 3):
                if (arm, f"scr{k}") in drop:
                    continue
                for s_ in "nar":
                    shutil.copy(src / f"B{k}{s_}.englog", o / "speed" / f"{arm}{k}{s_}.englog")
                    recs = [json.loads(x) for x in (src / f"B{k}{s_}.jsonl").read_text().splitlines() if x.strip()]
                    for r in recs:
                        r["decode_tps"] = round(r["decode_tps"] * f.get(r["id"], f.get("all", 1.0)), 2)
                        if "prompt" in f and r.get("ttft_s"):
                            r["ttft_s"] = r["ttft_s"] / f["prompt"]
                    (o / "speed" / f"{arm}{k}{s_}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
                lines += [f"{g_}_{arm}_scr{k} PASS x" for g_ in ("env", "fenv", "line")]
        lines += list(gates_extra)
        (o / "gates.txt").write_text("\n".join(lines) + "\n")
        sq_ = {"X1": "PASS", "X2": "PASS"} if sampled is None else sampled
        if sq_ != "absent":
            ov = {x: {"verdict": "FAIL" if v == "FAIL" or verify == "FAIL" else ("PASS" if v == "PASS" and verify == "PASS"
                                                                                  else "NOT DECIDED"),
                      "sampled": v, "read_back": {"VF": verify}} for x, v in sq_.items()}
            (o / "sampled" / "decision.json").write_text(json.dumps(
                {"verdict": "ALL PASS", "flags": [], "candidates": {x: {"verdict": v, "why": f"D2 ({v})"} for x, v in sq_.items()},
                 "overall": ov}))
        (o / "sampled" / "verify-VF.json").write_text(json.dumps({"verdict": verify, "why": f"read-back {verify}",
                                                                   "read_back": 412, "differ": 0 if verify == "PASS" else 3,
                                                                   "mismatch_lines": 0 if verify == "PASS" else 3}))
        for r_, arm in (("X1", "F1"), ("X2", "F2"), ("R1", "P")):
            (o / "sampled" / r_).mkdir()
            (o / "sampled" / r_ / "engine.out").write_text((ON1 if arm == "F1" else ON2 if arm == "F2" else "")
                                                           + req(512, 4000, 30000, 40000, 12000, 52000, 9000,
                                                                 None if arm == "P" else 150))
        return o

    def run(o):
        cmd_decide(ns(outdir=str(o), sampled=None, quiet=True))
        return json.loads((o / "decision.json").read_text()), (o / "decision.txt").read_text()
    UP = {"P": {}, "F1": {"all": 1.04}, "F2": {"all": 1.004}}
    d, txt = run(mk("e2e", UP))
    C = d["candidates"]
    check("e2e: F1 speed CANDIDATE (+4 %), F2 NO GAIN (+0.4 %)", C["F1"]["speed"]["verdict"] == "CANDIDATE"
          and C["F2"]["speed"]["verdict"] == "NO GAIN", {x: C[x]["speed"].get("text", "")[:300] for x in C})
    check("e2e: proposals (F1 PROPOSAL, F2 QUALITY PASS NO SPEED GAIN)", C["F1"]["proposal"].startswith("PROPOSAL")
          and C["F2"]["proposal"] == "QUALITY PASS, NO SPEED GAIN", {x: C[x]["proposal"] for x in C})
    check("e2e: quality PASS both, read-back PASS", C["F1"]["quality"] == "PASS" and C["F2"]["quality"] == "PASS"
          and "read-back (VF" in txt)
    check("e2e: admissions per window listed (B2 F1 0.75, sampled X1 0.375)", C["F1"]["admissions"].get("B2") == 0.75
          and C["F1"]["admissions"].get("sampled X1") == 0.375, C["F1"]["admissions"])
    check("e2e: placement lines, P INFO, F2 vs F1 INFO", "placement main" in txt and "INFO P B2" in txt and "INFO F2 vs F1" in txt)
    check("e2e: B3 line has the 11-07 save line and the outside-engine INFO", "chat-cache save [11-07 amendment]" in txt
          and "(info) outside-engine time" in txt, txt[:2000])
    check("e2e: no flags", not d["flags"], d["flags"])
    check("e2e: result line", d["result_line"].startswith("build vs switch PASS; F1: PROPOSAL for Karl; speed CANDIDATE"),
          d["result_line"])
    # decode loss in F2's struct (-5 %) -> B2 FAIL -> speed FAIL -> FAIL
    C = run(mk("e2e-loss", {**UP, "F2": {"struct": 0.95}}))[0]["candidates"]
    check("F2 struct -5 % -> speed FAIL (decode), proposal FAIL", C["F2"]["speed"]["verdict"].startswith("FAIL (decode")
          and C["F2"]["proposal"].startswith("FAIL"), C["F2"]["speed"].get("text", "")[:300])
    # a per-workload decode loss in F1's screen (W1-think -20 % in every pass) -> B3 FAIL
    C = run(mk("e2e-wl", UP, scr={"P": {}, "F1": {"all": 1.04, "W1-think": 0.8}, "F2": {}}))[0]["candidates"]
    check("F1 W1-think -20 % in the screen -> speed FAIL (screen)", C["F1"]["speed"]["verdict"] == "FAIL (screen)",
          C["F1"]["speed"].get("text", "")[-600:])
    # B3_PROMPT_FORM: -2 % fails in both forms; -0.5 % passes "tol1" (Karl 11-09, the frozen form) and fails "strict"
    o = mk("e2e-pr2", UP, scr={"P": {}, "F1": {"all": 1.04, "prompt": 0.98}, "F2": {}})
    C = run(o)[0]["candidates"]
    g_ = read_gates(o / "gates.txt")
    check("B3 tol1 (frozen): F1 screen prompt -2 % -> FAIL (screen)", C["F1"]["speed"]["verdict"] == "FAIL (screen)"
          and "B3_PROMPT_FORM tol1: BELOW -1 %" in C["F1"]["speed"]["text"], C["F1"]["speed"].get("text", "")[-700:])
    sv = speed_verdict(o, g_, "F1", prompt_form="strict")
    check("B3 strict: F1 screen prompt -2 % -> FAIL (screen)", sv["verdict"] == "FAIL (screen)" and "B3_PROMPT_FORM strict: BELOW" in sv["text"])
    o = mk("e2e-pr05", UP, scr={"P": {}, "F1": {"all": 1.04, "prompt": 0.995}, "F2": {}})
    C = run(o)[0]["candidates"]
    g_ = read_gates(o / "gates.txt")
    check("B3 tol1 (frozen): F1 screen prompt -0.5 % -> CANDIDATE (within -1 %), the strict form as INFO 'below'",
          C["F1"]["speed"]["verdict"] == "CANDIDATE" and "B3_PROMPT_FORM tol1: within -1 %" in C["F1"]["speed"]["text"]
          and "strict form: below" in C["F1"]["speed"]["text"], C["F1"]["speed"].get("text", "")[-700:])
    sv = speed_verdict(o, g_, "F1", prompt_form="strict")
    check("B3 strict: F1 screen prompt -0.5 % -> FAIL (screen), the -1 % form as INFO 'within'",
          sv["verdict"] == "FAIL (screen)" and "the -1 % form: within -1 %" in sv["text"], sv["text"][-700:])
    # GAIN_FORM: B2 +4 % with a flat screen = NO GAIN under "screen" (Karl 11-09, frozen), a GAIN under "any4"; +6 % on
    # the screen too = GAIN in both; a fixture below -noise (struct -1.5 %, inside the B2 check's 2.3 %) with the screen
    # +6 % = NO GAIN in both
    o = mk("e2e-flat", UP, scr={"P": {}, "F1": {}, "F2": {}})
    C = run(o)[0]["candidates"]
    g_ = read_gates(o / "gates.txt")
    check("GAIN_FORM screen (frozen): B2 +4 %, screen flat -> NO GAIN; any4: CANDIDATE",
          C["F1"]["speed"]["verdict"] == "NO GAIN" and speed_verdict(o, g_, "F1", gain_form="any4")["verdict"] == "CANDIDATE",
          C["F1"]["speed"].get("text", "")[:500])
    o = mk("e2e-scrup", UP, scr={"P": {}, "F1": {"all": 1.06}, "F2": {}})
    g_ = read_gates(o / "gates.txt")
    v1, v2 = (speed_verdict(o, g_, "F1", gain_form=f_) for f_ in ("screen", "any4"))
    check("GAIN_FORM screen and any4: screen decode +6 % (noise 0.8 %) -> CANDIDATE in both",
          v1["verdict"] == "CANDIDATE" and v2["verdict"] == "CANDIDATE" and "[the primary target]" in v1["text"], v1["text"][:600])
    o = mk("e2e-scrfl", {**UP, "F1": {"all": 1.04, "struct": 0.985}}, scr={"P": {}, "F1": {"all": 1.06}, "F2": {}})
    g_ = read_gates(o / "gates.txt")
    v1, v2 = (speed_verdict(o, g_, "F1", gain_form=f_) for f_ in ("screen", "any4"))
    check("struct -1.5 % below -noise (the B2 check still PASS): GAIN_FORM screen -> FAIL (decode: struct below -noise), "
          "a no-loss failure; any4 -> NO GAIN", v1["verdict"] == "FAIL (decode: struct below -noise)" and v2["verdict"] == "NO GAIN"
          and "BELOW -noise" in v1["text"], (v1["verdict"], v2["verdict"], v1["text"][:500]))
    check("gain_of: screen form needs the screen target", not gain_of({"conv": (True, False, True, False)}, "screen")
          and gain_of({"conv": (True, False, True, False)}, "any4"))
    # a fatal line in a P start voids both; a fenv FAIL in F1 voids F1 only; a line FAIL in F2 = NOT DECIDED
    C = run(mk("e2e-fatalP", UP, gates_extra=["fatal_P_bp2decode FAIL x"]))[0]["candidates"]
    check("fatal in P -> F1 and F2 VOID", C["F1"]["speed"]["verdict"] == "VOID" and C["F2"]["speed"]["verdict"] == "VOID")
    C = run(mk("e2e-fenv", UP, gates_extra=["fenv_F1_scr2 FAIL x"]))[0]["candidates"]
    check("fenv FAIL in F1 -> F1 VOID, F2 judged", C["F1"]["speed"]["verdict"] == "VOID" and C["F2"]["speed"]["verdict"] == "NO GAIN")
    C = run(mk("e2e-line", UP, gates_extra=["line_F2_bp1decode FAIL UNEXERCISED"]))[0]["candidates"]
    check("line FAIL in F2 -> F2 NOT DECIDED (UNEXERCISED)", C["F2"]["speed"]["verdict"] == "NOT DECIDED"
          and "UNEXERCISED" in C["F2"]["speed"]["text"])
    # a foreign GPU user in F1's B2 pass 2: left out (its file moved), F1 judged on 2 passes, flagged
    o = mk("e2e-foreign", UP, gates_extra=["foreign_F1_bp2decode FAIL x"])
    (o / "bp90" / "F1-decode-2.jsonl").unlink()
    d, _ = run(o)
    check("foreign in F1 bp2: left out, F1 CANDIDATE on 2 passes, flagged", d["candidates"]["F1"]["speed"]["verdict"] == "CANDIDATE"
          and d["candidates"]["F1"]["speed"]["nums"]["conv"]["passes"] == [2, 3] and any("foreign" in f for f in d["flags"]))
    # one B2 pass only -> NOT DECIDED; a missing screen pass -> NOT DECIDED
    C = run(mk("e2e-miss", UP, drop=(("F1", "bp2"), ("F1", "bp3"))))[0]["candidates"]
    check("F1 with 1 B2 pass -> NOT DECIDED", C["F1"]["speed"]["verdict"] == "NOT DECIDED")
    C = run(mk("e2e-scr", UP, drop=(("F2", "scr3"),)))[0]["candidates"]
    check("F2 with 2 screen passes -> NOT DECIDED", C["F2"]["speed"]["verdict"] == "NOT DECIDED"
          and "2 complete passes of 3" in C["F2"]["speed"]["text"], C["F2"]["speed"].get("text", "")[-400:])
    # step 1 not PASS -> speed and sampled NOT RUN, proposal FAIL
    o = mk("e2e-exact", UP, gates_extra=["e7_F0 FAIL exact7 r23af-F0: 6/7, slots MATCHED"], sampled="absent")
    d, txt = run(o)
    C = d["candidates"]
    check("exact7 6/7 -> build vs switch FAIL; speed + sampled NOT RUN; FAIL", d["build_vs_switch"][0] == "FAIL"
          and C["F1"]["speed"]["verdict"] == "NOT RUN" and C["F1"]["sampled"] == "NOT RUN"
          and C["F1"]["proposal"].startswith("FAIL (build vs switch FAIL"), {x: (C[x]["speed"]["verdict"], C[x]["proposal"]) for x in C})
    # the sampled verdicts: X2 FAIL -> F2 quality FAIL; VF FAIL -> both FAIL; sampled part absent -> NOT RUN
    C = run(mk("e2e-x2", UP, sampled={"X1": "PASS", "X2": "FAIL"}))[0]["candidates"]
    check("X2 sampled FAIL -> F2 quality FAIL, F1 PASS", C["F2"]["quality"] == "FAIL" and C["F1"]["quality"] == "PASS"
          and C["F2"]["proposal"].startswith("FAIL (quality FAIL"))
    C = run(mk("e2e-vf", UP, verify="FAIL", sampled={"X1": "NOT DECIDED", "X2": "NOT DECIDED"}))[0]["candidates"]
    check("VF read-back FAIL -> both quality FAIL", C["F1"]["quality"] == "FAIL" and C["F2"]["quality"] == "FAIL"
          and C["F1"]["read_back"]["verdict"] == "FAIL")
    o = mk("e2e-nosq", UP, sampled="absent", gates_extra=["skip_sampled INFO the deadline: 30 min left, 42 needed"])
    (o / "sampled" / "verify-VF.json").unlink()
    C = run(o)[0]["candidates"]
    check("sampled part not run -> NOT RUN with its reason, proposal NOT DECIDED", C["F1"]["sampled"] == "NOT RUN"
          and "deadline" in C["F1"]["sampled_why"] and C["F1"]["proposal"].startswith("NOT DECIDED"))
    # the priority rule stopped the gap after step 1
    o = mk("e2e-prio", {}, scr={}, sampled="absent", gates_extra=["priority FAIL before B2 pass 1: PRIORITY HOLD: x/Qwen4-Flash",
                                                                  "skip_speed INFO the priority rule"])
    (o / "sampled" / "verify-VF.json").unlink()
    d, txt = run(o)
    check("priority stop: listed, speed NOT RUN, result line says STOPPED", "STOPPED: the priority rule" in txt
          and d["candidates"]["F1"]["speed"]["verdict"] == "NOT RUN" and "STOPPED by the priority rule" in d["result_line"])
    # a changed rule text -> FLAG; the frozen text holds the switches and this file's own sha
    o = mk("e2e-rules", UP)
    (o / "rules.txt").write_text("other\n")
    check("rules.txt changed -> FLAG", any("rule text" in f for f in run(o)[0]["flags"]))
    rt = rules_text()
    check("rules text: the switches at the freeze and this file's own sha (and sq_client.py, the spec)",
          "THE SWITCHES AT THE FREEZE:\n  B3_PROMPT_FORM = tol1\n  GAIN_FORM = screen\n  ORDER_FORM = vf-first" in rt
          and f"work/r23/afetch-gap/afetch_rules.py {sha256_file(AG / 'afetch_rules.py', 16)}" in rt
          and "sampled-qwen/sq_client.py" in rt and "sampled-qwen/spec-adaptfetch.json" in rt)
    global GAIN_FORM
    keep = GAIN_FORM
    GAIN_FORM = "bogus"
    check("forms_bad catches a switch outside its forms", forms_bad() == ["GAIN_FORM='bogus' (want one of ('any4', 'screen'))"])
    GAIN_FORM = keep
    check("the frozen switches are Karl's 11-09 answers (tol1, screen, vf-first)", (B3_PROMPT_FORM, GAIN_FORM, ORDER_FORM)
          == ("tol1", "screen", "vf-first") and not forms_bad())
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_forms(ns())
    check("forms prints the switches for the driver", rc == 0 and "ORDER_FORM=vf-first" in buf.getvalue())
    # the wording: "the same patch carries to the v0.2.13 port" only beside a PROPOSAL
    check("the port note only with a PROPOSAL", "carries to the v0.2.13 port" in (sc / "e2e" / "decision.txt").read_text()
          and "carries to the v0.2.13 port" not in (sc / "e2e-exact" / "decision.txt").read_text())
    # the gap's gates on the sampled starts
    for name, extra, w1, w2, wq in (
            ("envsq_X1", ["envsq_X1 FAIL ENV CHECK FAILED"], "NOT DECIDED", "PASS", ("NOT DECIDED", "PASS")),
            ("fatal_sqR1", ["fatal_sqR1 FAIL 1 line(s)"], "NOT DECIDED", "NOT DECIDED", ("NOT DECIDED", "NOT DECIDED")),
            ("env_sqR2", ["env_sqR2 FAIL x"], "NOT DECIDED", "NOT DECIDED", ("NOT DECIDED", "NOT DECIDED")),
            ("env_sqscore", ["env_sqscore FAIL ENV CHECK FAILED"], "NOT DECIDED", "NOT DECIDED", ("NOT DECIDED", "NOT DECIDED")),
            ("void_sqVF", ["void_sqVF FAIL left behind"], "PASS", "PASS", ("NOT DECIDED", "NOT DECIDED")),
            ("foreign_sqX1", ["foreign_sqX1 FAIL seen during sqX1"], "NOT DECIDED", "PASS", ("NOT DECIDED", "PASS")),
            ("foreign_sqVF", ["foreign_sqVF FAIL seen during sqVF"], "PASS", "PASS", ("NOT DECIDED", "NOT DECIDED")),
            ("foreign_sqVF retried", ["foreign_sqVF FAIL seen", "foreign_sqVF RETRIED try 1; tried again"], "PASS", "PASS",
             ("PASS", "PASS"))):
        C = run(mk(f"e2e-g-{name}", UP, gates_extra=extra))[0]["candidates"]
        check(f"sampled gate {name} FAIL -> sampled {w1} / {w2}, quality {wq[0]} / {wq[1]}",
              (C["F1"]["sampled"], C["F2"]["sampled"], C["F1"]["quality"], C["F2"]["quality"]) == (w1, w2) + wq,
              {x: (C[x]["sampled"], C[x]["quality"], C[x]["sampled_why"][:120]) for x in C})
    C = run(mk("e2e-g-vfboth", UP, verify="FAIL", sampled={"X1": "PASS", "X2": "PASS"}, gates_extra=["fatal_sqVF FAIL x"]))[0]["candidates"]
    check("a read-back FAIL stays FAIL with VF's fatal gate", C["F1"]["quality"] == "FAIL" and C["F1"]["read_back"]["verdict"] == "FAIL")
    # a speed start voided (its test server left behind): its file moved by the driver, judged on the rest, flagged
    o = mk("e2e-void", UP, gates_extra=["void_F2_bp3decode FAIL the run left its test server behind"])
    (o / "bp90" / "F2-decode-3.jsonl").unlink()
    d, _ = run(o)
    check("void_ speed start: left out (F2 on 2 passes), flagged", d["candidates"]["F2"]["speed"]["nums"]["conv"]["passes"] == [2, 3]
          and any("voided" in f for f in d["flags"]))
    o = mk("e2e-void2", UP, gates_extra=["void_F1_scr2 FAIL x"])
    C = run(o)[0]["candidates"]
    check("void_ screen start whose files are still in place -> NOT DECIDED", C["F1"]["speed"]["verdict"] == "NOT DECIDED"
          and "void pass(es) F12" in C["F1"]["speed"]["text"])
    # the override in the decision
    o = mk("e2e-ovr", UP, gates_extra=["priority_override INFO PRIORITY OVERRIDDEN: x; HOLD OVERRIDDEN by tmp/afetch-priority-done: 2026-11-14: Karl"])
    d, txt = run(o)
    check("the priority override is named in the decision and the result line", "PRIORITY OVERRIDE: " in txt
          and "priority hold OVERRIDDEN" in d["result_line"])
    print(f"afetch_rules selftest: {len(fails)} failure(s)" + (f": {', '.join(fails)}" if fails else ""))
    return 1 if fails else 0


# ================================================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)

    def sub(name, *pos, gates=True):
        p = sp.add_parser(name)
        for x in pos:
            p.add_argument(x)
        if gates:
            p.add_argument("--gate")
            p.add_argument("--gates")
        return p
    p = sub("priority", gates=False)
    p.add_argument("--state", default=str(STATE))
    p.add_argument("--override", default=str(PRIO_DONE))
    sub("forms", gates=False)
    p = sub("shapecheck", gates=False)
    p.add_argument("--result", default=str(SHAPE_RES))
    for n in ("arms", "cfgcheck"):
        p = sub(n, "outdir")
        p.add_argument("--spec", default=str(SPEC))
        p.add_argument("--no-sha", action="store_true", help="(the driver's --mock only) skip the engine sha / string checks")
        p.add_argument("--log-dir", help="(the driver's --mock only) the arms' engine logs elsewhere than logs/")
    p = sub("fetchenv", "exe", "config")
    p.add_argument("--mock-env")
    p = sub("startline", "englog")
    p.add_argument("--arm", required=True, choices=ARMS)
    sub("exact", "outdir")
    p = sub("fetchstats", "outdir", gates=False)
    p.add_argument("--sampled")
    sub("rules", "out", gates=False)
    p = sub("decide", "outdir", gates=False)
    p.add_argument("--sampled")
    p.add_argument("--quiet", action="store_true")
    sub("copycheck", gates=False)
    sub("selftest", "scratch", gates=False)
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest(a.scratch)
    f = {"priority": cmd_priority, "forms": cmd_forms, "shapecheck": cmd_shapecheck, "arms": cmd_arms, "cfgcheck": cmd_cfgcheck,
         "fetchenv": cmd_fetchenv, "startline": cmd_startline, "exact": cmd_exact, "fetchstats": cmd_fetchstats,
         "rules": cmd_rules, "decide": cmd_decide, "copycheck": cmd_copycheck}[a.cmd]
    return f(a)


if __name__ == "__main__":
    sys.exit(main())
