#!/usr/bin/env python3
"""K4 offline test (no model, no GPU, no network): the staged consistency pass (staging/k4/checks.py) against Fix 1b's
(staging/k4/checks.py.fix1b = staging/fix1b/checks.py), on the reports of the 10-28 replays b-f5c-full / b-f5c-fixes
(results/bench2/fixes/replays/<label>/input.md), with the question and the setup facts those replays used
(codetool/question.txt; user-setup.md through setup.facts_for, LDR_DEEP_FIX=baseline,consist as in the replay).

  1. prompts: a fake model records them. Same number of calls (1 + 2); the main prompt byte-identical; the focused
     call with --dspark holds the K4 claims, the 1.5x rule, the task's numbers and the evaluation instruction together;
     the focused blocks are the old ones plus sentence ids; each id maps back to a sentence the marks can find.
  2. replies in the new format, from a fake model: a correct K4 catch, non-catches, malformed replies.
  3. unchanged where intended: action_settings / sentences_about, the marks and section of the saved replay results,
     every line outside the consistency pass (besides the docstring and EST["consist"]).
  4. judge_k4.py on the old replays and on the faked catch.

  nice -n 19 .venv/bin/python -I staging/k4/tests/test_k4.py   (exit 1 on a failure)
"""
from __future__ import annotations

import difflib
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

os.environ["LDR_DEEP_FIX"] = "baseline,consist"         # as fix-replay.py ran F5c (setup.facts_for reads it)

WS = Path("/home/USER/ai/deep-research")
ST = WS / "staging" / "k4"
REPLAYS = WS / "results" / "bench2" / "fixes" / "replays"
QUESTION = (WS / "results" / "bench2" / "codetool" / "question.txt").read_text(encoding="utf-8").strip()


def _load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


old = _load("local_deep_research.deep.checks_fix1b", ST / "checks.py.fix1b")
new = _load("local_deep_research.deep.checks_k4", ST / "checks.py")
from local_deep_research.deep import setup as setup_profile  # noqa: E402

sys.path.insert(0, str(ST / "tests"))
import judge_k4  # noqa: E402

FAILS: list[str] = []


def check(ok: bool, what: str) -> bool:
    print(("  ok    " if ok else "  FAIL  ") + what)
    if not ok:
        FAILS.append(what)
    return ok


def body_of(label: str) -> str:
    return (REPLAYS / label / "input.md").read_text(encoding="utf-8")


FACTS = setup_profile.facts_for(str(WS / "user-setup.md"), QUESTION)


def recorder(replies=None):
    """A fake model: records each prompt; the main prompt gets an empty list, a focused one the reply that
    replies(prompt) gives (default: an empty list)."""
    prompts: list[str] = []

    def llm(p: str) -> str:
        prompts.append(p)
        if "<report>" in p:
            return '{"contradictions": []}'
        return replies(p) if replies else '{"settings": []}'
    return llm, prompts


def run(mod, body: str, replies=None):
    llm, prompts = recorder(replies)
    res = mod.consistency_check(llm, QUESTION, body, facts=FACTS)
    return res, prompts


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


# K4's statements in the b-f5c-full report (input.md) and the task's numbers they are judged on
K4_CLAIMS = {
    "auto loads": "The default `--dspark auto` loads the 8 GB Q8_0 DSpark drafter (Unsloth's draft model) into VRAM",
    "Answer": "freeing the 8 GB DSpark drafter from VRAM (`--dspark none`)",
    "plan item 1": "`--dspark none` — frees ~5.6 GB VRAM (≈592 expert slots at 9.4 MB/expert), directly recovers the "
                   "measured 8–16% decode loss",
}
K4_RULE = "sets `g.n_mtp = 0` (disabling the drafter entirely) when routed experts exceed 1.5× the available room"
TASK_NUMBERS = ["backbone 138 GB on disk", "RTX 5080 16 GB", "RTX 4060 Ti 8 GB", "40 layers x 384 experts",
                "1,357 of 15,360 experts pinned in VRAM", "dense/shared weights (~5.9 GB)"]
