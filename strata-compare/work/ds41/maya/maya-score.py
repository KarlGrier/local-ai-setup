#!/usr/bin/env python3
"""maya-score.py run NAME CONFIG [ENV=VALUE ...] | compare REF_DIR RUN_DIR - PREPARED 10-25 for the Maya v1.1.28
head-to-head (not run yet). skipcheck.py's teacher-forced scoring for a config file given as is (no tune.mkcfg), so the
Maya configs (maya-M1.json / maya-M2.json, the patched maya-ds4's --score) and a Strata config can be scored on the same
8 segments of results/ds41/tuning/teacher/long8.ids.json (12,000-token prefix read as one prompt, 256 positions scored):
  run      one engine run a segment (skipcheck.seg_files: DS4_SCORE_PREFIX joins a file's segments, so one each), through
           maya-scorearm.sh for a maya-ds4 config or tune/scorearm.sh for a strata-dsv41 one (by the exe's name), merged
           into results/ds41/tuning/teacher/NAME/score.tsv + .seg.json + run.txt exactly as skipcheck.score() merges them.
           DS4_SCORE_PREFIX=12000 is added unless given.
  compare  skipcheck.compare(REF, RUN): positions, KL mean / p90 / max / count > 1, top-1 agreements (stops if a target
           differs: not the same text).
Rounding references for a Maya verdict follow skipcheck's "vs" mode: R1 = the same config with another --prefill-chunk
(4096), R2 = --reserve-mib 2600 (more experts on the CPU lane); e.g. M1 vs S, M2 vs M1, with M1's own R1/R2.
Exit codes as skipcheck: 0 ok, 2 could not run, 3 kernel error.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import skipcheck  # noqa: E402

SC = "/home/USER/ai-speed-testing/strata-compare"
OUT = skipcheck.OUT


def run(name, cfg, env):
    env = dict(env)
    env.setdefault("DS4_SCORE_PREFIX", str(skipcheck.PREFIX))
    exe = os.path.basename(json.load(open(cfg))["exe"])
    arm = f"{SC}/work/ds41/maya/maya-scorearm.sh" if exe == "maya-ds4" else f"{SC}/work/ds41/tune/scorearm.sh"
    d = f"{OUT}/{name}"
    if os.path.exists(f"{d}/score.tsv") and os.path.exists(f"{d}/run.txt"):
        return d
    rows, segs, secs, low = [], [], 0, 999.0
    for i, sf in enumerate(skipcheck.seg_files(skipcheck.ids_file())):
        sd = f"{d}/s{i}"
        if not (os.path.exists(f"{sd}/score.tsv") and os.path.exists(f"{sd}/run.txt")):
            rc = subprocess.run(["bash", arm, sd, cfg, sf] + [f"{k}={v}" for k, v in env.items()]).returncode
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


def main():
    if sys.argv[1] == "run":
        env = dict(x.split("=", 1) for x in sys.argv[4:])
        print(run(sys.argv[2], sys.argv[3], env))
        return 0
    if sys.argv[1] == "compare":
        r = skipcheck.compare(sys.argv[2], sys.argv[3])
        print(f"{sys.argv[3]} vs {sys.argv[2]}: {r['positions']} positions, KL mean {r['kl_mean']:.5f}, p90 {r['kl_p90']:.5f}, "
              f"max {r['kl_max']:.5f}, KL>1 {r['kl_gt1']}, top-1 agree {r['top1_agree']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
