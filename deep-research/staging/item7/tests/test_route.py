"""Item 7 routing (10-29): the rule-based classifier on example queries, the routing table and the profile choice."""
import json
import os
import sys

sys.path.insert(0, "/home/USER/ai/deep-research/staging/item7/tests")
from _offline import TMP, TOOLS, finish  # noqa: E402

import search_route as sr  # noqa: E402

EXAMPLES = [
    # academic / paper
    ("meta-analysis of intermittent fasting and weight loss", "academic"),
    ("arxiv 2410.12345 speculative decoding", "academic"),
    ("doi 10.1038/s41586-024-07421-0", "academic"),
    ("randomized controlled trial vitamin D depression", "academic"),
    ("Smith et al. 2023 transformer scaling laws paper", "academic"),
    ("site:arxiv.org mixture of experts routing", "academic"),
    ("systematic review of product pricing strategies", "academic"),       # tie with product -> academic
    ("NeurIPS 2025 best paper on KV cache compression", "academic"),
    # product / price / shopping
    ("RTX 5090 price in Germany", "product"),
    ("cheapest 4TB NVMe SSD", "product"),
    ("best mechanical keyboard under $100", "product"),
    ("where to buy DDR5-6000 96GB kit", "product"),
    ("site:amazon.de noise cancelling headphones", "product"),
    ("Sony WH-1000XM6 review and specs", "product"),
    ("how much does a heat pump cost to install", "product"),
    # news / recent
    ("latest news on the EU AI Act", "news"),
    ("what happened today in the stock market", "news"),
    ("Nvidia announced Rubin GPU", "news"),
    ("election results October 2026", "news"),
    ("Nvidia RTX 5090 price announced today", "news"),                      # news 4 beats product 2
    ("site:reuters.com chip export rules", "news"),
    # code / repository
    ("github llama.cpp flash attention pull request", "code"),
    ("ModuleNotFoundError: No module named torch", "code"),
    ("how to read a csv file in python", "code"),
    ("pip install fails with cmake error", "code"),
    ("site:stackoverflow.com segfault in cuda kernel", "code"),
    ("latest version of numpy", "code"),
    ("torch.compile mode max-autotune --dynamic flag", "code"),
    ("config.yaml schema for searxng engines", "code"),
    # general
    ("history of the Roman empire", "general"),
    ("how to cook basmati rice", "general"),
    ("how do I install a dishwasher", "general"),
    ("effects of caffeine on sleep", "general"),
    ("how to remove rust from a bike chain", "general"),
    ("cost of living in Berlin", "general"),
    ("Paris weather in spring", "general"),
    ("", "general"),
]

bad = []
for q, want in EXAMPLES:
    got, why = sr.classify(q, now_year=2026)
    if got != want:
        bad.append(f"{q!r}: {got} ({why}), want {want}")
assert not bad, "\n".join(bad)
tag, why = sr.classify("meta-analysis 10.1038/abc", now_year=2026)
assert tag == "academic" and "paper words" in why and "doi" in why, why

assert sr.normalise("  Foo   BAR?? ") == "foo bar" and sr.normalise("Ｆｏｏ\tbar.") == "foo bar"
assert sr.normalise('"exact phrase" site:x.org') == '"exact phrase" site:x.org'

# the staged table loads; every profile and tag is valid
cfg, err = sr.load_config(os.path.join(TOOLS, "paid-route.json"))
assert not err, err
assert cfg["enabled"] is False and cfg["cache"]["enabled"] is False
assert set(cfg["profiles"]) == {"fallback", "types", "7a", "7b", "7c"}, cfg["profiles"].keys()
# a missing or broken table: routing and cache off, the error reported
for content in (None, "{not json", json.dumps({"profiles": {"x": {"general": {"paid": ["google"]}}}}),
                json.dumps({"profiles": {"x": {"weather": {}}}})):
    p = TMP / "bad-route.json"
    if content is None:
        p.unlink(missing_ok=True)
    else:
        p.write_text(content)
    c, e = sr.load_config(p)
    assert e and c["enabled"] is False and c["cache"]["enabled"] is False and set(c["profiles"]) == {"fallback"}, (content, e)

# which profile: PAID_ROUTE_PROFILE > the run file's "route" (LDR) > the config when enabled > today's fallback
assert sr.pick_profile(cfg, {}) == ("fallback", "routing off")
assert sr.pick_profile({**cfg, "enabled": True}, {}) == ("types", "config")
assert sr.pick_profile(cfg, {"route": "7b"}) == ("7b", "run file")
os.environ["PAID_ROUTE_PROFILE"] = "7c"
assert sr.pick_profile(cfg, {"route": "7b"}) == ("7c", "PAID_ROUTE_PROFILE")
os.environ["PAID_ROUTE_PROFILE"] = "nonsense"
name, src = sr.pick_profile(cfg, {})
assert name == "fallback" and "unknown profile" in src, (name, src)
del os.environ["PAID_ROUTE_PROFILE"]

# decisions
d = sr.decide("RTX 5090 price", cfg, "types", 2026)
assert (d["tag"], d["free"], d["paid"], d["fallback"]) == ("product", [], ["exa"], ["tavily"]), d
d = sr.decide("breaking news chip tariffs", cfg, "types", 2026)
assert (d["tag"], d["paid"], d["fallback"]) == ("news", ["tavily"], ["exa"]), d
d = sr.decide("meta-analysis of creatine", cfg, "types", 2026)
assert (d["tag"], d["free"], d["paid"]) == ("academic", ["s2"], []), d
d = sr.decide("history of Rome", cfg, "types", 2026)
assert (d["tag"], d["paid"], d["fallback"], d["fallback_below"]) == ("general", [], ["exa", "tavily"], 5), d
for q in ("RTX 5090 price", "history of Rome", "meta-analysis of creatine"):
    d = sr.decide(q, cfg, "fallback", 2026)                       # routing off: every tag = today's fallback
    assert (d["free"], d["paid"], d["fallback"], d["fallback_below"]) == ([], [], ["exa", "tavily"], 5), d
    assert sr.decide(q, cfg, "7b", 2026)["paid"] == ["tavily"] and sr.decide(q, cfg, "7c", 2026)["paid"] == ["exa"]
    assert sr.decide(q, cfg, "7a", 2026)["free"] == ["s2"]

assert sr.ttl_seconds(cfg, "news") == 6 * 3600 and sr.ttl_seconds(cfg, "academic") == 720 * 3600
assert sr.ttl_seconds(cfg, "academic", empty=True) == 24 * 3600 and sr.ttl_seconds(cfg, "news", empty=True) == 6 * 3600

finish(f"ok: classifier {len(EXAMPLES)} examples, normalise, table load + broken tables, profile choice, decisions, TTLs")
