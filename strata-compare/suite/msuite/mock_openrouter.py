"""An offline stand-in for openrouter.ai on 127.0.0.1, to test the OpenRouter path end to end (endpoint choice,
provider pinning, auth header, a 429 retry, streamed reasoning / tool calls / usage with cost, cost tracking, the
hard stop, a provider switch, collect-only then finish) without a key and without sending anything anywhere."""
from __future__ import annotations

import json
import shutil
import threading
from argparse import Namespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FAKE_KEY = "sk-or-v1-" + "ab" * 32
MODEL = {"id": "qwen/qwen3.8-flash", "name": "Qwen: Qwen3.8 Flash", "hugging_face_id": "Qwen/Qwen3.8-Flash-Next",
         "context_length": 1000000, "supported_parameters": ["reasoning", "tools", "top_k", "temperature", "top_p"],
         "pricing": {"prompt": "0.00000015", "completion": "0.00000047"}}
ENDPOINTS = [
    {"provider_name": "LowPrec", "tag": "lowprec/fp4", "quantization": "fp4", "context_length": 262144,
     "max_completion_tokens": 65536, "supported_parameters": ["reasoning", "tools", "top_k", "min_p", "temperature", "top_p"],
     "pricing": {"prompt": "0.0000001", "completion": "0.0000003"}},
    {"provider_name": "Alibaba", "tag": "alibaba/bf16", "quantization": "bf16", "context_length": 1000000,
     "max_completion_tokens": 131072, "supported_parameters": ["reasoning", "tools", "top_k", "temperature", "top_p"],
     "pricing": {"prompt": "0.00000015", "completion": "0.00000047"}},
]


class _State:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests = []
        self.first_429 = True
        self.switch_provider = False
        self.problems = []


def make_server():
    st = _State()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/api/v1/models":
                return self._json(200, {"data": [MODEL]})
            if self.path == "/api/v1/models/qwen/qwen3.8-flash/endpoints":
                return self._json(200, {"data": {"id": MODEL["id"], "endpoints": ENDPOINTS}})
            return self._json(404, {"error": {"message": "not found"}})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            with st.lock:
                st.requests.append({"headers": dict(self.headers), "body": body})
                if self.headers.get("Authorization") != "Bearer " + FAKE_KEY:
                    st.problems.append("bad auth header")
                prov = body.get("provider") or {}
                if prov.get("order") != ["alibaba/bf16"] or prov.get("only") != ["alibaba/bf16"] or prov.get("allow_fallbacks") is not False:
                    st.problems.append(f"provider not pinned: {prov}")
                if body.get("reasoning") != {"effort": "xhigh"} or body.get("usage") != {"include": True}:
                    st.problems.append("reasoning / usage fields")
                for k, v in (("temperature", 1.0), ("top_p", 0.95), ("top_k", 20), ("min_p", 0.05)):
                    if body.get(k) != v:
                        st.problems.append(f"sampling {k}")
                if st.first_429:
                    st.first_429 = False
                    return self._json(429, {"error": {"code": 429, "message": "rate limited"}})
                provider = "OtherHost" if st.switch_provider else "Alibaba"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            last = body["messages"][-1]
            text = last["content"] if isinstance(last["content"], str) else json.dumps(last["content"])
            tools = [t["function"]["name"] for t in body.get("tools") or []]
            chunks = [{"id": "gen-1", "provider": provider, "model": "qwen/qwen3.8-flash",
                       "choices": [{"index": 0, "delta": {"role": "assistant", "reasoning": "Let me think. "}}]}]
            finish = "stop"
            if "run_tests" in tools:
                if any(m.get("role") == "tool" for m in body["messages"]):
                    chunks.append({"choices": [{"index": 0, "delta": {"content": "All green."}}]})
                else:
                    chunks.append({"choices": [{"index": 0, "delta": {"tool_calls": [
                        {"index": 0, "id": "call_1", "type": "function", "function": {"name": "run_tests", "arguments": "{}"}}]}}]})
                    finish = "tool_calls"
            elif "get_weather" in tools and "Lisbon" in text:
                chunks.append({"choices": [{"index": 0, "delta": {"tool_calls": [
                    {"index": 0, "id": "call_w", "type": "function",
                     "function": {"name": "get_weather", "arguments": "{\"city\": \"Lisbon\", "}}]}}]})
                chunks.append({"choices": [{"index": 0, "delta": {"tool_calls": [
                    {"index": 0, "function": {"arguments": "\"unit\": \"fahrenheit\"}"}}]}}]})
                finish = "tool_calls"
            elif tools:
                chunks.append({"choices": [{"index": 0, "delta": {"content": "No tool needed here."}}]})
            else:
                chunks.append({"choices": [{"index": 0, "delta": {"content": "Some work.\nANSWER: 53"}}]})
            chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                           "usage": {"prompt_tokens": 100, "completion_tokens": 40,
                                     "completion_tokens_details": {"reasoning_tokens": 30}, "cost": 0.0012}})
            for c in chunks:
                self.wfile.write(b": OPENROUTER PROCESSING\n\n")
                self.wfile.write(b"data: " + json.dumps(c).encode() + b"\n\n")
            self.wfile.write(b"data: [DONE]\n\n")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, st


