#!/usr/bin/env python3
"""Fix 1b offline test (no model, no GPU, no network): the evidence version_check() sends for each name, built by the
installed checks.py and by the staged one (staging/fix1b/checks.py) against the Strata code at the replay's version
(git archive of the local clone at v0.2.4 / v0.2.6 in staging/fix1b/scratch/), with the engine folders each replay's
model answered (results/bench2/fixes/replays/<label>/versioncheck.json) given back by a fake model.

Checks:
  * the 11 false marks of fix1-judge (judged.jsonl): the new evidence has what the judge used - the launcher / server
    passing the value on or acting on it for DeepSeek, the long form of a short name, the CMake lines of a -D option;
  * the right marks (56): every line of the old evidence is still in the new one (or, for names whose search changed -
    a short name, a -D option - the new evidence still shows no hit in the engine's folders); a traced Qwen-only name
    says the engine's own folders do not have it; the passed-on flag of layer_split / expert_profile_save shows the
    engine ignoring / not parsing it; doc names are still sent (not taken for constants);
  * p4s6 o02 / o01 (v0.2.6, the live Qwen / whole-project examples): gpu_order and "args" traced to the engine's
    environment / arguments, the planner constants dropped, src/program disputed, AUTO_PIN -> STRATA_DS4_AUTO_PIN.

  nice -n 19 .venv/bin/python -I staging/fix1b/tests/test_fix1b.py   (writes tests/evidence-*.txt; exit 1 on a failure)
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
ST = WS / "staging" / "fix1b"
REPLAYS = WS / "results" / "bench2" / "fixes" / "replays"
JUDGED = WS / "results" / "bench2" / "fixes" / "fix1-judge" / "judged.jsonl"
OUT = ST / "tests"

import local_deep_research.deep.checks as old  # noqa: E402  (the installed one)
from local_deep_research.deep import codetool  # noqa: E402

spec = importlib.util.spec_from_file_location("local_deep_research.deep.checks_fix1b", ST / "checks.py")
new = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = new
spec.loader.exec_module(new)

FAILS: list[str] = []


def check(ok: bool, what: str) -> bool:
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        FAILS.append(what)
    return ok


def fake_llm(rec: dict, prompts: list[str]):
    """engine_dirs: the replay's two recorded answers (with its recorded shared folders); VERSION_PROMPT: captured."""
    answers = list(rec["answers"])
    calls = {"n": 0}

    def llm(prompt: str) -> str:
        if "<layout repo=" in prompt:
            i = min(calls["n"], len(answers) - 1)
            calls["n"] += 1
            return json.dumps({"dirs": answers[i], "shared": rec.get("shared") or [], "why": "recorded"})
        prompts.append(prompt)
        return ""
    return llm


def items_of(prompts: list[str]) -> dict[str, str]:
    out = {}
    for p in prompts:
        body = p.split("<settings>\n", 1)[1].rsplit("\n</settings>", 1)[0]
        for it in re.split(r"\n\n(?=### )", body):
            out[it.split("\n", 1)[0][4:]] = it
    return out


