#!/usr/bin/env python3
"""anthropic_guard.py - C4's budget guard: an OpenAI-compatible endpoint on 127.0.0.1 in front of Anthropic's Messages
API (official SDK), one process per experiment arm. STAGED 2026-10-29: tested offline against a local mock only, never
started against the real API (staging/c4/README.md).

  LDR (ChatOpenAI -> /v1/chat/completions)  ->  127.0.0.1:<port> (this)  ->  Anthropic Messages API, always streamed

Every chat completion:
  * is translated (system, user, assistant + tool_calls, tool results, tools, tool_choice, stop, max_tokens,
    response_format) into a Messages request for --model, whatever model name the client sends;
  * effort: the request's `reasoning_effort` (our names low / medium / high / xhigh; OpenAI's none / minimal -> low;
    max) -> output_config.effort, after --effort-map. Without one: --class-efforts for the call's class (agent /
    extract / compact / report / verify / synth / other, classified as strata-proxy does, plus LDR's own report-stage
    prompts), then --default-effort, else none (the API default). Thinking is adaptive. temperature, top_p and the
    other sampling fields are dropped (the model refuses non-default values) and logged by name;
  * prompt caching only on prefixes that are reused within the run (Karl 10-29): the top-level automatic breakpoint
    (the end of the growing transcript) only on requests that will grow - they carry tools (an agent loop: the lead,
    a subagent, a wrap-up with its tools sent again) or continue a conversation this guard answered (an earlier answer
    of it comes back under an unchanged prefix); the breakpoint on the last system block (on the last tool without a
    system prompt) on those, and on a request whose system + tools prefix this guard has already sent once in this
    run. A one-shot request (extraction, report section, verification, compaction, a citation pass) gets no
    cache_control at all. Lifetime 5 minutes; --lead-cache-1h (off by default) gives the lead agent's two breakpoints
    1 hour. Each lead call's gap to the previous one is logged (<log-dir>/lead-gaps-<run>.jsonl, no prompt content;
    tools/lead_gaps.py summarises it after the pilots);
  * thinking blocks: an OpenAI message cannot carry them, so the guard keeps each answer's content blocks (keyed by its
    tool-call ids, or by its text) and puts them back verbatim when the client sends that turn again - only where the
    turn's prefix (system, tools, earlier messages) is unchanged and the chain of earlier blocks is intact (an
    emulation of the API's history check, so LDR's compaction does not cost a 400), with
    `thinking.block_binding.prefix_mismatch_behavior: drop_block` as the safety net (beta
    thinking-binding-controls-2026-08-01). --thinking-replay strip never sends them back;
  * tools dropped by the client while the history still holds tool calls (our build's wrap-up step): the tool list
    last seen for that conversation is sent again with tool_choice none (the API refuses tool blocks without tools);
    with none on record the tool blocks are sent as text;
  * money: each response's usage (input, output, cache writes 5m / 1h, cache reads) is priced from --pricing and added
    to a ledger file shared by all arms (--ledger, file-locked). Before a request goes out its worst case is reserved:
    the whole input at the cache-write rate, counted as --input-tokens-per-byte tokens per byte of the request
    (default 1.0, an upper bound) plus --overhead-tokens, and max_tokens of output. A request whose worst case would
    pass the run cap, the total cap, the research cap (research requests only: (1 - --report-reserve) x the run cap,
    so the reserve, 22 % by default, is kept for the report stage) or the agent cap (requests with tools only,
    optional) is refused with HTTP 402 ("cap reached") and a message naming the cap and the numbers; nothing is sent.
    Report-stage requests are the ones identified by their prompt (the deep package's report / verification steps,
    LDR's citation pass and fallback synthesis); everything else counts as research. When only requests still
    running hold the rest of a cap, a new
    request waits for them (--wait-inflight-s) before it is refused. Usage that cannot be known (a stream cut off, a
    timeout) is charged at the reserved worst case;
  * log: one JSON line per request in <log-dir>/costs-<run>.jsonl (no prompt text, no headers, no key) and
    <log-dir>/summary-<run>.json after each request.

The key: read from --key-file inside each request, handed to that request's SDK client and dropped. Never printed,
logged, written or put in the environment. At start the guard deletes every ANTHROPIC_* variable from its own
environment (so the SDK cannot pick up another key, base URL, headers or debug logging), accepts only
https://api.anthropic.com or a loopback mock as the upstream, and does not follow redirects. Anything that looks like
an Anthropic key ("sk-ant-...") is masked in every error text and log line.

Endpoints (127.0.0.1 only): POST /v1/chat/completions, GET /v1/models, GET /health, GET /v1/guard/status.
Settings: command-line flags, each with a GUARD_* environment default (see --help); c4-arm.sh sets them from arms/*.env.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import itertools
import json
import os
import re
import signal
import sys
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

VERSION = "c4-staged-2026-10-29-karl1029"
DEFAULT_KEY_FILE = "~/.config/model-suite/anthropic.key"
DEFAULT_UPSTREAM = "https://api.anthropic.com"
DEFAULT_PRICING = str(Path(__file__).resolve().parent.parent / "pricing.json")
MODEL_MAX_OUTPUT = 128_000
API_EFFORTS = ("low", "medium", "high", "xhigh", "max")
EFFORT_ALIASES = {"none": "low", "minimal": "low"}
BETA_BINDING = "thinking-binding-controls-2026-08-01"
THINKING = ("thinking", "redacted_thinking")
KEY_LIKE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{6,}")
LOOPBACK = ("127.0.0.1", "localhost", "::1")
RETRY_STATUSES = (429, 500, 502, 503, 504, 529)
CLASSES = ("agent", "extract", "compact", "report", "verify", "synth", "other")
# the first words of LDR's extraction prompt and of the deep package's own prompts (as in tools/strata-proxy.py)
EXTRACT_MARK = "You are a content-extraction step inside a multi-step research agent."
CLASS_MARKS = (("compact", "You are the history-compaction step of a research agent."),
               ("report", "You are the report-writing step of a research system."),
               ("verify", "You are the claim-verification step of a research system."))
# LDR 1.10.7's own report-stage prompts (stock and our build): the fallback synthesis when the agent loop ends without
# an answer (langgraph_agent_strategy._synthesize_from_collector), the standard citation handler's fact check (off by
# default) and its cited answer, which may follow the user's output-instruction prefix (so it is looked for in the
# first SYNTH_SCAN characters)
SYNTH_START_MARKS = ("Synthesize a comprehensive answer to: ", "Analyze these sources for factual consistency:")
SYNTH_INNER_MARK = "Using the previous knowledge and new sources, answer the question."
SYNTH_SCAN = 4000
# the lead agent's system prompt (LDR 1.10.7, stock and our build alike; subagents: "You are a focused research ...")
LEAD_MARK = "You are a research assistant writing a research report."
# Karl 10-29: the report stage may spend the reserve; every other class (agent = lead + subagents, extract, compact,
# other = not identified) is research
REPORT_STAGE_CLASSES = ("report", "verify", "synth")
STOP_MAP = {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length", "tool_use": "tool_calls",
            "refusal": "content_filter", "pause_turn": "stop", "model_context_window_exceeded": "length"}
KNOWN_FIELDS = {"model", "messages", "tools", "functions", "tool_choice", "function_call", "parallel_tool_calls",
                "max_tokens", "max_completion_tokens", "stream", "stream_options", "stop", "response_format",
                "reasoning_effort", "reasoning", "output_config", "n"}
DROPPED_FIELDS = {"temperature", "top_p", "top_k", "min_p", "presence_penalty", "frequency_penalty",
                  "repetition_penalty", "seed", "logprobs", "top_logprobs", "logit_bias", "user", "service_tier",
                  "store", "metadata", "modalities", "audio", "prediction", "verbosity", "web_search_options",
                  "chat_template_kwargs", "safety_identifier", "prompt_cache_key"}
_ID_BAD = re.compile(r"[^A-Za-z0-9_-]")


def scrub(text: object) -> str:
    """Mask anything that looks like an Anthropic key."""
    return KEY_LIKE.sub("sk-ant-[masked]", str(text))


def env(name: str, default=None):
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()


# ================================================================================================== pricing
@dataclass(frozen=True)
class Rates:
    model: str
    input: float
    output: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float
    long_threshold: int | None = None
    long_input_mult: float = 1.0
    long_output_mult: float = 1.0
    checked: str = ""

    def write_rate(self, ttl: str) -> float:
        return self.cache_write_1h if ttl == "1h" else self.cache_write_5m


def load_rates(path: str, model: str) -> Rates:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if model not in d:
        raise SystemExit(f"anthropic-guard: no prices for {model} in {path}")
    m = d[model]
    lc = m.get("long_context") or {}
    return Rates(model, float(m["input"]), float(m["output"]), float(m["cache_write_5m"]), float(m["cache_write_1h"]),
                 float(m["cache_read"]), int(lc["threshold"]) if lc.get("threshold") else None,
                 float(lc.get("input_mult") or 1.0), float(lc.get("output_mult") or 1.0), str(m.get("checked") or ""))


def usage_dict(u) -> dict:
    """The SDK's usage object -> plain numbers (cache_write_5m / _1h None when the API gave no breakdown)."""
    def g(n):
        return int(getattr(u, n, 0) or 0)
    cc = getattr(u, "cache_creation", None)
    otd = getattr(u, "output_tokens_details", None)
    return {"input_tokens": g("input_tokens"), "output_tokens": g("output_tokens"),
            "cache_creation_input_tokens": g("cache_creation_input_tokens"),
            "cache_read_input_tokens": g("cache_read_input_tokens"),
            "cache_write_5m": int(cc.ephemeral_5m_input_tokens or 0) if cc is not None else None,
            "cache_write_1h": int(cc.ephemeral_1h_input_tokens or 0) if cc is not None else None,
            "thinking_tokens": int(getattr(otd, "thinking_tokens", 0) or 0) if otd is not None else None}


def split_writes(u: dict, ttl: str) -> tuple[int, int]:
    """Cache-write tokens as (5m, 1h): the API's breakdown when given, the rest at the request's TTL."""
    cw = int(u.get("cache_creation_input_tokens") or 0)
    w5, w1 = u.get("cache_write_5m"), u.get("cache_write_1h")
    w5, w1 = int(w5 or 0), int(w1 or 0)
    rest = cw - w5 - w1
    if rest > 0:
        if ttl == "1h":
            w1 += rest
        else:
            w5 += rest
    return w5, w1


