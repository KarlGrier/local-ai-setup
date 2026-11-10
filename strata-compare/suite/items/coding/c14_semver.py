LEVEL = "medium"
KIND = "parsing"
ENTRY = "compare_versions"
PROMPT = """Write a Python function `compare_versions(a: str, b: str) -> int` returning -1, 0 or 1 as version `a` has lower, equal or higher precedence than `b`, following Semantic Versioning 2.0.0:

- A version is MAJOR.MINOR.PATCH (non-negative integers without leading zeros, so "01" is invalid but "0" is fine), optionally followed by `-` and a pre-release, optionally followed by `+` and build metadata.
- Pre-release and build metadata are dot-separated identifiers made of ASCII letters, digits and hyphens; identifiers must not be empty. Numeric pre-release identifiers must not have leading zeros.
- Compare MAJOR, MINOR, PATCH numerically. A version with a pre-release has lower precedence than the same version without one.
- Pre-releases compare identifier by identifier: numeric identifiers numerically, alphanumeric ones in ASCII order, and a numeric identifier is lower than an alphanumeric one. If all shared identifiers are equal, the one with more identifiers is higher.
- Build metadata is ignored for precedence ("1.0.0+a" equals "1.0.0+b").
- Raise `ValueError` for any invalid version string.
"""

GOOD = r'''
import re

_IDENT = re.compile(r"^[0-9A-Za-z-]+$")


def _num(s):
    if not s.isdigit() or not s.isascii() or (len(s) > 1 and s[0] == "0"):
        raise ValueError("bad number %r" % s)
    return int(s)


def _parse(v):
    if not isinstance(v, str):
        raise ValueError("not a string")
    core, plus, build = v.partition("+")
    if plus:
        ids = build.split(".")
        if any(not _IDENT.match(i) for i in ids):
            raise ValueError("bad build")
    core, dash, pre = core.partition("-")
    parts = core.split(".")
    if len(parts) != 3:
        raise ValueError("need MAJOR.MINOR.PATCH")
    nums = tuple(_num(p) for p in parts)
    pre_ids = None
    if dash:
        pre_ids = pre.split(".")
        for i in pre_ids:
            if not _IDENT.match(i):
                raise ValueError("bad pre-release")
            if i.isdigit() and len(i) > 1 and i[0] == "0":
                raise ValueError("leading zero in pre-release")
    return nums, pre_ids


def _cmp(x, y):
    return (x > y) - (x < y)


def compare_versions(a, b):
    na, pa = _parse(a)
    nb, pb = _parse(b)
    if na != nb:
        return _cmp(na, nb)
    if pa is None or pb is None:
        if pa is None and pb is None:
            return 0
        return 1 if pa is None else -1
    for x, y in zip(pa, pb):
        xd, yd = x.isdigit(), y.isdigit()
        if xd and yd:
            c = _cmp(int(x), int(y))
        elif xd != yd:
            c = -1 if xd else 1
        else:
            c = _cmp(x, y)
        if c:
            return c
    return _cmp(len(pa), len(pb))
'''

BAD = r'''
def compare_versions(a, b):
    def parse(v):
        v = v.split("+")[0]
        core, _, pre = v.partition("-")
        nums = tuple(int(x) for x in core.split("."))
        if len(nums) != 3:
            raise ValueError("bad")
        return nums, pre
    na, pa = parse(a)
    nb, pb = parse(b)
    if na != nb:
        return (na > nb) - (na < nb)
    if not pa or not pb:
        return (not pa) - (not pb)
    xa, xb = pa.split("."), pb.split(".")
    return (xa > xb) - (xa < xb)
'''

# ==== HIDDEN TESTS ====
def _raises(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False


def test_core(sol):
    assert sol.compare_versions("1.0.0", "2.0.0") == -1
    assert sol.compare_versions("2.1.0", "2.0.9") == 1
    assert sol.compare_versions("1.10.0", "1.9.0") == 1
    assert sol.compare_versions("0.0.0", "0.0.0") == 0


def test_spec_chain(sol):
    chain = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
             "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
    for i in range(len(chain)):
        for j in range(len(chain)):
            exp = (i > j) - (i < j)
            assert sol.compare_versions(chain[i], chain[j]) == exp, (chain[i], chain[j])


def test_build_ignored(sol):
    assert sol.compare_versions("1.0.0+a", "1.0.0+b") == 0
    assert sol.compare_versions("1.0.0-rc.1+build.5", "1.0.0-rc.1") == 0
    assert sol.compare_versions("1.0.0+zzz", "1.0.1") == -1


def test_numeric_vs_alpha(sol):
    assert sol.compare_versions("1.0.0-2", "1.0.0-10") == -1
    assert sol.compare_versions("1.0.0-10", "1.0.0-a") == -1
    assert sol.compare_versions("1.0.0-a-b", "1.0.0-a") == 1
    assert sol.compare_versions("1.0.0-B", "1.0.0-a") == -1


def test_invalid(sol):
    for bad in ["1.0", "1.0.0.0", "01.0.0", "1.00.0", "1.0.0-", "1.0.0-01", "1.0.0-a..b", "1.0.0+",
                "1.0.0+a..b", "a.b.c", "1.0.0-a_b", "", "1.0.-1", " 1.0.0"]:
        assert _raises(sol.compare_versions, bad, "1.0.0"), bad
        assert _raises(sol.compare_versions, "1.0.0", bad), bad


def test_zero_ok(sol):
    assert sol.compare_versions("0.0.1-0", "0.0.1-0.0") == -1
    assert sol.compare_versions("10.20.30-0a", "10.20.30-0") == 1
