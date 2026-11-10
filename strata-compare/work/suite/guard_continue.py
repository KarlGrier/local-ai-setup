#!/usr/bin/env python3
"""guard_continue.py - 2026-10-13, the user's guard continuation: did the coding answers that Strata's repeat guard
ended (one digit 256 times in a row, repeat_stop_tokens 256) recover when allowed to go on?  Not a fresh sample: the
same answer, continued.  For each case (label:item:run) the original request is sent again to a server whose OpenAI
path takes strata_prefix_ids (the measurement hook, appended after the rendered prompt = after
"<|im_start|>assistant\\n<think>\\n"), with the answer's own tokens up to the cut as the prefix: its reasoning text
re-encoded, plus the 256th repeat that the guard drew but did not emit.  The server runs with repeat_stop_tokens =
total - 256 (its run counter starts at 0 for the new tokens), so the whole run may reach --guard-total digits.
Request otherwise as the original (sampling, reasoning effort, messages); max_tokens = the original's minus the
prefix.  Result: label <label><suffix> = the original label's coding answers with the continued ones replaced
(reasoning = original + 256th digit + continuation; tokens counted over the whole answer); grade with
`run.sh regrade`.  --dry-run: the prefixes only (no requests).  Measurement only; the scored labels are untouched."""
import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "suite"))
sys.path.insert(0, str(WS / "strata-cstar171" / "tools"))
from msuite import runner  # noqa: E402
from msuite.backend_openai import OpenAIBackend  # noqa: E402
from msuite.common import answer_path, label_dir, now_iso, read_json, write_json  # noqa: E402
import strata_tokenizer as ST  # noqa: E402


def load_tok(d):
    d = Path(d)
    v = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
    toks = [None] * len(v)
    for k, i in v.items():
        toks[i] = k
    return ST.Tokenizer(toks, (d / "merges.txt").read_text(encoding="utf-8").split("\n"),
                        json.loads((d / "token_type.json").read_text()))


def trailing_run(text):
    m = re.search(r"(.)\1*$", text, re.S)
    return (m.group(1), len(m.group(0))) if m else ("", 0)


def longest_run(text):
    best = ("", 0)
    for m in re.finditer(r"(\d)\1{63,}", text):
        if len(m.group(0)) > best[1]:
            best = (m.group(1), len(m.group(0)))
    return best


ap = argparse.ArgumentParser()
ap.add_argument("--endpoint", default="http://127.0.0.1:8081")
ap.add_argument("--tokenizer", required=True)
ap.add_argument("--cases", required=True, help="label:item:run,... (coding items)")
ap.add_argument("--suffix", default="-cont1024")
ap.add_argument("--guard-total", type=int, default=1024)
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--sampling", help="JSON over the original request's sampling (2026-10-13: '{\"min_p\": 0}')")
ap.add_argument("--base-suffix", default="", help="the new label starts from <label><base-suffix>'s coding answers "
                                                  "(default: the original label's)")
a = ap.parse_args()
tok = load_tok(a.tokenizer)
items = {i["id"]: i for i in runner.load_items(["coding"])}
summary = []
for case in a.cases.split(","):
    label, name, run = case.split(":")
    run = int(run)
    iid = f"coding/{name}"
    orig = read_json(answer_path(label, iid, run))
    meta = read_json(label_dir(label) / "meta.json")
    resp = orig["response"]
    z, content = resp.get("reasoning") or "", resp.get("content") or ""
    unit, n_run = trailing_run(z)
    assert not content and unit.isdigit() and n_run >= 255, (case, unit, n_run, len(content))
    ids = tok.encode(z)
    unit_id = tok.encode(unit)
    assert len(unit_id) == 1 and ids[-1] == unit_id[0], (case, unit_id, ids[-3:])
    ids = ids + unit_id                                   # the 256th repeat: drawn, then withheld by the guard
    used = resp["usage"]["completion_tokens"]
    orig_max = (orig.get("request") or {}).get("max_tokens") or 81920
    info = {"case": case, "prefix_ids": len(ids), "server_counted": used, "count_match": len(ids) == used,
            "run_at_cut": f"{unit!r} x{n_run} visible + 1 withheld", "orig_max_tokens": orig_max}
    out_label = label + a.suffix
    if a.dry_run:
        print(json.dumps(info))
        summary.append(info)
        continue
    od = label_dir(out_label)
    if not (od / "answers" / "coding").exists():                    # once per label: the original coding answers
        (od / "answers").mkdir(parents=True, exist_ok=True)
        shutil.copytree(label_dir(label + a.base_suffix) / "answers" / "coding", od / "answers" / "coding")
        m2 = dict(meta)
        m2.update({"label": out_label, "categories": ["coding"], "continuation_of": label,
                   "note": f"{label + a.base_suffix}'s coding answers; the repeat-guard stops continued from their "
                           f"cut with repeat_stop_tokens {a.guard_total} in total"
                           + (f", sampling {a.sampling}" if a.sampling else "") + " (work/suite/guard_continue.py)"})
        m2.pop("cost_usd", None)
        write_json(od / "meta.json", m2)
    b = meta.get("backend") or {}
    samp = {**(b.get("sampling") or {}), **(json.loads(a.sampling) if a.sampling else {})}
    be = OpenAIBackend(a.endpoint, max_tokens=orig_max, sampling=samp, effort=b.get("reasoning_effort"),
                       extra_body={"strata_prefix_ids": ids}, tokenizer=a.tokenizer)
    msgs, prec = runner.messages_for(items[iid])
    t0 = time.monotonic()
    rec = be.chat(msgs, max_tokens=orig_max - len(ids), prompt_tokens_est=len(ids) + 1024)
    new_r = dict(rec["response"])
    cont_z = new_r.get("reasoning") or ""
    new_r["reasoning"] = z + unit + cont_z
    tk = dict(rec.get("tokens") or {})
    for k in ("completion", "reasoning"):
        tk[k] = (tk.get(k) or 0) + len(ids)
    tm = dict(rec.get("timing") or {})
    tm["wall_s"] = round((orig.get("timing") or {}).get("wall_s", 0) + (tm.get("wall_s") or time.monotonic() - t0), 2)
    new = dict(rec)
    new.update({"response": new_r, "tokens": tk, "timing": tm,
                "continuation": {**info, "new_tokens": (rec.get("tokens") or {}).get("completion"),
                                 "new_finish": rec["response"].get("finish_reason"), "new_cut_off": rec.get("cut_off"),
                                 "digit_run_total": longest_run(z + unit + cont_z)[1],
                                 "continuation_head": cont_z[:300], "server_repeat_stop_tokens": a.guard_total - 256,
                                 "sampling": samp,
                                 "endpoint_server": be.server_info, "at": now_iso()}})
    runner._save(out_label, items[iid], run, new, be.describe(), prec)
    c = new["continuation"]
    print(f"{case}: prefix {len(ids)} ids (server counted {used}{', match' if info['count_match'] else ', MISMATCH'}); "
          f"continued {c['new_tokens']} tokens, finish {c['new_finish']}, cut {c['new_cut_off']}; digit run in total "
          f"{c['digit_run_total']}; content {len(new_r.get('content') or '')} chars; head {cont_z[:120]!r}", flush=True)
    summary.append(c)
out = WS / "results/r19/guardcont"
out.mkdir(parents=True, exist_ok=True)
write_json(out / f"continue{'-dry' if a.dry_run else ''}-{int(time.time())}.json", summary)
