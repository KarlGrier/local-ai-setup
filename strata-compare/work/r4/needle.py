#!/usr/bin/env python3
"""needle.py — round 4, item 2 (practical check): facts buried at several depths in long documents, asked back.

  build                      write work/r4/needle/<size>-r<k>.json (sizes 32k/64k/120k x runs 0-2): the round-1 speed
                             corpus (source files and license texts) cut to the size, with 5 short "field log" files
                             inserted at depths ~2/25/50/75/98 % (jittered per run); each names a device, a 6-digit
                             calibration code and the person who signed it (fresh random facts per document).
  ask --base URL --label L   send each document + the question (stream, no sampling fields: the server's defaults =
                             0.6/0.95/20/0.05, reasoning xhigh), grade the 10 answers (5 codes, 5 names), append to
                             results/needle.jsonl and print a line per request.
Both engines get byte-identical prompts (the same chat messages; both use the model's own chat template)."""
import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = WS / "work/r4/needle"
SIZES = {"32k": 32768, "64k": 65536, "120k": 122880}
DEPTHS = [0.02, 0.25, 0.50, 0.75, 0.98]
FIRST = ["Mirela", "Tobias", "Ingrid", "Kofi", "Anouk", "Ravi", "Selma", "Dmitri", "Yuki", "Oluwaseun", "Beatriz",
         "Henrik", "Zainab", "Lorcan", "Priya", "Matteo", "Astrid", "Kwame", "Noor", "Emil"]
LAST = ["Okonkwo", "Vasquez-Lind", "Haldorsen", "Brightwater", "Nakashima", "Ferreira", "Castellanos", "Oyelaran",
        "Lindqvist", "Marchetti", "Achterberg", "Sørensen", "Kowalczyk", "Abernathy", "Ranganathan", "Duval"]
DEVICES = ["Harrowgate spectrometer", "Pellucid tide gauge", "Kestrel seismograph", "Ashdown particle counter",
           "Morrow anemometer", "Varkeny hygrometer", "Tallis magnetometer", "Quillon pyranometer",
           "Brennock turbidimeter", "Castor radiometer", "Oriel barograph", "Fenwick lysimeter"]


