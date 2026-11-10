#!/usr/bin/env python3
"""hardset.py - 10-26 18:20 (Karl, via the user): "If the quick set turns out saturated, build a harder set of ~25-30
prompts: the items Qwen failed or passed inconsistently on October 17, plus the hardest items from the full suite (math,
coding with hidden tests, multi-step reasoning, tool use; no long-context items). Run Qwen at medium, Qwen at its highest
effort, and DeepSeek at effort 50, starting when the block ends. Grade them with the same scripts and the blind method.
... The summary should answer: is DeepSeek better than Qwen at its best on hard questions, and by how much?"
10-26 19:00 (Karl): "1. Thinking room: give both models the same room, not each its full context. Use a max of ~30K
total tokens per answer (it fits DeepSeek's 32K context) and no separate thinking cap. Report cut-off answers per model.
2. Add DeepSeek at effort 75 on all 29 items, so it's "DeepSeek at its best vs Qwen at its best". Main result:
DeepSeek's better setting minus Qwen's better setting, per item, with the interval. 3. Add DeepSeek at effort 25 on the
8 honesty items. 4. DSpark: check whether DSpark is actually drafting in the daily config ... If it is drafting, run a
3-pass decode A/B/A of the final config vs the same with --dspark none tonight, and keep whichever wins ... Also run the
~9-minute repeat pairs with DSpark off. 5. Order: hard set first, then the DSpark items. Night runs are fine."

The quick set is saturated, so the set has 29 items:
  - 19 that Qwen (IQ3_S, C*18 / C*18t) failed or passed inconsistently in its 10-15 xhigh, 10-17 medium (+ rerun), 10-17
    low and the 10-16/17 three-run effort probes: any answer below full marks
  - 10 of the hardest by the mean score of every graded label (all models, all runs) in math, coding with hidden tests,
    tool use and multi-step (agentic) - not already in the first group; no long context; r04 left out (its low mean is the
    fixed server bug)
Settings: Qwen P021m (the daily config, on 8085) at medium and xhigh (Strata's highest; "high" renders as xhigh);
DeepSeek on the final daily config at effort 50 and 75 (all 29) and 25 (the 8 honesty items). The same room for every
answer: max_tokens 30,000, no reasoning_budget_tokens (both servers then keep a quarter of max_tokens for the answer, so
the thinking stops at ~22,500); where DeepSeek's 32,768 context leaves less (long research / agentic prompts) the suite
fits max_tokens to it - reported per item with the cut-off answers. One run per item.
DSpark (item 4): with --dspark auto the engine does not load DSpark in the final config ("DSpark not loaded: the routed
experts (132 GB) are far more than the GPU holds") - checked in every arm of the block; this script checks the hard
set's own DeepSeek runs again and runs the decode A/B/A only if one of them drafted. Then the repeat pairs with
--dspark none (as rep-test-reuse0) and a carry-over check: one engine scores the same short8 segment twice, at window
128 (the prompt path) and window 1 (decode's path) - identical rows mean the engine's numbers carry nothing over
between requests.
Own gap (after ds41-after has closed its own and 8080 is back), state results/ds41/hard/state.json, log hard.log."""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/after")
import after as A  # noqa: E402

SC = A.SC
R = f"{SC}/results/ds41/hard"
A.STATE, A.LOG = f"{R}/state.json", f"{R}/hard.log"
ITEMS = ["coding/c01_parse_duration", "coding/c14_semver", "coding/c16_json_parser", "coding/c19_mini_regex",
         "coding/c24_exact_calc", "coding/c23_refactor_orderbook", "coding/c02_rle", "coding/c07_rpn", "coding/c05_wrap",
         "math/m03", "math/m08", "math/m05", "math/m09", "math/m15",
         "tools/t03_currency", "tools/t06_nested_ticket", "agentic/a2_textstats",
         "honesty/h01_cartographer", "honesty/h03_viirmets", "honesty/h05_strondalsvik", "honesty/h06_ostrava_linden",
         "honesty/h07_glasbienen", "honesty/h11_borovanadic", "honesty/h12_pan_baltic_1923", "honesty/h14_einstein_dentist",
         "instruct/i14_quadsept", "instruct/i15_title_rule", "research/r02_best_model", "research/r05_gpu_price"]
