#!/usr/bin/env python3
"""gentle_dl.py (day-one copy, 11-05) - work/qwen4-kit/unsloth-v31/dl/gentle_dl.py made general for Qwen4 day one. The
v3.1 copy is left as it was.

  gentle_dl.py --tree TREE.json --repo OWNER/NAME --commit SHA --dest DIR [--window measure|gap|any] [--gap-match TEXT]
               [--rate MB/s] [--ldr-share 0.25] [--ldr-fallback-mb 35] [--plan | --selftest DIR] PATH...

Kept from the v3.1 copy (Karl 11-04): pinned to a commit; every file's size and sha256 = the pinned LFS oid in TREE.json
(sha256 on the stream; "<file>.part" renamed only on a match, else -> .bad, exit 1); every 256 MiB fdatasync +
POSIX_FADV_DONTNEED on what it wrote; a file that would leave less than 100 GB free is refused (exit 3); downloaded
bytes are data only - never executed.

THE WINDOW (Karl 11-05, verbatim: "start as soon as I run it. If a gap is measuring, wait only until that gap closes;
never wait for the next gap. Rate-limit it only if LDR fetches would be starved.")
  --window measure  (the DEFAULT) transfers at once; pauses only while a gap is OPEN (tmp/port-gap.lockpid non-empty:
                    the measuring state - 8080 down, a test running) and resumes as soon as it closes. No "allowed gap"
                    is needed and none is waited for.
  --window gap      the 11-04 rule (kept for reference): transfers ONLY inside an open gap whose bench hold names one of
                    --gap-match (non-timed gaps).
  --window any      never pauses.
THE RATE: no fixed cap by default (--rate 0). --rate N sets one anyway.
  The LDR rule: while an LDR research run is LIVE, the download leaves a fixed share of the line to it - capped at
  (1 - --ldr-share) x the line rate this download measured itself while uncapped (default share 0.25 -> 75 %); before
  any measurement, at --ldr-fallback-mb (35 MB/s: bringup/fetch_model.py's standing cap "the research runs' web
  searches keep the rest of the line"). LIVE = deep-research's run/bench.lock is held, read from /proc/locks (the lock
  is never taken or tried - port_gap4.sh waits on the same lock for "the running research run").
  Why a share and not a starvation test: the only direct signal of starved fetches is LDR's own fetch log / proxy
  traffic, which is the user's research (off limits: titles / dates only), and it would show starvation only after
  fetches had already timed out; LDR's fetches are small (SearXNG <= 6 results, <= 12,000 chars a page), so a quarter
  of the line is far more than they use - the cap prevents starvation instead of reacting to it, and is observable from
  this side alone (this download's own rate, the lock).
  --plan        no network: per file here + verified / partial / to transfer; the bytes, the time (at the measured-line
                guess of --plan-line-mb), the disk check (>= 100 GB after); exit 0, or 3 if the floor fails.
  --selftest D  the window and rate decisions and the /proc/locks reading, on a lock file in D (no network).
"""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request

SC = "/home/USER/ai-speed-testing/strata-compare"
LOCKPID = f"{SC}/tmp/port-gap.lockpid"
HOLD = "/home/USER/ai/deep-research/tmp/bench2.hold"
BENCH_LOCK = "/home/USER/ai/deep-research/run/bench.lock"
CHUNK, DROP_EVERY, FLOOR = 1 << 20, 256 << 20, 100e9


def log(m):
    print(time.strftime("%F %T"), m, flush=True)


def gap_open(lockpid=LOCKPID):
    try:
        return os.path.getsize(lockpid) > 0
    except OSError:
        return False


def lock_held(path):
    """is a flock / POSIX lock held on PATH by anyone? read from /proc/locks (major:minor:inode), never taking it"""
    try:
        st = os.stat(path)
        want = (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)
        with open("/proc/locks") as f:
            for ln in f:
                for tok in ln.split():
                    parts = tok.split(":")
                    if len(parts) == 3:
                        try:
                            if (int(parts[0], 16), int(parts[1], 16), int(parts[2])) == want:
                                return True
                        except ValueError:
                            pass
    except OSError:
        return False
    return False


