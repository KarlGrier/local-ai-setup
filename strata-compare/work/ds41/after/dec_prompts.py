"""dec_prompts.py - 10-26 (Karl: the Maya-style decode check for IQ_Q8K): writes the three short prompts' token ids
(results/ds41/ports/decode/p1..p3.ids, comma-separated) through the GGUF's chat template, thinking on, as the server
renders them (the tokenizer and template skipcheck.decode uses). Prints each prompt's length. No GPU."""
import json
import os
import sys

SC = "/home/USER/ai-speed-testing/strata-compare"
V24 = f"{SC}/strata-v024"
sys.path.insert(0, f"{V24}/tools")
sys.path.insert(0, V24)
import strata_tokenizer as ST  # noqa: E402
from serve.frontend import ChatTemplate  # noqa: E402

OUT = f"{SC}/results/ds41/ports/decode"
PROMPTS = [
    "I keep a small vegetable garden on a balcony that gets about five hours of direct sun in the afternoon. Last year my "
    "tomatoes grew tall but gave very little fruit, while the basil and the peppers did well. I water every morning and "
    "use a general-purpose fertilizer once a week. What are the most likely reasons for the poor tomato harvest, and what "
    "should I change this season?",
    "Write a Python function that takes a list of meeting time ranges, each given as a pair of start and end minutes "
    "since midnight, and returns the smallest number of rooms needed so that no two overlapping meetings share a room. "
    "Explain the idea briefly, state the time complexity, and include two short test cases, one of them with meetings "
    "that touch exactly at their ends.",
    "A train leaves a city at 9:40 and travels at an average of 84 km/h. A second train leaves the same station on the "
    "same track at 10:25 and travels at an average of 108 km/h in the same direction. At what time does the second train "
    "catch up with the first, and how far from the station are they then? Show the steps so I can check them.",
]


def main():
    tp = f"{SC}/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/pack-ist-das-2.00bpw/tokenizer"
    vocab = json.load(open(f"{tp}/vocab.json", encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = ST.Tokenizer(toks, open(f"{tp}/merges.txt", encoding="utf-8").read().split("\n"), json.load(open(f"{tp}/token_type.json")))
    tmpl = ChatTemplate(f"{V24}/serve/fixtures/deepseek41/chat_template.jinja")
    os.makedirs(OUT, exist_ok=True)
    for i, p in enumerate(PROMPTS, 1):
        ids = tok.encode(tmpl.render([{"role": "user", "content": p}]), parse_special=True)
        open(f"{OUT}/p{i}.ids", "w").write(",".join(map(str, ids)))
        print(f"p{i}: {len(ids)} tokens")


if __name__ == "__main__":
    main()
