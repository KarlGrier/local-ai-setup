#!/usr/bin/env python3
"""ttft_client.py BASE OUTDIR ENGINE_LOG - 10-25 (the user, the v0.2.6 switch: "Add a short-prompt time-to-first-token check
(a ~30-token message, both cold and in a reused chat)"; v0.2.6 picks the prompt path by length only, which upstream says
fixes a ~7 s stall on short prompts - the chunked path now warms up at load). One engine, run on both engines:
  S0      cold: the first request after the engine is ready, a new chat with a ~30-token message
  S1-S3   new chats on the warm engine, ~30-token messages
  R0      a ~2K-token chat start (reply capped at 256)
  R1-R3   ~30-token follow-ups in that chat, each read on top of the reused state
64 tokens per short reply, seed 4242. -> OUTDIR/conv.jsonl (conv.py's records) + OUTDIR/ttft.json
"""
import json
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import conv  # noqa: E402

SHORT = ["What is the capital of Australia, and roughly how many people live there? One short sentence, please.",
         "Name one good reason to keep a laptop's battery between 20 and 80 percent. Keep it to one sentence.",
         "Which planet in our solar system has the longest day? Answer in a single short sentence.",
         "Give me one tip for remembering people's names after meeting them. One sentence is enough."]
FOLLOW = ["Thanks. In one sentence: which of those points matters most for speed?",
          "And in one sentence: which point would you test first, and why?",
          "Last one, one sentence: what would you measure to know it worked?"]


def main():
    base, out, elog = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    t = conv.Turns(base, out, elog, f"{out}/no-slot-dir")
    rows = []

    def short(label, msgs, n=64):
        r = t.turn(label, msgs, n, seed=4242)
        rows.append({"turn": label, "ttft_s": r["ttft_s"], "prompt_tokens": (r["usage"] or {}).get("prompt_tokens")})
        return r

    for i, q in enumerate(SHORT):
        short("S0 cold (first request)" if i == 0 else f"S{i} new chat, warm engine",
              [{"role": "system", "content": conv.SYS}, {"role": "user", "content": q}])
    msgs = [{"role": "system", "content": conv.SYS}, {"role": "user", "content": f"{conv.QS[0]}\n\n{conv.text(8000)}"}]
    msgs.append({"role": "assistant", "content": t.turn("R0 (~2K start)", msgs, 256, seed=4242)["answer"]})
    for i, q in enumerate(FOLLOW):
        msgs.append({"role": "user", "content": q})
        r = short(f"R{i + 1} follow-up, reused chat", msgs)
        msgs.append({"role": "assistant", "content": r["answer"]})
    recs = {json.loads(l)["turn"]: json.loads(l) for l in open(f"{out}/conv.jsonl")}
    for row in rows:
        row.update({k: recs.get(row["turn"], {}).get(k) for k in ("reused", "read")})

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None
    res = {"cold_s": rows[0]["ttft_s"], "warm_new_chat_s": mean([r["ttft_s"] for r in rows[1:4]]),
           "reused_chat_s": mean([r["ttft_s"] for r in rows[4:]]), "turns": rows}
    json.dump(res, open(f"{out}/ttft.json", "w"), indent=1)
    print(f"short-prompt TTFT: cold {res['cold_s']} s, new chat (warm) {res['warm_new_chat_s']} s, reused chat "
          f"{res['reused_chat_s']} s; " + "; ".join(f"{r['turn'].split()[0]}: {r['prompt_tokens']} = {r['reused']} reused + "
                                                     f"{r['read']} read, {r['ttft_s']} s" for r in rows), flush=True)


if __name__ == "__main__":
    main()
