#!/usr/bin/env python3
"""d12.py - 2026-11-08: the rules, decisions and reports of the DeepSeek gaps D1 and D2 (results/ds41/GAP-C234-PLAN.md; Karl's
decisions of 11-07 and 11-08 in its sections 4 and 6, fixed before D1 runs). Written at the desk 11-08. No GPU, no engine,
no network, no service: it reads result files and writes into the run folder it is given (and, at D1's end only,
results/ds41/d1-latest.txt). gap-d1.sh / gap-d2.sh call it; `selftest` uses synthetic data plus read-only looks at the
stored 11-04 / 11-07 results as known cases. All paths are absolute (the gap scripts run as snapshot copies elsewhere).

D1 (gap-d1.sh)
  d12.py d1-rule OUTDIR            the D1 rule -> OUTDIR/rule-d1.txt (written before the gap opens)
  d12.py d1-derive OUTDIR          configs/DS41-gate-C2.json must equal the config the 11-07 C2 arm ran
                                   (results/ds41/gate-1107-1152-ctie/C2/config.json); cfg-C3 / cfg-C4 = it with
                                   --dspark-block 3 / 4 and their own slot folders; cfg-CL = it with its own slot folder.
                                   Exit 0, 1 = refuse
  d12.py d1-decide OUTDIR          OUTDIR/C2, C3, C4 (tunearm.sh arm folders, linked), kl-c/, CL -> the winner by the
                                   fixed rule, KL / CL verdicts, per-arm speed and acceptance -> decision-d1.json, d1.md
  d12.py d1-finish OUTDIR EXIT     the gap's exit recorded in decision-d1.json; EXIT 0: OUTDIR -> results/ds41/d1-latest.txt
D2 (gap-d2.sh)
  d12.py d2-check-d1               the D1 run D2 may use: prints its folder (exit 0) or why not (exit 1): d1-latest.txt
                                   missing, not the D1 run d1-current.txt names (a newer D1 started), older than it, the
                                   run not finished (exit != 0), no winner, or the winner's config changed since
  d12.py d2-rule OUTDIR            rule.txt (sampled.py's rule, refused unless = C-SAMPLED-TEST-PLAN.md 2.5's text),
                                   rule-1108.txt (GAP-C234-PLAN.md 6's fixed rules, verbatim), think-rule.txt, rule-probe.txt
  d12.py d2-derive OUTDIR D1DIR    cfg-R1 (C0), cfg-X (D1's winner), cfg-R2 (C0, --vram-experts 0.98), cfg-TR1 (C0),
                                   cfg-TX (the winner), cfg-P1017 (C2 with the October pack: unsloth's 1017 drafter); each
                                   = its source but for its own slot folder (and R2's / P1017's stated change)
  d12.py d2-probe OUTDIR D1DIR     the 1017-drafter probe (DRAFTER-PROPOSAL-1107.md section 5 + Karl 11-07) -> probe.json,
                                   probe.md. Exit 0 a verdict, 2 none
  d12.py d2-report OUTDIR D1DIR    d2.md, d2-result.json (the main verdict, the thinking-on INFO, the probe, D1's KL / CL)
  d12.py selftest [DIR]            DIR under work/ds41/gate/scratch-d12 (default scratch-d12/d12-selftest)
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time

SC = "/home/USER/ai-speed-testing/strata-compare"
G = f"{SC}/work/ds41/gate"
RES = f"{SC}/results/ds41"
LATEST = f"{RES}/d1-latest.txt"
CURRENT = f"{RES}/d1-current.txt"
SCRATCH = f"{G}/scratch-d12"
CFGS = f"{SC}/configs"
C2CFG, C0CFG, ACFG = f"{CFGS}/DS41-gate-C2.json", f"{CFGS}/DS41-gate-C0.json", f"{CFGS}/DS41-gate-A.json"
REF_RUN = f"{RES}/gate-1107-1152-ctie"                         # the 11-07 gate (C0 / C1 / C2 under sampling)
SLOTS = f"{SC}/logs/ds41/gate-slots"
PROF = f"{SC}/logs/ds41/gate/profile-arm.bin"
DAILY_SLOTS, DAILY_PROF = f"{SC}/logs/ds41/ds4-slots", f"{SC}/logs/ds41/daily-profile.bin"
GATE_LOG = f"{SC}/logs/ds41/engine-DS41-v024.log"
M = f"{SC}/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF"
DPACK, NPACK = f"{M}/pack-ist-das-2.00bpw", f"{M}/pack-ist-das-2.00bpw-lucebox-q2k"
PLAN = f"{RES}/GAP-C234-PLAN.md"
SPLAN = f"{RES}/C-SAMPLED-TEST-PLAN.md"
DPROP = f"{RES}/DRAFTER-PROPOSAL-1107.md"
ARMS = ("C2", "C3", "C4")
BLOCK = {"C2": 2, "C3": 3, "C4": 4}
DECODE_MIN, PROMPT_MIN = 3.0, 5.0       # compare.py: a decode gain counts at >= 3 % beyond the noise, a prompt loss at 5 %
FEW_MIB, FEW_RSS_MB = 64, 256           # "a few MB": the winner's start lines vs C2's (report only)
PROBE_POINTS = 2.0                      # DRAFTER-PROPOSAL-1107.md 5: position 1 >= 2 points above C2's
VRAM_R2 = 0.98                          # Karl 11-04's Aa variant, applied to C0 (C-SAMPLED-TEST-PLAN.md 2.1)
SLOTNAME = {"R1": "csR1", "X": "csX", "R2": "csR2", "TR1": "csTR1", "TX": "csTX", "P1017": "probe1017",
            "C2": "C2", "C3": "C3", "C4": "C4", "CL": "CL"}

D1_RULE = """D1 rule (work/ds41/gate/d12.py), fixed 2026-11-08 at the desk, before the gap (Karl 11-07, GAP-C234-PLAN.md sections 2
and 4: "D1: C2, C3 and C4, plus the KL check and the long-prompt memory arms ... The winner is picked by the existing
>=3%-beyond-noise rule")
arms: C2 = configs/DS41-gate-C2.json (C2's 11-07 config, checked equal to the config the 11-07 C2 arm ran); C3 / C4 = it
with --dspark-block 3 / 4, nothing else changed but the arm's own slot folder. Each arm: gate.sh's speed step as on 11-07
(tunearm.sh + gate_speed.py: 3 passes of W1-W3, 3 x P4K, 3 x P20K; a fresh copy of the gap's profile snapshot).
numbers (summ.py's arm.json, compare.py's rule): decode = the mean of W1-W3 over the passes, its spread = half the range of
the pass means in % of the mean; P4K / P20K = the mean of the 3 prompts, spread = half their range; a pair's noise = the
larger of the two spreads.
"beats": decode gain - noise >= 3 % and neither P4K nor P20K lower by >= 5 % beyond its noise (compare.py's keep rule,
its decode branch: GAP-C234-PLAN.md 2 names only that branch).
winner: start at C2; C3 replaces it iff C3 beats C2; then C4 replaces the arm kept so far iff C4 beats it. Not beating
(a tie) keeps the arm with fewer drafts.
clean numbers (else an arm cannot win or replace; compare.py drops such a run): arm.json with >= 6 W answers and P4K / P20K
means; no GUARD / SOFTSTOP; and, as checks that the arm is C-N at all: 6 experts a word, the drafter loaded (no "DSpark not
loaded") and drafts offered in W1-W3, all 40 trunk layers on CUDA1 ("CUDA1 layers [0, 39]"), the config's --dspark on and
--dspark-block N. No winner when C2 has no clean numbers, or when C3 or C4 did not run at all (deadline, kernel check):
the rule cannot be finished.
KL (kl_c.py): C0's placement teacher-forced on the 11-03 KL harness vs A, Karl's 11-04 band from Aa / Ab (reused): PASS iff
changed top-1 picks <= the band's AND NLL distance <= the band's.
CL (the AL / BL rule, bl_verdict.py's): C2's config with everything up: PASS iff L64 and L97 both answered, no guard / soft
stop / swap failure, and the arm's lowest MemAvailable >= 14 GB. The winner's start lines vs C2's are reported (CL covers
the winner when they differ by a few MB: <= 64 MiB free VRAM per card and <= 256 MB engine RSS at ready - report only).
KL and CL do not pick the winner and do not block D2; both are daily conditions for C (Karl 11-07), reported.
Acceptance per arm (report only): per draft position kept / reached, all drafts kept / offered, verify rounds (= position
1 reached) and tokens per verify round = (kept + rounds) / rounds, over W1-W3 (3 passes) and over all requests."""

PROBE_RULE = """1017-drafter probe rule (work/ds41/gate/d12.py), fixed 2026-11-08 at the desk before the gap, from DRAFTER-PROPOSAL-1107.md
section 5 ("Rule, fixed now: build the Q2_K requant (then gate it as its own arm) only if its position-1 rate beats C2's by
>= 2 points. Otherwise close the idea.") and Karl 11-07 ("Don't build the 1017 Q2_K drafter unless the probe shows clearly
better acceptance than the current one"; GAP-C234-PLAN.md 4: "the probe's position-1 keep rate at least 2 points above
C2's in the same placement (W1-W3)").
arm: C2's config (configs/DS41-gate-C2.json) with the October pack pack-ist-das-2.00bpw (file 5 = unsloth's
dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf, its MXFP4-Q8 1017 drafter unchanged) and its tokenizer, its own slot folder;
W1-W3, one pass (gate_speed.py PASSES 1, NPROMPT 0); its speed is not judged.
rule: p1 = position 1 kept / reached over W1-W3; BUILD PROPOSED iff p1(probe) - p1(C2) >= 2.0 points, C2 = D1's C2 arm (W1-W3,
3 passes, the same placement and engine); else CLOSED (the 1017 requant idea is closed). No verdict if the probe's W1, W2
and W3 were not all answered, or its drafter did not load or offered no drafts, or D1 has no C2 acceptance. Nothing is
built either way: BUILD PROPOSED is a proposal to Karl."""


# ------------------------------------------------------------------------------------------------ small helpers
def js(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None


def jl(p):
    out = []
    if os.path.exists(p):
        for line in open(p, errors="replace"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def wjson(p, obj):
    tmp = p + ".part"
    json.dump(obj, open(tmp, "w"), indent=1)
    os.replace(tmp, p)


def wtext(p, txt):
    tmp = p + ".part"
    open(tmp, "w").write(txt)
    os.replace(tmp, p)


def args_map(a):
    m, i = {}, 0
    while i < len(a):
        k = a[i]
        if i + 1 < len(a) and not str(a[i + 1]).startswith("--"):
            m[k] = str(a[i + 1]); i += 2
        else:
            m[k] = True; i += 1
    return m


def set_arg(a, k, v):
    if k in a:
        a[a.index(k) + 1] = str(v)
    else:
        a += [k, str(v)]


def cfg_diff(a, b):
    """the differences between two configs (the comment left out): top-level keys, env keys and args by flag"""
    out = []
    for k in sorted(set(a) | set(b)):
        if k in ("_comment",):
            continue
        if k == "env":
            ea, eb = a.get("env") or {}, b.get("env") or {}
            out += [f"env {x}" for x in sorted(set(ea) | set(eb)) if ea.get(x) != eb.get(x)]
        elif k == "args":
            ma, mb = args_map(a.get("args") or []), args_map(b.get("args") or [])
            out += [f"args {x}" for x in sorted(set(ma) | set(mb)) if ma.get(x) != mb.get(x)]
            if not out and a.get("args") != b.get("args") and ma == mb:
                out.append("args order")
        elif a.get(k) != b.get(k):
            out.append(k)
    return out


def safety(c, slot):
    """a derived test config must never touch the daily profile, slot folder or log"""
    bad = []
    a = args_map(c.get("args") or [])
    if a.get("--expert-profile") != PROF:
        bad.append(f"--expert-profile is {a.get('--expert-profile')}, not the gate's copy {PROF}")
    sd = (c.get("env") or {}).get("STRATA_DS4_SLOT_DIR")
    if sd != f"{SLOTS}/{slot}" or sd == DAILY_SLOTS:
        bad.append(f"STRATA_DS4_SLOT_DIR is {sd}, not {SLOTS}/{slot}")
    if c.get("log") != GATE_LOG:
        bad.append(f"log is {c.get('log')}, not the test log")
    if DAILY_PROF in json.dumps(c.get("args")):
        bad.append("the daily profile appears in the args")
    return bad


def derive_cfg(src, dst, role, sets=None, top=None, note=""):
    c = json.load(open(src))
    c["env"]["STRATA_DS4_SLOT_DIR"] = f"{SLOTS}/{SLOTNAME[role]}"
    for k, v in (sets or {}).items():
        set_arg(c["args"], k, v)
    for k, v in (top or {}).items():
        c[k] = v
    c["_comment"] = f"d12.py ({time.strftime('%F')}) {role}: {src}{note}; own slot folder. " + c.get("_comment", "")[:300]
    wjson(dst, c)
    return c


# ------------------------------------------------------------------------------------------------ arm folders
CARD = re.compile(r"CUDA(\d) layers \[([\d, ]+)\][^:]*: weights ([\d.]+) GB, experts ([\d.]+) GB \((\d+) of (\d+) in VRAM\)"
                  r"(?:, caches ([\d.]+) GB)?, (\d+) MiB free")
READY = re.compile(r"ready after (\d+) s: MemAvailable ([\d.]+) GB, engine RSS (\d+) MB; vram (.*)$", re.M)


def acceptance(rows):
    """rows: gate_speed / sampled_client "drafts" records ({kept, offered, per_pos [[p, k, n]]}) -> per position and overall"""
    t = {"kept": 0, "offered": 0, "pos": {}}
    for r in rows:
        t["kept"] += int(r.get("kept") or 0); t["offered"] += int(r.get("offered") or 0)
        for p, k, n in r.get("per_pos") or []:
            x = t["pos"].setdefault(int(p), [0, 0]); x[0] += int(k); x[1] += int(n)
    rounds = t["pos"].get(1, [0, 0])[1]
    out = {"kept": t["kept"], "offered": t["offered"], "rounds": rounds,
           "kept_pct": round(100 * t["kept"] / t["offered"], 2) if t["offered"] else None,
           "tokens_per_verify_round": round((t["kept"] + rounds) / rounds, 3) if rounds else None,
           "positions": {str(p): {"kept": k, "reached": n, "pct": round(100 * k / n, 2) if n else None}
                         for p, (k, n) in sorted(t["pos"].items())}}
    return out


def arm_info(o, n):
    d = f"{o}/{n}"
    if not os.path.lexists(d):
        return {"ran": False, "name": n}
    rd = os.path.realpath(d)
    a = {"ran": True, "name": n, "dir": rd, "arm": js(f"{rd}/arm.json") or {}, "config": js(f"{rd}/config.json") or {}}
    a["disk"] = jl(f"{rd}/disk.jsonl")
    stl = open(f"{rd}/engine-start.log", errors="replace").read() if os.path.exists(f"{rd}/engine-start.log") else ""
    summ = open(f"{rd}/summary.txt", errors="replace").read() if os.path.exists(f"{rd}/summary.txt") else ""
    m = re.search(r"experts per word: (\d+)", stl)
    a["experts_per_word"] = int(m.group(1)) if m else None
    a["dspark_not_loaded"] = "DSpark not loaded" in stl
    a["trunk_on_cuda1"] = bool(re.search(r"CUDA1 layers \[0, 39\]", stl))
    a["placement"] = [x.strip()[:200] for x in stl.splitlines() if re.search(r"CUDA\d layers|routed experts on the CPU lane|DSpark", x)][:6]
    a["cards"] = [{"dev": int(c[0]), "layers": c[1].replace(" ", ""), "vram_experts": int(c[4]), "of": int(c[5]),
                   "free_mib": int(c[7])} for c in CARD.findall(stl)]
    r = READY.search(summ)
    a["ready"] = {"s": int(r.group(1)), "memavail_gb": float(r.group(2)), "rss_mb": int(r.group(3)), "vram": r.group(4).strip()} if r else None
    a["stops"] = {k: open(f"{rd}/{k}", errors="replace").read().strip()[:200] for k in ("GUARD", "SOFTSTOP") if os.path.exists(f"{rd}/{k}")}
    w = [x for x in a["disk"] if str(x.get("id", ""))[:2] in ("W1", "W2", "W3")]
    a["acc_w"] = acceptance([r for x in w for r in (x.get("engine") or {}).get("drafts", [])])
    a["acc_all"] = acceptance([r for x in a["disk"] for r in (x.get("engine") or {}).get("drafts", [])])
    a["w_answered"] = sorted({str(x["id"])[:2] for x in w if not x.get("error") and x.get("completion_tokens")})
    return a


def clean(a, n):
    """-> (ok, why): compare.py's "no clean numbers" plus the checks that the arm is C-N (the D1 rule)"""
    why = []
    if not a.get("ran"):
        return False, ["did not run"]
    x = a["arm"]
    dec = x.get("decode") or {}
    if not dec or (dec.get("n") or 0) < 6:
        why.append(f"{dec.get('n', 0)} W answers (< 6)")
    for k in ("P4K", "P20K"):
        if not (x.get(k) or {}).get("mean"):
            why.append(f"no {k} numbers")
    why += [f"{k}: {v[:80]}" for k, v in a["stops"].items()]
    if a["experts_per_word"] != 6:
        why.append(f"experts per word {a['experts_per_word']} (6 pinned)")
    if a["dspark_not_loaded"]:
        why.append("DSpark not loaded")
    if not a["acc_w"]["offered"]:
        why.append("no drafts offered in W1-W3")
    if not a["trunk_on_cuda1"]:
        why.append("no 'CUDA1 layers [0, 39]' start line")
    am = args_map((a.get("config") or {}).get("args") or [])
    if am.get("--dspark") != "on" or am.get("--dspark-block") != str(BLOCK.get(n, -1)):
        why.append(f"its config runs --dspark {am.get('--dspark')} --dspark-block {am.get('--dspark-block')} (want on / {BLOCK.get(n)})")
    return not why, why


def gain(ref, new, key):
    """report.py's gain(): new against ref -> (gain %, noise %) or None"""
    x, y = (ref or {}).get(key), (new or {}).get(key)
    if not x or not y or not x.get("mean"):
        return None
    return round(100 * (y["mean"] / x["mean"] - 1), 2), round(max(x.get("spread_pct") or 0, y.get("spread_pct") or 0), 2)


def beats(ref, new):
    """the D1 rule's "beats" (compare.py's keep rule, decode branch): -> (bool, detail)"""
    d = gain(ref, new, "decode")
    pr = {k: gain(ref, new, k) for k in ("P4K", "P20K")}
    down = [k for k, v in pr.items() if v and -v[0] - v[1] >= PROMPT_MIN]
    up = bool(d) and d[0] - d[1] >= DECODE_MIN
    return (up and not down), {"decode": d, "P4K": pr["P4K"], "P20K": pr["P20K"], "decode_beyond_noise": round(d[0] - d[1], 2) if d else None,
                               "prompt_lower_beyond_noise": down}


def compare_verdict(ref, new):
    """report.py's verdict() string (compare.py's whole keep rule), for the report"""
    d, p4, p20 = gain(ref, new, "decode"), gain(ref, new, "P4K"), gain(ref, new, "P20K")
    if not d:
        return "no numbers"
    up = [k for k, v in (("P4K", p4), ("P20K", p20)) if v and v[0] - v[1] >= 5]
    down = [k for k, v in (("P4K", p4), ("P20K", p20)) if v and -v[0] - v[1] >= 5]
    if d[0] - d[1] >= 3 and not down:
        return "decode gain beyond noise"
    if up and not (-d[0] - d[1] > 0):
        return f"prompt gain beyond noise ({', '.join(up)}), decode not lower beyond noise"
    if -d[0] - d[1] >= 3:
        return "decode loss beyond noise"
    if down:
        return f"prompt loss beyond noise ({', '.join(down)})"
    return "trade-off: prompt up, decode down" if up else "no gain beyond noise"


def pick(infos):
    """the D1 rule's winner: -> (winner or None, steps, why)"""
    cl = {n: clean(infos[n], n) for n in ARMS}
    steps = []
    if not infos["C2"].get("ran"):
        return None, steps, ["C2 did not run: no winner"]
    if not cl["C2"][0]:
        return None, steps, ["C2 has no clean numbers (" + "; ".join(cl["C2"][1]) + "): no winner"]
    missing = [n for n in ("C3", "C4") if not infos[n].get("ran")]
    if missing:
        return None, steps, [f"{', '.join(missing)} did not run (deadline or kernel check): the rule cannot be finished, no winner"]
    kept, why = "C2", []
    for n in ("C3", "C4"):
        if not cl[n][0]:
            steps.append({"step": f"{n} vs {kept}", "replaces": False, "why": "no clean numbers: " + "; ".join(cl[n][1])})
            why.append(f"{n} cannot replace {kept}: no clean numbers")
            continue
        b, det = beats(infos[kept]["arm"], infos[n]["arm"])
        steps.append(dict(det, step=f"{n} vs {kept}", replaces=b, compare_py=compare_verdict(infos[kept]["arm"], infos[n]["arm"])))
        why.append(f"{n} vs {kept}: decode {det['decode']} (gain %, noise %) -> beyond noise {det['decode_beyond_noise']}; "
                   f"prompts lower beyond noise {det['prompt_lower_beyond_noise'] or 'none'} -> " +
                   (f"{n} replaces {kept}" if b else f"{kept} kept (fewer drafts)"))
        if b:
            kept = n
    return kept, steps, why


def cl_verdict(d):
    """bl_verdict.py's rule on an arm folder: -> dict (pass, lowest_gb, answered, stops, lines)"""
    if not d or not os.path.exists(d):
        return {"verdict": "NOT RUN", "pass": None}
    d = os.path.realpath(d)
    lj = js(f"{d}/long.json")
    if lj is None:
        return {"verdict": "FAIL", "pass": False, "why": "no long.json", "dir": d,
                "stops": [k for k in ("GUARD", "SOFTSTOP") if os.path.exists(f"{d}/{k}")]}
    lows = [p["memavail_low_gb"] for p in lj if p.get("memavail_low_gb") is not None]
    a = js(f"{d}/arm.json") or {}
    if a.get("lowest_memavail_gb") is not None:
        lows.append(a["lowest_memavail_gb"])
    done = {p["id"] for p in lj if not p.get("error") and p.get("completion_tokens")}
    stops = [k for k in ("GUARD", "SOFTSTOP") if os.path.exists(f"{d}/{k}")]
    low = min(lows) if lows else None
    ok = done >= {"L64", "L97"} and not stops and low is not None and low >= 14.0
    return {"verdict": "PASS" if ok else "FAIL", "pass": ok, "dir": d, "lowest_gb": low, "answered": sorted(done), "stops": stops,
            "stop_text": {k: open(f"{d}/{k}", errors="replace").read().strip()[:200] for k in stops},
            "lines": {str(t): low is not None and low >= t for t in (14, 13, 12)},
            "per_prompt": {p["id"]: {"tokens": p.get("prompt_tokens"), "before_gb": p.get("memavail_before_gb"),
                                     "low_gb": p.get("memavail_low_gb"), "read_tps": p.get("read_tps_engine"),
                                     "error": p.get("error")} for p in lj}}


def kl_read(o):
    k = js(f"{o}/kl-c/kl-c-result.json")
    if k:
        return {"verdict": k.get("verdict"), "pass": k.get("pass"), "top1_changed": k["vs_A"]["top1_changed"],
                "nll_distance": k["vs_A"]["nll_distance"], "band": k.get("band"), "kl_mean": k["vs_A"].get("kl_mean"),
                "kl_p90": k["vs_A"].get("kl_p90"), "kl_gt1": k["vs_A"].get("kl_gt1"), "placement": k.get("placement"),
                "time": k.get("time")}
    return {"verdict": "NO VERDICT" if os.path.exists(f"{o}/kl-c-run.out") else "NOT RUN", "pass": None}


def start_compare(w, c2):
    """the winner's start lines vs C2's: free MiB per card and the engine RSS at ready"""
    if not w.get("ran") or not c2.get("ran"):
        return {"checked": False}
    fw = {c["dev"]: c["free_mib"] for c in w["cards"]}
    f2 = {c["dev"]: c["free_mib"] for c in c2["cards"]}
    dfree = {str(k): fw.get(k, 0) - f2.get(k, 0) for k in sorted(set(fw) | set(f2))}
    drss = (w["ready"]["rss_mb"] - c2["ready"]["rss_mb"]) if w.get("ready") and c2.get("ready") else None
    few = bool(dfree) and all(abs(v) <= FEW_MIB for v in dfree.values()) and drss is not None and abs(drss) <= FEW_RSS_MB
    return {"checked": True, "free_mib_delta": dfree, "ready_rss_mb_delta": drss, "within_a_few_mb": few,
            "winner_ready": w.get("ready"), "c2_ready": c2.get("ready")}


def speed_row(a):
    x = a.get("arm") or {}
    d = x.get("decode") or {}
    return {"decode": {k: d.get(k) for k in ("mean", "spread_pct", "pass_means", "n")},
            "P4K": {k: (x.get("P4K") or {}).get(k) for k in ("mean", "spread_pct", "tps")},
            "P20K": {k: (x.get("P20K") or {}).get(k) for k in ("mean", "spread_pct", "tps")},
            "disk_gb_per_token": x.get("disk_gb_per_token"), "lowest_memavail_gb": x.get("lowest_memavail_gb"),
            "peak_rss_mb": x.get("peak_rss_mb"), "peak_vram_mib": x.get("peak_vram_mib")}


# ------------------------------------------------------------------------------------------------ D1
def d1_rule(o):
    os.makedirs(o, exist_ok=True)
    wtext(f"{o}/rule-d1.txt", D1_RULE + "\n")
    print(D1_RULE)
    return 0


def d1_derive(o, c2src=C2CFG, ref_cfg=None):
    os.makedirs(o, exist_ok=True)
    ref_cfg = ref_cfg or f"{os.path.realpath(f'{REF_RUN}/C2')}/config.json"
    bad = []
    c2, ref = js(c2src), js(ref_cfg)
    if c2 is None or ref is None:
        print(f"d1-derive: cannot read {c2src} or {ref_cfg}"); return 1
    if c2 != ref:
        bad.append(f"{c2src} is not the config the 11-07 C2 arm ran ({ref_cfg}): differs in {cfg_diff(c2, ref) or ['the comment']}")
    bad += [f"C2: {b}" for b in safety(c2, "C2")]
    am = args_map(c2["args"])
    if am.get("--dspark") != "on" or am.get("--dspark-block") != "2":
        bad.append(f"C2 runs --dspark {am.get('--dspark')} --dspark-block {am.get('--dspark-block')}")
    out = {"C2": {"config": c2src, "sha256": sha256(c2src), "diff_vs_C2": []}}
    for role, sets in (("C3", {"--dspark-block": 3}), ("C4", {"--dspark-block": 4}), ("CL", {})):
        dst = f"{o}/cfg-{role}.json"
        c = derive_cfg(c2src, dst, role, sets, note=(f" with --dspark-block {sets['--dspark-block']}" if sets else " (the long prompts)"))
        diff = cfg_diff(c, c2)
        want = (["args --dspark-block"] if sets else []) + ["env STRATA_DS4_SLOT_DIR"]
        if sorted(diff) != sorted(want):
            bad.append(f"cfg-{role} differs from C2 in {diff} (want {want})")
        bad += [f"{role}: {b}" for b in safety(c, role)]
        out[role] = {"config": dst, "sha256": sha256(dst), "diff_vs_C2": diff}
    wjson(f"{o}/derive-d1.json", {"configs": out, "problems": bad})
    for role, v in out.items():
        print(f"{role}: {v['config']} (sha256 {v['sha256'][:16]}; vs C2: {v['diff_vs_C2'] or 'the same file'})")
    print("d1-derive: " + ("OK" if not bad else "REFUSED - " + " | ".join(bad)))
    return 0 if not bad else 1


def d1_decide(o):
    st = js(f"{o}/started.json") or {}
    infos = {n: arm_info(o, n) for n in ARMS}
    winner, steps, why = pick(infos)
    dv = js(f"{o}/derive-d1.json") or {}
    cfgs = (dv.get("configs") or {})
    wcfg = (cfgs.get(winner) or {}).get("config") if winner else None
    kl = kl_read(o)
    cl = cl_verdict(f"{o}/CL" if os.path.lexists(f"{o}/CL") else None)
    cl["config"] = "C2's (cfg-CL.json = DS41-gate-C2.json + its own slot folder)"
    sc = start_compare(infos[winner], infos["C2"]) if winner else {"checked": False}
    if winner == "C2":
        sc = {"checked": True, "within_a_few_mb": True, "note": "the winner is C2: CL ran on its own config"}
    ref2 = arm_info(os.path.dirname(f"{REF_RUN}/C2"), "C2")
    D = {"version": 1, "run": os.path.realpath(o), "run_started_epoch": st.get("epoch"), "run_started": st.get("iso"),
         "written": time.strftime("%F %T"), "complete": False, "exit": None,
         "winner": winner, "winner_config": wcfg, "winner_config_sha256": (cfgs.get(winner) or {}).get("sha256") if winner else None,
         "winner_why": why, "steps": steps, "rule_file": f"{os.path.realpath(o)}/rule-d1.txt",
         "arms": {}, "kl": kl, "cl": cl, "cl_start_lines_vs_winner": sc,
         "reference_1107_C2": {"dir": ref2.get("dir"), "decode": speed_row(ref2)["decode"] if ref2.get("ran") else None,
                               "acceptance_w1w3": ref2.get("acc_w")}}
    for n in ARMS:
        a = infos[n]
        ok, w = clean(a, n)
        D["arms"][n] = {"ran": a.get("ran", False), "dir": a.get("dir"), "config": (cfgs.get(n) or {}).get("config"),
                        "clean": ok, "why_not_clean": w}
        if a.get("ran"):
            D["arms"][n].update(speed=speed_row(a), acceptance_w1w3=a["acc_w"], acceptance_all=a["acc_all"], cards=a["cards"],
                                ready=a["ready"], stops=a["stops"], experts_per_word=a["experts_per_word"], placement=a["placement"])
    wjson(f"{o}/decision-d1.json", D)
    wtext(f"{o}/d1.md", d1_md(D))
    print(f"D1 winner: {winner} ({'; '.join(why)}); KL {kl['verdict']}; CL {cl['verdict']}")
    return 0


def acc_cells(t, nmax):
    pos = t.get("positions") or {}
    cells = []
    for p in range(1, nmax + 1):
        x = pos.get(str(p))
        cells.append(f"{x['kept']} / {x['reached']} = {x['pct']} %" if x and x["reached"] else "-")
    return cells


def d1_md(D):
    L = ["# DeepSeek gap D1: C2 / C3 / C4, C's KL check, C's long-prompt arm", "",
         f"Run folder: `{D['run']}`. Rule: rule-d1.txt (fixed before the gap). Written {D['written']}.", "",
         f"**Winner: {D['winner'] or 'none'}**" + (f" (`{D['winner_config']}`)" if D["winner"] else ""), ""]
    L += [f"- {w}" for w in D["winner_why"]]
    L += ["", "## Speed (3 passes; spread = half the range, % of the mean)", "",
          "| arm | decode tok/s (spread; pass means) | P4K (spread) | P20K (spread) | SSD GB / token | lowest MemAvailable | clean |",
          "|---|---|---|---|---|---|---|"]
    for n in ARMS:
        a = D["arms"][n]
        if not a["ran"]:
            L.append(f"| {n} | did not run | | | | | no |"); continue
        s = a["speed"]
        L.append(f"| {n} | {s['decode']['mean']} ({s['decode']['spread_pct']} %; {s['decode']['pass_means']}) | {s['P4K']['mean']} "
                 f"({s['P4K']['spread_pct']} %) | {s['P20K']['mean']} ({s['P20K']['spread_pct']} %) | {s['disk_gb_per_token']} | "
                 f"{s['lowest_memavail_gb']} | {'yes' if a['clean'] else 'NO: ' + '; '.join(a['why_not_clean'])[:120]} |")
    r = D.get("reference_1107_C2") or {}
    if r.get("decode"):
        L.append(f"| 11-07 C2 (reference only) | {r['decode']['mean']} ({r['decode']['spread_pct']} %; {r['decode']['pass_means']}) | | | | | |")
    L += ["", "Rule steps (compare.py's rule, decode branch; ties to fewer drafts):", ""]
    for s in D["steps"]:
        L.append(f"- {s['step']}: " + (s.get("why") or f"decode {s['decode']} (gain, noise) -> {s['decode_beyond_noise']} beyond noise; "
                                       f"P4K {s['P4K']}, P20K {s['P20K']}; lower beyond noise: {s['prompt_lower_beyond_noise'] or 'none'} "
                                       f"-> {'REPLACES' if s['replaces'] else 'does not replace'} (compare.py: {s['compare_py']})"))
    nmax = 4
    L += ["", "## The drafter's acceptance per draft position (kept / reached)", "",
          "| arm | requests | position 1 | position 2 | position 3 | position 4 | all drafts kept / offered | verify rounds | "
          "tokens a verify round |", "|---|---|---|---|---|---|---|---|---|"]
    for n in ARMS:
        a = D["arms"][n]
        if not a["ran"]:
            continue
        for lab, t in (("W1-W3, 3 passes", a["acceptance_w1w3"]), ("all requests", a["acceptance_all"])):
            L.append(f"| {n} | {lab} | " + " | ".join(acc_cells(t, nmax)) + f" | {t['kept']} / {t['offered']} ({t['kept_pct']} %) | "
                     f"{t['rounds']} | {t['tokens_per_verify_round']} |")
    if r.get("acceptance_w1w3"):
        t = r["acceptance_w1w3"]
        L.append("| 11-07 C2 (reference) | W1-W3, 3 passes | " + " | ".join(acc_cells(t, nmax)) +
                 f" | {t['kept']} / {t['offered']} ({t['kept_pct']} %) | {t['rounds']} | {t['tokens_per_verify_round']} |")
    k = D["kl"]
    L += ["", "## C's trunk KL check vs A (Karl's 11-04 noise band; kl_c.py)", "",
          f"- **{k['verdict']}**" + (f": changed top-1 picks {k['top1_changed']} (band {k['band']['top1']}), NLL distance "
                                      f"{k['nll_distance']:.5f} (band {k['band']['nll']:.5f}); KL mean {k['kl_mean']:.5f}, p90 "
                                      f"{k['kl_p90']:.5f}, KL>1 {k['kl_gt1']}; {k.get('time')}" if k.get("band") else "")]
    c = D["cl"]
    L += ["", "## C's long-prompt memory arm CL (the AL / BL rule, on C2's config, everything up)", "",
          f"- **{c['verdict']}**" + (f": lowest MemAvailable {c.get('lowest_gb')} GB; answered {c.get('answered')}; stops "
                                      f"{c.get('stops') or 'none'}; 14 / 13 / 12 GB lines {c.get('lines')}" if c.get("dir") else "")]
    for pid, p in (c.get("per_prompt") or {}).items():
        L.append(f"  - {pid}: {p['tokens']} tokens, MemAvailable before {p['before_gb']} / lowest {p['low_gb']} GB, read "
                 f"{p['read_tps']} tok/s" + (f", ERROR {str(p['error'])[:80]}" if p.get("error") else ""))
    sc = D["cl_start_lines_vs_winner"]
    if sc.get("checked"):
        L.append(f"- the winner's start lines vs C2's: " + (sc.get("note") or
                 f"free MiB per card {sc['free_mib_delta']}, engine RSS at ready {sc['ready_rss_mb_delta']} MB -> "
                 f"{'within a few MB: CL covers the winner' if sc['within_a_few_mb'] else 'MORE than a few MB: Karl decides whether CL on C2 covers the winner'}"))
    L += ["", "KL and CL are daily conditions for C (Karl 11-07); they do not pick the winner and do not block D2.", "",
          "## Placement (engine start lines)", ""]
    for n in ARMS:
        a = D["arms"][n]
        if a["ran"]:
            L.append(f"- {n} (`{a['dir']}`): " + " / ".join(a.get("placement") or []))
    return "\n".join(L) + "\n"


def d1_finish(o, rc, latest=LATEST):
    D = js(f"{o}/decision-d1.json")
    if D is None:
        print("d1-finish: no decision-d1.json"); return 1
    D["exit"] = int(rc)
    D["complete"] = int(rc) == 0
    D["finished"] = time.strftime("%F %T")
    wjson(f"{o}/decision-d1.json", D)
    if int(rc) == 0:
        wtext(latest, os.path.realpath(o) + "\n")
        print(f"d1-finish: exit 0 recorded; {latest} -> {os.path.realpath(o)}")
    else:
        print(f"d1-finish: exit {rc} recorded; {latest} NOT written (D2 will refuse)")
    return 0


# ------------------------------------------------------------------------------------------------ D2
def d2_check_d1(latest=LATEST, current=CURRENT):
    """-> (ok, folder, decision, why)"""
    if not os.path.exists(latest):
        return False, None, None, f"{latest} is missing (no finished D1 run)"
    lines = [x.strip() for x in open(latest).read().splitlines() if x.strip()]
    if len(lines) != 1 or not lines[0].startswith("/"):
        return False, None, None, f"{latest} is not one absolute path ({lines[:2]})"
    d = lines[0]
    if not os.path.isdir(d):
        return False, None, None, f"{latest} names {d}, which is not a folder"
    if not os.path.exists(current):
        return False, d, None, f"{current} is missing (D1 writes it first thing): cannot tell the current D1 run"
    cur = open(current).read().split()
    if len(cur) < 2:
        return False, d, None, f"{current} is not 'FOLDER EPOCH ...'"
    if os.path.realpath(cur[0]) != os.path.realpath(d):
        return False, d, None, (f"{latest} names {d}, but the current D1 run is {cur[0]} (started {cur[1]}): a newer D1 started "
                                "and did not finish")
    if os.path.getmtime(latest) < os.path.getmtime(current):
        return False, d, None, f"{latest} is older than {current} (the current D1 run)"
    D = js(f"{d}/decision-d1.json")
    if D is None:
        return False, d, None, f"{d}/decision-d1.json is missing or unreadable"
    if os.path.realpath(D.get("run") or "") != os.path.realpath(d) or str(D.get("run_started_epoch")) != cur[1]:
        return False, d, D, f"decision-d1.json's run / start ({D.get('run')}, {D.get('run_started_epoch')}) is not the current D1 run's"
    if not D.get("complete") or D.get("exit") != 0:
        return False, d, D, f"the D1 run did not finish cleanly (exit {D.get('exit')})"
    if D.get("winner") not in ARMS:
        return False, d, D, f"D1 has no winner ({'; '.join(D.get('winner_why') or [])})"
    wc = D.get("winner_config")
    if not wc or not os.path.exists(wc) or sha256(wc) != D.get("winner_config_sha256"):
        return False, d, D, f"the winner's config {wc} is missing or changed since D1 (sha256)"
    return True, d, D, "ok"


def plan_rule_block():
    t = open(SPLAN).read()
    sec = t[t.index("### 2.5"):]
    blk = sec[sec.index("```\n") + 4:]
    return blk[:blk.index("```")].rstrip("\n")


def plan_fixed_rules():
    t = open(PLAN).read()
    i = t.index("## 6. Karl's decisions on the sampled test")
    j = t.index("Fixed rules for D2", i)
    return t[i:].rstrip("\n"), t[j:].rstrip("\n")


def d2_rule(o):
    sys.path.insert(0, f"{G}/sampled")
    import sampled as SA
    os.makedirs(o, exist_ok=True)
    rt = SA.rule_text()
    if rt != plan_rule_block():
        print(f"d2-rule: sampled.py's rule is not C-SAMPLED-TEST-PLAN.md section 2.5's text - nothing written, refused")
        return 1
    whole, fixed = plan_fixed_rules()
    wtext(f"{o}/rule.txt", rt + "\n")
    wtext(f"{o}/rule-1108.txt", f"From {PLAN} (verbatim; Karl 11-08, fixed before D1 runs):\n\n{whole}\n")
    wtext(f"{o}/think-rule.txt", SA.think_rule_text() + "\n")
    wtext(f"{o}/rule-probe.txt", PROBE_RULE + "\n")
    print(rt + "\n\n" + fixed + "\n\n" + SA.think_rule_text() + "\n\n" + PROBE_RULE)
    return 0


def d2_derive(o, d1dir, D=None):
    D = D or js(f"{d1dir}/decision-d1.json")
    os.makedirs(o, exist_ok=True)
    bad, out = [], {}
    wsrc = D["winner_config"]
    plan = (("R1", C0CFG, {}, None, " (C0: C's placement, --dspark off)"),
            ("X", wsrc, {}, None, f" (D1's winner {D['winner']})"),
            ("R2", C0CFG, {"--vram-experts": VRAM_R2}, None, f" with --vram-experts {VRAM_R2} (Karl's 11-04 Aa variant on C0)"),
            ("TR1", C0CFG, {}, None, " (C0, the thinking-on arm)"),
            ("TX", wsrc, {}, None, f" (D1's winner {D['winner']}, the thinking-on arm)"),
            ("P1017", C2CFG, {"--pack": DPACK}, {"tokenizer": f"{DPACK}/tokenizer"},
             " with the October pack pack-ist-das-2.00bpw (unsloth's 1017 drafter) and its tokenizer: the probe"))
    want = {"R1": [], "X": [], "TR1": [], "TX": [], "R2": ["args --vram-experts"], "P1017": ["args --pack", "tokenizer"]}
    for role, src, sets, top, note in plan:
        dst = f"{o}/cfg-{role}.json"
        c = derive_cfg(src, dst, role, sets, top, note)
        diff = cfg_diff(c, json.load(open(src)))
        w = sorted(want[role] + ["env STRATA_DS4_SLOT_DIR"])
        if sorted(diff) != w:
            bad.append(f"cfg-{role} differs from {src} in {diff} (want {w})")
        bad += [f"{role}: {b}" for b in safety(c, SLOTNAME[role])]
        out[role] = {"config": dst, "source": src, "sha256": sha256(dst), "diff": diff, "slot": SLOTNAME[role]}
    am = args_map(json.load(open(wsrc))["args"])
    if am.get("--dspark") != "on" or am.get("--dspark-block") != str(BLOCK[D["winner"]]):
        bad.append(f"the winner's config runs --dspark {am.get('--dspark')} --dspark-block {am.get('--dspark-block')}")
    if args_map(json.load(open(C0CFG))["args"]).get("--dspark") != "off":
        bad.append("C0 does not run --dspark off")
    if not os.path.exists(f"{DPACK}/tokenizer"):
        bad.append(f"{DPACK}/tokenizer is missing")
    wjson(f"{o}/derive-d2.json", {"d1": d1dir, "winner": D["winner"], "configs": out, "problems": bad})
    for role, v in out.items():
        print(f"{role}: {v['config']} from {v['source']} (sha256 {v['sha256'][:16]}; changed: {v['diff']})")
    print("d2-derive: " + ("OK" if not bad else "REFUSED - " + " | ".join(bad)))
    return 0 if not bad else 1


def probe_verdict(p, c2acc):
    """-> (verdict, detail): the fixed probe rule"""
    why = []
    if not p.get("ran"):
        return "NO VERDICT", {"why": ["the probe did not run"]}
    if p["w_answered"] != ["W1", "W2", "W3"]:
        why.append(f"W1-W3 not all answered ({p['w_answered']})")
    if p["dspark_not_loaded"]:
        why.append("its drafter did not load (DSpark not loaded)")
    pp = (p["acc_w"]["positions"].get("1") or {})
    if not pp.get("reached"):
        why.append("no drafts offered in W1-W3")
    cp = ((c2acc or {}).get("positions") or {}).get("1") or {}
    if not cp.get("reached"):
        why.append("D1 has no C2 acceptance")
    det = {"probe_pos1": pp, "c2_pos1": cp, "probe_acceptance": p["acc_w"], "why": why}
    if why:
        return "NO VERDICT", det
    a, b = 100.0 * pp["kept"] / pp["reached"], 100.0 * cp["kept"] / cp["reached"]
    det["points"] = round(a - b, 3)
    det["se_points"] = round(100 * ((a / 100 * (1 - a / 100) / pp["reached"]) + (b / 100 * (1 - b / 100) / cp["reached"])) ** 0.5, 3)
    return ("BUILD PROPOSED" if a - b >= PROBE_POINTS else "CLOSED"), det


def d2_probe(o, d1dir):
    D = js(f"{d1dir}/decision-d1.json") or {}
    p = arm_info(o, "P1017")
    v, det = probe_verdict(p, ((D.get("arms") or {}).get("C2") or {}).get("acceptance_w1w3"))
    res = {"verdict": v, "rule_file": f"{os.path.realpath(o)}/rule-probe.txt", **det, "dir": p.get("dir"),
           "cards": p.get("cards"), "placement": p.get("placement"), "stops": p.get("stops"),
           "reference_1107_C2_pos1": (((D.get("reference_1107_C2") or {}).get("acceptance_w1w3") or {}).get("positions") or {}).get("1")}
    wjson(f"{o}/probe.json", res)
    L = [f"# The 1017-drafter acceptance probe: **{v}**", "", "Rule: rule-probe.txt (fixed before the gap). Nothing is built.", ""]
    if det.get("points") is not None:
        L.append(f"- position 1: probe {det['probe_pos1']['kept']} / {det['probe_pos1']['reached']} = "
                 f"{det['probe_pos1']['pct']} % vs D1's C2 {det['c2_pos1']['kept']} / {det['c2_pos1']['reached']} = {det['c2_pos1']['pct']} %: "
                 f"{det['points']:+.2f} points (needed >= +{PROBE_POINTS}; standard error of the difference ~{det['se_points']} points)")
    L += [f"- {w}" for w in det.get("why") or []]
    t = det.get("probe_acceptance") or p.get("acc_w") or {}
    if t.get("positions"):
        L.append("- the probe per position (W1-W3, 1 pass): " + "; ".join(f"{k}: {x['kept']} / {x['reached']} = {x['pct']} %"
                                                                       for k, x in t["positions"].items())
                 + f"; tokens a verify round {t.get('tokens_per_verify_round')}")
    L.append(f"- placement: {' / '.join(p.get('placement') or [])}")
    wtext(f"{o}/probe.md", "\n".join(L) + "\n")
    print("\n".join(L))
    return 0 if v != "NO VERDICT" else 2


def d2_report(o, d1dir):
    D = js(f"{d1dir}/decision-d1.json") or {}
    v = js(f"{o}/verdict.json")
    t = js(f"{o}/think/think.json")
    tskip = open(f"{o}/think-skipped.txt").read().strip() if os.path.exists(f"{o}/think-skipped.txt") else None
    pr = js(f"{o}/probe.json")
    main = (v or {}).get("verdict") or "NOT RUN"
    kl, cl = (D.get("kl") or {}).get("verdict"), (D.get("cl") or {}).get("verdict")
    ready = main == "PASS" and kl == "PASS" and cl == "PASS"
    R = {"written": time.strftime("%F %T"), "run": os.path.realpath(o), "d1": d1dir, "winner": D.get("winner"),
         "sampled_test": {"verdict": main, "why": (v or {}).get("why"), "d2_x_r1": (v or {}).get("d2_x_r1"),
                          "band": (v or {}).get("band"), "d2_r2_r1": (v or {}).get("d2_r2_r1"), "mde_top1": (v or {}).get("mde_top1")},
         "thinking_on_info": ({"result": t.get("result"), "why": t.get("why"), "d2_x_r1": t.get("d2_x_r1"), "mde_top1": t.get("mde_top1")}
                              if t else {"result": "SKIPPED" if tskip else "NOT RUN", "why": tskip}),
         "probe": {"verdict": (pr or {}).get("verdict", "NOT RUN"), "points": (pr or {}).get("points"), "why": (pr or {}).get("why")},
         "d1_kl": kl, "d1_cl": cl, "d1_cl_covers_winner": (D.get("cl_start_lines_vs_winner") or {}).get("within_a_few_mb"),
         "daily_conditions": {"sampled_test_pass": main == "PASS", "kl_pass": kl == "PASS", "cl_pass": cl == "PASS",
                              "karls_ok": "pending"},
         "proposal": (f"all three checks pass: propose C{BLOCK.get(D.get('winner'), '?')} as the DeepSeek daily config to Karl (no switch "
                      "without his OK)") if ready else "not every daily condition passed: A stays daily; the failing checks go to Karl"}
    wjson(f"{o}/d2-result.json", R)
    ti = R["thinking_on_info"]
    L = [f"# DeepSeek gap D2: the sampled-distribution test on D1's winner {D.get('winner')}", "",
         f"Run folder: `{R['run']}`; D1: `{d1dir}`. Rules: rule.txt, rule-1108.txt, think-rule.txt, rule-probe.txt (fixed before the gap).", "",
         f"- **The sampled-distribution test (the verdict): {main}**" + (f" - {'; '.join(v.get('why') or [])}" if v else ""),
         f"- thinking-on arm (INFO only, beside the result, never part of the verdict): {ti['result']}" +
         (f" - {'; '.join(ti['why']) if isinstance(ti['why'], list) else ti['why']}" if ti.get("why") else ""),
         f"- the 1017-drafter probe: **{R['probe']['verdict']}**" + (f" ({R['probe']['points']:+.2f} points at position 1)"
                                                                       if R["probe"]["points"] is not None else ""),
         f"- D1 (reported, not blocking): C's KL check {kl}; C's long-prompt arm CL {cl}"
         + ("" if R["d1_cl_covers_winner"] in (None, True) else " (on C2's config; the winner's start lines differ by more than a few MB)"),
         "", f"**Daily conditions for C** (Karl 11-03 / 11-07): sampled test {main}, KL {kl}, CL {cl}, Karl's OK pending -> {R['proposal']}."]
    wtext(f"{o}/d2.md", "\n".join(L) + "\n")
    print("\n".join(L))
    return 0


# ------------------------------------------------------------------------------------------------ selftest
def _arm(d, n, block, decode, spread, p4=(460.0, 4.0), p20=(813.0, 1.0), stops=(), epw=6, loaded=True, drafts=True,
         trunk=True, wn=9, pos=((7000, 8500), (4500, 5200), (3000, 3500), (2000, 2300)), free=(1144, 572), rss=58232, cfg=None):
    os.makedirs(d, exist_ok=True)
    a = {"decode": {"mean": decode, "spread_pct": spread, "pass_means": [decode] * 3, "n": wn},
         "P4K": {"mean": p4[0], "spread_pct": p4[1], "tps": [p4[0]] * 3}, "P20K": {"mean": p20[0], "spread_pct": p20[1], "tps": [p20[0]] * 3},
         "disk_gb_per_token": 0.09, "lowest_memavail_gb": 18.3}
    json.dump(a, open(f"{d}/arm.json", "w"))
    c = cfg or {"args": ["--dspark", "on", "--dspark-block", str(block)]}
    json.dump(c, open(f"{d}/config.json", "w"))
    pp = [[i + 1, k, r] for i, (k, r) in enumerate(pos[:block])] if drafts else []
    with open(f"{d}/disk.jsonl", "w") as f:
        for w in ("W1-think", "W2-code", "W3-research"):
            f.write(json.dumps({"id": w, "rep": 0, "completion_tokens": 3072,
                                "engine": {"drafts": [{"kept": sum(x[1] for x in pp) // 3, "offered": sum(x[2] for x in pp) // 3,
                                                       "per_pos": [[p, k // 3, r // 3] for p, k, r in pp]}] if drafts else []}}) + "\n")
        f.write(json.dumps({"id": "P4K", "rep": 0, "engine": {}}) + "\n")
    lines = [f"ds4: experts per word: {epw} (full quality)",
             f"ds4: CUDA0 layers [40, 42]: weights 0.34 GB, experts 4.47 GB (384 of 384 in VRAM), caches 0.00 GB, {free[0]} MiB free",
             f"ds4: CUDA1 layers [{'0' if trunk else '8'}, 39] + head: weights 5.99 GB, experts 6.31 GB (693 of 15360 in VRAM), caches 0.12 GB, {free[1]} MiB free"]
    if not loaded:
        lines.append("ds4: DSpark not loaded: the routed experts ...")
    open(f"{d}/engine-start.log", "w").write("\n".join(lines) + "\n")
    open(f"{d}/summary.txt", "w").write(f"=== 2026-11-09 10:00:00 ready after 12 s: MemAvailable 29.6 GB, engine RSS {rss} MB; vram 0, 15362 MiB, 572 MiB;\n")
    for s in stops:
        open(f"{d}/{s}", "w").write(f"{s}: synthetic\n")


def selftest(base):
    rb = os.path.realpath(base)
    if not (rb == os.path.realpath(SCRATCH) or rb.startswith(os.path.realpath(SCRATCH) + os.sep)):
        print(f"selftest writes only under {SCRATCH}"); return 2
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    ok = True

    def chk(what, cond):
        nonlocal ok
        print(f"{'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and cond

    # --- the winner rule on synthetic arms (decode means / spreads in %)
    cases = [
        ("C3 wins, C4 does not beat it", {"C2": (30.0, 1.0), "C3": (31.5, 1.0), "C4": (32.0, 1.0)}, {}, "C3"),
        ("C3 2.9 % beyond noise: C2 kept; C4 beats C2", {"C2": (30.0, 1.0), "C3": (31.17, 1.0), "C4": (31.3, 1.0)}, {}, "C4"),
        ("C3 exactly 3 % beyond noise: replaces", {"C2": (30.0, 1.0), "C3": (31.2, 1.0), "C4": (31.0, 1.0)}, {}, "C3"),
        ("C3 beats decode but P20K lower beyond noise: C2 kept", {"C2": (30.0, 1.0), "C3": (32.0, 1.0), "C4": (30.1, 1.0)},
         {"C3": {"p20": (760.0, 1.0)}}, "C2"),
        ("C2's spread 3.91 % (11-07) eats C3's +5 %: C2 kept", {"C2": (30.0, 3.91), "C3": (31.5, 1.0), "C4": (31.6, 1.0)}, {}, "C2"),
        ("C2 hit a guard: no winner", {"C2": (30.0, 1.0), "C3": (32.0, 1.0), "C4": (33.0, 1.0)}, {"C2": {"stops": ("GUARD",)}}, None),
        ("C4 did not run: no winner", {"C2": (30.0, 1.0), "C3": (32.0, 1.0)}, {}, None),
        ("C3 soft-stopped: dropped; C4 vs C2", {"C2": (30.0, 1.0), "C3": (35.0, 1.0), "C4": (31.5, 1.0)}, {"C3": {"stops": ("SOFTSTOP",)}}, "C4"),
        ("C3 at 5 experts a word: dropped", {"C2": (30.0, 1.0), "C3": (35.0, 1.0), "C4": (30.5, 1.0)}, {"C3": {"epw": 5}}, "C2"),
        ("C4's config says --dspark-block 2: dropped", {"C2": (30.0, 1.0), "C3": (30.5, 1.0), "C4": (35.0, 1.0)},
         {"C4": {"cfg": {"args": ["--dspark", "on", "--dspark-block", "2"]}}}, "C2"),
        ("C3's drafter not loaded: dropped", {"C2": (30.0, 1.0), "C3": (35.0, 1.0), "C4": (30.0, 1.0)}, {"C3": {"loaded": False}}, "C2"),
        ("C3 with 5 W answers: dropped", {"C2": (30.0, 1.0), "C3": (35.0, 1.0), "C4": (30.0, 1.0)}, {"C3": {"wn": 5}}, "C2"),
        ("ties go to fewer drafts: all equal -> C2", {"C2": (30.0, 0.5), "C3": (30.0, 0.5), "C4": (30.0, 0.5)}, {}, "C2"),
    ]
    for name, dec, mods, want in cases:
        o = f"{base}/rule-{len(name)}-{abs(hash(name)) % 10000}"
        for n, (m, s) in dec.items():
            _arm(f"{o}/arms/{n}", n, BLOCK[n], m, s, **mods.get(n, {}))
            os.symlink(f"{o}/arms/{n}", f"{o}/{n}")
        infos = {n: arm_info(o, n) for n in ARMS}
        w, steps, why = pick(infos)
        chk(f"rule: {name}: winner {w} (want {want}); {'; '.join(why)[:150]}", w == want)
    # --- against the stored 11-07 arms (read-only): gain / noise as report.json, the rule, the acceptance
    rj = js(f"{REF_RUN}/report.json") or {}
    ref = {n: arm_info(REF_RUN, n) for n in ("C0", "C1", "C2")}
    g = gain(ref["C0"]["arm"], ref["C2"]["arm"], "decode")
    want = tuple((rj.get("compare") or {}).get("C2_vs_C0", {}).get("gain_noise_pct", {}).get("decode") or ())
    chk(f"stored 11-07: C2 vs C0 decode {g} = report.json's {want}", want and g == want)
    b, det = beats(ref["C1"]["arm"], ref["C2"]["arm"])
    chk(f"stored 11-07: C2 vs C1 under the D1 rule: decode {det['decode']} -> beyond noise {det['decode_beyond_noise']} < 3: "
        f"does not beat ({b})", not b and det["decode_beyond_noise"] < 3)
    b2, det2 = beats(ref["C0"]["arm"], ref["C2"]["arm"])
    chk(f"stored 11-07: C2 vs C0: beats ({b2}); compare.py's words '{compare_verdict(ref['C0']['arm'], ref['C2']['arm'])}' = "
        f"report.json's '{(rj.get('compare') or {}).get('C2_vs_C0', {}).get('verdict')}'",
        b2 and compare_verdict(ref["C0"]["arm"], ref["C2"]["arm"]) == (rj.get("compare") or {}).get("C2_vs_C0", {}).get("verdict"))
    ok2, w2 = clean(ref["C2"], "C2")
    chk(f"stored 11-07 C2 is clean under the D1 rule ({w2})", ok2)
    t = ref["C2"]["acc_w"]
    ra = ((rj.get("acceptance") or {}).get("C2") or {}).get("W1-W3") or {}
    chk(f"stored 11-07 C2 acceptance W1-W3: position 1 {t['positions'].get('1')}, 2 {t['positions'].get('2')}, rounds {t['rounds']}, "
        f"tokens a round {t['tokens_per_verify_round']} (report.json: {ra.get('kept')} / {ra.get('offered')}, {ra.get('rounds')}, "
        f"{ra.get('tokens_per_verify_round')})",
        t["kept"] == ra.get("kept") and t["offered"] == ra.get("offered") and t["rounds"] == ra.get("rounds")
        and round(t["tokens_per_verify_round"], 2) == ra.get("tokens_per_verify_round") and t["positions"]["1"]["pct"] == 82.84)
    # --- CL on the stored AL / BL (read-only): PASS / FAIL as report.md
    al, bl = cl_verdict(f"{REF_RUN}/AL"), cl_verdict(f"{REF_RUN}/BL")
    chk(f"CL rule on the stored AL: {al['verdict']} (lowest {al.get('lowest_gb')}), BL: {bl['verdict']} (lowest {bl.get('lowest_gb')}, "
        f"stops {bl.get('stops')}) - report.md: AL PASS, BL FAIL", al["verdict"] == "PASS" and bl["verdict"] == "FAIL")
    chk("CL not run -> NOT RUN", cl_verdict(None)["verdict"] == "NOT RUN")
    # --- d1-derive against the real C2 config (writes only into the scratch folder)
    o = f"{base}/derive1"
    rc = d1_derive(o)
    dv = js(f"{o}/derive-d1.json") or {}
    c3 = js(f"{o}/cfg-C3.json") or {}
    chk(f"d1-derive on the real configs: rc {rc}; C3 = C2 but --dspark-block {args_map(c3.get('args') or []).get('--dspark-block')} "
        f"and slot {(c3.get('env') or {}).get('STRATA_DS4_SLOT_DIR')}; problems {dv.get('problems')}",
        rc == 0 and args_map(c3["args"]).get("--dspark-block") == "3" and c3["env"]["STRATA_DS4_SLOT_DIR"] == f"{SLOTS}/C3")
    bad = json.load(open(C2CFG)); set_arg(bad["args"], "--dspark-conf", "0.6")
    json.dump(bad, open(f"{base}/c2-changed.json", "w"))
    chk("d1-derive refuses a C2 config that is not the 11-07 one", d1_derive(f"{base}/derive1b", c2src=f"{base}/c2-changed.json") == 1)
    # --- a whole synthetic D1 folder: decide, finish, and D2's check of it
    o = f"{base}/d1run"
    os.makedirs(o)
    d1_derive(o)                                    # (its own cfg-C3 / C4 / CL, as gap-d1.sh's preflight writes them)
    for n, m in (("C2", 30.0), ("C3", 32.0), ("C4", 32.5)):
        _arm(f"{o}/arms/{n}", n, BLOCK[n], m, 1.0, rss=58232 + (4 if n != "C2" else 0))
        os.symlink(f"{o}/arms/{n}", f"{o}/{n}")
    os.makedirs(f"{o}/kl-c")
    json.dump({"verdict": "PASS", "pass": True, "vs_A": {"top1_changed": 33, "nll_distance": 0.005, "kl_mean": 0.007, "kl_p90": 0.013,
                                                         "kl_gt1": 1}, "band": {"top1": 40, "nll": 0.00701}, "time": "rc 0"},
              open(f"{o}/kl-c/kl-c-result.json", "w"))
    epoch = int(time.time())
    json.dump({"epoch": epoch, "iso": "x"}, open(f"{o}/started.json", "w"))
    cur, lat = f"{base}/d1-current.txt", f"{base}/d1-latest.txt"
    open(cur, "w").write(f"{os.path.realpath(o)} {epoch} x\n")
    d1_decide(o)
    D = js(f"{o}/decision-d1.json")
    chk(f"d1-decide: winner {D['winner']} (want C3: C4's +1.6 % is not 3 % beyond noise), config {os.path.basename(D['winner_config'] or '')}, "
        f"KL {D['kl']['verdict']}, CL {D['cl']['verdict']} (not run), start lines {D['cl_start_lines_vs_winner'].get('within_a_few_mb')}",
        D["winner"] == "C3" and D["winner_config"].endswith("/cfg-C3.json") and D["kl"]["verdict"] == "PASS"
        and D["cl"]["verdict"] == "NOT RUN" and D["cl_start_lines_vs_winner"]["within_a_few_mb"] is True
        and os.path.exists(f"{o}/d1.md") and "position 3" in open(f"{o}/d1.md").read())
    ok_, _, _, why = d2_check_d1(lat, cur)
    chk(f"d2-check before D1 finished: refused ({why[:90]})", not ok_)
    time.sleep(0.05)
    d1_finish(o, 0, latest=lat)
    ok_, d1d, _, why = d2_check_d1(lat, cur)
    chk(f"d2-check after D1 exit 0: ok ({why}; {d1d == os.path.realpath(o)})", ok_ and d1d == os.path.realpath(o))
    time.sleep(0.05)
    open(cur, "w").write(f"{base}/newer-run {epoch + 5} y\n")
    ok_, _, _, why = d2_check_d1(lat, cur)
    chk(f"d2-check when a newer D1 run started: refused ({why[:80]})", not ok_)
    open(cur, "w").write(f"{os.path.realpath(o)} {epoch} x\n")
    os.utime(lat, (time.time() - 100, time.time() - 100))
    ok_, _, _, why = d2_check_d1(lat, cur)
    chk(f"d2-check when d1-latest.txt is older than d1-current.txt: refused ({why[:70]})", not ok_)
    os.utime(lat, None)
    keep = open(D["winner_config"], "rb").read()
    c = json.load(open(D["winner_config"])); c["_comment"] += " touched"
    json.dump(c, open(D["winner_config"], "w"), indent=1)
    ok_, _, _, why = d2_check_d1(lat, cur)
    chk(f"d2-check when the winner's config changed: refused ({why[:70]})", not ok_)
    open(D["winner_config"], "wb").write(keep)
    D2 = js(f"{o}/decision-d1.json")
    D2["winner"] = None; wjson(f"{o}/decision-d1.json", D2)
    ok_, _, _, why = d2_check_d1(lat, cur)
    chk(f"d2-check with no winner: refused ({why[:70]})", not ok_)
    D2["winner"] = "C3"; D2["exit"] = 3; D2["complete"] = False; wjson(f"{o}/decision-d1.json", D2)
    ok_, _, _, why = d2_check_d1(lat, cur)
    chk(f"d2-check after a D1 exit 3: refused ({why[:70]})", not ok_)
    ok_, _, _, why = d2_check_d1(f"{base}/no-such-latest.txt", cur)
    chk(f"d2-check without d1-latest.txt: refused ({why[:60]})", not ok_)
    D2["exit"] = 0; D2["complete"] = True; wjson(f"{o}/decision-d1.json", D2)
    os.utime(lat, None)
    # --- d2-derive / probe / rule / report
    o2 = f"{base}/d2run"
    rc = d2_derive(o2, o, D=js(f"{o}/decision-d1.json"))
    dd = js(f"{o2}/derive-d2.json") or {}
    r2 = js(f"{o2}/cfg-R2.json") or {}
    pk = js(f"{o2}/cfg-P1017.json") or {}
    chk(f"d2-derive: rc {rc}; X = {os.path.basename(dd.get('configs', {}).get('X', {}).get('source', ''))}; R2 --vram-experts "
        f"{args_map(r2.get('args') or []).get('--vram-experts')}; P1017 pack {os.path.basename(args_map(pk.get('args') or []).get('--pack', ''))}; "
        f"problems {dd.get('problems')}",
        rc == 0 and dd["configs"]["X"]["source"].endswith("/cfg-C3.json") and args_map(r2["args"]).get("--vram-experts") == "0.98"
        and args_map(pk["args"]).get("--pack") == DPACK and pk["tokenizer"] == f"{DPACK}/tokenizer"
        and args_map(pk["args"]).get("--dspark-block") == "2")
    c2acc = D["arms"]["C2"]["acceptance_w1w3"]
    base_pct = 100.0 * c2acc["positions"]["1"]["kept"] / c2acc["positions"]["1"]["reached"]
    for name, pct, want in (("+2.1 points", base_pct + 2.1, "BUILD PROPOSED"), ("+1.9 points", base_pct + 1.9, "CLOSED"),
                            ("-3 points", base_pct - 3, "CLOSED")):
        pd = f"{o2}/probe-{want.split()[0].lower()}-{int(pct * 10)}"
        _arm(pd, "P1017", 2, 25.0, 1.0, pos=((int(pct * 100), 10000), (8000, 9000)))
        v, det = probe_verdict(arm_info(os.path.dirname(pd), os.path.basename(pd)), c2acc)
        chk(f"probe {name}: {v} ({det.get('points')} points; want {want})", v == want)
    _arm(f"{o2}/probe-nl", "P1017", 2, 25.0, 1.0, loaded=False)
    v, det = probe_verdict(arm_info(o2, "probe-nl"), c2acc)
    chk(f"probe whose drafter did not load: {v} ({det.get('why')})", v == "NO VERDICT")
    os.symlink(f"{o2}/probe-closed-{int((base_pct + 1.9) * 10)}", f"{o2}/P1017")
    d2_probe(o2, o)
    chk("d2-probe writes probe.json / probe.md (CLOSED)", (js(f"{o2}/probe.json") or {}).get("verdict") == "CLOSED")
    rc = d2_rule(o2)
    chk(f"d2-rule: rc {rc}; rule.txt = the plan's 2.5 text, rule-1108.txt holds Karl's 11-08 decisions, think-rule.txt INFO only",
        rc == 0 and open(f"{o2}/rule.txt").read().rstrip("\n") == plan_rule_block()
        and "Fixed rules for D2" in open(f"{o2}/rule-1108.txt").read() and "INFO ONLY" in open(f"{o2}/think-rule.txt").read())
    json.dump({"verdict": "PASS", "why": ["synthetic"], "d2_x_r1": 2.0, "band": 11.3449}, open(f"{o2}/verdict.json", "w"))
    open(f"{o2}/think-skipped.txt", "w").write("thinking-on arm skipped: synthetic reason\n")
    d2_report(o2, o)
    R = js(f"{o2}/d2-result.json")
    chk(f"d2-report: verdict {R['sampled_test']['verdict']}, thinking {R['thinking_on_info']['result']}, probe {R['probe']['verdict']}, "
        f"KL {R['d1_kl']}, CL {R['d1_cl']} -> {R['proposal'][:40]}",
        R["sampled_test"]["verdict"] == "PASS" and R["thinking_on_info"]["result"] == "SKIPPED" and R["probe"]["verdict"] == "CLOSED"
        and R["d1_cl"] == "NOT RUN" and R["proposal"].startswith("not every") and "skipped: synthetic" in open(f"{o2}/d2.md").read())
    # --- the real files D1 / D2 use exist (read-only)
    need = [C0CFG, C2CFG, ACFG, f"{NPACK}/tensors.txt", f"{DPACK}/tensors.txt", PLAN, SPLAN, DPROP, f"{os.path.realpath(f'{REF_RUN}/C2')}/config.json"]
    miss = [p for p in need if not os.path.exists(p)]
    t5 = open(f"{DPACK}/tensors.txt").read()
    chk(f"real inputs present ({len(need) - len(miss)} of {len(need)}; missing {miss}); the October pack's file 5 is the 1017 Q8_0 drafter",
        not miss and "\nfile 5 dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf\n" in "\n" + t5)
    print("D12 SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else ""
    if cmd == "d1-rule":
        return d1_rule(a[1])
    if cmd == "d1-derive":
        return d1_derive(a[1])
    if cmd == "d1-decide":
        return d1_decide(a[1])
    if cmd == "d1-finish":
        return d1_finish(a[1], a[2])
    if cmd == "d2-check-d1":
        ok, d, D, why = d2_check_d1()
        if ok:
            print(d)
            return 0
        print(f"REFUSED: {why}")
        return 1
    if cmd == "d2-rule":
        return d2_rule(a[1])
    if cmd == "d2-derive":
        return d2_derive(a[1], a[2])
    if cmd == "d2-probe":
        return d2_probe(a[1], a[2])
    if cmd == "d2-report":
        return d2_report(a[1], a[2])
    if cmd == "selftest":
        return selftest(a[1] if len(a) > 1 else f"{SCRATCH}/d12-selftest")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
