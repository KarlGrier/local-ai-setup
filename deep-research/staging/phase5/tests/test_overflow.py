#!/usr/bin/env python3
"""Offline tests for staging/phase5/overflow.py (Karl 11-07 context-overflow flags) - synthetic run folders only, written
under P5_TEST_TMP (default staging/phase5/tests/scratch); no model, service, GPU or network.

    P5_TEST_TMP=/home/USER/ai/deep-research/staging/phase5/tests/scratch \
      nice -n 19 /home/USER/ai/deep-research/.venv/bin/python -I -B /home/USER/ai/deep-research/staging/phase5/tests/test_overflow.py
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("overflow_t", HERE.parent / "overflow.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)
TMP = Path(tempfile.mkdtemp(prefix="ovtest-", dir=os.environ.get("P5_TEST_TMP", str(HERE / "scratch"))))
REF = "Error code: 400 - {'error': {'message': 'request exceeds the context window: prompt (%d tokens) leaves no room'}}"


def mkrun(name, logs, statuses=(200,), bench=None):
    r = TMP / "runs" / "set-baseline-p5" / name
    r.mkdir(parents=True)
    (r / "research-logs.json").write_text(json.dumps(logs))
    (r / "calls.jsonl").write_text("".join(json.dumps({"status": s}) + "\n" for s in statuses))
    (r / "bench.json").write_text(json.dumps(bench or {"rc": 0}))
    return r


class Overflow(unittest.TestCase):
    def setUp(self):
        self.flags = TMP / f"flags-{self._testMethodName}.json"
        self.flags.write_text(json.dumps({"flags": {}}))
        ov.FLAGS = self.flags

    def test_clean(self):
        r = mkrun("c1", [{"log_type": "INFO", "message": "fine"}])
        self.assertIsNone(ov.overflow(r))
        self.assertEqual(ov.flags(r)[0], [])

    def test_near_window_only_is_not_an_overflow(self):
        r = mkrun("c2", [{"log_type": "WARNING", "message": "Context overflow detected [provider-confirmed] prompt_tokens=105381"}])
        self.assertIsNone(ov.overflow(r))

    def test_one_refusal_logged_twice_counts_once(self):
        r = mkrun("c3", [{"log_type": "WARNING", "message": "LLM Request - Failed with error: " + REF % 131155},
                         {"log_type": "ERROR", "message": "[OpenAIInvalidRequestError: " + REF % 131155 + "] LangGraph agent"},
                         {"log_type": "DEBUG", "message": "exception details " + REF % 131155},
                         {"log_type": "WARNING", "message": "LLM Request - Failed with error: " + REF % 218650},
                         {"log_type": "WARNING", "message": "Citation handler failed, using raw agent answer (query 'x')"}],
                  statuses=(200, 400, 200, 400))
        c = ov.overflow(r)
        self.assertEqual((c["refused"], c["raw_fallback"], c["http_400"]), (2, True, 2))
        self.assertEqual(ov.flags(r)[0], ["context overflow (kind not yet checked)"])

    def test_noted_kind_and_search_trip(self):
        r = mkrun("c4", [{"log_type": "WARNING", "message": "Citation handler failed, using raw agent answer (q)"}],
                  bench={"rc": 0, "search_trip": {"at": "x"}})
        self.flags.write_text(json.dumps({"flags": {"set-baseline-p5/c4": {"flag": "context overflow: cut-off answer"}}}))
        self.assertEqual(ov.flags(r)[0], ["search trip, end check passed", "context overflow: cut-off answer"])

    def test_real_phase5_runs(self):
        ov.FLAGS = ov.WS / "results" / "bench2" / "p5-run-flags.json"
        base = ov.RUNS / "holdout-baseline-p5"
        if not (base / "o06").exists():
            self.skipTest("Phase 5 runs not present")
        self.assertEqual(ov.flags(base / "o04")[0], ["context overflow: cut-off answer"])
        self.assertEqual(ov.flags(base / "o05")[0], [])
        self.assertEqual(ov.flags(base / "o06")[0], ["context overflow: snippet fallback"])
        self.assertEqual(ov.overflow(base / "o06")["refused"], ov.overflow(base / "o06")["http_400"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
