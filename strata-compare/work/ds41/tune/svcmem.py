#!/usr/bin/env python3
"""svcmem.py LABEL OUTFILE - 10-24 DeepSeek-V4.1 tuning round, the daily store size (the user: "choose the daily size with
the services that run alongside it day to day (Jan, SearXNG for web search, LDR if it stays up) ... report both sizes and
what each service costs in RAM"). One line per call: MemAvailable and each service group's RSS, by the RAM-dip recorder's
own grouping (deep-research tools/ram_dip.py, imported read-only), appended to OUTFILE as JSON.
"""
import json
import sys
import time

sys.path.insert(0, "/home/USER/ai/deep-research/tools")
import ram_dip  # noqa: E402

KEEP = ("Jan (app + its MCP servers)", "SearXNG 8888 (chat page)", "SearXNG 8889 (LDR)", "SearXNG (other granian)",
        "LDR (ldr-web)", "research runner", "strata-proxy", "browser")


def main():
    label, out = sys.argv[1], sys.argv[2]
    g = ram_dip.groups(ram_dip.procs())
    rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label,
           "MemAvailable_gib": round(ram_dip.meminfo()["MemAvailable"] / ram_dip.GIB, 2),
           "rss_gib": {k: (g.get(k) or {}).get("rss_gib", 0) for k in KEEP}}
    open(out, "a").write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
