"""Offline tests of the staged LDR patches 0007 (memwatch), 0008 (subagent steps), 0009 (paper quotes) and the runner's
fresh-LDR rule. Run by tests/run.sh, which builds a patched COPY of the installed package (scratch/testsite: the venv's
local_deep_research + the three patches) and points sys.path at it. No network, no model, no LDR server; the bench
runs' evidence files are only read.
"""
import ast
import importlib
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ST = Path("/home/USER/ai/deep-research/staging/ldr-study")
SITE = Path(os.environ.get("LDR_STUDY_TESTSITE", ST / "scratch" / "testsite"))
RUNS = Path("/home/USER/ai/deep-research/results/bench2/runs")
WORK = Path(tempfile.mkdtemp(prefix="t-", dir=ST / "scratch"))
os.environ["LDR_MEMWATCH_LOG"] = str(WORK / "ldr-mem.jsonl")
os.environ.setdefault("LDR_DATA_DIR", str(WORK / "data"))
sys.path.insert(0, str(SITE))

from loguru import logger  # noqa: E402

logger.remove()
logger.add(sys.stderr, level="ERROR")


def set_fix(value: str) -> None:
    os.environ["LDR_DEEP_FIX"] = value


def evidence_record(run: str, line: int) -> dict | None:
    p = RUNS / run / "deep" / "evidence.jsonl"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        for n, row in enumerate(f):
            if n == line:
                return json.loads(row)
    return None


def page_of(run: str, url: str) -> str:
    with open(RUNS / run / "deep" / "evidence.jsonl", encoding="utf-8") as f:
        for row in f:
            r = json.loads(row)
            if r.get("url") == url and r.get("page_text"):
                return r["page_text"]
    return ""


# ------------------------------------------------------------------------------------------------------ 0007 memwatch
class MemwatchTests(unittest.TestCase):
    def setUp(self):
        from local_deep_research.deep import memwatch
        self.mw = importlib.reload(memwatch)
        self.mw.LOG_PATH = WORK / f"mem-{self._testMethodName}.jsonl"

    def lines(self):
        return [json.loads(x) for x in self.mw.LOG_PATH.read_text().splitlines()] if self.mw.LOG_PATH.exists() else []

    def test_1_record_fields(self):
        """record() writes one JSON line with RSS, HWM, glibc in-use / free bytes, arena heaps, threads."""
        self.mw.record("unit")
        rec = self.lines()[-1]
        for k in ("rss_mb", "hwm_mb", "threads", "arena_heaps", "py_blocks", "malloc_in_use_mb", "malloc_free_mb"):
            self.assertIn(k, rec)
        self.assertEqual(rec["tag"], "unit")

    def test_2_trim_gives_memory_back(self):
        """After a burst of allocations in short-lived threads is freed, trim() returns RSS to the OS and says so."""
        def burst():
            junk = [("x" * 700) + str(i) for i in range(250_000)]      # ~190 MB of >512-byte strings (glibc malloc)
            del junk
        for _ in range(3):
            t = threading.Thread(target=burst)
            t.start()
            t.join()
        freed = self.mw.trim("unit")
        rec = self.lines()[-1]
        self.assertTrue(rec["tag"].startswith("trim (unit)"))
        self.assertIn("rss_before_mb", rec)
        self.assertGreaterEqual(freed, 0.0)
        print(f"\n  trim after a 3 x 190 MB burst: freed {freed:.0f} MB", file=sys.stderr)

    def test_3_after_fetch_thresholds(self):
        """A big page or a PDF triggers a trim; a small page does not; two big pages within MIN_GAP_S trim once."""
        self.mw.MIN_GAP_S = 3600
        self.mw._state["last_trim"] = 0.0
        self.mw.after_fetch({"status": "success", "content": "x" * 1000, "source_type": "Web Page"})
        self.assertEqual(self.mw._state["trims"], 0)
        self.mw.after_fetch({"status": "success", "content": "x" * 150_000, "source_type": "Web Page"})
        self.mw.after_fetch({"status": "success", "content": "y", "source_type": "arXiv"})
        self.assertEqual(self.mw._state["trims"], 1)
        self.mw._state["last_trim"] = 0.0
        self.mw.after_fetch({"status": "success", "content": "y", "source_type": "PDF"})
        self.assertEqual(self.mw._state["trims"], 2)

    def test_4_research_end(self):
        """research_end records, empties the user-file text cache and trims TRIM_DELAY_S later in a timer thread."""
        from local_deep_research.deep import files
        files._texts["/x.pdf"] = "text"
        self.mw.TRIM_DELAY_S = 0.2
        self.mw.research_start("r1")
        self.mw.research_end("r1")
        self.assertEqual(files._texts, {})
        time.sleep(1.0)
        tags = [r["tag"] for r in self.lines()]
        self.assertIn("research start", tags)
        self.assertIn("research end", tags)
        self.assertTrue(any(t.startswith("trim (research end") for t in tags), tags)

    def test_5_switch_off(self):
        """LDR_MEM_TRIM=0 keeps the records and does no trim."""
        self.mw.TRIM = False
        self.assertEqual(self.mw.trim("off"), 0.0)
        self.mw.after_fetch({"status": "success", "content": "x" * 200_000})
        self.assertFalse(any(r["tag"].startswith("trim") for r in self.lines()))


