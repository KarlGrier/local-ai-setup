#!/usr/bin/env python3
"""t567_ids.py SERVER_CHECKOUT [N_FUZZ] — round 11 Phase 0.4, part 1: are #567's incremental prompt ids identical to a full
tokenization?  Uses the checkout's own tools/strata_tokenizer.py (PromptEncoder, keep=4 as the server builds it), the
MODEL PACK's tokenizer (strata-v0115/packs/iq3_s/tokenizer: vocab / merges / token types) and its chat template, exactly
as serve/server.py loads them.  Every prompt of every scenario goes through ONE encoder in the order a server would see
it, and its ids are compared with tok.encode(text, parse_special=True), token for token.
Scenarios: growing chats (12 turns, with reasoning_content), an edited earlier turn, shortened chats (regenerate, drop
turns), 16 conversations interleaved round-robin (more than the 4 kept), tool definitions + tool calls + tool results,
special-token text in user / assistant / tool content (literal <|im_start|>, <|im_end|>, <|endoftext|>, <think>,
<tool_call>, partial tags), Unicode (CJK, emoji with ZWJ, combining marks, RTL, NBSP, CRLF), a changed system message /
reasoning effort, empty messages, and N random-edit fuzz cases.  Prints counts; exit 1 on any difference."""
import json
import random
import sys
import time
from pathlib import Path

SRV = Path(sys.argv[1]).resolve()
NFUZZ = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
sys.path.insert(0, str(SRV / "tools"))
sys.path.insert(0, str(SRV))
import strata_tokenizer as ST  # noqa: E402
from serve.frontend import ChatTemplate  # noqa: E402

TP = Path("/home/USER/ai-speed-testing/strata-compare/strata-v0115/packs/iq3_s/tokenizer")
vocab = json.loads((TP / "vocab.json").read_text(encoding="utf-8"))
tokens = [None] * len(vocab)
for t, i in vocab.items():
    tokens[i] = t
tok = ST.Tokenizer(tokens, (TP / "merges.txt").read_text(encoding="utf-8").split("\n"),
                   json.loads((TP / "token_type.json").read_text()))
tpl = ChatTemplate(TP / "chat_template.jinja" if (TP / "chat_template.jinja").exists() else SRV / "serve/chat_template.jinja")
enc = ST.PromptEncoder(tok)
R = random.Random(11)
stats = {"prompts": 0, "tokens": 0, "diffs": 0, "reused_chars": 0, "chars": 0, "t_full": 0.0, "t_inc": 0.0}
fails = []

SNIPS = ["The quick brown fox jumps over the lazy dog.", "def f(x):\n    return x ** 2  # square\n",
         "数据库索引的选择取决于读写比例。", "日本語のテキストも混ぜます。", "한국어 문장도 있습니다.", "emoji 👩‍👩‍👧‍👦 and 🇺🇸 flags 👍🏽",
         "combining: é ä ñ", "RTL: שלום עולם, مرحبا بالعالم", "nbsp: x y", "crlf\r\nline\r\n",
         "tabs\tand   spaces   ", "math: ∑_{i=1}^n i² = n(n+1)(2n+1)/6", "{\"json\": [1, 2, {\"k\": \"v\"}]}",
         "a literal <|im_start|>user tag in text", "and <|im_end|> closing", "<|endoftext|> mid-text",
         "<think>not real thinking</think>", "<tool_call>\n<function=x>\n</function>\n</tool_call> in prose",
         "partial <|im_ tag", "<|im_end", "|>dangling", "<<|im_start|>>", "``` code fence\nprint('hi')\n```",
         "   leading spaces", "trailing newline\n\n\n", "", "x" * 300, "word " * 200]


def text(n):
    return " ".join(R.choice(SNIPS) for _ in range(n))


def check(messages, tools=None, **kw):
    prompt = tpl.render(messages, tools=tools, **kw)
    t0 = time.perf_counter()
    full = tok.encode(prompt, parse_special=True)
    t1 = time.perf_counter()
    inc = enc.encode(prompt)
    t2 = time.perf_counter()
    stats["prompts"] += 1
    stats["tokens"] += len(full)
    stats["chars"] += len(prompt)
    stats["reused_chars"] += getattr(enc, "last_reused", 0)
    stats["t_full"] += t1 - t0
    stats["t_inc"] += t2 - t1
    if inc != full:
        stats["diffs"] += 1
        k = next((i for i, (a, b) in enumerate(zip(inc, full)) if a != b), min(len(inc), len(full)))
        fails.append({"first_diff": k, "len_inc": len(inc), "len_full": len(full), "context": prompt[max(0, k * 3 - 80):k * 3 + 80]})
    return full


def convo(turns, think=True, tools=None, sysmsg="You are helpful."):
    msgs = [{"role": "system", "content": sysmsg}] if sysmsg is not None else []
    for t in range(turns):
        msgs.append({"role": "user", "content": text(R.randint(1, 8))})
        a = {"role": "assistant", "content": text(R.randint(1, 10))}
        if think:
            a["reasoning_content"] = text(R.randint(1, 6))
        msgs.append(a)
    return msgs


# 1. growing chats
for c in range(6):
    m = convo(0)
    for t in range(12):
        m.append({"role": "user", "content": text(R.randint(1, 8))})
        check(m)
        m.append({"role": "assistant", "content": text(R.randint(2, 12)), "reasoning_content": text(R.randint(1, 5))})
