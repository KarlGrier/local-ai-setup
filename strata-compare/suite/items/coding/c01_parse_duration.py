LEVEL = "easy"
KIND = "parsing"
ENTRY = "parse_duration"
PROMPT = """Write a Python function `parse_duration(text: str) -> int` that converts a duration string into a whole number of seconds.

Rules:
- A duration is one or more parts. Each part is a non-negative decimal integer immediately followed by a unit: `d` (days), `h` (hours), `m` (minutes) or `s` (seconds). Example: "1h30m" is 5400.
- Parts may be separated by any amount of whitespace, or written together ("2h 5m 10s" and "2h5m10s" are both 7510). Leading and trailing whitespace is ignored.
- Units must appear in the order d, h, m, s, each at most once. "30m1h" and "1h1h" are invalid.
- Units are case-insensitive ("1H" is valid). Leading zeros are allowed ("05m" is 300).
- Anything else is invalid: an empty or blank string, a number without a unit, a unit without a number, signs, decimals, other characters. For invalid input raise `ValueError`.
"""

GOOD = r'''
import re

_PART = re.compile(r"(\d+)\s*([dhms])", re.I)
_ORDER = "dhms"
_MULT = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_duration(text):
    if not isinstance(text, str):
        raise ValueError("not a string")
    s = text.strip()
    if not s:
        raise ValueError("empty")
    pos, total, last = 0, 0, -1
    while pos < len(s):
        m = re.compile(r"(\d+)([dhmsDHMS])").match(s, pos)
        if not m:
            raise ValueError("bad part at %d" % pos)
        unit = m.group(2).lower()
        idx = _ORDER.index(unit)
        if idx <= last:
            raise ValueError("unit order")
        last = idx
        total += int(m.group(1)) * _MULT[unit]
        pos = m.end()
        while pos < len(s) and s[pos].isspace():
            pos += 1
    return total
'''

BAD = r'''
import re

def parse_duration(text):
    s = text.strip()
    if not s:
        raise ValueError("empty")
    parts = re.findall(r"(\d+)\s*([dhms])", s, re.I)
    if not parts:
        raise ValueError("no parts")
    mult = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return sum(int(n) * mult[u.lower()] for n, u in parts)
'''

# ==== HIDDEN TESTS ====
def _raises(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False


def test_simple(sol):
    assert sol.parse_duration("45s") == 45
    assert sol.parse_duration("90m") == 5400
    assert sol.parse_duration("1h30m") == 5400
    assert sol.parse_duration("2d") == 172800


def test_spaces(sol):
    assert sol.parse_duration("2h 5m 10s") == 7510
    assert sol.parse_duration("  2h5m10s\t") == 7510
    assert sol.parse_duration("1d   1s") == 86401


def test_case_and_zeros(sol):
    assert sol.parse_duration("1H") == 3600
    assert sol.parse_duration("05m") == 300
    assert sol.parse_duration("0s") == 0


def test_order_and_repeat(sol):
    assert _raises(sol.parse_duration, "30m1h")
    assert _raises(sol.parse_duration, "1h1h")
    assert _raises(sol.parse_duration, "1s1m")


def test_invalid(sol):
    for bad in ["", "   ", "10", "h", "1x", "-1h", "1.5h", "1h 30", "1h,30m", "abc", "h1", "1 h", "1h 2"]:
        assert _raises(sol.parse_duration, bad), bad


def test_unit_space_allowed_between_parts_only(sol):
    assert sol.parse_duration("3d 4h 5m 6s") == 3 * 86400 + 4 * 3600 + 306
    assert _raises(sol.parse_duration, "1h30m!")


def test_big(sol):
    assert sol.parse_duration("100000d") == 100000 * 86400
