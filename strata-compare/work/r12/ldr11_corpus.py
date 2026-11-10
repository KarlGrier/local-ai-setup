#!/usr/bin/env python3
"""ldr11_corpus.py — round 11 (before Phase A): the source material for Round 11's NEW LDR-shaped holdout (6 topics no
earlier set used; read-only until Phase G). Copy of round 10's ldr_corpus.py: the source material for the LDR-shaped screen (S), its holdout (H) and the
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
sys.path.insert(0, str(WS / "strata-cstar121"))
from serve import websearch as W  # noqa: E402

OUT = WS / "work/r12/ldr11/corpus"
SKIP = ("youtube.com", "youtu.be", "reddit.com", "facebook.com", "x.com", "twitter.com", "linkedin.com", "instagram.com",
        "tiktok.com", "quora.com", "pinterest.", "amazon.", ".pdf")

# (set, id, research question, [search queries]) — six topics none of Round 10's 42 (S / H / T) covers
TOPICS = [
    ("H", "groundwater", "How is groundwater depletion measured, for example with the GRACE satellites, and which aquifers are declining fastest?",
     ["GRACE satellite groundwater depletion measurement", "fastest declining aquifers world study"]),
    ("H", "riscv", "How does RISC-V compare with ARM for embedded and server processors, and how mature is its software ecosystem?",
     ["RISC-V vs ARM embedded server comparison", "RISC-V software ecosystem maturity Linux distributions"]),
    ("H", "sleepapnea", "What treatments for obstructive sleep apnea exist besides CPAP, and how effective are they?",
     ["obstructive sleep apnea treatment alternatives to CPAP effectiveness", "hypoglossal nerve stimulation oral appliance sleep apnea trial"]),
    ("H", "kessler", "How large is the risk of Kessler syndrome from satellite megaconstellations, and what mitigation measures exist?",
     ["Kessler syndrome risk satellite megaconstellations", "space debris mitigation active debris removal deorbit rules"]),
    ("H", "littleiceage", "What caused the Little Ice Age, and how did it affect European agriculture and society?",
     ["little ice age causes volcanic solar", "little ice age europe agriculture famine society impact"]),
    ("H", "desal", "How do reverse-osmosis and thermal desalination compare in energy use and cost, and what are the environmental effects of the brine?",
     ["reverse osmosis vs thermal desalination energy cost", "desalination brine discharge environmental impact study"]),
]


def screens_running() -> bool:
    r = subprocess.run(["pgrep", "-f", r"work/r1[01]/(screen|decscreen|ldrscreen|holdscreen|ttftscreen|p0prof)\.sh"], capture_output=True)
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
