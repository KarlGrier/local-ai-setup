#!/usr/bin/env python3
"""loop_probe.py - 2026-10-14 (C, loop test: quant vs engine): how peaked is the model's next-token distribution inside
the digit runs that Strata's repeat guard stops?  Teacher-forced, not sampled: for every case (label:item:run) the
original request is sent again with strata_prefix_ids = the token sequence to read (the original answer's reasoning
re-encoded + the withheld 256th repeat + a continuation's reasoning), max_tokens 1, to a server whose engine writes
STRATA_LOGPOS (+ STRATA_LOGPOS_TOPK): the engine logs, for every prompt token it reads, the log-probability of the token
that follows, the top token's and the top K.  A priming request with the sequence up to 8 tokens before the run goes first
(read by the batched prompt path and kept as the live session), so the probe reads only the run's tail through the
decode windows (fewer fresh tokens than the server's --short-read, 2048 in the probe configs), which log.  The digit run is the block of positions whose
next token is the run's digit; digit j = the j-th digit of the run counting the original's 255 visible + the withheld
256th + the continuation's.  Per case: p(top) and p(2nd) at j = 300 / 600 / 900 (and the mean over j +-10), how many
positions have p(top) < 0.95 (at temperature 1.0 with top_p 0.95 only those can leave the run), and the expected number
of departures sum(1 - p(digit) after the request's filters).  Measurement only; nothing is graded.
  --seq-from LABEL_SUFFIX  whose continuation to read (default -cont1024-q8; the IQ3_S continuations: -cont1024)"""
import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "suite"))
sys.path.insert(0, str(WS / "strata-cstar171" / "tools"))
from msuite import runner  # noqa: E402
from msuite.backend_openai import OpenAIBackend  # noqa: E402
from msuite.common import answer_path, label_dir, read_json, write_json  # noqa: E402
import strata_tokenizer as ST  # noqa: E402


def load_tok(d):
    d = Path(d)
    v = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(v)
    for k, i in v.items():
        toks[i] = k
    return ST.Tokenizer(toks, (d / "merges.txt").read_text(encoding="utf-8").split("\n"),
                        json.loads((d / "token_type.json").read_text()))


def trailing_run(text):
    m = re.search(r"(.)\1*$", text, re.S)
    return (m.group(1), len(m.group(0))) if m else ("", 0)


def filtered_p(row_top, unit_id, top_k=20, top_p=0.95, min_p=0.05):
    """The engine's chain (sampler.cu: top_k, top_p over the top_k list, min_p vs the top token; T 1.0) on the top-K
    list we have: the probability that the digit is drawn.  With K=5 logged, top_k 20 is approximated by the top 5
    (the rest of the mass sits outside the top_p cut whenever p(top) is large, which is the case of interest)."""
    ps = [(i, math.exp(lp)) for i, lp in row_top]
    kept, acc = [], 0.0
    for i, p in ps[:top_k]:
        kept.append((i, p))
        acc += p
        if acc >= top_p:
            break
    pmax = kept[0][1]
    kept = [(i, p) for i, p in kept if p >= min_p * pmax]
    z = sum(p for _, p in kept)
    return sum(p for i, p in kept if i == unit_id) / z


