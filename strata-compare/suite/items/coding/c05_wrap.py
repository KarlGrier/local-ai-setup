LEVEL = "easy"
KIND = "algorithms"
ENTRY = "wrap_text"
PROMPT = """Write a Python function `wrap_text(text: str, width: int) -> list[str]` that wraps text greedily.

Rules:
- Words are the pieces of `text` separated by whitespace (any run of spaces, tabs or newlines).
- Fill each line with as many words as fit, joined by single spaces, so that the line is at most `width` characters long; then start a new line.
- A word longer than `width` goes on a line of its own, unbroken.
- Return the list of lines (no trailing spaces). Blank or empty text gives [].
- If `width` < 1, raise `ValueError`.
"""

GOOD = r'''
def wrap_text(text, width):
    if width < 1:
        raise ValueError("width must be at least 1")
    lines, cur = [], ""
    for w in text.split():
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
'''

BAD = r'''
def wrap_text(text, width):
    if width < 1:
        raise ValueError("width must be at least 1")
    lines, cur = [], ""
    for w in text.split():
        if not cur:
            cur = w
        elif len(cur) + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
'''

# ==== HIDDEN TESTS ====
def test_basic(sol):
    assert sol.wrap_text("the quick brown fox jumps", 10) == ["the quick", "brown fox", "jumps"]


def test_exact_fit(sol):
    assert sol.wrap_text("aaaa bbbb cccc", 9) == ["aaaa bbbb", "cccc"]
    assert sol.wrap_text("aaaa bbbb cccc", 8) == ["aaaa", "bbbb", "cccc"]


def test_long_word(sol):
    assert sol.wrap_text("a supercalifragilistic b", 5) == ["a", "supercalifragilistic", "b"]


def test_whitespace(sol):
    assert sol.wrap_text("  one\ttwo\n\nthree   ", 7) == ["one two", "three"]
    assert sol.wrap_text("   \n\t ", 4) == []
    assert sol.wrap_text("", 4) == []


def test_width_one(sol):
    assert sol.wrap_text("a b cd", 1) == ["a", "b", "cd"]


def test_invalid_width(sol):
    for w in (0, -3):
        try:
            sol.wrap_text("abc", w)
        except ValueError:
            continue
        raise AssertionError("no ValueError for width %d" % w)


def test_random_property(sol):
    import random
    rng = random.Random(3)
    for _ in range(200):
        words = ["x" * rng.randint(1, 9) for _ in range(rng.randint(0, 30))]
        width = rng.randint(1, 20)
        lines = sol.wrap_text(" ".join(words), width)
        assert " ".join(lines).split() == words
        for i, ln in enumerate(lines):
            assert len(ln) <= width or " " not in ln
            if i + 1 < len(lines):
                assert len(ln) + 1 + len(lines[i + 1].split()[0]) > width
