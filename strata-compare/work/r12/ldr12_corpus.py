#!/usr/bin/env python3
"""ldr12_corpus.py — round 12 (Phase A, before any Round 12 build or served A/B): the source material for Round 12's NEW
LDR-shaped holdout (6 topics no earlier set used — 48 checked; read-only until Phase C). Copy of round 10's ldr_corpus.py: the source material for the LDR-shaped screen (S), its holdout (H) and the
aging / routing-trace pool (T).  For each research topic: two searches through OUR SearXNG (127.0.0.1:8888, not Local
Deep Research's 8889/8890), then the result pages fetched with the server's own fetcher (serve/websearch.py: public
addresses only, 5 redirects, size cap) and turned into text.  Everything is frozen into work/r10/ldr/corpus/SET/ID.json;
the prompt builder (ldr_prompts.py) only reads these files, so the screens never touch the network.

It never runs beside a timing measurement: before every fetch it waits while a screen script is running."""
import concurrent.futures as cf
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "strata-cstar13"))
from serve import websearch as W  # noqa: E402

OUT = WS / "work/r12/ldr12/corpus"
SKIP = ("youtube.com", "youtu.be", "reddit.com", "facebook.com", "x.com", "twitter.com", "linkedin.com", "instagram.com",
        "tiktok.com", "quora.com", "pinterest.", "amazon.", ".pdf")

# (set, id, research question, [search queries]) — six topics none of Round 10's 42 (S / H / T) covers
TOPICS = [
    ("H", "passkeys", "How do passkeys work, how secure are they compared with passwords and two-factor codes, and what is holding back their adoption?",
     ["how passkeys work security compared to passwords 2FA", "passkeys adoption problems account recovery sync"]),
    ("H", "gutbrain", "What does the evidence say about the gut microbiome's role in depression and anxiety in humans?",
     ["gut microbiome depression human studies evidence", "probiotics depression randomized controlled trial meta-analysis"]),
    ("H", "zswap", "How do zram and zswap compare for Linux memory compression, and when does each help or hurt?",
     ["zram vs zswap linux memory compression comparison", "zswap zram performance benchmark swap desktop server"]),
    ("H", "hanseatic", "Why did the Hanseatic League decline, and what role did trade, states and war play?",
     ["Hanseatic League decline causes", "Hanseatic League Dutch competition territorial states sixteenth century"]),
    ("H", "smr", "Where do small modular nuclear reactors stand in licensing, construction and cost, and what happened to the projects that were cancelled?",
     ["small modular reactor status licensing construction 2026", "NuScale cancelled project cost small modular reactor economics"]),
    ("H", "rustlinux", "How far has Rust been adopted in the Linux kernel, and what have the main technical and social obstacles been?",
     ["Rust for Linux kernel status drivers", "Rust in the Linux kernel maintainers controversy obstacles"]),
]


def screens_running() -> bool:
    r = subprocess.run(["pgrep", "-f", r"work/r1[0-2]/(screen|decscreen|ldrscreen|holdscreen|ttftscreen|p0prof|p12prof|a4arms|drift|exact7|fixpair)\.sh|tmp/r12/(warmpipe|hotcold)"], capture_output=True)
    return r.returncode == 0


def search(q: str) -> list[dict]:
    url = "http://127.0.0.1:8888/search?" + urllib.parse.urlencode({"q": q, "format": "json"})
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.loads(r.read())
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": (x.get("content") or "")[:600],
             "engine": x.get("engine", "")} for x in d.get("results", [])]


def page(url: str) -> dict:
    while screens_running():
        time.sleep(10)
    try:
        final, ctype, body = W.fetch(url, 20.0, 3_000_000)
        if "html" not in ctype and "text/plain" not in ctype:
            return {"url": url, "error": f"content type {ctype}"}
        doc = W._decode(body, ctype)
        title, text = W.html_to_text(doc) if "html" in ctype else ("", doc)
        return {"url": url, "final": final, "title": title, "text": text[:16000], "chars": len(text)}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": repr(e)[:200]}


def build(t):
    st, tid, question, queries = t
    out = OUT / st / f"{tid}.json"
    if out.exists():
        return f"{st}/{tid}: exists"
    while screens_running():
        time.sleep(10)
    results, seen = [], set()
    for q in queries:
        try:
            for r in search(q):
                key = W._norm(r["url"])
                if key in seen:
                    continue
                seen.add(key)
                results.append({**r, "query": q})
        except Exception as e:  # noqa: BLE001
            results.append({"query": q, "error": repr(e)[:200]})
        time.sleep(1.0)
    cand = [r for r in results if r.get("url") and not any(s in r["url"].lower() for s in SKIP)][:22]
    with cf.ThreadPoolExecutor(6) as ex:
        pages = list(ex.map(page, [r["url"] for r in cand]))
    good = [p for p in pages if p.get("text") and len(p["text"]) > 1500]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"set": st, "id": tid, "question": question, "queries": queries, "results": results,
                               "pages": pages, "fetched": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False,
                              indent=1), encoding="utf-8")
    return f"{st}/{tid}: {len(results)} results, {len(good)} usable pages of {len(cand)} fetched"


if __name__ == "__main__":
    only = set(sys.argv[1:])
    for t in TOPICS:
        if only and t[1] not in only and t[0] not in only:
            continue
        print(build(t), flush=True)
