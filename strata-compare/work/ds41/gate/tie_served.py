#!/usr/bin/env python3
"""tie_served.py MODE ... - 11-06 (Karl, on the 11-05 csample gap, results/ds41/gate-1105-2032-csample: "C rerun: (a).
Run the near-tie check through the served path, where the divergence appeared. Record that the command-line path didn't
diverge within 512 tokens. Add it to the series as a step after the Basalt rerun, between questions. If it needs more
than about 90 min with 8080 down, tell me first.")

A SEPARATE mode beside tie_check.py, which is NOT changed. The rule is tie_check.py's: its own threshold() recomputes it
from the stored KL scores, and nothing runs unless the text it gives equals the 11-05 rule.txt byte for byte (p90 0.5883
nats decides, max 4.3312 reported beside it). Only WHERE the first divergence is found changes:
  - 11-05 (tie_check.py): C0f / C1f decoded on the command line (cliarm.sh --ids ... --n 512); C0f reproduced the served
    text, but C1f did not leave C0f within 512 tokens (all 512 ids identical) - no verdict, exit 2
  - here: in this gap's SERVED greedy runs of C0f and C1f (work/ds41/tune/tunearm.sh + greedy_client.py: G-W1, G-W2,
    G-P4K0 on one fresh test server each, thinking off, temperature 0, 512 tokens), exactly as 11-04's CG step ran them
    when C1f left C0f at char 126 of G-P4K0. The generated ids come from server.py itself (STRATA_DEBUG=1 in the
    server's env: "[strata] raw ids: [...]" per request - a print; the engine binary has no STRATA_DEBUG string)
The measurement at the divergence is tie_check.py's, unchanged: teacher-forced scoring of the prompt + C0f's ids up to
j + 2 on cfg-C0f via cliarm.sh (DS4_SCORE_PREFIX = the prompt), --window 1 (decides) and --window 2 at both alignments
(reported), the top-64 at every generated position up to j.
Two validity conditions (no number, no verdict - exit 2, never 1): no window-1 row at j; C1f's token outside the scored
top-64 while the bound that leaves (logprob(C0f's) - the 64th logprob) is at or under the threshold.

Modes:
  selftest                         no engine, no GPU: the files, the configs, the rule (recomputed = the frozen text), the
                                   prompt (4,115 ids = 11-05's), 11-04's served texts (char 126), 11-05's command-line
                                   ids (no divergence within 512), the engine binary, server.py's id print, and synthetic
                                   checks of the id parser, the divergence finder, the env check and the verdict.
                                   Exit 0 all OK, 1 not
  derive SRC NAME OUT SLOTDIR      gate.sh's derivation (SRC + --no-expert-cache) with its own slot folder SLOTDIR -> OUT;
                                   exit 1 unless it equals 11-04's cfg-NAME.json but for STRATA_DS4_SLOT_DIR and _comment
  rule OUTDIR                      OUTDIR/rule.txt (the frozen text, byte for byte) + OUTDIR/where.txt, before any
                                   engine run; exit 1 if the recomputed rule is not the frozen one
  envcheck EXE CONFIG --label L    tunearm.sh's CLIENT runs it once the served engine is up: exactly one engine of EXE
                                   (/proc/PID/exe), its env = the config's env exactly + STRATA_DEBUG=1, no other
                                   DS4_ / DSV4_ / STRATA_ / GGML_ key that the binary can read, argv = --serve + the
                                   config's args. Exit 0 OK, 1 not (the client then does not run: no measurement)
  judge OUTDIR                     inside gap-ctie-served.sh's gap only (CTIE_IN_GAP=1, the gap's lock holder alive):
                                   the reproduction checks, j from the served ids, the three scorings (each engine's env
                                   watched by /proc/PID/exe, a mismatch stopped by its PID), the frozen rule at j ->
                                   OUTDIR/tie/{served.json,tie.json,tie.md}. Exit 0 within rounding, 1 not, 2 could not
                                   run or reproduce, 3 kernel error
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

SC = "/home/USER/ai-speed-testing/strata-compare"
G = f"{SC}/work/ds41/gate"
sys.path.insert(0, G)
import tie_check as TC  # noqa: E402  (the frozen rule's own code: threshold(), tokenizer(), render(), gen_ids())

G2 = TC.G2                                          # results/ds41/gate-1104-0725: the served texts, cfg-C0f / C1f, snapshot
G3 = f"{SC}/results/ds41/gate-1105-2032-csample"    # 11-05: the frozen rule.txt, prompt.ids, the command-line decodes
FROZEN_RULE = f"{G3}/tie/rule.txt"
SNAP = f"{G2}/profile-snapshot.bin"                 # the 11-04 gap's profile snapshot (b54bd76a...), as tie_check uses
SNAP_SHA = "b54bd76a129d2d2d"
EXE = f"{SC}/engine-v026p343-slotram-ds41/strata-dsv41"
SERVER = f"{SC}/strata-v026/serve/server.py"
NS = ("DS4_", "DSV4_", "STRATA_", "GGML_")          # the env namespaces the engine binary reads (its strings)
SERVED_EXTRA = {"STRATA_DEBUG": "1"}                # the one key the served arms add (server.py: print the generated ids)
PROMPTS = ("G-W1", "G-W2", "G-P4K0")                # greedy_client.py's order, one server per arm
CHAR_1104 = 126
P90_FROZEN, MAX_FROZEN = 0.5883, 4.3312
SCRATCH = f"{G}/scratch-ctie"
RAW = "[strata] raw ids: "


# ------------------------------------------------------------------------------------------------ the rule (frozen)
def rule_text():
    """tie_check.py's rule text, built from tie_check.threshold() with tie_check.py's own words (lines 136-141)"""
    (mx, v, seg, pos), nflip, med, p90 = TC.threshold()
    rule = [f"tie_check.py rule, written before any engine run", "",
            f"near-tie within rounding iff, in C0f's window-1 scoring, logprob(C0f's token) - logprob(C1f's token) at the first "
            f"divergent position <= {p90:.4f} nats: the 90th percentile of the A-side gaps of the {nflip} top-1 flips of A's "
            f"placement variants Aa / Ab in the KL harness (Karl 11-04: 'C's threshold: 0.59 nats (the 90th percentile), with "
            f"the verdict also reported under the maximum (4.33)'; median {med:.3f}, max {mx:.4f} at {v}, {seg}, position {pos}). "
            "The verdict that decides is the p90 one; the max one is reported beside it"]
    return "\n".join(rule) + "\n", p90, mx


def rule_check():
    txt, p90, mx = rule_text()
    return txt == open(FROZEN_RULE).read(), txt, p90, mx


WHERE = """Where the first divergence is found (tie_served.py, 11-06 - Karl's decision (a) on the 11-05 csample gap):
in this gap's SERVED greedy runs of C0f and C1f (work/ds41/tune/tunearm.sh + greedy_client.py: G-W1, G-W2, G-P4K0 on one
fresh test server each, thinking off, temperature 0, 512 tokens - as 11-04's CG step ran them, when C1f left C0f at char
126 of G-P4K0), from the generated ids server.py prints (STRATA_DEBUG=1). Not on the command line: on 11-05 C1f's
command-line path did not leave C0f's within 512 tokens. The rule above is unchanged (tie_check.threshold() recomputed it;
it equals the 11-05 rule.txt byte for byte) and is applied as written: C0f's window-1 scoring (teacher-forced, command
line, cfg-C0f) at that position. No number, no verdict (exit 2): no window-1 row at j, or C1f's token outside the scored
top-64 with the bound at or under the threshold.
"""


# ------------------------------------------------------------------------------------------------ small pieces
def first_div(a, b):
    """the first index where a and b differ; len(shorter) if one is a proper prefix; None if equal"""
    k = next((x for x in range(min(len(a), len(b))) if a[x] != b[x]), None)
    if k is None and len(a) != len(b):
        k = min(len(a), len(b))
    return k


def related(a, b):
    """tie_check.py's reproduction relation: equal, or one a prefix of the other"""
    return a == b or a.startswith(b) or b.startswith(a)


