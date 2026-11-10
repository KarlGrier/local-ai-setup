#!/usr/bin/env python3
"""test_enginescope.py - offline tests of the engine-scope labels (10-29). No model, no services, no network, no GPU.

  nice -n 19 .venv/bin/python -I -B staging/enginescope/tests/test_enginescope.py [--out DIR]

The staged files are loaded over the installed package (staging/enginescope/deep first on the deep package's path, the
staged fetch tool under its own name); the installed codetool / report / fetch tool are loaded next to them for the
"nothing changes" comparisons. A fake model answers every call. The code tool runs on a local copy of Strata v0.2.4
(`git archive v0.2.4` of strata-compare/strata in staging/enginescope/scratch/strata-v0.2.4; made here if missing) -
it is put into the code tool as an already-open clone, so nothing is cloned or fetched.

Data: results/bench2/codetool/run-full-bundle-verpin (the second 10-24 rerun) - its evidence, code-tool log and
question. Writes test-output.txt, results.json and samples/*.txt next to this file (or --out). Exit 0 = all PASS.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

WS = Path("/home/USER/ai/deep-research")
SITE = WS / ".venv/lib/python3.12/site-packages/local_deep_research"
ST = WS / "staging/enginescope"
RUN = WS / "results/bench2/codetool/run-full-bundle-verpin"
QFILE = WS / "results/bench2/codetool/question.txt"
STRATA = Path("/home/USER/ai-speed-testing/strata-compare/strata")
CLONE = ST / "scratch/strata-v0.2.4"
SCRATCH = ST / "scratch/tmp"
C3 = WS / "staging/c3"
# --variant installed (default): staged files over the installed package, compared with the installed files;
# --variant c3: the c3-merged files over staging/c3's copies (c3 installs first), compared with c3's copies
VARIANTS = {
    "installed": {"init": SITE / "deep/__init__.py", "path": [ST / "deep", SITE / "deep"], "fetch": ST / "fetch",
                  "strategy": ST / "strategies", "base_codetool": SITE / "deep/codetool.py",
                  "base_report": SITE / "deep/report.py"},
    "c3": {"init": C3 / "deep/__init__.py", "path": [ST / "c3-merged/deep", C3 / "deep", SITE / "deep"],
           "fetch": ST / "c3-merged/fetch", "strategy": ST / "c3-merged/strategies",
           "base_codetool": C3 / "deep/codetool.py", "base_report": C3 / "deep/report.py"},
}
V = VARIANTS["c3" if "--variant" in sys.argv and sys.argv[sys.argv.index("--variant") + 1] == "c3" else "installed"]
FIXES = "version,inline,arith,cite,baseline,budget,consist,read,claims"      # the verpin run's LDR_DEEP_FIX
FIXES_NO_VERSION = "inline,arith,cite,baseline,budget,consist,read,claims"
NAMES = ["--pcie-frac", "--adapt-every", "--trim-stage-weights", "--vram-reserve-mib", "STRATA_IO_THREADS",
         "STRATA_UNBUFFERED_LOAD", "--layer-split"]

SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update({"LDR_DEEP": "1", "LDR_DEEP_FIX": FIXES, "LDR_DEEP_SETUP_PROFILE": "", "LDR_DEEP_CODE": "1",
                   "LDR_DEEP_CODE_DIR": str(SCRATCH / "code-tool"), "LDR_DEEP_OUT_DIR": "", "TMPDIR": str(SCRATCH)})
sys.dont_write_bytecode = True

OUT = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": [], "shown": {}}
LOG: list[str] = []


def say(msg: str = "") -> None:
    print(msg)
    LOG.append(msg)


def check(name: str, ok: bool, detail=None) -> bool:
    OUT["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
    say(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {str(detail)[:400]}" if detail is not None and not ok else ""))
    return ok


# ------------------------------------------------------------------------------------------------ loading
def load_modules():
    import local_deep_research
    spec = importlib.util.spec_from_file_location("local_deep_research.deep", V["init"],
                                                  submodule_search_locations=[str(x) for x in V["path"]])
    deep = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = deep
    spec.loader.exec_module(deep)
    local_deep_research.deep = deep
    import local_deep_research.advanced_search_system.tools  # noqa: F401
    mods = {}
    for name, path, sub in [
        ("local_deep_research.advanced_search_system.tools.fetch", V["fetch"] / "__init__.py",
         [str(SITE / "advanced_search_system/tools/fetch")]),
        ("local_deep_research.advanced_search_system.tools._installed_fetch",
         SITE / "advanced_search_system/tools/fetch/__init__.py", [str(SITE / "advanced_search_system/tools/fetch")]),
        ("local_deep_research.deep._installed_codetool", V["base_codetool"], None),
        ("local_deep_research.deep._installed_report", V["base_report"], None)]:
        spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=sub)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        mods[name.rsplit(".", 1)[-1]] = m
    from local_deep_research.deep import codetool, enginescope, evidence, report, seed
    for m in (enginescope, report, codetool, mods["fetch"]):
        assert Path(m.__file__).is_relative_to(V["path"][0].parent), m.__file__
    return SimpleNamespace(es=enginescope, report=report, codetool=codetool, evidence=evidence, seed=seed,
                           fetch=mods["fetch"], fetch0=mods["_installed_fetch"], codetool0=mods["_installed_codetool"],
                           report0=mods["_installed_report"])


class Resp:
    def __init__(self, text: str):
        self.content = text
        self.response_metadata = {"finish_reason": "stop"}


class FakeModel:
    """Answers with the next queued text (or a short section); records every prompt."""

    def __init__(self, answers: list[str] | None = None):
        self.answers, self.prompts = list(answers or []), []

    def invoke(self, prompt, **kw):
        self.prompts.append(prompt if isinstance(prompt, str) else str(prompt))
        return Resp(self.answers.pop(0) if self.answers else "## Section\n\nText [1].")


class Collector:
    def __init__(self, store, start: int = 90000):
        self.deep_store, self.n, self.urls = store, start, {}

    def find_or_add_result(self, r, engine_name=None):
        u = r["link"]
        if u not in self.urls:
            self.n += 1
            self.urls[u] = self.n
        return self.urls[u]


def ensure_clone() -> None:
    if (CLONE / "docs/MULTI_GPU.md").is_file():
        return
    CLONE.mkdir(parents=True, exist_ok=True)
    arc = subprocess.run(["git", "-C", str(STRATA), "archive", "v0.2.4"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(CLONE)], input=arc, check=True)


def evidence_sources() -> dict[int, SimpleNamespace]:
    src: dict[int, SimpleNamespace] = {}
    with open(RUN / "deep/evidence.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["type"] in ("fetch", "read") and r.get("idx") is not None:
                s = src.setdefault(r["idx"], SimpleNamespace(idx=r["idx"], url=r["url"], title=r.get("title", ""),
                                                             page_text="", ex=[], snippets=[]))
                if len(r.get("page_text") or "") > len(s.page_text):
                    s.page_text = r["page_text"]
                if r.get("extraction"):
                    s.ex.append(r["extraction"])
            elif r["type"] == "search":
                for x in r.get("results", []):
                    s = src.setdefault(x["idx"], SimpleNamespace(idx=x["idx"], url=x["url"], title=x.get("title", ""),
                                                                 page_text="", ex=[], snippets=[]))
                    if x.get("snippet") and x["snippet"] not in s.snippets:
                        s.snippets.append(x["snippet"])
    return src


def store_from_run(M, task: str):
    st = M.evidence.EvidenceStore(task, None)
    M.seed.fill_store(M.seed.load([str(RUN / "deep")]), st)
    return st


def sample(name: str, text: str) -> None:
    d = ARGS.out / "samples"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")


# ------------------------------------------------------------------------------------------------ the tests
def t_scopes(M, Q):
    es = M.es
    say("\n== 1. which engine the task is about")
    check("the 10-24 question -> Strata's DeepSeek engine", es.task_scopes(Q, "") == {"strata": "dsv41"},
          es.task_scopes(Q, ""))
    no_eng = "How can I make Strata v0.2.4 faster on my PC (RTX 5080 + RTX 4060 Ti, 96 GB RAM)? Settings only."
    check("a Strata task naming no engine -> no scope", es.task_scopes(no_eng, "") == {}, es.task_scopes(no_eng, ""))
    both = "Strata v0.2.4: compare its Qwen3.8-Flash-Next engine with its DeepSeek-V4.1 engine on my PC."
    check("a task naming both engines -> no scope", es.task_scopes(both, "") == {}, es.task_scopes(both, ""))
    qwen = "Make Strata v0.2.4 faster for Qwen3.8-Flash-Next IQ3_S on an RTX 5080."
    check("a Qwen task -> Strata's Qwen engine", es.task_scopes(qwen, "") == {"strata": "qwen"})
    other = "How fast is DeepSeek-V4.1-Flash on llama.cpp and ik_llama.cpp with an RTX 5080?"
    check("an unrelated project (llama.cpp) with DeepSeek named -> no scope", es.task_scopes(other, "") == {})
    prof_ds = "- Engine: Strata v0.2.4, DeepSeek-V4.1-Flash engine (strata-dsv41)\n- GPU: RTX 5080"
    prof_both = "- Engines: Strata v0.2.4 Qwen3.8-Flash-Next (main) and DeepSeek-V4.1-Flash (on demand)"
    check("no engine in the task, one in the profile -> the profile's", es.task_scopes(no_eng, prof_ds) == {"strata": "dsv41"})
    check("no engine in the task, two in the profile -> no scope", es.task_scopes(no_eng, prof_both) == {})
    check("the task's engine wins over the profile's", es.task_scopes(qwen, prof_ds) == {"strata": "qwen"})
    check("prompt rule only with a scope", bool(es.prompt_rule(SimpleNamespace(query=Q)))
          and es.prompt_rule(SimpleNamespace(query=no_eng)) == "")
    OUT["shown"]["prompt_rule"] = es.prompt_rule(SimpleNamespace(query=Q))
    say("   lead / subagent rule: " + OUT["shown"]["prompt_rule"].strip()[:400])


def t_paths(M):
    es = M.es
    say("\n== 2. GitHub paths (folder table, checked against the v0.2.4 tree; the v0.2.4 map and the base map)")
    sc = {"strata": "dsv41"}
    pin = {"strata": "v0.2.4"}
    base = "https://github.com/Niko1221/Strata/blob/v0.2.4/"
    other = ["src/program/generate.cpp", "src/qwen35/q36_engine.cu", "include/strata/program/split_ring.hpp",
             "src/spec/controller.cpp", "tools/qwen35/"]
    per_version = ["src/core/expert_cache.cpp", "include/strata/core/device.hpp", "src/platform/direct_file.cpp",
                   "include/strata/platform/direct_file.hpp", "src/prefill/gemm.cu", "src/ngram/ple_reader.cpp",
                   "sycl/src/platform/direct_file.cpp", "tests/platform/direct_file_async.cpp"]
    own = ["src/dsv41/ds4_model.cu", "include/strata/dsv41/exl3.hpp", "tools/dsv41/compare.py", "docs/DEEPSEEK41.md",
           "data/dsv41/profile-2.00.bin", "tools/dsv41_lab/ds4_lab.cu"]
    shared = ["src/core/device.cu", "include/strata/hip_compat/cuda_runtime.h", "src/kernels/cpu/iq_avx512.cpp",
              "include/strata/kernels/cpu/iq_avx2.hpp", "serve/server.py", "strata_control/gpu_roles.py",
              "strata_cli/launch/__init__.py", "setup.py", "CMakeLists.txt", "tools/needle_bench.py"]
    for p in other + per_version + own + shared:
        if not (CLONE / p.rstrip("/")).exists():
            check(f"path exists at v0.2.4: {p}", False)
    lab = {p: es.classify(base + p, "", "", sc, pins=pin) for p in other + per_version + own + shared}
    check("v0.2.4: Qwen engine folders -> OTHER ENGINE (file)",
          all(lab[p] is not None and lab[p].engine == "qwen" for p in other), {p: bool(lab[p]) for p in other})
    check("v0.2.4: src/core, src/platform, src/prefill, src/ngram (+ include/strata/), sycl/src/platform, tests/platform "
          "-> OTHER ENGINE 'at v0.2.4'",
          all(lab[p] is not None and lab[p].engine == "qwen" and lab[p].at == "v0.2.4" for p in per_version),
          {p: (bool(lab[p]), getattr(lab[p], "at", "")) for p in per_version})
    check("v0.2.4: DeepSeek engine folders / doc -> no label", all(lab[p] is None for p in own),
          {p: bool(lab[p]) for p in own})
    check("v0.2.4: shared (device.cu, hip_compat, kernels, serve, launcher, setup, tools/) -> no label",
          all(lab[p] is None for p in shared), {p: bool(lab[p]) for p in shared})
    lab0 = {p: es.classify(base + p, "", "", sc, pins={}) for p in per_version + other}
    check("no pin: the conservative map - src/core, src/platform, src/prefill, src/ngram shared; the Qwen folders still "
          "labelled", all(lab0[p] is None for p in per_version) and all(lab0[p] is not None for p in other),
          {p: bool(lab0[p]) for p in per_version})
    # which entry a version takes
    picks = {v: (es.version_entry("strata", v) or ("base",))[0]
             for v in ("v0.2.3", "v0.2.4", "v0.2.4.2", "v0.2.5", "0.2.6", "v0.2.6", "v0.2.7", "v0.2.7.1", "v0.3.0",
                       "main", None)}
    say("   version -> folder map: " + ", ".join(f"{k}={v}" for k, v in picks.items()))
    check("version rule: the newest entry at or below; below every entry / unpinned / unparseable -> base",
          picks == {"v0.2.3": "base", "v0.2.4": "v0.2.4", "v0.2.4.2": "v0.2.4", "v0.2.5": "v0.2.4", "0.2.6": "v0.2.6",
                    "v0.2.6": "v0.2.6", "v0.2.7": "v0.2.7", "v0.2.7.1": "v0.2.7", "v0.3.0": "v0.2.7", "main": "base",
                    None: "base"}, picks)
    # the folders of the table exist in the v0.2.4 tree
    tab = es.table()["strata"]
    missing = [f for e in tab["engines"].values() for f in e["folders"] + e["docs"] if not (CLONE / f.rstrip("/")).exists()]
    missing += [f for f in tab["shared"] if not (CLONE / f.rstrip("/")).exists()]
    missing += [f for k, e in tab["folders_by_version"].items() if not k.startswith("_")
                for eng, fs in e.items() if isinstance(fs, list) for f in fs if not (CLONE / f.rstrip("/")).exists()]
    check("every folder / file of the table exists at v0.2.4", not missing, missing)
    # every top-level src / include folder is placed (engine or shared), in the base map and the v0.2.4 map
    tops = sorted({f"src/{d.name}/" for d in (CLONE / "src").iterdir() if d.is_dir()}
                  | {f"include/strata/{d.name}/" for d in (CLONE / "include/strata").iterdir() if d.is_dir()})
    unplaced = [t for t in tops for v in (None, "v0.2.4") if es.path_engine("strata", t + "x.cpp", v) is None]
    check("every src/ and include/strata/ folder of v0.2.4 is in the table (base and v0.2.4 maps)", not unplaced, unplaced)
    OUT["shown"]["folders_v0.2.4"] = {t: es.path_engine("strata", t + "x.cpp", "v0.2.4") for t in tops}
    OUT["shown"]["folders_base"] = {t: es.path_engine("strata", t + "x.cpp", None) for t in tops}
    say("   v0.2.4: " + ", ".join(f"{k}={v}" for k, v in OUT["shown"]["folders_v0.2.4"].items()))


def _git(*args) -> str:
    return subprocess.run(["git", "-C", str(STRATA), *args], capture_output=True, text=True).stdout


def t_versions(M):
    """What the local clone shows at each entry's tag (read-only: git show / git grep at the tag): which of strata's
    libraries strata-dsv41 links outside the Windows-HIP guard, and which strata/ headers src/dsv41 includes - the
    entry must not call a folder the DeepSeek engine uses the Qwen engine's."""
    es = M.es
    say("\n== 2b. the per-version folder maps against the clone (CMakeLists.txt and #includes at each tag)")
    libs = {"strata_core": ["src/core/", "src/platform/"],
            "strata_kernels": ["src/kernels/", "src/platform/", "src/ngram/"],
            "strata_engine": ["src/core/", "src/kernels/", "src/platform/", "src/ngram/"],
            "strata_prefill": ["src/prefill/", "src/core/", "src/kernels/", "src/platform/", "src/ngram/"]}
    found = {}
    for tag in [k for k in es.table()["strata"]["folders_by_version"] if not k.startswith("_")]:
        cm = _git("show", f"{tag}:CMakeLists.txt")
        blk = cm[cm.index("option(STRATA_BUILD_DSV41"):]
        blk = blk[:blk.index("\n  endif()")]
        lines, guard, linked = blk.splitlines(), False, set()
        for ln in lines:
            if "if(WIN32 AND STRATA_ENABLE_HIP)" in ln:
                guard = True
            elif guard and ln.strip().startswith("endif()"):
                guard = False
            m = re.search(r"target_link_libraries\(strata-dsv41 PRIVATE ([^)]*)", ln)
            if m and not guard:
                linked |= {x for x in m.group(1).split() if x in libs}
        heads = set(re.findall(r'#include "strata/([a-z_0-9]+)/', _git("grep", "-h", "#include \"strata/", tag, "--",
                                                                         "src/dsv41", "include/strata/dsv41")))
        used = {f for lib in linked for f in libs[lib]} | {f"src/{h}/" for h in heads}
        entry = es.table()["strata"]["folders_by_version"][tag]
        wrong = [f for f in entry.get("qwen", []) if f.replace("include/strata/", "src/") in used]
        blk_text = "\n".join(lines)
        for f in entry.get("qwen", []):            # a listed folder the DeepSeek build or code names at this tag
            if not f.startswith(("src/", "include/")):
                hits = _git("grep", "-il", "dsv41\\|deepseek", tag, "--", f).strip()
                if f.rstrip("/") in blk_text or hits:
                    wrong.append(f)
        found[tag] = {"links (not only on Windows HIP)": sorted(linked), "includes strata/": sorted(heads),
                      "qwen at this tag": entry.get("qwen", []), "conflicts": wrong}
        say(f"   {tag}: links {sorted(linked) or '-'}; includes strata/{sorted(heads)}; "
            f"Qwen-only here: {', '.join(f for f in entry.get('qwen', []) if f.startswith('src/')) or 'none (base map)'}")
        check(f"{tag}: no folder the DeepSeek engine links or includes is called the Qwen engine's", not wrong, wrong)
    OUT["shown"]["clone_per_tag"] = found
    check("v0.2.6: the clone shows src/core and src/platform NOT linked into strata-dsv41 (outside Windows HIP)",
          "strata_core" not in found.get("v0.2.6", {}).get("links (not only on Windows HIP)", ["x"]))
    check("v0.2.7: the clone shows strata_prefill linked -> core / platform / prefill / ngram shared from v0.2.7",
          "strata_prefill" in found.get("v0.2.7", {}).get("links (not only on Windows HIP)", [])
          and not es.table()["strata"]["folders_by_version"]["v0.2.7"].get("qwen"))
    url = "https://github.com/Niko1221/Strata/blob/{}/src/core/expert_cache.cpp"
    q = "Speed up Strata {} DeepSeek-V4.1-Flash engine on my PC"
    res = {}
    v27 = M.es.classify("https://github.com/Niko1221/Strata/blob/v0.2.7/sycl/src/platform/direct_file.cpp", "", "",
                        {"strata": "dsv41"}, pins={"strata": "v0.2.7"})
    check("v0.2.7 map: sycl/src/platform stays shared (as found)", v27 is None)
    for tag in ("v0.2.4", "v0.2.6", "v0.2.7", None):
        task = q.format(tag) if tag else "Speed up Strata's DeepSeek-V4.1-Flash engine on my PC"
        st = SimpleNamespace(query=task)
        v = M.es.for_source(st, url.format(tag or "main"), "", "")
        res[tag] = M.es.note(v) if v else ""
    say("   src/core/expert_cache.cpp for a DeepSeek task at v0.2.4 / v0.2.6 / v0.2.7 / no version: "
        + " | ".join((n[:70] + "...") if n else "-" for n in res.values()))
    check("a v0.2.4 and a v0.2.6 task label src/core (the clone: Qwen-only there); a v0.2.7 task and an unpinned one "
          "keep it shared", "at v0.2.4" in res["v0.2.4"] and "at v0.2.6" in res["v0.2.6"] and not res["v0.2.7"]
          and not res[None], res)


