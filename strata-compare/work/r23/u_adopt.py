#!/usr/bin/env python3
"""u_adopt.py - Karl 11-09: "U: adopt it today. After D2 and the end of the chain, put STRATA_HC_UPMIX=1 into P028x's
config together with the mismatch guard install, so it's one restart. Keep a dated backup of the config for rollback.
Run the usual post-restart checks (exact7 and the short speed check) and tell me the result."

The config steps and checks of work/r23/gap-u-adopt.sh (CPU only, no GPU, no server started):
  plan P028X X28H BACKUP     before the gap: the guard key is in P028X, its env has no STRATA_HC_UPMIX (or exactly "1":
                             a rerun), and P028X + U without the picture reader, the fallback and the guard key is
                             x28h.json + U key by key (so this morning's PU arm measured the same engine setup)
  edit P028X BACKUP          BACKUP = a copy of P028X (made when absent; when present it must equal P028X), then env
                             STRATA_HC_UPMIX="1" and nothing else (checked against BACKUP), written atomically, the
                             guard installer's form (indent 1)
  derive P028X X28H OUT LOG  the test config S: P028X without --vision / vision / fallback / the guard key, its own LOG;
                             checked against x28h.json + U
  restore P028X BACKUP       BACKUP back (P028x as before the edit: the guard kept, no U)
  speed BP90 MORNING         the short speed check: S's one pass of pp16k / pp64k / decode against this morning's P and PU
                             (median of their 3 passes for pp16k / pp64k, pass 1 for decode). FLAG when S is more than
                             3 % below P on pp16k or pp64k (reported, Karl decides; decode is within its noise of 4-7 %)
  served URL MODEL           after the restart: a request naming DeepSeek's model gets the guard's 400 and its text; one
                             short chat answers (T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05)
  selftest DIR               the steps above on synthetic files inside DIR
"""
import copy
import json
import os
import shutil
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

KEY, VAL = "STRATA_HC_UPMIX", "1"
GUARD = "model_not_running"
DS_MODEL = "deepseek-v4.1-flash"
GUARD_TEXT = "DeepSeek isn't running"            # what the guarded server answers (install-model-guard.sh's text)
NOT_ENGINE = ("vision", "fallback", GUARD)          # server-side parts S leaves out (x28h has none of them)
IGNORE = ("_comment", "log")                        # differ by design between S and x28h
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
FLAG_PCT = 3.0


def load(p):
    return json.loads(Path(p).read_text())


def write_json(p, d, like):
    raw = Path(like).read_text() if Path(like).exists() else "\n"
    tmp = Path(str(p) + ".new")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""))
    json.loads(tmp.read_text())
    os.replace(tmp, p)


def strip_engine(d, log=None):
    s = copy.deepcopy(d)
    s["args"] = [x for x in s.get("args", []) if x != "--vision"]
    for k in NOT_ENGINE:
        s.pop(k, None)
    if log is not None:
        s["log"] = str(log)
    return s


def diff_vs_x28h(s, x28h):
    x = copy.deepcopy(x28h)
    x["env"] = dict(x.get("env", {}), **{KEY: VAL})
    return sorted(k for k in set(s) | set(x) if k not in IGNORE and s.get(k) != x.get(k))


