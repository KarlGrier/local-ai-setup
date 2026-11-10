LEVEL = "medium"
KIND = "algorithms"
ENTRY = "min_rooms"
PROMPT = """Write a Python function `min_rooms(meetings: list[tuple[int, int]]) -> int`.

Each meeting is a pair (start, end) of integers meaning the half-open time interval [start, end): a meeting ending at 10 and another starting at 10 do not overlap. Return the minimum number of rooms needed so that no two overlapping meetings share a room. An empty list needs 0 rooms. If any meeting has end <= start, raise `ValueError`. The list can hold up to 200,000 meetings, so the solution must be O(n log n).
"""

GOOD = r'''
def min_rooms(meetings):
    events = []
    for s, e in meetings:
        if e <= s:
            raise ValueError("empty or negative meeting")
        events.append((s, 1))
        events.append((e, -1))
    events.sort(key=lambda x: (x[0], x[1]))
    cur = best = 0
    for _, d in events:
        cur += d
        best = max(best, cur)
    return best
'''

BAD = r'''
def min_rooms(meetings):
    events = []
    for s, e in meetings:
        if e <= s:
            raise ValueError("empty or negative meeting")
        events.append((s, -1))
        events.append((e, 1))
    events.sort()
    cur = best = 0
    for _, d in events:
        cur -= d
        best = max(best, cur)
    return best
'''

# ==== HIDDEN TESTS ====
def test_basic(sol):
    assert sol.min_rooms([]) == 0
    assert sol.min_rooms([(0, 30), (5, 10), (15, 20)]) == 2
    assert sol.min_rooms([(7, 10), (2, 4)]) == 1


def test_touching(sol):
    assert sol.min_rooms([(1, 10), (10, 20), (20, 30)]) == 1
    assert sol.min_rooms([(1, 10), (10, 20), (9, 11)]) == 2


def test_nested(sol):
    assert sol.min_rooms([(1, 100), (2, 99), (3, 98), (4, 97)]) == 4


def test_invalid(sol):
    for bad in ([(5, 5)], [(1, 2), (6, 3)]):
        try:
            sol.min_rooms(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_negative_times(sol):
    assert sol.min_rooms([(-10, -5), (-6, 0), (-5, 1)]) == 2


def test_large(sol):
    import random
    rng = random.Random(11)
    ms = []
    for _ in range(200000):
        s = rng.randint(0, 10 ** 6)
        ms.append((s, s + rng.randint(1, 50)))
    ev = sorted([(s, 1) for s, _ in ms] + [(e, -1) for _, e in ms], key=lambda x: (x[0], x[1]))
    cur = best = 0
    for _, d in ev:
        cur += d
        best = max(best, cur)
    assert sol.min_rooms(ms) == best
