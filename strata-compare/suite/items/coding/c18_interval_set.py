LEVEL = "hard"
KIND = "data structures"
ENTRY = "IntervalSet"
PROMPT = """Write a Python class `IntervalSet` that stores a set of integers as half-open intervals [lo, hi).

Methods:
- `add(lo: int, hi: int)`: add every integer x with lo <= x < hi.
- `remove(lo: int, hi: int)`: remove every integer x with lo <= x < hi (removing what is not there is fine).
- `contains(x: int) -> bool`.
- `intervals() -> list[tuple[int, int]]`: the stored set as a sorted list of disjoint, non-adjacent intervals (touching intervals are merged: adding [1, 3) and [3, 5) gives [(1, 5)]).
- `total() -> int`: how many integers are stored.
For `add` and `remove`: lo == hi does nothing; lo > hi raises `ValueError`.
With n stored intervals, `contains` must be O(log n), and `add`/`remove` O(log n + k) where k is the number of stored intervals they touch (a sorted list with `bisect` is fine). Up to 100,000 operations.
"""

GOOD = r'''
import bisect


class IntervalSet:
    def __init__(self):
        self._lo = []
        self._hi = []

    def add(self, lo, hi):
        if lo > hi:
            raise ValueError("lo > hi")
        if lo == hi:
            return
        i = bisect.bisect_left(self._hi, lo)          # first interval with hi >= lo (touching merges)
        j = bisect.bisect_right(self._lo, hi)         # intervals with lo <= hi touch or overlap
        if i < j:
            lo = min(lo, self._lo[i])
            hi = max(hi, self._hi[j - 1])
        self._lo[i:j] = [lo]
        self._hi[i:j] = [hi]

    def remove(self, lo, hi):
        if lo > hi:
            raise ValueError("lo > hi")
        if lo == hi:
            return
        i = bisect.bisect_right(self._hi, lo)         # first interval with hi > lo
        j = bisect.bisect_left(self._lo, hi)          # intervals with lo < hi overlap
        if i >= j:
            return
        new_lo, new_hi = [], []
        if self._lo[i] < lo:
            new_lo.append(self._lo[i])
            new_hi.append(lo)
        if self._hi[j - 1] > hi:
            new_lo.append(hi)
            new_hi.append(self._hi[j - 1])
        self._lo[i:j] = new_lo
        self._hi[i:j] = new_hi

    def contains(self, x):
        i = bisect.bisect_right(self._lo, x) - 1
        return i >= 0 and x < self._hi[i]

    def intervals(self):
        return list(zip(self._lo, self._hi))

    def total(self):
        return sum(h - l for l, h in zip(self._lo, self._hi))
'''

BAD = r'''
class IntervalSet:
    def __init__(self):
        self._iv = []

    def add(self, lo, hi):
        if lo > hi:
            raise ValueError("lo > hi")
        if lo == hi:
            return
        out = []
        for a, b in self._iv:
            if b < lo or a > hi or b == lo or a == hi:
                out.append((a, b))
            else:
                lo, hi = min(lo, a), max(hi, b)
        out.append((lo, hi))
        self._iv = sorted(out)

    def remove(self, lo, hi):
        if lo > hi:
            raise ValueError("lo > hi")
        out = []
        for a, b in self._iv:
            if b <= lo or a >= hi:
                out.append((a, b))
            else:
                if a < lo:
                    out.append((a, lo))
                if b > hi:
                    out.append((hi, b))
        self._iv = sorted(out)

    def contains(self, x):
        return any(a <= x < b for a, b in self._iv)

    def intervals(self):
        return list(self._iv)

    def total(self):
        return sum(b - a for a, b in self._iv)
'''

# ==== HIDDEN TESTS ====
def test_merge_touching(sol):
    s = sol.IntervalSet()
    s.add(1, 3)
    s.add(3, 5)
    assert s.intervals() == [(1, 5)]
    s.add(7, 9)
    s.add(5, 7)
    assert s.intervals() == [(1, 9)]
    assert s.total() == 8


def test_overlaps(sol):
    s = sol.IntervalSet()
    for lo, hi in [(10, 20), (30, 40), (15, 35), (-5, 0), (50, 60)]:
        s.add(lo, hi)
    assert s.intervals() == [(-5, 0), (10, 40), (50, 60)]
    assert s.contains(-5) and not s.contains(0) and s.contains(39) and not s.contains(40)


def test_remove_split(sol):
    s = sol.IntervalSet()
    s.add(0, 100)
    s.remove(10, 20)
    s.remove(50, 50)
    assert s.intervals() == [(0, 10), (20, 100)]
    s.remove(-10, 5)
    s.remove(90, 200)
    assert s.intervals() == [(5, 10), (20, 90)]
    s.remove(0, 1000)
    assert s.intervals() == [] and s.total() == 0


def test_errors_and_empty(sol):
    s = sol.IntervalSet()
    s.add(3, 3)
    assert s.intervals() == []
    for f in (s.add, s.remove):
        try:
            f(5, 4)
        except ValueError:
            continue
        raise AssertionError("no ValueError")


def test_random_against_set(sol):
    import random
    rng = random.Random(21)
    s = sol.IntervalSet()
    ref = set()
    for _ in range(3000):
        lo = rng.randint(-60, 60)
        hi = lo + rng.randint(0, 15)
        if rng.random() < 0.55:
            s.add(lo, hi)
            ref |= set(range(lo, hi))
        else:
            s.remove(lo, hi)
            ref -= set(range(lo, hi))
        x = rng.randint(-70, 80)
        assert s.contains(x) == (x in ref)
    exp, xs = [], sorted(ref)
    for x in xs:
        if exp and exp[-1][1] == x:
            exp[-1][1] = x + 1
        else:
            exp.append([x, x + 1])
    assert s.intervals() == [tuple(e) for e in exp]
    assert s.total() == len(ref)


def test_speed(sol):
    import time
    s = sol.IntervalSet()
    t = time.time()
    for i in range(50000):
        s.add(4 * i, 4 * i + 2)
    for i in range(50000):
        assert s.contains(4 * i + 1)
        assert not s.contains(4 * i + 3)
    for i in range(0, 50000, 2):
        s.remove(4 * i, 4 * i + 1)
    assert len(s.intervals()) == 50000
    assert time.time() - t < 6
