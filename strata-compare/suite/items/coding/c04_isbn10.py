LEVEL = "easy"
KIND = "parsing"
ENTRY = "is_valid_isbn10"
PROMPT = """Write a Python function `is_valid_isbn10(s: str) -> bool`.

Rules:
- Hyphens may appear only between two characters of the code: not at the start, not at the end, and never two in a row. Remove them before the checks below.
- After removing hyphens the code must be exactly 10 characters: nine ASCII digits ('0'-'9') followed by a final character that is an ASCII digit or an uppercase `X` (value 10). `X` anywhere else, a lowercase `x`, spaces or any other character make the code invalid.
- With values d1..d10 (d1 first), the code is valid when (10*d1 + 9*d2 + 8*d3 + ... + 1*d10) is divisible by 11.
Return True or False; never raise.
"""

GOOD = r'''
def is_valid_isbn10(s):
    if not isinstance(s, str) or not s:
        return False
    if s[0] == "-" or s[-1] == "-" or "--" in s:
        return False
    code = s.replace("-", "")
    if len(code) != 10:
        return False
    vals = []
    for i, ch in enumerate(code):
        if ch in "0123456789":
            vals.append(int(ch))
        elif ch == "X" and i == 9:
            vals.append(10)
        else:
            return False
    return sum((10 - i) * v for i, v in enumerate(vals)) % 11 == 0
'''

BAD = r'''
def is_valid_isbn10(s):
    code = s.replace("-", "")
    if len(code) != 10:
        return False
    total = 0
    for i, ch in enumerate(code):
        if ch.isdigit():
            v = int(ch)
        elif ch in "xX":
            v = 10
        else:
            return False
        total += (10 - i) * v
    return total % 11 == 0
'''

# ==== HIDDEN TESTS ====
def test_valid(sol):
    for s in ["0306406152", "0-306-40615-2", "080442957X", "0-8044-2957-X", "3598215088", "0000000000"]:
        assert sol.is_valid_isbn10(s) is True, s


def test_bad_checksum(sol):
    for s in ["0306406153", "0804429579", "3598215089"]:
        assert sol.is_valid_isbn10(s) is False, s


def test_hyphen_placement(sol):
    for s in ["-0306406152", "0306406152-", "0-306--406152", "-"]:
        assert sol.is_valid_isbn10(s) is False, s


def test_x_rules(sol):
    assert sol.is_valid_isbn10("080442957x") is False
    assert sol.is_valid_isbn10("X804429570") is False
    assert sol.is_valid_isbn10("08044295X7") is False


def test_lengths_and_chars(sol):
    for s in ["", "030640615", "03064061522", "0 306406152", "03064O6152", "0306406152 "]:
        assert sol.is_valid_isbn10(s) is False, s


def test_unicode_digits(sol):
    assert sol.is_valid_isbn10("030640615٢") is False
