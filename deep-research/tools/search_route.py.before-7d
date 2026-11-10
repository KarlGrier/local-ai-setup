"""search_route.py - query-type routing for LDR's searches (phase 4 item 7, staged 10-29; not installed).

A rule-based classifier (no model) tags each search query academic / product / news / code / general, and a routing
table (paid-route.json next to this file, or PAID_ROUTE_CONFIG) says which sources each tag gets beside SearXNG:

* "free":  free sources asked on every search of the tag ("s2" = Semantic Scholar, s2_search.py).
* "paid":  paid providers asked on every search of the tag, in order, until one returns results ("exa", "tavily").
* "fallback" + "fallback_below": paid providers asked in order (skipping those already asked) only when SearXNG + the
  sources above brought fewer than fallback_below results - today's fallback (patch 0005: Exa then Tavily, < 5).

Profiles hold whole tables: "fallback" is today's behaviour (every tag: fallback Exa -> Tavily below 5 results) and is
used whenever routing is off, which is the default; "types" is the query-type table; "7a"/"7b"/"7c" are item 7's
one-source parts (Semantic Scholar / Tavily / Exa Lite on every search). Which profile: PAID_ROUTE_PROFILE, else (LDR
only) "route" in the run file paid_budget reads (~/ai/deep-research/run/paid-run.json), else the config's "profile" when
its "enabled" is true, else "fallback". Paid providers always go through paid_budget's caps (exa_fallback /
tavily_fallback); this module only decides. Standard library only.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path

TAGS = ("academic", "product", "news", "code", "general")
PRIORITY = ("academic", "code", "product", "news")      # a tie goes to the earlier tag
THRESHOLD = 2.0                                          # a tag needs this score, else "general"
FREE_SOURCES = ("s2",)
PAID_SOURCES = ("exa", "tavily")
CONFIG_FILE = Path(os.environ.get("PAID_ROUTE_CONFIG", str(Path(__file__).resolve().parent / "paid-route.json")))

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def _rx(p: str, flags: int = re.I) -> re.Pattern:
    return re.compile(p, flags)


# (tag, weight, label, pattern[, most]) - a rule scores weight x its distinct matches, at most `most` of them
# (default 1); the label is what the log shows as the reason
RULES: list[tuple] = [
    # academic / paper
    ("academic", 3, "academic site", _rx(r"\bsite:\S*(?:arxiv\.org|doi\.org|pubmed|ncbi\.nlm\.nih\.gov|scholar\.google|"
                                         r"semanticscholar\.org|researchgate\.net|acm\.org|ieee\.org|springer|"
                                         r"sciencedirect|nature\.com|biorxiv|medrxiv)")),
    ("academic", 2, "doi", _rx(r"\b10\.\d{4,9}/\S+")),
    ("academic", 2, "arxiv id", _rx(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")),
    ("academic", 2, "paper words", _rx(r"\b(?:arxiv|doi|pubmed|pmid|semantic scholar|google scholar|jstor|ssrn|"
                                       r"biorxiv|medrxiv|papers?|preprints?|journals?|peer[- ]reviewed|"
                                       r"meta[- ]analys[ie]s|systematic reviews?|literature reviews?|clinical trials?|"
                                       r"randomi[sz]ed controlled|rcts?|cohort stud(?:y|ies)|case[- ]control|"
                                       r"citations?|cited by|et al\b\.?|proceedings|thesis|dissertation)"), 2),
    ("academic", 2, "venue", _rx(r"\b(?:neurips|icml|iclr|emnlp|naacl|cvpr|iccv|eccv|aaai|ijcai|sigir|lancet|nejm|"
                                 r"jama|bmj)\b")),
    ("academic", 1, "study words", _rx(r"\b(?:study|studies|researchers|empirical|hypothesis|theorem|dataset|"
                                       r"survey of|evidence for|evidence on)\b")),
    # product / price / shopping
    ("product", 3, "shop site", _rx(r"\bsite:\S*(?:amazon\.|ebay\.|bestbuy\.|newegg\.|geizhals\.|idealo\.|walmart\.|"
                                    r"aliexpress\.|mindfactory\.|alternate\.)")),
    ("product", 2, "price words", _rx(r"\b(?:price|prices|pricing|priced|cheap(?:est|er)?|buy|buying|purchase|"
                                      r"discount|coupon|for sale|in stock|out of stock|msrp|retailers?|where to buy|"
                                      r"shopping|price per)\b"), 2),
    ("product", 2, "currency", _rx(r"[$€£¥]\s?\d|\b\d+(?:[.,]\d+)?\s?(?:usd|eur|gbp|dollars|euros)\b")),
    ("product", 2, "best under", _rx(r"\b(?:best|top)\s+(?:\S+\s+){0,3}?(?:under|below|for less than)\b")),
    ("product", 2, "how much cost", _rx(r"\bhow much (?:does|do|is|are|would)\b.*\bcost\b")),
    ("product", 1, "product words", _rx(r"\b(?:cost|costs|deal|deals|sale|shop|(?<!systematic )(?<!literature )reviews?|"
                                        r"specs|specifications|warranty|refurbished|model number)\b"), 2),
    # news / recent
    ("news", 3, "news site", _rx(r"\bsite:\S*(?:reuters\.|apnews\.|bbc\.|theguardian\.|nytimes\.|cnn\.|"
                                 r"tagesschau\.|spiegel\.|news\.)")),
    ("news", 2, "news words", _rx(r"\b(?:news|headlines?|breaking|today|tonight|yesterday|this (?:week|month|morning)|"
                                  r"last (?:night|week)|just (?:announced|released)|announced|announces|announcement|"
                                  r"press release|election|ceasefire|lawsuit filed|stock market)\b"), 2),
    ("news", 1, "recent words", _rx(r"\b(?:latest|recent|recently|current|currently|update on|developments?|"
                                    r"this year)\b")),
    # code / repository
    ("code", 3, "code site", _rx(r"\bsite:\S*(?:github\.com|gitlab\.|stackoverflow\.com|stackexchange\.com|"
                                 r"readthedocs|pypi\.org|npmjs\.com|crates\.io|docs\.python\.org)")),
    ("code", 2, "repo words", _rx(r"\b(?:github|gitlab|bitbucket|repo|repository|pull request|merge request|"
                                  r"stack ?overflow|pypi|npm|crates\.io|pip install|conda install|apt install|"
                                  r"traceback|segfault|segmentation fault|stack trace|core dump|cmake|makefile|"
                                  r"dockerfile|compile error|compiler error|linker error|syntax error)\b"), 2),
    ("code", 2, "file name", _rx(r"\b[\w-]+\.(?:py|js|ts|tsx|rs|cpp|hpp|cc|go|java|rb|sh|toml|ya?ml|ipynb|cu)\b")),
    ("code", 2, "error class", _rx(r"\b[A-Z]\w*(?:Error|Exception)\b", 0)),
    ("code", 1, "code token", _rx(r"\w\(\)|::|\b[a-z]+_[a-z0-9_]+\b|--[a-z][\w-]+|\b0x[0-9a-f]{4,}\b")),
    ("code", 1, "language", _rx(r"(?:\b(?:python|javascript|typescript|golang|kotlin|c\+\+|c#|php|bash|powershell|"
                                r"sql|haskell|scala|lua|perl|cuda|pytorch|tensorflow|numpy|pandas|react|django|"
                                r"flask|node\.?js|llama\.cpp|vllm|linux kernel)(?![\w+#]))")),
    ("code", 0.5, "language?", _rx(r"\b(?:rust|swift|java|ruby|go|julia)\b")),
    ("code", 1, "code words", _rx(r"\b(?:api|sdk|cli|library|package|module|function|method|bug|regex|compile|"
                                  r"install|installation|error|version|changelog|release notes|how to|how do i|"
                                  r"example code|tutorial|documentation|docs)\b")),
]


def normalise(query: str) -> str:
    """NFKC, case-folded, whitespace collapsed, trailing ?!. dropped (quotes and operators kept)."""
    q = unicodedata.normalize("NFKC", query or "").casefold()
    return re.sub(r"\s+", " ", q).strip().rstrip("?!. ").strip()


def classify(query: str, now_year: int | None = None) -> tuple[str, str]:
    """(tag, reason). The reason names the winning tag's score and the rules that matched, plus any runner-up."""
    q = unicodedata.normalize("NFKC", query or "")
    scores = {t: 0.0 for t in PRIORITY}
    hits: dict[str, list[str]] = {t: [] for t in PRIORITY}
    for tag, w, label, rx, *most in RULES:
        n = min(len({m.group(0).casefold() for m in rx.finditer(q)}), most[0] if most else 1)
        if n:
            scores[tag] += w * n
            hits[tag].append(label if n == 1 else f"{label} x{n}")
    y = now_year or time.gmtime().tm_year
    if re.search(rf"\b(?:{_MONTHS})\s+(?:{y}|{y - 1})\b", q, re.I):
        scores["news"] += 2
        hits["news"].append("month and year")
    elif re.search(rf"\b{y}\b", q):
        scores["news"] += 1
        hits["news"].append("this year")
    best = max(PRIORITY, key=lambda t: (scores[t], -PRIORITY.index(t)))
    others = "; ".join(f"{t} {scores[t]:g}" for t in PRIORITY if t != best and scores[t] > 0)
    if scores[best] < THRESHOLD:
        low = "; ".join(f"{t} {scores[t]:g}: {', '.join(hits[t])}" for t in PRIORITY if scores[t] > 0)
        return "general", f"no tag reached {THRESHOLD:g}" + (f" ({low})" if low else "")
    return best, f"{best} {scores[best]:g}: {', '.join(hits[best])}" + (f" (also {others})" if others else "")


