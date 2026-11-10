#!/usr/bin/env python3
"""client_check.py - one short request from each coding client through the recorder, and the sampling Strata applies
to it (2026-10-17, after the sampling changes).

    client_check.py [ARM ...]      ARM: opencode | opencode-xhigh | codex | dsh-minimal | server
                                   (default: opencode codex dsh-minimal)

Needs turnlog.py on 127.0.0.1:8090 -> 8080 (logs/usability/turns). Each client runs through its usability launcher
with harness_run.py's measurement config (endpoint 8090, nothing else changed) on a one-file repo, asked for one word.
Prints, per client, what its first request sent and the values the server uses: the run config's "sampling" block,
then <config>.shared-settings.json (the Chat settings), then the request's own non-null fields (serve/server.py _run).
Jan is not driven here (it would take over the desktop's mouse and keyboard).
2026-10-17 (default effort): the effort each request gets (its own reasoning_effort / reasoning.effort, else the Chat
settings' level, else the config's; Strata reads "high" as xhigh); "opencode-xhigh" = OpenCode with its xhigh variant
(-m strata/qwen3.8-flash#xhigh); "server" = three plain requests through the recorder (no effort / medium / xhigh,
max_tokens 1): the same prompt-token count for "no effort" and the default level shows what the server filled in.
"""
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
CFG = WS / "configs/usability"
RUNS = WS / "tmp/usability/client-check"
TURNS = WS / "logs/usability/turns"
MEASURE = "http://127.0.0.1:8090/v1"
SERVED = WS / "configs/Cstar18t.json"
PROMPT = "Reply with the single word OK. Do not run any tools or commands."
KEYS = ("temperature", "top_p", "top_k", "min_p", "reasoning_effort")


