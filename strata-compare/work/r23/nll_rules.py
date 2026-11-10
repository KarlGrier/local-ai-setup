#!/usr/bin/env python3
"""nll_rules.py - round 23 item 6 (Karl 11-04): the rules of the NLL many-positions gap (work/r23/gap-nll.sh), written
BEFORE the gap ran (11-04). The bound is PLAN.md's proposal (results/r23/nll-many/PLAN.md section 3) exactly; the tool
is work/r23/nll-many/score.py (its `compare` writes result.json, these rules re-derive every verdict from its numbers and
cross-check score.py's own).

Karl 11-04: "adopt the new bound once the gap has validated the offline head against the engine's own output. Apply it
going forward; past verdicts stay as recorded, with a note."

VALIDATION (the first judging step; nothing is judged without it)
  validate_ref  score.py validate on the ref arm (P021n): the engine's own window logits at the 5 check prompts against
                the offline head on the full read's dumped row at the same position -> AGREES (mean KL <= 0.05, each <=
                0.5) = PASS. Anything else (DOES NOT AGREE, no data, the arm did not run) = the gap stops judging:
                NOT JUDGED, the bound is NOT adopted, no candidate gets a verdict. Fallback (PLAN.md section 1): the
                engine-side scoring mode (C++ + a build - Karl's OK).
  validate_<x>  the other arms: reported (INFO). A candidate whose window and batched rows disagree is flagged beside
                its verdict (its batched rows are what compare scores).

THE BOUND ("nll-many 11-04"; positions: every 8th batched prompt row from 1,024 on over the 11 long texts - score.py run
--set long11 --rows all:8; compare --min-pos 1024, blocks of 2,048 tokens inside a text, 10,000 bootstrap replicates,
seed 20261104; reference ref = P021n, rounding references R1 = unfused (STRATA_PF_FUSED=0), R2 = cpushare
(STRATA_PREFILL_CPU_SHARE=0.4)):
  NLL      d_X = mean(NLL_X - NLL_ref) over the positions every arm scored, se_X = the block-bootstrap sd of d_X
           bound = 1.10 x max(|d_R1|, |d_R2|)                  (Karl's 10-26 spread bound)
           FAIL          d_cand > bound + 1.645 x se_cand     (+ a one-sided 95 % noise margin on the candidate's own d)
           UNDERPOWERED  not FAIL and se_cand > 0.01 nats      (too few positions to see a 0.05-nat loss; the fix is more
                                                               text - --max-len 65536 or more texts -, not a decision)
           PASS          otherwise
  KL       unchanged (kernel_rule2/3's form), on the same positions: mean <= 1.10 x the larger reference's mean, p90 <=
           1.10 x the larger p90, rows with KL > 1 <= the larger count + 1, changed top-1 <= 1.10 x the larger count
  verdict  PASS = every KL check and NLL PASS; FAIL = a KL check or NLL FAIL; UNDERPOWERED = KL checks pass, NLL
           UNDERPOWERED; NOT DECIDED = the arm did not run cleanly (run / env gate) or is missing from result.json
  identity ref2 (P021n again) must be exactly ref: d = 0, every position's difference 0, KL 0 (and the kept rows byte for
           byte: ident_ref2); x28h-nov2 must be byte-identical to x28h (gap 16: v2 on = off on P028x; ident_nov2).
           A miss is a FLAG in the decision (the dump path or the build is not deterministic) - the verdicts are still
           reported, Karl reads them with it.
  power    se of every candidate <= 0.01 -> "powered"; otherwise the recommendation is to extend the texts.
  extra    (INFO) --from-rows strides 2 / 8 (every 16th / 64th row): what N buys; --block-scan; with the optional arms
           (x28h-unfused, x28h-cpushare) the same bound with P028x (x28h) as the reference, for later gates.

ADOPTION
  validated -> decision "JUDGED"; ADOPTED-BOUND.json (the rule above, its parameters, from this gap on - later gates
  apply it in place of kernel_rule3's point NLL rule; the KL checks stay) and PAST-VERDICTS-NOTE.txt (every past verdict
  stays as recorded - gaps 8-17, the 10-30 FAILs, the DeepSeek gates -; the note says what the many-position data says
  about the arms measured here: v2, r28h, x28h). Not validated -> "NOT JUDGED", neither file is written.

Subcommands:
  envwatch JOB CONFIG [--env K=V ...] [--kill] [--gate G --gates F]   the score.py engine's environment as it starts
           (found by /proc/PID/exe in the job's process tree, never by a command-line pattern): the config's env with
           pf_yardstick's fixed env over it and --env over that; no other STRATA_* (the dump hooks and STRATA_MON_GPU
           allowed); STRATA_ROUTE_TAIL_SKIP=0; the config's GPU count; score.py's fixed engine args. Exit 0 = OK.
  ident DIR_A DIR_B [--gate --gates]    the kept rows (a.*.npy) and window logits (first.*) byte for byte
  decide ROOT                           -> ROOT/decision.txt, decision.json (+ ADOPTED-BOUND.json, PAST-VERDICTS-NOTE.txt)
  selftest [--dir D]                    dry runs on PLAN.md's stored past-case results and synthetic gaps (no GPU)
"""
import argparse
import importlib.util
import json
import math
import os
import shutil
import signal
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
WS = Path("/home/USER/ai-speed-testing/strata-compare")
PFY = WS / "work/r22/pf_yardstick.py"
TOL, Z, SE_CAP, KL_HIGH = 1.10, 1.645, 0.01, 1.0
REF, REFS = "ref", ("unfused", "cpushare")
CANDS = ("ref2", "v2", "x28h", "x28h-nov2", "r28h")
OPTIONAL = ("x28h-unfused", "x28h-cpushare")
ALLOWED_EXTRA = {"STRATA_MON_GPU", "STRATA_DUMP_FIRST_LOGITS", "STRATA_PREFILL_DUMP_R_ALL", "STRATA_PREFILL_DUMP_R"}
RULE = {"name": "nll-many 11-04", "plan": "results/r23/nll-many/PLAN.md section 3", "tool": "work/r23/nll-many/score.py",
        "positions": "every 8th batched prompt row from 1,024 on, 11 long texts (run --set long11 --rows all:8)",
        "min_pos": 1024, "block_tokens": 2048, "boot": 10000, "seed": 20261104, "tol": TOL, "z_one_sided": Z,
        "se_cap": SE_CAP,
        "nll": "FAIL if d_cand > 1.10 x max(|d_R1|, |d_R2|) + 1.645 x se(d_cand); else UNDERPOWERED if se(d_cand) > 0.01; "
               "else PASS",
        "kl": "unchanged: mean, p90 <= 1.10 x the larger reference; KL > 1 rows <= larger + 1; changed top-1 <= 1.10 x larger",
        "references": "ref P021n (configs/r21n1.json); R1 unfused (STRATA_PF_FUSED=0); R2 cpushare "
                      "(STRATA_PREFILL_CPU_SHARE=0.4) - or the served build's own pair when it is the reference"}
