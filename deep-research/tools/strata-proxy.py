#!/usr/bin/env python3
"""strata-proxy — a pass-through between Local Deep Research and Strata that logs every LLM call and can lower the
reasoning effort of LDR's small steps.

  127.0.0.1:$PROXY_PORT (8090)  ->  $UPSTREAM (http://127.0.0.1:8080)

Why: LDR 1.10.7 cannot send `reasoning_effort` (its ChatOpenAI gets model/key/url/temperature/max_tokens/streaming/
retries/timeout only), so every call it makes gets Strata's shared default (high -> xhigh). This proxy recognises
LDR's page-extraction calls (fetch_content's summary step, prompt starting with EXTRACT_MARK, no tools) and, when
the mode file says so, adds `reasoning_effort` (or turns thinking off) for those calls only. Everything else is
forwarded byte for byte. Nothing is changed in LDR or in Strata's shared settings.

Mode file ($PROXY_MODE_FILE, re-read on every request; missing = pure pass-through):
  {"extract_effort": "low"}      low | medium | xhigh | "off" (enable_thinking false) | null (pass through)

Log: one JSON line per call in $PROXY_LOG — class (agent / extract / other), a conversation id (hash of the first
two messages), message count, tools, prompt chars, effort sent, timings, finish reason, streamed content/reasoning
chars, tool calls, and Strata's usage (prompt, completion, cached = reused prompt tokens).

Context guard: Strata rejects a request whose prompt + max_tokens exceeds its context (HTTP 400 "prompt (N tokens) +
max tokens (M) exceeds the context (C)") instead of truncating. When that happens the proxy retries the request once
with max_tokens = C - 8 - N - GUARD_MARGIN (Strata's own slack is 8), if that still leaves >= GUARD_MIN_ANSWER tokens;
the log line records `ctx_clamp`. A prompt that is itself too large still gets the 400 (the deep-research patches
compact the agent's history well before that).

Chat cache (2026-10-19): run/chat-cache-policy.json (re-read on every request; off unless "enabled": true) marks
research calls for Strata's chat cache - see apply_chat_cache_policy. The log line records `chat_cache`.

Classes: agent (has tools) / extract (page extraction) / compact (history compaction) / report (report writing) /
verify (claim checking) / other. The mode file can set "<class>_effort" for any of them.

A client that goes away (LDR cancel or timeout) closes the upstream connection too, so Strata's disconnect
watcher stops the request (streamed requests only; Strata cannot notice a non-streamed client leaving).

Research gate (2026-10-17; the research runner and the Jan MCP server use it). Before a chat completion is forwarded
the proxy checks, in this order, and holds the call (between model calls; a call already running is never cut):
  * the control file ($PROXY_CONTROL_FILE, run/research-control.json) says pause ("pause": true, with a reason: you
    paused it, or the night pause 23:00-09:00), or "abort": true (held calls then fail at once: research cancelled)
  * a test holds strata-compare's measurement lock (tmp/gpu-test.lock, or the test queue's tmp/suite/heavy.lock)
  * yield: another client (Jan, the chat page, OpenCode, ...) used Strata in the last "yield_minutes" minutes
    (control file; 0 = never yield). Seen from Strata's /metrics: requests running, queued or finished that the
    proxy did not send.
  * Strata is not answering: it is started on demand (strata-compare's configs/usability/bin/strata-ensure.sh).
While a streamed call is held the client gets its HTTP headers at once and an SSE comment every 10 s, so its read
timeout never fires. The time the gate is closed is the research clock's pause: run/research-clock.json
("paused_total_s", kept across proxy restarts) - the deep-research patches subtract it from every deadline.
GET /_research/status shows the gate; GET /_research/wait-idle?timeout=S returns once no research call is running
upstream while the gate is closed (for test scripts: take the lock, then wait for this).

Capture (measurements): with "capture_dir" in the mode file every chat completion's messages and answer (content,
tool calls) are appended to <capture_dir>/calls.jsonl.

Tool-call text in prose: an answer whose content contains "<tool_call" / "</tool_call", a "tool_calls" finish
without a parsed call (or on a request without tools), or a call whose arguments are not valid JSON is logged with
"tooltag": {...} (Strata cuts an answer where the model writes the tag in prose - the research counts these).
Standard library only; 127.0.0.1 only.
"""
import fcntl
import hashlib
import http.client
import itertools
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
from urllib.parse import parse_qs, urlsplit

