#!/usr/bin/env python3
"""gdn_nll_rules.py - r23 (Karl 11-04: "If tonight's NLL gap validates the many-positions scorer, add a stock on-vs-off
arm with it (~6 min each)."). The rules of work/r23/gap-gdn-nll.sh, WRITTEN 11-04 BEFORE ANY RUN. A DIAGNOSTIC for
Karl's upstream issue about stock v0.2.10's two GDN prompt paths (STRATA_GDN_TC=1 + STRATA_GDN_CONVL2=2: what stock
serve/server.py's gdn_stack_env sets on Linux / CUDA / Qwen3.8). Gap 19 measured that pair with pf_yardstick long40
(the last-token logits of 40 prompts, the text NLL at 36 of them). This gap measures the same pair at ~31K positions
(every 8th batched prompt row from 1,024 on over the 11 long texts), so the issue does not rest on the 36-position check.
NOTHING SWITCHES: P028x stays served; what is posted upstream is Karl's call.

ARMS (score.py run CONFIG gap/ARM --set long11 --rows all:8 = the NLL gap's settings; engine-v0210stock c8fe72abe45a)
  s210     configs/s0210-h.json: stock v0.2.10 with the 14 pins, both GDN paths OFF (TC=0, CONVL2=0): the reference
  s210gdn  configs/s0210-h-gdn.json: s210 with only STRATA_GDN_TC=1 and STRATA_GDN_CONVL2=2: the candidate
  optional, only if 14 min fit before the deadline (35 min after the gap opens): the stock build's own rounding pair
  s210unf  s0210-h.json + STRATA_PF_FUSED=0                (as the NLL gap's `unfused`)
  s210cpu  s0210-h.json + STRATA_PREFILL_CPU_SHARE=0.4     (as the NLL gap's `cpushare`; pf_yardstick's fixed env sets 0)

PRECONDITIONS (`pre`; the driver refuses before the gap opens, exit 1, 8080 untouched, unless all four hold)
  nll     the NLL gap validated the scorer: results/r23/nll-many/gap/decision.json status JUDGED, its gates'
          validate_ref PASS, ADOPTED-BOUND.json present, and a band source there (result-x28h.json or result.json
          holding both of its rounding references)
  cfg     the two configs differ only in STRATA_GDN_TC 0 -> 1 and STRATA_GDN_CONVL2 0 -> 2 (and "log", "_comment");
          those are stock server.py's GDN_STACK_CUDA values; exe = engine-v0210stock/strata in both;
          STRATA_ROUTE_TAIL_SKIP=0
  head    the static half of "score.py's own head applies to the stock build". The configs' --native is score.py's
          GGUF (the same file) and --pack is bringup/out/r20a/pack. The pack serves output.weight natively (index kind 0:
          the engine reads it from that GGUF, Q6_K [2560, 248320]). Its output_hc_{norm,down,up} bytes in dense.bin
          equal the GGUF's bytes that score.py's Head reads (F32 / BF16 / BF16). The dynamic half is validate_s210 below
  engine  engine-v0210stock/strata sha256 = c8fe72abe45a = its SHA256 file; its SOURCE says stock v0.2.10
  (the driver's own: no gpu-test.lock / other gap / model server other than the 8080 queue's P028x / 8081 listener; the
  kernel watcher; the 11 prompt files; >= 20 GB free)

JUDGING (`compare`, then `decide`; NOT JUDGED, with the reason named, unless all of these hold)
  run_X + env_X PASS for s210 and s210gdn: score.py run rc 0; nll_rules.py envwatch = the config's env +
          pf_yardstick's fixed env, no other STRATA_*, tail skip 0, the config's 2 GPUs, score.py's engine args
  validate_s210 PASS: score.py validate on s210 (the engine's own window logits at the 5 check prompts vs score.py's
          offline head on the full read's row; mean KL <= 0.05, each <= 0.5) = score.py's head is the stock build's.
          validate_s210gdn: INFO; a miss is FLAGGED beside the verdict (the ON arm's window path and its batched rows
          disagree there)
  statistics  ADOPTED-BOUND.json's (defaults = nll_rules.py RULE): positions from min_pos (1,024), blocks of
          block_tokens (2,048) inside a text, a block bootstrap of boot (10,000) replicates, seed 20261104, z 1.645,
          se cap 0.01, tol 1.10; score.py's own load_dump + analyse (the code the NLL gap used), every arm at the same
          positions: d = mean(NLL_s210gdn - NLL_s210) with its block-bootstrap se and 95 % CI; KL(s210 || s210gdn) on
          those positions: mean, p90, rows with KL > 1, changed top-1
  band    in nats/token, 1.10 x max(|d_R1|, |d_R2|); the KL bounds in kernel_rule3's form (mean, p90 <= 1.10 x the
          larger reference; KL > 1 rows <= the larger + 1; changed top-1 <= 1.10 x the larger). Source:
            1 the stock build's own pair (s210unf, s210cpu against s210), when both ran cleanly; else
            2 borrowed from the NLL gap at the same positions: P028x's own pair (result-x28h.json: x28h vs
              x28h-unfused, x28h-cpushare) when that gap ran it, else P021n's (result.json: ref vs unfused, cpushare).
          The decision names the source. With source 1, the verdict under the borrowed band is INFO beside it.
  NLL     m = z x se:  OUTSIDE (higher NLL)  d > band + m;  OUTSIDE (lower NLL)  d < -(band + m);
          UNDERPOWERED  neither, and se > the se cap;  INSIDE  otherwise.
          Two-sided, as ud31's BETTER / WORSE: the question is whether the paths move the output beyond rounding, in
          either direction (gap 19: NLL -0.31 at 36 positions, i.e. lower)
  KL      each of the four checks against the band's KL bounds: OUTSIDE (names) if one exceeds, else INSIDE
  verdict "the GDN paths' distance is OUTSIDE the rounding band" = NLL OUTSIDE or a KL check OUTSIDE;
          "... INSIDE the rounding band" = NLL INSIDE and every KL check INSIDE;
          "... UNDERPOWERED (not outside the band; se > the cap)" = NLL UNDERPOWERED and KL INSIDE
  INFO    the adopted gate rule's own verdict (nll-many 11-04, one-sided: FAIL if d > band + m or a KL check fails,
          else UNDERPOWERED if se > cap, else PASS) for s210gdn as a candidate against s210; the mean |per-position
          NLL difference| beside the references'; per text and per position range (1-4K, 4-16K, 16-32K): d, KL mean,
          changed top-1 (rows.tsv); the block scan; gap 19's 40-prompt numbers for the same pair
  FLAGS   validate_s210gdn not PASS; a stock reference identical to s210 (it measured no rounding); positions not the
          borrowed band's count (n); a kernel-check failure during the gap

Subcommands (pre / compare take --gate NAME --gates FILE; .venv/bin/python -I -B, numpy):
  pre NLL_ROOT CFG_OFF CFG_ON          the four preconditions; exit 0 = all hold
  compare ROOT [--nll-root R] [--threads N] [--json OUT] [--rows-out OUT.tsv]   s210gdn (and the stock pair) vs s210
  decide ROOT [--nll-root R] [--out DIR]   -> DIR/decision.txt, decision.json
  selftest [--dir D]                   the checks on the real configs / files (read only) + synthetic dumps and gaps
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path


def _threads_from_argv() -> None:   # BLAS threads must be set before numpy loads (as score.py)
    n = "1"
    for i, a in enumerate(sys.argv):
        if a == "--threads" and i + 1 < len(sys.argv):
            n = sys.argv[i + 1]
    for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(k, n)


_threads_from_argv()
import numpy as np  # noqa: E402

sys.dont_write_bytecode = True     # the modules loaded below live in trees this script must not write to
WS = Path("/home/USER/ai-speed-testing/strata-compare")
SCORE = WS / "work/r23/nll-many/score.py"
NLLR = WS / "work/r23/nll_rules.py"
PFY = WS / "work/r22/pf_yardstick.py"
NLL_ROOT = WS / "results/r23/nll-many/gap"
EST = WS / "engine-v0210stock"
STOCK_SHA = "c8fe72abe45a"
SERVER = WS / "strata-v0210stock/serve/server.py"
PACK = WS / "bringup/out/r20a/pack"
CFG_OFF = WS / "configs/s0210-h.json"
CFG_ON = WS / "configs/s0210-h-gdn.json"
REF, CAND = "s210", "s210gdn"
OWN = ("s210unf", "s210cpu")
OWN_WHAT = "the stock build's own rounding pair (s210 + STRATA_PF_FUSED=0, s210 + STRATA_PREFILL_CPU_SHARE=0.4)"
GDN_DIFF = {"STRATA_GDN_TC": ("0", "1"), "STRATA_GDN_CONVL2": ("0", "2")}
N_EMBD, HC, HC_LR, VOCAB = 2560, 4, 320, 248320
D = HC * N_EMBD
HC_NEED = {"output_hc_norm.weight": ("F32", 2, D * 4), "output_hc_down.weight": ("BF16", 4, D * HC_LR * 2),
           "output_hc_up.weight": ("BF16", 4, D * HC_LR * 2)}
DEFAULTS = {"min_pos": 1024, "block_tokens": 2048, "boot": 10000, "seed": 20261104, "tol": 1.10, "z_one_sided": 1.645,
            "se_cap": 0.01}
RANGES = ((1024, 4096, "1-4K"), (4096, 16384, "4-16K"), (16384, 1 << 30, "16-32K"))
BLOCK_SCAN = ("1024", "4096", "text")
GAP19 = ("gap 19 (pf_yardstick long40, results/r22/gap19/decision.txt), stock ON against stock OFF: KL mean 0.648253, "
         "p90 1.031009, KL>1 4, changed top-1 4/40, NLL -0.3055 (36 positions with a next token)")
NOTE_SWITCH = "NOTHING SWITCHES: P028x stays served; what goes upstream is Karl's call."


# ------------------------------------------------------------------------------------------------ small helpers
def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail} [gdn {time.strftime('%m-%d %H:%M')}]\n")


def read_gates(p):
    g = {}
    p = Path(p)
    for line in p.read_text().splitlines() if p.exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)
    return g


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_SCORE = None


def score():
    global _SCORE
    if _SCORE is None:
        _SCORE = load("score_nll", SCORE)
    return _SCORE


def argval(args, flag):
    v = [args[i + 1] for i, x in enumerate(args[:-1]) if x == flag]
    return v[-1] if v else None


def bound_params(path):
    out = dict(DEFAULTS)
    p = Path(path)
    try:
        r = json.loads(p.read_text())
        for k in DEFAULTS:
            if k in r:
                out[k] = type(DEFAULTS[k])(r[k])
        out["source"] = str(p)
    except (OSError, ValueError):
        out["source"] = f"defaults ({p} unreadable)"
    return out


def sha256_file(p, chunk=16 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                return h.hexdigest()
            h.update(b)


def read_at(path, off, n):
    with open(path, "rb") as f:
        f.seek(off)
        b = f.read(n)
    if len(b) != n:
        raise OSError(f"{path}: short read at {off}")
    return b


# ------------------------------------------------------------------------------------------------ the bands
def band_from(arms, kl, refs, tol, source, n):
    ds = {x: float(arms[x]["d"]) for x in refs}
    return {"band": tol * max(abs(v) for v in ds.values()), "d_refs": ds, "refs": list(refs), "source": source, "n": n,
            "kl_refs": {x: kl[x] for x in refs},
            "kl_bounds": {"mean": tol * max(kl[x]["mean"] for x in refs), "p90": tol * max(kl[x]["p90"] for x in refs),
                          "high": max(kl[x]["high"] for x in refs) + 1, "flips": tol * max(kl[x]["flips"] for x in refs)},
            "mean_abs": {x: arms[x].get("mean_abs") for x in refs},
            "exact0": {x: arms[x].get("frac_exact0") for x in refs}}


def borrowed_band(root, tol):
    """the NLL gap's band at the same positions: P028x's own pair when it ran (result-x28h.json), else P021n's"""
    for f, what in (("result-x28h.json", "borrowed from the NLL gap: P028x's own rounding pair (x28h vs x28h-unfused, "
                                         "x28h-cpushare)"),
                    ("result.json", "borrowed from the NLL gap: P021n's rounding pair (ref vs unfused, cpushare; "
                                    "P028x's own pair did not run there)")):
        p = Path(root) / f
        try:
            r = json.loads(p.read_text())
            arms, kl = r["nll"]["arms"], r["kl"]
            refs = [x for x in r["refs"] if x in arms and x in kl]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if len(refs) == 2:
            return band_from(arms, kl, refs, tol, f"{what}, {p}", r["nll"].get("n"))
    return None


