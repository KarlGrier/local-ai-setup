"""Item 7 cache (10-29): hit / miss / expiry / size cap (LRU) / no keys or headers stored - temp folder only."""
import json
import os
import sys
import time

sys.path.insert(0, "/home/USER/ai/deep-research/staging/item7/tests")
from _offline import FAKE_KEY, TMP, finish  # noqa: E402

from paid_cache import PaidCache  # noqa: E402

folder = TMP / "cache-unit"
c = PaidCache(folder, max_bytes=8_000)
P = {"type": "lite", "num": 10, "contents": "highlights"}
R = [{"title": "t", "url": "https://a.example/1", "content": "c", "score": 0.5, "published_date": None}]
T0 = 1_800_000_000.0

# a lookup never creates the folder
assert c.lookup("exa", "q", P) == (None, "miss") and not folder.exists()
# store + hit; the normalised query hits; other parameters or provider miss
assert c.store("exa", "RTX 5090 price", P, R, ttl_s=3600, tag="product", now=T0)
assert folder.is_dir() and (folder.stat().st_mode & 0o777) == 0o700
assert c.lookup("exa", "RTX 5090 price", P, now=T0 + 10) == (R, "hit")
assert c.lookup("exa", "  rtx   5090 PRICE? ", P, now=T0 + 10)[1] == "hit"
assert c.lookup("exa", "RTX 5090 price", {**P, "num": 5}, now=T0 + 10)[1] == "miss"
assert c.lookup("tavily", "RTX 5090 price", P, now=T0 + 10)[1] == "miss"
# an empty answer is a valid entry (it cost a search)
assert c.store("exa", "nothing here", P, [], ttl_s=60, now=T0)
assert c.lookup("exa", "nothing here", P, now=T0 + 1) == ([], "hit")
# expiry: the entry goes, the next lookup is a miss
assert c.lookup("exa", "RTX 5090 price", P, now=T0 + 3601) == (None, "expired")
assert c.lookup("exa", "RTX 5090 price", P, now=T0 + 3602) == (None, "miss")
# a corrupt or foreign file is a miss
k = PaidCache.key("exa", "broken", P)
(folder / f"exa-{k[:40]}.json").write_text("{not json")
assert c.lookup("exa", "broken", P)[1] == "miss"
(folder / f"exa-{k[:40]}.json").write_text(json.dumps({"key": "other", "results": [], "expires": 9e18}))
assert c.lookup("exa", "broken", P)[1] == "miss"

# only the result fields are stored - never a key, header or caller
leaky = [{"title": "t", "url": "https://b.example", "content": "c", "headers": {"x-api-key": FAKE_KEY},
          "Authorization": f"Bearer {FAKE_KEY}", "client": "jan"}]
assert c.store("tavily", "leak test", {"depth": "basic"}, leaky, ttl_s=60, now=T0)
blob = "".join(p.read_text() for p in folder.glob("*.json"))
assert FAKE_KEY not in blob and "Authorization" not in blob and "x-api-key" not in blob and '"client"' not in blob

# size cap: expired entries go first, then the least recently used, down to 90 % of the cap
for p in folder.glob("*.json"):
    p.unlink()
big = [{"title": "x" * 200, "url": "https://c.example/0", "content": "y" * 600}]
now = time.time()
fill = PaidCache(folder, max_bytes=1 << 20)            # fill without a cap first, mtimes in store order
paths = []
for i in range(8):
    assert fill.store("exa", f"query {i}", P, big, ttl_s=10_000 if i != 3 else 5, now=now)
    p = folder / f"exa-{PaidCache.key('exa', f'query {i}', P)[:40]}.json"
    os.utime(p, (now - 1000 + i, now - 1000 + i))
    paths.append(p)
size = paths[0].stat().st_size
c = PaidCache(folder, max_bytes=int(size * 8.5))      # 8 entries fit, a 9th goes over
assert c.lookup("exa", "query 0", P, now=now)[1] == "hit"   # query 0 becomes the most recently used
assert c.store("exa", "query 8", P, big, ttl_s=10_000, now=now + 10)
st = c.stats()
assert st["bytes"] <= c.max_bytes * 0.9, st
assert paths[0].exists(), "a recently used entry was evicted"
assert not paths[3].exists(), "the expired entry should go first"
assert not paths[1].exists(), "the least recently used entry should go"
assert c.lookup("exa", "query 8", P, now=now + 11)[1] == "hit" and paths[2].exists()
# nothing left behind but entries and the lock file
assert all(p.suffix == ".json" or p.name == ".lock" for p in folder.iterdir()), list(folder.iterdir())

finish("ok: cache miss/hit/normalised hit/params+provider in key/empty answer/expiry/corrupt file/no keys or headers/"
       "size cap (expired first, then LRU)")