PORT = int(os.environ.get("PROXY_PORT", "8090"))
UPSTREAM = urlsplit(os.environ.get("UPSTREAM", "http://127.0.0.1:8080"))
MODE_FILE = os.environ.get("PROXY_MODE_FILE", "")
LOG = os.environ.get("PROXY_LOG", "")
CONTROL_FILE = os.environ.get("PROXY_CONTROL_FILE", "")     # written by the research runner / MCP server
CLOCK_FILE = os.environ.get("PROXY_CLOCK_FILE", "")         # written here: the research clock's pause total
# 2026-10-19 (the user's memory proposal A): how research calls use Strata's chat cache; re-read on every request,
# off unless "enabled" is true (switched on between phase 3 and phase 4, see results/bench2/PLAN.md)
CHAT_CACHE_POLICY_FILE = os.environ.get("PROXY_CHAT_CACHE_POLICY",
                                        "/home/USER/ai/deep-research/run/chat-cache-policy.json")
SC = "/home/USER/ai-speed-testing/strata-compare"
TEST_LOCKS = ((SC + "/tmp/gpu-test.lock", fcntl.LOCK_EX), (SC + "/tmp/suite/heavy.lock", fcntl.LOCK_SH))
if os.environ.get("PROXY_TEST_LOCKS"):            # tests: "path:ex,path:sh"
    TEST_LOCKS = tuple((x.rsplit(":", 1)[0], fcntl.LOCK_EX if x.endswith(":ex") else fcntl.LOCK_SH)
                       for x in os.environ["PROXY_TEST_LOCKS"].split(","))
ENSURE = os.environ.get("PROXY_ENSURE", SC + "/configs/usability/bin/strata-ensure.sh")
TOOLTAG_RE = re.compile(r"</?tool_call")
GRACE_S = float(os.environ.get("PROXY_GRACE_S", "90"))   # after a Strata start: its own warm-up/test requests
EXTRACT_MARK = "You are a content-extraction step inside a multi-step research agent."
# First words of the deep-research patches' own prompts (local_deep_research/deep/prompts.py)
CLASS_MARKS = (("compact", "You are the history-compaction step of a research agent."),
               ("report", "You are the report-writing step of a research system."),
               ("verify", "You are the claim-verification step of a research system."))
GUARD_MARGIN = int(os.environ.get("PROXY_GUARD_MARGIN", "64"))
GUARD_MIN_ANSWER = int(os.environ.get("PROXY_GUARD_MIN_ANSWER", "1024"))
CTX_ERR = re.compile(rb"prompt \((\d+) tokens\) \+ max tokens \((\d+)\) exceeds the context \((\d+)\)")
EFFORTS = ("low", "medium", "high", "xhigh")
HOP = {"connection", "keep-alive", "proxy-connection", "transfer-encoding", "upgrade", "te", "trailer",
       "proxy-authenticate", "proxy-authorization", "content-length", "host"}

_ids = itertools.count(1)
_log_lock = threading.Lock()


def mode() -> dict:
    if not MODE_FILE:
        return {}
    try:
        with open(MODE_FILE, encoding="utf-8") as f:
            m = json.load(f)
        return m if isinstance(m, dict) else {}
    except (OSError, ValueError):
        return {}


def chat_cache_policy() -> dict:
    try:
        with open(CHAT_CACHE_POLICY_FILE, encoding="utf-8") as f:
            p = json.load(f)
        return p if isinstance(p, dict) and p.get("enabled") is True else {}
    except (OSError, ValueError):
        return {}


