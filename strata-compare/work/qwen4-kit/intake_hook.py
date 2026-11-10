#!/usr/bin/env python3
"""intake_hook.py - Karl 11-09: "when a Qwen4 repo appears, run upstream's tools/qwen4_intake.py --hf on it (header-only
range reads, no download), and put its verdict (case A/B/C, the shape fields that differ, any blockers) in the alert."

The HF watch (dayone.py watch) calls verdict_for() when it alerts on a repo with GGUF files. The intake always runs through
work/r23/nogap-run.sh (nice 19; it waits while a gap is open and freezes if one opens). If no gap is open, it runs inline and
its verdict goes into that alert. If a gap is open, the alert goes out at once saying the verdict follows, and a transient
user unit runs the intake after the gap and sends a second alert with it. A gated or private repo is not read (no login,
nothing worked around). The tool is upstream's stock copy at v0.2.13 (strata-v0213stock), never our patched tree.

  intake_hook.py run REPO REV OUTDIR [--alert] [--dry]   the intake on a Hugging Face repo (--alert: the follow-up alert)
  intake_hook.py local OUTDIR PATH...                     local files (the 11-09 test on our ISTA file and the UD headers)
  intake_hook.py selftest DIR                             synthetic reports and a fake tool; no network, no real alert
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
KIT = WS / "work/qwen4-kit"
PY = WS / ".venv/bin/python"
NOGAP = WS / "work/r23/nogap-run.sh"
GAP_LOCKPID = WS / "tmp/port-gap.lockpid"
NOTES_MD = WS / "NOTES.md"
NTFY_FILE = KIT / "hfwatch/ntfy-topic"   # read inside the code only, never printed or logged (absent today: alert-push relays)
UA = {"User-Agent": "strata-compare-dayone/1.0"}
TIMEOUT_S = 1800
SHORT_MAX = 72                            # alert-push cuts a message at 180 characters; the verdict goes first


def tool() -> Path:
    return Path(os.environ.get("Q4_INTAKE_TOOL", str(WS / "strata-v0213stock/tools/qwen4_intake.py")))


def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def gap_open() -> bool:
    try:
        return GAP_LOCKPID.stat().st_size > 0
    except OSError:
        return False


def phone_safe(s: str) -> str:
    """alert-push drops every word with a / ~ @ or backslash: keep the words, lose the slashes"""
    return re.sub(r"\s+", " ", s.replace("/", " ").replace("\\", " ").replace("~", "").replace("@", " at ")).strip()


# ---------------------------------------------------------------------------------------------------------- the summary
def _model_sets(report: dict) -> list[dict]:
    return [s for s in report.get("sets", []) if (s.get("verdict") or {}).get("case") in ("A", "B", "C")]


def _set_name(s: dict) -> str:
    f = (s.get("files") or [{}])[0].get("name") or "?"
    return re.sub(r"-0+1-of-0*\d+\.gguf$|\.gguf$", "", os.path.basename(f))


def _diff_text(d: dict, short: bool) -> str:
    want = d.get("kernels_built_for", d.get("limit"))
    return f"{d.get('field')} {d.get('got')}" + ("" if short else f" (built for {want})" if "kernels_built_for" in d else f" (limit {want})")


def summarize(report: dict) -> dict:
    """{'short': <= SHORT_MAX characters for the alert, 'long': the NOTES line's text, 'cases': {case: n}}"""
    sets = _model_sets(report)
    if not sets:
        other = [(s.get("verdict") or {}).get("reading", "?") for s in report.get("sets", [])]
        txt = "no model set in the GGUF files" + (f" ({'; '.join(other)[:80]})" if other else "")
        return {"short": "intake: " + txt[:SHORT_MAX - 8], "long": txt, "cases": {}}
    cases: dict[str, int] = {}
    for s in sets:
        c = s["verdict"]["case"]
        cases[c] = cases.get(c, 0) + 1
    worst = "C" if "C" in cases else "B" if "B" in cases else "A"
    w = next(s for s in sets if s["verdict"]["case"] == worst)
    v = w["verdict"]
    if len(cases) == 1:
        head = f"intake case {worst}" + (f" ({len(sets)} sets)" if len(sets) > 1 else "")
    else:
        head = "intake " + " ".join(f"{c}x{n}" for c, n in sorted(cases.items()))
    if worst == "A":
        detail = "runs now" + (f" on {', '.join(v.get('backends') or [])}" if v.get("backends") else "")
    elif worst == "B":
        detail = ", ".join(_diff_text(d, True) for d in v.get("shape_fields_that_differ") or []) or "a new name"
    else:
        detail = (v.get("blockers") or ["?"])[0]
    short = phone_safe(f"{head}: {detail}")
    if len(short) > SHORT_MAX:
        short = short[:SHORT_MAX - 1].rstrip(" ,;:") + "…"
    parts = []
    for s in sets:
        sv = s["verdict"]
        p = f"{_set_name(s)} CASE {sv['case']} ({sv.get('reading')})"
        if sv.get("backends"):
            p += f" on {', '.join(sv['backends'])}"
        if sv.get("shape_fields_that_differ"):
            p += "; shape: " + ", ".join(_diff_text(d, False) for d in sv["shape_fields_that_differ"])
        if sv.get("blockers"):
            p += f"; {len(sv['blockers'])} blocker(s): " + " | ".join(sv["blockers"][:3]) + (" | ..." if len(sv["blockers"]) > 3 else "")
        if sv.get("warnings"):
            p += f"; {len(sv['warnings'])} warning(s): " + " | ".join(sv["warnings"][:2])
        parts.append(p)
    return {"short": short, "long": "; ".join(parts), "cases": cases}


# ---------------------------------------------------------------------------------------------------------- running it
def run_tool(args: list[str], outdir: Path, timeout: int = TIMEOUT_S) -> dict:
    """the intake through nogap-run; {'ok', 'json', 'log', 'error', 'summary'}"""
    outdir.mkdir(parents=True, exist_ok=True)
    js, lg = outdir / "intake.json", outdir / "intake.log"
    t = tool()
    if not t.exists():
        return {"ok": False, "json": str(js), "log": str(lg), "error": f"the intake tool is missing ({t.parent.parent.name}): not run"}
    if js.exists():
        js.rename(js.with_suffix(f".json.before-{time.strftime('%m%d%H%M%S')}"))
    cmd = ["/bin/bash", str(NOGAP), str(lg), str(PY), "-I", "-B", str(t), *args, "--out", str(js), "--quiet"]
    with open(lg, "a") as f:
        f.write(f"{now()} intake_hook: {' '.join(shlex.quote(c) for c in cmd[3:])}\n")
    try:
        rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=timeout, pass_fds=()).returncode
    except subprocess.TimeoutExpired:
        return {"ok": False, "json": str(js), "log": str(lg), "error": f"still running after {timeout // 60} min (see its log)"}
    if rc != 0 or not js.exists():
        tail = ""
        try:
            lines = [x for x in lg.read_text(errors="replace").splitlines() if x.strip() and "nogap-run:" not in x]
            tail = lines[-1][-160:] if lines else ""
        except OSError:
            pass
        return {"ok": False, "json": str(js), "log": str(lg), "error": f"rc {rc}" + (f": {tail}" if tail else "")}
    rep = json.loads(js.read_text())
    return {"ok": True, "json": str(js), "log": str(lg), "error": None, "summary": summarize(rep)}


