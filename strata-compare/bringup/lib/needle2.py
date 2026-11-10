#!/usr/bin/env python3
"""needle2.py — round 5, phase 5: a harder long-document recall set (build once, ask on each engine).

  build                      bringup/out/needles/needle2/<size>-r<k>.json (32k/64k/120k x runs 0-3): the round-1 speed corpus (source
                             files, license texts) cut to the size, with short "memo" files inserted between files at
                             spread, jittered depths. Six questions per document:
                               1. 3-hop: device -> technician (memo 1) -> laboratory (memo 2) -> door code (memo 3),
                                  three memos at different depths
                               2. 2-hop: project -> budget holder (memo 4) -> phone extension (memo 5)
                               3./4. near-duplicate distractors: two sensor units whose numbers differ by one digit,
                                  with serial codes that differ by one digit, in two memos far apart; asked for one
                               5. which of two sentences is in the document: a memo sentence vs the same with one digit
                                  changed (order random)
                               6. the same for an ordinary line of the corpus that contains a number
  ask --base URL --label L   send each document + the questions (stream, no sampling fields: the server's defaults =
                             your 0.6/0.95/20/0.05, reasoning xhigh), grade, append to bringup/out/results/needle2.jsonl.
Both engines get byte-identical chat messages."""
import argparse
import os
import json
import random
import re
import sys
import time
from pathlib import Path

import requests

WS = Path("/home/USER/ai-speed-testing/strata-compare")
OUT = Path(os.environ.get("NEEDLE_DIR", WS / "bringup/out/needles/needle2"))   # bring-up: the generated set
RES = WS / "bringup/out/results/needle2.jsonl"
SIZES = {"32k": 32768, "64k": 65536, "120k": 122880}
FIRST = ["Mirela", "Tobias", "Ingrid", "Kofi", "Anouk", "Ravi", "Selma", "Dmitri", "Yuki", "Oluwaseun", "Beatriz",
         "Henrik", "Zainab", "Lorcan", "Priya", "Matteo", "Astrid", "Kwame", "Noor", "Emil"]
LAST = ["Okonkwo", "Vasquez-Lind", "Haldorsen", "Brightwater", "Nakashima", "Ferreira", "Castellanos", "Oyelaran",
        "Lindqvist", "Marchetti", "Achterberg", "Kowalczyk", "Abernathy", "Ranganathan", "Duval"]
DEVICES = ["Harrowgate spectrometer", "Pellucid tide gauge", "Kestrel seismograph", "Ashdown particle counter",
           "Morrow anemometer", "Varkeny hygrometer", "Tallis magnetometer", "Quillon pyranometer",
           "Brennock turbidimeter", "Castor radiometer", "Oriel barograph", "Fenwick lysimeter"]
LABS = ["Kellsbrook", "Marrowdene", "Ostvale", "Pinecrest", "Quarrymoor", "Ravensholt", "Saltmere", "Thornby"]
PROJECTS = ["Heron", "Lantern", "Basalt", "Cormorant", "Juniper", "Meridian", "Tamarisk", "Vireo"]