HONESTY = [i for i in ITEMS if i.startswith("honesty/")]
LAB = {"qwen-medium": "h1026-qwen-medium", "qwen-xhigh": "h1026-qwen-xhigh", "ds-e50": "h1026-ds-e50",
       "ds-e75": "h1026-ds-e75", "ds-e25": "h1026-ds-e25-honesty"}
MAXTOK = 30000


def cmd(label, url, effort, items=ITEMS):
    cats = ",".join(sorted({i.split("/")[0] for i in items}))
    return (f"bash {A.SUITE} --label {label} --endpoint {url} --mode quick --only {cats} --items {','.join(items)} "
            f"--max-tokens {MAXTOK} --no-grade --extra-body '{json.dumps({'reasoning_effort': effort})}'")


def wait_block():
    """until ds41-after has ended with its gap closed (8080 back); a stopped block -> nothing runs"""
    A.say("hard set: waiting for the follow-up block (ds41-after) to end")
    while True:
        act = subprocess.run(["systemctl", "--user", "is-active", "--quiet", "ds41-after.service"]).returncode == 0
        if not act:
            try:
                s = json.load(open(f"{SC}/results/ds41/after/state.json"))
            except (OSError, ValueError):
                s = {}
            if s.get("stopped"):
                A.say(f"hard set: the block stopped ({s['stopped']}) - nothing runs")
                A.notify("Hard set not started", "the follow-up block stopped", True)
                sys.exit(1)
            if s.get("gap_closed"):
                A.say(f"hard set: the block ended (gap closed {s['gap_closed']})")
                return
        time.sleep(60)


