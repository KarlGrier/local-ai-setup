#!/usr/bin/env python3
"""C4 offline tests: the Anthropic budget guard against a local mock of the Messages API, plus the launcher wiring.

Run (nothing leaves 127.0.0.1, no real key, no model, no GPU, no live service is called or changed):
  nice -n 19 /home/USER/ai/deep-research/.venv/bin/python -I -B staging/c4/tests/test_c4.py
Writes tests/results/results.{md,json}. Temporary files go to $TMPDIR (removed at the end unless C4_TEST_KEEP=1).

The fake keys below are made up for these tests; the real key file is never opened.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unittest
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
C4 = HERE.parent
C3 = C4.parent / "c3"
WS = Path("/home/USER/ai/deep-research")
PY = str(WS / ".venv/bin/python")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(C4 / "tools"))

import anthropic_guard as G  # noqa: E402
from mock_anthropic import MockAnthropic  # noqa: E402

FAKE_KEY = "sk-ant-api03-TESTONLY-" + "Q" * 24 + "-fake"            # looks like a key: masked anywhere it shows up
FAKE_KEY_B = "sk-ant-api03-TESTONLY-" + "R" * 24 + "-fake"
FAKE_KEY_PLAIN = "plainkey-testonly-0123456789abcdefXYZ"            # does not look like one: only exact masking
ENV_KEY = "sk-ant-api03-FROM-ENV-" + "Z" * 20                       # must never be used (the guard drops ANTHROPIC_*)
ALL_KEYS = (FAKE_KEY, FAKE_KEY_B, FAKE_KEY_PLAIN, ENV_KEY)
TMP = Path(tempfile.mkdtemp(prefix="c4test-"))
BODIES: list[str] = []          # every response body the tests saw (checked for keys at the end)
FACTS: dict = {}                # numbers shown in results.md

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
for k in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
    os.environ[k] = "false"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def write_key(path: Path, key: str) -> None:
    path.write_text(key + "\n")
    path.chmod(0o600)


def thinking(sig):
    return {"type": "thinking", "thinking": "", "signature": sig}


def text(t):
    return {"type": "text", "text": t}


def tool_use(i, name, inp):
    return {"type": "tool_use", "id": i, "name": name, "input": inp}


class GuardProc:
    """The guard as its own process (like c4-arm.sh starts it), against the mock."""

    def __init__(self, name, mock, key_file, *, run_cap=5.0, total_cap=50.0, ledger=None, extra=(), env_extra=None):
        self.name = name
        self.port = free_port()
        self.dir = TMP / f"guard-{name}"
        self.dir.mkdir()
        self.ledger = str(ledger or self.dir / "ledger.json")
        self.out = self.dir / "guard.out"
        args = [PY, "-I", "-B", str(C4 / "tools/anthropic_guard.py"), "--arm", name, "--port", str(self.port),
                "--run-id", f"run-{name}", "--upstream", mock.url, "--key-file", str(key_file),
                "--run-cap-usd", str(run_cap), "--total-cap-usd", str(total_cap), "--ledger", self.ledger,
                "--log-dir", str(self.dir / "log"), *extra]
        env = {"PATH": os.environ["PATH"], "HOME": str(TMP), "NO_PROXY": "127.0.0.1,localhost",
               # all of these must be ignored and removed by the guard
               "ANTHROPIC_API_KEY": ENV_KEY, "ANTHROPIC_BASE_URL": "http://127.0.0.1:1", "ANTHROPIC_LOG": "debug",
               "ANTHROPIC_CUSTOM_HEADERS": "x-test: leaked"}
        env.update(env_extra or {})
        self.p = subprocess.Popen(args, env=env, stdout=open(self.out, "w"), stderr=subprocess.STDOUT)
        self.url = f"http://127.0.0.1:{self.port}"
        for _ in range(200):
            try:
                urllib.request.urlopen(self.url + "/health", timeout=1).read()
                return
            except OSError:
                if self.p.poll() is not None:
                    raise RuntimeError(f"guard {name} exited: {self.out.read_text()}")
                time.sleep(0.05)
        raise RuntimeError(f"guard {name} did not start")

    def client(self):
        from openai import OpenAI
        return OpenAI(base_url=self.url + "/v1", api_key="unused-by-the-guard", max_retries=0, timeout=30)

    def log(self) -> list[dict]:
        p = self.dir / "log" / f"costs-run-{self.name}.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def log_wait(self, n: int, timeout: float = 5.0) -> list[dict]:
        """The log once it has n lines (the guard writes a request's line just after its answer went out)."""
        t = time.time() + timeout
        while True:
            lines = self.log()
            if len(lines) >= n or time.time() > t:
                return lines
            time.sleep(0.02)

    def gaps(self) -> list[dict]:
        p = self.dir / "log" / f"lead-gaps-run-{self.name}.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def summary(self) -> dict:
        return json.loads((self.dir / "log" / f"summary-run-{self.name}.json").read_text())

    def status(self) -> dict:
        return json.loads(urllib.request.urlopen(self.url + "/v1/guard/status", timeout=5).read())

    def post(self, body: dict) -> tuple[int, dict]:
        req = urllib.request.Request(self.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                BODIES.append(raw)
                return r.status, json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            BODIES.append(raw)
            return e.code, json.loads(raw)

    def stop(self):
        self.p.terminate()
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()


def make_cfg(d: Path, mock_url: str, key_file: Path, **kw) -> G.Config:
    base = dict(arm="unit", port=1, run_id="unit", model="claude-sonnet-5-5", upstream=mock_url,
                key_file=str(key_file), run_cap=5.0, total_cap=50.0, agent_cap=None, ledger=str(d / "ledger.json"),
                log_dir=str(d / "log"), pricing=G.DEFAULT_PRICING, default_effort="medium",
                class_efforts={"agent": "medium", "extract": "low"}, effort_map={}, default_max_tokens=32000,
                max_tokens_cap=64000, cache_ttl="5m", replay="store", tokens_per_byte=1.0, overhead_tokens=2000,
                wait_inflight_s=5.0, upstream_retries=2, read_timeout=60.0, store_max_mb=64, status="draft")
    base.update(kw)
    return G.Config(**base)


SYS = "You are the lead agent of a research system. " * 40
# the first words of LDR 1.10.7's lead and subagent system prompts (stock and our build)
LEAD_SYS = G.LEAD_MARK + " Today's date: 2026-10-29.\nThis is NOT a chat conversation. " + "Research. " * 200
SUB_SYS = "You are a focused research assistant working for a lead researcher. Today's date: 2026-10-29. " * 20
TOOLS = [{"type": "function", "function": {"name": "web_search", "description": "Search the web.",
                                           "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                                                          "required": ["query"]}}},
         {"type": "function", "function": {"name": "fetch_page", "description": "Read a page.",
                                           "parameters": {"type": "object", "properties": {"url": {"type": "string"}},
                                                          "required": ["url"]}}}]


def n_markers(body: dict) -> int:
    n = sum(1 for t in body.get("tools") or [] if "cache_control" in t)
    n += sum(1 for b in body.get("system") or [] if isinstance(b, dict) and "cache_control" in b)
    for m in body.get("messages") or []:
        if isinstance(m["content"], list):
            n += sum(1 for b in m["content"] if "cache_control" in b)
    return n + (1 if body.get("cache_control") else 0)


# ============================================================================================ unit tests (in-process)
class T1Units(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = TMP / "unit"
        cls.d.mkdir()
        cls.key = cls.d / "key"
        write_key(cls.key, FAKE_KEY)
        cls.g = G.Guard(make_cfg(cls.d, "http://127.0.0.1:9", cls.key))

    def test_effort_names(self):
        m = {}
        for raw, want in (("low", "low"), ("medium", "medium"), ("high", "high"), ("xhigh", "xhigh"), ("max", "max"),
                          ("minimal", "low"), ("none", "low"), ("XHIGH", "xhigh")):
            self.assertEqual(G.map_effort(raw, m), want, raw)
        with self.assertRaises(G.TranslateError):
            G.map_effort("turbo", m)
        mp = G.parse_effort_spec("xhigh=high,low=", "map")
        self.assertEqual(G.map_effort("xhigh", mp), "high")
        self.assertIsNone(G.map_effort("low", mp))
        with self.assertRaises(SystemExit):
            G.parse_effort_spec("agent=ultra", "class")
        with self.assertRaises(SystemExit):
            G.parse_effort_spec("lead=low", "class")

    def test_effort_precedence(self):
        g = self.g
        self.assertEqual(g.pick_effort({"reasoning_effort": "xhigh"}, "agent"), ("xhigh", "request"))
        self.assertEqual(g.pick_effort({"reasoning": {"effort": "low"}}, "other"), ("low", "request"))
        self.assertEqual(g.pick_effort({}, "agent"), ("medium", "class:agent"))
        self.assertEqual(g.pick_effort({}, "extract"), ("low", "class:extract"))
        self.assertEqual(g.pick_effort({}, "report"), ("medium", "default"))
        g2 = G.Guard(make_cfg(self.d / "x", "http://127.0.0.1:9", self.key, default_effort=None, class_efforts={},
                              ledger=str(self.d / "l2.json")))
        self.assertEqual(g2.pick_effort({}, "other"), (None, "api-default"))
        p = g2.translate({"messages": [{"role": "user", "content": "hi"}]})
        self.assertNotIn("output_config", p.params)
        p = self.g.translate({"messages": [{"role": "user", "content": G.EXTRACT_MARK + " page..."}]})
        self.assertEqual((p.cls, p.effort), ("extract", "low"))
        for mark_cls, mark in G.CLASS_MARKS:
            self.assertEqual(self.g.translate({"messages": [{"role": "user", "content": mark + " x"}]}).cls, mark_cls)

    def test_price(self):
        r = G.load_rates(G.DEFAULT_PRICING, "claude-sonnet-5-5")
        self.assertEqual((r.input, r.output, r.cache_write_5m, r.cache_write_1h, r.cache_read), (2.0, 10.0, 2.5, 4.0, 0.2))
        u = {"input_tokens": 1000, "output_tokens": 2000, "cache_creation_input_tokens": 3000,
             "cache_read_input_tokens": 50000, "cache_write_5m": 3000, "cache_write_1h": 0}
        self.assertAlmostEqual(G.price(u, r, "5m"), (1000 * 2 + 3000 * 2.5 + 50000 * 0.2 + 2000 * 10) / 1e6, places=12)
        # no breakdown: the writes take the request's TTL
        u2 = dict(u, cache_write_5m=None, cache_write_1h=None)
        self.assertAlmostEqual(G.price(u2, r, "1h"), (1000 * 2 + 3000 * 4.0 + 50000 * 0.2 + 2000 * 10) / 1e6, places=12)
        u3 = dict(u, cache_creation_input_tokens=4000, cache_write_5m=1000, cache_write_1h=3000)
        self.assertAlmostEqual(G.price(u3, r, "5m"), (1000 * 2 + 1000 * 2.5 + 3000 * 4 + 50000 * 0.2 + 20000) / 1e6,
                               places=12)
        long = G.Rates("m", 2, 10, 2.5, 4, 0.2, long_threshold=200_000, long_input_mult=2.0, long_output_mult=1.5)
        u4 = {"input_tokens": 250_000, "output_tokens": 1000, "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 0}
        self.assertAlmostEqual(G.price(u4, long, "5m"), (250_000 * 2 * 2.0 + 1000 * 10 * 1.5) / 1e6, places=12)
        self.assertAlmostEqual(G.worst_case(100_000, 64_000, r, "5m"), (100_000 * 2.5 + 64_000 * 10) / 1e6, places=12)
        self.assertAlmostEqual(G.worst_case(100_000, 64_000, r, "1h"), (100_000 * 4.0 + 64_000 * 10) / 1e6, places=12)
        FACTS["worst_case_200k_in_64k_out_usd"] = round(G.worst_case(200_000, 64_000, r, "5m"), 4)

    def test_translate_plain(self):
        req = {"model": "anything", "messages": [{"role": "system", "content": SYS},
                                                 {"role": "user", "content": "Question?"}],
               "temperature": 0.7, "top_p": 0.9, "seed": 3, "max_tokens": 200000, "stop": "END",
               "strata_owner": "x", "foo": 1}
        p = self.g.translate(req)
        b = p.params
        self.assertEqual(b["model"], "claude-sonnet-5-5")
        self.assertEqual(b["max_tokens"], 64000)
        self.assertIn("max_tokens_clamped_from_200000", p.notes)
        # Karl 10-29: a one-shot call (no tools, nothing continued, a system prompt not sent before) is not cached
        self.assertNotIn("cache_control", b["system"][-1])
        self.assertNotIn("cache_control", b)
        self.assertEqual((p.cache_why, p.cache_head, p.cache_tail), ("one-shot", "none", False))
        self.assertEqual(b["thinking"], {"type": "adaptive", "display": "omitted",
                                         "block_binding": {"prefix_mismatch_behavior": "drop_block"}})
        self.assertEqual(b["betas"], [G.BETA_BINDING])
        for k in ("temperature", "top_p", "seed", "top_k"):
            self.assertNotIn(k, b)
        self.assertEqual(p.dropped, ["seed", "strata_owner", "temperature", "top_p"])
        self.assertEqual(p.ignored, ["foo"])
        self.assertEqual(b["stop_sequences"], ["END"])
        self.assertEqual(b["output_config"], {"effort": "medium"})
        self.assertLessEqual(n_markers(b), 4)
        with self.assertRaises(G.TranslateError):
            self.g.translate({"messages": [{"role": "user", "content": "x"}], "n": 2})
        with self.assertRaises(G.TranslateError):                # prefill
            self.g.translate({"messages": [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]})
        p = self.g.translate({"messages": [{"role": "user", "content": "x"}],
                              "response_format": {"type": "json_schema", "json_schema": {"name": "n", "schema": {
                                  "type": "object", "properties": {}, "additionalProperties": False}}}})
        self.assertEqual(p.params["output_config"]["format"]["type"], "json_schema")

    def test_cache_markers_tools_only_and_1h(self):
        """Tools without a system prompt: the marker on the last tool + the tail, 5m by default; 1h only on the
        lead's two breakpoints, and only with the switch on (Karl 10-29)."""
        p = self.g.translate({"messages": [{"role": "user", "content": "x"}], "tools": TOOLS})
        b = p.params
        self.assertEqual([t["name"] for t in b["tools"]], ["fetch_page", "web_search"])     # name-sorted
        self.assertEqual(b["tools"][-1]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", b["tools"][0])
        self.assertEqual(b["cache_control"], {"type": "ephemeral"})
        self.assertEqual(b["tools"][1]["input_schema"]["required"], ["query"])
        self.assertEqual(n_markers(b), 2)
        lead = {"messages": [{"role": "system", "content": LEAD_SYS}, {"role": "user", "content": "task"}],
                "tools": TOOLS}
        sub = {"messages": [{"role": "system", "content": SUB_SYS}, {"role": "user", "content": "subtopic"}],
               "tools": TOOLS}
        p = self.g.translate(lead)                                             # switch off (the default): 5m
        self.assertEqual((p.role, p.ttl), ("lead", "5m"))
        self.assertEqual(p.params["system"][-1]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(p.params["cache_control"], {"type": "ephemeral"})
        g = G.Guard(make_cfg(self.d / "h", "http://127.0.0.1:9", self.key, lead_cache_1h=True,
                             ledger=str(self.d / "l3.json")))
        p = g.translate(lead)
        self.assertEqual((p.role, p.ttl), ("lead", "1h"))
        self.assertEqual(p.params["system"][-1]["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        self.assertEqual(p.params["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        self.assertEqual(n_markers(p.params), 2)
        p = g.translate(sub)                                                    # a subagent stays at 5m
        self.assertEqual((p.role, p.ttl), ("sub", "5m"))
        self.assertEqual(p.params["system"][-1]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(p.params["cache_control"], {"type": "ephemeral"})
        p = g.translate({"messages": [{"role": "user", "content": G.EXTRACT_MARK + " page"}]})   # one-shot: none
        self.assertEqual(n_markers(p.params), 0)
        with self.assertRaises(SystemExit):                                    # no global 1h from the command line
            G.parse_args(["--arm", "a", "--port", "1", "--run-id", "r", "--ledger", "l", "--log-dir", "d",
                          "--run-cap-usd", "1", "--total-cap-usd", "2", "--cache-ttl", "1h"])
        cfg = G.parse_args(["--arm", "a", "--port", "1", "--run-id", "r", "--ledger", "l", "--log-dir", "d",
                            "--run-cap-usd", "1", "--total-cap-usd", "2"])
        self.assertEqual((cfg.cache_ttl, cfg.lead_cache_1h, cfg.report_reserve), ("5m", False, 0.22))

    def test_tool_turns(self):
        msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": "Q"},
                {"role": "assistant", "content": "Let me look.", "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "a"}'}},
                    {"id": "call 2!", "type": "function", "function": {"name": "fetch_page", "arguments": "not json"}}]},
                {"role": "tool", "tool_call_id": "call_1", "content": "r1"},
                {"role": "tool", "tool_call_id": "call 2!", "content": ""},
                {"role": "user", "content": "Wrap up now."}]
        p = self.g.translate({"messages": msgs, "tools": TOOLS, "tool_choice": "required", "parallel_tool_calls": False})
        b = p.params
        a = b["messages"][1]
        self.assertEqual([x["type"] for x in a["content"]], ["text", "tool_use", "tool_use"])
        self.assertEqual(a["content"][2]["id"], "call_2_")
        self.assertEqual(a["content"][2]["input"], {"_unparsed_arguments": "not json"})
        u = b["messages"][2]
        self.assertEqual([x["type"] for x in u["content"]], ["tool_result", "tool_result", "text"])
        self.assertEqual(u["content"][1]["tool_use_id"], "call_2_")
        self.assertEqual(u["content"][1]["content"], "(empty result)")
        self.assertIn("forced_tool_choice_sent_as_auto", p.notes)
        self.assertEqual(b["tool_choice"], {"type": "auto", "disable_parallel_tool_use": True})
        self.assertEqual(p.cls, "agent")
        p2 = self.g.translate({"messages": [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "x"}]})
        self.assertEqual(p2.params["messages"][0]["role"], "user")
        self.assertIn("leading_user_inserted", p2.notes)

    def _answer(self, g, plan, blocks):
        class B:
            def __init__(self, d):
                self.__dict__.update(d)
        g.remember(plan, [B(x) for x in blocks])

    def test_thinking_replay_and_compaction(self):
        """The store puts thinking back only where the API's history check would accept it."""
        g = G.Guard(make_cfg(self.d / "r", "http://127.0.0.1:9", self.key, ledger=str(self.d / "l4.json")))
        s, u = {"role": "system", "content": SYS}, {"role": "user", "content": "task"}

        def a(cid, name="web_search", txt=""):
            return {"role": "assistant", "content": txt, "tool_calls": [
                {"id": cid, "type": "function", "function": {"name": name, "arguments": '{"query": "q"}'}}]}

        def t(cid, out="res"):
            return {"role": "tool", "tool_call_id": cid, "content": out}
        r1 = g.translate({"messages": [s, u], "tools": TOOLS})
        self._answer(g, r1, [thinking("s1"), tool_use("t1", "web_search", {"query": "q"})])
        r2 = g.translate({"messages": [s, u, a("t1"), t("t1")], "tools": TOOLS})
        self.assertEqual(r2.params["messages"][1]["content"][0], thinking("s1"))         # replayed verbatim
        self.assertEqual((r2.replayed, r2.stripped), (1, 0))
        self._answer(g, r2, [thinking("s2"), tool_use("t2", "web_search", {"query": "q"})])
        r3 = g.translate({"messages": [s, u, a("t1"), t("t1"), a("t2"), t("t2")], "tools": TOOLS})
        self.assertEqual(r3.replayed, 2)
        self._answer(g, r3, [thinking("s3"), tool_use("t3", "web_search", {"query": "q"})])
        # keep-tail compaction: [task, notes, t2 + t3 kept] -> the kept turns' thinking was made under the old
        # history: stripped; new turns after it keep theirs
        notes = {"role": "user", "content": "[Research notes: ...]"}
        r4 = g.translate({"messages": [s, u, notes, a("t2"), t("t2"), a("t3"), t("t3")], "tools": TOOLS})
        kinds = [[b["type"] for b in m["content"]] for m in r4.params["messages"] if m["role"] == "assistant"]
        self.assertEqual(kinds, [["tool_use"], ["tool_use"]])
        self.assertEqual((r4.replayed, r4.stripped), (0, 2))
        self._answer(g, r4, [thinking("s4"), tool_use("t4", "web_search", {"query": "q"})])
        r5 = g.translate({"messages": [s, u, notes, a("t2"), t("t2"), a("t3"), t("t3"), a("t4"), t("t4")],
                          "tools": TOOLS})
        kinds = [[b["type"] for b in m["content"]] for m in r5.params["messages"] if m["role"] == "assistant"]
        self.assertEqual(kinds, [["tool_use"], ["tool_use"], ["thinking", "tool_use"]])
        # an edit in the middle: t2's result changed -> t3 (after it) stripped, and t4 whose chain went through t3...
        r6 = g.translate({"messages": [s, u, a("t1"), t("t1"), a("t2"), t("t2", "EDITED"), a("t3"), t("t3")],
                          "tools": TOOLS})
        kinds = [[b["type"] for b in m["content"]] for m in r6.params["messages"] if m["role"] == "assistant"]
        self.assertEqual(kinds, [["thinking", "tool_use"], ["thinking", "tool_use"], ["tool_use"]])
        # a leading record missing (a restart / eviction): later blocks whose prefix still matches stay (leading run)
        g.store.by_key.pop("tc:t1")
        r7 = g.translate({"messages": [s, u, a("t1"), t("t1"), a("t2"), t("t2"), a("t3"), t("t3")], "tools": TOOLS})
        kinds = [[b["type"] for b in m["content"]] for m in r7.params["messages"] if m["role"] == "assistant"]
        self.assertEqual(kinds, [["tool_use"], ["thinking", "tool_use"], ["thinking", "tool_use"]])
        # a client that changed the turn's text: not this answer -> its own blocks, no thinking
        r8 = g.translate({"messages": [s, u, a("t1"), t("t1"), a("t2", txt="different"), t("t2")], "tools": TOOLS})
        self.assertIn("store_mismatch", r8.notes)
        # strip mode never sends thinking (and no beta)
        g3 = G.Guard(make_cfg(self.d / "s", "http://127.0.0.1:9", self.key, replay="strip",
                              ledger=str(self.d / "l5.json")))
        self._answer(g3, g3.translate({"messages": [s, u], "tools": TOOLS}), [thinking("x"), tool_use("z1", "web_search", {})])
        r9 = g3.translate({"messages": [s, u, a("z1"), t("z1")], "tools": TOOLS})
        self.assertNotIn("betas", r9.params)
        self.assertNotIn("block_binding", r9.params["thinking"])
        self.assertEqual(r9.params["messages"][1]["content"][0]["type"], "tool_use")

    def test_wrapup_without_tools(self):
        g = self.g
        s, u = {"role": "system", "content": SYS + "wrap"}, {"role": "user", "content": "task-w"}
        hist = [s, u, {"role": "assistant", "content": "", "tool_calls": [
            {"id": "w1", "type": "function", "function": {"name": "web_search", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "w1", "content": "r"}, {"role": "user", "content": "Wrap up."}]
        g.translate({"messages": [s, u], "tools": TOOLS})                       # the conversation had tools
        p = g.translate({"messages": hist})                                     # the wrap-up call drops them
        self.assertEqual([t["name"] for t in p.params["tools"]], ["fetch_page", "web_search"])
        self.assertEqual(p.params["tool_choice"], {"type": "none"})
        self.assertFalse(p.has_tools)
        self.assertEqual(p.cls, "agent")
        p2 = g.translate({"messages": [{"role": "user", "content": "never seen"}] + hist[2:]})
        self.assertIn("tool_blocks_as_text", p2.notes)
        self.assertNotIn("tools", p2.params)
        self.assertTrue(all(b["type"] == "text" for m in p2.params["messages"] for b in m["content"]))

    def test_stage_classification(self):
        """Karl 10-29: which calls are research (held to the research cap) and which are the report stage (may use
        the reserve). Anything not identified is research (the conservative fallback)."""
        g = self.g

        def u(t):
            return {"role": "user", "content": t}

        def call(msgs, **kw):
            p = g.translate({"messages": msgs, **kw})
            return p.cls, p.role, p.stage
        lead_s, sub_s = {"role": "system", "content": LEAD_SYS}, {"role": "system", "content": SUB_SYS}
        tc = {"role": "assistant", "content": "", "tool_calls": [
            {"id": "st1", "type": "function", "function": {"name": "web_search", "arguments": "{}"}}]}
        tr = {"role": "tool", "tool_call_id": "st1", "content": "r"}
        compact, report, verify = (m for _, m in G.CLASS_MARKS)
        cases = {
            "lead": (call([lead_s, u("task")], tools=TOOLS), ("agent", "lead", "research")),
            "lead's last answer (stock: its report)": (call([lead_s, u("task"), tc, tr], tools=TOOLS),
                                                       ("agent", "lead", "research")),
            "lead wrap-up, tools dropped": (call([lead_s, u("task-w2"), tc, tr, u("Wrap up.")]),
                                            ("agent", "lead", "research")),
            "subagent": (call([sub_s, u("subtopic")], tools=TOOLS), ("agent", "sub", "research")),
            "extraction": (call([u(G.EXTRACT_MARK + "\n\npage")]), ("extract", None, "research")),
            "compaction": (call([u(compact + " history")]), ("compact", None, "research")),
            "report section": (call([u(report + " Write one section")]), ("report", None, "report")),
            "verification": (call([u(verify + " claims")]), ("verify", None, "report")),
            "fallback synthesis": (call([u("Synthesize a comprehensive answer to: q\n\nBased on these sources:\n[1] a")]),
                                   ("synth", None, "report")),
            "citation pass": (call([u(G.SYNTH_INNER_MARK + " Include citations ...")]), ("synth", None, "report")),
            "citation pass after an output prefix": (call([u("Respond in German.\n\n" + G.SYNTH_INNER_MARK + " ...")]),
                                                     ("synth", None, "report")),
            "fact check": (call([u("Analyze these sources for factual consistency:\n1. ...")]),
                           ("synth", None, "report")),
            "not identified": (call([u("Please summarise this.")]), ("other", None, "research")),
            "citation words deep inside a page": (call([u("x" * 5000 + G.SYNTH_INNER_MARK)]),
                                                  ("other", None, "research")),
        }
        for what, (got, want) in cases.items():
            self.assertEqual(got, want, what)
        FACTS["call_kinds_classified"] = len(cases)

    def test_marks_match_the_ldr_sources(self):
        """The prompt marks the classification relies on are in the sources the arms run (read only): stock LDR
        1.10.7 (baseline/site) and the installed build with the deep package."""
        stock = WS / "baseline/site/local_deep_research"
        ours = WS / ".venv/lib/python3.12/site-packages/local_deep_research"
        need = {
            "advanced_search_system/strategies/langgraph_agent_strategy.py":
                (G.LEAD_MARK, "You are a focused research assistant", G.SYNTH_START_MARKS[0].rstrip()),
            "citation_handlers/standard_citation_handler.py": (G.SYNTH_INNER_MARK, G.SYNTH_START_MARKS[1]),
            "advanced_search_system/tools/fetch/prompts.py": (G.EXTRACT_MARK,),
        }
        checked = 0
        for root in (stock, ours):
            for rel, marks in need.items():
                f = root / rel
                if not f.exists():
                    self.skipTest(f"{f} not found")
                src = f.read_text(encoding="utf-8")
                for mk in marks:
                    self.assertIn(mk, src, f"{rel} ({root.parent.name})")
                    checked += 1
        prompts = (ours / "deep/prompts.py").read_text(encoding="utf-8")
        for _, mk in G.CLASS_MARKS:
            self.assertIn(mk, prompts)
            checked += 1
        FACTS["prompt_marks_found_in_ldr_sources"] = checked

    def test_cache_rule(self):
        """Karl 10-29: cache_control only on prefixes reused within the run; none on one-shot calls."""
        g = G.Guard(make_cfg(self.d / "c", "http://127.0.0.1:9", self.key, ledger=str(self.d / "l7.json")))

        def u(t):
            return {"role": "user", "content": t}
        compact, report, verify = (m for _, m in G.CLASS_MARKS)
        for one in (G.EXTRACT_MARK + " page", compact + " h", report + " s", verify + " c", G.SYNTH_INNER_MARK):
            p = g.translate({"messages": [u(one)]})
            self.assertEqual((n_markers(p.params), p.cache_why), (0, "one-shot"), one[:40])
        # a system prompt: not cached the first time; once a request with it was answered, its prefix is marked
        sys1 = {"role": "system", "content": "You list the facts in a document. " * 60}
        p1 = g.translate({"messages": [sys1, u("doc 1")]})
        self.assertEqual(n_markers(p1.params), 0)
        g.note_sent(p1)
        p2 = g.translate({"messages": [sys1, u("doc 2")]})
        self.assertEqual((p2.cache_why, p2.cache_head, p2.cache_tail), ("head-seen", "system", False))
        self.assertEqual(p2.params["system"][-1]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", p2.params)
        # an agent loop: its first call (tools) and its continuation carry both breakpoints
        s, t = {"role": "system", "content": SUB_SYS}, u("task-c")
        a1 = g.translate({"messages": [s, t], "tools": TOOLS})
        self.assertEqual((a1.cache_why, a1.cache_head, a1.cache_tail, n_markers(a1.params)), ("tools", "system", True, 2))
        self._answer(g, a1, [thinking("c1"), tool_use("c1t", "web_search", {"query": "q"})])
        hist = [s, t, {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1t", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "q"}'}}]},
                {"role": "tool", "tool_call_id": "c1t", "content": "res"}]
        a2 = g.translate({"messages": hist, "tools": TOOLS})
        self.assertEqual((a2.continues, n_markers(a2.params)), (1, 2))
        # a conversation without tools that continues one of the guard's answers: the tail (no system, no tools)
        c1 = g.translate({"messages": [u("chat start")]})
        self.assertEqual(n_markers(c1.params), 0)
        self._answer(g, c1, [thinking("t1"), text("first answer")])
        c2 = g.translate({"messages": [u("chat start"), {"role": "assistant", "content": "first answer"}, u("more")]})
        self.assertEqual((c2.continues, c2.cache_why, c2.cache_head, c2.cache_tail), (1, "continues", "none", True))
        self.assertEqual(c2.params["cache_control"], {"type": "ephemeral"})
        # a client-edited answer is not ours: no continuation, no cache
        c3 = g.translate({"messages": [u("chat start"), {"role": "assistant", "content": "edited"}, u("more")]})
        self.assertEqual((c3.continues, n_markers(c3.params)), (0, 0))

    def test_report_reserve_ledger(self):
        lp = self.d / "ledger-reserve.json"
        L = G.Ledger(str(lp), "r", "a", run_cap=1.0, total_cap=5.0, agent_cap=None, report_reserve=0.25)
        self.assertAlmostEqual(L.research_cap, 0.75)
        r = L.reserve(0.5, True, research=True)
        L.settle(r["ok"], 0.5, stage="research")
        refused = L.reserve(0.3, True, research=True)                  # 0.5 + 0.3 > 0.75
        self.assertEqual(refused["refuse"]["cap"], "research")
        self.assertEqual(L.reserve(0.3, False, research=True)["refuse"]["cap"], "research")   # tool-less research too
        r = L.reserve(0.25, False, research=True)                      # 0.5 + 0.25 = 0.75: still fits
        L.settle(r["ok"], 0.2, stage="research")
        r = L.reserve(0.3, False, research=False)                      # report stage: 0.7 + 0.3 <= the run cap 1.0
        self.assertIn("ok", r)
        L.settle(r["ok"], 0.3, stage="report")
        self.assertEqual(L.reserve(0.01, False, research=False)["refuse"]["cap"], "run")
        snap = L.snapshot()
        self.assertAlmostEqual(snap["run"]["stage_usd"]["research"], 0.7)
        self.assertAlmostEqual(snap["run"]["stage_usd"]["report"], 0.3)
        L0 = G.Ledger(str(self.d / "ledger-reserve0.json"), "r", "a", 1.0, 5.0, None, report_reserve=0.0)
        self.assertIsNone(L0.research_cap)
        self.assertIn("ok", L0.reserve(0.9, True))                     # reserve 0 = off: the run cap only

    def test_lead_gaps_summary(self):
        """tools/lead_gaps.py on a made-up gap log: counts and the 1h estimate."""
        import lead_gaps as LG
        rates = json.loads(Path(G.DEFAULT_PRICING).read_text())["claude-sonnet-5-5"]
        calls = [{"t": 0.0, "duration_s": 20, "prompt_tokens": 10_000, "cache_read": 0, "cache_write": 10_000},
                 {"t": 100.0, "duration_s": 20, "prompt_tokens": 20_000, "cache_read": 10_000, "cache_write": 10_000},
                 {"t": 500.0, "duration_s": 20, "prompt_tokens": 30_000, "cache_read": 0, "cache_write": 30_000},
                 {"t": 4500.0, "duration_s": 20, "prompt_tokens": 40_000, "cache_read": 0, "cache_write": 40_000}]
        s = LG.summarise(calls, rates)
        self.assertEqual((s["lead_calls"], s["gaps"], s["gaps_over_ttl"], s["gaps_over_1h"], s["idle_over_ttl"]),
                         (4, 3, 2, 1, 2))
        self.assertEqual(s["cold_after_long_gap"], 2)
        self.assertEqual(s["prefix_tokens_rewritten_after_5_60min_gaps"], 20_000)      # the 400 s gap only
        self.assertAlmostEqual(s["est_1h_saves_usd"], 20_000 * (2.5 - 0.2) / 1e6, places=6)
        self.assertAlmostEqual(s["est_1h_costs_usd"], (90_000 - 20_000) * (4.0 - 2.5) / 1e6, places=6)
        f = self.d / "lead-gaps-x.jsonl"
        f.write_text("".join(json.dumps(dict(c, run="x")) + "\n" for c in calls) + "not json\n")
        self.assertEqual(LG.load([str(self.d)])["x"][2]["t"], 500.0)

    def test_upstream_and_key_file(self):
        G.check_upstream("https://api.anthropic.com")
        G.check_upstream("http://127.0.0.1:4321")
        for bad in ("https://api.anthropic.com.evil.example", "http://api.anthropic.com", "https://example.com",
                    "http://10.0.0.5:8080", "https://api.anthropic.com:8443"):
            with self.assertRaises(SystemExit, msg=bad):
                G.check_upstream(bad)
        self.assertEqual(G.read_key(str(self.key)), FAKE_KEY)
        bad = self.d / "badkey"
        bad.write_text("two words\n")
        with self.assertRaises(G.KeyFileError) as cm:
            G.read_key(str(bad))
        self.assertNotIn("two", str(cm.exception))
        with self.assertRaises(G.KeyFileError):
            G.read_key(str(self.d / "missing"))
        loose = self.d / "key-loose"
        write_key(loose, FAKE_KEY)
        loose.chmod(0o644)
        self.assertIn("WARNING", G.key_file_note(str(loose)))
        self.assertNotIn(FAKE_KEY, G.key_file_note(str(loose)))
        self.assertEqual(G.scrub(f"bad key {FAKE_KEY} here"), "bad key sk-ant-[masked] here")

    def test_ledger(self):
        lp = self.d / "ledger-unit.json"
        L = G.Ledger(str(lp), "r1", "a", run_cap=1.0, total_cap=1.5, agent_cap=0.5)
        r = L.reserve(0.4, True)
        self.assertIn("ok", r)
        self.assertIn("wait", L.reserve(0.4, True))          # agent cap: 0 + 0.4 running + 0.4 > 0.5
        L.settle(r["ok"], 0.3, usage={"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 0,
                                      "cache_read_input_tokens": 0})
        self.assertIn("refuse", L.reserve(0.3, True))       # 0.3 + 0.3 > 0.5 (agent) - can never fit
        r2 = L.reserve(0.3, False)                           # without tools the run cap applies
        self.assertIn("ok", r2)
        L.settle(r2["ok"], 0.25, unknown_usd=0.05)
        snap = L.snapshot()
        self.assertAlmostEqual(snap["run"]["spent_usd"], 0.6)
        self.assertAlmostEqual(snap["run"]["charged_unknown_usd"], 0.05)
        L2 = G.Ledger(str(lp), "r2", "b", run_cap=5.0, total_cap=1.5, agent_cap=None)
        self.assertEqual(L2.reserve(1.0, False)["refuse"]["cap"], "total")   # 0.6 + 1.0 > 1.5
        # a reservation of a process that died is charged in full
        st = json.loads(lp.read_text())
        st["inflight"]["dead-1"] = {"run": "r2", "arm": "b", "usd": 0.2, "pid": 2 ** 22 + 12345, "t": 0}
        lp.write_text(json.dumps(st))
        snap = L2.snapshot()
        self.assertAlmostEqual(snap["total_spent_usd"], 0.8)
        self.assertEqual(snap["stale_charged"], 1)
        lp.write_text("{not json")
        with self.assertRaises(G.LedgerError):
            L2.snapshot()

    def test_in_process_environment(self):
        """The guard never puts the key into its environment (in-process server, one request against the mock)."""
        mock = MockAnthropic()
        try:
            cfg = make_cfg(self.d / "ip", mock.url, self.key, ledger=str(self.d / "l6.json"), port=free_port())
            os.environ["ANTHROPIC_API_KEY"] = ENV_KEY
            removed = G.scrub_environment()
            self.assertIn("ANTHROPIC_API_KEY", removed)
            g = G.Guard(cfg)
            srv = G.Server(("127.0.0.1", cfg.port), G.Handler)
            srv.guard = g
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            req = urllib.request.Request(f"http://127.0.0.1:{cfg.port}/v1/chat/completions", data=json.dumps(
                {"messages": [{"role": "user", "content": "hi"}]}).encode(), headers={"Content-Type": "application/json"})
            out = urllib.request.urlopen(req, timeout=20).read().decode()
            BODIES.append(out)
            self.assertEqual(json.loads(out)["choices"][0]["message"]["content"], "ok")
            self.assertEqual(mock.requests[-1]["headers"]["x-api-key"], FAKE_KEY)
            for k, v in os.environ.items():
                for key in ALL_KEYS:
                    self.assertNotIn(key, v, f"key in os.environ[{k}]")
            self.assertNotIn(FAKE_KEY, repr(vars(g)))
            srv.shutdown()
            srv.server_close()
        finally:
            mock.close()


# ============================================================================================ end to end (subprocess)
class T2EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = MockAnthropic()
        cls.key = TMP / "key-e2e"
        write_key(cls.key, FAKE_KEY)
        cls.g = GuardProc("e2e", cls.mock, cls.key, extra=("--default-effort", "high", "--class-efforts",
                                                            "agent=medium,extract=low"))

    @classmethod
    def tearDownClass(cls):
        cls.g.stop()
        cls.mock.close()

    def setUp(self):
        self.mock.clear()

    def test_plain_nonstream(self):
        c = self.g.client()
        n0 = len(self.g.log())
        sys_once = SYS + " (plain test)"                       # a system prompt no other test sends
        r = c.chat.completions.create(model="gpt-whatever", messages=[{"role": "system", "content": sys_once},
                                                                       {"role": "user", "content": "hi"}],
                                      temperature=0.7, max_tokens=1000)
        self.assertEqual(r.choices[0].message.content, "ok")
        self.assertEqual(r.choices[0].finish_reason, "stop")
        q = self.mock.requests[-1]
        b, hd = q["body"], q["headers"]
        self.assertEqual(hd["x-api-key"], FAKE_KEY)                  # the file's key, not ANTHROPIC_API_KEY
        self.assertNotIn("x-test", hd)                              # ANTHROPIC_CUSTOM_HEADERS was dropped
        self.assertIn(G.BETA_BINDING, hd.get("anthropic-beta", ""))
        self.assertTrue(q["path"].startswith("/v1/messages"))
        self.assertTrue(b["stream"])                                # always streamed upstream
        self.assertEqual(b["model"], "claude-sonnet-5-5")
        self.assertEqual(b["max_tokens"], 1000)
        self.assertNotIn("temperature", b)
        self.assertEqual(b["thinking"]["type"], "adaptive")
        self.assertEqual(b["output_config"], {"effort": "high"})   # default effort (class "other")
        # Karl 10-29: a one-shot call is not cached; the same system prompt again: its prefix marker only
        self.assertEqual(n_markers(b), 0)
        c1 = self.g.log_wait(n0 + 1)[-1]["cache"]
        self.assertEqual({k: c1[k] for k in ("ttl", "marker", "auto_tail", "why", "continues")},
                         {"ttl": None, "marker": "none", "auto_tail": False, "why": "one-shot", "continues": 0})
        c.chat.completions.create(model="m", messages=[{"role": "system", "content": sys_once},
                                                       {"role": "user", "content": "another"}], max_tokens=1000)
        b2 = self.mock.requests[-1]["body"]
        self.assertEqual(b2["system"][-1]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", b2)
        self.assertEqual(self.g.log_wait(n0 + 2)[-1]["cache"]["why"], "head-seen")
        self.assertGreater(r.usage.prompt_tokens, 0)
        st = self.g.status()
        self.assertEqual((st["model"], st["cache"], st["arm"]), ("claude-sonnet-5-5", "on", "e2e"))
        models = json.loads(urllib.request.urlopen(self.g.url + "/v1/models", timeout=5).read())
        self.assertEqual(models["data"][0]["id"], "claude-sonnet-5-5")

    def test_stream_text(self):
        c = self.g.client()
        chunks = list(c.chat.completions.create(model="m", messages=[{"role": "user", "content": "hello"}],
                                                stream=True, stream_options={"include_usage": True}))
        txt = "".join(ch.choices[0].delta.content or "" for ch in chunks if ch.choices)
        self.assertEqual(txt, "ok")
        fin = [ch.choices[0].finish_reason for ch in chunks if ch.choices and ch.choices[0].finish_reason]
        self.assertEqual(fin, ["stop"])
        self.assertIsNotNone(chunks[-1].usage)
        self.assertEqual(chunks[-1].choices, [])

    def test_tools_round_trip_and_cache(self):
        c = self.g.client()
        self.mock.push(content=[thinking("sig-A"), text("Let me search."),
                                tool_use("toolu_A1", "web_search", {"query": "EU AI Act GPAI 2026"})])
        msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": "What changed in 2026?"}]
        r1 = c.chat.completions.create(model="m", messages=msgs, tools=TOOLS)
        m1 = r1.choices[0].message
        self.assertEqual(r1.choices[0].finish_reason, "tool_calls")
        self.assertEqual(m1.content, "Let me search.")
        self.assertEqual(m1.tool_calls[0].id, "toolu_A1")
        self.assertEqual(json.loads(m1.tool_calls[0].function.arguments), {"query": "EU AI Act GPAI 2026"})
        b1 = self.mock.requests[-1]["body"]
        self.assertEqual([t["name"] for t in b1["tools"]], ["fetch_page", "web_search"])
        self.assertEqual(b1["output_config"], {"effort": "medium"})       # class agent
        self.mock.push(text="Done: the answer.")
        msgs2 = msgs + [m1.model_dump(exclude_none=True), {"role": "tool", "tool_call_id": "toolu_A1",
                                                           "content": "search results ..."}]
        r2 = c.chat.completions.create(model="m", messages=msgs2, tools=TOOLS)
        self.assertEqual(r2.choices[0].message.content, "Done: the answer.")
        b2 = self.mock.requests[-1]["body"]
        a = b2["messages"][1]
        self.assertEqual(a["content"], [thinking("sig-A"), text("Let me search."),
                                        tool_use("toolu_A1", "web_search", {"query": "EU AI Act GPAI 2026"})])
        self.assertEqual(b2["messages"][2]["content"][0]["type"], "tool_result")
        # the first request's prompt is a byte-identical prefix of the second's (markers aside)
        strip = lambda m: [{k: v for k, v in x.items() if k != "cache_control"} for x in m["content"]]  # noqa: E731
        self.assertEqual(strip(b1["messages"][0]), strip(b2["messages"][0]))
        log = self.g.log()
        u2 = log[-1]["usage"]
        self.assertGreater(u2["cache_read_input_tokens"], 0)                # the mock saw the shared prefix
        self.assertEqual(log[-1]["replay"]["thinking_replayed"], 1)
        FACTS["cache_read_tokens_on_2nd_call"] = u2["cache_read_input_tokens"]
        FACTS["uncached_input_tokens_on_2nd_call"] = u2["input_tokens"] + u2["cache_creation_input_tokens"]

    def test_langchain_streaming_tools(self):
        """LDR's own client: ChatOpenAI(streaming=True).bind_tools(...), a tool round, streamed."""
        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI

        @tool
        def web_search(query: str) -> str:
            """Search the web."""
            return "results"
        llm = ChatOpenAI(model="claude-sonnet-5-5", base_url=self.g.url + "/v1", api_key="unused", streaming=True,
                         temperature=1.0, max_tokens=4000, max_retries=0, timeout=30)
        bound = llm.bind_tools([web_search])
        self.mock.push(content=[thinking("sig-LC"), text("Searching."),
                                tool_use("toolu_LC1", "web_search", {"query": "gpai obligations"})])
        hist = [SystemMessage(SYS), HumanMessage("question")]
        ai = bound.invoke(hist)
        self.assertEqual(ai.tool_calls[0]["name"], "web_search")
        self.assertEqual(ai.tool_calls[0]["args"], {"query": "gpai obligations"})
        self.assertEqual(ai.tool_calls[0]["id"], "toolu_LC1")
        self.assertEqual(ai.content, "Searching.")
        self.mock.push(text="final answer")
        ai2 = bound.invoke(hist + [ai, ToolMessage(content="r", tool_call_id="toolu_LC1")])
        self.assertEqual(ai2.content, "final answer")
        b = self.mock.requests[-1]["body"]
        self.assertEqual(b["messages"][1]["content"][0], thinking("sig-LC"))
        self.assertNotIn("temperature", b)
        self.assertTrue(self.mock.requests[-1]["body"]["stream"])

    def test_effort_e2e(self):
        c = self.g.client()
        for eff, want in (("xhigh", "xhigh"), ("low", "low"), ("minimal", "low")):
            c.chat.completions.create(model="m", messages=[{"role": "user", "content": "q"}], reasoning_effort=eff)
            self.assertEqual(self.mock.requests[-1]["body"]["output_config"], {"effort": want}, eff)
        c.chat.completions.create(model="m", messages=[{"role": "user", "content": G.EXTRACT_MARK + "\npage"}])
        self.assertEqual(self.mock.requests[-1]["body"]["output_config"], {"effort": "low"})
        n = len(self.mock.requests)
        st, body = self.g.post({"messages": [{"role": "user", "content": "q"}], "reasoning_effort": "turbo"})
        self.assertEqual(st, 400)
        self.assertIn("unknown reasoning effort", body["error"]["message"])
        self.assertEqual(len(self.mock.requests), n)                           # nothing sent

    def test_cost_log_exact(self):
        usage = {"input_tokens": 1000, "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 50000,
                 "cache_creation": {"ephemeral_5m_input_tokens": 3000, "ephemeral_1h_input_tokens": 0},
                 "output_tokens": 2000}
        before = self.g.summary()
        self.mock.push(usage=usage)
        st, body = self.g.post({"messages": [{"role": "user", "content": "cost?"}], "max_tokens": 5000})
        self.assertEqual(st, 200)
        want = (1000 * 2 + 3000 * 2.5 + 50000 * 0.2 + 2000 * 10) / 1e6
        rec = self.g.log()[-1]
        self.assertAlmostEqual(rec["cost_usd"], want, places=6)
        self.assertAlmostEqual(body["x_guard"]["cost_usd"], want, places=6)
        self.assertEqual(body["usage"]["prompt_tokens"], 54000)
        self.assertEqual(body["usage"]["prompt_tokens_details"]["cached_tokens"], 50000)
        after = self.g.summary()
        self.assertAlmostEqual(after["run_spent_usd"] - before["run_spent_usd"], want, places=6)
        self.assertEqual(after["tokens"]["cache_read"] - before["tokens"]["cache_read"], 50000)
        self.assertEqual(after["tokens"]["cache_write_5m"] - before["tokens"]["cache_write_5m"], 3000)
        self.assertEqual(after["tokens"]["output"] - before["tokens"]["output"], 2000)
        for k in ("prompt", "messages", "content", "x-api-key", "headers"):
            self.assertNotIn(k, rec)

    def test_key_read_per_request(self):
        write_key(self.key, FAKE_KEY_B)
        try:
            self.g.post({"messages": [{"role": "user", "content": "k"}]})
            self.assertEqual(self.mock.requests[-1]["headers"]["x-api-key"], FAKE_KEY_B)
        finally:
            write_key(self.key, FAKE_KEY)
        self.key.rename(self.key.with_suffix(".away"))
        try:
            spent = self.g.status()["run_spent_usd"]
            n = len(self.mock.requests)
            st, body = self.g.post({"messages": [{"role": "user", "content": "k"}]})
            self.assertEqual(st, 500)
            self.assertIn("key file", body["error"]["message"])
            self.assertEqual(len(self.mock.requests), n)
            self.assertEqual(self.g.status()["run_spent_usd"], spent)
            self.assertEqual(self.g.status()["inflight"], 0)
        finally:
            self.key.with_suffix(".away").rename(self.key)

    def test_upstream_echoes_the_key(self):
        """An upstream error that quotes the key: masked before it reaches the client or the log."""
        self.mock.push(status=401, err_type="authentication_error", err_msg=f"invalid x-api-key {FAKE_KEY}")
        st, body = self.g.post({"messages": [{"role": "user", "content": "x"}]})
        self.assertEqual(st, 401)
        self.assertNotIn(FAKE_KEY, json.dumps(body))
        self.assertIn("[masked]", body["error"]["message"])


class T3Errors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock = MockAnthropic()
        cls.key = TMP / "key-err"
        write_key(cls.key, FAKE_KEY_PLAIN)              # a key that does not look like one: only exact masking helps
        cls.g = GuardProc("err", cls.mock, cls.key, extra=("--upstream-retries", "1"))

    @classmethod
    def tearDownClass(cls):
        cls.g.stop()
        cls.mock.close()

    def setUp(self):
        self.mock.clear()

    def test_retry_then_ok(self):
        self.mock.push(status=429, err_type="rate_limit_error", err_msg="slow down", headers={"retry-after": "0"})
        self.mock.push(text="after retry")
        st, body = self.g.post({"messages": [{"role": "user", "content": "x"}]})
        self.assertEqual((st, body["choices"][0]["message"]["content"]), (200, "after retry"))
        self.assertEqual(len(self.mock.requests), 2)
        self.assertEqual(self.g.log()[-1]["retries"], [429])

    def test_overloaded_exhausted(self):
        self.mock.push(status=529, err_type="overloaded_error", err_msg="Overloaded", headers={"retry-after": "0"})
        self.mock.push(status=529, err_type="overloaded_error", err_msg="Overloaded", headers={"retry-after": "0"})
        st, body = self.g.post({"messages": [{"role": "user", "content": "x"}]})
        self.assertEqual(st, 503)
        self.assertEqual(self.g.log()[-1]["cost_usd"], 0.0)            # an error before any output costs nothing

    def test_refusal(self):
        self.mock.push(content=[text("I can't help with that.")], stop_reason="refusal",
                       stop_details={"type": "refusal", "category": "cyber", "explanation": "declined"})
        st, body = self.g.post({"messages": [{"role": "user", "content": "x"}]})
        self.assertEqual(body["choices"][0]["finish_reason"], "content_filter")
        self.assertEqual(body["choices"][0]["message"]["refusal"], "declined")
        rec = self.g.log()[-1]
        self.assertEqual(rec["refusal_category"], "cyber")
        self.assertGreater(rec["cost_usd"], 0)

    def test_cut_off_stream_is_charged(self):
        from openai import APIError
        self.mock.push(content=[text("partial"), text("never")], fail_after_start=True)
        c = self.g.client()
        got = ""
        with self.assertRaises(APIError):
            for ch in c.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}], stream=True,
                                                max_tokens=100):
                if ch.choices:
                    got += ch.choices[0].delta.content or ""
        self.assertEqual(got, "partial")
        rec = self.g.log()[-1]
        self.assertEqual(rec["event"], "error")
        self.assertIn("usage_estimated", rec)
        self.assertGreaterEqual(rec["cost_usd"], 100 * 10 / 1e6)          # output charged at max_tokens

    def test_signature_400_strip_retry(self):
        s, u = {"role": "system", "content": SYS}, {"role": "user", "content": "sig test"}
        self.mock.push(content=[thinking("sig-S"), tool_use("toolu_S1", "web_search", {"query": "q"})])
        st, b1 = self.g.post({"messages": [s, u], "tools": TOOLS})
        m = b1["choices"][0]["message"]
        self.mock.push(status=400, err_type="invalid_request_error",
                       err_msg="messages.1.content.0: Invalid `signature` in `thinking` block. The block is bound to a "
                               "different conversation.")
        self.mock.push(text="after strip")
        st, b2 = self.g.post({"messages": [s, u, m, {"role": "tool", "tool_call_id": "toolu_S1", "content": "r"}],
                              "tools": TOOLS})
        self.assertEqual((st, b2["choices"][0]["message"]["content"]), (200, "after strip"))
        first, retry = self.mock.requests[-2]["body"], self.mock.requests[-1]["body"]
        self.assertEqual(first["messages"][1]["content"][0]["type"], "thinking")
        self.assertEqual(retry["messages"][1]["content"][0]["type"], "tool_use")
        self.assertNotIn("block_binding", retry["thinking"])
        self.assertIn("strip_retry_after_400", self.g.log()[-1]["notes"])

    def test_upstream_echoes_plain_key(self):
        self.mock.push(status=403, err_type="permission_error", err_msg=f"key {FAKE_KEY_PLAIN} lacks access")
        st, body = self.g.post({"messages": [{"role": "user", "content": "x"}]})
        self.assertEqual(st, 403)
        self.assertNotIn(FAKE_KEY_PLAIN, json.dumps(body))

    def test_input_transformations_logged(self):
        self.mock.push(input_transformations=[{"type": "thinking_dropped", "path": "messages.1.content.0",
                                               "reason": "prefix_binding_mismatch"}])
        self.g.post({"messages": [{"role": "user", "content": "x"}]})
        self.assertEqual(self.g.log()[-1]["input_transformations"], ["thinking_dropped:prefix_binding_mismatch"])

    def test_zz_beta_refused_latches_strip_mode(self):
        self.mock.push(status=400, err_type="invalid_request_error", err_msg="thinking.block_binding: Extra inputs "
                                                                             "are not permitted")
        self.mock.push(text="ok without beta")
        st, body = self.g.post({"messages": [{"role": "user", "content": "x"}]})
        self.assertEqual(st, 200)
        self.g.post({"messages": [{"role": "user", "content": "y"}]})
        last = self.mock.requests[-1]
        self.assertNotIn("anthropic-beta", last["headers"])
        self.assertEqual(self.g.status()["thinking_replay"], "strip")


class T4Caps(unittest.TestCase):
    """Caps: a request is refused (HTTP 402, nothing sent) when spent + its worst case would pass a cap."""
    USAGE = {"input_tokens": 100, "output_tokens": 9000, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    COST = (100 * 2 + 9000 * 10) / 1e6              # 0.0902 per answer

    @classmethod
    def setUpClass(cls):
        cls.mock = MockAnthropic()
        cls.key = TMP / "key-caps"
        write_key(cls.key, FAKE_KEY)
        cls.shared = TMP / "shared-ledger.json"
        cls.procs = []

    @classmethod
    def tearDownClass(cls):
        for p in cls.procs:
            p.stop()
        cls.mock.close()

    def guard(self, name, **kw):
        g = GuardProc(name, self.mock, self.key, **kw)
        self.procs.append(g)
        return g

    def setUp(self):
        self.mock.clear()

    def test_1_run_cap_and_total_cap(self):
        # the run cap alone (these plain calls are research: the report reserve, tested in test_4, is set to 0 here)
        g = self.guard("capc", run_cap=0.5, total_cap=10.0, ledger=self.shared, extra=("--report-reserve", "0"))
        results = []
        for i in range(10):
            self.mock.push(usage=self.USAGE)
            n_before = len(self.mock.requests)
            st, body = g.post({"messages": [{"role": "user", "content": f"q{i}"}], "max_tokens": 10000})
            results.append((st, len(self.mock.requests) - n_before, body))
            if st == 402:
                break
        log = g.log()
        spent = 0.0
        for rec, (st, sent, body) in zip(log, results):
            if spent + rec["worst_usd"] > 0.5:
                self.assertEqual((st, sent, rec["event"]), (402, 0, "refused"))
                self.assertEqual(body["error"]["code"], "run_cap")
                self.assertIn("run cap", body["error"]["message"])
                self.assertIn("nothing was sent", body["error"]["message"])
            else:
                self.assertEqual((st, sent), (200, 1))
                spent += rec["cost_usd"]
        self.assertEqual(results[-1][0], 402)
        self.assertLessEqual(g.status()["run_spent_usd"], 0.5)
        self.assertEqual(g.summary()["refused"], 1)
        FACTS["run_cap_0.50_answers_before_refusal"] = sum(1 for r in results if r[0] == 200)
        # a second arm on the same ledger: the total cap counts the first arm's spending
        g2 = self.guard("capd", run_cap=5.0, total_cap=0.5, ledger=self.shared)
        n = len(self.mock.requests)
        st, body = g2.post({"messages": [{"role": "user", "content": "x"}], "max_tokens": 10000})
        self.assertEqual((st, body["error"]["code"]), (402, "total_cap"))
        self.assertIn("total cap", body["error"]["message"])
        self.assertEqual(len(self.mock.requests), n)

    def test_2_agent_cap(self):
        g = self.guard("cape", run_cap=10.0, total_cap=10.0, extra=("--agent-cap-usd", "0.15"))
        self.mock.push(usage=self.USAGE)
        st, _ = g.post({"messages": [{"role": "user", "content": "a"}], "tools": TOOLS, "max_tokens": 10000})
        self.assertEqual(st, 200)
        n = len(self.mock.requests)
        st, body = g.post({"messages": [{"role": "user", "content": "b"}], "tools": TOOLS, "max_tokens": 10000})
        self.assertEqual((st, body["error"]["code"]), (402, "agent_cap"))
        self.assertEqual(len(self.mock.requests), n)
        self.mock.push(usage=self.USAGE)
        st, _ = g.post({"messages": [{"role": "user", "content": "report"}], "max_tokens": 10000})
        self.assertEqual(st, 200)                       # tool-less (report stage) goes on to the run cap

    def test_3_waits_for_running_requests(self):
        g = self.guard("capf", run_cap=0.2, total_cap=10.0, extra=("--report-reserve", "0"))   # the run cap alone
        self.mock.push(usage=self.USAGE, delay_s=1.5)
        self.mock.push(usage=self.USAGE)
        out = {}

        def first():
            out["a"] = g.post({"messages": [{"role": "user", "content": "slow"}], "max_tokens": 10000})
        th = threading.Thread(target=first)
        th.start()
        time.sleep(0.4)
        out["b"] = g.post({"messages": [{"role": "user", "content": "second"}], "max_tokens": 10000})
        th.join()
        self.assertEqual((out["a"][0], out["b"][0]), (200, 200))
        rec_b = [r for r in g.log() if r.get("waited_s", 0) > 0]
        self.assertTrue(rec_b and rec_b[0]["waited_s"] >= 0.5, g.log())
        st, body = g.post({"messages": [{"role": "user", "content": "third"}], "max_tokens": 10000})
        self.assertEqual(st, 402)
        self.assertLessEqual(g.status()["run_spent_usd"], 0.2)

    def test_4_report_reserve(self):
        """Karl 10-29: research is refused ("cap reached") at (1 - 0.22) x the run cap; the report stage goes on to
        the whole run cap. The default reserve (0.22) - no flag."""
        g = self.guard("capr", run_cap=0.5, total_cap=10.0)
        research_cap = 0.5 * (1 - 0.22)
        small = {"input_tokens": 100, "output_tokens": 1500, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0}

        def lead(i):
            return {"messages": [{"role": "system", "content": LEAD_SYS}, {"role": "user", "content": f"task {i}"}],
                    "tools": TOOLS, "max_tokens": 10000}
        spent, ok = 0.0, 0
        for i in range(12):                                         # the lead (research) until the research cap
            self.mock.push(usage=self.USAGE)
            n = len(self.mock.requests)
            st, body = g.post(lead(i))
            rec = g.log_wait(i + 1)[-1]
            if spent + rec["worst_usd"] > research_cap:
                self.assertEqual((st, len(self.mock.requests) - n, rec["event"], rec["stage"]),
                                 (402, 0, "refused", "research"))
                self.assertEqual(body["error"]["code"], "research_cap")
                for words in ("cap reached", "research cap", "report stage", "nothing was sent"):
                    self.assertIn(words, body["error"]["message"])
                break
            self.assertEqual((st, len(self.mock.requests) - n), (200, 1))
            spent += rec["cost_usd"]
            ok += 1
        self.mock.clear()
        self.assertGreaterEqual(ok, 2)
        self.assertLessEqual(spent, research_cap)
        FACTS["reserve_0.22_of_0.50_research_answers_before_refusal"] = ok
        n = len(self.mock.requests)
        st, body = g.post({"messages": [{"role": "user", "content": "unidentified tool-less call"}],
                           "max_tokens": 10000})
        self.assertEqual((st, body["error"]["code"], len(self.mock.requests)), (402, "research_cap", n))   # fallback
        compact, report, verify = (m for _, m in G.CLASS_MARKS)
        for what in (report + " Write one section.", verify + " Check the claims.",
                     G.SYNTH_INNER_MARK + " Include citations.", "Synthesize a comprehensive answer to: q"):
            self.mock.push(usage=small)
            st, body = g.post({"messages": [{"role": "user", "content": what}], "max_tokens": 2000})
            self.assertEqual(st, 200, what[:40])                     # the report stage uses the reserve
        st, body = g.post(lead(99))                                  # research stays refused
        self.assertEqual((st, body["error"]["code"]), (402, "research_cap"))
        spent_now = g.status()["run_spent_usd"]
        self.assertGreater(spent_now, research_cap)                  # the reserve was spent - by the report stage
        n = len(self.mock.requests)
        st, body = g.post({"messages": [{"role": "user", "content": report + " last"}], "max_tokens": 10000})
        self.assertEqual((st, body["error"]["code"], len(self.mock.requests)), (402, "run_cap", n))
        s = g.summary()
        self.assertAlmostEqual(s["caps_usd"]["research"], research_cap)
        self.assertAlmostEqual(s["stage_spent_usd"]["research"], spent, places=6)
        self.assertAlmostEqual(s["stage_spent_usd"]["report"], spent_now - spent, places=6)
        self.assertLessEqual(spent_now, 0.5)


# ============================================================================================ launcher wiring
def bash(script: str, env_extra: dict | None = None, timeout=60) -> subprocess.CompletedProcess:
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")}
    env.update(env_extra or {})
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=timeout)


class T5Launcher(unittest.TestCase):
    def test_syntax(self):
        for f in ("run-ldr.sh", "c4-arm.sh"):
            r = subprocess.run(["bash", "-n", str(C4 / f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def _top(self, src: Path, ws: Path) -> Path:
        """The script up to its command dispatch, with WS pointing at a scratch folder (nothing live is touched)."""
        t = src.read_text()
        cut = t.rindex("\ncase ${1:-} in")
        t = t[:cut].replace("WS=/home/USER/ai/deep-research", f"WS={ws}", 1)
        out = TMP / f"top-{src.parent.name}-{src.name}"
        out.write_text(t)
        return out

    def test_strata_mode_unchanged(self):
        """With LDR_BACKEND unset, the staged copy exports exactly what C3's run-ldr.sh exports."""
        ws = TMP / "ws"
        ws.mkdir(exist_ok=True)
        pv = ("P_FILE=/x/flash-next.env P_MODEL=m P_STATUS=measured P_CONTEXT=131072 P_MAX_TOKENS=30000 "
              "P_TEMPERATURE=1.0 P_WORKERS=1 P_QUICK_ITERATIONS=12 P_TOKENIZER_DIR=/x/tok")
        outs = {}
        for name, src in (("c3", C3 / "run-ldr.sh"), ("c4", C4 / "run-ldr.sh")):
            top = self._top(src, ws)
            for case, extra in (("deep", {}), ("baseline", {"LDR_PROFILE": "baseline"}),
                                ("noproxy", {"LDR_VIA_PROXY": "0"}), ("quick+s2", {"LDR_QUICK_LIMITS": "1",
                                                                                   "LDR_RESEARCH_S2": "1"})):
                r = bash(f"source {top}; {pv}; (ldr_env served-model; env | grep -E '^(LDR_|PYTHONPATH=|TMPDIR=|XDG_|"
                         f"CUDA_)' | sort)", extra)
                self.assertEqual(r.returncode, 0, r.stderr)
                outs[(name, case)] = r.stdout
        for case in ("deep", "baseline", "noproxy", "quick+s2"):
            self.assertEqual(outs[("c3", case)], outs[("c4", case)], case)
            self.assertIn("LDR_LLM_OPENAI_ENDPOINT_URL=http://127.0.0.1:", outs[("c4", case)])

    def _guard_env(self, extra=None):
        arm = TMP / "arm-ours"
        env = {"LDR_BACKEND": "guard", "C4_ARM_DIR": str(arm), "GUARD_URL": "http://127.0.0.1:8191",
               "C4_LDR_PORT": "5011", "LDR_MODEL_PROFILE": "sonnet-5-5", "LDR_ALLOW_DRAFT_PROFILE": "1",
               "LDR_DEEP_PKG": str(C3 / "deep"), "LDR_PROFILES_DIR": str(C3 / "profiles")}
        env.update(extra or {})
        return arm, env

    def test_guard_mode_env(self):
        arm, env = self._guard_env()
        r = bash(f"{C4 / 'run-ldr.sh'} env", env)
        self.assertEqual(r.returncode, 0, r.stderr)
        e = dict(x.split("=", 1) for x in r.stdout.splitlines() if "=" in x)
        self.assertEqual(e["LDR_LLM_OPENAI_ENDPOINT_URL"], "http://127.0.0.1:8191/v1")
        self.assertEqual(e["LDR_LLM_MODEL"], "claude-sonnet-5-5")
        self.assertEqual(e["LDR_WEB_PORT"], "5011")
        self.assertEqual(e["LDR_DATA_DIR"], str(arm / "data"))
        self.assertEqual(e["LDR_DEEP_OUT_DIR"], str(arm / "deep-runs"))
        self.assertEqual(e["LDR_DEEP_CLOCK_FILE"], str(arm / "run/research-clock.json"))
        self.assertEqual(e["LDR_DEEP_NEXT_FILE"], str(arm / "run/next-research.json"))
        self.assertEqual(e["LDR_LLM_CONTEXT_WINDOW_SIZE"], "1000000")
        self.assertEqual(e["LDR_LLM_MAX_TOKENS"], "64000")
        self.assertEqual(e["LDR_LANGGRAPH_AGENT_MAX_SUBAGENT_WORKERS"], "4")
        self.assertTrue(e["LDR_DEEP_MODEL_PROFILE"].endswith("sonnet-5-5.env"))
        self.assertFalse(arm.exists(), "env must not create folders")
        for v in e.values():
            for live in ("/deep-research/run/", "/deep-research/data", "results/deep-runs"):
                self.assertNotIn(live, v + "/")
        FACTS["guard_mode_env_vars"] = len(e)

    def test_guard_mode_refusals(self):
        cases = {"live run dir": {"C4_ARM_DIR": str(WS / "run/c4")}, "live port": {"C4_LDR_PORT": "5000"},
                 "remote guard": {"GUARD_URL": "http://10.1.2.3:8191"}, "workspace": {"C4_ARM_DIR": str(WS)}}
        for what, extra in cases.items():
            arm, env = self._guard_env(extra)
            r = bash(f"{C4 / 'run-ldr.sh'} env", env)
            self.assertNotEqual(r.returncode, 0, what)
        arm, env = self._guard_env({"LDR_ALLOW_DRAFT_PROFILE": "0"})
        r = bash(f"{C4 / 'run-ldr.sh'} env", env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("draft", r.stderr)
        r = bash(f"{C4 / 'run-ldr.sh'} env", {})                      # strata mode has no env command
        self.assertNotEqual(r.returncode, 0)

    def test_c4_arm_plan(self):
        key = TMP / "key-launcher"
        write_key(key, FAKE_KEY)
        env = {"C4_ROOT": str(TMP / "c4root"), "C4_ALLOW_DRAFT": "1", "LDR_DEEP_PKG": str(C3 / "deep"),
               "LDR_PROFILES_DIR": str(C3 / "profiles"), "GUARD_KEY_FILE": str(key)}
        r = bash(f"{C4 / 'c4-arm.sh'} plan ours", env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("run o03-ours,", r.stdout)
        self.assertIn("LDR_LLM_OPENAI_ENDPOINT_URL=http://127.0.0.1:8191/v1", r.stdout)
        self.assertIn("LDR_DEEP_FIX=all", r.stdout)
        self.assertNotIn(FAKE_KEY, r.stdout + r.stderr)
        # Karl 10-29: effort high, the reserve, 5m with the lead's 1 h off
        self.assertIn("research stops at $31.20 (report reserve 0.22)", r.stdout)
        self.assertIn("efforts default high, class agent=high,extract=low", r.stdout)
        self.assertIn("ttl 5m, lead 1h 0", r.stdout)
        r = bash(f"{C4 / 'c4-arm.sh'} plan ours", dict(env, C4_RUN_SUFFIX="pilot", GUARD_RUN_CAP_USD="3"))
        self.assertIn("run o03-ours-pilot,", r.stdout)
        self.assertIn("caps run $3,", r.stdout)
        self.assertIn("research stops at $2.34", r.stdout)
        for bad in ({"GUARD_REPORT_RESERVE": "1.5"}, {"GUARD_REPORT_RESERVE": "x"}, {"GUARD_CACHE_TTL": "1h"},
                    {"GUARD_LEAD_CACHE_1H": "2"}):
            r = bash(f"{C4 / 'c4-arm.sh'} plan ours", dict(env, **bad))
            self.assertNotEqual(r.returncode, 0, bad)
        r = bash(f"{C4 / 'c4-arm.sh'} plan ours", {k: v for k, v in env.items() if k != "C4_ALLOW_DRAFT"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("draft", r.stderr)
        r = bash(f"{C4 / 'c4-arm.sh'} plan stock", dict(env, STOCK_VENV=str(TMP / "no-venv")))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stock arm's own venv is not built", r.stderr)
        r = bash(f"{C4 / 'c4-arm.sh'} plan stock", dict(env, C4_STOCK_MODE="baseline-site"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PYTHONPATH=/home/USER/ai/deep-research/baseline/site", r.stdout)
        self.assertNotIn("LDR_DEEP=1", r.stdout)
        self.assertIn("research stops at $9.36 (report reserve 0.22)", r.stdout)
        self.assertIn("efforts default high, class -", r.stdout)
        r = bash(f"{C4 / 'c4-arm.sh'} plan ours", dict(env, C4_ROOT=str(WS / "run/c4")))
        self.assertNotEqual(r.returncode, 0)
        r = bash(f"{C4 / 'c4-arm.sh'} plan ours", dict(env, GUARD_RUN_CAP_USD="80"))
        self.assertNotEqual(r.returncode, 0)                           # run cap above the $60 total
        self.assertFalse((TMP / "c4root").exists(), "plan must not create folders")

    def test_arm_files_reach_the_guard(self):
        """Karl 10-29 in both arm files, as the guard reads them (c4-arm.sh sources the file with set -a)."""
        want_class = {"ours": {"agent": "high", "extract": "low"}, "stock": {}}
        for arm in ("ours", "stock"):
            r = bash(f"set -a; source {C4 / 'arms' / (arm + '.env')}; set +a; {PY} -I -B -c '"
                     f"import sys, json; sys.path.insert(0, \"{C4 / 'tools'}\"); import anthropic_guard as G; "
                     "c = G.parse_args([\"--ledger\", \"/nonexistent/l.json\", \"--log-dir\", \"/nonexistent/d\"]); "
                     "print(json.dumps([c.default_effort, c.class_efforts, c.report_reserve, c.cache_ttl, "
                     "c.lead_cache_1h, c.run_cap]))'", {"GUARD_KEY_FILE": str(TMP / "no-key-here")})
            self.assertEqual(r.returncode, 0, r.stderr)
            eff, cls, reserve, ttl, lead1h, cap = json.loads(r.stdout)
            self.assertEqual((eff, cls, reserve, ttl, lead1h), ("high", want_class[arm], 0.22, "5m", False), arm)
            FACTS[f"{arm}_research_cap_usd"] = round(cap * (1 - reserve), 2)


# ============================================================================================ caching rule, lead TTL, gaps
class T7LeadCache(unittest.TestCase):
    """Karl 10-29 through the guard process: no cache_control on one-shot calls, both breakpoints on the agent loops,
    5m everywhere by default, 1h on the lead only with the switch, and the lead's gap log + its summary."""

    @classmethod
    def setUpClass(cls):
        cls.mock = MockAnthropic()
        cls.key = TMP / "key-lead"
        write_key(cls.key, FAKE_KEY)
        cls.g5 = GuardProc("lead5m", cls.mock, cls.key)                              # the default: switch off
        cls.g1 = GuardProc("lead1h", cls.mock, cls.key, extra=("--lead-cache-1h", "1"))

    @classmethod
    def tearDownClass(cls):
        cls.g5.stop()
        cls.g1.stop()
        cls.mock.close()

    def setUp(self):
        self.mock.clear()

    def _loop(self, g, sys_text, task, pause_s=0.0):
        """An agent loop of two calls: a tool call, then the answer after the tool result. Returns both bodies."""
        s, u = {"role": "system", "content": sys_text}, {"role": "user", "content": task}
        cid = "toolu_" + re.sub(r"\W", "_", task)
        self.mock.push(content=[thinking("sig-" + cid), tool_use(cid, "web_search", {"query": task})])
        st, b1 = g.post({"messages": [s, u], "tools": TOOLS})
        self.assertEqual(st, 200)
        body1 = self.mock.requests[-1]["body"]
        time.sleep(pause_s)
        m = b1["choices"][0]["message"]
        st, _ = g.post({"messages": [s, u, m, {"role": "tool", "tool_call_id": cid, "content": "results"}],
                        "tools": TOOLS})
        self.assertEqual(st, 200)
        return body1, self.mock.requests[-1]["body"]

    def test_default_5m_and_one_shot_calls(self):
        g = self.g5
        n0 = len(g.log())
        lead1, lead2 = self._loop(g, LEAD_SYS, "lead task")
        for b in (lead1, lead2):                                    # the lead: both breakpoints, 5 minutes
            self.assertEqual(b["system"][-1]["cache_control"], {"type": "ephemeral"})
            self.assertEqual(b["cache_control"], {"type": "ephemeral"})
        sub1, sub2 = self._loop(g, SUB_SYS, "sub task")
        self.assertEqual((n_markers(sub1), n_markers(sub2)), (2, 2))
        log = g.log_wait(n0 + 4)
        self.assertGreater(log[-1]["usage"]["cache_read_input_tokens"], 0)      # the subagent's 2nd call read its 1st
        self.assertEqual([r["role"] for r in log[n0:n0 + 4]], ["lead", "lead", "sub", "sub"])
        compact, report, verify = (m for _, m in G.CLASS_MARKS)
        for one in (G.EXTRACT_MARK + "\n\npage", compact + " h", report + " section", verify + " claims",
                    G.SYNTH_INNER_MARK + " cite"):
            st, _ = g.post({"messages": [{"role": "user", "content": one}], "max_tokens": 2000})
            self.assertEqual(st, 200)
            self.assertEqual(n_markers(self.mock.requests[-1]["body"]), 0, one[:30])
        log = g.log_wait(n0 + 9)
        self.assertEqual({r["cache"]["why"] for r in log[n0 + 4:n0 + 9]}, {"one-shot"})
        self.assertEqual(g.summary()["tokens"]["cache_write_1h"], 0)
        self.assertEqual(len(g.gaps()), 2)                          # lead calls only

    def test_lead_1h_switch_gap_log_and_summary(self):
        g = self.g1
        n0 = len(g.log())
        lead1, lead2 = self._loop(g, LEAD_SYS, "lead task 1h", pause_s=1.2)
        for b in (lead1, lead2):                                    # the lead: 1 hour on both breakpoints
            self.assertEqual(b["system"][-1]["cache_control"], {"type": "ephemeral", "ttl": "1h"})
            self.assertEqual(b["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        sub1, _ = self._loop(g, SUB_SYS, "sub task 1h")            # a subagent stays at 5 minutes
        self.assertEqual(sub1["system"][-1]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(sub1["cache_control"], {"type": "ephemeral"})
        st, _ = g.post({"messages": [{"role": "user", "content": G.EXTRACT_MARK + " page"}]})
        self.assertEqual(n_markers(self.mock.requests[-1]["body"]), 0)  # one-shot: none, switch or not
        log = g.log_wait(n0 + 5)
        self.assertEqual([r["cache"]["ttl"] for r in log[n0:n0 + 5]], ["1h", "1h", "5m", "5m", None])
        self.assertGreater(g.summary()["tokens"]["cache_write_1h"], 0)          # priced at the 1h write rate
        # the gap log: the two lead calls, times and counts only
        gaps = g.gaps()
        self.assertEqual(len(gaps), 2)
        self.assertIsNone(gaps[0]["gap_s"])
        self.assertGreaterEqual(gaps[1]["gap_s"], 1.2)
        self.assertGreaterEqual(gaps[1]["idle_s"], 1.1)
        self.assertEqual({k for x in gaps for k in x}, {"t", "id", "run", "arm", "gap_s", "idle_s", "duration_s",
                                                       "ttl", "cache_tail", "event", "n_msgs", "prompt_tokens",
                                                       "cache_read", "cache_write"})
        raw = (g.dir / "log" / "lead-gaps-run-lead1h.jsonl").read_text()
        for secret in ("Research.", "lead task", G.LEAD_MARK, "results"):
            self.assertNotIn(secret, raw)
        # the summary script, with a 1-second "lifetime" so the test need not wait 5 minutes
        r = subprocess.run([PY, "-I", "-B", str(C4 / "tools/lead_gaps.py"), str(g.dir / "log"), "--ttl-s", "1",
                            "--json"], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads(r.stdout)["run-lead1h"]
        self.assertEqual((s["lead_calls"], s["gaps"], s["gaps_over_ttl"], s["gaps_over_1h"]), (2, 1, 1, 0))
        r = subprocess.run([PY, "-I", "-B", str(C4 / "tools/lead_gaps.py"), str(g.dir / "log")],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("over 5 min: 0", r.stdout)                    # the real 5-minute threshold
        self.assertIn("Karl decides", r.stdout)
        FACTS["lead_gap_s_measured_in_test"] = gaps[1]["gap_s"]


# ============================================================================================ keys never written
class T6NoKeyAnywhere(unittest.TestCase):
    def test_no_key_in_any_file_or_answer(self):
        hits = []
        for p in TMP.rglob("*"):
            if not p.is_file() or p.name.startswith("key") or p.suffix == ".away":
                continue
            data = p.read_bytes()
            for k in ALL_KEYS:
                if k.encode() in data:
                    hits.append((str(p.relative_to(TMP)), k[:14]))
        for b in BODIES:
            for k in ALL_KEYS:
                if k in b:
                    hits.append(("response body", k[:14]))
        self.assertEqual(hits, [])
        FACTS["files_checked_for_keys"] = sum(1 for p in TMP.rglob("*") if p.is_file())
        FACTS["response_bodies_checked"] = len(BODIES)


# ============================================================================================ runner
class Recorder(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = []
        self._t = {}

    def startTest(self, test):
        self._t[test.id()] = time.time()
        super().startTest(test)

    def _row(self, test, status, detail=""):
        self.rows.append({"test": test.id().split(".", 1)[-1], "status": status,
                          "seconds": round(time.time() - self._t.get(test.id(), time.time()), 2),
                          "detail": detail[-2000:]})

    def addSuccess(self, test):
        super().addSuccess(test)
        self._row(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._row(test, "FAIL", "".join(traceback.format_exception(*err)))

    def addError(self, test, err):
        super().addError(test, err)
        self._row(test, "ERROR", "".join(traceback.format_exception(*err)))


def main() -> int:
    t0 = time.time()
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (T1Units, T2EndToEnd, T3Errors, T4Caps, T5Launcher, T7LeadCache, T6NoKeyAnywhere):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2, resultclass=Recorder)
    res = runner.run(suite)
    rows = res.rows
    ok = sum(r["status"] == "pass" for r in rows)
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    meta = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(time.time() - t0, 1), "passed": ok,
            "total": len(rows), "python": sys.version.split()[0], "facts": FACTS}
    try:
        import anthropic
        import openai
        meta["anthropic_sdk"], meta["openai_sdk"] = anthropic.__version__, openai.__version__
    except ImportError:
        pass
    (out / "results.json").write_text(json.dumps({"meta": meta, "tests": rows}, indent=1) + "\n")
    md = [f"# C4 offline tests - {ok} / {len(rows)} pass ({meta['when']}, {meta['seconds']} s)", "",
          f"anthropic SDK {meta.get('anthropic_sdk')}, openai SDK {meta.get('openai_sdk')}, Python {meta['python']}. "
          "Upstream = tests/mock_anthropic.py on 127.0.0.1; fake keys only.", "", "| test | result | s |", "|---|---|---|"]
    md += [f"| {r['test']} | {r['status']} | {r['seconds']} |" for r in rows]
    md += ["", "Facts:", ""] + [f"- {k}: {v}" for k, v in FACTS.items()]
    bad = [r for r in rows if r["status"] != "pass"]
    if bad:
        md += ["", "## Failures", ""] + [f"### {r['test']}\n```\n{r['detail']}\n```" for r in bad]
    (out / "results.md").write_text("\n".join(md) + "\n")
    if os.environ.get("C4_TEST_KEEP") != "1":
        shutil.rmtree(TMP, ignore_errors=True)
    else:
        print(f"kept {TMP}")
    return 0 if res.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
