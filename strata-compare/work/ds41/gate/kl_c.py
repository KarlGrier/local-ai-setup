#!/usr/bin/env python3
"""kl_c.py check OUTDIR | run OUTDIR | selftest [DIR] - 2026-11-08 (gap D1; Karl 11-07, results/ds41/GAP-C234-PLAN.md
sections 1, 2 and 4: "D1: C2, C3 and C4, plus the KL check and the long-prompt memory arms. Yes, both are daily conditions
for C, the same as for B"). C's trunk KL check vs A under Karl's 11-04 noise-band rule: teacher-forced scoring with C's
placement (configs/DS41-gate-C0.json: DS4_SPLIT 0,40 - the 40 trunk layers on the 5080 - and its own pack; drafting plays
no part: scorearm.sh passes --dspark none), on the first gate's KL harness exactly as kl_b.py / kl_noise.py / kl_bstore.py
ran it (skipcheck's long8: 8 segments, a 12,000-token prefix read as one prompt + 256 scored positions, one strata-dsv41
--score run each via work/ds41/tune/scorearm.sh with DS4_SCORE_PREFIX=12000 + DS4_FLOW_STATS=1; before every segment the
profile path the config names gets the first gate's snapshot, results/ds41/gate-1103-1354/profile-snapshot.bin).
A, Aa and Ab are REUSED from 11-03 / 11-04 (the plan: "same build, config and snapshot, so this is one new scoring run"):
  A   = results/ds41/gate-1103-1354/kl/base, only when kl_noise.reuse_check() finds nothing changed since its scores (the
        engine's sha256 = its SHA256 file and older than A's scores; cfg-base.json = today's derivation; scorearm.sh,
        skipcheck.py, kl_b.py and the segment files older than A's scores) - else `check` refuses (no new A is scored here:
        the band would no longer be the 11-04 one)
  band = results/ds41/gate-1104-0725/kl-noise/kl-noise-result.json's (Aa = --vram-experts 0.98, Ab = warmed by a W1
        decode): top-1 40, NLL 0.00701 - recomputed here from the stored Aa / Ab / A scores and refused if it differs
The verdict (Karl's 11-04 rule, as for B and B<N>: kl_noise.py / kl_bstore.py): PASS iff C0's changed top-1 picks vs A
<= the band's top-1 AND its NLL distance |NLL(C0) - NLL(A)| <= the band's NLL (inside the band; no 1.10 factor); else
FAIL. KL mean / p90 / KL>1 and byte-identity: report only. NO VERDICT (exit 2) if the scoring did not put all 40 trunk
layers on one card ("CUDA<n> layers [0, 39]" in segment 0's engine lines: not C's placement).
  check OUTDIR   no GPU, before the gap: the reuse check, the band recomputed, cfg-C0.json written (= DS41-gate-C0.json but
                 for its comment), rule.txt; exit 0 ready, 1 not
  run OUTDIR     inside an open gap only (tmp/port-gap.lockpid): check, then the one scoring run (~5.5 min) -> OUTDIR/C0,
                 kl-c-result.json, kl-c.md; exit 0 PASS, 1 FAIL, 2 could not run / no verdict, 3 kernel error
  selftest [DIR] synthetic verdict cases + the stored band recomputed (read-only); DIR under work/ds41/gate/scratch-d12
Written at the desk 11-08; not run on the GPU.
"""
import json
import os
import re
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/gate")
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import kl_b  # noqa: E402
import kl_noise  # noqa: E402
import skipcheck as SK  # noqa: E402

