#!/usr/bin/env python3
"""research-mcp.py - an MCP server (stdio) that lets Jan start and follow deep research on this PC (2026-10-17).

Jan starts it (Settings > MCP Servers: "deep-research", command /usr/bin/python3 -I <this file>). It only reads and
writes job files (jobs/<id>/job.json, via research_common.py); the research itself is run by the runner service
(tools/research-runner.py, systemd user unit deep-research-runner.service), so a research keeps going when Jan is
closed. Standard library only; it opens no network connections.

Tools: research_start, research_quick (2026-10-18: plain LDR's quick summary, 1-3 min), research_status, research_list,
research_pause, research_resume, research_cancel, research_report. Log: logs/research-mcp.log (every call with its arguments, so the file-attachment test can see what
Jan passed).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/USER/ai/deep-research/tools")
import research_common as rc  # noqa: E402
from tool_choice import PAST_REPORTS, RESEARCH_FAILED, TOOL_CHOICE  # noqa: E402

LOG = rc.WS / "logs" / "research-mcp.log"
INBOX = rc.WS / "inbox"              # 2026-10-19: "use my inbox" - Jan cannot hand attachments to a tool
LDR_LOG = rc.WS / "logs" / "ldr-web.log"   # run-ldr.sh's link to the current LDR log
PART_CHARS = 12_000
TEXT_EXT = {".md", ".markdown", ".txt", ".rst", ".py", ".json", ".jsonl", ".csv", ".tsv", ".html", ".htm", ".xml",
            ".yaml", ".yml", ".toml", ".log", ".tex", ".pdf", ".c", ".cc", ".cpp", ".h", ".hpp", ".cu", ".rs", ".go",
            ".js", ".ts", ".sh", ".ini", ".cfg", ".conf", ".org", ".adoc"}
MAX_FILES = 40

INSTRUCTIONS = (
    TOOL_CHOICE + " " + PAST_REPORTS + " " + RESEARCH_FAILED + " "
    "research_quick answers in about 1-3 minutes; if the answer is not back yet, read it with research_report and the "
    "job id when the user asks. "
    "Deep research runs on this PC in the background and takes hours (default 3 h of research plus the report). "
    "When the user says to use their inbox (\"use my inbox\", \"the files in my inbox\"), call research_start with "
    "use_inbox: true - the research then reads the files in ~/ai/deep-research/inbox (research_inbox lists them). "
    "Use research_start only when the user asks for deep research on a question; tell them the job id, that a desktop "
    "notification comes when it is done, and that research_status shows progress. Files: pass full paths of files or "
    "folders in `files` (attachments in Jan cannot be handed to this tool). Read a finished report with "
    "research_report, part by part; give the user the HTML path to open the whole report.")

TOOLS = [
    {"name": "research_start",
     "description": ("Queue a deep research job (runs for hours in the background on this PC, one job at a time). "
                     "Returns the job id. " + TOOL_CHOICE),
     "inputSchema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "The research question, complete and self-contained."},
         "files": {"type": "array", "items": {"type": "string"},
                   "description": ("Optional: full paths of the user's files or folders to research with "
                                   "(e.g. /home/user/notes/report.md). The research reads them itself, in pieces.")},
         "time_budget_minutes": {"type": "number",
                                 "description": "Optional research time in minutes (default 180; the report takes extra)."},
         "use_inbox": {"type": "boolean",
                       "description": "true when the user says to use their inbox: every file in ~/ai/deep-research/inbox "
                                      "is read by the research (copied into the job when it is queued)."}},
         "required": ["question"]}},
    {"name": "research_inbox",
     "description": "List the files in the user's research inbox (~/ai/deep-research/inbox): names and sizes.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "research_quick",
     "description": ("Quick web research, only when the user asks for it (\"quick research on ...\"): searches, reads "
                     "the top pages and answers with sources in about 1-3 "
                     "minutes (no long report). Returns the answer if it is ready within a few seconds, else the job "
                     "id to read it later with research_report. " + TOOL_CHOICE + " " + RESEARCH_FAILED),
     "inputSchema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "The question, complete and self-contained."}},
         "required": ["question"]}},
    {"name": "research_status",
     "description": "Progress of a research job (the running one if no id is given): state, time used, what it found so far.",
     "inputSchema": {"type": "object", "properties": {"job": {"type": "string", "description": "Job id (optional)."}}}},
    {"name": "research_list",
     "description": "All research jobs: queued, running, paused and finished, with their report files.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "research_pause",
     "description": "Pause a research job between model calls (its research clock stops). The running one if no id is given.",
     "inputSchema": {"type": "object", "properties": {"job": {"type": "string"}}}},
    {"name": "research_resume",
     "description": "Resume a paused research job.",
     "inputSchema": {"type": "object", "properties": {"job": {"type": "string"}}}},
    {"name": "research_cancel",
     "description": "Cancel a research job (queued or running). A running job stops at its next step without a report.",
     "inputSchema": {"type": "object", "properties": {"job": {"type": "string"}}}},
    {"name": "research_report",
     "description": ("The finished report of a job, in parts of about 12,000 characters (part 1 first; the answer says "
                     "how many parts there are), with the date it finished and the paths of its .md and .html files. "
                     "Without a job id it lists the finished reports to choose from. " + PAST_REPORTS + " " +
                     RESEARCH_FAILED),
     "inputSchema": {"type": "object", "properties": {"job": {"type": "string", "description": "Job id (research_list or research_report without one lists them)."},
                                                      "part": {"type": "integer", "description": "Part number, from 1."}}}},
]


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


# -- helpers -------------------------------------------------------------------------------------------------------------
def expand_files(items: list) -> tuple[list[str], list[str]]:
    """Paths of files or folders -> text-like files (folders recursively, up to MAX_FILES); problems listed."""
    out, problems = [], []
    for it in items or []:
        p = Path(os.path.expanduser(str(it).strip().strip('"').removeprefix("file://"))).resolve()
        if not p.exists():
            problems.append(f"not found: {it}")
            continue
        if p.is_file():
            out.append(str(p))
            continue
        for q in sorted(p.rglob("*")):
            if q.is_file() and q.suffix.lower() in TEXT_EXT and not any(part.startswith(".") for part in q.parts):
                out.append(str(q))
            if len(out) >= MAX_FILES:
                problems.append(f"{p}: only the first {MAX_FILES} files are used")
                break
    seen, uniq = set(), []
    for f in out:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq, problems


def _first_line(text: str) -> str:
    """A finding's first real line: no preamble ("Below is ..."), no heading marks or bullets."""
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw or raw.startswith(("#", "|", "---", "```", "===")):
            continue                                     # headings, table rows, rules, code
        s = raw.lstrip(">*-•0123456789. ").replace("**", "").strip()
        if len(s) < 30 or s.endswith(":") or \
                re.match(r"(?i)(below is|here is|here are|this is|i have|i've|consolidated|summary|findings)\b", s):
            continue
        return s
    return (text or "").strip().splitlines()[0][:200] if (text or "").strip() else ""


