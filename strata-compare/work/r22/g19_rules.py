#!/usr/bin/env python3
"""g19_rules.py - gap 19 (Karl 11-04): a DIAGNOSTIC on STOCK Strata v0.2.10 (engine-v0210stock c8fe72abe45a, ffa80d731,
none of our commits). Written down BEFORE the gap ran (11-04). Nothing switches; nothing here is a gate for serving.

Why: gap 17 (results/r22/gap17/decision.txt) failed two of v0.2.10's paths on our port (engine-r22p0210):
  (0) STRATA_GDN_TC + STRATA_GDN_CONVL2 (the GDN prompt stack): kl2_gdn + kl3_gdn FAIL (KL mean 0.575, p90 1.10, 5 rows
      KL > 1); each path alone failed too (kl2/kl3_gdntc, kl2/kl3_gdncv)
  (3) STRATA_PF_HC_REGION=1: e7_hcr 3/7 at MATCHED slots (upstream: "the same kernels on the same values: the same bits")
Karl 11-04: "Run stock v0.2.10 on the same KL check with the two GDN paths on vs. off, and add the HC region switch on
vs. off. If stock shows the same failure: it's upstream's. If stock is fine: it comes from our port; record which
patches interact, for the next port."

Arms (configs/, made by work/r22/scratch-g19/make_configs19.py; each = s0210-h + exactly the port arm's difference
against P0210x-h, checked by `cfgcheck`): s0210-h (off), s0210-h-gdn (TC=1 + CONVL2=2), s0210-h-gdntc, s0210-h-gdncv
(optional), s0210-h-hcr (+ STRATA_PF_HC_REGION=1).

THE RULES (per item; the port's verdicts are gap 17's gates, read from results/r22/gap17/gates.txt):
  KL items (0) stack, (0t) TC alone, (0v) CONVL2 alone - pf_yardstick long40, kernel_rule2.py AND kernel_rule3.py (with
    the NLL check) against gap 8's ref with gap 8's rounding references unfused / cpushare: the SAME rule, references and
    bounds as gap 17's klrules (the port's dirs are scored in the same call, so both builds sit under one set of bounds).
    Needed first: stock OFF passes both rules (kl2_s210 + kl3_s210, as the port's kl2_p210 + kl3_p210 did), every arm's
    engine environment check passed (env_pfy-*), every arm complete (40 of 40 logit rows written in this gap, no fatal /
    non-finite line in its engine log).
      UPSTREAM  stock ON fails every rule the port's arm failed in gap 17
      OURS      stock ON passes both rules where the port's arm failed
      UNCLEAR   anything else: stock OFF fails a rule itself, an env check failed, an arm is missing or incomplete, or
                the two rules disagree on stock (one PASS, one FAIL)
    INFO beside it: the same-build on-vs-off distance (stock ON against stock OFF, port ON against port OFF: KL mean,
    p90, KL > 1 rows, changed top-1, NLL change); bitwise rows (stock ON = port ON, stock OFF = port OFF: logit files
    identical of 40 - 40 of 40 means the port's arm IS stock's, bit for bit).
  HC item (3) - exact7 at pin 2500 (bringup/lib/exact7.sh; --adapt-swaps 0 --suffix-draft 0): stock OFF (g19-s210),
    then stock HC ON (g19-s210hcr) against it. Needed: both env checks passed, all 7 items of both runs written in this
    gap, slots MATCHED (one slot count over both runs), the start line "STRATA_PF_HC_REGION on" in every ON item's log
    and in no OFF item's log.
      UPSTREAM  stock ON < 7/7 identical to stock OFF (the port: 3/7 MATCHED in gap 17)
      OURS      stock ON 7/7 identical
      UNCLEAR   anything else (slots DIFFER, a run missing or incomplete, an env check failed, the start line missing)
    INFO: the mechanism table (`hcrdiag`, both pairs): per item the output hash, the slots the prompt path borrows, the
    prompt's experts on the CPU (and the share), the prompt chunk. PLACEMENT = the differing items are exactly the items
    whose prompt ran with the CPU share (share > 0) and whose CPU-expert count moved: the HC region shrinks the prompt
    path's loan, more experts stay held, the CPU share takes others - a placement change, not a kernel change. With
    G19_HCR_SHARE0=1 the gap also runs the pair with STRATA_PREFILL_CPU_SHARE=0 (g19-s210z / g19-s210hcrz): 7/7 there
    confirms it. g19-s210 against gap 17's g17-s210 (the same build and config, pin 2500) is the cross-gap repeat (INFO).
    The optional pf_yardstick on s0210-h-hcr: logit files differing from s210 (INFO; the port's: 0 of 40 in gap 17).

Subcommands (the gap script calls them):
  cfgcheck [--gate --gates]                          the stock arms differ from s0210-h exactly as the port's from P0210x-h
  envcli EXE CONFIG --job PID --mode pfy|e7 [--set K=V ...] [--kill] [--gate --gates]
        watches the job's process tree; every engine process (/proc/PID/exe = EXE) is checked as it starts: the config's
        env exactly (pfy: with pf_yardstick's FIXED_ENV over it; --set: ENVX over it), no other STRATA_* variable
        (STRATA_MON_GPU and pfy's STRATA_DUMP_FIRST_LOGITS allowed), STRATA_ROUTE_TAIL_SKIP=0, 2 GPUs, the harness's
        arguments (pfy: --serve, --expert-cache 1, --pcie-frac 0, --kv fp16, --prefill auto; e7: --expert-cache 2500,
        --adapt-swaps 0, --suffix-draft 0, --kv-resident 32768). --kill: an engine that fails is stopped by its PID
        before it measures (the arm is then void). Returns when the job has ended.
  klgates OUTDIR                                     kl2_* / kl3_* gates of the stock arms from OUTDIR/kl2.txt, kl3.txt
  hcrdiag OFF_LABEL ON_LABEL                         the mechanism table for one exact7 pair (any two labels)
  decide OUTDIR                                      -> OUTDIR/decision.txt
"""
import argparse
import filecmp
import hashlib
import importlib.util
import json
import os
import re
import signal
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
C = WS / "configs"
PROF = WS / "bringup/out/logs/prof"
G17 = WS / "results/r22/gap17"
EST = WS / "engine-v0210stock/strata"
ITEMS = ("x-math", "s-math", "x-code", "s-code", "x-p2000", "x-32k", "x-112k")
PINS = {   # results/r22/port-0210-review.md section 0 (as g17_rules.py)
    "STRATA_LOOKUP_MAX_T": "0", "STRATA_GDN_TC": "0", "STRATA_GDN_CONVL2": "0", "STRATA_GR_V3_PF": "0", "STRATA_GR_R2": "0",
    "STRATA_SMALL_UNR": "0", "STRATA_QSA_FUSE_NR": "0", "STRATA_IL_PAD": "0", "STRATA_DF_PDL": "0",
    "STRATA_PCIE_START": "old", "STRATA_ARENA_RAM_FALLBACK": "0", "STRATA_MTP_KEEP": "1", "STRATA_SPILL_OFF": "1",
    "STRATA_PENALTY_PROMPT": "1"}