FACT_NUMBERS = ["Total VRAM 24 GB"]
EVAL_INSTRUCTION = ["1. RULES.", "Evaluate it on this setup", "write the arithmetic out with the numbers",
                    "whether the condition holds here", "2. CLAIMS. Only then compare that outcome",
                    "\"arithmetic\": \"<the calculation, written out>\"", "\"holds\": \"yes|no|unknown\""]


def sid_of(ids: dict[str, str], text: str) -> str:
    t = norm(text)
    hits = [k for k, v in ids.items() if t in norm(v)]
    return hits[0] if hits else ""


# ------------------------------------------------------------------------------------------------ 1. prompts
def test_prompts() -> dict:
    print("== 1. prompts (fake model, b-f5c-full and b-f5c-fixes)")
    keep = {}
    for label in ("b-f5c-full", "b-f5c-fixes"):
        body = body_of(label)
        r_old, p_old = run(old, body)
        r_new, p_new = run(new, body)
        check(len(p_old) == len(p_new) == 3, f"{label}: {len(p_new)} calls (Fix 1b {len(p_old)}): 1 main + 2 focused")
        check(p_old[0] == p_new[0], f"{label}: the main prompt is byte-identical ({len(p_new[0]):,} chars)")
        check(r_old["focused_settings"] == r_new["focused_settings"],
              f"{label}: the same focused settings {r_new['focused_settings']}")
        # the focused blocks: the old ones plus the sentence ids
        for k in (1, 2):
            ob = p_old[k].split("<settings>\n", 1)[1].rsplit("\n</settings>", 1)[0]
            nb = p_new[k].split("<settings>\n", 1)[1].rsplit("\n</settings>", 1)[0]
            check(re.sub(r"(?m)^- S\d+ ", "- ", nb) == ob, f"{label} focused call {k}: the block is the old one plus ids")
            head_new = p_new[k].split("<task>", 1)[0]
            check(f"<task>\n{QUESTION}\n</task>" in p_new[k] and f"<user_setup>\n{FACTS}\n</user_setup>" in p_new[k],
                  f"{label} focused call {k}: the task and the setup facts are in the prompt")
            print(f"        focused call {k}: {len(p_old[k]):,} -> {len(p_new[k]):,} chars "
                  f"(instructions {len(p_old[k].split('<task>', 1)[0]):,} -> {len(head_new):,})")
        keep[label] = (body, p_new, r_new)
    # the K4 step: one focused prompt holds the claims, the rule, the task's numbers and the instruction
    body, p_new, _ = keep["b-f5c-full"]
    pk = [p for p in p_new[1:] if "### --dspark\n" in p]
    check(len(pk) == 1, "b-f5c-full: one focused call carries --dspark")
    p = pk[0]
    block = p.split("### --dspark\n", 1)[1].split("\n\n###", 1)[0]
    for k, c in K4_CLAIMS.items():
        check(norm(c) in norm(block), f"K4 claim ({k}) is in the --dspark block: \"{c[:70]}...\"")
    check(norm(K4_RULE) in norm(block), "the 1.5x rule is in the --dspark block")
    for t in TASK_NUMBERS:
        check(t in p, f"the task's number is in the same prompt: \"{t}\"")
    for t in FACT_NUMBERS:
        check(t in p, f"the setup facts' number is in the same prompt: \"{t}\"")
    for t in EVAL_INSTRUCTION:
        check(t in p, f"the evaluation instruction is in the same prompt: \"{t}\"")
    check(p.index("2. CLAIMS") > p.index("1. RULES") and p.index("<settings>") > p.index("2. CLAIMS"),
          "rules come before claims, both before the sentences")
    print("        the --dspark block as the model sees it:")
    for line in block.split("\n"):
        print("          " + line[:190])
    # ids -> the report's sentences; the marks can find them
    _, ids = new.focus_block(body, [n for n in new.action_settings(body) if len(new.sentences_about(body, n)) >= 2][:5])
    loc = new.Locator(body)
    check(all(loc.find(v) for v in ids.values()), f"all {len(ids)} sentence ids of the call map to sentences found in "
                                                     "the report (Locator)")
    want = {k: sid_of(ids, c.split("—")[-1] if k == "plan item 1" else c) for k, c in K4_CLAIMS.items()}
    want["rule"] = sid_of(ids, K4_RULE)
    check(all(want.values()), f"the K4 sentences' ids: {want}")
    return {"body": body, "ids": ids, "sid": want, "prompt": p}


