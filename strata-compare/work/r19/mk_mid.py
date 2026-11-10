"""mk_mid.py - round 19 (copy of work/r16/mk_short.py): prompts of 1,500, 2,000 and 3,000 tokens (TOTAL rendered prompt) for
the CPU share's chunk limit (STRATA_PREFILL_CPU_SHARE_MAX 3072 vs 1024). Four of each, each a different slice of the corpus (the 240,000
characters before mk_short's last 120,000) with a unique nonce first, so no request shares more than the template's first tokens.
Size "1k" rep 0 is the warm-up prompt bench.py skips; "w600" (2 reps, ~600 tokens) warm the short-prompt path and are not
counted; the measured sizes are "1500", "2000" and "3000" (reps 0-3). Only the slice is encoded."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/scripts")
from common import CORPUS, PROMPTS, load_template, load_tokenizer
tok = load_tokenizer(); tpl = load_template()
txt = CORPUS.read_text(encoding="utf-8"); ids = tok.encode(txt[-360_000:-120_000]); cursor = 0
n_prompt = lambda m: len(tok.encode(tpl.render(m), parse_special=True))
TASK = ("\n\nTask: Write a detailed, file-by-file technical summary of the material above. For each file, state its "
        "purpose, the main functions or sections it contains, and anything notable or unusual. Be thorough.")
out = [json.loads((PROMPTS / "speed.json").read_text())[0]]   # 1k rep 0: the warm-up
for size, reps in ((600, 2), (1500, 4), (2000, 4), (3000, 4)):
    for r in range(reps):
        nonce = f"{size}-r{r}-{hashlib.sha1(f'r19{size}{r}'.encode()).hexdigest()[:8]}"
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
(PROMPTS / "r19/ttft-mid.json").write_text(json.dumps(out, ensure_ascii=False))
print([(p["size"], p["rep"], p["prompt_tokens"]) for p in out])
