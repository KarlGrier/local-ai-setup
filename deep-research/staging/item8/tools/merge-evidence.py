#!/usr/bin/env python3
"""merge-evidence.py - item 8 (merged short runs): 2-3 saved deep runs of ONE question merged into one run folder,
so one report can be written from the merged evidence (tools/fix-replay.py write --run OUT, unchanged).

  merge-evidence.py --out OUT RUN_DIR RUN_DIR [RUN_DIR ...] [--evidence RUN_DIR=DIR] [--label RUN_DIR=NAME]
                    [--question FILE] [--index-order interleave|runs] [--subagent-order interleave|runs]
                    [--lead-share-tokens N] [--replace]

  RUN_DIR      a finished deep run: RUN_DIR/marks.json (the question), RUN_DIR/deep/evidence.jsonl,
               RUN_DIR/deep/lead_answer.md, RUN_DIR/deep/code-tool.jsonl (optional). The order given is the merge order.
  --evidence   that run's evidence.jsonl from DIR instead (e.g. results/bench2/fixes/readpass/o01: p4s6's evidence
               with tools/read-pass.py's pages), like fix-replay.py write --evidence.
  --label      the run's name in the merged texts and the map (default: screen-deep-p4s6/o01 -> p4s6).
  --question   the question when the runs' marks.json differ or are missing (otherwise they must be identical).
  --index-order  interleave (default): new indices go round the runs (run 1's first source, run 2's first, ...,
               run 1's second, ...); the report writer lists sources by index and cuts the list where its budget ends
               (the outline's digest: ~45K tokens for 600-900 read pages), so the cut hits every run alike;
               runs: run 1's sources first, then run 2's new ones, ...
  --subagent-order  interleave (default): run 1's first subagent, run 2's first, ... - the report's section prompts
               keep only ~30 subagents' findings (12K tokens, 400 per subagent), so a cut hits every run alike;
               runs: run 1's subagents, then run 2's, ...
  --lead-share-tokens N  cut each run's lead answer to N/runs tokens (the served model's tokenizer; default 0 = keep
               them whole). The outline prompt reads at most 10,000 tokens of the lead answer (report.py), so with
               whole answers it sees run 1's and part of run 2's.
  --replace    OUT may hold an earlier merge (it has merge-summary.json): it is deleted first.

OUT (a run folder):
  marks.json               the question, merged_from
  deep/evidence.jsonl      the runs' records in run order, renumbered, each tagged "run"; one start record; the
                           subagent records last (in --subagent-order)
  deep/lead_answer.md      each run's lead answer as its own block, labelled by run, renumbered
  deep/subagents.md        every run's subagent reports (as report.py's write_files lays them out)
  deep/code-tool.jsonl     the runs' code-tool logs, tagged "run" (fix-replay's version check opens their clones)
  merge-map.tsv            run, old_idx, new_idx, url (one row per source of each run)
  merge-summary.json       counts, references left alone or neutralised, lead-answer sizes, warnings

Sources: one index per source. Same URL (normalised: scheme and host lower case, default port and trailing slash
dropped, a fragment that only points inside a page dropped - kept for file:// (#part=N picks a piece of a file) and
for #!... / #/... routes) = one index, within a run too (a run's collector gives a URL a new index per search). New
indices 1..N in order of first appearance (--index-order; within a run by old index). seed.load does the per-source merge when it
reads the records: the longest page text, every snippet, fetch (extraction) and date, via and primaries; this tool
also drops claims whose quote the source already has (case and spacing ignored), duplicate primary links and
"unreadable" records of a source that some run read.

References: every [N] / [N, M] / [N-M] / 【N】 (evidence.CITE_RE, the report writer's own pattern) in subagent texts
and topics, lead answers and notes (compaction notes, lead_answer notes) whose numbers are all sources of that run is
renumbered (a range stays a range where the new numbers are consecutive, else a list; repeats after merging dropped).
Brackets inside `code` / ```fences``` are left as they are. Any other match (not a citation of that run: [0, 2],
[61317], an index the agent made up) is left as it is - unless one of its numbers is an index of the merged store,
then it is written "[ N]" so it cannot cite another run's page. Page text, snippets, extractions, claim quotes and
fetch focuses are never changed (they are page content or the agents' requests).

Deterministic: the same inputs in the same order give byte-identical output. No model, no network.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

WS = Path("/home/USER/ai/deep-research")
TOKENIZER_DIR = WS / "deep" / "tokenizer"
OUTLINE_LEAD_CAP = 10_000          # report.py outline(): min(10000, budget // 6) tokens of the lead answer
SECTION_FINDINGS = 12_000          # report.py section(): self._findings(12000), at least 400 tokens per subagent
SECTION_PER_SUB_MIN = 400

# evidence.CITE_RE with the brackets as groups (same matches)
CITE_RE = re.compile(r"([\[【])(\d+(?:\s*[,–-]\s*\d+)*)([\]】])")
RANGE_RE = re.compile(r"^(\d+)\s*([–-])\s*(\d+)$")
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
SOURCE_TYPES = ("search", "seed_search", "fetch", "seed_fetch", "read", "seed_read", "claims", "unreadable")


# -- URLs -------------------------------------------------------------------------------------------------------------
def url_key(url: str) -> str:
    """The URL as one source: scheme and host lower case, default port, trailing slash and in-page fragments out."""
    u = (url or "").strip()
    if not u:
        return ""
    try:
        sp = urlsplit(u)
    except ValueError:
        return u
    scheme = sp.scheme.lower()
    netloc = sp.netloc
    user, _, hostport = netloc.rpartition("@")
    hostport = hostport.lower()
    if (scheme == "http" and hostport.endswith(":80")) or (scheme == "https" and hostport.endswith(":443")):
        hostport = hostport.rsplit(":", 1)[0]
    netloc = (user + "@" if user else "") + hostport
    path = sp.path.rstrip("/") if sp.path.endswith("/") else sp.path
    frag = sp.fragment if (scheme == "file" or sp.fragment.startswith(("!", "/"))) else ""
    return urlunsplit((scheme, netloc, path, sp.query, frag))


# -- references -------------------------------------------------------------------------------------------------------
def code_spans(text: str) -> list[tuple[int, int]]:
    spans = [m.span() for m in FENCE_RE.finditer(text)]
    fences = list(spans)
    for m in INLINE_CODE_RE.finditer(text):
        if not any(a <= m.start() < b for a, b in fences):
            spans.append(m.span())
    return sorted(spans)


def parse_parts(inner: str) -> list[tuple]:
    """The parts of a citation's inside, as evidence.cited_indices reads them."""
    parts: list[tuple] = []
    for p in re.split(r"\s*,\s*", inner):
        m = RANGE_RE.match(p)
        if m:
            parts.append(("range", int(m.group(1)), int(m.group(3)), m.group(2)))
        elif p.strip().isdigit():
            parts.append(("num", int(p)))
        else:
            parts.append(("other", p))
    return parts


