#!/usr/bin/env python3
"""ctx128.py - 10-26 (Karl, via the user): "set DeepSeek's daily context to 128K if a filled-context check passes. After the
hard set and the repeat pairs:
1. Run one real long prompt on the daily config at 128K: ~100K tokens of text plus a short question. Report read time,
   decode speed at that length, peak memory (it must keep >= 14 GB free with everything up), and the size of the
   conversation slot it leaves, in RAM and on disk.
2. Estimate the worst case for 16 RAM slots if several chats are long. If it could break the 14 GB rule, cap slot RAM (or
   long slots) so it can't.
3. If it passes, switch DS41-daily.json to 128K and note it in the report.
4. Optional, if it fits in about 45 minutes: run the suite's long-context items (the ~95K-token documents, Qwen-only so
   far) on DeepSeek at effort 50. Grade them the same way and add them to the comparison."

Steps (state results/ds41/ctx128/state.json, log ctx128.log; its own gap once ds41-hard has ended with its gap closed):
  build   (CPU, 8080 up) the local variant p343+slotram: the shipped engine (v0.2.6 + #343) + STRATA_DS4_SLOT_RAM_GB, a
          byte cap on the conversations kept in RAM (unset = stock; the engine itself caps only their count, 16 here)
  long    the daily config at --max-context 131072 on the shipped engine, everything up (SearXNG 8889/8890 + the ballast
          as in the daily memory check), soft stop 14 GB: longprompt.py (L1 ~100K + a question, S1 short, L2 L1
          continued, S2 short); the slot on disk = the folder's .bin after the engine stops
  estimate  S128 = the long slot's bytes x 131,072 / its tokens (the fixed part counted per token: an overestimate, on
          the safe side); worst = min(this run's lowest MemAvailable, the daily check's 15.5 GB + its 16 x ~32K slots)
          - 16 x S128 - S128 (one more copy while a conversation is set aside or read back from the folder). Under 14 GB
          -> a byte cap B = what keeps 14 GB + 0.25 GB margin with one copy in flight
  ramtest / idcheck  (only with a cap) the variant at a tiny cap (0.03 GiB) must move the least recently used conversation
          to the folder and take it back from there; two seeded requests on fresh engines must give identical text on
          the shipped engine and the variant (at cap B)
  switch  DS41-daily.json (backup .before-128k): --max-context 131072 (+ the variant and STRATA_DS4_SLOT_RAM_GB B with a
          cap), the start check's RAM need from this run (+ B); the launcher smoke test on 8086 (as write_daily); a failed
          smoke test restores the backup
  longctx (optional) the 6 long-context items on the daily config (128K) at effort 50 with the graded set's settings
          (reasoning_budget_tokens 8,192, max_tokens 16,384) as g1026-ds-e50-longctx, if the estimate from the long run's
          read and decode speed is <= 50 min
  then the gap closes, the items are regraded and the graded report rebuilt with them (report.py, DeepSeek e50 =
  g1026-ds-e50+g1026-ds-e50-longctx) -> results/ds41/ctx128/summary.md"""
import contextlib
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/after")
import after as A  # noqa: E402

SC = A.SC
R = f"{SC}/results/ds41/ctx128"
A.STATE, A.LOG = f"{R}/state.json", f"{R}/ctx128.log"
CTX = 131072
NEW = "v026p343-slotram"
NEW_EXE = f"{SC}/engine-{NEW}-ds41/strata-dsv41"
A.tune.ENGINES[NEW] = dict(A.tune.ENGINES[A.FINAL_ENG], exe=NEW_EXE)
LC = "g1026-ds-e50-longctx"
DAILY_DS = 15.5      # the daily memory check (daily-68-1026-1536): lowest MemAvailable with everything up, 16 slots full
DAILY_SLOTS = 0.64   # ... the 16 slots it held (~32K tokens each), GB
GIB = 1073741824


def wait_hard():
    A.say("128K check: waiting for the hard set (ds41-hard) to end")
    while subprocess.run(["systemctl", "--user", "is-active", "--quiet", "ds41-hard.service"]).returncode == 0:
        time.sleep(60)
    try:
        h = json.load(open(f"{SC}/results/ds41/hard/state.json"))
    except (OSError, ValueError):
        h = {}
    if h.get("stopped") or not h.get("gap_closed"):
        why = h.get("stopped") or "it ended without closing its gap"
        A.say(f"128K check: the hard set did not finish cleanly ({why}) - nothing runs")
        A.notify("128K check not started", f"the hard set: {why}", True)
        sys.exit(1)
    A.say(f"128K check: the hard set ended (gap closed {h['gap_closed']})")