# PLAN.md section 4: what was recorded before this gap (kept as recorded; the note only adds what this gap measured)
PAST = [
    ("v2", "P021m's served v2 (gap 8 `v2`; the 10-30 FAIL)", "rule3 FAIL at 36 positions (d +0.143, bound 0.086)"),
    ("r28h", "the v0.2.8 port without switches (gap 15 `r28h`; = gap 12 `r27a`, gap 14 `r27h-noboth`)",
     "rule3 FAIL at 36 positions (d +0.118)"),
    ("x28h", "P028x as served (gap 16 `x28h` = `x28h-nov2` = gap 17 `p210` rows)", "rule3 PASS at 36 positions (d -0.024)"),
    (None, "gap 14 `r27h-nofork`", "rule3 FAIL at 36 positions - not measured in this gap"),
    (None, "gap 9 `pcie` (adopted 10-23 under kernel_rule2)", "adopted; rule3 would FAIL at 36 - not measured here"),
    (None, "int8 IMMA (gaps 8 + 9)", "rule3 PASS, KL top-1 FAIL - not measured here"),
    (None, "DeepSeek B vs A (11-03) and the stored DeepSeek gates", "as recorded - not measured here (teacher-forced data)"),
]


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------ the engine's environment
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


def want_of(cfg, sets, fixed_env):
    want = dict(cfg.get("env", {}))
    want.update(fixed_env)                     # score.py run: env.update(cfg env); env.update(FIXED_ENV); then --env
    for kv in sets or []:
        k, _, v = kv.partition("=")
        want[k] = v
    return want


