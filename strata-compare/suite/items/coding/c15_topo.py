LEVEL = "medium"
KIND = "algorithms"
ENTRY = "topo_order"
PROMPT = """Write a Python function `topo_order(deps: dict[str, list[str]]) -> list[str]`.

`deps` maps each task to the list of tasks it depends on (its prerequisites). Tasks that appear only as prerequisites are tasks too. Return an ordering of all tasks in which every task comes after all of its prerequisites. Among all valid orderings return the lexicographically smallest one (compare the lists element by element with normal string order). Duplicate entries in a prerequisite list count once; a task listing itself is a cycle. If the dependencies contain a cycle, raise `ValueError`. Up to 100,000 tasks: aim for O((V + E) log V).
"""

GOOD = r'''
import heapq


def topo_order(deps):
    nodes = set(deps)
    for pre in deps.values():
        nodes.update(pre)
    indeg = {n: 0 for n in nodes}
    out = {n: [] for n in nodes}
    for t, pre in deps.items():
        for p in set(pre):
            out[p].append(t)
            indeg[t] += 1
    heap = [n for n in nodes if indeg[n] == 0]
    heapq.heapify(heap)
    order = []
    while heap:
        n = heapq.heappop(heap)
        order.append(n)
        for m in out[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                heapq.heappush(heap, m)
    if len(order) != len(nodes):
        raise ValueError("cycle")
    return order
'''

BAD = r'''
def topo_order(deps):
    nodes = set(deps)
    for pre in deps.values():
        nodes.update(pre)
    state, order = {}, []

    def visit(n):
        if state.get(n) == 1:
            raise ValueError("cycle")
        if state.get(n) == 2:
            return
        state[n] = 1
        for p in sorted(set(deps.get(n, []))):
            visit(p)
        state[n] = 2
        order.append(n)

    for n in sorted(nodes):
        visit(n)
    return order
'''

# ==== HIDDEN TESTS ====
def _valid(deps, order):
    pos = {n: i for i, n in enumerate(order)}
    return all(pos[p] < pos[t] for t, pre in deps.items() for p in pre)


def test_simple(sol):
    deps = {"b": ["a"], "c": ["a"], "d": ["b", "c"]}
    assert sol.topo_order(deps) == ["a", "b", "c", "d"]


def test_lexicographic(sol):
    deps = {"a": ["z"], "b": [], "y": []}
    assert sol.topo_order(deps) == ["b", "y", "z", "a"]


def test_prereq_only_nodes(sol):
    assert sol.topo_order({"x": ["m", "n"]}) == ["m", "n", "x"]
    assert sol.topo_order({}) == []


def test_duplicates(sol):
    assert sol.topo_order({"b": ["a", "a", "a"]}) == ["a", "b"]


def test_cycles(sol):
    for deps in ({"a": ["b"], "b": ["a"]}, {"a": ["a"]}, {"a": ["b"], "b": ["c"], "c": ["a"], "d": []}):
        try:
            sol.topo_order(deps)
        except ValueError:
            continue
        raise AssertionError(deps)


def test_random_against_reference(sol):
    import heapq
    import random
    rng = random.Random(4)
    for _ in range(100):
        names = ["t%02d" % i for i in range(rng.randint(1, 25))]
        rng.shuffle(names)
        deps = {}
        for i, n in enumerate(names):
            k = rng.randint(0, min(3, i))
            deps[n] = rng.sample(names[:i], k)
        indeg = {n: len(set(deps[n])) for n in names}
        out = {n: [] for n in names}
        for t in names:
            for p in set(deps[t]):
                out[p].append(t)
        h = [n for n in names if indeg[n] == 0]
        heapq.heapify(h)
        exp = []
        while h:
            n = heapq.heappop(h)
            exp.append(n)
            for m in out[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    heapq.heappush(h, m)
        got = sol.topo_order(deps)
        assert got == exp and _valid(deps, got)


def test_large_chain(sol):
    n = 100000
    deps = {"n%06d" % i: ["n%06d" % (i - 1)] for i in range(1, n)}
    got = sol.topo_order(deps)
    assert got[0] == "n000000" and got[-1] == "n%06d" % (n - 1) and len(got) == n
