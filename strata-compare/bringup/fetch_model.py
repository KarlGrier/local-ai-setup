#!/usr/bin/env python3
"""fetch_model.py - 10-27 (day-one refresh): a model's files from Hugging Face, PINNED (a commit, exact file names, each
file's size and sha256), as work/ds41/download.py did for DeepSeek-V4.1 (10-23), for any repository:

  1. pins      fetch_model.py pins --repo OWNER/NAME --revision COMMIT --out PINS.json [--match GLOB ...]
               the repository's LFS files at that commit with size + sha256 (the API listing tools/hf_pin_fetch.py reads;
               nothing downloaded). Edit PINS.json down to the files you want: it is the download's whole list.
  2. heads     fetch_model.py heads --pins PINS.json --dest DIR
               only each .gguf's HEADER (range requests, grown until gguf_head.py parses it; a 206 with the asked
               Content-Range is required, #327) -> DIR/NAME + DIR/NAME.size (the real size): inspect_model.py,
               fitplan.py and placements.py read these like the real files. Minutes, a few MB per shard.
  3. plan      fetch_model.py plan --pins PINS.json --dest DIR     the download against the free space (exit 3 if short)
  4. get       fetch_model.py get --pins PINS.json --dest DIR [--rate 35]   the download itself - run it as a user unit:
               fetch_model.py unit --pins PINS.json --dest DIR [--rate 35] [--name qwen4-download] prints the line
               (systemd-run --user --unit NAME --collect -p MemoryHigh=2G ...); `get` outside a unit refuses
               unless --no-unit-ok.
Rules kept (the user's): >= 100 GB free on the drive before every file and after the whole download (else it stops and
says so: deleting anything is the user's decision, never this script's); never into ~/.cache (DEST must be under the
workspace's models/ unless --dest-anywhere); a file lands as NAME.part and is renamed only when its size and sha256 match
the pin (a mismatch -> NAME.bad); the page cache is dropped every 256 MiB written (posix_fadvise) and the unit runs with
MemoryHigh as a backstop; a speed cap (--rate MB/s, default 35: the research runs' web searches keep the rest of the line).
Log: DEST/fetch.log; status DEST/fetch-status.json; DEST/fetch-done when every file is verified; a desktop alert at the
end (critical on a failure). --base-url DIR reads ranges from local files of that name instead (offline tests only)."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gguf_head  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
KEEP_FREE = 100e9
CHUNK = 4 << 20
DROP_EVERY = 256 << 20
UA = {"User-Agent": "strata-compare-fetch/1.0"}
LOG = None


def log(msg):
    line = time.strftime("%F %T ") + msg
    print(line, flush=True)
    if LOG:
        with open(LOG, "a") as f:
            f.write(line + "\n")


def alert(title, body, critical=False):
    subprocess.run(["notify-send", "-a", "model download", "-u", "critical" if critical else "normal", title, body],
                   stderr=subprocess.DEVNULL, check=False)


def api_tree(repo: str, revision: str) -> dict:
    """{path: (size, sha256)} of the repo's LFS files at REVISION (paged by Link headers, as tools/hf_pin_fetch.py)."""
    out, url = {}, f"https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=1&expand=0"
    while url:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            for e in json.load(r):
                if e.get("type") == "file" and e.get("lfs"):
                    out[e["path"]] = (int(e["lfs"]["size"]), e["lfs"]["oid"])
            link = r.headers.get("Link", "")
        url = next((p.split(";")[0].strip(" <>") for p in link.split(",") if 'rel="next"' in p), None)
    return out


def load_pins(path: str) -> dict:
    d = json.loads(Path(path).read_text())
    for k in ("repo", "revision", "files"):
        if k not in d:
            sys.exit(f"{path}: no '{k}' (make it with `fetch_model.py pins`)")
    if not re.fullmatch(r"[0-9a-f]{40}", d["revision"]):
        sys.exit(f"{path}: revision {d['revision']!r} is not a commit hash - pin the commit, not a branch")
    for name, (size, sha) in d["files"].items():
        if not re.fullmatch(r"[0-9a-f]{64}", sha or ""):
            sys.exit(f"{path}: {name} has no sha256 - every file is pinned by its hash")
    return d


