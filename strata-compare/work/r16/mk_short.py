"""mk_short.py - round 16 step 1: prompts of 512 and 1,000 tokens (TOTAL rendered prompt, as make_prompts.py counts) for
the CPU prompt-read share A/B. Six of each, each a different slice of the corpus (its last 120,000 characters, so not the
speed set's slices) with a unique nonce first, so no request shares more than the template's first tokens with another.
Size "1k" rep 0 is the warm-up prompt bench.py skips; "w600" (2 reps, ~600 tokens) warm the short-prompt path and are not
counted; the measured sizes are "512" and "1000" (reps 0-5). Only the slice is encoded (the whole corpus took minutes)."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/scripts")
from common import CORPUS, PROMPTS, load_template, load_tokenizer
tok = load_tokenizer(); tpl = load_template()
txt = CORPUS.read_text(encoding="utf-8"); ids = tok.encode(txt[-120_000:]); cursor = 0
n_prompt = lambda m: len(tok.encode(tpl.render(m), parse_special=True))
TASK = ("\n\nTask: Write a detailed, file-by-file technical summary of the material above. For each file, state its "
        "purpose, the main functions or sections it contains, and anything notable or unusual. Be thorough.")
out = [json.loads((PROMPTS / "speed.json").read_text())[0]]   # 1k rep 0: the warm-up
for size, reps in ((600, 2), (512, 6), (1000, 6)):
    for r in range(reps):
        nonce = f"{size}-r{r}-{hashlib.sha1(f'r16{size}{r}'.encode()).hexdigest()[:8]}"
        head = f"[Session {nonce}] Below is a collection of source files and license texts.\n\n"
        over = n_prompt([{"role": "user", "content": head + TASK}])
        n = size - over
        for _ in range(6):   # decode/re-encode can shift the count by a token or two: adjust the slice (bounded: it can
            body = tok.decode(ids[cursor:cursor + n]); msgs = [{"role": "user", "content": head + body + TASK}]
            got = n_prompt(msgs)   # oscillate by one token, so +-2 is accepted)
            if abs(got - size) <= 2: break
            n += size - got
        cursor += n
        out.append({"messages": msgs, "prompt_tokens": got, "target": size, "size": "w600" if size == 600 else str(size), "rep": r})
(PROMPTS / "r16/ttft-short.json").write_text(json.dumps(out, ensure_ascii=False))
print([(p["size"], p["rep"], p["prompt_tokens"]) for p in out])