def tokenizer():
    sys.path.insert(0, str(WS / "strata-cstar3")); sys.path.insert(0, str(WS / "strata-cstar3/serve"))
    sys.path.insert(0, str(WS / "strata-cstar3/tools"))
    from serve.frontend import ChatTemplate
    import strata_tokenizer as ST
    tp = WS / "strata-v0115/packs/iq3_s/tokenizer"
    vocab = json.loads((tp / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = ST.Tokenizer(toks, (tp / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((tp / "token_type.json").read_text()))
    tpl = ChatTemplate(tp / "chat_template.jinja" if (tp / "chat_template.jinja").exists()
                       else WS / "strata-cstar3/serve/chat_template.jinja")
    return tok, tpl


def build():
    tok, tpl = tokenizer()
    speed = json.load(open(WS / "prompts/speed.json"))
    body = next(x for x in speed if x["size"] == "120k" and x["rep"] == 0)["messages"][0]["content"]
    body = body[body.index("\n") + 1: body.rindex("\n\nTask:")]          # the corpus without the header and task
    blocks = re.split(r"(?=\n===== FILE: )", body)                        # whole files, so needles sit between files
    OUT.mkdir(parents=True, exist_ok=True)
    for size, target in SIZES.items():
        for run in range(3):
            rng = random.Random(f"{size}-{run}")
            devs = rng.sample(DEVICES, 5)
            facts = []
            for d in devs:
                name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                while any(f['name'] == name for f in facts):
                    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                facts.append({"device": d, "code": f"{rng.randint(100000, 999999)}", "name": name})
            question = ("Task: The collection above contains five short field-log files. Using only the collection, "
                        "answer:\n" + "\n".join(
                            f"{i + 1}. What is the calibration code of the {f['device']}, and who signed its field log?"
                            for i, f in enumerate(facts)) +
                        "\nReply with exactly five lines in the form `N. <code> - <full name>`.")
            def needle(f):
                slug = f["device"].split()[0].lower()
                return (f"\n===== FILE: /srv/fieldlogs/{slug}-calibration.txt =====\n\nField log. The calibration "
                        f"code of the {f['device']} is {f['code']}. This field log was signed by {f['name']}.\n")
            rng_j = [rng.uniform(-0.02, 0.02) if 0 < i < 4 else 0.0 for i in range(5)]

            def render(nchars, text_only=False):
                filler = body[:nchars]
                filler = filler[:filler.rfind("\n") + 1] if "\n" in filler else filler
                parts, prev = [], 0
                for i, f in enumerate(facts):             # each fact at the line boundary nearest its depth
                    want = int(len(filler) * (DEPTHS[i] + rng_j[i]))
                    cut = filler.rfind("\n", 0, want) + 1 if want > 0 else 0
                    cut = max(cut, prev)
                    parts += [filler[prev:cut], needle(f)]
                    prev = cut
                parts.append(filler[prev:])
                doc = "Below is a collection of source files and license texts.\n" + "".join(parts) + "\n\n" + question
                if text_only:
                    return doc
                return len(tok.encode(tpl.render([{"role": "user", "content": doc}], tools=None), parse_special=True))
            lo, hi = 1000, len(body)                      # binary search on the corpus length (characters)
            while hi - lo > 200:
                mid = (lo + hi) // 2
                if render(mid) <= target:
                    lo = mid
                else:
                    hi = mid
            doc = render(lo, text_only=True)
            ntok = render(lo)
            depth_tok = []                                # measured depth of each fact, in tokens
            for f in facts:
                depth_tok.append(round(len(tok.encode(doc[:doc.index(f["code"])], parse_special=False)) / ntok, 3))
            json.dump({"size": size, "run": run, "prompt_tokens": ntok, "facts": facts, "depths": depth_tok,
                       "messages": [{"role": "user", "content": doc}]}, open(OUT / f"{size}-r{run}.json", "w"))
            print(size, run, ntok, "tokens, depths", depth_tok)


def grade(text, facts):
    lines = {}
    for m in re.finditer(r"(?m)^\s*\**\s*([1-5])[.)]\s*(.+)$", text or ""):
        lines.setdefault(int(m.group(1)), m.group(2))
    res = []
    for i, f in enumerate(facts, 1):
        ln = lines.get(i, "")
        res.append({"code": f["code"] in ln, "name": f["name"].lower() in ln.lower()})
    return res


def ask(base, label, sizes, runs, max_tokens):
    rows = []
    for size in sizes:
        for run in runs:
            d = json.load(open(OUT / f"{size}-r{run}.json"))
            # the answer must fit in the 131,072-token context next to the prompt (a 120K document leaves ~8,100)
            body = {"model": "x", "messages": d["messages"], "stream": True,
                    "max_tokens": min(max_tokens, 131072 - 8 - d["prompt_tokens"] - 64)}
            t0 = time.time(); ttft = None; content = ""; reasoning = ""; finish = None; usage = {}
            err = None
            try:
                with requests.post(f"{base}/v1/chat/completions", json=body, stream=True, timeout=3600) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if not line.startswith(b"data: ") or line == b"data: [DONE]":
                            continue
                        ev = json.loads(line[6:])
                        if "error" in ev:
                            err = str(ev["error"]); break
                        if ev.get("usage"):
                            usage = ev["usage"]
                        for ch in ev.get("choices", []):
                            dl = ch.get("delta", {})
                            piece = (dl.get("content") or "") + (dl.get("reasoning_content") or "")
                            if piece and ttft is None:
                                ttft = time.time() - t0
                            content += dl.get("content") or ""
                            reasoning += dl.get("reasoning_content") or ""
                            finish = ch.get("finish_reason") or finish
            except Exception as e:  # noqa: BLE001
                err = repr(e)
            g = grade(content, d["facts"])
            rec = {"label": label, "size": size, "run": run, "prompt_tokens": d["prompt_tokens"], "depths": d["depths"],
                   "ttft_s": ttft, "total_s": time.time() - t0, "finish": finish, "error": err,
                   "reasoning_chars": len(reasoning), "answer": content.strip()[-800:],
                   "codes_ok": sum(x["code"] for x in g), "names_ok": sum(x["name"] for x in g), "per_fact": g,
                   "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(WS / "results/needle.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
            rows.append(rec)
            print(f"[{label}] {size} r{run}: ttft {ttft if ttft is None else round(ttft, 1)} s, total "
                  f"{rec['total_s']:.0f} s, finish {finish}, codes {rec['codes_ok']}/5, names {rec['names_ok']}/5 "
                  f"{'' if not err else 'ERROR ' + err}", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "ask"])
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--label", default="")
    ap.add_argument("--sizes", default="32k,64k,120k")
    ap.add_argument("--runs", default="0,1,2")
    ap.add_argument("--max-tokens", type=int, default=12288)
    a = ap.parse_args()
    if a.mode == "build":
        build()
    else:
        ask(a.base, a.label, a.sizes.split(","), [int(x) for x in a.runs.split(",")], a.max_tokens)


if __name__ == "__main__":
    main()
