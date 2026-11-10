LEVEL = "medium"
KIND = "data structures"
ENTRY = "LRUCache"
PROMPT = """Write a Python class `LRUCache` (a least-recently-used cache) with:

- `LRUCache(capacity: int)`: capacity must be at least 1, else raise `ValueError`.
- `get(key, default=None)`: return the value for `key` and mark the key as most recently used; if the key is absent return `default` (and change nothing).
- `put(key, value)`: insert or update; the key becomes the most recently used. If inserting a new key makes the cache hold more than `capacity` keys, evict the least recently used key.
- `__len__()`: the number of keys held.
- `keys()`: a list of the keys from most recently used to least recently used.
- `__contains__(key)`: whether the key is held; this check does NOT change the order.
All operations except `keys()` must be O(1) on average.
"""

GOOD = r'''
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._d = OrderedDict()

    def get(self, key, default=None):
        if key not in self._d:
            return default
        self._d.move_to_end(key)
        return self._d[key]

    def put(self, key, value):
        if key in self._d:
            self._d.move_to_end(key)
        self._d[key] = value
        if len(self._d) > self.capacity:
            self._d.popitem(last=False)

    def __len__(self):
        return len(self._d)

    def __contains__(self, key):
        return key in self._d

    def keys(self):
        return list(reversed(self._d.keys()))
'''

BAD = r'''
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._d = OrderedDict()

    def get(self, key, default=None):
        return self._d.get(key, default)

    def put(self, key, value):
        if key in self._d:
            self._d.move_to_end(key)
        self._d[key] = value
        if len(self._d) > self.capacity:
            self._d.popitem(last=False)

    def __len__(self):
        return len(self._d)

    def __contains__(self, key):
        return key in self._d

    def keys(self):
        return list(reversed(self._d.keys()))
'''

# ==== HIDDEN TESTS ====
def test_basic(sol):
    c = sol.LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    c.put("c", 3)
    assert "b" not in c and c.get("b") is None
    assert c.get("a") == 1 and c.get("c") == 3
    assert len(c) == 2


def test_default(sol):
    c = sol.LRUCache(1)
    assert c.get("x", 42) == 42
    c.put("x", 0)
    assert c.get("x", 42) == 0


def test_update_refreshes(sol):
    c = sol.LRUCache(2)
    c.put(1, "a")
    c.put(2, "b")
    c.put(1, "A")
    c.put(3, "c")
    assert c.keys() == [3, 1]
    assert c.get(1) == "A"


def test_contains_does_not_refresh(sol):
    c = sol.LRUCache(2)
    c.put(1, 1)
    c.put(2, 2)
    assert 1 in c
    c.put(3, 3)
    assert 1 not in c and c.keys() == [3, 2]


def test_keys_order(sol):
    c = sol.LRUCache(3)
    for k in "abc":
        c.put(k, k)
    c.get("a")
    assert c.keys() == ["a", "c", "b"]


def test_capacity(sol):
    for bad in (0, -1):
        try:
            sol.LRUCache(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_against_model(sol):
    import random
    rng = random.Random(5)
    c = sol.LRUCache(5)
    model = []
    for _ in range(5000):
        k = rng.randint(0, 9)
        if rng.random() < 0.5:
            c.put(k, k * 10)
            if k in model:
                model.remove(k)
            model.insert(0, k)
            del model[5:]
        else:
            got = c.get(k, -1)
            if k in model:
                assert got == k * 10
                model.remove(k)
                model.insert(0, k)
            else:
                assert got == -1
        assert c.keys() == model


def test_speed(sol):
    import time
    c = sol.LRUCache(50000)
    t = time.time()
    for i in range(200000):
        c.put(i, i)
        c.get(i - 10)
    assert time.time() - t < 5