SC = kl_b.SC
G1 = f"{SC}/results/ds41/gate-1103-1354"
G2 = f"{SC}/results/ds41/gate-1104-0725"
C0CFG = f"{SC}/configs/DS41-gate-C0.json"
SNAP = f"{G1}/profile-snapshot.bin"
SCRATCH = f"{SC}/work/ds41/gate/scratch-d12"
PLACE = re.compile(r"CUDA\d layers \[0, 39\]")
RULE = ("kl_c.py rule, fixed 2026-11-08 at the desk before any run (Karl 11-07: C's KL check under his 11-04 rule is a daily "
        "condition for C, as for B; GAP-C234-PLAN.md section 1 item 2)\n"
        "Karl (11-04, verbatim, for B): \"" + kl_noise.KARL + "\"\n"
        "applied to C: C0's placement (configs/DS41-gate-C0.json; scorearm.sh --dspark none) teacher-forced on the 11-03 KL "
        "harness; A = the first gate's A scoring and the band = the second gate's Aa / Ab (both reused, unchanged); PASS iff "
        "C0's changed top-1 picks vs A <= band top-1 AND |NLL(C0) - NLL(A)| <= band NLL; else FAIL. Report only: KL mean, p90, "
        "KL>1, byte-identity. No verdict if the scoring's placement is not all 40 trunk layers on one card.\n")


def band_recomputed():
    """-> (band stored, band recomputed from the stored scores, same?)"""
    nb = json.load(open(f"{G2}/kl-noise/kl-noise-result.json"))
    a = f"{G1}/kl/base"
    pa, pb = kl_noise.pair(a, f"{G2}/kl-noise/Aa"), kl_noise.pair(a, f"{G2}/kl-noise/Ab")
    rec = {"top1": max(pa["top1_changed"], pb["top1_changed"]), "nll": max(pa["nll_distance"], pb["nll_distance"])}
    same = rec["top1"] == nb["band"]["top1"] and abs(rec["nll"] - nb["band"]["nll"]) < 1e-9
    return nb["band"], rec, same


def verdict(r, band):
    ck = {"top1": r["top1_changed"] <= band["top1"], "nll": r["nll_distance"] <= band["nll"]}
    return all(ck.values()), ck


def derive(o):
    c = json.load(open(C0CFG))
    c["_comment"] = "kl_c.py: C0 (C's placement) on the KL harness. " + c.get("_comment", "")[:200]
    p = f"{o}/cfg-C0.json"
    json.dump(c, open(p, "w"), indent=1)
    return p, c["args"][c["args"].index("--expert-profile") + 1]


def check(o):
    os.makedirs(o, exist_ok=True)
    why = []
    ok_reuse, rw = kl_noise.reuse_check(o, f"{G1}/kl", SNAP)
    if not ok_reuse:
        why.append("A cannot be reused: " + "; ".join(rw))
    try:
        stored, rec, same = band_recomputed()
        if not same:
            why.append(f"the stored band {stored} differs from the one recomputed from the stored scores {rec}")
    except (OSError, ValueError, KeyError) as e:
        why.append(f"the band could not be read or recomputed: {type(e).__name__}: {e}")
        stored = None
    cfg, prof = derive(o)
    if not prof.endswith("/logs/ds41/gate/profile-arm.bin"):
        why.append(f"cfg-C0's --expert-profile is {prof}, not the gate's copy")
    open(f"{o}/rule.txt", "w").write(RULE + f"band (11-04, reused): {stored}\n")
    print(RULE + f"band (11-04, reused): {stored}")
    print("check: " + ("OK" if not why else "NOT READY - " + " | ".join(why)), flush=True)
    return not why, stored


