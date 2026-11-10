#!/usr/bin/env python3
"""extract-effort-test.py — does LDR's page-extraction step need xhigh thinking? Replays real extraction tasks at
reasoning effort low / medium / xhigh and scores the outputs by quality (not speed).

  collect OUT_DIR [--n 36]   gather tasks: [FETCH] blocks of LDR's logs (page text, focus, question) and the deep
                             runs' evidence.jsonl (pages up to 120K chars); writes OUT_DIR/tasks.jsonl
  run OUT_DIR                each task at each effort (random order per task), the exact prompt the deep profile
                             sends (LDR's extraction prompt, 4,000-char limit); writes OUT_DIR/outputs.jsonl
  judge OUT_DIR              blind listwise ranking of the three outputs per task by the model at xhigh (the page
                             text is included up to 60K tokens); writes OUT_DIR/judge.jsonl
  report OUT_DIR             scores -> OUT_DIR/summary.json and summary.md

Scores: (1) verbatim rate — share of output lines that occur in the page text (the prompt demands verbatim
quotes; whitespace/quote normalised); (2) NOT RELEVANT agreement; (3) the judge's ranks and pairwise wins; (4)
output size, time and generated tokens (reported, not used for the choice).
Calls go to Strata directly (127.0.0.1:8080) with an explicit reasoning_effort. Connection errors are retried (up to
30 min); resumable: finished (task, effort) pairs are skipped.
"""
import argparse
import glob
import json
import random
import re
import sys
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai/deep-research")
sys.path.insert(0, str(WS / ".venv/lib/python3.12/site-packages"))
from local_deep_research.advanced_search_system.tools.fetch.prompts import SUMMARY_FOCUS_QUERY_PROMPT  # noqa: E402
from local_deep_research.deep.prompts import EXTRACT_LIMIT_NEW, EXTRACT_LIMIT_OLD  # noqa: E402

API = "http://127.0.0.1:8080/v1/chat/completions"     # Strata directly: independent of LDR/proxy restarts
EFFORTS = ["low", "medium", "xhigh"]


def model_id():
    return requests.get("http://127.0.0.1:8080/v1/models", timeout=10).json()["data"][0]["id"]


def chat(prompt, effort, max_tokens=30000, temperature=0.6):
    for attempt in range(60):
        try:
            body = {"model": model_id(), "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
                    "temperature": temperature, "reasoning_effort": effort, "stream": False}
            t = time.time()
            r = requests.post(API, json=body, timeout=3600)
            break
        except requests.ConnectionError as ex:
            print(f"  connection error ({ex.__class__.__name__}); retry in 30 s", flush=True)
            time.sleep(30)
    else:
        raise RuntimeError("Strata unreachable for 30 min")
    r.raise_for_status()
    d = r.json()
    m = d["choices"][0]["message"]
    return {"text": (m.get("content") or "").strip(), "reasoning_chars": len(m.get("reasoning_content") or ""),
            "usage": d.get("usage"), "seconds": round(time.time() - t, 1), "finish": d["choices"][0].get("finish_reason")}


