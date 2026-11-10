#!/usr/bin/env python3
"""tfaccept.py LABEL — round 10 D.3 (your addition): draft acceptance on the SAME texts for Q4 and IQ3_S.  On a
measurement-twin server ($ELOG; force mode: strata_prefix_ids + strata_force_ids), each human-written text (corpus,
long16k, long24k, long28k: its prompt ids, then its 1,536 scored ids teacher-forced) is fed through the verify windows;
after every window the drafter's guesses for the next positions are logged (FDRAFT, greedy: temperature 0).  Acceptance
on the text = for each window, drafts offered while their chained draft probability stays >= 0.5 (--spec-min-p), the
leading ones equal to the text's next tokens accepted; reported as accepted / offered, the first draft's hit rate, and
the mean NLL of the forced text (FORCE lines).  -> results/r11/tfaccept-LABEL.json"""
import json, os, re, sys, time, urllib.request
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
L, ELOG = sys.argv[1], Path(os.environ["ELOG"])
def ids(p): return [int(x) for x in re.split(r"[,\s]+", p.read_text().strip()) if x]
out = {}
for t in os.environ.get("TEXTS", "corpus long16k long24k long28k").split():   # TEXTS: other texts (B.1: > 32K)
    pr, tx = ids(WS / f"work/prof/tf-{t}.prompt"), ids(WS / f"work/prof/tf-{t}.text")
    off = ELOG.stat().st_size
    body = {"model": "x", "messages": [{"role": "user", "content": "Continue the text."}], "max_tokens": len(tx),
            "temperature": 0.0, "reasoning_effort": "none", "strata_prefix_ids": pr, "strata_force_ids": tx}
    req = urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        r.read()
    time.sleep(1.0)
    log = ELOG.read_bytes()[off:].decode("utf-8", "replace").split("\n")
    force = {int(f[1]): int(f[2]) for f in (l.split() for l in log if l.startswith("FORCE "))}
    nll = [float(l.split()[4]) for l in log if l.startswith("FORCE ")]
    off_n = acc_n = first = first_n = 0
    for l in log:
        if not l.startswith("FDRAFT "):
            continue
        f = l.split(); pos = int(f[1]); g = [(int(a), float(b)) for a, b in (x.split(":") for x in f[2:])]
        k = 0
        for j, (tok, prob) in enumerate(g):
            if prob < 0.5 or (pos + j) not in force:
                break
            k += 1
        a = 0
        while a < k and g[a][0] == force[pos + a]:
            a += 1
        off_n += k; acc_n += a
        if g and pos in force:
            first_n += 1; first += g[0][0] == force[pos]
    out[t] = {"windows_drafted": first_n, "offered": off_n, "accepted": acc_n,
              "acceptance": acc_n / off_n if off_n else None, "first_draft_hit": first / first_n if first_n else None,
              "nll": sum(nll) / len(nll) if nll else None, "forced": len(nll), "seconds": round(time.time() - t0, 1)}
    print(t, json.dumps(out[t]), flush=True)
(WS / f"results/r11/tfaccept-{L}.json").write_text(json.dumps(out, indent=1))
