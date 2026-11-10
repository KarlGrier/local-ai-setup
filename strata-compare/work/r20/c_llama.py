#!/usr/bin/env python3
"""c_llama.py - 2026-10-14 C, the engine cross-check: does another engine (llama.cpp, the signal-3.8-opus build
6fcaa16 that serves this architecture) see the same peaked distribution inside a digit run, on the same Unsloth Q8_0
file and the same token sequence?

  dump   --endpoint STRATA --cases ... : each case's full token sequence as Strata's engine reads it (rendered chat
         prompt + the original reasoning + the withheld 256th digit + the -cont1024-q8 continuation), written by the
         scratch hook server (strata_dump_ids) to results/r20/q8loop/ids-<case>.json (max_tokens 1).
  probe  --endpoint LLAMA --cases ... : llama-server /completion with the ids before digit j as the prompt
         (n_predict 1, n_probs 5, raw probabilities, cache_prompt on so each later j reads only the new tokens):
         p(top), whether top is the digit, p(2nd) at j = 256, 300, 600, 900.
Measurement only."""
import argparse
import json
import math
import re
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "suite"))
sys.path.insert(0, str(WS / "work/r20"))
from msuite import runner  # noqa: E402
from msuite.backend_openai import OpenAIBackend  # noqa: E402
from msuite.common import answer_path, label_dir, read_json  # noqa: E402
sys.path.insert(0, str(WS / "strata-cstar171" / "tools"))
import strata_tokenizer as ST  # noqa: E402


def load_tok(d):   # (as loop_probe.py's; that file is a script and parses its arguments on import)
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

O = WS / "results/r20/q8loop"


def post(url, body, timeout=3600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def case_seq(tok, case):
    label, name, run = case.split(":")
    iid = f"coding/{name}"
    orig = read_json(answer_path(label, iid, int(run)))
    z = orig["response"].get("reasoning") or ""
    unit, n_run = trailing_run(z)
    unit_id = tok.encode(unit)[0]
    cont = read_json(answer_path(label + "-cont1024-q8", iid, int(run)))
    zc = cont["response"].get("reasoning") or ""
    tail = zc[len(z) + 1:]
    seq = tok.encode(z) + [unit_id] + tok.encode(tail)
    return label, iid, unit_id, n_run, seq, len(tok.encode(z)) + 1


ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["dump", "probe"])
ap.add_argument("--endpoint", required=True)
ap.add_argument("--tokenizer", required=True)
ap.add_argument("--cases", required=True)
ap.add_argument("--positions", default="256,300,600,900", help="digits j to read (ascending: each request extends the cache)")
ap.add_argument("--tag", default="")
a = ap.parse_args()
tok = load_tok(a.tokenizer)
items = {i["id"]: i for i in runner.load_items(["coding"])}
res = []
for case in a.cases.split(","):
    label, iid, unit_id, n_run, seq, cut = case_seq(tok, case)
    f = O / f"ids-{case.replace(':', '_')}.json"
    if a.cmd == "dump":
        meta = read_json(label_dir(label) / "meta.json")
        b = meta.get("backend") or {}
        be = OpenAIBackend(a.endpoint, max_tokens=1, sampling=b.get("sampling"), effort=b.get("reasoning_effort"),
                           extra_body={"strata_prefix_ids": seq, "strata_dump_ids": str(f)})
        msgs, _ = runner.messages_for(items[iid])
        be._exchange(be._body(msgs, None, 1), 1)
        ids = json.loads(f.read_text())
        assert ids[-len(seq):] == seq
        print(case, "dumped", len(ids), "ids; prompt part", len(ids) - len(seq), flush=True)
        continue
    ids = json.loads(f.read_text())
    P = len(ids) - len(seq)
    start = P + cut - 1 - n_run                    # index of digit 1 of the run in ids
    assert all(t == unit_id for t in ids[start:start + n_run + 1]) and ids[start - 1] != unit_id
    out = {"case": case, "prompt_part": P, "at": {}}
    for j in sorted(int(x) for x in re.split(r"[ ,]+", a.positions.strip()) if x):
        t0 = time.time()
        r = post(a.endpoint.rstrip("/") + "/completion", {"prompt": ids[:start + j - 1], "n_predict": 1, "n_probs": 5,
                                                          "temperature": 0, "cache_prompt": True,
                                                          "post_sampling_probs": False})
        cp = (r.get("completion_probabilities") or [{}])[0]
        top = cp.get("top_logprobs") or cp.get("top_probs") or []
        ps = [(int(t["id"]), math.exp(t["logprob"]) if "logprob" in t else t["prob"]) for t in top]
        ps.sort(key=lambda x: -x[1])
        out["at"][str(j)] = {"p_top": round(ps[0][1], 6), "top_is_digit": ps[0][0] == unit_id,
                             "p_digit": round(next((p for i, p in ps if i == unit_id), 0.0), 6),
                             "p_2nd": round(ps[1][1], 6) if len(ps) > 1 else None,
                             "second": tok.decode([ps[1][0]]) if len(ps) > 1 else None,
                             "wall_s": round(time.time() - t0, 1),
                             "prompt_n": (r.get("timings") or {}).get("prompt_n")}
        print(case, j, json.dumps(out["at"][str(j)]), flush=True)
    res.append(out)
if a.cmd == "probe":
    (O / f"llama-q8{a.tag}-{int(time.time())}.json").write_text(json.dumps(res, indent=1))
