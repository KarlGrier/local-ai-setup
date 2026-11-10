#!/usr/bin/env python3
"""kl_noise.py OUTDIR A1_KL_DIR A1_SNAPSHOT - 11-04 (Karl's rule for B, set before any result; replaces the A-vs-A repeat,
which is byte-identical by construction). Inside an open gap only (gate.sh next, step KLV). Karl, verbatim:
  "compare A against two placement variants of A that happen in normal use, on the same KL harness and prompts: (a) A with
  a different VRAM expert-slot count, like the 3,238 vs 3,300 seen between starts; (b) A with the expert cache warmed by a
  different prompt first. The noise band is the largest top-1 change count and the largest NLL difference among those
  A-vs-variant pairs. B passes if both of its failing numbers fall inside that band; otherwise B stays off. The
  long-prompt memory arms and my OK are still needed before any switch."
The harness: kl_b.py's (skipcheck's long8: 8 segments of a 12,000-token prefix read as one prompt + 256 scored positions,
one strata-dsv41 --score run each via work/ds41/tune/scorearm.sh; env DS4_SCORE_PREFIX=12000 + DS4_FLOW_STATS=1 (print
only); configs/DS41-gate-A.json as kl_b.py derives it; the profile path it names gets the snapshot before every segment).
  A   = the first gate's A scoring (A1_KL_DIR/base) when nothing changed since (the engine's sha256 = its SHA256 file and
        older than A's scores; cfg-base.json = today's derivation; scorearm.sh, skipcheck.py, kl_b.py and the segment files
        older than A's scores) - else A is scored here the same way. A1_SNAPSHOT = the profile snapshot A used.
  Aa  = A with --vram-experts 0.98: 2 % fewer VRAM experts. Karl's 3,238 / 3,300 were the Qwen engine's 5080 and 4060 Ti
        slots in ONE run, not two starts; DeepSeek's daily config gets the SAME count at every real start at 128K - 451
        (4060 Ti, layers 0-7) + 857 (5080, layers 8-39) = 1,308 in all 9 starts with the cache on that we logged
        (results/ds41/tuning: ctx-128k 10-26, long100k / lc-e50 / id-old / id-new / id-old-again / slotram-test 10-27,
        sweep-ds-on-v10 and gate-A 11-03; logs/ds41/engine-daily.log the same). The count is set at load from the free
        VRAM after weights and caches, less --reserve-mib (600), times --vram-experts (model.cu:3926-3958: a budget per
        GPU group, floor(share x 384) a layer); the profile only picks which experts. It moves with the context size
        only (32K 1,330, 64K 1,320, 128K 1,308; the harness's 16K 1,335). No between-starts difference, so Karl's
        example ratio (3,238 / 3,300 = 0.981) is used: 2 % fewer. The engine's start line gives the count reached.
  Ab  = A with the expert cache warmed by a different prompt first. The engine does move experts during a run: its
        adaptive cache swaps the hottest CPU-lane picks into VRAM between windows (cache_tick, model.cu:8433 / 8644; 1,171
        moves in a 512-token decode, teacher/cli-decode-final), starting from the profile's counts as its heat
        (model.cu:4019-4024); daily's DS4_SETTLE_MS=0 only turns off the extra settling after a chunked prompt. The score
        mode cannot take a warm-up prompt in the same process: with DS4_SCORE_PREFIX it joins every segment of its ids
        file into the one scored stream (ds4_main.cpp:1019-1027). So the warm-up reaches the scoring the way a prompt
        reaches the next start in daily use: through the profile. One command-line decode of the screen's W1 prompt
        (teacher/w1t.ids, W1 through the chat template; not a KL prompt), 512 tokens (DS4_NO_EOS=1), on A's config
        and a copy of the snapshot; the engine writes its routing counts back into that copy at exit (CLI decode and
        serve do, --score does not); then the 8 segments start from the warmed copy. Reported: how many of the 15,360
        counts changed, and whether Ab's scores differ from A's at all.
The band and the verdict (written to OUTDIR/rule.txt before any run of this step, with Karl's words above):
  band_top1 = max(changed top-1 picks of Aa vs A, of Ab vs A); band_nll = max(|NLL(Aa) - NLL(A)|, |NLL(Ab) - NLL(A)|)
  (NLL = the mean NLL of the text over the scored positions, skipcheck.text_nll). B's failing numbers, from the first gate
  (A1_KL_DIR: B vs A): its changed top-1 picks (38) and its NLL distance |NLL(B) - NLL(A)| (+0.007). "Inside that band" =
  B's picks <= band_top1 AND B's NLL distance <= band_nll - no 1.10 factor. PASS: B's KL counts as a pass; else FAIL, B
  stays off. Mean, p90 and KL>1 of each pair: report only. The long-prompt memory arms and Karl's OK are still needed.
-> OUTDIR/rule.txt, reuse.json, kl-noise-result.json, kl-noise.md. Exit 0 PASS, 1 FAIL, 2 could not run, 3 kernel error.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/gate")
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import kl_b  # noqa: E402
import skipcheck as SK  # noqa: E402

SC = kl_b.SC
T = f"{SC}/work/ds41/tune"
W1IDS = f"{SC}/results/ds41/tuning/teacher/w1t.ids"
KARL = ("compare A against two placement variants of A that happen in normal use, on the same KL harness and prompts: "
        "(a) A with a different VRAM expert-slot count, like the 3,238 vs 3,300 seen between starts; (b) A with the "
        "expert cache warmed by a different prompt first. The noise band is the largest top-1 change count and the "
        "largest NLL difference among those A-vs-variant pairs. B passes if both of its failing numbers fall inside that "
        "band; otherwise B stays off. The long-prompt memory arms and my OK are still needed before any switch.")
VRAM_A = 0.98


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def reuse_check(o, a1, snap):
    why = []
    base = f"{a1}/base"
    if not (os.path.exists(f"{base}/score.tsv") and os.path.exists(f"{base}/run.txt")):
        return False, [f"{base}: no finished scoring"]
    t1 = os.path.getmtime(f"{base}/score.tsv")
    fresh = kl_b.configs(o)["base"][0]
    c_now, c_old = json.load(open(fresh)), json.load(open(f"{a1}/cfg-base.json"))
    for k in ("exe", "args", "env", "cwd", "lib_dirs"):
        if c_now.get(k) != c_old.get(k):
            why.append(f"cfg-base.json {k} differs from today's derivation")
    exe = c_now["exe"]
    sf = os.path.join(os.path.dirname(exe), "SHA256")
    want = open(sf).read().split()[0] if os.path.exists(sf) else None
    got = sha(exe)
    if want != got:
        why.append(f"engine sha256 {got[:12]} != its SHA256 file {str(want)[:12]}")
    if os.path.getmtime(exe) >= t1:
        why.append("the engine binary is newer than A's scores")
    for p in [f"{T}/scorearm.sh", f"{T}/skipcheck.py", f"{SC}/work/ds41/gate/kl_b.py"] + SK.seg_files(SK.ids_file()):
        if os.path.getmtime(p) >= t1:
            why.append(f"{os.path.basename(p)} changed after A's scores")
    if not os.path.exists(snap):
        why.append(f"no snapshot {snap}")
    json.dump({"a": base, "a_scores_time": time.strftime("%F %T", time.localtime(t1)), "engine_sha256": got,
               "snapshot_sha256": sha(snap) if os.path.exists(snap) else None, "reasons_not": why},
              open(f"{o}/reuse.json", "w"), indent=1)
    return not why, why


def placement(d):
    p = f"{d}/s0/engine.out"
    txt = open(p, errors="replace").read() if os.path.exists(p) else ""
    import re
    n = [int(x) for x in re.findall(r"CUDA\d layers[^:]*: weights [\d.]+ GB, experts [\d.]+ GB \((\d+) of \d+ in VRAM\)", txt)]
    return {"vram_experts": n, "total": sum(n)}


def pair(a_dir, v_dir):
    r = SK.compare(a_dir, v_dir)
    na, nv = SK.text_nll(a_dir), SK.text_nll(v_dir)
    same = open(f"{a_dir}/score.tsv", "rb").read() == open(f"{v_dir}/score.tsv", "rb").read()
    return {"top1_changed": r["positions"] - r["top1_agree"], "nll_distance": abs(nv - na), "nll": [na, nv],
            "kl_mean": r["kl_mean"], "kl_p90": r["kl_p90"], "kl_gt1": r["kl_gt1"], "positions": r["positions"],
            "byte_identical": same}


def main():
    o, a1, snap = sys.argv[1], sys.argv[2], sys.argv[3]
    lp = f"{SC}/tmp/port-gap.lockpid"
    if not (os.path.exists(lp) and os.path.getsize(lp) > 0):
        print("kl_noise.py: no gap is open (tmp/port-gap.lockpid) - nothing runs")
        return 2
    os.makedirs(o, exist_ok=True)
    k = json.load(open(f"{a1}/kl-result.json"))
    bp = pair(f"{a1}/base", f"{a1}/cand-B")
    if bp["top1_changed"] != k["detail"]["flips"][0]:
        print(f"B's changed picks recomputed {bp['top1_changed']} != stored {k['detail']['flips'][0]} - not running")
        return 2
    ok_reuse, why = reuse_check(o, a1, snap)
    plan = ("A = the first gate's A scoring (reused: same build, config, settings, snapshot)" if ok_reuse else
            "A scored again here (the first gate's cannot be reused: " + "; ".join(why) + ")")
    rule = [f"kl_noise.py rule, written {time.strftime('%F %T')} before any run of this step",
            f"Karl (11-04, verbatim): \"{KARL}\"",
            f"plan: {plan}; Aa = A with --vram-experts {VRAM_A} (2 % fewer VRAM experts: the count is the same at every real "
            "start of the daily config, 1,308 at 128K in 9 starts, so Karl's example ratio 3,238/3,300 is used); Ab = A "
            "started from the snapshot warmed by a 512-token command-line decode of W1 (the score mode cannot take a "
            "warm-up prompt in the same process)",
            "band_top1 = max(changed top-1 picks Aa vs A, Ab vs A); band_nll = max(|NLL(Aa) - NLL(A)|, |NLL(Ab) - NLL(A)|)",
            f"B (first gate, B vs A): changed top-1 picks {bp['top1_changed']}; NLL distance {bp['nll_distance']:.5f}",
            "PASS iff B's picks <= band_top1 AND B's NLL distance <= band_nll (inside the band; no 1.10 factor); else FAIL "
            "(B stays off). Long-prompt memory arms and Karl's OK still needed before any switch."]
    open(f"{o}/rule.txt", "w").write("\n".join(rule) + "\n")
    print("\n".join(rule), flush=True)
    cf = kl_b.configs(o)
    cfg, prof = cf["base"]
    segs = SK.seg_files(SK.ids_file())
    a_dir = f"{a1}/base" if ok_reuse else kl_b.score(o, "A", cfg, prof, snap, segs)
    # Aa: 2 % fewer VRAM experts
    ca = json.load(open(cfg))
    kl_b.set_arg(ca["args"], "--vram-experts", VRAM_A)
    ca["_comment"] = f"kl_noise.py Aa: A with --vram-experts {VRAM_A}. " + ca.get("_comment", "")[:200]
    cfg_a = f"{o}/cfg-Aa.json"
    json.dump(ca, open(cfg_a, "w"), indent=1)
    d_aa = kl_b.score(o, "Aa", cfg_a, prof, snap, segs)
    # Ab: the snapshot warmed by a W1 decode, then the same scoring
    warm = f"{o}/profile-warmed-W1.bin"
    if not os.path.exists(warm):
        shutil.copy(snap, prof)
        rc = subprocess.run(["bash", f"{T}/scorearm.sh", f"{o}/Ab-warmup", cfg, f"decode:{W1IDS}:512", "DS4_NO_EOS=1"]).returncode
        if rc == 3:
            print("KERNEL ERROR in the warm-up decode"); return 3
        if rc != 0:
            print(f"the warm-up decode failed (rc {rc}): {o}/Ab-warmup"); return 2
        shutil.copy(prof, warm)
    a0, a2 = open(snap, "rb").read(), open(warm, "rb").read()
    changed = sum(1 for i in range(0, min(len(a0), len(a2)), 4) if a0[i:i + 4] != a2[i:i + 4])
    d_ab = kl_b.score(o, "Ab", cfg, prof, warm, segs)
    res = {"Aa": dict(pair(a_dir, d_aa), placement=placement(d_aa)), "Ab": dict(pair(a_dir, d_ab), placement=placement(d_ab),
           profile_counts_changed=changed, profile_bytes=[len(a0), len(a2)])}
    band_top1 = max(res["Aa"]["top1_changed"], res["Ab"]["top1_changed"])
    band_nll = max(res["Aa"]["nll_distance"], res["Ab"]["nll_distance"])
    ck = {"top1": bp["top1_changed"] <= band_top1, "nll": bp["nll_distance"] <= band_nll}
    ok = all(ck.values())
    out = {"plan": plan, "a": a_dir, "a_placement": placement(a_dir), "variants": res, "band": {"top1": band_top1, "nll": band_nll},
           "b": bp, "checks": ck, "pass": ok, "times": {n: open(f"{d}/run.txt").read().strip() for n, d in (("Aa", d_aa), ("Ab", d_ab))}}
    json.dump(out, open(f"{o}/kl-noise-result.json", "w"), indent=1)
    row = lambda n, r: (f"| {n} | {r['top1_changed']} | {r['nll_distance']:.5f} | {r['kl_mean']:.5f} | {r['kl_p90']:.5f} | "  # noqa: E731
                        f"{r['kl_gt1']} | {r.get('placement', {}).get('total', '-')} | {r['byte_identical']} |")
    L = ["# B's KL check under Karl's 11-04 noise-band rule", "",
         f"Verdict: **{'PASS - B counts as passing the KL check' if ok else 'FAIL - B stays off'}** "
         f"(the long-prompt memory arms and Karl's OK are still needed before any switch)", "",
         f"- {plan}", f"- rule (rule.txt, written before the run): {rule[3]}; {rule[5]}", "",
         "| pair (vs A) | changed top-1 picks | NLL distance | KL mean | KL p90 | KL>1 | VRAM experts | byte-identical |",
         "|---|---|---|---|---|---|---|---|",
         row("Aa: --vram-experts 0.98", res["Aa"]), row("Ab: warmed by a W1 decode", res["Ab"]), row("B (first gate)", bp), "",
         f"- band: top-1 {band_top1}, NLL {band_nll:.5f}; B {bp['top1_changed']} / {bp['nll_distance']:.5f}: top-1 "
         f"{'inside' if ck['top1'] else 'OUTSIDE'}, NLL {'inside' if ck['nll'] else 'OUTSIDE'}",
         f"- A's VRAM experts in the harness: {out['a_placement']['total']} {out['a_placement']['vram_experts']}; Aa's "
         f"{res['Aa']['placement']['total']} {res['Aa']['placement']['vram_experts']}",
         f"- Ab's warm-up changed {changed} of the profile's {len(a0) // 4} counts",
         f"- run times: {out['times']}"]
    open(f"{o}/kl-noise.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