# ---- the routing table ---------------------------------------------------------------------------------------------

_RULE_FALLBACK = {"free": [], "paid": [], "fallback": ["exa", "tavily"], "fallback_below": 5}
DEFAULT_CONFIG = {                      # what applies when the config file is missing or broken: routing and cache off
    "enabled": False,
    "profile": "types",
    "cache": {"enabled": False, "dir": "~/.cache/deep-research/paid-search", "max_mb": 64, "empty_ttl_hours": 24},
    "ttl_hours": {"news": 6, "product": 24, "code": 168, "general": 168, "academic": 720},
    "profiles": {"fallback": {"*": _RULE_FALLBACK}},
}


def _check_rule(r) -> dict:
    if not isinstance(r, dict):
        raise ValueError("a rule must be an object")
    out = {"free": list(r.get("free") or []), "paid": list(r.get("paid") or []),
           "fallback": list(r.get("fallback") or []), "fallback_below": int(r.get("fallback_below") or 0)}
    for s in out["free"]:
        if s not in FREE_SOURCES:
            raise ValueError(f"unknown free source {s!r}")
    for s in out["paid"] + out["fallback"]:
        if s not in PAID_SOURCES:
            raise ValueError(f"unknown paid source {s!r}")
    return out


def load_config(path: Path | None = None) -> tuple[dict, str]:
    """(config, error). A missing or broken file gives DEFAULT_CONFIG (routing and cache off) and the error."""
    p = Path(path or CONFIG_FILE)
    try:
        raw = json.loads(p.read_text())
        if not isinstance(raw, dict):
            raise ValueError("not an object")
        cfg = {"enabled": bool(raw.get("enabled", False)), "profile": str(raw.get("profile") or "types"),
               "cache": {**DEFAULT_CONFIG["cache"], **(raw.get("cache") or {})},
               "ttl_hours": {**DEFAULT_CONFIG["ttl_hours"], **(raw.get("ttl_hours") or {})},
               "profiles": {"fallback": {"*": dict(_RULE_FALLBACK)}}}
        for name, prof in (raw.get("profiles") or {}).items():
            if not isinstance(prof, dict):
                raise ValueError(f"profile {name!r} must be an object")
            cfg["profiles"][name] = {tag: _check_rule(r) for tag, r in prof.items() if not tag.startswith("_")}
            for tag in cfg["profiles"][name]:
                if tag != "*" and tag not in TAGS:
                    raise ValueError(f"profile {name!r}: unknown tag {tag!r}")
        return cfg, ""
    except FileNotFoundError:
        return json.loads(json.dumps(DEFAULT_CONFIG)), f"no config file {p}"
    except (OSError, ValueError, TypeError) as e:
        return json.loads(json.dumps(DEFAULT_CONFIG)), f"config {p}: {e}"