def run(label: str, ver: str):
    vc = json.loads((REPLAYS / label / "versioncheck.json").read_text())
    rec = next(iter(vc["engine_dirs"].values()))
    body = (REPLAYS / label / "input.md").read_text(encoding="utf-8")
    repo = codetool.Repo("Niko1221/Strata", ver, ST / "scratch" / ver)
    res = {}
    for tag, mod in (("old", old), ("new", new)):
        prompts: list[str] = []
        t0 = time.time()
        r = mod.version_check(fake_llm(rec, prompts), "(task)", body, None, code=[repo], pins={"Strata": ver})
        res[tag] = {"items": items_of(prompts), "res": r, "s": time.time() - t0,
                    "chars": sum(len(p) for p in prompts), "calls": len(prompts)}
    n_old, n_new = res["old"]["res"]["names"], res["new"]["res"]["names"]
    check(n_old == n_new == vc["names"], f"{label}: same names as the replay ({len(n_new)})")
    print(f"  {label}: evidence built in {res['old']['s']:.2f} s (old) / {res['new']['s']:.2f} s (new); prompt chars "
          f"{res['old']['chars']:,} -> {res['new']['chars']:,} in {res['new']['calls']} call(s); constants dropped: "
          f"{res['new']['res'].get('results') and [x['name'] for x in res['new']['res']['results'] if x.get('kind') == 'not-a-setting']}; "
          f"long forms: {res['new']['res'].get('long_forms')}")
    with open(OUT / f"evidence-{label}.txt", "w", encoding="utf-8") as fh:
        for n in vc["names"]:
            fh.write(f"======== {n}\n--- old\n{res['old']['items'].get(n, '(not sent)')}\n--- new\n"
                     f"{res['new']['items'].get(n, '(not sent)')}\n\n")
    return res, vc


def item(res, name: str, tag: str = "new") -> str:
    it = res[tag]["items"]
    return it.get(name) or it.get(f'"{name}"') or ""


def lines_kept(res, name: str) -> bool:
    o, n = item(res, name, "old"), item(res, name, "new")
    return bool(o) and all(line in n for line in o.split("\n"))


def inside_count(text: str) -> int:
    m = re.search(r"in the engine's own folders \([^)]*\): (\d+)", text)
    return int(m.group(1)) if m else -1


