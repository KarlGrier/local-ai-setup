LEVEL = "hard"
KIND = "bug fix"
ENTRY = "LFUCache"
PROMPT = '''This least-frequently-used cache has bugs. Intended behaviour:

- `LFUCache(capacity)`: capacity >= 1, else `ValueError`.
- `get(key)` returns the value (or None when absent) and counts as one use of the key.
- `put(key, value)` on an existing key updates the value and counts as one use. On a new key: if the cache is full, first evict the key with the fewest uses; among keys with equally few uses evict the one whose last use (get or put) is the oldest. The new key starts with 1 use.
- `__len__` returns the number of keys. All operations O(1) on average.

Fix every bug and return the whole corrected class.

```python
from collections import defaultdict, OrderedDict


class LFUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self.vals = {}
        self.freq = {}
        self.groups = defaultdict(OrderedDict)
        self.min_freq = 0

    def _touch(self, key):
        f = self.freq[key]
        del self.groups[f][key]
        if not self.groups[f] and self.min_freq == f:
            self.min_freq = f + 1
        self.freq[key] = f + 1
        self.groups[f + 1][key] = None

    def get(self, key):
        if key not in self.vals:
            return None
        self._touch(key)
        return self.vals[key]

    def put(self, key, value):
        if key in self.vals:
            self.vals[key] = value
            return
        if len(self.vals) >= self.capacity:
            old, _ = self.groups[self.min_freq].popitem()
            del self.vals[old]
            del self.freq[old]
        self.vals[key] = value
        self.freq[key] = 1
        self.groups[1][key] = None

    def __len__(self):
        return len(self.vals)
```
'''

GOOD = r'''
from collections import defaultdict, OrderedDict


class LFUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self.vals = {}
        self.freq = {}
        self.groups = defaultdict(OrderedDict)
        self.min_freq = 0

    def _touch(self, key):
        f = self.freq[key]
        del self.groups[f][key]
        if not self.groups[f]:
            del self.groups[f]
            if self.min_freq == f:
                self.min_freq = f + 1
        self.freq[key] = f + 1
        self.groups[f + 1][key] = None

    def get(self, key):
        if key not in self.vals:
            return None
        self._touch(key)
        return self.vals[key]

    def put(self, key, value):
        if key in self.vals:
            self.vals[key] = value
            self._touch(key)
            return
        if len(self.vals) >= self.capacity:
            old, _ = self.groups[self.min_freq].popitem(last=False)
            if not self.groups[self.min_freq]:
                del self.groups[self.min_freq]
            del self.vals[old]
            del self.freq[old]
        self.vals[key] = value
        self.freq[key] = 1
        self.groups[1][key] = None
        self.min_freq = 1

    def __len__(self):
        return len(self.vals)
'''

BAD = r'''
from collections import defaultdict, OrderedDict


class LFUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self.vals = {}
        self.freq = {}
        self.groups = defaultdict(OrderedDict)
        self.min_freq = 0

    def _touch(self, key):
        f = self.freq[key]
        del self.groups[f][key]
        if not self.groups[f] and self.min_freq == f:
            self.min_freq = f + 1
        self.freq[key] = f + 1
        self.groups[f + 1][key] = None

    def get(self, key):
        if key not in self.vals:
            return None
        self._touch(key)
        return self.vals[key]

    def put(self, key, value):
        if key in self.vals:
            self.vals[key] = value
            self._touch(key)
            return
        if len(self.vals) >= self.capacity:
            old, _ = self.groups[self.min_freq].popitem(last=False)
            del self.vals[old]
            del self.freq[old]
        self.vals[key] = value
        self.freq[key] = 1
        self.groups[1][key] = None

    def __len__(self):
        return len(self.vals)
'''

# ==== HIDDEN TESTS ====
class _Ref:
    def __init__(self, cap):
        self.cap, self.d, self.t = cap, {}, 0

    def _use(self, k):
        self.t += 1
        v, f, _ = self.d[k]
        self.d[k] = (v, f + 1, self.t)

    def get(self, k):
        if k not in self.d:
            return None
        self._use(k)
        return self.d[k][0]

    def put(self, k, v):
        if k in self.d:
            self.d[k] = (v,) + self.d[k][1:]
            self._use(k)
            return
        if len(self.d) >= self.cap:
            old = min(self.d, key=lambda x: (self.d[x][1], self.d[x][2]))
            del self.d[old]
        self.t += 1
        self.d[k] = (v, 1, self.t)


def test_basic(sol):
    c = sol.LFUCache(2)
    c.put(1, 1)
    c.put(2, 2)
    assert c.get(1) == 1
    c.put(3, 3)
    assert c.get(2) is None and c.get(3) == 3 and c.get(1) == 1


def test_tie_oldest_use(sol):
    c = sol.LFUCache(3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.put("d", 4)
    assert c.get("a") is None and c.get("b") == 2


def test_put_counts_as_use(sol):
    c = sol.LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    assert c.get("a") == 10 and c.get("b") is None


def test_min_freq_reset_after_new_key(sol):
    c = sol.LFUCache(2)
    c.put("a", 1)
    c.get("a")
    c.get("a")
    c.put("b", 2)
    c.get("b")
    c.put("c", 3)
    c.put("d", 4)
    assert c.get("a") == 1 and c.get("c") is None and c.get("d") == 4


def test_capacity_one(sol):
    c = sol.LFUCache(1)
    c.put(1, 1)
    c.get(1)
    c.put(2, 2)
    assert c.get(1) is None and c.get(2) == 2 and len(c) == 1
    try:
        sol.LFUCache(0)
    except ValueError:
        pass
    else:
        raise AssertionError("no ValueError")


def test_random_against_reference(sol):
    import random
    rng = random.Random(15)
    for cap in (1, 2, 3, 5, 8):
        c, r = sol.LFUCache(cap), _Ref(cap)
        for _ in range(4000):
            k = rng.randint(0, 12)
            if rng.random() < 0.5:
                v = rng.randint(0, 999)
                c.put(k, v)
                r.put(k, v)
            else:
                assert c.get(k) == r.get(k)
            assert len(c) == len(r.d)