def own_band(res, tol):
    if not res or not all(x in res["nll"]["arms"] and x in res["kl"] for x in OWN):
        return None
    return band_from(res["nll"]["arms"], res["kl"], OWN, tol, OWN_WHAT, res["nll"]["n"])


# ------------------------------------------------------------------------------------------------ preconditions
def check_nll(root):
    root = Path(root)
    why = []
    try:
        st = json.loads((root / "decision.json").read_text()).get("status")
    except (OSError, ValueError):
        st = None
    if st != "JUDGED":
        why.append(f"{root / 'decision.json'}: status {st or 'missing'} (want JUDGED)")
    v = read_gates(root / "gates.txt").get("validate_ref", ("MISSING", ""))
    if v[0] != "PASS":
        why.append(f"validate_ref {v[0]}")
    if not (root / "ADOPTED-BOUND.json").exists():
        why.append("no ADOPTED-BOUND.json")
    b = borrowed_band(root, bound_params(root / "ADOPTED-BOUND.json")["tol"])
    if b is None:
        why.append(f"no result-x28h.json / result.json with both rounding references in {root}")
    line = (f"the NLL gap validated the scorer (JUDGED, validate_ref PASS: {v[1][:60]}; ADOPTED-BOUND.json); "
            f"borrowable band {b['band']:.4f} ({b['source'].split(':')[1].split('(')[0].strip()})" if not why else
            "the NLL gap did not validate the scorer: " + "; ".join(why))
    return why, line


