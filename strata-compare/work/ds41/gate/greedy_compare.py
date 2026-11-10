#!/usr/bin/env python3
"""greedy_compare.py OUT_JSON REF_DIR DIR [DIR ...] - 11-03 (Karl's gate, C's exactness): greedy_client.py's texts of
each DIR against REF_DIR's (C0f: the drafter loaded, never used), prompt by prompt, text for text (and the token counts).
Identical = greedy speculative decoding gave plain decoding's tokens in that placement. A difference prints the first
differing character and the text around it (repeat_compare.py's form). -> OUT_JSON; exit 0 = all identical, 1 = not,
2 = a run is missing or incomplete.
"""
import json
import os
import sys


def texts(d):
    p = f"{d}/greedy.jsonl"
    if not os.path.exists(p):
        return None
    return {r["id"]: (r.get("text") or "", r.get("completion_tokens")) for r in map(json.loads, open(p))}


def diff(a, b):
    if a == b:
        return "identical", None
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return f"differ from char {i} of {len(a)}/{len(b)}: ...{a[max(0, i - 40):i + 30]!r} vs ...{b[max(0, i - 40):i + 30]!r}", i


def main():
    out, ref, runs = sys.argv[1], sys.argv[2], sys.argv[3:]
    tr = texts(ref)
    res = {"ref": ref, "runs": {}, "identical": True, "complete": True}
    if not tr or len(tr) < 3:
        res["complete"] = False
    for d in runs:
        t = texts(d)
        rr = {}
        if not t or len(t) < len(tr or {}):
            res["complete"] = False
        for pid, (txt, n) in sorted((tr or {}).items()):
            if t is None or pid not in t:
                rr[pid] = {"verdict": "missing"}
                res["complete"] = False
                continue
            v, at = diff(txt, t[pid][0])
            rr[pid] = {"verdict": v, "first_diff_char": at, "tokens": [n, t[pid][1]], "chars": [len(txt), len(t[pid][0])]}
            if at is not None or n != t[pid][1]:
                res["identical"] = False
        res["runs"][d] = rr
        for pid, r in rr.items():
            print(f"{os.path.basename(d.rstrip('/'))} vs {os.path.basename(ref.rstrip('/'))} {pid}: {r['verdict']}"
                  + (f" (tokens {r['tokens'][0]} / {r['tokens'][1]})" if "tokens" in r else ""))
    json.dump(res, open(out, "w"), indent=1)
    verdict = "DIFFERENT" if not res["identical"] else ("INCOMPLETE" if not res["complete"] else "IDENTICAL")
    res["verdict"] = verdict
    json.dump(res, open(out, "w"), indent=1)
    print(f"greedy identity: {verdict}")
    return 0 if verdict == "IDENTICAL" else (2 if verdict == "INCOMPLETE" else 1)


if __name__ == "__main__":
    sys.exit(main())
