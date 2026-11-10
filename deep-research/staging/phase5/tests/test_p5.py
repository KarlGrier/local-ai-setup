#!/usr/bin/env python3
"""Offline tests for staging/phase5 - no model, service, GPU or network; reads existing bench2 runs, writes only to a
temporary folder (P5_TEST_TMP, default the system temp dir).

    nice -n 19 /home/USER/ai/deep-research/.venv/bin/python -I /home/USER/ai/deep-research/staging/phase5/tests/test_p5.py

Answer keys are only used inside assertions (bench2's matcher on the packet text); nothing prints them.
"""
from __future__ import annotations

import contextlib
import difflib
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S = HERE.parent
WS = Path("/home/USER/ai/deep-research")
B = WS / "results" / "bench2"
PY = str(WS / ".venv" / "bin" / "python")
TCFG = HERE / "p5-test.json"
TMP = Path(tempfile.mkdtemp(prefix="p5test-", dir=os.environ.get("P5_TEST_TMP")))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path, loader=SourceFileLoader(name, str(path)))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


p5 = load("p5_under_test", S / "p5.py")


def run(*args, env=None):
    return subprocess.run([PY, "-I", str(S / "p5.py"), *map(str, args)], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def tcfg_with(**changes) -> Path:
    cfg = json.loads(TCFG.read_text())
    for k, v in changes.items():
        cur = cfg
        parts = k.split("__")
        for p in parts[:-1]:
            cur = cur[int(p)] if isinstance(cur, list) else cur[p]
        cur[parts[-1]] = v
    p = TMP / f"cfg-{abs(hash(json.dumps(changes, sort_keys=True)))}.json"
    p.write_text(json.dumps(cfg))
    return p


BO = p5.blind_open_module("Setup check,Check these,Version check,Arithmetic check,Consistency check".split(","))
CUES = ["http", "[[", "[Check", "Setup check", "⚠", "Citation check", "Key findings", "URL:"]


class Extraction(unittest.TestCase):
    def pk(self, raw):
        return p5.packet_text(raw, BO)

    def test_deep_answer_section(self):
        raw = ("# Most Bronze: Kazakhstan\n\n## Answer\n\nKazakhstan won 48 bronze **[Check: reasoning: the date "
               "(a search that would settle it: x)]**. Confirmed [92][93] and *[⚠ only partly supported by the cited "
               "source: x]*. **[Setup check: the PC has 8 GB]** Also [1, 2] and 【4】.\n\n## Key findings\n\n- 48 [1]\n\n"
               "## Sources\n\n[1] t\n URL: https://a.example/x\n")
        text, where = self.pk(raw)
        self.assertEqual(where, "answer")
        self.assertTrue(text.startswith("## Answer section\n\nKazakhstan won 48 bronze."), text)
        for c in CUES + ["Most Bronze", "[9", "[1", "【"]:
            self.assertNotIn(c, text)

    def test_ldr_answer_colon(self):
        raw = ("## Answer: Paris Saint-Germain\n\nThe goal by **Ferran Torres** [[2]](https://www.x.com/a)"
               "[[5]](https://en.wikipedia.org/wiki/Foo_(film)).\n\n### Key details:\n- moved [[97]](https://psg.fr/x)\n"
               "- see [the club](https://psg.fr/y) and https://bare.example/z\n\n## Sources\n\n[2] t\n URL: https://www.x.com/a\n\n"
               "## Research Metrics\n- x\n")
        text, where = self.pk(raw)
        self.assertEqual(where, "answer")
        self.assertIn("Paris Saint-Germain", text)
        self.assertIn("The goal by **Ferran Torres**.", text)
        self.assertIn("Key details:", text)
        self.assertIn("see the club and", text)
        for c in CUES + ["(film)"]:
            self.assertNotIn(c, text)
        self.assertNotIn("#", text.split("\n", 1)[1])

    def test_lead_fallback_headline(self):
        raw = ("## **Kazakhstan — with 48 bronze medals**\n\nExcluding China, **Kazakhstan** won [[95]](https://24.kz/x).\n\n"
               "### Ranking\n| a | b |\n\n## Sources\n\n[95] t\n URL: https://24.kz/x\n\n## Research Metrics\nx\n")
        text, where = self.pk(raw)
        self.assertEqual(where, "lead")
        self.assertIn("**Kazakhstan — with 48 bronze medals**", text)
        self.assertIn("Ranking", text)
        self.assertNotIn("#", text.split("\n", 1)[1])
        self.assertNotIn("Research Metrics", text)

    def test_lead_without_heading_and_key_findings(self):
        text, where = self.pk("The encoder has **27 layers** [[33]](https://n.io/x).\n\n## Sources\n\n[33] t\n URL: https://n.io/x\n")
        self.assertEqual((where, text), ("lead", "## Answer section\n\nThe encoder has **27 layers**.\n"))
        text, where = self.pk("# T\n\n## Key findings\n\n- 39 seats [3]\n\n## Details\n\nmore\n")
        self.assertEqual((where, text), ("key findings", "## Answer section\n\n- 39 seats\n"))

    def test_empty(self):
        self.assertEqual(self.pk("## Sources\n\n[1] x\n URL: https://a\n")[1], "none")
        self.assertEqual(self.pk(None), ("(The report has no answer text.)\n", "none"))


class Plan(unittest.TestCase):
    def test_real_config_refuses_placeholders(self):
        r = run("plan")
        self.assertEqual(r.returncode, 1)
        for w in ("PLACEHOLDER", "arms[1].items", "engine.config", "engine.sha12"):
            self.assertIn(w, r.stderr)

    def test_preview(self):
        out = TMP / "preview.json"
        r = run("plan", "--allow-placeholder", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        steps = json.loads(out.read_text())
        p4 = json.loads((B / "queue-plan-p4s7.json").read_text())
        self.assertEqual([(s["set"], s["profile"], len(s["ids"])) for s in steps],
                         [("holdout", "baseline", 3), ("holdout", "deep", 3), ("p5-harder", "baseline", 4),
                          ("p5-harder", "deep", 4), ("holdout", "baseline", 15), ("holdout", "deep", 15),
                          ("hard-holdout", "baseline", 10), ("hard-holdout", "deep", 10)])
        for s in steps:
            self.assertEqual((s["open_min"], s["checkable_min"]), (p4[0]["open_min"], p4[0]["checkable_min"]))
            self.assertEqual(s["needs"], {"holdout": "FROZEN.txt", "hard-holdout": "FROZEN-hard.txt",
                                          "p5-harder": "FROZEN-p5-harder.txt"}[s["set"]])
            if s["profile"] == "baseline":
                self.assertEqual(s["label"], "p5")
                self.assertFalse({"items", "effort", "verify_effort"} & set(s))
            else:
                self.assertEqual((s["label"], s["items"], s["effort"], s["verify_effort"]),
                                 ("p5final", ["PLACEHOLDER"], "medium", "xhigh"))
        self.assertEqual(set(steps[0]["ids"]), {"o04", "o05", "o06"})
        self.assertIn("estimate", r.stderr)

    def test_filled_unknown_items_timing(self):
        self.assertEqual(run("--config", TCFG, "plan").returncode, 0)
        r = run("--config", tcfg_with(arms__1__items=["setup", "tavily"]), "plan")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not switched by bench2-queue.sh", r.stderr)
        r = run("--config", tcfg_with(timing__checkable_min=30), "plan")
        self.assertEqual(r.returncode, 1)
        self.assertIn("differs from queue-plan-p4s7.json", r.stderr)
        r = run("--config", tcfg_with(include_o01=True), "plan")
        self.assertEqual(r.returncode, 1)           # p5-o01 is not frozen (no questions file in results/bench2)


class Bench2Staged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.new = load("bench2_staged", S / "bench2.py")
        cls.old = load("bench2_orig", S / "bench2.py.orig")

    def test_sets_and_answers(self):
        self.assertIn("p5-harder", self.new.SETS)
        self.assertEqual([q["id"] for q in self.new.questions("p5-harder")], ["p5c1b", "p5c2", "p5c5", "p5c6"])
        self.assertTrue({"p5c1b", "p5c2", "p5c5", "p5c6", "h11", "c03"} <= set(self.new.answers()))
        self.assertFalse({"p5c1b"} & set(self.old.answers()))

    def test_orig_is_live_and_change_small(self):
        self.assertEqual((S / "bench2.py.orig").read_bytes(), (WS / "tools" / "bench2.py").read_bytes(),
                         "tools/bench2.py changed since staging: p5-start.sh would refuse; re-stage")
        d = [l for l in difflib.unified_diff((S / "bench2.py.orig").read_text().splitlines(),
                                             (S / "bench2.py").read_text().splitlines(), n=0)
             if l[:1] in "+-" and not l.startswith(("+++", "---"))]
        self.assertLessEqual(len(d), 14, d)

    def test_next_on_preview_plan(self):
        out = TMP / "preview-next.json"
        self.assertEqual(run("plan", "--allow-placeholder", "--out", out).returncode, 0)
        r = subprocess.run([PY, "-I", str(S / "bench2.py"), "next"], capture_output=True, text=True,
                           env={**os.environ, "BENCH2_PLAN": str(out)})
        self.assertEqual(r.stdout.split(), ["holdout", "baseline", "o04", "-", "p5", "-", "-"], r.stderr)

    def test_next_uses_step_budget(self):
        class At21(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 4, 21, 0)
        plan = TMP / "night-plan.json"
        plan.write_text(json.dumps([{"set": "hard-holdout", "profile": "deep", "ids": ["h11"], "label": "p5nighttest",
                                     "open_min": 171, "checkable_min": 47}]))
        outs = {}
        for name, mod in (("old", self.old), ("new", self.new)):
            mod.NIGHT_OK, mod.datetime = Path("/nonexistent/night-ok"), At21
            os.environ["BENCH2_PLAN"] = str(plan)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.cmd_next(None)
            outs[name] = buf.getvalue().split()
        os.environ.pop("BENCH2_PLAN")
        self.assertEqual(outs["old"][:3], ["hard-holdout", "deep", "h11"])   # 30+60 min "fits" by 22:30 ...
        self.assertEqual(outs["new"], ["wait"])                              # ... 47+60 does not


class PacketsAndTally(unittest.TestCase):
    """One flow on real runs: packets -> refusals -> synthetic grades -> tally."""

    def test_flow(self):
        out = TMP / "blind"
        r = run("--config", TCFG, "packets", "--out", out)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("runs not done yet", r.stderr)
        r = run("--config", TCFG, "packets", "--out", out, "--allow-missing")
        self.assertEqual(r.returncode, 0, r.stderr)
        ck = out / "checkable"
        key = json.loads((ck / p5.KEY_NAME).read_text())
        man = json.loads((ck / "MANIFEST.json").read_text())
        both, one = ["h02", "h04", "h05", "h06", "h08"], ["h01", "h03", "c01", "c05", "c09"]
        self.assertEqual(man["lines"], {"checkable": ["h01", "h02", "h03", "h04", "h05", "c01", "c05", "c09"],
                                        "harder": ["h06", "h08"]})
        for q in both:
            self.assertEqual(sorted(key[q]["labels"].values()), ["baseline", "final"])
            self.assertEqual(man["packets"][q]["labels"], ["A", "B"])
        for q in one:
            self.assertEqual((key[q]["labels"], key[q]["missing"]), ({"A": "baseline"}, ["final"]))
        # the stripping, on real reports; and the answer survives it (bench2's matcher; keys stay inside the assert)
        b2 = load("bench2_live", WS / "tools" / "bench2.py")
        ans = {x["id"]: x for f in ("answers.jsonl", "answers-hard.jsonl") for x in b2.load_jsonl(B / "answers" / f)}
        lost = []
        for q in both + one:
            for lab in man["packets"][q]["labels"]:
                t = (ck / q / f"{lab}.md").read_text()
                self.assertTrue(t.startswith("## Answer section\n\n"), (q, lab))
                for c in CUES:
                    self.assertNotIn(c, t, (q, lab, c))
                self.assertIsNone(re.search(r"\[\d{1,4}\]", t), (q, lab))
                if not b2.matches(t, ans[q]):
                    lost.append(f"{q}/{lab}")
        self.assertEqual(lost, [], "the packet lost the answer the run gave")
        self.assertEqual({key[q]["source"][lab] for q in both for lab in key[q]["source"]
                          if key[q]["labels"][lab] == "final"}, {"answer"})
        for f in [ck / "MANIFEST.json", *ck.glob("grader-*.md"), *ck.glob("*/question.md")]:
            t = f.read_text()
            for w in ("p4s7", "hard-screen-baseline", "screen-deep", "-baseline"):
                self.assertNotIn(w, t, (f.name, w))
            self.assertIsNone(re.search(r"\{[A-Z_]+\}", t), f.name)
        self.assertEqual(sorted(p.name for p in ck.glob("grader-*.md")), ["grader-b1.md", "grader-b2.md",
                                                                          "grader-b3.md", "grader-b4.md"])
        op = out / "open"
        for q in ("o01", "o02", "o03"):
            self.assertEqual(sorted(p.name for p in (op / q).glob("*.md")), ["A.md", "B.md"])
            g = (op / f"grader-{q}.md").read_text()
            self.assertIsNone(re.search(r"\{[A-Z_]+\}", g), q)
            self.assertIn(f"results/bench2/my-research/{json.loads(TCFG.read_text())['open_refs'][q][0]}", g)
        # rebuild refusals
        r = run("--config", TCFG, "packets", "--out", out, "--allow-missing")
        self.assertIn("built already", r.stderr)
        self.assertEqual(run("--config", TCFG, "packets", "--out", out, "--allow-missing", "--force").returncode, 0)
        key = json.loads((ck / p5.KEY_NAME).read_text())     # labels were reshuffled by the rebuild
        man = json.loads((ck / "MANIFEST.json").read_text())
        okey = json.loads((op / p5.KEY_NAME).read_text())
        # tally before any grade: refused, keys closed
        r = run("--config", TCFG, "tally", "--out", out)
        self.assertEqual(r.returncode, 2)
        self.assertIn("keys left closed", r.stderr)
        # synthetic grades
        rng = random.Random(7)
        want = {"checkable": {}, "harder": {}}
        for line, ids in man["lines"].items():
            cnt = {a: {c: 0 for c in p5.CLASSES + ["not run"]} for a in ("baseline", "final")}
            for q in ids:
                cls, com = {}, {}
                for lab in man["packets"][q]["labels"]:
                    c = rng.choice(p5.CLASSES)
                    cls[lab] = "wrong" if c == "wrong commitment" and q == "h02" else c    # an alias
                    com[lab] = "SYNTHETIC-WRONG" if c == "wrong commitment" else None
                    cnt[key[q]["labels"][lab]][c] += 1
                for a in key[q]["missing"]:
                    cnt[a]["not run"] += 1
                (ck / "grades" / f"{q}.json").write_text(json.dumps(
                    {"id": q, "batch": "test", "graded": "2026-10-29 12:00", "class": cls, "committed_to": com,
                     "why": {k: "synthetic" for k in cls}, "key_doubt": "synthetic doubt" if q == "h04" else None}))
            want[line] = cnt
        r = run("--config", TCFG, "tally", "--out", out)
        self.assertEqual(r.returncode, 2)                     # the open grades are still missing
        self.assertIn("open o01: no grade", r.stderr)
        otot = {}
        for q in ("o01", "o02", "o03"):
            tot = {lab: rng.choice([4, 6.5, 9]) for lab in ("A", "B")}
            otot[q] = {okey[q][lab]: v for lab, v in tot.items()}
            (op / f"grades-{q}.json").write_text(json.dumps({"id": q, "graded": "2026-10-29 12:00",
                                                             "rank": ["A", "B"], "totals": tot,
                                                             "wrong_claims": {"A": 1, "B": 2}}))
        # never rebuilt once graded; a bad class is refused
        r = run("--config", TCFG, "packets", "--out", out, "--allow-missing", "--force")
        self.assertIn("grades exist", r.stderr)
        gp = ck / "grades" / "h05.json"
        good = gp.read_text()
        bad = json.loads(good)
        bad["class"]["A"] = "probably right"
        gp.write_text(json.dumps(bad))
        r = run("--config", TCFG, "tally", "--out", out)
        self.assertEqual(r.returncode, 2)
        self.assertIn("h05: grade file incomplete", r.stderr)
        gp.write_text(good)
        # the tally
        r = run("--config", TCFG, "tally", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        res = json.loads((out / "p5-results.json").read_text())
        for line in ("checkable", "harder"):
            for a in ("baseline", "final"):
                got = {c: res["lines"][line]["counts"][a][c] for c in p5.CLASSES + ["not run"]}
                self.assertEqual(got, want[line][a], (line, a))
        self.assertEqual(res["lines"]["checkable"]["counts"]["final"]["not run"], 5)
        tfold = {"screen-baseline": "baseline", "screen-deep-p4s7": "final"}
        for q in ("o01", "o02", "o03"):
            self.assertEqual(res["open"][q]["totals"], {tfold[f]: v for f, v in otot[q].items()})
            self.assertEqual(res["open"][q]["rank"], [tfold[okey[q]["A"]], tfold[okey[q]["B"]]])
        rep = (out / "REPORT.md").read_text()
        for w in ("## checkable (test)", "## harder checkable (test)", "## open (3)", "| h06 |", "| h08 |",
                  "synthetic doubt", "## Blind grade vs the string cross-check", "engine-P021m.log"):
            self.assertIn(w, rep)
        self.assertIn("one engine for every run: **NO", rep)    # phase 3's baseline ran on another engine
        n1 = len((op / "grades.jsonl").read_text().splitlines())
        self.assertEqual(run("--config", TCFG, "tally", "--out", out).returncode, 0)
        self.assertEqual(n1, 3)
        self.assertEqual(len((op / "grades.jsonl").read_text().splitlines()), 3)


class Checks(unittest.TestCase):
    def test_frozen(self):
        r = run("check-frozen")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("CHANGED", r.stdout)
        self.assertEqual(r.stdout.count(" ok"), 12)

    def test_status(self):
        r = run("--config", TCFG, "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hard-screen", r.stdout)
        r = run("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("p5-harder", r.stdout)

    def test_start_check(self):
        env = {"P5_TEST": "1", "P5_LOG": str(TMP / "start.log"), "P5_PLAN_OUT": str(TMP / "start-plan.json")}
        r = subprocess.run(["bash", str(S / "p5-start.sh"), "--check"], capture_output=True, text=True,
                           env={**os.environ, **env})
        self.assertEqual(r.returncode, 1)
        self.assertIn("the plan was not built", r.stdout)
        r = subprocess.run(["bash", str(S / "p5-start.sh"), "--check"], capture_output=True, text=True,
                           env={**os.environ, **env, "P5_CONFIG": str(TCFG)})
        log = (TMP / "start.log").read_text()
        self.assertNotIn("engine is not the final one", log)
        self.assertNotIn("frozen question / answer file changed", log)
        self.assertIn("engine wanted: P021m.json", log)
        # it stops at whatever is live now (a chain unit, the bench lock) or passes every check
        self.assertTrue(r.returncode == 0 and "every check passed" in r.stdout
                        or r.returncode == 1 and re.search(r"chain unit is active|bench.lock is held|service is running",
                                                           r.stdout), r.stdout)


if __name__ == "__main__":
    print(f"test folder: {TMP}")
    unittest.main(verbosity=2)
