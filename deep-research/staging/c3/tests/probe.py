"""probe.py - run in a child process by test_equivalence.py: import ONE deep package (the installed one or the staged
copy), with the environment the parent gives, and print JSON of every effective size / setting it sees plus traces of
the code paths that use them. No model is called: a fake model answers every call and records what it was sent.

  probe.py --pkg installed|staged [--traces] [--runner FILE] [--scratch DIR]

Staged = staging/c3/deep first on the package's path, the installed deep/ after it (modules that were not changed).
Nothing here writes outside --scratch (bytecode writing is off: run with python -I -B).
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import os
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
WS = Path("/home/USER/ai/deep-research")
SITE = WS / ".venv/lib/python3.12/site-packages"
INSTALLED = SITE / "local_deep_research"
STAGED = WS / "staging/c3"


def sha(x) -> str:
    if not isinstance(x, (str, bytes)):
        x = json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)
    if isinstance(x, str):
        x = x.encode("utf-8", "surrogatepass")
    return hashlib.sha256(x).hexdigest()[:16]


def load(pkg: str):
    import local_deep_research  # noqa: F401  (the installed parent package: light)
    if pkg == "staged":
        spec = importlib.util.spec_from_file_location(
            "local_deep_research.deep", STAGED / "deep/__init__.py",
            submodule_search_locations=[str(STAGED / "deep"), str(INSTALLED / "deep")])
        mod = importlib.util.module_from_spec(spec)
        sys.modules["local_deep_research.deep"] = mod
        spec.loader.exec_module(mod)
        local_deep_research.deep = mod
    import local_deep_research.deep as deep
    return deep


# ------------------------------------------------------------------------------------------------ the fake model
class Resp:
    def __init__(self, text: str, finish: str = "stop"):
        self.content = text
        self.response_metadata = {"finish_reason": finish}


def respond(p: str) -> str:
    if "history-compaction step" in p:
        return "Research notes: found [1] and [2]; the figures in [3] disagree with [4]. Open: the 2025 numbers."
    if "plan the final report" in p:
        return json.dumps({"title": "Synthetic report", "answer_format": "",
                           "sections": [{"heading": f"Part {k}", "purpose": f"what part {k} covers",
                                         "sources": list(range(1 + 10 * k, 11 + 10 * k)) + [26, 27]}
                                        for k in range(3)]})
    if "Section to write now" in p:
        out = []
        for k in range(60):
            a, b, c = 1 + k % 30, 1 + (k * 7) % 30, 1 + (k * 13) % 30
            more = ", ".join(str(1 + (k * m) % 20) for m in (17, 19, 23))      # six sources: the token cap binds
            cite = f"[{a}]" if k % 3 == 0 else (f"[{a}][{b}]" if k % 3 == 1 else f"[{a}, {b}, {c}, {more}]")
            out.append(f"Measured value number {k} for alpha component reached {k * 7} units in March 2024 "
                       f"according to Source Name {k} {cite}.")
        out.append("Setting --expert-cache 2500 and STRATA_ROUTE_TAIL_SKIP=0 gave 110 GB / 10 GB = 11 parts [3].")
        return "## Part\n\n" + " ".join(out)
    if "===LIMITATIONS===" in p:
        return ("# Synthetic report\n\n## Answer\n\nThe answer is 42 units, as Source One measured [1].\n\n"
                "## Key findings\n\n- Finding one: 12 units in 2024 [2].\n- Finding two: 9 units [3][4].\n"
                "===LIMITATIONS===\n## Limitations\n\nSynthetic data only.")
    if "### Claim 1" in p:
        n = p.count("### Claim ")
        v = ("supported", "partial", "unsupported")
        return "\n".join(json.dumps({"claim": j + 1, "verdict": v[j % 3], "supporting": [1], "quote": "q",
                                     "note": "n"}) for j in range(n))
    if "List every technique" in p or "entries extracted part by part" in p:
        return json.dumps({"entries": [{"name": f"technique {i}", "status": "tried_rejected", "result": "r",
                                        "where": "w"} for i in range(5)]})
    return "{}"


class FakeModel:
    def __init__(self, empty_for: tuple[str, ...] = (), fail_times: int = 0):
        self.calls: list[dict] = []
        self.empty_for, self.fail_times = empty_for, fail_times

    def invoke(self, prompt, **kw):
        p = prompt if isinstance(prompt, str) else str(prompt)
        self.calls.append({"prompt": sha(p), "chars": len(p), "kw": dict(sorted(kw.items())),
                           "claims_in_call": p.count("### Claim ")})
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("synthetic failure")
        if any(m in p for m in self.empty_for):
            return Resp("", "length")
        return Resp(respond(p))


# ------------------------------------------------------------------------------------------------ synthetic data
WORDS = ("alpha beta gamma delta epsilon zeta theta kappa lambda sigma omega value figure measured result decode "
         "prompt expert cache layer token context memory bandwidth latency regulation article annex obligation "
         "provider deployer system model risk market March 2024 2025 component units source report").split()


def text(rng: random.Random, chars: int, para: int = 700) -> str:
    out, cur, n = [], [], 0
    while n < chars:
        w = rng.choice(WORDS)
        cur.append(w)
        n += len(w) + 1
        if sum(len(x) + 1 for x in cur) > para:
            out.append(" ".join(cur) + ".")
            cur = []
    if cur:
        out.append(" ".join(cur) + ".")
    return "\n\n".join(out)


def build_store(deep_pkg):
    from local_deep_research.deep.evidence import EvidenceStore
    rng = random.Random(1029)
    store = EvidenceStore("What do the synthetic sources say about alpha components and their measured values?", None)
    for i in range(1, 31):
        url = f"https://example.org/page/{i}"
        store.add_search(f"query {i % 7}", [{"index": i, "link": url, "title": f"Source title {i} " + "x" * 120,
                                             "snippet": text(rng, 900)}], engine="searxng")
    for i in range(1, 21):                       # pages read by the agents, with extractions (claims when on)
        page = text(rng, 20_000 + 5_000 * i)
        paras = page.split("\n\n")
        step = 1 if i == 8 else max(1, len(paras) // 12)       # source 8: > 40 checked quotes (the claim cap)
        quotes = [paras[j].split(".")[0][:400] for j in range(0, len(paras), step)]
        extraction = "\n".join(f'- "{q}"' for q in quotes)
        if i == 7:                               # one huge extraction: the section's 60 % share cuts it
            extraction += "\n" + text(rng, 110_000)
        store.add_fetch(i, f"https://example.org/page/{i}", f"Source title {i}", "alpha values", page, extraction)
    for i in range(21, 26):                      # pages only the background reader fetched (item 6)
        store.add_read(i, f"https://example.org/page/{i}", f"Source title {i}", text(rng, 60_000), date="2024-03-01",
                       via=(3 if i == 21 else None))
    for k in range(4):
        body = text(rng, 45_000)
        store.add_subagent(f"subtopic {k}", body + " " + " ".join(f"[{1 + (k * 5 + j) % 30}]" for j in range(30)),
                           "ok", 100.0, 12)
    lead = text(rng, 48_000) + " [1] [2] [3] [21] [22]"
    return store, lead


# ------------------------------------------------------------------------------------------------ the dumps
def config_dump(deep) -> dict:
    c = deep.config()
    d = dataclasses.asdict(c)
    meta = {k: d.pop(k) for k in ("profile", "profile_errors", "extra") if k in d}
    meta["sources"] = deep.config_sources() if hasattr(deep, "config_sources") else {}
    return {"config": d, "meta": meta}


def tool_descriptions(mod) -> dict:
    """The @tool(description=...) strings of codetool.make_tools, evaluated with the module's own names (no tools are
    made: make_tools would sweep the scratch root and import LDR's fetch tool)."""
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    out = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name == "make_tools":
            for inner in fn.body:
                if isinstance(inner, ast.FunctionDef):
                    for dec in inner.decorator_list:
                        if isinstance(dec, ast.Call):
                            for kw in dec.keywords:
                                if kw.arg == "description":
                                    out[inner.name] = eval(compile(ast.Expression(kw.value), "<desc>", "eval"),
                                                           vars(mod))
    return out


