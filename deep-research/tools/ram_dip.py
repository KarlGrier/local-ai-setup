#!/usr/bin/env python3
"""ram_dip.py - what uses RAM when MemAvailable dips below the relief trigger (2026-10-19 evening, the user's request:
"at the next dip below 20 GB, capture the same breakdown as at o03 ... and tell me what's bigger than at o03's 20.7 GB
low").

Samples MemAvailable every second. Below DIP_GIB (20) a dip starts; every new low in it (50 MiB lower than the last
snapshot) writes a full snapshot - the tools/ram_lowpoint.py breakdown (meminfo, Strata's engine with its expert arena,
parked chat-cache conversations and the rest of its RSS by mapping kind, Strata's server, LDR, both SearXNGs, Jan with
its MCP servers, proxy / runner / bench client) plus the browser, the other desktop apps, and this Claude Code session
with its shells - so the dip's lowest point is the one left in results/ram-dip-<start>.json. The dip ends when
MemAvailable stays above END_GIB (24) for 30 s (a relief restart) or after 20 minutes. Context per dip: the bench run in
progress and the class of the proxy's latest call (agent / extract / report / verify), or a port-gap test.

  ram_dip.py [MAX_DIPS]     (default 10; stops early on tmp/ram-dip.stop)   log: logs/ram-dip.log
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
SC = Path("/home/USER/ai-speed-testing/strata-compare")
DIP_GIB, END_GIB = 20.0, 24.0
LOG = WS / "logs" / "ram-dip.log"
STOP = WS / "tmp" / "ram-dip.stop"
GIB = 2**30

DESKTOP = ("gnome-", "gsd-", "Xorg", "Xwayland", "xdg-", "pipewire", "wireplumber", "ibus", "tracker", "evolution",
           "nautilus", "at-spi", "dbus", "goa-", "mutter", "nm-applet", "pulseaudio", "systemd", "gvfs", "dconf",
           "snapd", "update-notifier", "seahorse", "nautilus", "ptyxis", "gnome-terminal")


def meminfo() -> dict:
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        m[k] = int(v.split()[0]) * 1024
    return m


def procs() -> list[dict]:   # as tools/ram_lowpoint.py, + the parent PID
    out = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            st = Path(f"/proc/{p}/status").read_text()
            cmd = Path(f"/proc/{p}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            comm = Path(f"/proc/{p}/comm").read_text().strip()
        except OSError:
            continue
        f = dict(re.findall(r"^(\w+):\s+(\d+) kB", st, re.M))
        ppid = re.search(r"^PPid:\s+(\d+)", st, re.M)
        rss = int(f.get("VmRSS", 0)) * 1024
        if rss:
            out.append({"pid": int(p), "ppid": int(ppid.group(1)) if ppid else 0, "cmd": cmd, "comm": comm, "rss": rss,
                        "anon": int(f.get("RssAnon", 0)) * 1024, "shmem": int(f.get("RssShmem", 0)) * 1024})
    return out


def engine_log(ps: list[dict]) -> Path | None:
    """The running engine's log: its server's --config, that config's "log" (8080's C*18t, or a port-gap test server)."""
    for p in ps:
        if "serve/server.py" in p["cmd"] and "--config" in p["cmd"]:
            cfg = p["cmd"].split("--config", 1)[1].split()[0]
            try:
                return Path(json.loads(Path(cfg).read_text())["log"])
            except (OSError, ValueError, KeyError):
                continue
    return None


def chat_cache_parked(log_path: Path | None) -> dict | None:   # as tools/ram_lowpoint.py, for the running engine's log
    try:
        lines = log_path.read_text(errors="replace").splitlines() if log_path else None
    except OSError:
        lines = None
    if lines is None:
        return None
    start = max((i for i, l in enumerate(lines) if "participating threads" in l), default=0)
    parked: list[tuple[int, int]] = []   # (tokens, MiB)
    for l in lines[start:]:
        m = re.search(r"chat cache: parked a conversation of (\d+) tokens \(\d+ checkpoints?, (\d+) MiB\)", l)
        if m:
            parked.append((int(m.group(1)), int(m.group(2))))
            continue
        m = re.search(r"chat cache: (?:dropped a conversation|dropped an older copy|restored a conversation) of (\d+) tokens", l)
        if m:
            t = int(m.group(1))
            for i, (tt, _) in enumerate(parked):
                if tt == t:
                    parked.pop(i)
                    break
    return {"log": log_path.name, "conversations": len(parked), "mib": sum(m for _, m in parked),
            "largest_mib": max((m for _, m in parked), default=0)}


def strata_metrics() -> dict | None:
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for port in (8080, 8081):
        try:
            e = json.load(op.open(f"http://127.0.0.1:{port}/metrics", timeout=3))["engine"]
            return {"port": port, **{k: e.get(k) for k in ("arena_mib", "expert_cache_mib", "expert_slots", "kv_resident",
                                                          "vram_free_mib")}}
        except Exception:  # noqa: BLE001 - not on this port
            continue
    return None


def claude_tree(ps: list[dict]) -> set[int]:
    """This Claude Code session and everything it started (its shells, watchers): the claude process and descendants."""
    kids: dict[int, list[int]] = {}
    for p in ps:
        kids.setdefault(p["ppid"], []).append(p["pid"])
    roots = [p["pid"] for p in ps if p["comm"] == "claude"]
    seen, todo = set(), list(roots)
    while todo:
        q = todo.pop()
        if q not in seen:
            seen.add(q)
            todo += kids.get(q, [])
    return seen


def groups(ps: list[dict]) -> dict:
    mine = claude_tree(ps)
    rules = [
        ("Strata engine", lambda p: p["comm"] in ("strata", "strata-host")),
        ("Strata server", lambda p: "serve/server.py" in p["cmd"]),
        ("LDR (ldr-web)", lambda p: "ldr-web" in p["cmd"] or p["comm"] == "ldr-web"),
        ("SearXNG 8889 (LDR)", lambda p: "granian" in p["cmd"] and (":8889" in p["cmd"] or "deep-research/searxng" in p["cmd"])),
        ("SearXNG 8888 (chat page)", lambda p: "granian" in p["cmd"] and (":8888" in p["cmd"] or "websearch" in p["cmd"])),
        ("SearXNG (other granian)", lambda p: "granian" in p["cmd"]),
        ("Jan (app + its MCP servers)", lambda p: "Jan_0.8.6" in p["cmd"] or "/tmp/.mount_Jan" in p["cmd"]
         or p["comm"].lower().startswith("jan") or "research-mcp.py" in p["cmd"] or "web-mcp.py" in p["cmd"]),
        ("strata-proxy", lambda p: "strata-proxy.py" in p["cmd"]),
        ("research runner", lambda p: "research-runner.py" in p["cmd"]),
        ("bench client", lambda p: "ldr-client.py" in p["cmd"] or "bench2.py" in p["cmd"]),
        ("port-gap tests / builds", lambda p: p["comm"] in ("cc1plus", "cicc", "ptxas", "nvcc", "ninja", "cmake", "ctest")
         or "work/r22/" in p["cmd"] or "bringup/lib/" in p["cmd"]),
        ("this Claude Code session + its shells", lambda p: p["pid"] in mine),
        ("browser", lambda p: any(b in p["cmd"].lower() for b in ("brave", "chrome", "chromium", "firefox"))),
        ("other desktop apps", lambda p: p["comm"].startswith(DESKTOP) or "open_webui" in p["cmd"]),
    ]
    out, used = {}, set()
    for name, test in rules:
        sel = [p for p in ps if p["pid"] not in used and test(p)]
        used |= {p["pid"] for p in sel}
        if sel:
            out[name] = {"rss_gib": round(sum(p["rss"] for p in sel) / GIB, 2), "procs": len(sel),
                         "anon_gib": round(sum(p["anon"] for p in sel) / GIB, 2),
                         "shmem_gib": round(sum(p["shmem"] for p in sel) / GIB, 2),
                         "top": [(p["comm"], round(p["rss"] / GIB, 2)) for p in sorted(sel, key=lambda p: -p["rss"])[:4]]}
    rest = sorted((p for p in ps if p["pid"] not in used), key=lambda p: -p["rss"])
    out["everything else"] = {"rss_gib": round(sum(p["rss"] for p in rest) / GIB, 2), "procs": len(rest),
                              "top": [(p["comm"], round(p["rss"] / GIB, 2)) for p in rest[:8]]}
    return out


def engine_maps(ps: list[dict]) -> dict | None:
    """The Strata engine's resident memory by mapping kind (smaps): anonymous (arena, chat cache, heap), the NVIDIA
    device mappings (pinned host buffers the driver maps), files (the binary, libraries, mapped model files)."""
    eng = [p for p in ps if p["comm"] in ("strata", "strata-host")]
    if not eng:
        return None
    kinds: dict[str, int] = {}
    try:
        cur = "anon"
        for line in open(f"/proc/{eng[0]['pid']}/smaps", errors="replace"):
            if re.match(r"^[0-9a-f]+-[0-9a-f]+ ", line):
                parts = line.split(None, 5)
                path = parts[5].strip() if len(parts) > 5 else ""
                cur = ("nvidia device mappings" if path.startswith("/dev/nvidia") else
                       "anon" if not path or path.startswith("[") else
                       "model files" if path.endswith((".gguf", ".bin")) or "/pack/" in path else "other files")
            elif line.startswith("Rss:"):
                kinds[cur] = kinds.get(cur, 0) + int(line.split()[1]) * 1024
    except OSError:
        return None
    return {k: round(v / GIB, 2) for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])}


def context() -> dict:
    c: dict = {"port_gap_open": (SC / "tmp" / "port-gap.lockpid").exists()}
    try:
        runs = [l for l in (WS / "logs" / "bench2-queue.log").read_text(errors="replace").splitlines() if ": running" in l]
        c["last_bench_run_started"] = runs[-1] if runs else None
    except OSError:
        pass
    try:
        with open(WS / "logs" / "llm-calls.jsonl", "rb") as f:
            f.seek(max(0, f.seek(0, 2) - 20000))
            last = [json.loads(l) for l in f.read().decode("utf-8", "replace").splitlines()[1:] if l.strip().startswith("{")]
        if last:
            c["proxy_last_call"] = {"cls": last[-1].get("cls"), "t0": time.strftime("%H:%M:%S", time.localtime(last[-1]["t0"]))}
    except (OSError, ValueError, KeyError):
        pass
    return c


def log(msg: str) -> None:
    with open(LOG, "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def main() -> None:
    max_dips = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    log(f"start (dip < {DIP_GIB} GiB, ends above {END_GIB} GiB for 30 s; up to {max_dips} dips)")
    dips = 0
    while dips < max_dips and not STOP.exists():
        av = meminfo()["MemAvailable"] / GIB
        if av >= DIP_GIB:
            time.sleep(1)
            continue
        dips += 1
        t_start = time.time()
        out = WS / "results" / f"ram-dip-{time.strftime('%Y%m%dT%H%M%S')}.json"
        low, above_since = None, None
        log(f"dip {dips} started: MemAvailable {av:.2f} GiB -> {out.name}")
        while time.time() - t_start < 1200:
            m = meminfo()
            av = m["MemAvailable"]
            if low is None or av < low - 50 * 2**20:
                low = av
                ps = procs()
                snap = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "context": context(),
                        "meminfo_gib": {k: round(m[k] / GIB, 2) for k in ("MemTotal", "MemAvailable", "MemFree", "Cached",
                                        "Buffers", "Shmem", "AnonPages", "Mlocked", "Unevictable", "Slab", "PageTables")},
                        "swap_used_gib": round((m["SwapTotal"] - m["SwapFree"]) / GIB, 2),
                        "groups": groups(ps), "strata_engine_by_mapping": engine_maps(ps),
                        "strata_metrics": strata_metrics(), "chat_cache_parked": chat_cache_parked(engine_log(ps))}
                out.write_text(json.dumps(snap, indent=1))
            if av / GIB > END_GIB:
                above_since = above_since or time.time()
                if time.time() - above_since >= 30:
                    break
            else:
                above_since = None
            time.sleep(1)
        log(f"dip {dips} ended: lowest MemAvailable {low / GIB:.2f} GiB ({out.name})")
    log("stop")


if __name__ == "__main__":
    main()
