#!/usr/bin/env python3
"""maya-speed3.py BASE OUTDIR [PASSES [NPROMPT]] - PREPARED 10-25 for the Maya v1.1.28 head-to-head (not run yet).
work/ds41/tune/speed3.py unchanged (same requests, order, records, disk counters), with two things set from outside:
  ENGINE_NAME  the engine process whose /proc/<pid>/io is read per request (default maya-ds4; strata-dsv41 for the S arm)
  EFFORT       reasoning_effort sent as a JSON integer on every thinking-on request (default 62), for BOTH engines: Maya
               maps the name "medium" to 75 (frontend.py:121, ds41_encoding.py:445-479), Strata's DeepSeek template to
               62; an integer 1..100 is taken as given by both servers (Maya frontend.py:149-156; Strata frontend.py
               140-160), so S, M1 and M2 get the same "Reasoning Effort: 62" prompt line. Thinking-off requests (P4K,
               P20K) are sent as before (no reasoning_effort).
Use it for the S arm too (CLIENT="ENGINE_NAME=strata-dsv41 .venv/bin/python work/ds41/maya/maya-speed3.py $URL $OUT 3 3"),
so all arms send byte-identical bodies.
Note: the SSD GB a token from /proc/<pid>/io is not comparable across the engines (Strata's store reads with O_DIRECT,
Maya's CPU lane through page faults on the files); compare device_read_gb (the drive's own counter) instead.
"""
import os
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402
import speed3  # noqa: E402

NAME = os.environ.get("ENGINE_NAME", "maya-ds4")
EFFORT = int(os.environ.get("EFFORT", "62"))


def engine_pid():
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if os.path.basename(os.readlink(f"/proc/{p}/exe")) == NAME:
                    return int(p)
            except OSError:
                pass
    return None


_one = abrun.one


def one(base, arm, wl, sampling, extra, rep, out, keep_text=False):
    if wl.get("thinking", True):
        wl = dict(wl, effort=EFFORT)   # (abrun.one: body["reasoning_effort"] = wl.get("effort", "medium"))
    return _one(base, arm, wl, sampling, extra, rep, out, keep_text)


speed3.engine_pid = engine_pid
abrun.one = one

if __name__ == "__main__":
    speed3.main()
