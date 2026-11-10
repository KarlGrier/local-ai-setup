LEVEL = "hard"
KIND = "algorithms"
ENTRY = "full_match"
PROMPT = """Write a Python function `full_match(pattern: str, text: str) -> bool` implementing a small regular-expression language without using the `re` module (or any regex library). The whole text must match the whole pattern.

Pattern syntax:
- An atom is: a literal character; `.` (any single character); a class `[...]`; or `\\` followed by any character (that character literally, e.g. `\\.` or `\\*` or `\\\\`).
- A class lists characters and ranges like `a-z`; `[^...]` negates it. Inside a class, `\\` escapes the next character, `-` is literal when it is first or last, and `]` is literal when it is the first character (after an optional `^`). A class must not be empty.
- An atom may be followed by one quantifier: `*` (zero or more), `+` (one or more) or `?` (zero or one).
- Invalid patterns raise `ValueError`: a quantifier with no atom before it (including two quantifiers in a row like `a**`), an unterminated class, an empty class `[]` or `[^]`, a range whose start is after its end (`[z-a]`), a trailing lone backslash.

The matcher must not take exponential time: patterns like `a*a*a*a*a*a*a*a*b` on a text of 30 `a`s must answer quickly.
"""

GOOD = r'''
def _parse(p):
    atoms = []
    i, n = 0, len(p)
    while i < n:
        c = p[i]
        if c in "*+?":
            raise ValueError("quantifier without atom")
        if c == "\\":
            if i + 1 >= n:
                raise ValueError("trailing backslash")
            atom = ("lit", p[i + 1])
            i += 2
        elif c == ".":
            atom = ("any",)
            i += 1
        elif c == "[":
            i += 1
            neg = False
            if i < n and p[i] == "^":
                neg = True
                i += 1
            items = []
            first = True
            while True:
                if i >= n:
                    raise ValueError("unterminated class")
                ch = p[i]
                if ch == "]" and not first:
                    i += 1
                    break
                if ch == "\\":
                    if i + 1 >= n:
                        raise ValueError("trailing backslash")
                    ch = p[i + 1]
                    i += 2
                else:
                    i += 1
                first = False
                if i + 1 < n and p[i] == "-" and p[i + 1] != "]":
                    hi = p[i + 1]
                    j = i + 2
                    if hi == "\\":
                        if i + 2 >= n:
                            raise ValueError("trailing backslash")
                        hi = p[i + 2]
                        j = i + 3
                    if ch > hi:
                        raise ValueError("bad range")
                    items.append((ch, hi))
                    i = j
                else:
                    items.append((ch, ch))
            if not items:
                raise ValueError("empty class")
            atom = ("cls", neg, tuple(items))
        else:
            atom = ("lit", c)
            i += 1
        q = None
        if i < n and p[i] in "*+?":
            q = p[i]
            i += 1
            if i < n and p[i] in "*+?":
                raise ValueError("double quantifier")
        atoms.append((atom, q))
    return atoms


def _ok(atom, ch):
    if atom[0] == "lit":
        return ch == atom[1]
    if atom[0] == "any":
        return True
    hit = any(a <= ch <= b for a, b in atom[2])
    return hit != atom[1]


def full_match(pattern, text):
    atoms = _parse(pattern)
    # NFA simulation over positions in the atom list
    def closure(states):
        out, stack = set(), list(states)
        while stack:
            k = stack.pop()
            if k in out:
                continue
            out.add(k)
            if k < len(atoms) and atoms[k][1] in ("*", "?"):
                stack.append(k + 1)
        return out

    cur = closure({0})
    for ch in text:
        nxt = set()
        for k in cur:
            if k < len(atoms) and _ok(atoms[k][0], ch):
                q = atoms[k][1]
                if q in ("*", "+"):
                    nxt.add(k)
                    nxt.add(k + 1)
                else:
                    nxt.add(k + 1)
        cur = closure(nxt)
        if not cur:
            return False
    return len(atoms) in cur
'''

BAD = r'''
def full_match(pattern, text):
    def m(pi, ti):
        if pi == len(pattern):
            return ti == len(text)
        c = pattern[pi]
        if c == "\\":
            atom, nxt = pattern[pi + 1], pi + 2
        else:
            atom, nxt = c, pi + 1
        q = pattern[nxt] if nxt < len(pattern) and pattern[nxt] in "*+?" else None
        ok = lambda t: t < len(text) and (atom == "." or text[t] == atom)
        if q in ("*", "+"):
            return m(nxt + 1, ti) or (ok(ti) and m(pi, ti + 1))
        if q == "?":
            return m(nxt + 1, ti) or (ok(ti) and m(nxt + 1, ti + 1))
        return ok(ti) and m(nxt, ti + 1)
    return m(0, 0)
'''

# ==== HIDDEN TESTS ====
import re as _re


def _raises(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False


def test_literals_and_dot(sol):
    assert sol.full_match("abc", "abc")
    assert not sol.full_match("abc", "abcd")
    assert not sol.full_match("abc", "ab")
    assert sol.full_match("a.c", "axc")
    assert sol.full_match("", "")
    assert not sol.full_match("", "a")


def test_quantifiers(sol):
    assert sol.full_match("ab*c", "ac") and sol.full_match("ab*c", "abbbc")
    assert not sol.full_match("ab+c", "ac") and sol.full_match("ab+c", "abc")
    assert sol.full_match("colou?r", "color") and sol.full_match("colou?r", "colour")
    assert not sol.full_match("colou?r", "colouur")
    assert sol.full_match(".*", "anything at all")


def test_classes(sol):
    assert sol.full_match("[a-c]+", "abcab") and not sol.full_match("[a-c]+", "abd")
    assert sol.full_match("[^0-9]*", "no digits") and not sol.full_match("[^0-9]*", "a1")
    assert sol.full_match("[]a]+", "]a]") and sol.full_match("[^]]", "x") and not sol.full_match("[^]]", "]")
    assert sol.full_match("[a-]+", "a-a") and sol.full_match("[-a]", "-")
    assert sol.full_match("[\\]x]", "]") and sol.full_match("[.]", ".") and not sol.full_match("[.]", "a")


def test_escapes(sol):
    assert sol.full_match("a\\.b", "a.b") and not sol.full_match("a\\.b", "axb")
    assert sol.full_match("\\*+", "***")
    assert sol.full_match("\\\\", "\\")


def test_invalid(sol):
    for bad in ["*a", "a**", "a+?", "[abc", "[]", "[^]", "[z-a]", "abc\\", "?", "[a-"]:
        assert _raises(sol.full_match, bad, "x"), bad


def test_no_backtracking_blowup(sol):
    import time
    t = time.time()
    assert not sol.full_match("a*a*a*a*a*a*a*a*a*a*b", "a" * 40)
    assert sol.full_match(".*.*.*.*.*.*x", "y" * 60 + "x")
    assert time.time() - t < 2


def test_random_against_re(sol):
    import random
    rng = random.Random(6)
    atoms = ["a", "b", ".", "[ab]", "[^a]", "\\.", "[a-c]"]
    for _ in range(1500):
        pat = "".join(rng.choice(atoms) + rng.choice(["", "", "*", "+", "?"]) for _ in range(rng.randint(0, 5)))
        txt = "".join(rng.choice("abc.") for _ in range(rng.randint(0, 7)))
        assert sol.full_match(pat, txt) == bool(_re.fullmatch(pat, txt, _re.S)), (pat, txt)
