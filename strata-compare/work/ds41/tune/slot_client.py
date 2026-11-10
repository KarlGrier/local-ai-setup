#!/usr/bin/env python3
"""slot_client.py BASE OUTDIR ENGINE_LOG - 10-25 (the user, B.2: "Chat-cache policy: make sure one-off calls (Jan title
generation and similar) and research conversations don't take one of the 4 RAM slots away from real chats. Use
STRATA_DS4_SLOT_MIN / SLOT_CAP / AUTO_PIN or the control layer"). One engine with slot keep on (the arm sets SLOT_CAP):
  1. four chats A-D, each a ~3K-token start then a follow-up, interleaved (A1 B1 C1 D1 A2 B2 C2 D2)
  2. nine one-offs: six title-style requests (a chat's first message + "a short title", max_tokens 64, as a client's title
     generation sends it - over STRATA_DS4_SLOT_MIN's 1,024 tokens, so the engine sets each aside like a chat) and three
     research-style calls (~6K tokens, "strata_checkpoint": false as deep-research's one-shot calls send them)
  3. back to each chat (A3 B3 C3 D3): reused tokens, TTFT, and where the engine took it back from (its "ds4 slots: took back
     ... from RAM / the folder" line)
256 tokens per chat reply. -> OUTDIR/conv.jsonl (conv.py's records) + OUTDIR/slots.json
"""
import json
import re
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/work/ds41/tune")
import conv  # noqa: E402

FOLLOW2 = "Thanks. Which one of those points would you check first on a PC with a 16 GB and an 8 GB GPU, and why? Keep it short."
FOLLOW3 = "Back to this one: in two sentences, what was the most important point you made above?"
TITLE = "\n\nGive the conversation above a short title of at most eight words. Reply with the title only."
RESEARCH = ("You are a research assistant. Read the source below and list every concrete claim it makes about memory use, "
            "with a one-line quote for each. Then rate how well supported each claim is (high / medium / low).\n\nSOURCE:\n")


def main():
    base, out, elog = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    t = conv.Turns(base, out, elog, f"{out}/no-slot-dir")
    src = conv.text(140000)
    chats = {c: [{"role": "system", "content": conv.SYS},
                 {"role": "user", "content": f"{conv.QS[0]}\n\n{src[i * 12000:(i + 1) * 12000]}"}] for i, c in enumerate("ABCD")}
    rows = []

    def turn(label, msgs, n=256, extra=None):
        normal = conv.abrun.NORMAL
        if extra:   # conv.chat spreads abrun.NORMAL into its body: the one-off's own fields ride along that way
            conv.abrun.NORMAL = dict(normal, **extra)
        try:
            r = t.turn(label, msgs, n)
        finally:
            conv.abrun.NORMAL = normal
        rows.append(label)
        return r

    for c in "ABCD":
        chats[c].append({"role": "assistant", "content": turn(f"{c}1 chat start", chats[c])["answer"]})
    for c in "ABCD":
        chats[c].append({"role": "user", "content": FOLLOW2})
        chats[c].append({"role": "assistant", "content": turn(f"{c}2 chat follow-up", chats[c])["answer"]})
    for i in range(6):
        c = "ABCD"[i % 4]
        turn(f"T{i + 1} title-style one-off (chat {c}'s first message)",
             [{"role": "user", "content": chats[c][1]["content"] + TITLE + ("" if i < 4 else f" (variant {i})")}], 64)
    for i in range(3):
        turn(f"R{i + 1} research-style one-off (strata_checkpoint false)",
             [{"role": "user", "content": RESEARCH + src[48000 + i * 24000:48000 + (i + 1) * 24000]}], 256,
             extra={"strata_checkpoint": False})   # (the server sends ckpt=0; dsv41 does not read it - the test shows the effect)
    back = []
    for c in "ABCD":
        chats[c].append({"role": "user", "content": FOLLOW3})
        r = turn(f"{c}3 back to chat {c}", chats[c])
        chats[c].append({"role": "assistant", "content": r["answer"]})
        back.append(f"{c}3 back to chat {c}")
    recs = {}
    for line in open(f"{out}/conv.jsonl"):
        x = json.loads(line)
        recs[x["turn"]] = x
    res = {"back": []}
    for label in back:
        x = recs.get(label, {})
        src_ = next((m.group(1) for l in x.get("engine_lines", []) for m in [re.search(r"took back .* from (RAM|the folder)", l)] if m), None)
        res["back"].append({"turn": label, "prompt_tokens": x.get("prompt_tokens"), "reused": x.get("reused"), "read": x.get("read"),
                            "ttft_s": x.get("ttft_s"), "from": src_, "engine_rss_mb": x.get("engine_rss_mb")})
    res["from_ram"] = sum(1 for b in res["back"] if b["from"] == "RAM")
    res["from_folder"] = sum(1 for b in res["back"] if b["from"] == "the folder")
    json.dump(res, open(f"{out}/slots.json", "w"), indent=1)
    print(f"slots: back to the 4 chats after 9 one-offs - {res['from_ram']} from RAM, {res['from_folder']} from the folder; "
          + "; ".join(f"{b['turn'][:2]}: {b['prompt_tokens']} = {b['reused']} reused + {b['read']} read, TTFT {b['ttft_s']} s, "
                      f"from {b['from']}" for b in res["back"]), flush=True)


if __name__ == "__main__":
    main()
