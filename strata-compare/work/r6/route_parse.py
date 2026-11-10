#!/usr/bin/env python3
"""route_parse.py — round 6: read the routing trace v2 (STRATA_R6_ROUTE) and the fixed --dump-routing file.

Library:  load_v2(path) -> list of windows, each a dict:
    id, pos0, T, kind (0 decode, 1 read), tokens[T], n_keep, out[T], t_commit_ns,
    layers: list of 48 dicts {layer, n_tok, k, ids (n_tok x k), w (n_tok x k), kind (n_tok x k: -1 CPU, 0 VRAM, 1 PCIe,
            2 helper), wait, plan, rbegin, actq, jobs, run, rwait (us), rang_ns}
          load_dump(path) -> list of (layer, ids[k]) records (upstream format: i32 layer, i32 k, k ids, k f32 weights)
CLI:  route_parse.py verify V2.bin DUMP.bin STATS.out   — the completeness checks of item 5 against the engine's
      own --stats counters (rounds, window sizes, accepted per round, drafts, hit counts, pool time).
"""
import re
import struct
import sys

import numpy as np

WIND, ACPT, LAYR = 0x444E4957, 0x54504341, 0x5259414C


def load_v2(path):
    b = open(path, "rb").read()
    at, wins, cur = 0, [], None
    while at < len(b):
        (m,) = struct.unpack_from("<I", b, at)
        if m == WIND:
            wid, pos0, T, kind = struct.unpack_from("<iqii", b, at + 4)
            at += 4 + 4 + 8 + 4 + 4
            toks = list(struct.unpack_from(f"<{T}i", b, at)); at += 4 * T
            cur = dict(id=wid, pos0=pos0, T=T, kind=kind, tokens=toks, layers=[], n_keep=None)
            wins.append(cur)
        elif m == LAYR:
            wid, layer, nt, k = struct.unpack_from("<4i", b, at + 4)
            at += 20
            n = nt * k
            ids = np.frombuffer(b, "<i4", n, at).reshape(nt, k); at += 4 * n
            w = np.frombuffer(b, "<f4", n, at).reshape(nt, k); at += 4 * n
            kd = np.frombuffer(b, "i1", n, at).reshape(nt, k); at += (n + 3) & ~3
            tm = struct.unpack_from("<7f", b, at); at += 28
            (ns,) = struct.unpack_from("<q", b, at); at += 8
            rec = dict(window=wid, layer=layer, n_tok=nt, k=k, ids=ids, w=w, kind=kd, wait=tm[0], plan=tm[1],
                       rbegin=tm[2], actq=tm[3], jobs=tm[4], run=tm[5], rwait=tm[6], rang_ns=ns)
            assert cur is not None and cur["id"] == wid, f"LAYR of window {wid} outside its window"
            cur["layers"].append(rec)
        elif m == ACPT:
            wid, nk, T = struct.unpack_from("<3i", b, at + 4)
            at += 16
            out = list(struct.unpack_from(f"<{T}i", b, at)); at += 4 * T
            (ns,) = struct.unpack_from("<q", b, at); at += 8
            assert cur is not None and cur["id"] == wid and cur["T"] == T, f"ACPT {wid} does not close window {cur and cur['id']}"
            cur["n_keep"], cur["out"], cur["t_commit_ns"] = nk, out, ns
        else:
            raise ValueError(f"bad magic {m:#x} at {at}")
    return wins


def load_dump(path):
    b = open(path, "rb").read()
    at, recs = 0, []
    while at < len(b):
        layer, k = struct.unpack_from("<2i", b, at); at += 8
        ids = struct.unpack_from(f"<{k}i", b, at); at += 4 * k
        at += 4 * k
        recs.append((layer, ids))
    return recs


def stats_of(path):
    s = open(path).read()
    d = {}
    m = re.search(r"speculation\s+(\d+) rounds of \d+, drafts accepted (\d+) of (\d+)", s)
    d["rounds"], d["drafts_ok"], d["drafts"] = map(int, m.groups())
    m = re.search(r"window sizes\s+(.*?)\s+\(min", s)
    d["win_hist"] = {int(a): int(c) for a, c in re.findall(r"T(\d+):(\d+)", m.group(1))}
    m = re.search(r"accepted per round\s+(.*)", s)
    d["acc_hist"] = {int(a): int(c) for a, c in re.findall(r"(\d+):(\d+)", m.group(1))}
    m = re.search(r"decode\s+(\d+) tokens in ([\d.]+) ms", s)
    d["tokens"], d["decode_ms"] = int(m.group(1)), float(m.group(2))
    m = re.search(r"R4 expert-cache hits\s+(\d+) of (\d+)", s)
    d["hits"], d["lookups"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"verify window\s+wait for rings ([\d.]+)\s+pool ([\d.]+)", s)
    d["wait_ms_round"], d["pool_ms_round"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"dispatch\s+plan ([\d.]+)\s+activation quantize ([\d.]+)\s+jobs ([\d.]+)\s+run ([\d.]+)", s)
    d["plan"], d["actq"], d["jobs"], d["run"] = map(float, m.groups())
    m = re.search(r"CPU experts ([\d.]+) distinct / ([\d.]+) routed per layer", s)
    d["cpu_distinct"], d["cpu_routed"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"routing dumped\s+\S+ \((\d+) records.*?(\d+) accepted", s)
    if m:
        d["dump_calls"], d["dump_rows"] = int(m.group(1)), int(m.group(2))
    return d