def verdicts_on_evidence(M, Q, src, sc=None):
    es = M.es
    sc = sc if sc is not None else es.task_scopes(Q, "")
    store = SimpleNamespace(query=Q, sources=src, engine_scopes=sc)
    out = {}
    for idx, s in src.items():
        if not s.page_text:
            continue
        v = es.for_source(store, s.url, s.title, s.page_text, whole=es.file_text(store, s.url))
        if v is not None:
            out[idx] = (v, es.note(v, es.line_range(s.page_text)))
    return store, {k: v for k, v in out.items() if v[1]}


def t_evidence(M, Q, src):
    es = M.es
    say("\n== 3. which read sources of the verpin rerun would be labelled (page / file / parts)")
    store, lab = verdicts_on_evidence(M, Q, src)
    read = [s for s in src.values() if s.page_text]
    rows = []
    for idx in sorted(lab):
        v, n = lab[idx]
        rows.append(f"[{idx}] {'PAGE' if v.engine else 'PARTS'} ({v.how}) {src[idx].url}")
    say(f"   {len(lab)} of {len(read)} read sources labelled:")
    for r in rows:
        say("     " + r)
    OUT["shown"]["labelled_sources"] = rows

    def by_url(sub):
        return [i for i, s in src.items() if sub in s.url and s.page_text]
    must = by_url("docs/MULTI_GPU.md") + by_url("bench/results/2026-10-09-community-rtx-5080-4060ti") + \
        by_url("bench/results/2026-10-09-community-4x-rx-7900-xt")
    check("MULTI_GPU.md and the community bench results are labelled (all their reads)",
          len(must) >= 5 and all(i in lab and lab[i][0].engine == "qwen" for i in must),
          {i: (i in lab) for i in must})
    never = by_url("docs/DEEPSEEK41.md") + by_url("/src/dsv41/") + by_url("/tools/dsv41/") + \
        by_url("docs/release-notes-0.2.4.md")
    check("DEEPSEEK41.md, src/dsv41, tools/dsv41 and the 0.2.4 release notes are not labelled",
          len(never) >= 20 and not [i for i in never if i in lab], [i for i in never if i in lab])
    others = [i for i, s in src.items() if s.page_text and es.project_of(s.url, s.title, s.page_text) is None]
    check("no source of another project is labelled (Xolotl, Abyss, project-maya, llama.cpp, papers ...)",
          not [i for i in others if i in lab], [src[i].url for i in others if i in lab][:5])
    xol = [i for i, s in src.items() if re.search(r"github\.com/(Indras-Mirror/Xolotl|zephel01/Abyss|mw00/project-maya|"
                                                 r"vincalkr/Strata-DSV4\.1)", s.url) and s.page_text]
    check("forks / related repos are another project (no label)", xol and not [i for i in xol if i in lab],
          [src[i].url for i in xol if i in lab])
    gh_search = [i for i, s in src.items() if "github.com/search" in s.url and s.page_text]
    check("GitHub search pages (lists of repos) are not labelled", not [i for i in gh_search if i in lab])
    # the writer's view (the store, no clone) and the code tool's (the whole file) agree on these reads
    agree = []
    for idx, s in src.items():
        m = re.match(r"https://github\.com/Niko1221/Strata/blob/v0\.2\.4/([^#?]+)", s.url)
        if not m or not s.page_text or not (CLONE / m.group(1)).is_file():
            continue
        whole = (CLONE / m.group(1)).read_text(encoding="utf-8", errors="replace")
        v = es.classify(s.url, s.title, s.page_text, store.engine_scopes, whole=whole if es._is_doc(m.group(1)) else None,
                        pins=es.pins_of(store))
        agree.append((idx, bool(v and es.note(v, es.line_range(s.page_text))), idx in lab))
    dis = [a for a in agree if a[1] != a[2]]
    check(f"code tool (whole file) and writer (evidence) agree on all {len(agree)} Strata v0.2.4 reads", not dis, dis)
    # nothing for a task naming no engine, or an unrelated task
    for name, task in (("no engine named", "How can I make Strata v0.2.4 faster on my PC? Settings only."),
                       ("unrelated project", "How fast is DeepSeek-V4.1-Flash on llama.cpp with an RTX 5080?")):
        _st, lab2 = verdicts_on_evidence(M, task, src)
        check(f"no source labelled for a task with {name}", not lab2, list(lab2)[:5])
    return store, lab


