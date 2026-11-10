#!/usr/bin/env python3
"""bench.py — baseline vs tuned measurements with LDR's benchmark tooling.

  prepare DIR [--browsecomp 3] [--frames 3] [--seed 2026]
        hard multi-step questions: BrowseComp via LDR's DatasetRegistry (downloads and decrypts OpenAI's test set)
        and FRAMES (google/frames-benchmark, multi-hop over Wikipedia), sampled with a fixed seed; plus the two
        open-ended report questions in OPEN below. BrowseComp queries use LDR's BROWSECOMP_QUERY_TEMPLATE (asks for
        "Exact Answer:" / "Confidence:"). Writes DIR/questions.jsonl.
  run DIR LABEL [--only ID,...] [--kind multi|open]
        runs each question (not yet done under LABEL) through tools/ldr-client.py research, i.e. the running LDR
        (start it in the wanted profile first); results/bench-LABEL-<id>/ per question
  grade DIR LABEL
        grades each finished answer with LDR's grade_single_result (BrowseComp template for BrowseComp, SimpleQA
        template for FRAMES), the judge being the served model at xhigh through strata-proxy; open-ended questions
        are not graded (for you to judge); writes DIR/grades-LABEL.jsonl
  table DIR LABEL [LABEL...]
        accuracy, sources used per answer, citation checks and wall time per label -> DIR/results.md
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai/deep-research")
CACHE = WS / "cache" / "bench"
OPEN = [
    {"id": "open1", "kind": "open", "dataset": "open",
     "question": ("How do inference engines run Mixture-of-Experts language models whose experts do not fit in GPU "
                  "memory, on consumer hardware (one or two GPUs plus system RAM)? Compare the main techniques — "
                  "expert offloading and caching policies, expert prediction/prefetching, CPU execution of experts, "
                  "quantization of experts, and speculative decoding with MoE models — with the speed-ups and "
                  "accuracy costs reported for each, the engines that implement them, and which combination gives "
                  "the best tokens per second for single-user chat.")},
    {"id": "open2", "kind": "open", "dataset": "open",
     "question": ("What is the current state of speculative decoding for large language models? Compare draft-model "
                  "speculation, self-speculation (early exit / layer skipping), multi-token-prediction (MTP) heads, "
                  "Medusa/EAGLE-style heads, lookahead and suffix/n-gram drafting: typical acceptance rates, "
                  "end-to-end speed-ups reported, what limits them (batch size, sampling temperature, memory "
                  "bandwidth), and which approaches production engines have adopted.")},
]
FRAMES_URL = "https://huggingface.co/datasets/google/frames-benchmark/resolve/main/test.tsv"


def load_jsonl(p):
    p = Path(p)
    return [json.loads(l) for l in p.open(encoding="utf-8")] if p.exists() else []


def cmd_prepare(a):
    out = Path(a.dir)
    out.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(WS / ".venv/lib/python3.12/site-packages"))
    from local_deep_research.benchmarks.datasets import DatasetRegistry
    from local_deep_research.benchmarks.datasets.browsecomp import BrowseCompDataset
    from local_deep_research.benchmarks.runners import format_query
    qs = []
    if a.browsecomp:
        csv = CACHE / "browse_comp_test_set.csv"
        if not csv.exists():
            r = requests.get(BrowseCompDataset.get_default_dataset_path(), timeout=120)
            r.raise_for_status()
            csv.write_bytes(r.content)
        ex = DatasetRegistry.load_dataset("browsecomp", dataset_path=str(csv), num_examples=a.browsecomp, seed=a.seed)
        for i, e in enumerate(ex):
            q = e.get("problem") or e.get("question")
            qs.append({"id": f"bc{i + 1}", "kind": "multi", "dataset": "browsecomp", "question": q,
                       "query": format_query(q, "browsecomp"), "answer": e.get("answer") or e.get("correct_answer")})
    if a.frames:
        tsv = CACHE / "frames_test.tsv"
        if not tsv.exists():
            r = requests.get(FRAMES_URL, timeout=120)
            r.raise_for_status()
            tsv.write_bytes(r.content)
        import pandas as pd
        df = pd.read_csv(tsv, sep="\t")
        rows = df.to_dict("records")
        random.seed(a.seed)
        for i, e in enumerate(random.sample(rows, a.frames)):
            qs.append({"id": f"fr{i + 1}", "kind": "multi", "dataset": "frames", "question": e["Prompt"],
                       "query": e["Prompt"], "answer": str(e["Answer"]), "reasoning_types": e.get("reasoning_types")})
    for o in OPEN:
        qs.append({**o, "query": o["question"], "answer": None})
    with open(out / "questions.jsonl", "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"{len(qs)} questions -> {out / 'questions.jsonl'}")
    for q in qs:
        print(f"  {q['id']:6s} {q['dataset']:10s} {q['question'][:110]}")


def cmd_run(a):
    qs = load_jsonl(Path(a.dir) / "questions.jsonl")
    only = set(a.only.split(",")) if a.only else None
    for q in qs:
        if only and q["id"] not in only:
            continue
        if a.kind and q["kind"] != a.kind:
            continue
        tag = f"bench-{a.label}-{q['id']}"
        if (WS / "results" / tag / "summary.json").exists():
            print(f"{tag}: done already", flush=True)
            continue
        cmd = [str(WS / ".venv/bin/python"), str(WS / "tools/ldr-client.py"), "research", tag, q["query"]]
        if a.effort_extract:
            cmd += ["--effort-extract", a.effort_extract]
        print(f"{time.strftime('%H:%M:%S')} {tag}: start", flush=True)
        with open(WS / "logs" / f"{tag}.out", "w") as log:
            rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
        print(f"{time.strftime('%H:%M:%S')} {tag}: exit {rc}", flush=True)


class StrataJudge:
    """Minimal evaluation LLM for LDR's grader: .invoke(prompt) -> object with .content (xhigh, temperature 0)."""

    class _R:
        def __init__(self, c):
            self.content = c

    def invoke(self, prompt):
        model = requests.get("http://127.0.0.1:8080/v1/models", timeout=10).json()["data"][0]["id"]
        body = {"model": model, "messages": [{"role": "user", "content": prompt if isinstance(prompt, str) else
                                               prompt[0].content}],
                "temperature": 0.0, "max_tokens": 16000, "reasoning_effort": "xhigh", "stream": False}
        r = requests.post("http://127.0.0.1:8090/v1/chat/completions", json=body, timeout=3600)
        r.raise_for_status()
        return self._R(r.json()["choices"][0]["message"].get("content") or "")