def main() -> int:
    judged = [json.loads(x) for x in JUDGED.read_text().splitlines() if x.strip()]
    runs = {}
    for label in ("b-f1-jan1024", "b-f1-full", "b-f1-fixes"):
        print(f"== {label} (v0.2.4)")
        runs[label] = run(label, "v0.2.4")
    for label in ("b-f1-p4s6o02-code", "b-f1-p4s6o01-code"):
        print(f"== {label} (v0.2.6)")
        runs[label] = run(label, "v0.2.6")

    print("== the 11 false marks: the new evidence has the pass-through / long form / CMake lines")
    want = {
        ("b-f1-jan1024", "gpu"): ["Launcher / server use", "child_env()", 'env["CUDA_VISIBLE_DEVICES"]', "gpu_list()"],
        ("b-f1-jan1024", "gpu_order"): ["Launcher / server use", "ordered_gpus()", "child_env()",
                                        'env["CUDA_VISIBLE_DEVICES"]'],
        ("b-f1-full", "--model"): ["Launcher / server use", "strata_cli/launch/cmd.py:85", "the model size",
                                   "catalog.resolve(a.model"],
        ("b-f1-full", "--plan"): ["Launcher / server use", "strata_cli/launch/cmd.py:138", "show what would happen"],
        ("b-f1-full", "--tune"): ["Launcher / server use", "strata_cli/launch/cmd.py:111", "tune_deepseek()",
                                  "tools/dsv41/tune.py"],
        ("b-f1-full", "--set"): ["Launcher / server use", "strata_cli/launch/cmd.py:113", "kept in .extra",
                                 "apply_to_argv"],
        ("b-f1-fixes", "--set"): ["Launcher / server use", "strata_cli/launch/cmd.py:113", "kept in .extra",
                                  "apply_to_argv"],
        ("b-f1-full", "-DSTRATA_NATIVE_EXPERTS"): ["searched without the -D", "Build files (CMake)",
                                                   "option(STRATA_NATIVE_EXPERTS", "strata-dsv41", "src/dsv41/"],
        ("b-f1-fixes", "SLOT_KEEP"): ["Short form", "`STRATA_DS4_SLOT_KEEP` (named in the report too)",
                                      "src/dsv41/ds4_main.cpp:348"],
        ("b-f1-fixes", "SLOT_CAP"): ["Short form", "`STRATA_DS4_SLOT_CAP`", "src/dsv41/ds4_main.cpp:350"],
        ("b-f1-fixes", "STRATA_DS4_AUTO_PIN"): ["Launcher / server use", "deepseek_shared_start()",
                                                'self.family == "deepseek41"', "DeepSeek-V4.1 only"],
    }
    false = [j for j in judged if j["verdict"] == "false"]
    check(len(false) == 11 and {(j["replay"], j["name"]) for j in false} == set(want), "the 11 false marks are the ones listed")
    for (label, name), needles in want.items():
        t = item(runs[label][0], name)
        miss = [x for x in needles if x not in t]
        check(bool(t) and not miss, f"{label} {name}: {'has ' + ', '.join(needles) if not miss else 'missing ' + str(miss)}")
    t = item(runs["b-f1-full"][0], "-DSTRATA_NATIVE_EXPERTS")
    check(inside_count(t) > 0, f"b-f1-full -DSTRATA_NATIVE_EXPERTS: hits in the engine's own folders now "
                               f"({inside_count(t)}; was {inside_count(item(runs['b-f1-full'][0], '-DSTRATA_NATIVE_EXPERTS', 'old'))})")

    print("== the right marks keep what made them right")
    right = [j for j in judged if j["verdict"] == "correct"]
    check(len(right) == 56, f"56 right marks ({len(right)})")
    changed_search = {"ROUTE_TAIL_SKIP"}           # a short name: now searched as STRATA_ROUTE_TAIL_SKIP
    for j in right:
        res = runs[j["replay"]][0]
        n = j["name"]
        t = item(res, n)
        if not t:
            check(False, f"{j['replay']} {n}: still sent to the model")
            continue
        if n in changed_search:
            check("Short form" in t and inside_count(t) == 0,
                  f"{j['replay']} {n}: judged by its long form, still no hit in the engine's folders ({inside_count(t)})")
            continue
        ok = lines_kept(res, n)
        extra = ""
        if "Launcher / server use" in t and not n.startswith(("expert_profile_save", "layer_split")) and \
                not t.startswith('### "'):
            ok = ok and ("itself has no hit in the engine's own folders" in t or "only in text" in t)
            extra = " + traced, says the engine's folders lack it"
        check(ok, f"{j['replay']} {n} ({j['kind']}): every old evidence line kept{extra}")
    t = item(runs["b-f1-jan1024"][0], "layer_split")
    check("`--layer-split`" in t and "balances its own split" in t,
          "b-f1-jan1024 layer_split: the passed --layer-split shown with the engine's '(void) val ... balances its own split'")
    for n, flag in (("expert_profile_save", "--expert-profile-save"),
                    ("expert_profile_save_every", "--expert-profile-save-every")):
        t = item(runs["b-f1-jan1024"][0], n)
        check(f"`{flag}`: no hits" in t, f"b-f1-jan1024 {n}: the passed {flag} has no hit in the engine's folders")
    for label in ("b-f1-jan1024", "b-f1-full", "b-f1-fixes"):
        dropped = [x["name"] for x in runs[label][0]["new"]["res"]["results"] if x.get("kind") == "not-a-setting"]
        flagged_right = {j["name"] for j in right if j["replay"] == label}
        check(not (set(dropped) & flagged_right), f"{label}: no right mark dropped as a constant (dropped: {dropped})")

    print("== p4s6 o02 / o01 (v0.2.6): the live Qwen / whole-project examples")
    res, vc = runs["b-f1-p4s6o02-code"]
    t = item(res, "gpu_order")
    check("ordered_gpus()" in t and 'env["CUDA_VISIBLE_DEVICES"]' in t, "o02 gpu_order: traced to the engine's CUDA_VISIBLE_DEVICES")
    t = item(res, "args")
    check("engine_args()" in t and "Launcher / server use" in t, "o02 \"args\": traced into engine_args()")
    consts = {x["name"] for x in res["new"]["res"]["results"] if x.get("kind") == "not-a-setting"}
    check({"SMALLEST_CARD_GB", "RESERVE_GB", "ISTA_DENSE_ON_GPU_GB", "REST_RAM_GB"} <= consts,
          f"o02: the planner constants are not sent (dropped: {sorted(consts)})")
    eng = res["new"]["res"]["engine_dirs"]["Niko1221/Strata"]
    check("src/program" in eng["disputed"] and "src/program" not in eng["shared"], "o02: src/program disputed, not shared")
    t = item(res, "STRATA_SPLIT_UNIFORM")
    check("Folders that may also be the engine's" in t, "o02 STRATA_SPLIT_UNIFORM: found in a disputed folder (unsure, not flagged)")
    res, vc = runs["b-f1-p4s6o01-code"]
    t = item(res, "AUTO_PIN")
    check("`STRATA_DS4_AUTO_PIN`" in t and "deepseek_shared_start()" in t, "o01 AUTO_PIN: judged by STRATA_DS4_AUTO_PIN, traced")
    eng_old = runs["b-f1-p4s6o01-code"][0]["old"]["res"]["engine_dirs"]["Niko1221/Strata"]
    eng_new = res["new"]["res"]["engine_dirs"]["Niko1221/Strata"]
    check(all(eng_old[k] == eng_new[k] for k in ("dirs", "shared", "disputed")), "o01: engine folders as before")
    for label in ("b-f1-jan1024", "b-f1-full", "b-f1-fixes"):
        eo = runs[label][0]["old"]["res"]["engine_dirs"]["Niko1221/Strata"]
        en = runs[label][0]["new"]["res"]["engine_dirs"]["Niko1221/Strata"]
        check(all(eo[k] == en[k] for k in ("dirs", "shared", "disputed")), f"{label}: engine folders as before")

    print("== the model's answers: config keys come back without quotes (the disputed-folder rule matches them now)")
    check(new._bare('"gpu"') == "gpu" and new._bare("gpu") == "gpu" and new._bare('"') == '"', "_bare")
    # version_check's handling of the answers (a fake reply on o02): a name found in a disputed folder is unsure, the
    # constants are listed as not-a-setting, neither is flagged; the marks / section still work
    vc = json.loads((REPLAYS / "b-f1-p4s6o02-code" / "versioncheck.json").read_text())
    rec = next(iter(vc["engine_dirs"].values()))
    body = (REPLAYS / "b-f1-p4s6o02-code" / "input.md").read_text(encoding="utf-8")
    repo = codetool.Repo("Niko1221/Strata", "v0.2.6", ST / "scratch" / "v0.2.6")
    reply = "\n".join(json.dumps(d) for d in (
        {"name": "STRATA_SPLIT_UNIFORM", "kind": "launcher-only", "use": "recommended", "note": "x"},
        {"name": "gpu_order", "kind": "this-version", "use": "recommended", "note": "server orders the cards"},
        {"name": "--chunk-mmq", "kind": "not-found", "use": "recommended", "note": "y"}))
    base = fake_llm(rec, [])
    r = new.version_check(lambda p: base(p) if "<layout repo=" in p else reply, "(task)", body, None, code=[repo],
                          pins={"Strata": "v0.2.6"})
    kinds = {x["name"]: x["kind"] for x in r["results"]}
    check(kinds.get("STRATA_SPLIT_UNIFORM") == "unsure" and kinds.get("SMALLEST_CARD_GB") == "not-a-setting"
          and kinds.get("gpu_order") == "this-version",
          f"o02 answers: disputed -> unsure, constants listed, not flagged ({kinds})")
    flagged = [x["name"] for x in new.version_flagged(r)]
    check(flagged == ["--chunk-mmq"], f"o02 answers: only the not-found name is flagged ({flagged})")
    check(new.version_section(r, "Strata v0.2.6").startswith("## Version check") and
          isinstance(new.version_marks(body, r, "Strata v0.2.6"), list), "version_section / version_marks still run")
    print(f"\n{'ALL OK' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
