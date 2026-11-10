#!/usr/bin/env python3
"""af_adopt.py - Karl 11-09 (after the ADAPT_FETCH gap): "ADAPT_FETCH: make =2 the daily, as a recorded owner exception
to the prompt no-loss rule. [...] Outside a gap, one restart: 1. Back up the config with a date. 2. Point P028x at the
fetch build's engine and add STRATA_ADAPT_FETCH=2. 3. Run exact7 and the short speed check, and tell me the result.
Keep a ready =1 config as the fallback. Give me the one-command rollback."

The config steps and checks of work/r23/afetch-adopt/gap-afetch-adopt.sh (CPU only, no GPU, no server started). The
change is exactly the gap's F2 arm: exe engine-r22p028x/strata -> engine-r23afetch/strata, env STRATA_ADAPT_FETCH="2".
  plan P028X GAPCFG BACKUP   before the gap: the guard key and STRATA_HC_UPMIX=1 are in P028X; either P028X is as the
                             gap measured it (sha256 = the gap manifest's base_sha256, engine-r22p028x, no switch) or
                             a rerun (P028X = BACKUP + the change, exactly); P028X + the change without the picture
                             reader / fallback / guard key = the gap's F2.json key by key (_comment and log aside)
  fallback P028X GAPCFG FB [BACKUP [VAL]]
                             a ready config FB = P028X's form before the edit (P028X itself, or a rerun's BACKUP) + the
                             change with STRATA_ADAPT_FETCH=VAL (default "1": the =1 fallback; "2": a copy of the adopted
                             daily, for served-afetch.sh afetch2); its engine form = the gap's F<VAL>.json; never served
                             here (not a *.json name, so no launcher reads it)
  edit P028X BACKUP          BACKUP = a copy of P028X (made when absent; when present it must equal P028X), then exe and
                             env STRATA_ADAPT_FETCH="2" and nothing else (checked against BACKUP), written atomically
  derive P028X GAPCFG S2 S0 LOGDIR
                             the test configs: S2 = P028X without --vision / vision / fallback / the guard key, its own
                             log (= the gap's F2.json); S0 = S2 without STRATA_ADAPT_FETCH (= the gap's F0.json)
  restore P028X BACKUP [GAPCFG]  BACKUP back (P028x as before: engine-r22p028x, U, the guard, no switch); with GAPCFG only
                             when BACKUP's sha256 is the gap manifest's base_sha256 (the file the gap measured from)
  speed BP90 GAPBP UBP MORNING
                             the short speed check: S2's one pass of pp16k / pp64k / decode. pp16k / pp64k against this
                             morning's PU (= P028x + U as served until now; median of 3 passes) and P, and the U
                             adoption's own S pass; decode against the ADAPT_FETCH gap's P and F2 (median of 3 passes).
                             FLAG when S2 is more than 3 % below PU on pp16k or pp64k (reported; Karl decides)
  served URL MODEL           after the restart: a request naming DeepSeek's model gets the guard's 400 and its text; one
                             short chat answers (T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05)
  selftest DIR               the steps above on synthetic files inside DIR
"""
import copy
import hashlib
import json
import os
import shutil
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

KEY, VAL, VAL_FB = "STRATA_ADAPT_FETCH", "2", "1"
WS = "/home/USER/ai-speed-testing/strata-compare"
E28 = f"{WS}/engine-r22p028x/strata"
EAF = f"{WS}/engine-r23afetch/strata"
UKEY = "STRATA_HC_UPMIX"
GUARD = "model_not_running"
DS_MODEL = "deepseek-v4.1-flash"
GUARD_TEXT = "DeepSeek isn't running"
NOT_ENGINE = ("vision", "fallback", GUARD)
IGNORE = ("_comment", "log")
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
FLAG_PCT = 3.0


def load(p):
    return json.loads(Path(p).read_text())


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(p, d, like):
    raw = Path(like).read_text() if Path(like).exists() else "\n"
    tmp = Path(str(p) + ".new")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""))
    json.loads(tmp.read_text())
    os.replace(tmp, p)


