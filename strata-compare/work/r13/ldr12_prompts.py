#!/usr/bin/env python3
"""ldr12_prompts.py — round 13 (Phase A, before any build / served A/B): Round 12's NEW LDR-shaped holdout from its own
frozen corpus (work/r13/ldr12/corpus/H), the same 12-request plan as Round 10's screen and holdout;
prompts/r13/ldr-holdout12.json is read-only and unseen until Phase C. Copy of round 10's ldr_prompts.py (LDR-shaped request sets from the frozen corpus).

Shape (Round 8's uptime log of C*7 on 8080: 529 of your requests, mostly Local Deep Research): prompts from < 1K to
> 32K tokens, median ~4K; 94 % of the time in decode; 70 % of the decode time in answers of 8K+ tokens on 16K+ prompts;
15 % of requests reuse a cached prefix.  My own prompts in that shape, in the way a deep-research tool talks to the model
(none of LDR's text, data or settings is read):
  queries    research question -> 4 search queries                 (~200 tokens, cap 2048)
  triage     search results (title / URL / snippet) -> JSON          (~2.5K, cap 2048)
  toolcall   an OpenAI tools request: the assistant searched, the tool answered, the model picks the next call (~3K, cap 2048)
  analysis   full source texts -> findings with [n] citations        (5K / 9K / 14K, cap 4096)
  synthesis  full source texts -> a research report with citations   (20K / 28K / 36K, cap 8192)
  followup   the same system + sources prefix as a synthesis, another instruction (reuses the cached prefix, cap 4096)

Sets: S = the LDR-shaped screen (6 topics, 12 requests), H = its holdout (6 other topics, same plan; frozen now, run only
in Phase E), T = the aging / routing-trace pool (30 other topics, 60 requests).  Output: prompts/r10/ldr-{screen,holdout,
pool}.json + prompts/r10/MANIFEST.sha256."""
import hashlib
import json
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "scripts"))
from common import load_tokenizer  # noqa: E402

TOK = load_tokenizer()
NT = lambda s: len(TOK.encode(s))  # noqa: E731
CORPUS = WS / "work/r13/ldr12/corpus"
OUT = WS / "prompts/r12"
DATE = "2026-10-05"
SYSTEM = ("You are a careful research assistant. You answer from the sources you are given, cite them by their number "
          "in square brackets, say when sources disagree or are weak, and never invent a source.")