def window(a):
    """may it transfer now? measure: not while a gap is open; gap: only inside a named open gap; any: always"""
    if a.window == "any":
        return True
    if a.window == "measure":
        return not gap_open(a.lockpid)
    try:
        if not gap_open(a.lockpid):
            return False
        h = open(HOLD).read()
    except OSError:
        return False
    return any(k in h for k in a.gap_match)


def rate_cap(a, line_mbps):
    """MB/s cap now (0 = none): --rate if set; else, while an LDR run is live, (1 - share) x the measured line rate
    (the fallback before a measurement); else none"""
    if a.rate > 0:
        return a.rate, "fixed --rate"
    if lock_held(a.ldr_lock):
        if line_mbps:
            return (1 - a.ldr_share) * line_mbps, f"an LDR run is live: {100 * (1 - a.ldr_share):.0f} % of the measured {line_mbps:.0f} MB/s"
        return a.ldr_fallback_mb, "an LDR run is live: fallback cap (no line measurement yet)"
    return 0.0, "no cap (no LDR run live)"


def rehash(path):
    """sha256 + length of an existing .part, reading it without keeping its pages cached."""
    h, n = hashlib.sha256(), 0
    with open(path, "rb") as f:
        while True:
            b = f.read(8 << 20)
            if not b:
                break
            h.update(b); n += len(b)
            os.posix_fadvise(f.fileno(), 0, n, os.POSIX_FADV_DONTNEED)
    return h, n


LINE = {"mbps": None}     # this download's own uncapped rate (EMA over 4 s windows), kept across files