def check_dest(dest: Path, anywhere: bool) -> Path:
    dest = dest.resolve()
    if str(dest).startswith(str(Path.home() / ".cache")):
        sys.exit(f"{dest}: never into ~/.cache (the user's rule)")
    if not anywhere and not str(dest).startswith(str(WS / "models")):
        sys.exit(f"{dest}: not under {WS / 'models'} (--dest-anywhere if you mean it)")
    return dest


def url_of(pins: dict, name: str, base: str | None) -> str:
    if base:
        return str(Path(base) / name)
    return f"https://huggingface.co/{pins['repo']}/resolve/{pins['revision']}/{name}"


def read_range(url: str, start: int, end: int) -> tuple[bytes, int | None]:
    """bytes start..end (inclusive) and the file's total size; a local path is read directly (offline tests)."""
    if not url.startswith("http"):
        with open(url, "rb") as f:
            f.seek(start)
            return f.read(end - start + 1), os.path.getsize(url)
    req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cr = r.headers.get("Content-Range", "")
        m = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", cr.strip())
        # #327 (tools/mtp_fetch.py): a mirror that ignores Range answers 200 with the whole file - refuse, never read it
        if r.status != 206 or not m or int(m.group(1)) != start or int(m.group(2)) > end:
            raise OSError(f"no proper range answer (HTTP {r.status}, Content-Range {cr!r}): not reading the whole file")
        return r.read(end - start + 1), (int(m.group(3)) if m.group(3) != "*" else None)


def fetch_head(pins: dict, name: str, dest: Path, base: str | None) -> Path:
    """The .gguf's header alone: ranges from 8 MiB up (doubling, 512 MiB at most) until gguf_head parses it."""
    url, out = url_of(pins, name, base), dest / Path(name).name
    size_pin = pins["files"][name][0]
    want, data, total = 8 << 20, b"", None
    while True:
        if len(data) < want:
            more, total = read_range(url, len(data), min(want, size_pin) - 1)
            data += more
        tmp = out.with_name(out.name + ".head-part")
        tmp.write_bytes(data)
        try:
            gguf_head.read_shard(tmp)
            hend = gguf_head.read_shard.layout[0]
            break
        except (ValueError, KeyError) as e:
            if "truncated" not in str(e) or len(data) >= min(512 << 20, size_pin):
                tmp.unlink()
                raise
            want *= 2
    if total is not None and total != size_pin:
        tmp.unlink()
        raise OSError(f"{name}: the server says {total} bytes, the pin {size_pin}")
    tmp.write_bytes(data[:hend])
    os.replace(tmp, out)
    Path(str(out) + ".size").write_text(f"{size_pin}\n")
    log(f"{name}: header {hend:,} bytes of {size_pin:,} -> {out} (+ .size)")
    return out


def drop(fd):
    os.fdatasync(fd)
    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)


def rehash(path, h):
    fd = os.open(path, os.O_RDONLY)
    n = 0
    try:
        while b := os.read(fd, 16 << 20):
            h.update(b)
            n += len(b)
            if n % DROP_EVERY < (16 << 20):
                os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)
    return n