TOOLS = [
    {"type": "function", "function": {
        "name": "web_search", "description": f"Search the web. Today is {DATE}. Returns titles, URLs and snippets.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "the search query"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "fetch_page", "description": "Fetch a web page found by web_search and return its text.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
]


def load(st, tid):
    return json.loads((CORPUS / st / f"{tid}.json").read_text(encoding="utf-8"))


def sources(d, budget_tokens, skip=0):
    """Numbered full-text sources, in search rank order, until `budget_tokens` (each source capped so that at least
    four fit)."""
    pages = [p for p in d["pages"] if p.get("text") and len(p["text"]) > 1500][skip:]
    per = max(900, budget_tokens // max(4, min(len(pages), 10)))
    out, used = [], 0
    for i, p in enumerate(pages, 1):
        text = p["text"]
        while NT(text) > per and len(text) > 2000:
            text = text[: int(len(text) * 0.85)]
        block = f"[{i}] {p.get('title') or p['url']}\nURL: {p.get('final') or p['url']}\n\n{text.strip()}\n"
        n = NT(block)
        if used + n > budget_tokens and out:
            break
        out.append(block)
        used += n
    return "\n".join(out), len(out)


def results_list(d, budget_tokens):
    rows, used = [], 0
    for i, r in enumerate([r for r in d["results"] if r.get("url")], 1):
        row = f"[{i}] {r['title']}\n    {r['url']}\n    {r.get('snippet', '')}\n"
        n = NT(row)
        if used + n > budget_tokens:
            break
        rows.append(row)
        used += n
    return "".join(rows)


def req(rid, kind, messages, cap, **kw):
    r = {"id": rid, "kind": kind, "messages": messages, "max_tokens": cap, **kw}
    body = json.dumps(messages, ensure_ascii=False)
    r["approx_prompt_tokens"] = NT(body)
    return r


def make(kind, st, tid, size=None, tag=""):
    d = load(st, tid)
    q = d["question"]
    rid = f"{tid}-{kind}{tag}"
    if kind == "queries":
        u = (f"Today is {DATE}. I am researching this question:\n\n{q}\n\nPropose four distinct web search queries that "
             "together cover the question from different angles (evidence, mechanisms, numbers, criticism). Return a "
             "numbered list with one query per line and nothing else.")
        return req(rid, kind, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": u}], 2048)
    if kind == "triage":
        lst = results_list(d, size or 2400)
        u = (f"Research question: {q}\n\nSearch results:\n\n{lst}\nDecide which results are worth reading in full for "
             "this question. Answer with one JSON object and nothing else: {\"relevant\": [result numbers, best first], "
             "\"skip\": {\"number\": \"short reason\", ...}, \"follow_up_queries\": [two queries for what the results "
             "do not cover]}.")
        return req(rid, kind, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": u}], 2048)
    if kind == "toolcall":
        lst = results_list(d, size or 2600)
        msgs = [{"role": "system", "content": SYSTEM + " Use the tools to find and read sources before answering."},
                {"role": "user", "content": q},
                {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function", "function": {
                    "name": "web_search", "arguments": json.dumps({"query": d["queries"][0]})}}]},
                {"role": "tool", "tool_call_id": "call_1", "content": lst}]
        return req(rid, kind, msgs, 2048, tools=TOOLS)
    src, n = sources(d, size)
    head = f"Research question: {q}\n\nSources ({n}):\n\n{src}\n"
    if kind == "analysis":
        u = head + ("\nExtract the findings in these sources that bear on the research question. Give them as bullet "
                    "points grouped by theme, each with its source numbers, include the numbers the sources report, and "
                    "end with a short list of contradictions or gaps between the sources.")
        return req(rid, kind, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": u}], 4096)
    if kind == "synthesis":
        u = head + ("\nWrite a comprehensive research report that answers the question from these sources: an executive "
                    "summary, sections by theme with citations [n] for every claim, a table of the key quantitative "
                    "results where the sources give numbers, the main disagreements and how strong the evidence is, and "
                    "a conclusion with open questions.")
        return req(rid, kind, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": u}], 8192)
    if kind == "followup":   # the synthesis's exact system + sources prefix, another instruction
        u = head + ("\nList the ten most important quantitative claims in these sources, each with its source number, "
                    "the conditions it was measured under, and whether another source confirms or contradicts it.")
        return req(rid, kind, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": u}], 4096,
                   reuses=f"{tid}-synthesis")
    raise ValueError(kind)


# the per-topic plan of a 12-request screen (S) and its holdout (H)
PLAN = [
    [("queries", None), ("synthesis", 20000)],
    [("queries", None), ("analysis", 9000)],
    [("triage", 2400), ("synthesis", 28000), ("followup", 28000)],
    [("triage", 2400), ("analysis", 5000)],
    [("toolcall", 2600), ("analysis", 14000)],
    [("synthesis", 36000)],
]
# the pool (T): 30 topics, two requests each, cycling through these pairs
POOL_PLAN = [
    [("queries", None), ("synthesis", 24000)],
    [("triage", 2400), ("analysis", 7000)],
    [("toolcall", 2600), ("synthesis", 16000)],
    [("queries", None), ("analysis", 12000)],
    [("triage", 2400), ("synthesis", 32000)],
    [("analysis", 4000), ("followup", 4000)],
]


def build(st):
    from ldr12_corpus import TOPICS
    tids = [t[1] for t in TOPICS if t[0] == st]
    out = []
    plan = PLAN if st in ("S", "H") else POOL_PLAN
    for i, tid in enumerate(tids):
        for kind, size in plan[i % len(plan)]:
            if kind == "followup" and st == "T":   # the pool's followup reuses its own analysis prefix
                r = make("analysis", st, tid, size)
                f = make("followup", st, tid, size)
                f["reuses"] = r["id"]
                out += [r, f]
                continue
            out.append(make(kind, st, tid, size))
    # a pool entry may hold the analysis twice when the plan already had it: keep the first
    seen, uniq = set(), []
    for r in out:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        uniq.append(r)
    return uniq


if __name__ == "__main__":
    sys.path.insert(0, str(WS / "work/r13"))
    OUT.mkdir(parents=True, exist_ok=True)
    reqs = build("H")
    p = OUT / "ldr-holdout12.json"
    if p.exists():
        sys.exit(f"{p} exists: the holdout is frozen")
    p.write_text(json.dumps(reqs, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "MANIFEST.sha256").open("a").write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    toks = sorted(r["approx_prompt_tokens"] for r in reqs)
    print(f"ldr-holdout12: {len(reqs)} requests, prompt tokens min {toks[0]} median {toks[len(toks) // 2]} max {toks[-1]}, "
          f"sum {sum(toks)}; output caps sum {sum(r['max_tokens'] for r in reqs)}")
    for r in reqs:
        print(f"   {r['id']:28s} {r['kind']:9s} ~{r['approx_prompt_tokens']:6d} tok  cap {r['max_tokens']}"
              + (f"  reuses {r['reuses']}" if r.get("reuses") else ""))