def apply_chat_cache_policy(req: dict, cls: str) -> str | None:
    """Marks a research call for Strata's chat cache (memory proposal A); returns what was done, or None (policy off).
    * every call: "strata_owner" = the policy's owner tag ("research"), so Strata can tell research from the user's
      chats (Jan, OpenCode, dsh), which carry no tag and keep being parked;
    * the classes in "no_park_classes": "strata_checkpoint": false - the call keeps no conversation checkpoint, so
      there is nothing to park when the next call takes the session (upstream #830; outputs unchanged);
    * the classes in "drop_classes" (the report stage: report, verify): "strata_chat_drop" = the owner tag - Strata
      drops every parked conversation with that tag before the call (needs the engine change planned for the port;
      an engine without it ignores the field)."""
    pol = chat_cache_policy()
    if not pol:
        return None
    tag = str(pol.get("owner") or "research")
    req["strata_owner"] = tag
    done = ["owner"]
    if cls in (pol.get("no_park_classes") or ()):
        req["strata_checkpoint"] = False
        done.append("no-park")
    if cls in (pol.get("drop_classes") or ()):
        req["strata_chat_drop"] = tag
        done.append("drop")
    return "+".join(done)


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def classify(req: dict) -> str:
    msgs = req.get("messages") or []
    if req.get("tools"):
        return "agent"
    first_user = next((text_of(m.get("content")) for m in msgs if m.get("role") == "user"), "")
    if first_user.startswith(EXTRACT_MARK):
        return "extract"
    first_text = next((text_of(m.get("content")) for m in msgs if m.get("role") in ("system", "user")), "")
    for cls, mark in CLASS_MARKS:
        if first_text.startswith(mark) or first_user.startswith(mark):
            return cls
    return "other"


def conv_id(req: dict) -> str:
    msgs = req.get("messages") or []
    head = json.dumps([[m.get("role"), text_of(m.get("content"))[:4000]] for m in msgs[:2]], ensure_ascii=False)
    return hashlib.sha1(head.encode()).hexdigest()[:10]


def write_log(rec: dict) -> None:
    if not LOG:
        return
    line = json.dumps(rec, ensure_ascii=False)
    with _log_lock, open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


class SSEStats:
    """Counts what a streamed chat completion carried, from the SSE lines as they pass (and keeps the answer text and
    tool-call arguments for the tool-tag check)."""

    def __init__(self):
        self.buf = b""
        self.content = self.reasoning = 0
        self.text: list[str] = []
        self.args: dict[int, str] = {}
        self.names: dict[int, str] = {}
        self.tool_calls = set()
        self.finish = None
        self.usage = None
        self.error = None
        self.first_token_at = None

    def feed(self, data: bytes) -> None:
        self.buf += data
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                continue
            try:
                c = json.loads(payload)
            except ValueError:
                continue
            if "error" in c:
                self.error = str(c["error"])[:300]
            if c.get("usage"):
                self.usage = c["usage"]
            for ch in c.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("content") or d.get("reasoning_content") or d.get("tool_calls"):
                    if self.first_token_at is None:
                        self.first_token_at = time.time()
                if d.get("content"):
                    self.content += len(d["content"])
                    if self.content < 2_000_000:
                        self.text.append(d["content"])
                self.reasoning += len(d.get("reasoning_content") or d.get("reasoning") or "")
                for tc in d.get("tool_calls") or []:
                    k = tc.get("index", 0)
                    self.tool_calls.add(k)
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        self.names[k] = fn["name"]
                    a = fn.get("arguments")
                    if a:
                        self.args[k] = self.args.get(k, "") + a
                if ch.get("finish_reason"):
                    self.finish = ch["finish_reason"]


def tooltag_check(req: dict, content: str, args: dict, finish, n_calls: int, error) -> dict | None:
    """An answer cut off (or broken) by tool-call text in prose, as far as the response shows it."""
    m = TOOLTAG_RE.search(content or "")
    if m:
        return {"kind": "tag_in_content", "at": m.start(), "of": len(content),
                "around": content[max(0, m.start() - 100):m.start() + 60]}
    if finish == "tool_calls" and not n_calls:
        return {"kind": "tool_calls_finish_without_call"}
    if n_calls and not req.get("tools"):
        return {"kind": "call_without_tools"}
    for k, a in (args or {}).items():
        try:
            json.loads(a or "{}")
        except ValueError:
            return {"kind": "bad_arguments", "index": k, "args": (a or "")[:200]}
    if error and re.search(r"tool", str(error), re.I):
        return {"kind": "error", "error": str(error)[:200]}
    return None


