"""Models hosted on OpenRouter (openrouter.ai), for the suite's test prompts only.

* The key is read from ~/.config/model-suite/openrouter.key and handed straight to the request headers.  It is never
  printed, logged, written anywhere or put into an environment variable.
* One provider endpoint is pinned for the whole run (`provider.order` = `provider.only` = its full slug,
  `allow_fallbacks: false`), so a run never switches hosts or precision.  The endpoint is chosen from OpenRouter's
  public listing: the highest published precision among the endpoints that take tools and reasoning, then the one
  that honours the most of the user's sampling parameters; `--endpoint openrouter:<model>@<slug>` picks one by hand.
  Every response's provider (and model) is recorded; a response from any other provider stops the run.
* Sampling: the user's temperature / top-p / top-k / min-p are sent; which of them the pinned endpoint honours is
  read from its published supported_parameters and recorded (the rest are sent but ignored by the provider).
* Thinking: `reasoning.effort = "xhigh"` (OpenRouter's documented values: max, xhigh, high, ...; on budget-only
  providers xhigh means ~95 % of max_tokens).
* Cost: `usage.include` makes OpenRouter return each request's cost; it is added up and the run stops before the
  hard limit (default $15).  Requests run in parallel (default 6); each in-flight request reserves its worst case
  (max_tokens at the output price) against the limit, so the limit holds even with several requests open.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .backend_openai import EndpointError, OpenAIBackend
from .common import LOCAL_SAMPLING
from . import tokcount

OR_BASE = "https://openrouter.ai/api/v1"
KEY_FILE = Path.home() / ".config" / "model-suite" / "openrouter.key"
PREC_RANK = {"fp32": 9, "bf16": 8, "fp16": 8, "fp8": 5, "int8": 4, "fp6": 3, "fp4": 2, "int4": 1, "unknown": 0}
RETRY_DELAY_S = 5.0
RETRY_STATUS = {0, 408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}


class NoKey(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def _load_key(path=None) -> str:
    p = Path(path) if path else KEY_FILE
    if not p.exists():
        raise NoKey(f"{p} is missing")
    k = p.read_text(encoding="utf-8").strip()
    if not k:
        raise NoKey(f"{p} is empty")
    return k


def _get_json(url, timeout=60, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def model_page(model: str, base=OR_BASE) -> dict:
    """Public listing: the model's page data (name, Hugging Face id, description, parameters, pricing)."""
    for m in _get_json(base + "/models").get("data", []):
        if m.get("id") == model:
            return {k: m.get(k) for k in ("id", "name", "hugging_face_id", "description", "context_length", "created",
                                          "supported_parameters", "pricing", "canonical_slug")}
    raise SystemExit(f"OpenRouter lists no model {model!r}")


def model_endpoints(model: str, base=OR_BASE) -> list[dict]:
    d = _get_json(f"{base}/models/{model}/endpoints").get("data") or {}
    return d.get("endpoints") or []


def choose_endpoint(eps: list[dict], want: str | None = None) -> dict:
    if want:
        for e in eps:
            if want in (e.get("tag"), e.get("provider_name")):
                return e
        raise SystemExit(f"no endpoint {want!r}; listed: {[e.get('tag') for e in eps]}")
    usable = [e for e in eps if "tools" in (e.get("supported_parameters") or [])
              and {"reasoning", "reasoning_effort"} & set(e.get("supported_parameters") or [])]
    if not usable:
        raise SystemExit("no endpoint takes both tools and reasoning")

    def key(e):
        sp = set(e.get("supported_parameters") or [])
        price = float((e.get("pricing") or {}).get("completion") or 0)
        return (PREC_RANK.get(e.get("quantization") or "unknown", 0), ("top_k" in sp) + ("min_p" in sp),
                min(e.get("max_completion_tokens") or 0, 81920), -price)

    best = max(key(e) for e in usable)
    return next(e for e in usable if key(e) == best)          # the first listed among equals