def raw_ids(path):
    out = []
    for line in open(path, errors="replace"):
        if line.startswith(RAW):
            out.append([int(x) for x in json.loads(line[len(RAW):].strip())])
    return out


def texts_of(d):
    p = f"{os.path.realpath(d)}/greedy.jsonl"
    if not os.path.exists(p):
        return {}, []
    recs = [json.loads(x) for x in open(p) if x.strip()]
    return {r["id"]: r.get("text") or "" for r in recs}, [r["id"] for r in recs]


def placement(path):
    """the placement lines of an engine start (free MiB left out: the expert counts are what must match)"""
    if not os.path.exists(path):
        return None
    lines = [re.sub(r", \d+ MiB free", "", x.strip()) for x in open(path, errors="replace")
             if re.search(r"CUDA[01] layers|routed experts on the CPU lane|experts per word|DSpark not loaded", x)]
    return lines


def binary_bytes(exe=EXE):
    with open(exe, "rb") as f:
        return f.read()


def engines(exe=EXE):
    """(pid, env, argv) of every process whose /proc/PID/exe is EXE (no command-line patterns)"""
    rx, out = os.path.realpath(exe), []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            if os.readlink(f"/proc/{d}/exe") != rx:
                continue
            env = dict(x.split("=", 1) for x in open(f"/proc/{d}/environ", "rb").read().decode("utf-8", "replace").split("\0")
                       if "=" in x)
            argv = open(f"/proc/{d}/cmdline", "rb").read().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        while argv and argv[-1] == "":
            argv.pop()
        out.append((int(d), env, argv))
    return out


def env_bad(env, argv, cfg, kind, extra, binary, cli_args=()):
    """-> (bad, notes). kind 'served': argv = EXE --serve ARGS; 'cli': argv = EXE ARGS --vision off CLI_ARGS (cliarm.sh)"""
    bad, notes = [], []
    want = {str(k): str(v) for k, v in (cfg.get("env") or {}).items()}
    for k, v in list(want.items()) + list(extra.items()):
        if env.get(k) != v:
            bad.append(f"{k}={env.get(k, 'unset')} (want {v})")
    for k in sorted(env):
        if k.startswith(NS) and k not in want and k not in extra:
            if k.encode() in binary:
                bad.append(f"{k}={env[k]} set behind the config (the engine reads it)")
            else:
                notes.append(f"{k}={env[k]} (not read by this engine)")
    exp = (["--serve"] + list(cfg["args"])) if kind == "served" else (list(cfg["args"]) + ["--vision", "off"] + list(cli_args))
    got = argv[1:]
    if got[:len(exp)] != exp:
        k = first_div(got, exp)
        bad.append(f"argv differs from the config's from item {k}: {got[k:k + 3]} vs {exp[k:k + 3]}")
    elif len(got) > len(exp):
        notes.append(f"extra args {got[len(exp):]}")
    if env.get("CUDA_DEVICE_ORDER"):
        notes.append(f"CUDA_DEVICE_ORDER={env['CUDA_DEVICE_ORDER']}")
    return bad, notes