def fetch(a, url, out, size, oid):
    part = out + ".part"
    h, have = rehash(part) if os.path.exists(part) else (hashlib.sha256(), 0)
    if have > size:
        raise SystemExit(f"{part} is longer than the pinned size - stopped")
    waited = False
    while have < size:
        if not window(a):
            if not waited:
                log(f"{os.path.basename(out)}: paused - " + ("a gap is open (measuring); resumes when it closes"
                                                            if a.window == "measure" else
                                                            f"waiting for an allowed gap ({' | '.join(a.gap_match)})"))
                waited = True
            time.sleep(10 if a.window == "measure" else 30); continue
        waited = False
        cap, why = rate_cap(a, LINE["mbps"])
        log(f"{os.path.basename(out)}: transferring from {have:,} of {size:,} B (window {a.window}; "
            + (f"cap {cap:.0f} MB/s: {why})" if cap else f"{why})"))
        req = urllib.request.Request(url, headers={"Range": f"bytes={have}-", "User-Agent": "gentle-dl/1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(part, "ab") as f:
                if have and r.status != 206:
                    raise RuntimeError(f"HTTP {r.status} to a Range request")
                fd, last = f.fileno(), have
                t0, got, w0, wgot, tchk = time.monotonic(), 0, time.monotonic(), 0, time.monotonic()
                while have < size:
                    if time.monotonic() - tchk >= 2:          # the window and the LDR state, every 2 s
                        tchk = time.monotonic()
                        if not window(a):
                            log("a gap opened - pausing" if a.window == "measure" else "the gap closed - pausing"); break
                        new_cap, new_why = rate_cap(a, LINE["mbps"])
                        if abs(new_cap - cap) > 0.5:
                            log(f"rate: {('cap %.0f MB/s: ' % new_cap) if new_cap else ''}{new_why}")
                            cap, t0, got = new_cap, time.monotonic(), 0
                    b = r.read(CHUNK)
                    if not b:
                        break
                    f.write(b); h.update(b); have += len(b); got += len(b); wgot += len(b)
                    if have - last >= DROP_EVERY:
                        f.flush(); os.fdatasync(fd); os.posix_fadvise(fd, 0, have, os.POSIX_FADV_DONTNEED); last = have
                    dt = time.monotonic() - w0
                    if dt >= 4:
                        if not cap:                           # the line measured only while uncapped
                            v = wgot / dt / 1e6
                            LINE["mbps"] = v if LINE["mbps"] is None else 0.7 * LINE["mbps"] + 0.3 * v
                        w0, wgot = time.monotonic(), 0
                    if cap:
                        lag = got / (cap * 1e6) - (time.monotonic() - t0)
                        if lag > 0:
                            time.sleep(lag)
                f.flush(); os.fdatasync(fd); os.posix_fadvise(fd, 0, have, os.POSIX_FADV_DONTNEED)
        except Exception as e:   # noqa: BLE001 - any network / HTTP error: re-derive the state from the file, retry
            log(f"error {e!r} - retry in 60 s"); time.sleep(60)
            h, have = rehash(part)
    if have != size or h.hexdigest() != oid:
        os.replace(part, out + ".bad")
        raise SystemExit(f"{out}: size {have:,} / sha256 {h.hexdigest()} does not match {size:,} / {oid} - kept as .bad")
    os.replace(part, out)
    log(f"{os.path.basename(out)}: done, sha256 OK ({oid})")


def sums_of(dest):
    p, out = os.path.join(dest, "SHA256SUMS"), {}
    if os.path.exists(p):
        for ln in open(p):
            if ln.strip():
                h, _, n = ln.strip().partition("  ")
                out[n] = h
    return out


def plan(a, pin):
    sums, rows, todo = sums_of(a.dest), [], 0
    for p in a.paths:
        size, oid = pin[p]
        out = os.path.join(a.dest, os.path.basename(p))
        have = os.path.getsize(out) if os.path.exists(out) else 0
        part = os.path.getsize(out + ".part") if os.path.exists(out + ".part") else 0
        if have == size and sums.get(os.path.basename(p)) == oid:
            st, left = "here, verified (size + SHA256SUMS = the pin)", 0
        elif have == size:
            st, left = "here, size matches, NO SHA256SUMS line: re-hash before use", 0
        elif part:
            st, left = f"partial: {part:,} of {size:,} B (.part)", size - part
        else:
            st, left = "to transfer", size
        todo += left
        rows.append({"path": p, "size": size, "oid": oid, "state": st, "to_transfer": left})
        print(f"  {p}: {size / 1e9:.2f} GB - {st}")
    du = shutil.disk_usage(a.dest if os.path.isdir(a.dest) else os.path.dirname(a.dest.rstrip("/")) or "/")
    after = du.free - todo
    r_ = a.rate or a.plan_line_mb
    win = {"measure": "at once; paused only while a gap is open (measuring)", "any": "any time",
           "gap": "inside gaps whose hold names " + " | ".join(a.gap_match or ["<none given>"])}[a.window]
    print(f"to transfer {todo / 1e9:.1f} GB: ~{todo / (r_ * 1e6) / 60:.0f} min at {r_:g} MB/s "
          f"({'the --rate cap' if a.rate else 'no cap; the guessed line rate --plan-line-mb'}; while an LDR run is live: "
          f"{100 * (1 - a.ldr_share):.0f} % of the measured line, {a.ldr_fallback_mb:g} MB/s before a measurement); {win}; "
          f"free {du.free / 1e9:.1f} GB -> {after / 1e9:.1f} GB after (floor 100 GB: {'OK' if after >= FLOOR else 'FAILS'})")
    print(json.dumps({"files": rows, "to_transfer": todo, "free": du.free, "free_after": after, "floor_ok": after >= FLOOR}))
    return 0 if after >= FLOOR else 3


def selftest(d):
    """the window and rate decisions and the /proc/locks reading, on files in D (no network)"""
    os.makedirs(d, exist_ok=True)
    lp, lk = os.path.join(d, "lockpid"), os.path.join(d, "bench.lock")
    open(lp, "w").close()
    open(lk, "w").close()
    fails = []

    def chk(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'} {name}")
        fails.extend([] if cond else [name])
    a = argparse.Namespace(window="measure", lockpid=lp, gap_match=[], rate=0.0, ldr_share=0.25, ldr_fallback_mb=35.0,
                           ldr_lock=lk)
    chk("measure: no gap open -> transfers at once", window(a))
    open(lp, "w").write("12345\n")
    chk("measure: a gap open (lockpid non-empty) -> paused", not window(a))
    open(lp, "w").close()
    chk("measure: the gap closed -> transfers again (no waiting for another gap)", window(a))
    chk("no LDR run live -> no cap", rate_cap(a, 400.0)[0] == 0)
    with open(lk) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        chk("lock_held reads a held flock from /proc/locks", lock_held(lk))
        chk("LDR live, line measured 400 MB/s -> cap 300 (75 %)", abs(rate_cap(a, 400.0)[0] - 300.0) < 1e-6)
        chk("LDR live, no measurement yet -> the 35 MB/s fallback", rate_cap(a, None)[0] == 35.0)
        fcntl.flock(f, fcntl.LOCK_UN)
    chk("lock released -> not held, no cap", not lock_held(lk) and rate_cap(a, 400.0)[0] == 0)
    a.rate = 50.0
    chk("--rate 50 -> a fixed cap whatever LDR does", rate_cap(a, 400.0)[0] == 50.0)
    a.window = "gap"
    chk("gap (11-04 rule) without an open gap -> paused", not window(a))
    print(f"selftest: {len(fails)} failure(s)")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    if "--selftest" in sys.argv:
        return selftest(sys.argv[sys.argv.index("--selftest") + 1])
    ap.add_argument("--tree", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--window", choices=["measure", "gap", "any"], default="measure")
    ap.add_argument("--gap-match", action="append", default=[])
    ap.add_argument("--rate", type=float, default=float(os.environ.get("DL_RATE_MB", "0")), help="a fixed cap, MB/s (0 = none)")
    ap.add_argument("--ldr-share", type=float, default=0.25, help="the line share left to a live LDR run")
    ap.add_argument("--ldr-fallback-mb", type=float, default=35.0)
    ap.add_argument("--ldr-lock", default=BENCH_LOCK)
    ap.add_argument("--lockpid", default=LOCKPID)
    ap.add_argument("--plan-line-mb", type=float, default=100.0, help="--plan's time estimate without a cap")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("paths", nargs="+")
    a = ap.parse_args()
    if len(a.commit) != 40 or any(c not in "0123456789abcdef" for c in a.commit):
        raise SystemExit(f"--commit {a.commit!r} is not a commit hash: pin the commit, not a branch")
    pin = {e["path"]: (e["size"], e["lfs"]["oid"]) for e in json.load(open(a.tree)) if e.get("type") == "file" and e.get("lfs")}
    miss = [p for p in a.paths if p not in pin]
    if miss:
        raise SystemExit(f"not pinned in {a.tree}: {miss}")
    if a.plan:
        return plan(a, pin)
    if a.window == "gap" and not a.gap_match:
        raise SystemExit("--window gap needs --gap-match TEXT: name the non-timed gap(s) whose window it may use")
    os.makedirs(a.dest, exist_ok=True)
    sums = open(os.path.join(a.dest, "SHA256SUMS"), "a")
    for p in a.paths:
        size, oid = pin[p]
        out = os.path.join(a.dest, os.path.basename(p))
        if os.path.exists(out) and os.path.getsize(out) == size:
            log(f"{p}: already here ({size:,} B)"); continue
        st = os.statvfs(a.dest)
        have = os.path.getsize(out + ".part") if os.path.exists(out + ".part") else 0
        if st.f_bavail * st.f_frsize - (size - have) < FLOOR:
            log(f"{p}: would leave under 100 GB free - stopped"); return 3
        fetch(a, f"https://huggingface.co/{a.repo}/resolve/{a.commit}/{p}", out, size, oid)
        sums.write(f"{oid}  {os.path.basename(p)}\n"); sums.flush()
    log("all files done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
