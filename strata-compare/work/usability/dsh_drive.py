#!/usr/bin/env python3
"""dsh_drive.py - run one task through DeepSeek Harness's Web UI (headless Chrome), as a user would.

    dsh_drive.py --repo DIR --mode Minimal|Standard|PTC --prompt-file F --home DSH_HOME --out DIR [--timeout 2700]

Starts `dsh-strata --no-open` (the usability launcher) with its working directory at the repo and the repo as the only
workspace, opens the UI, dismisses the preview notice, picks the mode, types the task and sends it, then watches the UI
until the turn is over (the composer's Stop control gone and no request to Strata for a while). Screenshots and a DOM
trace go to --out. The DSH_HOME given must already hold profiles/web/cordis.patch.yml.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cdp import Browser  # noqa: E402

LAUNCHER = "/home/USER/ai-speed-testing/strata-compare/configs/usability/bin/dsh-strata"

CLICK = """(t => { const el = [...document.querySelectorAll('button,[role=button],[role=option],[role=menuitem],[role=menuitemradio]')]
  .find(e => e.innerText && e.innerText.trim().split('\\n')[0].trim() === t); if (!el) return 'not found: ' + t; el.click(); return 'ok'; })"""
BUTTONS = """[...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)
  .map(b => (b.getAttribute('aria-label') || b.title || b.innerText || '').trim().slice(0, 40)).filter(Boolean)"""


def write_workspace(home: Path, repo: Path):
    wid = str(uuid.uuid4())
    st = {"unit": {"name": "workspace", "version": 2},
          "global": {"initialized": True, "workspaceIds": [wid], "archivedSessionIds": [], "pinnedSessionIds": [],
                     "defaultWorkspaceId": wid},
          "tables": {"workspaces": {wid: {"path": str(repo), "title": repo.name, "sessionIds": [],
                                          "createdAt": "2026-10-16T00:00:00.000Z",
                                          "updatedAt": "2026-10-16T00:00:00.000Z"}}}}
    (home / "storages").mkdir(parents=True, exist_ok=True)
    (home / "storages/workspace.json").write_text(json.dumps(st, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--mode", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--home", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=3080)
    ap.add_argument("--timeout", type=int, default=2700)
    ap.add_argument("--turnlog", default="")
    a = ap.parse_args()
    repo, home, out = Path(a.repo).resolve(), Path(a.home).resolve(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    write_workspace(home, repo)
    env = dict(os.environ, DSH_HOME=str(home), STRATA_NO_AUTOSTART="1")   # never starts Strata (2026-10-17)
    log = open(out / "dsh-web.log", "w")
    srv = subprocess.Popen([LAUNCHER, "--no-open", "--port", str(a.port)], cwd=repo, env=env, stdout=log,
                           stderr=subprocess.STDOUT, start_new_session=True)
    trace = open(out / "ui-trace.jsonl", "w")
    url, t0 = None, time.time()
    try:
        while time.time() - t0 < 90 and not url:
            time.sleep(1)
            m = re.search(r"http://127\.0\.0\.1:\d+/\?token=[A-Za-z0-9_-]+", (out / "dsh-web.log").read_text())
            url = m.group(0) if m else None
        if not url:
            raise SystemExit("dsh web did not start")
        b = Browser()
        try:
            b.goto(url, wait=6)
            print("continue:", b.js(CLICK + "('Continue')"))
            time.sleep(1)
            print("mode menu:", b.js(CLICK + "('Standard mode')"))
            time.sleep(1)
            print("mode:", b.js(CLICK + f"('{a.mode} mode')"))
            time.sleep(1)
            b.shot(str(out / "0-ready.png"))
            prompt = Path(a.prompt_file).read_text()
            focus = b.js("""(() => { const e = document.querySelector('textarea, [contenteditable=true]'); if (!e) return 'no input';
                              e.focus(); return e.tagName; })()""")
            print("input:", focus)
            b.insert_text(prompt)
            time.sleep(1)
            b.shot(str(out / "1-typed.png"))
            b.key("Enter", vk=13)
            sent_at = time.time()
            print("sent at", time.strftime("%H:%M:%S"))
            quiet_since, last_req, n = None, 0, 0
            while time.time() - sent_at < a.timeout:
                time.sleep(5)
                n += 1
                btns = b.js(BUTTONS) or []
                running = any(re.search(r"\b(stop|interrupt|cancel)\b", x, re.I) for x in btns)
                reqs = 0
                if a.turnlog:
                    idx = Path(a.turnlog) / "index.jsonl"
                    started = len(list(Path(a.turnlog).glob("*.req.json.gz")))
                    done = len(idx.read_text().splitlines()) if idx.exists() else 0
                    reqs = started - done
                    if started != last_req:
                        last_req, quiet_since = started, None
                trace.write(json.dumps({"t": round(time.time() - sent_at, 1), "running": running, "in_flight": reqs,
                                        "buttons": btns[:30]}) + "\n")
                trace.flush()
                if n % 24 == 0:
                    b.shot(str(out / f"2-at-{int(time.time() - sent_at)}s.png"))
                if not running and reqs == 0:
                    quiet_since = quiet_since or time.time()
                    if time.time() - quiet_since >= 20:
                        break
                else:
                    quiet_since = None
            else:
                print("TIMEOUT")
            b.shot(str(out / "3-end.png"))
            (out / "page-text.txt").write_text(b.js("document.body.innerText") or "")
            print("ended after", round(time.time() - sent_at, 1), "s")
        finally:
            b.close()
    finally:
        try:
            os.killpg(srv.pid, signal.SIGTERM)
            srv.wait(timeout=20)
        except Exception:
            os.killpg(srv.pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
