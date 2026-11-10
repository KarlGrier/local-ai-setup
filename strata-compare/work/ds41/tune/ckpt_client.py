#!/usr/bin/env python3
"""ckpt_client.py BASE OUTDIR ENGINE_LOG [SLOTS] - 10-25 (the user: "a follow-up re-reading the whole ~24K chat shouldn't be
accepted as expected. The engine keeps checkpoints at the last prompt's end precisely for a client sending the history back
without the earlier reasoning ... Target: a follow-up re-reads only the last answer plus the new message").
Jan's request format (no system prompt, stream, reasoning_effort medium, the user's sampling; the history's assistant turns
as their answer text only, no reasoning_content), two chats one after the other on one engine:
  jan      Jan's two MCP tools (tools turn the template's drop_thinking off: the next turn shares the whole last prompt)
  notools  no tools (drop_thinking on: the next turn shares the last prompt up to its last token, "<think>" -> "</think>")
Each chat: a ~6K-token start (cap 4096), then 5 follow-ups whose caps alternate 512 / 4096. At 512 answer_room's budget (256)
ends the thinking and the server sends the short second pass; at 4096 the thinking ends on its own. So follow-ups come after
both kinds of answer.
Per follow-up: the prompt ids rendered here as the server renders them (its openai_to_messages, template and tokenizer;
checked against the reply's prompt_tokens), the shared prefix with the previous prompt, whether the history matches the
previous prompt up to its last user message (text), the previous request's engine passes and the checkpoints they leave
(ds4_model.cu: ck1 = before a prompt's last token, ck0 = its end, both rewritten by every pass; the anchor = the first pass's
ck1, set only with STRATA_DS4_SLOT_KEEP=1), the position the engine went back to (its first pass's "reused") and the tokens
it read. Target: read <= (prompt - shared) + 1 (the anchor sits one token before the shared end).
SLOTS (1/0, for the expected checkpoints only): whether the arm runs with STRATA_DS4_SLOT_KEEP=1.
-> OUTDIR/ckpt.jsonl (one record per request) + OUTDIR/ckpt.json
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

SC = Path("/home/USER/ai-speed-testing/strata-compare")
SV = SC / "strata-v024"     # the server code that renders (v0.2.6: the template and the request path are unchanged)
TOKDIR = SC / "models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF/pack-ist-das-2.00bpw/tokenizer"
sys.path[:0] = [str(SV), str(SV / "tools"), str(SC / "work/r22"), str(SC / "work/ds41/tune")]
import conv  # noqa: E402
import toolcall_check  # noqa: E402

NORMAL = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
LINE = re.compile(r"prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms.*?, (\d+) generated")
SLOTLINE = re.compile(r"[^\n]*(?:ds4 slots|taking a conversation back|going back to token|kept conversation)[^\n]*")
START = ("Here is part of a document about my inference engine. Read it and summarise its three most important points. "
         "Answer from this text only; do not search the web.\n\n")
FOLLOWS = ["Which of those three points would matter most on a PC with a 16 GB and an 8 GB GPU? Answer from the text only.",
           "Quote the one sentence from the text that best supports your last answer, and explain it in two sentences.",
           "What does the text leave unclear about that point? List up to three open questions.",
           "Which setting or number in the text would you test first, and how would you know it worked?",
           "Summarise our whole conversation so far in three short bullet points."]
CAPS = [512, 4096, 512, 4096, 512]
NO_TOOL = "Web search is not available in this test. Answer from the text above."


def renderer():
    """the server's own path from a chat-completions body to the engine's ids (Service.encode_prompt, no engine)"""
    import strata_tokenizer as ST
    from serve.frontend import ChatTemplate, openai_to_messages
    from serve.server import MockEngine, Service
    vocab = json.loads((TOKDIR / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tcfg = json.loads((TOKDIR / "tokenizer.json").read_text(encoding="utf-8"))
    tok = ST.Tokenizer(toks, (TOKDIR / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((TOKDIR / "token_type.json").read_text()), tcfg.get("pre") or "qwen35",
                       tcfg.get("special_ids") or None)
    svc = Service(MockEngine(tok, "ok"), tok, ChatTemplate(SV / "serve/fixtures/deepseek41/chat_template.jinja"))

    def render(body):
        msgs, tools, kw = openai_to_messages(body)
        return svc.render_prompt(msgs, tools, kw), svc.encode_prompt(msgs, tools, kw)
    return render


def lcp(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def ask(base, body):
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    t1, reasoning, content, calls, usage, finish = None, [], [], {}, None, None
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            usage = ev.get("usage") or usage
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                if t1 is None and (d.get("content") or d.get("reasoning_content") or d.get("reasoning") or d.get("tool_calls")):
                    t1 = time.monotonic()
                reasoning.append(d.get("reasoning_content") or d.get("reasoning") or "")
                content.append(d.get("content") or "")
                for tc in d.get("tool_calls") or []:
                    c = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                    c["id"] = tc.get("id") or c["id"]
                    f = tc.get("function") or {}
                    c["name"] += f.get("name") or ""
                    c["args"] += f.get("arguments") or ""
                finish = ch.get("finish_reason") or finish
    return {"ttft_s": round(t1 - t0, 2) if t1 else None, "total_s": round(time.monotonic() - t0, 1),
            "reasoning": "".join(reasoning), "answer": "".join(content), "calls": [calls[k] for k in sorted(calls)],
            "usage": usage or {}, "finish": finish}


def checks(passes, slots):
    """the checkpoints the previous request leaves (expected, from its passes): ck0 / ck1 of its last pass, and with slots
    the anchor - ck1 of the last pass that did not continue the state in place (a re-read continuation moves it)"""
    if not passes:
        return {}
    last = passes[-1]
    out = {"ck0": last[0], "ck1": last[0] - 1}
    if slots:
        anchor = passes[0][0] - 1
        for prev, p in zip(passes, passes[1:]):
            if p[1] < prev[0] + prev[4] - 1:            # this pass went back instead of going on in place
                anchor = p[0] - 1
        out["anchor"] = anchor
    return out


def main():
    base, out, elog = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    slots = len(sys.argv) > 4 and sys.argv[4] == "1"
    render = renderer()
    src = conv.text(60000)
    recs = []
    for chat, tools, doc in (("jan", toolcall_check.jan_tools(), src[:24000]), ("notools", None, src[24000:48000])):
        msgs = [{"role": "user", "content": START + doc}]
        prev = None
        plan = [("start", 4096)] + [(f"F{i + 1}", c) for i, c in enumerate(CAPS)]
        step = 0
        while step < len(plan):
            label, cap = plan[step]
            body = {"model": "x", "messages": msgs, "max_tokens": cap, "stream": True,
                    "stream_options": {"include_usage": True}, "reasoning_effort": "medium", **NORMAL}
            if tools:
                body["tools"] = tools
            text, ids = render(body)
            off = Path(elog).stat().st_size
            r = ask(base, body)
            time.sleep(1.5)                               # the engine's lines (and any slot write) after the reply
            new = Path(elog).read_text(encoding="utf-8", errors="replace")[off:]
            passes = [[int(a), int(b), int(c), float(d), int(e)] for a, b, c, d, e in LINE.findall(new)]
            rec = {"chat": chat, "turn": label, "cap": cap, "prompt": len(ids),
                   "prompt_server": r["usage"].get("prompt_tokens"), "passes": passes, "budget_hit": len(passes) > 1,
                   "ttft_s": r["ttft_s"], "total_s": r["total_s"], "finish": r["finish"], "calls": [c["name"] for c in r["calls"]],
                   "thinking_chars": len(r["reasoning"]), "answer_chars": len(r["answer"]),
                   "slot_lines": [x[:220] for x in SLOTLINE.findall(new)]}
            rec["render_ok"] = rec["prompt_server"] == len(ids)
            if prev is not None:
                head = prev["text"][:prev["text"].rfind("<｜Assistant｜>")]   # the previous prompt up to its last user turn's end
                hist_ok = text.startswith(head)
                diff = None
                if not hist_ok:
                    i = lcp(head, text)
                    diff = {"at_char": i, "prev": head[max(0, i - 40):i + 40], "new": text[max(0, i - 40):i + 40]}
                shared = lcp(prev["ids"], ids)
                ck = checks(prev["passes"], slots)
                lim = min(shared, len(ids) - 1)
                back = [v for v in ck.values() if v <= lim]
                first = passes[0] if passes else None
                rec.update({"prev_prompt": len(prev["ids"]), "prev_passes": prev["passes"],
                            "after": "a budget-hit answer (2 passes)" if len(prev["passes"]) > 1 else "a normal answer (1 pass)",
                            "shared": shared, "history_ok": hist_ok, "history_diff": diff, "checks_expected": ck,
                            "restorable_expected": max(back) if back else None,
                            "went_back_to": first[1] if first else None, "read": first[2] if first else None,
                            "target_read": len(ids) - shared})
                rec["verdict"] = None if first is None else ("ok" if first[2] <= rec["target_read"] + 1 else "RE-READ")
            recs.append(rec)
            with open(f"{out}/ckpt.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"{chat} {label} (cap {cap}): prompt {rec['prompt']} (server {rec['prompt_server']}), passes "
                  f"{[p[:3] for p in passes]} (prompt, reused, read)"
                  + (f"; after {rec['after']}: shared {rec['shared']} of the previous {rec['prev_prompt']}, history "
                     f"{'matches' if rec['history_ok'] else 'DIFFERS'}, expected checkpoints {rec['checks_expected']}, went back "
                     f"to {rec['went_back_to']}, read {rec['read']} (target {rec['target_read']}) -> {rec['verdict']}, "
                     f"TTFT {rec['ttft_s']} s" if prev is not None else f", TTFT {rec['ttft_s']} s"), flush=True)
            prev = {"ids": ids, "text": text, "passes": passes}
            if r["calls"]:                                # a tool call despite the instruction: answered, then the same step again
                msgs = msgs + [{"role": "assistant", "content": r["answer"] or "",
                                "tool_calls": [{"id": c["id"] or f"call_{i}", "type": "function",
                                                "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                                               for i, c in enumerate(r["calls"])]}] + \
                    [{"role": "tool", "tool_call_id": c["id"] or f"call_{i}", "content": NO_TOOL} for i, c in enumerate(r["calls"])]
                if label.count("+tool") < 2:
                    plan[step] = (label + "+tool", cap)
                    continue
                step += 1                                 # (a third call in a row: on to the next follow-up)
                if step < len(plan):
                    msgs.append({"role": "user", "content": FOLLOWS[step - 1]})
                continue
            msgs = msgs + [{"role": "assistant", "content": r["answer"]}]
            step += 1
            if step < len(plan):
                msgs.append({"role": "user", "content": FOLLOWS[step - 1]})
    fu = [x for x in recs if x.get("verdict")]
    res = {"slots": slots, "followups": len(fu), "ok": sum(x["verdict"] == "ok" for x in fu),
           "re_read": sum(x["verdict"] == "RE-READ" for x in fu), "render_mismatch": sum(not x["render_ok"] for x in recs),
           "history_differs": sum(x.get("history_ok") is False for x in fu)}
    for kind in ("a budget-hit answer (2 passes)", "a normal answer (1 pass)"):
        xs = [x for x in fu if x["after"] == kind]
        res[f"after {kind}"] = {"n": len(xs), "ok": sum(x["verdict"] == "ok" for x in xs),
                                "mean_read": round(sum(x["read"] for x in xs) / len(xs)) if xs else None,
                                "mean_target": round(sum(x["target_read"] for x in xs) / len(xs)) if xs else None,
                                "mean_ttft_s": round(sum(x["ttft_s"] or 0 for x in xs) / len(xs), 2) if xs else None}
    res["verdict"] = "PASS" if fu and res["ok"] == len(fu) else "FAIL"
    json.dump(res, open(f"{out}/ckpt.json", "w"), indent=1)
    print(f"follow-up reads ({'slot keep on' if slots else 'slot keep off'}): {res['verdict']} - {res['ok']} of {len(fu)} read only "
          f"the last answer + the new message; " + "; ".join(
              f"after {k[6:]}: {v['ok']}/{v['n']} ok, read {v['mean_read']} (target {v['mean_target']}), TTFT {v['mean_ttft_s']} s"
              for k, v in res.items() if k.startswith("after ")) +
          f"; render mismatches {res['render_mismatch']}, history differs {res['history_differs']}", flush=True)


if __name__ == "__main__":
    main()
