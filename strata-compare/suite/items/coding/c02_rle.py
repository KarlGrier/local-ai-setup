LEVEL = "easy"
KIND = "parsing"
ENTRY = "compress"
PROMPT = """Write two Python functions for a run-length code.

`compress(s: str) -> str`: every maximal run of one character `c` repeated `n` times becomes `f"{n}{c}"` when n > 1, and just `c` when n == 1. Example: "aaabccdddd" -> "3ab2c4d". The empty string compresses to "". The input may contain any characters except decimal digits ('0'-'9'); if it contains a digit, raise `ValueError`.

`expand(code: str) -> str`: the exact inverse of `compress` for every string `compress` can produce. Raise `ValueError` for any code that `compress` could never produce, including: a count with no character after it ("3"), a count of 0 or 1 written out ("1a", "0a"), a count with a leading zero ("03a"), and two neighbouring runs of the same character ("2a3a", "a2a", "aa").
"""

GOOD = r'''
def compress(s):
    if any(ch in "0123456789" for ch in s):
        raise ValueError("digits are not allowed")
    out = []
    i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        n = j - i
        out.append((str(n) if n > 1 else "") + s[i])
        i = j
    return "".join(out)


def expand(code):
    out = []
    i = 0
    prev = None
    while i < len(code):
        j = i
        while j < len(code) and code[j] in "0123456789":
            j += 1
        digits = code[i:j]
        if j >= len(code):
            raise ValueError("count without a character")
        ch = code[j]
        if digits:
            if digits[0] == "0" or int(digits) < 2:
                raise ValueError("bad count")
            n = int(digits)
        else:
            n = 1
        if ch == prev:
            raise ValueError("neighbouring runs of the same character")
        out.append(ch * n)
        prev = ch
        i = j + 1
    return "".join(out)
'''

BAD = r'''
def compress(s):
    out = []
    i = 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        n = j - i
        out.append((str(n) if n > 1 else "") + s[i])
        i = j
    return "".join(out)


def expand(code):
    out = []
    i = 0
    while i < len(code):
        if code[i].isdigit():
            out.append(code[i + 1] * int(code[i]))
            i += 2
        else:
            out.append(code[i])
            i += 1
    return "".join(out)
'''

# ==== HIDDEN TESTS ====
def _raises(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False


def test_compress_basic(sol):
    assert sol.compress("aaabccdddd") == "3ab2c4d"
    assert sol.compress("") == ""
    assert sol.compress("abc") == "abc"
    assert sol.compress("zzzzzzzzzzzz") == "12z"


def test_compress_any_chars(sol):
    assert sol.compress("  !!é") == "2 2!é"
    assert sol.compress("\n\n\t") == "2\n\t"


def test_compress_digits_rejected(sol):
    assert _raises(sol.compress, "ab1")
    assert _raises(sol.compress, "0")


def test_expand_basic(sol):
    assert sol.expand("3ab2c4d") == "aaabccdddd"
    assert sol.expand("") == ""
    assert sol.expand("12z") == "z" * 12
    assert sol.expand("100x") == "x" * 100


def test_roundtrip(sol):
    import random
    rng = random.Random(7)
    for _ in range(300):
        s = "".join(rng.choice("ab -é") * rng.choice([1, 1, 2, 3, 11]) for _ in range(rng.randint(0, 8)))
        assert sol.expand(sol.compress(s)) == s


def test_expand_invalid(sol):
    for bad in ["3", "1a", "0a", "03a", "2a3a", "a2a", "aa", "ab2", "12"]:
        assert _raises(sol.expand, bad), bad
