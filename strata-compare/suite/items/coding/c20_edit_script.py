LEVEL = "hard"
KIND = "algorithms"
ENTRY = "edit_script"
PROMPT = """Write a Python function `edit_script(a: str, b: str) -> list[tuple]` that returns a shortest edit script turning `a` into `b`.

The script is a list of operations applied left to right while walking through `a`:
- `("keep", ch)`: copy the next character of `a` (it must equal `ch`) to the output,
- `("sub", old, new)`: replace the next character of `a` (which must be `old`) by `new` (with old != new),
- `("del", ch)`: skip the next character of `a` (it must equal `ch`),
- `("ins", ch)`: write `ch` to the output without consuming anything from `a`.
Applying the whole script must consume all of `a` and produce exactly `b`. The number of operations that are not "keep" must equal the Levenshtein distance between `a` and `b` (substitution, deletion and insertion each cost 1). Any shortest script is accepted. Strings can be up to 2,000 characters each; the solution must run in O(len(a) * len(b)) time.
"""

GOOD = r'''
def edit_script(a, b):
    n, m = len(a), len(b)
    prev = list(range(m + 1))
    rows = [prev]
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1]
            else:
                cur[j] = 1 + min(prev[j - 1], prev[j], cur[j - 1])
        rows.append(cur)
        prev = cur
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and a[i - 1] == b[j - 1] and rows[i][j] == rows[i - 1][j - 1]:
            ops.append(("keep", a[i - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and rows[i][j] == rows[i - 1][j - 1] + 1:
            ops.append(("sub", a[i - 1], b[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and rows[i][j] == rows[i - 1][j] + 1:
            ops.append(("del", a[i - 1]))
            i -= 1
        else:
            ops.append(("ins", b[j - 1]))
            j -= 1
    ops.reverse()
    return ops
'''

BAD = r'''
def edit_script(a, b):
    n, m = len(a), len(b)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if a[i] == b[j] else max(L[i + 1][j], L[i][j + 1])
    ops, i, j = [], 0, 0
    while i < n and j < m:
        if a[i] == b[j]:
            ops.append(("keep", a[i])); i += 1; j += 1
        elif L[i + 1][j] >= L[i][j + 1]:
            ops.append(("del", a[i])); i += 1
        else:
            ops.append(("ins", b[j])); j += 1
    ops += [("del", c) for c in a[i:]] + [("ins", c) for c in b[j:]]
    return ops
'''

# ==== HIDDEN TESTS ====
def _lev(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = prev[j - 1] if a[i - 1] == b[j - 1] else 1 + min(prev[j - 1], prev[j], cur[j - 1])
        prev = cur
    return prev[-1]


def _apply(a, ops):
    out, i = [], 0
    for op in ops:
        kind = op[0]
        if kind == "keep":
            assert len(op) == 2 and i < len(a) and a[i] == op[1], op
            out.append(op[1])
            i += 1
        elif kind == "sub":
            assert len(op) == 3 and i < len(a) and a[i] == op[1] and op[1] != op[2], op
            out.append(op[2])
            i += 1
        elif kind == "del":
            assert len(op) == 2 and i < len(a) and a[i] == op[1], op
            i += 1
        elif kind == "ins":
            assert len(op) == 2, op
            out.append(op[1])
        else:
            raise AssertionError("unknown op %r" % (op,))
    assert i == len(a), "did not consume all of a"
    return "".join(out)


def _check(sol, a, b):
    ops = [tuple(o) for o in sol.edit_script(a, b)]
    assert _apply(a, ops) == b, (a, b)
    assert sum(1 for o in ops if o[0] != "keep") == _lev(a, b), (a, b)


def test_examples(sol):
    _check(sol, "kitten", "sitting")
    _check(sol, "flaw", "lawn")
    _check(sol, "", "")
    _check(sol, "", "abc")
    _check(sol, "abc", "")
    _check(sol, "same", "same")


def test_substitution_preferred_when_shorter(sol):
    ops = sol.edit_script("abc", "axc")
    assert sum(1 for o in ops if o[0] != "keep") == 1


def test_random(sol):
    import random
    rng = random.Random(10)
    for _ in range(300):
        a = "".join(rng.choice("abcd") for _ in range(rng.randint(0, 12)))
        b = "".join(rng.choice("abcd") for _ in range(rng.randint(0, 12)))
        _check(sol, a, b)


def test_unicode(sol):
    _check(sol, "naïve café", "naive cafe!")


def test_large(sol):
    import random
    import time
    rng = random.Random(3)
    a = "".join(rng.choice("acgt") for _ in range(1500))
    b = list(a)
    for _ in range(200):
        k = rng.randrange(len(b))
        r = rng.random()
        if r < 0.33:
            b[k] = rng.choice("acgt")
        elif r < 0.66:
            del b[k]
        else:
            b.insert(k, rng.choice("acgt"))
    b = "".join(b)
    t = time.time()
    _check(sol, a, b)
    assert time.time() - t < 9
