#!/usr/bin/env python3
"""r04_probe_live.py - 2026-10-12, the user's r04 diagnostic: what the model's distribution looks like at the position
where an r04 reply ended, before and after the sampler's filters.

  contexts  --label L --requests DIR --server-log FILE --tokenizer DIR --out CTX.json
            From a suite run with MSUITE_DUMP_REQUESTS=DIR on a server with STRATA_DEBUG=1: for every r04 run, the final
            request (the dump, split per run by the answer's n_steps), the reply's raw output (the "[strata] raw:"
            line - the generated text with the token that ended it, e.g. <|im_end|>), whether the answer has its JSON.
  probe     --endpoint URL --contexts CTX.json[,CTX2.json] --logpos FILE --tokenizer DIR --out PROBE.json
            On a server whose engine writes STRATA_LOGPOS (+ STRATA_LOGPOS_TOPK=20) and whose server takes
            strata_prefix_ids: for every context without its JSON (the cut ones), the final request again with the
            generated ids appended (re-encoded from the raw text, the ending token left off) and one candidate after
            them - first a priming request without the last 10 ids, so the probe reads only the tail through the
            verify windows (<= --short-read, 64) and the engine logs the stop position's row: the top 20 with
            log-probabilities, the candidate's exact log-probability and <|im_end|>'s. Candidates: </tool_call>,
            <tool_call>. After the filters = the engine's sampler chain on that row (sampler.cu: top_k, then top_p over
            the top_k list, then min_p against the top token, then temperature) with the request's own settings.
Measurement only; nothing here is graded."""
import argparse
import ast
import json
import math
import re
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "strata-cstar171" / "tools"))
import strata_tokenizer as ST  # noqa: E402

ITEM = "r04_strata_release"
CANDS = {248059: "</tool_call>", 248058: "<tool_call>"}
ENDS = {"<|im_end|>": 248046, "<|endoftext|>": 248044}


def load_tok(d):
    d = Path(d)
    v = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(v)
    for k, i in v.items():
        toks[i] = k
    return ST.Tokenizer(toks, (d / "merges.txt").read_text(encoding="utf-8").split("\n"),
                        json.loads((d / "token_type.json").read_text()))


def contexts(a):
    tok = load_tok(a.tokenizer)
    ans = sorted((WS / "suite/results" / a.label / "answers/research").glob(f"{ITEM}.r*.json"),
                 key=lambda p: int(re.search(r"\.r(\d+)\.json$", p.name).group(1)))
    reqs = sorted(Path(a.requests).glob("req-*.json"))
    raws = []
    for line in Path(a.server_log).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("[strata] raw: "):
            try:
                raws.append(ast.literal_eval(line[len("[strata] raw: "):]))
            except (ValueError, SyntaxError):
                raws.append(None)
    out, ri, cur = [], 0, 0
    for p in ans:
        d = json.loads(p.read_text())
        n = d["n_steps"]
        final = json.loads(reqs[ri + n - 1].read_text(encoding="utf-8")) if ri + n - 1 < len(reqs) else None
        ri += n
        c, z = (d["response"].get("content") or ""), (d["response"].get("reasoning") or "")
        key = c[-60:] if c.strip() else z[-60:]
        raw = None
        while cur < len(raws):                       # the replies come in request order: the next one that matches
            r = raws[cur]
            cur += 1
            if r is not None and key and key in r:
                raw = r
                break
        end = next((k for k in ENDS if raw is not None and raw.endswith(k)), None)
        gen = raw[: len(raw) - len(end)] if (raw is not None and end) else raw
        out.append({"label": a.label, "run": d["run"], "n_steps": n, "has_json": "```json" in c,
                    "content_tail": c[-120:], "reasoning_tail": z[-120:], "ended_by": end,
                    "raw_tail": raw[-200:] if raw else None, "gen_text": gen,
                    "gen_ids_n": len(tok.encode(gen)) if gen else None, "final_request": final})
        print(f"{a.label} r{d['run']}: {n} steps, JSON {'yes' if out[-1]['has_json'] else 'NO'}, ended by "
              f"{end!r}, raw tail {(raw or '')[-90:]!r}")
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))


def post(url, body):
    req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def parse_row(line):
    f = line.rstrip("\n").split("\t")
    row = {"pos": int(f[0]), "target": int(f[1]), "target_lp": float(f[2]), "top": int(f[3]), "top_lp": float(f[4]),
           "extra_lp": float(f[6]) if f[6] != "nan" else None, "topk": []}
    for x in " ".join(f[8:]).split():
        if ":" in x:
            i, lp = x.split(":", 1)
            row["topk"].append((int(i), float(lp)))
    return row


