"""The staged s2_search.py (optional with 7d): key file read at request time, HTTP status per call, 429 surfaced.
python -I -B test_s2.py"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _offline as T  # noqa: E402

T.wire_providers()
import paid_search as PS  # noqa: E402
import s2_search as S2  # noqa: E402

n_ok = 0


def ok(cond, what):
    global n_ok
    assert cond, what
    n_ok += 1


def log():
    p = Path(os.environ["S2_LOG"])
    return [json.loads(x) for x in p.read_text().split("\n") if x] if p.exists() else []


ok(str(S2.KEY_FILE).startswith(str(T.TMP)), f"the key path is inside the test HOME: {S2.KEY_FILE}")
ok(not S2.has_key(), "no key file -> unauthenticated, as before")
got = S2.search("mixture of experts offloading")
ok(isinstance(got, list) and len(got) == 2 and got[0]["url"].startswith("https://doi.org/10.1234/"), got)
ok(T.Mock.s2_keyed == [False] and S2.last_status() == "sent", "no x-api-key header without the file")
ok(log()[-1]["status"] == 200 and log()[-1]["key"] is False and log()[-1]["results"] == 2, log()[-1])

S2.KEY_FILE.write_text(T.FAKE_KEY + "\n")
got = S2.search("expert prefetching")
ok(T.Mock.s2_keyed[-1] is True and S2.has_key(), "the key from the file goes out as x-api-key")
ok(log()[-1]["key"] is True and T.FAKE_KEY not in json.dumps(log()), "the log says a key was used, never the key")

ok(S2.search("rate429 please") is None and S2.last_status() == "error: HTTP 429", "HTTP 429 -> None + status")
ok(log()[-1]["status"] == 429 and log()[-1]["error"] == "HTTP 429", log()[-1])
ok(all("query" not in r for r in log()), "no query text in the S2 log")
ok(all(r["t"][-5] in "+-" for r in log()), "times carry their UTC offset")

# route 7a: the route log's free-source outcome now shows why S2 gave nothing
T.write_run_file("screen-deep-p7a-check/o01", "7a", written=1.0)
PS.search("rate429 paper search", [{"url": "https://searx.example/1"}], client="ldr")
row = T.route_rows()[-1]
ok(row["actions"][0]["source"] == "s2" and row["actions"][0]["outcome"] == "error: HTTP 429", row["actions"])
PS.search("a working paper search", [{"url": "https://searx.example/1"}], client="ldr")
ok(T.route_rows()[-1]["actions"][0]["outcome"] == "sent", "a working S2 call is 'sent' as before")
S2.KEY_FILE.unlink()

T.finish(f"test_s2: {n_ok} checks passed")