def server_gdn_table(path=SERVER):
    tree = ast.parse(Path(path).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GDN_STACK_CUDA" for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def check_cfgs(off_p, on_p):
    bad = []
    off, on = json.loads(Path(off_p).read_text()), json.loads(Path(on_p).read_text())
    for c, p in ((off, off_p), (on, on_p)):
        if os.path.realpath(c.get("exe", "")) != os.path.realpath(EST / "strata"):
            bad.append(f"{Path(p).name}: exe {c.get('exe')} (want engine-v0210stock/strata)")
        if c.get("env", {}).get("STRATA_ROUTE_TAIL_SKIP") != "0":
            bad.append(f"{Path(p).name}: STRATA_ROUTE_TAIL_SKIP={c.get('env', {}).get('STRATA_ROUTE_TAIL_SKIP', 'unset')}")
    for k in sorted((set(off) | set(on)) - {"log", "_comment", "env"}):
        if off.get(k) != on.get(k):
            bad.append(f"{k} differs")
    eo, en = off.get("env", {}), on.get("env", {})
    for k in sorted(set(eo) | set(en)):
        if k in GDN_DIFF:
            if (eo.get(k), en.get(k)) != GDN_DIFF[k]:
                bad.append(f"{k} {eo.get(k)} -> {en.get(k)} (want {GDN_DIFF[k][0]} -> {GDN_DIFF[k][1]})")
        elif eo.get(k) != en.get(k):
            bad.append(f"env {k} differs ({eo.get(k)} / {en.get(k)})")
    want = {k: v[1] for k, v in GDN_DIFF.items()}
    try:
        srv = server_gdn_table()
    except (OSError, SyntaxError, ValueError) as e:
        srv = f"unreadable ({e})"
    if srv != want:
        bad.append(f"stock server.py's GDN_STACK_CUDA is {srv} (the ON config sets {want})")
    line = (f"{Path(off_p).name} -> {Path(on_p).name}: only STRATA_GDN_TC 0 -> 1, STRATA_GDN_CONVL2 0 -> 2 (= stock "
            f"server.py's GDN_STACK_CUDA); engine-v0210stock; tail skip 0" if not bad else "; ".join(bad))
    return bad, line


def pack_index(pack):
    rows = {}
    for line in (Path(pack) / "index.txt").read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split()
        rows.setdefault(f[0], {"kind": int(f[2]), "off": int(f[3]), "n": int(f[4])})
    return rows


def check_head(cfg_p):
    S = score()
    bad = []
    cfg = json.loads(Path(cfg_p).read_text())
    native, pack = argval(cfg["args"], "--native"), argval(cfg["args"], "--pack")
    try:
        if not (native and os.path.samefile(native, S.GGUF)):
            bad.append(f"--native {native} is not score.py's GGUF {S.GGUF}")
        if not (pack and os.path.samefile(pack, PACK)):
            bad.append(f"--pack {pack} is not {PACK}")
    except OSError as e:
        bad.append(f"path check: {e}")
    if bad:
        return bad, "; ".join(bad)
    if str(S.GGUF_TOOLS) not in sys.path:
        sys.path.insert(0, str(S.GGUF_TOOLS))
    import gguf_reader as G       # header reader only (no ggml); bytecode off
    g = G.GGUFFile(S.GGUF)
    t = {x.name: x for x in g.tensors}
    idx = pack_index(pack)
    ow = t.get("output.weight")
    if ow is None or ow.type_name != "Q6_K" or list(ow.shape) != [N_EMBD, VOCAB]:
        bad.append(f"output.weight in the GGUF is {ow.type_name if ow else 'missing'} {list(ow.shape) if ow else ''}")
    r = idx.get("output.weight")
    if r is None or r["kind"] != 0 or r["n"] != 0:
        bad.append(f"the pack's output.weight row is {r} (want kind 0, no bytes: served natively from the GGUF)")
    same = []
    for k, (ty, kind, n) in HC_NEED.items():
        x, r = t.get(k), idx.get(k)
        if x is None or x.type_name != ty:
            bad.append(f"{k} in the GGUF is {x.type_name if x else 'missing'} (want {ty})")
            continue
        if r is None or r["kind"] != kind or r["n"] != n:
            bad.append(f"{k} in the pack's index is {r} (want kind {kind}, {n} B)")
            continue
        a = hashlib.sha256(read_at(Path(pack) / "dense.bin", r["off"], n)).hexdigest()
        b = hashlib.sha256(read_at(S.GGUF, g.data_start + x.offset, n)).hexdigest()
        if a != b:
            bad.append(f"{k}: the pack's bytes differ from the GGUF's (sha {a[:12]} / {b[:12]})")
        else:
            same.append(f"{k.split('.')[0]} {a[:8]}")
    line = (f"{Path(cfg_p).name}: --native = score.py's GGUF, --pack = r20a; output.weight Q6_K served natively; the "
            f"pack's {', '.join(same)} = the GGUF's bytes (score.py's Head reads those)" if not bad else "; ".join(bad))
    return bad, line


def check_engine():
    bad = []
    exe = EST / "strata"
    try:
        sha = sha256_file(exe)[:12]
        rec = (EST / "SHA256").read_text()[:12]
        src = (EST / "SOURCE").read_text().strip()
    except OSError as e:
        return [str(e)], f"engine-v0210stock: {e}"
    if sha != STOCK_SHA:
        bad.append(f"strata sha {sha} (want {STOCK_SHA})")
    if rec != sha:
        bad.append(f"SHA256 file says {rec}")
    if not src.startswith("stock v0.2.10 ("):
        bad.append(f"SOURCE: {src[:80]}")
    line = (f"engine-v0210stock {sha} = its SHA256 file; {src[:90]}" if not bad else "engine-v0210stock: " + "; ".join(bad))
    return bad, line


def cmd_pre(a):
    out = []
    for name, fn in (("nll", lambda: check_nll(a.nll_root)), ("cfg", lambda: check_cfgs(a.cfg_off, a.cfg_on)),
                     ("head", lambda: check_head(a.cfg_off)), ("head-on", lambda: check_head(a.cfg_on)),
                     ("engine", check_engine)):
        try:
            bad, line = fn()
        except Exception as e:      # a check that cannot run is a refusal, not a crash
            bad, line = [repr(e)], f"{name}: could not run ({e!r})"
        out.append((name, bool(bad), line))
        print(f"{name}: {'FAIL' if bad else 'ok'}: {line}")
    fails = [n for n, b, _ in out if b]
    line = ("PRE OK: " + " | ".join(l for _, _, l in out) if not fails else
            "PRE REFUSED (" + ", ".join(fails) + "): " + " | ".join(l for n, b, l in out if b))
    print(line)
    gate(a, "PASS" if not fails else "FAIL", line[:600])
    return 0 if not fails else 1


# ------------------------------------------------------------------------------------------------ compare
def clean(g, root, x):
    return g.get(f"run_{x}", ("",))[0] == "PASS" and g.get(f"env_{x}", ("",))[0] == "PASS" and \
        (Path(root) / x / "index.json").exists()


def blocks_of(keys, bt):
    ids = {}
    return np.array([ids.setdefault((t,) if bt <= 0 else (t, p // bt), len(ids)) for t, p in keys])


def cmd_compare(a):
    root = Path(a.root)
    g = read_gates(root / "gates.txt")
    prm = bound_params(Path(a.nll_root) / "ADOPTED-BOUND.json")
    why = [f"arm {x} did not run cleanly (run {g.get('run_' + x, ('MISSING',))[0]}, env {g.get('env_' + x, ('MISSING',))[0]})"
           for x in (REF, CAND) if not clean(g, root, x)]
    if g.get("validate_s210", ("MISSING",))[0] != "PASS":
        why.append(f"validate_s210 {g.get('validate_s210', ('MISSING',))[0]} (score.py's head not validated on the stock build)")
    if why:
        line = "not compared: " + "; ".join(why)
        print(line)
        gate(a, "FAIL", line[:400])
        return 1
    arms = [CAND] + [x for x in OWN if clean(g, root, x)]
    S = score()
    ns = argparse.Namespace(min_pos=prm["min_pos"], stride=1, chunk=a.chunk, block_tokens=prm["block_tokens"])
    head = getattr(a, "head", None)
    A = S.load_dump(root, REF, arms, ns, head)
    res = S.analyse(A, REF, arms, [], prm["boot"], prm["seed"], prm["se_cap"])
    out = {"ref": REF, "cand": CAND, "arms": arms, "own_refs": [x for x in OWN if x in arms], "params": prm,
           "note": res["note"], "nll": {k: v for k, v in res["nll"].items() if k != "bound_rule3"}, "kl": res["kl"],
           "block_scan": {}}
    keep = A.block
    for spec in BLOCK_SCAN:
        A.block = blocks_of(A.keys, -1 if spec == "text" else int(spec))
        r2 = S.analyse(A, REF, arms, [], min(prm["boot"], 4000), prm["seed"], prm["se_cap"])
        out["block_scan"][spec] = {"blocks": r2["nll"]["blocks"], "se": {x: r2["nll"]["arms"][x]["se"] for x in arms}}
    A.block = keep
    nl = out["nll"]
    print(f"positions {nl['n']} in {nl['blocks']} blocks ({'; '.join(res['note'])}); NLL of {REF} {nl['base']:.4f}; "
          f"bootstrap {prm['boot']} (seed {prm['seed']}; {prm['source']})")
    for x in arms:
        q, k = nl["arms"][x], out["kl"][x]
        print(f"  {x:8s} d {q['d']:+.4f} [{q['lo']:+.4f}, {q['hi']:+.4f}] se {q['se']:.4f} mean|d| {q['mean_abs']:.4f} "
              f"exact0 {q['frac_exact0']:.3f} | KL mean {k['mean']:.6f} p90 {k['p90']:.6f} >1 {k['high']} top-1 {k['flips']}")
    for spec, v in out["block_scan"].items():
        print(f"  block scan {spec:>5s} ({v['blocks']} blocks): se " + ", ".join(f"{x} {s:.4f}" for x, s in v["se"].items()))
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str))
    if a.rows_out:
        with open(a.rows_out, "w") as f:          # score.py compare's --rows-out layout (its --from-rows reads it)
            f.write("\t".join(["block", "text", "pos", f"nll_{REF}"] + [f"{h}_{x}" for x in arms
                                                                    for h in ("nll", "kl", "flip")]) + "\n")
            for i, (t, p) in enumerate(A.keys):
                f.write("\t".join([str(A.block[i]), t, str(p), f"{A.nll[REF][i]:.6f}"] +
                                  [f"{v:.6g}" for x in arms for v in (A.nll[x][i], A.kl[x][i], float(A.flip[x][i]))]) + "\n")
    q = nl["arms"][CAND]
    line = (f"{nl['n']} positions, {nl['blocks']} blocks; {CAND} d {q['d']:+.4f} se {q['se']:.4f}, KL mean "
            f"{out['kl'][CAND]['mean']:.5f}; arms {', '.join(arms)}")
    gate(a, "PASS", line)
    return 0


# ------------------------------------------------------------------------------------------------ the rules
def judge(q, k, band, prm):
    d, se, b = q["d"], q["se"], band["band"]
    m = prm["z_one_sided"] * se
    if d > b + m:
        nll = "OUTSIDE (higher NLL)"
    elif d < -(b + m):
        nll = "OUTSIDE (lower NLL)"
    elif se > prm["se_cap"]:
        nll = "UNDERPOWERED"
    else:
        nll = "INSIDE"
    kb = band["kl_bounds"]
    kfail = [n for n, x in (("mean", k["mean"] > kb["mean"]), ("p90", k["p90"] > kb["p90"]),
                            ("KL>1 rows", k["high"] > kb["high"]), ("top-1", k["flips"] > kb["flips"])) if x]
    verdict = "OUTSIDE" if (nll.startswith("OUTSIDE") or kfail) else ("UNDERPOWERED" if nll == "UNDERPOWERED" else "INSIDE")
    gate_nll = "FAIL" if d > b + m else ("UNDERPOWERED" if se > prm["se_cap"] else "PASS")
    gate_v = "FAIL" if (gate_nll == "FAIL" or kfail) else gate_nll
    return {"d": d, "se": se, "lo": q["lo"], "hi": q["hi"], "band": b, "margin": m, "nll": nll, "kl": k, "kl_bounds": kb,
            "kl_fails": kfail, "verdict": verdict, "gate_rule": gate_v, "z": (abs(d) - b) / se if se > 0 else float("nan")}


def verdict_line(j):
    if j["verdict"] == "OUTSIDE":
        parts = []
        if j["nll"].startswith("OUTSIDE"):
            parts.append("NLL " + ("higher (worse) with the paths ON" if "higher" in j["nll"] else "lower with the paths ON")
                         + f": d {j['d']:+.4f} vs band {j['band']:.4f} + margin {j['margin']:.4f}")
        if j["kl_fails"]:
            parts.append("KL " + ", ".join(j["kl_fails"]))
        return "the GDN paths' distance is OUTSIDE the rounding band (" + "; ".join(parts) + ")"
    if j["verdict"] == "INSIDE":
        return "the GDN paths' distance is INSIDE the rounding band (NLL and all four KL checks)"
    return (f"the GDN paths' distance is UNDERPOWERED: not outside the band, but se {j['se']:.4f} > the cap (more text "
            f"would decide it; the KL checks are inside)")


def fmt_band(b):
    kb = b["kl_bounds"]
    return (f"{b['band']:.4f} nats/token = 1.10 x max(" + ", ".join(f"|d {x}| {abs(v):.4f}" for x, v in b["d_refs"].items())
            + f"): {b['source']}; KL bounds mean <= {kb['mean']:.6f}, p90 <= {kb['p90']:.6f}, KL>1 rows <= {kb['high']}, "
            f"changed top-1 <= {kb['flips']:.1f}" + (f" (at {b['n']} positions)" if b.get("n") else ""))


def fmt_j(j):
    k = j["kl"]
    return (f"NLL  {CAND} d {j['d']:+.4f} [{j['lo']:+.4f}, {j['hi']:+.4f}] se {j['se']:.4f}; band {j['band']:.4f} + margin "
            f"{j['margin']:.4f} -> {j['nll']}\n"
            f"KL   KL({REF} || {CAND}) mean {k['mean']:.6f} p90 {k['p90']:.6f} KL>1 {k['high']} changed top-1 {k['flips']} "
            f"of {k['n']} -> " + ("INSIDE" if not j["kl_fails"] else "OUTSIDE (" + ", ".join(j["kl_fails"]) + ")"))


def breakdown(rows_p, min_pos):
    """per text and per position range from rows.tsv: n, d, KL mean, changed top-1 (INFO)"""
    p = Path(rows_p)
    if not p.exists():
        return []
    lines = p.read_text().splitlines()
    col = {h: i for i, h in enumerate(lines[0].split("\t"))}
    need = (f"nll_{REF}", f"nll_{CAND}", f"kl_{CAND}", f"flip_{CAND}")
    if not all(h in col for h in need):
        return []
    acc = {}
    for line in lines[1:]:
        f = line.split("\t")
        t, pos = f[1], int(f[2])
        if pos < min_pos:
            continue
        dv, kv, fv = float(f[col[need[1]]]) - float(f[col[need[0]]]), float(f[col[need[2]]]), float(f[col[need[3]]]) > 0.5
        rg = next(n for lo, hi, n in RANGES if lo <= pos < hi)
        for key in (("text", t), ("range", rg)):
            s = acc.setdefault(key, [0, 0.0, 0.0, 0])
            s[0] += 1
            s[1] += dv
            s[2] += kv
            s[3] += fv
    out = []
    for kind in ("text", "range"):
        items = [(k[1], v) for k, v in acc.items() if k[0] == kind]
        if kind == "range":
            order = [n for _, _, n in RANGES]
            items.sort(key=lambda x: order.index(x[0]))
        out.append(f"per {kind}: " + "; ".join(f"{n} n {v[0]} d {v[1] / v[0]:+.4f} KL {v[2] / v[0]:.4f} top-1 {v[3]}"
                                                 for n, v in items))
    return out


def decide(root, nll_root=NLL_ROOT, out_dir=None):
    root, nll_root = Path(root), Path(nll_root)
    out_dir = Path(out_dir) if out_dir else root
    g = read_gates(root / "gates.txt")
    st = lambda k: g.get(k, ("MISSING", ""))[0]
    L, flags = [], []
    out = {"rules": "work/r23/gdn_nll_rules.py", "written": time.strftime("%F %T"), "status": None, "flags": flags}
    L.append(f"GDN prompt paths ON vs OFF on STOCK v0.2.10 at many positions - decision ({out['written']}; rules: "
             "work/r23/gdn_nll_rules.py, written before the gap)")
    L.append(f"  arms: {REF} = configs/s0210-h.json (both paths off), {CAND} = configs/s0210-h-gdn.json (STRATA_GDN_TC=1 + "
             f"STRATA_GDN_CONVL2=2, as stock server.py sets them); engine-v0210stock {STOCK_SHA}")
    L.append(f"  pre-gap checks: {st('pre')} {g.get('pre', ('', ''))[1][:300]}")
    if "kfail" in g:
        flags.append(f"a kernel check failed during the gap ({g['kfail'][1][:80]}; the gap stays open; Karl decides)")
    v = g.get("validate_s210", ("MISSING", "not validated"))
    L.append(f"  validation (score.py's own head on the stock build, arm {REF}): {v[0]} {v[1][:200]}")
    prm = bound_params(nll_root / "ADOPTED-BOUND.json")
    out["params"] = prm
    why = []
    if st("pre") != "PASS":
        why.append(f"the pre-gap checks did not pass (pre {st('pre')})")
    for x in (REF, CAND):
        if st(f"run_{x}") != "PASS" or st(f"env_{x}") != "PASS":
            why.append(f"arm {x} did not run cleanly (run {st('run_' + x)}, env {st('env_' + x)})")
    if v[0] != "PASS":
        why.append(f"score.py's head was not validated on the stock build (validate_{REF} {v[0]})")
    res = None
    try:
        res = json.loads((root / "result.json").read_text())
        if CAND not in res["nll"]["arms"] or CAND not in res["kl"]:
            res = None
    except (OSError, ValueError, KeyError, TypeError):
        res = None
    if res is None:
        why.append(f"no compare result with {CAND} (compare {st('compare')} {g.get('compare', ('', ''))[1][:120]})")
    own = own_band(res, prm["tol"])
    bor = borrowed_band(nll_root, prm["tol"])
    band = own or bor
    if band is None and res is not None:
        why.append("no rounding band: the stock pair did not run cleanly and the NLL gap has no result with both references")
    if why:
        out["status"] = "NOT JUDGED"
        L.append("=> NOT JUDGED: " + "; ".join(why) + ". The GDN paths' distance is not decided here.")
        return finish(out_dir, out, L, 1)
    out["status"] = "JUDGED"
    nl = res["nll"]
    L.append(f"positions: {nl['n']} in {nl['blocks']} blocks ({'; '.join(res.get('note', []))}); NLL of {REF} there "
             f"{nl['base']:.4f}; statistics {prm['source']} (z {prm['z_one_sided']}, se cap {prm['se_cap']}, "
             f"bootstrap {prm['boot']}, seed {prm['seed']})")
    L.append("band: " + fmt_band(band))
    j = judge(nl["arms"][CAND], res["kl"][CAND], band, prm)
    out.update({"band": band, "judgement": j})
    L.extend(fmt_j(j).split("\n"))
    vg = st(f"validate_{CAND}")
    L.append("=> " + verdict_line(j) + ("" if vg in ("PASS", "MISSING") else
                                        f"  [validate_{CAND} {vg}: the ON arm's window and batched rows disagree]"))
    out["verdict"] = verdict_line(j)
    # ---- INFO
    if own and bor:
        jb = judge(nl["arms"][CAND], res["kl"][CAND], bor, prm)
        out["borrowed"] = {"band": bor, "judgement": jb}
        L.append(f"INFO with the borrowed band ({bor['band']:.4f}; {bor['source'].split(', /')[0]}): NLL {jb['nll']}, KL "
                 + ("INSIDE" if not jb["kl_fails"] else "OUTSIDE (" + ", ".join(jb["kl_fails"]) + ")")
                 + f" -> {jb['verdict']}")
    elif own is None and bor is not None:
        L.append("INFO the stock build's own rounding pair did not run (optional, deadline) or not cleanly: "
                 + ", ".join(f"{x} run {st('run_' + x)} env {st('env_' + x)}" for x in OWN))
    L.append(f"INFO the adopted gate rule (nll-many 11-04, one-sided) on {CAND} as a candidate against {REF}: "
             f"{j['gate_rule']}")
    ma = nl["arms"][CAND].get("mean_abs")
    if ma is not None:
        L.append(f"INFO mean |per-position NLL difference|: {CAND} {ma:.4f}; the band's references "
                 + ", ".join(f"{x} {v:.4f}" for x, v in band["mean_abs"].items() if v is not None))
    for x in OWN:
        if x in nl["arms"] and x in res["kl"]:
            q, k = nl["arms"][x], res["kl"][x]
            L.append(f"INFO {x}: d {q['d']:+.4f} se {q['se']:.4f}, KL mean {k['mean']:.6f} p90 {k['p90']:.6f} >1 {k['high']} "
                     f"top-1 {k['flips']}, exactly-0 positions {q.get('frac_exact0', 0):.3f}")
    for line in breakdown(root / "rows.tsv", prm["min_pos"]):
        L.append("INFO " + line)
    for spec, bs in (res.get("block_scan") or {}).items():
        L.append(f"INFO block scan {spec:>5s} ({bs['blocks']} blocks): se " + ", ".join(f"{x} {s:.4f}" for x, s in bs["se"].items()))
    L.append("INFO " + GAP19)
    vs = [f"{x} {st('validate_' + x)}" for x in (CAND,) + OWN if st("validate_" + x) != "MISSING"]
    if vs:
        L.append("INFO validate on the other arms: " + ", ".join(vs))
    # ---- flags
    if vg not in ("PASS", "MISSING"):
        flags.append(f"validate_{CAND} {vg}: the ON arm's engine window rows and its batched rows disagree at the check "
                     "prompts (the verdict scores the batched rows)")
    if own:
        same = [x for x, e in own["exact0"].items() if e is not None and e >= 1.0]
        if same:
            flags.append(f"{', '.join(same)} identical to {REF} at every position: that reference measured no rounding")
    if band is bor and bor.get("n") is not None and bor["n"] != nl["n"]:
        flags.append(f"the positions ({nl['n']}) are not the borrowed band's ({bor['n']}): the band was measured on "
                     "another position set")
    return finish(out_dir, out, L, 0)


def finish(out_dir, out, L, rc):
    if out["flags"]:
        L.append("FLAGS: " + " | ".join(out["flags"]))
    L.append(NOTE_SWITCH)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "decision.txt").write_text("\n".join(L) + "\n")
    (out_dir / "decision.json").write_text(json.dumps(out, indent=1, default=str))
    print("\n".join(L))
    return rc


def cmd_decide(a):
    return decide(a.root, a.nll_root, a.out)


# ------------------------------------------------------------------------------------------------ dry runs
def selftest(a):
    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    bad = []

    def chk(name, ok, detail=""):
        print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + detail[:300]) if detail else ''}")
        if not ok:
            bad.append(name)
    S = score()
    # 1 the preconditions on the real files (read only)
    b, line = check_cfgs(CFG_OFF, CFG_ON)
    chk("cfg: the stock configs differ only in the GDN pair = server.py's GDN_STACK_CUDA", not b, line)
    for k, v, what in (("STRATA_GR_R2", "1", "a stray switch"), ("STRATA_GDN_CONVL2", "1", "CONVL2=1 (not server.py's 2)")):
        on = json.loads(CFG_ON.read_text())
        on["env"][k] = v
        (d / "on-bad.json").write_text(json.dumps(on))
        chk(f"cfg: {what} in the ON config fails", bool(check_cfgs(CFG_OFF, d / "on-bad.json")[0]))
    b, line = check_head(CFG_OFF)
    chk("head: score.py's GGUF + r20a's pack, hc bytes = the GGUF's", not b, line)
    cf = json.loads(CFG_OFF.read_text())
    cf["args"][cf["args"].index("--pack") + 1] = str(d)
    (d / "off-otherpack.json").write_text(json.dumps(cf))
    chk("head: another --pack fails", bool(check_head(d / "off-otherpack.json")[0]))
    b, line = check_engine()
    chk("engine: engine-v0210stock = c8fe72abe45a", not b, line)
    b, line = check_nll(NLL_ROOT)
    print(f"info the real NLL gap now: {'not validated' if b else 'validated'}: {line[:200]}")

    # 2 envwatch's rules (nll_rules.py check_engine) on the four arms' environments as score.py run sets them
    NR = load("nll_rules_t", NLLR)
    qq = load("pf_yardstick_t", PFY).tool()
    fx = dict(zip(qq.FIXED[0::2], qq.FIXED[1::2]))
    fx.update({"--prefill": "auto", "--kv": "fp16"})
    aw = {k: fx[k] for k in ("--expert-cache", "--pcie-frac", "--kv", "--prefill", "--adapt-every", "--suffix-draft",
                             "--prompt-cache")}
    argv = [str(EST / "strata"), "--serve"] + [x for k, v in aw.items() for x in (k, v)]
    envs = {}
    for name, cfgp, sets in ((REF, CFG_OFF, []), (CAND, CFG_ON, []), ("s210unf", CFG_OFF, ["STRATA_PF_FUSED=0"]),
                             ("s210cpu", CFG_OFF, ["STRATA_PREFILL_CPU_SHARE=0.4"])):
        cfg = json.loads(cfgp.read_text())
        want = NR.want_of(cfg, sets, qq.FIXED_ENV)
        env = dict(want, STRATA_MON_GPU="x", STRATA_PREFILL_DUMP_R_ALL="/x", STRATA_DUMP_FIRST_LOGITS="/y")
        envs[name] = (env, want)
        ng = len(cfg["env"]["CUDA_VISIBLE_DEVICES"].split(","))
        chk(f"envwatch: arm {name}'s engine environment passes ({ng} GPUs)", NR.check_engine(env, argv, want, ng, aw) == [],
            str(NR.check_engine(env, argv, want, ng, aw)))
    e0, w0 = envs[REF]
    chk("envwatch: the OFF arm with STRATA_GDN_TC=1 fails", bool(NR.check_engine(dict(e0, STRATA_GDN_TC="1"), argv, w0, 2, aw)))
    chk("envwatch: s210cpu's share is 0.4 over pf_yardstick's fixed 0; s210's is 0",
        envs["s210cpu"][1]["STRATA_PREFILL_CPU_SHARE"] == "0.4" and w0["STRATA_PREFILL_CPU_SHARE"] == "0")
    chk("envwatch: s210unf's STRATA_PF_FUSED is 0 (the config's 1 replaced)", envs["s210unf"][1]["STRATA_PF_FUSED"] == "0")

    # 3 compare on synthetic dumps (score.py's own load_dump + analyse; a synthetic head; the real pp4k / rep9k texts)
    rng = np.random.default_rng(20261104)
    n_, hc_, lr_ = 8, 4, 3
    Dm = n_ * hc_
    head = S.Head(weights=(np.ones(Dm, np.float32), rng.normal(0, 0.3, (lr_, Dm)).astype(np.float32),
                           rng.normal(0, 0.3, (Dm, lr_)).astype(np.float32),
                           rng.normal(0, 1.0, (VOCAB, n_)).astype(np.float32), n_, hc_, lr_))
    texts = [(f, min(len(S.load_ids(f)), c)) for f, c in (("pp4k.tokens", 4096), ("rep9k.tokens", 6144))]
    K = 8
    nll_syn = d / "nll-root"
    nll_syn.mkdir(exist_ok=True)
    prm_syn = dict(DEFAULTS, block_tokens=512, boot=2000)
    (nll_syn / "ADOPTED-BOUND.json").write_text(json.dumps(prm_syn))

    def mkgap(name, noise, own=True, gdn_same=False):
        r = d / name
        if r.exists():
            shutil.rmtree(r)           # (the selftest's own scratch folder only)
        r.mkdir()
        base = [rng.normal(0, 1, (len(range(0, n - 1, K)), Dm)).astype(np.float32) for _, n in texts]
        arms = {REF: 0.0, CAND: 0.0 if gdn_same else noise}
        if own:
            arms.update({"s210unf": 0.01, "s210cpu": 0.015})
        for x, s in arms.items():
            (r / x).mkdir()
            reqs = []
            for i, ((f, n), B) in enumerate(zip(texts, base)):
                R = B + (rng.normal(0, s, B.shape).astype(np.float32) if s > 0 else 0)
                bits = (S.bf16_round(R).view(np.uint32) >> 16).astype(np.uint16)
                np.save(r / x / f"a.{i}.npy", bits)
                reqs.append({"name": f"{f.split('.')[0]}-{n}", "file": f, "cut": n, "kind": "text", "rows": len(B),
                             "dump": f"a.{i}.npy", "tokens": n})
            (r / x / "index.json").write_text(json.dumps({"requests": reqs, "rows": f"all:{K}"}))
        gl = [f"pre PASS synthetic", f"validate_s210 PASS synthetic AGREES"]
        gl += [f"{k}_{x} PASS synthetic" for x in arms for k in ("run", "env")]
        (r / "gates.txt").write_text("\n".join(gl) + "\n")
        return r

    def run_compare(r, nll_root):
        ns = argparse.Namespace(root=str(r), nll_root=str(nll_root), json=str(r / "result.json"),
                                rows_out=str(r / "rows.tsv"), chunk=128, threads="1", gate="compare",
                                gates=str(r / "gates.txt"), head=head)
        return cmd_compare(ns)
    r = mkgap("syn-own", 0.5)
    rc = run_compare(r, nll_syn)
    res = json.loads((r / "result.json").read_text())
    n_exp = sum(len([p for p in range(0, n - 1, K) if p >= 1024 and p + 1 < n]) for _, n in texts)
    chk(f"compare: rc 0, {n_exp} positions, the candidate + both stock references, blocks of 512 from ADOPTED-BOUND.json",
        rc == 0 and res["nll"]["n"] == n_exp and set(res["nll"]["arms"]) == {CAND, *OWN} and res["params"]["block_tokens"] == 512,
        f"n {res['nll']['n']} arms {sorted(res['nll']['arms'])}")
    rows = (r / "rows.tsv").read_text().splitlines()
    chk("compare: rows.tsv has one line per position", len(rows) == n_exp + 1, f"{len(rows) - 1} rows")
    # one KL and one NLL by hand at a position of the second text
    hdr = rows[0].split("\t")
    f = rows[-5].split("\t")
    t, pos = f[1], int(f[2])
    ti = [i for i, (fn, n) in enumerate(texts) if f"{fn.split('.')[0]}-{n}" == t][0]
    rr = {x: S.bf16_to_f32(np.load(r / x / f"a.{ti}.npy")[pos // K]) for x in (REF, CAND)}
    lr_, lc_ = head.logp(rr[REF][None, :])[0], head.logp(rr[CAND][None, :])[0]
    kl_hand = float((np.exp(lr_) * (lr_ - lc_)).sum())
    tg = S.load_ids(texts[ti][0])[pos + 1]
    kl_t, nll_t = float(f[hdr.index(f"kl_{CAND}")]), float(f[hdr.index(f"nll_{REF}")])
    chk("compare: one KL and one NLL by hand = rows.tsv", abs(kl_hand - kl_t) <= 1e-4 + 1e-3 * kl_hand
        and abs(-lr_[tg] - nll_t) <= 1e-4, f"KL {kl_hand:.6g} vs {kl_t:.6g}, NLL {-lr_[tg]:.6f} vs {nll_t:.6f}")
    # score.py's --from-rows re-analysis of our rows.tsv gives the same d / se
    ns = argparse.Namespace(min_pos=1024, stride=1, block_tokens=512, rows_kind="dump")
    A2 = S.load_rows(r / "rows.tsv", REF, [CAND] + list(OWN), ns)
    r2 = S.analyse(A2, REF, [CAND] + list(OWN), [], 2000, prm_syn["seed"], 0.01)
    chk("compare: score.py --from-rows on rows.tsv reproduces d (1e-5: the table keeps 6 digits) and se (2 %)",
        abs(r2["nll"]["arms"][CAND]["d"] - res["nll"]["arms"][CAND]["d"]) < 1e-5
        and abs(r2["nll"]["arms"][CAND]["se"] - res["nll"]["arms"][CAND]["se"]) <= 0.02 * res["nll"]["arms"][CAND]["se"] + 1e-9)
    rc = decide(r, nll_syn)
    dj = json.loads((r / "decision.json").read_text())
    chk("decide (synthetic dumps, big noise): JUDGED, own band, OUTSIDE", dj["status"] == "JUDGED" and rc == 0
        and dj["band"]["source"] == OWN_WHAT and dj["judgement"]["verdict"] == "OUTSIDE", dj.get("verdict", ""))
    r = mkgap("syn-same", 0.5, gdn_same=True)
    run_compare(r, nll_syn)
    decide(r, nll_syn)
    dj = json.loads((r / "decision.json").read_text())
    chk("decide (s210gdn = s210 byte for byte): d 0, KL 0 -> INSIDE", dj["status"] == "JUDGED"
        and dj["judgement"]["d"] == 0 and dj["judgement"]["kl"]["mean"] == 0 and dj["judgement"]["verdict"] == "INSIDE",
        dj.get("verdict", ""))
    r = mkgap("syn-noown", 0.5, own=False)
    rc = run_compare(r, nll_syn)
    res = json.loads((r / "result.json").read_text())
    chk("compare without the stock pair: the candidate alone", rc == 0 and list(res["nll"]["arms"]) == [CAND])
    rc = decide(r, nll_syn)
    dj = json.loads((r / "decision.json").read_text())
    chk("decide without the stock pair and no NLL-gap result: NOT JUDGED (no band)", dj["status"] == "NOT JUDGED"
        and rc == 1)
    g = (r / "gates.txt").read_text()
    (r / "gates.txt").write_text(g.replace("validate_s210 PASS", "validate_s210 FAIL"))
    chk("compare refuses when validate_s210 is not PASS", run_compare(r, nll_syn) == 1)

    # 4 decide on synthetic gaps (stored numbers; every branch)
    def fake_arm(dv, se, ex=0.0):
        return {"d": dv, "lo": dv - 2 * se, "hi": dv + 2 * se, "se": se, "sd_pos": 1.0, "mean_abs": abs(dv) + 0.2,
                "frac_gt05": 0.1, "frac_exact0": ex, "deff": 3.0}

    def fake_kl(**kw):
        return dict({"n": 31400, "mean": 0.010, "p90": 0.02, "high": 3, "max": 2.0, "flips": 300}, **kw)

    def fake_res(cd, cse, own=True, ckl=None, n=31400, own_ex=0.0):
        arms = {CAND: fake_arm(cd, cse)}
        kl = {CAND: fake_kl(**(ckl or {}))}
        if own:
            arms.update({"s210unf": fake_arm(0.004, 0.006, own_ex), "s210cpu": fake_arm(-0.006, 0.007)})
            kl.update({"s210unf": fake_kl(), "s210cpu": fake_kl(mean=0.012)})
        return {"ref": REF, "cand": CAND, "nll": {"n": n, "blocks": 130, "base": 1.9, "arms": arms}, "kl": kl,
                "note": ["synthetic"], "block_scan": {}}

    def mk_nll_root(name, x28h=True, p021=True, judged=True, validated=True, adopted=True):
        r = d / name
        r.mkdir(exist_ok=True)
        for f in ("result-x28h.json", "result.json", "decision.json", "ADOPTED-BOUND.json", "gates.txt"):
            (r / f).unlink(missing_ok=True)
        if x28h:
            (r / "result-x28h.json").write_text(json.dumps({"refs": ["x28h-unfused", "x28h-cpushare"], "nll": {
                "n": 31400, "arms": {"x28h-unfused": fake_arm(0.008, 0.006), "x28h-cpushare": fake_arm(-0.005, 0.006)}},
                "kl": {"x28h-unfused": fake_kl(), "x28h-cpushare": fake_kl(flips=320)}}))
        if p021:
            (r / "result.json").write_text(json.dumps({"refs": ["unfused", "cpushare"], "nll": {
                "n": 31400, "arms": {"unfused": fake_arm(0.003, 0.006), "cpushare": fake_arm(0.002, 0.006)}},
                "kl": {"unfused": fake_kl(), "cpushare": fake_kl()}}))
        (r / "decision.json").write_text(json.dumps({"status": "JUDGED" if judged else "NOT JUDGED"}))
        (r / "gates.txt").write_text(f"validate_ref {'PASS' if validated else 'FAIL'} offline head AGREES\n")
        if adopted:
            (r / "ADOPTED-BOUND.json").write_text(json.dumps(DEFAULTS))
        return r
    nr_all = mk_nll_root("nll-all")
    nr_p021 = mk_nll_root("nll-p021", x28h=False)
    ok_gates = ["pre PASS x", "validate_s210 PASS AGREES", "compare PASS x"] + \
        [f"{k}_{x} PASS x" for x in (REF, CAND) + OWN for k in ("run", "env")]

    def case(name, res, gates=None, nll_root=nr_all):
        r = d / f"dec-{name}"
        r.mkdir(exist_ok=True)
        (r / "rows.tsv").unlink(missing_ok=True)
        (r / "gates.txt").write_text("\n".join(gates if gates is not None else ok_gates) + "\n")
        (r / "result.json").write_text(json.dumps(res))
        rc = decide(r, nll_root)
        return rc, json.loads((r / "decision.json").read_text())
    # own band = 1.10 x 0.006 = 0.0066; margin 1.645 x 0.008 = 0.01316
    rc, dj = case("higher", fake_res(0.05, 0.008))
    chk("d +0.05 (> 0.0066 + 0.0132) -> OUTSIDE (higher NLL), own band", dj["judgement"]["nll"] == "OUTSIDE (higher NLL)"
        and dj["judgement"]["verdict"] == "OUTSIDE" and dj["band"]["source"] == OWN_WHAT and dj["judgement"]["gate_rule"] == "FAIL")
    rc, dj = case("lower", fake_res(-0.05, 0.008))
    chk("d -0.05 -> OUTSIDE (lower NLL); the one-sided gate rule PASSes it", dj["judgement"]["nll"] == "OUTSIDE (lower NLL)"
        and dj["judgement"]["verdict"] == "OUTSIDE" and dj["judgement"]["gate_rule"] == "PASS")
    rc, dj = case("inside", fake_res(0.003, 0.008))
    chk("d +0.003 se 0.008, KL at the references' -> INSIDE", dj["judgement"]["verdict"] == "INSIDE" and rc == 0)
    chk("with the own band, the borrowed (P028x's) verdict is INFO beside it",
        "P028x's own" in dj.get("borrowed", {}).get("band", {}).get("source", ""))
    rc, dj = case("under", fake_res(0.003, 0.015))
    chk("se 0.015 > cap -> UNDERPOWERED", dj["judgement"]["verdict"] == "UNDERPOWERED")
    rc, dj = case("klflips", fake_res(0.003, 0.008, ckl={"flips": 400}))
    chk("changed top-1 400 > 1.1 x 300 -> OUTSIDE (KL top-1), NLL INSIDE", dj["judgement"]["verdict"] == "OUTSIDE"
        and dj["judgement"]["kl_fails"] == ["top-1"] and dj["judgement"]["nll"] == "INSIDE")
    rc, dj = case("klmean", fake_res(0.003, 0.008, ckl={"mean": 0.5, "p90": 1.0, "high": 40}))
    chk("KL mean / p90 / KL>1 far out -> OUTSIDE (mean, p90, KL>1 rows)", dj["judgement"]["kl_fails"] == ["mean", "p90", "KL>1 rows"])
    nog = [x for x in ok_gates if not x.startswith(("run_s210unf", "env_s210unf"))]
    rc, dj = case("borrow-x28h", fake_res(0.003, 0.008, own=False), nog)
    chk("no stock pair -> band borrowed from P028x's own pair (1.10 x 0.008)", dj["status"] == "JUDGED"
        and "P028x's own" in dj["band"]["source"] and abs(dj["band"]["band"] - 0.0088) < 1e-12)
    rc, dj = case("borrow-p021", fake_res(0.003, 0.008, own=False), nog, nll_root=nr_p021)
    chk("no stock pair, no P028x pair -> P021n's (1.10 x 0.003)", "P021n's" in dj["band"]["source"]
        and abs(dj["band"]["band"] - 0.0033) < 1e-12)
    rc, dj = case("borrow-n", fake_res(0.003, 0.008, own=False, n=31000), nog)
    chk("borrowed band at another position count -> FLAG", any("not the borrowed band's" in x for x in dj["flags"]))
    rc, dj = case("val-fail", fake_res(0.003, 0.008), [x.replace("validate_s210 PASS", "validate_s210 FAIL") for x in ok_gates])
    chk("validate_s210 FAIL -> NOT JUDGED", dj["status"] == "NOT JUDGED" and rc == 1)
    rc, dj = case("run-fail", fake_res(0.003, 0.008), [x.replace("run_s210gdn PASS", "run_s210gdn FAIL") for x in ok_gates])
    chk("run_s210gdn FAIL -> NOT JUDGED", dj["status"] == "NOT JUDGED")
    rc, dj = case("pre-fail", fake_res(0.003, 0.008), [x.replace("pre PASS", "pre FAIL") for x in ok_gates])
    chk("pre FAIL -> NOT JUDGED", dj["status"] == "NOT JUDGED")
    rc, dj = case("gdnval", fake_res(0.003, 0.008), ok_gates + ["validate_s210gdn FAIL DOES NOT AGREE", "kfail FAIL after x"])
    chk("validate_s210gdn FAIL + a kernel-check failure -> both FLAGGED", any("validate_s210gdn" in x for x in dj["flags"])
        and any("kernel check" in x for x in dj["flags"]))
    rc, dj = case("ident-ref", fake_res(0.003, 0.008, own_ex=1.0))
    chk("a stock reference identical to s210 -> FLAG", any("measured no rounding" in x for x in dj["flags"]))
    for name, kw, want in (("ok", {}, False), ("notjudged", {"judged": False}, True), ("notval", {"validated": False}, True),
                           ("noadopt", {"adopted": False}, True), ("nores", {"x28h": False, "p021": False}, True)):
        b, line = check_nll(mk_nll_root(f"pre-{name}", **kw))
        chk(f"pre nll: {name} -> {'refused' if want else 'ok'}", bool(b) == want, line)
    print(f"selftest: {len(bad)} failure(s)" + (": " + ", ".join(bad) if bad else ""))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("pre")
    p.add_argument("nll_root")
    p.add_argument("cfg_off")
    p.add_argument("cfg_on")
    p.add_argument("--gate")
    p.add_argument("--gates")
    p = sp.add_parser("compare")
    p.add_argument("root")
    p.add_argument("--nll-root", default=str(NLL_ROOT))
    p.add_argument("--threads", default="1", help="BLAS threads (read before numpy loads)")
    p.add_argument("--chunk", type=int, default=128)
    p.add_argument("--json")
    p.add_argument("--rows-out")
    p.add_argument("--gate")
    p.add_argument("--gates")
    p = sp.add_parser("decide")
    p.add_argument("root")
    p.add_argument("--nll-root", default=str(NLL_ROOT))
    p.add_argument("--out")
    sp.add_parser("selftest").add_argument("--dir", default=str(WS / "work/r23/scratch-gdn-nll/selftest"))
    a = ap.parse_args()
    return {"pre": cmd_pre, "compare": cmd_compare, "decide": cmd_decide, "selftest": selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