def pick_profile(cfg: dict, run_now: dict | None = None) -> tuple[str, str]:
    """(profile name, where it came from). An unknown name falls back to "fallback" (today's behaviour)."""
    env = os.environ.get("PAID_ROUTE_PROFILE", "").strip()
    if env:
        name, src = env, "PAID_ROUTE_PROFILE"
    elif run_now and str(run_now.get("route") or "").strip():
        name, src = str(run_now["route"]).strip(), "run file"
    elif cfg.get("enabled"):
        name, src = cfg.get("profile") or "fallback", "config"
    else:
        name, src = "fallback", "routing off"
    if name not in cfg["profiles"]:
        return "fallback", f"{src}: unknown profile {name!r}, today's fallback"
    return name, src


def rule_for(cfg: dict, profile: str, tag: str) -> dict:
    prof = cfg["profiles"].get(profile) or cfg["profiles"]["fallback"]
    return dict(prof.get(tag) or prof.get("*") or prof.get("general") or _RULE_FALLBACK)


def decide(query: str, cfg: dict, profile: str, now_year: int | None = None) -> dict:
    """The routing decision for one query (pure; the caller asks the sources and logs)."""
    tag, why = classify(query, now_year)
    r = rule_for(cfg, profile, tag)
    return {"tag": tag, "why": why, "profile": profile, **r}


def ttl_seconds(cfg: dict, tag: str, empty: bool = False) -> int:
    h = float(cfg["ttl_hours"].get(tag, cfg["ttl_hours"].get("general", 168)))
    if empty:
        h = min(h, float(cfg["cache"].get("empty_ttl_hours", 24)))
    return int(h * 3600)
