#!/usr/bin/env python3
"""pic_budget.py - round 22 pictures (the user, 10-21: "the CPU reader shrinks images to ~300 tokens and misreads small
text. In the next gap, test a 4K screenshot with small text at a larger image budget (e.g. ~1,000 and ~2,000 tokens), on
the CPU reader and on the 4060 Ti reader: time to first word, total time, whether the small text is read correctly, and
the decode cost of the GPU reader. Then recommend a default for screenshots with text.")

  pic_budget.py make OUTDIR      the test screenshot (3840x2160 PNG, a synthetic build dashboard: big stat cards, a
                                 30-row table at 26 px and a log pane at 18 px) + truth.json (every row and log line)
  pic_budget.py run URL OUTDIR LABEL
                                 against a running server: (1) "describe" twice on fresh conversations (seconds to the
                                 first answer token and to the end; the second may reuse the encoded picture), (2) one
                                 "transcribe" request: the table's first 13 rows and the log pane's 6 lines, scored
                                 field by field against truth.json. One JSON line per request to OUTDIR/LABEL.jsonl.
  pic_budget.py score OUTDIR LABEL...   the table: times, prompt tokens, row/field/log accuracy per label

Requests go the way Jan sends a pasted screenshot (OpenAI chat, streamed, a text part + an image_url data URI, thinking
on, reasoning effort medium, the server's sampling). Everything in the picture is made up.
"""
from __future__ import annotations

import base64
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

W, H = 3840, 2160
ROWS, ASK_ROWS, ASK_LOGS = 30, 13, 6


def font(sz):
    from PIL import ImageFont
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def make(out: Path):
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(20261021)
    img = Image.new("RGB", (W, H), (30, 32, 38)); d = ImageDraw.Draw(img)
    f, fb, fs, fl = font(26), font(44), font(22), font(18)
    d.rectangle([0, 0, W, 90], fill=(45, 48, 58))
    d.text((30, 20), "Build Monitor - nightly pipeline #5318", font=fb, fill=(230, 230, 230))
    d.rectangle([0, 90, 700, H], fill=(38, 40, 48))
    for i, name in enumerate(["Overview", "Builds", "Tests", "Deploys", "Alerts", "Settings"]):
        d.text((40, 140 + i * 70), name, font=f, fill=(120, 200, 255) if i == 1 else (200, 200, 210))
    rows = []
    for r in range(ROWS):
        st = rnd.choice(["passed"] * 6 + ["failed"])
        total = rnd.choice([1240, 1240, 1252])
        rows.append({"num": 5318 - r,
                     "branch": rnd.choice(["main", "release/2.4", "feat/cache", "fix/login", "docs", "perf/io"]),
                     "status": st, "duration": f"{rnd.randint(6, 19)}m {rnd.randint(0, 59):02d}s",
                     "tests": f"{rnd.randint(1100, total) if st == 'failed' else total}/{total}"})
    n_fail = sum(r["status"] == "failed" for r in rows)
    cards = [("Builds today", str(ROWS)), ("Passed", str(ROWS - n_fail)), ("Failed", str(n_fail)), ("Median time", "11m 42s")]
    for i, (k, v) in enumerate(cards):
        x = 760 + i * 760; d.rectangle([x, 130, x + 700, 380], fill=(50, 54, 66))
        d.text((x + 30, 160), k, font=f, fill=(170, 170, 180)); d.text((x + 30, 230), v, font=font(90), fill=(240, 240, 240))
    d.text((760, 430), "Recent builds", font=fb, fill=(230, 230, 230))
    d.text((760, 510), f"{'#':>6}  {'branch':<14}{'status':<9}{'duration':>9}  {'tests':>10}", font=f, fill=(150, 150, 160))
    for i, r in enumerate(rows):
        line = f"{r['num']:>6}  {r['branch']:<14}{r['status']:<9}{r['duration']:>9}  {r['tests']:>10}"
        d.text((760, 560 + i * 46), line, font=f, fill=(235, 120, 120) if r["status"] == "failed" else (210, 210, 215))
    # the log pane, smaller text (18 px)
    d.rectangle([2000, 430, 3800, 1000], fill=(22, 24, 28)); d.text((2020, 445), "build.log (tail)", font=fs, fill=(170, 170, 180))
    logs = []
    for i in range(ASK_LOGS + 4):
        t = f"{rnd.randint(0, 23):02d}:{rnd.randint(0, 59):02d}:{rnd.randint(0, 59):02d}"
        lvl = rnd.choice(["INFO", "INFO", "WARN", "ERROR"])
        msg = rnd.choice(["cache hit ratio {:.1f}%".format(rnd.uniform(60, 99)), f"retry {rnd.randint(1, 5)}/5 fetching artifact",
                          f"test shard {rnd.randint(1, 16)} took {rnd.randint(20, 400)} s", f"disk free {rnd.randint(5, 90)} GB",
                          f"queue depth {rnd.randint(0, 40)}", f"exit code {rnd.choice([0, 1, 2, 137])}"])
        logs.append(f"{t} {lvl:<5} {msg}")
    for i, l in enumerate(logs):
        d.text((2020, 490 + i * 30), l, font=fl, fill=(200, 200, 200))
    d.rectangle([2000, 1040, 3800, 2100], fill=(42, 45, 55)); d.text((2020, 1060), "Build time (minutes), last 14 days", font=fs, fill=(200, 200, 210))
    vals = [rnd.randint(9, 14) for _ in range(14)]
    for i, v in enumerate(vals):
        x = 2060 + i * 120; d.rectangle([x, 2040 - v * 65, x + 70, 2040], fill=(90, 160, 240)); d.text((x + 15, 2050), str(v), font=fs, fill=(200, 200, 210))
    img.save(out / "screenshot-text-3840x2160.png")
    truth = {"cards": dict(cards), "rows": rows, "logs": logs, "bars": vals}
    (out / "truth.json").write_text(json.dumps(truth, indent=1))
    print(f"wrote {out}/screenshot-text-3840x2160.png and truth.json ({n_fail} failed rows)")


