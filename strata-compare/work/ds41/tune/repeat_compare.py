#!/usr/bin/env python3
"""repeat_compare.py RUNDIR [RUNDIR ...] - A.1: compares repeat_client.py's texts. Request 1 of each run (a fresh engine,
same prompt, same seed) against run 1's request 1; and request 2 against request 1 inside each run (same engine). Prints
identical / the first differing character and the text around it.
"""
import json
import sys


def texts(d):
    return {r["rep"]: r.get("text") or "" for r in map(json.loads, open(f"{d}/repeat.jsonl"))}


def diff(a, b):
    if a == b:
        return "identical"
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return f"differ from char {i} of {len(a)}/{len(b)}: ...{a[max(0, i - 40):i + 30]!r} vs ...{b[max(0, i - 40):i + 30]!r}"


def main():
    runs = sys.argv[1:]
    t = [texts(d) for d in runs]
    for k in range(1, len(t)):
        print(f"run {k + 1} vs run 1, request 1 (fresh engines): {diff(t[0].get(1, ''), t[k].get(1, ''))}")
    for k in range(len(t)):
        print(f"run {k + 1}, request 2 vs request 1 (same engine): {diff(t[k].get(1, ''), t[k].get(2, ''))}")


if __name__ == "__main__":
    main()
