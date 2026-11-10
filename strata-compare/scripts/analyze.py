"""Offline analysis of saved outputs.

    analyze.py longreason [--configs A,B,C0]     sustained decode, rate curve, loop signs
    analyze.py diverge REF_CONFIG CFG [--scenario correctness] [--session-ref S] [--session S]
                                                 first divergence of two configs' greedy outputs
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, load_tokenizer  # noqa: E402

TOK = None


def tok():
    global TOK
    if TOK is None:
        TOK = load_tokenizer()
    return TOK


def outputs(config, scenario, session=None):
    d = RESULTS / "outputs" / config
    out = {}
    for p in sorted(d.glob(f"{scenario}_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        if session and r.get("session") != session:
            continue
        out.setdefault(r["item"], []).append(r)          # later sessions after earlier ones (sorted by name)
    return out


def raw_text(r):
    """The model's output as one string, in the order it was produced (reasoning, then answer)."""
    return (r.get("reasoning") or "") + "\n</think>\n\n" + (r.get("content") or "")


def loop_signs(ids, n=32):
    """Repetition measures over token ids: share of n-grams in the last quarter that already occurred earlier (n=32:
    verbatim loops; n=8: templated loops whose wording varies a little), the most repeated 32-gram, and the zlib
    ratio of the last 2,000 tokens' text (normal prose ~0.35-0.45; a loop compresses far better, < 0.2)."""
    import zlib
    out = {"rep_tail_share": 0.0, "rep8_tail_share": 0.0, "max_ngram_repeats": 0, "tail_zlib": None}
    if len(ids) < 4 * n:
        return out
    seen = Counter(tuple(ids[i:i + n]) for i in range(0, len(ids) - n + 1))
    q = len(ids) * 3 // 4
    for k, key in ((n, "rep_tail_share"), (8, "rep8_tail_share")):
        early = set(tuple(ids[i:i + k]) for i in range(0, q - k + 1))
        tail = [tuple(ids[i:i + k]) for i in range(q, len(ids) - k + 1)]
        out[key] = round(sum(1 for g in tail if g in early) / max(1, len(tail)), 3)
    out["max_ngram_repeats"] = max(seen.values())
    txt = tok().decode(ids[-2000:]).encode()
    out["tail_zlib"] = round(len(zlib.compress(txt, 9)) / max(1, len(txt)), 3)
    return out


def curve(r, window_s=60.0):
    """Tokens per window of wall time from the streamed pieces -> [(t_mid_s, depth_tokens, tok/s)]."""
    pieces = r.get("pieces") or []
    if not pieces:
        return []
    t0 = pieces[0][0]
    out, buf, w_start, depth = [], [], t0, 0
    for t, _, txt in pieces:
        if t - w_start >= window_s and buf:
            n = len(tok().encode("".join(buf)))
            depth += n
            out.append((round((w_start + t) / 2 - t0, 1), depth, round(n / (t - w_start), 2)))
            buf, w_start = [], t
        buf.append(txt)
    return out


def cmd_longreason(a):
    cfgs = a.configs.split(",")
    print("| config | prompt | gen tokens | finish | decode tok/s (whole) | first→last window tok/s | answer chars | tail repeats 32-gram / 8-gram | tail zlib ratio | loop? |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for c in cfgs:
        for item, rs in {**outputs(c, "longreason", a.session or None), **(outputs(c, "quality", a.session or None) if a.quality else {})}.items():
            for r in rs:
                ids = tok().encode(raw_text(r))
                ls = loop_signs(ids)
                cv = curve(r)
                fl = f"{cv[0][2]} → {cv[-1][2]}" if len(cv) >= 2 else "–"
                loop = "LOOP" if (ls["tail_zlib"] or 1) < 0.2 or ls["rep8_tail_share"] > 0.5 else "no"
                print(f"| {c} | {item} | {r.get('completion_tokens')} | {r.get('finish_reason')} | "
                      f"{round(r.get('decode_tps') or 0, 2)} | {fl} | {len(r.get('content') or '')} | "
                      f"{ls['rep_tail_share']} / {ls['rep8_tail_share']} | {ls['tail_zlib']} | {loop} |")
                if a.curves:
                    print("    curve (t_s, depth, tok/s):", cv)


def cmd_diverge(a):
    ref = outputs(a.ref, a.scenario, a.session_ref or None)
    oth = outputs(a.cfg, a.scenario, a.session or None)
    print(f"| prompt | {a.ref} tokens | {a.cfg} tokens | identical | first divergence (token index) | context at divergence |")
    print("|---|---|---|---|---|---|")
    for item in ref:
        if item not in oth:
            continue
        r, o = ref[item][-1], oth[item][-1]
        x, y = raw_text(r), raw_text(o)
        ix, iy = tok().encode(x), tok().encode(y)
        n = next((i for i, (p, q) in enumerate(zip(ix, iy)) if p != q), None)
        if n is None:
            same = len(ix) == len(iy)
            n_txt = "none" if same else f"none in common length ({min(len(ix), len(iy))})"
            ctx = ""
        else:
            n_txt = str(n)
            ctx = repr(tok().decode(ix[max(0, n - 8):n])) + " → " + repr(tok().decode(ix[n:n + 3])) + " vs " + \
                repr(tok().decode(iy[n:n + 3]))
            same = False
        print(f"| {item} | {len(ix)} | {len(iy)} | {'yes' if same and x == y else 'no'} | {n_txt} | {ctx[:160]} |")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("longreason")
    p.add_argument("--configs", default="A,B,C0")
    p.add_argument("--session", default="")
    p.add_argument("--curves", action="store_true")
    p.add_argument("--quality", action="store_true", help="also the quality outputs")
    p = sub.add_parser("diverge")
    p.add_argument("ref")
    p.add_argument("cfg")
    p.add_argument("--scenario", default="correctness")
    p.add_argument("--session-ref", default="")
    p.add_argument("--session", default="")
    a = ap.parse_args()
    {"longreason": cmd_longreason, "diverge": cmd_diverge}[a.cmd](a)


if __name__ == "__main__":
    main()
