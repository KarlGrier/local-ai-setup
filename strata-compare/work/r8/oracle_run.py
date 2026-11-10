#!/usr/bin/env python3
"""oracle_run.py LABEL ORACLE_FILE [--base URL] [--sets a,b] [--max-tokens N] — round 8 A.4: drive the oracle build
(engine-r8o, STRATA_SPEC_ORACLE=ORACLE_FILE set in its config env) through the server at your settings (T 1.0, top-p
0.95, top-k 20, min-p 0.05, effort high = xhigh) with fixed seeds, one request per scenario; after each request the
oracle file's size is recorded, so results/r8/oracle/LABEL.ranges.json maps each scenario to its byte range.
Scenarios: math, code (the long-reasoning prompts), prose (an explanatory essay), websyn (web-result synthesis with
numbered citations, ~6K tokens of results), doc64k / doc120k (question over the 64K / 120K documents),
websyn64k (synthesis over ~64K tokens of results)."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from client import stream_chat  # noqa: E402
from common import load_tokenizer  # noqa: E402

SET = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05, "reasoning_effort": "high"}


def results_block(text, n_results, words_each, topic):
    """numbered 'search results' cut from a real document (distinct passages), the shape a research agent pastes"""
    w = text.split()
    out, step = [], max(1, (len(w) - words_each) // max(1, n_results))
    for i in range(n_results):
        chunk = " ".join(w[i * step:i * step + words_each])
        out.append(f"[{i + 1}] Source: https://example.org/{topic}/{i + 1}\nTitle: {topic} notes, part {i + 1}\n"
                   f"Excerpt: {chunk}\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("oracle_file")
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--sets", default="math,code,prose,websyn,doc64k,doc120k")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=101)
    a = ap.parse_args()
    lr = {p["id"]: p for p in json.load(open(WS / "prompts/longreason.json"))}
    speed = json.load(open(WS / "prompts/speed.json"))
    doc = lambda size, rep: next(p for p in speed if (p["size"], p["rep"]) == (size, rep))["messages"][-1]["content"]
    big = doc("120k", 1)
    prompts = {
        "math": lr["math"]["messages"],
        "code": lr["code"]["messages"],
        "prose": [{"role": "user", "content": "Write an essay of about 1,200 words on how the printing press changed the "
                                              "way people in Europe learned, argued and kept records between 1450 and "
                                              "1650. Use concrete examples and a clear structure with headings."}],
        "websyn": [{"role": "user", "content": "You are writing one section of a research report. Using ONLY the search "
                                               "results below, write a 600-900 word section titled 'What the sources say' "
                                               "that synthesizes their main points, compares them, and cites every claim "
                                               "with its result number in square brackets like [3].\n\n"
                                               + results_block(big, 24, 180, "source")}],
        "websyn64k": [{"role": "user", "content": "Using ONLY the search results below, write a 600-900 word synthesis "
                                                  "with bracketed citations like [12].\n\n" + results_block(big, 120, 380, "ref")}],
        "doc64k": [{"role": "user", "content": doc("64k", 0) + "\n\nWrite a detailed, well-organized summary of the "
                                                               "document above for a new team member, with sections."}],
        "doc120k": [{"role": "user", "content": doc("120k", 0) + "\n\nWrite a detailed, well-organized summary of the "
                                                                 "document above for a new team member, with sections."}],
    }
    ranges = {}
    outp = WS / f"results/r8/oracle/{a.label}.ranges.json"
    for i, name in enumerate(a.sets.split(",")):
        before = os.path.getsize(a.oracle_file) if os.path.exists(a.oracle_file) else 0
        body = dict(SET, model="x", max_tokens=a.max_tokens, seed=a.seed + i, messages=prompts[name])
        t0 = time.time()
        r = stream_chat(a.base, body)
        time.sleep(0.5)
        after = os.path.getsize(a.oracle_file) if os.path.exists(a.oracle_file) else 0
        ranges[name] = {"from": before, "to": after, "prompt_tokens": r.get("prompt_tokens"),
                        "completion_tokens": r.get("completion_tokens"), "seconds": round(time.time() - t0, 1),
                        "decode_tps": r.get("decode_tps"), "error": r.get("error")}
        print(f"[{a.label}] {name}: prompt {r.get('prompt_tokens')} gen {r.get('completion_tokens')} in "
              f"{time.time() - t0:.1f} s ({r.get('decode_tps') and round(r['decode_tps'], 1)} tok/s), oracle bytes "
              f"{after - before}{' ERROR ' + str(r.get('error')) if r.get('error') else ''}", flush=True)
        json.dump(ranges, open(outp, "w"), indent=1)


if __name__ == "__main__":
    main()