def qwen(st):
    """Qwen P021m exactly as the daily launcher starts it, on 8085: medium, then xhigh, one server start"""
    if st.get("qwen_done"):
        return
    env = A.clean_env(STRATA_PORT="8085", STRATA_CONFIG=f"{SC}/configs/P021m.json")
    A.say("hard set: Qwen P021m on 8085 - effort medium, then xhigh")
    if A.sh(["bash", f"{SC}/run-strata.sh", "start"], env=env) != 0:
        st["qwen_done"] = "run-strata.sh start failed"
        A.save(st)
        return
    out = {}
    for k, eff in (("qwen-medium", "medium"), ("qwen-xhigh", "xhigh")):
        if A.suite_done(LAB[k]):
            continue
        t0, low, why = time.time(), 999.0, None
        lf = open(f"{R}/{k}-suite.log", "a")
        p = subprocess.Popen(["bash", "-c", cmd(LAB[k], "http://127.0.0.1:8085", eff)], cwd=SC, stdout=lf, stderr=lf,
                             env=A.clean_env())
        n = 0
        while p.poll() is None:
            m = A.memavail()
            low = min(low, m)
            if m < 12:
                why = f"failed: memory - MemAvailable {m:.1f} GB < 12"
                break
            n += 1
            if n % 30 == 0 and subprocess.run(["bash", f"{SC}/bringup/lib/kcheck.sh", "hard-qwen"],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                why = "kernel check failed"
                break
            time.sleep(2)
        if p.poll() is None:
            p.terminate()
            p.wait()
        out[k] = {"label": LAB[k], "min": round((time.time() - t0) / 60, 1), "lowest_mem": round(low, 1), "guard": why,
                  "complete": A.suite_done(LAB[k])}
        A.say(f"hard set {k}: {out[k]}")
        if why:
            break
    A.sh(["bash", f"{SC}/run-strata.sh", "stop"], env=env)
    for _ in range(60):
        if not subprocess.run(["pgrep", "-x", "strata"], capture_output=True).stdout:
            break
        time.sleep(1)
    st["qwen_done"] = out
    A.save(st)
    if any(v.get("guard") == "kernel check failed" for v in out.values()) or \
            A.sh(["bash", f"{SC}/bringup/lib/kcheck.sh", "hard-qwen-end"]) != 0:
        A.stop(st, "kernel check failed in the hard set's Qwen runs")


def deepseek(st):
    """DeepSeek on the final daily config: effort 50 and 75 on all 29 items, 25 on the honesty items; one arm each"""
    mods = A.daily_mods(json.load(open(f"{SC}/results/ds41/after/state.json")), f"{R}/slots")
    for key, eff, items in (("ds-e50", 50, ITEMS), ("ds-e75", 75, ITEMS), ("ds-e25", 25, HONESTY)):
        if st.get(f"{key}_done"):
            continue
        for attempt in range(2):   # (the suite resumes: a second run collects only what is missing)
            A.arm(st, f"h-{key}" + (f"-r{attempt + 1}" if attempt else ""), mods,
                  f"hard set: DeepSeek effort {eff} on the final daily config ({A.FINAL_ENG} + {A.FINAL_MODS}), {len(items)} items",
                  cmd(LAB[key], "$URL", eff, items), server_env="STRATA_DS4_AUTO_PIN=1", client_timeout=14400)
            if A.suite_done(LAB[key]):
                break
        st[f"{key}_done"] = {"label": LAB[key], "complete": A.suite_done(LAB[key]),
                             "runs": [x for x in st["steps"] if x.startswith(f"h-{key}")]}
        A.save(st)
        A.say(f"hard set DeepSeek effort {eff}: {st[f'{key}_done']}")


def dspark(st):
    """item 4: was DSpark loaded / drafting in the hard set's DeepSeek arms? A/B/A only if it drafted"""
    if st.get("dspark"):
        return
    seen = {}
    for k, v in st["steps"].items():
        p = f"{v.get('dir')}/engine-run.log" if v.get("dir") else ""
        if k.startswith("h-ds") and p and os.path.exists(p):
            t = open(p, errors="replace").read()
            seen[k] = {"not_loaded": "DSpark not loaded" in t, "draft_lines": t.count("drafts ")}
    drafted = any(not x["not_loaded"] or x["draft_lines"] for x in seen.values())
    out = {"arms": seen, "drafted": drafted}
    if drafted:
        f = A.ds_mods()
        runs = {"A1": A.arm(st, "dsp-A1", f, "DSpark A/B/A: A1 = the final config (--dspark auto)", "", passes=3, nprompt=3, cool=60),
                "B": A.arm(st, "dsp-B", dict(f, **{"--dspark": "none"}), "DSpark A/B/A: B = --dspark none", "", passes=3, nprompt=3, cool=60),
                "A2": A.arm(st, "dsp-A2", f, "DSpark A/B/A: A2 = the final config", "", passes=3, nprompt=3, cool=60)}
        ok = lambda r: bool(r.get("dir")) and not r.get("guard") and not r.get("softstop")
        comps = {a: A.cmp(runs[a]["dir"], runs["B"]["dir"]) for a in ("A1", "A2") if ok(runs[a]) and ok(runs["B"])}
        none_wins = len(comps) == 2 and all((c.get("decode") or {}).get("gain_pct", -99) > (c.get("decode") or {}).get("noise_pct", 99)
                                            for c in comps.values())
        out.update(aba={a: {m: (c.get(m) or {}) for m in ("decode", "P4K", "P20K")} for a, c in comps.items()}, none_wins=none_wins)
        if none_wins and os.path.exists(A.DAILY_CFG):
            c = json.load(open(A.DAILY_CFG))
            c["args"][c["args"].index("--dspark") + 1] = "none"
            json.dump(c, open(A.DAILY_CFG, "w"), indent=1)
            out["daily"] = "--dspark none written to configs/DS41-daily.json"
    else:
        out["verdict"] = "not drafting (--dspark auto does not load DSpark in this config) - no A/B/A, the daily config unchanged"
    st["dspark"] = out
    A.save(st)
    A.say(f"DSpark: {json.dumps(out)[:600]}")


def pairs_and_carryover(st):
    """the repeat pairs with --dspark none (as rep-test-reuse0), then the carry-over check (the same segment twice in one
    engine, window 128 and window 1)"""
    f = A.final()
    if "rep-test-reuse0-nodspark" not in st["steps"]:
        A.arm(st, "rep-test-reuse0-nodspark", dict(f, engine="v026test", STRATA_DS4_REUSE="0", DS4_TEST_SEED_RESET="1",
                                                   **{"--no-expert-cache": None, "--dspark": "none"}),
              "item 2 (Karl 19:00): repeat pairs as rep-test-reuse0 with --dspark none",
              f"{A.PY} {A.T}/cont_client.py $URL $OUT {A.ELOG} exact")
    if st.get("carryover"):
        return
    src = json.load(open(f"{A.skipcheck.OUT}/short8-s0.ids.json"))
    seg = src["segments"][0]
    p = f"{R}/carryover.ids.json"
    json.dump(dict(src, segments=[seg, dict(seg, name=seg["name"] + "-again")]), open(p, "w"))
    cfg = A.tune.mkcfg("hard-carryover", dict(f, engine="v026test", **{"--expert-profile": A.tune.SHIPPED}))
    out = {}
    for w in (128, 1):
        d = f"{R}/carryover-w{w}"
        rc = subprocess.run(["bash", f"{A.T}/scorearm.sh", d, cfg, p], env=dict(os.environ, SCORE_WINDOW=str(w), SCORE_LIMIT_S="1800")).returncode
        if rc == 3:
            A.stop(st, "kernel error in the carry-over check")
        rows = [l.split("\t") for l in open(f"{d}/score.tsv")] if os.path.exists(f"{d}/score.tsv") else []
        n = len(rows) // 2
        a, b = [r[1:] for r in rows[:n]], [r[1:] for r in rows[n:]]
        diff = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), None)
        out[w] = {"rc": rc, "positions": n, "identical": bool(n) and a == b, "first_difference": diff}
    st["carryover"] = out
    A.save(st)
    A.say(f"carry-over (the same segment twice in one engine): {json.dumps(out)}")


