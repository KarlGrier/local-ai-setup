#!/usr/bin/env python3
"""kl_b.py OUTDIR SNAPSHOT - 11-03 (Karl: "B's KL / distribution check against A (the round's scorearm.sh / skipcheck.py
form) is REQUIRED before any daily switch"). Inside an open gap only (kl-b.sh starts it). The round's usual check, its
"vs" form (skipcheck.py vs: a candidate against a base, two rounding references on the base), on the gate's configs:
  base          configs/DS41-gate-A.json (the daily config)
  R1-chunk4096  A with --prefill-chunk 4096 (another prompt chunk: a rounding-level variant)
  R2-cpu-share  A with --reserve-mib 2600 (fewer VRAM experts: more of them on the CPU lane)
  cand-B        configs/DS41-gate-B.json (the 5080 alone)
Each = 8 teacher-forced segments (skipcheck's long8: 12,000 prompt tokens read as one prompt - 2 chunks of 8192 - then
256 positions scored), one strata-dsv41 --score run per
segment through work/ds41/tune/scorearm.sh (its guards: MemAvailable < 12 GB or the 5080 under 300 MiB -> killed; a
kernel-check failure -> exit 3; 900 s a segment), with DS4_FLOW_STATS=1 (print only: the engine's per-prompt stream
line, which says "(layer-major, N chunks ...)" when B's one-device path ran - whether the check covered it is
reported; lm_begin's own cost test may stream a 2-chunk prompt per chunk instead). Before every segment the expert
profile path the configs name (logs/ds41/gate/profile-arm.bin) gets a fresh copy of SNAPSHOT (the gap's daily-profile snapshot), so A and B start
from the same profile. The verdict: skipcheck.rounding_checks (the 10-26 rule: KL mean and p90 <= 1.10 x the larger
reference's, KL>1 count <= the worse reference's + 1, changed top-1 picks <= 1.10 x the larger reference's, text NLL
above the base's <= 1.10 x the larger reference's distance). Report only, no GPU: A and B against the round's stored
stock base and references (results/ds41/tuning/teacher/final-*), as the 10-26 final gate judged the daily config.
Resumable: a finished segment is not run again. -> OUTDIR/kl-result.json, OUTDIR/kl.md. Exit 0 PASS, 1 FAIL, 2 could not
run, 3 kernel error.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import skipcheck as SK  # noqa: E402

SC = "/home/USER/ai-speed-testing/strata-compare"
T = f"{SC}/work/ds41/tune"
ORDER = ["base", "cand-B", "R1-chunk4096", "R2-cpu-share"]


def set_arg(a, k, v):
    if k in a:
        a[a.index(k) + 1] = str(v)
    else:
        a += [k, str(v)]


def configs(o):
    A = json.load(open(f"{SC}/configs/DS41-gate-A.json"))
    B = json.load(open(f"{SC}/configs/DS41-gate-B.json"))
    out = {}
    for name, c, mod in (("base", A, None), ("R1-chunk4096", A, ("--prefill-chunk", 4096)),
                         ("R2-cpu-share", A, ("--reserve-mib", 2600)), ("cand-B", B, None)):
        c = json.loads(json.dumps(c))
        if mod:
            set_arg(c["args"], *mod)
        c["_comment"] = f"kl_b.py {name}: " + c.get("_comment", "")[:300]
        p = f"{o}/cfg-{name}.json"
        json.dump(c, open(p, "w"), indent=1)
        out[name] = (p, c["args"][c["args"].index("--expert-profile") + 1])
    return out


def score(o, name, cfg, prof, snap, segs):
    d = f"{o}/{name}"
    if os.path.exists(f"{d}/score.tsv") and os.path.exists(f"{d}/run.txt"):
        return d
    rows, sj, secs, low = [], [], 0, 999.0
    for i, sf in enumerate(segs):
        sd = f"{d}/s{i}"
        if not (os.path.exists(f"{sd}/score.tsv") and os.path.exists(f"{sd}/run.txt")):
            shutil.copy(snap, prof)
            t0 = time.time()
            rc = subprocess.run(["bash", f"{T}/scorearm.sh", sd, cfg, sf, f"DS4_SCORE_PREFIX={SK.PREFIX}",
                                 "DS4_FLOW_STATS=1"]).returncode
            print(f"  {name} segment {i}: rc {rc}, {time.time() - t0:.0f} s", flush=True)
            if rc == 3:
                print(f"KERNEL ERROR in the scoring run {name} (segment {i})", flush=True)
                sys.exit(3)
            if rc != 0 or not os.path.exists(f"{sd}/score.tsv"):
                why = open(f"{sd}/GUARD").read().strip() if os.path.exists(f"{sd}/GUARD") else \
                    ((open(f"{sd}/engine.out", errors="replace").read().strip().splitlines() or [""])[-1][:300]
                     if os.path.exists(f"{sd}/engine.out") else "")
                print(f"{name}: the scoring run of segment {i} failed (rc {rc}): {why}", flush=True)
                sys.exit(2)
        r = open(f"{sd}/score.tsv").read().splitlines()
        for s in json.load(open(f"{sd}/score.tsv.seg.json"))["segments"]:
            sj.append(dict(s, first_line=s["first_line"] + len(rows), end_line=s["end_line"] + len(rows)))
        rows += r
        m = re.search(r"rc \d+, (\d+) s, lowest MemAvailable ([\d.]+) GB", open(f"{sd}/run.txt").read())
        if m:
            secs += int(m.group(1)); low = min(low, float(m.group(2)))
    open(f"{d}/score.tsv", "w").write("\n".join(rows) + "\n")
    json.dump({"segments": sj}, open(f"{d}/score.tsv.seg.json", "w"))
    open(f"{d}/run.txt", "w").write(f"rc 0, {secs} s, lowest MemAvailable {low} GB ({len(sj)} engine runs, one segment each)\n")
    return d


def lines(d, pat):
    n = 0
    for i in range(8):
        p = f"{d}/s{i}/engine.out"
        if os.path.exists(p):
            n += sum(1 for l in open(p, errors="replace") if pat in l)
    return n


def main():
    o, snap = sys.argv[1], sys.argv[2]
    os.makedirs(o, exist_ok=True)
    cf = configs(o)
    segs = SK.seg_files(SK.ids_file())   # (the stored long8 segments: results/ds41/tuning/teacher/long8-s*.ids.json)
    dirs = {}
    for name in ORDER:
        p, prof = cf[name]
        print(f"scoring {name} ({p})", flush=True)
        dirs[name] = score(o, name, p, prof, snap, segs)
    res = {k: SK.compare(dirs["base"], dirs[k]) for k in ORDER[1:]}
    r1, r2, c = res["R1-chunk4096"], res["R2-cpu-share"], res["cand-B"]
    ck, det = SK.rounding_checks(c, r1, r2, dirs["cand-B"], dirs["R1-chunk4096"], dirs["R2-cpu-share"], dirs["base"])
    checks = {SK.CHECK_LABELS[k]: v for k, v in ck.items()}
    ok = all(checks.values())
    same = open(f"{dirs['base']}/score.tsv", "rb").read() == open(f"{dirs['cand-B']}/score.tsv", "rb").read()
    times = {k: open(f"{d}/run.txt").read().strip() for k, d in dirs.items()}
    # report only: A and B against the round's stored stock base and references (the 10-26 final gate's)
    stock = {}
    tb = f"{SK.OUT}/final-base"
    trefs = {"R1-chunk4096": f"{SK.OUT}/final-R1-chunk4096", "R2-cpu-share": f"{SK.OUT}/final-R2-cpu-share"}
    if all(os.path.exists(f"{x}/score.tsv") for x in [tb] + list(trefs.values())):
        sr = {k: SK.compare(tb, d) for k, d in trefs.items()}
        for lab in ("base", "cand-B"):
            cc = SK.compare(tb, dirs[lab])
            k2, d2 = SK.rounding_checks(cc, sr["R1-chunk4096"], sr["R2-cpu-share"], dirs[lab], trefs["R1-chunk4096"],
                                        trefs["R2-cpu-share"], tb)
            stock["A" if lab == "base" else "B"] = {"vs_stock": cc, "checks": {SK.CHECK_LABELS[k]: v for k, v in k2.items()},
                                                    "pass": all(k2.values()), "detail": d2}
    out = {"res": res, "checks": checks, "pass": ok, "detail": det, "identical_to_base": same, "times": times,
           "prompt_skip_lines": {k: lines(d, "prompt skip") for k, d in dirs.items()},
           "layer_major_lines": {k: lines(d, "(layer-major,") for k, d in dirs.items()},
           "placement": {k: SK.placement(d) for k, d in dirs.items()}, "report_only_vs_stock": stock}
    json.dump(out, open(f"{o}/kl-result.json", "w"), indent=1)
    f = lambda r: (f"{r['positions']} positions, KL mean {r['kl_mean']:.5f}, p90 {r['kl_p90']:.5f}, max {r['kl_max']:.3f}, "  # noqa: E731
                   f"KL>1 {r['kl_gt1']}, top-1 agree {r['top1_agree']}")
    L = ["# B (the 5080 alone) vs A (daily): teacher-forced KL check", "",
         f"Verdict: **{'PASS (rounding-level)' if ok else 'FAIL'}**" + (" (byte-identical to the base)" if same else ""), ""]
    L += [f"- {k} vs base (A): {f(r)}" for k, r in res.items()]
    L += [f"- changed top-1 picks {det['flips']} (B, R1, R2; bound {det['flips_bound']}); text NLL {det.get('nll')} "
          f"(B, R1, R2, A; B above A {det.get('nll_excess')}, bound {det.get('nll_bound')})"]
    L += [f"- {'ok  ' if v else 'FAIL'} {k}" for k, v in checks.items()]
    lm = out["layer_major_lines"].get("cand-B", 0)
    L += ["", "Prompt-skip engine lines (8 segments each): " + json.dumps(out["prompt_skip_lines"]),
          f"B's one-device layer-major prompt path (DS4_FLOW_STATS lines \"(layer-major, N chunks\"): {lm} of 8 "
          "segments" + ("" if lm else " - NOT covered by this check: for a 12,000-token prefix (2 chunks) the engine "
          "chose per-chunk streaming (lm_begin's cost test, model.cu:8113); a >= 3-chunk prefix needs scorearm.sh's "
          "--max-context 16384 raised - Karl decides"),
          "", "Run times: " + "; ".join(f"{k}: {v}" for k, v in times.items())]
    for lab, s in stock.items():
        L.append(f"- report only, {lab} vs stock v0.2.6 (teacher/final-base, its stored references): "
                 f"{'PASS' if s['pass'] else 'FAIL'}; {f(s['vs_stock'])}; changed picks {s['detail']['flips']}")
    open(f"{o}/kl.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