def constants(deep) -> dict:
    from local_deep_research.deep import (advisory, claims, codetool, llm, middleware, reading, seed, tokens,
                                          tried)
    names = {
        "tokens": ["MSG_OVERHEAD"], "middleware": ["MARGIN", "NOTES_KEY", "WRAP_KEY"],
        "reading": ["READ_MAX", "PRIMARY_MAX", "PRIMARY_PER_PAGE"], "seed": ["SEED_TEXT_MAX"],
        "tried": ["PART_CHARS", "MAP_MAX", "MERGE_CHARS", "FINAL_MAX", "BLOCK_CHARS"],
        "codetool": ["MAX_MB", "CLONE_TIMEOUT_S", "GREP_HITS", "READ_LINES", "LINE_CHARS", "TREE_ENTRIES",
                     "TEXT_MAX_BYTES", "API_MAX", "SEARCH_MAX", "API_RESERVE", "HISTORY_DEPTH", "LEAD_ADDENDUM"],
        "llm": ["LOWER"], "advisory": ["CHECK_MAX", "VERIFY2_MAX_CLAIMS", "VERIFY2_OTHERS"],
        "claims": ["MIN_QUOTE_CHARS", "NEAR_CHARS"],
    }
    mods = dict(tokens=tokens, middleware=middleware, reading=reading, seed=seed, tried=tried, codetool=codetool,
                llm=llm, advisory=advisory, claims=claims)
    out = {f"{m}.{n}": getattr(mods[m], n) for m, ns in names.items() for n in ns if hasattr(mods[m], n)}
    out["codetool.tool_descriptions"] = tool_descriptions(codetool)
    out["claims.evidence_block.default"] = sha(claims.evidence_block(
        [{"quote": f"quote number {i} " * 3, "found": "exact", "date": "2024-03-01", "date_how": "in the quote"}
         for i in range(100)]))
    return out