def price(u: dict, r: Rates, ttl: str) -> float:
    """USD for one response's usage."""
    inp, out = int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
    cr = int(u.get("cache_read_input_tokens") or 0)
    w5, w1 = split_writes(u, ttl)
    mi = mo = 1.0
    if r.long_threshold and inp + w5 + w1 + cr > r.long_threshold:
        mi, mo = r.long_input_mult, r.long_output_mult
    return ((inp * r.input + w5 * r.cache_write_5m + w1 * r.cache_write_1h + cr * r.cache_read) * mi
            + out * r.output * mo) / 1e6


def input_side_price(u: dict, r: Rates, ttl: str) -> float:
    return price({**u, "output_tokens": 0}, r, ttl)


def worst_case(est_in: int, max_tokens: int, r: Rates, ttl: str) -> float:
    """The most one request can cost: every input token at the dearest input rate (a cache write), all of max_tokens."""
    mi = mo = 1.0
    if r.long_threshold and est_in > r.long_threshold:
        mi, mo = r.long_input_mult, r.long_output_mult
    return (est_in * max(r.input, r.write_rate(ttl)) * mi + max_tokens * r.output * mo) / 1e6


# ================================================================================================== ledger
class LedgerError(Exception):
    pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError, TypeError):
        return True


def _new_run(arm: str) -> dict:
    return {"arm": arm, "spent_usd": 0.0, "charged_unknown_usd": 0.0, "requests": 0, "refused": 0, "errors": 0,
            "tokens": {"input": 0, "output": 0, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0,
                       "thinking": 0},
            "stage_usd": {"research": 0.0, "report": 0.0},
            "first_t": None, "last_t": None, "cap_usd": None, "research_cap_usd": None}