def fetch_file(pins, name, dest: Path, rate, status, base):
    size, sha = pins["files"][name]
    final = dest / name
    part = Path(str(final) + ".part")
    final.parent.mkdir(parents=True, exist_ok=True)
    if name in status["verified"] and final.exists() and final.stat().st_size == size:
        log(f"{name}: already verified")
        return True
    h = hashlib.sha256()
    have = part.stat().st_size if part.exists() else 0
    if have > size:
        os.truncate(part, 0)
        have = 0
    if have:
        log(f"{name}: resuming at {have / 1e9:.2f} GB (re-reading the partial file for the checksum)")
        rehash(part, h)
    url = url_of(pins, name, base)
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    fails, t_file, b_file = 0, time.monotonic(), have
    try:
        while have < size:
            try:
                if not url.startswith("http"):
                    raise OSError("get needs a URL (--base-url is for heads / tests)")
                req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={have}-"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    if have and r.status != 206:
                        raise OSError(f"no range support (HTTP {r.status})")
                    t0, got, since = time.monotonic(), 0, 0
                    while b := r.read(CHUNK):
                        mv = memoryview(b)
                        while mv:
                            mv = mv[os.write(fd, mv):]
                        h.update(b)
                        have += len(b)
                        got += len(b)
                        since += len(b)
                        fails = 0
                        if since >= DROP_EVERY:
                            drop(fd)
                            since = 0
                            el = time.monotonic() - t_file
                            status.update(file=name, file_done=have, file_size=size,
                                          MBps=round((have - b_file) / el / 1e6, 1) if el > 0 else None)
                            (dest / "fetch-status.json").write_text(json.dumps(status, indent=1))
                        ahead = got / (rate * 1e6) - (time.monotonic() - t0)
                        if ahead > 0:
                            time.sleep(ahead)
            except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as e:
                if isinstance(e, OSError) and e.errno == 28:          # ENOSPC: not a network error
                    raise
                fails += 1
                log(f"{name}: {type(e).__name__}: {str(e)[:160]} at {have / 1e9:.2f} GB - retry {fails}/20")
                if fails > 20:
                    return False
                time.sleep(min(300, 15 * fails))
        drop(fd)
    finally:
        os.close(fd)
    digest = h.hexdigest()
    if have != size or digest != sha:
        os.replace(part, Path(str(final) + ".bad"))
        log(f"{name}: MISMATCH - {have} of {size} bytes, sha256 {digest} vs the pin {sha} -> {name}.bad")
        return False
    os.replace(part, final)
    status["verified"].append(name)
    el = time.monotonic() - t_file
    log(f"{name}: {size / 1e9:.2f} GB in {el / 60:.1f} min ({(size - b_file) / max(el, 1e-9) / 1e6:.1f} MB/s), sha256 matches the pin")
    return True


def plan(pins, dest: Path, keep=KEEP_FREE) -> bool:
    status = json.loads((dest / "fetch-status.json").read_text()) if (dest / "fetch-status.json").exists() else {"verified": []}
    rest = sum(s for n, (s, _) in pins["files"].items() if n not in status["verified"])
    parts = sum((dest / (n + ".part")).stat().st_size for n in pins["files"] if (dest / (n + ".part")).exists())
    probe = dest if dest.exists() else WS / "models"
    free = shutil.disk_usage(probe).free
    after = free - (rest - parts)
    ok = after >= keep
    log(f"plan: {len(pins['files'])} files, {sum(s for s, _ in pins['files'].values()) / 1e9:.1f} GB pinned, "
        f"{(rest - parts) / 1e9:.1f} GB still to fetch; {free / 1e9:.1f} GB free -> {after / 1e9:.1f} GB after "
        f"({'ok' if ok else 'SHORT by %.1f GB of the %d GB that stay free: ask the user what to delete - nothing is deleted here' % ((keep - after) / 1e9, keep / 1e9)})")
    return ok