def parse_fetch_blocks(path):
    """[FETCH] records in an LDR log (the sink writes each multi-line record on one line): url, focus, question,
    title. The page text is re-downloaded by collect (the log copy lost its line breaks)."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "[FETCH] mode=" not in line or "[FETCH] focus: " not in line:
                continue
            parts = {}
            for seg in line.split("[FETCH] ")[1:]:
                for key in ("mode=", "focus: ", "overall_query: ", "title: "):
                    if seg.startswith(key):
                        parts[key] = seg[len(key):].strip()
            m = re.match(r"\S+ url=(\S+)", parts.get("mode=", ""))
            if m and parts.get("focus: ") and parts.get("overall_query: "):
                out.append({"url": m.group(1), "focus": parts["focus: "], "query": parts["overall_query: "],
                            "title": parts.get("title: ", ""), "page_text": "", "src": Path(path).name})
    return out


def cmd_collect(a):
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tasks = []
    for p in sorted(glob.glob(str(WS / "logs/ldr-web_*.log"))):
        tasks += parse_fetch_blocks(p)
    for p in sorted(glob.glob(str(WS / "results/deep-runs/*/evidence.jsonl"))):
        q = None
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            if r.get("type") == "start":
                q = r.get("query")
            if r.get("type") == "fetch" and r.get("page_text"):
                tasks.append({"url": r["url"], "focus": r["focus"], "query": q, "title": r.get("title", ""),
                              "page_text": r["page_text"], "orig_summary": r.get("extraction", ""), "src": p})
    # one task per (url, focus); keep a mix of page sizes
    seen, uniq = set(), []
    for t in tasks:
        k = (t["url"], t["focus"])
        if k in seen or not t.get("query"):
            continue
        seen.add(k)
        uniq.append(t)
    random.seed(20260930)
    # re-download the pages with LDR's own ContentFetcher: half of the tasks at the upstream cap (10,000 chars),
    # half at the deep cap (120,000 chars) — the same kinds of tasks at both page lengths
    from local_deep_research.content_fetcher import ContentFetcher
    random.shuffle(uniq)
    got = []
    for t in uniq:
        if len(got) >= a.n:
            break
        want_long = sum(1 for g in got if g["cap"] == 120000) < a.n // 2
        cap = 120000 if want_long else 10000
        try:
            with ContentFetcher(timeout=30) as f:
                r = f.fetch(t["url"], max_length=cap)
        except Exception as ex:  # noqa: BLE001
            print(f"  fetch failed {t['url'][:80]}: {ex}")
            continue
        txt = (r or {}).get("content") or ""
        if r.get("status") != "success" or len(txt) < 1500:
            continue
        if want_long and len(txt) <= 12000:
            cap = 10000                         # a short page: use it as a short task
            txt = txt[:10000]
        t.update(page_text=txt, cap=cap, title=t.get("title") or r.get("title") or "")
        got.append(t)
        print(f"  {cap:6d} cap  {len(txt):7d} chars  {t['url'][:90]}", flush=True)
    uniq = got
    long_ = [t for t in uniq if len(t["page_text"]) > 12000]
    short = [t for t in uniq if len(t["page_text"]) <= 12000]
    random.shuffle(long_)
    random.shuffle(short)
    n_long = min(len(long_), a.n // 2)
    pick = long_[:n_long] + short[: a.n - n_long]
    for i, t in enumerate(pick):
        t["id"] = i
    with open(out / "tasks.jsonl", "w", encoding="utf-8") as f:
        for t in pick:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"{len(uniq)} distinct tasks found ({len(long_)} long, {len(short)} short); picked {len(pick)} "
          f"({n_long} long) -> {out / 'tasks.jsonl'}")


def prompt_of(t):
    p = SUMMARY_FOCUS_QUERY_PROMPT.format(focus=t["focus"], title=t.get("title", ""), url=t["url"],
                                          content=t["page_text"], overall_query=t["query"])
    return p.replace(EXTRACT_LIMIT_OLD, EXTRACT_LIMIT_NEW.format(max_chars=4000))


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if Path(p).exists() else []


def cmd_run(a):
    out = Path(a.out_dir)
    tasks = load(out / "tasks.jsonl")
    done = {(r["id"], r["effort"]) for r in load(out / "outputs.jsonl")}
    random.seed(7)
    with open(out / "outputs.jsonl", "a", encoding="utf-8") as f:
        for t in tasks:
            order = EFFORTS[:]
            random.shuffle(order)
            for e in order:
                if (t["id"], e) in done:
                    continue
                try:
                    r = chat(prompt_of(t), e)
                except Exception as ex:  # noqa: BLE001
                    print(f"task {t['id']} {e}: {ex!r:.200}; not recorded", flush=True)
                    continue
                r.update(id=t["id"], effort=e)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                print(f"task {t['id']:3d} {e:6s} {r.get('seconds')} s  out {len(r.get('text', ''))} chars  "
                      f"gen {(r.get('usage') or {}).get('completion_tokens')}", flush=True)


JUDGE = """You are grading the page-extraction step of a research agent. The step receives a web page, the overall
research question and the specific focus for this page, and must return only verbatim quotes from the page that
help answer the focus or the question (or exactly "NOT RELEVANT" if nothing on the page helps).

Overall research question: {query}
Focus for this page: {focus}

<page>
{page}
</page>

Three extraction outputs, in random order:

