#!/usr/bin/env python3
"""skipcheck.py skip | final MODS_JSON - 10-24 DeepSeek-V4.1 tuning round, teacher-forced pass/fail checks.
  skip   (the user, item 5: "test STRATA_DS4_PROMPT_SKIP=1 (the full-dependency mode only; never mode 2 or a shortened
         DS4_YOCO_KEEP) with the same rounding-reference method as the Flash-Next kernels"). The skip only runs with every
         trunk layer on one GPU, so all four runs are on the 5080 alone (--tp 1): base = skip off, chunk 1024 (as the
         engine's own test_prompt_skip.py), --expert-profile none (placement by index, no profile drift); our rounding
         references = R1 the same with a different chunk (DS4_CHUNK 2048) and R2 the same with ~230 fewer VRAM experts
         (--reserve-mib 2600: those experts computed by the CPU lane, this engine's "CPU share"); candidate = skip on (mode 1).
  final  the confirmed best config (MODS_JSON, as tune.py builds it) against the reference config (two GPUs), with the
         same two kinds of rounding reference on the reference config (--prefill-chunk 4096; --reserve-mib 2600).
  vs BASE_JSON CAND_JSON LABEL  (10-25) a candidate against a base config, the same two kinds of rounding reference on the
         base (another prompt chunk; --reserve-mib 2600): the v0.2.6 engine switch ({"engine": ...} in the mods) and the
         user's 5-vs-6 experts per word measurement (report only).
Segments: 8 x (12,000 prompt tokens read as one prompt + 256 positions scored, teacher-forced), cut from the long texts
in prompts/speed.json (its 64k and 120k prompts, two offsets each), DeepSeek tokenizer.
  pin MODS_JSON  (10-26, the user, report only) the final check's base built up to MODS_JSON one change at a time
         (expert profile; + GPU order and layer split; + cache decay; + the rest = what ships), each step against the
         base and against the step before: which change moves the KL percentiles most (feeds the IQ_Q8K port).
Rule (yardstick-kernel-rule, per scored position here): candidate KL mean <= 1.10 x the larger reference's mean; KL p90
<= 1.10 x the larger reference's p90 (10-26, the user: with no margin a rounding-only change failed about 1 time in 3,
having to beat the larger of two references - the same spread-based bound as the mean; before: <= the worse reference's
p90); positions with KL > 1 <= the worse reference's count + 1; changed top-1 picks vs the base <= 1.10 x the larger
reference's (10-26 16:40, Karl: was top-1 agreements >= the lower reference's - 1; rounding-level variants ranged 2,005-
2,015 of 2,040, so a margin of 1 was a coin flip); the mean NLL of the text <= the worse reference's (10-26 16:40, Karl:
a fifth check, stricter where it matters). All in rounding_checks().
Exit 0 = pass, 1 = fail, 2 = could not run, 3 = kernel error.
"""
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import tune  # noqa: E402

SC = tune.SC
V24 = f"{SC}/strata-v024"
OUT = f"{tune.R}/teacher"
PREFIX, SCORED, NSEG = 12000, 256, 8