def main():
    global LOG
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["pins", "heads", "plan", "get", "unit"])
    ap.add_argument("--repo")
    ap.add_argument("--revision")
    ap.add_argument("--match", action="append", default=[], help="pins: keep only paths matching this glob")
    ap.add_argument("--out", help="pins: the JSON to write")
    ap.add_argument("--pins")
    ap.add_argument("--dest")
    ap.add_argument("--dest-anywhere", action="store_true")
    ap.add_argument("--rate", type=float, default=35.0, help="MB/s cap (1 MB = 10^6 bytes)")
    ap.add_argument("--keep-gb", type=float, default=100.0)
    ap.add_argument("--name", default="model-download", help="unit: the systemd unit's name")
    ap.add_argument("--base-url", help="tests: read ranges from local files in this directory instead of HTTP")
    ap.add_argument("--no-unit-ok", action="store_true", help="get: run outside a systemd unit")
    a = ap.parse_args()
    if a.cmd == "pins":
        if not (a.repo and a.revision and a.out):
            ap.error("pins needs --repo, --revision (a commit) and --out")
        t = api_tree(a.repo, a.revision)
        files = {p: list(v) for p, v in sorted(t.items()) if not a.match or any(fnmatch.fnmatch(p, g) for g in a.match)}
        Path(a.out).write_text(json.dumps({"repo": a.repo, "revision": a.revision, "files": files}, indent=1) + "\n")
        print(f"{len(files)} files, {sum(s for s, _ in files.values()) / 1e9:.1f} GB -> {a.out} (edit it down to what you want)")
        return 0
    if not (a.pins and a.dest):
        ap.error(f"{a.cmd} needs --pins and --dest")
    pins = load_pins(a.pins)
    dest = check_dest(Path(a.dest), a.dest_anywhere)
    if a.cmd == "unit":
        py = WS / ".venv/bin/python"
        print(f"systemd-run --user --unit {a.name} --collect -p MemoryHigh=2G -p WorkingDirectory={WS} {py} -u "
              f"{Path(__file__).resolve()} get --pins {Path(a.pins).resolve()} --dest {dest} --rate {a.rate} --keep-gb {a.keep_gb:g}")
        print(f"# follow: journalctl --user -u {a.name} -f   or   tail -f {dest}/fetch.log")
        return 0
    keep = a.keep_gb * 1e9
    if a.cmd == "plan":                     # nothing written (not even DEST) by a plan
        return 0 if plan(pins, dest, keep) else 3
    if a.cmd == "get" and not os.environ.get("INVOCATION_ID") and not a.no_unit_ok:
        sys.exit("get runs as a user-level systemd unit (the user's rule): `fetch_model.py unit ...` prints the line")
    dest.mkdir(parents=True, exist_ok=True)
    LOG = dest / "fetch.log"
    if a.cmd == "heads":
        hd = dest / "heads"
        hd.mkdir(exist_ok=True)
        for name in pins["files"]:
            if name.endswith(".gguf"):
                fetch_head(pins, name, hd, a.base_url)
        print(f"next: python3 bringup/inspect_model.py {hd}/<shard 1>.gguf; python3 bringup/fitplan.py {hd}/<shard 1>.gguf")
        return 0
    # get (inside its unit)
    if not plan(pins, dest, keep):
        alert("Model download not started", f"Not enough room: {a.keep_gb:g} GB must stay free.", critical=True)
        return 3
    sp = dest / "fetch-status.json"
    status = json.loads(sp.read_text()) if sp.exists() else {}
    status.setdefault("verified", [])
    names = sorted(pins["files"], key=lambda n: (pins["files"][n][0] > 1e9, n))      # small files first
    log(f"{len(names)} files from {pins['repo']}@{pins['revision'][:12]}, cap {a.rate} MB/s -> {dest}")
    for name in names:
        rest = sum(pins["files"][n][0] for n in names if n not in status["verified"])
        rest -= sum((dest / (n + ".part")).stat().st_size for n in names if (dest / (n + ".part")).exists())
        free = shutil.disk_usage(dest).free
        if free - rest < keep:
            log(f"STOP: {free / 1e9:.1f} GB free, {rest / 1e9:.1f} GB still to download - would leave less than {a.keep_gb:g} GB")
            alert("Model download stopped", f"Not enough room: {free / 1e9:.0f} GB free, {rest / 1e9:.0f} GB to go "
                  f"({a.keep_gb:g} GB must stay free).", critical=True)
            sp.write_text(json.dumps(status, indent=1))
            return 1
        if not fetch_file(pins, name, dest, a.rate, status, a.base_url):
            sp.write_text(json.dumps(status, indent=1))
            alert("Model download failed", f"{name}: see {LOG}", critical=True)
            return 1
        sp.write_text(json.dumps(status, indent=1))
    (dest / "fetch-done").write_text(time.strftime("%F %T\n"))
    free = shutil.disk_usage(dest).free
    log(f"ALL DONE: {len(names)} files verified against their pinned sha256, {free / 1e9:.1f} GB free")
    alert("Model download done", f"{len(names)} files, checksums OK; {free / 1e9:.0f} GB free.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
