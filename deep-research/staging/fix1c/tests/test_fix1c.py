#!/usr/bin/env python3
"""Fix 1c offline test (no model, no GPU, no network): the Fix 1b replays' recorded engine-folder answers given back by a
fake model, the staged checks.py (staging/fix1c/deep/checks.py = the installed Fix 1b + K4 checks.py + Fix 1c) and the
staged engine map (staging/fix1c/deep/enginescope.py + engines/strata.json, copies of staging/enginescope's) against the
Strata code at the replay's version (staging/fix1b/scratch/<tag>, git archives of the local clone).

Checks:
  * the map settle: b-f1b-jan1024's two answers (one took src/core, src/prefill, ... as the DeepSeek engine's) give the
    DeepSeek engine's folders, nothing disputed, src/core / src/program as the Qwen engine's; a project or version the
    map does not cover (or a task naming no engine) keeps the model's answers unchanged;
  * the 25 right marks Fix 1b lost through the folder answer (18 "unsure" from a disputed folder, 7 "this version"):
    none is unsettled any more, and each one whose hits sit in Qwen folders gets the "In the Qwen engine's folders" line;
  * the 7 lost through "attributed" (b-f1b-fixes): the report text does not attribute them in every sentence, so they
    go back to "described"; every other name the five replays' model called attributed is listed (new marks to judge);
  * a name the model's answer leaves out is asked once more;
  * the 11 false marks Fix 1b cleared: their evidence still has Fix 1b's launcher / server lines.

  nice -n 19 .venv/bin/python -I staging/fix1c/tests/test_fix1c.py   (writes tests/test-output.txt; exit 1 on a failure)
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
ST = WS / "staging" / "fix1c"
SCR = WS / "staging" / "fix1b" / "scratch"
REPLAYS = WS / "results" / "bench2" / "fixes" / "replays"
QUESTION = (WS / "results" / "bench2" / "codetool" / "question.txt").read_text(encoding="utf-8")

from local_deep_research.deep import codetool  # noqa: E402

for name, path in (("enginescope", ST / "deep" / "enginescope.py"), ("checks_fix1c", ST / "deep" / "checks.py")):
    spec = importlib.util.spec_from_file_location(f"local_deep_research.deep.{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
new = sys.modules["local_deep_research.deep.checks_fix1c"]
es = sys.modules["local_deep_research.deep.enginescope"]

FAILS: list[str] = []


def check(ok: bool, what: str) -> bool:
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        FAILS.append(what)
    return ok


def fake_llm(rec: dict, prompts: list[str], drop: str | None = None):
    answers = list(rec["answers"])
    calls = {"n": 0}

    def llm(prompt: str) -> str:
        if "<layout repo=" in prompt:
            i = min(calls["n"], len(answers) - 1)
            calls["n"] += 1
            return json.dumps({"dirs": answers[i], "shared": rec.get("shared") or [], "why": "recorded"})
        prompts.append(prompt)
        if drop is None:
            return ""
        # an answer naming every item but `drop` (the missing-name retry)
        names = [it.split("\n", 1)[0][4:] for it in re.split(r"\n\n(?=### )", prompt.split("<settings>\n", 1)[1])]
        return "\n".join(json.dumps({"name": n.strip('"'), "kind": "this-version", "use": "described"})
                         for n in names if n.strip('"') != drop)
    return llm


def items_of(prompts: list[str]) -> dict[str, str]:
    out = {}
    for p in prompts:
        body = p.split("<settings>\n", 1)[1].rsplit("\n</settings>", 1)[0]
        for it in re.split(r"\n\n(?=### )", body):
            out[it.split("\n", 1)[0][4:]] = it
    return out


def evidence(label: str, ver: str, task: str):
    vc = json.loads((REPLAYS / label / "versioncheck.json").read_text())
    rec = next(iter(vc["engine_dirs"].values()))
    body = (REPLAYS / label / "input.md").read_text(encoding="utf-8")
    repo = codetool.Repo("Niko1221/Strata", ver, SCR / ver)
    prompts: list[str] = []
    r = new.version_check(fake_llm(rec, prompts), task, body, None, code=[repo], pins={"Strata": ver})
    return vc, rec, body, repo, r, items_of(prompts)


def item(items: dict, name: str) -> str:
    return items.get(name) or items.get(f'"{name}"') or ""


def lost_marks() -> list[tuple[str, str]]:
    out, cur = [], None
    for line in (WS / "results" / "bench2" / "fixes" / "fix1b-compare.txt").read_text().splitlines():
        m = re.match(r"== (\S+) \(was", line)
        if m:
            cur = m.group(1)
        m = re.match(r"\s+right lost: (\S+) \(", line)
        if m:
            out.append((cur, m.group(1)))
    return out


def main() -> int:
    lost = lost_marks()
    check(len(lost) == 33, f"33 lost right marks read from fix1b-compare.txt ({len(lost)})")

    print("== the map settle")
    vc, rec, body, repo, r, items = evidence("b-f1b-jan1024", "v0.2.4", QUESTION)
    e = r["engine_dirs"]["Niko1221/Strata"]
    check(any("src/core" in d for a in rec["answers"] for d in a), "b-f1b-jan1024's recorded answers name src/core")
    check(e.get("map", "").startswith("Strata v0.2.4") and e["disputed"] == [], f"map used, nothing disputed ({e.get('map')})")
    check(set(e["dirs"]) >= {"src/dsv41", "include/strata/dsv41"} and not any(d.startswith("src/core") for d in e["dirs"]),
          f"engine folders = the DeepSeek engine's ({e['dirs']})")
    check(e["other_engines"].get("src/core") == "Qwen engine" and e["other_engines"].get("src/program") == "Qwen engine",
          "src/core and src/program are the Qwen engine's at v0.2.4")
    check(not any(d.startswith(("src/program", "src/core")) for d in e["shared"]), f"no Qwen folder left as shared ({e['shared']})")
    plain = {"dirs": ["a"], "shared": ["b"], "disputed": ["c"]}
    other = codetool.Repo("ggml-org/llama.cpp", "b1", SCR / "v0.2.4")
    check(new._map_dirs(other, QUESTION, {"llama.cpp": "b1"}, plain) is plain, "a project the map does not cover: unchanged")
    check(new._map_dirs(repo, "(task)", {"Strata": "v0.2.4"}, plain) is plain, "a task naming no engine: unchanged")
    check(new._map_dirs(codetool.Repo("Niko1221/Strata", "v0.1.9", SCR / "v0.2.4"), QUESTION, {"Strata": "v0.1.9"}, plain)
          is plain, "a version below every map entry: unchanged")

    print("== the 25 marks lost through the folder answer (b-f1b-jan1024)")
    res_old = {x["name"]: x for x in vc["results"]}
    unsettled = {str(x["name"]) for x in r["results"] if x.get("kind") == "unsure" and x.get("was")}
    n_folder = 0
    for lab, n in lost:
        if lab != "b-f1b-jan1024":
            continue
        o = res_old.get(n, {})
        if not (o.get("kind") == "unsure" or o.get("kind") == "this-version"):
            continue
        n_folder += 1
        it = item(items, n)
        check(bool(it) and "Folders that may also be the engine's" not in it and n not in unsettled,
              f"{n}: sent, no disputed folder (was {o.get('kind')})")
        qwen_hit = "In the Qwen engine's folders at the user's version" in it
        no_engine = re.search(r"in the engine's own folders \([^)]*\): 0", it) is not None
        check(qwen_hit or no_engine, f"{n}: {'Qwen-folder line' if qwen_hit else 'no hit in the engine folders'}")
    check(n_folder == 25, f"25 folder-answer losses checked ({n_folder})")

    print("== the 7 marks lost through 'attributed' (b-f1b-fixes)")
    fx = (REPLAYS / "b-f1b-fixes" / "input.md").read_text(encoding="utf-8")
    pins = {"Strata": "v0.2.4"}
    fx_kind = {x["name"]: x["kind"] for x in json.loads((REPLAYS / "b-f1b-fixes" / "versioncheck.json").read_text())["results"]}
    back = 0
    for lab, n in lost:
        if lab == "b-f1b-fixes":
            same = fx_kind.get(n) in ("other-engine", "other-version")
            check(not new._attributed_in_text(n, fx, pins), f"{n}: not attributed in every sentence")
            back += same
            print(f"        {n} ({fx_kind.get(n)}): {'back to described (same project)' if same else 'stays lost (another program: the model keeps its word)'}")
    check(back == 4, f"4 of the 7 come back ({back})")
    check(new._attributed_in_text("--cache-type-q", "Use `--cache-type-q` in llama.cpp to set it.", pins),
          "a sentence naming llama.cpp stays attributed")
    check(new._attributed_in_text("--speed", "In v0.2.5 `--speed` picks 5 experts.", pins), "another release stays attributed")
    check(not new._attributed_in_text("--speed", "In v0.2.4 `--speed` picks 5 experts.", pins), "the user's own version does not attribute")

    print("== names every replay's model called attributed that Fix 1c turns back (new marks to judge)")
    flips = []
    for lab, ver in (("b-f1b-jan1024", "v0.2.4"), ("b-f1b-full", "v0.2.4"), ("b-f1b-fixes", "v0.2.4"),
                     ("b-f1b-p4s6o01-code", "v0.2.6"), ("b-f1b-p4s6o02-code", "v0.2.6")):
        v = json.loads((REPLAYS / lab / "versioncheck.json").read_text())
        b = (REPLAYS / lab / "input.md").read_text(encoding="utf-8")
        for x in v["results"]:
            if new._use(x) == "attributed" and x.get("kind") in ("other-engine", "other-version") \
                    and not new._attributed_in_text(str(x["name"]), b, {"Strata": ver}):
                flips.append((lab, x["name"], x["kind"]))
    for f in flips:
        print(f"  flip  {f[0]}: {f[1]} ({f[2]})")
    lost7 = {(lab, n) for lab, n in lost if lab == "b-f1b-fixes"}
    extra = [f for f in flips if (f[0], f[1]) not in lost7]
    print(f"  {len(flips)} flips: {len(flips) - len(extra)} of the 7 lost right marks, {len(extra)} new to judge")
    check(len(extra) <= 5, f"at most 5 new marks to judge ({len(extra)})")

    print("== a name the answer leaves out is asked once more")
    prompts: list[str] = []
    rr = new.version_check(fake_llm(rec, prompts, drop="--pcie-frac"), QUESTION, body, None, code=[repo], pins=pins)
    asked = [p for p in prompts if "### --pcie-frac" in p]
    check(len(asked) == 2 and len(prompts) == len(range(0, len(items), 40)) + 1,
          f"--pcie-frac asked twice, one extra call ({len(prompts)} calls)")

    print("== the 11 false marks Fix 1b cleared keep Fix 1b's launcher / server lines")
    for lab, names in (("b-f1b-jan1024", ["gpu", "gpu_order"]), ("b-f1b-full", ["--model", "--plan", "--tune", "--set"])):
        _vc, _rec, _b, _repo, _r, its = evidence(lab, "v0.2.4", QUESTION)
        for n in names:
            check("Launcher / server use" in item(its, n), f"{lab} {n}: launcher / server use kept")

    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
