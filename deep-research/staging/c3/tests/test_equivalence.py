#!/usr/bin/env python3
"""test_equivalence.py - C3b / C3c offline equivalence test (no model calls, no services, no GPU).

The staged copy (staging/c3) against the package and launcher as installed, each imported in its own process
(probe.py), at nice 19:
  1. static: both profiles parse with no unknown keys; flash-next.env resolves to exactly the built-in defaults; the
     staged DeepConfig defaults equal the loader's; every *.orig equals the installed file (the diff is against what is
     installed now); the strategy's only change is the two fair-share literals.
  2. run-ldr.sh: the environment ldr_env() exports (old script vs staged script with profiles/flash-next.env), for
     several caller environments - identical except the one new variable LDR_DEEP_MODEL_PROFILE.
  3. the deep package: every config field, module constant and tool description both see, plus traces of the code
     paths that use the sizes (report stage in three modes, compaction, the context guard, the token counter, the
     effort ladder, the seeded continuation, the tried list, the code tool) - every prompt (hash + length) and every
     max_tokens / effort the fake model receives must be identical. Scenarios: no profile, flash-next.env through
     run-ldr.sh, LDR_DEEP_CONTEXT=131072, LDR_DEEP_CONTEXT_TOKENS=131072, bench2-like and Jan-like overrides.
  4. the research runner: DEEP_EFFORTS / DEEP_LDR_EFFORTS / DEEP_LDR_EFFORTS_FILE / QUICK_CAP_S identical.
  5. shown, not asserted: what changes at 262,144 tokens, and the Sonnet 5.5 draft's values.

  .venv/bin/python -I -B staging/c3/tests/test_equivalence.py [--quick] [--out DIR]
Writes results.json + results.md to --out (default staging/c3/tests/results). Exit 0 = every assertion holds.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
PY = WS / ".venv/bin/python"
PKG = WS / ".venv/lib/python3.12/site-packages/local_deep_research"
ST = WS / "staging/c3"
PROBE = ST / "tests/probe.py"
FLASH = ST / "profiles/flash-next.env"
SONNET = ST / "profiles/sonnet-5-5.env"
DROP = {"seconds", "trace_seconds", "deep_file", "pkg", "meta"}

ORIGS = {  # staged file -> installed file
    "deep/__init__.py": "deep/__init__.py", "deep/middleware.py": "deep/middleware.py",
    "deep/tokens.py": "deep/tokens.py", "deep/llm.py": "deep/llm.py", "deep/report.py": "deep/report.py",
    "deep/claims.py": "deep/claims.py", "deep/reading.py": "deep/reading.py", "deep/seed.py": "deep/seed.py",
    "deep/tried.py": "deep/tried.py", "deep/codetool.py": "deep/codetool.py", "deep/advisory.py": "deep/advisory.py",
    "strategies/langgraph_agent_strategy.py": "advanced_search_system/strategies/langgraph_agent_strategy.py",
}
LIVE = {"run-ldr.sh": WS / "run-ldr.sh", "tools/research-runner.py": WS / "tools/research-runner.py"}

results: dict = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": [], "shown": {}}


def check(name: str, ok: bool, detail=None) -> bool:
    results["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {str(detail)[:300]}" if detail and not ok else ""))
    return ok


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def diff(a, b, path: str = "", out: list | None = None, limit: int = 40) -> list:
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k in DROP:
                continue
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'staged' if k not in a else 'installed'}")
            else:
                diff(a[k], b[k], f"{path}/{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: {len(a)} vs {len(b)} items")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {str(a)[:120]!r} != {str(b)[:120]!r}")
    return out


# ------------------------------------------------------------------------------------------------ environments
def base_env(scratch: Path) -> dict:
    return {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "/home/USER"), "LANG": "C.UTF-8"}


def safety(env: dict, scratch: Path) -> dict:
    """Same on both sides: nothing a probe does lands outside the scratch folder."""
    e = dict(env)
    for k in ("TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "HF_HOME", "MPLCONFIGDIR", "NLTK_DATA",
              "TIKTOKEN_CACHE_DIR", "TORCH_HOME", "PIP_CACHE_DIR"):
        e[k] = str(scratch / "env" / k.lower())
        Path(e[k]).mkdir(parents=True, exist_ok=True)
    e.update(LDR_DEEP_OUT_DIR=str(scratch / "out"), LDR_DEEP_CLOCK_FILE=str(scratch / "clock.json"),
             LDR_DEEP_NEXT_FILE=str(scratch / "next.json"), LDR_DEEP_CODE_DIR=str(scratch / "code"),
             LDR_DEEP_TRIED_DIR=str(scratch / "tried"), LDR_DEEP_NOTYET_SEARX="http://127.0.0.1:9",
             PYTHONDONTWRITEBYTECODE="1")
    return e


BASH_DRIVER = r"""
set -euo pipefail
src=$1; mode=$2
source <(sed '/^case \${1:-} in$/,$d' "$src")
if [[ $mode == new ]]; then DEEP_PKG=$C3_STAGED_DEEP; model_profile; fi
ldr_env probe-model
env -0
"""


def ldr_env(script: Path, mode: str, extra: dict, scratch: Path) -> tuple[int, dict, str]:
    env = {**base_env(scratch), **extra, "C3_STAGED_DEEP": str(ST / "deep")}
    if mode == "new":
        env.setdefault("LDR_MODEL_PROFILE", str(FLASH))
    r = subprocess.run(["nice", "-n", "19", "bash", "-c", BASH_DRIVER, "driver", str(script), mode], env=env,
                       capture_output=True, timeout=120)
    out = {}
    for item in r.stdout.split(b"\0"):
        if b"=" in item:
            k, _, v = item.decode().partition("=")
            out[k] = v
    for k in ("C3_STAGED_DEEP", "SHLVL", "_", "PWD", "OLDPWD", "LDR_MODEL_PROFILE"):
        out.pop(k, None)
    return r.returncode, out, r.stderr.decode()[-500:]


def probe(pkg: str, env: dict, scratch: Path, traces: bool) -> dict:
    cmd = ["nice", "-n", "19", str(PY), "-I", "-B", str(PROBE), "--pkg", pkg, "--scratch", str(scratch / "probe")]
    if traces:
        cmd.append("--traces")
    r = subprocess.run(cmd, env=env, capture_output=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"probe {pkg} failed:\n{r.stderr.decode()[-3000:]}")
    return json.loads(r.stdout)


def load_mp():
    spec = importlib.util.spec_from_file_location("c3_modelprofile", ST / "deep/modelprofile.py")
    mp = importlib.util.module_from_spec(spec)
    sys.modules["c3_modelprofile"] = mp
    spec.loader.exec_module(mp)
    return mp


# ------------------------------------------------------------------------------------------------ the parts
def part_static(mp) -> None:
    for p in (FLASH, SONNET):
        check(f"profile parses, known keys only: {p.name}", not mp.check_profile(p), mp.check_profile(p))
    d0 = mp.resolve(env={}, profile="").values
    d1 = mp.resolve(env={}, profile=str(FLASH)).values
    dd = {k: (d0[k], d1[k]) for k in d0 if d0[k] != d1[k]}
    check("flash-next.env = the built-in defaults (all but the tokenizer path run-ldr.sh exported before)",
          set(dd) == {"tokenizer_dir", "profile_model"} and d1["tokenizer_dir"] == str(WS / "deep/tokenizer"), dd)
    keys_in_flash = set(mp.read_profile(FLASH))
    missing = sorted(s.key for s in mp.ALL_SPECS if s.key not in keys_in_flash and s.group != "switch"
                     and s.key not in ("LDR_PROMPT_CACHING",))
    check("flash-next.env lists every model setting", not missing, missing)
    for staged, inst in ORIGS.items():
        o = ST / (staged + ".orig")
        check(f".orig = installed now: {staged}", sha_file(o) == sha_file(PKG / inst))
    for staged, live in LIVE.items():
        check(f".orig = live now: {staged}", sha_file(ST / (staged + ".orig")) == sha_file(live))
    s = (ST / "strategies/langgraph_agent_strategy.py").read_text()
    s = s.replace("                # (0.75 and the 60 s below: LDR_DEEP_SUBAGENT_SHARE / _MIN_START_S of the model "
                  "profile, C3b 10-29)\n", "")
    s = s.replace("_DEEP.subagent_share", "0.75").replace("_DEEP.subagent_min_start_s", "60")
    check("strategy: only the fair-share 0.75 / 60 s literals changed",
          s == (ST / "strategies/langgraph_agent_strategy.py.orig").read_text())
    for f in sorted((ST / "deep").glob("*.py")):
        r = subprocess.run([str(PY), "-I", "-B", "-c", f"import ast,sys; ast.parse(open(sys.argv[1]).read())", str(f)],
                           capture_output=True)
        check(f"parses: deep/{f.name}", r.returncode == 0, r.stderr.decode()[-300:])
    r = subprocess.run(["bash", "-n", str(ST / "run-ldr.sh")], capture_output=True)
    check("bash -n run-ldr.sh", r.returncode == 0, r.stderr.decode())
    # codetool stays loadable straight from its file (tools/code-mcp.py does that), with the loader next to it
    code = ("import importlib.util as u,sys; s=u.spec_from_file_location('codetool', sys.argv[1]); m=u.module_from_spec(s);"
            " s.loader.exec_module(m); print(m.READ_LINES, m.GREP_HITS, m.TREE_ENTRIES, m.ISSUE_CHARS, m.SHORT_READS)")
    r = subprocess.run([str(PY), "-I", "-B", "-c", code, str(ST / "deep/codetool.py")], capture_output=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "")})
    check("codetool.py loads standalone (code-mcp.py), today's sizes", r.stdout.decode().split() ==
          ["120", "40", "200", "3000", "True"], (r.stdout + r.stderr).decode()[-400:])


def part_runldr(scratch: Path) -> dict:
    envs = {}
    scen = {
        "deep (default)": {},
        "deep + bench2-like overrides": {"LDR_DEEP_REPORT_EFFORT": "medium", "LDR_DEEP_VERIFY_EFFORT": "xhigh",
                                         "LDR_DEEP_FIX": "all,read,claims", "LDR_DEEP_CRITIC": "1",
                                         "LDR_DEEP_CODE": "1", "LDR_WORKERS": "2", "LDR_TEMPERATURE": "0.7",
                                         "LDR_DEEP_TIME_BUDGET_S": "2820"},
        "deep + Jan-like (S2, fallback, setup + critic)": {"LDR_RESEARCH_S2": "1", "LDR_SEARCH_FALLBACK": "1",
                                                           "LDR_DEEP_SETUP_PROFILE": str(WS / "user-setup.md"),
                                                           "LDR_DEEP_CRITIC": "1", "LDR_DEEP_REPORT_EFFORT": "medium",
                                                           "LDR_DEEP_VERIFY_EFFORT": "xhigh",
                                                           "LDR_DEEP_VERIFY_MAX_CLAIMS": "120"},
        "baseline profile, quick limits": {"LDR_PROFILE": "baseline", "LDR_QUICK_LIMITS": "1"},
        "deep, LDR_VIA_PROXY=0": {"LDR_VIA_PROXY": "0"},
    }
    for name, extra in scen.items():
        rc_o, old, err_o = ldr_env(ST / "run-ldr.sh.orig", "old", extra, scratch)
        rc_n, new, err_n = ldr_env(ST / "run-ldr.sh", "new", extra, scratch)
        added = {k: new[k] for k in set(new) - set(old)}
        expect = {"LDR_DEEP_MODEL_PROFILE"} if extra.get("LDR_PROFILE", "deep") == "deep" else set()
        same = {k for k in old if old.get(k) == new.get(k)}
        changed = {k: (old[k], new.get(k)) for k in old if k not in same}
        check(f"run-ldr.sh env [{name}]: identical but LDR_DEEP_MODEL_PROFILE",
              rc_o == 0 and rc_n == 0 and not changed and set(added) == expect,
              {"rc": (rc_o, rc_n), "changed": changed, "added": added, "err": err_o or err_n})
        envs[name] = (old, new)
    # shown: 262,144 through run-ldr.sh
    _, new262, _ = ldr_env(ST / "run-ldr.sh", "new", {"LDR_DEEP_CONTEXT_TOKENS": "262144"}, scratch)
    old0, new0 = envs["deep (default)"]
    results["shown"]["run-ldr.sh env at LDR_DEEP_CONTEXT_TOKENS=262144 (vs default)"] = {
        k: (new0.get(k), new262.get(k)) for k in sorted(set(new0) | set(new262)) if new0.get(k) != new262.get(k)}
    # a draft profile is refused
    env = {**base_env(scratch), "LDR_MODEL_PROFILE": str(SONNET), "C3_STAGED_DEEP": str(ST / "deep")}
    r = subprocess.run(["bash", "-c", BASH_DRIVER, "driver", str(ST / "run-ldr.sh"), "new"], env=env,
                       capture_output=True, timeout=60)
    check("run-ldr.sh refuses the draft Sonnet profile", r.returncode != 0 and b"draft" in r.stderr,
          r.stderr.decode()[-300:])
    env["LDR_MODEL_PROFILE"] = str(ST / "profiles/no-such.env")
    r = subprocess.run(["bash", "-c", BASH_DRIVER, "driver", str(ST / "run-ldr.sh"), "new"], env=env,
                       capture_output=True, timeout=60)
    check("run-ldr.sh refuses a missing profile", r.returncode != 0, r.stderr.decode()[-300:])
    return envs


def part_package(envs: dict, scratch: Path, quick: bool) -> None:
    base = {**base_env(scratch), "LDR_DEEP": "1"}
    old0, new0 = envs["deep (default)"]
    oldb, newb = envs["deep + bench2-like overrides"]
    oldj, newj = envs["deep + Jan-like (S2, fallback, setup + critic)"]
    nosetup = {"LDR_DEEP_SETUP_PROFILE": None}            # the setup check would read user-setup.md: not here
    scen = [
        # name, installed env, staged env, traces
        ("no profile", base, base, True),
        ("flash-next.env through run-ldr.sh", old0, new0, not quick),
        ("LDR_DEEP_CONTEXT=131072", base, {**base, "LDR_DEEP_CONTEXT": "131072"}, not quick),
        ("LDR_DEEP_CONTEXT_TOKENS=131072", {**base, "LDR_DEEP_CONTEXT_TOKENS": "131072"},
         {**base, "LDR_DEEP_CONTEXT_TOKENS": "131072"}, False),
        ("items read+claims (classic report path)", {**base, "LDR_DEEP_FIX": "read,claims"},
         {**base, "LDR_DEEP_FIX": "read,claims"}, True),
        ("bench2-like through run-ldr.sh (fixes all + items, critic, verify2)",
         {**oldb, "LDR_DEEP_VERIFY2": "flag"}, {**newb, "LDR_DEEP_VERIFY2": "flag"}, True),
        ("Jan-like through run-ldr.sh", {**oldj, **nosetup}, {**newj, **nosetup}, False),
    ]
    staged_ref = None
    for name, ei, es, traces in scen:
        ei = safety({k: v for k, v in ei.items() if v is not None}, scratch)
        es = safety({k: v for k, v in es.items() if v is not None}, scratch)
        t0 = time.time()
        a, b = probe("installed", ei, scratch, traces), probe("staged", es, scratch, traces)
        common = {k: v for k, v in b["config"].items() if k in a["config"]}
        d = diff({**a, "config": a["config"]}, {**b, "config": common})
        new_fields = {k: v for k, v in b["config"].items() if k not in a["config"]}
        check(f"package [{name}]: config, constants{', traces' if traces else ''} identical "
              f"({round(time.time() - t0)} s)", not d, d[:12])
        if traces:
            r = b["traces"]["report"]
            results["shown"].setdefault("trace coverage", {})[name] = {
                "report calls": r["n_calls"], "report call kinds max_tokens": sorted({c["kw"].get("max_tokens")
                                                                                      for c in r["calls"]}),
                "middleware": {k: v.get("compactions", v.get("shortened"))
                               for k, v in b["traces"]["middleware"].items()},
                "verify batches": r.get("verify_batches"), "claims on one source (max)": r.get("claims_per_source_max"),
                "tokenizer": b["traces"]["tokens"]["tokenizer"], "trace_s": (a.get("trace_seconds"),
                                                                             b.get("trace_seconds"))}
        if b["meta"].get("profile_errors"):
            check(f"package [{name}]: no profile errors", False, b["meta"]["profile_errors"])
        if name == "flash-next.env through run-ldr.sh":
            staged_ref = (es, b)
            results["shown"]["new config fields (staged only) = the old literals"] = new_fields
            results["shown"]["where each value came from (flash-next via run-ldr.sh)"] = b["meta"]["sources"]
    if staged_ref is None:                     # --quick: the reference without traces
        es = safety(new0, scratch)
        staged_ref = (es, probe("staged", es, scratch, False))
    es, ref = staged_ref
    # shown: 262,144 and the Sonnet draft (staged only; not asserted)
    for label, extra in (("context 262144", {"LDR_DEEP_CONTEXT_TOKENS": "262144"}),
                         ("sonnet-5-5.env (draft)", {"LDR_DEEP_MODEL_PROFILE": str(SONNET),
                                                     "LDR_DEEP_TOKENIZER_DIR": ""})):
        # 262144 through run-ldr.sh's environment; the Sonnet draft on its own (run-ldr.sh's Flash-Next exports, e.g.
        # LDR_LLM_MAX_TOKENS=30000, would mask the profile's values)
        e2 = {**es, **extra} if "262144" in label else safety({**base_env(scratch), "LDR_DEEP": "1", **extra}, scratch)
        b = probe("staged", e2, scratch, False)
        changed = {k: (ref["config"][k], v) for k, v in b["config"].items() if ref["config"].get(k) != v}
        cchanged = {k: (ref["constants"][k], v) for k, v in b["constants"].items()
                    if k != "codetool.tool_descriptions" and ref["constants"].get(k) != v}
        tdesc = [k for k, v in b["constants"]["codetool.tool_descriptions"].items()
                 if ref["constants"]["codetool.tool_descriptions"].get(k) != v]
        results["shown"][f"changes at {label} (vs flash-next)"] = {"config": changed, "constants": cchanged,
                                                                    "tool descriptions changed": tdesc}


NEGATIVE = (  # (variable, a value that crosses a boundary of the synthetic data: a 1-unit step of a
              # 48K budget moves no 233-token paragraph, so some steps are larger)
    ("LDR_DEEP_REPORT_FINDINGS_TOKENS", "12001"), ("LDR_DEEP_SECTION_EXTRACT_FRAC", "0.3"),
    ("LDR_DEEP_OUTLINE_LEAD_TOKENS", "9999"), ("LDR_DEEP_OUTLINE_FINDINGS_FRAC", "0.41"),
    ("LDR_DEEP_REPORT_EVIDENCE_TOKENS", "40000"), ("LDR_DEEP_VERIFY_BATCH_TOKENS", "30000"),
    ("LDR_DEEP_VERIFY_BATCH_CLAIMS", "7"), ("LDR_DEEP_VERIFY_CLAIM_SOURCE_TOKENS", "1500"),
    ("LDR_DEEP_REPORT_MAX_OUTPUT", "59999"), ("LDR_DEEP_REPORT_MARGIN", "1025"),
    ("LDR_DEEP_CLAIMS_PER_SOURCE", "39"), ("LDR_DEEP_READ_PASSAGE_TOKENS", "200"),
    ("LDR_DEEP_TOKEN_MARGIN", "513"), ("LDR_DEEP_COMPACT_AT", "30000"), ("LDR_DEEP_KEEP_RECENT_FRAC", "0.1"),
    ("LDR_DEEP_COMPACT_FALLBACK_TOKENS", "11999"), ("LDR_DEEP_TOK_MSG_OVERHEAD", "9"),
    ("LDR_DEEP_TOK_TOOLS_OVERHEAD", "151"), ("LDR_DEEP_TOK_CHARS_PER_TOKEN", "4"),
    ("LDR_DEEP_SEED_TEXT_CHARS", "59999"), ("LDR_DEEP_TRIED_PART_CHARS", "59999"),
    ("LDR_DEEP_TRIED_BLOCK_CHARS", "35999"), ("LDR_DEEP_TRIED_MAP_EFFORT", "medium"),
    ("LDR_DEEP_CODE_READ_LINES", "121"), ("LDR_DEEP_CODE_GREP_HITS", "41"), ("LDR_DEEP_CODE_TREE_ENTRIES", "199"),
    ("LDR_DEEP_CODE_LINE_CHARS", "239"), ("LDR_DEEP_CODE_ISSUE_CHARS", "2999"),
    ("LDR_DEEP_CODE_COMMENT_CHARS", "1499"), ("LDR_DEEP_CODE_ISSUE_LIST_CHARS", "599"),
    ("LDR_DEEP_CODE_SHORT_READS", "0"), ("LDR_DEEP_READ_PRIMARY_PER_PAGE", "3"),
    ("LDR_DEEP_EFFORT_MAP", "xhigh=high"), ("LDR_DEEP_EFFORT_LADDER", "same"), ("LDR_DEEP_CONTEXT", "131073"),
)


def part_negative(scratch: Path) -> None:
    """The test must see a small change of each routed setting in what the code DOES (traces, module constants) -
    not only in the config dump - else a pass would prove nothing. Run on the items path (claims + reader)."""
    base = safety({**base_env(scratch), "LDR_DEEP": "1", "LDR_DEEP_FIX": "read,claims"}, scratch)
    a = probe("installed", base, scratch, True)
    for k, v in NEGATIVE:
        b = probe("staged", {**base, k: v}, scratch, True)
        d = diff({**a, "config": a["config"]}, {**b, "config": {x: y for x, y in b["config"].items()
                                                                if x in a["config"]}})
        seen = [x for x in d if x.startswith(("/traces", "/constants"))]
        check(f"negative control: {k}={v} changes what the code does", bool(seen),
              d[:3] or "no difference found")
        results["shown"].setdefault("negative controls: first differences", {})[f"{k}={v}"] = seen[:3]


def part_runner(scratch: Path) -> None:
    for label, prof in (("flash-next.env", str(FLASH)), ("no profile file", str(scratch / "missing.env"))):
        env = {**base_env(scratch), "LDR_MODEL_PROFILE": prof}
        outs = []
        for path in (ST / "tools/research-runner.py.orig", ST / "tools/research-runner.py"):
            r = subprocess.run(["nice", "-n", "19", str(PY), "-I", "-B", str(PROBE), "--pkg", "installed", "--runner",
                                str(path), "--scratch", str(scratch / "probe")], env=env, capture_output=True,
                               timeout=120)
            outs.append(json.loads(r.stdout)["runner"] if r.returncode == 0 else {"error": r.stderr.decode()[-500:]})
        check(f"research runner settings identical [{label}]", outs[0] == outs[1], diff(outs[0], outs[1]))
    results["shown"]["research runner (staged, flash-next)"] = outs[1]


def write(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=1, default=str, ensure_ascii=False))
    n_ok = sum(c["ok"] for c in results["checks"])
    lines = [f"# C3 equivalence test - {results['started']}", "",
             f"**{n_ok} / {len(results['checks'])} checks pass.**", "", "| check | result |", "|---|---|"]
    lines += [f"| {c['check']} | {'pass' if c['ok'] else 'FAIL: ' + str(c['detail'])[:200]} |" for c in results["checks"]]
    for k, v in results["shown"].items():
        lines += ["", f"## {k} (shown, not asserted)", "", "```", json.dumps(v, indent=1, default=str)[:12000], "```"]
    (out / "results.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="traces only in the no-profile scenario")
    ap.add_argument("--out", default=str(ST / "tests/results"))
    ap.add_argument("--scratch", default=None, help="scratch folder (default: a new temp folder)")
    a = ap.parse_args()
    scratch = Path(a.scratch or tempfile.mkdtemp(prefix="c3-equiv-"))
    scratch.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    mp = load_mp()
    part_static(mp)
    envs = part_runldr(scratch)
    part_package(envs, scratch, a.quick)
    if not a.quick:
        part_negative(scratch)
    part_runner(scratch)
    results["seconds"] = round(time.time() - t0)
    write(Path(a.out))
    bad = [c["check"] for c in results["checks"] if not c["ok"]]
    print(f"\n{len(results['checks']) - len(bad)} / {len(results['checks'])} checks pass in {results['seconds']} s"
          f"; results in {a.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