class Ledger:
    """Spending of every run and arm, in one JSON file shared by all guard processes (flock on <file>.lock).
    A request reserves its worst case first and settles to its real cost after; reservations of a process that died
    are charged in full at the next look (we cannot know what they cost).
    report_reserve (Karl 10-29): research requests are held to (1 - report_reserve) x the run cap, counted against
    everything the run has spent; report-stage requests may use the whole run cap."""

    def __init__(self, path: str, run_id: str, arm: str, run_cap: float, total_cap: float, agent_cap: float | None,
                 report_reserve: float = 0.0):
        self.path = Path(path)
        self.lock_path = str(self.path) + ".lock"
        self.run_id, self.arm = run_id, arm
        self.run_cap, self.total_cap, self.agent_cap = run_cap, total_cap, agent_cap
        self.report_reserve = report_reserve
        self.research_cap = run_cap * (1.0 - report_reserve) if report_reserve > 0 else None
        self.tlock = threading.Lock()
        self._ids = itertools.count(1)
        self.pid = os.getpid()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._state() as st:          # fails here (at start) on a corrupt ledger
            run = st["runs"].setdefault(run_id, _new_run(arm))
            run["cap_usd"] = run_cap
            run["research_cap_usd"] = self.research_cap
            run.setdefault("stage_usd", {"research": 0.0, "report": 0.0})
            st["total_cap_usd"] = total_cap

    def _load(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "total_spent_usd": 0.0, "total_cap_usd": None, "runs": {}, "inflight": {},
                    "stale_charged": []}
        try:
            st = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise LedgerError(f"ledger {self.path} unreadable: {e}") from e
        if not isinstance(st, dict) or "runs" not in st:
            raise LedgerError(f"ledger {self.path} is not a guard ledger")
        st.setdefault("inflight", {})
        st.setdefault("stale_charged", [])
        return st

    def _save(self, st: dict) -> None:
        tmp = self.path.with_name(self.path.name + f".tmp{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    @contextmanager
    def _state(self):
        with self.tlock:
            fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                st = self._load()
                self._reap(st)
                yield st
                self._save(st)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def _reap(self, st: dict) -> None:
        for rid, r in list(st["inflight"].items()):
            if int(r.get("pid") or 0) == self.pid or _pid_alive(r.get("pid")):
                continue
            del st["inflight"][rid]
            usd = float(r.get("usd") or 0.0)
            run = st["runs"].setdefault(r.get("run") or "?", _new_run(r.get("arm") or "?"))
            run["spent_usd"] += usd
            run["charged_unknown_usd"] += usd
            st["total_spent_usd"] += usd
            st["stale_charged"].append({"reservation": rid, "run": r.get("run"), "usd": usd, "t": time.time()})

    def _caps(self, has_tools: bool, research: bool):
        caps = []
        if research and self.research_cap is not None:      # the tightest for research: checked (and named) first
            caps.append(("research", self.research_cap))
        caps.append(("run", self.run_cap))
        if has_tools and self.agent_cap is not None:
            caps.append(("agent", self.agent_cap))
        caps.append(("total", self.total_cap))
        return caps

    def reserve(self, worst: float, has_tools: bool, research: bool = True) -> dict:
        """{'ok': reservation id} | {'refuse': info} (can never fit) | {'wait': info} (fits once running ones end).
        research: the request is research (not identified as report stage) - held to the research cap."""
        with self._state() as st:
            run = st["runs"].setdefault(self.run_id, _new_run(self.arm))
            infl_run = sum(float(r["usd"]) for r in st["inflight"].values() if r.get("run") == self.run_id)
            infl_all = sum(float(r["usd"]) for r in st["inflight"].values())
            numbers = {"run": (run["spent_usd"], infl_run), "agent": (run["spent_usd"], infl_run),
                       "research": (run["spent_usd"], infl_run), "total": (st["total_spent_usd"], infl_all)}
            for name, cap in self._caps(has_tools, research):
                spent, _ = numbers[name]
                if spent + worst > cap + 1e-12:
                    run["refused"] += 1
                    return {"refuse": {"cap": name, "cap_usd": cap, "spent_usd": spent, "inflight_usd": numbers[name][1],
                                       "worst_usd": worst}}
            for name, cap in self._caps(has_tools, research):
                spent, infl = numbers[name]
                if spent + infl + worst > cap + 1e-12:
                    return {"wait": {"cap": name, "cap_usd": cap, "spent_usd": spent, "inflight_usd": infl,
                                     "worst_usd": worst}}
            rid = f"{self.pid}-{next(self._ids)}"
            st["inflight"][rid] = {"run": self.run_id, "arm": self.arm, "usd": worst, "pid": self.pid, "t": time.time()}
            return {"ok": rid}

    def note_refused(self) -> None:
        with self._state() as st:
            st["runs"].setdefault(self.run_id, _new_run(self.arm))["refused"] += 1

    def settle(self, rid: str, usd: float, unknown_usd: float = 0.0, usage: dict | None = None,
               ttl: str = "5m", error: bool = False, stage: str | None = None) -> dict:
        """Release a reservation and book its real cost; returns the run entry and the total after it."""
        with self._state() as st:
            st["inflight"].pop(rid, None)
            run = st["runs"].setdefault(self.run_id, _new_run(self.arm))
            total = usd + unknown_usd
            run["spent_usd"] += total
            run["charged_unknown_usd"] += unknown_usd
            if stage:
                su = run.setdefault("stage_usd", {"research": 0.0, "report": 0.0})
                su[stage] = su.get(stage, 0.0) + total
            st["total_spent_usd"] += total
            run["requests"] += 1
            run["errors"] += int(bool(error))
            now = time.time()
            run["first_t"] = run["first_t"] or now
            run["last_t"] = now
            if usage:
                w5, w1 = split_writes(usage, ttl)
                tk = run["tokens"]
                tk["input"] += int(usage.get("input_tokens") or 0)
                tk["output"] += int(usage.get("output_tokens") or 0)
                tk["cache_write_5m"] += w5
                tk["cache_write_1h"] += w1
                tk["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
                tk["thinking"] += int(usage.get("thinking_tokens") or 0)
            return {"run": json.loads(json.dumps(run)), "total_spent_usd": st["total_spent_usd"],
                    "inflight": len(st["inflight"])}

    def snapshot(self) -> dict:
        with self._state() as st:
            run = st["runs"].get(self.run_id) or _new_run(self.arm)
            return {"run": json.loads(json.dumps(run)), "total_spent_usd": st["total_spent_usd"],
                    "inflight_usd": sum(float(r["usd"]) for r in st["inflight"].values()),
                    "inflight": len(st["inflight"]), "stale_charged": len(st["stale_charged"])}


# ================================================================================================== thinking store
THINK_BLOCK_TYPES = THINKING


@dataclass
class Rec:
    rid: str
    blocks: list            # the answer's content blocks in request form, thinking included, as the API sent them
    prefix: str             # hash of everything before the answer (system, tools, messages; thinking excluded)
    chain: str | None       # the record whose thinking came last before this answer in the request that made it
    has_thinking: bool
    text: str               # the answer's text (stripped) and tool calls, to check a turn really is this answer
    calls: list
    size: int


class ReplayStore:
    """Answer content blocks by turn key and prefix hash, least recently used dropped past max_bytes."""

    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self.lock = threading.Lock()
        self.by_key: dict[str, OrderedDict] = {}
        self.order: OrderedDict = OrderedDict()
        self.bytes = 0
        self.evicted = 0
        self._ids = itertools.count(1)

    def new_id(self) -> str:
        return f"r{next(self._ids)}"

    def put(self, key: str, rec: Rec) -> None:
        with self.lock:
            d = self.by_key.setdefault(key, OrderedDict())
            old = d.pop(rec.prefix, None)
            if old is not None:
                self.bytes -= old.size
                self.order.pop((key, rec.prefix), None)
            d[rec.prefix] = rec
            self.order[(key, rec.prefix)] = rec.size
            self.bytes += rec.size
            while self.bytes > self.max_bytes and len(self.order) > 1:
                (k, p), size = self.order.popitem(last=False)
                self.bytes -= size
                self.evicted += 1
                dd = self.by_key.get(k)
                if dd is not None:
                    dd.pop(p, None)
                    if not dd:
                        del self.by_key[k]

    def find(self, key: str, prefix: str) -> tuple[Rec | None, bool]:
        """(record, prefix matches): the record made under this prefix, else the newest one under the key."""
        with self.lock:
            d = self.by_key.get(key)
            if not d:
                return None, False
            if prefix in d:
                self.order.move_to_end((key, prefix))
                return d[prefix], True
            return next(reversed(d.values())), False

    def stats(self) -> dict:
        with self.lock:
            return {"records": len(self.order), "bytes": self.bytes, "evicted": self.evicted}


# ================================================================================================== translation
class TranslateError(Exception):
    def __init__(self, status: int, message: str, code: str = "invalid_request_error"):
        super().__init__(message)
        self.status, self.message, self.code = status, message, code


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _view(blocks: list) -> list:
    """Blocks as the history check compares them: no thinking, no cache_control."""
    return [{k: v for k, v in b.items() if k != "cache_control"} for b in blocks if b.get("type") not in THINKING]


def _sha(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


def _roll(h: str, role: str, blocks: list) -> str:
    return _sha(h.encode(), _canon([role, _view(blocks)]))


def _tb(text: str) -> dict:
    return {"type": "text", "text": text}


def _text_of(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, str):
                out.append(p)
            elif isinstance(p, dict) and isinstance(p.get("text"), str) and p.get("type") in (None, "text", "input_text",
                                                                                                  "output_text"):
                out.append(p["text"])
        return "".join(out)
    return str(content)


def _tid(x, i: int = 0) -> str:
    s = _ID_BAD.sub("_", str(x or ""))
    return s or f"call_{i}"


def _image_block(url) -> dict | None:
    if not isinstance(url, str):
        return None
    m = re.match(r"data:(image/[A-Za-z0-9.+-]+);base64,(.*)$", url, re.S)
    if m:
        return {"type": "image", "source": {"type": "base64", "media_type": m.group(1), "data": m.group(2)}}
    if url.startswith(("https://", "http://")):
        return {"type": "image", "source": {"type": "url", "url": url}}
    return None


def _user_blocks(content, notes: set) -> list:
    if content is None:
        return []
    if isinstance(content, str):
        return [_tb(content)] if content.strip() else []
    blocks = []
    for p in content if isinstance(content, list) else [content]:
        if isinstance(p, str):
            if p.strip():
                blocks.append(_tb(p))
            continue
        if not isinstance(p, dict):
            continue
        t = p.get("type")
        if t in ("text", "input_text") and isinstance(p.get("text"), str):
            if p["text"].strip():
                blocks.append(_tb(p["text"]))
        elif t == "image_url":
            iu = p.get("image_url")
            blk = _image_block(iu.get("url") if isinstance(iu, dict) else iu)
            if blk:
                blocks.append(blk)
            else:
                notes.add("image_dropped")
        else:
            notes.add(f"part_dropped:{t}")
    return blocks


def _assistant_blocks(m: dict, notes: set) -> tuple[str, list]:
    text = _text_of(m.get("content"))
    blocks = [_tb(text)] if text.strip() else []
    calls = list(m.get("tool_calls") or [])
    if m.get("function_call"):
        calls.append({"id": None, "function": m["function_call"]})
    for i, tc in enumerate(calls):
        f = tc.get("function") or {}
        args = f.get("arguments")
        if isinstance(args, str):
            try:
                inp = json.loads(args) if args.strip() else {}
            except ValueError:
                inp = {"_unparsed_arguments": args}
                notes.add("bad_tool_arguments")
        elif isinstance(args, dict):
            inp = args
        else:
            inp = {}
        if not isinstance(inp, dict):
            inp = {"value": inp}
        blocks.append({"type": "tool_use", "id": _tid(tc.get("id"), i), "name": str(f.get("name") or "unknown"),
                       "input": inp})
    return text, blocks


def turn_key(text: str, tool_uses: list) -> str:
    if tool_uses:
        return "tc:" + ",".join(sorted(str(b["id"]) for b in tool_uses))
    return "tx:" + hashlib.sha256(text.strip().encode()).hexdigest()


def classify(req: dict) -> str:
    """agent (tools, or tool calls in the history) / extract / compact / report / verify / synth (LDR's own
    report-stage prompts) / other."""
    msgs = req.get("messages") or []
    if req.get("tools") or req.get("functions") or any(
            isinstance(m, dict) and (m.get("role") == "tool" or m.get("tool_calls")) for m in msgs):
        return "agent"
    first_user = next((_text_of(m.get("content")) for m in msgs if isinstance(m, dict) and m.get("role") == "user"), "")
    if first_user.startswith(EXTRACT_MARK):
        return "extract"
    first_text = next((_text_of(m.get("content")) for m in msgs
                       if isinstance(m, dict) and m.get("role") in ("system", "developer", "user")), "")
    for cls, mark in CLASS_MARKS:
        if first_text.startswith(mark) or first_user.startswith(mark):
            return cls
    if first_user.startswith(SYNTH_START_MARKS) or SYNTH_INNER_MARK in first_user[:SYNTH_SCAN]:
        return "synth"
    return "other"


def agent_role(req: dict, cls: str) -> str | None:
    """For agent calls: 'lead' (the lead agent's system prompt) or 'sub' (a subagent, or any other tool loop)."""
    if cls != "agent":
        return None
    first_sys = next((_text_of(m.get("content")) for m in req.get("messages") or []
                      if isinstance(m, dict) and m.get("role") in ("system", "developer")), "")
    return "lead" if first_sys.lstrip().startswith(LEAD_MARK) else "sub"


def stage_of(cls: str) -> str:
    """'report' for the classes identified as the report stage, else 'research' (the conservative fallback)."""
    return "report" if cls in REPORT_STAGE_CLASSES else "research"


def parse_effort_spec(spec: str | None, what: str) -> dict[str, str]:
    """'agent=medium,extract=low' -> dict; values checked against the API's levels."""
    out = {}
    for part in (spec or "").split(","):
        k, sep, v = part.partition("=")
        if not sep or not k.strip():
            continue
        v = EFFORT_ALIASES.get(v.strip().lower(), v.strip().lower())
        if what == "class" and k.strip() not in CLASSES:
            raise SystemExit(f"anthropic-guard: unknown call class {k.strip()!r} in --class-efforts ({', '.join(CLASSES)})")
        if v not in API_EFFORTS and not (what == "map" and v == ""):
            raise SystemExit(f"anthropic-guard: {v!r} is not an effort level ({', '.join(API_EFFORTS)})")
        out[k.strip().lower() if what == "map" else k.strip()] = v
    return out


def map_effort(raw, effort_map: dict) -> str | None:
    r = str(raw).strip().lower()
    if r in effort_map:
        r = effort_map[r]
        if r == "":
            return None
    r = EFFORT_ALIASES.get(r, r)
    if r not in API_EFFORTS:
        raise TranslateError(400, f"unknown reasoning effort {raw!r} (known: {', '.join(API_EFFORTS)}, minimal, none)")
    return r


@dataclass
class Plan:
    params: dict
    cls: str
    effort: str | None
    effort_source: str
    max_tokens: int
    est_in_tokens: int
    request_bytes: int
    has_tools: bool
    stream: bool
    include_usage: bool
    prefix_hash: str
    last_replayed: str | None
    replayed: int = 0
    stripped: int = 0
    store_hits: int = 0
    n_messages: int = 0
    client_model: str | None = None
    tools_hash: str = ""
    notes: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    ignored: list = field(default_factory=list)
    force_strip: bool = False
    role: str | None = None        # agent calls: lead / sub
    stage: str = "research"        # research / report (the reserve)
    ttl: str = "5m"                # the lifetime on this request's breakpoints (pricing of its writes, worst case)
    cache_head: str = "none"       # system / tools / none: where the prefix breakpoint went
    cache_tail: bool = False       # the top-level automatic breakpoint (end of the transcript)
    cache_why: str = "one-shot"    # tools / continues / head-seen / one-shot
    head_hash: str = ""            # system + tools prefix (registered once the request was answered)
    continues: int = 0             # assistant turns of this request that are this guard's answers, prefix unchanged


def _param_block(b) -> dict | None:
    """A response content block -> request form (what is sent back next turn)."""
    t = getattr(b, "type", None)
    if t == "thinking":
        sig = getattr(b, "signature", None)
        return {"type": "thinking", "thinking": getattr(b, "thinking", "") or "", "signature": sig} if sig else None
    if t == "redacted_thinking":
        return {"type": "redacted_thinking", "data": b.data}
    if t == "text":
        return {"type": "text", "text": b.text} if (b.text or "").strip() else None
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input if isinstance(b.input, dict) else {}}
    try:
        return b.model_dump(exclude_none=True)
    except Exception:  # noqa: BLE001
        return None


# ================================================================================================== config
@dataclass
class Config:
    arm: str
    port: int
    run_id: str
    model: str
    upstream: str
    key_file: str
    run_cap: float
    total_cap: float
    agent_cap: float | None
    ledger: str
    log_dir: str
    pricing: str
    default_effort: str | None
    class_efforts: dict
    effort_map: dict
    default_max_tokens: int
    max_tokens_cap: int
    cache_ttl: str
    replay: str
    tokens_per_byte: float
    overhead_tokens: int
    wait_inflight_s: float
    upstream_retries: int
    read_timeout: float
    store_max_mb: int
    status: str
    report_reserve: float = 0.22     # Karl 10-29: share of the run cap kept for the report stage
    lead_cache_1h: bool = False      # Karl 10-29: off unless the pilots' lead gaps say otherwise


def parse_args(argv=None) -> Config:
    ap = argparse.ArgumentParser(prog="anthropic_guard.py", description=__doc__.split("\n\n")[0])
    a = ap.add_argument
    a("--arm", default=env("GUARD_ARM"), help="arm name (ours / stock / ...) [GUARD_ARM]")
    a("--port", type=int, default=int(env("GUARD_PORT", "0") or 0), help="127.0.0.1 port [GUARD_PORT]")
    a("--run-id", default=env("GUARD_RUN_ID"), help="the run the spending counts against [GUARD_RUN_ID]")
    a("--model", default=env("GUARD_MODEL", "claude-sonnet-5-5"), help="[GUARD_MODEL]")
    a("--upstream", default=env("GUARD_UPSTREAM", DEFAULT_UPSTREAM),
      help="https://api.anthropic.com, or a loopback mock for tests [GUARD_UPSTREAM]")
    a("--key-file", default=env("GUARD_KEY_FILE", DEFAULT_KEY_FILE), help="[GUARD_KEY_FILE]")
    a("--run-cap-usd", type=float, default=float(env("GUARD_RUN_CAP_USD", "0") or 0), help="[GUARD_RUN_CAP_USD]")
    a("--total-cap-usd", type=float, default=float(env("GUARD_TOTAL_CAP_USD", "0") or 0),
      help="all runs in the ledger together [GUARD_TOTAL_CAP_USD]")
    a("--agent-cap-usd", type=float, default=float(env("GUARD_AGENT_CAP_USD")) if env("GUARD_AGENT_CAP_USD") else None,
      help="optional: requests with tools are refused past this, tool-less ones (report stage) go on to the run cap "
           "[GUARD_AGENT_CAP_USD]")
    a("--ledger", default=env("GUARD_LEDGER"), help="the shared ledger file [GUARD_LEDGER]")
    a("--log-dir", default=env("GUARD_LOG_DIR"), help="costs-<run>.jsonl and summary-<run>.json [GUARD_LOG_DIR]")
    a("--pricing", default=env("GUARD_PRICING", DEFAULT_PRICING), help="[GUARD_PRICING]")
    a("--default-effort", default=env("GUARD_DEFAULT_EFFORT"),
      help="effort for requests without one and without a class effort; empty = none (API default) "
           "[GUARD_DEFAULT_EFFORT]")
    a("--class-efforts", default=env("GUARD_CLASS_EFFORTS", ""), help="'agent=medium,extract=low' [GUARD_CLASS_EFFORTS]")
    a("--effort-map", default=env("GUARD_EFFORT_MAP", ""),
      help="request effort names -> API levels, 'xhigh=high'; 'x=' sends none [GUARD_EFFORT_MAP]")
    a("--default-max-tokens", type=int, default=int(env("GUARD_DEFAULT_MAX_TOKENS", "32000")),
      help="when the request names none [GUARD_DEFAULT_MAX_TOKENS]")
    a("--max-tokens-cap", type=int, default=int(env("GUARD_MAX_TOKENS_CAP", "64000")),
      help="requests asking for more are clamped (thinking + answer) [GUARD_MAX_TOKENS_CAP]")
    a("--report-reserve", type=float, default=float(env("GUARD_REPORT_RESERVE", "0.22")),
      help="share of the run cap kept for the report stage: requests not identified as report stage are refused at "
           "(1 - this) x the run cap; 0 = off [GUARD_REPORT_RESERVE]")
    a("--cache-ttl", choices=("5m",), default=env("GUARD_CACHE_TTL", "5m"),
      help="lifetime of every cache breakpoint; a 1-hour lifetime exists only for the lead (--lead-cache-1h) "
           "[GUARD_CACHE_TTL]")
    a("--lead-cache-1h", type=int, choices=(0, 1), default=int(env("GUARD_LEAD_CACHE_1H", "0")),
      help="1 = the lead agent's breakpoints live 1 hour (off by default; decide from tools/lead_gaps.py after the "
           "pilots) [GUARD_LEAD_CACHE_1H]")
    a("--thinking-replay", choices=("store", "strip"), default=env("GUARD_THINKING_REPLAY", "store"),
      help="[GUARD_THINKING_REPLAY]")
    a("--input-tokens-per-byte", type=float, default=float(env("GUARD_INPUT_TOKENS_PER_BYTE", "1.0")),
      help="worst-case input tokens per request byte; 1.0 is an upper bound [GUARD_INPUT_TOKENS_PER_BYTE]")
    a("--overhead-tokens", type=int, default=int(env("GUARD_OVERHEAD_TOKENS", "2000")),
      help="added to the worst-case input (the API's tool-use prompt) [GUARD_OVERHEAD_TOKENS]")
    a("--wait-inflight-s", type=float, default=float(env("GUARD_WAIT_INFLIGHT_S", "900")),
      help="how long a request waits for running ones to settle before it is refused [GUARD_WAIT_INFLIGHT_S]")
    a("--upstream-retries", type=int, default=int(env("GUARD_UPSTREAM_RETRIES", "2")),
      help="retries of 429 / 5xx / 529 answers that came before any output [GUARD_UPSTREAM_RETRIES]")
    a("--read-timeout", type=float, default=float(env("GUARD_READ_TIMEOUT_S", "900")), help="[GUARD_READ_TIMEOUT_S]")
    a("--store-max-mb", type=int, default=int(env("GUARD_STORE_MAX_MB", "512")),
      help="memory for kept thinking blocks [GUARD_STORE_MAX_MB]")
    a("--status", default=env("GUARD_STATUS", "draft"), help="draft | measured (shown in the log) [GUARD_STATUS]")
    ns = ap.parse_args(argv)
    for name in ("arm", "run_id", "ledger", "log_dir"):
        if not getattr(ns, name):
            ap.error(f"--{name.replace('_', '-')} is required (or its GUARD_* variable)")
    if not ns.port:
        ap.error("--port is required")
    if ns.run_cap_usd <= 0 or ns.total_cap_usd <= 0:
        ap.error("--run-cap-usd and --total-cap-usd must be > 0")
    de = ns.default_effort.strip().lower() if ns.default_effort else None
    if de:
        de = EFFORT_ALIASES.get(de, de)
        if de not in API_EFFORTS:
            ap.error(f"--default-effort {de!r} is not one of {', '.join(API_EFFORTS)}")
    if not 1 <= ns.max_tokens_cap <= MODEL_MAX_OUTPUT:
        ap.error(f"--max-tokens-cap must be 1..{MODEL_MAX_OUTPUT}")
    if not 0.0 <= ns.report_reserve < 1.0:
        ap.error("--report-reserve must be 0 <= r < 1 (a share of the run cap)")
    if ns.cache_ttl != "5m":            # an environment default skips argparse's choices check
        ap.error("--cache-ttl: only 5m (a 1-hour lifetime is for the lead only: --lead-cache-1h 1)")
    if ns.lead_cache_1h not in (0, 1):
        ap.error("--lead-cache-1h must be 0 or 1")
    return Config(arm=ns.arm, port=ns.port, run_id=ns.run_id, model=ns.model, upstream=ns.upstream.rstrip("/"),
                  key_file=os.path.expanduser(ns.key_file), run_cap=ns.run_cap_usd, total_cap=ns.total_cap_usd,
                  agent_cap=ns.agent_cap_usd, ledger=ns.ledger, log_dir=ns.log_dir, pricing=ns.pricing,
                  default_effort=de, class_efforts=parse_effort_spec(ns.class_efforts, "class"),
                  effort_map=parse_effort_spec(ns.effort_map, "map"),
                  default_max_tokens=min(ns.default_max_tokens, ns.max_tokens_cap), max_tokens_cap=ns.max_tokens_cap,
                  cache_ttl=ns.cache_ttl, replay=ns.thinking_replay, tokens_per_byte=ns.input_tokens_per_byte,
                  overhead_tokens=ns.overhead_tokens, wait_inflight_s=ns.wait_inflight_s,
                  upstream_retries=ns.upstream_retries, read_timeout=ns.read_timeout, store_max_mb=ns.store_max_mb,
                  status=ns.status, report_reserve=ns.report_reserve, lead_cache_1h=bool(ns.lead_cache_1h))


def check_upstream(url: str) -> None:
    u = urlsplit(url)
    if u.hostname in LOOPBACK and u.scheme in ("http", "https"):
        return
    if u.scheme == "https" and u.hostname == "api.anthropic.com" and not u.port:
        return
    raise SystemExit(f"anthropic-guard: upstream {url!r} refused - only https://api.anthropic.com or a loopback mock")


def scrub_environment() -> list[str]:
    """Delete ANTHROPIC_* from this process's environment (names returned, values never read out)."""
    names = sorted(k for k in os.environ if k.upper().startswith("ANTHROPIC"))
    for k in names:
        del os.environ[k]
    return names


class KeyFileError(Exception):
    pass


def read_key(path: str) -> str:
    """The API key, read fresh for one request. Errors never contain the file's content."""
    try:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
    except OSError as e:
        raise KeyFileError(f"key file {path} cannot be read ({type(e).__name__})") from None
    if not key or any(c.isspace() for c in key):
        raise KeyFileError(f"key file {path} does not hold one key")
    return key


def key_file_note(path: str) -> str:
    """A start-up check of the key file by stat() only (it is not read here)."""
    try:
        st = os.stat(path)
    except OSError:
        return f"key file {path}: MISSING (requests will fail until it exists)"
    note = f"key file {path}: present"
    if st.st_mode & 0o077:
        note += f" - WARNING: mode {oct(st.st_mode & 0o777)} lets others read it (chmod 600)"
    return note


# ================================================================================================== the guard
class ClientGone(Exception):
    pass


class SSEOut:
    """OpenAI chat.completion.chunk events to the client, chunked HTTP/1.1."""

    def __init__(self, h: BaseHTTPRequestHandler, model: str, include_usage: bool):
        self.h, self.model, self.include_usage = h, model, include_usage
        self.started = False
        self.id = f"chatcmpl-{os.urandom(12).hex()}"
        self.created = int(time.time())
        self.last_write = time.time()
        self.tools: dict[int, int] = {}
        self.args_sent: dict[int, bool] = {}

    def _w(self, data: bytes) -> None:
        try:
            self.h.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
            self.h.wfile.flush()
        except OSError as e:
            raise ClientGone(str(e)) from None
        self.last_write = time.time()

    def begin(self) -> None:
        if self.started:
            return
        try:
            self.h.send_response(200)
            self.h.send_header("Content-Type", "text/event-stream")
            self.h.send_header("Cache-Control", "no-cache")
            self.h.send_header("Transfer-Encoding", "chunked")
            self.h.end_headers()
        except OSError as e:
            raise ClientGone(str(e)) from None
        self.started = True
        self.chunk({"role": "assistant", "content": ""})

    def chunk(self, delta: dict, finish: str | None = None, extra: dict | None = None) -> None:
        obj = {"id": self.id, "object": "chat.completion.chunk", "created": self.created, "model": self.model,
               "choices": [{"index": 0, "delta": delta, "logprobs": None, "finish_reason": finish}]}
        if extra:
            obj.update(extra)
        self._w(b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n")

    def usage(self, usage: dict, extra: dict | None = None) -> None:
        obj = {"id": self.id, "object": "chat.completion.chunk", "created": self.created, "model": self.model,
               "choices": [], "usage": usage}
        if extra:
            obj.update(extra)
        self._w(b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n")

    def keepalive(self) -> None:
        if self.started and time.time() - self.last_write >= 10:
            self._w(b": keep-alive\n\n")

    def feed(self, ev) -> None:
        """One SDK stream event (raw events only; the SDK's derived text / input_json events are skipped)."""
        t = getattr(ev, "type", None)
        if t == "content_block_start" and getattr(ev.content_block, "type", None) == "tool_use":
            k = len(self.tools)
            self.tools[ev.index], self.args_sent[k] = k, False
            self.chunk({"tool_calls": [{"index": k, "id": ev.content_block.id, "type": "function",
                                        "function": {"name": ev.content_block.name, "arguments": ""}}]})
            return
        if t == "content_block_delta":
            d = ev.delta
            if d.type == "text_delta" and d.text:
                self.chunk({"content": d.text})
                return
            if d.type == "input_json_delta" and ev.index in self.tools and d.partial_json:
                k = self.tools[ev.index]
                self.args_sent[k] = True
                self.chunk({"tool_calls": [{"index": k, "function": {"arguments": d.partial_json}}]})
                return
        if t == "content_block_stop" and ev.index in self.tools and not self.args_sent[self.tools[ev.index]]:
            k = self.tools[ev.index]
            self.args_sent[k] = True
            self.chunk({"tool_calls": [{"index": k, "function": {"arguments": "{}"}}]})
            return
        self.keepalive()

    def error(self, message: str, typ: str, code) -> None:
        self._w(b"data: " + json.dumps({"error": {"message": message, "type": typ, "code": code}}).encode() + b"\n\n")

    def done(self) -> None:
        self._w(b"data: [DONE]\n\n")
        try:
            self.h.wfile.write(b"0\r\n\r\n")
            self.h.wfile.flush()
        except OSError:
            pass


def oa_usage(u: dict) -> dict:
    prompt = u["input_tokens"] + u["cache_creation_input_tokens"] + u["cache_read_input_tokens"]
    d = {"prompt_tokens": prompt, "completion_tokens": u["output_tokens"], "total_tokens": prompt + u["output_tokens"],
         "prompt_tokens_details": {"cached_tokens": u["cache_read_input_tokens"]}}
    if u.get("thinking_tokens") is not None:
        d["completion_tokens_details"] = {"reasoning_tokens": u["thinking_tokens"]}
    return d


def err_body(message: str, typ: str, code) -> dict:
    return {"error": {"message": scrub(message), "type": typ, "code": code, "param": None}}


class Guard:
    def __init__(self, cfg: Config):
        import anthropic                       # imported here: the module stays importable for the unit tests

        self.anthropic = anthropic
        self.cfg = cfg
        check_upstream(cfg.upstream)
        self.rates = load_rates(cfg.pricing, cfg.model)
        Path(cfg.log_dir).mkdir(parents=True, exist_ok=True)
        self.ledger = Ledger(cfg.ledger, cfg.run_id, cfg.arm, cfg.run_cap, cfg.total_cap, cfg.agent_cap,
                             report_reserve=cfg.report_reserve)
        self.store = ReplayStore(cfg.store_max_mb * 1024 * 1024)
        self.toolsets: OrderedDict = OrderedDict()
        self.heads: OrderedDict = OrderedDict()   # system + tools prefixes already sent (and answered) in this run
        self.tlock = threading.Lock()
        self.replay_disabled = False           # set when the API refuses the binding beta (logged)
        self.log_path = Path(cfg.log_dir) / f"costs-{_safe_name(cfg.run_id)}.jsonl"
        self.summary_path = Path(cfg.log_dir) / f"summary-{_safe_name(cfg.run_id)}.json"
        self.gap_path = Path(cfg.log_dir) / f"lead-gaps-{_safe_name(cfg.run_id)}.jsonl"
        self.lead_last: dict = {"start": None, "end": None}     # the lead's previous call (this process)
        self._ids = itertools.count(1)
        self._log_lock = threading.Lock()
        self.started = time.time()
        self.counts = {"requests": 0, "refused": 0, "errors": 0, "rejected": 0}
        self.http = anthropic.DefaultHttpxClient(follow_redirects=False)
        # the base client never carries the key: each request gets a copy with that request's key (with_options)
        self.base = anthropic.Anthropic(api_key="no-key-in-the-base-client", base_url=cfg.upstream,
                                        http_client=self.http, max_retries=0,
                                        timeout=anthropic.Timeout(cfg.read_timeout, connect=20.0))
        self.write_summary(self.ledger.snapshot())     # from the start: the caps and what the ledger already holds

    # ------------------------------------------------------------------ logging
    def log(self, rec: dict) -> None:
        line = scrub(json.dumps(rec, ensure_ascii=False, sort_keys=True))
        with self._log_lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ------------------------------------------------------------------ the lead's gaps (Karl 10-29: TTL decision)
    def _lead_gap_start(self, t: float) -> dict:
        """A lead call is being sent: its gap to the previous lead call (start to start = what the cache sees, since
        every lead call reads and so refreshes the cached prefix) and its idle time (previous end to this start)."""
        with self.tlock:
            prev_s, prev_e = self.lead_last["start"], self.lead_last["end"]
            self.lead_last["start"] = t
        return {"gap_s": round(t - prev_s, 3) if prev_s is not None else None,
                "idle_s": round(max(0.0, t - prev_e), 3) if prev_e is not None else None}

    def _lead_gap_log(self, gap: dict, plan: Plan, rec: dict, t_send: float, usage: dict | None, event: str) -> None:
        """One line per lead call in lead-gaps-<run>.jsonl: times and token counts only, never prompt content."""
        now = time.time()
        with self.tlock:
            self.lead_last["end"] = now
        u = usage or {}
        line = {"t": round(t_send, 3), "id": rec.get("id"), "run": self.cfg.run_id, "arm": self.cfg.arm,
                "gap_s": gap["gap_s"], "idle_s": gap["idle_s"], "duration_s": round(now - t_send, 3),
                "ttl": plan.ttl, "cache_tail": plan.cache_tail, "event": event, "n_msgs": plan.n_messages,
                "prompt_tokens": (int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
                                  + int(u.get("cache_read_input_tokens") or 0)) if usage else None,
                "cache_read": int(u.get("cache_read_input_tokens") or 0) if usage else None,
                "cache_write": int(u.get("cache_creation_input_tokens") or 0) if usage else None}
        try:
            with self._log_lock, open(self.gap_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, sort_keys=True) + "\n")
        except OSError as e:
            print(f"anthropic-guard: lead gap not logged: {e}", file=sys.stderr, flush=True)

    def write_summary(self, snap: dict) -> None:
        run = snap["run"]
        tk = run["tokens"]
        prompt = tk["input"] + tk["cache_write_5m"] + tk["cache_write_1h"] + tk["cache_read"]
        s = {"version": VERSION, "arm": self.cfg.arm, "run": self.cfg.run_id, "model": self.cfg.model,
             "status": self.cfg.status, "updated": round(time.time(), 3),
             "caps_usd": {"run": self.cfg.run_cap, "total": self.cfg.total_cap, "agent": self.cfg.agent_cap,
                          "research": self.ledger.research_cap},
             "report_reserve": self.cfg.report_reserve,
             "stage_spent_usd": {k: round(v, 6) for k, v in (run.get("stage_usd") or {}).items()},
             "cache": {"rule": "reused-prefixes", "ttl": self.cfg.cache_ttl, "lead_1h": self.cfg.lead_cache_1h},
             "run_spent_usd": round(run["spent_usd"], 6), "total_spent_usd": round(snap["total_spent_usd"], 6),
             "charged_unknown_usd": round(run["charged_unknown_usd"], 6), "requests": run["requests"],
             "refused": run["refused"], "errors": run["errors"], "tokens": tk,
             "cache_read_share_of_prompt": round(tk["cache_read"] / prompt, 4) if prompt else None,
             "rates_usd_per_mtok": {"input": self.rates.input, "output": self.rates.output,
                                    "cache_write_5m": self.rates.cache_write_5m,
                                    "cache_write_1h": self.rates.cache_write_1h, "cache_read": self.rates.cache_read,
                                    "checked": self.rates.checked}}
        tmp = self.summary_path.with_name(self.summary_path.name + ".tmp")
        tmp.write_text(scrub(json.dumps(s, indent=1, sort_keys=True)) + "\n", encoding="utf-8")
        os.replace(tmp, self.summary_path)

    # ------------------------------------------------------------------ tool sets seen per conversation
    def _remember_tools(self, head: str, tools: list) -> None:
        with self.tlock:
            self.toolsets[head] = [dict(t) for t in tools]
            self.toolsets.move_to_end(head)
            while len(self.toolsets) > 2000:
                self.toolsets.popitem(last=False)

    def _recall_tools(self, head: str) -> list | None:
        with self.tlock:
            t = self.toolsets.get(head)
            return [dict(x) for x in t] if t is not None else None

    # ------------------------------------------------------------------ system + tools prefixes seen in this run
    def _head_seen(self, head: str) -> bool:
        with self.tlock:
            return head in self.heads

    def note_sent(self, plan: Plan) -> None:
        """A request was answered: its system + tools prefix counts as seen (the next request with it is cached)."""
        if not plan.head_hash:
            return
        with self.tlock:
            self.heads[plan.head_hash] = True
            self.heads.move_to_end(plan.head_hash)
            while len(self.heads) > 5000:
                self.heads.popitem(last=False)

    # ------------------------------------------------------------------ effort
    def pick_effort(self, req: dict, cls: str) -> tuple[str | None, str]:
        raw = req.get("reasoning_effort")
        if raw in (None, "") and isinstance(req.get("reasoning"), dict):
            raw = req["reasoning"].get("effort")
        if raw in (None, "") and isinstance(req.get("output_config"), dict):
            raw = req["output_config"].get("effort")
        if raw not in (None, ""):
            return map_effort(raw, self.cfg.effort_map), "request"
        if cls in self.cfg.class_efforts:
            return self.cfg.class_efforts[cls], f"class:{cls}"
        if self.cfg.default_effort:
            return self.cfg.default_effort, "default"
        return None, "api-default"

    # ------------------------------------------------------------------ OpenAI -> Anthropic
    def translate(self, req: dict, force_strip: bool = False) -> Plan:
        cfg = self.cfg
        if not isinstance(req, dict):
            raise TranslateError(400, "the request body must be a JSON object")
        oa_msgs = req.get("messages")
        if not isinstance(oa_msgs, list) or not oa_msgs:
            raise TranslateError(400, "messages must be a non-empty list")
        if req.get("n") not in (None, 1):
            raise TranslateError(400, "n > 1 is not supported by this endpoint")
        notes: set = set()
        dropped = sorted(k for k in req if k in DROPPED_FIELDS or k.startswith("strata_"))
        ignored = sorted(k for k in req if k not in KNOWN_FIELDS and k not in dropped)
        cls = classify(req)

        # tools: name-sorted, so the cached prefix does not depend on the client's order
        oa_tools = list(req.get("tools") or [])
        for f in req.get("functions") or []:
            oa_tools.append({"type": "function", "function": f})
        tools = []
        for t in oa_tools:
            if not isinstance(t, dict) or t.get("type", "function") != "function" or not isinstance(t.get("function"), dict):
                raise TranslateError(400, "only function tools are supported")
            f = t["function"]
            if not f.get("name"):
                raise TranslateError(400, "a tool has no name")
            schema = f.get("parameters") if isinstance(f.get("parameters"), dict) else {"type": "object",
                                                                                         "properties": {}}
            if schema.get("type") != "object":
                schema = {"type": "object", "properties": {"value": schema}, "required": ["value"]}
                notes.add("non_object_tool_schema_wrapped")
            d = {"name": str(f["name"]), "input_schema": schema}
            if f.get("description"):
                d["description"] = str(f["description"])
            if f.get("strict") is True:
                d["strict"] = True
            tools.append(d)
        tools.sort(key=lambda d: d["name"])

        # system prompt (the leading system / developer messages) and the turns
        system: list = []
        entries: list = []
        seen_turn = False
        for i, m in enumerate(oa_msgs):
            if not isinstance(m, dict):
                raise TranslateError(400, f"messages[{i}] is not an object")
            role = m.get("role")
            if role in ("system", "developer"):
                text = _text_of(m.get("content"))
                if not seen_turn:
                    if text.strip():
                        system.append(_tb(text))
                elif text.strip():
                    notes.add("late_system_as_user")
                    entries.append(["user", [_tb("[system note]\n" + text)], None])
                continue
            seen_turn = True
            if role == "user":
                blocks = _user_blocks(m.get("content"), notes)
                if not blocks:
                    notes.add("empty_user_message")
                    blocks = [_tb("(empty message)")]
                entries.append(["user", blocks, None])
            elif role == "assistant":
                text, blocks = _assistant_blocks(m, notes)
                if not blocks:
                    notes.add("empty_assistant_skipped")
                    continue
                entries.append(["assistant", blocks, {"text": text,
                                                      "tool_uses": [b for b in blocks if b["type"] == "tool_use"]}])
            elif role in ("tool", "function"):
                content = _text_of(m.get("content"))
                entries.append(["user", [{"type": "tool_result", "tool_use_id": _tid(m.get("tool_call_id") or m.get("name"), i),
                                          "content": content if content.strip() else "(empty result)"}], None])
            else:
                raise TranslateError(400, f"messages[{i}]: unknown role {role!r}")
        merged: list = []
        for e in entries:                     # consecutive user entries -> one user turn, tool results first
            if merged and e[0] == "user" and merged[-1][0] == "user":
                merged[-1][1] = merged[-1][1] + e[1]
            else:
                merged.append([e[0], list(e[1]), e[2]])
        for e in merged:
            if e[0] == "user":
                e[1] = [b for b in e[1] if b["type"] == "tool_result"] + [b for b in e[1] if b["type"] != "tool_result"]
        if not merged:
            raise TranslateError(400, "no user or assistant messages")
        if merged[0][0] != "user":
            merged.insert(0, ["user", [_tb("(conversation start)")], None])
            notes.add("leading_user_inserted")
        if merged[-1][0] == "assistant":
            raise TranslateError(400, f"the last message is an assistant message (prefill); {cfg.model} does not "
                                      "accept assistant prefill")

        # tool calls in the history but no tools (our build's wrap-up step)
        has_tool_blocks = any(b["type"] in ("tool_use", "tool_result") for e in merged for b in e[1])
        head = _sha(_canon(["system", _view(system)]), _canon([merged[0][0], _view(merged[0][1])]))
        tool_choice = None
        as_text = False
        if tools:
            self._remember_tools(head, tools)
        elif has_tool_blocks:
            again = self._recall_tools(head)
            if again is not None:
                tools, tool_choice = again, {"type": "none"}
                notes.add("tools_reattached_tool_choice_none")
            else:
                as_text = True
                notes.add("tool_blocks_as_text")
        if tools and tool_choice is None:
            tc = req.get("tool_choice")
            if tc == "none":
                tool_choice = {"type": "none"}
            elif tc == "required" or isinstance(tc, dict):
                notes.add("forced_tool_choice_sent_as_auto")      # the model refuses forced tool use
            if req.get("parallel_tool_calls") is False and tool_choice is None:
                tool_choice = {"type": "auto", "disable_parallel_tool_use": True}

        # assistant turns: the answer's own blocks where the guard has them; thinking only where still valid
        replay = cfg.replay == "store" and not force_strip and not self.replay_disabled and not as_text
        base = _sha(_canon(["system", _view(system)]), _canon(["tools", [_view([dict(t, type="tool")])
                                                                         for t in tools]]))
        h = base
        last: str | None = None
        n_rep = n_strip = n_hit = n_cont = 0
        out: list = []
        for role, blocks, meta in merged:
            if role == "assistant":
                rec, prefix_ok = self.store.find(turn_key(meta["text"], meta["tool_uses"]), h)
                if rec is not None and (rec.text != meta["text"].strip() or
                                        rec.calls != [[b["id"], b["name"]] for b in meta["tool_uses"]]):
                    rec = None
                    notes.add("store_mismatch")
                if rec is not None:
                    n_hit += 1
                    n_cont += int(prefix_ok)          # this guard's answer, under the prefix it was made under
                    use = rec.blocks
                    if rec.has_thinking:
                        if replay and prefix_ok and (rec.chain == last or last is None):
                            last = rec.rid
                            n_rep += 1
                        else:
                            use = [b for b in use if b["type"] not in THINKING]
                            n_strip += 1
                    blocks = [dict(b) for b in use]
            out.append({"role": role, "content": blocks})
            h = _roll(h, role, blocks)
        if as_text:
            for m in out:
                nb = []
                for b in m["content"]:
                    if b["type"] == "tool_use":
                        nb.append(_tb(f"[tool call {b['name']}: {json.dumps(b['input'], ensure_ascii=False, sort_keys=True)}]"))
                    elif b["type"] == "tool_result":
                        nb.append(_tb(f"[tool result for {b['tool_use_id']}]\n{_text_of(b.get('content'))}"))
                    elif b["type"] not in THINKING:
                        nb.append(b)
                m["content"] = nb or [_tb("(empty)")]

        # the request. Caching (Karl 10-29): only prefixes that are reused within the run.
        #  * tail (top-level automatic breakpoint, end of the transcript): the request will grow - it has tools (an
        #    agent loop: the next call is this one + the answer + tool results) or continues a conversation this guard
        #    answered (n_cont);
        #  * head (last system block, else last tool): on those, and when this system + tools prefix was already sent
        #    once in this run (a repeating system prompt);
        #  * neither on a one-shot request (no tools, no earlier answer of ours, a new prefix): no cache_control.
        role = agent_role(req, cls)
        stage = stage_of(cls)
        sys_param = [dict(b) for b in system]
        tools_param = [dict(t) for t in tools]
        grows = bool(tools) or n_cont > 0
        head_seen = bool(sys_param or tools_param) and self._head_seen(base)
        why = "tools" if tools else "continues" if n_cont else "head-seen" if head_seen else "one-shot"
        ttl = "1h" if (cfg.lead_cache_1h and role == "lead") else cfg.cache_ttl
        cc = {"type": "ephemeral"} if ttl == "5m" else {"type": "ephemeral", "ttl": "1h"}
        cache_head = "none"
        if grows or head_seen:
            if sys_param:
                sys_param[-1]["cache_control"] = dict(cc)
                cache_head = "system"
            elif tools_param:
                tools_param[-1]["cache_control"] = dict(cc)
                cache_head = "tools"
        effort, esrc = self.pick_effort(req, cls)
        asked = req.get("max_completion_tokens") or req.get("max_tokens")
        try:
            asked = int(asked) if asked is not None else None
        except (TypeError, ValueError):
            raise TranslateError(400, "max_tokens must be an integer") from None
        if asked is not None and asked < 1:
            raise TranslateError(400, "max_tokens must be >= 1")
        mt = asked if asked is not None else cfg.default_max_tokens
        if mt > cfg.max_tokens_cap:
            notes.add(f"max_tokens_clamped_from_{mt}")
            mt = cfg.max_tokens_cap
        thinking: dict = {"type": "adaptive", "display": "omitted"}
        params: dict = {"model": cfg.model, "max_tokens": mt, "messages": out, "thinking": thinking}
        if grows:
            params["cache_control"] = dict(cc)
        if cfg.replay == "store" and not force_strip and not self.replay_disabled:
            thinking["block_binding"] = {"prefix_mismatch_behavior": "drop_block"}
            params["betas"] = [BETA_BINDING]
        if sys_param:
            params["system"] = sys_param
        if tools_param:
            params["tools"] = tools_param
        if tool_choice:
            params["tool_choice"] = tool_choice
        oc: dict = {}
        if effort:
            oc["effort"] = effort
        rf = req.get("response_format")
        if isinstance(rf, dict) and rf.get("type") == "json_schema":
            schema = (rf.get("json_schema") or {}).get("schema")
            if isinstance(schema, dict):
                oc["format"] = {"type": "json_schema", "schema": schema}
        elif isinstance(rf, dict) and rf.get("type") == "json_object":
            notes.add("json_object_not_enforced")
        if oc:
            params["output_config"] = oc
        stop = req.get("stop")
        if isinstance(stop, str):
            stop = [stop]
        if isinstance(stop, list):
            stop = [s for s in stop if isinstance(s, str) and s.strip()]
            if stop:
                params["stop_sequences"] = stop
        nbytes = len(json.dumps({k: params.get(k) for k in ("system", "tools", "messages")},
                                ensure_ascii=False).encode())
        so = req.get("stream_options") if isinstance(req.get("stream_options"), dict) else {}
        return Plan(params=params, cls=cls, effort=effort, effort_source=esrc, max_tokens=mt,
                    est_in_tokens=int(nbytes * cfg.tokens_per_byte) + cfg.overhead_tokens, request_bytes=nbytes,
                    has_tools=bool(tools) and tool_choice != {"type": "none"}, stream=bool(req.get("stream")),
                    include_usage=bool(so.get("include_usage")), prefix_hash=h, last_replayed=last, replayed=n_rep,
                    stripped=n_strip, store_hits=n_hit, n_messages=len(oa_msgs),
                    client_model=str(req.get("model")) if req.get("model") is not None else None,
                    tools_hash=base[:12], notes=sorted(notes), dropped=dropped, ignored=ignored,
                    force_strip=force_strip, role=role, stage=stage, ttl=ttl, cache_head=cache_head,
                    cache_tail=grows, cache_why=why, head_hash=base if (sys_param or tools_param) else "",
                    continues=n_cont)

    def remember(self, plan: Plan, content: list) -> None:
        """Keep an answer's blocks for the next time the client sends this turn."""
        blocks = [b for b in (_param_block(x) for x in content) if b is not None]
        if not any(b["type"] not in THINKING for b in blocks):
            return
        text = "".join(b.get("text", "") for b in blocks if b["type"] == "text")
        tus = [b for b in blocks if b["type"] == "tool_use"]
        rec = Rec(rid=self.store.new_id(), blocks=blocks, prefix=plan.prefix_hash, chain=plan.last_replayed,
                  has_thinking=any(b["type"] in THINKING for b in blocks), text=text.strip(),
                  calls=[[b["id"], b["name"]] for b in tus], size=len(_canon(blocks)) + 200)
        self.store.put(turn_key(text, tus), rec)

    # ------------------------------------------------------------------ one request
    def refusal_text(self, info: dict, plan: Plan, waited: float | None = None) -> str:
        cap = info["cap"]
        what = {"run": f"run cap of run {self.cfg.run_id}", "agent": f"agent cap (requests with tools) of run "
                f"{self.cfg.run_id}", "total": "total cap (all arms and runs in the ledger)",
                "research": f"research cap of run {self.cfg.run_id} (the run cap ${self.cfg.run_cap:.2f} less the "
                            f"{self.cfg.report_reserve * 100:.0f} % kept for the report stage; this request is "
                            f"research: class {plan.cls})"}[cap]
        s = (f"budget guard ({self.cfg.arm}): cap reached - the {what} ${info['cap_usd']:.2f} would be passed - spent "
             f"${info['spent_usd']:.4f}")
        if waited is not None:
            s += (f" + ${info['inflight_usd']:.4f} reserved by requests still running (waited {waited:.0f} s for "
                  "them)")
        s += (f" + this request's worst case ${info['worst_usd']:.4f} (max_tokens {plan.max_tokens:,}, up to "
              f"{plan.est_in_tokens:,} input tokens at the cache-write rate) > ${info['cap_usd']:.2f}. Refused; "
              "nothing was sent to Anthropic.")
        if cap == "research":
            s += " Report-stage requests may still use the rest of the run cap."
        return s

    def handle_chat(self, h: BaseHTTPRequestHandler, body: bytes) -> None:
        cfg = self.cfg
        t0 = time.time()
        rec: dict = {"t": round(t0, 3), "id": next(self._ids), "arm": cfg.arm, "run": cfg.run_id, "model": cfg.model}
        try:
            req = json.loads(body or b"null")
        except ValueError:
            self.counts["rejected"] += 1
            rec.update(event="rejected", status=400, error="body is not JSON")
            self.log(rec)
            return send_json(h, 400, err_body("the request body is not JSON", "invalid_request_error", "bad_json"))
        try:
            plan = self.translate(req)
        except TranslateError as e:
            self.counts["rejected"] += 1
            rec.update(event="rejected", status=e.status, error=e.message)
            self.log(rec)
            return send_json(h, e.status, err_body(e.message, e.code, "translation"))
        worst = worst_case(plan.est_in_tokens, plan.max_tokens, self.rates, plan.ttl)
        rec.update(cls=plan.cls, role=plan.role, stage=plan.stage, effort=plan.effort, effort_source=plan.effort_source,
                   stream=plan.stream, n_msgs=plan.n_messages, n_tools=len(plan.params.get("tools") or []),
                   max_tokens=plan.max_tokens, request_bytes=plan.request_bytes, est_in_tokens=plan.est_in_tokens,
                   worst_usd=round(worst, 6),
                   cache={"ttl": plan.ttl if (plan.cache_tail or plan.cache_head != "none") else None,
                          "marker": plan.cache_head, "auto_tail": plan.cache_tail, "why": plan.cache_why,
                          "continues": plan.continues, "prefix": plan.tools_hash},
                   replay={"mode": "strip" if (cfg.replay == "strip" or self.replay_disabled) else "store",
                           "store_hits": plan.store_hits, "thinking_replayed": plan.replayed,
                           "thinking_stripped": plan.stripped},
                   notes=plan.notes, dropped=plan.dropped, ignored=plan.ignored, client_model=plan.client_model)
        # reserve the worst case (waits while requests still running hold the rest of a cap)
        waited = 0.0
        while True:
            try:
                r = self.ledger.reserve(worst, plan.has_tools, research=plan.stage == "research")
            except LedgerError as e:
                rec.update(event="error", status=500, error=str(e))
                self.log(rec)
                return send_json(h, 500, err_body(f"budget guard: {e}; refusing all requests", "guard_error",
                                                  "ledger"))
            if "ok" in r:
                res = r["ok"]
                break
            if "refuse" in r or waited >= cfg.wait_inflight_s:
                info = r.get("refuse") or r["wait"]
                if "wait" in r:
                    self.ledger.note_refused()
                msg = self.refusal_text(info, plan, waited if "wait" in r else None)
                self.counts["refused"] += 1
                rec.update(event="refused", status=402, cap=info["cap"], cap_usd=info["cap_usd"],
                           spent_usd=round(info["spent_usd"], 6), inflight_usd=round(info["inflight_usd"], 6),
                           waited_s=round(waited, 1), error=msg)
                self.log(rec)
                print(f"anthropic-guard: {msg}", file=sys.stderr, flush=True)
                try:
                    self.write_summary(self.ledger.snapshot())
                except (OSError, LedgerError):
                    pass
                return send_json(h, 402, err_body(msg, "budget_exceeded", f"{info['cap']}_cap"))
            time.sleep(0.5)
            waited = time.time() - t0
        rec["waited_s"] = round(waited, 1)
        self.counts["requests"] += 1
        try:
            self._send(h, req, plan, rec, res, worst)
        finally:
            rec["duration_s"] = round(time.time() - t0, 3)
            self.log(rec)

    def _send(self, h, req: dict, plan: Plan, rec: dict, res: str, worst: float) -> None:
        cfg, A = self.cfg, self.anthropic
        try:
            key = read_key(cfg.key_file)
        except KeyFileError as e:
            self.ledger.settle(res, 0.0, error=True, stage=plan.stage)
            self.counts["errors"] += 1
            rec.update(event="error", status=500, error=str(e))
            return send_json(h, 500, err_body(f"budget guard: {e}", "guard_error", "key_file"))
        try:
            self._send_with(h, req, plan, rec, res, worst, key)
        finally:
            key = None                 # the request is over; the guard keeps no reference to the key

    def _send_with(self, h, req: dict, plan: Plan, rec: dict, res: str, worst: float, key: str) -> None:
        cfg, A = self.cfg, self.anthropic

        def kscrub(s: object) -> str:  # error texts: anything key-like, and this key verbatim, masked
            return scrub(s).replace(key, "[key]")
        client = self.base.with_options(api_key=key)
        sse = SSEOut(h, cfg.model, plan.include_usage) if plan.stream else None
        final = None
        start_usage = None
        fail = None                    # (http status, message, type, code, headers)
        unknown_all = False            # the request may have run, usage unknown -> charge the worst case
        gone = False
        attempt = 0
        sent = False
        t_send = time.time()
        gap = self._lead_gap_start(t_send) if plan.role == "lead" else None
        while True:
            start_usage = None
            try:
                sent = True
                with client.beta.messages.stream(**plan.params) as stream:
                    for ev in stream:
                        if ev.type == "message_start":
                            start_usage = usage_dict(ev.message.usage)
                            rec["ttfb_s"] = round(time.time() - t_send, 3)
                            if sse is not None:
                                sse.begin()
                        elif sse is not None:
                            sse.feed(ev)
                    final = stream.get_final_message()
                break
            except ClientGone:
                gone = True
                break
            except A.APIStatusError as e:
                st = int(getattr(e, "status_code", 0) or 0)
                msg = kscrub(_api_message(e))
                if start_usage is None and not (sse is not None and sse.started):
                    if st in RETRY_STATUSES and attempt < cfg.upstream_retries:
                        attempt += 1
                        time.sleep(_retry_after(e, attempt))
                        rec.setdefault("retries", []).append(st)
                        continue
                    beta_err = st == 400 and re.search(r"block_binding|thinking-binding|anthropic-beta", msg)
                    sig_err = st == 400 and plan.replayed and re.search(r"signature|thinking", msg, re.I)
                    if (beta_err or sig_err) and not plan.force_strip:
                        if beta_err:
                            self.replay_disabled = True
                            print("anthropic-guard: the API refused the thinking-binding beta - thinking blocks are "
                                  "no longer sent back (strip mode)", file=sys.stderr, flush=True)
                        rec["notes"] = list(rec.get("notes") or []) + ["strip_retry_after_400"]
                        rec["replay"] = dict(rec.get("replay") or {}, retried_without_thinking=True)
                        plan = self.translate(req, force_strip=True)
                        continue
                hdrs = {}
                ra = _header(e, "retry-after")
                if ra:
                    hdrs["Retry-After"] = ra
                out_st = st if st in (400, 401, 403, 404, 413, 422, 429) else 503 if st >= 500 else 502
                fail = (out_st, f"upstream {st}: {msg}", _api_type(e), f"upstream_{st}", hdrs)
                break
            except A.APIConnectionError as e:
                cause = e.__cause__
                refused = cause is not None and type(cause).__name__ in ("ConnectError", "ConnectTimeout")
                unknown_all = not refused and start_usage is None
                fail = (502, f"upstream connection failed ({type(e).__name__}"
                             f"{': ' + type(cause).__name__ if cause else ''})", "upstream_error", "upstream_connection",
                        {})
                break
            except Exception as e:  # noqa: BLE001 - always settle the reservation
                unknown_all = sent and start_usage is None
                fail = (502, kscrub(f"guard error: {type(e).__name__}: {e}"), "guard_error", "internal", {})
                break
        # ---- money
        usage = None
        cost = unknown = 0.0
        if final is not None:
            usage = usage_dict(final.usage)
            cost = price(usage, self.rates, plan.ttl)
        elif start_usage is not None:                       # cut off after it started: input known, output not
            usage = start_usage
            cost = input_side_price(start_usage, self.rates, plan.ttl)
            unknown = plan.max_tokens * self.rates.output / 1e6
            rec["usage_estimated"] = "input from message_start, output charged at max_tokens"
        elif unknown_all:
            unknown = worst
            rec["usage_estimated"] = "no usage seen; charged the reserved worst case"
        # the token totals count finished responses only; a cut-off one adds its money (above) but not its tokens
        snap = self.ledger.settle(res, cost, unknown, usage=usage if final is not None else None,
                                  ttl=plan.ttl, error=final is None, stage=plan.stage)
        rec.update(usage=usage, cost_usd=round(cost + unknown, 6), run_spent_usd=round(snap["run"]["spent_usd"], 6),
                   total_spent_usd=round(snap["total_spent_usd"], 6))
        try:
            self.write_summary(snap)
        except OSError as e:
            print(f"anthropic-guard: summary not written: {e}", file=sys.stderr, flush=True)
        if gap is not None:
            self._lead_gap_log(gap, plan, rec, t_send, usage if final is not None else None,
                               "ok" if final is not None else "client_gone" if gone else "error")
        if final is not None:
            self.note_sent(plan)
            prompt = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
            if prompt > plan.est_in_tokens:
                rec["estimate_exceeded"] = True
            rec.update(event="ok", status=200, stop_reason=final.stop_reason, msg_id=final.id)
            it = getattr(final, "input_transformations", None) or []
            if it:
                rec["input_transformations"] = [f"{getattr(x, 'type', '?')}:{getattr(x, 'reason', '')}" for x in it]
            if final.stop_reason == "refusal":
                sd = getattr(final, "stop_details", None)
                rec["refusal_category"] = getattr(sd, "category", None)
            try:
                self.remember(plan, final.content)
            except Exception as e:  # noqa: BLE001
                rec["notes"] = list(rec.get("notes") or []) + [f"store_failed:{type(e).__name__}"]
        elif gone:
            rec.update(event="client_gone", status=None)
        else:
            self.counts["errors"] += 1
            rec.update(event="error", status=fail[0], error=fail[1])
        # ---- answer
        if gone:
            return
        if final is None:
            st, msg, typ, code, hdrs = fail
            if sse is not None and sse.started:
                try:
                    sse.error(scrub(msg), typ, code)
                    sse.done()
                except ClientGone:
                    pass
                return
            return send_json(h, st, err_body(msg, typ, code), hdrs)
        text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text")
        calls = [{"id": b.id, "type": "function", "function": {"name": b.name, "arguments": json.dumps(
            b.input if isinstance(b.input, dict) else {}, ensure_ascii=False)}}
            for b in final.content if getattr(b, "type", None) == "tool_use"]
        finish = STOP_MAP.get(final.stop_reason or "end_turn", "stop")
        ou = oa_usage(usage)
        xg = {"x_guard": {"cost_usd": round(cost, 6), "run_spent_usd": rec["run_spent_usd"],
                          "total_spent_usd": rec["total_spent_usd"], "effort": plan.effort,
                          "cache_creation_input_tokens": usage["cache_creation_input_tokens"],
                          "cache_read_input_tokens": usage["cache_read_input_tokens"]}}
        if sse is not None:
            try:
                sse.chunk({}, finish=finish)
                if plan.include_usage:
                    sse.usage(ou, xg)
                sse.done()
            except ClientGone:
                rec["event"] = "client_gone_at_end"
            return
        msg = {"role": "assistant", "content": text if (text or not calls) else None}
        if calls:
            msg["tool_calls"] = calls
        if final.stop_reason == "refusal":
            sd = getattr(final, "stop_details", None)
            msg["refusal"] = getattr(sd, "explanation", None) or "refused"
        out = {"id": f"chatcmpl-{final.id}", "object": "chat.completion", "created": int(time.time()),
               "model": cfg.model, "choices": [{"index": 0, "message": msg, "logprobs": None, "finish_reason": finish}],
               "usage": ou}
        out.update(xg)
        send_json(h, 200, out)

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        snap = self.ledger.snapshot()
        return {"version": VERSION, "arm": self.cfg.arm, "run": self.cfg.run_id, "model": self.cfg.model,
                "status": self.cfg.status, "upstream_host": urlsplit(self.cfg.upstream).hostname,
                "cache": "on", "cache_rule": "reused-prefixes", "cache_ttl": self.cfg.cache_ttl,
                "lead_cache_1h": self.cfg.lead_cache_1h,
                "thinking_replay": "strip" if (self.cfg.replay == "strip" or self.replay_disabled) else "store",
                "caps_usd": {"run": self.cfg.run_cap, "total": self.cfg.total_cap, "agent": self.cfg.agent_cap,
                             "research": self.ledger.research_cap},
                "report_reserve": self.cfg.report_reserve,
                "stage_spent_usd": {k: round(v, 6) for k, v in (snap["run"].get("stage_usd") or {}).items()},
                "run_spent_usd": round(snap["run"]["spent_usd"], 6), "total_spent_usd": round(snap["total_spent_usd"], 6),
                "inflight": snap["inflight"], "inflight_usd": round(snap["inflight_usd"], 6),
                "requests": snap["run"]["requests"], "refused": snap["run"]["refused"],
                "efforts": {"default": self.cfg.default_effort, "class": self.cfg.class_efforts,
                            "map": self.cfg.effort_map},
                "max_tokens": {"default": self.cfg.default_max_tokens, "cap": self.cfg.max_tokens_cap},
                "store": self.store.stats(), "this_process": dict(self.counts), "started": round(self.started, 3)}


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def _api_message(e) -> str:
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:800]
    return str(getattr(e, "message", "") or e)[:800]


def _api_type(e) -> str:
    body = getattr(e, "body", None)
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return str(body["error"].get("type") or "upstream_error")
    return "upstream_error"


def _header(e, name: str) -> str | None:
    resp = getattr(e, "response", None)
    try:
        return resp.headers.get(name) if resp is not None else None
    except Exception:  # noqa: BLE001
        return None


def _retry_after(e, attempt: int) -> float:
    ra = _header(e, "retry-after")
    try:
        if ra is not None:
            return min(60.0, max(0.0, float(ra)))
    except ValueError:
        pass
    return min(30.0, 2.0 * 2 ** (attempt - 1))


def send_json(h: BaseHTTPRequestHandler, code: int, obj: dict, headers: dict | None = None) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode()
    try:
        h.send_response(code)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            h.send_header(k, v)
        h.end_headers()
        h.wfile.write(data)
        h.wfile.flush()
    except OSError:
        pass
    h.close_connection = True


# ================================================================================================== HTTP
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "anthropic-guard"

    def log_message(self, fmt, *args):  # the JSONL log is the record (and request lines carry nothing useful)
        pass

    @property
    def guard(self) -> Guard:
        return self.server.guard  # type: ignore[attr-defined]

    def do_GET(self):
        p = urlsplit(self.path).path.rstrip("/")
        if p == "/health":
            return send_json(self, 200, {"ok": True, "arm": self.guard.cfg.arm, "run": self.guard.cfg.run_id})
        if p == "/v1/models":
            return send_json(self, 200, {"object": "list", "data": [
                {"id": self.guard.cfg.model, "object": "model", "created": 0, "owned_by": "anthropic"}]})
        if p == "/v1/guard/status":
            try:
                return send_json(self, 200, self.guard.status())
            except LedgerError as e:
                return send_json(self, 500, err_body(str(e), "guard_error", "ledger"))
        return send_json(self, 404, err_body(f"unknown path {p}", "not_found", 404))

    def do_POST(self):
        p = urlsplit(self.path).path.rstrip("/")
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        if p not in ("/v1/chat/completions", "/chat/completions"):
            return send_json(self, 404, err_body(f"unknown path {p}", "not_found", 404))
        try:
            self.guard.handle_chat(self, body)
        except Exception as e:  # noqa: BLE001
            print(f"anthropic-guard: request failed: {scrub(type(e).__name__)}: {scrub(e)}", file=sys.stderr, flush=True)
        self.close_connection = True


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main(argv=None) -> int:
    removed = scrub_environment()             # before anything can read them
    cfg = parse_args(argv)
    guard = Guard(cfg)
    srv = Server(("127.0.0.1", cfg.port), Handler)
    srv.guard = guard  # type: ignore[attr-defined]

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    r = guard.rates
    print(f"anthropic-guard {VERSION} ({cfg.status}) arm={cfg.arm} run={cfg.run_id} on 127.0.0.1:{cfg.port} -> "
          f"{urlsplit(cfg.upstream).hostname} model={cfg.model}", flush=True)
    print(f"  caps: run ${cfg.run_cap:.2f}, total ${cfg.total_cap:.2f}, agent "
          f"{'$%.2f' % cfg.agent_cap if cfg.agent_cap is not None else 'off'}, research "
          f"{'$%.2f' % guard.ledger.research_cap if guard.ledger.research_cap is not None else 'off'} (report reserve "
          f"{cfg.report_reserve * 100:.0f} %); ledger {cfg.ledger}; log {guard.log_path}", flush=True)
    print(f"  rates $/MTok: input {r.input}, output {r.output}, cache write 5m {r.cache_write_5m} / 1h "
          f"{r.cache_write_1h}, cache read {r.cache_read} (checked: {r.checked or '?'})", flush=True)
    print(f"  caching: reused prefixes only (agent loops, continued conversations, repeated system prompts; none on "
          f"one-shot calls), ttl {cfg.cache_ttl}, lead 1h {'ON' if cfg.lead_cache_1h else 'off'} (gaps: "
          f"{guard.gap_path.name}); thinking: adaptive, replay "
          f"{cfg.replay}; efforts: default {cfg.default_effort or 'api-default'}, class {cfg.class_efforts or '-'}, "
          f"map {cfg.effort_map or '-'}; max_tokens default {cfg.default_max_tokens}, cap {cfg.max_tokens_cap}",
          flush=True)
    print(f"  {key_file_note(cfg.key_file)}; ANTHROPIC_* removed from the environment: {', '.join(removed) or 'none'}",
          flush=True)
    if cfg.run_cap > cfg.total_cap:
        print("  WARNING: the run cap is above the total cap", flush=True)
    try:
        snap = guard.ledger.snapshot()
        print(f"  ledger: run spent ${snap['run']['spent_usd']:.4f}, all runs ${snap['total_spent_usd']:.4f}",
              flush=True)
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
