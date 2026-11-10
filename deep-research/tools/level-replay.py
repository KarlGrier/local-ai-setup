#!/usr/bin/env python3
"""level-replay.py - phase 3 thinking-level tests by replay (2026-10-17): the same inputs, only the reasoning effort
changes. Daytime runs (09:00-22:30), through strata-proxy (8090: the gate, the call log), holding run/bench.lock.

  extract RUNS_GLOB [--n 30] [--levels low,medium,xhigh] [--seed 1]
        sample N page-extraction calls captured in measurement runs (results/bench2/runs/*/<id>/capture/calls.jsonl,
        class "extract") and send each again at every level -> results/bench2/replays/extract/outputs.jsonl, plus
        blinded judging packets (A/B/C in random order; the key in a separate file)
  report RUN_DIR [--levels medium,xhigh]
        rebuild the evidence store of a finished deep run (RUN_DIR/deep/evidence.jsonl) and write the report (outline,
        sections, opening; no citation check) at each level -> results/bench2/replays/report/<run>/report-<level>.md
  verify RUN_DIR [--levels medium,xhigh] [--max-claims 40]
        run the citation check on the run's own unverified report at each level ->
        results/bench2/replays/verify/<run>/verify-<level>.json (verdict per claim, same claims for every level)

Phase 4 stage 1 (2026-10-20; item 1 = the user's setup profile + setup-claim check, user-setup.md):
  lead RUN_DIR --id N [--setup FILE] [--n 3] [--label L] [--effort medium]
        send one captured lead-agent call (capture/calls.jsonl; e.g. o07's wrap-up answer) again N times, the
        <user_setup> block appended to its system prompt with --setup -> results/bench2/replays/lead/<run>/
  report RUN_DIR ... [--setup FILE] [--lead FILE] [--n 1] [--label L]
        as above; --setup adds the <user_setup> block to the outline, section and opening prompts; --lead replaces
        the run's lead answer (a `lead` replay's output); --n repeats -> report-<level>[-<label>-<k>].md
  setupcheck REPORT.md [...] --setup FILE [--n 3] [--effort xhigh] [--out DIR]
        the setup-claim check: every statement about the user's machine in the report, judged against the setup
        facts (contradicts / consistent / unsupported, with a fix for contradictions) -> <report>.setupcheck-<k>.json
Item 3 (critic / verifier with two sources per claim):
  critic RUN_DIR REPORT.md [--n 3] [--effort xhigh] [--label L]
        a fresh-context review of a finished report against its task: reasoning errors, unsupported or
        single-source key claims, contradictions, stale statuses, gaps; each with a fix or a search query ->
        results/bench2/replays/critic/<run>/<label>-<k>.json
  verify2 RUN_DIR REPORT.md [--n 3] [--max-claims 40] [--label L]
        the key claims checked against their cited sources AND the other stored sources that share the most words
        with them (up to 4): which sources support / contradict each, independent sites counted (distinct domains)
        -> results/bench2/replays/verify2/<run>/<label>-<k>.json
"""
from __future__ import annotations

import argparse
import fcntl
import glob
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
OUT = WS / "results" / "bench2" / "replays"
PROXY = "http://127.0.0.1:8090"


def daytime_or_exit() -> None:
    if (WS / "run" / "night-ok").exists():   # 2026-10-20: the user allows long runs at night for good (bench2.py's rule)
        return
    now = datetime.now()
    if not (9 <= now.hour and (now.hour, now.minute) < (22, 30)):
        raise SystemExit("level-replay: daytime only (09:00-22:30)")


def bench_lock():
    f = open(WS / "run" / "bench.lock", "w")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