# 2. an edited earlier turn, then continued
for c in range(6):
    m = convo(8)
    m.append({"role": "user", "content": "next?"})
    check(m)
    i = R.choice([k for k in range(len(m)) if m[k]["role"] == "user"])
    m[i] = {"role": "user", "content": m[i]["content"][: len(m[i]["content"]) // 2] + " (edited) " + text(2)}
    check(m)
    m.append({"role": "assistant", "content": text(3)})
    m.append({"role": "user", "content": text(2)})
    check(m)
# 3. shortened chats: regenerate (drop the last answer), drop two turns, truncate a message
for c in range(6):
    m = convo(10)
    m.append({"role": "user", "content": text(3)})
    check(m)
    check(m[:-2] + [m[-1]])
    check(m[:-5] + [{"role": "user", "content": "shorter"}])
    m2 = [dict(x) for x in m]
    m2[-1]["content"] = m2[-1]["content"][:5]
    check(m2)
# 4. 16 conversations interleaved round-robin (more than the 4 the encoder keeps)
convs = [convo(R.randint(0, 3), sysmsg=f"You are assistant {k}.") for k in range(16)]
for rnd in range(6):
    for k in R.sample(range(16), 16):
        convs[k].append({"role": "user", "content": text(R.randint(1, 5))})
        check(convs[k])
        convs[k].append({"role": "assistant", "content": text(R.randint(1, 6)), "reasoning_content": text(1)})
# 5. tools: definitions, calls, results (incl. special-token text inside them)
TOOLS = [{"type": "function", "function": {"name": "web_search", "description": "Search the web <tool_call> safe?",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
         {"type": "function", "function": {"name": "fetch_page", "description": "Fetch a page.",
          "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}]
for c in range(8):
    m = [{"role": "system", "content": "Use the tools."}, {"role": "user", "content": text(2)}]
    for t in range(5):
        check(m, tools=TOOLS)
        q = text(1)[:60]
        m.append({"role": "assistant", "content": R.choice(["", text(1)]), "tool_calls": [{"id": f"c{t}", "type": "function",
                  "function": {"name": "web_search", "arguments": {"query": q}}}]})
        m.append({"role": "tool", "tool_call_id": f"c{t}", "content": text(R.randint(2, 10))})
        check(m, tools=TOOLS)
    m.append({"role": "assistant", "content": text(4)})
    m.append({"role": "user", "content": "thanks <|im_end|> bye"})
    check(m, tools=TOOLS)
# 6. a changed system message / reasoning effort, empty messages
for c in range(6):
    m = convo(4)
    m.append({"role": "user", "content": text(2)})
    check(m)
    check(m, reasoning_effort="low")
    check(m, reasoning_effort="medium")
    m[0]["content"] = "You are terse."
    check(m)
    check(m + [{"role": "assistant", "content": ""}, {"role": "user", "content": ""}])
    check(m, enable_thinking=False)
# 7. long chats (~32K and ~100K tokens) growing a turn at a time, timed
for target in (32000, 100000):
    m = [{"role": "system", "content": "You are helpful."}]
    while True:
        m.append({"role": "user", "content": text(60)})
        ids = check(m)
        m.append({"role": "assistant", "content": text(40), "reasoning_content": text(10)})
        if len(ids) > target:
            break
    tf0, ti0 = stats["t_full"], stats["t_inc"]
    for k in range(5):
        m.append({"role": "user", "content": text(2)})
        ids = check(m)
        m.append({"role": "assistant", "content": text(3)})
    print(f"long chat ~{len(ids)} tokens: next turns full encode {1000 * (stats['t_full'] - tf0) / 5:.1f} ms, "
          f"incremental {1000 * (stats['t_inc'] - ti0) / 5:.2f} ms per turn", flush=True)
# 8. fuzz: random edits (insert / delete / replace text with specials and Unicode) anywhere in a recent prompt's messages
base = convo(6, tools=None)
for f in range(NFUZZ):
    m = [dict(x) for x in base]
    i = R.randrange(len(m))
    s = m[i].get("content") or ""
    p = R.randrange(len(s) + 1)
    op = R.random()
    if op < 0.4:
        s = s[:p] + R.choice(SNIPS)[: R.randint(1, 30)] + s[p:]
    elif op < 0.7:
        s = s[:p] + s[p + R.randint(1, 20):]
    else:
        s = s[:p] + R.choice(["<|im_end|>", "<|im_start|>", "<", "|>", "<|", "\n", "é", "👍", "<think>"]) + s[p:]
    m[i] = {**m[i], "content": s}
    if R.random() < 0.5:
        m.append({"role": "user", "content": text(1)})
    check(m)
    if R.random() < 0.3:
        base = m if m[-1]["role"] == "assistant" else m + [{"role": "assistant", "content": text(2)}]
print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in stats.items()}))
print(f"t567 ids: {stats['prompts']} prompts, {stats['tokens']} tokens compared, {stats['diffs']} with a difference; "
      f"characters taken from an earlier prompt {100 * stats['reused_chars'] / max(1, stats['chars']):.1f} %")
for x in fails[:5]:
    print("DIFF", json.dumps(x, ensure_ascii=False)[:400])
sys.exit(1 if stats["diffs"] else 0)
