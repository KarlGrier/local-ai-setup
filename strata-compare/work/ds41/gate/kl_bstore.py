#!/usr/bin/env python3
"""kl_bstore.py OUTDIR N - 11-04 (gate.sh bstore, step KLBS): B with the smaller RAM store (configs/DS41-gate-B<N>.json,
--ssd-cache N) on the KL harness against A, judged by Karl's 11-04 noise-band rule with the band the second gate measured
(results/ds41/gate-1104-0725/kl-noise/kl-noise-result.json: A vs Aa (2 % fewer VRAM experts) and Ab (warmed by a W1
decode) - top-1 40, NLL 0.00701). Inside an open gap only. The harness exactly as kl_b.py / kl_noise.py ran it: the 8
long8 segments, DS4_SCORE_PREFIX=12000 + DS4_FLOW_STATS=1, the first gate's profile snapshot before every segment, A =
the first gate's A scoring (results/ds41/gate-1103-1354/kl/base). Expected: the store's size changes where an expert's
bytes come from (RAM or the drive), not how it is computed, so B<N> may score byte-identically to B (the first gate's
cand-B) - reported either way. PASS = B<N>'s changed top-1 picks vs A <= the band's AND its NLL distance <= the band's.
-> OUTDIR/kl-bstore-result.json, OUTDIR/kl-bstore.md. Exit 0 PASS, 1 FAIL, 2 could not run, 3 kernel error.
"""
import json
import os
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/gate")
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import kl_b  # noqa: E402
import kl_noise  # noqa: E402
import skipcheck as SK  # noqa: E402

SC = kl_b.SC
G1 = f"{SC}/results/ds41/gate-1103-1354"
G2 = f"{SC}/results/ds41/gate-1104-0725"


def main():
    o, n = sys.argv[1], int(sys.argv[2])
    lp = f"{SC}/tmp/port-gap.lockpid"
    if not (os.path.exists(lp) and os.path.getsize(lp) > 0):
        print("kl_bstore.py: no gap is open - nothing runs"); return 2
    os.makedirs(o, exist_ok=True)
    nb = json.load(open(f"{G2}/kl-noise/kl-noise-result.json"))
    band = nb["band"]
    c = json.load(open(f"{SC}/configs/DS41-gate-B{n}.json"))
    c["_comment"] = f"kl_bstore.py: B{n} on the KL harness. " + c.get("_comment", "")[:200]
    cfg = f"{o}/cfg-B{n}.json"
    json.dump(c, open(cfg, "w"), indent=1)
    prof = c["args"][c["args"].index("--expert-profile") + 1]
    d = kl_b.score(o, f"B{n}", cfg, prof, f"{G1}/profile-snapshot.bin", SK.seg_files(SK.ids_file()))
    r = kl_noise.pair(f"{G1}/kl/base", d)
    same_b = open(f"{G1}/kl/cand-B/score.tsv", "rb").read() == open(f"{d}/score.tsv", "rb").read()
    ck = {"top1": r["top1_changed"] <= band["top1"], "nll": r["nll_distance"] <= band["nll"]}
    ok = all(ck.values())
    out = {"n": n, "vs_A": r, "band": band, "checks": ck, "pass": ok, "byte_identical_to_B": same_b,
           "placement": kl_noise.placement(d), "time": open(f"{d}/run.txt").read().strip()}
    json.dump(out, open(f"{o}/kl-bstore-result.json", "w"), indent=1)
    L = [f"# B{n} (B, --ssd-cache {n}) vs A on the KL harness, Karl's 11-04 noise-band rule", "",
         f"Verdict: **{'PASS' if ok else 'FAIL'}**; byte-identical to B (68 GB store): {same_b}", "",
         f"- B{n} vs A: changed top-1 picks {r['top1_changed']} (band {band['top1']}), NLL distance {r['nll_distance']:.5f} "
         f"(band {band['nll']:.5f}); KL mean {r['kl_mean']:.5f}, p90 {r['kl_p90']:.5f}, KL>1 {r['kl_gt1']}",
         f"- VRAM experts {out['placement']}; {out['time']}"]
    open(f"{o}/kl-bstore.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
