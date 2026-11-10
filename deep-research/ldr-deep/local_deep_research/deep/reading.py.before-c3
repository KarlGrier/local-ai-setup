"""Read every cited source; follow cited secondary pages to their primary sources (phase 4 item 6, Karl 10-27).

The agents cite search results whose page nobody opened: ~85 % of cited sources in the phase 3 screen runs, 29 % in the
10-27 combined rerun. With LDR_DEEP_FIX including "read":
  * a background reader fetches each cited-but-unread page as soon as a subagent's findings (or the lead's answer) cite
    it, and keeps the page text in the evidence store - a fetch, no model call;
  * a page that is not itself a primary source leads to up to two primary sources (regulator, paper, repository,
    standard, official documentation) named in its text, ranked by how close they sit to words of the sentences that
    cite the page; they get their own [N];
  * the report writer cites only sources that were read (report.py) and Fix 4's citation guard removes citations of
    unread ones, so every [N] in the report stands for a page that was read.

Pages are fetched one at a time (ContentFetcher's process-wide lock) in the reader's own thread, so reading overlaps the
model calls. The reader stops at the run's deadline.
"""

from __future__ import annotations

import os
import queue
import re
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

from loguru import logger

from .evidence import cited_indices

READ_MAX = int(os.environ.get("LDR_DEEP_READ_MAX", "400"))                  # pages the reader fetches per run
PRIMARY_MAX = int(os.environ.get("LDR_DEEP_READ_PRIMARY_MAX", "40"))        # primary sources it adds per run
PRIMARY_PER_PAGE = 2

# hosts whose pages are primary sources themselves (a suffix match on the host name)
PRIMARY_HOSTS = (
    "arxiv.org", "doi.org", "dl.acm.org", "ieeexplore.ieee.org", "openreview.net", "aclanthology.org",
    "proceedings.mlr.press", "papers.nips.cc", "proceedings.neurips.cc", "nature.com", "science.org", "springer.com",
    "sciencedirect.com", "semanticscholar.org", "github.com", "gitlab.com", "huggingface.co", "pypi.org",
    "eur-lex.europa.eu", "europa.eu", "legislation.gov.uk", "federalregister.gov", "congress.gov", "iso.org",
    "cencenelec.eu", "etsi.org", "ietf.org", "rfc-editor.org", "w3.org", "nist.gov", "kernel.org", "python.org",
    "pytorch.org", "nvidia.com", "amd.com", "intel.com", "pcisig.com", "jedec.org", "ncbi.nlm.nih.gov", "who.int",
)
PRIMARY_SUFFIXES = (".gov", ".gov.uk", ".gov.au", ".gc.ca", ".gouv.fr", ".bund.de", ".admin.ch", ".go.jp", ".int")
# of the vendors' sites only the documentation and developer pages count (not their news and marketing)
VENDOR_DOC_HOSTS = ("nvidia.com", "amd.com", "intel.com")

URL_RE = re.compile(r"https?://[^\s<>\]\[)(\"'`|]+")
ARXIV_RE = re.compile(r"(?i)\barxiv[:\s]*(?:abs/)?(\d{4}\.\d{4,5})(?:v\d+)?")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>,;]+[^\s\"<>,;.)\]])")
EU_ACT_RE = re.compile(r"\b(Regulation|Directive|Decision)\s*\((EU|EC|EEC|Euratom)\)\s*(No\.?\s*)?(\d{1,4})/(\d{1,4})")
GITHUB_RE = re.compile(r"(?<![\w/.])github\.com/([\w.-]+)/([\w.-]+)")
ELI_RE = re.compile(r"eur-lex\.europa\.eu/eli/(reg|dir|dec)/(\d{4})/(\d{1,4})")


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_primary(url: str) -> bool:
    h = host_of(url)
    if not h:
        return False
    if h.startswith(("docs.", "developer.", "developers.")):
        return True
    for p in PRIMARY_HOSTS:
        if h == p or h.endswith("." + p):
            if p in VENDOR_DOC_HOSTS:
                return h.startswith(("docs.", "developer.")) or "/docs" in url
            return True
    return h.endswith(PRIMARY_SUFFIXES)


