#!/usr/bin/env python3
"""ldr_corpus.py — round 10 Phase 0.3: the source material for the LDR-shaped screen (S), its holdout (H) and the
aging / routing-trace pool (T).  For each research topic: two searches through OUR SearXNG (127.0.0.1:8888, not Local
Deep Research's 8889/8890), then the result pages fetched with the server's own fetcher (serve/websearch.py: public
addresses only, 5 redirects, size cap) and turned into text.  Everything is frozen into work/r11/ldr/corpus/SET/ID.json;
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
sys.path.insert(0, str(WS / "strata-v35"))
from serve import websearch as W  # noqa: E402

OUT = WS / "work/r11/ldr/corpus"
SKIP = ("youtube.com", "youtu.be", "reddit.com", "facebook.com", "x.com", "twitter.com", "linkedin.com", "instagram.com",
        "tiktok.com", "quora.com", "pinterest.", "amazon.", ".pdf")

# (set, id, research question, [search queries])
TOPICS = [
    ("S", "heatpump", "How do air-source heat pumps perform in very cold climates, and what do field studies say about their efficiency below -15 °C?",
     ["cold climate air source heat pump field study COP below -15C", "heat pump performance extreme cold efficiency study"]),
    ("S", "fasting", "What is the current evidence on intermittent fasting versus continuous calorie restriction for weight loss and metabolic health?",
     ["intermittent fasting vs continuous calorie restriction randomized trial", "time restricted eating meta-analysis weight loss"]),
    ("S", "gridstorage", "What are the main approaches to grid-scale energy storage besides lithium-ion batteries, and how do their costs compare?",
     ["grid scale energy storage alternatives to lithium ion cost comparison", "iron-air flow battery pumped hydro compressed air storage levelized cost"]),
    ("S", "memsafety", "How do Rust's borrow checker, Swift's ownership model and modern C++ compare as approaches to memory safety?",
     ["rust borrow checker vs swift ownership vs c++ memory safety", "memory safe languages comparison rust swift c++ safety profiles"]),
    ("S", "gfc2008", "What caused the 2008 global financial crisis, according to the main academic explanations?",
     ["causes of the 2008 financial crisis academic explanations", "global financial crisis 2008 subprime leverage shadow banking causes"]),
    ("S", "specdec", "How do modern LLM inference engines use speculative decoding, and what speedups are reported?",
     ["speculative decoding LLM inference speedup", "EAGLE Medusa MTP speculative decoding benchmark vLLM"]),
    ("H", "microplastics", "What is known about microplastics in drinking water and their effects on human health?",
     ["microplastics drinking water health effects review", "microplastics human health evidence WHO"]),
    ("H", "solidstate", "How do solid-state batteries differ from lithium-ion batteries, and when are they expected in cars?",
     ["solid state battery vs lithium ion differences", "solid state battery electric car timeline production"]),
    ("H", "pgmysql", "What are the trade-offs between PostgreSQL and MySQL for write-heavy workloads?",
     ["postgresql vs mysql write heavy workload performance", "postgres mysql MVCC vacuum write amplification comparison"]),
    ("H", "romefall", "What were the main causes of the fall of the Western Roman Empire according to historians?",
     ["causes of the fall of the western roman empire historians", "fall of rome historiography economic military explanations"]),
    ("H", "fourday", "How did four-day work week trials affect productivity, wellbeing and company outcomes?",
     ["four day work week trial results productivity", "4 day week pilot study wellbeing revenue results"]),
    ("H", "crispr", "How does CRISPR base editing differ from prime editing, and what are their clinical uses so far?",
     ["base editing vs prime editing differences", "base editing prime editing clinical trials therapy"]),
    ("T", "vectordb", "How do vector databases index embeddings (HNSW, IVF, product quantization) and what are the trade-offs?",
     ["vector database indexing HNSW IVF product quantization trade-offs", "approximate nearest neighbor index comparison recall latency"]),
    ("T", "screensleep", "What does research say about the effects of screen time on adolescent sleep?",
     ["screen time adolescent sleep research", "smartphone use teenagers sleep quality study"]),
    ("T", "jwst", "How has the James Webb Space Telescope changed the study of exoplanet atmospheres?",
     ["JWST exoplanet atmosphere discoveries", "James Webb transmission spectroscopy exoplanet results"]),
    ("T", "minwage", "What are the employment and income effects of minimum wage increases according to recent studies?",
     ["minimum wage increase employment effects recent studies", "minimum wage research meta-analysis employment"]),
    ("T", "wasm", "How do WebAssembly runtimes compare for server-side use (Wasmtime, Wasmer, WasmEdge)?",
     ["wasmtime vs wasmer vs wasmedge comparison", "server side webassembly runtime performance"]),
    ("T", "fusion", "What is the state of nuclear fusion research after the recent ignition results?",
     ["nuclear fusion ignition NIF progress", "fusion energy state of research tokamak stellarator 2025"]),
    ("T", "amoc", "How does the Atlantic Meridional Overturning Circulation affect European climate, and is it slowing?",
     ["AMOC slowing evidence", "atlantic meridional overturning circulation europe climate impact"]),
    ("T", "zdmigr", "What are the best practices for zero-downtime database schema migrations?",
     ["zero downtime database migration best practices", "expand contract schema migration online"]),
    ("T", "sourdough", "How does sourdough fermentation affect bread's digestibility and glycemic response?",
     ["sourdough fermentation digestibility glycemic index study", "sourdough bread gluten fructan fermentation health"]),
    ("T", "bbr", "What are the differences between TCP BBR and CUBIC congestion control, and when is each better?",
     ["TCP BBR vs CUBIC comparison", "BBRv2 BBRv3 fairness CUBIC performance"]),
    ("T", "printing", "How did the printing press change literacy and religion in early modern Europe?",
     ["printing press impact literacy reformation", "gutenberg printing press effects early modern europe"]),
    ("T", "carbonprice", "What does the evidence say about the effectiveness of carbon pricing schemes?",
     ["carbon pricing effectiveness evidence emissions", "carbon tax emissions trading ex-post evaluation"]),
    ("T", "ebike", "How do e-bike regulations differ between the EU, the UK and the US?",
     ["e-bike regulations EU UK US differences", "electric bicycle classes speed power limits law"]),
    ("T", "raghall", "What are the main techniques for reducing hallucinations in retrieval-augmented generation?",
     ["reducing hallucinations retrieval augmented generation techniques", "RAG grounding citation verification hallucination"]),
    ("T", "mrna", "How does the immune response to mRNA vaccines compare with protein subunit vaccines?",
     ["mRNA vaccine vs protein subunit vaccine immune response", "mRNA vaccine T cell response comparison adjuvanted protein"]),
    ("T", "monorepo", "What are the trade-offs between monorepos and polyrepos for large engineering organizations?",
     ["monorepo vs polyrepo trade-offs", "monorepo at scale google meta tooling bazel"]),
    ("T", "coral", "How do coral reefs recover after mass bleaching events?",
     ["coral reef recovery after bleaching", "great barrier reef bleaching recovery rate"]),
    ("T", "ubi", "What do universal basic income pilot programs show about its effects?",
     ["universal basic income pilot results", "basic income experiment employment wellbeing findings"]),
    ("T", "cgroups", "How do Linux cgroups v2 and systemd manage resource limits for services and containers?",
     ["cgroups v2 systemd resource control", "cgroup v2 memory.max cpu.max containers"]),
    ("T", "upf", "What is known about the health effects of ultra-processed foods?",
     ["ultra-processed food health effects evidence", "ultra processed food NOVA cohort mortality"]),
    ("T", "gnss", "How do GPS and other satellite navigation systems reach meter-level or better accuracy?",
     ["how GPS accuracy works RTK SBAS", "GNSS positioning accuracy dual frequency multipath"]),
    ("T", "housing", "What are the causes and consequences of the housing affordability crisis in major cities?",
     ["housing affordability crisis causes", "housing supply zoning rents research cities"]),
    ("T", "zkp", "How do zero-knowledge proofs work, and where are they used in practice?",
     ["zero knowledge proofs explained applications", "zk-SNARK zk-STARK practical use cases"]),
    ("T", "bilingual", "What does research say about the benefits of bilingual education?",
     ["bilingual education research outcomes", "dual language immersion achievement study"]),
    ("T", "windblade", "How are wind turbine blades recycled, and what are the challenges?",
     ["wind turbine blade recycling challenges", "recyclable wind turbine blades thermoplastic pyrolysis"]),
    ("T", "longcovid", "What is the current understanding of the mechanisms of long COVID?",
     ["long covid mechanisms current understanding", "long covid viral persistence autoimmunity research"]),
    ("T", "branchpred", "How do branch predictors work in modern CPUs?",
     ["how modern cpu branch predictors work TAGE", "branch prediction perceptron TAGE explanation"]),
    ("T", "brexit", "What were the economic consequences of Brexit for UK trade?",
     ["brexit impact on uk trade evidence", "brexit trade effects study exports imports"]),
    ("T", "lithium", "How do lithium extraction methods (brine evaporation, hard rock, direct lithium extraction) compare environmentally?",
     ["lithium extraction brine vs hard rock environmental impact", "direct lithium extraction DLE water use comparison"]),
    ("T", "cbti", "How effective is cognitive behavioral therapy for insomnia compared with sleep medication?",
     ["CBT-I vs sleeping pills effectiveness", "cognitive behavioral therapy insomnia meta-analysis long term"]),
]


def screens_running() -> bool:
    r = subprocess.run(["pgrep", "-f", r"work/r11/(screen|decscreen|ldrscreen|holdscreen)\.sh"], capture_output=True)
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