# -- extraction ----------------------------------------------------------------------------------------------------------
def stream_call(messages: list, effort: str, max_tokens: int = 30000) -> dict:
    import requests

    body = {"model": "strata", "messages": messages, "stream": True, "temperature": 1.0, "max_tokens": max_tokens,
            "reasoning_effort": effort, "stream_options": {"include_usage": True}}
    t0 = time.time()
    text, usage, finish = [], None, None
    with requests.post(PROXY + "/v1/chat/completions", json=body, stream=True, timeout=3600,
                       proxies={"http": None, "https": None}) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: ") or line == b"data: [DONE]":
                continue
            d = json.loads(line[6:])
            if d.get("error"):
                raise RuntimeError(str(d["error"])[:300])
            usage = d.get("usage") or usage
            for ch in d.get("choices") or []:
                text.append((ch.get("delta") or {}).get("content") or "")
                finish = ch.get("finish_reason") or finish
    return {"text": "".join(text).strip(), "usage": usage, "finish": finish, "seconds": round(time.time() - t0, 1)}


def cmd_extract(a) -> None:
    daytime_or_exit()
    pool = []
    for f in sorted(glob.glob(a.runs_glob)):
        for line in open(f, encoding="utf-8"):
            try:
                c = json.loads(line)
            except ValueError:
                continue
            if c.get("cls") == "extract" and c.get("status") == 200 and c.get("messages"):
                pool.append({"src": f, "id": c["id"], "messages": c["messages"], "orig_effort": c.get("reasoning_effort")})
    rng = random.Random(a.seed)
    rng.shuffle(pool)
    tasks = pool[:a.n]
    out = OUT / "extract"
    out.mkdir(parents=True, exist_ok=True)
    levels = a.levels.split(",")
    done = {(r["task"], r["effort"]) for r in map(json.loads, open(out / "outputs.jsonl"))} if (out / "outputs.jsonl").exists() else set()
    lock = bench_lock()
    with open(out / "tasks.jsonl", "w") as tf:
        for i, t in enumerate(tasks):
            tf.write(json.dumps({"task": i, **t}, ensure_ascii=False) + "\n")
    for i, t in enumerate(tasks):
        order = levels[:]
        rng.shuffle(order)
        for eff in order:
            if (i, eff) in done:
                continue
            daytime_or_exit()
            r = stream_call(t["messages"], eff)
            with open(out / "outputs.jsonl", "a") as f:
                f.write(json.dumps({"task": i, "effort": eff, **r}, ensure_ascii=False) + "\n")
            print(f"task {i} {eff}: {r['seconds']} s, {len(r['text'])} chars, finish {r['finish']}", flush=True)
    lock.close()
    make_packets(out, levels, rng)


def make_packets(out: Path, levels: list[str], rng) -> None:
    tasks = {t["task"]: t for t in map(json.loads, open(out / "tasks.jsonl"))}
    outs: dict = {}
    for r in map(json.loads, open(out / "outputs.jsonl")):
        outs.setdefault(r["task"], {})[r["effort"]] = r
    key, packets = {}, []
    labels = "ABC"[:len(levels)]
    for i, t in tasks.items():
        if set(outs.get(i, {})) != set(levels):
            continue
        order = levels[:]
        rng.shuffle(order)
        key[str(i)] = dict(zip(labels, order))
        user = next((m.get("content") for m in t["messages"] if m.get("role") == "user"), "")
        user = user if isinstance(user, str) else json.dumps(user)
        focus = re.search(r"(?s)FOCUS[^:]*:\s*(.{0,400})", user)
        packets.append({"id": str(i), "focus": focus.group(1) if focus else user[:400], "prompt_chars": len(user),
                        "page": user, "outputs": {lab: {"text": outs[i][eff]["text"]} for lab, eff in zip(labels, order)}})
    json.dump(key, open(out / "KEY-do-not-open-before-ranking.json", "w"))
    with open(out / "packets.jsonl", "w") as f:
        for p in packets:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"{len(packets)} blinded packets in {out / 'packets.jsonl'}")


# -- report / verify -----------------------------------------------------------------------------------------------------
def deep_modules(effort_env: dict):
    os.environ.update({"LDR_DEEP": "1", "LDR_DEEP_TOKENIZER_DIR": str(WS / "deep" / "tokenizer"), **effort_env})
    from local_deep_research.deep import report, seed
    from local_deep_research.deep.evidence import EvidenceStore
    return report, seed, EvidenceStore