# ------------------------------------------------------------------------------------------------ 2. replies
def reply_for(setting_json: list) -> callable:
    """The focused reply: the given settings for the call with --dspark, an empty list for the other."""
    def f(p: str) -> str:
        return json.dumps({"settings": setting_json}) if "### --dspark\n" in p else '{"settings": []}'
    return f


def k4_rule(s: dict, arithmetic: str, holds="yes", claims=None) -> dict:
    return {"rule": s["rule"], "condition": "the drafter is not loaded when the routed experts exceed 1.5x the room",
            "inputs": "routed experts 138 GB (task: backbone 138 GB); room 24 GB VRAM (task: 16 + 8 GB) minus dense "
                      "5.9 GB (task)",
            "arithmetic": arithmetic, "holds": holds,
            "outcome": "--dspark auto does not load the drafter on this PC: the baseline already runs without it",
            "claims": claims if claims is not None else [
                {"claim": s["auto loads"], "agrees": "no", "right": "rule",
                 "why": "auto leaves the drafter out on this PC, so it does not load the 8 GB drafter",
                 "fix": "On this PC `--dspark auto` already leaves the drafter out (138 GB of experts > 1.5 x the room)."},
                {"claim": s["plan item 1"], "agrees": "no", "right": "rule",
                 "why": "the baseline has no drafter loaded, so --dspark none recovers nothing",
                 "fix": "`--dspark none` changes nothing here: auto already does not load the drafter."},
                {"claim": s["Answer"], "agrees": "no", "right": "rule", "why": "no drafter to free", "fix": ""},
                {"claim": "S8", "agrees": "yes"}]}


GOOD_ARITH = "24 GB - 5.9 GB = 18.1 GB; 1.5 x 18.1 GB = 27.15 GB; 138 GB > 27.15 GB"