def _eu_celex(kind: str, no: str | None, a: str, b: str) -> str | None:
    """'Regulation (EU) 2024/1689' (year/number since 2015) or 'Regulation (EU) No 1025/2012' (number/year) -> CELEX."""
    letter = {"regulation": "R", "directive": "L", "decision": "D"}[kind.lower()]
    year, num = (b, a) if no else (a, b)
    if len(year) == 2:                                       # 'Directive 95/46/EC' style years
        year = ("19" if int(year) > 50 else "20") + year
    if not (len(year) == 4 and 1950 <= int(year) <= 2100):
        return None
    return f"3{year}{letter}{int(num):04d}"


def candidate_links(text: str, base_url: str) -> list[tuple[int, str]]:
    """Primary-source links named in a page's text, with their position: written-out URLs on primary hosts, arXiv ids,
    DOIs, EU acts (as EUR-Lex CELEX links) and GitHub repositories."""
    base = (base_url or "").rstrip("/")
    out: dict[str, int] = {}

    def add(pos: int, url: str) -> None:
        url = url.rstrip(".,;:")
        eli = ELI_RE.search(url)                     # one act, one link: EUR-Lex's ELI form -> the CELEX form
        if eli:
            url = (f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:3{eli.group(2)}"
                   f"{dict(reg='R', dir='L', dec='D')[eli.group(1)]}{int(eli.group(3)):04d}")
        if url.rstrip("/") != base and url not in out:
            out[url] = pos

    for m in URL_RE.finditer(text or ""):
        if is_primary(m.group(0)):
            add(m.start(), m.group(0))
    for m in ARXIV_RE.finditer(text or ""):
        add(m.start(), f"https://arxiv.org/abs/{m.group(1)}")
    for m in DOI_RE.finditer(text or ""):
        add(m.start(), f"https://doi.org/{m.group(1)}")
    for m in EU_ACT_RE.finditer(text or ""):
        celex = _eu_celex(m.group(1), m.group(3), m.group(4), m.group(5))
        if celex:
            add(m.start(), f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}")
    for m in GITHUB_RE.finditer(text or ""):
        repo = m.group(2)
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        add(m.start(), f"https://github.com/{m.group(1)}/{repo}")
    return sorted(((p, u) for u, p in out.items()), key=lambda x: x[0])


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", (s or "").lower())}


def rank_links(text: str, links: list[tuple[int, str]], context: set[str], window: int = 400) -> list[str]:
    """Links ordered by how many of the citing sentences' words stand within `window` characters of them (ties: first
    in the page)."""
    low = (text or "").lower()
    scored = []
    for i, (pos, url) in enumerate(links):
        near = _words(low[max(0, pos - window):pos + window])
        scored.append((-len(near & context), i, url))
    return [u for _, _, u in sorted(scored)]


def citing_context(text: str, idx: int) -> set[str]:
    """The words of the sentences in `text` that cite [idx]."""
    words: set[str] = set()
    for sent in re.split(r"(?<=[.!?])\s+|\n", text or ""):
        if idx in cited_indices(sent):
            words |= _words(re.sub(r"[\[【]\d[\d,\s–-]*[\]】]", " ", sent))
    return words


