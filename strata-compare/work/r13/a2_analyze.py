#!/usr/bin/env python3
"""a2_analyze.py ROUTE_LABEL ORACLE_LABEL [--waits FILE] — round 13 A2 (warming early-layer CPU experts during the draft
round), from the R12 routing dump tmp/r13/route-LABEL.bin (every verified row with its fate, its input token and who
computed each routed expert; the residency of layers 0-11 whenever it changed; request markers).

Topics: the LDR pool's requests (results/runs.jsonl, session LABEL-*, matched by prompt length); topics sorted, every
other one -> FIT half, the rest HELD-OUT. Table (fit half, every verified row, accepted or not): token id -> per layer
0-11 the routed experts' counts. Held-out: for every decode window (MTP or lookup), per layer 0-11, the TRUE set =
distinct experts the window's kept rows (row <= a) routed that the CPU computed (kind 3); the PREDICTION ranks the
experts that are CPU-side in the current residency by the sum over the window's input tokens (every row: token 0 and
the drafts, all known before the window) of P(expert | token, layer) from the table; a global score threshold sets
the predicted bytes to <= 2 x the true bytes (expert bytes per layer from the GGUF). Recall = covered true experts /
true experts (count- and byte-weighted), per layer.  Also: recall with token 0 only (known earliest).
Prize (ms per LDR window) = sum over layers 0-11 of the exposed CPU wait (Phase 0: GPU waitCPU per layer) x recall."""
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

WS = Path("/home/USER/ai-speed-testing/strata-compare")
rl = sys.argv[1] if len(sys.argv) > 1 else ""
EB = {int(k): v for k, v in json.loads((WS / "results/r13/expert_bytes.json").read_text()).items()}
NL = 12


def read_route(label):
    """yields ('req', req, n_prompt, resume) | ('res', array[layers, NE]) | ('win', dict) with rows"""
    buf = (WS / f"tmp/r13/route-{label}.bin").read_bytes()
    a = np.frombuffer(buf, dtype=np.int32) if len(buf) % 4 == 0 else None
    i, n = 0, len(buf)
    cur = None
    while i < n:
        tag = struct.unpack_from("<i", buf, i)[0]
        if tag == -3:
            _, req, npr, res = struct.unpack_from("<4i", buf, i); i += 16
            if cur: yield ("win", cur); cur = None
            yield ("req", req, npr, res)
        elif tag == -2:
            _, layers, ne = struct.unpack_from("<3i", buf, i); i += 12
            arr = np.frombuffer(buf, dtype=np.uint8, count=layers * ne, offset=i).reshape(layers, ne); i += layers * ne
            i = (i + 3) & ~3 if False else i
            if cur: yield ("win", cur); cur = None
            yield ("res", arr)
        elif tag == -1:
            h = struct.unpack_from("<8i", buf, i); i += 32
            T = h[1]
            toks = list(struct.unpack_from(f"<{T}i", buf, i)) if T > 0 else []
            i += 4 * T
            if cur: yield ("win", cur)
            cur = {"T": T, "a": h[2], "keep": h[3], "sfx": h[4], "pos": h[5] | (h[6] << 31), "req": h[7], "toks": toks, "rows": []}
        else:
            layer, row, k = struct.unpack_from("<3i", buf, i); i += 12
            ids = struct.unpack_from(f"<{k}i", buf, i); i += 4 * k
            kinds = struct.unpack_from(f"<{k}i", buf, i); i += 4 * k
            if cur is not None and layer < NL:
                cur["rows"].append((layer, row, ids, kinds))
    if cur:
        yield ("win", cur)


def topics_for(label):
    recs = [json.loads(l) for l in open(WS / "results/runs.jsonl") if f'"session": "{label}-' in l]
    return recs


if __name__ == "__main__":
    ol = sys.argv[2] if len(sys.argv) > 2 else rl
    recs = topics_for(ol)
    # request index in the route -> topic, by prompt length order
    events = list(read_route(rl))
    reqmark = [(e[1], e[2]) for e in events if e[0] == "req"]
    topic_of = {}
    j = 0
    for req, npr in reqmark:
        k = j
        while k < len(recs) and recs[k].get("prompt_tokens") != npr:
            k += 1
        if k < len(recs):
            rec = recs[k]
            topic_of[req] = rec["item"].split("-")[0] if rec["scenario"].startswith("ldr-") else None
            j = k + 1
    topics = sorted({t for t in topic_of.values() if t})
    fit = set(topics[0::2]); held = set(topics[1::2])
    print(f"{rl}: {len(reqmark)} requests, {len(topics)} LDR topics -> fit {len(fit)}, held-out {len(held)}")
    table = [defaultdict(Counter) for _ in range(NL)]
    res = None
    held_w = []
    nfit_rows = 0
    for e in events:
        if e[0] == "res":
            res = e[1]
        elif e[0] == "win":
            w = e[1]
            tp = topic_of.get(w["req"])
            if w["sfx"] < 0 or tp is None:
                continue
            if tp in fit:
                for layer, row, ids, kinds in w["rows"]:
                    if row < len(w["toks"]):
                        table[layer][w["toks"][row]].update(ids)
                        nfit_rows += 1
            elif tp in held:
                held_w.append((w, res))
    print(f"table: {nfit_rows} fit layer-rows; held-out windows {len(held_w)}")
    # per (window, layer): candidates with scores, true set
    cand = {l: [] for l in range(NL)}   # (score, layer, is_true, bytes)
    cand0 = {l: [] for l in range(NL)}
    true_n = Counter(); true_b = Counter()
    for w, rs in held_w:
        for l in range(NL):
            rows = [(r, ids, kinds) for (layer, r, ids, kinds) in w["rows"] if layer == l]
            tru = set()
            for r, ids, kinds in rows:
                if r <= w["a"]:
                    tru |= {e for e, k in zip(ids, kinds) if k == 3}
            true_n[l] += len(tru); true_b[l] += len(tru) * EB[l]
            for which, toks, store in (("all", w["toks"], cand), ("tok0", w["toks"][:1], cand0)):
                sc = Counter()
                for t in toks:
                    c = table[l].get(t)
                    if not c:
                        continue
                    tot = sum(c.values())
                    for e, v in c.items():
                        if rs is None or rs[l][e] == 3:
                            sc[e] += v / tot
                for e, s in sc.items():
                    store[l].append((s, e in tru))
    out = {}
    for name, store in (("all tokens of the window", cand), ("token 0 only", cand0)):
        print(f"\n## recall at <= 2x the true bytes ({name})")
        print("| layer | true CPU experts / window | recall (count) | predicted / true bytes |\n|---|---|---|---|")
        rec_l = {}
        for l in range(NL):
            arr = sorted(store[l], key=lambda x: -x[0])
            budget = 2 * true_n[l]          # same bytes per expert within a layer: 2x the true count
            take = arr[:budget]
            hit = sum(1 for s, t in take if t)
            rec_l[l] = hit / max(true_n[l], 1)
            print(f"| {l} | {true_n[l]/max(len(held_w),1):.2f} | {100*rec_l[l]:.1f} % | {len(take)/max(true_n[l],1):.2f} |")
        out[name] = rec_l
    json.dump({k: {str(l): v for l, v in d.items()} for k, d in out.items()}, open(WS / f"results/r13/a2-recall-{rl}.json", "w"))
    print(f"\nheld-out windows: {len(held_w)}; true CPU-side experts in layers 0-11 per window: {sum(true_n.values())/max(len(held_w),1):.2f} "
          f"({sum(true_b.values())/max(len(held_w),1)/1e6:.1f} MB)")