class OpenRouterBackend(OpenAIBackend):
    kind = "openrouter"

    def __init__(self, model: str, provider: str | None = None, max_tokens: int = 81920, hard_stop: float = 15.0,
                 spent: float = 0.0, key_path=None, base: str | None = None, effort: str = "xhigh",
                 idle_timeout_s: float = 900, total_timeout_s: float = 7200, sampling: dict | None = None,
                 rpm: float | None = None, free_only: bool = False):
        self.base = base or OR_BASE
        self._key = _load_key(key_path)
        self.model = model
        self.page = model_page(model, self.base)
        self.endpoints = model_endpoints(model, self.base)
        self.endpoint = choose_endpoint(self.endpoints, provider)
        self.slug = self.endpoint.get("tag") or self.endpoint.get("provider_name")
        self.provider_name = self.endpoint.get("provider_name")
        sp = set(self.endpoint.get("supported_parameters") or [])
        # 2026-10-19: a sampling set other than the standard one (e.g. the model maker's recommendation); None drops a key
        self.sampling = {k: v for k, v in (sampling if sampling is not None else LOCAL_SAMPLING).items() if v is not None}
        self.honoured = [k for k in self.sampling if k in sp]
        self.ignored = [k for k in self.sampling if k not in sp]
        self.effort = None                                   # not the local reasoning_effort field
        self.reasoning = {"effort": effort}
        self.extra_body = {}
        self.max_tokens = min(max_tokens, self.endpoint.get("max_completion_tokens") or max_tokens)
        self.ctx = self.endpoint.get("context_length") or self.page.get("context_length") or 131072
        self.idle_timeout_s, self.total_timeout_s = idle_timeout_s, total_timeout_s
        self.counter = tokcount.Counter()                    # the API reports reasoning tokens itself
        pr = self.endpoint.get("pricing") or {}
        self.price_in = float(pr.get("prompt") or 0)
        self.price_out = float(pr.get("completion") or 0)
        self.price_cache_read = float(pr.get("input_cache_read") or self.price_in)
        self.hard_stop, self.spent = hard_stop, spent
        self._reserved = 0.0
        self._lock = threading.Lock()
        self.stopped = None
        self.server_info = {}
        # 2026-10-19 (free models): start at most `rpm` requests a minute; 429s are retried without a limit (a per-day
        # cap waits for the UTC reset); `free_only` stops the run at the first request that costs anything
        self.rpm, self.free_only = rpm, free_only
        self._next_start = 0.0
        self.rate_limited = 0

    # ------------------------------------------------------------------------------------------------ requests
    def _headers(self) -> dict:
        return {"Content-Type": "application/json", "Accept": "text/event-stream",
                "Authorization": "Bearer " + self._key, "X-Title": "model test suite"}

    def _body(self, messages, tools, mt) -> dict:
        body = super()._body(messages, tools, mt)
        body.pop("stream_options", None)
        body["reasoning"] = dict(self.reasoning)
        body["provider"] = {"order": [self.slug], "only": [self.slug], "allow_fallbacks": False}
        body["usage"] = {"include": True}
        return body

    def describe(self) -> dict:
        e = self.endpoint
        return {"kind": "openrouter", "model": self.model, "model_page": self.page,
                "pinned_endpoint": {"slug": self.slug, "provider": self.provider_name,
                                    "published_precision": e.get("quantization"), "context": e.get("context_length"),
                                    "max_completion_tokens": e.get("max_completion_tokens"),
                                    "supported_parameters": e.get("supported_parameters"), "pricing": e.get("pricing")},
                "endpoints_listed": [{"slug": x.get("tag"), "provider": x.get("provider_name"),
                                     "precision": x.get("quantization")} for x in self.endpoints],
                "sampling_sent": self.sampling, "sampling_honoured": self.honoured, "sampling_ignored": self.ignored,
                "reasoning": self.reasoning, "max_tokens_default": self.max_tokens, "ctx": self.ctx,
                "hard_stop_usd": self.hard_stop, "fallbacks": False, "rpm": self.rpm, "free_only": self.free_only}

    def _worst_case(self, prompt_tokens_est, mt) -> float:
        return prompt_tokens_est * self.price_in + mt * self.price_out

    def chat(self, messages: list, tools: list | None = None, max_tokens: int | None = None,
             prompt_tokens_est: int = 0) -> dict:
        mt = self.fit_max_tokens(prompt_tokens_est, max_tokens)
        reserve = self._worst_case(prompt_tokens_est, mt)
        with self._lock:
            if self.stopped:
                raise BudgetExceeded(self.stopped)
            if self.spent + self._reserved + reserve >= self.hard_stop:
                self.stopped = (f"spent ${self.spent:.2f} + open requests ${self._reserved:.2f} + this one's worst case "
                                f"${reserve:.2f} reaches the ${self.hard_stop:.2f} hard stop")
                raise BudgetExceeded(self.stopped)
            self._reserved += reserve
        try:
            body = self._body(messages, tools, mt)
            delay, last, attempt = RETRY_DELAY_S, None, 0
            while True:
                self._pace()
                try:
                    rec = self._exchange(body, mt)
                    break
                except EndpointError as e:
                    last = e
                    if e.status == 429:                 # rate limited: never graded, never given up
                        with self._lock:
                            self.rate_limited += 1
                        time.sleep(self._rate_limit_wait())
                        continue
                    attempt += 1
                    if e.status not in RETRY_STATUS or attempt >= 5:
                        raise
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
        finally:
            with self._lock:
                self._reserved -= reserve
        meta = rec["response"].get("meta") or {}
        usage = rec["response"].get("usage") or {}
        cost = usage.get("cost")
        if cost is None or not meta.get("provider"):
            gen = self._generation(meta.get("id"))
            if cost is None and gen.get("total_cost") is not None:
                cost, rec["cost_source"] = gen["total_cost"], "generation"
            if gen.get("provider_name"):
                meta.setdefault("provider", gen["provider_name"])
        if cost is None:      # priced from the endpoint's published prices
            cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
            cost = (((usage.get("prompt_tokens") or 0) - cached) * self.price_in + cached * self.price_cache_read
                    + (usage.get("completion_tokens") or 0) * self.price_out)
            rec["cost_source"] = "computed from published prices"
        rec["cost_usd"] = round(float(cost), 6)
        rec["response"]["meta"] = meta
        with self._lock:
            self.spent += float(cost)
            if self.free_only and float(cost) > 0 and not self.stopped:
                self.stopped = f"billing started: a request cost ${float(cost):.6f} (free-only run)"
        prov = meta.get("provider")
        if prov and prov != self.provider_name:
            with self._lock:
                self.stopped = f"a response came from {prov}, not the pinned {self.provider_name}"
            raise EndpointError(self.stopped, status=-1)
        rec["response"]["provider"] = prov
        rec["request"]["provider_pinned"] = self.slug
        return rec

    def _pace(self):
        if not self.rpm:
            return
        with self._lock:
            now = time.time()
            start = max(now, self._next_start)
            self._next_start = start + 60.0 / self.rpm
        if start > now:
            time.sleep(start - now)

    def _rate_limit_wait(self) -> float:
        """Seconds to wait after a 429: the free-model day cap waits for the UTC reset, else a minute."""
        try:
            d = _get_json(f"{self.base}/key", headers={"Authorization": "Bearer " + self._key}).get("data") or {}
            fm = d.get("free_model_daily_requests") or {}
            if fm.get("remaining") == 0:
                now = time.time()
                return max(60.0, (int(now // 86400) + 1) * 86400 - now + 60)
        except Exception:  # noqa: BLE001 - the wait below is the fallback
            pass
        return 60.0

    def _generation(self, gid) -> dict:
        if not gid:
            return {}
        for _ in range(3):
            try:
                return _get_json(f"{self.base}/generation?id={gid}", timeout=30,
                                 headers={"Authorization": "Bearer " + self._key}).get("data") or {}
            except (urllib.error.URLError, OSError, ValueError):
                time.sleep(2)
        return {}


def estimate(model: str, items, runs, log=print, base_label=None, provider=None) -> dict:
    """Dollar estimate from the last local run's tokens and the pinned endpoint's published prices (public data,
    no key needed)."""
    from .cost import _base_label, _tokens_by_item
    import statistics
    ep = choose_endpoint(model_endpoints(model), provider)
    pr = ep.get("pricing") or {}
    pin, pout = float(pr.get("prompt") or 0), float(pr.get("completion") or 0)
    base = _base_label(base_label)
    tok = _tokens_by_item(base) if base else {}
    cats = {}
    for it in items:
        e = tok.get(it["id"])
        comp = statistics.mean(e["completion"]) if e and e["completion"] else 8000
        prompt = statistics.mean(e["prompt"]) if e and e["prompt"] else len(it.get("prompt", "")) / 3.5
        c = 0.0
        if (it.get("agentic") or it.get("research")) and e and e["steps"]:
            c = sum(p * pin + q * pout for p, q in e["steps"][0])
        elif it.get("research"):
            c = sum((4000 + 6000 * k) * pin + 4000 * pout for k in range(6))
        else:
            c = prompt * pin + comp * pout
        a = cats.setdefault(it["category"], [0.0, 0.0])
        a[0] += c * runs
        a[1] += (c + comp * pout) * runs
    point, high = sum(v[0] for v in cats.values()), sum(v[1] for v in cats.values())
    log(f"cost estimate for {model} on {ep.get('tag')} ({ep.get('quantization')}), {runs} run(s) per item, from "
        f"local run '{base or 'none'}': ${point:.2f} (if it writes 2x the tokens: ${high:.2f})")
    for c, (lo, hi) in cats.items():
        log(f"   {c:10s} ${lo:7.3f}")
    return {"point": round(point, 2), "high_2x_output": round(high, 2), "base_label": base, "endpoint": ep.get("tag"),
            "prices_per_token": {"prompt": pin, "completion": pout}}
