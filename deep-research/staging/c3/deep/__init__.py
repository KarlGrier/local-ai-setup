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

Settings (C3b/C3c, 10-29): every value comes from deep/modelprofile.py - an explicit LDR_DEEP_* variable, else the
model's profile file (LDR_DEEP_MODEL_PROFILE, set by run-ldr.sh from profiles/<model>.env), else today's default; the
sizes that fill a share of the context are derived from LDR_DEEP_CONTEXT_TOKENS (exactly today's values at 131,072).
"""

from __future__ import annotations

import contextvars
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import modelprofile as _modelprofile


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
    # C3b / C3c (10-29): sizes and choices that were hard-coded in the modules (defaults = the old literals; the ones
    # marked ctx in deep/modelprofile.py scale with context_tokens when not given)
    report_max_output: int = 60_000      # report calls' output cap, within the context (report.py)
    report_answer_reserve: int = 8192    # a report prompt is cut to context - this - report_margin
    report_margin: int = 1024
    token_margin: int = 512              # agent calls: tokens kept free below the context (middleware.py)
    keep_recent_frac: float = 0.35       # share of compact_at the verbatim recent messages may take
    compact_fallback_tokens: int = 12_000  # history kept (cut) when a compaction summary fails
    report_findings_tokens: int = 12_000   # subagent findings per section call
    section_extract_frac: float = 0.6      # share of a section's evidence for extractions / claims
    outline_lead_tokens: int = 10_000      # the lead's answer in the outline call
    outline_findings_frac: float = 0.40    # share of the outline budget for subagent findings
    claims_per_source: int = 40            # item 5: checked quotes per source in a section's evidence
    read_passage_tokens: int = 350         # item 6: passages of a page only the reader fetched
    seed_text_chars: int = 60_000          # earlier findings in front of the lead in a continued run (seed.py)
    verify_batch_tokens: int = 36_000      # citation check: tokens per call (also the two-source verifier)
    verify_batch_claims: int = 8           # citation check: claims per call
    tried_part_chars: int = 60_000         # tried list (tried.py): one part per call, merge input, prompt block
    tried_merge_chars: int = 100_000
    tried_block_chars: int = 36_000
    tok_msg_overhead: int = 8              # tokens.py: chat-template tokens per message
    tok_tools_overhead: int = 150          # tokens.py: the template's tool-use instructions
    tok_chars_per_token: int = 3           # tokens.py: the estimate without a tokenizer
    tried_map_effort: str = "low"
    tried_merge_effort: str = "medium"
    effort_map: str = ""                   # llm.py: our effort names -> the API's ("" = as is)
    effort_ladder: str = "lower"           # llm.py: lower (no answer / error -> one effort lower) | same
    subagent_share: float = 0.75           # strategy: a subagent's share of the research time left per wave
    subagent_min_start_s: int = 60         # strategy: no subagent starts with less time left
    read_max: int = 400                    # item 6 (reading.py): pages the reader fetches per run
    read_primary_max: int = 40             # item 6: primary sources it adds per run
    read_primary_per_page: int = 2         # item 6: primary-source links followed per page
    code_read_lines: int = 120             # code tool (codetool.py): lines per code_read
    code_grep_hits: int = 40               # hits per code_search
    code_tree_entries: int = 200
    code_line_chars: int = 240
    code_issue_chars: int = 3000           # an opened issue / PR's text
    code_comment_chars: int = 1500         # each of its first comments
    code_issue_list_chars: int = 600       # an issue's text in a search listing
    code_short_reads: bool = True          # the lead prompt's "read short ranges - never whole files"
    profile: str = ""                      # the model profile file these values were read with ("" = none)
    profile_errors: tuple = ()
    extra: dict = field(default_factory=dict)


_RESOLVED = None


def load_config() -> DeepConfig:
    """Every setting from deep/modelprofile.py: an explicit variable > the model profile > derived / default."""
    global _RESOLVED
    res = _modelprofile.resolve()
    _modelprofile.warn(res)
    _RESOLVED = res
    return DeepConfig(**res.deep(), profile=res.profile, profile_errors=tuple(res.errors))


def config_sources() -> dict[str, str]:
    """Where each setting of config() came from: 'env KEY', 'profile KEY', 'derived' (from the context) or 'default'."""
    return dict(_RESOLVED.source) if _RESOLVED is not None else {}


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
