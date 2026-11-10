"""search_fallback.py - the search fallback chain after SearXNG: Exa first, then Tavily (2026-10-19, the user's order).

Each provider is dormant until its key file exists and keeps its own monthly counter (exa_fallback.py,
tavily_fallback.py). Tavily is asked only when Exa is off, over its cap, failed or found nothing. Standard library
only; used by LDR (patch 0005, with LDR_SEARCH_FALLBACK=1 only) and the Strata chat page (serve/websearch.py).
"""
from __future__ import annotations

import exa_fallback
import tavily_fallback

PROVIDERS = (("exa", exa_fallback), ("tavily", tavily_fallback))


def available() -> bool:
    return any(m.available() for _, m in PROVIDERS)


def search(query: str, max_results: int = 10, client: str = "?", reason: str = "") -> list[dict]:
    """Results from the first provider that has any, each with "engine" = "exa" or "tavily"; [] if none. Never raises."""
    why = reason
    for name, mod in PROVIDERS:
        try:
            if not mod.available():
                continue
            got = mod.search(query, max_results=max_results, client=client, reason=why)
        except Exception:  # noqa: BLE001 - the next provider, or SearXNG's results stand
            got = None
        if got:
            return [dict(x, engine=name) for x in got]
        why = f"{reason}; {name}: {'none' if got == [] else 'unavailable'}"
    return []
