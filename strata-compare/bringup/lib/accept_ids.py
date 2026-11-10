#!/usr/bin/env python3
"""accept_ids.py LLAMA_BASE SERVE_TREE TOKENIZER_DIR OUT.json — acceptance row "tokenizer and template ids": the same
conversations rendered and tokenized by Strata's server code (SERVE_TREE's ChatTemplate + strata_tokenizer, the
model's exported template and vocabulary) and by llama.cpp's llama-server (/apply-template, then /tokenize with
parse_special) on the SAME GGUF.  Synthetic conversations only (plain chat, reasoning, tools, Unicode, long).
Pass: every rendered prompt identical and every token id identical."""
import json
import sys
import urllib.request
from pathlib import Path

BASE, TREE, TP, OUT = sys.argv[1].rstrip("/"), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
sys.path.insert(0, str(TREE)); sys.path.insert(0, str(TREE / "tools"))
import strata_tokenizer as ST  # noqa: E402
from serve.frontend import ChatTemplate  # noqa: E402

vocab = json.loads((TP / "vocab.json").read_text(encoding="utf-8"))
toks = [None] * len(vocab)
for t, i in vocab.items():
    toks[i] = t
tok = ST.Tokenizer(toks, (TP / "merges.txt").read_text(encoding="utf-8").split("\n"), json.loads((TP / "token_type.json").read_text()))
tpl = ChatTemplate(TP / "chat_template.jinja")


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


TOOLS = [{"type": "function", "function": {"name": "web_search", "description": "Search the web.",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}]
CONVS = [
    ("plain", [{"role": "user", "content": "What is the capital of Australia?"}], None),
    ("system", [{"role": "system", "content": "You are terse."}, {"role": "user", "content": "Name three rivers."}], None),
    ("multi", [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello! How can I help?"},
               {"role": "user", "content": "Tell me a joke about compilers."}], None),
    ("reasoning", [{"role": "user", "content": "2+2?"}, {"role": "assistant", "content": "4", "reasoning_content": "Simple sum."},
                   {"role": "user", "content": "And 3+3?"}], None),
    ("unicode", [{"role": "user", "content": "数据库 日本語 한국어 emoji 👩‍👩‍👧 RTL שלום nbsp x y tabs\tend"}], None),
    ("code", [{"role": "user", "content": "```python\ndef f(x):\n    return x ** 2\n```\nExplain."}], None),
    ("tools", [{"role": "user", "content": "Find the boiling point of water at 2,000 m."}], TOOLS),
    ("toolresult", [{"role": "user", "content": "Search for zram."},
                    {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "web_search", "arguments": {"query": "zram"}}}]},
                    {"role": "tool", "tool_call_id": "c1", "content": "zram is a compressed RAM block device."}], TOOLS),
    ("long", [{"role": "user", "content": " ".join(f"word{i % 97} sentence {i}." for i in range(3000))}], None),
]
rows, ok_all = [], True
for name, msgs, tools in CONVS:
    mine = tpl.render(msgs, tools=tools)
    try:
        body = {"messages": msgs}
        if tools:
            body["tools"] = tools
        theirs = post("/apply-template", body).get("prompt", "")
    except Exception as e:  # noqa: BLE001
        theirs = f"<error {e}>"
    ids_mine = tok.encode(mine, parse_special=True)
    try:
        ids_theirs = post("/tokenize", {"content": mine, "add_special": False, "parse_special": True}).get("tokens", [])
    except Exception as e:  # noqa: BLE001
        ids_theirs = []
    same_text, same_ids = mine == theirs, ids_mine == ids_theirs
    first = next((i for i, (a, b) in enumerate(zip(mine, theirs)) if a != b), min(len(mine), len(theirs)))
    rows.append({"case": name, "text_same": same_text, "ids_same": same_ids, "n_ids": len(ids_mine),
                 "text_first_diff": None if same_text else {"at": first, "strata": mine[max(0, first - 40):first + 60],
                                                             "llama": theirs[max(0, first - 40):first + 60]}})
    ok_all &= same_ids
    print(f"{name:11s} template text {'same' if same_text else 'DIFFERS'}, ids {'same' if same_ids else 'DIFFER'} ({len(ids_mine)} ids)")
OUT.write_text(json.dumps({"rows": rows, "pass": ok_all, "text_all_same": all(r["text_same"] for r in rows)}, indent=1))
print(f"accept ids: {'PASS' if ok_all else 'FAIL'} (token ids of Strata's rendering in both tokenizers); template text identical in "
      f"{sum(r['text_same'] for r in rows)}/{len(rows)}")
