#!/usr/bin/env python3
"""download.py - 2026-10-23 (the user): DeepSeek-V4.1-Flash-1017 GSQ-RCO IQ2_XXS (4 backbone shards) + the shared
Engram file (~249 GB) from ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF, while phase 4's o03 runs. Not IQ1_M (the
user decides after the IQ2_XXS speed test; only its backbone would be needed then).
- Speed cap (--rate MB/s, default 35): the research runs' web searches keep most of the line.
- Out of the page cache: every 256 MiB written is synced and dropped (posix_fadvise DONTNEED); the systemd unit runs
  with MemoryHigh as a backstop.
- sha256 computed while writing and compared with the repo's LFS sha256 (a resumed .part is re-read the same way).
- Keeps >= 100 GB free: before each file, the rest of the download must still leave 100 GB (else it stops + alert).
Files land as NAME.part and are renamed when size and sha256 match (a mismatch -> NAME.bad). Log: logs/ds41/download.log,
status logs/ds41/download-status.json, logs/ds41/download-done when everything is verified; desktop alert at the end
(critical on a failure).
"""
import argparse
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

REPO = "ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF"
DEST = "/home/USER/ai-speed-testing/strata-compare/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF"
LOGD = "/home/USER/ai-speed-testing/strata-compare/logs/ds41"
KEEP_FREE = 100e9
CHUNK = 4 << 20
DROP_EVERY = 256 << 20
UA = {"User-Agent": "ds41-download/1.0"}


def log(msg):
    print(time.strftime("%F %T ") + msg, flush=True)


def alert(title, body, critical=False):
    subprocess.run(["notify-send", "-a", "DeepSeek-V4.1 download", "-u", "critical" if critical else "normal", title, body],
                   stderr=subprocess.DEVNULL, check=False)


def files():
    for i in range(10):
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    f"https://huggingface.co/api/models/{REPO}/tree/main?recursive=1", headers=UA), timeout=60) as r:
                tree = json.load(r)
            break
        except (urllib.error.URLError, OSError, ValueError) as e:
            log(f"file list: {e} - retry {i + 1}/10")
            time.sleep(30)
    else:
        raise SystemExit("could not list the repo")
    want = [f for f in tree if f.get("type") == "file"
            and ("IQ2_XXS" in f["path"] or "Engram" in f["path"] or f["path"] == "README.md")]
    return sorted(want, key=lambda f: (f["size"] > 1e9, "Engram" in f["path"], f["path"]))   # small, shards, Engram


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


def fetch(f, rate, status):
    name, size, sha = f["path"], f["size"], (f.get("lfs") or {}).get("oid")
    final = os.path.join(DEST, name)
    part = final + ".part"
    os.makedirs(os.path.dirname(final), exist_ok=True)
    if name in status["verified"] and os.path.exists(final) and os.path.getsize(final) == size:
        log(f"{name}: already verified")
        return True
    h = hashlib.sha256()
    have = os.path.getsize(part) if os.path.exists(part) else 0
    if have > size:
        os.truncate(part, 0)
        have = 0
    if have:
        log(f"{name}: resuming at {have / 1e9:.2f} GB (re-reading the partial file for the checksum)")
        rehash(part, h)
    url = f"https://huggingface.co/{REPO}/resolve/main/{name}"
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    fails, t_file, b_file = 0, time.monotonic(), have
    try:
        while have < size:
            try:
                req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={have}-"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    if r.status != 206 and have:
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
                            json.dump(status, open(os.path.join(LOGD, "download-status.json"), "w"), indent=1)
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
    el = time.monotonic() - t_file
    digest = h.hexdigest()
    if have != size or (sha and digest != sha):
        os.replace(part, final + ".bad")
        log(f"{name}: MISMATCH - {have} of {size} bytes, sha256 {digest} vs {sha} -> {name}.bad")
        return False
    os.replace(part, final)
    status["verified"].append(name)
    log(f"{name}: {size / 1e9:.2f} GB in {el / 60:.1f} min ({(size - b_file) / max(el, 1e-9) / 1e6:.1f} MB/s), "
        f"{'sha256 matches' if sha else 'size matches (no LFS sha256 for this file)'}")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, default=35.0, help="MB/s cap (1 MB = 10^6 bytes)")
    a = ap.parse_args()
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(LOGD, exist_ok=True)
    sp = os.path.join(LOGD, "download-status.json")
    status = json.load(open(sp)) if os.path.exists(sp) else {}
    status.setdefault("verified", [])
    fl = files()
    total = sum(f["size"] for f in fl)
    log(f"{len(fl)} files, {total / 1e9:.2f} GB, cap {a.rate} MB/s -> {DEST}")
    for f in fl:
        rest = sum(g["size"] for g in fl if g["path"] not in status["verified"]) - sum(
            os.path.getsize(os.path.join(DEST, g["path"]) + ".part") for g in fl
            if os.path.exists(os.path.join(DEST, g["path"]) + ".part"))
        free = shutil.disk_usage(DEST).free
        if free - rest < KEEP_FREE:
            log(f"STOP: {free / 1e9:.1f} GB free, {rest / 1e9:.1f} GB still to download - would leave less than 100 GB")
            alert("DeepSeek-V4.1 download stopped", f"Not enough room: {free / 1e9:.0f} GB free, {rest / 1e9:.0f} GB to go "
                  "(100 GB must stay free).", critical=True)
            raise SystemExit(1)
        if not fetch(f, a.rate, status):
            json.dump(status, open(sp, "w"), indent=1)
            alert("DeepSeek-V4.1 download failed", f"{f['path']}: see logs/ds41/download.log", critical=True)
            raise SystemExit(1)
        json.dump(status, open(sp, "w"), indent=1)
    free = shutil.disk_usage(DEST).free
    open(os.path.join(LOGD, "download-done"), "w").write(time.strftime("%F %T\n"))
    log(f"ALL DONE: {len(fl)} files verified, {free / 1e9:.1f} GB free")
    alert("DeepSeek-V4.1 download done", f"IQ2_XXS + Engram: {len(fl)} files, checksums OK; {free / 1e9:.0f} GB free.")


if __name__ == "__main__":
    main()
