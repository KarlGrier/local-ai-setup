#!/usr/bin/env python3
"""make_tf_long.py — round 4: the long teacher-forced texts, tokenized exactly as the server does (chat template ->
Strata tokenizer, the same ids llama.cpp produces; checked in round 1). Checks the 32K speed prompt against
work/prof/32k.tokens (round 3's source of long16k/long24k), then writes long64k = first 65,536 tokens of the 120K
speed prompt as the prompt and the next 1,536 as the scored text (work/prof/tf-long64k.{prompt,text})."""
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
def ids_of(size, rep):
    p = next(x for x in speed if x["size"] == size and x["rep"] == rep)
    return tok.encode(tpl.render(p["messages"], tools=None), parse_special=True)
i32 = ids_of("32k", 0)
ref = [int(x) for x in open(WS / "work/prof/32k.tokens").read().split(",")]
print("32k r0:", len(i32), "tokens; == work/prof/32k.tokens:", i32 == ref)
assert i32 == ref
i120 = ids_of("120k", 0)
print("120k r0:", len(i120), "tokens")
P, N = 65536, 1536
(WS / "work/prof/tf-long64k.prompt").write_text(",".join(map(str, i120[:P])))
(WS / "work/prof/tf-long64k.text").write_text(",".join(map(str, i120[P:P + N])))
print("wrote tf-long64k: prompt", P, "text", N)