def selftest():
    from .common import RESULTS, TMP, read_json
    from . import backend_openrouter as BOR, privacy, runner
    out = []
    srv, st = make_server()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/v1"
    kdir = TMP / "mock-or"
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / "fake.key").write_text(FAKE_KEY)
    label = "zz-mock-openrouter-selftest"
    shutil.rmtree(RESULTS / label, ignore_errors=True)
    BOR.RETRY_DELAY_S = 0.05
    try:
        b = BOR.OpenRouterBackend("qwen/qwen3.8-flash", hard_stop=15.0, key_path=kdir / "fake.key", base=base)
        out.append(("openrouter (mock): highest published precision pinned (bf16 over fp4), min_p recorded as ignored",
                    b.slug == "alibaba/bf16" and b.ignored == ["min_p"] and "top_k" in b.honoured, f"{b.slug} {b.ignored}"))
        items = [i for i in runner.load_items(["math", "tools", "longctx", "agentic"])
                 if i["id"] in ("math/m01", "tools/t01_weather_unit", "tools/t04_no_tool_poem", "longctx/la_count",
                                "agentic/a1_inventory")]
        meta = {}
        collect = [i for i in items if not i.get("agentic")]          # what --collect-only sends
        runner.run_openrouter(Namespace(label=label, concurrency=3), b, collect, 1, lambda m: None, meta)
        ans = sorted((RESULTS / label / "answers").rglob("*.json"))
        out.append(("openrouter (mock): collect-only saved the 4 single-turn answers, no agentic item",
                    len(ans) == 4 and not (RESULTS / label / "answers" / "agentic").exists(), f"{len(ans)} answers"))
        recs = [read_json(p) for p in ans]
        out.append(("openrouter (mock): provider and cost recorded on every answer; reasoning tokens from usage",
                    all(r["response"].get("provider") == "Alibaba" and r.get("cost_usd") == 0.0012
                        and r["tokens"]["method"] == "usage" and r["tokens"]["reasoning"] == 30 for r in recs), ""))
        out.append(("openrouter (mock): request pinned, authorised, xhigh, sampling sent; the 429 was retried",
                    not st.problems and len(st.requests) >= 5, "; ".join(st.problems[:3])))
        runner.run_openrouter(Namespace(label=label, concurrency=3), b, items, 1, lambda m: None, meta)
        g = runner.grade_label(label, log=lambda m: None, render=False)
        gg = {k.split("#")[0]: v for k, v in g.items()}
        out.append(("openrouter (mock): the second pass ran only the agentic loop, then everything graded",
                    len(g) == 5 and gg["agentic/a1_inventory"]["n_steps"] == 2 and gg["math/m01"]["solved"]
                    and gg["tools/t01_weather_unit"]["solved"], f"{len(g)} grades"))
        ag = read_json(RESULTS / label / "answers" / "agentic" / "a1_inventory.r0.json")
        out.append(("openrouter (mock): the agentic loop records the provider of every step",
                    all(x.get("provider") == "Alibaba" for x in ag["steps"]) and ag["response"]["meta"]["provider"] == "Alibaba",
                    str([x.get("provider") for x in ag["steps"]])))
        out.append(("openrouter (mock): cost added up from the reported usage", abs(b.spent - 0.0012 * len(st.requests[1:])) < 1e-9,
                    f"${b.spent:.4f} for {len(st.requests) - 1} answered requests"))
        leaks = privacy.check_paths([RESULTS / label])
        raw = any(FAKE_KEY in p.read_text(errors="replace") for p in (RESULTS / label).rglob("*") if p.is_file())
        out.append(("openrouter (mock): the key appears nowhere in the results", not raw and not leaks, "; ".join(leaks)[:200]))
        b2 = BOR.OpenRouterBackend("qwen/qwen3.8-flash", hard_stop=0.01, key_path=kdir / "fake.key", base=base)
        n0 = len(st.requests)
        meta2 = {}
        runner.run_openrouter(Namespace(label=label + "-stop", concurrency=2), b2, collect, 1, lambda m: None, meta2)
        out.append(("openrouter (mock): hard stop: nothing sent when a request's worst case would pass it",
                    "hard stop" in meta2.get("stopped", "") and len(st.requests) == n0, meta2.get("stopped", "")[:120]))
        st.switch_provider = True
        b3 = BOR.OpenRouterBackend("qwen/qwen3.8-flash", hard_stop=15.0, key_path=kdir / "fake.key", base=base)
        meta3 = {}
        runner.run_openrouter(Namespace(label=label + "-switch", concurrency=1), b3, collect[:2], 1, lambda m: None, meta3)
        saved = list((RESULTS / (label + "-switch")).rglob("*.json")) if (RESULTS / (label + "-switch")).exists() else []
        out.append(("openrouter (mock): a response from another provider stops the run and is not saved",
                    "OtherHost" in meta3.get("stopped", "") and not [p for p in saved if "answers" in str(p)],
                    meta3.get("stopped", "")[:120]))
    finally:
        srv.shutdown()
        for suffix in ("", "-stop", "-switch"):
            shutil.rmtree(RESULTS / (label + suffix), ignore_errors=True)
        shutil.rmtree(kdir, ignore_errors=True)
    return out
