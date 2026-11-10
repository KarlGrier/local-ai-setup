"""Build the frozen prompt sets (prompts/*.json) used identically for every configuration.

Speed prompts are cut from the signal-3.8-opus corpus (2.24 MB of source code + license texts, 606,046 tokens) in
non-overlapping slices, so every request is novel text (no prefix/n-gram reuse between repetitions), and each starts
with a unique nonce. Target sizes are the TOTAL rendered prompt (template + xhigh system line included).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CORPUS, EVAL_DIR, PROMPTS, S3_PROMPTS, load_template, load_tokenizer  # noqa: E402

tok = load_tokenizer()
tpl = load_template()
text = CORPUS.read_text(encoding="utf-8")
ids = tok.encode(text)
cursor = 0


def n_prompt(messages) -> int:
    return len(tok.encode(tpl.render(messages), parse_special=True))


def take(n: int) -> str:
    """The next n corpus tokens as text (non-overlapping)."""
    global cursor
    if cursor + n > len(ids):
        raise SystemExit("corpus exhausted")
    s = tok.decode(ids[cursor:cursor + n])
    cursor += n
    return s


SPEED_TASK = ("\n\nTask: Write a detailed, file-by-file technical summary of the material above. For each file, "
              "state its purpose, the main functions or sections it contains, and anything notable or unusual. "
              "Be thorough.")


def speed_prompt(target: int, nonce: str) -> dict:
    head = f"[Session {nonce}] Below is a collection of source files and license texts.\n\n"
    overhead = n_prompt([{"role": "user", "content": head + SPEED_TASK}])
    body = take(target - overhead)
    msgs = [{"role": "user", "content": head + body + SPEED_TASK}]
    return {"messages": msgs, "prompt_tokens": n_prompt(msgs), "target": target}


out = {}
SIZES = {"1k": 1024, "4k": 4096, "32k": 32768, "64k": 65536, "120k": 122880}
REPS = {"1k": 4, "4k": 3, "32k": 3, "64k": 2, "120k": 2}   # 1k rep 0 is the warm-up
speed = []
for name, target in SIZES.items():
    for r in range(REPS[name]):
        p = speed_prompt(target, f"{name}-r{r}-{hashlib.sha1(f'{name}{r}'.encode()).hexdigest()[:8]}")
        p.update(size=name, rep=r)
        speed.append(p)
out["speed"] = speed

# ---- multi-turn chat: 7 turns growing to ~40K tokens, full history resent each turn (Open WebUI style: earlier
# reasoning is not resent). Assistant turns are CANNED (identical for every config), so the history is the same.
QUESTIONS = [
    "Which files appear in this part, and what is each one for?",
    "Which of these files would matter most to someone debugging a GPU kernel, and why?",
    "Are there any license obligations in this part that a company redistributing binaries must follow?",
    "Summarize the programming patterns that repeat across these files.",
    "Which file in this part is the most complex, and what makes it complex?",
    "If you had to delete one file from this part, which would cause the least damage? Explain.",
    "Give a one-paragraph overview of everything we have read so far.",
]
turn_text = []
for k in range(7):
    turn_text.append(take(5550))
mt_turns = []
for k in range(7):
    files = re.findall(r"===== FILE: (\S+) =====", turn_text[k])
    user = f"[Chat mt-7f3a] Part {k + 1} of the document:\n\n{turn_text[k]}\n\nQuestion {k + 1}: {QUESTIONS[k]}"
    canned = ("Here is what I found in part %d. It contains %d file headers%s. The material mixes source code and "
              "license text; the question is answered from the visible content only, and anything outside this part "
              "is not assumed." % (k + 1, len(files), (": " + ", ".join(Path(f).name for f in files[:12])) if files else ""))
    mt_turns.append({"user": user, "assistant": canned})
out["multiturn"] = {"turns": mt_turns}
# size check
hist = []
sizes = []
for t in mt_turns:
    hist.append({"role": "user", "content": t["user"]})
    sizes.append(n_prompt(hist))
    hist.append({"role": "assistant", "content": t["assistant"]})
out["multiturn"]["prompt_tokens_per_turn"] = sizes

TITLE_TMPL = """### Task:
Generate a concise, 3-5 word title with an emoji summarizing the chat history.
### Guidelines:
- The title should clearly represent the main theme or subject of the conversation.
- Use emojis that enhance understanding of the topic, but avoid quotation marks or special formatting.
- Write the title in the chat's primary language; default to English if multilingual.
- Prioritize accuracy over excessive creativity; keep it clear and simple.
- Your entire response must consist solely of the JSON object, without any introductory or concluding text.
- The output must be a single, raw JSON object, without any markdown code fences or other encapsulation.
### Output:
JSON format: { "title": "your concise title here" }
### Chat History:
<chat_history>
USER: %s
ASSISTANT: %s
</chat_history>"""
out["side_requests"] = [
    {"messages": [{"role": "user", "content": TITLE_TMPL % (QUESTIONS[k], mt_turns[k]["assistant"][:300])}]}
    for k in range(7)]
for s in out["side_requests"]:
    s["prompt_tokens"] = n_prompt(s["messages"])

s3 = json.loads(S3_PROMPTS.read_text())["s3"]
out["longreason"] = [{"id": k, "messages": [{"role": "user", "content": s3[k]["text"]}]} for k in ("math", "code", "puzzle")]

out["correctness"] = [
    {"id": "arith", "messages": [{"role": "user", "content": "What is 17 * 23 + 144 / 12? Show the steps briefly."}]},
    {"id": "code", "messages": [{"role": "user", "content": "Write a Python function is_palindrome(s) that ignores case and non-alphanumeric characters, with a docstring and three doctest examples."}]},
    {"id": "science", "messages": [{"role": "user", "content": "Explain in three sentences why the sky is blue and sunsets are red."}]},
    {"id": "network", "messages": [{"role": "user", "content": "For the host 172.16.45.200/27, give the network address, broadcast address, and the usable host range."}]},
    {"id": "translate", "messages": [{"role": "user", "content": "Translate into French and German: 'The meeting has been moved to Thursday afternoon because the projector is broken.'"}]},
]

out["quality"] = [{"id": p.stem, "messages": [{"role": "user", "content": p.read_text(encoding="utf-8")}]}
                  for p in sorted(EVAL_DIR.glob("*.txt"))]

PROMPTS.mkdir(parents=True, exist_ok=True)
manifest = {}
for k, v in out.items():
    path = PROMPTS / f"{k}.json"
    data = json.dumps(v, ensure_ascii=False, indent=1).encode()
    path.write_bytes(data)
    manifest[k] = hashlib.sha256(data).hexdigest()
(PROMPTS / "MANIFEST.json").write_text(json.dumps({"corpus_tokens_used": cursor, "sha256": manifest}, indent=1))
print("corpus tokens used", cursor, "of", len(ids))
print("speed:", [(p["size"], p["rep"], p["prompt_tokens"]) for p in speed])
print("multiturn prompt tokens per turn:", sizes)
print("side:", [s["prompt_tokens"] for s in out["side_requests"]])