def part_numbers(p: tuple) -> list[int]:
    if p[0] == "num":
        return [p[1]]
    if p[0] == "range":
        a, b = p[1], p[2]
        return list(range(a, b + 1)) if 0 <= b - a <= 20 else [a, b]
    return []


def render(parts: list[tuple], mp: dict[int, int], inner: str) -> str:
    """The citation with new numbers: first-appearance order kept, repeats dropped, ranges kept where consecutive."""
    m = re.search(r"\s*,\s*", inner)
    sep = m.group(0) if m else ", "
    seen: set[int] = set()
    out: list[str] = []
    for p in parts:
        new = [n for n in dict.fromkeys(mp[o] for o in part_numbers(p)) if n not in seen]
        seen.update(new)
        if not new:
            continue
        if p[0] == "range" and 0 <= p[2] - p[1] <= 20 and len(new) >= 2 and \
                new == list(range(new[0], new[0] + len(new))):
            out.append(f"{new[0]}{p[3]}{new[-1]}")
        else:
            out.extend(str(n) for n in new)
    return sep.join(out)


def renumber_text(text: str, mp: dict[int, int], n_merged: int, st: Counter, examples: list | None = None,
                  where: str = "") -> str:
    """Every citation of this run's sources renumbered (see the module doc)."""
    if not text or ("[" not in text and "【" not in text):
        return text
    spans = code_spans(text)
    out: list[str] = []
    pos = si = 0
    for m in CITE_RE.finditer(text):
        s = m.start()
        while si < len(spans) and spans[si][1] <= s:
            si += 1
        if si < len(spans) and spans[si][0] <= s < spans[si][1]:
            st["refs_in_code_left"] += 1
            continue
        ob, inner, cb = m.groups()
        parts = parse_parts(inner)
        nums = [n for p in parts for n in part_numbers(p)]
        if nums and all(p[0] != "other" for p in parts) and all(n in mp for n in nums):
            repl = ob + render(parts, mp, inner) + cb
            st["refs_renumbered"] += 1
        elif any(1 <= n <= n_merged for n in nums):
            repl = ob + " " + inner + cb
            st["refs_neutralised"] += 1
            ex = {"where": where, "ref": m.group(0), "context": text[max(0, s - 60):m.end() + 20]}
            if examples is not None and len(examples) < 40 and ex not in examples:
                examples.append(ex)
        else:
            st["refs_left"] += 1
            continue
        out.append(text[pos:s])
        out.append(repl)
        pos = m.end()
    if not out:
        return text
    out.append(text[pos:])
    return "".join(out)