# ------------------------------------------------------------------------------------------------ traces
def trace_tokens(deep) -> dict:
    from local_deep_research.deep import tokens
    rng = random.Random(7)
    t = text(rng, 50_000)
    msg = SimpleNamespace(content=t[:5000], tool_calls=[{"name": "web_search", "args": {"query": "q"}}])
    tools = [{"name": "web_search", "description": "search the web", "parameters": {"q": "string"}},
             SimpleNamespace(name="fetch", description="fetch a page", args_schema=None, args={"url": "string"})]
    return {"count_text": [tokens.count_text(t[:n]) for n in (0, 1, 100, 5000, 50_000)],
            "count_message": tokens.count_message(msg), "count_tools": tokens.count_tools(tools),
            "count_tools_empty": tokens.count_tools([]),
            "truncate": [sha(tokens.truncate_to_tokens(t, n)) for n in (0, 10, 1000, 100_000)],
            "tokenizer": bool(tokens._load())}


def trace_llm(deep) -> dict:
    from local_deep_research.deep import llm
    if hasattr(llm, "SAME_PAUSE_S"):                 # LDR_DEEP_EFFORT_LADDER=same: no real pauses in a test
        llm.SAME_PAUSE_S = (0.0, 0.0)
    out = {}
    for name, model, eff in (("ok", FakeModel(), "xhigh"), ("ok_default", FakeModel(), ""),
                             ("empty", FakeModel(empty_for=("synthetic",)), "xhigh"),
                             ("empty_low", FakeModel(empty_for=("synthetic",)), "low"),
                             ("error", FakeModel(fail_times=5), "high")):
        text_, info = llm.invoke(model, "a synthetic prompt", eff, what=f"probe {name}", max_tokens=1234)
        out[name] = {"text": sha(text_), "info": {k: v for k, v in info.items() if k != "error"},
                     "calls": [c["kw"] for c in model.calls]}
    return out


def trace_report(deep, label: str) -> dict:
    from local_deep_research.deep import report as rep
    store, lead = build_store(deep)
    model = FakeModel()
    w = rep.ReportWriter(store.query, store, model, lead)
    t0 = time.time()
    res = w.run()
    st = {k: v for k, v in res["stats"].items() if k not in ("report_seconds", "elapsed_s", "effort_drops")}
    vb = [c["claims_in_call"] for c in model.calls if c.get("claims_in_call")]
    return {"label": label, "calls": model.calls, "n_calls": len(model.calls), "markdown": sha(res["markdown"]),
            "verify_batches": vb, "claims_per_source_max": max((len(s.claims) for s in store.all_sources()), default=0),
            "claims": sha([{k: c.get(k) for k in ("line", "text", "sources", "verdict")} for c in res["claims"]]),
            "stats": st, "outline": res["outline"], "seconds": round(time.time() - t0, 1)}