def answer_text(tag):
    d = WS / "results" / tag
    for p in (d / "report.md", d / "deep" / "report.md"):
        if p.exists() and p.read_text().strip():
            return p.read_text()
    return ""


def cmd_grade(a):
    sys.path.insert(0, str(WS / ".venv/lib/python3.12/site-packages"))
    from local_deep_research.benchmarks import graders
    graders.get_evaluation_llm = lambda *x, **k: StrataJudge()
    qs = load_jsonl(Path(a.dir) / "questions.jsonl")
    outp = Path(a.dir) / f"grades-{a.label}.jsonl"
    done = {g["id"] for g in load_jsonl(outp)}
    with open(outp, "a", encoding="utf-8") as f:
        for q in qs:
            if q["kind"] != "multi" or q["id"] in done:
                continue
            tag = f"bench-{a.label}-{q['id']}"
            resp = answer_text(tag)
            if not resp:
                rec = {"id": q["id"], "tag": tag, "is_correct": False, "note": "no answer"}
            else:
                # the grader sees the answer part: the report up to its citation check / sources
                cut = resp
                for mark in ("\n## Citation check", "\n## Sources"):
                    cut = cut.split(mark)[0]
                g = graders.grade_single_result(
                    {"id": q["id"], "problem": q["question"], "correct_answer": q["answer"], "response": cut[:60000]},
                    dataset_type="browsecomp" if q["dataset"] == "browsecomp" else "simpleqa")
                rec = {"id": q["id"], "tag": tag, **{k: g.get(k) for k in ("is_correct", "extracted_by_grader",
                                                                          "reasoning", "confidence",
                                                                          "graded_extracted_answer")}}
            rec["correct_answer"] = q["answer"]
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{q['id']}: correct={rec.get('is_correct')}  answer={rec.get('graded_extracted_answer') or rec.get('extracted_by_grader')}", flush=True)


