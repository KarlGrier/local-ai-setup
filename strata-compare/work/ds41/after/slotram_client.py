#!/usr/bin/env python3
"""slotram_client.py BASE OUTDIR ENGINE_LOG - 10-26: does STRATA_DS4_SLOT_RAM_GB move conversations to the folder? Run with
a tiny cap (0.03 GiB = 32 MB; a ~3K-token conversation is ~13-14 MB in RAM) and the count cap 16: chats A, B, C, D (one
request each, ~3,000 prompt tokens, max_tokens 64 as in slotfill.py), then A continued.
Expected: B sets A aside (1 in RAM), C sets B aside (2 in RAM, ~27 MB), D sets C aside (3 would be ~40 MB > 32: the least
recently used, A, goes to the folder -> 2 in RAM, 1 in the folder); A continued sets D aside (B to the folder) and takes A
back from the folder, reading only the new tokens. -> OUTDIR/slotram.json"""
import json
import os
import re
import sys
import time
import uuid

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import conv  # noqa: E402

SC = "/home/USER/ai-speed-testing/strata-compare"


def main():
    base, out, elog = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    sp = json.load(open(f"{SC}/prompts/speed.json"))
    src = max((p["messages"][0]["content"] for p in sp if p["size"] == "120k"), key=len)
    off = os.path.getsize(elog) if os.path.exists(elog) else 0
    sysm = {"role": "system", "content": "You are a helpful assistant."}
    chats = {}
    log = []
    for i, k in enumerate("ABCD"):
        chats[k] = [sysm, {"role": "user", "content": f"[slot test {k} {uuid.uuid4().hex[:8]}] Summarise the text below in one "
                           f"sentence.\n\n" + src[i * 11000:i * 11000 + 10500]}]
    steps = [("A", None), ("B", None), ("C", None), ("D", None), ("A", "One more sentence, please.")]
    for k, follow in steps:
        msgs = chats[k]
        if follow:
            msgs = msgs + [{"role": "assistant", "content": chats[k + "_answer"]}, {"role": "user", "content": follow}]
        r = conv.chat(base, msgs, 64)
        chats[k + "_answer"] = r["answer"]
        time.sleep(1.5)
        new = open(elog, errors="replace").read()[off:] if os.path.exists(elog) else ""
        off = os.path.getsize(elog) if os.path.exists(elog) else off
        rd = re.findall(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read", new)
        rec = {"chat": k + (" continued" if follow else ""), "prompt_tokens": r["usage"].get("prompt_tokens"),
               "reused_read": [[int(a), int(b), int(c)] for a, b, c in rd][:1], "ttft_s": r["ttft_s"],
               "slot_lines": [l[:200] for l in new.splitlines() if l.startswith("ds4 slots")]}
        log.append(rec)
        print(f"{rec['chat']}: prompt {rec['prompt_tokens']}, {rec['reused_read']}, TTFT {rec['ttft_s']} s; " +
              " | ".join(rec["slot_lines"]), flush=True)
    counts = [re.findall(r"; (\d+) in RAM, (\d+) in", " ".join(r["slot_lines"])) for r in log]
    after_d = counts[3][-1] if counts[3] else None
    back = " ".join(log[4]["slot_lines"])
    ok = bool(after_d) and after_d == ("2", "1") and "from the folder" in back and \
        bool(log[4]["reused_read"]) and log[4]["reused_read"][0][2] < 200
    res = {"ok": ok, "after_D_in_ram_folder": after_d, "continued_A": log[4], "steps": log}
    json.dump(res, open(f"{out}/slotram.json", "w"), indent=1)
    print(f"slotram: {'PASS' if ok else 'FAIL'} (after D: {after_d} in RAM / folder; A taken back: {back[:200]})", flush=True)


if __name__ == "__main__":
    main()