def env_line(label, pid, env, cfg, bad, notes):
    return (f"engine pid {pid} ({label}): {len(cfg.get('env') or {})} config env keys, STRATA_DS4_SLOT_DIR="
            f"{env.get('STRATA_DS4_SLOT_DIR', 'unset')}, CUDA_VISIBLE_DEVICES={env.get('CUDA_VISIBLE_DEVICES', 'unset')}"
            + (f"; notes: {'; '.join(notes)}" if notes else "") + (f" -> ENV MISMATCH {'; '.join(bad)}" if bad else " -> ENV OK"))


# ------------------------------------------------------------------------------------------------ derive / rule
def derive(src, name, out, slots, write=True):
    """gate.sh derive(): SRC + its own slot folder + --no-expert-cache. -> (config, differences vs 11-04's cfg-NAME)"""
    c = json.load(open(src))
    c["env"]["STRATA_DS4_SLOT_DIR"] = slots
    if "--no-expert-cache" not in c["args"]:
        c["args"].append("--no-expert-cache")
    c["_comment"] = (f"tie_served.py derive (gap-ctie-served.sh, 11-06) from {src}, as gate.sh derives {name} (placement "
                     f"frozen: --no-expert-cache), its own slot folder. " + c.get("_comment", ""))
    ref = json.load(open(f"{G2}/cfg-{name}.json"))
    ref["env"]["STRATA_DS4_SLOT_DIR"] = slots
    a = {k: v for k, v in c.items() if k != "_comment"}
    b = {k: v for k, v in ref.items() if k != "_comment"}
    diffs = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    if write and not diffs:
        json.dump(c, open(out, "w"), indent=1)
    return c, diffs


def cmd_derive(av):
    src, name, out, slots = av
    _, diffs = derive(src, name, out, slots)
    if diffs:
        print(f"derive {name}: differs from {G2}/cfg-{name}.json in {diffs} (beyond the slot folder) - not written")
        return 1
    print(f"derive {name}: {out} = 11-04's cfg-{name}.json but for STRATA_DS4_SLOT_DIR={slots}")
    return 0


def cmd_rule(av):
    o = av[0]
    os.makedirs(o, exist_ok=True)
    same, txt, p90, mx = rule_check()
    if not same:
        print(f"the rule recomputed by tie_check.threshold() differs from the frozen {FROZEN_RULE} - nothing written")
        return 1
    open(f"{o}/rule.txt", "w").write(txt)
    open(f"{o}/where.txt", "w").write(WHERE)
    print(txt + "\n" + WHERE, end="")
    return 0


def cmd_envcheck(av):
    exe, cfgp = av[0], av[1]
    label = av[av.index("--label") + 1] if "--label" in av else "?"
    cfg = json.load(open(cfgp))
    ps = engines(exe)
    if len(ps) != 1:
        print(f"ENV CHECK FAILED ({label}): {len(ps)} running engine(s) of {exe} (want exactly 1)")
        return 1
    pid, env, argv = ps[0]
    bad, notes = env_bad(env, argv, cfg, "served", SERVED_EXTRA, binary_bytes(exe))
    print(env_line(label, pid, env, cfg, bad, notes))
    print(("ENV CHECK OK" if not bad else "ENV CHECK FAILED - this arm is not measured") + f" ({label})")
    return 0 if not bad else 1


# ------------------------------------------------------------------------------------------------ the verdict
def verdict(runs, P, j, i0, alt, p90, mx):
    """tie_check.py's numbers at j (its rows / at() / within), with the two validity conditions. -> (rc, dict)"""
    p = P + j - 1                         # the row that predicts generated token j
    rows, ok_path = [], True
    for g in range(1, j + 1):             # (generated token 0 is predicted inside the prompt read: not scored)
        r = runs["w1"].get(P + g - 1)
        if not r:
            continue
        tgt, lt, top, kk = r
        two = sorted(kk, key=lambda x: -x[1])[:2]
        rows.append({"gen": g, "target": tgt, "top1": top, "top2": two, "gap": two[0][1] - two[1][1]})
        if g < j and top != tgt:
            ok_path = False

    def at(name):
        r = runs.get(name, {}).get(p)
        if not r:
            return None
        tgt, lt, top, kk = r
        d = dict(kk)
        fl = min(x for _, x in kk)
        return {"top1": top, "lp_c0f_token": d.get(i0[j], fl), "lp_c1f_token": d.get(alt, fl),
                "gap_c0f_minus_c1f": d.get(i0[j], fl) - d.get(alt, fl), "top5": sorted(kk, key=lambda x: -x[1])[:5],
                "c0f_token_in_top64": i0[j] in d, "c1f_token_in_top64": alt in d}
    res = {n: at(n) for n in runs}
    w1 = res.get("w1")
    out = {"rule_gap": p90, "rule_max_gap": mx, "at_j": res, "positions": rows,
           "window1_reproduces_c0f_path": ok_path and bool(w1) and w1["top1"] == i0[j]}
    if not w1:
        out.update(within_rounding=False, within_rounding_under_max=None, why="no window-1 row at j")
        return 2, out
    g0 = w1["gap_c0f_minus_c1f"]
    if not w1["c1f_token_in_top64"] and g0 <= p90:
        out.update(within_rounding=False, within_rounding_under_max=None,
                   why=f"C1f's token is outside the scored top-64: the gap is only known to be >= {g0:.4f}, at or under the threshold")
        return 2, out
    within = g0 <= p90                    # Karl 11-04: the deciding threshold is the p90 (0.59 nats)
    within_max = (g0 <= mx) if (w1["c1f_token_in_top64"] or g0 > mx) else None   # reported beside it: the maximum (4.33)
    out.update(within_rounding=within, within_rounding_under_max=within_max, why="")
    return (0 if within else 1), out