DESCRIBE = "I pasted a screenshot. What does it show? Describe it briefly, and give the key numbers you can read."
TRANSCRIBE = (f"I pasted a screenshot. Transcribe exactly, character for character: (1) the first {ASK_ROWS} rows of the "
              "'Recent builds' table, one row per line as: number | branch | status | duration | tests; (2) the first "
              f"{ASK_LOGS} lines of the build.log pane, one per line, exactly as shown. No commentary.")


def ask(url, img_b64, text, n):
    body = {"model": "x", "stream": True, "stream_options": {"include_usage": True}, "reasoning_effort": "medium",
            "messages": [{"role": "user", "content": [{"type": "text", "text": text},
                                                      {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img_b64}}]}]}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic(); first = None; usage = None; ans = []
    with urllib.request.urlopen(req, timeout=1800) as r:
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
                c = (ch.get("delta") or {}).get("content")
                if c:
                    first = first or time.monotonic(); ans.append(c)
    return {"n": n, "first_answer_token_s": round(first - t0, 2) if first else None, "total_s": round(time.monotonic() - t0, 2),
            "usage": usage, "answer": "".join(ans)}


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def score(truth, answer):
    lines = [l for l in answer.splitlines() if l.strip()]
    rows_ok = fields_ok = 0
    for r in truth["rows"][:ASK_ROWS]:
        cand = next((l for l in lines if re.search(rf"\b{r['num']}\b", l)), None)
        if cand is None:
            continue
        parts = [norm(p) for p in re.split(r"\s*\|\s*", cand.strip().strip("|"))]
        want = [str(r["num"]), r["branch"], r["status"], r["duration"], r["tests"]]
        ok = sum(1 for w in want if norm(w) in parts or norm(w) in norm(cand))
        fields_ok += ok; rows_ok += int(ok == len(want))
    logs_ok = sum(1 for l in truth["logs"][:ASK_LOGS] if any(norm(l) == norm(x) for x in lines))
    return {"rows_exact": rows_ok, "rows": ASK_ROWS, "fields_ok": fields_ok, "fields": ASK_ROWS * 5,
            "logs_exact": logs_ok, "logs": ASK_LOGS}


def run(url, out: Path, label):
    img = out / "screenshot-text-3840x2160.png"; truth = json.loads((out / "truth.json").read_text())
    b64 = base64.b64encode(img.read_bytes()).decode()
    with open(out / f"{label}.jsonl", "a") as fo:
        for n in (1, 2):
            rec = {"label": label, "kind": "describe", **ask(url, b64, DESCRIBE, n)}
            fo.write(json.dumps(rec) + "\n"); print(json.dumps({k: rec[k] for k in ("kind", "n", "first_answer_token_s", "total_s")}
                                                               | {"prompt_tokens": (rec["usage"] or {}).get("prompt_tokens")}), flush=True)
        rec = {"label": label, "kind": "transcribe", **ask(url, b64, TRANSCRIBE, 3)}
        rec["score"] = score(truth, rec["answer"])
        fo.write(json.dumps(rec) + "\n")
        print(json.dumps({"kind": "transcribe", "total_s": rec["total_s"], **rec["score"]}), flush=True)


def table(out: Path, labels):
    print("| reader / budget | prompt tokens | first word, cold (s) | total, cold (s) | first word, repeat (s) | "
          "table rows exact | table fields | log lines exact | transcribe total (s) |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for lb in labels:
        p = out / f"{lb}.jsonl"
        if not p.exists():
            print(f"| {lb} | - |"); continue
        recs = [json.loads(l) for l in p.read_text().splitlines()]
        d = [r for r in recs if r["kind"] == "describe"]; t = next((r for r in recs if r["kind"] == "transcribe"), None)
        s = t["score"] if t else {}
        print(f"| {lb} | {(d[0]['usage'] or {}).get('prompt_tokens') if d else '-'} | {d[0]['first_answer_token_s'] if d else '-'} | "
              f"{d[0]['total_s'] if d else '-'} | {d[1]['first_answer_token_s'] if len(d) > 1 else '-'} | "
              f"{s.get('rows_exact', '-')}/{s.get('rows', '-')} | {s.get('fields_ok', '-')}/{s.get('fields', '-')} | "
              f"{s.get('logs_exact', '-')}/{s.get('logs', '-')} | {t['total_s'] if t else '-'} |")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "make":
        make(Path(sys.argv[2]))
    elif cmd == "run":
        run(sys.argv[2], Path(sys.argv[3]), sys.argv[4])
    elif cmd == "score":
        table(Path(sys.argv[2]), sys.argv[3:])
    else:
        print(__doc__); sys.exit(2)
