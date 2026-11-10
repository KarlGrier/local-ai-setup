LEVEL = "medium"
KIND = "bug fix"
ENTRY = "first_at_least"
PROMPT = '''The function below should return the index of the first element of the sorted list `a` that is greater than or equal to `x`, or `len(a)` if there is none. It must stay O(log n) (do not use the `bisect` module and do not scan the list). It has bugs. Fix them and return the whole corrected function.

```python
def first_at_least(a, x):
    """Index of the first element >= x in the sorted list a; len(a) if none."""
    lo, hi = 0, len(a) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo
```
'''

GOOD = r'''
def first_at_least(a, x):
    """Index of the first element >= x in the sorted list a; len(a) if none."""
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return lo
'''

BAD = r'''
def first_at_least(a, x):
    """Index of the first element >= x in the sorted list a; len(a) if none."""
    lo, hi = 0, len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if a[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo
'''

# ==== HIDDEN TESTS ====
import bisect as _bisect


def test_examples(sol):
    a = [1, 3, 3, 3, 7, 9]
    assert sol.first_at_least(a, 3) == 1
    assert sol.first_at_least(a, 4) == 4
    assert sol.first_at_least(a, 0) == 0
    assert sol.first_at_least(a, 9) == 5


def test_past_end(sol):
    assert sol.first_at_least([1, 2, 3], 4) == 3
    assert sol.first_at_least([], 4) == 0
    assert sol.first_at_least([5], 6) == 1
    assert sol.first_at_least([5], 5) == 0


def test_duplicates(sol):
    a = [2] * 10 + [4] * 10
    assert sol.first_at_least(a, 2) == 0
    assert sol.first_at_least(a, 3) == 10
    assert sol.first_at_least(a, 4) == 10


def test_random(sol):
    import random
    rng = random.Random(9)
    for _ in range(2000):
        a = sorted(rng.randint(-20, 20) for _ in range(rng.randint(0, 15)))
        x = rng.randint(-25, 25)
        assert sol.first_at_least(a, x) == _bisect.bisect_left(a, x), (a, x)


def test_log_time(sol):
    import time
    a = list(range(0, 4_000_000, 2))
    t = time.time()
    for x in range(0, 200000, 7):
        assert sol.first_at_least(a, x) == (x + 1) // 2
    assert time.time() - t < 3
