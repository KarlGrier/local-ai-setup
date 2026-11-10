#!/usr/bin/env python3
"""make_configs0213.py - the arm configs of THE v0.2.13 PORT'S BASELINE GATE (Karl 11-10; work/r23/gate-0213/gap-gate0213.sh,
the rules work/r23/gate-0213/gate0213_rules.py). Written 2026-11-10 at the desk. The gate's configs are written AT RUN
TIME into the gate's own folder (results/r23/port-0213/gate/configs/; the dry run and the mock test: their scratch), never
into configs/ - in the form work/r23/scratch-port0211/make_configs0211.py made the v0.2.11 gate's (s0211-h, P0211x-h,
P0211x-h-off, P0211x-h-nov2). The served-form arms B and P are switch_rules.py's own recipes (imported, not copied). The
ONE file this script writes into configs/ is configs/P0213x-single.json (`single`, run once at the desk 11-10; it refuses
to overwrite). Every source config is only read.

  make OUTDIR --log-dir DIR [--no-sha] [--gate G --gates F]   the configs + manifest.json into OUTDIR, then `check`
  check OUTDIR [--no-sha] [--gate G --gates F]                 every config = its recipe recomputed now (CHECKS below)
  single [--out PATH]                                          configs/P0213x-single.json from configs/P0213x.json
  singlecheck [PATH]                                           PATH = P0213x.json with exactly the single-card differences

RECIPES (each its own engine log in --log-dir, engine-g0213-NAME.log: never a served or shared config's log):
  B    switch_rules.py arm_config("B") = configs/P028x.json's test form = configs/x28h.json + STRATA_HC_UPMIX=1 +
       STRATA_ADAPT_FETCH=2 with exe engine-r23afetch/strata (153ce47d3ef0), server strata-r22p028x: the daily as served.
       The screen, Basalt's M, the INFO exact7 da2.
  P    switch_rules.py arm_config("P") = configs/P0213x-af2.json's test form = P0213x.json's + STRATA_ADAPT_FETCH=2 with exe
       engine-r23p0213/strata (639dfb1b7042), server strata-r23p0213: the port in the daily's served form. The screen,
       Basalt's H, the INFO exact7 pa2.
  PH   THE PORT'S CLI FORM (P0211x-h's analogue): configs/P0213x.json's test form (no --vision; no vision / fallback /
       model_not_running key; sq.py's STRIP_ARGS / STRIP_KEYS) = P without STRATA_ADAPT_FETCH. It keeps U
       (STRATA_HC_UPMIX=1, upstream's switch, exact: exact7 7/7 and long40 0 of 40 differ on P028x, 11-09). exact7 p213a /
       p213b, pf_yardstick long40, the patch guards.
  OFF  PH with every switch of ours off: STRATA_SPEC_EXACT, STRATA_GR_FORK, STRATA_PREFILL_V2, STRATA_ROUTER_Q8K,
       STRATA_COST_GATE, STRATA_DRAFT_CUM unset and no --chat-cache / --chat-cache-mib: "patched, every switch off = the
       release" (exact7 against ST).
  ST   OFF on the stock release: exe engine-v0213stock/strata (build-port0213.sh stock), server strata-v0213stock's
       server.py; the same args and env (the 19 pins; U, an upstream switch, stays) - s0211-h's form.
  NOV2 PH without STRATA_PREFILL_V2 (v2 on = off, exact7).
  SG   configs/P0213x-single.json's test form (the single-card fallback start, INFO), when that file exists.
  Used as they are, from configs/: x28h.json (P028x's CLI reference, engine-r22p028x f4c4f654fb24, every gap's) and
  s028-h.json (stock 0.2.8, only when PH is not exact7-identical to x28h).

CHECKS (`check`; every one must hold, else CONFIG CHECK FAILED and the gate does not open):
  - B and P: switch_rules.py cfg_problems() (B = x28h + U + fetch=2 key by key on the daily's binary; P = P0213x's test
    form + fetch=2; P = B apart from the paths, logs, the port's keys and its 19 env pins; the standard sampling; the test
    form; two GPUs; the engine binaries' sha256 and their switch strings - unless --no-sha) with this gate's log names;
  - PH = P0213x.json's test form; PH = P minus STRATA_ADAPT_FETCH and nothing else; PH = x28h + the port's 19 pins +
    STRATA_HC_UPMIX=1 (every x28h env value carried, the same args; top keys beyond x28h's only exe, server, log,
    _comment, drafting, user_args - and x28h's "fallback": null);
  - OFF = PH minus exactly our six switches and the two chat-cache flags; ST = OFF with exe / server swapped, nothing
    else; NOV2 = PH minus STRATA_PREFILL_V2, nothing else; SG = P0213x-single.json's test form and `singlecheck` holds;
  - every gate config: the standard sampling (T 1.0 / 0.95 / 20 / min-p 0.05), no STRATA_DEBUG, no STRATA_ADAPT_FETCH*
    but B's / P's STRATA_ADAPT_FETCH=2, its log in --log-dir under the gate's name;
  - the source configs' sha256 at `make` = now (manifest.json);
  - unless --no-sha: PH / OFF / NOV2 / SG name engine-r23p0213/strata (639dfb1b7042); ST's engine exists and matches its
    SHA256 file.

THE SINGLE-CARD FALLBACK (`single`; REVIEW-1105 4.7, Karl 11-10 "only if it's cheap"): configs/P0213x-single.json =
configs/P0213x.json with the differences configs/Cstar18-single.json has from configs/Cstar18.json, and nothing else:
  CUDA_VISIBLE_DEVICES = the RTX 5080 alone (GPU-UUID-RTX5080-..., the first of P0213x's two); no --expert-cache-device1 N (no
  helper cache); STRATA_DISJOINT_ADAPT unset (the adaptive tier's helper split); STRATA_ROUTE_TAIL_SKIP=0 (the one-GPU
  rule; v0.2.13 has the switch, generate.cpp:12782 - P0213x already pins it 0); "fallback": null; its own log
  (logs/engine-P0213x-single.log); its own _comment.
  NOT carried from Cstar18-single: its strata-v0115 pack / profile / cwd / tokenizer (that file's history, not a one-card
  property): P0213x-single keeps P0213x's bringup/out/r20a pack, the port's. --vision and the vision block (the picture
  reader runs on the CPU, "gpu": false), the model_not_running guard key, the 19 pins and U stay as in P0213x.json.
  P0213x.json's "fallback" key is NOT changed here (Claude does that after the gate).
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path("/home/USER/ai-speed-testing/strata-compare")
C = WS / "configs"
SWR = WS / "work/r23/switch-gap/switch_rules.py"
P13 = C / "P0213x.json"
SGC = C / "P0213x-single.json"
X28H = C / "x28h.json"
S028 = C / "s028-h.json"
SOURCES = {"P028x.json": C / "P028x.json", "P0213x-af2.json": C / "P0213x-af2.json", "P0213x.json": P13,
           "x28h.json": X28H, "s028-h.json": S028, "P0213x-single.json": SGC}
E13 = WS / "engine-r23p0213/strata"
EST = WS / "engine-v0213stock/strata"
SRV13 = WS / "strata-r23p0213/serve/server.py"
SRVST = WS / "strata-v0213stock/serve/server.py"
P_SHA = "639dfb1b7042"
OURS = ("STRATA_SPEC_EXACT", "STRATA_GR_FORK", "STRATA_PREFILL_V2", "STRATA_ROUTER_Q8K", "STRATA_COST_GATE",
        "STRATA_DRAFT_CUM")    # our six engine switches (make_configs0211.py's OURS)
CHAT = ("--chat-cache", "--chat-cache-mib")   # our serve flags (stock has none)
GPU_5080 = "GPU-UUID-RTX5080"
SINGLE_DROP_ENV = ("STRATA_DISJOINT_ADAPT",)
NAMES = ("B", "P", "PH", "OFF", "ST", "NOV2", "SG")
STANDARD = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
FETCH_PREFIX = "STRATA_ADAPT_FETCH"
_M = {}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def swr():
    """switch_rules.py (arm_config, test_form, cfg_problems, port_pins, sha256_file): read-only, loaded once"""
    if "swr" not in _M:
        _M["swr"] = load("switch_rules_g13", SWR)
    return _M["swr"]


def sha(p, n=None):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return h[:n] if n else h


def gate(a, status, detail):
    if getattr(a, "gates", None) and getattr(a, "gate", None):
        with open(a.gates, "a") as f:
            f.write(f"{a.gate} {status} {detail}\n")


def drop_args(args, flags):
    out, i = [], 0
    while i < len(args):
        if args[i] in flags:
            i += 2
            continue
        out.append(args[i])
        i += 1
    return out


def logname(log_dir, n):
    return str(Path(log_dir) / f"engine-g0213-{n}.log")


COMMENTS = {
    "B": "the daily as served (configs/P028x.json's test form = x28h + U + STRATA_ADAPT_FETCH=2 on engine-r23afetch; "
         "switch_rules.py arm B)",
    "P": "the port in the daily's served form (configs/P0213x-af2.json's test form on engine-r23p0213; switch_rules.py arm P)",
    "PH": "the port's CLI form (P0211x-h's analogue): configs/P0213x.json's test form, no STRATA_ADAPT_FETCH",
    "OFF": "PH with every switch of ours off (no SPEC_EXACT, GR_FORK, PREFILL_V2, ROUTER_Q8K, COST_GATE, DRAFT_CUM, no "
           "--chat-cache flags): 'patched, every switch off = the release' (exact7 against ST)",
    "ST": "STOCK v0.2.13 (engine-v0213stock, none of our commits) with OFF's args and env (the 19 pins): exact7's "
          "reference for 'every switch off = the release'",
    "NOV2": "PH without STRATA_PREFILL_V2 (exact7 v2 on vs off)",
    "SG": "configs/P0213x-single.json's test form (the single-card fallback start; INFO)",
}


def recipe(n, log_dir):
    """the gate config NAME as its recipe makes it now (None: SG without configs/P0213x-single.json)"""
    s = swr()
    if n in ("B", "P"):
        c = s.arm_config(n, log_dir)
    elif n == "SG":
        if not SGC.exists():
            return None
        c = s.test_form(SGC)
    else:
        c = s.test_form(P13)
        if n in ("OFF", "ST"):
            for k in OURS:
                c["env"].pop(k, None)
            c["args"] = drop_args(c["args"], CHAT)
        if n == "ST":
            c["exe"], c["server"] = str(EST), str(SRVST)
        if n == "NOV2":
            c["env"].pop("STRATA_PREFILL_V2", None)
    c["log"] = logname(log_dir, n)
    c["_comment"] = (f"r23 v0.2.13 baseline gate (work/r23/gate-0213/make_configs0213.py): arm {n} = {COMMENTS[n]}. "
                     "Measurement only, never served.")
    return c


def cmd_make(a):
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for n in NAMES:
        c = recipe(n, a.log_dir)
        if c is None:
            continue
        (out / f"{n}.json").write_text(json.dumps(c, indent=1) + "\n")
        made.append(n)
    man = {"log_dir": str(a.log_dir), "made": made,
           "_shas": {k: (sha(p) if p.exists() else None) for k, p in SOURCES.items()}}
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n")
    print(f"gate configs in {out}: {', '.join(made)}")
    return cmd_check(a)


def single_problems(path=SGC):
    """[problem]: PATH is P0213x.json with exactly the single-card differences (the docstring's list)"""
    bad = []
    try:
        s1, s0 = json.loads(Path(path).read_text()), json.loads(P13.read_text())
    except (OSError, ValueError) as e:
        return [f"{path}: {e}"]
    want = copy.deepcopy(s0)
    want["args"] = drop_args(want["args"], ("--expert-cache-device1",))
    for k in SINGLE_DROP_ENV:
        want["env"].pop(k, None)
    want["env"]["CUDA_VISIBLE_DEVICES"] = s0["env"]["CUDA_VISIBLE_DEVICES"].split(",")[0]
    want["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"
    want["fallback"] = None
    want["log"] = str(WS / "logs/engine-P0213x-single.log")
    d = sorted(k for k in set(s1) | set(want) if k != "_comment" and s1.get(k) != want.get(k))
    if d:
        bad.append(f"{Path(path).name} is not P0213x.json with the single-card differences (differs in {d})")
    if want["env"]["CUDA_VISIBLE_DEVICES"] != GPU_5080:
        bad.append(f"P0213x.json's first GPU is {want['env']['CUDA_VISIBLE_DEVICES']}, not the RTX 5080 {GPU_5080}")
    e = s1.get("env", {})
    if e.get("STRATA_ROUTE_TAIL_SKIP") != "0" or "--expert-cache-device1" in s1.get("args", []) \
            or len([x for x in e.get("CUDA_VISIBLE_DEVICES", "").split(",") if x]) != 1:
        bad.append("not the one-GPU form (tail skip 0, one GPU, no helper cache)")
    if any(k.startswith(FETCH_PREFIX) for k in e):
        bad.append("a STRATA_ADAPT_FETCH key (P0213x has none)")
    if s1.get("sampling") != STANDARD:
        bad.append(f"sampling {s1.get('sampling')}")
    return bad


def cmd_singlecheck(a):
    bad = single_problems(a.path or SGC)
    print("SINGLE CHECK OK: P0213x.json + the single-card differences (the RTX 5080 alone, no helper cache, no "
          "DISJOINT_ADAPT, tail skip 0, fallback null, its own log)" if not bad else "SINGLE CHECK FAILED: " + "; ".join(bad))
    return 1 if bad else 0


def cmd_single(a):
    out = Path(a.out or SGC)
    if out.exists():
        raise SystemExit(f"{out} exists - not overwritten")
    s0 = json.loads(P13.read_text())
    c = {"_comment": "P0213x-single (Karl 11-10, REVIEW-1105 4.7; work/r23/gate-0213/make_configs0213.py single): the v0.2.13 "
                     "port on the RTX 5080 alone - the launcher's fallback (run-strata.sh helper_check) when the RTX 4060 Ti "
                     "has too little free memory. = configs/P0213x.json with Cstar18-single's one-card differences: "
                     "CUDA_VISIBLE_DEVICES the 5080 only, no --expert-cache-device1, no STRATA_DISJOINT_ADAPT, "
                     "STRATA_ROUTE_TAIL_SKIP=0, fallback null, its own log. A test config: nothing serves it; P0213x.json's "
                     "fallback key still names Cstar18-single until the gate is read."}
    for k, v in s0.items():
        if k == "_comment":
            continue
        c[k] = copy.deepcopy(v)
    c["args"] = drop_args(c["args"], ("--expert-cache-device1",))
    for k in SINGLE_DROP_ENV:
        c["env"].pop(k, None)
    c["env"]["CUDA_VISIBLE_DEVICES"] = s0["env"]["CUDA_VISIBLE_DEVICES"].split(",")[0]
    c["env"]["STRATA_ROUTE_TAIL_SKIP"] = "0"
    c["fallback"] = None
    c["log"] = str(WS / "logs/engine-P0213x-single.log")
    out.write_text(json.dumps(c, indent=1) + "\n")
    print(f"wrote {out}")
    bad = single_problems(out)
    print("SINGLE CHECK OK" if not bad else "SINGLE CHECK FAILED: " + "; ".join(bad))
    return 1 if bad else 0


def problems(out, no_sha=False):
    s = swr()
    bad = []
    try:
        man = json.loads((out / "manifest.json").read_text())
    except (OSError, ValueError):
        return ["manifest.json missing"]
    log_dir = man.get("log_dir")
    cfgs = {}
    for n in NAMES:
        p = out / f"{n}.json"
        if p.exists():
            cfgs[n] = json.loads(p.read_text())
    for n in NAMES:
        want = recipe(n, log_dir)
        if want is None:
            if n in cfgs:
                bad.append(f"{n}.json present but configs/P0213x-single.json is not")
            continue
        if n not in cfgs:
            bad.append(f"{n}: config missing")
            continue
        d = sorted(k for k in set(cfgs[n]) | set(want) if k != "_comment" and cfgs[n].get(k) != want.get(k))
        if d:
            bad.append(f"{n}: differs from its recipe now in {d}")
    for k, p in SOURCES.items():
        now = sha(p) if p.exists() else None
        if now != man.get("_shas", {}).get(k):
            bad.append(f"configs/{k} changed since the configs were made")
    if bad:
        return bad
    # B / P: switch_rules.py's own recipe check (with its log names put back, and its debug arms as it makes them)
    sw = {n: s.arm_config(n, log_dir) for n in s.ARMS}
    for n in ("B", "P"):
        sw[n] = dict(cfgs[n], log=sw[n]["log"])
    sman = {n: {"log_dir": log_dir} for n in s.ARMS}
    sman["_shas"] = {k: man["_shas"][k] for k in ("P028x.json", "P0213x-af2.json", "P0213x.json", "x28h.json")}
    bad += [f"(switch_rules) {x}" for x in s.cfg_problems(sw, sman, no_sha)]
    b, p, ph, off, st, nov2 = (cfgs[n] for n in ("B", "P", "PH", "OFF", "ST", "NOV2"))
    pins = s.port_pins()
    top_ok = {"_comment", "log"}
    # PH = P minus STRATA_ADAPT_FETCH
    w = copy.deepcopy(p)
    w["env"].pop("STRATA_ADAPT_FETCH", None)
    d = sorted(k for k in set(ph) | set(w) if k not in top_ok and ph.get(k) != w.get(k))
    if d:
        bad.append(f"PH is not P minus STRATA_ADAPT_FETCH (differs in {d})")
    # PH = x28h + the 19 pins + U
    x = json.loads(X28H.read_text())
    extra = {k: v for k, v in ph["env"].items() if k not in x["env"]}
    want_extra = dict(pins, STRATA_HC_UPMIX="1")
    if extra != want_extra:
        bad.append(f"PH's env beyond x28h's is not the port's {len(pins)} pins + STRATA_HC_UPMIX=1: extra "
                   f"{sorted(set(extra) - set(want_extra))}, missing {sorted(set(want_extra) - set(extra))}, values "
                   f"{sorted(k for k in extra if k in want_extra and extra[k] != want_extra[k])}")
    lost = sorted(k for k in x["env"] if ph["env"].get(k) != x["env"][k])
    if lost:
        bad.append(f"PH does not carry x28h's env value for {lost}")
    if ph.get("args") != x.get("args"):
        bad.append("PH's args are not x28h's")
    dtop = sorted(k for k in set(ph) | set(x) if k not in ("exe", "server", "log", "_comment", "drafting", "user_args", "env")
                  and ph.get(k) != x.get(k) and not (k == "fallback" and x.get(k) is None and k not in ph))
    if dtop:
        bad.append(f"PH and x28h differ beyond the paths and the port's keys in {dtop}")
    # OFF, ST, NOV2
    w = copy.deepcopy(ph)
    for k in OURS:
        w["env"].pop(k, None)
    w["args"] = drop_args(w["args"], CHAT)
    if sorted(k for k in set(off) | set(w) if k not in top_ok and off.get(k) != w.get(k)):
        bad.append("OFF is not PH minus our six switches and the chat-cache flags")
    if any(k in off["env"] for k in OURS) or any(f in off["args"] for f in CHAT):
        bad.append("OFF still has one of our switches")
    w = dict(copy.deepcopy(off), exe=str(EST), server=str(SRVST))
    if sorted(k for k in set(st) | set(w) if k not in top_ok and st.get(k) != w.get(k)):
        bad.append("ST is not OFF on the stock engine")
    w = copy.deepcopy(ph)
    w["env"].pop("STRATA_PREFILL_V2", None)
    if sorted(k for k in set(nov2) | set(w) if k not in top_ok and nov2.get(k) != w.get(k)):
        bad.append("NOV2 is not PH minus STRATA_PREFILL_V2")
    if "SG" in cfgs:
        bad += [f"(single) {x}" for x in single_problems(SGC)]
    for n, c in cfgs.items():
        e = c.get("env", {})
        if c.get("sampling") != STANDARD:
            bad.append(f"{n}: sampling {c.get('sampling')}")
        if "STRATA_DEBUG" in e:
            bad.append(f"{n}: STRATA_DEBUG set")
        fk = {k: v for k, v in e.items() if k.startswith(FETCH_PREFIX)}
        if fk != ({"STRATA_ADAPT_FETCH": "2"} if n in ("B", "P") else {}):
            bad.append(f"{n}: fetch keys {fk}")
        if c.get("log") != logname(log_dir, n):
            bad.append(f"{n}: log {c.get('log')}")
        if n != "B" and n != "ST" and c.get("exe") != str(E13):
            bad.append(f"{n}: exe {c.get('exe')} (want {E13})")
    if ph.get("drafting") != "mtp" or ph.get("user_args") != ["--kv-resident", "32768"]:
        bad.append("PH lacks the port's keys (drafting mtp, user_args --kv-resident 32768)")
    if not no_sha:
        if not E13.is_file() or sha(E13, 12) != P_SHA:
            bad.append(f"{E13} is not {P_SHA}")
        sf = EST.parent / "SHA256"
        if not EST.is_file() or not sf.is_file() or sha(EST, 12) != sf.read_text()[:12]:
            bad.append(f"{EST} missing or not its SHA256 file's")
    return bad


def cmd_check(a):
    out = Path(a.outdir)
    bad = problems(out, getattr(a, "no_sha", False))
    try:
        made = json.loads((out / "manifest.json").read_text()).get("made", [])
    except (OSError, ValueError):
        made = []
    line = ("CONFIG CHECK OK: B / P = switch_rules.py's arms (the daily / the port, served form); PH = P minus "
            "STRATA_ADAPT_FETCH = x28h + the port's 19 pins + U; OFF = PH minus our six switches; ST = OFF on stock "
            f"v0.2.13; NOV2 = PH minus v2{'; SG = P0213x-single (one GPU)' if 'SG' in made else '; no SG (no P0213x-single.json)'}"
            + ("" if getattr(a, "no_sha", False) else f"; engine {P_SHA}, stock = its SHA256 file")
            if not bad else "CONFIG CHECK FAILED: " + "; ".join(bad))
    print(line)
    gate(a, "FAIL" if bad else "PASS", line[:300])
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("make")
    p.add_argument("outdir")
    p.add_argument("--log-dir", required=True)
    for p in (p, sp.add_parser("check")):
        if p.prog.endswith("check"):
            p.add_argument("outdir")
        p.add_argument("--no-sha", action="store_true")
        p.add_argument("--gate")
        p.add_argument("--gates")
    sp.add_parser("single").add_argument("--out")
    sp.add_parser("singlecheck").add_argument("path", nargs="?")
    a = ap.parse_args()
    return {"make": cmd_make, "check": cmd_check, "single": cmd_single, "singlecheck": cmd_singlecheck}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