# ------------------------------------------------------------------------------------------------ judge (in the gap)
def served(o, tok):
    """the reproduction checks on this gap's served arms -> (record, why-not or '')"""
    r = {"path": "served (tunearm.sh + greedy_client.py, one fresh server per arm: G-W1, G-W2, G-P4K0)", "arms": {}}
    arms = {}
    for n in ("C0f", "C1f"):
        d = os.path.realpath(f"{o}/{n}")
        if not os.path.isdir(d):
            return r, f"{n}'s served arm did not run"
        ec = open(f"{d}/envcheck.txt").read() if os.path.exists(f"{d}/envcheck.txt") else ""
        if "ENV CHECK OK" not in ec:
            return r, f"{n}: its engine's env was not checked OK ({(ec.strip().splitlines() or ['no envcheck.txt'])[-1][:200]})"
        for f in ("GUARD", "SOFTSTOP"):
            if os.path.exists(f"{d}/{f}"):
                return r, f"{n} was stopped: {open(f'{d}/{f}').read().strip()[:200]}"
        texts, order = texts_of(d)
        if order != list(PROMPTS):
            return r, f"{n}: requests answered {order} (want {list(PROMPTS)})"
        ids = raw_ids(f"{d}/server.out")
        if len(ids) != len(PROMPTS):
            return r, f"{n}: {len(ids)} '{RAW.strip()}' lines in server.out (want 3: did STRATA_DEBUG=1 reach the server?)"
        for pid, x in zip(PROMPTS, ids):
            if not related(tok.decode(x), texts[pid]):
                return r, f"{n} {pid}: the printed ids do not decode to the streamed text"
        pl, pl_ref = placement(f"{d}/engine-start.log"), placement(f"{G2}/{n}/engine-start.log")
        if not pl or pl != pl_ref:
            return r, f"{n}: the placement lines differ from 11-04's {n}: {pl} vs {pl_ref}"
        eng = [json.loads(x) for x in open(f"{d}/greedy-engine.jsonl")] if os.path.exists(f"{d}/greedy-engine.jsonl") else []
        arms[n] = {"dir": d, "texts": texts, "ids": dict(zip(PROMPTS, ids)), "placement": pl,
                   "drafts": {e["id"]: (e.get("engine") or {}).get("drafts") for e in eng}}
        r["arms"][n] = {"dir": d, "placement": pl, "drafts": arms[n]["drafts"], "envcheck": ec.strip().splitlines()[-2:]}
    ref = {n: texts_of(f"{G2}/{n}")[0] for n in ("C0f", "C1f")}
    r["c0f_text_eq_1104"] = {p: arms["C0f"]["texts"][p] == ref["C0f"].get(p) for p in PROMPTS}
    r["c1f_text_eq_1104"] = {p: arms["C1f"]["texts"][p] == ref["C1f"].get(p) for p in PROMPTS}
    t0, t1 = arms["C0f"]["texts"]["G-P4K0"], arms["C1f"]["texts"]["G-P4K0"]
    r["char"] = first_div(t0, t1)
    r["char_1104"] = first_div(ref["C0f"]["G-P4K0"], ref["C1f"]["G-P4K0"])
    r["w1w2_c1f_eq_c0f"] = {p: arms["C0f"]["texts"][p] == arms["C1f"]["texts"][p] for p in PROMPTS[:2]}
    i0, i1 = arms["C0f"]["ids"]["G-P4K0"], arms["C1f"]["ids"]["G-P4K0"]
    r["i0"], r["i1"] = i0, i1
    cli0, cli1 = TC.gen_ids(f"{G3}/tie/decode-C0f"), TC.gen_ids(f"{G3}/tie/decode-C1f")
    r["c0f_ids_eq_cli_1105"] = i0 == cli0
    r["c0f_ids_first_diff_vs_cli_1105"] = first_div(i0, cli0)
    r["cli_1105_c1f_eq_c0f"] = cli0 == cli1
    if not r["c0f_text_eq_1104"]["G-P4K0"]:
        return r, (f"C0f's served G-P4K0 text differs from 11-04's (from char {first_div(t0, ref['C0f']['G-P4K0'])}): "
                   "the reference path is not reproduced")
    if first_div(i0, i1) is None:
        return r, f"C1f's served path did not leave C0f's within {len(i0)} tokens this time (11-04: char {r['char_1104']})"
    return r, ""


