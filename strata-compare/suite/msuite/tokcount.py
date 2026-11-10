"""Reasoning / answer token split.

Order of preference: the API's own count (usage.completion_tokens_details.reasoning_tokens); the model's tokenizer
(llama.cpp's /tokenize, or for a Strata server the pack's tokenizer found through its /config file name, or
--tokenizer DIR); otherwise an estimate by characters (marked "estimate" in every record).
"""
from __future__ import annotations

import importlib
import json
import sys
import urllib.request
from pathlib import Path

from .common import WS


class Counter:
    method = "estimate"

    def count(self, text: str):
        return None

    def split(self, completion, reasoning_text: str, answer_text: str, details=None) -> dict:
        if details and details.get("reasoning_tokens") is not None and completion is not None:
            r = int(details["reasoning_tokens"])
            return {"completion": completion, "reasoning": r, "answer": max(0, completion - r), "method": "usage"}
        a = self.count(answer_text) if answer_text else 0
        if a is not None:
            if completion is None:
                rt = self.count(reasoning_text) if reasoning_text else 0
                if rt is not None:                    # (no counter for the text: the estimate below)
                    return {"completion": rt + a, "reasoning": rt, "answer": a, "method": self.method + "+no-usage"}
            else:
                a = min(a, completion)
                return {"completion": completion, "reasoning": completion - a, "answer": a, "method": self.method}
        lr, la = len(reasoning_text or ""), len(answer_text or "")
        if completion is None:
            completion = round((lr + la) / 3.5)
            meth = "estimate+no-usage"
        else:
            meth = "estimate"
        r = round(completion * lr / (lr + la)) if lr + la else 0
        return {"completion": completion, "reasoning": r, "answer": completion - r, "method": meth}


class StrataTokenizer(Counter):
    method = "tokenizer"

    def __init__(self, tok_dir: Path, tools_dir: Path):
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        ST = importlib.import_module("strata_tokenizer")
        vocab = json.loads((tok_dir / "vocab.json").read_text(encoding="utf-8"))
        tokens = [None] * len(vocab)
        for t, i in vocab.items():
            tokens[i] = t
        merges = (tok_dir / "merges.txt").read_text(encoding="utf-8").split("\n")
        types = json.loads((tok_dir / "token_type.json").read_text())
        self.tok = ST.Tokenizer(tokens, merges, types)
        self.where = str(tok_dir)

    def count(self, text):
        return len(self.tok.encode(text))


class LlamaCppTokenizer(Counter):
    method = "tokenizer"

    def __init__(self, root):
        self.url = root + "/tokenize"
        self.count("probe")

    def count(self, text):
        req = urllib.request.Request(self.url, data=json.dumps({"content": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return len(json.loads(r.read())["tokens"])


def strata_dirs_from_config(cfg_file: str):
    """configs/<file> -> (tokenizer dir, the server's tools dir), or None."""
    p = WS / "configs" / Path(cfg_file).name
    if not p.exists():
        return None
    cfg = json.loads(p.read_text())
    tok, server = cfg.get("tokenizer"), cfg.get("server")
    if not tok or not server:
        return None
    tools = Path(server).parent.parent / "tools"
    if (Path(tok) / "vocab.json").exists() and (tools / "strata_tokenizer.py").exists():
        return Path(tok), tools
    return None


def local_counter(root: str, tokenizer: str | None = None) -> Counter:
    if tokenizer:
        d = Path(tokenizer)
        tools = next((t for t in sorted(WS.glob("strata-cstar*/tools"), reverse=True)
                      if (t / "strata_tokenizer.py").exists()), None)
        if (d / "vocab.json").exists() and tools:
            return StrataTokenizer(d, tools)
        raise SystemExit(f"--tokenizer {tokenizer}: needs vocab.json, merges.txt, token_type.json")
    try:
        return LlamaCppTokenizer(root)
    except Exception:
        pass
    try:
        with urllib.request.urlopen(root + "/config", timeout=5) as r:
            c = json.loads(r.read())
        dirs = strata_dirs_from_config(c.get("file", "")) if isinstance(c, dict) else None
        if dirs:
            return StrataTokenizer(*dirs)
    except Exception:
        pass
    return Counter()
