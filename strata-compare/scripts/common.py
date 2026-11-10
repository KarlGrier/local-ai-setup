"""Shared helpers for the strata-compare harness: tokenizer, corpus, paths, JSONL output."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
STRATA = WS / "strata"
CORPUS = Path("/home/USER/ai-speed-testing/signal-3.8-opus/corpus/mixed.txt")   # read-only input
S3_PROMPTS = Path("/home/USER/ai-speed-testing/signal-3.8-opus/bench/prompts.json")  # read-only input
EVAL_DIR = Path("/home/USER/ai-speed-testing/eval_prompts")                       # read-only input
PROMPTS = WS / "prompts"
RESULTS = WS / "results"

sys.path.insert(0, str(STRATA / "tools"))


def load_tokenizer(tdir: str | Path = WS / "work/tok-signal/tokenizer"):
    """Strata's reference BPE tokenizer over a tokenizer/ dir exported from a GGUF (identical to llama.cpp's
    tokenization on the 606,046-token corpus)."""
    import strata_tokenizer as ST
    tdir = Path(tdir)
    vocab = json.loads((tdir / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    merges = (tdir / "merges.txt").read_text(encoding="utf-8").split("\n")
    types = json.loads((tdir / "token_type.json").read_text())
    return ST.Tokenizer(toks, merges, types)


def load_template(path: str | Path = WS / "work/tok-signal/tokenizer/chat_template.jinja"):
    sys.path.insert(0, str(STRATA))
    from serve.frontend import ChatTemplate
    return ChatTemplate(path)


def append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def meminfo() -> dict:
    out = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        out[k] = int(v.split()[0])  # kB
    return out