OURS = ("STRATA_SPEC_EXACT", "STRATA_GR_FORK", "STRATA_PREFILL_V2", "STRATA_ROUTER_Q8K", "STRATA_COST_GATE",
        "STRATA_DRAFT_CUM")   # our six engine switches (no read site in stock v0.2.10)
# stock arm config, port arm config (each against its base: s0210-h / P0210x-h)
CFG_PAIRS = (("s0210-h-gdn", "P0210x-h-gdn"), ("s0210-h-gdntc", "P0210x-h-gdntc"), ("s0210-h-gdncv", "P0210x-h-gdncv"),
             ("s0210-h-hcr", "P0210x-h-hcr"))
# pf_yardstick dir: (gate suffix, port dir, port gate suffix, what)
KL_ARMS = {"s210": ("s210", "p210", "p210", "both GDN paths off"),
           "s210gdn": ("sgdn", "p210gdn", "gdn", "GDN stack (TC=1 + CONVL2=2)"),
           "s210gdntc": ("sgdntc", "p210gdntc", "gdntc", "GDN_TC alone (TC=1, CONVL2=0)"),
           "s210gdncv": ("sgdncv", "p210gdncv", "gdncv", "GDN_CONVL2 alone (TC=0, CONVL2=2)")}
FATAL = re.compile(r"fatal GPU error|no progress for [0-9]+ s|became non-finite|nonfinite|non-finite logits")
HC_LINE = "STRATA_PF_HC_REGION on"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def read_gates(p):
    g = {}
    for line in Path(p).read_text().splitlines() if Path(p).exists() else []:
        k, _, rest = line.partition(" ")
        s, _, det = rest.partition(" ")
        g[k] = (s, det)     # the last line of a gate counts
    return g


# ------------------------------------------------------------------------------------------------ configs
def env_diff(base, arm):
    b, x = base.get("env", {}), arm.get("env", {})
    return {k: (b.get(k), x.get(k)) for k in sorted(set(b) | set(x)) if b.get(k) != x.get(k)}