def tokenizer():
    tree = Path(os.environ.get("STRATA_SERVE_TREE", WS / "strata-cstar4"))   # bring-up: the engine checkout's serve/tools
    sys.path.insert(0, str(tree)); sys.path.insert(0, str(tree / "serve")); sys.path.insert(0, str(tree / "tools"))
    from serve.frontend import ChatTemplate
    import strata_tokenizer as ST
    tp = Path(os.environ.get("STRATA_TOKENIZER_DIR", WS / "strata-v0115/packs/iq3_s/tokenizer"))
    vocab = json.loads((tp / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(vocab)
    for t, i in vocab.items():
        toks[i] = t
    tok = ST.Tokenizer(toks, (tp / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((tp / "token_type.json").read_text()))
    return tok, ChatTemplate(tp / "chat_template.jinja")


def one_digit_change(rng, s):
    idx = [i for i, c in enumerate(s) if c.isdigit()]
    i = rng.choice(idx)
    d = rng.choice([x for x in "0123456789" if x != s[i]])
    return s[:i] + d + s[i + 1:]


def memo(path, text):
    return f"\n===== FILE: {path} =====\n\n{text}\n"


def build():
    tok, tpl = tokenizer()
    speed = json.load(open(WS / "prompts/speed.json"))
    body = next(x for x in speed if x["size"] == "120k" and x["rep"] == 0)["messages"][0]["content"]
    body = body[body.index("\n") + 1: body.rindex("\n\nTask:")]
    OUT.mkdir(parents=True, exist_ok=True)
    for size, target in SIZES.items():
        for run in range(4):
            rng = random.Random(f"needle2-{size}-{run}")
            names = rng.sample([f"{a} {b}" for a in FIRST for b in LAST], 3)
            dev, lab, proj = rng.choice(DEVICES), rng.choice(LABS), rng.choice(PROJECTS)
            door = f"{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
            ext = str(rng.randint(2000, 8999))
            u1 = rng.randint(1100, 8899)
            u2 = int(one_digit_change(rng, str(u1)))                  # the twin unit: one digit different
            s1 = str(rng.randint(100000, 999999))
            s2 = one_digit_change(rng, s1)                            # its serial: one digit different
            ask_unit = rng.choice([0, 1])
            order = rng.choice([1, 2])
            ship = f"#{rng.randint(10000, 99999)}"
            ship_day = f"{rng.randint(3, 27)} {rng.choice(['March', 'April', 'June', 'October'])}"
            true_sent = f"Spare-parts order {ship} left the warehouse on {ship_day} with {rng.randint(12, 96)} crates."
            false_sent = one_digit_change(rng, true_sent)
            memos = [  # (depth, file, text)
                (0.10, f"/srv/memos/wo-{u1 % 97:02d}.txt",
                 f"Work order memo. The {dev} was calibrated last week by technician {names[0]}."),
                (0.55, "/srv/memos/staff-assignments.txt",
                 f"Staff note. Technician {names[0]} is permanently assigned to the {lab} laboratory."),
                (0.90, f"/srv/memos/{lab.lower()}-access.txt",
                 f"Access memo. The door code of the {lab} laboratory is {door}."),
                (0.30, f"/srv/memos/project-{proj.lower()}.txt",
                 f"Project memo. The budget holder of Project {proj} is {names[1]}."),
                (0.78, "/srv/memos/phone-list.txt",
                 f"Phone list update. {names[1]} can be reached on extension {ext}."),
                (0.20, f"/srv/memos/sensor-{u1}.txt", f"Sensor memo. Sensor unit {u1} carries serial code {s1}."),
                (0.68, f"/srv/memos/sensor-{u2}.txt", f"Sensor memo. Sensor unit {u2} carries serial code {s2}."),
                (0.42, "/srv/memos/shipping.txt", f"Shipping memo. {true_sent}"),
            ]
            jit = [rng.uniform(-0.04, 0.04) for _ in memos]
            want_unit, want_serial = (u1, s1) if ask_unit == 0 else (u2, s2)

            def render(nchars, text_only=False):
                filler = body[:nchars]
                filler = filler[:filler.rfind("\n") + 1] if "\n" in filler else filler
                # Q6: an ordinary corpus line with a number (40-140 chars, unique), from ~ the middle third
                lines = [ln for ln in filler.split("\n") if 40 <= len(ln) <= 140 and re.search(r"\d", ln)
                         and filler.count(ln) == 1 and "=====" not in ln]
                lines = lines[len(lines) // 3: 2 * len(lines) // 3] or lines
                crng = random.Random(f"line-{size}-{run}")
                cline = crng.choice(lines)
                cfalse = one_digit_change(crng, cline)
                items = sorted(((d + j, f, t) for (d, f, t), j in zip(memos, jit)), key=lambda x: x[0])
                parts, prev = [], 0
                for d, f, t in items:
                    want = int(len(filler) * min(0.98, max(0.02, d)))
                    cut = filler.rfind("\n===== FILE:", 0, want)       # between files if one ends nearby,
                    if cut < prev or want - cut > 0.03 * len(filler):     # else at a line boundary
                        cut = filler.rfind("\n", 0, want) + 1
                    cut = max(cut, prev)
                    parts += [filler[prev:cut], memo(f, t)]
                    prev = cut
                parts.append(filler[prev:])
                a5, b5 = (true_sent, false_sent) if order == 1 else (false_sent, true_sent)
                o6 = crng.choice([1, 2])
                a6, b6 = (cline, cfalse) if o6 == 1 else (cfalse, cline)
                q = ("Task: The collection above also contains a few short memo files. Using only the collection, "
                     "answer:\n"
                     f"1. What is the door code of the laboratory where the technician who calibrated the {dev} "
                     "works?\n"
                     f"2. What is the phone extension of the budget holder of Project {proj}?\n"
                     f"3. What is the serial code of sensor unit {want_unit}?\n"
                     f"4. Which sensor unit carries the serial code {s2 if ask_unit == 0 else s1}?\n"
                     "5. Exactly one of these two sentences appears word for word in the collection. Which one?\n"
                     f"   (a) {a5}\n   (b) {b5}\n"
                     "6. Exactly one of these two lines appears word for word in the collection. Which one?\n"
                     f"   (a) {a6.strip()}\n   (b) {b6.strip()}\n"
                     "Reply with exactly six lines in the form `N. <answer>`: for 1-4 only the code, extension, "
                     "serial or unit number; for 5 and 6 only (a) or (b).")
                doc = "Below is a collection of source files and license texts.\n" + "".join(parts) + "\n\n" + q
                key = {"1": door, "2": ext, "3": want_serial, "4": str(u2 if ask_unit == 0 else u1),
                       "5": "a" if order == 1 else "b", "6": "a" if o6 == 1 else "b",
                       "wrong3": s2 if ask_unit == 0 else s1, "wrong4": str(u1 if ask_unit == 0 else u2)}
                if text_only:
                    return doc, key, items
                return len(tok.encode(tpl.render([{"role": "user", "content": doc}], tools=None), parse_special=True))
            lo, hi = 1000, len(body)
            while hi - lo > 200:
                mid = (lo + hi) // 2
                if render(mid) <= target:
                    lo = mid
                else:
                    hi = mid
            doc, key, items = render(lo, text_only=True)
            ntok = render(lo)
            depths = {}
            for d, f, t in items:
                depths[f] = round(len(tok.encode(doc[:doc.index(t)], parse_special=False)) / ntok, 3)
            json.dump({"size": size, "run": run, "prompt_tokens": ntok, "key": key, "depths": depths,
                       "messages": [{"role": "user", "content": doc}]}, open(OUT / f"{size}-r{run}.json", "w"))
            print(size, run, ntok, "tokens; depths", sorted(depths.values()))


def grade(text, key):
    lines = {}
    for m in re.finditer(r"(?m)^\s*\**\s*([1-6])[.)]\s*(.+)$", text or ""):
        lines.setdefault(m.group(1), m.group(2).strip())
    out = {}
    for q in "1234":
        ln = re.sub(r"[`*]", "", lines.get(q, ""))
        nums = re.findall(r"\d[\d-]*\d|\d", ln)
        ok = key[q] in nums or ln.strip() == key[q]
        if q in "34":
            ok = ok and key[f"wrong{q}"] not in nums
        out[q] = bool(ok)
    for q in "56":
        ln = lines.get(q, "").lower()
        m = re.search(r"\(?\b([ab])\b\)?", ln)
        out[q] = bool(m and m.group(1) == key[q])
    return out


def ask(base, label, sizes, runs, max_tokens, temperature=None):
    RES.parent.mkdir(parents=True, exist_ok=True)
    for size in sizes:
        for run in runs:
            d = json.load(open(OUT / f"{size}-r{run}.json"))
            body = {"model": "x", "messages": d["messages"], "stream": True,
                    "max_tokens": min(max_tokens, 131072 - 8 - d["prompt_tokens"] - 64)}
            if temperature is not None:        # your settings, sent explicitly (both engines sample alike)
                body.update(temperature=temperature, top_p=0.95, top_k=20, min_p=0.05)
            t0 = time.time(); ttft = None; content = ""; reasoning = ""; finish = None; err = None
            try:
                with requests.post(f"{base}/v1/chat/completions", json=body, stream=True, timeout=5400) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if not line.startswith(b"data: ") or line == b"data: [DONE]":
                            continue
                        ev = json.loads(line[6:])
                        if "error" in ev:
                            err = str(ev["error"]); break
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
            g = grade(content, d["key"])
            rec = {"label": label, "size": size, "run": run, "prompt_tokens": d["prompt_tokens"], "ttft_s": ttft,
                   "total_s": time.time() - t0, "finish": finish, "error": err, "reasoning_chars": len(reasoning),
                   "answer": content.strip()[-600:], "per_q": g, "score": sum(g.values()),
                   "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(RES, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"[{label}] {size} r{run}: ttft {ttft if ttft is None else round(ttft, 1)} s, total "
                  f"{rec['total_s']:.0f} s, finish {finish}, score {rec['score']}/6 {g} "
                  f"{'' if not err else 'ERROR ' + err}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "ask"])
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--label", default="")
    ap.add_argument("--sizes", default="32k,64k,120k")
    ap.add_argument("--runs", default="0,1,2,3")
    ap.add_argument("--max-tokens", type=int, default=12288)
    ap.add_argument("--temperature", type=float, default=None)
    a = ap.parse_args()
    if a.mode == "build":
        build()
    else:
        ask(a.base, a.label, a.sizes.split(","), [int(x) for x in a.runs.split(",")], a.max_tokens, a.temperature)


if __name__ == "__main__":
    main()
