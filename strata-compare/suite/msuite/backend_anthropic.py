"""Claude models through the Anthropic API (official SDK), for the suite's test prompts only.

* The key is read from ~/.config/model-suite/anthropic.key and handed straight to the SDK client.  It is never
  printed, logged, written anywhere or put into an environment variable.
* Thinking / effort: each model's highest setting as the Models API reports it (adaptive thinking where supported,
  else extended thinking with the largest budget that leaves room for the answer; the highest supported effort).
* Single-turn items go through the Message Batches API (50 % price); agentic loops and long-context items stream
  (long-context documents are prompt-cached).
* Cost: every response's reported usage is priced and added up; the run stops at the hard limit (default $40).
"""
from __future__ import annotations

import json
import re
import time

from .common import KEY_FILE

# Published prices, $ per million tokens (base input, output).  Cache writes cost 1.25x input (5-minute TTL) or 2x
# (1-hour), cache reads 0.1x input; the Batch API halves everything.  Source: Anthropic's pricing table as cached in
# the claude-api reference (2026-10-06); Opus 4.5's is its published launch price.
PRICES = {
    "claude-opus-4-6": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-5": (5.00, 25.00),
    "claude-opus-4-5-20251101": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),          # the user's figure, 2026-10-13
}
CACHE_WRITE_5M, CACHE_WRITE_1H, CACHE_READ, BATCH = 1.25, 2.0, 0.10, 0.5
EFFORT_ORDER = ["max", "xhigh", "high", "medium", "low"]
ANSWER_ROOM = 16000          # tokens kept for the visible answer when a model needs an explicit thinking budget


class BudgetExceeded(RuntimeError):
    pass


class NoKey(RuntimeError):
    pass


def price_of(model: str):
    if model in PRICES:
        return PRICES[model]
    base = re.sub(r"-\d{8}$", "", model)
    if base in PRICES:
        return PRICES[base]
    raise SystemExit(f"no published price known for {model}; add it to PRICES in msuite/backend_anthropic.py")


def usage_cost(model: str, usage: dict, batch: bool = False) -> float:
    pin, pout = price_of(model)
    u = usage or {}
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens") or 0
    w5m = cc.get("ephemeral_5m_input_tokens")
    if w5m is None:
        w5m = max(0, (u.get("cache_creation_input_tokens") or 0) - w1h)
    cost = ((u.get("input_tokens") or 0) * pin + w5m * pin * CACHE_WRITE_5M + w1h * pin * CACHE_WRITE_1H
            + (u.get("cache_read_input_tokens") or 0) * pin * CACHE_READ + (u.get("output_tokens") or 0) * pout) / 1e6
    return cost * (BATCH if batch else 1.0)


class CostTracker:
    def __init__(self, model: str, hard_stop: float, spent: float = 0.0):
        self.model, self.hard_stop, self.spent = model, hard_stop, spent
        self.calls = 0

    def add(self, usage: dict, batch: bool = False) -> float:
        c = usage_cost(self.model, usage, batch)
        self.spent += c
        self.calls += 1
        return c

    def check(self, upcoming: float = 0.0):
        if self.spent + upcoming >= self.hard_stop:
            raise BudgetExceeded(f"spent ${self.spent:.2f} + next ~${upcoming:.2f} reaches the ${self.hard_stop:.2f} "
                                 f"hard stop")


def _load_key() -> str:
    if not KEY_FILE.exists():
        raise NoKey(f"{KEY_FILE} is missing")
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        raise NoKey(f"{KEY_FILE} is empty")
    return key