def evidence_summary(job: dict) -> dict:
    """Counts, whether the lead has finished (the report stage started) and the latest subtopic findings, from the
    current run's evidence file (2026-10-19)."""
    s = {"searches": 0, "pages_read": 0, "subagents": 0, "lead_done": False, "findings": []}
    for r in job.get("runs", []):
        ev = Path(r.get("out_dir", "")) / "evidence.jsonl"
        if not ev.exists():
            continue
        try:
            with open(ev, encoding="utf-8") as f:
                for line in f:
                    t = line[:200]
                    if '"type": "search"' in t:
                        s["searches"] += 1
                    elif '"type": "fetch"' in t:
                        s["pages_read"] += 1
                    elif '"type": "subagent"' in t:
                        s["subagents"] += 1
                        try:
                            d = json.loads(line)
                            s["findings"].append((str(d.get("topic") or "")[:70], _first_line(str(d.get("text") or ""))[:120]))
                        except ValueError:
                            pass
                    elif '"kind": "lead_answer"' in t and r is job["runs"][-1]:
                        s["lead_done"] = True
        except OSError:
            pass
    return s


def ldr_milestones() -> dict:
    """The current LDR log's latest milestones: the subtopic being researched and the latest stage line."""
    out = {"subtopic": None, "last": None}
    try:
        with open(LDR_LOG, "rb") as f:
            f.seek(max(0, LDR_LOG.stat().st_size - 300_000))
            lines = [l for l in f.read().decode("utf-8", "replace").splitlines() if "| MILESTONE |" in l]
    except OSError:
        return out
    for l in lines:
        msg = l.split(" - ", 1)[-1].strip()
        m = re.search(r"Investigating subtopic:\s*\"?(.+?)\"?\s*$", msg)
        if m:
            out["subtopic"] = m.group(1)[:160]
        out["last"] = msg[:160]
    return out