def plan(p028x, x28h, backup):
    d, why, b = load(p028x), [], Path(backup)
    if GUARD not in d:
        why.append("the guard key is not in P028x.json (the guard install has not run)")
    elif GUARD_TEXT not in str((d.get(GUARD) or {}).get(DS_MODEL, "")):
        why.append(f"the guard key has no {DS_MODEL} entry with the text the served check looks for")
    v = d.get("env", {}).get(KEY)
    if v not in (None, VAL):
        why.append(f"P028x.json already sets {KEY}={v!r}")
    if v is None and b.exists() and load(b) != d:
        why.append(f"the backup {b.name} exists and is not P028x.json as it is now")
    if v == VAL:
        if not b.exists():
            why.append(f"P028x.json has {KEY}={VAL} but there is no backup {b.name}")
        else:
            old = load(b)
            if old.get("env", {}).get(KEY) is not None or {**old, "env": {**old.get("env", {}), KEY: VAL}} != d:
                why.append(f"P028x.json has {KEY} but differs from {b.name} by more than it")
    with_u = copy.deepcopy(d)
    with_u.setdefault("env", {})[KEY] = VAL
    bad = diff_vs_x28h(strip_engine(with_u), load(x28h))
    if bad:
        why.append("P028x.json + U without the picture reader is not x28h.json + U in: " + ", ".join(bad))
    return why, ("rerun: U already set" if v == VAL else "U to be added")


def edit(p028x, backup):
    p, b = Path(p028x), Path(backup)
    cur = load(p)
    if cur.get("env", {}).get(KEY) == VAL:
        if not b.exists():
            raise SystemExit(f"FAIL: {p.name} already has {KEY}={VAL} but there is no backup {b.name}")
        old = load(b)
        if old.get("env", {}).get(KEY) is not None or {**old, "env": {**old["env"], KEY: VAL}} != cur:
            raise SystemExit(f"FAIL: {p.name} has {KEY} but differs from {b.name} by more than it")
        return "already: U set, the backup in place"
    if b.exists():
        if load(b) != cur:
            raise SystemExit(f"FAIL: the backup {b.name} exists and is not {p.name} as it is now - nothing changed")
    else:
        shutil.copy2(p, b)
        if b.read_bytes() != p.read_bytes():
            raise SystemExit("FAIL: the backup copy does not match")
    new = copy.deepcopy(cur)
    new.setdefault("env", {})[KEY] = VAL
    try:
        write_json(p, new, p)
        got, old = load(p), load(b)
    except Exception as e:      # the file may already be rewritten: the driver restores the backup on FAIL-WRITTEN
        raise SystemExit(f"FAIL-WRITTEN: the write or its re-read failed ({type(e).__name__}: {e})")
    old_u = copy.deepcopy(old)
    old_u["env"][KEY] = VAL
    if got != old_u:
        raise SystemExit("FAIL-WRITTEN: after the edit P028x.json differs from the backup by more than " + KEY)
    return f"edited: env {KEY}={VAL} added ({len(got['env'])} env keys), backup {b.name}"


def derive(p028x, x28h, out, log):
    s = strip_engine(load(p028x), log)
    s["_comment"] = "11-09 U adoption check (work/r23/gap-u-adopt.sh): configs/P028x.json with U, without the picture reader"
    bad = diff_vs_x28h(s, load(x28h))
    if bad:
        raise SystemExit("FAIL: S is not x28h.json + U in: " + ", ".join(bad))
    if s["env"].get(KEY) != VAL:
        raise SystemExit("FAIL: S has no " + KEY)
    write_json(out, s, p028x)
    return f"S = configs/P028x.json (with U) without the picture reader = x28h.json + {KEY}={VAL}: OK"


def restore(p028x, backup):
    tmp = Path(str(p028x) + ".restore")
    shutil.copy2(backup, tmp)
    os.replace(tmp, p028x)
    if Path(p028x).read_bytes() != Path(backup).read_bytes():
        raise SystemExit("FAIL: the restore did not take")
    return "restored: P028x.json = its backup (the guard kept, no U)"