def launch(arm, d, label):
    repo = d / "repo"
    repo.mkdir(parents=True)
    (repo / "README.md").write_text("A test folder.\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    (d / "prompt.txt").write_text(PROMPT)
    env = dict(os.environ, STRATA_NO_AUTOSTART="1")   # measured runs never start Strata (launchers, 2026-10-17)
    if arm in ("opencode", "opencode-xhigh"):
        conf = d / "opencode-measure.jsonc"
        conf.write_text((CFG / "opencode/opencode.jsonc").read_text().replace("http://127.0.0.1:8080/v1", MEASURE))
        env.update(OPENCODE_CONFIG=str(conf))
        cmd = [str(CFG / "bin/opencode-strata"), "run", "--auto", PROMPT]
        if arm == "opencode-xhigh":
            cmd[2:2] = ["-m", "strata/qwen3.8-flash#xhigh"]
    elif arm == "codex":
        home = d / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text((CFG / "codex/config.toml").read_text().replace("http://127.0.0.1:8080/v1",
                                                                                          MEASURE))
        env["CODEX_HOME_STRATA"] = str(home)
        cmd = [str(CFG / "bin/codex-strata"), "exec", "--skip-git-repo-check", "-c", 'approval_policy="never"',
               "-c", 'sandbox_mode="workspace-write"', PROMPT]
    elif arm == "dsh-minimal":
        home = d / "dsh-home"
        (home / "profiles/web").mkdir(parents=True)
        (home / "profiles/web/cordis.patch.yml").write_text(
            (CFG / "dsh/web.cordis.patch.yml").read_text().replace("http://127.0.0.1:8080/v1", MEASURE))
        cmd = [sys.executable, str(WS / "work/usability/dsh_drive.py"), "--repo", str(repo), "--mode", "Minimal",
               "--prompt-file", str(d / "prompt.txt"), "--home", str(home), "--out", str(d / "ui"),
               "--turnlog", str(TURNS / label), "--timeout", "420"]
    else:
        raise SystemExit(f"unknown arm {arm}")
    (TURNS / "LABEL").write_text(label)
    t0 = time.time()
    with open(d / "stdout.txt", "w") as so, open(d / "stderr.txt", "w") as se:
        try:
            rc = subprocess.run(cmd, cwd=repo, env=env, stdout=so, stderr=se, timeout=600).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    (TURNS / "LABEL").write_text("idle")
    return rc, round(time.time() - t0, 1)


EFFORT = {"low": "low", "medium": "medium", "high": "xhigh", "xhigh": "xhigh", "max": "xhigh"}   # serve/frontend.py


def effort_used(sent, shared, cfg):
    """The level Strata applies: the request's own, else the Chat settings', else the config's (server.py)."""
    own = sent.get("reasoning_effort") or (sent.get("reasoning") or {}).get("effort")
    lv = own or shared.get("reasoning_effort") or cfg.get("reasoning_effort")
    return EFFORT.get(str(lv).lower(), lv) if lv else "the template's default (xhigh)"


def server_check(stamp):
    """Three requests through the recorder: no effort, medium, xhigh; prompt tokens of each."""
    import urllib.request
    label = f"client-check-server-{stamp}"
    shutil.rmtree(TURNS / label, ignore_errors=True)
    (TURNS / "LABEL").write_text(label)
    out = {}
    try:
        for name, extra in (("no effort", {}), ("medium", {"reasoning_effort": "medium"}),
                            ("low", {"reasoning_effort": "low"}), ("xhigh", {"reasoning_effort": "xhigh"})):
            body = {"model": "strata-qwen3.8-flash-next-iq3s", "max_tokens": 1, "stream": False,
                    "messages": [{"role": "user", "content": PROMPT}], **extra}
            req = urllib.request.Request(MEASURE + "/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                out[name] = json.load(r)["usage"]["prompt_tokens"]
    finally:
        (TURNS / "LABEL").write_text("idle")
    print(f"server: prompt tokens by effort {out}")
    same = [k for k in ("low", "medium", "xhigh") if out.get(k) == out.get("no effort")]
    print(f"server: a request with no effort is rendered as {same or 'none of them'}; "
          f"xhigh {'differs' if out.get('xhigh') != out.get('no effort') else 'is the same'}")
    return out


def main():
    arms = sys.argv[1:] or ["opencode", "codex", "dsh-minimal"]
    cfg = json.loads(SERVED.read_text())
    base = dict(cfg.get("sampling") or {})
    shared_p = SERVED.with_name(SERVED.stem + ".shared-settings.json")
    shared = json.loads(shared_p.read_text()) if shared_p.exists() else {}
    defaults = {**base, **shared}
    print(f"server defaults: config sampling {base} + Chat settings {shared}")
    stamp = time.strftime("%m%d%H%M")
    rows = []
    for arm in arms:
        if arm == "server":
            rows.append((arm, None, server_check(stamp), 4))
            continue
        label = f"client-check-{arm}-{stamp}"
        d = RUNS / label
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(TURNS / label, ignore_errors=True)
        rc, wall = launch(arm, d, label)
        reqs = sorted((TURNS / label).glob("*.req.json.gz"))
        if not reqs:
            print(f"{arm}: rc {rc}, {wall} s, NO request recorded")
            rows.append((arm, None, None, len(reqs)))
            continue
        body = json.loads(gzip.decompress(reqs[0].read_bytes()))
        sent = {k: body.get(k) for k in KEYS}
        if "reasoning" in body:
            sent["reasoning"] = body["reasoning"]
        eff = {**defaults, **{k: v for k, v in sent.items() if v is not None and k in KEYS}}
        eff = {k: eff.get(k) for k in KEYS}
        eff["reasoning_effort"] = effort_used(sent, shared, cfg)
        print(f"{arm}: rc {rc}, {wall} s, {len(reqs)} request(s); first request sent {sent}")
        print(f"{arm}: the server uses {eff}")
        rows.append((arm, sent, eff, len(reqs)))
    (RUNS / f"summary-{stamp}.json").write_text(json.dumps(
        [{"arm": a, "sent": s, "effective": e, "requests": n} for a, s, e, n in rows], indent=1))


if __name__ == "__main__":
    main()
