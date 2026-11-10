#!/usr/bin/env python3
"""probe_offline.py LOGPOS REF_JSON MODEL - 2026-10-14 C: loop_probe.py's per-case statistics computed from an engine's
STRATA_LOGPOS file after the fact (c_probe3 pointed the script at another file name than the engine's config, so the
rows went to the config's file).  The rendered prompt length P of each case comes from REF_JSON (the IQ3_S probe of the
same sequences: the same server code renders the same prompt), the sequence from the saved answers, and only rows
whose target token equals the sequence's token at that position are used; of several sessions' rows for a position the
last complete block wins.  Writes results/r20/q8loop/probe-<MODEL>-cont1024-q8-offline.json."""
import json
import math
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "suite"))
sys.path.insert(0, str(WS / "strata-cstar171" / "tools"))
from msuite.common import answer_path, read_json  # noqa: E402
import strata_tokenizer as ST  # noqa: E402

lp_file, ref_file, model = sys.argv[1], sys.argv[2], sys.argv[3]
d = Path(json.loads((WS / "configs/Cstar171.json").read_text())["tokenizer"])
v = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
toks = [None] * len(v)
for k, i in v.items():
    toks[i] = k
tok = ST.Tokenizer(toks, (d / "merges.txt").read_text(encoding="utf-8").split("\n"), json.loads((d / "token_type.json").read_text()))

rows_all = []
for ln in open(lp_file, encoding="utf-8", errors="replace"):
    c = ln.rstrip("\n").split("\t")
    if len(c) < 8 or not c[0].isdigit():
        continue
    rows_all.append((int(c[0]), int(c[1]), float(c[4]), int(c[3]), float(c[6]) if c[6] != "nan" else None,
                     [(int(x.split(":")[0]), float(x.split(":")[1])) for x in c[8:]]))
# the file in blocks of consecutive positions, in file order (each probe request reads one tail block)
blocks, cur = [], []
for r in rows_all:
    if cur and r[0] != cur[-1][0] + 1:
        blocks.append(cur)
        cur = []
    cur.append(r)
if cur:
    blocks.append(cur)
ref = {r["case"]: r for r in json.loads(Path(ref_file).read_text())}
out = []
for case, r in ref.items():
    label, name, run = case.split(":")
    iid = f"coding/{name}"
    z = read_json(answer_path(label, iid, int(run)))["response"].get("reasoning") or ""
    m = re.search(r"(.)\1*$", z, re.S)
    unit, n_run = m.group(1), len(m.group(0))
    unit_id = tok.encode(unit)[0]
    zc = read_json(answer_path(label + "-cont1024-q8", iid, int(run)))["response"].get("reasoning") or ""
    tail = zc[len(z) + 1:]
    seq = tok.encode(z) + [unit_id] + tok.encode(tail)
    P = r["first_pos"]
    cut = len(tok.encode(z)) + 1
    s0 = P + cut - 1 - n_run - 1                       # the row predicting digit 1
    want = {s0 + j: seq[cut - 1 - n_run + j] for j in range(n_run + 1 + len(tail))}   # row pos -> the digit it predicts
    # this case's tail block: from 8 tokens before the run to the sequence's last row, every target as the sequence
    b_start, b_end = P + cut - 1 - n_run - 8 - 1 + 1, P + len(seq) - 2
    got = {}
    for b in blocks:                                   # the last complete block of this case wins
        if b[0][0] == b_start and b[-1][0] == b_end and all(r[1] == seq[r[0] - P + 1] for r in b):
            got = {r[0]: (r[2], r[3], r[4], r[5]) for r in b}
    run_rows = [got.get(s0 + j) for j in range(n_run + 1 + len(tail))]
    n_have = sum(x is not None for x in run_rows)

    def at(j):
        x = run_rows[j - 1] if j <= len(run_rows) else None
        if x is None:
            return None
        lp_top, top, im, topk = x
        return {"j": j, "p_top": round(math.exp(lp_top), 6), "top_is_digit": top == unit_id,
                "p_2nd": round(math.exp(topk[1][1]), 6) if len(topk) > 1 else None,
                "second": tok.decode([topk[1][0]]) if len(topk) > 1 else None,
                "p_im_end": round(math.exp(im), 8) if im is not None else None}

    have = [(j, x) for j, x in enumerate(run_rows, 1) if x is not None]
    below = [j for j, x in have if math.exp(x[0]) < 0.95]
    res = {"case": case, "model": model, "offline": True, "digits_in_sequence": len(run_rows), "rows_found": n_have, "block": [b_start, b_end],
           "at": {str(j): at(j) for j in (256, 300, 600, 900)},
           "positions_p_top_below_0.95": len(below), "first_below_0.95": below[:10],
           "last_below_0.95": below[-1] if below else None,
           "min_p_top": round(min(math.exp(x[0]) for _, x in have), 6) if have else None,
           "series": [[j, round(math.exp(x[0]), 5), round(math.exp(x[3][1][1]), 5) if len(x[3]) > 1 else None,
                       tok.decode([x[3][1][0]]) if len(x[3]) > 1 else None] for j, x in have]}
    out.append(res)
    print(json.dumps({k: res[k] for k in ("case", "rows_found", "digits_in_sequence", "positions_p_top_below_0.95",
                                           "last_below_0.95", "min_p_top")}))
    for j in ("300", "600", "900"):
        print("   ", j, json.dumps(res["at"][j]))
(WS / f"results/r20/q8loop/probe-{model}-cont1024-q8-offline.json").write_text(json.dumps(out, indent=1))