def qnorm(q: str) -> str:
    return " ".join((q or "").split()).casefold()


# -- runs -------------------------------------------------------------------------------------------------------------
class Run:
    def __init__(self, n: int, run_dir: Path, evidence: Path, label: str):
        self.n, self.dir, self.evidence, self.label = n, run_dir, evidence, label
        self.urls: dict[int, str] = {}          # old idx -> first URL seen
        self.titles: dict[int, str] = {}
        self.page_len: dict[int, int] = {}      # old idx -> longest page text
        self.unreadable: set[int] = set()
        self.conflicts: dict[int, list[str]] = {}
        self.types: Counter = Counter()
        self.question = ""
        self.marks: dict = {}

    def scan(self) -> None:
        """Pass 1: every source index of the run, its first URL and the longest page text."""
        mk = self.dir / "marks.json"
        if mk.exists():
            self.marks = json.loads(mk.read_text(encoding="utf-8"))
            self.question = str(self.marks.get("question") or "").strip()
        keys: dict[int, set[str]] = defaultdict(set)
        with open(self.evidence, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    self.types["(bad line)"] += 1
                    continue
                t = r.get("type")
                self.types[t] += 1
                if t in ("search", "seed_search"):
                    rows = [(x.get("idx"), x.get("url"), x.get("title")) for x in r.get("results") or []
                            if isinstance(x, dict)]
                elif t in SOURCE_TYPES:
                    rows = [(r.get("idx"), r.get("url"), r.get("title"))]
                elif t == "primary":              # seed.load makes a source of `via` even without a URL
                    rows = [(r.get("via"), "", ""), (r.get("idx"), "", "")]
                else:
                    continue
                for i, u, title in rows:
                    if i is None:
                        continue
                    i = int(i)
                    if u:
                        self.urls.setdefault(i, u)
                        keys[i].add(url_key(u))
                    else:
                        self.urls.setdefault(i, "")
                    if title and not self.titles.get(i):
                        self.titles[i] = title
                if t in ("fetch", "seed_fetch", "read", "seed_read") and r.get("idx") is not None and \
                        r.get("page_text"):
                    i = int(r["idx"])
                    self.page_len[i] = max(self.page_len.get(i, 0), len(r["page_text"]))
                if t == "unreadable" and r.get("idx") is not None:
                    self.unreadable.add(int(r["idx"]))
        for i, ks in keys.items():
            if len(ks) > 1:
                self.conflicts[i] = sorted(ks)
        for i, u in self.urls.items():           # an index first seen without a URL: take any later URL
            if not u and keys.get(i):
                self.urls[i] = sorted(keys[i])[0]


def default_label(d: Path) -> str:
    if re.fullmatch(r"o\d+", d.name):
        return d.parent.name.removeprefix("screen-deep-")
    return d.name


def parse_pairs(items: list[str], what: str) -> dict[Path, str]:
    out: dict[Path, str] = {}
    for it in items or []:
        a, sep, b = it.partition("=")
        if not sep or not a or not b:
            raise SystemExit(f"--{what} wants RUN_DIR=VALUE, got {it!r}")
        out[Path(a).resolve()] = b
    return out


# -- lead answers -----------------------------------------------------------------------------------------------------
def token_counter():
    """The served model's tokenizer (deep/tokens.py), or None."""
    try:
        os.environ.setdefault("LDR_DEEP_TOKENIZER_DIR", str(TOKENIZER_DIR))
        from local_deep_research.deep import tokens
        if tokens._load() is None:
            return None
        return tokens
    except Exception:  # noqa: BLE001
        return None


def cut_lead(text: str, max_tokens: int, tokens) -> str:
    if tokens is None or tokens.count_text(text) <= max_tokens:
        return text
    cut = tokens.truncate_to_tokens(text, max_tokens - 40)
    p = cut.rfind("\n\n")
    if p > len(cut) * 0.7:
        cut = cut[:p]
    return cut.rstrip() + "\n\n[... the rest of this run's lead answer is cut so every run's answer fits]"


# -- main -------------------------------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--evidence", action="append", default=[])
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--question")
    ap.add_argument("--index-order", choices=("interleave", "runs"), default="interleave")
    ap.add_argument("--subagent-order", choices=("interleave", "runs"), default="interleave")
    ap.add_argument("--lead-share-tokens", type=int, default=0)
    ap.add_argument("--replace", action="store_true")
    a = ap.parse_args()

    if len(a.runs) < 2:
        print("give at least two runs")
        return 2
    evid, labels = parse_pairs(a.evidence, "evidence"), parse_pairs(a.label, "label")
    runs: list[Run] = []
    seen_labels: set[str] = set()
    for n, rd in enumerate(a.runs, 1):
        d = Path(rd).resolve()
        ev = Path(evid[d]).resolve() / "evidence.jsonl" if d in evid else d / "deep" / "evidence.jsonl"
        if not ev.exists():
            print(f"{ev} missing")
            return 2
        lab = labels.get(d) or default_label(d)
        base, k = lab, 2
        while lab in seen_labels:
            lab, k = f"{base}#{k}", k + 1
        seen_labels.add(lab)
        if re.search(r"[\t\n]", lab):
            print(f"label {lab!r}: no tabs or newlines")
            return 2
        runs.append(Run(n, d, ev, lab))
    if len({r.dir for r in runs}) < len(runs):
        print("the same run twice")
        return 2

    out = Path(a.out).resolve()
    if any(out == r.dir or out in r.dir.parents or r.dir in out.parents for r in runs):
        print("OUT must be outside the runs")
        return 2
    if out.exists() and any(out.iterdir()):
        if a.replace and (out / "merge-summary.json").exists():
            shutil.rmtree(out)
        else:
            print(f"{out} is not empty (--replace deletes an earlier merge)")
            return 2

    # pass 1: sources of every run
    for r in runs:
        r.scan()
    if a.question:
        question = Path(a.question).read_text(encoding="utf-8").strip()
    else:
        qs = {r.question for r in runs}
        if len(qs) != 1 or not next(iter(qs)):
            print("the runs' questions differ or are missing - give --question FILE")
            return 2
        question = next(iter(qs))
    warnings: list[str] = []
    if a.question and any(r.question and r.question != question for r in runs):
        warnings.append("--question differs from a run's marks.json question")

    # one index per source, in order of first appearance (--index-order)
    key_new: dict[str, int] = {}
    maps: dict[str, dict[int, int]] = {r.label: {} for r in runs}
    new_from: dict[int, list[tuple[str, int]]] = defaultdict(list)
    ranked = [sorted(r.urls) for r in runs]
    if a.index_order == "interleave":
        seq = [(r, lst[k]) for k in range(max(map(len, ranked))) for r, lst in zip(runs, ranked) if k < len(lst)]
    else:
        seq = [(r, i) for r, lst in zip(runs, ranked) for i in lst]
    for r, i in seq:
        k = url_key(r.urls[i]) or f"(no url) {r.label}#{i}"
        if k not in key_new:
            key_new[k] = len(key_new) + 1
        maps[r.label][i] = key_new[k]
        new_from[key_new[k]].append((r.label, i))
    n_merged = len(key_new)
    has_page = {maps[r.label][i] for r in runs for i in r.page_len}

    st: Counter = Counter()
    ref_examples: list[dict] = []
    (out / "deep").mkdir(parents=True, exist_ok=True)
    tmp = out / "deep" / "evidence.jsonl.tmp"
    claims_kept: dict[int, set[str]] = defaultdict(set)
    prim_kept: set[tuple[int, int]] = set()
    unread_kept: set[int] = set()
    subs: list[list[dict]] = []
    notes_by_run: Counter = Counter()

    def dump(f, rec: dict) -> None:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # pass 2: the records, renumbered
    with open(tmp, "w", encoding="utf-8") as f:
        dump(f, {"t": 0.0, "agent": "merge", "type": "start", "query": question,
                 "merged_from": [r.label for r in runs]})
        dump(f, {"t": 0.0, "agent": "merge", "type": "note", "kind": "merge", "runs": [
            {"label": r.label, "run": str(r.dir), "evidence": str(r.evidence)} for r in runs],
            "sources": n_merged, "index_order": a.index_order, "subagent_order": a.subagent_order})
        for r in runs:
            mp = maps[r.label]
            rsubs: list[dict] = []
            subs.append(rsubs)

            def nm(v):
                return None if v is None else mp[int(v)]     # pass 1 gave every index of the run a new one

            with open(r.evidence, encoding="utf-8") as src:
                for line in src:
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    t = rec.get("type")
                    if t == "start":
                        continue
                    if t in ("search", "seed_search"):
                        rec["results"] = [{**x, "idx": nm(x.get("idx"))} if isinstance(x, dict) else x
                                          for x in rec.get("results") or []]
                    elif t in ("fetch", "seed_fetch"):
                        rec["idx"] = nm(rec.get("idx"))
                    elif t in ("read", "seed_read"):
                        rec["idx"] = nm(rec.get("idx"))
                        if rec.get("via") is not None:
                            rec["via"] = nm(rec["via"])
                    elif t == "claims":
                        if rec.get("idx") is None:
                            continue
                        rec["idx"] = nm(rec["idx"])
                        kept = claims_kept[rec["idx"]]
                        new = []
                        for c in rec.get("claims") or []:
                            k = qnorm(c.get("quote", ""))
                            if k in kept:
                                st["claims_dropped_duplicate"] += 1
                                continue
                            kept.add(k)
                            new.append(c)
                        st["claims_kept"] += len(new)
                        if not new:
                            continue
                        rec["claims"] = new
                    elif t == "primary":
                        if rec.get("idx") is None or rec.get("via") is None:
                            continue
                        rec["via"], rec["idx"] = nm(rec["via"]), nm(rec["idx"])
                        pair = (rec["via"], rec["idx"])
                        if pair in prim_kept or pair[0] == pair[1]:
                            st["primary_dropped_duplicate"] += 1
                            continue
                        prim_kept.add(pair)
                    elif t == "unreadable":
                        if rec.get("idx") is None:
                            continue
                        rec["idx"] = nm(rec["idx"])
                        if rec["idx"] in has_page or rec["idx"] in unread_kept:
                            st["unreadable_dropped_read_elsewhere" if rec["idx"] in has_page
                               else "unreadable_dropped_duplicate"] += 1
                            continue
                        unread_kept.add(rec["idx"])
                    elif t in ("subagent", "seed_subagent"):
                        for fld in ("text", "topic"):
                            if rec.get(fld):
                                rec[fld] = renumber_text(rec[fld], mp, n_merged, st, ref_examples,
                                                         f"{r.label} subagent {fld}")
                        rsubs.append({**rec, "run": r.label})
                        continue
                    elif t == "note":
                        for fld in ("text", "notes_text"):
                            if isinstance(rec.get(fld), str):
                                rec[fld] = renumber_text(rec[fld], mp, n_merged, st, ref_examples,
                                                         f"{r.label} note {rec.get('kind')}")
                        notes_by_run[r.label] += 1
                    else:
                        st[f"other_record_type:{t}"] += 1
                    dump(f, {**rec, "run": r.label})
        # the subagent reports last, in the chosen order
        if a.subagent_order == "interleave":
            order = [s[k] for k in range(max(map(len, subs), default=0)) for s in subs if k < len(s)]
        else:
            order = [x for s in subs for x in s]
        for rec in order:
            dump(f, rec)
    os.replace(tmp, out / "deep" / "evidence.jsonl")

    # lead answers: one block per run
    tok = token_counter()
    lead_info = []
    blocks = []
    k = len(runs)
    for r in runs:
        p = r.dir / "deep" / "lead_answer.md"
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        if not text.strip():                         # the last lead_answer note, if the file is missing
            with open(r.evidence, encoding="utf-8") as src:
                for line in src:
                    if '"lead_answer"' in line:
                        try:
                            rec = json.loads(line)
                        except ValueError:
                            continue
                        if rec.get("type") == "note" and rec.get("kind") == "lead_answer" and rec.get("text"):
                            text = rec["text"]
        if not text.strip():
            warnings.append(f"{r.label}: no lead answer")
            lead_info.append({"run": r.label, "chars": 0, "tokens": 0})
            continue
        text = renumber_text(text, maps[r.label], n_merged, st, ref_examples, f"{r.label} lead answer").strip()
        full_tokens = tok.count_text(text) if tok else len(text) // 3 + 1
        if a.lead_share_tokens > 0:
            if tok is None:
                print("--lead-share-tokens needs the model's tokenizer (deep/tokenizer)")
                return 2
            text = cut_lead(text, a.lead_share_tokens // k, tok)
        n_tok = tok.count_text(text) if tok else len(text) // 3 + 1
        lead_info.append({"run": r.label, "chars": len(text), "tokens": n_tok, "tokens_whole": full_tokens})
        blocks.append(f"===== Lead answer of run {r.n} of {k} ({r.label}) =====\n\n{text}\n")
    head = (f"(Merged research: {k} separate runs on the same question, each with its own lead answer below. The "
            f"source numbers [N] are the merged evidence's.)\n\n")
    lead_md = head + "\n".join(blocks)
    (out / "deep" / "lead_answer.md").write_text(lead_md, encoding="utf-8")
    lead_tokens = tok.count_text(lead_md) if tok else len(lead_md) // 3 + 1

    # subagents.md, as report.write_files lays it out
    (out / "deep" / "subagents.md").write_text("\n\n---\n\n".join(
        f"## {s.get('topic') or ''}\n(run {s['run']}; {s.get('status') or ''}, {s.get('seconds') or 0} s, "
        f"{s.get('calls') or 0} model calls)\n\n{s.get('text') or ''}" for s in order), encoding="utf-8")

    # the code-tool logs (fix-replay's version check opens the clones the research made)
    ct_lines = []
    for r in runs:
        p = r.dir / "deep" / "code-tool.jsonl"
        if p.exists():
            with open(p, encoding="utf-8", errors="replace") as f:    # not splitlines(): U+2028 inside strings
                for line in f:
                    line = line.rstrip("\n")
                    if not line.strip():
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        d = None
                    ct_lines.append(json.dumps({**d, "run": r.label}, ensure_ascii=False) if isinstance(d, dict)
                                    else line)
    if ct_lines:
        (out / "deep" / "code-tool.jsonl").write_text("\n".join(ct_lines) + "\n", encoding="utf-8")

    m0 = runs[0].marks
    marks = {"question": question, "mode": m0.get("mode"), "profile": m0.get("profile"), "final_status": "merged",
             "merged_from": [{"label": r.label, "run": str(r.dir), "evidence": str(r.evidence),
                              "research_id": r.marks.get("research_id"), "final_status": r.marks.get("final_status")}
                             for r in runs]}
    (out / "marks.json").write_text(json.dumps(marks, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    # the map: run, old idx -> new idx
    with open(out / "merge-map.tsv", "w", encoding="utf-8") as f:
        f.write("run\told_idx\tnew_idx\turl\n")
        for r in runs:
            for i in sorted(r.urls):
                u = re.sub(r"[\t\n]", " ", r.urls[i])
                f.write(f"{r.label}\t{i}\t{maps[r.label][i]}\t{u}\n")

    # summary
    shared = Counter(len({lab for lab, _ in v}) for v in new_from.values())
    n_subs = sum(map(len, subs))
    per_sub = max(SECTION_PER_SUB_MIN, SECTION_FINDINGS // max(1, n_subs))
    for r in runs:
        if r.conflicts:
            warnings.append(f"{r.label}: {len(r.conflicts)} index(es) with URLs that normalise differently "
                            f"(first URL kept), e.g. {next(iter(r.conflicts.items()))}")
    if lead_tokens > OUTLINE_LEAD_CAP:
        warnings.append(f"the merged lead answer is {lead_tokens} tokens; the outline reads only the first "
                        f"{OUTLINE_LEAD_CAP} (see --lead-share-tokens)")
    if per_sub * n_subs > SECTION_FINDINGS:
        warnings.append(f"{n_subs} subagent reports: each section prompt keeps ~{SECTION_FINDINGS // per_sub} of them "
                        f"({per_sub} tokens each; order {a.subagent_order})")
    summary = {
        "question": question[:300],
        "runs": [{"n": r.n, "label": r.label, "run": str(r.dir), "evidence": str(r.evidence),
                  "sources": len(r.urls), "distinct_urls": len({url_key(u) or f'{r.label}#{i}' for i, u in
                                                                r.urls.items()}),
                  "pages_with_text": len(r.page_len), "unreadable": len(r.unreadable),
                  "records": dict(sorted(r.types.items(), key=lambda x: str(x[0]))), "notes": notes_by_run[r.label],
                  "subagents": len(subs[r.n - 1]), "url_conflicts": len(r.conflicts)} for r in runs],
        "merged": {"sources": n_merged, "pages_with_text": len(has_page),
                   "sources_in_runs": {str(k): v for k, v in sorted(shared.items())},
                   "subagents": n_subs, "index_order": a.index_order, "subagent_order": a.subagent_order,
                   "unreadable_kept": len(unread_kept), "primary_links": len(prim_kept)},
        "counts": dict(sorted(st.items())),
        "lead_answer": {"runs": lead_info, "tokens": lead_tokens, "outline_reads": OUTLINE_LEAD_CAP,
                        "share_tokens": a.lead_share_tokens, "tokenizer": bool(tok)},
        "neutralised_examples": ref_examples,
        "warnings": warnings,
    }
    (out / "merge-summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(f"{out}: {k} runs ({', '.join(r.label for r in runs)}) -> {n_merged} sources "
          f"(per run {', '.join(str(len(r.urls)) for r in runs)}), {len(has_page)} with page text, {n_subs} subagent "
          f"reports; refs renumbered {st['refs_renumbered']}, neutralised {st['refs_neutralised']}, left "
          f"{st['refs_left']}, in code {st['refs_in_code_left']}; claims kept {st['claims_kept']} "
          f"(duplicates {st['claims_dropped_duplicate']}); lead answer {lead_tokens} tokens")
    for w in warnings:
        print("  warning:", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