def changed(d, val=VAL, exe=None):
    n = copy.deepcopy(d)
    n["exe"] = exe or EAF   # (read at call time: the selftest swaps EAF)
    n.setdefault("env", {})[KEY] = val
    return n


def strip_engine(d, log=None):
    s = copy.deepcopy(d)
    s["args"] = [x for x in s.get("args", []) if x != "--vision"]
    for k in NOT_ENGINE:
        s.pop(k, None)
    if log is not None:
        s["log"] = str(log)
    return s


def diff_vs(s, ref):
    return sorted(k for k in set(s) | set(ref) if k not in IGNORE and s.get(k) != ref.get(k))


def envdiff(a, b):
    ea, eb = a.get("env", {}), b.get("env", {})
    return sorted(k for k in set(ea) | set(eb) if ea.get(k) != eb.get(k))


def is_before(d):
    return d.get("exe") == E28 and KEY not in d.get("env", {})


def is_after_of(d, old):
    return is_before(old) and changed(old) == d


def plan(p028x, gapcfg, backup):
    d, why, b, g = load(p028x), [], Path(backup), Path(gapcfg)
    if GUARD not in d:
        why.append("the guard key is not in P028x.json")
    elif GUARD_TEXT not in str((d.get(GUARD) or {}).get(DS_MODEL, "")):
        why.append(f"the guard key has no {DS_MODEL} entry with the text the served check looks for")
    if d.get("env", {}).get(UKEY) != "1":
        why.append(f"P028x.json has no {UKEY}=1 (the gap measured P028x with U)")
    man = load(g / "manifest.json")
    want_sha = man["F2"]["base_sha256"]
    if man["F0"]["base_sha256"] != want_sha or man["F1"]["base_sha256"] != want_sha:
        why.append("the gap manifest's arms have different bases")
    if Path(man["F2"]["exe"]) != Path(EAF) or man["F2"]["env"] != {KEY: VAL}:
        why.append(f"the gap's F2 arm is not {EAF} + {KEY}={VAL}")
    if is_before(d):
        state, base = "the switch to be added", d
        if sha256(p028x) != want_sha:
            why.append(f"P028x.json (sha {sha256(p028x)[:12]}) is not the file the gap measured from ({want_sha[:12]})")
        if b.exists() and b.read_bytes() != Path(p028x).read_bytes():
            why.append(f"the backup {b.name} exists and is not P028x.json as it is now")
    elif d.get("exe") == EAF and d.get("env", {}).get(KEY) == VAL:
        state, base = "rerun: the switch already set", None
        if not b.exists():
            why.append(f"P028x.json already has the change but there is no backup {b.name}")
        else:
            base = load(b)
            if not is_after_of(d, base):
                why.append(f"P028x.json differs from {b.name} by more than the change (exe + {KEY}={VAL})")
            if sha256(b) != want_sha:
                why.append(f"the backup {b.name} is not the file the gap measured from")
    else:
        state, base = "?", None
        why.append(f"P028x.json is neither as the gap measured it nor the adopted form (exe {d.get('exe')}, "
                   f"{KEY}={d.get('env', {}).get(KEY)!r})")
    if base is not None:
        bad = diff_vs(strip_engine(changed(base)), load(g / "F2.json"))
        if bad:
            why.append("P028x.json + the change without the picture reader is not the gap's F2.json in: " + ", ".join(bad)
                       + (f" (env: {', '.join(envdiff(strip_engine(changed(base)), load(g / 'F2.json')))})" if "env" in bad else ""))
    return why, state