def settings_from_model_info(info):
    """The Models API's answer -> (models_api record, max output tokens, context, thinking, effort): adaptive thinking
    when the model accepts it, else an explicit budget; the highest effort level the model supports.  The SDK returns
    `capabilities` as pydantic objects (ModelCapabilities), so they are dumped to plain dicts first (2026-10-12: the
    first real run failed on `.get` here; the mock had handed in dicts)."""
    caps = getattr(info, "capabilities", None)
    if hasattr(caps, "model_dump"):
        caps = caps.model_dump(exclude_none=True)
    caps = caps if isinstance(caps, dict) else {}
    models_api = {"id": info.id, "display_name": getattr(info, "display_name", None),
                  "max_input_tokens": getattr(info, "max_input_tokens", None),
                  "max_tokens": getattr(info, "max_tokens", None),
                  "thinking": caps.get("thinking"), "effort": caps.get("effort")}
    max_out = int(models_api["max_tokens"] or 64000)
    ctx = int(models_api["max_input_tokens"] or 200000)
    th = (caps.get("thinking") or {}).get("types") or {}
    if (th.get("adaptive") or {}).get("supported"):
        thinking = {"type": "adaptive"}
    else:
        thinking = {"type": "enabled", "budget_tokens": max(1024, max_out - ANSWER_ROOM)}
    eff = caps.get("effort") or {}
    effort = next((lv for lv in EFFORT_ORDER if (eff.get(lv) or {}).get("supported")), None) \
        if eff.get("supported") else None
    return models_api, max_out, ctx, thinking, effort


def _block_dicts(content) -> list[dict]:
    out = []
    for b in content:
        d = b.model_dump(exclude_none=True) if hasattr(b, "model_dump") else dict(b)
        out.append(d)
    return out