def t_sections(M, Q, src):
    es = M.es
    say("\n== 4. a mixed page: labels per section")
    sc = es.task_scopes(Q, "")
    readme = (CLONE / "README.md").read_text(encoding="utf-8")
    url = "https://github.com/Niko1221/Strata/blob/v0.2.4/README.md"
    v = es.classify(url, "", readme, sc)
    heads = [p.heading for p in v.parts] if v else []
    say("   README.md parts: " + "; ".join(f"{p.heading or '(top)'} {p.start}-{p.end} {p.counts}" for p in v.parts))
    check("README.md is mixed -> PARTLY (not the whole page)", v is not None and not v.engine and bool(v.parts))
    check("README.md: the Qwen model sections are labelled",
          any("The other sizes" in h for h in heads) and any("Gyro" in h for h in heads), heads)
    check("README.md: the DeepSeek section is not", not any("DeepSeek" in h for h in heads), heads)
    ds_line = readme.splitlines().index(next(ln for ln in readme.splitlines() if ln.startswith("### DeepSeek V4.1-Flash"))) + 1
    check("README.md: a line in the DeepSeek section is in no labelled part", v.part_at(ds_line + 3) is None)
    lines = readme.splitlines()
    q_qwen = next(ln for i, ln in enumerate(lines) if v.part_at(i + 1) and len(ln) > 60 and not ln.startswith("#"))
    q_ds = lines[ds_line + 1]
    marked = es.mark_quotes(f'- "{q_qwen.strip()}" (undated)\n- "{q_ds.strip()}" (undated)', readme, v)
    ml = marked.splitlines()
    check("quotes: the Qwen-section quote is marked, the DeepSeek one is not",
          "[OTHER ENGINE" in ml[0] and "[OTHER ENGINE" not in ml[1], marked)
    sample("mixed-readme-quotes.txt", f"{es.note(v)}\n\n{marked}\n")
    # the repo root page as the research read it (rendered GitHub page, 4393)
    root = [s for s in src.values() if s.url.rstrip("/") == "https://github.com/Niko1221/Strata" and s.page_text]
    if root:
        s = root[0]
        v2 = es.classify(s.url, s.title, s.page_text, sc)
        check("the repo root page as read (4393) -> PARTLY, its DeepSeek section unlabelled",
              v2 is not None and v2.parts and not any("DeepSeek" in p.heading for p in v2.parts),
              [p.heading for p in (v2.parts if v2 else [])])
        sample("mixed-repo-root-note.txt", es.note(v2) + "\n")
    # a page mostly about the task's engine with a stray mention of the other: no label
    ds_doc = (CLONE / "docs/DEEPSEEK41.md").read_text(encoding="utf-8")
    check("DEEPSEEK41.md (59 DeepSeek / 2 Qwen markers) -> no label at all",
          es.classify("https://github.com/Niko1221/Strata/blob/v0.2.4/docs/DEEPSEEK41.md", "", ds_doc, sc) is None)
    # a non-GitHub page about Strata (newreleases.io, 4394) - the 0.2.4.2 notes: about the DeepSeek engine
    nr = [s for s in src.values() if "newreleases.io" in s.url and s.page_text]
    if nr:
        check("newreleases.io v0.2.4 notes (a DeepSeek release) -> no label",
              es.classify(nr[0].url, nr[0].title, nr[0].page_text, sc) is None)


