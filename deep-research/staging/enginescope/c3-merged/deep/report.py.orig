"""Report stage of a deep run: a full report written from everything gathered, then a claim-verification pass.

  1. outline   the task, the lead's answer, all subagent findings and a digest of every page read -> sections, each
               with the source indices it needs
  2. sections  one call per section, with that section's evidence (all extractions of its sources, plus the most
               relevant passages of their stored page text) -> Markdown with [N] citations
  3. opening   title, "Answer" (in the task's prescribed format, if any), "Key findings", "Limitations"
  4. verify    every sentence that cites a source is checked against that source's stored page text (or its search
               snippet when the page was never read); one call per source; unsupported/partial claims are flagged in
               the text and listed in a "Citation check" section
Each LLM call is budgeted to stay under the context limit (and the proxy clamps max_tokens as a backstop).
The sizes (findings and evidence per section, the outline's view of the lead's answer, the output cap, the citation
check's batches) come from the model profile (deep/modelprofile.py, C3b/C3c 10-29); the defaults are the old numbers.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from . import config, current_agent
from .evidence import EvidenceStore, Source, cited_indices
from .prompts import OPENING_PROMPT, OUTLINE_PROMPT, SECTION_PROMPT, VERIFY_JOINT_PROMPT, VERIFY_PROMPT
from . import setup as setup_profile
from . import advisory
from . import checks
from . import claims as claim_store
from . import notyet as fresh_check
from . import tried as tried_list
from .tokens import count_text, truncate_to_tokens

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-']+")
STOP = set("""a an the and or of to in on for with by from at as is are was were be been being this that these those
it its into than then which who whom whose what when where why how not no nor but if so such can could may might must
shall should will would do does did done have has had having about above after again against all also any because
before below between both each few more most other over same some through under until very via per there their they
them our your you we he she his her""".split())


def _text(resp: Any) -> str:
    c = getattr(resp, "content", resp)
    if isinstance(c, list):
        c = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c or "").strip()


def _words(s: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(s or "") if w.lower() not in STOP and len(w) > 2}


def _paragraphs(text: str, target_chars: int = 900) -> list[str]:
    """Split page text into passages of roughly target_chars (on blank lines, then lines)."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    out, buf = [], ""
    for p in parts:
        if len(p) > 2 * target_chars:
            lines = p.split("\n")
            for ln in lines:
                if len(buf) + len(ln) > target_chars and buf:
                    out.append(buf)
                    buf = ""
                buf += ("\n" if buf else "") + ln
            continue
        if len(buf) + len(p) > target_chars and buf:
            out.append(buf)
            buf = ""
        buf += ("\n\n" if buf else "") + p
    if buf:
        out.append(buf)
    return out


def relevant_passages(text: str, query_words: set[str], max_tokens: int) -> str:
    """The passages of text sharing the most words with query_words, in page order, within max_tokens."""
    if not text or max_tokens <= 0:
        return ""
    if count_text(text) <= max_tokens:
        return text
    paras = _paragraphs(text)
    scored = []
    for i, p in enumerate(paras):
        w = _words(p)
        score = len(w & query_words) / (1 + 0.002 * len(p))
        scored.append((score, i, p))
    chosen, used = [], 0
    for score, i, p in sorted(scored, key=lambda x: -x[0]):
        n = count_text(p)
        if used + n > max_tokens:
            continue
        chosen.append((i, p))
        used += n
        if used > max_tokens * 0.97:
            break
    chosen.sort()
    out, last = [], -1
    for i, p in chosen:
        out.append(("[...]\n" if i != last + 1 else "") + p)
        last = i
    return "\n\n".join(out)


# phase 4 fixes (2026-10-27): rules added to the section / opening prompts when the fix is on (no braces: the prompts
# are str.format templates)
FIX_SECTION_RULES = [
    ("arith", "- When you derive a number from others, show the inputs and the operation in the sentence (for example "
              "\"110.6 GB / 9.4 KB per row = 11.8 million rows\"), so it can be recomputed."),
    ("version", "- A flag, environment variable or setting you recommend for the program the task is about must come "
                "from a source about that program at the user's version (its code at that version is the strongest). "
                "Label anything else - another engine of the same project, another version, another program - as such "
                "and do not present it as an option of the user's version. A source marked [OTHER VERSION ...], "
                "[RELEASE NOTES OF EVERY VERSION ...] or [ISSUE / PR ...] is about another version, every version or a "
                "proposal: never present its flags, defaults, files or numbers as the user's version's - say which "
                "version it is, or that it is a proposal, and keep it out of the steps you recommend unless a source "
                "at the user's version confirms it."),
    ("baseline", "- Compare a gain with the user's measured numbers like with like (prompt speed with prompt speed, "
                 "decode with decode, the same context and model). A setting the user already runs is not a gain."),
    # phase 4 item 6 (10-28): only read pages are in the evidence
    ("claims", "- The evidence gives checked verbatim quotes with their dates. State each fact as its quote supports it; "
               "give the date where timing matters (releases, prices, versions, rules in force, \"not yet\" "
               "statements), and where two dated quotes disagree, follow the newer one and say so."),
    ("read", "- Cite only the sources in the evidence above; every one of them was read. A source the findings cite "
             "that is not in the evidence could not be read: do not cite it - support the point with a source from "
             "the evidence, or leave the point out. Where the evidence holds a primary source (marked \"primary "
             "source behind [N]\"), cite it for the fact instead of, or next to, the page that reported it."),
]
FIX_OPENING_RULES = [
    ("consist", "The Answer and Key findings must agree with the sections: do not recommend a step that a section "
                "shows has no effect on the user's setup, and use the sections' figures and defaults."),
    ("version", "Recommend only settings the sections establish for the user's program at the user's version; keep "
                "other engines', versions' and programs' settings labelled as such."),
    ("baseline", "State gains against the user's measured numbers like with like; a setting the user already runs is "
                 "not a gain."),
]


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        # common repair: trailing commas
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
        except ValueError:
            return None


