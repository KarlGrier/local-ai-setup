#!/usr/bin/env python3
"""make_tf_more.py — round 4: four more long teacher-forced texts from other documents of the speed set (same tokenizer
path as make_tf_long.py): prompt = the first P tokens of a document, text = the next 1,536 tokens.
  long28k: 32K doc rep 1, P 28,672 · long40k: 64K doc rep 1, P 40,960 · long96k: 120K doc rep 0, P 98,304 ·
  long112k: 120K doc rep 1, P 114,688"""
import json, sys
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "strata-cstar3")); sys.path.insert(0, str(WS / "strata-cstar3/serve")); sys.path.insert(0, str(WS / "strata-cstar3/tools"))
from serve.frontend import ChatTemplate  # noqa: E402
import strata_tokenizer as ST  # noqa: E402
tp = WS / "strata-v0115/packs/iq3_s/tokenizer"
vocab = json.loads((tp / "vocab.json").read_text(encoding="utf-8")); toks = [None] * len(vocab)
for t, i in vocab.items(): toks[i] = t
tok = ST.Tokenizer(toks, (tp / "merges.txt").read_text(encoding="utf-8").split("\n"), json.loads((tp / "token_type.json").read_text()))
tpl = ChatTemplate(tp / "chat_template.jinja" if (tp / "chat_template.jinja").exists() else WS / "strata-cstar3/serve/chat_template.jinja")
speed = json.load(open(WS / "prompts/speed.json"))
for name, size, rep, P in (("long28k", "32k", 1, 28672), ("long40k", "64k", 1, 40960), ("long96k", "120k", 0, 98304), ("long112k", "120k", 1, 114688)):
    p = next(x for x in speed if x["size"] == size and x["rep"] == rep)
    ids = tok.encode(tpl.render(p["messages"], tools=None), parse_special=True)
    assert len(ids) >= P + 1536, (name, len(ids))
    (WS / f"work/prof/tf-{name}.prompt").write_text(",".join(map(str, ids[:P])))
    (WS / f"work/prof/tf-{name}.text").write_text(",".join(map(str, ids[P:P + 1536])))
    print(name, "doc", size, rep, len(ids), "tokens; prompt", P, "text 1536; first text tokens", ids[P:P + 6])