def model():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model="strata", base_url=PROXY + "/v1", api_key="none", temperature=1.0, max_tokens=30000,
                      streaming=True, timeout=1800, max_retries=1)


def load_run(run_dir: Path, seed_mod, store_cls):
    ev = run_dir / "deep"
    query = json.loads((run_dir / "marks.json").read_text()).get("question", "") if (run_dir / "marks.json").exists() else ""
    sd = seed_mod.load([str(ev)])
    store = store_cls(query, None)
    seed_mod.fill_store(sd, store)
    lead = (ev / "lead_answer.md").read_text() if (ev / "lead_answer.md").exists() else ""
    return query, store, lead


def cmd_report(a) -> None:
    daytime_or_exit()
    run = Path(a.run_dir)
    lock = bench_lock()
    for eff in a.levels.split(","):
        for k in range(1, a.n + 1):
            tag = eff if a.n == 1 and not a.label else f"{eff}-{a.label or 'x'}-{k}"
            # one process per report: the deep config is read from the environment at import
            if os.fork() == 0:
                report, seed_mod, store_cls = deep_modules({"LDR_DEEP_REPORT_EFFORT": eff, "LDR_DEEP_VERIFY": "0"})
                query, store, lead = load_run(run, seed_mod, store_cls)
                if a.lead:
                    lead = Path(a.lead).read_text(encoding="utf-8")
                if a.setup:
                    add_setup_to_report_prompts(report, a.setup)
                w = report.ReportWriter(query, store, model(), lead)
                res = w.run()
                out = OUT / "report" / run.name
                out.mkdir(parents=True, exist_ok=True)
                (out / f"report-{tag}.md").write_text(res["markdown"])
                (out / f"calls-{tag}.json").write_text(json.dumps({"calls": res["calls"], "stats": res["stats"],
                                                                   "setup": a.setup, "lead": a.lead}, indent=1))
                print(f"report {tag}: {res['stats'].get('report_seconds')} s, {len(res['markdown'])} chars", flush=True)
                os._exit(0)
            os.wait()
    lock.close()


# -- phase 4 item 1: the user's setup (2026-10-20) ------------------------------------------------------------------------
SETUP_INTRO = ("The user's own computer and setup, as the user gave them (facts, not search results). Where the task "
               "concerns the user's machine, judge what fits, runs or helps on it from these facts. Do not contradict "
               "them, do not restate them differently, and do not assume another model or size of a component.")