def trace_middleware(deep) -> dict:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    from local_deep_research.deep.middleware import DeepAgentMiddleware
    rng = random.Random(11)

    def history(n_tools: int, chars: int) -> list:
        msgs = [HumanMessage(content="The task: what do the sources say about alpha?", id="h0")]
        for k in range(n_tools):
            msgs.append(AIMessage(content=f"step {k}", id=f"a{k}",
                                  tool_calls=[{"name": "web_search", "args": {"query": f"q{k}"}, "id": f"c{k}"}]))
            msgs.append(ToolMessage(content=text(rng, chars) + f" [{1 + k % 30}]", tool_call_id=f"c{k}",
                                    name="web_search", id=f"t{k}"))
        return msgs

    def ser(out):
        if out is None:
            return None
        return [(type(m).__name__, sha(getattr(m, "content", "")), len(str(getattr(m, "content", ""))))
                for m in out.get("messages", [])]

    res = {}
    for name, model in (("compact", FakeModel()), ("compact_fallback", FakeModel(empty_for=("history-compaction",)))):
        mw = DeepAgentMiddleware(role="lead", label="lead", model=model, store=None, task="the task",
                                 deadline=1e18, max_calls=200)
        out = mw.before_model({"messages": history(30, 20_000)}, None)    # over compact_at with either counter
        res[name] = {"out": ser(out), "calls": model.calls, "compactions": mw.compactions,
                     "after": mw.after_last_compaction}

    class Req:
        def __init__(self, system_message, tools, messages):
            self.system_message, self.tools, self.messages = system_message, tools, messages

        def override(self, **kw):
            d = dict(system_message=self.system_message, tools=self.tools, messages=self.messages)
            d.update(kw)
            return Req(**d)

    seen = {}

    def handler(req):
        seen["msgs"] = [(type(m).__name__, len(str(m.content)), sha(str(m.content))) for m in req.messages]
        seen["tools"] = len(req.tools)
        return "ok"

    mw = DeepAgentMiddleware(role="sub", label="sub1", model=FakeModel(), store=None, task="t", deadline=1e18,
                             max_calls=30)
    tools = [{"name": "web_search", "description": "search", "parameters": {"q": "string"}}]
    mw.wrap_model_call(Req(SystemMessage(content="system prompt " * 300), tools, history(40, 20_000)), handler)
    res["guard"] = {"seen": seen, "fixed_tokens": mw.fixed_tokens,
                    "shortened": sum(1 for m in seen["msgs"] if m[0] == "ToolMessage" and m[1] < 20_000)}
    return res


def trace_seed(deep) -> dict:
    from local_deep_research.deep import seed
    rng = random.Random(5)
    s = seed.Seed()
    for i in range(1, 200):
        s.src(i, f"https://example.org/{i}", f"title {i}")["page_text"] = "p" if i % 2 else ""
    s.subagents = [{"topic": f"topic {k}", "text": text(rng, 30_000)} for k in range(6)]
    s.notes = [{"kind": "lead_answer", "who": "lead", "text": text(rng, 40_000)}]
    s.queries = [f"query {i}" for i in range(200)]
    return {"lead_addendum": sha(seed.lead_addendum(s)), "chars": len(seed.lead_addendum(s))}


def trace_tried(deep, scratch: Path) -> dict:
    from local_deep_research.deep import tried
    rng = random.Random(9)
    files = []
    for k in range(2):
        f = scratch / f"tried-file-{k}.md"
        f.write_text(text(rng, 150_000), encoding="utf-8")
        files.append(str(f))
    seen = []

    def llm(prompt, max_tokens, effort):
        seen.append({"prompt": sha(prompt), "chars": len(prompt), "max_tokens": max_tokens, "effort": effort})
        return respond(prompt), "stop"

    res = tried.build(llm, files)
    big = {"entries": [{"name": f"technique {i} " + "n" * 60, "status": "tried_rejected", "result": "r" * 200,
                        "where": "w" * 40} for i in range(400)]}
    return {"calls": seen, "build": sha({k: v for k, v in res.items() if k not in ("seconds", "built")}),
            "block": sha(tried.block(big)), "block_chars": len(tried.block(big))}


