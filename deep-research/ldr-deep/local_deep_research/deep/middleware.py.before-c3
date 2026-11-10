"""Agent middleware for deep runs: history compaction, the time/step budget, and a per-call context check.

One instance per agent (the lead, and each subagent). Hooks (LangChain 1.x AgentMiddleware):
  before_model     wrap-up when the budget is used up (adds an instruction message); compaction when the history's
                   token count passes ``compact_at``: older messages are replaced by running research notes written
                   by the model plus a deterministic list of the sources and searches they involved, so no source
                   index or URL is lost. The task message and the most recent steps are kept verbatim.
  wrap_model_call  counts the call; after a wrap-up the model gets no tools (it must answer); last line of defence:
                   if system + messages + tool schemas + max_tokens would still exceed the context, the largest tool
                   results in this request (not in the stored history) are shortened until it fits.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from loguru import logger

from . import config, current_agent
from .control import clock
from .evidence import EvidenceStore, cited_indices
from .prompts import COMPACT_PROMPT, WRAP_UP_LEAD, WRAP_UP_SUB
from .tokens import count_message, count_messages, count_text, count_tools, truncate_to_tokens

NOTES_KEY = "deep_notes"
WRAP_KEY = "deep_wrap_up"
MARGIN = 512                      # tokens kept free below the context on every call


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content or "")


def _render(msg: Any) -> str:
    if isinstance(msg, ToolMessage):
        return f"<tool_result name=\"{getattr(msg, 'name', '') or ''}\">\n{_text(msg.content)}\n</tool_result>"
    if isinstance(msg, AIMessage):
        parts = []
        if _text(msg.content).strip():
            parts.append(_text(msg.content).strip())
        for tc in msg.tool_calls or []:
            parts.append(f"CALL {tc.get('name')}({json.dumps(tc.get('args'), ensure_ascii=False)})")
        return "<agent>\n" + "\n".join(parts) + "\n</agent>"
    return f"<{getattr(msg, 'type', 'message')}>\n{_text(getattr(msg, 'content', msg))}\n</{getattr(msg, 'type', 'message')}>"


def _safe_cutoff(msgs: list, cutoff: int) -> int:
    """Move the cutoff back so that no ToolMessage is separated from the AIMessage that called it."""
    while 0 < cutoff < len(msgs) and isinstance(msgs[cutoff], ToolMessage):
        cutoff -= 1
    return cutoff


class DeepAgentMiddleware(AgentMiddleware):
    def __init__(self, *, role: str, label: str, model: Any, store: EvidenceStore | None, task: str,
                 deadline: float, max_calls: int, terminate_check: Callable[[], None] | None = None,
                 progress: Callable[[str], None] | None = None):
        super().__init__()
        self.cfg = config()
        self.role, self.label, self.model, self.store, self.task = role, label, model, store, task
        self.deadline, self.max_calls = deadline, max_calls
        self.terminate_check, self.progress = terminate_check, progress
        self.calls = 0
        self.wrapped: str | None = None
        self.fixed_tokens = 2000          # system prompt + tool schemas, measured on the first call
        self.compactions = 0
        self.after_last_compaction = 0     # prompt tokens right after the last compaction (thrash guard)
        self.lock = threading.Lock()

    @property
    def name(self) -> str:  # one instance per agent; the name only has to be unique within one agent
        return "DeepAgentMiddleware"

    # -- budget ------------------------------------------------------------------------------------------------------
    def _wrap_reason(self) -> str | None:
        if clock() >= self.deadline:      # the research clock: stops while the proxy gate holds calls
            return "time budget reached"
        if self.calls >= self.max_calls - 1:
            return f"step limit of {self.max_calls} reached"
        return None

    def before_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        current_agent.set(self.label)
        if self.terminate_check is not None:
            self.terminate_check()                 # raises when the research was cancelled
        msgs = list(state["messages"])
        extra: list = []
        if self.wrapped is None:
            why = self._wrap_reason()
            if why:
                self.wrapped = why
                text = (WRAP_UP_LEAD if self.role == "lead" else WRAP_UP_SUB).format(why=why)
                extra.append(HumanMessage(content=text, additional_kwargs={WRAP_KEY: True}))
                logger.info(f"deep[{self.label}]: wrap-up ({why}) after {self.calls} model calls")
                if self.store:
                    self.store.add_note("wrap_up", who=self.label, why=why, calls=self.calls)
        total = self.fixed_tokens + count_messages(msgs) + sum(count_message(m) for m in extra)
        hard = self.cfg.context_tokens - self.cfg.max_tokens - MARGIN
        grown = total - self.after_last_compaction >= 0.2 * self.cfg.compact_at
        if total > self.cfg.compact_at and len(msgs) > 3 and (grown or total > 0.9 * hard):
            new = self._compact(msgs, total)
            if new is not None:
                return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *new, *extra]}
        if extra:
            return {"messages": extra}
        return None

    # -- compaction --------------------------------------------------------------------------------------------------
    def _compact(self, msgs: list, total: int) -> list | None:
        t0 = time.time()
        head = msgs[0]
        prev_notes, body = "", []
        for m in msgs[1:]:
            if isinstance(m, HumanMessage) and m.additional_kwargs.get(NOTES_KEY):
                prev_notes = m.additional_kwargs.get("notes_text", _text(m.content))
            else:
                body.append(m)
        # keep the most recent messages verbatim: at most keep_recent of them and at most 35 % of compact_at tokens
        # (at least the last one), cut where no tool result is separated from its call
        budget, kept_tokens, start = int(0.35 * self.cfg.compact_at), 0, len(body)
        while start > 0 and len(body) - start < self.cfg.keep_recent:
            n = count_message(body[start - 1])
            if kept_tokens + n > budget and start < len(body):
                break
            kept_tokens += n
            start -= 1
        cutoff = _safe_cutoff(body, start)
        old, keep = body[:cutoff], body[cutoff:]
        if not old:
            return None
        if self.progress:
            self.progress(f"Compacting {self.label} history ({total:,} tokens)")
        # summarise in chunks that fit the context: notes = f(notes, chunk)
        room = self.cfg.context_tokens - self.cfg.max_tokens - MARGIN - 3000 - count_text(self.task)
        notes = prev_notes
        chunk: list[str] = []
        chunk_tokens = 0
        rendered = [_render(m) for m in old]
        cited_text = prev_notes
        for r in rendered:
            n = count_text(r)
            budget = room - count_text(notes)
            if n > budget:                   # a single huge message: shorten it for the summary
                r = truncate_to_tokens(r, max(1000, budget // 2))
                n = count_text(r)
            if chunk and chunk_tokens + n > room - count_text(notes):
                notes = self._summarise(notes, "\n\n".join(chunk))
                chunk, chunk_tokens = [], 0
            chunk.append(r)
            chunk_tokens += n
            cited_text += "\n" + r
        if chunk:
            notes = self._summarise(notes, "\n\n".join(chunk))
        idx = set(cited_indices(cited_text)) | set(cited_indices(notes))
        src_lines = []
        if self.store is not None:
            for i in sorted(idx):
                s = self.store.source(i)
                if s is not None:
                    src_lines.append(f"[{i}] {s.title[:90]} — {s.url}{' (read)' if s.fetches else ''}")
            mine = [s["query"] for s in self.store.searches if s.get("agent") == self.label]
        else:
            mine = []
        content = ("[Research notes: your earlier steps were compacted to save context. Everything below was "
                   "found by you; keep citing sources by the same [N].]\n\n" + notes)
        if src_lines:
            content += "\n\nSources referred to above (index, title, URL; '(read)' = page was read):\n" + "\n".join(src_lines)
        if mine:
            content += "\n\nSearches you already ran: " + "; ".join(dict.fromkeys(mine))
        notes_msg = HumanMessage(content=content, additional_kwargs={NOTES_KEY: True, "notes_text": notes})
        new = [head, notes_msg, *keep]
        after = self.fixed_tokens + count_messages(new)
        self.after_last_compaction = after
        self.compactions += 1
        logger.info(f"deep[{self.label}]: compacted {len(old)} messages, {total:,} -> {after:,} tokens "
                    f"in {time.time() - t0:.0f} s (#{self.compactions})")
        if self.store:
            self.store.add_note("compaction", who=self.label, messages=len(old), tokens_before=total,
                                tokens_after=after, seconds=round(time.time() - t0, 1), notes_tokens=count_text(notes),
                                notes_text=notes)       # kept for a seeded continuation (deep/seed.py)
        return new

    def _summarise(self, notes: str, history: str) -> str:
        from .llm import invoke

        prompt = COMPACT_PROMPT.format(task=self.task, previous_notes=notes or "(none yet)", history=history)
        text, info = invoke(self.model, prompt, self.cfg.compact_effort, what=f"compaction [{self.label}]")
        if text:
            return text
        # never lose the history: fall back to keeping it verbatim-but-shortened
        return (notes + "\n\n" if notes else "") + truncate_to_tokens(history, 12000)

    # -- per call ------------------------------------------------------------------------------------------------------
    def wrap_model_call(self, request: Any, handler: Callable[[Any], Any]) -> Any:
        with self.lock:
            self.calls += 1
        sys_tokens = count_text(_text(request.system_message.content)) if request.system_message else 0
        tools = [] if self.wrapped else request.tools
        self.fixed_tokens = sys_tokens + count_tools(tools) + 50
        if self.wrapped:
            request = request.override(tools=[])
        limit = self.cfg.context_tokens - self.cfg.max_tokens - MARGIN
        msgs = list(request.messages)
        total = self.fixed_tokens + count_messages(msgs)
        if total > limit:
            # shorten the largest tool results of this request until it fits (stored history is untouched)
            order = sorted((i for i, m in enumerate(msgs) if isinstance(m, ToolMessage)),
                           key=lambda i: -count_message(msgs[i]))
            for i in order:
                if total <= limit:
                    break
                m = msgs[i]
                n = count_message(m)
                target = max(500, n - (total - limit) - 200)
                cut = truncate_to_tokens(_text(m.content), target) + "\n[... shortened to fit the context]"
                msgs[i] = ToolMessage(content=cut, tool_call_id=m.tool_call_id, name=getattr(m, "name", None), id=m.id)
                total = self.fixed_tokens + count_messages(msgs)
            logger.warning(f"deep[{self.label}]: request shortened to {total:,} prompt tokens to fit the context")
            if self.store:
                self.store.add_note("context_guard", who=self.label, tokens=total)
            request = request.override(messages=msgs)
        return handler(request)