def hf_args(repo: str, rev: str) -> list[str]:
    return ["--hf", repo, "--rev", rev]


def alert(title: str, body: str, notes_line: str, dry: bool) -> None:
    """as dayone.py's hfw_alert: desktop (app "Strata", critical: alert-push relays it to ntfy), a NOTES.md line, ntfy direct
    only if that file is set up"""
    if dry:
        print(f"[DRY] notify-send -a Strata -u critical {title!r} {body!r}")
        print(f"[DRY] NOTES.md: {now()[5:]} QWEN4 HF WATCH: {notes_line}")
        return
    subprocess.run(["notify-send", "-a", "Strata", "-u", "critical", title, body], capture_output=True)
    with open(NOTES_MD, "a") as f:
        f.write(f"{now()[5:]} QWEN4 HF WATCH: {notes_line}\n")
    if NTFY_FILE.exists():
        try:
            url = NTFY_FILE.read_text().strip()
            urllib.request.urlopen(urllib.request.Request(url, data=body.encode(), headers={**UA, "Title": title}), timeout=20)
        except (OSError, ValueError):
            print("ntfy: the post failed (the topic is not printed)")


def verdict_for(rid: str, sha: str, is_open: bool, n_gguf: int, outdir: Path, dry: bool = False) -> dict:
    """for the HF watch's alert: {'short': text for the alert body, 'long': text for the NOTES line}"""
    if not n_gguf:
        return {"short": "intake: no GGUF yet", "long": "INTAKE not run: no GGUF files in the repo yet"}
    if not is_open:
        return {"short": "intake: gated, not read", "long": "INTAKE not run: the repo is gated or private (no login; not worked around)"}
    od = outdir / "intake"
    if gap_open():
        unit = f"q4intake-{re.sub(r'[^a-z0-9]', '', rid.lower())[:16]}-{time.strftime('%m%d%H%M')}"
        cmd = ["systemd-run", "--user", "--unit", unit, "--collect", "-p", "Nice=19", "-p", "MemoryHigh=2G",
               str(PY), "-I", "-B", str(Path(__file__).resolve()), "run", rid, sha, str(od), "--alert"]
        if dry:
            return {"short": "intake after the open gap (2nd alert)",
                    "long": f"INTAKE: a gap is open - [DRY] would start unit {unit}: {' '.join(shlex.quote(c) for c in cmd[4:])}"}
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            return {"short": "intake after the open gap (2nd alert)",
                    "long": f"INTAKE: a gap is open - unit {unit} runs it through nogap-run after the gap and sends a second alert"}
        return {"short": "intake: start FAILED", "long": f"INTAKE: a gap is open and the unit did not start (rc {r.returncode}: {r.stderr[-160:]})"}
    res = run_tool(hf_args(rid, sha), od)
    if not res["ok"]:
        return {"short": phone_safe(f"intake failed: {res['error']}")[:SHORT_MAX], "long": f"INTAKE FAILED: {res['error']} (log {res['log']})"}
    s = res["summary"]
    return {"short": s["short"], "long": f"INTAKE {s['long']} (report {res['json']})"}


