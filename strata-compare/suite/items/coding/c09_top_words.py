LEVEL = "medium"
KIND = "parsing"
ENTRY = "top_words"
PROMPT = """Write a Python function `top_words(text: str, k: int) -> list[tuple[str, int]]`.

Rules:
- A token is a maximal run of ASCII letters (a-z, A-Z) and apostrophes ('). Strip apostrophes from both ends of each token; what remains, lowercased, is a word. Tokens that become empty are ignored. Inside a word apostrophes stay ("Don't" -> "don't").
- Count how often each word occurs.
- Return the k most frequent words as (word, count) pairs, ordered by count (highest first) and, for equal counts, alphabetically (plain string order).
- If there are fewer than k distinct words, return all of them. k = 0 gives []. A negative k raises `ValueError`.
"""

GOOD = r'''
import re
from collections import Counter


def top_words(text, k):
    if k < 0:
        raise ValueError("k must be >= 0")
    words = []
    for tok in re.findall(r"[A-Za-z']+", text):
        w = tok.strip("'").lower()
        if w:
            words.append(w)
    c = Counter(words)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
'''

BAD = r'''
import re
from collections import Counter


def top_words(text, k):
    if k < 0:
        raise ValueError("k must be >= 0")
    words = [t.strip("'").lower() for t in re.findall(r"[A-Za-z']+", text)]
    words = [w for w in words if w]
    return Counter(words).most_common(k)
'''

# ==== HIDDEN TESTS ====
def test_basic(sol):
    assert sol.top_words("the cat and the hat", 2) == [("the", 2), ("and", 1)]


def test_ties_alphabetical(sol):
    assert sol.top_words("b a c b a c d", 3) == [("a", 2), ("b", 2), ("c", 2)]
    assert sol.top_words("zeta alpha zeta alpha mid", 5) == [("alpha", 2), ("zeta", 2), ("mid", 1)]


def test_apostrophes(sol):
    assert sol.top_words("Don't 'quote' me, don't!", 2) == [("don't", 2), ("me", 1)]
    assert sol.top_words("'' ' rock'n'roll", 3) == [("rock'n'roll", 1)]


def test_non_letters_split(sol):
    assert sol.top_words("e-mail e mail 123abc ABC", 3) == [("abc", 2), ("e", 2), ("mail", 2)]
    assert sol.top_words("café cafe", 5) == [("caf", 1), ("cafe", 1)]


def test_k_edges(sol):
    assert sol.top_words("a b", 0) == []
    assert sol.top_words("a b", 10) == [("a", 1), ("b", 1)]
    assert sol.top_words("", 3) == []
    try:
        sol.top_words("a", -1)
    except ValueError:
        pass
    else:
        raise AssertionError("no ValueError")


def test_case(sol):
    assert sol.top_words("Hello HELLO hello World", 1) == [("hello", 3)]
