"""One place for the deep module's own model calls (compaction, report, verification): an explicit reasoning effort
per call type, and a fallback when a call spends its whole max_tokens thinking and returns no answer (seen at xhigh:
a 4.5K-token compaction prompt thought for 30,000 tokens / 249 s and answered nothing)."""

from __future__ import annotations

import threading
import time
from typing import Any

from loguru import logger

LOWER = {"xhigh": "medium", "high": "medium", "medium": "low", "low": None, "": "medium"}

# 10-27 (Karl): every effort drop of the retry ladder is logged and counted, so a quiet drop is visible in every
# measurement (report.py puts the count of the research's drops into stats.json -> ldr-client's summary.json)
_drops: list[dict] = []
_drops_lock = threading.Lock()


def _dropped(what: str, frm: str | None, to: str, why: str) -> None:
    try:
        from . import current_agent
        agent = current_agent.get()
    except Exception:  # noqa: BLE001
        agent = "?"
    rec = {"t": time.time(), "what": what, "from": frm or "default", "to": to, "why": why[:160], "agent": agent}
    with _drops_lock:
        _drops.append(rec)
    logger.warning(f"deep: EFFORT LOWERED for {what}: {rec['from']} -> {to} ({rec['why']})")


def effort_drops(since: float = 0.0) -> list[dict]:
    """The effort drops recorded in this process since `since` (time.time())."""
    with _drops_lock:
        return [dict(d) for d in _drops if d["t"] >= since]


def _text(resp: Any) -> str:
    c = getattr(resp, "content", resp)
    if isinstance(c, list):
        c = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c or "").strip()


def invoke(model: Any, prompt: str, effort: str = "", what: str = "call", max_tokens: int | None = None
           ) -> tuple[str, dict]:
    """Call the model; returns (text, info). On an empty answer that hit the length limit, retry one effort lower.
    max_tokens overrides LDR's llm.max_tokens for this call (the proxy still clamps it to the context)."""
    info = {"efforts": [], "finish": None}
    eff = effort
    for _ in range(3):
        kw = {"reasoning_effort": eff} if eff else {}
        if max_tokens:
            kw["max_tokens"] = max_tokens
        info["efforts"].append(eff or "default")
        try:
            resp = model.invoke(prompt, **kw)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"deep: {what} failed at effort {eff or 'default'}: {exc}")
            info["error"] = str(exc)[:300]
            old = eff
            eff = LOWER.get(eff or "", None) if eff is not None else None
            if eff is None:
                break
            _dropped(what, old, eff, f"error: {exc}")
            info["dropped"] = info.get("dropped", 0) + 1
            continue
        text = _text(resp)
        finish = (getattr(resp, "response_metadata", None) or {}).get("finish_reason")
        info["finish"] = finish
        if text:
            return text, info
        nxt = LOWER.get(eff or "", None)
        logger.warning(f"deep: {what} returned no answer at effort {eff or 'default'} (finish {finish}); "
                       f"{'retrying at ' + nxt if nxt else 'giving up'}")
        if not nxt:
            break
        _dropped(what, eff, nxt, f"no answer (finish {finish})")
        info["dropped"] = info.get("dropped", 0) + 1
        eff = nxt
    return "", info