<output_A>
{A}
</output_A>

<output_B>
{B}
</output_B>

<output_C>
{C}
</output_C>

Rank the outputs from most to least useful to the research agent. Judge: (1) coverage — does it keep every passage
of the page that bears on the focus or the question (exact figures, dates, names)? (2) faithfulness — are the quotes
really in the page, unaltered? (3) precision — little irrelevant material. A correct "NOT RELEVANT" beats quotes that
do not help; a wrong "NOT RELEVANT" is the worst outcome.
Reply with JSON only: {{"ranking": ["A","B","C"], "missing": {{"A": "...", "B": "...", "C": "..."}}, "reason": "..."}}
where "missing" names the most important relevant fact each output left out (or "")."""


def cmd_judge(a):
    out = Path(a.out_dir)
    tasks = {t["id"]: t for t in load(out / "tasks.jsonl")}
    outs = {}
    for r in load(out / "outputs.jsonl"):
        outs.setdefault(r["id"], {})[r["effort"]] = r
    done = {r["id"] for r in load(out / "judge.jsonl")}
    sys.path.insert(0, str(WS / ".venv/lib/python3.12/site-packages"))
    import os
    os.environ.setdefault("LDR_DEEP_TOKENIZER_DIR", str(WS / "deep/tokenizer"))
    from local_deep_research.deep.tokens import truncate_to_tokens
    random.seed(99)
    with open(out / "judge.jsonl", "a", encoding="utf-8") as f:
        for i, t in tasks.items():
            if i in done or len(outs.get(i, {})) < 3 or any("error" in outs[i][e] for e in EFFORTS):
                continue
            labels = EFFORTS[:]
            random.shuffle(labels)                        # labels[0] -> A, ...
            page = truncate_to_tokens(t["page_text"], 60000)
            p = JUDGE.format(query=t["query"], focus=t["focus"], page=page,
                             A=outs[i][labels[0]]["text"], B=outs[i][labels[1]]["text"], C=outs[i][labels[2]]["text"])
            try:
                r = chat(p, "xhigh")
                m = re.search(r"\{.*\}", r["text"], re.S)
                d = json.loads(m.group(0)) if m else {}
            except Exception as ex:  # noqa: BLE001
                r, d = {"error": repr(ex)[:200]}, {}
            rank = [labels["ABC".index(x)] for x in d.get("ranking", []) if x in "ABC" and len(x) == 1]
            missing = {labels["ABC".index(k)]: v for k, v in (d.get("missing") or {}).items() if k in ("A", "B", "C")}
            rec = {"id": i, "labels": labels, "ranking": rank, "missing": missing, "reason": d.get("reason"),
                   "seconds": r.get("seconds"), "raw": r.get("text", "")[:3000] if not rank else None}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"task {i:3d} ranking {rank}", flush=True)


def norm(s):
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"\[\d+\]|\[citation needed\]|\[[a-z]\]", "", s)          # reference markers
    s = re.sub(r"[*_`#>|]", "", s)                                            # markdown emphasis / tables
    s = s.replace("…", " ").replace("...", " ")
    s = re.sub(r"^[\s\"'\-•]+|[\s\"']+$", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


SENT = re.compile(r"(?<=[.!?;:])\s+(?=[A-Z0-9(\"'])")


def verbatim(text, page):
    """Share of the output's sentences (and characters) that occur word for word in the page, after removing
    reference markers, markdown and ellipses on both sides (quotes may drop "[17]" or join sentences)."""
    pg = norm(page)
    sents = [x for l in (text or "").splitlines() for x in SENT.split(l) if len(norm(x)) >= 12]
    if not sents:
        return None, None
    ok = ok_chars = tot = 0
    for x in sents:
        n = norm(x)
        tot += len(n)
        parts = [norm(p) for p in re.split(r"\s*(?:\.\.\.|…|\[\.\.\.\])\s*", x) if len(norm(p)) >= 8] or [n]
        if all(p in pg for p in parts):
            ok += 1
            ok_chars += len(n)
    return ok / len(sents), ok_chars / max(1, tot)


def cmd_report(a):
    out = Path(a.out_dir)
    tasks = {t["id"]: t for t in load(out / "tasks.jsonl")}
    outs = {}
    for r in load(out / "outputs.jsonl"):
        outs.setdefault(r["id"], {})[r["effort"]] = r
    judge = {r["id"]: r for r in load(out / "judge.jsonl")}
    per = {e: {"n": 0, "not_relevant": 0, "verbatim_lines": [], "verbatim_chars": [], "chars": [], "seconds": [],
               "gen_tokens": [], "rank": [], "first": 0, "errors": 0, "length_finish": 0} for e in EFFORTS}
    pair = {(x, y): [0, 0] for x in EFFORTS for y in EFFORTS if x < y}
    for i, o in outs.items():
        t = tasks.get(i)
        if not t:
            continue
        for e, r in o.items():
            d = per[e]
            if "error" in r:
                d["errors"] += 1
                continue
            d["n"] += 1
            txt = r["text"]
            if txt.strip().upper().startswith("NOT RELEVANT"):
                d["not_relevant"] += 1
            else:
                vl, vc = verbatim(txt, t["page_text"])
                if vl is not None:
                    d["verbatim_lines"].append(vl)
                    d["verbatim_chars"].append(vc)
            d["chars"].append(len(txt))
            d["seconds"].append(r["seconds"])
            d["gen_tokens"].append((r.get("usage") or {}).get("completion_tokens") or 0)
            d["length_finish"] += r.get("finish") == "length"
        j = judge.get(i)
        if j and len(j["ranking"]) == 3:
            for pos, e in enumerate(j["ranking"]):
                per[e]["rank"].append(pos + 1)
            per[j["ranking"][0]]["first"] += 1
            for (x, y), w in pair.items():
                if j["ranking"].index(x) < j["ranking"].index(y):
                    w[0] += 1
                else:
                    w[1] += 1

    def mean(v):
        return round(sum(v) / len(v), 3) if v else None

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else None

    summ = {e: {"tasks": d["n"], "errors": d["errors"], "not_relevant": d["not_relevant"],
                "verbatim_line_rate": mean(d["verbatim_lines"]), "verbatim_char_rate": mean(d["verbatim_chars"]),
                "mean_rank": mean(d["rank"]), "ranked_first": d["first"], "judged": len(d["rank"]),
                "median_output_chars": med(d["chars"]), "median_seconds": med(d["seconds"]),
                "total_seconds": round(sum(d["seconds"]), 1), "median_generated_tokens": med(d["gen_tokens"]),
                "hit_length_limit": d["length_finish"]} for e, d in per.items()}
    # NOT RELEVANT disagreements
    disagree = [i for i, o in outs.items() if len(o) == 3 and
                len({o[e]["text"].strip().upper().startswith("NOT RELEVANT") for e in EFFORTS if "text" in o[e]}) > 1]
    res = {"per_effort": summ, "pairwise_wins": {f"{x} vs {y}": w for (x, y), w in pair.items()},
           "not_relevant_disagreements": disagree, "tasks": len(tasks),
           "long_pages": sum(1 for t in tasks.values() if len(t["page_text"]) > 12000)}
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    lines = ["| effort | tasks | verbatim lines | verbatim chars | judge mean rank (1 best) | ranked first | "
             "NOT RELEVANT | median output chars | median s | total s | median generated tokens |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in EFFORTS:
        s = summ[e]
        lines.append(f"| {e} | {s['tasks']} | {s['verbatim_line_rate']} | {s['verbatim_char_rate']} | {s['mean_rank']} "
                     f"| {s['ranked_first']}/{s['judged']} | {s['not_relevant']} | {s['median_output_chars']} | "
                     f"{s['median_seconds']} | {s['total_seconds']} | {s['median_generated_tokens']} |")
    lines.append("")
    lines.append("Pairwise (judge): " + "; ".join(f"{k}: {w[0]}–{w[1]}" for k, w in res["pairwise_wins"].items()))
    lines.append(f"NOT RELEVANT disagreements: {disagree}")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    q = sp.add_parser("collect")
    q.add_argument("out_dir")
    q.add_argument("--n", type=int, default=36)
    for c in ("run", "judge", "report"):
        q = sp.add_parser(c)
        q.add_argument("out_dir")
    a = p.parse_args()
    {"collect": cmd_collect, "run": cmd_run, "judge": cmd_judge, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