def build(st):
    if st.get("build"):
        return
    rc = A.sh(["bash", f"{A.A}/build-variant.sh", "p343+slotram"], f"{R}/build.log")
    if rc != 0 or not os.path.exists(NEW_EXE):
        st["build"] = f"FAILED (rc {rc}, {R}/build.log)"
    else:
        # the #343 part must be the shipped engine's: every line of its variant.diff's changes is in the new one
        old = [l for l in open(f"{SC}/engine-{A.FINAL_ENG}-ds41/variant.diff") if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        new = open(f"{SC}/engine-{NEW}-ds41/variant.diff").read()
        missing = [l for l in old if l not in new]
        st["build"] = (open(f"{SC}/engine-{NEW}-ds41/SHA256").read().split()[0][:12] if not missing
                       else f"FAILED (the #343 part differs from the shipped engine's: {len(missing)} lines)")
    A.save(st)
    A.say(f"build p343+slotram: {st['build']}")


@contextlib.contextmanager
def everything_up():
    """as the daily memory check: SearXNG 8889/8890 up, the ballast holding what LDR + SearXNG 8889 use in daily life"""
    A.sh(["systemctl", "--user", "start", "searxng-ldr.service", "searxng-ldr-baseline.service"])
    time.sleep(60)
    mf = f"{R}/svcmem.jsonl"
    sx = json.loads(subprocess.run([A.PY, f"{A.T}/svcmem.py", "SearXNG 8889/8890 started", mf], capture_output=True,
                                   text=True).stdout or "{}").get("rss_gib", {}).get("SearXNG 8889 (LDR)", 0) or 0
    hold = round(3.54 + max(0.0, 1.74 - sx), 2)
    bal = subprocess.Popen([A.PY, f"{A.T}/ballast.py", str(hold)], stdout=subprocess.DEVNULL)
    try:
        time.sleep(30)
        subprocess.run([A.PY, f"{A.T}/svcmem.py", f"everything up (held {hold} GiB: LDR 3.54 + SearXNG 8889 to 1.74)", mf])
        yield hold
    finally:
        bal.kill()
        bal.wait()
        A.sh(["systemctl", "--user", "stop", "searxng-ldr.service", "searxng-ldr-baseline.service"])


def daily_mods(slot_dir, **extra):
    m = dict(A.daily_mods(json.load(open(f"{SC}/results/ds41/after/state.json")), slot_dir), **{"--max-context": CTX})
    m.update(extra)
    return m


def long_run(st):
    if st.get("long"):
        return
    sd = f"{R}/slots-long"
    shutil.rmtree(sd, ignore_errors=True)
    with everything_up() as hold:
        r = A.arm(st, "long100k", daily_mods(sd), f"128K check: the daily config at --max-context {CTX}, ~100K-token prompt + "
                  f"question, then short / continued / short; everything up (ballast {hold} GiB); soft stop 14 GB",
                  f"{A.PY} {A.A}/longprompt.py $URL $OUT {A.ELOG} {sd}", soft=14, server_env="STRATA_DS4_AUTO_PIN=1",
                  client_timeout=3600)
    lp = json.load(open(f"{r['dir']}/longprompt.json")) if r.get("dir") and os.path.exists(f"{r['dir']}/longprompt.json") else {}
    ended = re.findall(r"ds4 slots: saved a (\d+)-token conversation as the engine ended \(([\d.]+) GB",
                       open(f"{r['dir']}/engine-run.log", errors="replace").read()) if r.get("dir") else []
    bins = sorted((os.path.getsize(f), f) for f in glob.glob(f"{sd}/slot-*.bin"))
    m0 = next((float(l.split()[1]) for l in list(open(f"{r['dir']}/monitor.tsv"))[1:2]), None) if r.get("dir") else None
    big = (lp.get("largest_slot") or {})
    st["long"] = {"dir": r.get("dir"), "lowest_mem": r.get("lowest_mem"), "guard": r.get("guard"), "softstop": r.get("softstop"),
                  "memavail_start": m0, "lp": lp, "ended_saves": ended,
                  "disk_bins": [[b, os.path.basename(f)] for b, f in bins],
                  "slot_tokens": big.get("tokens"), "slot_ram_gb": big.get("gb"),
                  "slot_disk_bytes": bins[-1][0] if bins else None,
                  "ok": bool(lp) and not r.get("guard") and not r.get("softstop") and (r.get("lowest_mem") or 0) >= 14.0}
    A.save(st)
    A.say(f"128K long prompt: {json.dumps({k: v for k, v in st['long'].items() if k != 'lp'})[:900]}")


def estimate(st):
    L = st["long"]
    tok, b = L.get("slot_tokens"), L.get("slot_disk_bytes")
    if not (tok and b and L.get("lowest_mem")):
        st["estimate"] = {"error": "no slot size or lowest MemAvailable from the long run"}
        A.save(st)
        return st["estimate"]
    s128 = b * CTX / tok / GIB                          # GiB, one slot at the full context (fixed part counted per token)
    base = min(L["lowest_mem"], DAILY_DS + DAILY_SLOTS)  # what the engine + everything up leaves with (almost) no slots
    worst = base - 16 * s128 - s128
    cap = math.floor((base - 14.0 - 0.25 - s128) * 10) / 10 if worst < 14.0 else None
    st["estimate"] = {"slot_gib_per_1k": round(b / tok * 1000 / GIB, 5), "s128_gib": round(s128, 3), "base_gib": round(base, 2),
                      "worst_16_long_gib": round(worst, 2), "breaks_14": worst < 14.0, "cap_gib": cap,
                      "cap_holds_16_daily_chats": cap is None or cap >= DAILY_SLOTS + 0.05}
    A.save(st)
    A.say(f"128K estimate: {json.dumps(st['estimate'])}")
    return st["estimate"]


def ramtest(st):
    if "ramtest" in st:
        return
    sd = f"{R}/slots-ramtest"
    shutil.rmtree(sd, ignore_errors=True)
    r = A.arm(st, "slotram-test", daily_mods(sd, engine=NEW, STRATA_DS4_SLOT_RAM_GB="0.03"),
              "128K check: the slot RAM cap at 0.03 GiB - the least recently used conversation goes to the folder and comes back",
              f"{A.PY} {A.A}/slotram_client.py $URL $OUT {A.ELOG}", server_env="STRATA_DS4_AUTO_PIN=1", client_timeout=1800)
    res = json.load(open(f"{r['dir']}/slotram.json")) if r.get("dir") and os.path.exists(f"{r['dir']}/slotram.json") else {}
    st["ramtest"] = {"ok": bool(res.get("ok")) and not r.get("guard"), "after_D": res.get("after_D_in_ram_folder"),
                     "continued_A": res.get("continued_A"), "dir": r.get("dir"), "guard": r.get("guard")}
    A.save(st)
    A.say(f"slot RAM cap test: {json.dumps(st['ramtest'])[:700]}")


def idcheck(st, cap):
    if "idcheck" in st:
        return
    out = {}
    for k, eng, extra in (("old", A.FINAL_ENG, {}), ("new", NEW, {"STRATA_DS4_SLOT_RAM_GB": str(cap)})):
        sd = f"{R}/slots-id-{k}"
        shutil.rmtree(sd, ignore_errors=True)
        r = A.arm(st, f"id-{k}", daily_mods(sd, engine=eng, **extra), f"128K check: two seeded requests on a fresh {eng} engine",
                  f"{A.PY} {A.A}/idcheck_client.py $URL $OUT", server_env="STRATA_DS4_AUTO_PIN=1", client_timeout=1800)
        p = f"{r['dir']}/idcheck.json" if r.get("dir") else ""
        out[k] = json.load(open(p)) if p and os.path.exists(p) else None
    same = bool(out["old"]) and bool(out["new"]) and [x["text"] for x in out["old"]] == [x["text"] for x in out["new"]]
    st["idcheck"] = {"identical": same, "tokens": {k: [x["completion_tokens"] for x in (v or [])] for k, v in out.items()}}
    A.save(st)
    A.say(f"identity check (shipped engine vs the slot-cap build, fresh engines, seed 4242): {json.dumps(st['idcheck'])}")


def smoke(cfg):
    """launcher smoke test on 8086 (as write_daily): start through run-strata.sh, one completion, stop - on a copy of the
    config whose profile is a throwaway file"""
    sp = f"{R}/smoke-profile.bin"
    if os.path.exists(sp):
        os.remove(sp)
    c = json.load(open(cfg))
    c["args"][c["args"].index("--expert-profile") + 1] = sp
    sc = f"{R}/DS41-daily-smoke.json"
    json.dump(c, open(sc, "w"), indent=1)
    env = A.clean_env(STRATA_PORT="8086", STRATA_CONFIG=sc)
    with open(A.LOG, "a") as lf:
        rc = subprocess.run(["bash", f"{SC}/run-strata.sh", "start"], env=env, stdout=lf, stderr=lf).returncode
        out = subprocess.run(["curl", "-s", "-m", "300", "http://127.0.0.1:8086/v1/chat/completions", "-H",
                              "Content-Type: application/json", "-d", json.dumps({"model": "x", "max_tokens": 1, "stream": False,
                              "messages": [{"role": "user", "content": "Reply with OK."}]})], capture_output=True, text=True).stdout
        models = subprocess.run(["curl", "-s", "-m", "10", "http://127.0.0.1:8086/v1/models"], capture_output=True, text=True).stdout
        subprocess.run(["bash", f"{SC}/run-strata.sh", "stop"], env=env, stdout=lf, stderr=lf)
    for _ in range(60):
        if not subprocess.run(["pgrep", "-x", "strata-dsv41"], capture_output=True, text=True).stdout.split():
            break
        time.sleep(1)
    for p in subprocess.run(["pgrep", "-x", "strata-dsv41"], capture_output=True, text=True).stdout.split():
        subprocess.run(["kill", "-9", p])
    return rc == 0 and '"finish_reason"' in out and "deepseek" in models, f"start rc {rc}; models {models[:100]}; reply {out[:140]}"


def switch(st, est):
    if st.get("switch"):
        return
    L = st["long"]
    cap = est.get("cap_gib")
    why = None
    if not L.get("ok"):
        why = "the long-prompt run did not pass (guard, soft stop, under 14 GB or no result)"
    elif est.get("error"):
        why = est["error"]
    elif est.get("breaks_14"):
        if not str(st.get("build", "")).strip() or str(st.get("build")).startswith("FAILED"):
            why = f"a slot RAM cap is needed but the build failed ({st.get('build')})"
        elif cap is None or cap < 0.3:
            why = f"a slot RAM cap is needed but it would be too small ({cap} GiB)"
        elif not (st.get("ramtest") or {}).get("ok"):
            why = "the slot RAM cap test failed"
        elif not (st.get("idcheck") or {}).get("identical"):
            why = "the slot-cap build does not serve identically to the shipped engine"
    if why:
        st["switch"] = f"NOT switched: {why} - DS41-daily.json stays at 32K"
        A.save(st)
        A.say(st["switch"])
        return
    p = A.DAILY_CFG
    bak = p + ".before-128k"
    if not os.path.exists(bak):
        shutil.copy(p, bak)
    c = json.load(open(p))
    a = c["args"]
    a[a.index("--max-context") + 1] = str(CTX)
    need = int(((L["memavail_start"] or 0) - L["lowest_mem"] + (cap or 0) + 12) * 1024) if L.get("memavail_start") else 0
    c["need_ram_mib"] = max(int(c.get("need_ram_mib") or 0), need)
    note = (f" 10-26 night (Karl: 128K if a filled-context check passes): --max-context {CTX}; a ~{L.get('slot_tokens')}-token "
            f"prompt with everything up left {L['lowest_mem']} GB ({L['dir']})")
    if est.get("breaks_14"):
        c["exe"] = NEW_EXE
        c["env"]["STRATA_DS4_SLOT_RAM_GB"] = str(cap)
        note += (f"; slot RAM capped at {cap} GiB (engine {NEW}: the shipped engine + STRATA_DS4_SLOT_RAM_GB) - 16 chats at "
                 f"128K would need {16 * est['s128_gib']:.2f} GiB")
    c["_comment"] = c.get("_comment", "") + note + "."
    json.dump(c, open(p, "w"), indent=1)
    ok, detail = smoke(p)
    if not ok:
        shutil.copy(bak, p)
        st["switch"] = f"NOT switched: the launcher smoke test failed ({detail}) - the 32K config restored"
    else:
        st["switch"] = (f"switched: DS41-daily.json at {CTX}" + (f", slot RAM cap {cap} GiB on {NEW}" if est.get("breaks_14") else "")
                        + f", need_ram_mib {c['need_ram_mib']}; smoke test ok ({detail[:120]}); backup {bak}")
    A.save(st)
    A.say(st["switch"])


def longctx(st):
    if st.get("longctx"):
        return
    lp = (st.get("long") or {}).get("lp") or {}
    rt, dt = lp.get("read_tps"), (lp.get("decode_tps") or [None])[0]
    if not (rt and dt):
        st["longctx"] = "skipped: no read / decode speed from the long run"
        A.save(st)
        return
    est_s = 90 + 6 * 100000 / rt + (4 * 8600 + 2 * 800) / dt   # (count / track items think to the budget, as Qwen did)
    st["longctx_estimate_min"] = round(est_s / 60, 1)
    if est_s > 50 * 60:
        st["longctx"] = f"skipped: estimated {est_s / 60:.0f} min (over ~45)"
        A.save(st)
        A.say(f"long-context items: {st['longctx']}")
        return
    sw = str(st.get("switch", ""))
    capped = sw.startswith("switched") and "slot RAM cap" in sw
    extra = {"engine": NEW, "STRATA_DS4_SLOT_RAM_GB": str(st["estimate"]["cap_gib"])} if capped else {}
    sd = f"{R}/slots-longctx"
    shutil.rmtree(sd, ignore_errors=True)
    r = A.arm(st, "lc-e50", daily_mods(sd, **extra), f"long-context items on DeepSeek effort 50 at 128K (estimate "
              f"{est_s / 60:.0f} min), the graded set's settings", A.suite_cmd(LC, "$URL", 50, "longctx"),
              server_env="STRATA_DS4_AUTO_PIN=1", client_timeout=5400)
    st["longctx"] = {"label": LC, "complete": A.suite_done(LC), "min": r.get("min"), "lowest_mem": r.get("lowest_mem"),
                     "guard": r.get("guard"), "estimate_min": round(est_s / 60, 1)}
    A.save(st)
    A.say(f"long-context items: {json.dumps(st['longctx'])}")


def grade(st):
    if st.get("graded") or not isinstance(st.get("longctx"), dict):
        return
    A.sh(["bash", A.SUITE, "regrade", LC, "--no-render"], f"{R}/regrade.log")
    rc = A.sh([A.PY, f"{A.A}/report.py", A.GL["qwen"], f"{A.GL[50]}+{LC}", A.GL[75], f"{SC}/results/ds41/after/graded"],
              f"{R}/report.log")
    st["graded"] = f"rc {rc}: results/ds41/after/graded/REPORT.md (DeepSeek e50 + {LC})"
    A.save(st)
    A.say(f"long-context graded: {st['graded']}")


def summary(st):
    L, E = st.get("long") or {}, st.get("estimate") or {}
    lp = L.get("lp") or {}
    S = ["# DeepSeek at 128K context (10-26 night)", "",
         f"- Long prompt (daily config at {CTX}, everything up): {lp.get('prompt_tokens')} prompt tokens read in {lp.get('read_s')} s "
         f"({lp.get('read_tps')} tok/s); decode at that length {lp.get('decode_tps')} tok/s ({lp.get('generated')} tokens); TTFT "
         f"{lp.get('ttft_s')} s, first answer token {lp.get('t_first_answer_s')} s, total {lp.get('total_s')} s.",
         f"- Follow-up on it: {json.dumps(lp.get('followup'))}",
         f"- Lowest MemAvailable in the run: {L.get('lowest_mem')} GB (start {L.get('memavail_start')}; guard {L.get('guard')}; "
         f"soft stop {L.get('softstop')}) -> {'PASS' if L.get('ok') else 'FAIL'} (>= 14 GB).",
         f"- Its slot: {L.get('slot_tokens')} tokens, {L.get('slot_ram_gb')} GB in RAM (engine), {L.get('slot_disk_bytes')} bytes on "
         f"disk; folder {L.get('disk_bins')}; engine-end saves {L.get('ended_saves')}.",
         f"- Worst case, 16 RAM slots at 128K: {json.dumps(E)}",
         f"- Build p343+slotram: {st.get('build')}; cap test: {json.dumps(st.get('ramtest'))[:400]}; identity: {json.dumps(st.get('idcheck'))}",
         f"- Daily config: {st.get('switch')}",
         f"- Long-context items: {json.dumps(st.get('longctx'))}; graded: {st.get('graded')}"]
    open(f"{R}/summary.md", "w").write("\n".join(S) + "\n")


def main():
    os.makedirs(R, exist_ok=True)
    st = A.load()
    if st.get("stopped"):
        A.say(f"not resuming: stopped earlier ({st['stopped']})")
        return 1
    if not st.get("gap_open"):
        wait_hard()
        build(st)
    A.open_gap(st)
    long_run(st)
    est = estimate(st)
    if est.get("breaks_14") and st.get("long", {}).get("ok") and not str(st.get("build")).startswith("FAILED"):
        ramtest(st)
        if (st.get("ramtest") or {}).get("ok") and est.get("cap_gib") and est["cap_gib"] >= 0.3:
            idcheck(st, est["cap_gib"])
    switch(st, est)
    longctx(st)
    rc = A.close_gap(st)
    try:
        grade(st)
    except Exception as e:   # noqa: BLE001
        A.say(f"long-context grading failed: {type(e).__name__}: {e}")
    summary(st)
    A.notify("128K check done", f"{st.get('switch')}; 8080 {'back on P021m' if rc == 0 else 'NOT restored'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