def run(o):
    lp = f"{SC}/tmp/port-gap.lockpid"
    if not (os.path.exists(lp) and os.path.getsize(lp) > 0):
        print("kl_c.py run: no gap is open (tmp/port-gap.lockpid) - nothing runs"); return 2
    ok, band = check(o)
    if not ok:
        return 2
    cfg, prof = derive(o)
    d = kl_b.score(o, "C0", cfg, prof, SNAP, SK.seg_files(SK.ids_file()))   # (exits 2 / 3 itself on a failed segment)
    r = kl_noise.pair(f"{G1}/kl/base", d)
    pl = kl_noise.placement(d)
    eng = open(f"{d}/s0/engine.out", errors="replace").read() if os.path.exists(f"{d}/s0/engine.out") else ""
    placed = bool(PLACE.search(eng))
    ok, ck = verdict(r, band)
    same_b = open(f"{G1}/kl/cand-B/score.tsv", "rb").read() == open(f"{d}/score.tsv", "rb").read()
    out = {"vs_A": r, "band": band, "checks": ck, "pass": ok if placed else None, "placement_ok": placed,
           "placement": pl, "byte_identical_to_B": same_b, "time": open(f"{d}/run.txt").read().strip(),
           "verdict": ("PASS" if ok else "FAIL") if placed else "NO VERDICT"}
    json.dump(out, open(f"{o}/kl-c-result.json", "w"), indent=1)
    L = ["# C (C0's placement) vs A on the KL harness, Karl's 11-04 noise-band rule", "",
         f"Verdict: **{out['verdict']}**" + ("" if placed else " (the scoring did not put the 40 trunk layers on one card)"), "",
         f"- C0 vs A: changed top-1 picks {r['top1_changed']} (band {band['top1']}), NLL distance {r['nll_distance']:.5f} "
         f"(band {band['nll']:.5f}); KL mean {r['kl_mean']:.5f}, p90 {r['kl_p90']:.5f}, KL>1 {r['kl_gt1']}; byte-identical to "
         f"B's scores: {same_b}",
         f"- VRAM experts {pl}; {out['time']}"]
    open(f"{o}/kl-c.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    return 2 if not placed else (0 if ok else 1)


def selftest(base):
    rb = os.path.realpath(base)
    if not (rb == os.path.realpath(SCRATCH) or rb.startswith(os.path.realpath(SCRATCH) + os.sep)):
        print(f"selftest writes only under {SCRATCH}"); return 2
    ok = True

    def chk(what, cond):
        nonlocal ok
        print(f"{'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and cond

    band = {"top1": 40, "nll": 0.00701}
    for name, t1, nll, want in (("inside", 38, 0.00698, True), ("top-1 at the band", 40, 0.007, True),
                                ("top-1 over", 41, 0.001, False), ("NLL over", 10, 0.00702, False)):
        v, ck = verdict({"top1_changed": t1, "nll_distance": nll}, band)
        chk(f"verdict {name}: {t1} / {nll} vs {band} -> {'PASS' if v else 'FAIL'} {ck}", v == want)
    chk("placement line: 'CUDA1 layers [0, 39] + head' matches, A's 'CUDA1 layers [8, 39]' does not",
        bool(PLACE.search("ds4: CUDA1 layers [0, 39] + head: weights 5.99 GB")) and not PLACE.search("ds4: CUDA1 layers [8, 39] + head"))
    try:
        stored, rec, same = band_recomputed()
        chk(f"the stored 11-04 band {stored} = recomputed from the stored A / Aa / Ab scores {rec}", same and stored["top1"] == 40)
        bp = kl_noise.pair(f"{G1}/kl/base", f"{G1}/kl/cand-B")
        v, _ = verdict(bp, stored)
        chk(f"B's stored scores under this verdict: {bp['top1_changed']} / {bp['nll_distance']:.5f} -> {'PASS' if v else 'FAIL'} "
            "(the 11-04 report: PASS)", v)
    except Exception as e:  # noqa: BLE001
        chk(f"stored band: {type(e).__name__}: {e}", False)
    c = json.load(open(C0CFG))
    chk(f"C0's config: --dspark {c['args'][c['args'].index('--dspark') + 1]}, DS4_SPLIT {c['env'].get('DS4_SPLIT')}, the gate's "
        "profile copy, its own slot folder", c["env"].get("DS4_SPLIT") == "0,40" and c["args"][c["args"].index("--dspark") + 1] == "off"
        and c["args"][c["args"].index("--expert-profile") + 1].endswith("/logs/ds41/gate/profile-arm.bin")
        and c["env"]["STRATA_DS4_SLOT_DIR"].endswith("/logs/ds41/gate-slots/C0"))
    print("KL_C SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("check", "run", "selftest"):
        print(__doc__); return 2
    if a[0] == "selftest":
        return selftest(a[1] if len(a) > 1 else f"{SCRATCH}/kl-c-selftest")
    if a[0] == "check":
        ok, _ = check(a[1])
        return 0 if ok else 1
    return run(a[1])


if __name__ == "__main__":
    sys.exit(main())