def test_replies(ctx: dict) -> dict:
    print("== 2. replies in the new format (fake model)")
    body, s = ctx["body"], ctx["sid"]
    # a: the correct K4 catch
    rep = [{"setting": "--dspark", "rules": [k4_rule(s, GOOD_ARITH)], "conflicts": []},
           {"setting": "--experts", "rules": [], "conflicts": [
               {"quote_a": "S1", "quote_b": "S2", "right": "unclear", "why": "a plain pair", "fix": ""}]}]
    res, _ = run(new, body, reply_for(rep))
    cs = res["contradictions"]
    rule = [c for c in cs if c.get("step") == "rule"]
    check(len(rule) == 3, f"K4 catch: 3 rule-step pairs (one per disagreeing claim), got {len(rule)}")
    first = rule[0] if rule else {}
    check(first.get("quote_a") == ctx["ids"][s["auto loads"]] and first.get("quote_b") == ctx["ids"][s["rule"]],
          "K4 catch: quote_a = the 'auto loads' sentence, quote_b = the 1.5x rule sentence, both exact from the ids")
    check(first.get("right") == "b", "K4 catch: the rule side holds (right = b)")
    ev = first.get("evaluation") or {}
    check(ev.get("arithmetic") == GOOD_ARITH and ev.get("holds") == "yes", "K4 catch: the evaluation is kept with the pair")
    rc = res.get("rule_checks") or []
    check(len(rc) == 1 and rc[0]["recheck"] == {"equations": 2, "comparisons": 1, "wrong": []},
          f"K4 catch: the arithmetic recomputes in code ({rc[0]['recheck'] if rc else None})")
    check(len(rc) == 1 and [c["agrees"] for c in rc[0]["claims"]] == ["no", "no", "no", "yes"],
          "K4 catch: every compared claim is in rule_checks (3 disagree, 1 agrees)")
    plain = [c for c in cs if c.get("step") == "focused"]
    check(len(plain) == 1 and plain[0]["quote_a"] == ctx["ids"]["S1"], "a plain pair by ids still comes back (focused)")
    marks = new.consistency_marks(res)
    out, found = new.insert_marks(body, marks)
    check(all(found), f"all {len(found)} marks placed in the report")
    i = out.find(K4_CLAIMS["auto loads"])
    seg = out[i:i + 900]
    mk = seg[len(K4_CLAIMS["auto loads"]):].split("\n")[0]
    check("[Consistency check: contradicts the rule elsewhere in this report (the drafter is not loaded when the routed "
          "experts exceed 1.5x the room), which the evidence supports; On this PC" in mk
          and f"; applied to this setup: {GOOD_ARITH}]**" in mk,
          "the mark after 'auto loads ...' names the rule by its condition, the fix and the arithmetic (not cut)")
    print("        " + mk[:600])
    long = dict(rule[0], evaluation=dict(ev, arithmetic="routed experts 15,360 x 9.4 MB = 144.4 GB; room 16 GB + 8 GB "
                                                        "- 5.9 GB = 18.1 GB; 1.5 x 18.1 GB = 27.15 GB; 144.4 GB > 27.15 GB"))
    lm = new.consistency_marks({"contradictions": [long]})
    check(len(lm) == 1 and lm[0][1].endswith("applied to this setup: ... 144.4 GB > 27.15 GB]**"),
          "a long evaluation: the mark keeps its deciding step (the section has it whole)")
    sec = new.consistency_section(res)
    check("The rule applied to this setup: condition the drafter is not loaded" in sec and GOOD_ARITH in sec,
          "the section shows the evaluation under the pair")
    print("        section: " + [ln for ln in sec.split("\n") if "The rule applied" in ln][0][:300])
    good = res
    # b: non-catches
    res, _ = run(new, body, reply_for([{"setting": "--dspark", "rules": [k4_rule(
        s, "1.5 x 18.1 GB = 27.15 GB; 138 GB > 27.15 GB",
        claims=[{"claim": s["auto loads"], "agrees": "yes"}, {"claim": s["Answer"], "agrees": "yes"}])],
        "conflicts": []}]))
    check(not res["contradictions"] and len(res["rule_checks"]) == 1,
          "non-catch (the claims agree): no pair, the rule's evaluation is still in rule_checks")
    res, _ = run(new, body, reply_for([{"setting": "--dspark", "rules": [k4_rule(s, "", holds="unknown")], "conflicts": []}]))
    check(not res["contradictions"] and res["rule_checks"][0]["holds"] == "unknown",
          "holds 'unknown' + claims that disagree: no pair (the rule could not be applied), kept in rule_checks")
    res, _ = run(new, body, reply_for([{"setting": "--dspark", "rules": [], "conflicts": []}]))
    check(res["contradictions"] == [] and res["rule_checks"] == [] and "focused_unparsed" not in res,
          "an empty reply: nothing found, nothing unparsed")
    # c: malformed
    res, _ = run(new, body, lambda p: "I could not decide.")
    check(res["contradictions"] == [] and res.get("focused_unparsed") == 2, "no JSON in either focused reply: "
          f"counted (focused_unparsed {res.get('focused_unparsed')}), the main result kept")
    full = json.dumps({"settings": rep})
    cut = full[:full.index('"--experts"') + 30]
    res, _ = run(new, body, lambda p: cut if "### --dspark\n" in p else '{"settings": []}')
    check(len([c for c in res["contradictions"] if c.get("step") == "rule"]) == 3,
          "a reply cut off after the first setting (finish=length): the complete setting is salvaged")
    weird = [{"setting": "--dspark", "rules": "none"},
             {"setting": "--dspark", "rules": [{"rule": "S999", "holds": "yes", "claims": [{"claim": s["Answer"], "agrees": "no"}]},
                                               {"rule": s["rule"], "holds": True, "arithmetic": GOOD_ARITH,
                                                "claims": {"S9": "no"}},
                                               {"rule": s["rule"], "holds": True, "arithmetic": GOOD_ARITH,
                                                "claims": [{"claim": s["rule"], "agrees": "no"},
                                                           {"claim": f"[{s['auto loads']}]", "agrees": False, "right": "RULE"},
                                                           "S3", None]}],
              "conflicts": [{"quote_a": "S999", "quote_b": "S1"}, {"quote_a": "S1", "quote_b": "S1"}, "x"]},
             "not a dict"]
    res, _ = run(new, body, reply_for(weird))
    rule = [c for c in res["contradictions"] if c.get("step") == "rule"]
    check(len(rule) == 1 and rule[0]["quote_a"] == ctx["ids"][s["auto loads"]] and rule[0]["right"] == "b",
          "wrong types (rules a string, claims a dict, an unknown id, a rule against itself, bool holds / agrees, "
          "'[S9]', 'RULE'): no crash, only the one valid pair kept")
    check(not [c for c in res["contradictions"] if c.get("step") == "focused"], "plain pairs with an unknown id or "
                                                                               "one sentence twice: dropped")
    old_shape = '{"contradictions": [{"setting": "--dspark", "quote_a": "The default `--dspark auto` loads the 8 GB ' \
                'Q8_0 DSpark drafter", "quote_b": "when routed experts exceed 1.5× the available room", "right": "b", ' \
                '"why": "old shape", "fix": ""}]}'
    res, _ = run(new, body, lambda p: old_shape if "### --dspark\n" in p else '{"settings": []}')
    check(len(res["contradictions"]) == 1 and res["contradictions"][0]["step"] == "focused"
          and all(new.insert_marks(body, new.consistency_marks(res))[1]),
          "a reply in the old shape (contradictions with quotes) is still taken, and its marks are placed")
    # d: the evaluation's own arithmetic is wrong -> not settled
    res, _ = run(new, body, reply_for([{"setting": "--dspark", "rules": [k4_rule(
        s, "1.5 x 18.1 GB = 40 GB; 138 GB < 27.15 GB")], "conflicts": []}]))
    rule = [c for c in res["contradictions"] if c.get("step") == "rule"]
    check(len(rule) == 3 and all(c["right"] == "unclear" for c in rule)
          and "does not recompute: 1.5 x 18.1 GB = 40 GB (recomputed 27.1)" in rule[0]["why"],
          "wrong arithmetic in the evaluation: the pairs stay but are not settled, with the recomputed step")
    mk = new.consistency_marks(res)
    check(len(mk) == 6 and all("not settled" in m for _, m in mk), "  ... and both statements of each are marked "
                                                                     "'not settled'")
    print("        recheck: " + json.dumps(res["rule_checks"][0]["recheck"], ensure_ascii=False))
    return good