class AnthropicBackend:
    kind = "anthropic"

    def __init__(self, model: str, hard_stop: float = 40.0, spent: float = 0.0, max_tokens: int | None = None,
                 effort: str | None = None):
        import anthropic                                   # only needed for Claude runs
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=_load_key(), max_retries=4, timeout=3600)
        self.model = model
        price_of(model)
        self.models_api, self.max_out, self.ctx, self.thinking, self.effort = \
            settings_from_model_info(self.client.models.retrieve(model))
        if max_tokens:                                     # 2026-10-27: the same room as a local run (--max-tokens)
            self.max_out = min(self.max_out, int(max_tokens))
        if effort:                                         # 2026-10-29: a pinned level (--claude-effort), if supported
            lv = (self.models_api.get("effort") or {}).get(effort)
            if not (isinstance(lv, dict) and lv.get("supported")):
                raise SystemExit(f"{model} does not support effort {effort!r}; nothing was sent")
            self.effort = effort
        self.cost = CostTracker(model, hard_stop, spent)
        self._overhead = None

    def describe(self) -> dict:
        return {"kind": "anthropic", "model": self.model, "models_api": self.models_api, "thinking": self.thinking,
                "effort": self.effort, "max_tokens": self.max_out, "hard_stop_usd": self.cost.hard_stop,
                "sampling": "API defaults (temperature 1.0; thinking does not allow changing it)"}

    # -------------------------------------------------------------------------------------------- requests
    def params(self, messages: list, tools: list | None = None, max_tokens: int | None = None,
               cache_auto: bool = False) -> dict:
        p = {"model": self.model, "max_tokens": min(max_tokens or self.max_out, self.max_out),
             "messages": messages, "thinking": dict(self.thinking)}
        if self.thinking["type"] == "enabled":
            p["thinking"]["budget_tokens"] = min(p["thinking"]["budget_tokens"], p["max_tokens"] - 1024)
        if self.effort:
            p["output_config"] = {"effort": self.effort}
        if tools:
            p["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                           "input_schema": t["parameters"]} for t in tools]
        if cache_auto:
            p["cache_control"] = {"type": "ephemeral"}
        return p

    def answer_tokens(self, text: str) -> tuple[int | None, str]:
        """Visible-answer tokens via the free count_tokens endpoint (minus a one-word message's overhead)."""
        if not text:
            return 0, "count_tokens"
        try:
            if self._overhead is None:
                self._overhead = self.client.messages.count_tokens(
                    model=self.model, messages=[{"role": "user", "content": "x"}]).input_tokens - 1
            n = self.client.messages.count_tokens(model=self.model,
                                                  messages=[{"role": "user", "content": text}]).input_tokens
            return max(0, n - self._overhead), "count_tokens"
        except Exception:
            return round(len(text) / 3.6), "estimate"

    def record_from_message(self, msg, wall=None, ttft=None, batch=False, aborted=None) -> dict:
        blocks = _block_dicts(msg.content) if msg is not None else []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        think = "\n".join(b.get("thinking", "") for b in blocks if b.get("type") == "thinking")
        calls = [{"id": b["id"], "name": b["name"], "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}
                 for b in blocks if b.get("type") == "tool_use"]
        usage = msg.usage.model_dump(exclude_none=True) if msg is not None else {}
        cost = self.cost.add(usage, batch=batch) if msg is not None else 0.0
        out = usage.get("output_tokens")
        ans, meth = self.answer_tokens(text + "".join(c["name"] + c["arguments"] for c in calls))
        if out is not None and ans is not None:
            ans = min(ans, out)
        stop = msg.stop_reason if msg is not None else aborted
        prompt = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                 "cache_read_input_tokens"))
        return {
            "response": {"content": text, "reasoning": think, "reasoning_is_summary": True, "tool_calls": calls,
                         "finish_reason": stop, "usage": usage, "blocks": blocks,
                         "stop_details": (msg.stop_details.model_dump() if getattr(msg, "stop_details", None) else None)},
            "cut_off": stop == "max_tokens" or bool(aborted),
            "tokens": {"prompt": prompt, "completion": out, "reasoning": (out - ans) if out is not None else None,
                       "answer": ans, "method": meth, "cached_prompt": usage.get("cache_read_input_tokens")},
            "timing": {"wall_s": round(wall, 2) if wall is not None else None,
                       "ttft_s": round(ttft, 2) if ttft is not None else None,
                       "e2e_tps": round(out / wall, 1) if out and wall else None,
                       "decode_tps": round(out / (wall - ttft), 1) if out and wall and ttft is not None and wall > ttft else None,
                       "server_decode_tps": None, "batch": batch},
            "cost_usd": round(cost, 5),
        }

    def stream(self, params: dict, est_input_cost: float = 0.0, on_first=None) -> dict:
        """One streamed request; aborted (and billed by estimate) if the running total would pass the hard stop.
        on_first() is called when the response starts (from then on its cache entry can be read by others)."""
        self.cost.check(est_input_cost)
        pout = price_of(self.model)[1]
        t0 = time.monotonic()
        ttft, chars, n_ev, aborted, msg = None, 0, 0, None, None
        with self.client.messages.stream(**params) as s:
            for ev in s:
                n_ev += 1
                if ev.type == "message_start" and on_first is not None:
                    on_first()
                    on_first = None
                if ev.type == "content_block_delta":
                    if ttft is None:
                        ttft = time.monotonic() - t0
                    d = ev.delta
                    chars += len(getattr(d, "text", None) or getattr(d, "thinking", None)
                                 or getattr(d, "partial_json", None) or "")
                    if n_ev % 50 == 0 and (self.cost.spent + est_input_cost + chars / 3.0 * pout / 1e6
                                           >= self.cost.hard_stop):
                        aborted = "budget"
                        break
            if aborted is None:
                msg = s.get_final_message()
        if on_first is not None:
            on_first()
        wall = time.monotonic() - t0
        if aborted:
            # the stream was closed early; count the estimate (no usage is reported for a closed stream)
            self.cost.spent += est_input_cost + chars / 3.0 * pout / 1e6
            raise BudgetExceeded("stream aborted at the hard stop")
        return self.record_from_message(msg, wall=wall, ttft=ttft)

    def chat(self, messages: list, tools: list | None = None, max_tokens: int | None = None,
             prompt_tokens_est: int = 0) -> dict:
        """One streamed turn (used by the agentic loop): automatic prompt caching of the growing conversation."""
        pin = price_of(self.model)[0]
        return self.stream(self.params(messages, tools=tools, max_tokens=max_tokens, cache_auto=True),
                           est_input_cost=prompt_tokens_est * pin * 0.3 / 1e6)

    # ------------------------------------------------------------------------------------------------ batch
    def run_batch(self, reqs: list[tuple[str, dict]], poll_s: float = 30, log=print, resume_path=None) -> dict:
        """reqs: (custom_id, params).  Returns {custom_id: record or {'error': ...}}.
        resume_path (2026-10-12): the batch id is written there as soon as the batch exists, and a later call with the
        same custom ids re-attaches to it instead of submitting (and paying for) it again; the caller removes the file
        once the records are saved.  Every raw result is also kept (batch-<id>.jsonl beside it) before it is read, and a
        result that cannot be read becomes an error for that item only."""
        ids = sorted(cid for cid, _ in reqs)
        bid = None
        if resume_path is not None and resume_path.exists():
            try:
                prev = json.loads(resume_path.read_text())
                if sorted(prev.get("custom_ids") or []) == ids:
                    bid = prev["id"]
                    log(f"  batch {bid}: re-attached (submitted {prev.get('submitted')}, results not saved yet)")
            except (OSError, ValueError, KeyError):
                pass
        if bid is None:
            bid = self.client.messages.batches.create(requests=[{"custom_id": cid, "params": p} for cid, p in reqs]).id
            if resume_path is not None:
                resume_path.parent.mkdir(parents=True, exist_ok=True)
                resume_path.write_text(json.dumps({"id": bid, "custom_ids": ids,
                                                   "submitted": time.strftime("%Y-%m-%dT%H:%M:%S")}))
            log(f"  batch {bid}: {len(reqs)} requests submitted")
        t0 = time.monotonic()
        while True:
            b = self.client.messages.batches.retrieve(bid)
            if b.processing_status == "ended":
                break
            rc = b.request_counts
            log(f"  batch {bid}: {b.processing_status}, processing {rc.processing}, done "
                f"{rc.succeeded + rc.errored + rc.canceled + rc.expired}  ({(time.monotonic() - t0) / 60:.0f} min)")
            time.sleep(poll_s)
        out = {}
        raw = open(resume_path.with_name(f"batch-{bid}.jsonl"), "w") if resume_path is not None else None
        try:
            for r in self.client.messages.batches.results(bid):
                if raw is not None:
                    try:                                    # the SDK's pydantic result; the mock's objects differ
                        raw.write(json.dumps(r.model_dump(mode="json"), ensure_ascii=False) + "\n")
                    except Exception:
                        try:
                            raw.write(json.dumps(r.model_dump(), ensure_ascii=False, default=str) + "\n")
                        except Exception:
                            pass
                    raw.flush()
                try:
                    if r.result.type == "succeeded":
                        out[r.custom_id] = self.record_from_message(r.result.message, batch=True)
                    else:
                        err = getattr(r.result, "error", None)
                        out[r.custom_id] = {"error": f"{r.result.type}: {err.model_dump() if err is not None else ''}"[:800]}
                except Exception as e:                      # one unreadable result costs that item only
                    out[r.custom_id] = {"error": f"result not readable: {type(e).__name__}: {e}"[:800]}
        finally:
            if raw is not None:
                raw.close()
        out["_batch"] = {"id": bid, "minutes": round((time.monotonic() - t0) / 60, 1)}
        return out

    @staticmethod
    def assistant_message(rec: dict) -> dict:
        blocks = []
        for b in rec["response"]["blocks"]:
            b = {k: v for k, v in b.items() if k not in ("citations",) or v}
            blocks.append(b)
        return {"role": "assistant", "content": blocks}

    @staticmethod
    def tool_result_messages(results: list[tuple[str, str]]) -> list[dict]:
        return [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": cid, "content": text}
                                             for cid, text in results]}]