def evidence_counts(job: dict) -> dict:
    """Searches, pages read and subagents so far, from the runs' evidence files."""
    c = {"searches": 0, "pages_read": 0, "subagents": 0}
    for r in job.get("runs", []):
        ev = Path(r.get("out_dir", "")) / "evidence.jsonl"
        if not ev.exists():
            continue
        try:
            with open(ev, encoding="utf-8") as f:
                for line in f:
                    t = line[:200]
                    if '"type": "search"' in t:
                        c["searches"] += 1
                    elif '"type": "fetch"' in t:
                        c["pages_read"] += 1
                    elif '"type": "subagent"' in t:
                        c["subagents"] += 1
        except OSError:
            pass
    return c


def queue_position(job: dict) -> int:
    q = [j for j in rc.all_jobs() if j.get("state") in ("queued",) + rc.ACTIVE]
    q.sort(key=lambda j: (j.get("state") not in rc.ACTIVE, j.get("mode") != "quick"))   # the runner's order
    ids = [j["id"] for j in q]
    return ids.index(job["id"]) if job["id"] in ids else -1


def when_text(job: dict) -> str:
    s = rc.settings()
    pos = queue_position(job)
    if job.get("state") in rc.ACTIVE:
        return "it is running now"
    ahead = pos if pos > 0 else 0
    night = rc.is_night(s=s)
    parts = []
    if ahead:
        parts.append(f"after {ahead} job{'s' if ahead > 1 else ''} ahead of it")
    if night:
        parts.append(f"after the night pause ({rc.night_end_text(s)})")
    if rc.bench_running():
        parts.append("after the measurement question that is using the research engine now")
    return "it starts " + (" and ".join(parts) if parts else "within a minute")


def outcome_line(job: dict) -> str | None:
    """2026-10-19 (the user's rule: failed research must never look like research): a job that ended without a report,
    or a quick answer that has not started, said plainly; None for a report or research that is going."""
    if job.get("report_md"):
        return None
    if job.get("state") in rc.FINAL:
        t0 = job.get("started") or job.get("created")
        mins = f"{max(0.0, (float(job.get('finished') or time.time()) - float(t0 or time.time())) / 60):.0f} min"
        if job.get("stop_reason"):
            return f"FAILED: stopped at {mins} ({job['stop_reason']}), no report - nothing was researched."
        if job.get("state") == "failed":
            return f"FAILED after {mins}: {job.get('note') or 'no report was written'} - no report, nothing was researched."
        return (f"CANCELLED{' by you' if job.get('cancel_requested') or job.get('user_cancelled') else ''}"
                f" ({job.get('note') or 'cancelled'}): no report - nothing was researched.")
    if job.get("mode") == "quick" and job.get("state") == "queued" and (
            rc.bench_running() or rc.is_night(s=rc.settings()) or queue_position(job) > 0):
        return f"NOT STARTED: this quick answer cannot start now - {when_text(job)}; no research has been done."
    return None


