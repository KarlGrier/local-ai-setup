#!/usr/bin/env python3
"""read-pass.py - phase 4 item 6 offline (10-28): the pages a finished deep run cited without reading them, fetched
now, plus the primary sources those pages name - added to a copy of the run's evidence, so that
`fix-replay.py write --evidence DIR` writes the report again as if the background reader had run (deep/reading.py).

Network only, no model: one page at a time, no JavaScript rendering, public addresses only, at low priority.

  read-pass.py RUN_DIR --out DIR [--max-minutes M]
      RUN_DIR: a finished deep run (RUN_DIR/deep/evidence.jsonl). What counts as cited: the [N] in the subagents'
      findings and the lead's answer (what the reader sees during a run).
      -> DIR/evidence.jsonl (the run's records, then "read" / "primary" / "unreadable" records) and DIR/read-pass.json
         (cited, already read, read now, failed, primary sources found)
Caveat: the pages are fetched today, not on the day of the run; some will have changed or gone.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

STAGING = Path("/home/USER/ai/deep-research/staging/bundle-1028")


def deep_modules():
    """The installed deep package when it has the reader, else the staged copy (before the bundle is installed)."""
    try:
        from local_deep_research.deep import evidence, reading, seed  # noqa: F401
        return evidence, reading, seed
    except ImportError:
        sys.path.insert(0, str(STAGING))
        from deep import evidence, reading, seed  # type: ignore
        return evidence, reading, seed


def public(url: str) -> bool:
    """http(s) to a host whose every address is public (no loopback, private or link-local targets)."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-minutes", type=float, default=45.0)
    a = ap.parse_args()
    os.nice(15)
    run, out = Path(a.run), Path(a.out)
    src_ev = run / "deep" / "evidence.jsonl"
    if not src_ev.exists():
        print(f"no evidence in {run}")
        return 1
    if out.exists() and any(out.iterdir()):
        print(f"{out} exists - pick another folder")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("LDR_DEEP", "1")
    evidence, reading, seed_mod = deep_modules()
    from local_deep_research.content_fetcher import ContentFetcher

    shutil.copyfile(src_ev, out / "evidence.jsonl")
    for f in ("lead_answer.md",):
        if (run / "deep" / f).exists():
            shutil.copyfile(run / "deep" / f, out / f)
    sd = seed_mod.load([str(run / "deep")])
    store = evidence.EvidenceStore(sd.queries[0] if sd and sd.queries else "", None)
    seed_mod.fill_store(sd, store)
    store._jsonl = open(out / "evidence.jsonl", "a", encoding="utf-8")       # the reader's records after the run's
    texts = [s["text"] for s in sd.subagents] + [n["text"] for n in sd.notes if n["kind"] == "lead_answer"]
    lead = (run / "deep" / "lead_answer.md").read_text(encoding="utf-8") if (run / "deep" / "lead_answer.md").exists() else ""
    texts.append(lead)
    cited = sorted({i for t in texts for i in evidence.cited_indices(t) if store.source(i) is not None})
    already = [i for i in cited if store.source(i).page_text]

    def fetch(url: str) -> dict:
        if not public(url):
            return {"status": "error", "error": "not a public web address"}
        with ContentFetcher(timeout=30, enable_js_rendering=False) as f:
            return f.fetch(url, max_length=120_000)

    nxt = [max(store.sources) + 1 if store.sources else 1]

    def register(url: str, title: str, text: str) -> int:
        idx = store.url_to_idx.get(url)
        if idx is None:
            idx, nxt[0] = nxt[0], nxt[0] + 1
        return idx

    rd = reading.Reader(store, fetch, register, deadline=None)
    t0 = time.time()
    for t in texts:
        rd.want(t)
    res = rd.finish(time.time() + 60 * a.max_minutes)
    rd.stop()
    store.close()
    summary = {"run": str(run), "cited": len(cited), "already_read": len(already),
               "read_now": res["read"], "failed": res["failed"], "left_unread": res["left_unread"],
               "primary_links": res["primary_links"], "primary_read": res["primary_read"],
               "seconds": round(time.time() - t0, 1), "fetch_s": res["fetch_s"],
               "unreadable": {str(s.idx): s.unreadable for s in store.all_sources() if s.unreadable},
               "primaries": {str(s.idx): s.primaries for s in store.all_sources() if s.primaries}}
    (out / "read-pass.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("unreadable", "primaries")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