# ------------------------------------------------------------------------------------------------- 0008 subagent steps
class StepTests(unittest.TestCase):
    """The real DeepAgentMiddleware in a LangChain create_agent graph with a fake model that always asks for a tool
    (until the middleware takes the tools away at its wrap-up), under the strategy's recursion limit."""

    def run_agent(self, fix: str):
        set_fix(fix)
        from langchain.agents import create_agent
        from langchain_core.language_models.chat_models import BaseChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        from langchain_core.tools import tool
        from langgraph.errors import GraphRecursionError
        from local_deep_research.advanced_search_system.strategies import langgraph_agent_strategy as strat
        from local_deep_research.deep.middleware import DeepAgentMiddleware

        calls = {"n": 0, "final": 0}

        class Fake(BaseChatModel):
            has_tools: bool = False

            def _generate(self, messages, stop=None, run_manager=None, **kw):
                calls["n"] += 1
                if self.has_tools:
                    msg = AIMessage(content="", tool_calls=[{"name": "noop", "args": {"q": str(calls["n"])},
                                                             "id": f"c{calls['n']}"}])
                else:
                    calls["final"] += 1
                    msg = AIMessage(content="FINDINGS: the facts with [1]")
                return ChatResult(generations=[ChatGeneration(message=msg)])

            def bind_tools(self, tools, **kw):
                return Fake(has_tools=bool(tools))

            @property
            def _llm_type(self):
                return "fake"

        @tool
        def noop(q: str) -> str:
            """does nothing"""
            return "ok"

        mw = DeepAgentMiddleware(role="sub", label="sub1", model=Fake(), store=None, task="t",
                                 deadline=time.time() + 3600, max_calls=30)
        agent = create_agent(model=Fake(), tools=[noop], middleware=[mw])
        limit = strat._deep_recursion_limit(30)
        try:
            res = agent.invoke({"messages": [{"role": "user", "content": "topic"}]}, {"recursion_limit": limit})
            return limit, calls, mw, res["messages"][-1].content
        except GraphRecursionError:
            return limit, calls, mw, None

    def test_6_old_limit_cuts_at_23(self):
        """Without the "steps" item: limit 70, GraphRecursionError at the 23rd model call, no wrap-up (the bug)."""
        limit, calls, mw, final = self.run_agent("all,read,claims")
        self.assertEqual(limit, 70)
        self.assertIsNone(final)
        self.assertEqual(calls["n"], 23)
        self.assertIsNone(mw.wrapped)

    def test_7_new_limit_lets_the_wrap_up_finish(self):
        """With "steps": limit 100; the middleware wraps up at its step limit and the subagent answers (call 30)."""
        limit, calls, mw, final = self.run_agent("all,read,claims,steps")
        self.assertEqual(limit, 100)
        self.assertEqual(final, "FINDINGS: the facts with [1]")
        self.assertEqual(calls["final"], 1)
        self.assertEqual(calls["n"], 30)
        self.assertTrue((mw.wrapped or "").startswith("step limit"))

    def test_8_salvage(self):
        """The backstop: a subagent that still hits the limit hands the lead its own extractions (with "steps")."""
        from local_deep_research.advanced_search_system.strategies import langgraph_agent_strategy as strat
        from local_deep_research.deep import current_agent
        from local_deep_research.deep.evidence import EvidenceStore
        store = EvidenceStore("q", None)
        current_agent.set("sub3")
        store.add_fetch(7, "https://example.org/p", "Paper", "focus", "page text", "\"A quote with a number 42.\"")
        current_agent.set("sub4")
        store.add_fetch(8, "https://example.org/q", "Other", "focus", "page", "\"Not mine.\"")
        set_fix("all,steps")
        text = strat._deep_salvage(store, "sub3", "the topic")
        self.assertIn("[7] Paper - https://example.org/p", text)
        self.assertIn("A quote with a number 42.", text)
        self.assertNotIn("Not mine", text)
        set_fix("all")
        self.assertEqual(strat._deep_salvage(store, "sub3", "the topic"), "Research on 'the topic' reached iteration limit.")