def run_cli(o, name, cfg_path, *args, env=()):
    """tie_check.run() (one cliarm.sh run on the config, the snapshot copied to its profile first), with its engine's
    env watched by /proc/PID/exe as it starts: a mismatch is stopped by its PID and the run counts as not run"""
    c = json.load(open(cfg_path))
    shutil.copy(SNAP, c["args"][c["args"].index("--expert-profile") + 1])
    sd = c["env"]["STRATA_DS4_SLOT_DIR"]
    shutil.rmtree(sd, ignore_errors=True)
    os.makedirs(sd, exist_ok=True)                  # (its own slot folder, emptied before the run)
    d = f"{o}/{name}"
    extra = dict(x.split("=", 1) for x in env)
    b = binary_bytes(c["exe"])
    pr = subprocess.Popen(["bash", f"{G}/cliarm.sh", d, cfg_path, *env, "--", *args], pass_fds=())
    seen, lines = {}, []
    while pr.poll() is None:
        for pid, e, argv in engines(c["exe"]):
            if pid in seen:
                continue
            bad, notes = env_bad(e, argv, c, "cli", extra, b, args)
            seen[pid] = bad
            if bad:
                try:
                    os.kill(pid, signal.SIGKILL)
                    bad.append("STOPPED by its PID before it measured")
                except OSError:
                    pass
            lines.append(env_line(name, pid, e, c, bad, notes))
            print(lines[-1], flush=True)
        time.sleep(0.3)
    rc = pr.returncode
    os.makedirs(d, exist_ok=True)
    ok = bool(seen) and not any(seen.values())
    open(f"{d}/envcheck.txt", "w").write("\n".join(lines + ["ENV CHECK OK" if ok else "ENV CHECK FAILED"]) + "\n")
    if rc == 3:
        print(f"KERNEL ERROR in {name}"); sys.exit(3)
    if not seen:
        print(f"{name}: no engine of {c['exe']} was seen - its env not checked: the run does not count"); sys.exit(2)
    if not ok:
        print(f"{name}: its engine's env was not as configured - the run does not count"); sys.exit(2)
    if rc != 0:
        why = open(f"{d}/GUARD").read().strip() if os.path.exists(f"{d}/GUARD") else \
            (open(f"{d}/engine.out", errors="replace").read().strip().splitlines() or [""])[-1][:300]
        print(f"{name} failed (rc {rc}): {why}"); sys.exit(2)
    return d