class Gate:
    """Holds research calls between model calls (see the module docstring) and keeps the research clock."""
    POLL_S = 5.0
    DOWN = "Strata is not answering"

    def __init__(self):
        self.cond = threading.Condition()
        self.reason: str | None = None
        self.since: float | None = None
        self.paused_total = self._load_total()
        self.inflight = 0               # research calls forwarded upstream right now
        self.held = 0                   # calls waiting at the gate
        self.done_ok = 0                # calls Strata finished (HTTP 200)
        self.last_foreign = 0.0
        self.base = None                # (Strata's finished-request count, done_ok) at the last rebase
        self.suspect_busy = False
        self.suspect_excess = False
        self.strata_up = True
        self.ensuring = False
        self.ensure_failed_at = 0.0
        self.ensure_msg = ""
        self.yield_minutes = 0.0
        self.tooltags = 0
        self.grace_until = time.time() + GRACE_S
        self.lock_seen: str | None = None
        # after Strata (re)starts, its start-up script sends a warm-up and test requests (phase_end.sh) for a while
        # after the model is loaded: none of them is another client (grace_until is set above: a fresh proxy too)
        threading.Thread(target=self._loop, daemon=True).start()

    # -- inputs -------------------------------------------------------------------------------------------------------
    @staticmethod
    def _load_total() -> float:
        try:
            with open(CLOCK_FILE, encoding="utf-8") as f:
                return float(json.load(f).get("paused_total_s") or 0.0)
        except (OSError, ValueError, TypeError):
            return 0.0

    @staticmethod
    def control() -> dict:
        if not CONTROL_FILE:
            return {}
        try:
            with open(CONTROL_FILE, encoding="utf-8") as f:
                c = json.load(f)
            return c if isinstance(c, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def test_lock() -> str | None:
        for path, how in TEST_LOCKS:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "a") as f:
                    try:
                        fcntl.flock(f, how | fcntl.LOCK_NB)
                        fcntl.flock(f, fcntl.LOCK_UN)
                    except BlockingIOError:
                        return os.path.basename(path)
            except OSError:
                pass
        return None

    def _poll_strata(self) -> None:
        try:
            c = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port or 80, timeout=5)
            c.request("GET", "/metrics")
            r = c.getresponse()
            m = json.loads(r.read())
            c.close()
        except (OSError, ValueError, http.client.HTTPException):
            self.strata_up = False
            return
        if not self.strata_up:                                  # it was down: a start (ours or a launcher's)
            self.grace_until = time.time() + GRACE_S
        self.strata_up = True
        live = m.get("live") or {}
        total = int((m.get("totals") or {}).get("requests") or 0)
        busy = (0 if live.get("state") in (None, "idle") else 1) + int(live.get("queued") or 0)
        with self.cond:
            inflight, done = self.inflight, self.done_ok
        now = time.time()
        if self.base is None or total < self.base[0] or now < self.grace_until:
            # first poll, Strata restarted, or inside the start-up grace window: re-base, nothing is foreign
            if self.base is not None and total < self.base[0]:
                self.grace_until = now + GRACE_S
            self.base, self.suspect_excess, self.suspect_busy = (total, done), False, False
            return
        # requests Strata finished that the proxy did not send (a call of ours may already be counted: in flight)
        excess = (total - self.base[0]) - (done - self.base[1]) - inflight
        # minus tiny probes (< 64 prompt tokens: the start-up checks of phase_end.sh / switch-model.sh, which can queue
        # behind a long research call and end after the grace window); a chat from Jan or the chat page is far larger
        since = getattr(self, "last_poll_t", now - self.POLL_S)
        probes = sum(1 for r in (m.get("requests") or [])
                     if (r.get("prompt_tokens") or 0) < 64 and float(r.get("time") or 0) + float(r.get("duration_s") or 0) >= since - 1)
        self.last_poll_t = now
        if probes and excess > 0:
            self.base = (self.base[0] + min(probes, excess), self.base[1])
            excess -= min(probes, excess)
        if excess > 0:
            if self.suspect_excess:                            # seen twice in a row: not a timing artefact
                self.last_foreign = now
                self.base = (self.base[0] + excess, self.base[1])
                self.suspect_excess = False
            else:
                self.suspect_excess = True
        else:
            self.suspect_excess = False
        # someone else's request running or queued right now
        if busy > inflight:
            if self.suspect_busy:
                self.last_foreign = now
            self.suspect_busy = True
        else:
            self.suspect_busy = False

    # -- state ----------------------------------------------------------------------------------------------------------
    def _evaluate(self) -> None:
        now = time.time()
        c = self.control()
        try:
            self.yield_minutes = float(c.get("yield_minutes") or 0)
        except (TypeError, ValueError):
            self.yield_minutes = 0.0
        lock = self.test_lock()
        self.lock_seen = lock
        rb = c.get("rebase_at")
        if rb and rb != getattr(self, "_rebase_seen", None):
            # the runner restarted Strata: its start-up test request is not another client
            self._rebase_seen = rb
            self.base, self.suspect_excess, self.suspect_busy = None, False, False
            self.grace_until = time.time() + GRACE_S
        if c.get("abort"):
            reason = "abort"
        elif c.get("pause"):
            reason = "paused: " + str(c.get("reason") or "paused")
        elif lock:
            reason = f"a test holds the GPUs ({lock})"
        elif self.yield_minutes > 0 and now - self.last_foreign < self.yield_minutes * 60:
            reason = (f"yielding to another client (it used Strata {(now - self.last_foreign) / 60:.0f} min ago; "
                      f"yield {self.yield_minutes:g} min)")
        elif not self.strata_up:
            reason = self.DOWN
        else:
            reason = None
        with self.cond:
            if reason != self.reason:
                if self.reason is not None and self.since is not None:
                    self.paused_total += now - self.since
                self.since = now if reason is not None else None
                self.reason = reason
                self.cond.notify_all()
        self._write_clock(now)

    def snapshot(self, now: float | None = None) -> dict:
        now = now or time.time()
        with self.cond:
            total = self.paused_total + (now - self.since if self.since is not None else 0.0)
            return {"paused_total_s": round(total, 2), "gate": "closed" if self.reason else "open",
                    "reason": self.reason, "since": self.since, "updated": round(now, 3), "inflight": self.inflight,
                    "held": self.held, "last_foreign": self.last_foreign or None, "yield_minutes": self.yield_minutes,
                    "strata_up": self.strata_up, "ensuring": self.ensuring, "ensure_msg": self.ensure_msg,
                    "tooltags": self.tooltags}

    def _write_clock(self, now: float) -> None:
        if not CLOCK_FILE:
            return
        tmp = CLOCK_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.snapshot(now), f)
            os.replace(tmp, CLOCK_FILE)
        except OSError:
            pass

    def _loop(self) -> None:
        last_poll = 0.0
        while True:
            try:
                if time.time() - last_poll >= self.POLL_S:
                    last_poll = time.time()
                    self._poll_strata()
                self._evaluate()
            except Exception as e:  # noqa: BLE001 - the gate must keep running
                print(f"gate loop: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            time.sleep(1.0)

    def _ensure_async(self) -> None:
        with self.cond:
            if self.ensuring or time.time() - self.ensure_failed_at < 60:
                return
            self.ensuring = True

        def run():
            ok = False
            try:
                env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
                r = subprocess.run([ENSURE, "Deep research"], env=env, capture_output=True, text=True, timeout=420)
                ok = r.returncode == 0
                self.ensure_msg = (r.stderr or r.stdout or "").strip()[-300:]
            except (OSError, subprocess.SubprocessError) as e:
                self.ensure_msg = f"{type(e).__name__}: {e}"[:300]
            with self.cond:
                self.ensuring = False
                if not ok:
                    self.ensure_failed_at = time.time()
                self.base = None                  # the start's own test request is not another client
                self.grace_until = time.time() + GRACE_S
            self._poll_strata()
            self._evaluate()

        threading.Thread(target=run, daemon=True).start()

    def wait(self, tick) -> str | None:
        """Block while the gate is closed. tick(reason) is called at once and every 10 s (keep-alives); it returns
        False when the client is gone. Returns None (go on), "abort" or "gone"."""
        with self.cond:
            if self.reason is None:
                return None
            self.held += 1
        try:
            last_tick = 0.0
            while True:
                with self.cond:
                    r = self.reason
                    if r is None:
                        return None
                    if r == "abort":
                        return "abort"
                if r == self.DOWN:
                    self._ensure_async()
                if time.time() - last_tick >= 10:
                    last_tick = time.time()
                    if not tick(r):
                        return "gone"
                with self.cond:
                    self.cond.wait(timeout=2)
        finally:
            with self.cond:
                self.held -= 1

    def mark_down(self) -> None:
        self.strata_up = False
        self._evaluate()


GATE: Gate | None = None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet; the JSONL log is the record
        pass

    def do_GET(self):
        if self.path.startswith("/_research/"):
            return self._research_api()
        self._forward(None)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._forward(self.rfile.read(n) if n else b"")

    def _json(self, code: int, obj: dict) -> None:
        msg = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(msg)))
        self.end_headers()
        self.wfile.write(msg)
        self.close_connection = True

    def _research_api(self) -> None:
        u = urlsplit(self.path)
        if u.path == "/_research/status":
            return self._json(200, GATE.snapshot())
        if u.path == "/_research/wait-idle":
            q = parse_qs(u.query)
            timeout = float((q.get("timeout") or ["900"])[0])
            t0 = time.time()
            while time.time() - t0 < timeout:
                snap = GATE.snapshot()
                if snap["gate"] == "closed" and snap["inflight"] == 0:
                    snap.update(idle=True, waited_s=round(time.time() - t0, 1))
                    return self._json(200, snap)
                time.sleep(1.0)
            snap = GATE.snapshot()
            snap.update(idle=False, waited_s=round(time.time() - t0, 1))
            return self._json(200, snap)
        return self._json(404, {"error": "unknown"})

    # -- held streamed calls: headers at once, then SSE comments -----------------------------------------------------
    def _start_held_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        self.wfile.flush()

    def _chunk(self, data: bytes) -> None:
        self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
        self.wfile.flush()

    def _forward(self, body):
        rec = {"id": next(_ids), "t0": round(time.time(), 3), "method": self.command, "path": self.path}
        req = None
        if body and self.path.rstrip("/").endswith("/chat/completions"):
            try:
                req = json.loads(body)
            except ValueError:
                req = None
        if isinstance(req, dict):
            cls = classify(req)
            msgs = req.get("messages") or []
            first = msgs[0] if msgs else {}
            rec.update(cls=cls, conv=conv_id(req), n_msgs=len(msgs),
                       head=f"{first.get('role')}: {text_of(first.get('content'))[:90]}",
                       tools=[(t.get("function") or {}).get("name") for t in req.get("tools") or []],
                       prompt_chars=sum(len(text_of(m.get("content"))) for m in msgs),
                       stream=bool(req.get("stream")), max_tokens=req.get("max_completion_tokens") or req.get("max_tokens"),
                       client_effort=req.get("reasoning_effort"))
            cc = apply_chat_cache_policy(req, cls)
            if cc:
                rec["chat_cache"] = cc
                body = json.dumps(req).encode()
            want = mode().get(f"{cls}_effort")
            if want and not req.get("reasoning_effort"):
                if want == "off":
                    ctk = dict(req.get("chat_template_kwargs") or {})
                    ctk["enable_thinking"] = False
                    req["chat_template_kwargs"] = ctk
                    rec["effort"] = "off"
                elif want in EFFORTS:
                    req["reasoning_effort"] = want
                    rec["effort"] = want
                body = json.dumps(req).encode()
        streamed = bool((req or {}).get("stream"))
        held_open = False                      # headers already sent while the call was held
        client_gone = False

        def tick(reason: str) -> bool:
            nonlocal held_open
            rec["held_reason"] = reason
            if not streamed:
                return True
            try:
                if not held_open:
                    self._start_held_stream()
                    held_open = True
                self._chunk(f": held - {reason}\n\n".encode())
                return True
            except OSError:
                return False

        if isinstance(req, dict):
            for attempt in range(2):
                t_hold = time.time()
                verdict = GATE.wait(tick)
                if time.time() - t_hold > 0.5:
                    rec["held_s"] = round(rec.get("held_s", 0) + time.time() - t_hold, 1)
                if verdict is None:
                    break
                if verdict == "gone":
                    client_gone = True
                    rec.update(status=None, t_end=round(time.time(), 3), client_gone=True, error="client left while held")
                    write_log(rec)
                    self.close_connection = True
                    return
                # abort: the research is being cancelled
                msg = {"error": {"type": "research_cancelled", "message": "research cancelled (held call released)"}}
                try:
                    if held_open:
                        self._chunk(b"data: " + json.dumps(msg).encode() + b"\n\n")
                        self._chunk(b"data: [DONE]\n\n")
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
                    else:
                        self._json(503, msg)
                except OSError:
                    pass
                rec.update(status=503, t_end=round(time.time(), 3), error="aborted while held")
                write_log(rec)
                self.close_connection = True
                return

        stats = SSEStats() if streamed else None
        status, raw = None, b""
        pending = b""                          # a 400 body already read while checking for the context error
        counted = False
        conn = None
        try:
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            if body is not None:
                headers["Content-Length"] = str(len(body))
            if req is not None:
                with GATE.cond:
                    GATE.inflight += 1
                counted = True
            resp = None
            for attempt in range(2):
                conn = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port or 80, timeout=None)
                try:
                    conn.request(self.command, self.path, body=body, headers=headers)
                    resp = conn.getresponse()
                    break
                except ConnectionRefusedError:
                    conn.close()
                    if req is None or attempt == 1:
                        raise
                    # Strata went away between the gate check and now: start it and wait at the gate once more
                    GATE.mark_down()
                    with GATE.cond:
                        GATE.inflight -= 1
                    verdict = GATE.wait(tick)
                    with GATE.cond:
                        GATE.inflight += 1
                    if verdict is not None:
                        raise
            if resp.status == 400 and isinstance(req, dict):
                pending = resp.read()
                m = CTX_ERR.search(pending)
                if m:
                    n_prompt, asked, ctx = (int(x) for x in m.groups())
                    fit = ctx - 8 - n_prompt - GUARD_MARGIN
                    rec["ctx_clamp"] = {"prompt": n_prompt, "asked": asked, "context": ctx,
                                        "to": fit if fit >= GUARD_MIN_ANSWER else None}
                    if fit >= GUARD_MIN_ANSWER:
                        for k in ("max_tokens", "max_completion_tokens"):
                            if k in req:
                                req[k] = fit
                        if "max_tokens" not in req and "max_completion_tokens" not in req:
                            req["max_tokens"] = fit
                        body = json.dumps(req).encode()
                        headers["Content-Length"] = str(len(body))
                        conn.close()
                        conn = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port or 80, timeout=None)
                        conn.request(self.command, self.path, body=body, headers=headers)
                        resp = conn.getresponse()
                        pending = b""
            status = resp.status
            rec["t_headers"] = round(time.time(), 3)
            if held_open:
                # the client already has "200 + event-stream" headers: pass the body on, an error as an SSE event
                if status != 200:
                    err = pending or resp.read()
                    raw = err
                    try:
                        e = json.loads(err)
                        e = e if isinstance(e, dict) and "error" in e else {"error": {"message": err.decode(errors="replace")[:500]}}
                    except ValueError:
                        e = {"error": {"message": err.decode(errors="replace")[:500]}}
                    e["error"].setdefault("code", status)
                    self._chunk(b"data: " + json.dumps(e).encode() + b"\n\n")
                    self._chunk(b"data: [DONE]\n\n")
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                    pending = b"x"             # nothing more to stream
                chunked = True
            else:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in HOP:
                        self.send_header(k, v)
                chunked = resp.getheader("Content-Length") is None and not pending
                if chunked:
                    self.send_header("Transfer-Encoding", "chunked")
                else:
                    self.send_header("Content-Length", str(len(pending)) if pending else resp.getheader("Content-Length"))
                self.end_headers()
                if pending:                        # the 400 we read above: forward it as it was
                    raw = pending
                    self.wfile.write(pending)
                self.wfile.flush()
            while not pending:
                data = resp.read1(65536)
                if not data:
                    break
                if stats is not None:
                    stats.feed(data)
                elif req is not None and len(raw) < 4_000_000:
                    raw += data
                try:
                    if chunked:
                        self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                    else:
                        self.wfile.write(data)
                    self.wfile.flush()
                except OSError:
                    client_gone = True
                    break
            if chunked and not client_gone and not (held_open and pending):
                try:
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except OSError:
                    client_gone = True
        except (OSError, http.client.HTTPException) as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            if status is None:
                try:
                    msg = {"error": {"type": "proxy_error", "message": rec["error"]}}
                    if held_open:
                        self._chunk(b"data: " + json.dumps(msg).encode() + b"\n\n")
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
                    else:
                        self._json(502, msg)
                except OSError:
                    client_gone = True
        finally:
            if conn is not None:
                conn.close()                  # a vanished client closes the upstream too: Strata stops the request
            if counted:
                with GATE.cond:
                    GATE.inflight -= 1
                    if status == 200:
                        GATE.done_ok += 1
        if req is None:
            return
        rec.update(status=status, t_end=round(time.time(), 3), client_gone=client_gone)
        rec["duration_s"] = round(rec["t_end"] - rec["t0"], 2)
        text, args, n_calls, finish, error = "", {}, 0, None, None
        if stats is not None:
            rec.update(finish=stats.finish, content_chars=stats.content, reasoning_chars=stats.reasoning,
                       n_tool_calls=len(stats.tool_calls), usage=stats.usage, stream_error=stats.error,
                       t_first_token=round(stats.first_token_at, 3) if stats.first_token_at else None)
            text, args, n_calls, finish, error = "".join(stats.text), stats.args, len(stats.tool_calls), stats.finish, stats.error
        else:
            try:
                d = json.loads(raw)
                ch = (d.get("choices") or [{}])[0]
                m = ch.get("message") or {}
                rec.update(finish=ch.get("finish_reason"), content_chars=len(m.get("content") or ""),
                           reasoning_chars=len(m.get("reasoning_content") or ""),
                           n_tool_calls=len(m.get("tool_calls") or []), usage=d.get("usage"),
                           stream_error=str(d.get("error"))[:300] if d.get("error") else None)
                text, finish, error = m.get("content") or "", ch.get("finish_reason"), d.get("error")
                n_calls = len(m.get("tool_calls") or [])
                args = {i: (tc.get("function") or {}).get("arguments") or "" for i, tc in enumerate(m.get("tool_calls") or [])}
            except ValueError:
                pass
        if status == 200 or error:
            tt = tooltag_check(req, text, args, finish, n_calls, error)
            if tt:
                rec["tooltag"] = tt
                with GATE.cond:
                    GATE.tooltags += 1
        write_log(rec)
        cap = mode().get("capture_dir")
        if cap:
            # measurement runs (results/bench2): every call's input and output, so failures can be sorted the same way
            # for the baseline and the deep profile (where an answer was found, read, kept or lost)
            try:
                names = stats.names if stats is not None else {}
                capture(cap, {"id": rec["id"], "t0": rec["t0"], "cls": rec.get("cls"), "status": status,
                              "messages": req.get("messages"), "tools": rec.get("tools"),
                              "reasoning_effort": req.get("reasoning_effort"), "content": text,
                              "tool_calls": [{"name": names.get(k), "arguments": a} for k, a in sorted(args.items())],
                              "finish": finish})
            except Exception as e:  # noqa: BLE001
                print(f"capture failed: {e}", file=sys.stderr, flush=True)
        self.close_connection = True


_cap_lock = threading.Lock()


def capture(directory: str, rec: dict) -> None:
    os.makedirs(directory, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False)
    with _cap_lock, open(os.path.join(directory, "calls.jsonl"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    global GATE
    GATE = Gate()
    srv = Server(("127.0.0.1", PORT), Handler)
    print(f"strata-proxy on 127.0.0.1:{PORT} -> {UPSTREAM.geturl()} (mode file: {MODE_FILE or '-'}, log: {LOG or '-'}, "
          f"control: {CONTROL_FILE or '-'}, clock: {CLOCK_FILE or '-'})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
