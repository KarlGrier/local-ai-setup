#!/usr/bin/env python3
"""repeat_client.py BASE OUTDIR - 10-24 DeepSeek-V4.1 tuning round, item A.1 (the user: "Repeatability: same prompt, same
seed, same config, 3 runs"). Against a freshly started engine: the W1 prompt with no nonce, seed 4242, T 1.0 / 0.95 / 20 /
min-p 0.05, thinking on (medium), 320 tokens - twice in a row (request 1 on the fresh engine, request 2 right after on the
same engine). Texts -> OUTDIR/repeat.jsonl. work/ds41/tune/tune.sh starts the engine three times per variant and
repeat_compare.py compares the texts.
"""
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
import abrun  # noqa: E402
import json  # noqa: E402


def main():
    base, out = sys.argv[1], sys.argv[2]
    wl = json.load(open(abrun.WL))
    w1 = next(w for w in wl["normal"] if w["id"].startswith("W1"))
    job = dict(w1, id="repeat", max_tokens=320, nonce=False)
    for rep in (1, 2):
        rec = abrun.one(base, "repeat", job, abrun.NORMAL, {"seed": 4242}, rep, f"{out}/repeat.jsonl", keep_text=True)
        print(f"request {rep}: {rec.get('completion_tokens')} tokens, {len(rec.get('text') or '')} chars", flush=True)


if __name__ == "__main__":
    main()