def describe(job: dict, full: bool = True) -> str:
    s = rc.settings()
    lines = [f"Job {job['id']}: {job.get('state')}" + (f" - {job['note']}" if job.get("note") else ""),
             f"Question: {job['question']}"]
    oc = outcome_line(job)
    if oc:
        lines.insert(0, oc)
    budget = float(job.get("budget_minutes") or s["default_budget_minutes"]) * 60
    used = job.get("research_used_s")
    active = job.get("state") in rc.ACTIVE
    if job.get("mode") == "quick":
        lines.append("Quick answer (plain web research, usually 1-3 minutes)"
                     + (f"; {when_text(job)}" if job.get("state") == "queued" else ""))
        if active and full:
            ms = ldr_milestones()
            if ms["last"]:
                lines.append(f"Stage: {ms['last']}")
    elif job.get("state") == "queued":
        lines.append(f"Queued: {when_text(job)}. Research time {rc.fmt_minutes(budget)} plus the report.")
    else:
        ev = evidence_summary(job) if full else None
        out = Path((job.get("runs") or [{}])[-1].get("out_dir", ""))
        ms = ldr_milestones() if (active and full) else {"subtopic": None, "last": None}
        left = max(0.0, budget - float(used or 0))
        if not active:
            stage = None
        elif (out / "report.md").exists():
            stage = "finishing (the report is written and checked)"
        elif (out / "report-unverified.md").exists():
            stage = "checking the report's citations"
        elif ev and ev["lead_done"]:
            stage = "writing the report" + (f" - {ms['last']}" if ms["last"] and ms["last"].startswith("Writing") else "")
        else:
            stage = f"researching ({rc.fmt_minutes(left)} of research time left, then the report)"
        if stage:
            lines.append(f"Stage: {stage}")
        lines.append(f"Research time used: {rc.fmt_minutes(used)} of {rc.fmt_minutes(budget)}"
                     + (f" ({rc.fmt_minutes(left)} left)" if active and left > 0 else "")
                     + " (the report stage comes after)")
        if stage and stage.startswith("researching") and ms["subtopic"]:
            lines.append(f"Now: {ms['subtopic']}")
    if job.get("progress") is not None and job.get("state") in rc.ACTIVE:
        lines.append(f"LDR progress: {job['progress']}%")
    if job.get("gate") and job.get("state") in rc.ACTIVE:
        lines.append(f"Waiting between steps: {job['gate']}")
    if full and job.get("runs") and job.get("mode") != "quick":
        c = evidence_summary(job)
        lines.append(f"So far: {c['searches']} searches, {c['pages_read']} pages or file parts read, "
                     f"{c['subagents']} subtopics researched" + (f", in {len(job['runs'])} runs (interrupted and continued)"
                                                                 if len(job["runs"]) > 1 else ""))
        if c["findings"]:
            lines.append("Latest findings:")
            lines += [f"- {topic}: {line}" for topic, line in c["findings"][-4:]]
    if job.get("files"):
        lines.append("Files: " + ", ".join(Path(f).name for f in job["files"][:12]) + (" ..." if len(job["files"]) > 12 else ""))
    if job.get("tooltags"):
        lines.append(f"Answers cut by tool-call text in prose: {sum(job['tooltags'].values())}")
    if job.get("report_md"):
        lines.append(f"Report: {job['report_md']} (HTML: {job.get('report_html')}) - read it with research_report")
    if job.get("user_paused") and job.get("state") not in rc.FINAL:
        lines.append("Paused by you: research_resume continues it.")
    return "\n".join(lines)