def fallback(p028x, gapcfg, fb1, backup=None, val=VAL_FB):
    d = load(p028x)
    if is_before(d):
        base = d
    elif backup and Path(backup).exists() and is_after_of(d, load(backup)):
        base = load(backup)
    else:
        raise SystemExit("FAIL: P028x.json is neither as the gap measured it nor the adopted form - no fallback written")
    if val not in ("1", "2"):
        raise SystemExit(f"FAIL: STRATA_ADAPT_FETCH={val!r}: only 1 or 2")
    f = changed(base, val)
    bad = diff_vs(strip_engine(f), load(Path(gapcfg) / f"F{val}.json"))
    if bad:
        raise SystemExit(f"FAIL: the ={val} config without the picture reader is not the gap's F{val}.json in: " + ", ".join(bad))
    p = Path(fb1)
    if p.exists():
        if load(p) != f:
            raise SystemExit(f"FAIL: {p.name} exists and is not the ={val} form of P028x.json - nothing written")
        return f"fallback: {p.name} already in place (= the gap's F{val} form + the picture reader, U, the guard)"
    write_json(p, f, p028x)
    if load(p) != f:
        raise SystemExit("FAIL: the fallback's re-read differs")
    return f"fallback: {p.name} written (= P028x.json + engine-r23afetch + {KEY}={val}; the gap's F{val} form)"


def edit(p028x, backup):
    p, b = Path(p028x), Path(backup)
    cur = load(p)
    if cur.get("exe") == EAF and cur.get("env", {}).get(KEY) == VAL:
        if not b.exists():
            raise SystemExit(f"FAIL: {p.name} already has the change but there is no backup {b.name}")
        if not is_after_of(cur, load(b)):
            raise SystemExit(f"FAIL: {p.name} differs from {b.name} by more than the change")
        return "already: the change in place, the backup in place"
    if not is_before(cur):
        raise SystemExit(f"FAIL: {p.name} is not P028x as the gap measured it (exe / {KEY}) - nothing changed")
    if b.exists():
        if b.read_bytes() != p.read_bytes():
            raise SystemExit(f"FAIL: the backup {b.name} exists and is not {p.name} as it is now - nothing changed")
    else:
        shutil.copy2(p, b)
        if b.read_bytes() != p.read_bytes():
            raise SystemExit("FAIL: the backup copy does not match")
    new = changed(cur)
    try:
        write_json(p, new, p)
        got, old = load(p), load(b)
    except Exception as e:      # the file may already be rewritten: the driver restores the backup on FAIL-WRITTEN
        raise SystemExit(f"FAIL-WRITTEN: the write or its re-read failed ({type(e).__name__}: {e})")
    if not is_after_of(got, old):
        raise SystemExit(f"FAIL-WRITTEN: after the edit P028x.json differs from the backup by more than exe + {KEY}")
    return f"edited: exe engine-r23afetch/strata, env {KEY}={VAL} added ({len(got['env'])} env keys), backup {b.name}"


def derive(p028x, gapcfg, s2, s0, logdir):
    d = load(p028x)
    if not (d.get("exe") == EAF and d.get("env", {}).get(KEY) == VAL):
        raise SystemExit("FAIL: P028x.json does not have the change")
    g = Path(gapcfg)
    a = strip_engine(d, Path(logdir) / "engine-r23aa-S2.log")
    a["_comment"] = "11-09 ADAPT_FETCH=2 adoption check (work/r23/afetch-adopt): configs/P028x.json as adopted, without the picture reader"
    bad = diff_vs(a, load(g / "F2.json"))
    if bad:
        raise SystemExit("FAIL: S2 is not the gap's F2.json in: " + ", ".join(bad))
    z = copy.deepcopy(a)
    del z["env"][KEY]
    z["log"] = str(Path(logdir) / "engine-r23aa-S0.log")
    z["_comment"] = "11-09 ADAPT_FETCH adoption check: S2 with the switch unset (the build-vs-switch exact7)"
    bad = diff_vs(z, load(g / "F0.json"))
    if bad:
        raise SystemExit("FAIL: S0 is not the gap's F0.json in: " + ", ".join(bad))
    write_json(s2, a, p028x)
    write_json(s0, z, p028x)
    return "S2 = configs/P028x.json (adopted) without the picture reader = the gap's F2.json; S0 = S2 without the switch = F0.json: OK"


