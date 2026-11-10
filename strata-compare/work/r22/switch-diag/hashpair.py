#!/usr/bin/env python3
# hashpair.py - does a check-(2) twin run's forced reference end in the same session state as its sampled requests?
#
# Reads ONE engine log (or a slice of one) from a check-(2) twin run: N sampled arith-j3 requests, then
# sampling_probe.py's strata_logp forced requests, with STRATA_STATE_HASH=1. It pairs each sampled request with its
# generated ids, read from sampling_probe.py's sp-strata-<label>.jsonl. It keeps the steady state: requests that start
# after the last "PCIe share:" change printed before the first forced request. For the on-path requests
# (ids[:len(path)] == path) it compares their STATE_HASH fields (gdn / ple / tail / kv) with the forced request that
# scores the tie (len(path) + 1 forced tokens on the same prompt).
#
# Both sides end at prompt + path, the same tokens:
#   sampled: prompt, then the path drawn in 1-token windows;
#   forced:  prompt, then the path in the forced windows ("1, then S_mtp" by default; 1-token windows with
#            STRATA_FORCE_T1=1).
# MATCH means the reference's logits come from the same state the sampler drew from.
#
# Usage:  python3 -I hashpair.py ENGINE_LOG [--label L] [--path 17,13,7860] [--jsonl FILE]
#   --label L   SP_LABEL of the run: the ids come from sp-strata-L.jsonl, found in $SP_DIR,
#               then results/r22/*/sp, then work/*/ (or give --jsonl FILE)
#   --path      the forced path before the tie (default arith-j3's 17,13,7860)
# Exit: 0 every field MATCH, 1 a field DIFFER, 2 no usable pairs (no ids, no on-path steady requests, or no forced
# request of len(path) + 1 tokens on the sampled prompt).
#
# ---- tested 2026-10-30 on gap 14's logs (results/r22/switch-diag/gr-fork.md, section 3, evidence 1) ----
# $ cd /home/USER/ai-speed-testing/strata-compare
# $ python3 -I work/r22/switch-diag/hashpair.py logs/engine-r27t-hnospec-nov2.log --label g14-hnospec-nov2; echo "exit $?"
# log logs/engine-r27t-hnospec-nov2.log (lines 1-35075), ids results/r22/gap14/sp/sp-strata-g14-hnospec-nov2.jsonl (4000)
# sampled requests on prompt 108: 4000 in the log, 4000 paired
# steady state: after the PCIe share change at line 296 -> 3964 paired, 3799 on path [17, 13, 7860]
# forced requests: prompt 108, 4 forced: 90
#   gdn   sampled a737f025a52d0445 x3799 | forced b9feffe6ecbba098 x90 | DIFFER
#   ple   sampled d78ebf2fca579a10 x3799 | forced 92066361d2689bdb x90 | DIFFER
#   tail  sampled f24859b0f4a96304 x3799 | forced 81219feb7f6b8222 x90 | DIFFER
#   kv    sampled 3137f66042f2e8f0 x3799 | forced 23b203f1ec0c02a3 x90 | DIFFER
# (tie at steady state on path: 2012 of 3799 = 52.96 % token 28)
# DIFFER
# exit 1
# $ python3 -I work/r22/switch-diag/hashpair.py logs/engine-r27t-hnospec-nofork.log --label g14-hnospec-nofork; echo "exit $?"
# log logs/engine-r27t-hnospec-nofork.log (lines 1-35078), ids results/r22/gap14/sp/sp-strata-g14-hnospec-nofork.jsonl (4000)
# sampled requests on prompt 108: 4000 in the log, 4000 paired
# steady state: after the PCIe share change at line 299 -> 3964 paired, 3789 on path [17, 13, 7860]
# forced requests: prompt 108, 4 forced: 90
#   gdn   sampled 43d3a31eddf945bf x3789 | forced ed9357057b67e708 x90 | DIFFER
#   ple   sampled febf6c031cc7ec24 x3789 | forced b02d73c94f6c8ce4 x90 | DIFFER
#   tail  sampled 274fa824d1f1e51b x3789 | forced 282fb4e05942909a x90 | DIFFER
#   kv    sampled eba3256981241356 x3789 | forced 30e080b4985aa1c7 x90 | DIFFER
# (tie at steady state on path: 1975 of 3789 = 52.12 % token 28)
# DIFFER
# exit 1
import argparse
import collections
import glob
import json
import os
import re
import sys

WS = "/home/USER/ai-speed-testing/strata-compare"
FIELDS = ("gdn", "ple", "tail", "kv")
RE_FORCE = re.compile(r"strata serve: FORCE begin: prompt (\d+) tokens, (\d+) forced")
RE_PROMPT = re.compile(r"strata serve: prompt (\d+) tokens = ")
RE_HASH = re.compile(r"strata serve: STATE_HASH ")