def split_parts(text: str) -> list[str]:
    """~PART_CHARS per part, cut at section headings, else at paragraphs."""
    blocks = re.split(r"(?m)^(?=#{1,3} )", text)
    parts, cur = [], ""
    for b in blocks:
        while len(b) > PART_CHARS:
            cut = b.rfind("\n\n", 0, PART_CHARS)
            cut = cut if cut > PART_CHARS // 3 else PART_CHARS
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(b[:cut])
            b = b[cut:].lstrip("\n")
        if len(cur) + len(b) > PART_CHARS and cur:
            parts.append(cur)
            cur = ""
        cur += b
    if cur.strip():
        parts.append(cur)
    return parts or [""]


# -- tools ---------------------------------------------------------------------------------------------------------------
def t_start(args: dict) -> str:
    q = str(args.get("question") or "").strip()
    if len(q) < 10:
        return "Please give the full research question."
    s = rc.settings()
    try:
        budget = float(args.get("time_budget_minutes") or s["default_budget_minutes"])
    except (TypeError, ValueError):
        budget = s["default_budget_minutes"]
    budget = max(5.0, min(budget, s["max_budget_minutes"]))
    files, problems = expand_files(args.get("files") or [])
    jid = rc.new_job_id(q)
    inbox_note = None
    if args.get("use_inbox"):
        got, inbox_problems = expand_files([str(INBOX)]) if INBOX.exists() else ([], [])
        problems += inbox_problems
        if not got:
            return f"Your inbox ({INBOX}) is empty: put the files there first, then ask again. Nothing was queued."
        dest = rc.JOBS / jid / "inbox"
        dest.mkdir(parents=True, exist_ok=True)
        import shutil
        copied = []
        for src in got:
            rel = Path(src).relative_to(INBOX.resolve()) if Path(src).is_relative_to(INBOX.resolve()) else Path(Path(src).name)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied.append(str(target))
        files += copied
        inbox_note = f"From your inbox ({len(copied)}, copied into the job, so you can empty the inbox now): " + \
            ", ".join(str(Path(c).relative_to(dest)) for c in copied[:12]) + (" ..." if len(copied) > 12 else "")
    with rc.jobs_lock():
        job = {"id": jid, "question": q, "files": files, "budget_minutes": budget,
               "created": time.time(), "state": "queued", "note": "queued", "history": [], "runs": []}
        if inbox_note:
            job["inbox"] = True
        rc.save_job(job)
    msg = [f"Research queued as job {job['id']}.", f"Question: {q}",
           f"Research time: {rc.fmt_minutes(budget * 60)}, then the report (often another 30-90 min). {when_text(job).capitalize()}.",
           "A desktop notification comes when it finishes; research_status shows progress, research_report the result."]
    if inbox_note:
        msg.append(inbox_note)
    if files and not inbox_note:
        msg.append(f"Files ({len(files)}): " + ", ".join(Path(f).name for f in files[:12]) + (" ..." if len(files) > 12 else ""))
    if problems:
        msg.append("File problems: " + "; ".join(problems))
    return "\n".join(msg)