def grade(st):
    """the suite's checkers after the gap (CPU), then the report (hard_report.py) with the blind research packets"""
    if st.get("graded"):
        return
    for lab in LAB.values():
        if os.path.isdir(f"{SC}/suite/results/{lab}"):
            A.sh(["bash", A.SUITE, "regrade", lab, "--no-render"], f"{R}/regrade.log")
    rc = A.sh([A.PY, f"{A.A}/hard_report.py", R] + [LAB[k] for k in ("qwen-medium", "qwen-xhigh", "ds-e50", "ds-e75", "ds-e25")],
              f"{R}/report.log")
    st["graded"] = f"rc {rc}: {R}/REPORT.md"
    A.save(st)
    A.say(f"hard set graded: {st['graded']}")


def main():
    os.makedirs(R, exist_ok=True)
    st = A.load()
    if st.get("stopped"):
        A.say(f"not resuming: stopped earlier ({st['stopped']})")
        return 1
    wait_block()
    A.open_gap(st)
    qwen(st)
    deepseek(st)
    dspark(st)
    pairs_and_carryover(st)
    rc = A.close_gap(st)
    try:
        grade(st)
    except Exception as e:   # noqa: BLE001
        A.say(f"hard set grading failed: {type(e).__name__}: {e}")
    A.notify("Hard set done", f"{R}/REPORT.md; 8080 {'back on P021m' if rc == 0 else 'NOT restored'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
