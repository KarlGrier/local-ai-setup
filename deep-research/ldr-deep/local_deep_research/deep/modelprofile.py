"""Per-model profiles (C3b) and sizes derived from the context (C3c): the one loader for the deep package's settings.

A profile is a KEY=VALUE file, one per model: ~/ai/deep-research/profiles/<name>.env (run-ldr.sh picks it with
LDR_MODEL_PROFILE=<name or path>, default flash-next, and passes its path to LDR as LDR_DEEP_MODEL_PROFILE). Every
setting below is resolved the same way, by run-ldr.sh, the research runner and the deep package:
  1. an explicit environment variable - as before (run-ldr.sh's callers, bench2, the research runner, tests);
  2. the profile's value;
  3. a size marked ctx: today's value scaled with the context, ``base * context // 131072`` - exactly today's value
     at Flash-Next's 131,072 tokens, so a model with a bigger context gets bigger views by itself;
     any other setting: the built-in default (today's value).
``auto`` (or an empty value) means "not given" for a number: a ctx size is then derived, any other number takes its
default. For a text setting (an effort, a path) an empty value is a value: "" = send no effort / no tokenizer.

With no profile and no variables every value is today's (Qwen3.8-Flash-Next on Strata, 131,072 tokens);
profiles/flash-next.env repeats those values and the equivalence test (staging/c3/tests) checks both against the
package as it was.

Stdlib only and no package imports: deep/codetool.py loads this file directly when it runs outside LDR's package
(tools/code-mcp.py), and run-ldr.sh runs it as a script (``python -I .../deep/modelprofile.py --shell``).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

REF_CONTEXT = 131_072          # Strata's --max-context for Qwen3.8-Flash-Next: today's sizes were tuned at this context
WS = Path("/home/USER/ai/deep-research")
PROFILES_DIR = WS / "profiles"
DEFAULT_PROFILE = "flash-next"
PROFILE_ENV = "LDR_DEEP_MODEL_PROFILE"      # the profile file LDR reads (set by run-ldr.sh)
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class Spec:
    field: str                 # DeepConfig field (deep package) or launcher name (run-ldr.sh / research runner)
    key: str                   # environment variable = profile key
    kind: str                  # int | float | bool | str (stripped; empty is a value) | word (stripped; empty = not
                               # given) | path (verbatim)
    default: Any               # today's value (for a ctx size: its value at REF_CONTEXT)
    ctx: bool = False          # derived from the context when not given
    group: str = ""
    aliases: tuple[str, ...] = ()
    doc: str = ""


def _s(*a, **k) -> Spec:
    return Spec(*a, **k)


# The deep package's settings (DeepConfig fields, same order and defaults as deep/__init__.py).
DEEP_SPECS: tuple[Spec, ...] = (
    # switches - environment only in practice (run-ldr.sh, the queue); listed so the loader knows them
    _s("enabled", "LDR_DEEP", "bool", False, group="switch", doc="the deep patch on"),
    # pace: step limits and time
    _s("max_iterations", "LDR_DEEP_MAX_ITERATIONS", "int", 200, group="pace", doc="lead agent model calls"),
    _s("max_sub_iterations", "LDR_DEEP_MAX_SUB_ITERATIONS", "int", 30, group="pace", doc="model calls per subagent"),
    _s("max_subtopics", "LDR_DEEP_MAX_SUBTOPICS", "int", 8, group="pace", doc="subtopics per research_subtopic call"),
    _s("max_subtopics_hard", "LDR_DEEP_MAX_SUBTOPICS_HARD", "int", 12, group="pace"),
    _s("subagent_budget_s", "LDR_DEEP_SUBAGENT_BUDGET_S", "int", 3600, group="pace"),
    _s("subagent_hard_s", "LDR_DEEP_SUBAGENT_HARD_S", "int", 7200, group="pace"),
    _s("time_budget_s", "LDR_DEEP_TIME_BUDGET_S", "int", 3 * 3600, group="pace", doc="research phase (s)"),
    # what the agents see of a page
    _s("fetch_max_chars", "LDR_DEEP_FETCH_MAX_CHARS", "int", 120_000, ctx=True, group="view",
       doc="page text given to extraction (and the user's file parts)"),
    _s("extract_max_chars", "LDR_DEEP_EXTRACT_MAX_CHARS", "int", 4000, group="view", doc="extraction output"),
    # efforts (our names: low / medium / high / xhigh; LDR_DEEP_EFFORT_MAP translates them for another API)
    _s("extract_effort", "LDR_DEEP_EXTRACT_EFFORT", "str", "", group="effort", doc='"" = the proxy / server decides'),
    _s("compact_effort", "LDR_DEEP_COMPACT_EFFORT", "str", "medium", group="effort"),
    _s("report_effort", "LDR_DEEP_REPORT_EFFORT", "str", "xhigh", group="effort", doc="outline, sections, opening"),
    _s("verify_effort", "LDR_DEEP_VERIFY_EFFORT", "str", "xhigh", group="effort",
       doc="citation check, setup check, critic, version / arithmetic / consistency checks"),
    _s("sub_return_max_chars", "LDR_DEEP_SUB_RETURN_MAX_CHARS", "int", 16_000, ctx=True, group="view",
       doc="how much of a subagent's report the lead sees"),
    _s("search_results", "LDR_DEEP_SEARCH_RESULTS", "int", 50, group="switch", doc="read but unused (SearXNG max)"),
    _s("snippet_chars", "LDR_DEEP_SNIPPET_CHARS", "int", 300, ctx=True, group="view",
       doc="snippet length the agents see per search result"),
    # context and output
    _s("context_tokens", "LDR_DEEP_CONTEXT_TOKENS", "int", REF_CONTEXT, group="context",
       aliases=("LDR_DEEP_CONTEXT",), doc="the model's context (prompt + max_tokens must fit)"),
    _s("max_tokens", "LDR_LLM_MAX_TOKENS", "int", 30_000, group="context", doc="completion budget per LDR call"),
    _s("compact_at", "LDR_DEEP_COMPACT_AT", "int", 56_000, ctx=True, group="compaction",
       doc="compact an agent's history above this many prompt tokens"),
    _s("keep_recent", "LDR_DEEP_KEEP_RECENT", "int", 6, group="compaction", doc="messages kept verbatim"),
    # report stage
    _s("report", "LDR_DEEP_REPORT", "bool", True, group="switch"),
    _s("verify", "LDR_DEEP_VERIFY", "bool", True, group="switch"),
    _s("report_evidence_tokens", "LDR_DEEP_REPORT_EVIDENCE_TOKENS", "int", 48_000, ctx=True, group="view",
       doc="evidence per section-writing call"),
    _s("verify_page_tokens", "LDR_DEEP_VERIFY_PAGE_TOKENS", "int", 40_000, ctx=True, group="view",
       doc="page text per call of the old per-source citation check"),
    _s("verify_claim_source_tokens", "LDR_DEEP_VERIFY_CLAIM_SOURCE_TOKENS", "int", 2000, ctx=True, group="view",
       doc="passages per cited source per claim (citation check)"),
    _s("verify_max_claims", "LDR_DEEP_VERIFY_MAX_CLAIMS", "int", 120, group="pace", doc="key claims checked; 0 = all"),
    _s("out_dir", "LDR_DEEP_OUT_DIR", "path", "", group="switch"),
    _s("tokenizer_dir", "LDR_DEEP_TOKENIZER_DIR", "path", "", group="tokenizer",
       doc='vocab.json + merges.txt + tokenizer.json of the served model; "" = chars / LDR_DEEP_TOK_CHARS_PER_TOKEN'),
    # ---- C3b / C3c: sizes that were hard-coded until 10-29 (defaults = the old literals)
    _s("report_max_output", "LDR_DEEP_REPORT_MAX_OUTPUT", "int", 60_000, group="context",
       doc="report calls' output cap (within the context); the model's own output limit"),
    _s("report_answer_reserve", "LDR_DEEP_REPORT_ANSWER_RESERVE", "int", 8192, group="context",
       doc="a report prompt is cut to context - this - LDR_DEEP_REPORT_MARGIN"),
    _s("report_margin", "LDR_DEEP_REPORT_MARGIN", "int", 1024, group="context", doc="report calls' token margin"),
    _s("token_margin", "LDR_DEEP_TOKEN_MARGIN", "int", 512, group="context",
       doc="agent calls: tokens kept free below the context (assumes exact token counts)"),
    _s("keep_recent_frac", "LDR_DEEP_KEEP_RECENT_FRAC", "float", 0.35, group="compaction",
       doc="share of compact_at the verbatim recent messages may take"),
    _s("compact_fallback_tokens", "LDR_DEEP_COMPACT_FALLBACK_TOKENS", "int", 12_000, ctx=True, group="compaction",
       doc="history kept verbatim (cut) when a compaction summary fails"),
    _s("report_findings_tokens", "LDR_DEEP_REPORT_FINDINGS_TOKENS", "int", 12_000, ctx=True, group="view",
       doc="subagent findings per section-writing call"),
    _s("section_extract_frac", "LDR_DEEP_SECTION_EXTRACT_FRAC", "float", 0.6, group="view",
       doc="share of the section evidence for extractions / claims (the rest: page passages)"),
    _s("outline_lead_tokens", "LDR_DEEP_OUTLINE_LEAD_TOKENS", "int", 10_000, ctx=True, group="view",
       doc="the lead's answer in the outline call (also at most 1/6 of the outline budget)"),
    _s("outline_findings_frac", "LDR_DEEP_OUTLINE_FINDINGS_FRAC", "float", 0.40, group="view",
       doc="share of the outline budget for subagent findings (a digest of every source gets the rest)"),
    _s("claims_per_source", "LDR_DEEP_CLAIMS_PER_SOURCE", "int", 40, ctx=True, group="view",
       doc="item 5: checked quotes per source in a section's evidence"),
    _s("read_passage_tokens", "LDR_DEEP_READ_PASSAGE_TOKENS", "int", 350, ctx=True, group="view",
       doc="item 6: passages of a page the reader fetched (no extraction) in the section evidence"),
    _s("seed_text_chars", "LDR_DEEP_SEED_TEXT_CHARS", "int", 60_000, ctx=True, group="view",
       doc="earlier findings put in front of the lead in a continued run"),
    _s("verify_batch_tokens", "LDR_DEEP_VERIFY_BATCH_TOKENS", "int", 36_000, ctx=True, group="view",
       doc="citation check (and the two-source verifier): tokens per call"),
    _s("verify_batch_claims", "LDR_DEEP_VERIFY_BATCH_CLAIMS", "int", 8, group="pace", doc="claims per citation-check call"),
    _s("tried_part_chars", "LDR_DEEP_TRIED_PART_CHARS", "int", 60_000, ctx=True, group="view",
       doc="tried list: one part of the user's files per call"),
    _s("tried_merge_chars", "LDR_DEEP_TRIED_MERGE_CHARS", "int", 100_000, ctx=True, group="view"),
    _s("tried_block_chars", "LDR_DEEP_TRIED_BLOCK_CHARS", "int", 36_000, ctx=True, group="view",
       doc="tried list block in the prompts"),
    # tokenizer
    _s("tok_msg_overhead", "LDR_DEEP_TOK_MSG_OVERHEAD", "int", 8, group="tokenizer",
       doc="chat-template tokens per message (ChatML)"),
    _s("tok_tools_overhead", "LDR_DEEP_TOK_TOOLS_OVERHEAD", "int", 150, group="tokenizer",
       doc="the template's tool-use instructions"),
    _s("tok_chars_per_token", "LDR_DEEP_TOK_CHARS_PER_TOKEN", "int", 3, group="tokenizer",
       doc="the estimate without a tokenizer"),
    # effort
    _s("tried_map_effort", "LDR_DEEP_TRIED_MAP_EFFORT", "str", "low", group="effort"),
    _s("tried_merge_effort", "LDR_DEEP_TRIED_MERGE_EFFORT", "str", "medium", group="effort"),
    _s("effort_map", "LDR_DEEP_EFFORT_MAP", "str", "", group="effort",
       doc='our effort names -> the API\'s, "xhigh=high,low=minimal"; "name=" sends no effort; "" = as is'),
    _s("effort_ladder", "LDR_DEEP_EFFORT_LADDER", "str", "lower", group="effort",
       doc="lower = a call with no answer or an error is retried one effort lower (Strata); same = errors are "
           "retried at the same effort after a pause, an empty answer is not retried (APIs)"),
    # pace
    _s("subagent_share", "LDR_DEEP_SUBAGENT_SHARE", "float", 0.75, group="pace",
       doc="a subagent's deadline: this share of the research time left / the waves still to run"),
    _s("subagent_min_start_s", "LDR_DEEP_SUBAGENT_MIN_START_S", "int", 60, group="pace",
       doc="no subagent starts with less time than this"),
    _s("read_max", "LDR_DEEP_READ_MAX", "int", 400, group="pace", doc="item 6: pages the reader fetches per run"),
    _s("read_primary_max", "LDR_DEEP_READ_PRIMARY_MAX", "int", 40, group="pace",
       doc="item 6: primary sources it adds per run"),
    _s("read_primary_per_page", "LDR_DEEP_READ_PRIMARY_PER_PAGE", "int", 2, group="pace",
       doc="item 6: primary-source links followed per page"),
    # code tool
    _s("code_read_lines", "LDR_DEEP_CODE_READ_LINES", "int", 120, ctx=True, group="code", doc="lines per code_read"),
    _s("code_grep_hits", "LDR_DEEP_CODE_GREP_HITS", "int", 40, ctx=True, group="code", doc="hits per code_search"),
    _s("code_tree_entries", "LDR_DEEP_CODE_TREE_ENTRIES", "int", 200, ctx=True, group="code"),
    _s("code_line_chars", "LDR_DEEP_CODE_LINE_CHARS", "int", 240, group="code", doc="a returned line is cut here"),
    _s("code_issue_chars", "LDR_DEEP_CODE_ISSUE_CHARS", "int", 3000, ctx=True, group="code",
       doc="an opened issue / PR's text"),
    _s("code_comment_chars", "LDR_DEEP_CODE_COMMENT_CHARS", "int", 1500, ctx=True, group="code",
       doc="each of its first comments"),
    _s("code_issue_list_chars", "LDR_DEEP_CODE_ISSUE_LIST_CHARS", "int", 600, ctx=True, group="code",
       doc="an issue's text in a search listing"),
    _s("code_short_reads", "LDR_DEEP_CODE_SHORT_READS", "bool", True, group="code",
       doc='the lead prompt\'s "read short ranges - never whole files" (0 = the large-context wording)'),
)

# run-ldr.sh and the research runner (not DeepConfig fields)
LAUNCH_SPECS: tuple[Spec, ...] = (
    _s("profile_model", "LDR_PROFILE_MODEL", "word", "", group="about", doc="the model this profile is for"),
    _s("profile_status", "LDR_PROFILE_STATUS", "word", "measured", group="about",
       doc="measured | draft (run-ldr.sh refuses a draft unless LDR_ALLOW_DRAFT_PROFILE=1)"),
    _s("prompt_caching", "LDR_PROMPT_CACHING", "word", "", group="about",
       doc="required = the client must cache prompts (not wired yet: needs an API launcher)"),
    _s("temperature", "LDR_TEMPERATURE", "word", "1.0", group="sampling", doc="exported as LDR_LLM_TEMPERATURE"),
    _s("workers", "LDR_WORKERS", "int", 1, group="pace", doc="subagent workers (LDR_LANGGRAPH_AGENT_MAX_SUBAGENT_WORKERS)"),
    _s("quick_max_iterations", "LDR_QUICK_MAX_ITERATIONS", "int", 12, group="pace",
       doc="quick jobs (LDR_QUICK_LIMITS=1): agent cycles"),
    _s("quick_cap_s", "LDR_QUICK_CAP_S", "int", 15 * 60, group="pace", doc="research runner: a quick job is stopped after"),
    _s("job_agent_effort", "LDR_JOB_AGENT_EFFORT", "str", "medium", group="effort",
       doc="research runner (Jan's deep jobs): the agent, through the proxy mode file"),
    _s("job_extract_effort", "LDR_JOB_EXTRACT_EFFORT", "str", "medium", group="effort",
       doc="research runner: extraction, through the proxy mode file"),
    _s("job_report_effort", "LDR_JOB_REPORT_EFFORT", "str", "medium", group="effort",
       doc="research runner: report writing (LDR_DEEP_REPORT_EFFORT at LDR's start)"),
    _s("job_verify_effort", "LDR_JOB_VERIFY_EFFORT", "str", "xhigh", group="effort",
       doc="research runner: citation check (LDR_DEEP_VERIFY_EFFORT at LDR's start)"),
)

ALL_SPECS = DEEP_SPECS + LAUNCH_SPECS
BY_KEY = {k: s for s in ALL_SPECS for k in (s.key, *s.aliases)}
BY_FIELD = {s.field: s for s in ALL_SPECS}


class ProfileError(Exception):
    pass


@dataclass
class Resolved:
    values: dict[str, Any]                 # field -> value (DEEP_SPECS + LAUNCH_SPECS)
    source: dict[str, str]                 # field -> "env KEY" | "profile KEY" | "derived" | "default"
    profile: str = ""                      # the profile file, "" = none
    errors: list[str] = field(default_factory=list)

    def deep(self) -> dict[str, Any]:
        return {s.field: self.values[s.field] for s in DEEP_SPECS}

    def launch(self) -> dict[str, Any]:
        return {s.field: self.values[s.field] for s in LAUNCH_SPECS}


# ---------------------------------------------------------------------------------------------------------- files
def read_profile(path: str | Path) -> dict[str, str]:
    """KEY=VALUE lines; '#' starts a comment (a whole line, or after whitespace); 'export ' and quotes are allowed."""
    out: dict[str, str] = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[7:].lstrip()
        k, sep, v = s.partition("=")
        k = k.strip()
        if not sep or not KEY_RE.match(k):
            raise ProfileError(f"{path}:{n}: not a KEY=VALUE line: {line!r}")
        v = v.strip()
        m = re.search(r"(^|\s)#", v)              # 'KEY=   # comment' is an empty value
        if m:
            v = v[:m.start()].rstrip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k] = v
    return out


def profile_file(name_or_path: str | None = None, profiles_dir: str | Path = PROFILES_DIR) -> Path:
    """A profile name ('flash-next') -> profiles/<name>.env; a path (with '/' or ending in .env) as given."""
    n = (name_or_path or DEFAULT_PROFILE).strip()
    if "/" in n or n.endswith(".env"):
        return Path(n).expanduser()
    return Path(profiles_dir) / f"{n}.env"


# ---------------------------------------------------------------------------------------------------------- values
def _parse(spec: Spec, raw: str) -> tuple[bool, Any]:
    """(given, value) of one raw string; given=False = fall through to the next source."""
    if spec.kind == "path":
        return True, raw
    if spec.kind == "str":
        return True, raw.strip()
    v = raw.strip()
    if spec.kind == "word":
        return (True, v) if v else (False, None)
    if not v or v.lower() == "auto":
        return False, None
    if spec.kind == "bool":
        return True, v.lower() in ("1", "true", "yes", "on")
    try:
        return True, (int(v) if spec.kind == "int" else float(v))
    except ValueError:
        raise ProfileError(f"{spec.key}={raw!r} is not {'an integer' if spec.kind == 'int' else 'a number'}")


def derive(base: int, context: int) -> int:
    """A ctx size at `context`: today's value scaled with the context (exactly today's value at 131,072)."""
    return max(1, int(base) * int(context) // REF_CONTEXT)


def resolve(env: Mapping[str, str] | None = None, profile: str | Path | None = None) -> Resolved:
    """Every setting from env > the profile > derived / default. profile=None: the file named by
    LDR_DEEP_MODEL_PROFILE in env (none if unset); "" = no profile."""
    env = os.environ if env is None else env
    errors: list[str] = []
    if profile is None:
        profile = env.get(PROFILE_ENV, "") or ""
    prof: dict[str, str] = {}
    if profile:
        try:
            prof = read_profile(profile)
        except (OSError, ProfileError) as e:
            errors.append(f"profile {profile}: {e}")
        for k in prof:
            if k not in BY_KEY:
                errors.append(f"profile {profile}: unknown key {k}")
    values: dict[str, Any] = {}
    source: dict[str, str] = {}

    def given(spec: Spec) -> tuple[bool, Any, str]:
        for where, m in (("env", env), ("profile", prof)):
            for k in (spec.key, *spec.aliases):
                if k in m:
                    try:
                        ok, v = _parse(spec, m[k])
                    except ProfileError as e:
                        errors.append(f"{where}: {e}")
                        continue
                    if ok:
                        return True, v, f"{where} {k}"
        return False, None, ""

    order = sorted(ALL_SPECS, key=lambda s: s.field != "context_tokens")   # the context first: ctx sizes need it
    for spec in order:
        ok, v, src = given(spec)
        if not ok:
            if spec.ctx:
                v, src = derive(spec.default, values["context_tokens"]), "derived"
            else:
                v, src = spec.default, "default"
        values[spec.field], source[spec.field] = v, src
    values = {s.field: values[s.field] for s in ALL_SPECS}
    return Resolved(values, source, str(profile or ""), errors)


def check_profile(path: str | Path) -> list[str]:
    """Problems of one profile file (unknown keys, values that do not parse) - [] when it is clean."""
    return resolve(env={}, profile=str(path)).errors


def warn(res: Resolved) -> None:
    for e in res.errors:
        print(f"deep model profile: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------------------------------------- CLI
def _shell(res: Resolved) -> str:
    """The values run-ldr.sh exports itself, as shell assignments."""
    v = res.values
    rows = {"P_FILE": res.profile, "P_MODEL": v["profile_model"], "P_STATUS": v["profile_status"],
            "P_CONTEXT": v["context_tokens"], "P_MAX_TOKENS": v["max_tokens"], "P_TEMPERATURE": v["temperature"],
            "P_WORKERS": v["workers"], "P_QUICK_ITERATIONS": v["quick_max_iterations"],
            "P_TOKENIZER_DIR": v["tokenizer_dir"]}
    return "\n".join(f"{k}={shlex.quote(str(x))}" for k, x in rows.items())


def _table(res: Resolved) -> str:
    lines = [f"profile: {res.profile or '(none)'}   context: {res.values['context_tokens']}"]
    for s in ALL_SPECS:
        lines.append(f"  {s.key:<36} {str(res.values[s.field])!s:<12} {res.source[s.field]}")
    return "\n".join(lines + [f"  ERROR: {e}" for e in res.errors])


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="modelprofile.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--profile", help="a profile name (profiles/<name>.env) or path; default: "
                                      f"$LDR_MODEL_PROFILE, else {DEFAULT_PROFILE}")
    ap.add_argument("--profiles-dir", default=str(PROFILES_DIR))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--shell", action="store_true", help="the values run-ldr.sh exports, as shell assignments")
    g.add_argument("--show", action="store_true", help="every setting with its value and where it came from")
    g.add_argument("--json", action="store_true", help="every setting as JSON")
    g.add_argument("--check", nargs="+", metavar="FILE", help="check profile files (unknown keys, bad values)")
    a = ap.parse_args(argv)
    if a.check:
        bad = 0
        for f in a.check:
            probs = check_profile(f) if Path(f).is_file() else [f"{f}: no such file"]
            print(f"{f}: " + ("ok" if not probs else "; ".join(probs)))
            bad += bool(probs)
        return 1 if bad else 0
    path = profile_file(a.profile or os.environ.get("LDR_MODEL_PROFILE") or DEFAULT_PROFILE, a.profiles_dir)
    if not path.is_file():
        print(f"modelprofile: no profile file {path}", file=sys.stderr)
        return 1
    res = resolve(profile=str(path.resolve()))
    if res.errors:
        for e in res.errors:
            print(f"modelprofile: {e}", file=sys.stderr)
        return 1
    if a.shell:
        print(_shell(res))
    elif a.json:
        print(json.dumps({"profile": res.profile, "values": res.values, "source": res.source}, indent=1))
    else:
        print(_table(res))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