def t_quick(args: dict) -> str:
    q = str(args.get("question") or "").strip()
    if len(q) < 10:
        return "Please give the full question."
    s = rc.settings()
    with rc.jobs_lock():
        job = {"id": rc.new_job_id(q), "question": q, "files": [], "budget_minutes": 15, "mode": "quick",
               "created": time.time(), "state": "queued", "note": "queued", "history": [], "runs": []}
        rc.save_job(job)
    deadline = time.time() + max(0.0, s["quick_wait_seconds"])
    while time.time() < deadline:
        j = rc.load_job(job["id"]) or job
        if j.get("state") in rc.FINAL:
            return t_report({"job": j["id"]})   # the report, or FAILED / CANCELLED said plainly
        time.sleep(1.0)
    j = rc.load_job(job["id"]) or job
    oc = outcome_line(j)
    if oc:                                     # e.g. NOT STARTED behind a measurement run: do not wait for it
        if oc.startswith("NOT STARTED"):       # withdrawn, so it does not run hours later after the fallback answer
            with rc.jobs_lock():
                jj = rc.load_job(j["id"]) or j
                jj.update(cancel_requested=True, stop_reason="not started in time (the research engine was busy)")
                rc.save_job(jj)
            oc += " The quick answer was withdrawn."
        return f"{oc}\nJob {j['id']}.\n{RESEARCH_FAILED}"
    return (f"Quick answer job {j['id']}: {j.get('state')} - {j.get('note') or ''}. "
            f"{'It is running; ' if j.get('state') in rc.ACTIVE else when_text(j).capitalize() + '; '}"
            f"answers usually take 1-3 minutes. Read it with research_report (job {j['id']}); a desktop notification "
            f"comes when it is ready.")


def t_inbox(args: dict) -> str:
    INBOX.mkdir(parents=True, exist_ok=True)
    got, problems = expand_files([str(INBOX)])
    if not got:
        return f"Your inbox ({INBOX}) is empty."
    lines = [f"Your inbox ({INBOX}) has {len(got)} file(s) the research can read:"]
    for f in got:
        p = Path(f)
        lines.append(f"- {p.relative_to(INBOX.resolve()) if p.is_relative_to(INBOX.resolve()) else p.name} "
                     f"({p.stat().st_size / 1024:,.0f} KB)")
    if problems:
        lines.append("Note: " + "; ".join(problems))
    others = [p.name for p in INBOX.iterdir() if p.is_file() and str(p.resolve()) not in got]
    if others:
        lines.append("Not readable as text (skipped): " + ", ".join(others[:10]))
    return "\n".join(lines)


def t_status(args: dict) -> str:
    job = rc.find_job(args.get("job"))
    if not job:
        return "No research job found." if not args.get("job") else f"No job matches {args.get('job')!r}."
    return describe(job)


def t_list(args: dict) -> str:
    jobs = rc.all_jobs()
    if not jobs:
        return "No research jobs yet."
    out = []
    for j in reversed(jobs[-30:]):
        when = datetime.fromtimestamp(j.get("created", 0)).strftime("%m-%d %H:%M")
        oc = outcome_line(j)
        line = f"- {j['id']} [{j.get('state')}{', ' + oc.split(':')[0] + ', no report' if oc else ''}] {when}: {j['question'][:90]}"
        if j.get("report_html"):
            line += f"\n  report: {j['report_html']}"
        out.append(line)
    return "\n".join(out)


def _flag(args: dict, **changes) -> str:
    job = rc.find_job(args.get("job"))
    if not job:
        return "No matching research job."
    if job.get("state") in rc.FINAL:
        return f"Job {job['id']} is already {job['state']}."
    with rc.jobs_lock():
        j = rc.load_job(job["id"])
        j.update(changes)
        rc.save_job(j)
    return None, j


def t_pause(args: dict) -> str:
    r = _flag(args, user_paused=True)
    if isinstance(r, str):
        return r
    j = r[1]
    return (f"Job {j['id']} will pause at its next step (a model call already running finishes first); its research "
            f"clock stops. research_resume continues it.")


def t_resume(args: dict) -> str:
    r = _flag(args, user_paused=False)
    if isinstance(r, str):
        return r
    j = r[1]
    extra = ""
    if rc.is_night():
        extra = f" It is inside the night pause, so it continues at {rc.night_end_text()}."
    return f"Job {j['id']} resumes.{extra}"


def t_cancel(args: dict) -> str:
    r = _flag(args, cancel_requested=True)
    if isinstance(r, str):
        return r
    j = r[1]
    return f"Job {j['id']} is being cancelled (a running research stops at its next step; no report)."


SERVER_START = time.time()   # jobs created since are this Jan session's; a report of an older job is an earlier report


