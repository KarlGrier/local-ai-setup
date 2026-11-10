LEVEL = "medium"
KIND = "bug fix"
ENTRY = "moving_average"
PROMPT = '''The function below is meant to return the average of every full window of `window` consecutive values, in order, as floats: for n values there are n - window + 1 averages. It must raise `ValueError` when `window` is not between 1 and len(values) (inclusive), and it must run in O(n) time for long lists. Users report wrong results. Find and fix every bug; return the whole corrected function.

```python
def moving_average(values, window):
    if window < 1 or window >= len(values):
        raise ValueError("bad window")
    out = []
    total = sum(values[:window])
    for i in range(window, len(values)):
        out.append(total // window)
        total += values[i] - values[i - window + 1]
    return out
```
'''

GOOD = r'''
def moving_average(values, window):
    if window < 1 or window > len(values):
        raise ValueError("bad window")
    out = []
    total = sum(values[:window])
    out.append(total / window)
    for i in range(window, len(values)):
        total += values[i] - values[i - window]
        out.append(total / window)
    return out
'''

BAD = r'''
def moving_average(values, window):
    if window < 1 or window > len(values):
        raise ValueError("bad window")
    out = []
    total = sum(values[:window])
    for i in range(window, len(values)):
        out.append(total / window)
        total += values[i] - values[i - window]
    return out
'''

# ==== HIDDEN TESTS ====
def _close(a, b):
    return len(a) == len(b) and all(abs(x - y) < 1e-9 for x, y in zip(a, b))


def test_basic(sol):
    assert _close(sol.moving_average([1, 2, 3, 4, 5], 2), [1.5, 2.5, 3.5, 4.5])
    assert _close(sol.moving_average([1, 2, 3, 4, 5], 3), [2.0, 3.0, 4.0])


def test_full_window(sol):
    assert _close(sol.moving_average([4, 8], 2), [6.0])
    assert _close(sol.moving_average([7], 1), [7.0])


def test_window_one(sol):
    assert _close(sol.moving_average([3, -1, 2], 1), [3.0, -1.0, 2.0])


def test_floats_type(sol):
    out = sol.moving_average([1, 2], 2)
    assert isinstance(out[0], float) and abs(out[0] - 1.5) < 1e-12


def test_invalid(sol):
    for vals, w in (([1, 2, 3], 0), ([1, 2, 3], 4), ([], 1), ([1], -1)):
        try:
            sol.moving_average(vals, w)
        except ValueError:
            continue
        raise AssertionError((vals, w))


def test_random(sol):
    import random
    rng = random.Random(2)
    for _ in range(300):
        vals = [rng.randint(-50, 50) for _ in range(rng.randint(1, 30))]
        w = rng.randint(1, len(vals))
        exp = [sum(vals[i:i + w]) / w for i in range(len(vals) - w + 1)]
        assert _close(sol.moving_average(vals, w), exp)


def test_linear_time(sol):
    import time
    vals = list(range(1_000_000))
    t = time.time()
    out = sol.moving_average(vals, 5000)
    assert len(out) == 1_000_000 - 4999
    assert time.time() - t < 3