def write_md(t, L):
    open(f"{t}/tie.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)


def cmd_judge(av):
    o = av[0]
    t = f"{o}/tie"
    if os.environ.get("CTIE_IN_GAP") != "1":
        print("tie_served.py judge: run only by gap-ctie-served.sh inside its own gap (CTIE_IN_GAP=1) - nothing runs"); return 2
    lp = f"{SC}/tmp/port-gap.lockpid"
    try:
        os.kill(int(open(lp).read().strip()), 0)
    except (OSError, ValueError):
        print("tie_served.py judge: no gap is open (tmp/port-gap.lockpid) - nothing runs"); return 2
    os.makedirs(t, exist_ok=True)
    same, txt, p90, mx = rule_check()
    if not same or not os.path.exists(f"{t}/rule.txt") or open(f"{t}/rule.txt").read() != txt:
        print("the rule recomputed now, tie/rule.txt (written before the arms) and the frozen 11-05 rule.txt are not one "
              "text - no verdict"); return 2
    print(txt + "\n" + WHERE, flush=True)
    import quant_quality as qq
    tok = TC.tokenizer()
    pids = TC.render(tok)
    if ",".join(map(str, pids)) != open(f"{G3}/tie/prompt.ids").read().strip():
        print("G-P4K0's prompt ids differ from 11-05's prompt.ids - no verdict"); return 2
    open(f"{t}/prompt.ids", "w").write(",".join(map(str, pids)))
    rep, why = served(o, tok)
    json.dump(rep, open(f"{t}/served.json", "w"), indent=1)
    head = ["# C's greedy divergence on G-P4K0 through the SERVED path: a near-tie within rounding?", "",
            "Rule: tie/rule.txt (tie_check.py's, unchanged: the frozen 11-05 text, byte for byte); where: tie/where.txt.",
            "11-05 (command line, results/ds41/gate-1105-2032-csample): C1f did not leave C0f within 512 tokens - no verdict.", ""]
    if why:
        write_md(t, head + [f"Verdict: **none - could not reproduce: {why}**"]); return 2
    i0, i1 = rep["i0"], rep["i1"]
    j = first_div(i0, i1)
    if j >= len(i0) or j >= len(i1):
        write_md(t, head + [f"Verdict: **none - one id list is a prefix of the other ({len(i0)} / {len(i1)} ids)**"]); return 2
    alt, c = i1[j], rep["char"]
    json.dump({"version": "tie", "segments": [{"name": "p4k0", "ids": pids + i0[:j + 2]}]}, open(f"{t}/tie.ids.json", "w"))
    P = len(pids)
    cfg0 = f"{o}/cfg-C0f.json"
    runs = {}
    for name, w, pre in (("w1", 1, P), ("w2a", 2, P), ("w2b", 2, P + 1)):
        run_cli(t, f"score-{name}", cfg0, "--score", f"{t}/tie.ids.json", "--score-out", f"{t}/score-{name}.tsv",
                "--window", str(w), env=(f"DS4_SCORE_PREFIX={pre}",))
        runs[name] = qq.read_run(f"{t}/score-{name}.tsv").get("p4k0", {})
    rc, out = verdict(runs, P, j, i0, alt, p90, mx)
    out.update({"path": "served", "prompt_tokens": P, "j": j, "char": c, "char_1104": rep["char_1104"],
                "c0f_token": i0[j], "c1f_token": alt, "c0f_token_text": tok.decode([i0[j]]), "c1f_token_text": tok.decode([alt]),
                "c1f_text_eq_1104": rep["c1f_text_eq_1104"], "c0f_ids_eq_cli_1105": rep["c0f_ids_eq_cli_1105"],
                "cli_1105_c1f_eq_c0f": rep["cli_1105_c1f_eq_c0f"],
                "times": {n: open(f"{t}/score-{n}/run.txt").read().strip() for n in runs if os.path.exists(f"{t}/score-{n}/run.txt")}})
    json.dump(out, open(f"{t}/tie.json", "w"), indent=1)
    g0 = (out["at_j"].get("w1") or {}).get("gap_c0f_minus_c1f")
    wm = out["within_rounding_under_max"]
    L = head + [f"Verdict: **{'within rounding - C is not disqualified (its speed arms run under sampling)' if rc == 0 else ('NOT within rounding - C stays out' if rc == 1 else 'none - ' + out['why'])}**", "",
                f"- first divergent generated token j = {j} (served texts this gap: char {c}; 11-04: char {rep['char_1104']}): "
                f"C0f {out['c0f_token_text']!r} vs C1f {out['c1f_token_text']!r}",
                f"- C1f's served G-P4K0 text = 11-04's: {rep['c1f_text_eq_1104']['G-P4K0']}"
                + ("" if rep['c1f_text_eq_1104']['G-P4K0'] else " - NOTE: the served divergence is not the 11-04 one; the rule is applied at THIS gap's first divergence"),
                f"- C0f's served G-P4K0 text = 11-04's: True; its served ids = 11-05's command-line ids: {rep['c0f_ids_eq_cli_1105']}",
                f"- rule: gap <= {p90:.4f} nats, the p90 (rule.txt; Karl 11-04); C0f's own gap (window 1): {g0}",
                f"- under the maximum ({mx:.4f} nats, reported only): {'within' if wm else ('NOT within' if wm is False else 'not known')}",
                f"- window 1 reproduces C0f's path at every position before j: {out['window1_reproduces_c0f_path']}"]
    for n, r in out["at_j"].items():
        if r:
            L.append(f"- {n}: top-1 {tok.decode([r['top1']])!r}; logprob C0f's token {r['lp_c0f_token']:.4f}, C1f's "
                     f"{r['lp_c1f_token']:.4f}{'' if r['c1f_token_in_top64'] else ' (outside the top-64: the 64th)'}, gap "
                     f"{r['gap_c0f_minus_c1f']:.4f}; top-5 " + ", ".join(f"{tok.decode([i])!r} {x:.3f}" for i, x in r["top5"]))
    L += ["", "| generated token | target | top-1 = target | top-2 gap (nats) |", "|---|---|---|---|"]
    L += [f"| {r['gen']} | {tok.decode([r['target']])!r} | {r['top1'] == r['target']} | {r['gap']:.4f} |" for r in out["positions"]]
    write_md(t, L)
    return rc


# ------------------------------------------------------------------------------------------------ selftest
def cmd_selftest(av):
    ok = [True]

    def chk(name, cond, detail=""):
        print(f"{'ok  ' if cond else 'FAIL'} {name}" + (f": {detail}" if detail else ""), flush=True)
        ok[0] = ok[0] and bool(cond)

    print("tie_served.py selftest (no engine, no GPU)")
    need = [FROZEN_RULE, f"{G3}/tie/prompt.ids", f"{G3}/tie/decode-C0f/engine.stdout", f"{G3}/tie/decode-C1f/engine.stdout",
            f"{G3}/prep/converted.sha256", SNAP, f"{G2}/cfg-C0f.json", f"{G2}/cfg-C1f.json",
            f"{TC.G1}/kl/base/score.tsv", f"{G2}/kl-noise/Aa/score.tsv", f"{G2}/kl-noise/Ab/score.tsv",
            f"{SC}/configs/DS41-gate-C0.json", f"{SC}/configs/DS41-gate-C1.json", f"{SC}/configs/DS41-gate-C2.json",
            EXE, f"{os.path.dirname(EXE)}/SHA256", SERVER, f"{G}/cliarm.sh", f"{G}/greedy_client.py", f"{G}/greedy_compare.py",
            f"{G}/gate.sh", f"{G}/report.py", f"{SC}/work/ds41/tune/tunearm.sh", f"{SC}/work/r22/port_gap4.sh",
            f"{SC}/bringup/lib/kcheck.sh", f"{TC.TP}/vocab.json"]
    need += [f"{G2}/{n}/{f}" for n in ("C0f", "C1f", "C2f", "C0r") for f in ("greedy.jsonl", "engine-start.log")]
    miss = [f for f in need if not os.path.exists(f)]
    chk(f"{len(need)} files there", not miss, ", ".join(miss))
    if miss:
        return 1
    # the rule
    same, txt, p90, mx = rule_check()
    chk("the rule recomputed by tie_check.threshold() = the frozen 11-05 rule.txt, byte for byte", same,
        f"p90 {p90:.4f}, max {mx:.4f}")
    chk("p90 / max are 0.5883 / 4.3312 nats", abs(p90 - P90_FROZEN) < 5e-5 and abs(mx - MAX_FROZEN) < 5e-5)
    import hashlib
    chk("the profile snapshot is 11-04's", hashlib.sha256(open(SNAP, "rb").read()).hexdigest()[:16] == SNAP_SHA)
    # the prompt
    tok = TC.tokenizer()
    pids = TC.render(tok)
    chk("G-P4K0 renders to 4,115 ids = 11-05's prompt.ids", len(pids) == 4115
        and ",".join(map(str, pids)) == open(f"{G3}/tie/prompt.ids").read().strip())
    # 11-04's served texts
    t = {n: texts_of(f"{G2}/{n}") for n in ("C0f", "C1f", "C2f", "C0r")}
    chk("11-04 served arms answered G-W1, G-W2, G-P4K0 in that order", all(o == list(PROMPTS) for _, o in t.values()))
    t = {n: x[0] for n, x in t.items()}
    chk("11-04: C1f and C2f leave C0f on G-P4K0 at char 126",
        first_div(t["C0f"]["G-P4K0"], t["C1f"]["G-P4K0"]) == CHAR_1104 == first_div(t["C0f"]["G-P4K0"], t["C2f"]["G-P4K0"]))
    chk("11-04: G-W1 / G-W2 identical in C0f / C1f; C0r = C0f on all three",
        all(t["C0f"][p] == t["C1f"][p] for p in PROMPTS[:2]) and all(t["C0f"][p] == t["C0r"][p] for p in PROMPTS))
    # 11-05's command-line decodes (the record: no divergence within 512 tokens)
    c0, c1 = TC.gen_ids(f"{G3}/tie/decode-C0f"), TC.gen_ids(f"{G3}/tie/decode-C1f")
    chk("11-05 command line: 512 generated ids each", len(c0) == 512 == len(c1), f"{len(c0)} / {len(c1)}")
    chk("11-05 command line: C0f's text reproduces 11-04's served C0f text", related(tok.decode(c0), t["C0f"]["G-P4K0"]))
    chk("11-05 command line: C1f's 512 ids = C0f's (C1f did not leave C0f within 512 tokens)", c0 == c1 and len(c0) == 512)
    k = next((x for x in range(1, len(c0) + 1) if len(tok.decode(c0[:x])) > CHAR_1104), None)
    print(f"     (char 126 of the served texts falls in generated token {None if k is None else k - 1}: "
          f"{tok.decode(c0[max(0, (k or 1) - 4):k or 1])!r} - the j a reproduced served divergence should give)")
    chk("11-05 command line: C1f's text is not 11-04's served C1f text", not related(tok.decode(c1), t["C1f"]["G-P4K0"]))
    # the configs
    for n, src in (("C0f", "DS41-gate-C0"), ("C1f", "DS41-gate-C1")):
        c, diffs = derive(f"{SC}/configs/{src}.json", n, None, f"{SC}/logs/ds41/gate-slots/ctie-{n}", write=False)
        chk(f"derive {n} from configs/{src}.json = 11-04's cfg-{n}.json but for its own slot folder", not diffs, str(diffs))
        chk(f"  {n}: --no-expert-cache, --dspark {'off' if n == 'C0f' else 'on, --dspark-block 1'}, own slot folder ctie-{n}",
            "--no-expert-cache" in c["args"] and c["args"][c["args"].index("--dspark") + 1] == ("off" if n == "C0f" else "on")
            and (n == "C0f" or c["args"][c["args"].index("--dspark-block") + 1] == "1")
            and c["env"]["STRATA_DS4_SLOT_DIR"].endswith(f"/gate-slots/ctie-{n}") and c["exe"] == EXE)
    # the engine and the server
    b = binary_bytes()
    chk("the engine's sha256 = its SHA256 file", hashlib.sha256(b).hexdigest() == open(f"{os.path.dirname(EXE)}/SHA256").read().split()[0])
    chk("the engine binary has no STRATA_DEBUG string (the served arms' one addition is not read by it)", b"STRATA_DEBUG" not in b)
    chk("the engine binary reads DS4_SCORE_PREFIX (the scorings' key)", b"DS4_SCORE_PREFIX" in b)
    srv = open(SERVER).read()
    chk("server.py prints each request's generated ids under STRATA_DEBUG",
        'if os.environ.get("STRATA_DEBUG") and raw_ids:' in srv and 'print(f"[strata] raw ids: {list(raw_ids)}", flush=True)' in srv)
    chk("server.py reads STRATA_DEBUG only for prints (2 places)", srv.count('os.environ.get("STRATA_DEBUG")') == 2)
    ta = open(f"{SC}/work/ds41/tune/tunearm.sh").read()
    chk("tunearm.sh takes SERVER_ENV and CLIENT", "${SERVER_ENV:-}" in ta and 'bash -c "$CLIENT"' in ta)
    gs = open(f"{G}/gate.sh").read()
    chk("gate.sh has csample with GATE_STEPS / GATE_IN_GAP / GATE_OUT / GATE_DEADLINE_MIN",
        all(x in gs for x in ("csample)", "GATE_STEPS", "GATE_IN_GAP", "GATE_OUT", "GATE_DEADLINE_MIN")))
    # synthetic: the id parser, the divergence finder
    os.makedirs(f"{SCRATCH}/selftest", exist_ok=True)
    so = f"{SCRATCH}/selftest/server.out"
    open(so, "w").write("[strata] done: 3 tokens\n[strata] raw: 'abc'\n[strata] raw ids: [1, 2, 3]\nnoise\n"
                        "[strata] raw ids: [4]\n[strata] raw ids: [5, 6]\n")
    chk("synthetic: the raw-id parser", raw_ids(so) == [[1, 2, 3], [4], [5, 6]])
    chk("synthetic: the divergence finder", first_div([1, 2, 3, 4], [1, 2, 9, 4]) == 2 and first_div([1, 2], [1, 2]) is None
        and first_div("Version 2.0 text", "Version 2.0 terms") == 14 and first_div([1, 2], [1, 2, 3]) == 2)
    # synthetic: the env check
    c1 = derive(f"{SC}/configs/DS41-gate-C1.json", "C1f", None, f"{SC}/logs/ds41/gate-slots/ctie-C1f", write=False)[0]
    env = {**{k: str(v) for k, v in c1["env"].items()}, "STRATA_DEBUG": "1", "PATH": "/usr/bin", "HOME": "/home/USER"}
    av = [EXE, "--serve", *c1["args"]]
    chk("synthetic env: the served engine as configured -> OK", env_bad(env, av, c1, "served", SERVED_EXTRA, b) [0] == [])
    e2 = dict(env); e2.pop("DS4_SPLIT")
    chk("synthetic env: a config key missing -> MISMATCH", env_bad(e2, av, c1, "served", SERVED_EXTRA, b)[0] != [])
    e2 = dict(env, DS4_SPLIT="8,32")
    chk("synthetic env: a config key changed -> MISMATCH", env_bad(e2, av, c1, "served", SERVED_EXTRA, b)[0] != [])
    e2 = dict(env, DS4_FLOW_STATS="1")
    chk("synthetic env: a stray key the engine reads -> MISMATCH", env_bad(e2, av, c1, "served", SERVED_EXTRA, b)[0] != [])
    e2 = dict(env, STRATA_NOT_A_SWITCH_ZZ="1")
    bd, nt = env_bad(e2, av, c1, "served", SERVED_EXTRA, b)
    chk("synthetic env: a stray key the engine cannot read -> a note only", bd == [] and any("not read" in x for x in nt))
    e2 = dict(env); e2.pop("STRATA_DEBUG")
    chk("synthetic env: STRATA_DEBUG missing on a served engine -> MISMATCH", env_bad(e2, av, c1, "served", SERVED_EXTRA, b)[0] != [])
    a2 = list(av); a2[a2.index("--dspark") + 1] = "off"
    chk("synthetic env: argv not the config's -> MISMATCH", env_bad(env, a2, c1, "served", SERVED_EXTRA, b)[0] != [])
    ca = ("--score", "x.json", "--score-out", "x.tsv", "--window", "1")
    ec = {k: v for k, v in env.items() if k != "STRATA_DEBUG"}
    ec["DS4_SCORE_PREFIX"] = "4115"
    cav = [EXE, *c1["args"], "--vision", "off", *ca]
    chk("synthetic env: a scoring engine as cliarm.sh starts it -> OK",
        env_bad(ec, cav, c1, "cli", {"DS4_SCORE_PREFIX": "4115"}, b, ca)[0] == [])
    chk("synthetic env: the scoring's DS4_SCORE_PREFIX wrong -> MISMATCH",
        env_bad(dict(ec, DS4_SCORE_PREFIX="4116"), cav, c1, "cli", {"DS4_SCORE_PREFIX": "4115"}, b, ca)[0] != [])
    # synthetic: the verdict
    P, j, i0, alt = 10, 3, [100, 101, 102, 103, 104, 105], 200

    def runs_with(top_at_j, extra_rows=True):
        w = {P + 0: (101, -0.1, 101, [(101, -0.1), (7, -3.0)]), P + 1: (102, -0.2, 102, [(102, -0.2), (8, -2.0)])}
        if top_at_j is not None:
            w[P + 2] = (103, top_at_j[0][1], top_at_j[0][0], top_at_j)
        return {"w1": w, "w2a": dict(w), "w2b": dict(w)} if extra_rows else {"w1": w}
    rc, o = verdict(runs_with([(103, -0.1), (200, -0.4), (9, -5.0)]), P, j, i0, alt, p90, mx)
    chk("synthetic verdict: gap 0.30 -> 0 (within rounding)", rc == 0 and o["within_rounding"] and o["within_rounding_under_max"]
        and o["window1_reproduces_c0f_path"] and abs(o["at_j"]["w1"]["gap_c0f_minus_c1f"] - 0.3) < 1e-9)
    rc, o = verdict(runs_with([(103, -0.1), (200, -1.1), (9, -5.0)]), P, j, i0, alt, p90, mx)
    chk("synthetic verdict: gap 1.00 -> 1 (not within; within the max, reported)", rc == 1 and o["within_rounding_under_max"] is True)
    rc, o = verdict(runs_with([(103, -0.1), (200, -5.1), (9, -9.0)]), P, j, i0, alt, p90, mx)
    chk("synthetic verdict: gap 5.00 -> 1 (not within, not under the max)", rc == 1 and o["within_rounding_under_max"] is False)
    rc, o = verdict(runs_with([(103, -0.1), (9, -0.3)]), P, j, i0, alt, p90, mx)
    chk("synthetic verdict: C1f's token outside the top-64, bound 0.20 -> 2 (no verdict)", rc == 2)
    rc, o = verdict(runs_with([(103, -0.1), (9, -6.0)]), P, j, i0, alt, p90, mx)
    chk("synthetic verdict: C1f's token outside the top-64, bound 5.9 -> 1", rc == 1)
    rc, o = verdict(runs_with(None), P, j, i0, alt, p90, mx)
    chk("synthetic verdict: no window-1 row at j -> 2 (no verdict)", rc == 2)
    rc, o = verdict(runs_with([(200, -0.1), (103, -0.2)]), P, j, i0, alt, p90, mx)
    chk("synthetic verdict: window 1 picks C1f's token at j -> gap -0.10, 0, window 1 does not reproduce C0f (reported)",
        rc == 0 and o["window1_reproduces_c0f_path"] is False)
    print("SELFTEST " + ("OK" if ok[0] else "FAILED"))
    return 0 if ok[0] else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    mode, av = sys.argv[1], sys.argv[2:]
    f = {"selftest": cmd_selftest, "derive": cmd_derive, "rule": cmd_rule, "envcheck": cmd_envcheck, "judge": cmd_judge}.get(mode)
    if not f:
        print(f"unknown mode {mode}"); return 2
    return f(av)


if __name__ == "__main__":
    # tie_check.py's 11-05 lesson: a crash exits 2 ("could not run"), never 1 (read as "not within rounding"); for the
    # other modes 1 = not OK
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.exit(2 if sys.argv[1:2] == ["judge"] else 1)
