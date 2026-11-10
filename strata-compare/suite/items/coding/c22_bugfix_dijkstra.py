LEVEL = "hard"
KIND = "bug fix"
ENTRY = "shortest_paths"
PROMPT = '''`shortest_paths(graph, source)` should return a dict mapping every node reachable from `source` to its shortest distance, and must raise `ValueError` if any edge weight is negative. `graph` maps a node to a list of `(neighbour, weight)` pairs; nodes that appear only as neighbours have no outgoing edges; `source` may also be absent from `graph` (then only the source itself is reachable). Nodes can be any hashable values (not necessarily comparable with each other). Weights are ints or floats. It gives wrong distances on some graphs. Fix every bug, keep it O((V + E) log V), and return the whole corrected function.

```python
import heapq


def shortest_paths(graph, source):
    dist = {source: 0}
    done = set()
    heap = [(0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        for v, w in graph.get(u, []):
            if v in done:
                continue
            done.add(v)
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist
```
'''

GOOD = r'''
import heapq


def shortest_paths(graph, source):
    for u, edges in graph.items():
        for v, w in edges:
            if w < 0:
                raise ValueError("negative edge weight")
    dist = {source: 0}
    done = set()
    heap = [(0, 0, source)]
    tie = 1
    while heap:
        d, _, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        for v, w in graph.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, tie, v))
                tie += 1
    return dist
'''

BAD = r'''
import heapq


def shortest_paths(graph, source):
    for u, edges in graph.items():
        for v, w in edges:
            if w < 0:
                raise ValueError("negative edge weight")
    dist = {source: 0}
    done = set()
    heap = [(0, source)]
    while heap:
        d, u = heapq.heappop(heap)
        done.add(u)
        for v, w in graph.get(u, []):
            if v in done:
                continue
            nd = d + w
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist
'''

# ==== HIDDEN TESTS ====
def _bf(graph, src):
    nodes = set(graph) | {v for es in graph.values() for v, _ in es} | {src}
    INF = float("inf")
    dist = {n: INF for n in nodes}
    dist[src] = 0
    for _ in range(len(nodes)):
        for u, es in graph.items():
            if dist[u] == INF:
                continue
            for v, w in es:
                if dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
    return {n: d for n, d in dist.items() if d != INF}


def test_simple(sol):
    g = {"a": [("b", 1), ("c", 4)], "b": [("c", 2), ("d", 5)], "c": [("d", 1)]}
    assert sol.shortest_paths(g, "a") == {"a": 0, "b": 1, "c": 3, "d": 4}


def test_later_shorter_path(sol):
    g = {"s": [("x", 10), ("y", 1)], "y": [("z", 1)], "z": [("x", 1)]}
    assert sol.shortest_paths(g, "s") == {"s": 0, "x": 3, "y": 1, "z": 2}


def test_source_absent_and_unreachable(sol):
    assert sol.shortest_paths({}, "q") == {"q": 0}
    g = {"a": [("b", 2)], "c": [("a", 1)]}
    assert sol.shortest_paths(g, "a") == {"a": 0, "b": 2}


def test_negative_rejected(sol):
    try:
        sol.shortest_paths({"a": [("b", -1)]}, "a")
    except ValueError:
        return
    raise AssertionError("no ValueError")


def test_zero_and_float_weights(sol):
    g = {1: [(2, 0), (3, 0.5)], 2: [(3, 0.25)], 3: [(1, 0)]}
    assert sol.shortest_paths(g, 1) == {1: 0, 2: 0, 3: 0.25}


def test_unorderable_nodes(sol):
    a, b, c = object(), object(), object()
    g = {a: [(b, 1), (c, 1)], b: [(c, 1)]}
    assert sol.shortest_paths(g, a) == {a: 0, b: 1, c: 1}


def test_random(sol):
    import random
    rng = random.Random(14)
    for _ in range(200):
        n = rng.randint(1, 12)
        g = {}
        for u in range(n):
            g[u] = [(rng.randrange(n), rng.randint(0, 9)) for _ in range(rng.randint(0, 4))]
        src = rng.randrange(n)
        assert sol.shortest_paths(g, src) == _bf(g, src)


def test_large(sol):
    import random
    import time
    rng = random.Random(2)
    n = 60000
    g = {u: [(rng.randrange(n), rng.randint(1, 100)) for _ in range(4)] for u in range(n)}
    t = time.time()
    d = sol.shortest_paths(g, 0)
    assert time.time() - t < 6
    assert d[0] == 0 and len(d) > n // 2
    for u in rng.sample(sorted(d), 200):
        for v, w in g[u]:
            assert d[v] <= d[u] + w
