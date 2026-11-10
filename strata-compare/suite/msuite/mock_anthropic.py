"""An offline stand-in for the Anthropic SDK client, to test the Claude code path (batches, streaming, caching
fan-out, the agentic loop, cost tracking) without a key and without sending anything."""
from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace as NS


class _Obj(NS):
    def model_dump(self, exclude_none=False):
        d = {}
        for k, v in vars(self).items():
            if exclude_none and v is None:
                continue
            d[k] = v.model_dump(exclude_none) if isinstance(v, _Obj) else v
        return d


def _usage(inp, out, cw=0, cr=0):
    return _Obj(input_tokens=inp, output_tokens=out, cache_creation_input_tokens=cw, cache_read_input_tokens=cr,
                cache_creation=None)


def _text(params):
    msgs = params["messages"]
    last = msgs[-1]["content"]
    if isinstance(last, list):
        return " ".join(b.get("text", "") or json.dumps(b.get("content", "")) for b in last)
    return last


class _Stream:
    def __init__(self, client, params):
        self.client, self.params = client, params

    def __enter__(self):
        self.msg = self.client._answer(self.params)
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        yield _Obj(type="message_start")
        for b in self.msg.content:
            yield _Obj(type="content_block_delta", delta=_Obj(text=getattr(b, "text", None) or getattr(b, "thinking", None)
                                                               or json.dumps(getattr(b, "input", {}))))
        yield _Obj(type="message_stop")

    def get_final_message(self):
        return self.msg


def _model_info(mid, adaptive=False):
    """A real SDK ModelInfo (anthropic.types, built the way the client builds responses: nested pydantic objects, not
    dicts), so the backend's Models API parsing is tested as it runs against the API."""
    from anthropic.types import ModelInfo
    yes, no = {"supported": True}, {"supported": False}
    return ModelInfo.construct(**{
        "id": mid, "type": "model", "display_name": "Mock", "created_at": "2026-01-01T00:00:00Z", "lifecycle": "active",
        "max_input_tokens": 1_000_000, "max_tokens": 64000,
        "capabilities": {"batch": yes, "citations": yes, "code_execution": no, "image_input": yes, "pdf_input": yes,
                         "structured_outputs": yes,
                         "thinking": {"supported": True, "types": {"enabled": yes, "adaptive": yes if adaptive else no,
                                                                   "disabled": yes}},
                         "effort": {"supported": True, "low": yes, "medium": yes, "high": yes, "xhigh": no,
                                    "max": no}}})


