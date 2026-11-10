#!/usr/bin/env python3
"""pairs2.py - 10-27: the two items the hard set's driver left undone or open, in their own gap after the 128K check.
1. The repeat pairs with --dspark none (Karl 10-26 19:00: "Also run the ~9-minute repeat pairs with DSpark off"): as
   rep-test-reuse0 (v026test, DS4_TEST_SEED_RESET=1, STRATA_DS4_REUSE=0, placement frozen) plus --dspark none. hardset.py
   skipped it: its arm() looked for the test build's record in the hard set's own state, which never had one (the build,
   0cf5fa1bac59, is in results/ds41/after/state.json and on disk).
2. The carry-over check again with placement frozen (--no-expert-cache, as the pairs): hardset.py's run (expert cache on)
   differed from position 0 - small past position 512 (KL mean 0.0008-0.0010, the rounding references 0.006-0.007) but
   0.28-0.36 over the first 16 positions. Frozen and identical -> the expert cache's moves were the whole difference;
   frozen and still different -> something else in the engine carries over.
State results/ds41/hard/pairs2-state.json, log results/ds41/hard/pairs2.log, summary results/ds41/hard/pairs2.md."""
import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/after")
import after as A  # noqa: E402

SC = A.SC
R = f"{SC}/results/ds41/hard"
A.STATE, A.LOG = f"{R}/pairs2-state.json", f"{R}/pairs2.log"


def wait_ctx128():
    A.say("pairs2: waiting for the 128K check (ds41-ctx128) to end")
    while subprocess.run(["systemctl", "--user", "is-active", "--quiet", "ds41-ctx128.service"]).returncode == 0:
        time.sleep(60)
    try:
        h = json.load(open(f"{SC}/results/ds41/ctx128/state.json"))
    except (OSError, ValueError):
        h = {}
    if h.get("stopped") or not h.get("gap_closed"):
        why = h.get("stopped") or "it ended without closing its gap"
        A.say(f"pairs2: the 128K check did not finish cleanly ({why}) - nothing runs")
        A.notify("Repeat pairs not started", f"the 128K check: {why}", True)
        sys.exit(1)
    A.say(f"pairs2: the 128K check ended (gap closed {h['gap_closed']})")


def rows(p):
    out = []
    for l in open(p):
        f = l.rstrip("\n").split("\t")
        out.append((int(f[0]), int(f[1]), int(f[3]), [(int(a), float(b)) for a, b in (x.split(":") for x in f[8:] if ":" in x)]))
    return out


def kl(x, y):
    kb = dict(y[3])
    fl = min(v for _, v in y[3])
    pr = [math.exp(v) for _, v in x[3]]
    pa = [math.exp(kb.get(i, fl)) for i, _ in x[3]]
    sr, sa = sum(pr), sum(pa)
    return sum((p / sr) * math.log((p / sr) / (q / sa)) for p, q in zip(pr, pa) if p > 0)


def copies(d):
    """the second copy against the first: KL mean, changed top-1 picks, KL mean by position band"""
    r = rows(f"{d}/score.tsv")
    n = len(r) // 2
    a, b = r[:n], r[n:]
    ks = [kl(x, y) for x, y in zip(a, b)]
    band = lambda lo, hi: round(sum(ks[lo:hi]) / max(1, len(ks[lo:hi])), 4)
    diff = next((i for i in range(n) if a[i][1:3] != b[i][1:3] or a[i][3] != b[i][3]), None)
    return {"positions": n, "identical": diff is None, "first_difference": diff, "kl_mean": round(sum(ks) / max(1, n), 5),
            "top1_changed": sum(x[2] != y[2] for x, y in zip(a, b)),
            "kl_by_pos": {"0-16": band(0, 16), "16-128": band(16, 128), "128-512": band(128, 512), "512-end": band(512, n)}}


def carryover_frozen(st):
    if st.get("carryover_frozen"):
        return
    f = A.final()
    src = json.load(open(f"{A.skipcheck.OUT}/short8-s0.ids.json"))
    seg = src["segments"][0]
    p = f"{R}/carryover.ids.json"
    json.dump(dict(src, segments=[seg, dict(seg, name=seg["name"] + "-again")]), open(p, "w"))
    cfg = A.tune.mkcfg("hard-carryover-frozen", dict(f, engine="v026test", **{"--expert-profile": A.tune.SHIPPED,
                                                                              "--no-expert-cache": None}))
    out = {}
    for w in (128, 1):
        d = f"{R}/carryover-frozen-w{w}"
        rc = subprocess.run(["bash", f"{A.T}/scorearm.sh", d, cfg, p], env=dict(os.environ, SCORE_WINDOW=str(w), SCORE_LIMIT_S="1800")).returncode
        if rc == 3:
            A.stop(st, "kernel error in the frozen carry-over check")
            sys.exit(3)
        out[w] = dict(copies(d), rc=rc) if os.path.exists(f"{d}/score.tsv") else {"rc": rc, "missing": True}
    st["carryover_frozen"] = out
    A.save(st)
    A.say(f"carry-over, placement frozen: {json.dumps(out)}")


def summary(st):
    L = ["# Repeat pairs with DSpark off; carry-over with placement frozen (10-27)", ""]
    s = st["steps"].get("rep-test-reuse0-nodspark") or {}
    ident = None
    if s.get("dir") and os.path.exists(f"{s['dir']}/cont.json"):
        ident = json.load(open(f"{s['dir']}/cont.json")).get("identical")
    L.append(f"- Repeat pairs (v026test, counter reset, REUSE=0, placement frozen, --dspark none): identical {ident} "
             f"(10-26 with --dspark auto: none identical) - {s.get('dir') or s}")
    for k, lab in (("carryover", "expert cache on (hard set, 10-27 01:28)"), ("carryover_frozen", "placement frozen")):
        src = st.get(k) or {}
        for w, v in src.items():
            L.append(f"- Carry-over, {lab}, window {w}: {json.dumps(v)}")
    open(f"{R}/pairs2.md", "w").write("\n".join(L) + "\n")


def main():
    st = A.load()
    if st.get("stopped"):
        A.say(f"not resuming: stopped earlier ({st['stopped']})")
        return 1
    st["build_test"] = json.load(open(f"{SC}/results/ds41/after/state.json"))["build_test"]
    st["carryover"] = {w: copies(f"{R}/carryover-w{w}") for w in (128, 1)}   # (the hard set's run, expert cache on)
    A.save(st)
    wait_ctx128()
    A.open_gap(st)
    f = A.final()
    A.arm(st, "rep-test-reuse0-nodspark", dict(f, engine="v026test", STRATA_DS4_REUSE="0", DS4_TEST_SEED_RESET="1",
                                               **{"--no-expert-cache": None, "--dspark": "none"}),
          "item 2 (Karl 19:00): repeat pairs as rep-test-reuse0 with --dspark none",
          f"{A.PY} {A.T}/cont_client.py $URL $OUT {A.ELOG} exact")
    carryover_frozen(st)
    rc = A.close_gap(st)
    summary(st)
    A.notify("Repeat pairs done", f"{R}/pairs2.md; 8080 {'back on P021m' if rc == 0 else 'NOT restored'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