def restore(p028x, backup, gapcfg=None):
    if gapcfg is not None:   # (review 11-09 A) only the file the gap measured from goes back - never a partial or wrong copy
        want = load(Path(gapcfg) / "manifest.json")["F2"]["base_sha256"]
        if not Path(backup).exists() or sha256(backup) != want:
            raise SystemExit(f"FAIL: the backup {Path(backup).name} is not the file the gap measured from ({want[:12]}) - not restored")
    tmp = Path(str(p028x) + ".restore")
    shutil.copy2(backup, tmp)
    os.replace(tmp, p028x)
    if Path(p028x).read_bytes() != Path(backup).read_bytes():
        raise SystemExit("FAIL: the restore did not take")
    return "restored: P028x.json = its backup (engine-r22p028x, U, the guard, no switch)"


def recs(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def med_prompt(d, arm, st, passes=(1, 2, 3)):
    v = [r["prompt_tps"] for k in passes for r in recs(Path(d) / f"{arm}-{st}-{k}.jsonl") if r.get("prompt_tps")]
    return statistics.median(v) if v else None


def med_decode(d, arm):
    by = {}
    for k in (1, 2, 3):
        for r in recs(Path(d) / f"{arm}-decode-{k}.jsonl"):
            if r.get("decode_tps"):
                by.setdefault(r["test"], []).append(r["decode_tps"])
    return {t: statistics.median(v) for t, v in by.items()}


def pct(a, b):
    return 100 * (a / b - 1)


def speed(bp90, gapbp, ubp, morning):
    out, flags = [], []
    for st in ("pp16k", "pp64k"):
        s = [r["prompt_tps"] for r in recs(Path(bp90) / f"S2-{st}-1.jsonl") if r.get("prompt_tps")]
        if not s:
            out.append(f"{st}: S2 not measured")
            flags.append(f"{st} missing")
            continue
        line = f"{st}: S2 {s[0]:,.1f} tok/s"
        ref = {arm: med_prompt(morning, arm, st) for arm in ("PU", "P")}
        for arm in ("PU", "P"):
            if ref[arm]:
                line += f"; vs this morning's {arm} {ref[arm]:,.1f} ({pct(s[0], ref[arm]):+.1f} %)"
        u = med_prompt(ubp, "S", st, (1,))
        if u:
            line += f"; vs the U adoption's check {u:,.1f} ({pct(s[0], u):+.1f} %)"
        if not ref["PU"]:
            flags.append(f"{st}: no PU reference")
        elif pct(s[0], ref["PU"]) < -FLAG_PCT:
            flags.append(f"{st} {pct(s[0], ref['PU']):+.1f} % vs PU")
        out.append(line)
    sd = {r["test"]: r.get("decode_tps") for r in recs(Path(bp90) / "S2-decode-1.jsonl")}
    if not sd:
        out.append("decode: S2 not measured")
        flags.append("decode missing")
    else:
        ref = {arm: med_decode(gapbp, arm) for arm in ("P", "F2")}
        parts, gp, gf = [], [], []
        for t in ("conv", "struct", "prose"):
            v = sd.get(t)
            if not v:
                parts.append(f"{t} -")
                continue
            q = f"{t} {v:.1f}"
            for arm in ("P", "F2"):
                if ref[arm].get(t):
                    q += f" ({'gap P' if arm == 'P' else 'gap F2'} {ref[arm][t]:.1f}, {pct(v, ref[arm][t]):+.1f} %)"
            if ref["P"].get(t):
                gp.append(v / ref["P"][t])
            if ref["F2"].get(t):
                gf.append(v / ref["F2"][t])
            parts.append(q)
        gm = lambda xs: 100 * (statistics.geometric_mean(xs) - 1) if xs else None
        tail = ""
        if gp:
            tail += f"; geomean vs gap P {gm(gp):+.1f} %"
        if gf:
            tail += f", vs gap F2 {gm(gf):+.1f} %"
        out.append("decode tok/s (1 pass, sampled, noise 4-7 %): " + "; ".join(parts) + tail)
    out.append("SPEED " + ("FLAG: " + ", ".join(flags) if flags else "OK (no prompt set more than 3 % below P028x + U)"))
    return out


def post(url, body, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 127.0.0.1 only, never a proxy
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode(errors="replace") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw[:300]}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 0, {"error": f"{type(e).__name__}: {str(e)[:200]}"}


def served(url, model):
    out, ok = [], True
    msg = [{"role": "user", "content": "Reply with the single word OK."}]
    code, j = post(f"{url}/v1/chat/completions", {"model": DS_MODEL, "messages": msg, "max_tokens": 16, **SAMPLING}, 60)
    text = json.dumps(j)[:300]
    g = code == 400 and GUARD_TEXT in text
    ok &= g
    out.append(f"guard: a request naming {DS_MODEL} -> HTTP {code} {'with the guard text: PASS' if g else '(want 400 + the guard text): FAIL ' + text[:160]}")
    code, j = post(f"{url}/v1/chat/completions", {"model": model, "messages": msg, "max_tokens": 1024, **SAMPLING}, 300)
    u = j.get("usage", {}) if isinstance(j, dict) else {}
    ch = (j.get("choices") or [{}])[0] if isinstance(j, dict) else {}
    c = code == 200 and (u.get("completion_tokens") or 0) > 0
    ok &= c
    ans = ((ch.get("message") or {}).get("content") or "").strip().replace("\n", " ")[:40]
    out.append(f"chat: HTTP {code}, {u.get('completion_tokens')} tokens, finish {ch.get('finish_reason')}, answer {ans!r}: {'PASS' if c else 'FAIL'}")
    out.append("SERVED " + ("PASS" if ok else "FAIL"))
    return out, ok


def selftest(d):
    global E28, EAF
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    n = [0, 0]

    def chk(name, cond):
        n[0] += 1
        n[1] += 0 if cond else 1
        print(("ok   " if cond else "FAIL ") + name)

    E28, EAF = "/e28/strata", "/eaf/strata"
    env = {"STRATA_ROUTE_TAIL_SKIP": "0", UKEY: "1", "STRATA_DISJOINT_ADAPT": "1"}
    p = {"exe": E28, "args": ["--serve", "--vision", "--kv-resident", "32768"], "env": dict(env), "log": "/l/P.log",
         "vision": {"exe": "v"}, "fallback": "/c/f.json", GUARD: {DS_MODEL: "DeepSeek isn't running - use the icon"}, "_comment": "p"}
    P, B, FB, S2, S0 = d / "P028x.json", d / "P028x.json.before-afetch2-test", d / "P028x.json.afetch1-test", d / "S2.json", d / "S0.json"
    G = d / "gap"
    G.mkdir(exist_ok=True)
    for f in (P, B, FB, S2, S0):
        f.unlink(missing_ok=True)
    P.write_text(json.dumps(p, indent=1) + "\n")
    base = strip_engine(p)
    for arm, e in (("F0", {}), ("F1", {KEY: "1"}), ("F2", {KEY: "2"})):
        f = copy.deepcopy(base)
        f["exe"] = EAF
        f["env"].update(e)
        f["log"], f["_comment"] = f"/l/{arm}.log", arm
        (G / f"{arm}.json").write_text(json.dumps(f, indent=1) + "\n")
    man = {a: {"exe": EAF, "env": e, "base_sha256": sha256(P)} for a, e in (("F0", {}), ("F1", {KEY: "1"}), ("F2", {KEY: "2"}))}
    (G / "manifest.json").write_text(json.dumps(man) + "\n")
    why, st = plan(P, G, B)
    chk("plan OK as the gap measured it", why == [] and st == "the switch to be added")
    chk("fallback written (= F1 form)", fallback(P, G, FB).startswith("fallback: ") and load(FB)["env"][KEY] == "1" and load(FB)["exe"] == EAF)
    chk("fallback again = in place", "already in place" in fallback(P, G, FB))
    before = P.read_bytes()
    r = edit(P, B)
    chk("edit: exe + switch", r.startswith("edited") and load(P)["env"][KEY] == VAL and load(P)["exe"] == EAF and B.read_bytes() == before)
    chk("edit changes nothing else", changed(load(B)) == load(P))
    chk("edit again = already", edit(P, B).startswith("already"))
    chk("plan after the edit = a rerun", plan(P, G, B) == ([], "rerun: the switch already set"))
    chk("fallback after the edit (from the backup) = in place", "already in place" in fallback(P, G, FB, B))
    F2C = d / "P028x.json.afetch2-test"
    F2C.unlink(missing_ok=True)
    chk("the =2 copy from the backup = the edited file", fallback(P, G, F2C, B, "2").startswith("fallback: ") and load(F2C) == load(P))
    chk("plan refuses the change with no backup", any("no backup" in w for w in plan(P, G, d / "no-such-backup")[0]))
    r = derive(P, G, S2, S0, d)
    a, z = load(S2), load(S0)
    chk("derive: S2 = F2 form, own log", "--vision" not in a["args"] and not any(k in a for k in NOT_ENGINE)
        and a["log"].endswith("S2.log") and a["env"][KEY] == VAL and a["exe"] == EAF)
    chk("derive: S0 = S2 without the switch", KEY not in z["env"] and z["exe"] == EAF and z["log"].endswith("S0.log"))
    f2 = load(G / "F2.json")
    f2["env"]["STRATA_OTHER"] = "1"
    (G / "F2.json").write_text(json.dumps(f2, indent=1) + "\n")
    try:
        derive(P, G, S2, S0, d)
        chk("derive refuses another env difference", False)
    except SystemExit as e:
        chk("derive refuses another env difference", "env" in str(e))
    chk("plan refuses another env difference", any("F2.json in: env" in w for w in plan(P, G, B)[0]))
    del f2["env"]["STRATA_OTHER"]
    (G / "F2.json").write_text(json.dumps(f2, indent=1) + "\n")
    f0 = load(G / "F0.json")
    f0["env"]["STRATA_ADAPT_FETCH"] = "1"
    (G / "F0.json").write_text(json.dumps(f0, indent=1) + "\n")
    try:
        derive(P, G, S2, S0, d)
        chk("derive refuses S0 unlike F0.json", False)
    except SystemExit as e:
        chk("derive refuses S0 unlike F0.json", "S0 is not" in str(e))
    del f0["env"]["STRATA_ADAPT_FETCH"]
    (G / "F0.json").write_text(json.dumps(f0, indent=1) + "\n")
    odd = d / "P028x.json.afetch1-odd"
    odd.write_text(json.dumps({"exe": "/x"}) + "\n")
    try:
        fallback(P, G, odd, B)
        chk("fallback refuses an existing different file", False)
    except SystemExit as e:
        chk("fallback refuses an existing different file", "nothing written" in str(e) and load(odd) == {"exe": "/x"})
    chk("plan (rerun) refuses a backup the gap did not measure", any("not the file the gap measured" in w for w in plan(P, G, odd)[0])
        or any("differs from" in w for w in plan(P, G, odd)[0]))
    chk("restore", restore(P, B, G).startswith("restored") and P.read_bytes() == before)
    bad_b = d / "P028x.json.before-afetch2-bad"
    bad_b.write_text("{\"exe\": \"/x\"\n")
    try:
        restore(P, bad_b, G)
        chk("restore refuses a backup the gap did not measure", False)
    except SystemExit as e:
        chk("restore refuses a backup the gap did not measure", "not restored" in str(e) and P.read_bytes() == before)
    q = copy.deepcopy(p)
    q["env"]["STRATA_X"] = "1"
    P.write_text(json.dumps(q, indent=1) + "\n")
    chk("plan refuses a file the gap did not measure (sha)", any("is not the file the gap measured" in w for w in plan(P, G, d / "nb")[0]))
    try:
        edit(P, B)
        chk("edit refuses when the backup is not the current file", False)
    except SystemExit as e:
        chk("edit refuses when the backup is not the current file", "nothing changed" in str(e) and KEY not in load(P)["env"])
    q2 = copy.deepcopy(p)
    q2["env"][KEY] = "1"
    P.write_text(json.dumps(q2, indent=1) + "\n")
    chk("plan refuses another switch value", any("neither" in w for w in plan(P, G, B)[0]))
    q3 = copy.deepcopy(p)
    del q3["env"][UKEY]
    P.write_text(json.dumps(q3, indent=1) + "\n")
    chk("plan refuses no U", any(UKEY in w for w in plan(P, G, d / "nb")[0]))
    q4 = copy.deepcopy(p)
    del q4[GUARD]
    P.write_text(json.dumps(q4, indent=1) + "\n")
    chk("plan refuses no guard key", any("guard key" in w for w in plan(P, G, d / "nb")[0]))
    P.write_bytes(before)
    bp, gb, ub, mo = d / "bp90", d / "gapbp", d / "ubp", d / "morning"
    for x in (bp, gb, ub, mo):
        x.mkdir(exist_ok=True)
    for arm, b0 in (("P", 3850.0), ("PU", 3975.0)):
        for k in (1, 2, 3):
            (mo / f"{arm}-pp16k-{k}.jsonl").write_text(json.dumps({"test": "pp16k", "prompt_tps": b0 + k}) + "\n")
            (mo / f"{arm}-pp64k-{k}.jsonl").write_text(json.dumps({"test": "pp64k", "prompt_tps": b0 + 500 + k}) + "\n")
    (ub / "S-pp16k-1.jsonl").write_text(json.dumps({"prompt_tps": 3930.0}) + "\n")
    (ub / "S-pp64k-1.jsonl").write_text(json.dumps({"prompt_tps": 4566.0}) + "\n")
    for arm, m in (("P", 1.0), ("F2", 1.1)):
        for k in (1, 2, 3):
            (gb / f"{arm}-decode-{k}.jsonl").write_text("".join(json.dumps({"test": t, "decode_tps": v * m + k}) + "\n"
                                                                 for t, v in (("conv", 140.0), ("struct", 225.0), ("prose", 130.0))))
    (bp / "S2-pp16k-1.jsonl").write_text(json.dumps({"prompt_tps": 3990.0}) + "\n")
    (bp / "S2-pp64k-1.jsonl").write_text(json.dumps({"prompt_tps": 4480.0}) + "\n")
    (bp / "S2-decode-1.jsonl").write_text("".join(json.dumps({"test": t, "decode_tps": v}) + "\n"
                                                  for t, v in (("conv", 156.0), ("struct", 250.0), ("prose", 145.0))))
    o = speed(bp, gb, ub, mo)
    chk("speed OK case", o[-1].startswith("SPEED OK") and "vs this morning's PU 3,977.0 (+0.3 %)" in o[0] and "vs gap P" in o[2])
    (bp / "S2-pp64k-1.jsonl").write_text(json.dumps({"prompt_tps": 4300.0}) + "\n")
    o = speed(bp, gb, ub, mo)
    chk("speed FLAG below PU by > 3 %", o[-1].startswith("SPEED FLAG") and "pp64k" in o[-1])
    (bp / "S2-decode-1.jsonl").unlink()
    chk("speed FLAG on a missing set", "decode missing" in speed(bp, gb, ub, mo)[-1])
    print(f"{n[0] - n[1]} / {n[0]} ok" + ("" if not n[1] else " - FAILED"))
    return 1 if n[1] else 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    c, a = argv[0], argv[1:]
    if c == "plan":
        why, st = plan(*a[:3])
        print("PLAN OK: " + st if not why else "PLAN REFUSED: " + "; ".join(why))
        return 0 if not why else 1
    if c in ("edit", "derive", "restore", "fallback"):
        try:
            print({"edit": edit, "derive": derive, "restore": restore, "fallback": fallback}[c](*a))
        except SystemExit as e:
            print(str(e))
            return 1
        return 0
    if c == "speed":
        print("\n".join(speed(*a[:4])))
        return 0
    if c == "served":
        lines, ok = served(*a[:2])
        print("\n".join(lines))
        return 0 if ok else 1
    if c == "selftest":
        return selftest(a[0])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