# ---------------------------------------------------------------------------------------------------------- commands
def cmd_run(argv: list[str]) -> int:
    dry = "--dry" in argv
    send = "--alert" in argv
    pos = [x for x in argv if not x.startswith("--")]
    rid, rev, od = pos[0], pos[1], Path(pos[2])
    res = run_tool(hf_args(rid, rev), od)
    if res["ok"]:
        s = res["summary"]
        body = phone_safe(f"{rid}: {s['short']}")
        notes = f"{rid}@{rev[:12]}: INTAKE (after the gap) {s['long']} (report {res['json']})"
    else:
        body = phone_safe(f"{rid}: intake failed: {res['error']}")
        notes = f"{rid}@{rev[:12]}: INTAKE (after the gap) FAILED: {res['error']} (log {res['log']})"
    print(body)
    print(notes)
    if send:
        alert("Qwen4 intake verdict", body, notes, dry)
    return 0 if res["ok"] else 1


def cmd_local(argv: list[str]) -> int:
    od, paths = Path(argv[0]), argv[1:]
    res = run_tool(paths, od)
    if not res["ok"]:
        print(f"intake failed: {res['error']} (log {res['log']})")
        return 1
    print(f"short: {res['summary']['short']}")
    print(f"long:  {res['summary']['long']}")
    print(f"json:  {res['json']}")
    return 0