def setup_facts(path: str) -> str:
    """The facts of user-setup.md: from its first bullet on (the header and intro are for people)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[next(i for i, ln in enumerate(lines) if ln.startswith("- ")):]).strip()


def setup_block(path: str) -> str:
    return "<user_setup>\n" + SETUP_INTRO + "\n" + setup_facts(path) + "\n</user_setup>"


def add_setup_to_report_prompts(report_mod, path: str) -> None:
    """The report writer's outline, section and opening prompts with the setup block right after the task (what a
    deep/prompts.py change would do; the replay patches the imported names only, in its own process)."""
    block = setup_block(path).replace("{", "{{").replace("}", "}}")
    note = ("Statements about the user's own machine must agree with <user_setup>; where the evidence was gathered "
            "for another machine (another card, slot or memory size), say so instead of carrying it over.")
    for name in ("OUTLINE_PROMPT", "SECTION_PROMPT", "OPENING_PROMPT"):
        p = getattr(report_mod, name)
        assert "</task>" in p, name
        setattr(report_mod, name, p.replace("</task>", "</task>\n\n" + block + "\n" + note, 1))


def cmd_lead(a) -> None:
    daytime_or_exit()
    run = Path(a.run_dir)
    c = next(c for c in map(json.loads, open(run / "capture" / "calls.jsonl", encoding="utf-8")) if c["id"] == a.id)
    msgs = [dict(m) for m in c["messages"]]
    if a.setup:
        assert msgs[0]["role"] == "system"
        msgs[0]["content"] += "\n\n" + setup_block(a.setup)
    out = OUT / "lead" / run.name
    out.mkdir(parents=True, exist_ok=True)
    lock = bench_lock()
    for k in range(1, a.n + 1):
        daytime_or_exit()
        r = stream_call(msgs, a.effort)
        (out / f"call{a.id}-{a.label}-{k}.md").write_text(r["text"], encoding="utf-8")
        with open(out / "outputs.jsonl", "a") as f:
            f.write(json.dumps({"id": a.id, "label": a.label, "k": k, "setup": a.setup, "effort": a.effort,
                                **{x: r[x] for x in ("usage", "finish", "seconds")}, "chars": len(r["text"])}) + "\n")
        print(f"lead {a.id} {a.label} {k}: {r['seconds']} s, {len(r['text'])} chars, finish {r['finish']}", flush=True)
    lock.close()


SETUPCHECK_PROMPT = """You are the claim-verification step of a research system. Below are the facts of the user's \
own computer, as the user gave them, and a research report written for this user. Find every statement in the report \
about the user's own machine or setup: its components and which model or size each is, memory sizes, slots and PCIe \
links, bandwidths, and what fits, runs or helps on it (including limits and budgets the report derives from them). \
Judge each one against the facts:
- "contradicts": it conflicts with the facts, or with what follows directly from them (for example, a card in a slot \
that runs at x4 gets x4 at most, whatever the card supports). Give the corrected statement.
- "consistent": the facts support it.
- "unsupported": the facts neither confirm nor contradict it. That is not an error.
General statements about other machines are not about the user's setup; leave them out.

<user_setup>
{setup}
</user_setup>

<report>
{report}
</report>

Reply with JSON only: {{"claims": [{{"quote": "<the statement, copied exactly from the report>", "verdict": \
"contradicts|consistent|unsupported", "why": "<one sentence>", "fix": "<the corrected statement, or empty>"}}]}}"""

# 10-21 (the user: "an output that can't be truncated"): when the full list hits the token cap (or gives no JSON), the
# same check runs again listing only the statements that contradict the facts or that the facts do not support.
SETUPCHECK_FLAGGED_PROMPT = SETUPCHECK_PROMPT.replace(
    "General statements about other machines are not about the user's setup; leave them out.",
    "General statements about other machines are not about the user's setup; leave them out. List ONLY the statements "
    "whose verdict is \"contradicts\" or \"unsupported\"; leave every consistent one out, so the list stays short.")
assert SETUPCHECK_FLAGGED_PROMPT != SETUPCHECK_PROMPT


def cmd_setupcheck(a) -> None:
    daytime_or_exit()
    setup = setup_facts(a.setup)
    lock = bench_lock()
    for rp in a.reports:
        body = Path(rp).read_text(encoding="utf-8")
        body = re.split(r"(?m)^#{1,3} (Citation check|Sources|References)\s*$", body)[0]   # the report alone
        out = Path(a.out) if a.out else Path(rp).parent
        out.mkdir(parents=True, exist_ok=True)
        for k in range(1, a.n + 1):
            daytime_or_exit()
            def check(prompt):
                r = stream_call([{"role": "user", "content": prompt.format(setup=setup, report=body)}], a.effort,
                                max_tokens=a.max_tokens)
                m = re.search(r"(?s)\{.*\}", r["text"])
                try:
                    claims = json.loads(m.group(0))["claims"] if m else None
                except (ValueError, KeyError):
                    claims = None
                return r, claims
            r, claims = check(SETUPCHECK_PROMPT)
            mode, first = "full", None
            if r["finish"] == "length" or claims is None:
                first = {"finish": r["finish"], "seconds": r["seconds"], "usage": r["usage"], "claims_parsed": claims is not None}
                print(f"setupcheck {Path(rp).parent.name}/{Path(rp).name} {k}: full list {r['finish']}"
                      f"{'' if claims is not None else ', no JSON'} - again, flagged statements only", flush=True)
                r, claims = check(SETUPCHECK_FLAGGED_PROMPT)
                mode = "flagged-only"
            res = {"report": rp, "k": k, "effort": a.effort, "mode": mode, "first_attempt": first, "seconds": r["seconds"],
                   "finish": r["finish"], "usage": r["usage"], "claims": claims, "raw": None if claims is not None else r["text"]}
            # stage 1 (10-21): saved reports are all report.md, so the run folder goes in the name (o01-report...)
            dst = out / f"{Path(rp).parent.name}-{Path(rp).stem}.setupcheck-{k}.json"
            dst.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
            bad = [c for c in (claims or []) if c.get("verdict") == "contradicts"]
            print(f"setupcheck {Path(rp).parent.name}/{Path(rp).name} {k} ({mode}): {r['seconds']} s, finish {r['finish']}, "
                  f"{len(claims or [])} claims, {len(bad)} contradict{'' if claims is not None else ' (NO JSON)'}", flush=True)
    lock.close()


# -- phase 4 item 3: critic and two-source verifier (2026-10-20) -----------------------------------------------------------
CRITIC_PROMPT = """You are the claim-verification step of a research system. Below are a research task and the final \
report written for it. Review the report as a critical expert reading it for the first time, for the person who \
asked. List the problems that matter:
- "reasoning": a conclusion that does not follow, a wrong calculation or comparison, a figure applied to the wrong \
item (another product's or model's specification), something technically impossible;
- "unsupported": a key claim with no citation, cited to something that is not a source, or resting on a single source \
where it matters;
- "contradiction": two statements of the report that disagree, or sources it reports as disagreeing without settling it;
- "stale": a status claim ("not yet", "pending", "expected", "the latest") that may have changed since its sources;
- "gap": a part of the task the report does not answer.
For each give the exact quote (for a gap: the part of the task), why it is a problem, and the action: "fix" with the \
corrected text where the report's own content is enough, or "research" with one web search query that would settle it.
At most 20, the most important first. Do not list matters of style.