class ReportWriter:
    def __init__(self, query: str, store: EvidenceStore, model: Any, lead_answer: str,
                 progress: Callable[[str, int], None] | None = None,
                 terminate_check: Callable[[], None] | None = None):
        self.cfg = config()
        self.query, self.store, self.model, self.lead_answer = query, store, model, lead_answer or ""
        self.progress = progress or (lambda msg, pct: None)
        self.terminate_check = terminate_check or (lambda: None)
        self.calls: list[dict[str, Any]] = []
        self.qwords = _words(query)
        # phase 4 item 1 (2026-10-21): with LDR_DEEP_SETUP_PROFILE the report prompts carry the user's setup facts
        self.setup_path = setup_profile.profile_path()
        sp = (lambda p: setup_profile.with_setup(p, self.setup_path, query)) if self.setup_path else (lambda p: p)
        # phase 4 item 4 (2026-10-23): with LDR_DEEP_TRIED the "tried / ruled out" list from the user's files too
        tb = getattr(store, "tried_block", "")
        tp = (lambda p: tried_list.with_tried(p, tb)) if tb else (lambda p: p)
        self.p_outline, self.p_section, self.p_opening = (tp(sp(OUTLINE_PROMPT)), tp(sp(SECTION_PROMPT)),
                                                          tp(sp(OPENING_PROMPT)))
        # phase 4 fixes (2026-10-27, LDR_DEEP_FIX): rules that prevent what the checks below would flag
        for fix, rule in FIX_SECTION_RULES:
            if checks.fix_on(fix):
                self.p_section += "\n" + rule
        for fix, rule in FIX_OPENING_RULES:
            if checks.fix_on(fix):
                self.p_opening += "\n" + rule
        # Fix 6: the report stage plans its steps to end by the run's deadline (set by the strategy on the store)
        from .control import clock
        self.plan = checks.TimePlan(getattr(store, "run_deadline", None) if checks.fix_on("budget") else None, clock)

    # -- LLM ----------------------------------------------------------------------------------------------------------
    def _llm(self, kind: str, prompt: str) -> str:
        self.terminate_check()
        cfg = self.cfg                 # keep at least 8K for the answer (report_answer_reserve 8192, report_margin 1024)
        limit = cfg.context_tokens - cfg.report_answer_reserve - cfg.report_margin
        n = count_text(prompt)
        if n > limit:                                  # should not happen (budgets below); keep the call valid
            logger.warning(f"deep report: {kind} prompt {n} tokens > {limit}; truncating")
            prompt = truncate_to_tokens(prompt, limit)
            n = limit
        from .llm import invoke

        t = time.time()
        effort = (self.cfg.verify_effort if kind in ("verify", "setupcheck", "critic", "version", "arith", "consist")
                  else self.cfg.report_effort)
        # report calls may think and write at length: up to 60K output tokens (report_max_output), within the context
        mt = max(4096, min(cfg.report_max_output, cfg.context_tokens - n - cfg.report_margin))
        mt = self.plan.max_tokens(n, mt)              # Fix 6: an output that can still end by the run's deadline
        try:
            text, info = invoke(self.model, prompt, effort, what=f"report {kind}", max_tokens=mt)
        except TypeError:          # an older deep.llm already loaded in a running process
            text, info = invoke(self.model, prompt, effort, what=f"report {kind}")
        self.calls.append({"kind": kind, "prompt_tokens": n, "seconds": round(time.time() - t, 1),
                           "out_chars": len(text), "efforts": info.get("efforts"), "finish": info.get("finish")})
        self.last_finish = info.get("finish")
        return text

    # -- material -----------------------------------------------------------------------------------------------------
    def _findings(self, max_tokens: int) -> str:
        subs = [s for s in self.store.subagents
                if s.get("text") and not str(s.get("status", "")).startswith("not started")]
        if not subs:
            return "(no subagent findings)"
        per = max(400, max_tokens // max(1, len(subs)))
        parts = []
        for s in subs:
            parts.append(f"### Subtopic: {s['topic']}\n{truncate_to_tokens(s['text'], per)}")
        out = "\n\n".join(parts)
        return truncate_to_tokens(out, max_tokens)

    def _relevant_sources(self) -> list[Source]:
        """Sources worth reporting: every page read, plus snippet-only sources the agents cited. Item 6 (LDR_DEEP_FIX
        read): only pages that were read, plus the primary sources found from them."""
        cited = set(cited_indices(self.lead_answer))
        for s in self.store.subagents:
            cited |= set(cited_indices(s.get("text", "")))
        out = []
        for s in self.store.all_sources():
            if s.fetches and any(f.extraction and not f.extraction.startswith("NOT RELEVANT") for f in s.fetches):
                out.append(s)
            elif s.idx in cited:
                out.append(s)
        if checks.fix_on("read"):
            keep = {s.idx: s for s in out if s.page_text}
            for s in self.store.all_sources():
                if s.via is not None and s.via in keep and s.page_text:
                    keep.setdefault(s.idx, s)
            out = sorted(keep.values(), key=lambda s: s.idx)
        return out

    def _extractions(self, s: Source) -> str:
        if checks.fix_on("claims") and getattr(s, "claims", None):
            block = claim_store.evidence_block(s.claims, self.cfg.claims_per_source)    # item 5: the checked, dated
                                                                                         # quotes, not the raw lines
            if block:
                return block
        seen, parts = set(), []
        for f in s.fetches:
            e = (f.extraction or "").strip()
            if not e or e.startswith("NOT RELEVANT") or e in seen:
                continue
            seen.add(e)
            parts.append(e)
        if not parts and s.page_text and checks.fix_on("read"):
            # item 6: a page the reader fetched has no extraction - its passages nearest the task and its snippet
            qw = self.qwords | _words(s.title + " " + " ".join(s.snippets[:2]))
            parts = [f"(page read; its most relevant passages) "
                     f"{relevant_passages(s.page_text, qw, self.cfg.read_passage_tokens)}"]
        elif not parts and s.snippets:
            parts = [f"(search snippet only) {sn}" for sn in s.snippets[:2]]
        return "\n".join(parts)

    def _version_note(self, s: Source) -> str:
        """Fix 1 (10-28, the bundle rerun): a GitHub page of the user's pinned project at another version (main-branch
        docs and code, the releases list, an issue or PR) says so, ahead of its title - the titles are cut at 100
        characters and the quotes alone read as facts about the user's version."""
        if not checks.fix_on("version"):
            return ""
        from .codetool import version_note
        return version_note(s.url, getattr(self.store, "pins", None))

    def _label(self, s: Source) -> str:
        """'[N] title (url)', with the page's date and, for a primary source, the page it was found from (item 6)."""
        extra = (f", dated {s.date}" if getattr(s, "date", "") else "") + (
            f"; primary source behind [{s.via}]" if getattr(s, "via", None) is not None else "")
        note = self._version_note(s)
        return f"[{s.idx}] {'[' + note + '] ' if note else ''}{s.title[:100]} ({s.url}{extra})"

    def _digest(self, sources: list[Source], max_tokens: int) -> str:
        if not sources:
            return "(none)"
        per = max(60, max_tokens // len(sources))
        lines = []
        for s in sources:
            body = re.sub(r"\s+", " ", self._extractions(s))
            lines.append(f"{self._label(s)}\n  {truncate_to_tokens(body, per)}")
        return truncate_to_tokens("\n".join(lines), max_tokens)

    # -- stages -------------------------------------------------------------------------------------------------------
    def outline(self, sources: list[Source]) -> dict:
        budget = self.cfg.context_tokens - self.cfg.max_tokens - 6000
        lead = truncate_to_tokens(self.lead_answer, min(self.cfg.outline_lead_tokens, budget // 6))
        findings = self._findings(int(budget * self.cfg.outline_findings_frac))
        digest = self._digest(sources, budget - count_text(lead) - count_text(findings) - count_text(self.query) - 2000)
        prompt = self.p_outline.format(task=self.query, lead_answer=lead or "(none)", findings=findings, sources=digest)
        for attempt in range(2):
            data = _extract_json(self._llm("outline", prompt))
            if data and isinstance(data.get("sections"), list) and data["sections"]:
                return data
            logger.warning(f"deep report: outline not parseable (attempt {attempt + 1})")
        return {"title": self.query[:100], "answer_format": "",
                "sections": [{"heading": "Findings", "purpose": "What the research found",
                              "sources": [s.idx for s in sources]}]}

    def section(self, sec: dict, outline_text: str, by_idx: dict[int, Source]) -> str:
        heading = str(sec.get("heading") or "Findings").strip().lstrip("#").strip()
        purpose = str(sec.get("purpose") or "")
        want = []
        for x in sec.get("sources") or []:
            try:
                want.append(int(x))
            except (TypeError, ValueError):
                continue
        srcs = [by_idx[i] for i in dict.fromkeys(want) if i in by_idx]
        findings = self._findings(self.cfg.report_findings_tokens)
        budget = self.cfg.report_evidence_tokens
        share = self.cfg.section_extract_frac            # 0.6: extractions / claims first, page passages after
        qw = self.qwords | _words(heading + " " + purpose)
        # 1) every extraction of the section's sources; 2) relevant page passages with what is left
        blocks, used = {}, 0
        for s in srcs:
            ex = self._extractions(s)
            blk = f"{self._label(s)}\n{ex}"
            n = count_text(blk)
            if used + n > budget * share:
                blk = truncate_to_tokens(blk, max(200, int(budget * share) - used))
                n = count_text(blk)
            blocks[s.idx] = blk
            used += n
        read = [s for s in srcs if s.page_text]
        if read and used < budget:
            per = (budget - used) // len(read)
            for s in read:
                extra = relevant_passages(s.page_text, qw, per)
                if extra:
                    blocks[s.idx] += f"\n--- more of the page [{s.idx}] ---\n{extra}"
        evidence = "\n\n".join(blocks[s.idx] for s in srcs) or "(no page evidence assigned; use the findings)"
        prompt = self.p_section.format(task=self.query, outline=outline_text, heading=heading, purpose=purpose,
                                       evidence=evidence, findings=findings)
        text = self._llm("section", prompt)
        if not text:
            return f"## {heading}\n\n(This section could not be written.)"
        if not text.lstrip().startswith("#"):
            text = f"## {heading}\n\n{text}"
        return text

    def opening(self, title: str, answer_format: str, sections_md: str) -> tuple[str, str]:
        fmt = f"\nRequired answer format (from the task): {answer_format}\n" if answer_format else ""
        budget = self.cfg.context_tokens - self.cfg.max_tokens - 4000
        body = truncate_to_tokens(sections_md, budget - count_text(self.query) - 1500)
        text = self._llm("opening", self.p_opening.format(task=self.query, format_note=fmt, sections=body, title=title))
        head, _, lim = text.partition("===LIMITATIONS===")
        head = head.strip() or f"# {title}"
        if not head.startswith("#"):
            head = f"# {title}\n\n{head}"
        return head, lim.strip()

    # -- verification ---------------------------------------------------------------------------------------------------
    @staticmethod
    def split_claims(md: str) -> list[dict]:
        """Sentences / table rows / bullets that carry [N] citations, with their line numbers."""
        claims = []
        in_code = False
        section = ""
        for ln, line in enumerate(md.split("\n")):
            s = line.strip()
            if s.startswith("```"):
                in_code = not in_code
            if s.startswith("## "):
                section = s[3:].strip()
            if in_code or not s or s.startswith("#") or re.match(r"^\|?\s*:?-{3,}", s):
                continue
            if s.startswith("|"):
                if cited_indices(s):
                    claims.append({"line": ln, "text": s, "sources": cited_indices(s), "section": section})
                continue
            # normalise "sentence. [3]" -> "sentence [3]." so the citation stays with its sentence
            s2 = re.sub(r"([.!?])((?:\s*\[\d+(?:\s*[,–-]\s*\d+)*\])+)", r"\2\1", s)
            for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[*_])", s2):
                idx = cited_indices(sent)
                if idx and len(WORD_RE.findall(sent)) >= 4:
                    claims.append({"line": ln, "text": sent.strip(), "sources": idx, "section": section})
        return claims

    @staticmethod
    def select_key_claims(claims: list[dict], n: int) -> list[dict]:
        """At most n claims: first the Answer and Key findings, then sentences with specific facts (figures, dates,
        quoted text, several capitalised names), then the rest; document order within each group."""
        if not n or len(claims) <= n:
            return claims

        def prio(c):
            sec = (c.get("section") or "").lower()
            if sec.startswith("answer") or sec.startswith("key finding"):
                return 0
            t = re.sub(r"\[\d+(?:\s*[,–-]\s*\d+)*\]", "", c["text"])
            if re.search(r"\d", t) or re.search(r"[\"“”]", t) or len(re.findall(r"\b[A-Z][a-z]+", t)) >= 3:
                return 1
            return 2
        order = sorted(range(len(claims)), key=lambda i: (prio(claims[i]), i))[:n]
        return [claims[i] for i in sorted(order)]

    def verify(self, md: str, claims: list[dict] | None = None) -> list[dict]:
        """Check each cited claim against all the sources it cites, together: per claim, the most relevant passages
        of each cited source's stored page text (or its snippets if the page was never read); claims batched ~8 per
        call. (The first design checked one source at a time; a sentence citing two sources that each state half of
        it then came out "partial" twice: 66 % of multi-source claims vs 17 % of single-source ones in smoke 2.)"""
        if claims is None:
            claims = self.split_claims(md)
        else:
            claims = [{k: c[k] for k in ("line", "text", "sources", "section") if k in c} for c in claims]
        per_src = self.cfg.verify_claim_source_tokens
        items = []
        for ci, c in enumerate(claims):
            plain = re.sub(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]", "", c["text"])
            c["plain"] = plain
            words = _words(plain)
            blocks, kinds = [], set()
            for i in c["sources"]:
                s = self.store.source(i)
                if s is None:
                    blocks.append(f"Source [{i}]: not in the research's evidence (unknown index)")
                    kinds.add("none")
                    continue
                if s.page_text:
                    txt, kind = relevant_passages(s.page_text, words, per_src), "page"
                else:
                    txt = "\n".join(s.snippets[:3] + [f.extraction for f in s.fetches if f.extraction])
                    txt, kind = truncate_to_tokens(txt, per_src), "snippet"
                kinds.add(kind)
                label = "page text" if kind == "page" else "search snippet only (page never read)"
                note = self._version_note(s)
                label += f"; {note}" if note else ""
                blocks.append(f"Source [{i}] {s.title[:100]} — {label}:\n{txt}")
            c["checked_against"] = sorted(kinds)
            items.append((ci, blocks))
        # batches of up to 8 claims and ~36K tokens (verify_batch_claims, verify_batch_tokens)
        batches, cur, cur_tok = [], [], 0
        per_call, per_call_tok = self.cfg.verify_batch_claims, self.cfg.verify_batch_tokens
        for ci, blocks in items:
            body = "\n\n".join(blocks)
            n = count_text(body) + count_text(claims[ci]["plain"]) + 30
            if cur and (len(cur) >= per_call or cur_tok + n > per_call_tok):
                batches.append(cur)
                cur, cur_tok = [], 0
            cur.append((ci, body))
            cur_tok += n
        if cur:
            batches.append(cur)
        for b, batch in enumerate(batches):
            self.progress(f"Checking citations: batch {b + 1} of {len(batches)} ({len(batch)} claims)",
                          93 + int(6 * b / max(1, len(batches))))
            listing = "\n\n".join(
                f"### Claim {j + 1}\n{claims[ci]['plain']}\nCited: {', '.join(f'[{i}]' for i in claims[ci]['sources'])}\n{body}"
                for j, (ci, body) in enumerate(batch))
            out = self._llm("verify", VERIFY_JOINT_PROMPT.format(items=listing))
            got = {}
            for line in out.splitlines():
                line = line.strip().strip(",")
                if line.startswith("{"):
                    try:
                        d = json.loads(line)
                        got[int(d.get("claim"))] = d
                    except (ValueError, TypeError):
                        continue
            for j, (ci, _) in enumerate(batch):
                d = got.get(j + 1)
                c = claims[ci]
                if d is None:
                    c.update(verdict="no_answer", note="", quote="", supporting=[])
                    continue
                v = str(d.get("verdict", "")).lower()
                c.update(verdict=v if v in ("supported", "partial", "unsupported") else "no_answer",
                         note=str(d.get("note", ""))[:300], quote=str(d.get("quote", ""))[:400],
                         supporting=[x for x in (d.get("supporting") or []) if isinstance(x, int)])
        for c in claims:
            c.pop("plain", None)
            c["checks"] = {}
        return claims

    def verify_per_source(self, md: str, claims: list[dict] | None = None) -> list[dict]:
        """The first design (one call per cited source, verdict per source, best one wins); kept for comparisons."""
        if claims is None:
            claims = self.split_claims(md)
        else:
            claims = [{k: c[k] for k in ("line", "text", "sources")} for c in claims]
        by_src: dict[int, list[int]] = {}
        for ci, c in enumerate(claims):
            c["checks"] = {}
            for i in c["sources"]:
                by_src.setdefault(i, []).append(ci)
        n_src = len(by_src)
        for k, (idx, cis) in enumerate(sorted(by_src.items())):
            self.progress(f"Checking citations: source {k + 1} of {n_src} ([{idx}], {len(cis)} claims)",
                          93 + int(6 * k / max(1, n_src)))
            s = self.store.source(idx)
            if s is None:
                for ci in cis:
                    claims[ci]["checks"][idx] = {"verdict": "no_source", "note": "index not in the evidence store"}
                continue
            if s.page_text:
                kind, kind_note = "page", "The text below was extracted from the page when the research read it."
                words = set().union(*(_words(claims[ci]["text"]) for ci in cis))
                text = relevant_passages(s.page_text, words, self.cfg.verify_page_tokens)
            else:
                kind = "snippet"
                kind_note = ("The page was never read; only its search-result snippet(s) and any extraction are "
                             "available below.")
                text = "\n".join(s.snippets[:4] + [f.extraction for f in s.fetches if f.extraction])
            if not text.strip():
                for ci in cis:
                    claims[ci]["checks"][idx] = {"verdict": "no_text", "kind": kind}
                continue
            for start in range(0, len(cis), 25):
                part = cis[start:start + 25]
                listing = "\n".join(f"{j + 1}. {re.sub(r'\s*\[\d+(?:\s*[,–-]\s*\d+)*\]', '', claims[ci]['text'])}"
                                    for j, ci in enumerate(part))
                out = self._llm("verify", VERIFY_PROMPT.format(idx=idx, title=s.title, url=s.url, kind_note=kind_note,
                                                               text=text, claims=listing))
                got = {}
                for line in out.splitlines():
                    line = line.strip().strip(",")
                    if not line.startswith("{"):
                        continue
                    try:
                        d = json.loads(line)
                        got[int(d.get("claim"))] = d
                    except (ValueError, TypeError):
                        continue
                for j, ci in enumerate(part):
                    d = got.get(j + 1)
                    if d is None:
                        claims[ci]["checks"][idx] = {"verdict": "no_answer", "kind": kind}
                    else:
                        v = str(d.get("verdict", "")).lower()
                        v = v if v in ("supported", "partial", "unsupported") else "no_answer"
                        claims[ci]["checks"][idx] = {"verdict": v, "kind": kind, "quote": str(d.get("quote", ""))[:400],
                                                     "note": str(d.get("note", ""))[:300]}
        rank = {"supported": 3, "partial": 2, "unsupported": 1, "no_answer": 0, "no_text": 0, "no_source": 0}
        for c in claims:
            best = max(c["checks"].values(), key=lambda d: rank.get(d["verdict"], 0), default={"verdict": "no_answer"})
            c["verdict"] = best["verdict"]
            c["checked_against"] = sorted({d.get("kind", "?") for d in c["checks"].values()})
        return claims

    @staticmethod
    def annotate(md: str, claims: list[dict], notes: bool = False) -> str:
        """Put a flag right after each unsupported / partly supported sentence (after its citation markers); with
        notes=True (Fix 2) the flag carries the checker's note."""
        lines = md.split("\n")
        flags = {"unsupported": " **[⚠ not supported by the cited source]**",
                 "partial": " *[⚠ only partly supported by the cited source]*"}
        noted = checks.verify_flags(claims) if notes else {}
        cite = r"\[\d+(?:\s*[,–-]\s*\d+)*\]"
        for c in claims:
            mark = noted[c["verdict"]](c) if c.get("verdict") in noted else flags.get(c.get("verdict"))
            if not mark:
                continue
            line = lines[c["line"]]
            plain = re.sub(r"\s*" + cite, "", c["text"])
            words = WORD_RE.findall(plain)
            pos = -1
            if words:
                anchor = r"\W+".join(map(re.escape, words[-4:]))
                for m in re.finditer(anchor, line):
                    pos = m.end()
            if pos < 0:
                lines[c["line"]] = line + mark
                continue
            m2 = re.match(r"((?:\s*" + cite + r")*[.!?]?(?:\s*" + cite + r")*)", line[pos:])
            end = pos + (len(m2.group(1)) if m2 else 0)
            if line[end:].startswith(mark):
                continue
            lines[c["line"]] = line[:end] + mark + line[end:]
        out = "\n".join(lines)
        for mark in flags.values():                  # two claims ending at the same spot: one flag
            out = re.sub("(" + re.escape(mark) + "){2,}", mark, out)
        if notes:
            out = re.sub(r"( \*{1,2}\[⚠ [^\]\n]*\]\*{1,2})\1+", r"\1", out)
        return out

    @staticmethod
    def check_section(claims: list[dict], total: int | None = None) -> str:
        n = len(claims)
        cnt = {}
        for c in claims:
            cnt[c["verdict"]] = cnt.get(c["verdict"], 0) + 1
        sup, par, uns = cnt.get("supported", 0), cnt.get("partial", 0), cnt.get("unsupported", 0)
        other = n - sup - par - uns
        snippet_only = sum(1 for c in claims if c.get("checked_against") == ["snippet"])
        out = ["## Citation check", "",
               f"Cited sentences were checked against the text of the sources they cite, as the research stored "
               f"it (the page text where the page was read, otherwise only its search snippet). "
               + (f"The key {n} of the report's {total} cited sentences were checked (all of the Answer and Key "
                  f"findings, then the sentences with figures, dates, quotations or names). " if total and total > n
                  else "")
               + f"{n} cited claims: "
               f"**{sup} supported**, **{par} partly supported**, **{uns} not supported**"
               + (f", {other} could not be checked" if other else "")
               + (f"; {snippet_only} were checked against a search snippet only" if snippet_only else "") + "."]
        flagged = [c for c in claims if c["verdict"] in ("unsupported", "partial")]
        if flagged:
            out += ["", "| claim | cites | verdict | what the source says / lacks |", "|---|---|---|---|"]
            for c in flagged:
                claim = re.sub(r"\s*\[\d+(?:\s*[,–-]\s*\d+)*\]", "", c["text"]).replace("|", "\\|")
                notes = c.get("note") or "; ".join(f"[{i}] {d.get('note') or d.get('verdict')}"
                                                   for i, d in c["checks"].items()
                                                   if d.get("verdict") in ("unsupported", "partial"))
                out.append(f"| {claim[:220]} | {', '.join(f'[{i}]' for i in c['sources'])} | {c['verdict']} | "
                           f"{notes.replace('|', chr(92) + '|')[:300]} |")
        return "\n".join(out)

    # -- all ----------------------------------------------------------------------------------------------------------
    def run(self) -> dict[str, Any]:
        token = current_agent.set("report")
        t0 = time.time()
        try:
            self.read_stats = self._finish_reading()
            sources = self._relevant_sources()
            by_idx = {s.idx: s for s in self.store.all_sources()}
            self.progress(f"Planning the report from {len(sources)} sources", 88)
            ol = self.outline(sources)
            secs = ol.get("sections") or []
            # Fix 6: with the run's deadline near, fewer sections (the rest merged into the last one), so the checks fit
            cap = (self.plan.max_sections(after=min(self._checks_min_s(), 0.5 * self.plan.left()))
                   if checks.fixes_on() else None)        # the checks never take more than half of what is left
            if cap is not None and len(secs) > cap:
                keep, rest = secs[:cap - 1], secs[cap - 1:]
                keep.append({"heading": rest[0].get("heading") if len(rest) == 1 else "Further findings",
                             "purpose": "; ".join(str(x.get("purpose") or x.get("heading") or "") for x in rest),
                             "sources": [i for x in rest for i in (x.get("sources") or [])]})
                self.plan.notes.append(f"{len(secs)} planned sections written as {cap} to finish within the time budget")
                secs = ol["sections"] = keep
            outline_text = "\n".join(f"- {s.get('heading')}: {s.get('purpose', '')}" for s in secs)
            parts = []
            for i, sec in enumerate(secs):
                self.progress(f"Writing section {i + 1} of {len(secs)}: {sec.get('heading')}", 89 + int(3 * i / max(1, len(secs))))
                parts.append(self.section(sec, outline_text, by_idx))
            sections_md = "\n\n".join(parts)
            title = str(ol.get("title") or self.query[:100]).strip()
            self.progress("Writing the answer and key findings", 92)
            head, limitations = self.opening(title, str(ol.get("answer_format") or ""), sections_md)
            body = head + "\n\n" + sections_md + ("\n\n" + limitations if limitations else "")
            # save the report before the citation check, so a stopped or failed check never loses it
            if self.store.out_dir is not None:
                try:
                    (self.store.out_dir / "report-unverified.md").write_text(body + "\n", encoding="utf-8")
                    (self.store.out_dir / "outline.json").write_text(json.dumps(ol, indent=1, ensure_ascii=False),
                                                                    encoding="utf-8")
                except OSError:
                    logger.exception("deep report: could not write the unverified report")
            if checks.fixes_on():
                return self._finish_fixed(body, ol, secs, t0)
            claims: list[dict] = []
            check_md = ""
            all_claims = 0
            if self.cfg.verify:
                every = self.split_claims(body)
                all_claims = len(every)
                try:
                    claims = self.verify(body, claims=self.select_key_claims(every, self.cfg.verify_max_claims))
                    body = self.annotate(body, claims)
                    check_md = self.check_section(claims, total=all_claims)
                except Exception as exc:  # noqa: BLE001
                    if "terminat" in type(exc).__name__.lower():
                        raise
                    logger.exception("deep report: citation check failed; keeping the report without it")
                    check_md = "## Citation check\n\nThe citation check did not complete (see the log)."
                    claims = []
            # phase 4 item 1 (2026-10-21): the setup check, the safety net for the lead agent - each statement that
            # contradicts the user's setup facts gets the fix right after it and a line in a short section
            setup_md, setup_res = "", None
            body_as_written = body                 # the advisory checks below read the report without the setup marks
            if self.setup_path:
                self.progress("Checking statements about your computer against your setup", 98)
                try:
                    setup_res = setup_profile.check(lambda pr: (self._llm("setupcheck", pr), self.last_finish),
                                                    body, self.setup_path)
                    body, setup_md = setup_profile.annotate(body, setup_res)
                except Exception as exc:  # noqa: BLE001
                    if "terminat" in type(exc).__name__.lower():
                        raise
                    logger.exception("deep report: setup check failed; keeping the report without it")
                    setup_md = "## Setup check\n\nThe setup check did not complete (see the log)."
                if self.store.out_dir is not None and setup_res is not None:
                    try:
                        (self.store.out_dir / "setupcheck.json").write_text(
                            json.dumps(setup_res, indent=1, ensure_ascii=False), encoding="utf-8")
                    except OSError:
                        logger.exception("deep report: could not write setupcheck.json")
            # phase 4 item 2 (2026-10-23, in item 4's runs): "not yet" statements get a fresh, dated search; each outdated
            # one gets the update right after it and a line in a short "Fresh check" section (LDR_DEEP_NOTYET)
            fresh_md, fresh_res = "", None
            if fresh_check.enabled():
                self.progress("Checking 'not yet' statements with a fresh search", 99)
                try:
                    fresh_res = fresh_check.check(lambda pr: self._llm("notyet", pr), body_as_written)
                    body, fresh_md = fresh_check.annotate(body, fresh_res)
                except Exception as exc:  # noqa: BLE001
                    if "terminat" in type(exc).__name__.lower():
                        raise
                    logger.exception("deep report: fresh check failed; keeping the report without it")
                    fresh_md = "## Fresh check\n\nThe fresh check of \"not yet\" statements did not complete (see the log)."
                if self.store.out_dir is not None and fresh_res is not None:
                    try:
                        (self.store.out_dir / "notyet.json").write_text(
                            json.dumps(fresh_res, indent=1, ensure_ascii=False), encoding="utf-8")
                    except OSError:
                        logger.exception("deep report: could not write notyet.json")
            # phase 4 item 3 (2026-10-21): advisory only - the critic and / or the two-source verifier (flag-only) add
            # a short "Check these" list; the report text is not changed
            advise_md = ""
            if advisory.critic_on() or advisory.verify2_on():
                self.progress("A second reading for points to check", 99)
                adv: dict[str, Any] = {}
                try:
                    if advisory.critic_on():
                        adv["critic"] = advisory.critic(lambda pr: self._llm("critic", pr), self.query, body_as_written)
                    if advisory.verify2_on():
                        adv["verify2"] = advisory.verify2(self, body_as_written, _words, relevant_passages, count_text)
                    advise_md = advisory.check_these(adv.get("critic"), adv.get("verify2"))
                except Exception as exc:  # noqa: BLE001
                    if "terminat" in type(exc).__name__.lower():
                        raise
                    logger.exception("deep report: the advisory checks failed; keeping the report without them")
                if self.store.out_dir is not None and adv:
                    try:
                        (self.store.out_dir / "advisory.json").write_text(json.dumps(adv, indent=1, ensure_ascii=False),
                                                                         encoding="utf-8")
                    except OSError:
                        logger.exception("deep report: could not write advisory.json")
            report = (body + ("\n\n" + setup_md if setup_md else "") + ("\n\n" + fresh_md if fresh_md else "")
                      + ("\n\n" + advise_md if advise_md else "")
                      + ("\n\n" + check_md if check_md else ""))
            cited = cited_indices(report)
            stats = {
                "report_seconds": round(time.time() - t0, 1), "report_calls": len(self.calls),
                "sections": len(secs), "sources_cited": len(cited),
                "sources_cited_read": sum(1 for i in cited if (self.store.source(i) and self.store.source(i).fetches)),
                "claims": len(claims), "claims_total": all_claims,
                "verdicts": {v: sum(1 for c in claims if c["verdict"] == v) for v in
                             ("supported", "partial", "unsupported", "no_answer", "no_text", "no_source")},
                "effort_drops": effort_drop_stats(self.store),
                **self.store.stats(),
            }
            return {"markdown": report, "outline": ol, "claims": claims, "stats": stats, "calls": self.calls,
                    "cited": cited}
        finally:
            current_agent.reset(token)


    # -- phase 4 item 6 (10-28) ------------------------------------------------------------------------------------------
    def _finish_reading(self) -> dict[str, Any] | None:
        """Queue what the lead's answer cites, wait a little for pages still being read (at most 12 % of the time
        left, 15 min), then stop the reader: what is not read by then is not cited."""
        reader = getattr(self.store, "reader", None)
        if reader is None or not checks.fix_on("read"):
            return None
        from .control import clock
        reader.want(self.lead_answer)
        wait = min(900.0, 0.12 * self.plan.left()) if self.plan.deadline else 600.0
        if reader.pending:
            self.progress(f"Reading the last {reader.pending} cited pages", 87)
        res = reader.finish(clock() + max(0.0, wait))
        reader.stop()
        self.store.add_note("reading", **res)
        logger.info(f"deep report: reading - {res}")
        return res

    # -- the phase 4 fixes (2026-10-27, LDR_DEEP_FIX) ----------------------------------------------------------------
    def _checks_min_s(self) -> float:
        """The least time the checks get when sections are cut (Fix 6): the setup and version checks, 20 claims."""
        t = 20 * checks.EST["claim"]
        if self.setup_path:
            t += checks.EST["setup"]
        if checks.fix_on("version"):
            t += checks.EST["version"]
        return t

    def _save(self, name: str, data: Any) -> None:
        if self.store.out_dir is None or data is None:
            return
        try:
            (self.store.out_dir / name).write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str),
                                                   encoding="utf-8")
        except OSError:
            logger.exception(f"deep report: could not write {name}")

    def _guarded(self, what: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if "terminat" in type(exc).__name__.lower():
                raise
            logger.exception(f"deep report: {what} failed; keeping the report without it")
            return None

    def _finish_fixed(self, body: str, ol: dict, secs: list, t0: float) -> dict[str, Any]:
        """The checks with the fixes on. Every check reads the report as written (no marks); the marks of all of them
        are put in at the end. Order = priority when time is short (Fix 6): the citation guard, the setup check (with
        Fix 5), the version check, the arithmetic check, the consistency pass, the citation check (as many claims as
        fit), the fresh check, the critic. A check that does not fit is listed as skipped."""
        plan, store, task = self.plan, self.store, self.query
        res: dict[str, Any] = {}
        plan.scale = max(0.15, min(2.0, count_text(body) / 45000))   # the check estimates scale with the report
        # Fix 4: citations outside the evidence (no model call)
        cite_res = None
        if checks.fix_on("cite"):
            body, cite_res = checks.cite_guard(body, (lambda i: store.source(i) is not None and bool(store.source(i).page_text))
                                               if checks.fix_on("read") else (lambda i: store.source(i) is not None))
            res["cite"] = cite_res
        written = checks.strip_marks(body)          # what the model checks read
        claim_min = min(20 * checks.EST["claim"], 0.2 * plan.left())   # kept for the citation check, at most 1/5 of what is left
        # the setup check (+ Fix 5's recommendation and like-with-like judgments)
        setup_res = None
        if self.setup_path and plan.fits("setup", after=claim_min):
            self.progress("Checking statements about your computer against your setup", 93)
            setup_res = self._guarded("setup check", lambda: setup_profile.check(
                lambda pr: (self._llm("setupcheck", pr), self.last_finish), written, self.setup_path, task=task,
                retry_ok=lambda: plan.fits("setup", after=claim_min)))
            self._save("setupcheck.json", setup_res)
        # Fix 1: the version check (the code tool's pinned clones when it is on, and the evidence)
        ver_res, versions = None, ""
        if checks.fix_on("version") and plan.fits("version", after=claim_min):
            self.progress("Checking the settings the report names against your version", 94)
            code, pins = self._pinned_repos()
            versions = ", ".join(f"{k} {v}" for k, v in (pins or {}).items())
            ver_res = self._guarded("version check", lambda: checks.version_check(
                lambda pr: self._llm("version", pr), task, written, store, code=code, pins=pins))
            self._save("versioncheck.json", ver_res)
        # Fix 3: the arithmetic, recomputed in code
        ar_res = None
        if checks.fix_on("arith") and plan.fits("arith", after=claim_min):
            self.progress("Recomputing the report's calculations", 95)
            ar_res = self._guarded("arithmetic check", lambda: checks.arith_check(
                lambda pr: self._llm("arith", pr), written))
            self._save("arithcheck.json", ar_res)
        # the consistency pass
        co_res = None
        if checks.fix_on("consist") and plan.fits("consist", after=claim_min):
            self.progress("Looking for statements that contradict each other", 96)
            co_res = self._guarded("consistency check", lambda: checks.consistency_check(
                lambda pr: self._llm("consist", pr), task, written,
                facts=setup_profile.facts_for(self.setup_path, task) if self.setup_path else ""))
            self._save("consistency.json", co_res)
        # the citation check: as many key claims as still fit (the critic's time kept back)
        claims: list[dict] = []
        check_md, all_claims = "", 0
        if self.cfg.verify:
            every = self.split_claims(body)
            all_claims = len(every)
            n = plan.claims(after=plan.est("critic") if advisory.critic_on() else 0.0, wanted=self.cfg.verify_max_claims)
            if n <= 0:
                plan.skipped.append("citation check")
                check_md = "## Citation check\n\nThe citation check was not run: the time budget was used up."
            else:
                if n < (self.cfg.verify_max_claims or all_claims) and n < all_claims:
                    plan.notes.append(f"citation check cut to {n} key claims to finish within the time budget")
                got = self._guarded("citation check", lambda: self.verify(body, claims=self.select_key_claims(every, n)))
                if got is None:
                    check_md = "## Citation check\n\nThe citation check did not complete (see the log)."
                else:
                    claims = got
                    body = self.annotate(body, claims, notes=checks.fix_on("inline"))
                    check_md = self.check_section(claims, total=all_claims)
        cs = checks.cite_section(cite_res)
        if cs:
            check_md = (check_md + "\n\n" + cs) if check_md else "## Citation check\n\n" + cs
        # the fresh check of "not yet" statements (LDR_DEEP_NOTYET, off by default)
        fresh_md, fresh_res = "", None
        if fresh_check.enabled() and plan.fits("notyet"):
            self.progress("Checking 'not yet' statements with a fresh search", 98)
            fresh_res = self._guarded("fresh check", lambda: fresh_check.check(lambda pr: self._llm("notyet", pr), written))
            self._save("notyet.json", fresh_res)
        # the critic (advisory) and the two-source verifier
        adv: dict[str, Any] = {}
        if (advisory.critic_on() or advisory.verify2_on()) and plan.fits("critic"):
            self.progress("A second reading for points to check", 99)
            if advisory.critic_on():
                adv["critic"] = self._guarded("critic", lambda: advisory.critic(
                    lambda pr: self._llm("critic", pr), task, written))
            if advisory.verify2_on():
                adv["verify2"] = self._guarded("verify2", lambda: advisory.verify2(
                    self, written, _words, relevant_passages, count_text))
            self._save("advisory.json", adv)
        # the marks, all at once (each check found its statements in the text as written)
        setup_md, setup_marks = "", 0
        if setup_res is not None:
            n0 = body.count("[Setup check:")
            body, setup_md = setup_profile.annotate(body, setup_res)
            setup_marks = body.count("[Setup check:") - n0
        elif self.setup_path:
            setup_md = ("## Setup check\n\nThe setup check was not run: the time budget was used up."
                        if "setup" in plan.skipped else "## Setup check\n\nThe setup check did not complete (see the log).")
        items: list[tuple[str, str]] = []
        if ver_res is not None:
            items += checks.version_marks(written, ver_res, versions)
        if ar_res is not None:
            items += checks.arith_marks(ar_res)
        if co_res is not None:
            items += checks.consistency_marks(co_res)
        if checks.fix_on("inline") and adv.get("critic"):
            items += checks.critic_marks(adv["critic"], advisory.CHECK_MAX)
        body, found = checks.insert_marks(body, items)
        res["marks"] = {"placed": sum(found), "not_found": len(found) - sum(found), "setup": setup_marks}
        if fresh_res is not None:
            body, fresh_md = fresh_check.annotate(body, fresh_res)
        advise_md = advisory.check_these(adv.get("critic"), adv.get("verify2")) if adv else ""
        if advise_md and checks.fix_on("inline"):
            advise_md = advise_md.replace("the report above is unchanged", "each is also marked [Check: ...] where it "
                                          "stands above; the report text is unchanged")
        ver_md = checks.version_section(ver_res, versions) if checks.fix_on("version") and (
            ver_res is not None or "version" not in plan.skipped) else ""
        ar_md = checks.arith_section(ar_res) if ar_res is not None else ""
        co_md = checks.consistency_section(co_res) if co_res is not None else ""
        if plan.skipped or plan.notes:
            note = "; ".join(plan.notes + ([f"not run within the time budget: {', '.join(dict.fromkeys(plan.skipped))}"]
                                           if plan.skipped else []))
            check_md = (check_md + "\n\n" if check_md else "") + f"_Time budget: {note}._"
        report = "\n\n".join(x for x in (body, setup_md, ver_md, ar_md, co_md, fresh_md, advise_md, check_md) if x)
        cited = cited_indices(report)
        stats = {
            "report_seconds": round(time.time() - t0, 1), "report_calls": len(self.calls),
            "sections": len(secs), "sources_cited": len(cited),
            "sources_cited_read": sum(1 for i in cited if (store.source(i) and store.source(i).fetches)),
            # items 5 + 6 (10-28): cited sources with page text (agent fetch or the reader), the reader, the claims
            "sources_cited_with_text": sum(1 for i in cited if (store.source(i) and store.source(i).page_text)),
            "items": [x for x in checks.ITEMS if checks.fix_on(x)],
            "reading": getattr(self, "read_stats", None),
            "claim_store": claim_store.stats(store.all_sources()) if checks.fix_on("claims") else None,
            "claims": len(claims), "claims_total": all_claims,
            "verdicts": {v: sum(1 for c in claims if c["verdict"] == v) for v in
                         ("supported", "partial", "unsupported", "no_answer", "no_text", "no_source")},
            "fixes": checks.fixes_on(), "skipped": plan.skipped, "plan_notes": plan.notes,
            "effort_drops": effort_drop_stats(store),
            "left_s": None if plan.deadline is None else round(plan.left(), 1),
            "checks": {"cite": cite_res, "marks": res.get("marks"),
                       "version_flagged": len(checks.version_flagged(ver_res)) if ver_res else None,
                       "arith_wrong": sum(1 for c in (ar_res or {}).get("calcs") or [] if c.get("status") == "wrong")
                       if ar_res else None,
                       "contradictions": len((co_res or {}).get("contradictions") or []) if co_res else None},
            **store.stats(),
        }
        return {"markdown": report, "outline": ol, "claims": claims, "stats": stats, "calls": self.calls, "cited": cited}

    def _pinned_repos(self) -> tuple[list, dict]:
        """The code tool's clones at the user's version (Fix 1): opened during the research or opened now."""
        ct = getattr(self.store, "code_tool", None)
        if ct is None:
            return [], dict(getattr(self.store, "pins", None) or {})
        try:
            return ct.pinned_repos(), ct.pin_labels()
        except Exception:  # noqa: BLE001
            logger.exception("deep report: the pinned clones could not be opened")
            return [], {}


def effort_drop_stats(store: EvidenceStore) -> dict[str, Any]:
    """Effort drops of the retry ladder during this research (deep.llm records them; Karl 10-27)."""
    from .llm import effort_drops

    d = effort_drops(store.t0)
    by: dict[str, int] = {}
    for x in d:
        by[x["what"]] = by.get(x["what"], 0) + 1
    return {"count": len(d), "by_call": by, "list": [{k: v for k, v in x.items() if k != "t"} for x in d[:40]]}


def write_files(out_dir: Path | None, result: dict[str, Any], store: EvidenceStore, lead_answer: str) -> None:
    if out_dir is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    src_lines = []
    for i in result.get("cited", []):
        s = store.source(i)
        if s is not None:
            src_lines.append(f"[{i}] {s.title} — {s.url}")
    (out_dir / "report.md").write_text(result["markdown"] + "\n\n## Sources\n\n" + "\n\n".join(src_lines) + "\n",
                                       encoding="utf-8")
    (out_dir / "lead_answer.md").write_text(lead_answer or "", encoding="utf-8")
    (out_dir / "outline.json").write_text(json.dumps(result.get("outline"), indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "verification.json").write_text(json.dumps(result.get("claims"), indent=1, ensure_ascii=False),
                                               encoding="utf-8")
    (out_dir / "stats.json").write_text(json.dumps({**result.get("stats", {}), "calls": result.get("calls")},
                                                   indent=1, ensure_ascii=False), encoding="utf-8")
    subs = "\n\n---\n\n".join(f"## {s['topic']}\n({s['status']}, {s['seconds']} s, {s['calls']} model calls)\n\n{s['text']}"
                              for s in store.subagents)
    (out_dir / "subagents.md").write_text(subs, encoding="utf-8")
