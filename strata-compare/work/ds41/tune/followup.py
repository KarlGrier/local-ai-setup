#!/usr/bin/env python3
"""followup.py BASE OUTDIR ENGINE_LOG - 10-24 DeepSeek-V4.1 tuning round, the chat follow-up measurement for the chunk
2048 confirm (the user: "also measure a follow-up turn that reuses the saved chat (new turn only), since that's where its
decode gain would matter in chat"). One engine: turn 1 = a ~20K-token conversation start (conv.py's docs text, the reply
capped at 1,024 tokens); then three ~300-token follow-ups in the same conversation, each read on top of the reused state
(the engine's "N tokens = X reused + Y read" line shows only the new turn read), seed 4242, 1,024 tokens each.
Per turn -> OUTDIR/conv.jsonl (conv.py's record) + the follow-ups' decode rate (completion tokens over the time after the
first token) -> OUTDIR/followup.json.
"""
import json
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import conv  # noqa: E402

FOLLOWS = [conv.FOLLOW,
           conv.FOLLOW.replace("Thanks. A follow-up", "One more follow-up"),
           conv.FOLLOW.replace("Thanks. A follow-up", "A last follow-up")]


def main():
    base, out, elog = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    t = conv.Turns(base, out, elog, f"{out}/no-slot-dir")
    src = conv.text(90000)
    msgs = [{"role": "system", "content": conv.SYS},
            {"role": "user", "content": f"{conv.QS[0]}\n\n{src[:80000]}"}]
    msgs.append({"role": "assistant", "content": t.turn("F0 (the ~20K start)", msgs, 1024)["answer"]})
    rows = []
    for i, q in enumerate(FOLLOWS):
        msgs.append({"role": "user", "content": q})
        r = t.turn(f"F{i + 1} (follow-up)", msgs, 1024, seed=4242)
        msgs.append({"role": "assistant", "content": r["answer"]})
        n = (r["usage"] or {}).get("completion_tokens") or 0
        dt = (r["total_s"] or 0) - (r["ttft_s"] or 0)
        rows.append({"turn": i + 1, "completion_tokens": n, "ttft_s": r["ttft_s"], "decode_tps": round(n / dt, 2) if dt > 0 else None})
    recs = [json.loads(l) for l in open(f"{out}/conv.jsonl")]
    for row, rec in zip(rows, recs[1:]):
        row.update({k: rec.get(k) for k in ("prompt_tokens", "reused", "read")})
    rates = [x["decode_tps"] for x in rows if x["decode_tps"]]
    res = {"followups": rows, "decode_tps_mean": round(sum(rates) / len(rates), 2) if rates else None,
           "ttft_s_mean": round(sum(x["ttft_s"] for x in rows if x["ttft_s"]) / len(rows), 2) if rows else None}
    json.dump(res, open(f"{out}/followup.json", "w"), indent=1)
    print(f"follow-ups: decode {res['decode_tps_mean']} tok/s (mean of {len(rates)}), TTFT {res['ttft_s_mean']} s; "
          + "; ".join(f"F{x['turn']}: {x['prompt_tokens']} = {x['reused']} reused + {x['read']} read, {x['decode_tps']} tok/s" for x in rows),
          flush=True)


if __name__ == "__main__":
    main()