<task>
{task}
</task>

<report>
{report}
</report>

Reply with JSON only: {{"issues": [{{"type": "reasoning|unsupported|contradiction|stale|gap", "quote": "...", "why": \
"...", "action": "fix|research", "fix": "<corrected text or empty>", "query": "<search query or empty>"}}]}}"""

VERIFY2_PROMPT = """You are the claim-verification step of a research system. Below are sentences from a research \
report, each followed by passages of several sources the research read: the ones the sentence cites and others that \
may bear on it. For each claim, say which sources state it, which contradict it, and which say nothing about it. Judge \
from the passages only, not from your own knowledge. A source supports a claim when it states the claim's facts \
(paraphrase is fine; figures, dates and names must match); it contradicts it when it states different facts.

{items}

For each claim output one line of JSON (JSON Lines, nothing else):
{{"claim": <number>, "supporting": [<source indices>], "contradicting": [<source indices>], "note": "<for a \
contradiction: what differs, at most 25 words>"}}"""


def report_body(path: str) -> str:
    body = Path(path).read_text(encoding="utf-8")
    return re.split(r"(?m)^#{1,3} (Citation check|Sources|References)\s*$", body)[0]


def cmd_critic(a) -> None:
    daytime_or_exit()
    run = Path(a.run_dir)
    task = json.loads((run / "marks.json").read_text()).get("question", "")
    body = report_body(a.report)
    out = OUT / "critic" / run.name
    out.mkdir(parents=True, exist_ok=True)
    lock = bench_lock()
    for k in range(1, a.n + 1):
        daytime_or_exit()
        r = stream_call([{"role": "user", "content": CRITIC_PROMPT.format(task=task, report=body)}], a.effort)
        m = re.search(r"(?s)\{.*\}", r["text"])
        try:
            issues = json.loads(m.group(0))["issues"] if m else None
        except (ValueError, KeyError):
            issues = None
        (out / f"{a.label}-{k}.json").write_text(json.dumps({
            "report": a.report, "k": k, "effort": a.effort, "seconds": r["seconds"], "finish": r["finish"],
            "usage": r["usage"], "issues": issues, "raw": None if issues is not None else r["text"]},
            indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"critic {run.name} {a.label} {k}: {r['seconds']} s, {len(issues or [])} issues"
              f"{'' if issues is not None else ' (NO JSON)'}", flush=True)
    lock.close()


def domain(url: str) -> str:
    from urllib.parse import urlparse

    d = urlparse(url or "").netloc.lower()
    return d[4:] if d.startswith("www.") else d


def cmd_verify2(a) -> None:
    daytime_or_exit()
    run = Path(a.run_dir)
    lock = bench_lock()
    for k in range(1, a.n + 1):
        if os.fork() == 0:
            report, seed_mod, store_cls = deep_modules({"LDR_DEEP_VERIFY_EFFORT": a.effort})
            query, store, lead = load_run(run, seed_mod, store_cls)
            w = report.ReportWriter(query, store, model(), lead)
            claims = w.select_key_claims(w.split_claims(report_body(a.report)), a.max_claims)
            srcs = store.all_sources()
            stext = {s.idx: (s.page_text or "\n".join(s.snippets[:3] + [f.extraction for f in s.fetches if f.extraction]))
                     for s in srcs}
            swords = {i: report._words(t[:200000]) for i, t in stext.items()}
            items = []
            for c in claims:
                plain = re.sub(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]", "", c["text"])
                cw = report._words(plain)
                others = sorted((i for i in swords if i not in c["sources"]), key=lambda i: -len(swords[i] & cw))
                others = [i for i in others[:a.others] if len(swords[i] & cw) >= 3]
                blocks = []
                for i in list(c["sources"]) + others:
                    s = store.source(i)
                    if s is None:
                        continue
                    tag = "cited" if i in c["sources"] else "not cited"
                    blocks.append(f"Source [{i}] ({tag}) {s.title[:100]} - {domain(s.url)}:\n"
                                  f"{report.relevant_passages(stext[i], cw, 900)}")
                items.append({"claim": c, "plain": plain, "others": others, "body": "\n\n".join(blocks)})
            batches, cur, tok = [], [], 0
            for it in items:
                n = report.count_text(it["body"]) + 60
                if cur and (len(cur) >= 6 or tok + n > 36000):
                    batches.append(cur)
                    cur, tok = [], 0
                cur.append(it)
                tok += n
            if cur:
                batches.append(cur)
            t0 = time.time()
            for b in batches:
                listing = "\n\n".join(f"### Claim {j + 1}\n{it['plain']}\nCited: {it['claim']['sources']}\n{it['body']}"
                                      for j, it in enumerate(b))
                outp = w._llm("verify", VERIFY2_PROMPT.format(items=listing))
                got = {}
                for line in outp.splitlines():
                    line = line.strip().strip(",")
                    if line.startswith("{"):
                        try:
                            d = json.loads(line)
                            got[int(d.get("claim"))] = d
                        except (ValueError, TypeError):
                            continue
                for j, it in enumerate(b):
                    d = got.get(j + 1) or {}
                    sup = [x for x in (d.get("supporting") or []) if isinstance(x, int)]
                    con = [x for x in (d.get("contradicting") or []) if isinstance(x, int)]
                    it["result"] = {"supporting": sup, "contradicting": con, "note": str(d.get("note", ""))[:300],
                                    "independent_support": len({domain(store.source(x).url) for x in sup
                                                                if store.source(x) is not None}),
                                    "answered": bool(d)}
            res = [{"text": it["claim"]["text"], "section": it["claim"].get("section"), "cited": it["claim"]["sources"],
                    "others": it["others"], **it.get("result", {})} for it in items]
            out = OUT / "verify2" / run.name
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{a.label}-{k}.json").write_text(json.dumps({"report": a.report, "k": k, "effort": a.effort,
                                                                 "seconds": round(time.time() - t0, 1), "claims": res},
                                                                indent=1, ensure_ascii=False), encoding="utf-8")
            one = sum(1 for r in res if r.get("independent_support") == 1)
            none = sum(1 for r in res if r.get("answered") and not r.get("supporting"))
            con = sum(1 for r in res if r.get("contradicting"))
            print(f"verify2 {run.name} {a.label} {k}: {len(res)} claims, {one} on one site, {none} unsupported, "
                  f"{con} contradicted, {time.time() - t0:.0f} s", flush=True)
            os._exit(0)
        os.wait()
    lock.close()


def cmd_verify(a) -> None:
    daytime_or_exit()
    run = Path(a.run_dir)
    body = (run / "deep" / "report-unverified.md").read_text()
    lock = bench_lock()
    for eff in a.levels.split(","):
        if os.fork() == 0:
            report, seed_mod, store_cls = deep_modules({"LDR_DEEP_VERIFY_EFFORT": eff,
                                                        "LDR_DEEP_VERIFY_MAX_CLAIMS": str(a.max_claims)})
            query, store, lead = load_run(run, seed_mod, store_cls)
            w = report.ReportWriter(query, store, model(), lead)
            claims = w.select_key_claims(w.split_claims(body), a.max_claims)
            t0 = time.time()
            checked = w.verify(body, claims=claims)
            out = OUT / "verify" / run.name
            out.mkdir(parents=True, exist_ok=True)
            (out / f"verify-{eff}.json").write_text(json.dumps({"seconds": round(time.time() - t0, 1),
                                                               "calls": w.calls, "claims": checked}, indent=1,
                                                              ensure_ascii=False))
            print(f"verify {eff}: {len(checked)} claims, {time.time() - t0:.0f} s", flush=True)
            os._exit(0)
        os.wait()
    lock.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    q = sp.add_parser("extract")
    q.add_argument("runs_glob", help='e.g. "results/bench2/runs/screen-*/*/capture/calls.jsonl"')
    q.add_argument("--n", type=int, default=30)
    q.add_argument("--levels", default="low,medium,xhigh")
    q.add_argument("--seed", type=int, default=1)
    for name in ("report", "verify"):
        q = sp.add_parser(name)
        q.add_argument("run_dir")
        q.add_argument("--levels", default="medium,xhigh")
        if name == "verify":
            q.add_argument("--max-claims", type=int, default=40)
        else:
            q.add_argument("--setup", help="user-setup.md: the <user_setup> block in the report prompts")
            q.add_argument("--lead", help="a replayed lead answer to write from instead of the run's own")
            q.add_argument("--n", type=int, default=1)
            q.add_argument("--label", default="")
    q = sp.add_parser("lead")
    q.add_argument("run_dir")
    q.add_argument("--id", type=int, required=True, help="the captured call's id")
    q.add_argument("--setup")
    q.add_argument("--n", type=int, default=3)
    q.add_argument("--label", default="x")
    q.add_argument("--effort", default="medium")
    q = sp.add_parser("setupcheck")
    q.add_argument("reports", nargs="+")
    q.add_argument("--setup", required=True)
    q.add_argument("--n", type=int, default=3)
    q.add_argument("--effort", default="xhigh")
    q.add_argument("--max-tokens", type=int, default=60000,
                   help="output cap (stage 1, 10-21: 9 of 18 runs hit 30,000 and saved no claims)")
    q.add_argument("--out")
    for name in ("critic", "verify2"):
        q = sp.add_parser(name)
        q.add_argument("run_dir")
        q.add_argument("report")
        q.add_argument("--n", type=int, default=3)
        q.add_argument("--effort", default="xhigh")
        q.add_argument("--label", default="x")
        if name == "verify2":
            q.add_argument("--max-claims", type=int, default=40)
            q.add_argument("--others", type=int, default=4, help="uncited sources offered per claim")
    a = ap.parse_args()
    {"extract": cmd_extract, "report": cmd_report, "verify": cmd_verify, "lead": cmd_lead,
     "setupcheck": cmd_setupcheck, "critic": cmd_critic, "verify2": cmd_verify2}[a.cmd](a)


if __name__ == "__main__":
    main()