# ------------------------------------------------------------------------------------------------ 3. unchanged
def test_unchanged() -> None:
    print("== 3. unchanged where intended")
    check(old.CONSIST_PROMPT == new.CONSIST_PROMPT, "CONSIST_PROMPT (the main pass) is identical")
    for label in ("b-f5c-full", "b-f5c-fixes"):
        body = body_of(label)
        check(old.action_settings(body) == new.action_settings(body), f"{label}: action_settings identical")
        names = sorted(set(old.setting_names(body)))
        same = all(old.sentences_about(body, n) == new.sentences_about(body, n) for n in names)
        rows = all([t for t, _ in new.sentences_about(body, n, rows=True)] == new.sentences_about(body, n) for n in names)
        check(same and rows, f"{label}: sentences_about identical for all {len(names)} setting names (rows=True gives "
                             "the same lines)")
        saved = json.loads((REPLAYS / label / "consistency.json").read_text())
        check(old.consistency_marks(saved) == new.consistency_marks(saved),
              f"{label}: the marks of the saved result ({len(saved['contradictions'])} pairs) are identical")
        check(old.consistency_section(saved) == new.consistency_section(saved),
              f"{label}: the section of the saved result is identical")
        out_o, f_o = old.insert_marks(body, old.consistency_marks(saved))
        out_n, f_n = new.insert_marks(body, new.consistency_marks(saved))
        check(out_o == out_n, f"{label}: the marked report is identical ({sum(f_n)} of {len(f_n)} marks placed)")
    check(old.consistency_section(None) == new.consistency_section(None)
          and old.consistency_section({"contradictions": []}) == new.consistency_section({"contradictions": []}),
          "the section for 'did not complete' / no pairs is identical")
    # every changed line is in the docstring's consist entry, the consistency pass, or EST["consist"]
    a = (ST / "checks.py.fix1b").read_text(encoding="utf-8").splitlines()
    b = (ST / "checks.py").read_text(encoding="utf-8").splitlines()
    lo = next(i for i, ln in enumerate(b) if "- consistency pass" in ln and ln.startswith("# ---"))
    hi = next(i for i, ln in enumerate(b) if "- Fix 2: critic inline" in ln and ln.startswith("# ---"))
    est = next(i for i, ln in enumerate(b) if ln.startswith("EST = {"))
    doc = next(i for i, ln in enumerate(b) if ln.startswith("  consist "))
    outside = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        for j in range(j1, max(j2, j1 + 1)):
            if not (lo <= j < hi or doc <= j <= doc + 5 or est - 3 <= j <= est + 1):
                outside.append(j + 1)
    check(not outside, f"no change outside the consistency pass, its docstring entry and EST (lines {outside[:8]})")
    check({k: v for k, v in old.EST.items() if k != "consist"} == {k: v for k, v in new.EST.items() if k != "consist"}
          and (old.EST["consist"], new.EST["consist"]) == (480, 900), "EST: only 'consist' changed (480 -> 900)")
    n_changed = sum(1 for ln in difflib.unified_diff(a, b, lineterm="", n=0) if ln[:1] in "+-" and ln[:3] not in ("+++", "---"))
    print(f"        diff against checks.py.fix1b: {n_changed} lines (+/-)")