ap = argparse.ArgumentParser()
ap.add_argument("--endpoint", default="http://127.0.0.1:8081")
ap.add_argument("--tokenizer", required=True)
ap.add_argument("--cases", required=True)
ap.add_argument("--logpos", required=True, help="the engine's STRATA_LOGPOS file")
ap.add_argument("--model", required=True, help="name for the output (q8 / iq3)")
ap.add_argument("--seq-from", default="-cont1024-q8")
ap.add_argument("--extra", type=int, default=64, help="tokens read past the end of the digit run when it ended")
ap.add_argument("--out", default=str(WS / "results/r20/q8loop"))
a = ap.parse_args()
tok = load_tok(a.tokenizer)
items = {i["id"]: i for i in runner.load_items(["coding"])}
lp_path = Path(a.logpos)
results = []
for case in a.cases.split(","):
    label, name, run = case.split(":")
    run = int(run)
    iid = f"coding/{name}"
    orig = read_json(answer_path(label, iid, run))
    meta = read_json(label_dir(label) / "meta.json")
    z = orig["response"].get("reasoning") or ""
    unit, n_run = trailing_run(z)
    unit_id = tok.encode(unit)
    assert len(unit_id) == 1, (case, unit_id)
    unit_id = unit_id[0]
    seq = tok.encode(z) + [unit_id]                            # the cut: 255 visible + the withheld 256th
    cut = len(seq)
    cont = read_json(answer_path(label + a.seq_from, iid, run))
    zc = cont["response"].get("reasoning") or ""
    assert zc.startswith(z + unit), (case, "the continuation does not start with the original + the 256th repeat")
    tail = zc[len(z) + 1:]
    # the continuation's own run, then at most --extra tokens past its end
    m = re.match(re.escape(unit) + "*", tail)
    run_chars = m.end()
    tail_ids = tok.encode(tail[:run_chars])
    assert all(t == unit_id for t in tail_ids), (case, "digits are not one token each")
    after = tok.encode(tail[run_chars:])[:a.extra] if run_chars < len(tail) else []
    seq = seq + tail_ids + after
    b = meta.get("backend") or {}
    samp = b.get("sampling") or {}
    be = OpenAIBackend(a.endpoint, max_tokens=1, sampling=samp, effort=b.get("reasoning_effort"),
                       extra_body={"strata_prefix_ids": seq})
    # prime: everything up to 8 tokens before the digit run, read by the batched prompt path (not logged) and kept as
    # the live session; the probe then reads only the tail - fewer than --short-read (2048 in the probe configs)
    # fresh tokens - through the decode windows, which write STRATA_LOGPOS.  (chat() floors max_tokens at 256.)
    run_start = cut - 1 - n_run
    msgs, _ = runner.messages_for(items[iid])
    prime = OpenAIBackend(a.endpoint, max_tokens=1, sampling=samp, effort=b.get("reasoning_effort"),
                          extra_body={"strata_prefix_ids": seq[:run_start - 8]})
    prime._exchange(prime._body(msgs, None, 1), 1)
    off = lp_path.stat().st_size if lp_path.exists() else 0
    t0 = time.monotonic()
    rec = be._exchange(be._body(msgs, None, 1), 1)
    wall = time.monotonic() - t0
    time.sleep(1.0)
    with open(lp_path, "rb") as f:
        f.seek(off)
        lines = f.read().decode("utf-8", "replace").splitlines()
    rows = {}
    for ln in lines:
        c = ln.split("\t")
        if len(c) < 8:
            continue
        rows[int(c[0])] = {"tgt": int(c[1]), "lp_tgt": float(c[2]), "top": int(c[3]), "lp_top": float(c[4]),
                           "im_end": float(c[6]) if c[6] != "nan" else None,
                           "topk": [(int(x.split(":")[0]), float(x.split(":")[1])) for x in c[8:]]}
    if not rows:
        print(f"{case}: no logged rows (wall {wall:.0f} s) - stop", flush=True)
        sys.exit(2)
    last = max(rows)
    # the run = the contiguous block of positions predicting the digit that holds the cut; the cut's withheld repeat is
    # the 256th digit, read at the row before it.  The full sequence ends at row `last` + 1 (the final token's row is
    # the 1-token generation, not logged); so token index k of seq sits at absolute position P + k.
    P = last + 1 - (len(seq) - 1)
    r256 = P + cut - 2                                         # the row that predicts the 256th digit
    assert rows[r256]["tgt"] == unit_id, (case, rows[r256])
    s = r256
    while s - 1 in rows and rows[s - 1]["tgt"] == unit_id:
        s -= 1
    e = r256
    while e + 1 in rows and rows[e + 1]["tgt"] == unit_id:
        e += 1
    run_rows = [rows[p] for p in range(s, e + 1)]               # run_rows[j-1] predicts digit j
    aligned = (s == r256 - n_run)                               # the block starts where the original's visible run did
    n_digits = len(run_rows)

    def at(j, w=10):
        lo, hi = max(1, j - w), min(n_digits, j + w)
        if j > n_digits:
            return None
        sel = run_rows[lo - 1:hi]
        r = run_rows[j - 1]
        p2 = math.exp(r["topk"][1][1]) if len(r["topk"]) > 1 else None
        return {"j": j, "p_top": round(math.exp(r["lp_top"]), 6), "top_is_digit": r["top"] == unit_id,
                "p_2nd": round(p2, 6) if p2 is not None else None,
                "second": tok.decode([r["topk"][1][0]]) if len(r["topk"]) > 1 else None,
                "p_im_end": round(math.exp(r["im_end"]), 8) if r["im_end"] is not None else None,
                "mean_p_top_pm10": round(sum(math.exp(x["lp_top"]) for x in sel) / len(sel), 6),
                "min_p_top_pm10": round(min(math.exp(x["lp_top"]) for x in sel), 6)}

    below = [j for j, r in enumerate(run_rows, 1) if math.exp(r["lp_top"]) < 0.95]
    leave = [(j, 1 - filtered_p(r["topk"], unit_id, samp.get("top_k", 20), samp.get("top_p", 0.95),
                                samp.get("min_p", 0.0) or 0.0)) for j, r in enumerate(run_rows, 1)]
    exp_leave = sum(x for _, x in leave)
    exp_leave_256 = sum(x for j, x in leave if j > 256)
    # the row right after the run (what came instead of the digit, when the run ended inside the sequence)
    end_row = rows.get(e + 1)
    res = {"case": case, "model": a.model, "seq_from": a.seq_from, "unit": unit, "digits_in_sequence": n_digits,
           "run_ended_in_sequence": end_row is not None and e + 1 <= last,
           "next_after_run": tok.decode([end_row["tgt"]]) if end_row else None,
           "probe_wall_s": round(wall, 1), "prompt_tokens": (rec.get("tokens") or {}).get("prompt"),
           "rows_logged": len(rows), "first_pos": P, "aligned": aligned, "visible_run_at_cut": n_run,
           "at": {str(j): at(j) for j in (256, 300, 600, 900, n_digits)},
           "positions_p_top_below_0.95": len(below), "first_below_0.95": below[:10],
           "expected_departures_all": round(exp_leave, 4), "expected_departures_after_256": round(exp_leave_256, 4),
           "min_p_top": round(min(math.exp(r["lp_top"]) for r in run_rows), 6),
           "min_p_top_at": 1 + min(range(n_digits), key=lambda k: run_rows[k]["lp_top"])}
    results.append(res)
    print(json.dumps({k: res[k] for k in ("case", "model", "aligned", "digits_in_sequence", "run_ended_in_sequence",
                                           "positions_p_top_below_0.95", "expected_departures_after_256",
                                           "min_p_top", "min_p_top_at")}), flush=True)
    for j in ("300", "600", "900"):
        print("   ", j, json.dumps(res["at"][j]), flush=True)
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
write_json(out / f"probe-{a.model}{a.seq_from}-{int(time.time())}.json", results)