class Reader:
    """The background reader. `fetch(url)` returns ContentFetcher's result dict; `register(url, title, text)` returns a
    new source's [N] (the strategy's collector); `wrap(fn)` runs fn under the run's egress policy; `clock` is the
    research clock and `deadline` the run's end on it."""

    def __init__(self, store: Any, fetch: Callable[[str], dict], register: Callable[[str, str, str], int],
                 wrap: Callable[[Callable[[], Any]], Any] | None = None, clock: Callable[[], float] | None = None,
                 deadline: float | None = None, primary: bool = True):
        self.store, self.fetch, self.register = store, fetch, register
        self.wrap = wrap or (lambda fn: fn())
        self.clock = clock or time.time
        self.deadline = deadline
        self.primary = primary
        self.q: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.tried: set[int] = set()
        self.pending = 0
        self.idle = threading.Event()
        self.idle.set()
        self._stop = threading.Event()
        self.stats = {"wanted": 0, "read": 0, "failed": 0, "cap": 0, "primary_links": 0, "primary_read": 0,
                      "primary_failed": 0, "fetch_s": 0.0}
        self.thread = threading.Thread(target=self._run, name="deep-reader", daemon=True)
        self.thread.start()

    # -- queueing ---------------------------------------------------------------------------------------------------
    def want(self, text: str) -> int:
        """Queue every source `text` cites whose page was not read. Returns how many were queued."""
        n = 0
        for idx in cited_indices(text):
            s = self.store.source(idx)
            if s is None or s.page_text:
                continue
            with self.lock:
                if idx in self.tried:
                    continue
                self.tried.add(idx)
                self.pending += 1
                self.idle.clear()
                self.stats["wanted"] += 1
            self.q.put((idx, citing_context(text, idx)))
            n += 1
        return n

    def finish(self, until: float) -> dict[str, Any]:
        """Wait (on the research clock) until the queue is done or `until`; what is still queued then stays unread."""
        while self.pending > 0 and self.clock() < until and not self._stop.is_set():
            self.idle.wait(1.0)
        with self.lock:
            left = self.pending
        return {**self.stats, "fetch_s": round(self.stats["fetch_s"], 1), "left_unread": left}

    def stop(self) -> None:
        self._stop.set()

    # -- the worker ---------------------------------------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                idx, ctx = self.q.get(timeout=0.5)
            except queue.Empty:
                if self.deadline is not None and self.clock() > self.deadline + 600:
                    return                         # a research that ended without its report stage: do not linger
                continue
            try:
                if self.deadline is not None and self.clock() >= self.deadline:
                    self.store.mark_unreadable(idx, "not read: the run's time was up")
                else:
                    self._read(idx, ctx)
            except Exception:  # noqa: BLE001
                logger.exception(f"deep reader: [{idx}] failed")
            finally:
                with self.lock:
                    self.pending -= 1
                    if self.pending <= 0:
                        self.pending = 0
                        self.idle.set()

    def _get(self, url: str) -> tuple[str, str, str, str]:
        """(text, title, date, error) of one page."""
        t = time.time()
        try:
            res = self.wrap(lambda: self.fetch(url)) or {}
        except Exception as exc:  # noqa: BLE001
            res = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        finally:
            self.stats["fetch_s"] += time.time() - t
        text = (res.get("content") or "") if res.get("status") == "success" else ""
        err = "" if text.strip() else str(res.get("error") or "no text on the page")[:200]
        return text, str(res.get("title") or ""), str(res.get("published_date") or ""), err

    def _read(self, idx: int, ctx: set[str]) -> None:
        s = self.store.source(idx)
        if s is None or s.page_text:
            return
        if self.stats["read"] + self.stats["failed"] >= READ_MAX:
            self.stats["cap"] += 1
            self.store.mark_unreadable(idx, f"not read: the per-run page cap ({READ_MAX}) was reached")
            return
        if not (s.url or "").startswith(("http://", "https://")):
            self.stats["failed"] += 1
            self.store.mark_unreadable(idx, "no web address")
            return
        text, title, date, err = self._get(s.url)
        if err:
            self.stats["failed"] += 1
            self.store.mark_unreadable(idx, err)
            return
        self.stats["read"] += 1
        self.store.add_read(idx, s.url, title or s.title, text, date=date)
        if self.primary and not is_primary(s.url):
            self._follow(idx, text, s.url, ctx)

    def _follow(self, via: int, text: str, url: str, ctx: set[str]) -> None:
        links = rank_links(text, candidate_links(text, url), ctx)[:PRIMARY_PER_PAGE]
        self.stats["primary_links"] += len(links)
        for link in links:
            if self.stats["primary_read"] >= PRIMARY_MAX or self._stop.is_set():
                return
            if self.deadline is not None and self.clock() >= self.deadline:
                return
            known = self.store.url_to_idx.get(link)
            if known is not None and self.store.source(known) is not None and self.store.source(known).page_text:
                self.store.link_primary(via, known)
                continue
            ptext, ptitle, pdate, err = self._get(link)
            if err:
                self.stats["primary_failed"] += 1
                continue
            try:
                new = int(self.register(link, ptitle, ptext))
            except Exception:  # noqa: BLE001
                logger.exception(f"deep reader: could not register {link}")
                continue
            self.stats["primary_read"] += 1
            self.store.add_read(new, link, ptitle, ptext, date=pdate, via=via)
            self.store.link_primary(via, new)