def rest(d):
    return {k: v for k, v in d.items() if k not in ("_comment", "log", "env", "exe", "server")}


def cfgcheck(a):
    sb = json.loads((C / "s0210-h.json").read_text())
    pb = json.loads((C / "P0210x-h.json").read_text())
    bad, lines = [], []
    if sb["exe"] != str(EST):
        bad.append(f"s0210-h exe {sb['exe']} (want {EST})")
    e = sb.get("env", {})
    bad += [f"s0210-h sets our {k}" for k in OURS if k in e]
    bad += [f"s0210-h pin {k}={e.get(k, 'unset')} (want {v})" for k, v in PINS.items() if e.get(k) != v]
    if e.get("STRATA_ROUTE_TAIL_SKIP") != "0":
        bad.append("s0210-h STRATA_ROUTE_TAIL_SKIP is not 0")
    if len([x for x in e.get("CUDA_VISIBLE_DEVICES", "").split(",") if x]) != 2:
        bad.append("s0210-h does not name 2 GPUs")
    if "--chat-cache" in sb["args"]:
        bad.append("s0210-h has --chat-cache (ours; stock has no such flag)")
    for s, p in CFG_PAIRS:
        try:
            sa = json.loads((C / f"{s}.json").read_text())
            pa = json.loads((C / f"{p}.json").read_text())
        except OSError as ex:
            bad.append(f"{ex}")
            continue
        ds, dp = env_diff(sb, sa), env_diff(pb, pa)
        same_rest = rest(sa) == rest(sb) and sa["exe"] == sb["exe"]
        lines.append(f"{s}: {ds} | {p}: {dp} -> {'same difference' if ds == dp and same_rest else 'NOT the same'}")
        if ds != dp:
            bad.append(f"{s} differs from s0210-h by {ds}, {p} from P0210x-h by {dp}")
        if not same_rest:
            bad.append(f"{s}: args / exe / other fields are not s0210-h's")
    for x in lines:
        print(x)
    line = ("the stock arms differ from s0210-h exactly as the port's arms from P0210x-h; s0210-h = stock, 14 pins, none of ours"
            if not bad else "; ".join(bad)[:400])
    print(("CONFIG CHECK OK: " if not bad else "CONFIG CHECK FAILED: ") + line)
    gate(a, "FAIL" if bad else "PASS", line)
    return 1 if bad else 0


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
        for c in kids.get(todo.pop(), []):
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