# ------------------------------------------------------------------------------------------------ 4. the judge
def test_judge(good: dict) -> None:
    print("== 4. judge_k4.py (for the GPU replays) on the old replays and on the faked catch")
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        full = judge_k4.judge("b-f5c-full", None)
        fixes = judge_k4.judge("b-f5c-fixes", None)
    check(full["k4_state"] == "NOT caught" and full["k1_state"] == "kept",
          f"b-f5c-full (10-28, Fix 1b's pass): K4 {full['k4_state']}, K1 {full['k1_state']} {full['k1']} - as "
          "BUNDLE-1028 F5c says")
    check(fixes["k4_state"].startswith("n/a") and not fixes["k4_rev"],
          f"b-f5c-fixes: K4 {fixes['k4_state']}, no K4-reversed false alarm")
    hits = [judge_k4.k4(c) for c in good["contradictions"]]
    check(hits.count("strong") == 3 and not any(judge_k4.k1(c) for c in good["contradictions"] if c.get("step") == "rule"),
          f"the faked K4 catch is judged 'strong' for all 3 claims ({hits})")
    plan17 = json.loads((REPLAYS / "b-f5c-full" / "consistency.json").read_text())["contradictions"][17]
    check(judge_k4.k4(plan17) == "", "the weaker 10-28 pair (8 GB vs 5.6 GB freed) is not counted as K4")


def main() -> int:
    ctx = test_prompts()
    good = test_replies(ctx)
    test_unchanged()
    test_judge(good)
    print("\n" + ("ALL OK" if not FAILS else f"{len(FAILS)} FAILED:\n  " + "\n  ".join(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