def cmd_table(a):
    qs = load_jsonl(Path(a.dir) / "questions.jsonl")
    lines = []
    for label in a.labels:
        grades = {g["id"]: g for g in load_jsonl(Path(a.dir) / f"grades-{label}.jsonl")}
        lines += [f"### {label}", "",
                  "| question | correct | wall | LLM calls | searches | pages read | sources cited (of them read) | "
                  "claims checked (supported / partial / unsupported) | cited URLs resolving |",
                  "|---|---|---|---|---|---|---|---|---|"]
        tot = {"correct": 0, "graded": 0, "wall": 0.0}
        for q in qs:
            tag = f"bench-{label}-{q['id']}"
            sp = WS / "results" / tag / "summary.json"
            if not sp.exists():
                lines.append(f"| {q['id']} | – | – | – | – | – | – | – | – |")
                continue
            s = json.loads(sp.read_text())
            d = s.get("deep") or {}
            g = grades.get(q["id"])
            corr = "–" if q["kind"] == "open" else ("yes" if g and g.get("is_correct") else ("no" if g else "?"))
            if g:
                tot["graded"] += 1
                tot["correct"] += bool(g.get("is_correct"))
            tot["wall"] += s["wall_s"]
            c = s.get("citations") or {}
            v = d.get("verdicts") or {}
            claims = (f"{d.get('claims')} ({v.get('supported', 0)} / {v.get('partial', 0)} / {v.get('unsupported', 0)})"
                      if d else "not run")
            lines.append(f"| {q['id']} ({q['dataset']}) | {corr} | {s['wall_s'] / 60:.0f} min | {s['llm_calls']} | "
                         f"{d.get('searches', '–')} | "
                         f"{d.get('pages_read', (s.get('llm_calls_by_class') or {}).get('extract', {}).get('calls', '–'))} | "
                         f"{d.get('sources_cited', c.get('cited_numbers', '–'))}"
                         f"{' (' + str(d['sources_cited_read']) + ')' if 'sources_cited_read' in d else ''} | {claims} | "
                         f"{c.get('urls_resolving', '–')}/{c.get('listed_urls', '–')} |")
        lines += ["", f"accuracy {tot['correct']}/{tot['graded']}, total wall {tot['wall'] / 3600:.1f} h", ""]
    (Path(a.dir) / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    q = sp.add_parser("prepare")
    q.add_argument("dir")
    q.add_argument("--browsecomp", type=int, default=3)
    q.add_argument("--frames", type=int, default=3)
    q.add_argument("--seed", type=int, default=2026)
    q = sp.add_parser("run")
    q.add_argument("dir")
    q.add_argument("label")
    q.add_argument("--only", default="")
    q.add_argument("--kind", choices=["multi", "open"], default=None)
    q.add_argument("--effort-extract", default=None)
    q = sp.add_parser("grade")
    q.add_argument("dir")
    q.add_argument("label")
    q = sp.add_parser("table")
    q.add_argument("dir")
    q.add_argument("labels", nargs="+")
    a = p.parse_args()
    {"prepare": cmd_prepare, "run": cmd_run, "grade": cmd_grade, "table": cmd_table}[a.cmd](a)


if __name__ == "__main__":
    main()
