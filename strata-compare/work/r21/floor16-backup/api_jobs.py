#!/usr/bin/env python3
"""api_jobs.py — start each API provider's runs as soon as its key file exists, beside the local runs.

  Anthropic  (~/.config/model-suite/anthropic.key):  opus-4-5-quick -> sonnet-4-6-quick -> opus-4-6-quick
  OpenRouter (~/.config/model-suite/openrouter.key): or-qwen3.8-flash-full -> or-qwen3.8-27b-full
                                                      -> or-qwen3.8-max-0902-quick
The two providers' chains run at the same time.  Each run first collects with --collect-only (requests + saved
answers only; no agentic items, no grading), then, once no local run is going (it takes tmp/suite/heavy.lock, which
the local chain holds), the same command again without it adds the agentic items and grades.  Estimates come from
c171-iq3s-quick's token counts; the suite's own gates apply (Claude: estimate $25, stop $40; OpenRouter: stop $15).
Rate limits (429/529) are retried with back-off inside the clients.  Memory: no run starts while MemAvailable is
under 20 GiB, except during the Q4 run (its own 6 GiB floor, your choice) where the API jobs only keep sending.
The key files are only checked for existence here; they are read by the API clients alone.
Log: logs/suite/api_jobs.log; state: tmp/suite/api_jobs/state.json.  Stops by itself 72 h after its start, or when
every run is finished, or when tmp/suite/api_jobs/STOP exists.
"""
import fcntl
import json
import subprocess
import threading
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
KEYS = {"anthropic": Path.home() / ".config/model-suite/anthropic.key",
        "openrouter": Path.home() / ".config/model-suite/openrouter.key"}
CHAINS = {
    "anthropic": [("opus-4-5-quick", "claude:claude-opus-4-5-20251101", "quick"),
                  ("sonnet-4-6-quick", "claude:claude-sonnet-4-6", "quick"),
                  ("opus-4-6-quick", "claude:claude-opus-4-6", "quick")],
    "openrouter": [("or-qwen3.8-flash-full", "openrouter:qwen/qwen3.8-flash", "full"),
                   ("or-qwen3.8-27b-full", "openrouter:qwen/qwen3.8-27b", "full"),
                   ("or-qwen3.8-max-0902-quick", "openrouter:qwen/qwen3.8-max-0902", "quick")],
}
D = WS / "tmp/suite/api_jobs"
STATE = D / "state.json"
LOG = WS / "logs/suite/api_jobs.log"
LOCK = WS / "tmp/suite/heavy.lock"
DEADLINE = time.time() + 72 * 3600
lock = threading.Lock()
FINAL = ("done", "over estimate", "no key", "stopped", "gave up after 3 failures")


def log(msg):
    with lock:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(st):
    with lock:
        D.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1))
        tmp.replace(STATE)


def mem_available_gib():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 ** 2
    return 0.0


def running(pattern):
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def q4_active():
    return running("work/suite/q4_quick.sh")


def local_busy():
    return (running(r"msuite .*--endpoint http://127\.0\.0\.1") or running("work/suite/local_chain.sh")
            or q4_active())


def wait_memory(label):
    while time.time() < DEADLINE and not (D / "STOP").exists():
        if q4_active() or mem_available_gib() >= 21.0:     # 20 GiB floor + ~1 GiB for the job itself
            return True
        log(f"{label}: MemAvailable {mem_available_gib():.1f} GiB < 21 GiB - waiting")
        time.sleep(120)
    return False


def suite(label, endpoint, mode, collect):
    cmd = [str(WS / "suite/run.sh"), "--label", label, "--endpoint", endpoint, "--mode", mode,
           "--estimate-from", "c171-iq3s-quick"]
    if collect:
        cmd.append("--collect-only")
    out = WS / f"tmp/suite/api_jobs/{label}.{'collect' if collect else 'finish'}.console"
    with open(out, "a") as f:
        f.write(f"\n### {time.strftime('%Y-%m-%dT%H:%M:%S')} {' '.join(cmd[1:])}\n")
        f.flush()
        rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=WS).returncode
    return rc


def collect_chain(provider):
    st = load_state()
    for label, endpoint, mode in CHAINS[provider]:
        if st.get(label, {}).get("collect") in FINAL:
            continue
        if not wait_memory(label):
            return
        log(f"{label}: collecting ({endpoint}, {mode})")
        rc = suite(label, endpoint, mode, collect=True)
        meta = {}
        try:
            meta = json.loads((WS / f"suite/results/{label}/meta.json").read_text())
        except (OSError, ValueError):
            pass
        status = {0: "done", 3: "no key", 4: "over estimate"}.get(rc, f"failed rc {rc}")
        if meta.get("stopped"):
            status = "stopped"
        st = load_state()
        fails = st.get(label, {}).get("failures", 0) + (1 if status.startswith("failed") else 0)
        if fails >= 3:
            status = "gave up after 3 failures"
        st.setdefault(label, {}).update({"collect": status, "failures": fails, "endpoint": endpoint, "mode": mode,
                                         "estimate": meta.get("estimate_usd"), "cost_usd": meta.get("cost_usd")})
        save_state(st)
        log(f"{label}: collect {status}; estimate {(meta.get('estimate_usd') or {}).get('point')}, "
            f"cost so far {meta.get('cost_usd')}")
        if rc not in (0, 4):
            return                      # resume on the next pass (failed) / nothing more possible (no key)


def finish_pending():
    """Agentic items + grading for collected runs, only while no local run is going (holds the heavy lock)."""
    st = load_state()
    todo = [l for l, s in st.items() if s.get("collect") in ("done", "stopped") and s.get("finish") != "done"]
    if not todo or local_busy():
        return
    fd = open(LOCK, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        return
    try:
        for label in todo:
            s = load_state()[label]
            if not wait_memory(label):
                return
            log(f"{label}: finishing (agentic items + grading)")
            rc = suite(label, s["endpoint"], s["mode"], collect=False)
            st = load_state()
            st[label]["finish"] = "done" if rc == 0 else f"rc {rc}"
            save_state(st)
            log(f"{label}: finish rc {rc}")
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def all_done():
    st = load_state()
    labels = [l for chain in CHAINS.values() for l, _, _ in chain]
    return all(st.get(l, {}).get("finish") == "done"
               or st.get(l, {}).get("collect") in ("over estimate", "gave up after 3 failures") for l in labels)


def main():
    D.mkdir(parents=True, exist_ok=True)
    log(f"start (pid {__import__('os').getpid()}); keys present: "
        f"{ {p: k.exists() for p, k in KEYS.items()} }")
    workers = {}
    reported = set()
    while time.time() < DEADLINE and not (D / "STOP").exists():
        if not (WS / "suite/results/c171-iq3s-quick/meta.json").exists():
            time.sleep(60)
            continue
        for provider, key in KEYS.items():
            if key.exists():
                if provider not in reported:
                    log(f"{provider}: key file present - starting its chain")
                    reported.add(provider)
                w = workers.get(provider)
                if w is None or not w.is_alive():
                    st = load_state()
                    pending = [l for l, _, _ in CHAINS[provider]
                               if st.get(l, {}).get("collect") not in FINAL]
                    if pending:
                        workers[provider] = threading.Thread(target=collect_chain, args=(provider,), daemon=True)
                        workers[provider].start()
        finish_pending()
        if all_done():
            log("every API run finished")
            break
        time.sleep(60)
    log("exit")


if __name__ == "__main__":
    main()