# --------------------------------------------------------------------------------------------------- 0009 paper quotes
PAPER = ("Abstract: We present FooMoE, a verifier-side selector. Although constraining target-expert eligibility changes "
         "the model distribution, across 12 model-task pairs FooMoE's mean accuracy is 0.27 percentage points lower "
         "than the baseline. As shown by Smith et al. in Fig. 3, the gain holds. 5 Evaluation. All experiments are "
         "conducted on a platform equipped with an AMD EPYC 7532 CPU with 64 cores and an RTX 3090. To ensure a fair "
         "comparison, we set the number of CPU cores to 16 and threads to 32 for all frameworks. FooMoE reaches 2.06x "
         "the throughput under offloading on one RTX 5090 while reducing traffic by 73 percent. References [1] A. B.")


class QuoteTests(unittest.TestCase):
    def setUp(self):
        from local_deep_research.deep import quotes
        self.q = importlib.reload(quotes)

    def test_09_clause_restored(self):
        """A quote cut open after a comma gets its sentence's first clause back (the AcceptMoE case)."""
        ext = "\"across 12 model-task pairs FooMoE's mean accuracy is 0.27 percentage points lower than the baseline.\""
        out, st = self.q.complete_quotes(ext, PAPER)
        self.assertIn("Although constraining target-expert eligibility changes the model distribution, across 12", out)
        self.assertEqual(st["start_extended"], 1)
        self.assertTrue(out.startswith("\"Although") and out.endswith("baseline.\""))

    def test_10_whole_sentences_and_abbreviations_unchanged(self):
        """A quote that starts its sentence stays as it is; "et al." / "Fig." are not sentence ends."""
        ext = "\"FooMoE reaches 2.06x the throughput under offloading on one RTX 5090 while reducing traffic by 73 percent.\""
        out, st = self.q.complete_quotes(ext, PAPER)
        self.assertEqual(out, ext)
        out2, _ = self.q.complete_quotes("\"in Fig. 3, the gain holds.\"", PAPER)
        self.assertIn("As shown by Smith et al. in Fig. 3, the gain holds.", out2)

    def test_11_end_extension_and_budget(self):
        """A quote cut before its sentence ends is completed; the budget caps what is added."""
        out, st = self.q.complete_quotes("\"To ensure a fair comparison, we set the number of CPU cores to 16\"", PAPER)
        self.assertIn("to 16 and threads to 32 for all frameworks.", out)
        out2, st2 = self.q.complete_quotes("\"across 12 model-task pairs FooMoE's mean accuracy is 0.27\"", PAPER,
                                           max_extra=10)
        self.assertEqual(st2["added_chars"], 0)

    def test_12_paper_notes(self):
        """A paper page gets its caveat and setup sentences the extraction lacks; a shop page gets none."""
        notes = self.q.paper_notes(PAPER, "https://arxiv.org/abs/2608.00001", "\"FooMoE reaches 2.06x ...\"")
        self.assertIn("(also on this page:)", notes)
        self.assertIn("changes the model distribution", notes)
        self.assertIn("we set the number of CPU cores to 16 and threads to 32", notes)
        self.assertIn("All experiments are conducted on a platform", notes)
        shop = "Buy now. This RAM kit changes the game. Free shipping on all orders over $50 for all customers."
        self.assertEqual(self.q.paper_notes(shop, "https://www.example-shop.com/ram", "\"Buy now.\""), "")
        self.assertEqual(self.q.improve("NOT RELEVANT", PAPER, "https://arxiv.org/abs/1", 4000)[0], "NOT RELEVANT")

    def test_13_real_cases(self):
        """The traced 7a / 7c / p4s8 cases (bench evidence; skipped when absent)."""
        r = evidence_record("screen-deep-p7a/o01", 681)
        if r is None:
            self.skipTest("bench evidence not present")
        out, _ = self.q.improve(r["extraction"], r["page_text"], r["url"], 4000)
        self.assertIn("Although constraining target-expert eligibility changes the model distribution", out)
        r = evidence_record("screen-deep-p4s8/o01", 459)
        out, _ = self.q.improve(r["extraction"], r.get("page_text") or page_of("screen-deep-p4s8/o01", r["url"]),
                                r["url"], 4000)
        self.assertNotIn("we set the number of CPU cores to 16", r["extraction"])
        self.assertIn("we set the number of CPU cores to 16 and threads to 32 for all frameworks", out)
        r = evidence_record("screen-deep-p7c/o01", 452)
        out, _ = self.q.improve(r["extraction"], r.get("page_text") or page_of("screen-deep-p7c/o01", r["url"]),
                                r["url"], 4000)
        for env in ("RTX 3090 24 GB", "RTX 4090 24 GB", "A100 40 GB"):
            self.assertTrue(any(env in ln and "4.0 x 16" in ln for ln in out.splitlines()), env)

    def test_14_switches(self):
        """"papers" / "steps" are items: never switched on by "all"; the extraction rules and the writer rules exist."""
        from local_deep_research.deep import checks, prompts, report
        set_fix("all,read,claims")
        self.assertFalse(checks.fix_on("papers"))
        self.assertFalse(checks.fix_on("steps"))
        set_fix("all,read,claims,papers")
        self.assertTrue(checks.fix_on("papers"))
        self.assertIn("Quote whole sentences", prompts.EXTRACT_PAPER_RULES)
        self.assertNotIn("{", prompts.EXTRACT_PAPER_RULES)
        self.assertIn("papers", [k for k, _ in report.FIX_SECTION_RULES])
        self.assertIn("papers", [k for k, _ in report.FIX_OPENING_RULES])
        for k, rule in report.FIX_SECTION_RULES + report.FIX_OPENING_RULES:
            self.assertNotIn("{", rule, k)                      # the prompts are str.format templates
        os.environ["LDR_DEEP_QUOTES"] = "0"
        q = importlib.reload(importlib.import_module("local_deep_research.deep.quotes"))
        self.assertEqual(q.improve("\"across 12 model-task pairs\"", PAPER, "https://arxiv.org/abs/1", 4000)[0],
                         "\"across 12 model-task pairs\"")
        del os.environ["LDR_DEEP_QUOTES"]
        importlib.reload(q)


