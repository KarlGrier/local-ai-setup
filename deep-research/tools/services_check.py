#!/usr/bin/env python3
"""services_check.py [--proxy] [--ldr] [--need PORTS] - the runners' pre-flight check (the user, 10-21): SearXNG 8889, 8890
and 8888 (a stopped unit is started once), optionally strata-proxy 8090 and LDR 5000. Prints one line per problem and
exits 1 when a REQUIRED service is down (--need, default 8889: the instance LDR and the checks search with); the other
SearXNG instances are reported as warnings (exit 0) - the watcher alerts on them too."""
import argparse
import sys
import urllib.request

sys.path.insert(0, "/home/USER/ai/deep-research/tools")
import research_common as rc  # noqa: E402


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status < 500
    except OSError:
        return False


ap = argparse.ArgumentParser()
ap.add_argument("--proxy", action="store_true", help="strata-proxy 8090 must answer")
ap.add_argument("--ldr", action="store_true", help="LDR 5000 must answer")
ap.add_argument("--need", default="8889", help="SearXNG ports that must answer (comma list; 'all' = 8889,8890,8888)")
a = ap.parse_args()
need = {8889, 8890, 8888} if a.need == "all" else {int(x) for x in a.need.split(",") if x}
probs = rc.searxng_problems()
fatal = []
for p, why in sorted(probs.items()):
    (fatal if p in need else []).append(why)
    print(("FAIL " if p in need else "WARN ") + why)
if a.proxy and not http_ok("http://127.0.0.1:8090/v1/models"):
    fatal.append("strata-proxy 8090 not answering"); print("FAIL strata-proxy 8090 not answering")
if a.ldr and not http_ok("http://127.0.0.1:5000/auth/login"):
    fatal.append("LDR 5000 not answering"); print("FAIL LDR 5000 not answering")
if not probs and not fatal:
    print("services ok: SearXNG 8889 8890 8888" + (", proxy 8090" if a.proxy else "") + (", LDR 5000" if a.ldr else ""))
sys.exit(1 if fatal else 0)
