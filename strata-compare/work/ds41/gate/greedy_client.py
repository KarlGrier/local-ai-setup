#!/usr/bin/env python3
"""greedy_client.py BASE OUTDIR - 11-03 (Karl's gate: "C's exactness: greedy output (temperature 0) must be identical with
the drafter on vs off in the same placement"). Run by tunearm.sh as CLIENT on the frozen-placement arms C0f / C1f / C2f
(C0 / C1 / C2 + --no-expert-cache: the VRAM experts stay the profile's, so every arm computes each expert on the same
side - VRAM vs CPU lane rounding cannot differ between them, and drafting cannot move experts). Three prompts, the same
bytes in every arm (no nonce): W1 (prompts/longreason.json "math"), W2 ("code"), P4K-0 (prompts/speed.json 4k rep 0);
thinking off, max_tokens 512, temperature 0 (+ top_k 1, top_p 1, min_p 0: greedy whichever way the engine reads it);
the text streamed back is kept -> OUTDIR/greedy.jsonl (abrun records with "text"), OUTDIR/greedy-engine.jsonl (the
engine's lines per request: tokens, speed, the drafts' acceptance under greedy). greedy_compare.py compares the arms.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/USER/ai-speed-testing/basalt-ab/scripts")
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/gate")
import abrun  # noqa: E402
import gate_speed as GS  # noqa: E402

SC = "/home/USER/ai-speed-testing/strata-compare"
GREEDY = {"temperature": 0.0, "top_p": 1.0, "top_k": 1, "min_p": 0.0}


def prompts():
    wl = json.load(open(abrun.WL))
    w = {x["id"][:2]: x for x in wl["normal"]}
    p4 = next(p for p in json.load(open(f"{SC}/prompts/speed.json")) if p["size"] == "4k" and p["rep"] == 0)
    return [{"id": "G-W1", "messages": w["W1"]["messages"]}, {"id": "G-W2", "messages": w["W2"]["messages"]},
            {"id": "G-P4K0", "messages": p4["messages"]}]


def main():
    base, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    rc = 0
    for p in prompts():
        job = dict(p, max_tokens=512, thinking=False, nonce=False)
        o0 = GS.log_size()
        try:
            rec = abrun.one(base, "greedy", job, GREEDY, {}, 0, f"{out}/greedy.jsonl", keep_text=True)
        except Exception as e:  # noqa: BLE001
            print(f"{p['id']}: failed ({type(e).__name__}: {e})", flush=True)
            rc = 1
            break
        time.sleep(2)   # the request's engine lines follow its last token
        e = GS.engine_lines(o0, GS.log_size())
        with open(f"{out}/greedy-engine.jsonl", "a") as f:
            f.write(json.dumps({"id": p["id"], "completion_tokens": rec.get("completion_tokens"), "engine": e}) + "\n")
        dr = e.get("drafts") or []
        print(f"{p['id']}: {rec.get('completion_tokens')} tokens, {len(rec.get('text') or '')} chars"
              + (f", drafts {dr[0]['kept']} of {dr[0]['offered']} kept" if dr else ""), flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