def verify(v2, dump, stats):
    W = load_v2(v2)
    D = load_dump(dump)
    S = stats_of(stats)
    ok = True

    def check(name, got, want, tol=0.0):
        nonlocal ok
        good = (abs(got - want) <= tol * max(1.0, abs(want))) if isinstance(want, float) or tol else got == want
        ok &= bool(good)
        print(f"  {'OK ' if good else 'BAD'} {name}: trace {got} vs expected {want}")

    dec = [w for w in W if w["kind"] == 0]
    print(f"{v2}: {len(W)} windows ({len(dec)} decode), {sum(len(w['layers']) for w in W)} layer records")
    check("every window closed (ACPT)", sum(w["n_keep"] is not None for w in W), len(W))
    check("window ids 0..n-1 in order", [w["id"] for w in W] == list(range(len(W))), True)
    check("48 layer records per window, layers 0..47 in order",
          all([r["layer"] for r in w["layers"]] == list(range(48)) for w in W), True)
    check("n_tok == T in every layer record", all(r["n_tok"] == w["T"] for w in W for r in w["layers"]), True)
    pos_ok = all(W[i + 1]["pos0"] == W[i]["pos0"] + W[i]["n_keep"] for i in range(len(W) - 1))
    check("positions contiguous: pos0[w+1] = pos0[w] + n_keep[w]", pos_ok, True)
    acc_ok = all(w["n_keep"] == 1 + next((a for a in range(w["T"] - 1) if w["tokens"][a + 1] != w["out"][a]), w["T"] - 1)
                 for w in dec)
    check("n_keep = 1 + accepted drafts (recomputed from tokens/outputs)", acc_ok, True)
    check("decode windows = --stats rounds", len(dec), S["rounds"])
    check("drafts offered sum(T-1)", sum(w["T"] - 1 for w in dec), S["drafts"])
    check("drafts accepted sum(n_keep-1)", sum(w["n_keep"] - 1 for w in dec), S["drafts_ok"])
    check("rejected draft rows sum(T-n_keep)", sum(w["T"] - w["n_keep"] for w in dec), S["drafts"] - S["drafts_ok"])
    wh = {}
    for w in dec:
        wh[w["T"]] = wh.get(w["T"], 0) + 1
    check("window-size histogram", {k: v for k, v in wh.items() if v}, {k: v for k, v in S["win_hist"].items() if v})
    ah = {}
    for w in dec:
        ah[w["n_keep"] - 1] = ah.get(w["n_keep"] - 1, 0) + 1
    check("accepted-per-round histogram", {k: v for k, v in ah.items() if v}, {k: v for k, v in S["acc_hist"].items() if v})
    check("tokens emitted sum(n_keep) (>= --stats decode tokens; eos/max cut the last window)",
          sum(w["n_keep"] for w in dec) >= S["tokens"], True)
    # placement: VRAM hits among all routed entries of the decode windows
    hits = sum(int((r["kind"] == 0).sum()) for w in dec for r in w["layers"])
    look = sum(r["kind"].size for w in dec for r in w["layers"])
    check("VRAM-hit entries (kind 0) vs R4 expert-cache hits", hits, S["hits"])
    check("routed entries vs R4 lookups", look, S["lookups"])
    cpu_rows = [r for w in dec for r in w["layers"]]
    dist = np.mean([len(set(r["ids"][r["kind"] == -1].tolist())) for r in cpu_rows])
    rout = np.mean([int((r["kind"] == -1).sum()) for r in cpu_rows])
    check("CPU experts distinct per layer", round(float(dist), 2), S["cpu_distinct"], tol=0.01)
    check("CPU experts routed per layer", round(float(rout), 2), S["cpu_routed"], tol=0.01)
    nr = S["rounds"]
    for key, sk in (("run", "run"), ("actq", "actq"), ("plan", "plan"), ("jobs", "jobs")):
        tot = sum(r[key] for w in dec for r in w["layers"]) / 1e3 / nr
        check(f"{key} ms/round (timing)", round(tot, 3), S[sk], tol=0.05)
    tw = sum(r["wait"] for w in dec for r in w["layers"]) / 1e3 / nr
    check("doorbell wait ms/round vs 'wait for rings'", round(tw, 3), S["wait_ms_round"], tol=0.05)
    wsum = [float(r["w"].sum(axis=1).mean()) for w in dec[:50] for r in w["layers"]]
    check("router weights present (row sums ~1, mean)", round(float(np.mean(wsum)), 3), 1.0, tol=0.05)
    # the fixed upstream dump: accepted rows only, same ids
    acc_rows = [(r["layer"], tuple(r["ids"][t].tolist())) for w in W for r in w["layers"] for t in range(w["n_keep"])]
    # upstream writes layer-major within a window: for each layer, rows t < n_keep
    check("--dump-routing records = accepted rows x 48", len(D), sum(w["n_keep"] for w in W) * 48)
    check("--dump-routing content = the v2 accepted rows", D == acc_rows, True)
    if "dump_rows" in S:
        check("engine's own accepted-row count", S["dump_rows"], len(D))
    all_rows = sum(w["T"] for w in W) * 48
    print(f"  (upstream's pre-fix dump would have had {all_rows} rows: {all_rows - len(D)} double-counted rejected-draft"
          f" rows = {100.0 * (all_rows - len(D)) / all_rows:.1f} %)")
    print("VERIFY", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    if sys.argv[1] == "verify":
        sys.exit(0 if verify(sys.argv[2], sys.argv[3], sys.argv[4]) else 1)