def trace_codetool(deep, scratch: Path) -> dict:
    from local_deep_research.deep import codetool as ct
    root = scratch / "repo"
    (root / "src").mkdir(parents=True, exist_ok=True)
    for k in range(260):
        (root / "src" / f"file{k:03d}.c").write_text("".join(f"int needle_{i} = {i}; /* {'x' * 300} */\n"
                                                               for i in range(400 if k == 0 else 3)))
    r = ct.Repo("owner/repo", "v1", root)
    g = r.grep("needle", ".")
    rd = r.read("src/file000.c", 10)
    tr = r.tree(".", 2)

    class FakeAPI(ct.GitHubAPI):
        def __init__(self):
            pass

        def _get(self, path, params=None):
            if path.startswith("/search/issues"):
                return {"total_count": 3, "items": [{"number": i, "title": "t", "state": "open",
                                                     "created_at": "2024-01-01T00:00:00Z", "html_url": "u",
                                                     "body": "b" * 5000} for i in range(12)]}
            if path.endswith("/comments"):
                return [{"author_association": "OWNER", "created_at": "2024-01-02T00:00:00Z", "body": "c" * 5000}
                        for _ in range(12)]
            return {"number": 1, "title": "t", "state": "open", "created_at": "2024-01-01T00:00:00Z",
                    "html_url": "u", "body": "b" * 9000, "comments": 12}

    api = FakeAPI()
    s = api.search("owner/repo", "needle")
    i = api.issue("owner/repo", 1)
    return {"grep": {"total": g["total"], "hits": len(g["hits"]), "more": g["more"],
                     "line_len": max(len(h["text"]) for h in g["hits"])},
            "read": {"start": rd["start"], "end": rd["end"], "text": sha(rd["text"])},
            "tree": {"entries": len(tr["entries"]), "cut": tr["cut"]},
            "search": [len(x["body"]) for x in s["items"]],
            "issue": {"body": len(i["body"]), "comments": [len(c["text"]) for c in i["comments"]]}}


def runner_dump(path: str) -> dict:
    import importlib.machinery
    sys.path.insert(0, str(WS / "tools"))
    # the staged runner reads the loader from the installed package (not there before the install): register the
    # staged one under the name the runner looks for first (the old runner does not use it)
    name = "deep_modelprofile"
    spec = importlib.util.spec_from_file_location(name, STAGED / "deep/modelprofile.py")
    mp = importlib.util.module_from_spec(spec)
    sys.modules[name] = mp
    spec.loader.exec_module(mp)
    loader = importlib.machinery.SourceFileLoader("research_runner_probe", path)   # also for the .orig file
    spec = importlib.util.spec_from_loader("research_runner_probe", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return {k: getattr(m, k) for k in ("DEEP_EFFORTS", "DEEP_LDR_EFFORTS", "DEEP_LDR_EFFORTS_FILE", "QUICK_CAP_S",
                                       "MEM_FLOOR_GB", "MEM_RELIEF_GB", "MEM_RELIEF_DS_GB")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", choices=("installed", "staged"), required=True)
    ap.add_argument("--traces", action="store_true")
    ap.add_argument("--runner")
    ap.add_argument("--scratch", required=True)
    a = ap.parse_args()
    scratch = Path(a.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    if a.runner:
        print(json.dumps({"runner": runner_dump(a.runner)}, default=str))
        return
    deep = load(a.pkg)
    out = {"pkg": a.pkg, "deep_file": deep.__file__, **config_dump(deep), "constants": constants(deep)}
    if a.traces:
        t0 = time.time()
        out["traces"] = {"tokens": trace_tokens(deep), "llm": trace_llm(deep), "seed": trace_seed(deep),
                         "tried": trace_tried(deep, scratch), "codetool": trace_codetool(deep, scratch / a.pkg),
                         "middleware": trace_middleware(deep), "report": trace_report(deep, os.environ.get(
                             "LDR_DEEP_FIX", "") or "classic")}
        out["trace_seconds"] = round(time.time() - t0, 1)
    print(json.dumps(out, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