def filtered(topk, s):
    """The engine's chain (sampler.cu) on the logged top list: top_k, top_p over the top_k list, min_p, temperature."""
    k = s.get("top_k") or 64
    k = k if 0 < k < 64 else 64
    sel = sorted(topk, key=lambda x: -x[1])[: min(k, len(topk))]
    mx = sel[0][1]
    n = len(sel)
    tp = s.get("top_p", 1.0)
    if tp < 1.0:
        tot = sum(math.exp(l - mx) for _, l in sel)
        cum = 0.0
        for i, (_, l) in enumerate(sel):
            cum += math.exp(l - mx) / tot
            if cum >= tp:
                n = i + 1
                break
    mp = s.get("min_p", 0.0)
    if mp > 0:
        th = sel[0][1] + math.log(mp)
        for i in range(n):
            if sel[i][1] < th:
                n = i
                break
    t = s.get("temperature", 1.0) or 1.0
    keep = sel[:max(1, n)]
    z = sum(math.exp((l - mx) / t) for _, l in keep)
    return [(i, math.exp((l - mx) / t) / z) for i, l in keep], len(keep)


def probe(a):
    tok = load_tok(a.tokenizer)
    name = lambda i: tok.decode([i])
    ctxs = [c for f in a.contexts.split(",") for c in json.loads(Path(f).read_text())]
    lp_path = Path(a.logpos)
    res = []
    for c in ctxs:
        if c["has_json"] or not c.get("gen_text") or not c.get("final_request"):
            continue
        gen = tok.encode(c["gen_text"])
        body = {k: v for k, v in c["final_request"].items() if k not in ("stream", "stream_options")}
        body.update({"stream": False, "max_tokens": 1})
        s = {k: body.get(k) for k in ("temperature", "top_p", "top_k", "min_p")}
        entry = {"label": c["label"], "run": c["run"], "ended_by": c["ended_by"], "gen_ids": len(gen),
                 "raw_tail": c["raw_tail"], "sampling": s, "candidates": {}}
        for cid, cname in CANDS.items():
            post(a.endpoint, {**body, "strata_prefix_ids": gen[:-10]})                    # prime: the bulk cached
            before = lp_path.stat().st_size if lp_path.exists() else 0
            r = post(a.endpoint, {**body, "strata_prefix_ids": gen + [cid]})
            time.sleep(0.5)
            rows = []
            if lp_path.exists():                     # the engine creates it at its first logged window
                with lp_path.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(before)
                    rows = [parse_row(x) for x in f if x.strip() and x[0].isdigit()]
            hit = [x for x in rows if x["target"] == cid]
            u = r.get("usage") or {}
            if not hit:
                entry["candidates"][cname] = {"error": f"no logged row with target {cid} ({len(rows)} rows read)",
                                              "usage": u}
                continue
            row = max(hit, key=lambda x: x["pos"])
            prev = {x["pos"]: x["target"] for x in rows}
            after, n_keep = filtered(row["topk"], s)
            entry["candidates"][cname] = {
                "pos": row["pos"], "usage": u, "context_check": [prev.get(row["pos"] - i) for i in (3, 2, 1)] == gen[-3:],
                "p_candidate": math.exp(row["target_lp"]), "p_im_end": math.exp(row["extra_lp"]) if row["extra_lp"] is not None else None,
                "top1": [row["top"], name(row["top"]), math.exp(row["top_lp"])],
                "before_top5": [[i, name(i), math.exp(l)] for i, l in sorted(row["topk"], key=lambda x: -x[1])[:5]],
                "after_top5": [[i, name(i), p] for i, p in sorted(after, key=lambda x: -x[1])[:5]],
                "after_n_kept": n_keep,
                "candidate_after": next((p for i, p in after if i == cid), 0.0),
                "im_end_after": next((p for i, p in after if i == 248046), 0.0)}
            e = entry["candidates"][cname]
            print(f"{c['label']} r{c['run']} +{cname}: p={e['p_candidate']:.4g}, p(<|im_end|>)={e['p_im_end']:.4g}, "
                  f"top {e['top1'][1]!r} {e['top1'][2]:.3f}; after filters ({n_keep} kept): "
                  + ", ".join(f"{t!r} {p:.3f}" for _, t, p in e["after_top5"]) + f"; context check {e['context_check']}")
        res.append(entry)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))


ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["contexts", "probe"])
for k in ("label", "requests", "server-log", "tokenizer", "out", "endpoint", "contexts", "logpos"):
    ap.add_argument("--" + k)
a = ap.parse_args()
contexts(a) if a.cmd == "contexts" else probe(a)
