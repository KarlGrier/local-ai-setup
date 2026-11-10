"""mk_cbprompts.py - the community benchmark's prompts (4,096 / 32,768 / 128,000 tokens, three runs each, plus one
~1,000-token warm-up), built only from Strata's own repository text at tag v0.1.41 (MIT licensed) so they can be shared and
rebuilt: docs/*.md, src/**/*.cpp, src/**/*.cu, include/**/*.hpp, serve/**/*.py, tools/**/*.py in that order (the
order tools/needle_bench.py uses, without third_party/), each file under a "=== path ===" line. Every prompt is a
different, non-overlapping slice of that text, with a unique run id as its first line, so no request can reuse another's
prefix beyond the chat template's first tokens. Token counts are of the rendered prompt (the pack's tokenizer and chat
template); the server reports the real count per request.

    python mk_cbprompts.py TREE TOKENIZER_DIR OUT.json"""
import hashlib
import json
import sys
from pathlib import Path

TREE, TDIR, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/scripts")
from common import load_template, load_tokenizer   # noqa: E402

tok = load_tokenizer(TDIR)
tpl = load_template(TDIR / "chat_template.jinja")
SOURCES = [("docs", "*.md"), ("src", "*.cpp"), ("src", "*.cu"), ("include", "*.hpp"), ("serve", "*.py"), ("tools", "*.py")]
parts = []
for d, pat in SOURCES:
    for f in sorted((TREE / d).rglob(pat)):
        parts.append(f"\n\n=== {f.relative_to(TREE).as_posix()} ===\n{f.read_text(encoding='utf-8', errors='replace')}")
text = "".join(parts)
PLAN = [("warmup", 1000, 1)] + [(str(n), n, 3) for n in (4096, 32768, 128000)]
need = sum(n * r for _, n, r in PLAN)
chars = int(need * 3.6)               # about 3.2 characters per token here; a margin for the slices' adjustments
ids = tok.encode(text[:chars])
print(f"text {len(text):,} chars; encoded the first {chars:,} = {len(ids):,} tokens for {need:,} needed", flush=True)
TASK = "\n\nTask: in one short paragraph, say what the material above is about."
n_prompt = lambda m: len(tok.encode(tpl.render(m), parse_special=True))
out, cursor = [], 0
for size, target, reps in PLAN:
    for r in range(reps):
        nonce = hashlib.sha1(f"cb-{size}-{r}".encode()).hexdigest()[:8]
        head = f"[Run cb-{size}-r{r}-{nonce}] Below is source code and documentation from the Strata repository (tag v0.1.41).\n\n"
        n = target - n_prompt([{"role": "user", "content": head + TASK}])
        for _ in range(8):            # decode/re-encode can move the count by a token or two
            body = tok.decode(ids[cursor:cursor + n])
            msgs = [{"role": "user", "content": head + body + TASK}]
            got = n_prompt(msgs)
            if abs(got - target) <= 2:
                break
            n += target - got
        if cursor + n > len(ids):
            raise SystemExit("ran out of text")
        cursor += n
        out.append({"size": size, "rep": r, "target": target, "prompt_tokens": got, "messages": msgs,
                    "first_file": body.split("\n=== ", 1)[-1].split(" ===", 1)[0] if "\n=== " in body else "(mid-file)"})
        print(size, r, got, flush=True)
OUT.write_text(json.dumps(out, ensure_ascii=False))
print(f"wrote {OUT}: {len(out)} prompts, {cursor:,} tokens of text used, sha256 "
      f"{hashlib.sha256(OUT.read_bytes()).hexdigest()}")