def t_fetch(M, Q):
    es = M.es
    say("\n== 5. the fetch tool's output (deep mode, summary_focus_query; the page from the store's page cache)")
    cases = [
        ("bench", "https://github.com/Niko1221/Strata/blob/v0.2.4/bench/results/2026-10-09-community-rtx-5080-4060ti-0.1.41/README.md",
         "bench/results/2026-10-09-community-rtx-5080-4060ti-0.1.41/README.md", "page"),
        ("multigpu", "https://raw.githubusercontent.com/Niko1221/Strata/v0.2.4/docs/MULTI_GPU.md", "docs/MULTI_GPU.md", "page"),
        ("readme", "https://github.com/Niko1221/Strata/blob/v0.2.4/README.md", "README.md", "parts"),
        ("deepseek41", "https://github.com/Niko1221/Strata/blob/v0.2.4/docs/DEEPSEEK41.md", "docs/DEEPSEEK41.md", None),
        ("unrelated", "https://example.org/llama-cpp-moe-offload", None, None),
    ]
    for key, url, rel, want in cases:
        if rel:
            page = (CLONE / rel).read_text(encoding="utf-8")
        else:
            page = ("# MoE offload in llama.cpp\n\nllama.cpp runs Qwen3.8-Flash-Next and Qwen3.6 with --n-cpu-moe; "
                    "the Qwen models use MTP drafts. Strata is mentioned once.\n\n## Flags\n\n--n-cpu-moe 30 --mlock\n")
        lines = [ln for ln in page.splitlines() if len(ln) > 50 and not ln.startswith(("#", "|", "```"))]
        pick = [lines[0], lines[len(lines) // 2], lines[-1]]
        if key == "readme":
            ds_i = page.splitlines().index(next(ln for ln in page.splitlines() if ln.startswith("### DeepSeek V4.1")))
            pick = [next(ln for ln in page.splitlines()[155:189] if len(ln) > 50 and not ln.startswith("|")),
                    next(ln for ln in page.splitlines()[ds_i + 1:ds_i + 12] if len(ln) > 50)]
        extraction = "\n".join(f'"{p.strip()}"' for p in pick)
        outs = {}
        for which, mod in (("staged", M.fetch), ("installed", M.fetch0)):
            st = M.evidence.EvidenceStore(Q, None)
            st.cache_page(url, {"status": "success", "title": f"Strata {rel}" if rel else "llama.cpp MoE offload",
                                "content": page})
            coll = Collector(st)
            tool = mod.build_fetch_tool("summary_focus_query", coll, model=FakeModel([extraction]), overall_query=Q)
            outs[which] = tool.func(url=url, focus="flags and settings for two GPUs")
        s, i = outs["staged"], outs["installed"]
        sample(f"fetch-{key}.txt", s + "\n")
        if want == "page":
            ok = s.splitlines()[2].startswith("[OTHER ENGINE: this page describes Strata's Qwen engine") and \
                s.replace(s.splitlines()[2] + "\n", "", 1) == i
            check(f"fetch {key}: labelled under the URL line, the rest as installed", ok, s[:300])
        elif want == "parts":
            sl = s.splitlines()
            ok = sl[2].startswith("[PARTLY OTHER ENGINE") and sum("[OTHER ENGINE" in x for x in sl[4:]) == 1
            check(f"fetch {key}: PARTLY note, the Qwen-section quote marked, the DeepSeek one not", ok, s[:600])
        else:
            check(f"fetch {key}: no label, byte-identical to the installed tool", s == i and "OTHER ENGINE" not in s,
                  s[:200])
    # the full-mode tool (not used in deep mode): page label only
    st = M.evidence.EvidenceStore(Q, None)
    url = cases[1][1]
    st.cache_page(url, {"status": "success", "title": "MULTI_GPU", "content": (CLONE / "docs/MULTI_GPU.md").read_text()})
    full = M.fetch.build_fetch_tool("full", Collector(st)).func(url=url)
    check("fetch (full mode): labelled too", "[OTHER ENGINE: this page describes" in full.splitlines()[2])
    # switch off: LDR_DEEP_FIX without "version"
    os.environ["LDR_DEEP_FIX"] = FIXES_NO_VERSION
    try:
        st = M.evidence.EvidenceStore(Q, None)
        st.cache_page(cases[0][1], {"status": "success", "title": "b", "content": (CLONE / cases[0][2]).read_text()})
        o = M.fetch.build_fetch_tool("summary_focus_query", Collector(st), model=FakeModel(['"x y z some quote here ok"']),
                                     overall_query=Q).func(url=cases[0][1], focus="f")
        check("fetch: no label when LDR_DEEP_FIX lacks 'version'", "OTHER ENGINE" not in o, o[:200])
    finally:
        os.environ["LDR_DEEP_FIX"] = FIXES


def make_code_tools(M, mod, task, store=None):
    st = store or M.evidence.EvidenceStore(task, None)
    coll = Collector(st)
    tools = mod.make_tools(coll, "enginescope-test", None, task=task, profile="")
    ct = coll.deep_code
    ct.pin_tags["niko1221/strata"] = "v0.2.4"
    ct.repos[("niko1221/strata", "v0.2.4")] = mod.Repo("Niko1221/Strata", "v0.2.4", CLONE.resolve(), ct._log,
                                                        user_ref="v0.2.4")
    return {t.name: t for t in tools}, st


def t_codetool(M, Q):
    say("\n== 6. the code tool's read and search output (local v0.2.4 tree as the open clone)")
    staged, _ = make_code_tools(M, M.codetool, Q)
    inst, _ = make_code_tools(M, M.codetool0, Q)
    reads = [("docs/MULTI_GPU.md", 190, 240, "page"),
             ("bench/results/2026-10-09-community-rtx-5080-4060ti-0.1.41/README.md", 108, 121, "page"),
             ("src/program/generate.cpp", 2880, 2900, "file"),
             ("README.md", 140, 200, "parts"),
             ("docs/DEEPSEEK41.md", 1, 60, None),
             ("src/dsv41/ds4_main.cpp", 60, 100, None),
             ("src/core/expert_cache.cpp", 1, 30, "file"),
             ("src/platform/direct_file.cpp", 1, 30, "file"),
             ("src/core/device.cu", 170, 200, None),
             ("serve/server.py", 1, 30, None)]
    for rel, a, b, want in reads:
        s = staged["code_read"].func(repo="Niko1221/Strata@v0.2.4", file=rel, start_line=a, end_line=b)
        i = inst["code_read"].func(repo="Niko1221/Strata@v0.2.4", file=rel, start_line=a, end_line=b)
        tag = re.sub(r"[^\w]+", "_", rel)[-40:]
        sample(f"code_read-{tag}-{a}-{b}.txt", s + "\n")
        third = s.splitlines()[2]
        if want in ("page", "file"):
            what = "page describes" if want == "page" else "file is part of"
            ok = third.startswith(f"[OTHER ENGINE: this {what} Strata's Qwen engine") and \
                s.replace(third + "\n", "", 1) == i
            check(f"code_read {rel}:{a}-{b}: OTHER ENGINE ({want}); the lines as installed", ok, s[:300])
        elif want == "parts":
            ok = third.startswith("[PARTLY OTHER ENGINE") and "[OTHER ENGINE from here" in s and \
                "[end of the OTHER ENGINE part]" in s
            check(f"code_read {rel}:{a}-{b}: PARTLY, start / end marks around the Qwen part", ok, s[:500])
        else:
            check(f"code_read {rel}:{a}-{b}: no label, byte-identical to the installed tool", s == i, s[:200])
    # searches
    s = staged["code_search"].func(repo="Niko1221/Strata@v0.2.4", pattern="--trim-stage-weights")
    i = inst["code_search"].func(repo="Niko1221/Strata@v0.2.4", pattern="--trim-stage-weights")
    sample("code_search-trim-stage-weights.txt", s + "\n")
    hits = [ln for ln in s.splitlines() if re.match(r"^[\w./-]+:\d+: ", ln)]
    marked = [ln for ln in hits if "[OTHER ENGINE: Strata's Qwen engine]" in ln]
    unmarked_files = sorted({ln.split(":")[0] for ln in hits if ln not in marked})
    say(f"   code_search --trim-stage-weights: {len(marked)} of {len(hits)} shown hits marked; unmarked files: "
        f"{', '.join(unmarked_files)}")
    check("code_search: Qwen engine files / docs marked, legend line added, shared files (serve, launcher) unmarked",
          marked and "hit(s) marked [OTHER ENGINE" in s and all(
              M.es.path_engine("strata", f) in ("shared", None) for f in unmarked_files), unmarked_files)
    strip = re.sub(r"\n\(\d+ hit\(s\) marked \[OTHER ENGINE.*\)$", "", s)
    strip = re.sub(r"\[OTHER ENGINE: Strata's Qwen engine\] ", "", strip)
    check("code_search: without the marks and the legend, identical to the installed output", strip == i)
    s2 = staged["code_search"].func(repo="Niko1221/Strata@v0.2.4", pattern="DS4_RING_MB")
    i2 = inst["code_search"].func(repo="Niko1221/Strata@v0.2.4", pattern="DS4_RING_MB")
    check("code_search for a DeepSeek-only name: unchanged", s2 == i2, s2[:200])
    # no scope (no engine named): every output as installed
    no_eng = "How can I make Strata v0.2.4 faster on my PC? Settings only."
    staged2, _ = make_code_tools(M, M.codetool, no_eng)
    inst2, _ = make_code_tools(M, M.codetool0, no_eng)
    same = all(staged2["code_read"].func(repo="Niko1221/Strata@v0.2.4", file=rel, start_line=a, end_line=b)
               == inst2["code_read"].func(repo="Niko1221/Strata@v0.2.4", file=rel, start_line=a, end_line=b)
               for rel, a, b, _w in reads)
    same &= staged2["code_search"].func(repo="Niko1221/Strata@v0.2.4", pattern="--trim-stage-weights") == \
        inst2["code_search"].func(repo="Niko1221/Strata@v0.2.4", pattern="--trim-stage-weights")
    check("code tool with no engine named: every read / search byte-identical to the installed tool", same)
    # standalone load (tools/code-mcp.py loads codetool.py on its own)
    alone = SCRATCH / "standalone-deep"            # the deep folder as installed: the staged files + what they load
    if alone.exists():
        import shutil
        shutil.rmtree(alone)
    (alone / "engines").mkdir(parents=True)
    for f in ("codetool.py", "enginescope.py"):
        (alone / f).write_bytes((V["path"][0] / f).read_bytes())
    (alone / "engines/strata.json").write_bytes((V["path"][0] / "engines/strata.json").read_bytes())
    if (V["path"][1] / "modelprofile.py").exists():                     # c3's loader (codetool reads it standalone)
        (alone / "modelprofile.py").write_bytes((V["path"][1] / "modelprofile.py").read_bytes())
    spec = importlib.util.spec_from_file_location("codetool_standalone", alone / "codetool.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["codetool_standalone"] = m
    spec.loader.exec_module(m)
    es2 = m._enginescope()
    r = m.Repo("Niko1221/Strata", "v0.2.4", CLONE.resolve())
    check("codetool.py still loads on its own (code-mcp.py); enginescope found next to it; Repo.read works",
          es2 is not None and hasattr(es2, "classify") and r.read("docs/MULTI_GPU.md", 1, 3)["end"] == 3)


def t_writer(M, Q, src):
    say("\n== 7. the writers' source labels, quotes and section prompt (verpin evidence; fake model)")
    lead = (RUN / "deep/lead_answer.md").read_text(encoding="utf-8")
    store = store_from_run(M, Q)
    w = M.report.ReportWriter(Q, store, FakeModel(), lead)
    check("section prompt carries the engine rule", M.es.SECTION_RULE in w.p_section)
    want = {}
    for sub in ("docs/MULTI_GPU.md#L190", "community-rtx-5080-4060ti-0.1.41/README.md#L108", "docs/DEEPSEEK41.md#L1-",
                "src/dsv41/ds4_model.cu#L960", "Indras-Mirror/Xolotl", "PREFILL_HEAD_ALIAS"):
        s = next((x for x in store.all_sources() if sub in x.url and x.page_text), None)
        if s is not None:
            want[sub] = w._label(s)
    shown = "\n".join(want.values())
    sample("writer-labels.txt", shown + "\n")
    say("   " + shown.replace("\n", "\n   ")[:1600])
    check("writer label: MULTI_GPU.md and the 5080 bench (lines 108-121) say OTHER ENGINE ahead of the title",
          all(re.match(r"^\[\d+\] \[OTHER ENGINE: this page describes Strata's Qwen engine", want[k])
              for k in ("docs/MULTI_GPU.md#L190", "community-rtx-5080-4060ti-0.1.41/README.md#L108")))
    check("writer label: DEEPSEEK41.md, src/dsv41 and Xolotl unlabelled",
          all("OTHER ENGINE" not in want[k] for k in ("docs/DEEPSEEK41.md#L1-", "src/dsv41/ds4_model.cu#L960",
                                                       "Indras-Mirror/Xolotl") if k in want))
    # the section prompt (evidence block) for a section citing MULTI_GPU, the 5080 bench, DEEPSEEK41 and the root page
    by_idx = {s.idx: s for s in store.all_sources()}
    ids = [s.idx for s in store.all_sources() if s.page_text and any(k in s.url for k in (
        "docs/MULTI_GPU.md#L190", "community-rtx-5080-4060ti-0.1.41/README.md#L1-", "docs/DEEPSEEK41.md#L70"))]
    ids += [s.idx for s in store.all_sources() if s.url.rstrip("/") == "https://github.com/Niko1221/Strata" and s.page_text]
    fm = FakeModel()
    w.model = fm
    w.section({"heading": "Two GPUs", "purpose": "split and settings for the 5080 + 4060 Ti", "sources": ids},
              "(outline)", by_idx)
    p = fm.prompts[-1]
    ev = p[p.index("<evidence>"):p.index("</evidence>") + 11]
    sample("writer-section-evidence.txt", ev + "\n")
    check("section evidence: OTHER ENGINE ahead of the Qwen pages' titles, PARTLY on the root page, none on DEEPSEEK41",
          ev.count("[OTHER ENGINE: this page describes") >= 2 and "[PARTLY OTHER ENGINE" in ev
          and not re.search(r"\[\d+\] \[OTHER ENGINE[^\n]*DEEPSEEK41", ev))
    check("section evidence: the root page's Qwen-section passages / quotes carry [OTHER ENGINE: Strata's Qwen engine]",
          "[OTHER ENGINE: Strata's Qwen engine]" in ev)
    # the citation check's source blocks carry the note next to the version note
    mg = next(x for x in store.all_sources() if "docs/MULTI_GPU.md#L190" in x.url)
    ds = next(x for x in store.all_sources() if "docs/DEEPSEEK41.md#L70" in x.url)
    fm = FakeModel(["{}"] * 4)
    w.model = fm
    try:
        w.verify(f"Set --pcie-frac 0 and --adapt-every 0 for a fixed placement [{mg.idx}].\n\n"
                 f"The DeepSeek engine keeps the Engram table on the SSD [{ds.idx}].\n")
    except Exception as e:  # noqa: BLE001 - only the prompt matters here
        say(f"   (verify raised {type(e).__name__}: {e})")
    vp = next((x for x in fm.prompts if "Source [" in x), "")
    sample("writer-verify-prompt.txt", vp[:6000] + "\n")
    check("citation check: the Qwen page's block says OTHER ENGINE, the DeepSeek doc's does not",
          f"Source [{mg.idx}]" in vp and "OTHER ENGINE: this page describes" in vp.split(f"Source [{mg.idx}]")[1][:600]
          and "OTHER ENGINE" not in vp.split(f"Source [{ds.idx}]")[1][:400] if f"Source [{ds.idx}]" in vp else False)
    # the same section with the installed writer and no engine named: identical prompts (nothing changes)
    no_eng = "How can I make Strata v0.2.4 faster on my PC (RTX 5080 + RTX 4060 Ti)? Settings only."
    prompts = []
    for mod in (M.report, M.report0):
        st = store_from_run(M, no_eng)
        fm = FakeModel()
        ww = mod.ReportWriter(no_eng, st, fm, lead)
        ww.section({"heading": "Two GPUs", "purpose": "split", "sources": ids}, "(outline)",
                   {s.idx: s for s in st.all_sources()})
        prompts.append((ww.p_section, fm.prompts[-1], ww._digest([x for x in st.all_sources() if x.page_text][:400], 60000)))
    check("writer with no engine named: section rules, section prompt and outline digest identical to installed",
          prompts[0] == prompts[1])
    os.environ["LDR_DEEP_FIX"] = FIXES_NO_VERSION
    try:
        prompts = []
        for mod in (M.report, M.report0):
            st = store_from_run(M, Q)
            fm = FakeModel()
            ww = mod.ReportWriter(Q, st, fm, lead)
            ww.section({"heading": "Two GPUs", "purpose": "split", "sources": ids}, "(outline)",
                       {s.idx: s for s in st.all_sources()})
            prompts.append((ww.p_section, fm.prompts[-1]))
        check("writer with LDR_DEEP_FIX lacking 'version': identical to installed (switch off)", prompts[0] == prompts[1])
    finally:
        os.environ["LDR_DEEP_FIX"] = FIXES
    return store


def t_strategy(M, Q):
    """The strategy's two edits without importing the strategy (it pulls in all of LDR): the search-title helper is
    compiled from the staged file on its own; the prompt-rule lines are checked in the source."""
    say("\n== 9. the strategy: search-result titles and the lead / subagent rule line")
    import ast
    import textwrap
    src = (V["strategy"] / "langgraph_agent_strategy.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_deep_engine_titles")
    code = textwrap.dedent(ast.get_source_segment(src, fn)).replace("from ...deep import enginescope as _es",
                                                                      "_es = ENGINESCOPE")
    from typing import Any
    from loguru import logger
    ns = {"Any": Any, "logger": logger, "ENGINESCOPE": M.es}
    exec(compile(code, "staged-strategy:_deep_engine_titles", "exec"), ns)
    res = [{"index": "1", "title": "generate.cpp", "link": "https://github.com/Niko1221/Strata/blob/v0.2.4/src/program/generate.cpp",
            "snippet": "--trim-stage-weights needs a layer split"},
           {"index": "2", "title": "QWEN36.md", "link": "https://github.com/Niko1221/Strata/blob/main/docs/QWEN36.md",
            "snippet": "Qwen3.6"},
           {"index": "3", "title": "DEEPSEEK41.md", "link": "https://github.com/Niko1221/Strata/blob/v0.2.4/docs/DEEPSEEK41.md",
            "snippet": "DeepSeek-V4.1-Flash"},
           {"index": "4", "title": "Strata on Reddit: Qwen3.8-Flash-Next MTP on a 5080",
            "link": "https://www.reddit.com/r/LocalLLaMA/comments/x/strata", "snippet": "Strata with Qwen3.8 and --mtp, Swift 1.5, Gyro-S"},
           {"index": "5", "title": "llama.cpp Qwen3.8 offload", "link": "https://github.com/ggml-org/llama.cpp/issues/1",
            "snippet": "Qwen3.8-Flash-Next --n-cpu-moe Qwen MTP"}]
    st = SimpleNamespace(query=Q)
    out = ns["_deep_engine_titles"](st, [dict(r) for r in res])
    marked = [r["index"] for r in out if r["title"].startswith("[OTHER ENGINE")]
    say("   " + " | ".join(r["title"][:70] for r in out))
    check("search titles: Qwen engine code / doc file / a Strata page about Qwen marked; DeepSeek doc and llama.cpp not",
          marked == ["1", "2", "4"], marked)
    check("search titles: the inputs are not changed (the collector keeps plain titles)",
          [r["title"] for r in res] == ["generate.cpp", "QWEN36.md", "DEEPSEEK41.md",
                                        "Strata on Reddit: Qwen3.8-Flash-Next MTP on a 5080", "llama.cpp Qwen3.8 offload"])
    out2 = ns["_deep_engine_titles"](SimpleNamespace(query="How fast is Strata v0.2.4 on my PC?"), [dict(r) for r in res])
    check("search titles: unchanged with no engine named", [r["title"] for r in out2] == [r["title"] for r in res])
    check("strategy: the rule line goes into the lead's system prompt and the subagents' prompt",
          "system_prompt += _deep_engine_rule(self.deep_store)" in src
          and "subagent_prompt = _DEEP_SUBAGENT_PROMPT.format(date=current_date) + _deep_engine_rule(" in src
          and "indexed = _deep_engine_titles(_store, indexed)" in src)


def t_names(M, Q, src):
    es = M.es
    say("\n== 8. the 7 wrong names: in which sources the research saw them, and would those be labelled")
    store, lab = verdicts_on_evidence(M, Q, src)
    # the lead's / agents' code searches at v0.2.4 (code-tool.jsonl), replayed on the local tree with the staged tool
    tools, _ = make_code_tools(M, M.codetool, Q)
    greps = []
    for line in (RUN / "deep/code-tool.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d.get("tool") == "grep" and d.get("ref") == "v0.2.4" and "strata" in str(d.get("repo", "")).lower():
            greps.append(d)
    grep_out = {}
    for d in greps:
        key = (d["pattern"], d.get("path") or ".", d.get("glob") or "")
        if key in grep_out:
            continue
        grep_out[key] = tools["code_search"].func(repo="Niko1221/Strata@v0.2.4", pattern=d["pattern"],
                                                  path="" if key[1] == "." else key[1], file_glob=key[2])
    rows, only = [], 0
    for n in NAMES:
        reads, read_lab = [], []
        for idx, s in src.items():
            if not s.page_text or (n not in s.page_text and not any(n in e for e in s.ex)):
                continue
            v = lab.get(idx, (None, ""))[0]
            if v is not None and v.parts:
                occ = [num for num, t in es.lines_of(s.page_text) if n in t]
                ok = bool(occ) and all(v.part_at(o) for o in occ)
            else:
                ok = v is not None and bool(v.engine)
            reads.append(idx)
            read_lab.append(ok)
        snip = [i for i, s in src.items() if any(n in x for x in s.snippets)]
        snip_lab = [es.search_title(store, src[i].url, src[i].title, " ".join(src[i].snippets)) != src[i].title
                    for i in snip]
        hl = [ln for out in grep_out.values() for ln in out.splitlines() if re.match(r"^[\w./-]+:\d+: ", ln) and n in ln]
        hl_lab = ["[OTHER ENGINE: " in ln for ln in hl]
        all_lab = read_lab + snip_lab + hl_lab
        only_read = bool(read_lab) and all(read_lab) and not snip
        only_all = bool(all_lab) and all(all_lab)
        only += only_read
        unl = [src[i].url for i, ok in zip(reads, read_lab) if not ok] + \
            sorted({ln.split(":")[0] for ln, ok in zip(hl, hl_lab) if not ok})
        rows.append({"name": n, "read_sources": len(reads), "read_labelled": sum(read_lab), "snippets": len(snip),
                     "snippets_labelled": sum(snip_lab), "grep_hit_lines": len(hl), "grep_labelled": sum(hl_lab),
                     "only_in_labelled_reads": only_read, "only_in_labelled_incl_grep": only_all, "unlabelled_in": unl[:8]})
        say(f"   {n:24s} reads {sum(read_lab)}/{len(reads)} labelled, snippets {sum(snip_lab)}/{len(snip)}, "
            f"code-search hit lines {sum(hl_lab)}/{len(hl)}; only labelled: reads {'YES' if only_read else 'no'}, "
            f"with search hits {'YES' if only_all else 'no'}" + (f"; unlabelled in: {', '.join(unl[:4])}" if unl else ""))
    OUT["shown"]["names"] = rows
    OUT["shown"]["names_only_labelled_reads"] = only
    OUT["shown"]["names_only_labelled_incl_grep"] = sum(r["only_in_labelled_incl_grep"] for r in rows)
    say(f"   => {only} of 7 appear ONLY in read sources that would be labelled; "
        f"{OUT['shown']['names_only_labelled_incl_grep']} of 7 counting the code-search hit lines too")
    check("at least the 4 names from MULTI_GPU.md / the 5080 bench are only in labelled reads", only >= 4, rows)


def main() -> int:
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--variant", default="installed", choices=sorted(VARIANTS))
    ARGS = ap.parse_args()
    ARGS.out = ARGS.out or (ST / "tests" / ("" if ARGS.variant == "installed" else "variant-c3"))
    OUT["variant"] = ARGS.variant
    say(f"variant: {ARGS.variant} (staged files from {V['path'][0]}; compared with {V['base_report'].parent})")
    t0 = time.time()
    ensure_clone()
    M = load_modules()
    Q = QFILE.read_text(encoding="utf-8")
    src = evidence_sources()
    t_scopes(M, Q)
    t_paths(M)
    t_versions(M)
    t_evidence(M, Q, src)
    t_sections(M, Q, src)
    t_fetch(M, Q)
    t_codetool(M, Q)
    t_writer(M, Q, src)
    t_names(M, Q, src)
    t_strategy(M, Q)
    fails = [c for c in OUT["checks"] if not c["ok"]]
    say(f"\n{len(OUT['checks']) - len(fails)} of {len(OUT['checks'])} checks pass ({time.time() - t0:.0f} s)")
    OUT["seconds"] = round(time.time() - t0, 1)
    ARGS.out.mkdir(parents=True, exist_ok=True)
    (ARGS.out / "results.json").write_text(json.dumps(OUT, indent=1, default=str), encoding="utf-8")
    (ARGS.out / "test-output.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