def cmd_selftest(argv: list[str]) -> int:
    d = Path(argv[0]).resolve()
    d.mkdir(parents=True, exist_ok=True)
    fails = []

    def chk(name, ok, got=""):
        print(("ok    " if ok else "FAIL  ") + name + ("" if ok else f"   got: {got!r}"))
        if not ok:
            fails.append(name)

    def rset(name, case, diffs=(), blockers=(), backends=(), warnings=()):
        return {"files": [{"name": name}], "verdict": {"case": case, "reading": {"A": "runs now", "B": "known layer types at a new shape or name",
                "C": "port first"}[case], "backends": list(backends), "blockers": list(blockers), "warnings": list(warnings),
                "shape_fields_that_differ": [{"key": "qwen4exp." + k, "field": k, "got": g, "kernels_built_for": w} for k, g, w in diffs]}}

    drafter = {"files": [{"name": "mtp-Q8_0.gguf"}], "verdict": {"case": "-", "reading": "a separate MTP drafter file, not a model"}}
    a = summarize({"sets": [rset("Qwen4-Flash-Q4_K_M-00001-of-00003.gguf", "A", backends=("CUDA", "HIP")), drafter]})
    chk("case A: short", a["short"] == "intake case A: runs now on CUDA, HIP", a["short"])
    chk("case A: the drafter set is not counted", a["cases"] == {"A": 1}, a["cases"])
    diffs = [("n_embd", 3072, 2560), ("n_head", 32, 24), ("ssm_v_heads", 64, 48), ("n_expert", 256, 512), ("n_expert_used", 8, 10),
             ("n_ff", 1024, 640)]
    b = summarize({"sets": [rset("Qwen4-Flash-UD-Q2_K_XL-00001-of-00002.gguf", "B", diffs), rset("Qwen4-Flash-Q8_0.gguf", "B", diffs)]})
    chk("case B: short starts with the case and the first fields", b["short"].startswith("intake case B (2 sets): n_embd 3072, n_head 32"), b["short"])
    chk("case B: short is cut to the alert's room", len(b["short"]) <= SHORT_MAX, len(b["short"]))
    chk("case B: long names what the kernels were built for", "n_embd 3072 (built for 2560)" in b["long"] and "n_ff 1024 (built for 640)" in b["long"], b["long"])
    chk("case B: long names each set", "Qwen4-Flash-UD-Q2_K_XL CASE B" in b["long"] and "Qwen4-Flash-Q8_0 CASE B" in b["long"], b["long"])
    c = summarize({"sets": [rset("x-IQ1_M.gguf", "C", blockers=("CUDA/HIP/SYCL/Metal: routed_gate IQ1_M (480 tensors, e.g. blk.0.ffn_gate_exps.weight): no kernel",
                                                                  "tokenizer: unknown pre-tokenizer 'qwen4'", "b3", "b4")),
                            rset("x-Q4_K.gguf", "A", backends=("CUDA",))]})
    chk("mixed: the worst case leads", c["short"].startswith("intake Ax1 Cx1: CUDA HIP SYCL Metal: routed_gate IQ1_M"), c["short"])
    chk("mixed: no slash survives for the phone", "/" not in c["short"], c["short"])
    chk("case C: long lists 3 blockers and says more", "2 blocker(s)" not in c["long"] and "4 blocker(s)" in c["long"] and "| ..." in c["long"], c["long"])
    n = summarize({"sets": [drafter]})
    chk("no model set", n["short"].startswith("intake: no model set") and not n["cases"], n)
    chk("phone_safe", phone_safe("unsloth/Qwen4-Flash: a/b ~x @y") == "unsloth Qwen4-Flash: a b x at y", phone_safe("unsloth/Qwen4-Flash: a/b ~x @y"))

    # the runner with a fake tool (through the real nogap-run: no gap is open in a selftest run, or it waits like the real one)
    fake = d / "fake_intake.py"
    fake.write_text("import json,sys\na=sys.argv[1:]\nout=a[a.index('--out')+1]\n"
                    "if '--hf' in a and 'boom' in a[a.index('--hf')+1]:\n    print('HTTP Error 500: fake'); sys.exit(2)\n"
                    "json.dump({'sets':[{'files':[{'name':'F-Q4_K_M-00001-of-00002.gguf'}],'verdict':{'case':'B','reading':'r','backends':[],"
                    "'blockers':[],'warnings':[],'shape_fields_that_differ':[{'key':'qwen4exp.block_count','field':'n_layers','got':60,"
                    "'kernels_built_for':48}]}}]},open(out,'w'))\n")
    os.environ["Q4_INTAKE_TOOL"] = str(fake)
    if gap_open():
        print("note  a gap is open: the runner tests would wait in nogap-run - skipped")
    else:
        r = run_tool(hf_args("unsloth/Qwen4-Flash-GGUF", "a" * 40), d / "run-ok")
        chk("runner: ok, through nogap-run", r["ok"] and r["summary"]["short"] == "intake case B: n_layers 60", r)
        chk("runner: nogap-run logged the start", "nogap-run: start:" in Path(r["log"]).read_text(), Path(r["log"]).read_text()[-300:])
        r2 = run_tool(hf_args("unsloth/boom", "b" * 40), d / "run-fail")
        chk("runner: a failure carries the tool's last line", not r2["ok"] and "HTTP Error 500: fake" in (r2["error"] or ""), r2)
        v = verdict_for("unsloth/Qwen4-Flash-GGUF", "c" * 40, True, 3, d / "vf")
        chk("verdict_for: inline when no gap is open", v["short"] == "intake case B: n_layers 60" and v["long"].startswith("INTAKE F-Q4_K_M CASE B"), v)
    os.environ["Q4_INTAKE_TOOL"] = str(d / "missing.py")
    if not gap_open():
        m = verdict_for("unsloth/Qwen4-Flash-GGUF", "d" * 40, True, 3, d / "vm")
        chk("verdict_for: a missing tool says so", m["short"].startswith("intake failed: the intake tool is missing"), m)
    chk("verdict_for: no GGUF", verdict_for("Qwen/Qwen4-Flash", "e" * 40, True, 0, d / "x")["short"] == "intake: no GGUF yet")
    chk("verdict_for: gated is not read", verdict_for("Qwen/Qwen4-Flash", "e" * 40, False, 4, d / "x")["short"] == "intake: gated, not read")
    # a gap open: the follow-up unit (dry) - simulated by pointing the lockpid check at a file of ours
    global GAP_LOCKPID
    real = GAP_LOCKPID
    GAP_LOCKPID = d / "fake-lockpid"
    GAP_LOCKPID.write_text("12345\n")
    try:
        g = verdict_for("unsloth/Qwen4-Flash-GGUF", "f" * 40, True, 3, d / "vg", dry=True)
        chk("verdict_for: a gap open -> the second alert, unit (dry)", g["short"] == "intake after the open gap (2nd alert)"
            and "[DRY] would start unit q4intake-unslothqwen4flas-" in g["long"] and " run unsloth/Qwen4-Flash-GGUF " in g["long"], g)
    finally:
        GAP_LOCKPID = real
    os.environ.pop("Q4_INTAKE_TOOL", None)
    print(f"selftest: {len(fails)} failure(s)")
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("run", "local", "selftest"):
        print(__doc__)
        return 2
    return {"run": cmd_run, "local": cmd_local, "selftest": cmd_selftest}[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
