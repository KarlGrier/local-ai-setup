"""test_model_mismatch.py - the model-mismatch guard (Karl 11-06). Run from a patched tree's root:
    python -B -m serve.test_model_mismatch
No GPU, no port but an ephemeral one on 127.0.0.1, no real engine: MockEngine, as serve/test_server.py."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from serve.test_server import ByteTokenizer, MockEngine, CTX, ROOT, _Reached
from serve.server import ChatTemplate, Service, serve

QWEN = "strata-qwen3.8-flash-next-iq3s"
DS = "deepseek-v4.1-flash"
MSG = "DeepSeek isn't running - use the 'Switch to DeepSeek' desktop icon"


class Counting(MockEngine):
    """counts what reaches the engine: a refused request must not"""
    calls = 0

    def generate(self, *a, **k):
        type(self).calls += 1
        return super().generate(*a, **k)


class Base(unittest.TestCase):
    guard = {DS: MSG}

    def setUp(self):
        tok = ByteTokenizer()
        self.svc = Service(MockEngine(tok, "ok", max_context=CTX), tok, ChatTemplate(ROOT / "serve/chat_template.jinja"), model_name=QWEN)
        self.svc.not_running = dict(self.guard)
        self.httpd = serve(self.svc, port=0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.headers.get("Content-Type", ""), e.read()

    def chat(self, model=None, **extra):
        body = {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 4, **extra}
        if model is not None:
            body["model"] = model
        return self.post("/v1/chat/completions", body)


class TheOtherModel(Base):
    def test_chat_gets_the_clear_error(self):
        code, ctype, raw = self.chat(DS)
        d = json.loads(raw)
        self.assertEqual(code, 400)
        self.assertIn("json", ctype)
        self.assertEqual(d["error"]["message"], MSG)
        self.assertEqual(d["error"]["code"], "model_not_running")

    def test_streaming_gets_it_too_not_an_event_stream(self):
        code, ctype, raw = self.chat(DS, stream=True)
        self.assertEqual(code, 400)
        self.assertNotIn("event-stream", ctype)
        self.assertEqual(json.loads(raw)["error"]["message"], MSG)

    def test_anthropic_dialect(self):
        code, _, raw = self.post("/v1/messages", {"model": DS, "max_tokens": 4, "messages": [{"role": "user", "content": "hi"}]})
        d = json.loads(raw)
        self.assertEqual(code, 400)
        self.assertEqual(d["type"], "error")
        self.assertEqual(d["error"]["message"], MSG)

    def test_responses_dialect(self):
        code, _, raw = self.post("/v1/responses", {"model": DS, "input": "hi"})
        self.assertEqual(code, 400)
        self.assertIn(MSG, raw.decode())

    def test_refusals_never_use_up_the_admission_slots(self):
        for _ in range(300):
            self.assertEqual(self.chat(DS)[0], 400)
        self.assertEqual(self.chat(QWEN)[0], 200)

    def test_it_never_reaches_the_engine(self):
        generated = []
        real = self.svc.run

        def spy(*a, **k):
            generated.append(1)
            return real(*a, **k)
        with mock.patch.object(self.svc, "run", spy):
            self.assertEqual(self.chat(DS)[0], 400)
            self.assertEqual(generated, [])
            self.assertEqual(self.chat(QWEN)[0], 200)
            self.assertEqual(generated, [1])


class EveryOtherName(Base):
    """LDR, the bench client and every other tool that sends its own name: served exactly as before"""

    def test_own_name_no_name_and_foreign_names(self):
        for name in (QWEN, None, "strata", "x", "gpt-4o", "DeepSeek-V4.1-Flash", "deepseek-v4.1-flash ", "", "local-model"):
            code, _, raw = self.chat(name)
            self.assertEqual(code, 200, repr(name))
            self.assertEqual(json.loads(raw)["object"], "chat.completion", repr(name))

    def test_a_model_that_is_not_a_string_does_not_crash_the_check(self):
        for name in ([DS], {"id": DS}, 7):
            self.assertIn(self.chat(name)[0], (200, 400), repr(name))
            self.assertEqual(self.chat(QWEN)[0], 200)

    def test_other_routes_untouched(self):
        with urllib.request.urlopen(self.base + "/v1/models", timeout=10) as r:
            self.assertEqual([m["id"] for m in json.loads(r.read())["data"]], [QWEN])
        with urllib.request.urlopen(self.base + "/health", timeout=10) as r:
            self.assertEqual(r.status, 200)


class NoConfigKey(Base):
    """every test config and the rollback: no key, no check - the old behaviour, the other name is served"""
    guard = {}

    def test_served_as_before(self):
        self.assertEqual(self.chat(DS)[0], 200)
        self.assertEqual(self.chat("x")[0], 200)


class TheOtherWay(Base):
    """the DeepSeek server's side: Qwen's id is refused, its own name is served"""
    guard = {QWEN: "Qwen isn't running - use the 'Back to Qwen' desktop icon"}

    def test_it(self):
        self.svc.model = DS
        code, _, raw = self.chat(QWEN)
        self.assertEqual(code, 400)
        self.assertIn("Back to Qwen", json.loads(raw)["error"]["message"])
        self.assertEqual(self.chat(DS)[0], 200)
        self.assertEqual(self.chat("strata")[0], 200)


class ThroughMain(unittest.TestCase):
    """the real startup: the config key reaches the service, a bad value is ignored, and the server says so"""

    def run_main(self, cfg):
        import serve.server as S
        seen = {}

        def fake_serve(svc, host=None, port=None):
            seen["guard"] = dict(svc.not_running)
            raise _Reached
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ), mock.patch.object(S, "serve", fake_serve), mock.patch.object(sys, "stdout", new=out):
            os.environ.pop("STRATA_API_KEY", None)
            p = Path(d) / "cfg.json"
            p.write_text(json.dumps(cfg), encoding="utf-8")
            with mock.patch.object(sys, "argv", ["server.py", "--engine", "mock", "--port", "0", "--config", str(p)]):
                try:
                    S.main()
                except _Reached:
                    pass
        return seen.get("guard"), out.getvalue()

    def test_the_key(self):
        guard, out = self.run_main({"model_not_running": {DS: MSG, "bad": 7, "empty": ""}})
        self.assertEqual(guard, {DS: MSG})
        self.assertIn(f"requests naming {DS} get a clear error", out)

    def test_no_key(self):
        guard, out = self.run_main({})
        self.assertEqual(guard, {})
        self.assertNotIn("get a clear error", out)


class RealClient(Base):
    """the OpenAI client (what LDR's langchain and most tools use): it surfaces the text and does not retry a 400"""

    def test_openai_client(self):
        try:
            import openai
        except ImportError:
            self.skipTest("openai is not in this Python")
        hits = []
        real = self.httpd.RequestHandlerClass.do_POST

        def counted(handler):
            hits.append(handler.path)
            return real(handler)
        with mock.patch.object(self.httpd.RequestHandlerClass, "do_POST", counted):
            c = openai.OpenAI(base_url=self.base + "/v1", api_key="none", max_retries=3)
            with self.assertRaises(openai.BadRequestError) as e:
                c.chat.completions.create(model=DS, messages=[{"role": "user", "content": "hi"}], max_tokens=4)
            self.assertIn(MSG, str(e.exception))
            self.assertEqual(len(hits), 1, "a refused request must not be retried")
            r = c.chat.completions.create(model="strata", messages=[{"role": "user", "content": "hi"}], max_tokens=4)
            self.assertTrue(r.choices)


if __name__ == "__main__":
    unittest.main()
