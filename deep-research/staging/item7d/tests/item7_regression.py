"""Regression (11-03): item 7's own suites (staging/item7/tests: test_route, test_paid_search, test_cache) run against
the STAGED 7d search_route / paid_search / s2_search with TODAY'S live paid-route.json - i.e. with the table as it is,
the 7d code behaves exactly as the installed code. Their harness is replaced by item 7d's _offline (temp files under
staging/item7d/scratch, not /tmp); the suites' sources are read, not changed. python -I -B item7_regression.py"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ITEM7 = Path("/home/USER/ai/deep-research/staging/item7/tests")
SUITES = ["test_route", "test_paid_search", "test_cache"]

if len(sys.argv) == 3 and sys.argv[1] == "--one":
    sys.path.insert(0, str(HERE))
    import _offline
    _offline.TOOLS = _offline.LIVE_TOOLS
    import search_route
    search_route.CONFIG_FILE = Path(_offline.LIVE_TOOLS) / "paid-route.json"
    sys.modules["_offline"] = _offline
    f = ITEM7 / f"{sys.argv[2]}.py"
    exec(compile(f.read_text(), str(f), "exec"), {"__name__": "__main__", "__file__": str(f)})
else:
    for t in SUITES:
        r = subprocess.run([sys.executable, "-I", "-B", __file__, "--one", t], capture_output=True, text=True)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-3000:])
            raise SystemExit(f"item 7 suite {t} FAILED against the staged 7d code")
        print(f"  item7/{t} (staged 7d code, live table): {last}")
    print(f"item7_regression: {len(SUITES)} item 7 suites passed against the staged 7d code")
