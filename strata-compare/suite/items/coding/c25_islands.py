LEVEL = "hard"
KIND = "data structures"
ENTRY = "island_counts"
PROMPT = """Write a Python function `island_counts(rows: int, cols: int, cells: list[tuple[int, int]]) -> list[int]`.

A rows x cols map starts as all water. `cells` lists (row, col) positions that are turned into land one after another. After each step, report how many islands exist, where an island is a maximal group of land cells connected through their 4 neighbours (up, down, left, right; no diagonals, no wrap-around). Turning a cell that is already land into land changes nothing (its count is still reported). Return the list of counts, one per step.

If rows or cols is less than 1, or any cell is outside the map, raise `ValueError` (before doing anything else). rows * cols can be up to 1,000,000 and there can be up to 200,000 steps, so use a disjoint-set (union-find) structure or something equally fast.
"""

GOOD = r'''
def island_counts(rows, cols, cells):
    if rows < 1 or cols < 1:
        raise ValueError("bad size")
    for r, c in cells:
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError("cell outside the map")
    parent = {}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    count = 0
    out = []
    for r, c in cells:
        k = r * cols + c
        if k not in parent:
            parent[k] = k
            count += 1
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    nk = nr * cols + nc
                    if nk in parent:
                        a, b = find(k), find(nk)
                        if a != b:
                            parent[a] = b
                            count -= 1
        out.append(count)
    return out
'''

BAD = r'''
def island_counts(rows, cols, cells):
    if rows < 1 or cols < 1:
        raise ValueError("bad size")
    parent = {}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    count = 0
    out = []
    for r, c in cells:
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError("cell outside the map")
        k = r * cols + c
        parent[k] = k
        count += 1
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nk = (r + dr) * cols + (c + dc)
            if nk in parent:
                a, b = find(k), find(nk)
                if a != b:
                    parent[a] = b
                    count -= 1
        out.append(count)
    return out
'''

# ==== HIDDEN TESTS ====
def _ref(rows, cols, cells):
    land, out = set(), []
    for cell in cells:
        land.add(tuple(cell))
        seen, n = set(), 0
        for s in land:
            if s in seen:
                continue
            n += 1
            stack = [s]
            seen.add(s)
            while stack:
                r, c = stack.pop()
                for nb in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    if nb in land and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        out.append(n)
    return out


def test_example(sol):
    assert sol.island_counts(3, 3, [(0, 0), (0, 1), (1, 2), (2, 1), (1, 1)]) == [1, 1, 2, 3, 1]


def test_duplicates(sol):
    assert sol.island_counts(2, 2, [(0, 0), (0, 0), (1, 1), (1, 1)]) == [1, 1, 2, 2]


def test_no_wrap(sol):
    assert sol.island_counts(2, 3, [(0, 2), (1, 0)]) == [1, 2]
    assert sol.island_counts(1, 5, [(0, 4), (0, 0), (0, 2), (0, 1), (0, 3)]) == [1, 2, 3, 2, 1]


def test_errors_before_work(sol):
    for args in ((0, 3, []), (3, 0, []), (2, 2, [(0, 0), (2, 0)]), (2, 2, [(0, -1)])):
        try:
            sol.island_counts(*args)
        except ValueError:
            continue
        raise AssertionError(args)


def test_random_against_reference(sol):
    import random
    rng = random.Random(25)
    for _ in range(120):
        rows, cols = rng.randint(1, 7), rng.randint(1, 7)
        cells = [(rng.randrange(rows), rng.randrange(cols)) for _ in range(rng.randint(0, 30))]
        assert sol.island_counts(rows, cols, cells) == _ref(rows, cols, cells), (rows, cols, cells)


def test_large(sol):
    import random
    import time
    rng = random.Random(26)
    n = 1000
    cells = [(rng.randrange(n), rng.randrange(n)) for _ in range(200000)]
    t = time.time()
    out = sol.island_counts(n, n, cells)
    assert time.time() - t < 8
    assert len(out) == 200000 and out[0] == 1
    snake = [(0, c) for c in range(n)] + [(r, n - 1) for r in range(1, n)]
    t = time.time()
    out = sol.island_counts(n, n, snake[::-1] + snake)
    assert out[-1] == 1 and max(out) == 1 and time.time() - t < 8