def find_jsonl(label):
    cands = []
    if os.environ.get("SP_DIR"):
        cands.append(os.path.join(os.environ["SP_DIR"], f"sp-strata-{label}.jsonl"))
    cands += sorted(glob.glob(f"{WS}/results/r22/*/sp/sp-strata-{label}.jsonl"))
    cands += sorted(glob.glob(f"{WS}/work/*/sp-strata-{label}.jsonl"))
    cands += sorted(glob.glob(f"{WS}/work/*/*/sp-strata-{label}.jsonl"))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("log")
    ap.add_argument("--label", help="SP_LABEL: the ids come from sp-strata-<label>.jsonl")
    ap.add_argument("--jsonl", help="the sampled ids file (overrides --label's lookup)")
    ap.add_argument("--path", default="17,13,7860", help="the forced path before the tie (comma list)")
    a = ap.parse_args()
    path = [int(x) for x in a.path.split(",") if x.strip()]

    jsonl = a.jsonl or (find_jsonl(a.label) if a.label else None)
    if jsonl is None or not os.path.isfile(jsonl):
        print("no ids file: give --label L or --jsonl FILE" +
              (f" (sp-strata-{a.label}.jsonl not found in $SP_DIR, results/r22/*/sp or work/)" if a.label else ""))
        return 2
    ids = []
    with open(jsonl) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                ids.append(json.loads(ln).get("ids") or [])

    # one record per request: its summary line closes it (FORCE begin and STATE_HASH come before it)
    reqs, force, hsh = [], None, None
    share_lines = []
    n_lines = 0
    with open(a.log, errors="replace") as f:
        for n, ln in enumerate(f, 1):
            n_lines = n
            if ln.startswith("strata serve: FORCE begin"):
                m = RE_FORCE.match(ln)
                force = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
            elif RE_HASH.match(ln):
                hsh = dict(kv.split("=", 1) for kv in ln.split() if "=" in kv and kv.split("=", 1)[0] in FIELDS)
            elif ln.startswith("strata serve: PCIe share:"):
                share_lines.append(n)
            else:
                m = RE_PROMPT.match(ln)
                if m:
                    reqs.append({"line": n, "prompt": int(m.group(1)), "force": force, "hash": hsh})
                    force, hsh = None, None
    print(f"log {a.log} (lines 1-{n_lines}), ids {os.path.relpath(jsonl, WS) if jsonl.startswith(WS) else jsonl} ({len(ids)})")

    sampled = [r for r in reqs if r["force"] is None]
    if not sampled or not ids:
        print("no sampled requests or no ids")
        return 2
    # the sampled prompt: the most common prompt length among the sampled requests
    p_len = collections.Counter(r["prompt"] for r in sampled).most_common(1)[0][0]
    samp = [r for r in sampled if r["prompt"] == p_len]
    off = len(samp) - len(ids)
    if off < 0:
        print(f"the ids file has {len(ids)} samples but the log only {len(samp)} sampled requests on prompt {p_len}: "
              "not this run's file")
        return 2
    print(f"sampled requests on prompt {p_len}: {len(samp)} in the log, {len(ids)} paired"
          + (f" (first {off} unpaired: warm-up)" if off else ""))
    pairs = list(zip(samp[off:], ids))

    forced_all = [r for r in reqs if r["force"] is not None]
    first_forced = min((r["line"] for r in forced_all), default=n_lines + 1)
    change = max((s for s in share_lines if s < first_forced), default=0)
    # steady: the request before it ended after the last share change (so its own windows all ran at the final share)
    prev_end = {}
    last = 0
    for r in reqs:
        prev_end[r["line"]] = last
        last = r["line"]
    steady = [(r, s) for r, s in pairs if prev_end[r["line"]] > change and r["hash"] is not None]
    on = [(r, s) for r, s in steady if len(s) > len(path) and s[:len(path)] == path]
    print(f"steady state: " + (f"after the PCIe share change at line {change}" if change else "no PCIe share change")
          + f" -> {len(steady)} paired, {len(on)} on path {path}")

    forced = [r for r in forced_all if r["force"] == (p_len, len(path) + 1) and r["hash"] is not None]
    print(f"forced requests: prompt {p_len}, {len(path) + 1} forced: {len(forced)}")
    if not on or not forced:
        print("no usable pairs (no steady on-path sampled request, or no matching forced request with a STATE_HASH)")
        return 2

    differ = False
    for fld in FIELDS:
        sc = collections.Counter(r["hash"].get(fld) for r, _ in on)
        fc = collections.Counter(r["hash"].get(fld) for r in forced)
        ok = len(fc) == 1 and sc.most_common(1)[0][0] == next(iter(fc))
        differ = differ or not ok
        s_txt = ", ".join(f"{h} x{c}" for h, c in sc.most_common(4)) + (" ..." if len(sc) > 4 else "")
        f_txt = ", ".join(f"{h} x{c}" for h, c in fc.most_common(4)) + (" ..." if len(fc) > 4 else "")
        print(f"  {fld:<5} sampled {s_txt} | forced {f_txt} | {'MATCH' if ok else 'DIFFER'}")
    tie = collections.Counter(s[len(path)] for _, s in on)
    top, cnt = tie.most_common(1)[0]
    print(f"(tie at steady state on path: {cnt} of {len(on)} = {100.0 * cnt / len(on):.2f} % token {top})")
    print("DIFFER" if differ else "MATCH")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