def recs(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def speed(bp90, morning):
    out, flags = [], []
    for st in ("pp16k", "pp64k"):
        s = [r["prompt_tps"] for r in recs(Path(bp90) / f"S-{st}-1.jsonl") if r.get("prompt_tps")]
        ref = {}
        for arm in ("P", "PU"):
            v = [r["prompt_tps"] for k in (1, 2, 3) for r in recs(Path(morning) / f"{arm}-{st}-{k}.jsonl") if r.get("prompt_tps")]
            ref[arm] = statistics.median(v) if v else None
        if not s:
            out.append(f"{st}: S not measured")
            flags.append(f"{st} missing")
            continue
        line = f"{st}: S {s[0]:,.1f} tok/s"
        for arm in ("P", "PU"):
            if ref[arm]:
                line += f"; vs this morning's {arm} {ref[arm]:,.1f} ({100 * (s[0] / ref[arm] - 1):+.1f} %)"
        if ref["P"] and 100 * (s[0] / ref["P"] - 1) < -FLAG_PCT:
            flags.append(f"{st} {100 * (s[0] / ref['P'] - 1):+.1f} % vs P")
        out.append(line)
    sd = {r["test"]: r.get("decode_tps") for r in recs(Path(bp90) / "S-decode-1.jsonl")}
    if not sd:
        out.append("decode: S not measured")
        flags.append("decode missing")
    else:
        ref = {arm: {r["test"]: r.get("decode_tps") for r in recs(Path(morning) / f"{arm}-decode-1.jsonl")} for arm in ("P", "PU")}
        parts = []
        for t in ("conv", "struct", "prose"):
            v = sd.get(t)
            if not v:
                parts.append(f"{t} -")
                continue
            q = f"{t} {v:.1f}"
            for arm in ("P", "PU"):
                if ref[arm].get(t):
                    q += f" ({arm} {ref[arm][t]:.1f}, {100 * (v / ref[arm][t] - 1):+.1f} %)"
            parts.append(q)
        out.append("decode tok/s (1 pass, sampled, noise 4-7 %): " + "; ".join(parts))
    out.append("SPEED " + ("FLAG: " + ", ".join(flags) if flags else "OK (no prompt set more than 3 % below P028x)"))
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
    except (urllib.error.URLError, OSError, ValueError) as e:     # refused, timed out, not JSON
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
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    n = [0, 0]

    def chk(name, cond):
        n[0] += 1
        n[1] += 0 if cond else 1
        print(("ok   " if cond else "FAIL ") + name)

    env = {"STRATA_ROUTE_TAIL_SKIP": "0", "STRATA_DEFAULTS": "026"}
    x = {"exe": "/e/strata", "args": ["--serve", "--kv-resident", "32768"], "env": dict(env), "log": "/l/x28h.log", "_comment": "x"}
    p = {**copy.deepcopy(x), "args": ["--serve", "--vision", "--kv-resident", "32768"], "log": "/l/P.log", "vision": {"exe": "v"},
         "fallback": "/c/f.json", "_comment": "p"}
    P, X, B, S = d / "P028x.json", d / "x28h.json", d / "P028x.json.before-upmix-test", d / "S.json"
    for f in (P, B, S):
        f.unlink(missing_ok=True)
    X.write_text(json.dumps(x, indent=1) + "\n")
    P.write_text(json.dumps(p, indent=1) + "\n")
    why, _ = plan(P, X, B)
    chk("plan refuses without the guard key", any("guard key" in w for w in why))
    p[GUARD] = {DS_MODEL: "something else"}
    P.write_text(json.dumps(p, indent=1) + "\n")
    chk("plan refuses a guard key without the served text", any("guard key has no" in w for w in plan(P, X, B)[0]))
    p[GUARD] = {DS_MODEL: "DeepSeek isn't running - use the 'Switch to DeepSeek' desktop icon"}
    P.write_text(json.dumps(p, indent=1) + "\n")
    why, st = plan(P, X, B)
    chk("plan OK with the guard key", why == [] and st == "U to be added")
    before = P.read_bytes()
    r = edit(P, B)
    chk("edit adds U", r.startswith("edited") and load(P)["env"][KEY] == VAL and B.read_bytes() == before)
    chk("edit changes nothing else", {**load(B), "env": {**load(B)["env"], KEY: VAL}} == load(P))
    chk("edit again = already", edit(P, B).startswith("already"))
    chk("plan after the edit = a rerun", plan(P, X, B) == ([], "rerun: U already set"))
    chk("plan refuses U set with no backup", any("no backup" in w for w in plan(P, X, d / "no-such-backup")[0]))
    r = derive(P, X, S, d / "S.log")
    s = load(S)
    chk("derive: no picture reader / fallback / guard key, own log",
        "--vision" not in s["args"] and not any(k in s for k in NOT_ENGINE) and s["log"].endswith("S.log") and s["env"][KEY] == VAL)
    x2 = copy.deepcopy(x)
    x2["env"]["STRATA_OTHER"] = "1"
    X.write_text(json.dumps(x2, indent=1) + "\n")
    try:
        derive(P, X, S, d / "S.log")
        chk("derive refuses another env difference", False)
    except SystemExit as e:
        chk("derive refuses another env difference", "env" in str(e))
    why, _ = plan(P, X, B)
    chk("plan refuses another env difference", any("env" in w for w in why))
    X.write_text(json.dumps(x, indent=1) + "\n")
    chk("restore", restore(P, B).startswith("restored") and P.read_bytes() == before)
    q = copy.deepcopy(p)
    q["env"]["STRATA_X"] = "1"
    P.write_text(json.dumps(q, indent=1) + "\n")
    try:
        edit(P, B)
        chk("edit refuses when the backup is not the current file", False)
    except SystemExit as e:
        chk("edit refuses when the backup is not the current file", "nothing changed" in str(e) and KEY not in load(P)["env"])
    chk("plan refuses when the backup is not the current file", any("exists and is not" in w for w in plan(P, X, B)[0]))
    q2 = copy.deepcopy(p)
    q2["env"][KEY] = "0"
    P.write_text(json.dumps(q2, indent=1) + "\n")
    chk("plan refuses U set to another value", any("already sets" in w for w in plan(P, X, B)[0]))
    bp, mo = d / "bp90", d / "morning"
    bp.mkdir(exist_ok=True)
    mo.mkdir(exist_ok=True)
    for arm, base in (("P", 3850.0), ("PU", 3975.0)):
        for k in (1, 2, 3):
            (mo / f"{arm}-pp16k-{k}.jsonl").write_text(json.dumps({"test": "pp16k", "prompt_tps": base + k}) + "\n")
            (mo / f"{arm}-pp64k-{k}.jsonl").write_text(json.dumps({"test": "pp64k", "prompt_tps": base + 500 + k}) + "\n")
        (mo / f"{arm}-decode-1.jsonl").write_text("".join(json.dumps({"test": t, "decode_tps": v}) + "\n"
                                                           for t, v in (("conv", 140.0), ("struct", 225.0), ("prose", 129.0))))
    (bp / "S-pp16k-1.jsonl").write_text(json.dumps({"prompt_tps": 3970.0}) + "\n")
    (bp / "S-pp64k-1.jsonl").write_text(json.dumps({"prompt_tps": 4560.0}) + "\n")
    (bp / "S-decode-1.jsonl").write_text(json.dumps({"test": "conv", "decode_tps": 141.0}) + "\n")
    o = speed(bp, mo)
    chk("speed OK case", o[-1].startswith("SPEED OK") and "+3.1 %" in o[0])
    (bp / "S-pp64k-1.jsonl").write_text(json.dumps({"prompt_tps": 4000.0}) + "\n")
    o = speed(bp, mo)
    chk("speed FLAG below P by > 3 %", o[-1].startswith("SPEED FLAG") and "pp64k" in o[-1])
    (bp / "S-decode-1.jsonl").unlink()
    chk("speed FLAG on a missing set", "decode missing" in speed(bp, mo)[-1])
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
    if c in ("edit", "derive", "restore"):
        try:
            print({"edit": edit, "derive": derive, "restore": restore}[c](*a))
        except SystemExit as e:
            print(str(e))
            return 1
        return 0
    if c == "speed":
        print("\n".join(speed(*a[:2])))
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