def _when(t) -> str:
    return datetime.fromtimestamp(float(t)).strftime("%Y-%m-%d %H:%M") if t else "an unknown date"


def t_report(args: dict) -> str:
    ref = args.get("job")
    if not ref:   # 2026-10-19: no more "the newest finished one" - a new chat must not pick up an unrelated old report
        done = [j for j in reversed(rc.all_jobs()) if j.get("report_md")][:15]
        if not done:
            return "No finished report yet."
        return ("Finished reports (newest first) - call research_report with the job id of the one the user means:\n" +
                "\n".join(f"- {j['id']}: finished {_when(j.get('finished'))} - {j['question'][:150]}" for j in done) +
                "\n" + PAST_REPORTS)
    job = rc.find_job(ref)
    if not job:
        return "No such job. research_list shows the jobs."
    if not job.get("report_md"):
        oc = outcome_line(job)
        if oc:                       # failed / cancelled / a quick answer not started: plainly, so polling stops
            return f"{oc}\nJob {job['id']} - question: {job['question'][:200]}\n{RESEARCH_FAILED}"
        return describe(job) + "\nThe report is not ready yet."
    try:
        text = Path(job["report_md"]).read_text(encoding="utf-8")
    except OSError as e:
        return f"Cannot read {job['report_md']}: {e}"
    parts = split_parts(text)
    try:
        n = int(args.get("part") or 1)
    except (TypeError, ValueError):
        n = 1
    n = max(1, min(n, len(parts)))
    html = job.get("report_html")
    head = (f"Report of job {job['id']}, finished {_when(job.get('finished'))}, part {n} of {len(parts)}. Whole report: "
            f"{html} (open in a browser: file://{html}); Markdown: {job['report_md']}\n")
    if float(job.get("created") or 0) < SERVER_START:   # not started in this Jan session: an earlier report
        head = (f"EARLIER REPORT - finished {_when(job.get('finished'))}, question: \"{job['question'][:200]}\". "
                f"{PAST_REPORTS}\n" + head)
    head += "\n"
    tail = f"\n\n[Part {n} of {len(parts)}{'; ask for part ' + str(n + 1) + ' to continue' if n < len(parts) else ''}]"
    return head + parts[n - 1] + tail


HANDLERS = {"research_start": t_start, "research_quick": t_quick, "research_inbox": t_inbox, "research_status": t_status, "research_list": t_list,
            "research_pause": t_pause, "research_resume": t_resume, "research_cancel": t_cancel,
            "research_report": t_report}


# -- JSON-RPC over stdio (MCP) ---------------------------------------------------------------------------------------------
def reply(msg_id, result=None, error=None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(msg: dict) -> None:
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        pv = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return reply(mid, {"protocolVersion": pv, "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "deep-research", "version": "1.0"}, "instructions": INSTRUCTIONS})
    if method in ("notifications/initialized", "notifications/cancelled") or (mid is None and method):
        return None
    if method == "ping":
        return reply(mid, {})
    if method == "tools/list":
        return reply(mid, {"tools": TOOLS})
    if method == "tools/call":
        p = msg.get("params") or {}
        name, args = p.get("name"), p.get("arguments") or {}
        log(f"call {name} {json.dumps(args, ensure_ascii=False)[:2000]}")
        fn = HANDLERS.get(name)
        if not fn:
            return reply(mid, {"content": [{"type": "text", "text": f"Unknown tool {name}"}], "isError": True})
        try:
            text = fn(args)
            return reply(mid, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:  # noqa: BLE001
            log("error:\n" + traceback.format_exc())
            return reply(mid, {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True})
    if mid is not None:
        return reply(mid, error={"code": -32601, "message": f"Method not found: {method}"})
    return None


def main() -> None:
    log(f"started (pid {os.getpid()})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            log(f"bad input: {line[:200]}")
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            handle(m)


if __name__ == "__main__":
    main()