def ids_file():
    p = f"{OUT}/long8.ids.json"
    if os.path.exists(p):
        return p
    sys.path.insert(0, f"{V24}/tools")
    import strata_tokenizer as ST  # noqa: E402
    tp = f"{SC}/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/pack-ist-das-2.00bpw/tokenizer"
    vocab = json.load(open(f"{tp}/vocab.json", encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = ST.Tokenizer(toks, open(f"{tp}/merges.txt", encoding="utf-8").read().split("\n"), json.load(open(f"{tp}/token_type.json")))
    sp = json.load(open(f"{SC}/prompts/speed.json"))
    texts = [p_["messages"][0]["content"] for p_ in sp if p_["size"] in ("64k", "120k")]
    segs = []
    for ti, text in enumerate(texts):
        ids = tok.encode(text)
        n = PREFIX + SCORED
        for k, off in enumerate((0, max(0, len(ids) - n))):
            if len(segs) < NSEG and len(ids) >= n:
                segs.append({"name": f"t{ti}o{k}", "ids": ids[off:off + n]})
    os.makedirs(OUT, exist_ok=True)
    json.dump({"version": "ds41-long8", "seg_tokens": PREFIX + SCORED, "segments": segs}, open(p, "w"))
    return p


def seg_files(ids):
    """one ids file per segment (10-25 fix): with DS4_SCORE_PREFIX set the engine joins all of a file's segments into one
    stream (ds4_main.cpp score(), "concat"), so 8 x 12,256 tokens ran past scorearm's --max-context 16384 ("the context
    is full", rc 1) and would have scored ~86K positions with only the first prefix read as one prompt; one segment per
    engine run keeps every scored position right after its own 12,000-token prefix"""
    d = json.load(open(ids))
    out = []
    for i, s in enumerate(d["segments"]):
        p = f"{OUT}/{os.path.basename(ids).replace('.ids.json', '')}-s{i}.ids.json"   # (10-26: named by the ids file - long8, short8)
        if not os.path.exists(p):
            json.dump(dict(d, segments=[s]), open(p, "w"))
        out.append(p)
    return out


def score(name, mods, ids, env):
    d = f"{OUT}/{name}"
    if os.path.exists(f"{d}/score.tsv") and os.path.exists(f"{d}/run.txt"):
        return d
    cfg = tune.mkcfg(f"score-{name}", mods)
    rows, segs, secs, low = [], [], 0, 999.0
    for i, sf in enumerate(seg_files(ids)):   # (one engine run a segment; the segment runs are merged into d/score.tsv)
        sd = f"{d}/s{i}"
        if not (os.path.exists(f"{sd}/score.tsv") and os.path.exists(f"{sd}/run.txt")):
            rc = subprocess.run(["bash", f"{tune.T}/scorearm.sh", sd, cfg, sf] + [f"{k}={v}" for k, v in env.items()]).returncode
            if rc == 3:
                print(f"KERNEL ERROR in the scoring run {name} (segment {i})"); sys.exit(3)
            if rc != 0 or not os.path.exists(f"{sd}/score.tsv"):
                why = open(sd + "/GUARD").read().strip() if os.path.exists(sd + "/GUARD") else \
                    (open(sd + "/engine.out", errors="replace").read().strip().splitlines() or [""])[-1][:300] \
                    if os.path.exists(sd + "/engine.out") else ""
                print(f"{name}: the scoring run of segment {i} failed (rc {rc}): {why}")
                sys.exit(2)
        r = open(f"{sd}/score.tsv").read().splitlines()
        for s in json.load(open(f"{sd}/score.tsv.seg.json"))["segments"]:
            segs.append(dict(s, first_line=s["first_line"] + len(rows), end_line=s["end_line"] + len(rows)))
        rows += r
        m = re.search(r"rc \d+, (\d+) s, lowest MemAvailable ([\d.]+) GB", open(f"{sd}/run.txt").read())
        if m:
            secs += int(m.group(1)); low = min(low, float(m.group(2)))
    open(f"{d}/score.tsv", "w").write("\n".join(rows) + "\n")
    json.dump({"segments": segs}, open(f"{d}/score.tsv.seg.json", "w"))
    open(f"{d}/run.txt", "w").write(f"rc 0, {secs} s, lowest MemAvailable {low} GB ({len(segs)} engine runs, one segment each)\n")
    return d


def compare(ref_dir, run_dir):
    kls, agree, n = kl_list(ref_dir, run_dir)
    return {"positions": n, "kl_mean": sum(kls) / max(n, 1), "kl_p90": kls[int(0.9 * (n - 1))] if n else float("nan"),
            "kl_max": kls[-1] if n else float("nan"),
            "kl_gt1": sum(1 for x in kls if x > 1), "top1_agree": agree}


def kl_list(ref_dir, run_dir):
    """the sorted per-position KLs, top-1 agreements, positions"""
    sys.path.insert(0, f"{V24}/tools")
    import quant_quality as qq  # noqa: E402
    a, b = qq.read_run(f"{ref_dir}/score.tsv"), qq.read_run(f"{run_dir}/score.tsv")
    kls, agree, n = [], 0, 0
    for name, rr in a.items():
        ra = b.get(name, {})
        for q in sorted(set(rr) & set(ra)):
            tr, _, topr, kr = rr[q]
            ta, _, topa, ka = ra[q]
            if tr != ta:
                raise SystemExit(f"{name} pos {q}: target differs (not the same text)")
            n += 1; agree += topr == topa
            da = dict(ka); floor = min(x for _, x in ka)
            pr = [math.exp(x) for _, x in kr]; pa = [math.exp(da.get(i, floor)) for i, _ in kr]
            sr, sa = sum(pr), sum(pa)
            kls.append(sum((x / sr) * math.log((x / sr) / (y / sa)) for x, y in zip(pr, pa) if x > 0))
    kls.sort()
    return kls, agree, n


PCTS = (50, 75, 90, 95, 99)


def pct_row(ref_dir, run_dir):
    kls, agree, n = kl_list(ref_dir, run_dir)
    r = {f"p{p}": kls[int(p / 100 * (n - 1))] for p in PCTS} if n else {}
    return dict(r, mean=sum(kls) / max(n, 1), max=kls[-1] if n else float("nan"), gt1=sum(1 for x in kls if x > 1),
                top1=agree, positions=n)


def text_nll(run_dir):
    """the mean negative log-probability of the text's own tokens over the run's scored positions (score.tsv's target
    log-prob) - the run's fit to the real text, whatever the base"""
    sys.path.insert(0, f"{V24}/tools")
    import quant_quality as qq  # noqa: E402
    lts = [lt for rr in qq.read_run(f"{run_dir}/score.tsv").values() for (_, lt, _, _) in rr.values()]
    return -sum(lts) / max(len(lts), 1)


def rounding_checks(c, r1, r2, c_dir=None, r1_dir=None, r2_dir=None, base_dir=None):
    """the rounding-level rule (yardstick-kernel-rule) on a candidate and two references, each against the same base -
    compare()'s or pct_row()'s rows; with the run folders also the text check. Returns ({check: ok}, detail):
      mean   KL mean <= 1.10 x the larger reference's
      p90    KL p90 <= 1.10 x the larger reference's (10-26 02:30)
      gt1    positions with KL > 1 <= the worse reference's + 1
      top1   changed top-1 picks vs the base <= 1.10 x the larger reference's (10-26 16:40, Karl; was: top-1 agreements >=
             the lower reference's - 1 - rounding-level variants range 2,005-2,015 of 2,040, a margin of 1 is a coin flip)
      nll    mean NLL of the text: the candidate's may exceed the base's by at most 1.10 x the larger reference's
             distance from the base (10-26 16:55, Karl; the 16:40 version - no worse than the worse reference's, no
             margin - failed a byte-identical candidate whenever both references fit the text better than the base)"""
    g = lambda r, a, b: r[a] if a in r else r[b]
    flips = lambda r: r["positions"] - g(r, "top1", "top1_agree")
    ck = {"mean": g(c, "mean", "kl_mean") <= 1.10 * max(g(r1, "mean", "kl_mean"), g(r2, "mean", "kl_mean")),
          "p90": g(c, "p90", "kl_p90") <= 1.10 * max(g(r1, "p90", "kl_p90"), g(r2, "p90", "kl_p90")),
          "gt1": g(c, "gt1", "kl_gt1") <= max(g(r1, "gt1", "kl_gt1"), g(r2, "gt1", "kl_gt1")) + 1,
          "top1": flips(c) <= 1.10 * max(flips(r1), flips(r2))}
    det = {"flips": [flips(c), flips(r1), flips(r2)], "flips_bound": round(1.10 * max(flips(r1), flips(r2)), 1)}
    if c_dir and r1_dir and r2_dir and base_dir:
        n = [text_nll(c_dir), text_nll(r1_dir), text_nll(r2_dir), text_nll(base_dir)]
        spread = max(abs(n[1] - n[3]), abs(n[2] - n[3]))
        ck["nll"] = n[0] - n[3] <= 1.10 * spread
        det["nll"] = [round(x, 4) for x in n]   # (cand, R1, R2, base)
        det["nll_excess"], det["nll_bound"] = round(n[0] - n[3], 4), round(1.10 * spread, 4)
    return ck, det


CHECK_LABELS = {"mean": "KL mean <= 1.10 x the larger reference", "p90": "KL p90 <= 1.10 x the larger reference",
                "gt1": "KL>1 count <= the worse reference's + 1",
                "top1": "changed top-1 picks <= 1.10 x the larger reference's",
                "nll": "text NLL above the base's <= 1.10 x the larger reference's distance"}


def placement(d):
    """the engine's placement lines from a scoring run's first segment (VRAM experts per card, the CPU lane)"""
    p = f"{d}/s0/engine.out"
    txt = open(p, errors="replace").read() if os.path.exists(p) else ""
    return [l.strip()[:200] for l in txt.splitlines() if re.search(r"CUDA[01] layers|routed experts on the CPU|RAM store:", l)]


def pinpoint(ids, fm):
    """pin MODS_JSON (10-26, the user: "Pinpoint check: yes, report only. Run it after the last end test and before the
    Maya head-to-head. Report which change moves the KL percentiles most; it feeds the IQ_Q8K port (GPU/CPU rounding
    mismatch is the likely source)"). The final check's base and references (teacher/final-*) are reused, so its four
    numbers stay comparable; each step adds one group of the ship config's settings on the same engine. Step 1 is the
    profile alone: the base was given the arm copy of the profile (tmp/ds41-profile-arm.bin, as the round's arms had
    updated it), the ship config the shipped file - so which experts sit in VRAM / the RAM store differs there already.
    Step 4 is the whole ship config again: it must be byte-identical to final-cand-final (the scoring is deterministic)."""
    env0 = {"DS4_SCORE_PREFIX": str(PREFIX)}
    keep = {k: v for k, v in fm.items() if k in ("engine",)}
    prof = {"--expert-profile": fm.get("profile", tune.SHIPPED)}
    groups = [("pin1-profile", "the ship's expert profile file", ()),
              ("pin2-placement", "+ GPU order and layer split", ("order", "DS4_SPLIT")),
              ("pin3-decay", "+ cache decay", ("DS4_CACHE_DECAY",)),
              ("pin4-ship", "+ the rest (settle, Engram cache, ...) = what ships", None)]
    steps, cur = [], dict(keep, **prof)
    for name, note, ks in groups:
        if ks is None:
            cur = dict(fm, **prof)
        else:
            cur = dict(cur, **{k: fm[k] for k in ks if k in fm})
        steps.append((name, note, dict(cur)))
    base = score("final-base", {}, ids, env0)
    refs = {k: f"{OUT}/final-{k}" for k in ("R1-chunk4096", "R2-cpu-share")}
    if not all(os.path.exists(f"{d}/score.tsv") for d in refs.values()):
        print("pin: the final check's references are missing (run skipcheck.py final first)"); return 2
    dirs = {name: score(f"final-{name}", m, ids, env0) for name, _, m in steps}
    L = [f"# Pinpoint: which change moves the KL percentiles (report only, {tune.engine_of(fm)})", "",
         "Teacher-forced, 8 segments x 256 positions (2040 compared), against the final check's base (the engine defaults).",
         "Each step adds one group of the ship config's settings. 'vs base' = KL of the step against the base; "
         "'vs previous' = KL of the step against the step before (what that one change moves).", ""]
    hdr = "| run | vs | " + " | ".join(f"p{p}" for p in PCTS) + " | mean | max | KL>1 | top-1 |"
    L += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    def row(label, vs, r):
        return (f"| {label} | {vs} | " + " | ".join(f"{r[f'p{p}']:.5f}" for p in PCTS) +
                f" | {r['mean']:.5f} | {r['max']:.3f} | {r['gt1']} | {r['top1']} |")
    rows = {}
    for k, d in refs.items():
        L.append(row(f"reference {k}", "base", pct_row(base, d)))
    prev, prev_name = base, "base"
    for name, note, m in steps:
        rb, rp = pct_row(base, dirs[name]), pct_row(prev, dirs[name])
        rows[name] = {"note": note, "mods": m, "vs_base": rb, "vs_prev": rp, "prev": prev_name}
        L.append(row(f"{name} ({note})", "base", rb))
        L.append(row("", prev_name, rp))
        prev, prev_name = dirs[name], name
    most = max(rows, key=lambda k: (rows[k]["vs_prev"]["p90"], rows[k]["vs_prev"]["mean"]))
    same = open(f"{dirs['pin4-ship']}/score.tsv", "rb").read() == open(f"{OUT}/final-cand-final/score.tsv", "rb").read() \
        if os.path.exists(f"{OUT}/final-cand-final/score.tsv") else None
    L += ["", f"Moves the percentiles most: **{most}** ({rows[most]['note']}): against the step before, p90 "
              f"{rows[most]['vs_prev']['p90']:.5f}, mean {rows[most]['vs_prev']['mean']:.5f}.",
          f"pin4-ship byte-identical to final-cand-final (the final check's candidate): {same}.", "", "Placement (segment 0):"]
    for name, d in [("base", base)] + [(n, dirs[n]) for n, _, _ in steps]:
        L.append(f"- {name}: " + " / ".join(placement(d)))
    L += ["", "Run times: " + "; ".join(f"{n}: {open(f'{dirs[n]}/run.txt').read().strip()}" for n, _, _ in steps)]
    open(f"{tune.R}/pinpoint.md", "w").write("\n".join(L) + "\n")
    json.dump({"steps": rows, "most": most, "pin4_identical_to_cand_final": same}, open(f"{OUT}/pin-result.json", "w"), indent=1)
    print("\n".join(L))
    return 0


def decode(mods=None, label="cli-decode", n=256):
    """the command-line decode of the W1 prompt (n tokens, DS4_TOKLOG=1): the only place the engine prints Engram reads
    per token and the CPU lane's share of a token (ds4_main.cpp:1427-1452); mods = a config as tune.py builds it (default:
    the reference, two GPUs). 20:40 fix: the first run (10-24 15:20) fed W1's raw text, the engine's greedy decode ended
    at once (1 token); now the prompt goes through the GGUF's chat template (thinking on, as the server renders it) and
    DS4_NO_EOS=1 decodes all n tokens"""
    sys.path.insert(0, f"{V24}/tools")
    sys.path.insert(0, V24)
    import strata_tokenizer as ST  # noqa: E402
    from serve.frontend import ChatTemplate  # noqa: E402
    sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
    import abrun  # noqa: E402
    tp = f"{SC}/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/pack-ist-das-2.00bpw/tokenizer"
    vocab = json.load(open(f"{tp}/vocab.json", encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = ST.Tokenizer(toks, open(f"{tp}/merges.txt", encoding="utf-8").read().split("\n"), json.load(open(f"{tp}/token_type.json")))
    w1 = next(w for w in json.load(open(abrun.WL))["normal"] if w["id"].startswith("W1"))
    text = ChatTemplate(f"{V24}/serve/fixtures/deepseek41/chat_template.jinja").render(w1["messages"])
    ids = tok.encode(text, parse_special=True)
    os.makedirs(OUT, exist_ok=True)
    open(f"{OUT}/w1t.ids", "w").write(",".join(map(str, ids)))
    d = f"{OUT}/{label}"
    m = dict(mods or {})
    prof = m.pop("profile", tune.SHIPPED)
    cfg = tune.mkcfg(label, dict(m, **{"--expert-profile": tune.PROF}))
    subprocess.run(["cp", prof, tune.PROF])
    rc = subprocess.run(["bash", f"{tune.T}/scorearm.sh", d, cfg, f"decode:{OUT}/w1t.ids:{n}", "DS4_TOKLOG=1",
                         "DS4_NO_EOS=1"]).returncode
    if rc == 3:
        print("KERNEL ERROR"); sys.exit(3)
    txt = open(f"{d}/engine.out", errors="replace").read() if os.path.exists(f"{d}/engine.out") else ""
    import re
    lines = [l for l in txt.splitlines() if re.search(r"engram|tok/s|ms/tok|per token", l, re.I)]
    print(f"rc {rc}; {len(ids)} prompt tokens; " + (open(f"{d}/run.txt").read().strip() if os.path.exists(f"{d}/run.txt") else ""))
    print("\n".join(lines[-12:]) or txt[-1500:])
    return 0 if rc == 0 else 2


def main():
    mode = sys.argv[1]
    if mode == "decode":
        return decode(json.loads(sys.argv[2]) if len(sys.argv) > 2 else None, *(sys.argv[3:4] or ["cli-decode"]),
                      n=int(sys.argv[4]) if len(sys.argv) > 4 else 256)
    ids = ids_file()
    if mode == "pin":
        return pinpoint(ids, json.loads(sys.argv[2]))
    if mode == "skip":
        base = {"one5080": True, "--expert-profile": "none", "DS4_LAYER_CACHE_MB": 4096}   # layer cache capped (MemAvailable)
        env0 = {"DS4_SCORE_PREFIX": str(PREFIX), "DS4_CHUNK": "1024", "STRATA_DS4_PROMPT_SKIP": "0"}
        runs = {"base": (base, env0), "R1-chunk2048": (base, dict(env0, DS4_CHUNK="2048")),
                "R2-cpu-share": (dict(base, **{"--reserve-mib": 2600}), env0),
                "cand-skip1": (base, dict(env0, STRATA_DS4_PROMPT_SKIP="1"))}
        prefix = "skip"
    elif mode == "vs":
        bm, cm, prefix = json.loads(sys.argv[2]), json.loads(sys.argv[3]), sys.argv[4]
        env0 = {"DS4_SCORE_PREFIX": str(PREFIX)}
        bm = dict(bm, **{"--expert-profile": bm.get("profile", tune.SHIPPED)})
        cm = dict(cm, **{"--expert-profile": cm.get("profile", tune.SHIPPED)})
        ch = 2048 if int(bm.get("--prefill-chunk", 8192)) == 4096 else 4096
        runs = {"base": (bm, env0), f"R1-chunk{ch}": (dict(bm, **{"--prefill-chunk": ch}), env0),
                "R2-cpu-share": (dict(bm, **{"--reserve-mib": 2600}), env0), "cand": (cm, env0)}
    else:
        fm = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        if not fm:
            print("final: the confirmed config is the reference - nothing to check"); return 0
        env0 = {"DS4_SCORE_PREFIX": str(PREFIX)}
        prof = {"--expert-profile": fm.get("profile", tune.SHIPPED)}
        runs = {"base": ({}, env0), "R1-chunk4096": ({"--prefill-chunk": 4096}, env0),
                "R2-cpu-share": ({"--reserve-mib": 2600}, env0), "cand-final": (dict(fm, **prof), env0)}
        prefix = "final"
    dirs = {k: score(f"{prefix}-{k}", m, ids, e) for k, (m, e) in runs.items()}
    names = list(dirs)
    res = {k: compare(dirs["base"], dirs[k]) for k in names[1:]}
    for k, r in res.items():
        print(f"{prefix} {k} vs base: {r['positions']} positions, KL mean {r['kl_mean']:.5f}, p90 {r['kl_p90']:.5f}, "
              f"max {r['kl_max']:.5f}, KL>1 {r['kl_gt1']}, top-1 agree {r['top1_agree']}")
    r1, r2, c = res[names[1]], res[names[2]], res[names[3]]
    ck, det = rounding_checks(c, r1, r2, dirs[names[3]], dirs[names[1]], dirs[names[2]], dirs["base"])
    checks = {CHECK_LABELS[k]: v for k, v in ck.items()}
    print(f"  changed top-1 picks {det['flips']} (cand, R1, R2; bound {det['flips_bound']}); mean NLL of the text "
          f"{det.get('nll')} (cand, R1, R2, base; above the base {det.get('nll_excess')}, bound {det.get('nll_bound')})")
    for k, v in checks.items():
        print(f"  {'ok  ' if v else 'FAIL'} {k}")
    ok = all(checks.values())
    times = {k: open(f"{d}/run.txt").read().strip() for k, d in dirs.items()}
    # (10-25) a candidate whose scores are byte-identical to the base's changed nothing: for the skip that means it did
    # not engage on this path (e.g. layer-major), so it is no test of the skip - reported as "could not test", not a pass
    same = open(f"{dirs['base']}/score.tsv", "rb").read() == open(f"{dirs[names[3]]}/score.tsv", "rb").read()
    verdict = "PASS (rounding-level)" if ok else "FAIL"
    if same and mode == "skip":
        verdict = "NOT TESTED: the skip-on scores are byte-identical to the base's (the skip did not engage)"
    elif same:
        verdict += " (byte-identical to the base)"
    print(f"{prefix}: {verdict}; run times: {json.dumps(times)}")
    json.dump({"res": res, "checks": checks, "pass": ok, "identical_to_base": same, "times": times},
              open(f"{OUT}/{prefix}-result.json", "w"), indent=1)
    if same and mode == "skip":
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