def envcli(a):
    cfg = json.loads(Path(a.config).read_text())
    want = dict(cfg.get("env", {}))
    allowed = {"STRATA_MON_GPU"}
    if a.mode == "pfy":
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
    for kv in a.set or []:
        k, _, v = kv.partition("=")
        want[k] = v
    exe = os.path.realpath(a.exe)
    seen = {}

    def check(env, argv):
        bad = [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]
        bad += [f"{k}={env[k]} (not in the config)" for k in sorted(env) if k.startswith("STRATA_") and k not in want
                and k not in allowed]
        if env.get("STRATA_ROUTE_TAIL_SKIP") != "0":
            bad.append(f"STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}")
        n = len([x for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
        if n != 2:
            bad.append(f"{n} GPU(s) in CUDA_VISIBLE_DEVICES (want 2)")
        if a.mode == "pfy" and (len(argv) < 2 or argv[1] != "--serve"):
            bad.append("not the --serve engine")
        bad += [f"{k} {last_val(argv, k)} (want {v})" for k, v in args_want.items() if last_val(argv, k) != v]
        return bad

    while True:
        done = not alive(a.job)
        for pid in sorted(proc_tree(a.job) | {a.job}):   # (a job of one command may exec the engine itself)
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
            bad = check(env, argv)
            seen[pid] = bad
            killed = ""
            if bad and a.kill:
                try:
                    os.kill(pid, signal.SIGTERM)
                    killed = "; STOPPED (pid) before it measures"
                except OSError:
                    killed = "; could not stop it"
            print(f"engine pid {pid}: {len(want)} env keys, STRATA_ROUTE_TAIL_SKIP={env.get('STRATA_ROUTE_TAIL_SKIP', 'unset')}, "
                  f"{len([x for x in env.get('CUDA_VISIBLE_DEVICES', '').split(',') if x])} GPU(s), "
                  f"{' '.join(f'{k} {last_val(argv, k)}' for k in args_want)}"
                  + (f" -> ENV MISMATCH {', '.join(bad)}{killed}" if bad else " -> ENV OK"), flush=True)
        if done:
            break
        time.sleep(0.2)
    bad_all = [b for v in seen.values() for b in v]
    if not seen:
        line = f"no engine {exe} started in job {a.job}"
    elif bad_all:
        line = f"{sum(1 for v in seen.values() if v)} of {len(seen)} engine start(s) not as configured: " + "; ".join(sorted(set(bad_all)))
    else:
        line = f"{len(seen)} engine start(s) ({a.mode}), {len(want)} env keys as configured, no other STRATA_*, harness args as expected"
    ok = bool(seen) and not bad_all
    print(("ENV CHECK OK: " if ok else "ENV CHECK FAILED - the arm is void: ") + line)
    gate(a, "PASS" if ok else "FAIL", line[:400])
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------------ KL
KL2_RE = re.compile(r"^(\S+)\s+top-1 (\d+)/(\d+)\s+KL mean ([\d.]+)\s+p90 ([\d.]+)\s+rows > 1: (\d+)\s+\(max ([\d.]+), not judged\)"
                    r"(?:\s+-> (PASS|FAIL.*))?\s*$")
KL3_RE = re.compile(r"^(\S+)\s+KL mean ([\d.]+)\s+p90 ([\d.]+)\s+rows > 1: (\d+)\s+changed top-1 (\d+)/(\d+)\s+NLL ([\d.]+) "
                    r"\(([+-][\d.]+)\)(?:\s+-> (PASS|FAIL.*))?\s*$")


def parse_kl(p2, p3):
    r = {}
    for f, rx, kind in ((p2, KL2_RE, 2), (p3, KL3_RE, 3)):
        for line in Path(f).read_text(errors="replace").splitlines() if Path(f).exists() else []:
            m = rx.match(line.strip())
            if not m:
                continue
            d = r.setdefault(m[1], {})
            if kind == 2:
                d.update(hits=int(m[2]), n=int(m[3]), mean=float(m[4]), p90=float(m[5]), high=int(m[6]), max=float(m[7]),
                         v2=(m[8] or "").strip(), l2=line.strip())
            else:
                d.update(mean3=float(m[2]), flips=int(m[5]), nll=float(m[7]), dnll=float(m[8]), v3=(m[9] or "").strip(),
                         l3=line.strip())
    return r


def bounds(p):
    for line in Path(p).read_text(errors="replace").splitlines() if Path(p).exists() else []:
        if " - bounds: " in line:
            return line.split(" - bounds: ", 1)[1].strip()
    return "?"


def klgates(a):
    o = Path(a.outdir)
    kl = parse_kl(o / "kl2.txt", o / "kl3.txt")
    g = o / "gates.txt"
    for arm, (gs, *_rest) in KL_ARMS.items():
        if not (o / "pfy" / arm / "index.json").exists():
            continue
        d = kl.get(arm, {})
        for k, v, l in (("kl2", d.get("v2"), d.get("l2")), ("kl3", d.get("v3"), d.get("l3"))):
            st = "PASS" if v == "PASS" else "FAIL"
            with open(g, "a") as f:
                f.write(f"{k}_{gs} {st} {re.sub(r'  +', ' ', l) if l else 'no line in ' + k + '.txt'}\n")
            print(f"  gate {k}_{gs} {st}")
    return 0


def pfy_state(d, t0):
    """(complete, why) for a pf_yardstick dir of this gap"""
    ix = d / "index.json"
    if not ix.exists():
        return False, "not run"
    if t0 and ix.stat().st_mtime < t0:
        return False, "index.json older than this gap (a stale run)"
    n = len(json.loads(ix.read_text())["requests"])
    rows = len(list(d.glob("first.*")))
    err = (d / "stderr.txt").read_text(errors="replace") if (d / "stderr.txt").exists() else ""
    fat = len(FATAL.findall(err))
    if n != 40 or rows != 40:
        return False, f"{rows} logit rows of {n} requests (want 40 / 40)"
    if fat:
        return False, f"{fat} fatal / non-finite line(s) in its stderr.txt"
    return True, "40 / 40"


def ndiff(a, b):
    if not (a / "index.json").exists() or not (b / "index.json").exists():
        return None
    fs = sorted(a.glob("first.*"))
    same = sum(1 for f in fs if (b / f.name).exists() and filecmp.cmp(f, b / f.name, shallow=False))
    return same, len(fs)


def onoff(root, off, on):
    """the same-build distance: ON's rows against OFF's (kernel_rule3's row arithmetic)"""
    if not (root / off / "index.json").exists() or not (root / on / "index.json").exists():
        return None
    k3 = load("kernel_rule3", WS / "work/r22/kernel_rule3.py")
    idx = json.loads((root / off / "index.json").read_text())["requests"]
    r = k3.run_rows(root / off, root / on, idx, k3.next_tokens(len(idx)))
    dn = sum(c - b for _, c, b in r["nll_rows"]) / max(len(r["nll_rows"]), 1)
    return (f"KL mean {r['mean']:.6f}  p90 {r['p90']:.6f}  KL>1 {r['high']}  changed top-1 {r['flips']}/{r['n']}  "
            f"NLL {dn:+.4f}")


# ------------------------------------------------------------------------------------------------ exact7
def item_info(label, item):
    o, e = PROF / f"{label}-{item}.out", PROF / f"{label}-{item}.err"
    d = {"ok": False, "mtime": 0}
    if not o.exists():
        return d
    t = o.read_text(errors="replace")
    m = re.search(r"^output\s*:\s*(.*)$", t, re.M)
    d["out"] = hashlib.sha256(m[1].strip().encode()).hexdigest()[:8] if m else None   # p0_table.parse's hash
    d["ok"] = d["out"] is not None
    d["mtime"] = o.stat().st_mtime
    err = e.read_text(errors="replace") if e.exists() else ""
    s = re.findall(r"expert cache (\d+) slots", err)
    h = re.findall(r"CUDA1: (\d+) additional experts", err)
    d["slots"] = (int(s[-1]) if s else 0, int(h[-1]) if h else 0)
    b = re.findall(r"prompt path borrows (\d+) cache slots", err)
    d["borrow"] = int(b[-1]) if b else None
    r = re.findall(r"resident (\d+), on the CPU (\d+) \(share ([\d.]+)\)", err)
    d["res"], d["cpu"], d["share"] = (int(r[-1][0]), int(r[-1][1]), float(r[-1][2])) if r else (None, None, None)
    c = re.findall(r"prompt chunk auto: (\d+) tokens", err)
    d["chunk"] = int(c[-1]) if c else None
    d["hc"] = HC_LINE in err
    d["fatal"] = len(FATAL.findall(err))
    return d


def e7pair(off, on, t0=0.0):
    """compare two exact7 runs item by item: (n_identical or None, slots verdict, why-not-complete, per-item rows)"""
    rows, why = [], []
    for it in ITEMS:
        x, y = item_info(off, it), item_info(on, it)
        for lab, d in ((off, x), (on, y)):
            if not d["ok"]:
                why.append(f"{lab}-{it} has no output")
            elif t0 and d["mtime"] < t0:
                why.append(f"{lab}-{it} is older than this gap")
            elif d["fatal"]:
                why.append(f"{lab}-{it}: {d['fatal']} fatal line(s)")
        rows.append((it, x, y))
    slots = {r[1].get("slots") for r in rows} | {r[2].get("slots") for r in rows}
    sv = "MATCHED" if len(slots) == 1 and None not in slots else "DIFFER"
    n = sum(1 for _, x, y in rows if x.get("out") and x.get("out") == y.get("out")) if not why else None
    return n, sv, why, rows, sorted(s for s in slots if s)


def hcr_table(off, on, t0=0.0):
    n, sv, why, rows, slots = e7pair(off, on, t0)
    out = [f"  {'item':8s} {'same':5s} {'borrow off/on':>14s} {'CPU experts off/on (share)':>27s} {'resident off/on':>16s} "
           f"{'chunk off/on':>13s}"]
    diff, moved = set(), set()
    for it, x, y in rows:
        known = x.get("out") is not None and y.get("out") is not None
        same = known and x.get("out") == y.get("out")
        if not same:
            diff.add(it)
        sh = x.get("share")
        if sh and sh > 0 and x.get("cpu") != y.get("cpu"):
            moved.add(it)
        out.append(f"  {it:8s} {('=' if same else 'DIFF') if known else '?':5s} {str(x.get('borrow')) + ' / ' + str(y.get('borrow')):>14s} "
                   f"{str(x.get('cpu')) + ' / ' + str(y.get('cpu')) + ' (' + str(sh) + ')':>27s} "
                   f"{str(x.get('res')) + ' / ' + str(y.get('res')):>16s} {str(x.get('chunk')) + ' / ' + str(y.get('chunk')):>13s}")
    if why:
        concl = "not judged (" + "; ".join(why[:3]) + ")"
    elif not diff:
        concl = "no item differs"
    elif diff == moved:
        concl = ("PLACEMENT: the differing items are exactly the prompts that ran with the CPU share and whose CPU-expert "
                 "count moved with the smaller loan; the items without the share are identical (even where the chunk moved)")
    else:
        concl = (f"NOT PLACEMENT ALONE: differing {sorted(diff)}, CPU-share items whose CPU-expert count moved "
                 f"{sorted(moved)}")
    head = (f"{on} vs {off}: {n if n is not None else '?'}/7 identical, slots {sv} "
            f"({' / '.join(f'{a}+{b}' for a, b in slots) or '?'})")
    return head, out, concl, n, sv, why, diff


def hcrdiag(a):
    head, out, concl, *_ = hcr_table(a.off, a.on)
    print(head)
    print("\n".join(out))
    print("  -> " + concl)
    return 0


# ------------------------------------------------------------------------------------------------ the decision
def fmt_row(name, build, d):
    if not d:
        return f"  {name:30s} {build:6s} (no data)"
    return (f"  {name:30s} {build:6s} {d.get('mean', float('nan')):9.6f} {d.get('p90', float('nan')):9.6f} "
            f"{d.get('high', '-'):>5} {str(d.get('hits', '-')) + '/' + str(d.get('n', '-')):>6} {str(d.get('flips', '-')):>6} "
            f"{d.get('nll', float('nan')):7.4f} ({d.get('dnll', float('nan')):+.4f})  "
            f"{(d.get('v2') or '-').split(' ')[0]:5s} {(d.get('v3') or '-').split(' ')[0]:5s}")


def fails_of(v):
    m = re.search(r"FAIL \((.*)\)", v or "")
    return m[1] if m else ""


def decide(a):
    o = Path(a.outdir)
    y = o / "pfy"
    g = read_gates(o / "gates.txt")
    g17 = read_gates(G17 / "gates.txt")
    s = lambda k: g.get(k, ("MISSING", ""))[0]
    s17 = lambda k: g17.get(k, ("MISSING", ""))[0]
    t0 = float((o / "t0.txt").read_text().split()[0]) if (o / "t0.txt").exists() else 0.0
    kl = parse_kl(o / "kl2.txt", o / "kl3.txt")
    k17 = parse_kl(G17 / "kl-p210-p210gdn.txt", G17 / "kl3-p210-p210gdn.txt")
    k17.update(parse_kl(G17 / "kl-p210gdntc-p210gdncv.txt", G17 / "kl3-p210gdntc-p210gdncv.txt"))
    L = []
    L.append("GAP 19 - a diagnostic on STOCK v0.2.10 (engine-v0210stock, ffa80d731) beside our port (engine-r22p0210, gap 17)."
             " Nothing switches.")
    L.append(f"  config check: {s('cfg')} {g.get('cfg', ('', ''))[1][:160]}")
    L.append(f"  stock engine: {s('build_stock')} {g.get('build_stock', ('', ''))[1][:160]}")

    # ---- KL table
    L.append("")
    L.append("KL (pf_yardstick long40 against gap 8's ref; rounding references unfused / cpushare; gap 17's rule and bounds)")
    L.append(f"  kernel_rule2 bounds: {bounds(o / 'kl2.txt')}")
    L.append(f"  kernel_rule3 bounds: {bounds(o / 'kl3.txt')}")
    L.append(f"  {'arm':30s} {'build':6s} {'KL mean':>9s} {'p90':>9s} {'KL>1':>5s} {'top-1':>6s} {'chg':>6s} {'NLL (vs ref)':>17s}  "
             f"{'kl2':5s} {'kl3':5s}")
    repro = []
    for arm, (gs, parm, pg, what) in KL_ARMS.items():
        sd = kl.get(arm)
        pd = kl.get(parm) or k17.get(parm)
        if sd is None and not (y / arm).exists():
            L.append(f"  {what:30s} stock  (not run)")
        else:
            L.append(fmt_row(what, "stock", sd))
        L.append(fmt_row(what, "port", pd))
        if kl.get(parm) and k17.get(parm):
            same = all(abs(kl[parm].get(k, 0) - k17[parm].get(k, 0)) < 1e-6 for k in ("mean", "p90", "nll"))
            repro.append(f"{parm} {'=' if same else 'DIFFERS from'} gap 17")
    if repro:
        L.append("  (the port's rows, rescored in this gap from gap 17's dirs: " + ", ".join(repro) + ")")
    L.append("  same build, ON against OFF (INFO):")
    for arm, (gs, parm, pg, what) in KL_ARMS.items():
        if arm == "s210":
            continue
        for build, off, on in (("stock", "s210", arm), ("port", "p210", parm)):
            r = onoff(y, off, on)
            if r:
                L.append(f"    {what:30s} {build:6s} {r}")
    L.append("  bitwise (INFO; logit files identical of 40):")
    for sa, pa in (("s210", "p210"), ("s210gdn", "p210gdn"), ("s210gdntc", "p210gdntc"), ("s210gdncv", "p210gdncv")):
        r = ndiff(y / sa, y / pa)
        if r:
            L.append(f"    stock {sa} = port {pa}: {r[0]} of {r[1]}" + ("  (the port's arm IS stock's, bit for bit)" if r[0] == r[1] == 40 else ""))
    r = ndiff(y / "s210hcr", y / "s210")
    if r:
        L.append(f"    stock HC ON = stock OFF (yardstick): {r[0]} of {r[1]}  (port, gap 17: hcr_logits {s17('hcr_logits')} "
                 f"{g17.get('hcr_logits', ('', ''))[1][:60]})")

    # ---- KL verdicts
    verdicts = []

    def kl_item(tag, arm):
        gs, parm, pg, what = KL_ARMS[arm]
        need = []
        for x in ("s210", arm):
            ok, why = pfy_state(y / x, t0)
            if not ok:
                need.append(f"{x}: {why}")
            if s(f"env_pfy-{x}") != "PASS":
                need.append(f"env_pfy-{x} {s(f'env_pfy-{x}')}")
        port = {r: s17(f"{r}_{pg}") for r in ("kl2", "kl3")}
        st = {r: s(f"{r}_{gs}") for r in ("kl2", "kl3")}
        base = {r: s(f"{r}_s210") for r in ("kl2", "kl3")}
        pf = [r for r in ("kl2", "kl3") if port[r] == "FAIL"]
        sd, pd = kl.get(arm, {}), kl.get(parm) or k17.get(parm, {})
        nums = (f"stock KL mean {sd.get('mean', float('nan')):.3f} p90 {sd.get('p90', float('nan')):.3f} KL>1 {sd.get('high', '?')} "
                f"NLL {sd.get('dnll', float('nan')):+.3f} [{fails_of(sd.get('v2')) or sd.get('v2', '?')}] / port "
                f"{pd.get('mean', float('nan')):.3f} / {pd.get('p90', float('nan')):.3f} / {pd.get('high', '?')} / "
                f"{pd.get('dnll', float('nan')):+.3f} [{fails_of(pd.get('v2')) or pd.get('v2', '?')}]")
        if need:
            v, why = "UNCLEAR", "not judged: " + "; ".join(need)
        elif base["kl2"] != "PASS" or base["kl3"] != "PASS":
            v, why = "UNCLEAR", (f"stock with both GDN paths OFF fails the rule itself (kl2_s210 {base['kl2']}, kl3_s210 "
                                 f"{base['kl3']}; the port's off arm passed): no clean base")
        elif not pf:
            v, why = "UNCLEAR", f"the port's arm did not fail in gap 17 (kl2_{pg} {port['kl2']}, kl3_{pg} {port['kl3']})"
        elif all(st[r] == "FAIL" for r in pf):
            v, why = "UPSTREAM", f"stock fails {' + '.join(f'{r}_{gs}' for r in pf)} as the port failed {' + '.join(f'{r}_{pg}' for r in pf)}"
        elif all(st[r] == "PASS" for r in ("kl2", "kl3")):
            v, why = "OURS", (f"stock passes kl2_{gs} + kl3_{gs} where the port failed {' + '.join(f'{r}_{pg}' for r in pf)}: "
                              f"our port's patches interact (candidates: PATCH-OVERLAP.md)")
        else:
            v, why = "UNCLEAR", f"the two rules disagree on stock (kl2_{gs} {st['kl2']}, kl3_{gs} {st['kl3']})"
        bw = ndiff(y / arm, y / parm)
        extra = f"; stock ON = port ON bit for bit on {bw[0]} of {bw[1]}" if bw else ""
        verdicts.append(f"({tag}) {what}: {v} - {why}")
        verdicts.append(f"     {nums}{extra}")

    kl_item("0", "s210gdn")
    for tag, arm in (("0t", "s210gdntc"), ("0v", "s210gdncv")):
        if (y / arm).exists() or s(f"env_pfy-{arm}") != "MISSING":
            kl_item(tag, arm)
        else:
            verdicts.append(f"({tag}) {KL_ARMS[arm][3]}: NOT RUN (optional; the deadline did not allow it)")

    # ---- exact7: the HC region
    L.append("")
    L.append("exact7 at pin 2500 (--adapt-swaps 0 --suffix-draft 0): PF_HC_REGION on vs off")
    head, rows, concl, n, sv, why, diff = hcr_table("g19-s210", "g19-s210hcr", t0)
    L.append("  stock: " + head)
    L += rows
    L.append("    -> " + concl)
    phead, prows, pconcl, pn, psv, pwhy, pdiff = hcr_table("g17-p210a", "g17-hcr")
    L.append(f"  port (gap 17, e7_hcr {s17('e7_hcr')} {g17.get('e7_hcr', ('', ''))[1]}): " + phead)
    L += prows
    L.append("    -> " + pconcl)
    rn, rsv, rwhy, _, rslots = e7pair("g17-s210", "g19-s210", 0.0)[:5]
    L.append(f"  stock OFF this gap vs gap 17's g17-s210 (the cross-gap repeat, INFO): "
             f"{rn if rn is not None else '?'}/7, slots {rsv}" + (f" ({'; '.join(rwhy[:2])})" if rwhy else ""))
    z = None
    if (PROF / "g19-s210hcrz-x-math.out").exists() or s("env_e7-g19-s210z") != "MISSING":
        zh, zrows, zconcl, zn, zsv, zwhy, _ = hcr_table("g19-s210z", "g19-s210hcrz", t0)
        z = (zn, zsv, zwhy)
        L.append("  stock with STRATA_PREFILL_CPU_SHARE=0 (G19_HCR_SHARE0): " + zh)
        L += zrows

    need = [w for w in why]
    for lab in ("g19-s210", "g19-s210hcr"):
        if s(f"env_e7-{lab}") != "PASS":
            need.append(f"env_e7-{lab} {s(f'env_e7-{lab}')}")
    if not why:
        offs = [item_info("g19-s210", it)["hc"] for it in ITEMS]
        ons = [item_info("g19-s210hcr", it)["hc"] for it in ITEMS]
        if any(offs):
            need.append(f"the HC start line in {sum(offs)} OFF item log(s)")
        if not all(ons):
            need.append(f"the HC start line missing in {7 - sum(ons)} ON item log(s) (the switch did not act)")
    if need:
        v, w = "UNCLEAR", "not judged: " + "; ".join(need[:4])
    elif sv != "MATCHED":
        v, w = "UNCLEAR", "slots DIFFER between stock off and on: not comparable"
    elif n == 7:
        v, w = "OURS", ("stock HC on = off 7/7 at MATCHED slots where the port's was 3/7: our port's patches interact "
                        "(candidates: PATCH-OVERLAP.md)")
    else:
        same = " (the same items as the port's)" if diff == pdiff else f" (port's differing items: {sorted(pdiff)})"
        v, w = "UPSTREAM", f"stock HC on = off only {n}/7 at MATCHED slots, as the port's 3/7{same}"
    verdicts.append(f"(3) PF_HC_REGION=1: {v} - {w}")
    verdicts.append(f"     mechanism (stock): {concl}")
    if z:
        zn, zsv, zwhy = z
        if zwhy or s("env_e7-g19-s210z") != "PASS" or s("env_e7-g19-s210hcrz") != "PASS":
            verdicts.append("     with the prompt CPU share off: not judged (" + "; ".join(zwhy[:2] or ["an env check"]) + ")")
        elif zsv == "MATCHED" and zn == 7:
            verdicts.append("     with the prompt CPU share off: 7/7 MATCHED - the HC region keeps the bits once the share is off: "
                            "upstream's 'same bits' holds for the kernels; the smaller loan moves prompt experts between the "
                            "CPU and the GPU")
        else:
            verdicts.append(f"     with the prompt CPU share off: {zn}/7, slots {zsv} - the placement is not the whole story")

    L.append("")
    L.append("VERDICTS (UPSTREAM = stock fails the same gate the port failed; OURS = stock passes where the port failed; "
             "UNCLEAR otherwise)")
    L += verdicts
    L.append("")
    L.append("Nothing switches (P028x stays served until item 7 is done). OURS -> the candidates are in "
             "results/r22/gap19/PATCH-OVERLAP.md; UPSTREAM -> it goes on the upstream list (Karl decides what is posted).")
    txt = "\n".join(L) + "\n"
    (o / "decision.txt").write_text(txt)
    print(txt, end="")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("cfgcheck")
    p.add_argument("--gate")
    p.add_argument("--gates")
    p = sp.add_parser("envcli")
    p.add_argument("exe")
    p.add_argument("config")
    p.add_argument("--job", type=int, required=True)
    p.add_argument("--mode", choices=["pfy", "e7"], required=True)
    p.add_argument("--set", action="append")
    p.add_argument("--kill", action="store_true")
    p.add_argument("--gate")
    p.add_argument("--gates")
    sp.add_parser("klgates").add_argument("outdir")
    p = sp.add_parser("hcrdiag")
    p.add_argument("off")
    p.add_argument("on")
    sp.add_parser("decide").add_argument("outdir")
    a = ap.parse_args()
    return {"cfgcheck": cfgcheck, "envcli": envcli, "klgates": klgates, "hcrdiag": hcrdiag, "decide": decide}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
