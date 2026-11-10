"""Deep-research extensions for the langgraph-agent strategy (workspace patch, not part of upstream LDR).

Everything here is switched on by ``LDR_DEEP=1`` in the environment of ``ldr-web`` and configured by ``LDR_DEEP_*``
variables (set by run-ldr.sh). With ``LDR_DEEP`` unset the patched strategy behaves exactly as upstream 1.10.7.

What it adds (see NOTES.md / README.md in the workspace for the measurements behind the defaults):
  * raised depth caps: lead iterations, subagent iterations, subtopics per call, page size, extraction size
  * a time budget for the research phase: when it runs out, agents are told to wrap up and lose their tools
  * an evidence store: every search result, fetched page (full text) and extraction, every subagent report
  * context management: the lead's (and each subagent's) history is compacted before it outgrows the model's
    context, keeping every source index/URL and finding; every model call is checked against the context limit
  * a report stage: outline -> sections written from the stored evidence with [N] citations -> answer summary
  * a verification pass: each cited claim is checked against the cited page's stored text; unsupported claims are
    flagged in the report and listed in a citation-check table
"""

from __future__ import annotations

import contextvars
import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class DeepConfig:
    enabled: bool = False
    # depth caps
    max_iterations: int = 200            # lead agent model calls (upstream: 50, UI max 100)
    max_sub_iterations: int = 30         # model calls per subagent (upstream: 8)
    max_subtopics: int = 8               # preferred subtopics per research_subtopic call (upstream: 5)
    max_subtopics_hard: int = 12         # rejected above this (upstream: 10)
    subagent_budget_s: int = 3600        # a subagent is told to wrap up after this long (upstream: hard 1800 s kill)
    subagent_hard_s: int = 7200          # upstream's abandon-the-thread backstop, raised
    time_budget_s: int = 3 * 3600        # research phase (all agents); then wrap up and write the report
    fetch_max_chars: int = 120_000       # page text given to the extraction step (upstream: 10,000)
    extract_max_chars: int = 4000        # extraction output (upstream prompt: 1,500)
    extract_effort: str = ""             # reasoning effort for page extraction ("" = the server's default)
    compact_effort: str = "medium"       # history compaction (a summary; xhigh looped to max_tokens in a test)
    report_effort: str = "xhigh"         # outline, sections, opening
    verify_effort: str = "xhigh"         # citation check
    sub_return_max_chars: int = 16_000   # how much of a subagent's report the lead sees (the store keeps all of it)
    search_results: int = 50             # results per web_search (set through LDR's SearXNG max_results in run-ldr.sh)
    snippet_chars: int = 300             # snippet length the agents see per result (the store keeps the full one)
    # context management
    context_tokens: int = 131_072        # the server's context (prompt + max_tokens must fit)
    max_tokens: int = 30_000             # completion budget LDR asks for (llm.max_tokens)
    compact_at: int = 56_000             # compact history when the prompt estimate exceeds this
    keep_recent: int = 6                 # messages kept verbatim after a compaction
    # report stage
    report: bool = True
    verify: bool = True
    report_evidence_tokens: int = 48_000  # evidence per section-writing call
    verify_page_tokens: int = 40_000      # page text per verification call (per-source design)
    verify_claim_source_tokens: int = 2000  # passages per cited source per claim (joint design, the default)
    verify_max_claims: int = 120          # key claims checked per report (0 = all; a full check of ~400 claims took ~1.5 h)
    out_dir: str = ""                    # evidence + report files per research (empty = don't write files)
    tokenizer_dir: str = ""              # vocab.json + merges.txt + tokenizer.json of the served model
    extra: dict = field(default_factory=dict)


def load_config() -> DeepConfig:
    d = DeepConfig()
    return DeepConfig(
        enabled=_env_bool("LDR_DEEP", False),
        max_iterations=_env_int("LDR_DEEP_MAX_ITERATIONS", d.max_iterations),
        max_sub_iterations=_env_int("LDR_DEEP_MAX_SUB_ITERATIONS", d.max_sub_iterations),
        max_subtopics=_env_int("LDR_DEEP_MAX_SUBTOPICS", d.max_subtopics),
        max_subtopics_hard=_env_int("LDR_DEEP_MAX_SUBTOPICS_HARD", d.max_subtopics_hard),
        subagent_budget_s=_env_int("LDR_DEEP_SUBAGENT_BUDGET_S", d.subagent_budget_s),
        subagent_hard_s=_env_int("LDR_DEEP_SUBAGENT_HARD_S", d.subagent_hard_s),
        time_budget_s=_env_int("LDR_DEEP_TIME_BUDGET_S", d.time_budget_s),
        fetch_max_chars=_env_int("LDR_DEEP_FETCH_MAX_CHARS", d.fetch_max_chars),
        extract_max_chars=_env_int("LDR_DEEP_EXTRACT_MAX_CHARS", d.extract_max_chars),
        extract_effort=os.environ.get("LDR_DEEP_EXTRACT_EFFORT", "").strip(),
        compact_effort=os.environ.get("LDR_DEEP_COMPACT_EFFORT", d.compact_effort).strip(),
        report_effort=os.environ.get("LDR_DEEP_REPORT_EFFORT", d.report_effort).strip(),
        verify_effort=os.environ.get("LDR_DEEP_VERIFY_EFFORT", d.verify_effort).strip(),
        sub_return_max_chars=_env_int("LDR_DEEP_SUB_RETURN_MAX_CHARS", d.sub_return_max_chars),
        search_results=_env_int("LDR_DEEP_SEARCH_RESULTS", d.search_results),
        snippet_chars=_env_int("LDR_DEEP_SNIPPET_CHARS", d.snippet_chars),
        context_tokens=_env_int("LDR_DEEP_CONTEXT_TOKENS", d.context_tokens),
        max_tokens=_env_int("LDR_LLM_MAX_TOKENS", d.max_tokens),
        compact_at=_env_int("LDR_DEEP_COMPACT_AT", d.compact_at),
        keep_recent=_env_int("LDR_DEEP_KEEP_RECENT", d.keep_recent),
        report=_env_bool("LDR_DEEP_REPORT", d.report),
        verify=_env_bool("LDR_DEEP_VERIFY", d.verify),
        report_evidence_tokens=_env_int("LDR_DEEP_REPORT_EVIDENCE_TOKENS", d.report_evidence_tokens),
        verify_page_tokens=_env_int("LDR_DEEP_VERIFY_PAGE_TOKENS", d.verify_page_tokens),
        verify_claim_source_tokens=_env_int("LDR_DEEP_VERIFY_CLAIM_SOURCE_TOKENS", d.verify_claim_source_tokens),
        verify_max_claims=_env_int("LDR_DEEP_VERIFY_MAX_CLAIMS", d.verify_max_claims),
        out_dir=os.environ.get("LDR_DEEP_OUT_DIR", ""),
        tokenizer_dir=os.environ.get("LDR_DEEP_TOKENIZER_DIR", ""),
    )


CONFIG = load_config()


def config() -> DeepConfig:
    return CONFIG


def enabled() -> bool:
    return CONFIG.enabled


# Which agent is running in this thread/context: "lead" or "sub<N>:<topic>". Set by the strategy; copied into
# LangGraph's tool threads (ContextThreadPoolExecutor copies contextvars) and set explicitly in subagent threads.
current_agent: contextvars.ContextVar[str] = contextvars.ContextVar("ldr_deep_agent", default="lead")


def out_path(*parts: str) -> Path | None:
    if not CONFIG.out_dir:
        return None
    p = Path(CONFIG.out_dir, *parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
