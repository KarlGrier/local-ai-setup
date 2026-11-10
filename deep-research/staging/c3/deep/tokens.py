"""Token counting with the served model's own BPE vocabulary (exact for text; the chat template adds a few tokens
per message, which MSG_OVERHEAD covers). Falls back to a conservative chars/3 estimate without the vocabulary (the
divisor and both overheads come from the model profile)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from . import config

# C3b (10-29): the overheads come from the model profile (deep/modelprofile.py; defaults = Qwen's ChatML numbers)
MSG_OVERHEAD = config().tok_msg_overhead      # <|im_start|>role\n ... <|im_end|>\n and tool-call wrapping, per message
TOOLS_OVERHEAD = config().tok_tools_overhead  # the chat template's tool-use instructions
CHARS_PER_TOKEN = max(1, config().tok_chars_per_token)   # the estimate without the vocabulary
_tok = None
_tok_lock = threading.Lock()
_tok_failed = False


def _load():
    global _tok, _tok_failed
    if _tok is not None or _tok_failed:
        return _tok
    with _tok_lock:
        if _tok is not None or _tok_failed:
            return _tok
        d = config().tokenizer_dir
        try:
            if not d:
                raise FileNotFoundError("LDR_DEEP_TOKENIZER_DIR not set")
            from tokenizers import Regex, Tokenizer, decoders, models, pre_tokenizers

            vocab = json.loads(Path(d, "vocab.json").read_text(encoding="utf-8"))
            merges = []
            with open(Path(d, "merges.txt"), encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if line and not line.startswith("#version"):
                        a, _, b = line.partition(" ")
                        merges.append((a, b))
            pattern = json.loads(Path(d, "tokenizer.json").read_text(encoding="utf-8"))["pre_pattern"]
            tok = Tokenizer(models.BPE(vocab=vocab, merges=merges))
            tok.pre_tokenizer = pre_tokenizers.Sequence(
                [pre_tokenizers.Split(Regex(pattern), behavior="isolated"),
                 pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False)])
            tok.decoder = decoders.ByteLevel()
            _tok = tok
            logger.info(f"deep: token counter uses the model vocabulary in {d} ({len(vocab)} tokens)")
        except Exception as exc:  # noqa: BLE001 — counting must never break research
            _tok_failed = True
            logger.warning(f"deep: exact token counter unavailable ({exc}); using chars/3")
    return _tok


def count_text(text: str) -> int:
    if not text:
        return 0
    tok = _load()
    if tok is None:
        return len(text) // CHARS_PER_TOKEN + 1
    return len(tok.encode(text, add_special_tokens=False).ids)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, dict):
                out.append(str(p.get("text", "")))
            else:
                out.append(str(p))
        return "".join(out)
    return str(content or "")


def count_message(msg: Any) -> int:
    n = MSG_OVERHEAD + count_text(_content_text(getattr(msg, "content", msg)))
    for tc in getattr(msg, "tool_calls", None) or []:
        n += count_text(json.dumps({"name": tc.get("name"), "arguments": tc.get("args")}, ensure_ascii=False)) + 6
    return n


def count_messages(msgs: Iterable[Any]) -> int:
    return sum(count_message(m) for m in msgs)


def count_tools(tools: Iterable[Any]) -> int:
    n = 0
    for t in tools or []:
        try:
            if isinstance(t, dict):
                n += count_text(json.dumps(t, ensure_ascii=False))
            else:
                schema = getattr(t, "args_schema", None)
                js = schema.model_json_schema() if hasattr(schema, "model_json_schema") else (getattr(t, "args", {}) or {})
                n += count_text(f"{getattr(t, 'name', '')} {getattr(t, 'description', '')} {json.dumps(js)}") + 20
        except Exception:  # noqa: BLE001
            n += 400
    return n + TOOLS_OVERHEAD  # the template's tool-use instructions


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Cut text to at most max_tokens (keeps the start)."""
    if max_tokens <= 0:
        return ""
    if count_text(text) <= max_tokens:
        return text
    tok = _load()
    if tok is None:
        return text[: max_tokens * CHARS_PER_TOKEN]
    enc = tok.encode(text, add_special_tokens=False)
    return tok.decode(enc.ids[:max_tokens])
