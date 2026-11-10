#!/usr/bin/env python3
"""split_probe.py SERVE_TREE OUT.json — acceptance row "stop, tool-call and control-text probes with every boundary
split" (the server side, no engine): the model's text reaches the server in pieces of any length (one token, several
tokens, a chunk), so the output parser and the stop matcher must give the same result however the text is split.

For each probe text: the parse of the whole text vs the parse of the text fed in pieces at EVERY single split point
(two pieces) and at 300 random multi-splits (pieces of 1-7 characters, seeded).  Compared: the merged events (kind and
text, tool calls with their name and arguments) of OutputParser (frontend.py), and what StopMatcher (server.py, #454)
lets through plus the stop string it hits.  Pass: identical in every split."""
import json
import random
import sys
from pathlib import Path

TREE, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(TREE)); sys.path.insert(0, str(TREE / "tools"))
from serve.frontend import OutputParser  # noqa: E402
from serve.server import StopMatcher  # noqa: E402

TOOLS = [{"name": "web_search", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}},
         {"name": "write", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "n": {"type": "integer"}}}}]
PARSE = {
    "think_then_answer": (True, "Let me think about it.\n</think>\n\nThe answer is 42."),
    "tool_call": (True, "Need a search.\n</think>\n\n<tool_call>\n<function=web_search>\n<parameter=query>\nboiling point at 2000 m\n</parameter>\n</function>\n</tool_call>"),
    "prose_tag_then_call": (False, "I will now use the <tool_call> format to search.\n<tool_call>\n<function=web_search>\n<parameter=query>\nzram vs zswap\n</parameter>\n</function>\n</tool_call>"),
    "two_calls": (False, "<tool_call>\n<function=write>\n<parameter=path>\na.txt\n</parameter>\n<parameter=n>\n3\n</parameter>\n</function>\n</tool_call>\n<tool_call>\n<function=web_search>\n<parameter=query>\nx\n</parameter>\n</function>\n</tool_call>"),
    "control_text_in_answer": (True, "ok\n</think>\n\nThe tokens are <|im_end|> and <|endoftext|>, written as text: IM_END = \"<|im_end|>\"."),
    "partial_tags": (True, "a </thi nk> b <tool_ c </think>\n\nd <tool_cal e"),
}
STOPS = {
    "multi_token": (["11, 12, 13"], ", ".join(str(i) for i in range(1, 41))),
    "two_stops": (["13", "END"], "1, 2, 3 ... 12, 13, 14 END"),
    "near_miss": (["13."], "1, 2, 13, 14, 113, 13x, end"),
    "overlap": (["abcab"], "xxabcabcabyy"),
    "control_text_stop": (["<|im_end|>"], "answer text <|im_e then <|im_end|> more"),
}


def parse(thinking, pieces):
    p = OutputParser(thinking=thinking, tools=TOOLS)
    ev = []
    for piece in pieces:
        ev += p.feed(piece)
    ev += p.finish()
    merged = []
    for e in ev:
        k = e.kind if hasattr(e, "kind") else e[0]
        t = getattr(e, "text", None)
        extra = {}
        call = getattr(e, "call", None)
        if call is not None:   # a tool call: its name and arguments (its id is random per parse)
            extra = {"name": getattr(call, "name", None), "arguments": json.dumps(getattr(call, "arguments", None), sort_keys=True)}
        if merged and merged[-1][0] == k and k in ("content", "reasoning") and not extra:
            merged[-1] = (k, merged[-1][1] + (t or ""), merged[-1][2])
        else:
            merged.append((k, t, json.dumps(extra, sort_keys=True)))
    return merged


def stop(stops, pieces):
    m = StopMatcher(stops)
    out = "".join(m.push(p) for p in pieces)
    if m.hit is None:
        out += m.flush()
    return out, m.hit


def splits(text, rng):
    yield [text]
    for i in range(1, len(text)):
        yield [text[:i], text[i:]]
    for _ in range(300):
        pieces, i = [], 0
        while i < len(text):
            n = rng.randint(1, 7)
            pieces.append(text[i:i + n])
            i += n
        yield pieces


rng = random.Random(13)
rows, ok_all = [], True
for name, (thinking, text) in PARSE.items():
    ref = parse(thinking, [text])
    bad = sum(parse(thinking, pcs) != ref for pcs in splits(text, rng))
    rows.append({"probe": f"parser:{name}", "splits": len(text) - 1 + 300, "differ": bad, "events": len(ref)})
    ok_all &= bad == 0
    print(f"parser {name:24s} {len(text) - 1 + 300:5d} splits, {bad} differ; whole-text events: {ref[:4]}{' ...' if len(ref) > 4 else ''}"[:220])
for name, (stops, text) in STOPS.items():
    ref = stop(stops, [text])
    bad = sum(stop(stops, pcs) != ref for pcs in splits(text, rng))
    rows.append({"probe": f"stop:{name}", "splits": len(text) - 1 + 300, "differ": bad, "result": list(ref)})
    ok_all &= bad == 0
    print(f"stop   {name:24s} {len(text) - 1 + 300:5d} splits, {bad} differ; whole text -> {ref}"[:220])
OUT.write_text(json.dumps({"rows": rows, "pass": ok_all}, indent=1))
print(f"split probe: {'PASS' if ok_all else 'FAIL'}")