# ------------------------------------------------------------------------------------------------- runner fresh LDR
class RunnerTests(unittest.TestCase):
    def load(self):
        src = (ST / "site" / "tools" / "research-runner.py").read_text()
        tree = ast.parse(src)
        keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("ldr_rss_gb", "ldr_memory_reasons")]
        ns = {"Path": Path, "os": os, "FRESH_RSS_GB": 1.0, "ldr_pid": lambda: None}
        exec(compile(ast.Module(body=keep, type_ignores=[]), "runner-excerpt", "exec"), ns)
        return ns

    def test_15_fresh_ldr_reason(self):
        """Above LDR_FRESH_RSS_GB the runner restarts LDR before a job; below it, or with 0, it does not."""
        ns = self.load()
        me = os.getpid()
        self.assertGreater(ns["ldr_rss_gb"](me), 0.0)
        self.assertTrue(ns["ldr_memory_reasons"](0.001, pid=me)[0].startswith("LDR holds "))
        self.assertEqual(ns["ldr_memory_reasons"](1000.0, pid=me), [])
        self.assertEqual(ns["ldr_memory_reasons"](0, pid=me), [])
        self.assertEqual(ns["ldr_memory_reasons"](1.0, pid=None), [])          # LDR not running


if __name__ == "__main__":
    unittest.main(verbosity=2)