def check_engine(env, argv, want, ngpu, args_want):
    bad = [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]
    bad += [f"{k}={env[k]} (not in the config)" for k in sorted(env) if k.startswith("STRATA_") and k not in want
            and k not in ALLOWED_EXTRA]
    if env.get("STRATA_ROUTE_TAIL_SKIP") != "0":
        bad.append(f"STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}")
    n = len([x for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
    if n != ngpu:
        bad.append(f"{n} GPU(s) in CUDA_VISIBLE_DEVICES (want {ngpu}, as the config)")
    if not any(k in env for k in ("STRATA_PREFILL_DUMP_R_ALL", "STRATA_PREFILL_DUMP_R")):
        bad.append("no prompt-row dump hook set")
    if len(argv) < 2 or argv[1] != "--serve":
        bad.append("not the --serve engine")
    bad += [f"{k} {last_val(argv, k)} (want {v})" for k, v in args_want.items() if last_val(argv, k) != v]
    if "--short-read" in argv:
        bad.append("--short-read given (score.py reads with the default 64-token short read)")
    return bad


def envwatch(a):
    cfg = json.loads(Path(a.config).read_text())
    qq = load("pf_yardstick", PFY).tool()
    want = want_of(cfg, a.env, qq.FIXED_ENV)
    fx = dict(zip(qq.FIXED[0::2], qq.FIXED[1::2]))
    fx.update({"--prefill": "auto", "--kv": "fp16"})             # score.py run's own replacements
    args_want = {k: fx[k] for k in ("--expert-cache", "--pcie-frac", "--kv", "--prefill", "--adapt-every",
                                    "--suffix-draft", "--prompt-cache")}
    ngpu = len([x for x in cfg.get("env", {}).get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
    exe = os.path.realpath(cfg["exe"])
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
            bad = check_engine(env, argv, want, ngpu, args_want)
            seen[pid] = bad
            killed = ""
            if bad and a.kill:
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed = "; STOPPED (by pid) before it measures"
                except OSError:
                    killed = "; could not stop it"
            print(f"engine pid {pid}: {len(want)} env keys, STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}, "
                  f"{len([x for x in env.get('CUDA_VISIBLE_DEVICES', '').split(',') if x])} GPU(s)"
                  + (f" -> ENV MISMATCH {', '.join(bad)}{killed}" if bad else " -> ENV OK"), flush=True)
        if done:
            break
        time.sleep(0.5)
    bad_all = [b for v in seen.values() for b in v]
    if not seen:
        line = f"no engine {exe} started in job {a.job}"
    elif bad_all:
        line = f"{sum(1 for v in seen.values() if v)} of {len(seen)} engine start(s) not as configured: " + "; ".join(sorted(set(bad_all)))
    else:
        line = (f"{len(seen)} engine start(s), {len(want)} env keys as configured (+ pf_yardstick's fixed env"
                + (f", {' '.join(a.env)}" if a.env else "") + "), no other STRATA_*, score.py's engine args")
    ok = bool(seen) and not bad_all
    print(("ENV CHECK OK: " if ok else "ENV CHECK FAILED - the arm is void: ") + line, flush=True)
    gate(a, "PASS" if ok else "FAIL", line[:400])
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ identity
def ident(a):
    A, B = Path(a.a), Path(a.b)
    names = sorted(p.name for p in A.glob("a.*.npy")) + sorted(p.name for p in A.glob("first.*"))
    diff = [n for n in names if not (B / n).exists() or not same_bytes(A / n, B / n)]
    missing = sorted(p.name for p in B.glob("a.*.npy") if not (A / p.name).exists())
    ok = bool(names) and not diff and not missing
    line = (f"{len(names) - len(diff)} of {len(names)} kept-row / window-logit files identical ({A.name} vs {B.name})"
            + (f"; differ: {', '.join(diff[:6])}" if diff else "") + (f"; only in {B.name}: {', '.join(missing)}" if missing else ""))
    print(line + (" -> IDENTICAL" if ok else " -> DIFFER"))
    gate(a, "PASS" if ok else "FAIL", line[:400])
    return 0 if ok else 1


def same_bytes(x, y, chunk=1 << 22):
    if x.stat().st_size != y.stat().st_size:
        return False
    with open(x, "rb") as f, open(y, "rb") as g:
        while True:
            u, v = f.read(chunk), g.read(chunk)
            if u != v:
                return False
            if not u:
                return True


# ------------------------------------------------------------------------------------------------ the rules
def read_gates(root):
    g = {}
    p = Path(root) / "gates.txt"
    for line in p.read_text().splitlines() if p.exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)
    return g


def judge(res, cand):
    """the proposed rule from result.json's numbers (independent of score.py's own 'verdicts')"""
    nl, kl = res["nll"]["arms"], res["kl"]
    refs = res["refs"]
    bound = TOL * max(abs(nl[r]["d"]) for r in refs)
    d, se = nl[cand]["d"], nl[cand]["se"]
    margin = Z * se
    if d > bound + margin:
        nll = "FAIL"
    elif se > SE_CAP:
        nll = "UNDERPOWERED"
    else:
        nll = "PASS"
    kb = {"mean": TOL * max(kl[r]["mean"] for r in refs), "p90": TOL * max(kl[r]["p90"] for r in refs),
          "high": max(kl[r]["high"] for r in refs) + 1, "flips": TOL * max(kl[r]["flips"] for r in refs)}
    k = kl[cand]
    kfail = [n for n, bad in (("mean", k["mean"] > kb["mean"]), ("p90", k["p90"] > kb["p90"]),
                              ("KL>1 rows", k["high"] > kb["high"]), ("top-1", k["flips"] > kb["flips"])) if bad]
    verdict = "FAIL" if (kfail or nll == "FAIL") else ("UNDERPOWERED" if nll == "UNDERPOWERED" else "PASS")
    # cross-check with score.py's own computation (the same rule, written there before the gap)
    sv = res.get("verdicts", {}).get(cand, {})
    agree = (sv.get("ci") in (None, nll)) and (sorted(sv.get("kl_fails", kfail)) == sorted(kfail))
    return {"d": d, "se": se, "lo": nl[cand]["lo"], "hi": nl[cand]["hi"], "bound": bound, "margin": margin,
            "excess": d - bound, "z": (d - bound) / se if se > 0 else float("nan"), "nll": nll, "kl": k, "kl_bounds": kb,
            "kl_fails": kfail, "verdict": verdict, "scorepy_agrees": agree, "frac_exact0": nl[cand].get("frac_exact0"),
            "n": res["nll"]["n"], "blocks": res["nll"]["blocks"]}


def fmt_j(x, j):
    z = f"{j['z']:+.1f} se" if math.isfinite(j["z"]) else "se 0"
    return (f"{x:10s} d {j['d']:+.4f} [{j['lo']:+.4f}, {j['hi']:+.4f}] se {j['se']:.4f} | bound {j['bound']:.4f} + margin "
            f"{j['margin']:.4f} (excess {j['excess']:+.4f} = {z}) -> NLL {j['nll']}; KL mean {j['kl']['mean']:.5f} p90 "
            f"{j['kl']['p90']:.5f} >1 {j['kl']['high']} top-1 {j['kl']['flips']} -> "
            + ("KL PASS" if not j["kl_fails"] else "KL FAIL (" + ", ".join(j["kl_fails"]) + ")") + f" => {j['verdict']}"
            + ("" if j["scorepy_agrees"] else "  [score.py's own verdict DIFFERS - check]"))


def decide(a):
    root = Path(a.root)
    g = read_gates(root)
    st = lambda k: g.get(k, ("MISSING", ""))[0]
    L, flags = [], []
    out = {"rule": RULE, "written": time.strftime("%F %T"), "status": None, "candidates": {}, "flags": flags}
    L.append(f"NLL many-positions gap - decision ({out['written']}; rules: work/r23/nll_rules.py, written before the gap)")
    if g.get("kfail"):
        flags.append("a kernel check failed during the gap (the gap stays open; Karl decides)")
    # ---- 1 validation: the offline head against the engine's own output (ref arm)
    v = g.get("validate_ref", ("MISSING", "the ref arm was not validated"))
    L.append(f"validation (score.py validate, ref arm): {v[0]} {v[1]}")
    ran = {x: st(f"run_{x}") == "PASS" and st(f"env_{x}") == "PASS" for x in (REF,) + REFS + CANDS + OPTIONAL}
    resp = root / "result.json"
    why = None
    if v[0] != "PASS":
        why = "the offline head was not validated against the engine's own output (validate_ref " + v[0] + ")"
    elif not all(ran[x] for x in (REF,) + REFS):
        why = "the reference or a rounding reference did not run cleanly: " + ", ".join(
            f"{x} (run {st('run_' + x)}, env {st('env_' + x)})" for x in (REF,) + REFS if not ran[x])
    elif not resp.exists():
        why = "score.py compare did not write result.json (compare gate: " + " ".join(g.get("compare", ("MISSING", ""))) + ")"
    if why:
        out["status"] = "NOT JUDGED"
        L.append(f"=> NOT JUDGED: {why}. No candidate gets a verdict and the new bound is NOT adopted"
                 + (" (fallback: the engine-side scoring mode - C++ + a build, Karl's OK)" if v[0] != "PASS" else "") + ".")
        for x in CANDS:
            out["candidates"][x] = {"verdict": "NOT JUDGED"}
        return finish(root, out, L, adopted=False)
    res = json.loads(resp.read_text())
    out["status"] = "JUDGED"
    nl = res["nll"]
    L.append(f"positions: {nl['n']} in {nl['blocks']} blocks; NLL of ref there {nl['base']:.4f}; references "
             + ", ".join(f"{r} d {nl['arms'][r]['d']:+.4f} (se {nl['arms'][r]['se']:.4f})" for r in res["refs"])
             + f"; bound 1.10 x max |d_R| = {TOL * max(abs(nl['arms'][r]['d']) for r in res['refs']):.4f}")
    for x in CANDS:
        if x not in res["nll"]["arms"]:
            out["candidates"][x] = {"verdict": "NOT DECIDED", "why": f"not in result.json (run {st('run_' + x)}, env {st('env_' + x)})"}
            L.append(f"{x:10s} NOT DECIDED: did not run cleanly (run {st('run_' + x)}, env {st('env_' + x)})")
            continue
        j = judge(res, x)
        vx = st(f"validate_{x}")
        j["validate"] = vx
        out["candidates"][x] = j
        L.append(fmt_j(x, j) + ("" if vx in ("PASS", "MISSING") else f"  [validate {vx}: its window and batched rows disagree]"))
        if not j["scorepy_agrees"]:
            flags.append(f"{x}: these rules and score.py's own verdict differ")
    # ---- identity checks
    c = out["candidates"]
    if "ref2" in c and "d" in c["ref2"]:
        exact = c["ref2"]["d"] == 0 and c["ref2"].get("frac_exact0") == 1.0 and c["ref2"]["kl"]["mean"] == 0
        L.append(f"identity ref2 = ref: d {c['ref2']['d']:+.6f}, exactly-0 positions {c['ref2'].get('frac_exact0', 0):.4f}, "
                 f"KL mean {c['ref2']['kl']['mean']:.2e}; bytes: {st('ident_ref2')} {g.get('ident_ref2', ('', ''))[1]}")
        if not exact or st("ident_ref2") == "FAIL":
            flags.append("ref2 is not exactly ref: the dump path or P021n is not deterministic (PLAN.md expected d = 0)")
        elif st("ident_ref2") != "PASS":
            flags.append("ref2's kept rows were not compared byte for byte (ident_ref2 " + st("ident_ref2") + ")")
    if st("ident_nov2") != "MISSING":
        L.append(f"identity x28h-nov2 = x28h (gap 16: v2 on = off on P028x): {st('ident_nov2')} {g['ident_nov2'][1]}")
        if st("ident_nov2") != "PASS":
            flags.append("x28h-nov2 is not byte-identical to x28h (gap 16 found them bit-identical)")
    # ---- power
    real = [x for x in ("v2", "x28h", "x28h-nov2", "r28h") if "se" in c.get(x, {})]
    under = [x for x in real if c[x]["se"] > SE_CAP]
    if real:
        ses = sorted(c[x]["se"] for x in real)
        L.append(f"power: se {ses[0]:.4f}-{ses[-1]:.4f} over {', '.join(real)} (cap {SE_CAP}) -> "
                 + ("POWERED: a loss of ~0.05 nats/token over the bound fails ~99 % of the time" if not under else
                    f"UNDERPOWERED for {', '.join(under)}: extend the texts (score.py run --max-len 65536: ~+40 % text, se x ~0.85; or add texts)"))
        out["power"] = {"se": {x: c[x]["se"] for x in real}, "underpowered": under}
    # ---- INFO: what N buys, block scan, the P028x-reference result
    for s, name in (("s2", "every 16th row"), ("s8", "every 64th row")):
        p = root / f"result-{s}.json"
        if p.exists():
            r2 = json.loads(p.read_text())
            L.append(f"what N buys ({name}: {r2['nll']['n']} positions): se " + ", ".join(
                f"{x} {r2['nll']['arms'][x]['se']:.4f}" for x in r2["nll"]["arms"]))
            out[f"stride_{s}"] = {x: r2["nll"]["arms"][x]["se"] for x in r2["nll"]["arms"]}
    if res.get("block_scan"):
        for spec, se in res["block_scan"].items():
            L.append(f"block scan {spec:>5s}: se " + ", ".join(f"{x} {v:.4f}" for x, v in se.items()))
    px = root / "result-x28h.json"
    if px.exists():
        rx = json.loads(px.read_text())
        L.append(f"INFO - P028x (x28h) as the reference, its own rounding references {', '.join(rx['refs'])}: bound "
                 f"{TOL * max(abs(rx['nll']['arms'][r]['d']) for r in rx['refs']):.4f}")
        out["x28h_reference"] = {}
        for x in rx["cands"]:
            j = judge(rx, x)
            out["x28h_reference"][x] = j
            L.append("  " + fmt_j(x, j))
    # ---- the other arms' validation (INFO)
    vs = [f"{x} {st('validate_' + x)}" for x in REFS + CANDS + OPTIONAL if st("validate_" + x) != "MISSING"]
    if vs:
        L.append("validate on the other arms (INFO): " + ", ".join(vs))
    L.append("=> JUDGED. The new bound is ADOPTED from this gap on (Karl 11-04): ADOPTED-BOUND.json. Past verdicts stay "
             "as recorded: PAST-VERDICTS-NOTE.txt.")
    return finish(root, out, L, adopted=True)


def finish(root, out, L, adopted):
    if out["flags"]:
        L.append("FLAGS: " + " | ".join(out["flags"]))
    (root / "decision.txt").write_text("\n".join(L) + "\n")
    (root / "decision.json").write_text(json.dumps(out, indent=1, default=str))
    if adopted:
        v = read_gates(root).get("validate_ref", ("", ""))
        (root / "ADOPTED-BOUND.json").write_text(json.dumps(dict(RULE, adopted=out["written"], validated_by=f"validate_ref {v[0]} {v[1]}",
                                                                 gap=str(root), applies="to gates after this one; past verdicts stay as recorded"), indent=1))
        N = [f"Past verdicts and the NLL many-positions gap ({out['written']})",
             "Karl 11-04: past verdicts stay as recorded. This note adds what the new data says; it changes no recorded verdict.",
             ""]
        for arm, what, rec in PAST:
            c = out["candidates"].get(arm) if arm else None
            now = ("not measured in this gap" if c is None else
                   f"at {c['n']} positions: d {c['d']:+.4f} [{c['lo']:+.4f}, {c['hi']:+.4f}], se {c['se']:.4f} -> "
                   f"{c['verdict']} under nll-many 11-04" if "d" in c else c.get("verdict", "NOT DECIDED"))
            N.append(f"- {what}: recorded {rec}. This gap: {now}. The recorded verdict stands.")
        (root / "PAST-VERDICTS-NOTE.txt").write_text("\n".join(N) + "\n")
    print("\n".join(L))
    return 0 if adopted else 1


# ------------------------------------------------------------------------------------------------ dry runs
def selftest(a):
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    past = WS / "results/r23/nll-many"
    bad = []

    def chk(name, ok, detail=""):
        print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + detail) if detail else ''}")
        if not ok:
            bad.append(name)
    # 1 the rule re-derived from every stored past result agrees with score.py's own verdicts (PLAN.md section 4)
    n = 0
    for p in sorted(past.glob("past-*.json")):
        res = json.loads(p.read_text())
        for x in res["cands"]:
            j = judge(res, x)
            n += 1
            chk(f"past {p.stem} {x}: {j['nll']} / KL {'PASS' if not j['kl_fails'] else 'FAIL'}", j["scorepy_agrees"],
                f"score.py {res['verdicts'][x]['ci']} {res['verdicts'][x]['kl_fails']}")
    chk(f"{n} stored candidates re-judged", n > 0)
    g8 = json.loads((past / "past-gap8-pfy.json").read_text())
    chk("gap 8 v2 (the 10-30 FAIL) is UNDERPOWERED at 36 positions", judge(g8, "v2")["nll"] == "UNDERPOWERED")
    ds = json.loads((past / "past-ds41-B.json").read_text())
    chk("DeepSeek B passes the proposed rule (PLAN.md: S +0.6 se)", judge(ds, "cand-B")["nll"] == "PASS")

    # 2 synthetic gaps: a full decision tree
    def synth(name, gates, res=None, extra=None):
        r = d / name
        if r.exists():
            shutil.rmtree(r)
        r.mkdir()
        (r / "gates.txt").write_text("".join(f"{k} {s} {t}\n" for k, s, t in gates))
        if res is not None:
            (r / "result.json").write_text(json.dumps(res))
        for k, v in (extra or {}).items():
            (r / k).write_text(json.dumps(v))
        rc = decide(argparse.Namespace(root=str(r)))
        return r, rc, json.loads((r / "decision.json").read_text())
    arms = (REF,) + REFS + CANDS
    ok_g = [(f"run_{x}", "PASS", "synthetic") for x in arms] + [(f"env_{x}", "PASS", "synthetic") for x in arms]

    def fake(ds_, ses, kl=None):
        A = {}
        for x, dv in ds_.items():
            A[x] = {"d": dv, "lo": dv - 2 * ses[x], "hi": dv + 2 * ses[x], "se": ses[x], "sd_pos": 1.1, "mean_abs": 0.3,
                    "frac_gt05": 0.2, "frac_exact0": 1.0 if (dv == 0 and ses[x] == 0) else 0.0, "deff": 3.0}
        K = {x: dict({"n": 31400, "mean": 0.010, "p90": 0.02, "high": 3, "max": 2.0, "flips": 300}, **(kl or {}).get(x, {}))
             for x in ds_}
        K["ref2"] = {"n": 31400, "mean": 0.0, "p90": 0.0, "high": 0, "max": 0.0, "flips": 0}
        return {"ref": "ref", "refs": list(REFS), "cands": list(CANDS), "nll": {"n": 31400, "blocks": 130, "base": 1.9,
                "arms": A, "bound_rule3": 0}, "kl": K, "kl_bounds": {}, "verdicts": {}}
    se = {x: 0.008 for x in REFS + CANDS}
    se["ref2"] = 0.0
    base = {"unfused": 0.004, "cpushare": -0.006, "ref2": 0.0, "v2": 0.003, "x28h": 0.0, "x28h-nov2": 0.0, "r28h": 0.02}
    r, rc, dj = synth("all-good", ok_g + [("validate_ref", "PASS", "offline head AGREES"), ("ident_ref2", "PASS", "x"),
                                          ("ident_nov2", "PASS", "x"), ("compare", "PASS", "x")], fake(base, se))
    chk("validated -> JUDGED, bound adopted", dj["status"] == "JUDGED" and rc == 0 and (r / "ADOPTED-BOUND.json").exists()
        and (r / "PAST-VERDICTS-NOTE.txt").exists())
    cv = {x: dj["candidates"][x]["verdict"] for x in CANDS}
    # bound 1.1 x 0.006 = 0.0066; r28h 0.02 > 0.0066 + 1.645 x 0.008 = 0.0198 -> FAIL; v2 0.003 -> PASS
    chk("verdicts: v2 PASS, r28h FAIL (0.02 > 0.0066 + 0.0132), ref2 / x28h PASS", cv == {"ref2": "PASS", "v2": "PASS",
        "x28h": "PASS", "x28h-nov2": "PASS", "r28h": "FAIL"}, str(cv))
    se2 = dict(se, v2=0.015)
    r, rc, dj = synth("underpowered", ok_g + [("validate_ref", "PASS", "AGREES"), ("compare", "PASS", "x")], fake(base, se2))
    chk("se 0.015 -> v2 UNDERPOWERED, flagged in power", dj["candidates"]["v2"]["verdict"] == "UNDERPOWERED"
        and dj["power"]["underpowered"] == ["v2"])
    r, rc, dj = synth("kl-fail", ok_g + [("validate_ref", "PASS", "AGREES"), ("compare", "PASS", "x")],
                      fake(base, se, kl={"v2": {"flips": 400}}))
    chk("changed top-1 400 > 1.1 x 300 -> v2 FAIL (KL)", dj["candidates"]["v2"]["verdict"] == "FAIL"
        and dj["candidates"]["v2"]["kl_fails"] == ["top-1"])
    r, rc, dj = synth("not-validated", ok_g + [("validate_ref", "FAIL", "offline head DOES NOT AGREE")], fake(base, se))
    chk("validate FAIL -> NOT JUDGED, nothing adopted", dj["status"] == "NOT JUDGED" and rc == 1
        and not (r / "ADOPTED-BOUND.json").exists() and all(v["verdict"] == "NOT JUDGED" for v in dj["candidates"].values()))
    r, rc, dj = synth("ref-missing", [g_ for g_ in ok_g if g_[0] != "run_cpushare"] + [("validate_ref", "PASS", "AGREES")],
                      fake(base, se))
    chk("a rounding reference did not run -> NOT JUDGED", dj["status"] == "NOT JUDGED")
    b2 = dict(base, ref2=0.001)
    r, rc, dj = synth("ref2-moved", ok_g + [("validate_ref", "PASS", "AGREES"), ("ident_ref2", "FAIL", "3 differ"),
                                            ("compare", "PASS", "x")], fake(b2, se))
    chk("ref2 not exactly ref -> FLAG (verdicts still reported)", any("not exactly ref" in f for f in dj["flags"])
        and dj["status"] == "JUDGED")
    # 3 envwatch's check on a synthetic engine environment (no process): the config's env + pf_yardstick's fixed env
    qq = load("pf_yardstick", PFY).tool()
    cfg = json.loads((WS / "configs/r21n1.json").read_text())
    want = want_of(cfg, ["STRATA_PREFILL_CPU_SHARE=0.4"], qq.FIXED_ENV)
    env = dict(want, STRATA_MON_GPU="x", STRATA_PREFILL_DUMP_R_ALL="/x", STRATA_DUMP_FIRST_LOGITS="/y")
    argv = [cfg["exe"], "--serve", "--expert-cache", "1", "--adapt-every", "100000", "--pcie-frac", "0", "--suffix-draft",
            "0", "--prompt-cache", "0", "--kv", "fp16", "--prefill", "auto"]
    aw = {"--expert-cache": "1", "--pcie-frac": "0", "--kv": "fp16", "--prefill": "auto", "--adapt-every": "100000",
          "--suffix-draft": "0", "--prompt-cache": "0"}
    ng = len(cfg["env"]["CUDA_VISIBLE_DEVICES"].split(","))
    chk("envwatch: the cpushare arm's environment passes", check_engine(env, argv, want, ng, aw) == [])
    chk("envwatch: CPU share 0.4 is what --env sets over FIXED_ENV's 0", want["STRATA_PREFILL_CPU_SHARE"] == "0.4")
    chk("envwatch: a stray STRATA_ switch fails", bool(check_engine(dict(env, STRATA_GDN_TC="1"), argv, want, ng, aw)))
    chk("envwatch: tail skip on fails", bool(check_engine(dict(env, STRATA_ROUTE_TAIL_SKIP="1"), argv, want, ng, aw)))
    chk("envwatch: a --short-read fails", bool(check_engine(env, argv + ["--short-read", "100"], want, ng, aw)))
    print(f"selftest: {len(bad)} failure(s)" + (": " + ", ".join(bad) if bad else ""))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("envwatch")
    p.add_argument("job", type=int)
    p.add_argument("config")
    p.add_argument("--env", action="append")
    p.add_argument("--kill", action="store_true")
    p.add_argument("--max-s", type=float, default=7200)
    p.add_argument("--gate")
    p.add_argument("--gates")
    p = sp.add_parser("ident")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--gate")
    p.add_argument("--gates")
    sp.add_parser("decide").add_argument("root")
    sp.add_parser("selftest").add_argument("--dir", default=str(WS / "work/r23/scratch-gaps/nll-selftest"))
    a = ap.parse_args()
    return {"envwatch": envwatch, "ident": ident, "decide": decide, "selftest": selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
