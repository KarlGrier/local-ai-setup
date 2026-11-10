LEVEL = "hard"
KIND = "algorithms"
ENTRY = "fuel_path"
PROMPT = """Write a Python function `fuel_path(grid: list[str], capacity: int) -> int`.

The grid is a rectangle of characters: `S` (start, exactly one), `G` (goal, exactly one), `.` (open), `#` (wall) and `F` (fuel station). A vehicle starts at S with a full tank of `capacity` units. Each move to one of the 4 neighbouring cells (up, down, left, right; never into a wall or off the grid) uses 1 unit, and a move is only possible with at least 1 unit left. Arriving on an `F` cell fills the tank back to `capacity` (stations can be used any number of times). Return the minimum number of moves needed to reach G, or -1 if G cannot be reached. If S or G is missing (or appears more than once), or capacity < 0, raise `ValueError`.

Grids can be up to 120 x 120 with capacity up to 300; the solution must finish in a few seconds.
"""

GOOD = r'''
from collections import deque


def fuel_path(grid, capacity):
    if capacity < 0:
        raise ValueError("capacity must be >= 0")
    starts = [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "S"]
    goals = [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "G"]
    if len(starts) != 1 or len(goals) != 1:
        raise ValueError("need exactly one S and one G")
    rows = len(grid)
    sr, sc = starts[0]
    # best[r][c] = most fuel seen at (r, c) for the current BFS layer or earlier
    best = [[-1] * len(row) for row in grid]
    best[sr][sc] = capacity
    q = deque([(sr, sc, capacity, 0)])
    while q:
        r, c, f, d = q.popleft()
        if grid[r][c] == "G":
            return d
        if f == 0:
            continue
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < len(grid[nr]) and grid[nr][nc] != "#":
                nf = capacity if grid[nr][nc] == "F" else f - 1
                if nf > best[nr][nc]:
                    best[nr][nc] = nf
                    q.append((nr, nc, nf, d + 1))
    return -1
'''

BAD = r'''
from collections import deque


def fuel_path(grid, capacity):
    if capacity < 0:
        raise ValueError("capacity must be >= 0")
    starts = [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "S"]
    goals = [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "G"]
    if len(starts) != 1 or len(goals) != 1:
        raise ValueError("need exactly one S and one G")
    seen = {starts[0]}
    q = deque([(starts[0][0], starts[0][1], capacity, 0)])
    while q:
        r, c, f, d = q.popleft()
        if grid[r][c] == "G":
            return d
        if f == 0:
            continue
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < len(grid) and 0 <= nc < len(grid[nr]) and grid[nr][nc] != "#" and (nr, nc) not in seen:
                seen.add((nr, nc))
                q.append((nr, nc, capacity if grid[nr][nc] == "F" else f - 1, d + 1))
    return -1
'''

# ==== HIDDEN TESTS ====
def _ref(grid, cap):
    from collections import deque
    s = next((r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "S")
    seen = {(s[0], s[1], cap)}
    q = deque([(s[0], s[1], cap, 0)])
    while q:
        r, c, f, d = q.popleft()
        if grid[r][c] == "G":
            return d
        if f == 0:
            continue
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < len(grid) and 0 <= nc < len(grid[nr]) and grid[nr][nc] != "#":
                nf = cap if grid[nr][nc] == "F" else f - 1
                if (nr, nc, nf) not in seen:
                    seen.add((nr, nc, nf))
                    q.append((nr, nc, nf, d + 1))
    return -1


def test_simple(sol):
    assert sol.fuel_path(["S..G"], 3) == 3
    assert sol.fuel_path(["S..G"], 2) == -1
    assert sol.fuel_path(["S.F.G"], 2) == 4


def test_detour_for_fuel(sol):
    grid = ["S...#....",
            ".##.#.##.",
            ".F#...#.G",
            "..#####.."]
    assert sol.fuel_path(grid, 12) == _ref(grid, 12)
    assert sol.fuel_path(grid, 5) == _ref(grid, 5)


def test_needs_station_twice(sol):
    grid = ["G...F...S"]
    assert sol.fuel_path(grid, 4) == 8
    assert sol.fuel_path(grid, 3) == -1


def test_zero_capacity(sol):
    assert sol.fuel_path(["SG"], 0) == -1
    assert sol.fuel_path(["S", "G"], 1) == 1


def test_errors(sol):
    for g, cap in ((["S.."], 3), (["..G"], 3), (["SSG"], 3), (["SGG"], 3), (["SG"], -1)):
        try:
            sol.fuel_path(g, cap)
        except ValueError:
            continue
        raise AssertionError(g)


def test_random(sol):
    import random
    rng = random.Random(12)
    for _ in range(150):
        h, w = rng.randint(1, 8), rng.randint(2, 8)
        cells = [rng.choice("..#F.") for _ in range(h * w)]
        a, b = rng.sample(range(h * w), 2)
        cells[a], cells[b] = "S", "G"
        grid = ["".join(cells[r * w:(r + 1) * w]) for r in range(h)]
        cap = rng.randint(0, 6)
        assert sol.fuel_path(grid, cap) == _ref(grid, cap), (grid, cap)


def test_large(sol):
    import random
    import time
    rng = random.Random(1)
    n = 120
    cells = [["#" if rng.random() < 0.25 else ("F" if rng.random() < 0.03 else ".") for _ in range(n)] for _ in range(n)]
    cells[0][0], cells[n - 1][n - 1] = "S", "G"
    cells[0][1] = cells[1][0] = cells[n - 2][n - 1] = cells[n - 1][n - 2] = "."
    grid = ["".join(r) for r in cells]
    t = time.time()
    got = [sol.fuel_path(grid, cap) for cap in (10, 12, 15, 20, 300)]
    assert time.time() - t < 8
    assert got == [-1, 286, 254, 242, 238], got