class MockClient:
    def __init__(self):
        self.lock = threading.Lock()
        self.cached = set()
        self.calls = []
        self.models = _Obj(retrieve=_model_info)
        self.batches_store = {}
        self.messages = _Obj(stream=lambda **p: _Stream(self, p), count_tokens=self._count,
                             batches=_Obj(create=self._bcreate, retrieve=self._bretrieve, results=self._bresults))

    def _count(self, model, messages):
        return _Obj(input_tokens=len(json.dumps(messages)) // 4 + 3)

    def _answer(self, p):
        with self.lock:
            self.calls.append(p)
        assert p.get("thinking", {}).get("type") in ("enabled", "adaptive")
        assert "temperature" not in p
        txt = _text(p)
        blocks = [_Obj(type="thinking", thinking="mock reasoning", signature="sig")]
        stop = "end_turn"
        usage = _usage(len(txt) // 4, 120)
        if p.get("tools"):
            names = [t["name"] for t in p["tools"]]
            if "run_tests" in names:
                n_tool_results = sum(1 for m in p["messages"] if m["role"] == "user" and isinstance(m["content"], list))
                if n_tool_results == 0:
                    blocks.append(_Obj(type="tool_use", id="toolu_1", name="run_tests", input={}))
                    stop = "tool_use"
                else:
                    blocks.append(_Obj(type="text", text="Done."))
            elif "get_weather" in names and "Lisbon" in txt:
                blocks.append(_Obj(type="tool_use", id="toolu_2", name="get_weather",
                                   input={"city": "Lisbon", "unit": "fahrenheit"}))
                stop = "tool_use"
            else:
                blocks.append(_Obj(type="text", text="No tool needed."))
        else:
            blocks.append(_Obj(type="text", text="Some answer.\nANSWER: 53"))
        content = p["messages"][-1]["content"]
        if isinstance(content, list) and content and content[0].get("cache_control"):
            key = content[0]["text"][:200]
            with self.lock:
                if key in self.cached:
                    usage = _usage(30, 200, 0, len(content[0]["text"]) // 4)
                else:
                    self.cached.add(key)
                    usage = _usage(30, 200, len(content[0]["text"]) // 4, 0)
        return _Obj(content=blocks, usage=usage, stop_reason=stop, stop_details=None)

    def _bcreate(self, requests):
        bid = f"msgbatch_{len(self.batches_store)}"
        self.batches_store[bid] = [(r["custom_id"], self._answer(r["params"])) for r in requests]
        return _Obj(id=bid, processing_status="in_progress")

    def _bretrieve(self, bid):
        n = len(self.batches_store[bid])
        return _Obj(id=bid, processing_status="ended",
                    request_counts=_Obj(processing=0, succeeded=n, errored=0, canceled=0, expired=0))

    def _bresults(self, bid):
        for cid, msg in self.batches_store[bid]:
            yield _Obj(custom_id=cid, result=_Obj(type="succeeded", message=msg))


def make_backend(model="claude-opus-4-5-20251101", hard_stop=40.0):
    """An AnthropicBackend wired to the mock client (bypasses the key file)."""
    from . import backend_anthropic as BA
    b = BA.AnthropicBackend.__new__(BA.AnthropicBackend)
    b.anthropic = None
    b.client = MockClient()
    b.model = model
    # the same code path as AnthropicBackend.__init__, on an SDK ModelInfo object (pydantic, as the real API returns)
    b.models_api, b.max_out, b.ctx, b.thinking, b.effort = BA.settings_from_model_info(b.client.models.retrieve(model))
    b.cost = BA.CostTracker(model, hard_stop, 0.0)
    b._overhead = None
    return b


def selftest():
    """Run the Claude path end to end on the mock (single-turn batch, long-context fan-out, one agentic repo)."""
    import shutil
    from argparse import Namespace
    from .common import RESULTS, read_json
    from . import runner
    label = "zz-mock-claude-selftest"
    d = RESULTS / label
    shutil.rmtree(d, ignore_errors=True)
    out = []
    try:
        b = make_backend()
        items = [i for i in runner.load_items(["math", "tools", "longctx", "agentic"])
                 if i["id"] in ("math/m01", "tools/t01_weather_unit", "tools/t04_no_tool_poem", "agentic/a1_inventory")
                 or i["category"] == "longctx" and i["doc"].endswith("doc_a.txt")]
        meta = {}
        args = Namespace(label=label, batch_chunk=2)
        runner.run_claude(args, b, items, 1, lambda m: None, meta)
        grades = runner.grade_label(label, log=lambda m: None, render=False)
        out.append(("claude path (mock): thinking from the Models API (Opus 4.5 style: budget, effort high)",
                    b.thinking == {"type": "enabled", "budget_tokens": 48000} and b.effort == "high", str(b.thinking)))
        out.append(("claude path (mock): every item answered and graded", len(grades) == len(items), f"{len(grades)}/{len(items)}"))
        g = {k.split("#")[0]: v for k, v in grades.items()}
        out.append(("claude path (mock): batch answer graded (math m01 = 53)", g["math/m01"]["solved"] is True, g["math/m01"]["detail"]))
        out.append(("claude path (mock): tool_use blocks graded", g["tools/t01_weather_unit"]["solved"] is True
                    and g["tools/t04_no_tool_poem"]["solved"] is True, ""))
        recs = [read_json(p) for p in (d / "answers" / "longctx").glob("*.json")]
        writes = sum(1 for r in recs if (r["response"]["usage"].get("cache_creation_input_tokens") or 0) > 0)
        reads = sum(1 for r in recs if (r["response"]["usage"].get("cache_read_input_tokens") or 0) > 0)
        out.append(("claude path (mock): long-context doc written to the cache once, read by the other two",
                    writes == 1 and reads == 2, f"writes {writes}, reads {reads}"))
        ag = read_json(d / "answers" / "agentic" / "a1_inventory.r0.json")
        out.append(("claude path (mock): agentic loop ran run_tests then stopped; thinking blocks passed back",
                    ag["n_steps"] == 2 and ag["stop"].startswith("no tool call")
                    and any(m["role"] == "assistant" and isinstance(m["content"], list) and m["content"][0]["type"] == "thinking"
                            for m in b.client.calls[-1]["messages"]), ag["stop"]))
        spent = b.cost.spent
        out.append(("claude path (mock): cost tracked from reported usage (batch at half price)", spent > 0, f"${spent:.4f}"))
        out.append(("claude path (mock): the pending batch file is removed once the answers are saved",
                    not (d / "pending_batch.json").exists(), ""))
        # 2026-10-12: a batch submitted by a run that died before saving its answers is re-attached, not paid twice
        pend = d / "pending_batch.json"
        b3 = make_backend()
        reqs = [("math__m01#0", b3.params(runner.messages_for(items[0])[0]))]
        r1 = b3.run_batch(reqs, log=lambda m: None, resume_path=pend)
        n1 = len(b3.client.batches_store)
        r2 = b3.run_batch(reqs, log=lambda m: None, resume_path=pend)
        out.append(("claude path (mock): a pending batch is re-attached, not submitted again",
                    n1 == 1 and len(b3.client.batches_store) == 1 and r2["_batch"]["id"] == r1["_batch"]["id"]
                    and "error" not in r2.get("math__m01#0", {"error": 1}), f"{len(b3.client.batches_store)} batch(es)"))
        pend.unlink(missing_ok=True)
        b2 = make_backend(hard_stop=0.000001)
        b2.cost.spent = 0.00001
        args2 = Namespace(label=label + "-stop", batch_chunk=2)
        meta2 = {}
        runner.run_claude(args2, b2, items[:1], 1, lambda m: None, meta2)
        out.append(("claude path (mock): hard stop prevents further requests", "hard stop" in meta2.get("stopped", "")
                    and not b2.client.calls, meta2.get("stopped", "")))
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(RESULTS / (label + "-stop"), ignore_errors=True)
    return out
