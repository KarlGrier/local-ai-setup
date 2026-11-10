"""Scores tables: one label (results/<label>/scores.md + scores.json), all labels side by side (results/SCORES.md),
and a paired item-by-item comparison of two labels (results/compare-<A>-vs-<B>.md)."""
from __future__ import annotations

import statistics

from .common import CAT_TITLES, RESULTS, SCORED, label_dir, read_json, write_json
from . import stats


def rating_exclusions() -> dict:
    """items/research/ratings-config.json "exclude_from_comparison": {question id: why} - research questions whose 1-5
    ratings stay on file but are left out of the comparison mean (11-01: r05, saturated)."""
    p = RESULTS.parent / "items" / "research" / "ratings-config.json"
    return (read_json(p).get("exclude_from_comparison") or {}) if p.exists() else {}


def _load(label):
    d = label_dir(label)
    meta = read_json(d / "meta.json") if (d / "meta.json").exists() else {}
    grades = read_json(d / "grades.json") if (d / "grades.json").exists() else {}
    return meta, grades


def step_limits(label) -> str:
    """The agentic per-step output limit the label's answers ran with (the field exists since 2026-10-13, when it
    went from 32,768 to 65,536; older answers ran at 32,768)."""
    seen = {}
    for p in sorted((label_dir(label) / "answers" / "agentic").glob("*.json")):
        try:
            v = read_json(p).get("step_max_tokens") or 32768
        except ValueError:
            continue
        seen.setdefault(v, []).append(p.stem)
    if not seen:
        return ""
    if len(seen) == 1:
        return f"{next(iter(seen)):,} output tokens per step"
    return "; ".join(f"{v:,} for {', '.join(n)}" for v, n in sorted(seen.items()))


def item_notes(label) -> dict:
    """results/<label>/item_notes.json: {"<category>/<item>": "note"} - facts about an item's answers that the score
    alone does not say (e.g. a serving bug fixed upstream).  Kept out of meta.json so a rerun or regrade keeps it."""
    p = label_dir(label) / "item_notes.json"
    return read_json(p) if p.exists() else {}


def _by_cat(grades):
    cats = {}
    for g in grades.values():
        if g.get("score") is None:
            continue
        e = cats.setdefault(g["category"], {}).setdefault(g["item"], {"runs": [], "weight": g.get("weight"),
                                                                       "stratum": g.get("stratum")})
        e["runs"].append(g["score"])
    return cats


def _resume_est(m) -> str:
    r = (m or {}).get("estimate_resume_usd")
    return f" (for the items left when it was resumed: ${r.get('point', 0):.2f})" if r else ""


def sampling_note(meta) -> str:
    """'' for local / Claude; for OpenRouter the sampling parameters its pinned provider ignores."""
    b = (meta or {}).get("backend") or {}
    if b.get("kind") != "openrouter":
        return ""
    ign = b.get("sampling_ignored") or []
    return f"provider ignores {', '.join(ign)} (sent, not honoured)" if ign else "provider honours all four sampling parameters"


def _providers_seen(label):
    seen = {}
    for p in (label_dir(label) / "answers").rglob("*.json"):
        r = read_json(p)
        m = (r.get("response") or {}).get("meta") or {}
        if m.get("provider"):
            key = (m.get("provider"), m.get("model"))
            seen[key] = seen.get(key, 0) + 1
    return seen


def _fmt(x, nd=1, pct=True):
    if x is None:
        return "-"
    return f"{100 * x:.{nd}f}" if pct else f"{x:,.{nd}f}"


def summarize(label) -> dict:
    meta, grades = _load(label)
    cats = _by_cat(grades)
    out = {"label": label, "meta": meta, "categories": {}}
    for cat in SCORED + ["freshness", "visual"]:
        gs = [g for g in grades.values() if g["category"] == cat]
        if not gs:
            continue
        row = {"answers": len(gs), "items": len({g["item"] for g in gs}),
               "cut_off": sum(1 for g in gs if g.get("cut_off"))}
        comp = [(g.get("tokens") or {}).get("completion") or 0 for g in gs]
        reas = [(g.get("tokens") or {}).get("reasoning") or 0 for g in gs]
        wall = [(g.get("timing") or {}).get("wall_s") for g in gs]
        wall_known = [w for w in wall if w is not None]
        tps = [(g.get("timing") or {}).get("server_decode_tps") or (g.get("timing") or {}).get("decode_tps") for g in gs]
        tps = [x for x in tps if x]
        row.update({"tokens_total": sum(comp), "reasoning_total": sum(reas),
                    "tokens_per_answer": statistics.mean(comp) if comp else None,
                    "reasoning_share": (sum(reas) / sum(comp)) if sum(comp) else None,
                    "wall_total_s": sum(wall_known) if wall_known else None,
                    "wall_per_answer_s": statistics.mean(wall_known) if wall_known else None,
                    "decode_tps_median": statistics.median(tps) if tps else None,
                    "cost_usd": sum(g.get("cost_usd") or 0 for g in gs) or None})
        if cat in cats:
            s, lo, hi, how = stats.category_score(cats[cat])
            solved = sum(g["score"] for g in gs if g.get("score") is not None)
            row.update({"score": s, "lo": lo, "hi": hi, "interval": how, "solved_sum": solved,
                        "fully_solved": sum(1 for g in gs if g.get("solved")),
                        "tokens_per_solved": (sum(comp) / solved) if solved else None,
                        "wall_per_solved_s": (sum(wall_known) / solved) if solved and len(wall_known) == len(gs) else None})
            if cat == "honesty":
                for st in ("unknown", "real"):
                    sub = [g for g in gs if g.get("stratum") == st]
                    row[f"{st}_correct"] = f"{sum(1 for g in sub if g.get('solved'))}/{len(sub)}"
        out["categories"][cat] = row
    tot = stats.overall_score({c: cats[c] for c in SCORED if c in cats})
    out["overall"] = {"score": tot[0], "lo": tot[1], "hi": tot[2], "categories": [c for c in SCORED if c in cats]}
    allg = list(grades.values())
    out["cut_reasons"] = sorted((g["item"], g["run"], g.get("cut_reason")) for g in allg if g.get("cut_off"))
    out["totals"] = {"answers": len(allg), "cut_off": sum(1 for g in allg if g.get("cut_off")),
                     "tokens": sum((g.get("tokens") or {}).get("completion") or 0 for g in allg),
                     "wall_s": sum((g.get("timing") or {}).get("wall_s") or 0 for g in allg),
                     "cost_usd": round(sum(g.get("cost_usd") or 0 for g in allg), 4) or None}
    return out


def write_label_report(label):
    d = label_dir(label)
    s = summarize(label)
    meta, grades = _load(label)
    write_json(d / "scores.json", s)
    m = meta
    b = m.get("backend") or {}
    L = [f"# Scores: {label}", "",
         f"- Endpoint: `{m.get('endpoint')}`  model: `{b.get('model')}`",
         f"- Mode: {m.get('mode')} ({m.get('runs')} run(s) per item); items fingerprint `{m.get('items_fingerprint')}`",
         f"- Started {m.get('started')}, finished {m.get('finished')}; status: {m.get('status')}",
         f"- Run wall time: {m.get('wall_s_total', 0) / 3600:.2f} h (sum of answer wall times "
         f"{s['totals']['wall_s'] / 3600:.2f} h); answers {s['totals']['answers']}, cut off {s['totals']['cut_off']}, "
         f"output tokens {s['totals']['tokens']:,}"]
    for inv in m.get("invocations") or []:
        L.append(f"  - invocation {str(inv.get('started'))[:16]}: {', '.join(inv.get('categories') or [])[:80]} "
                 f"({inv.get('mode')}{', ' + ', '.join(inv['flags']) if inv.get('flags') else ''}): "
                 f"{(inv.get('wall_s') or 0) / 3600:.2f} h")
    if b.get("kind") == "openai":
        L.append(f"- Sampling: {b.get('sampling')}, reasoning_effort {b.get('reasoning_effort')}, max_tokens "
                 f"{b.get('max_tokens_default')} (fit to the context {b.get('ctx')}); token split: {b.get('token_count')}")
    elif b.get("kind") == "openrouter":
        pe = b.get("pinned_endpoint") or {}
        pg = b.get("model_page") or {}
        seen = _providers_seen(label)
        L.append(f"- OpenRouter model `{b.get('model')}` (model page: {pg.get('name')}, Hugging Face id "
                 f"`{pg.get('hugging_face_id')}`); pinned endpoint `{pe.get('slug')}` ({pe.get('provider')}), "
                 f"published precision **{pe.get('published_precision')}**, fallbacks off")
        L.append(f"- Responses came from: " + (", ".join(f"{p} / model `{m}` x{n}" for (p, m), n in seen.items()) or "-"))
        L.append(f"- Sampling sent {b.get('sampling_sent')}; **{sampling_note(m)}**; reasoning {b.get('reasoning')}, "
                 f"max_tokens {b.get('max_tokens_default')}; cost (OpenRouter's reported usage): "
                 f"${m.get('cost_usd', 0):.2f}; estimate before the run: ${(m.get('estimate_usd') or {}).get('point', 0):.2f}" + _resume_est(m))
    else:
        L.append(f"- Thinking {b.get('thinking')}, effort {b.get('effort')}, max_tokens {b.get('max_tokens')}; "
                 f"API cost (reported usage): ${m.get('cost_usd', 0):.2f}; estimate before the run: "
                 f"${(m.get('estimate_usd') or {}).get('point', 0):.2f}" + _resume_est(m))
    notes = item_notes(label)
    for it, n in notes.items():
        L.append(f"- **Note on {it}: {n}**")
    ov = s["overall"]
    L += ["", f"**Total (mean of {len(ov['categories'])} scored categories): {_fmt(ov['score'])} %"
              f"  [95 % {_fmt(ov['lo'])}-{_fmt(ov['hi'])}]**", "",
          "| Category | items x runs | score % | 95 % interval | solved | cut off | tokens / answer | reasoning share | "
          "tokens / solved | wall / answer (s) | wall / solved (s) | decode tok/s |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cat, r in s["categories"].items():
        if cat in ("freshness", "visual"):
            continue
        extra = f" (unknowable {r['unknown_correct']}, real {r['real_correct']})" if cat == "honesty" else ""
        L.append(f"| {CAT_TITLES[cat]}{extra} | {r['items']} x {r['answers'] // max(1, r['items'])} | {_fmt(r.get('score'))} | "
                 f"{_fmt(r.get('lo'))}-{_fmt(r.get('hi'))} ({r.get('interval', '')}) | {_fmt(r.get('solved_sum'), 1, False)} | "
                 f"{r['cut_off']} | {_fmt(r['tokens_per_answer'], 0, False)} | {_fmt(r['reasoning_share'], 0)} % | "
                 f"{_fmt(r.get('tokens_per_solved'), 0, False)} | {_fmt(r['wall_per_answer_s'], 1, False)} | "
                 f"{_fmt(r.get('wall_per_solved_s'), 1, False)} | {_fmt(r['decode_tps_median'], 1, False)} |")
    if s["cut_reasons"]:
        L += ["", "Cut-off answers: " + "; ".join(f"{i.split('/')[1]} r{r}: {why}" for i, r, why in s["cut_reasons"])]
    L += ["", "Solved = sum of item scores (partial credit counts). Tokens = output tokens (thinking + answer). "
              "Wall per solved = all wall time in the category / solved. Agentic steps run serially; Batch API answers "
              "have no per-answer wall time.", ""]
    # per item
    for cat in SCORED:
        gs = sorted((g for g in grades.values() if g["category"] == cat), key=lambda g: (g["item"], g["run"]))
        if not gs:
            continue
        L += [f"## {CAT_TITLES[cat]}", ""]
        if cat == "agentic" and step_limits(label):
            L += [f"Per-step limit: {step_limits(label)} (65,536 for every model since 2026-10-13; 32,768 before, "
                  f"which only Sonnet 5.5 reached).", ""]
        L += ["| item | run | score | tokens | wall s | detail |", "|---|---|---|---|---|---|"]
        for g in gs:
            L.append(f"| {g['item'].split('/')[1]} | {g['run']} | {_fmt(g['score'], 0)} | "
                     f"{(g.get('tokens') or {}).get('completion')} | {(g.get('timing') or {}).get('wall_s')} | "
                     f"{('NOTE: ' + notes[g['item']] + '; ') if g['item'] in notes else ''}"
                     f"{('CUT OFF (' + str(g.get('cut_reason')) + '); ') if g.get('cut_off') else ''}"
                     f"{str(g.get('detail', '')).replace('|', '/')[:160]} |")
        L.append("")
    rs = sorted((g for g in grades.values() if g["category"] == "research"), key=lambda g: (g["item"], g["run"]))
    if rs:
        ratings = read_json(d / "ratings.json") if (d / "ratings.json").exists() else {}
        excl = rating_exclusions()
        rated = [v["rating"] for k, v in ratings.items() if k.split(".r")[0] not in excl]
        cache = next((g.get("web_cache") for g in rs if g.get("web_cache")), {}) or {}
        L += ["## Research with web search: key checks and your ratings", "",
              f"Web cache started {cache.get('created')} (the tools told every model 'today' = {cache.get('today')}). "
              f"Your ratings (blind page): " + (f"mean {sum(rated) / len(rated):.2f} of 5 over {len(rated)} answers"
                                               if rated else "none imported yet") +
              (f" ({', '.join(excl)} left out of the mean: {'; '.join(excl.values())} The research comparison now rests on "
               f"the remaining question(s), so it is a weak signal either way)" if excl else "") + ".", "",
              "| question | run | key score | checks | tool calls (cache hits) | tokens | wall s | your rating |",
              "|---|---|---|---|---|---|---|---|"]
        for g in rs:
            q = g["item"].split("/")[1]
            wc = g.get("web_cache") or {}
            rt = (ratings.get(f"{q}.r{g['run']}") or {}).get("rating", "-")
            if q in excl and rt != "-":
                rt = f"{rt} (not in the mean)"
            chk = "; ".join(f"{c['id']} {c['result']}" for c in g.get("checks") or []) or g.get("detail", "")
            if g["item"] in notes:
                chk = "NOTE: " + notes[g["item"]].split(":")[0] + "; " + chk
            L.append(f"| {q} | {g['run']} | {_fmt(g.get('score'), 0)} | {chk.replace('|', '/')[:150]} | "
                     f"{g.get('n_tool_calls')} ({wc.get('hits')}) | {(g.get('tokens') or {}).get('completion')} | "
                     f"{(g.get('timing') or {}).get('wall_s')} | {rt} |")
        notes = [f"{g['item'].split('/')[1]} r{g['run']}: " + "; ".join(g.get("speed_claims_not_scored") or [])
                 for g in rs if g.get("speed_claims_not_scored")]
        if notes:
            L += ["", "Speed claims (recorded, not scored): " + " | ".join(notes)]
        L.append("")
    fr = sorted((g for g in grades.values() if g["category"] == "freshness"), key=lambda g: (g["item"], g["run"]))
    if fr:
        L += ["## Knowledge freshness (not scored, not in the totals)", ""]
        for g in fr:
            rec = read_json(d / "answers" / "freshness" / f"{g['item'].split('/')[1]}.r{g['run']}.json")
            ans = (rec.get("response") or {}).get("content") or ""
            L += [f"**{g['item'].split('/')[1]} (run {g['run']})**: {g.get('detail')}", "", "> " +
                  ans.strip()[:1200].replace("\n", "\n> "), ""]
    vis = sorted((g for g in grades.values() if g["category"] == "visual"), key=lambda g: (g["item"], g["run"]))
    if vis:
        L += ["## Visual (judged by you: results/blind-*.html)", "",
              "| item | run | extracted | console errors | animated | changed after keys | blocked requests |",
              "|---|---|---|---|---|---|---|"]
        for g in vis:
            r = g.get("render") or {}
            L.append(f"| {g['item'].split('/')[1]} | {g['run']} | {g.get('detail')} | {r.get('console_errors')} | "
                     f"{r.get('animated')} | {r.get('changed_after_keys')} | {len(r.get('blocked') or [])} |")
        L.append("")
    (d / "scores.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return s


def write_table(labels=None):
    """All labels side by side: results/SCORES.md."""
    if not labels:
        labels = sorted(p.parent.name for p in RESULTS.glob("*/grades.json"))
    sums = [summarize(lb) for lb in labels]
    head = "| Category | " + " | ".join(labels) + " |"
    L = ["# All labels side by side", "", "Score % with 95 % interval; then output tokens and wall seconds per solved "
         "item (lower is better). Intervals overlap a lot at these item counts: use `run.sh compare A B` for paired "
         "tests.", "", head, "|---|" + "---|" * len(labels)]
    for cat in SCORED:
        cells = []
        for s in sums:
            r = s["categories"].get(cat)
            cells.append(f"{_fmt(r.get('score'))} [{_fmt(r.get('lo'), 0)}-{_fmt(r.get('hi'), 0)}]" if r and r.get("score") is not None else "-")
        L.append(f"| {CAT_TITLES[cat]} | " + " | ".join(cells) + " |")
    L.append("| **Total** | " + " | ".join(f"**{_fmt(s['overall']['score'])}** [{_fmt(s['overall']['lo'], 0)}-"
                                         f"{_fmt(s['overall']['hi'], 0)}]" for s in sums) + " |")
    L += ["", "Tokens per solved item / wall seconds per solved item:", "", head, "|---|" + "---|" * len(labels)]
    for cat in SCORED:
        cells = []
        for s in sums:
            r = s["categories"].get(cat) or {}
            cells.append(f"{_fmt(r.get('tokens_per_solved'), 0, False)} / {_fmt(r.get('wall_per_solved_s'), 0, False)}")
        L.append(f"| {CAT_TITLES[cat]} | " + " | ".join(cells) + " |")
    L += ["", "| Run | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    L.append("| mode / runs | " + " | ".join(f"{s['meta'].get('mode')} / {s['meta'].get('runs')}" for s in sums) + " |")
    L.append("| answers (cut off) | " + " | ".join(f"{s['totals']['answers']} ({s['totals']['cut_off']})" for s in sums) + " |")
    L.append("| run wall time h | " + " | ".join(f"{(s['meta'].get('wall_s_total') or 0) / 3600:.2f}" for s in sums) + " |")
    L.append("| output tokens | " + " | ".join(f"{s['totals']['tokens']:,}" for s in sums) + " |")
    L.append("| API cost $ | " + " | ".join(f"{s['meta']['cost_usd']:.2f}" if s["meta"].get("cost_usd") is not None else "-" for s in sums) + " |")
    L.append("| items fingerprint | " + " | ".join(f"`{s['meta'].get('items_fingerprint')}`" for s in sums) + " |")
    L.append("| sampling caveat | " + " | ".join(sampling_note(s["meta"]) or "-" for s in sums) + " |")
    L.append("| item notes | " + " | ".join("; ".join(f"{k.split('/')[1]}: {v.split(':')[0]}" for k, v in item_notes(lb).items())
                                            or "-" for lb in labels) + " |")
    L += human_ratings_section()
    (RESULTS / "SCORES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return RESULTS / "SCORES.md"


def _key_pct(label, item):
    """The script key's mean % over a research item's runs that have a score, and how many runs that is."""
    _, g = _load(label)
    sc = [v["score"] for k, v in g.items() if k.startswith(f"research/{item}#") and v.get("score") is not None]
    runs = sum(1 for k in g if k.startswith(f"research/{item}#"))
    return (100 * sum(sc) / len(sc) if sc else None), len(sc), runs


def human_ratings_section() -> list[str]:
    """results/human-ratings.json (your picks, ratings and notes from the blind pages, as given) as a SCORES.md
    section; kept in its own file so every rewrite of SCORES.md (table, compare) keeps it."""
    p = RESULTS / "human-ratings.json"
    if not p.exists():
        return []
    hr = read_json(p)
    L = ["", f"## Human ratings (blind pages, {hr.get('date', '')})", "",
         "Your picks, ratings and notes from the blind pages, recorded as you gave them; they are not part of any "
         "script score above. Data: `results/human-ratings.json`."]
    for pg in hr.get("pages", []):
        names = pg.get("names", {})
        L += ["", "### " + " vs ".join(f"{short} (`{label}`)" for short, label in names.items()), "",
              f"Page: `{pg['page']}`" + (". Not rated on the page." if pg.get("not_rated") else ".")
              + "".join(f' In your notes, "{w}" = {m}.' for w, m in pg.get("your_words", {}).items())]
        vp = pg.get("visual_picks")
        if vp:
            code, s, cards = vp["code"], vp["string"], vp["cards"]
            L += ["", f"Visual picks, your string `{s}` ({', '.join(f'{k} = {v}' for k, v in code.items())}), "
                      "one per card in the page's order:", "", "| item | r0 | r1 | r2 |", "|---|---|---|---|"]
            by_item = {}
            for c, ch in zip(cards, s):
                item, _, run = c.rpartition(".r")
                by_item.setdefault(item, {})[int(run)] = code[ch]
            for item, runs in by_item.items():
                L.append(f"| {item.split('_', 1)[1].replace('_', ' ')} | " + " | ".join(runs.get(r, "-") for r in range(3)) + " |")
            counts = {v: s.count(k) for k, v in code.items()}
            L += ["", f"All {len(s)} cards: " + ", ".join(f"{v} better {n}" if v != "tie" else f"tie {n}"
                                                       for v, n in counts.items()) + "."]
        rt = pg.get("research_totals")
        if rt:
            who = [k for k in names]
            L += ["", "Research, your total per question (the page rates each answer 1-5 and shows three runs, so 15 "
                      "at most), next to the script key's mean for the same answers:", "",
                  "| question | your name | " + " | ".join(f"{w} yours" for w in who) + " | "
                  + " | ".join(f"{w} key %" for w in who) + " |", "|---|---|" + "---|" * (2 * len(who))]
            tot = {w: 0 for w in who}
            for it in rt["items"]:
                keys = []
                for w in who:
                    tot[w] += it[w]
                    pct, n, runs = _key_pct(names[w], it["item"])
                    keys.append("-" if pct is None else f"{pct:.0f}" + (f" ({n} of {runs} runs checked)" if n < runs else ""))
                L.append(f"| {it['item']} | {it['your_name']} | " + " | ".join(str(it[w]) for w in who) + " | "
                         + " | ".join(keys) + " |")
            n = len(rt["items"])
            L.append(f"| **sum** | | " + " | ".join(f"**{tot[w]} / {15 * n}**" for w in who) + " |" + " |" * len(who))
            r04 = next(({w: it[w] for w in who} for it in rt["items"] if it["item"] == "r04_strata_release"), None)
            for w in who:
                note = item_notes(names[w]).get("research/r04_strata_release")
                if note and r04:
                    L += ["", f"r04 for {w}: {note.split(':')[0]} (its answers on this page ran on the v0.1.43-era "
                              "server). Without r04: " + ", ".join(f"{x} {tot[x] - r04[x]} / {15 * (n - 1)}" for x in who) + "."]
        if pg.get("notes"):
            L += ["", "Your notes:", ""] + [x for t in pg["notes"] for x in (f"> {t}", ">")][:-1]
    return L


def write_compare(a, b):
    ma, ga = _load(a)
    mb, gb = _load(b)
    ca, cb = _by_cat(ga), _by_cat(gb)
    L = [f"# {a} (A) vs {b} (B): item by item", "",
         f"Items fingerprints: A `{ma.get('items_fingerprint')}`, B `{mb.get('items_fingerprint')}`"
         + ("" if ma.get("items_fingerprint") == mb.get("items_fingerprint") else "  **(different test files!)**"), "",
         "Difference = B - A in score points, on the items both have; paired bootstrap 95 % interval; sign-flip "
         "permutation p. 'within noise' = the interval contains 0 or p >= 0.05.", "",
         "| Category | shared items | A % | B % | B - A | 95 % interval | p | items B better / A better | verdict |",
         "|---|---|---|---|---|---|---|---|---|"]
    notes = [f"{x}: {sampling_note(mm)}" for x, mm in (("A", ma), ("B", mb)) if sampling_note(mm)]
    if notes:
        L[-2:-2] = ["**Sampling: " + "; ".join(notes) + ".** Every row below carries this caveat.", ""]
    caveat = (" (" + "; ".join(notes) + ")") if notes else ""
    na, nb = item_notes(a), item_notes(b)
    res = {}
    for cat in SCORED:
        if cat not in ca or cat not in cb:
            continue
        r = stats.paired(ca[cat], cb[cat])
        res[cat] = r
        sa = stats.category_score({k: v for k, v in ca[cat].items() if k in cb[cat]})[0]
        sb = stats.category_score({k: v for k, v in cb[cat].items() if k in ca[cat]})[0]
        L.append(f"| {CAT_TITLES[cat]} | {r['n']} | {_fmt(sa)} | {_fmt(sb)} | {_fmt(r['diff'])} | "
                 f"{_fmt(r['lo'])} to {_fmt(r['hi'])} | {r['p']:.3f} | {r.get('items_b_better')} / {r.get('items_a_better')} | "
                 f"**{r['verdict']}**{caveat}"
                 + "".join(f" ({x}: {k.split('/')[1]} {v.split(':')[0]})" for x, nn in (("A", na), ("B", nb))
                           for k, v in nn.items() if k.split("/")[0] == cat) + " |")
    sa, sb = summarize(a), summarize(b)
    L += ["", "Efficiency (output tokens / wall seconds per solved item):", "", "| Category | A | B |", "|---|---|---|"]
    for cat in SCORED:
        x, y = sa["categories"].get(cat) or {}, sb["categories"].get(cat) or {}
        if x or y:
            L.append(f"| {CAT_TITLES[cat]} | {_fmt(x.get('tokens_per_solved'), 0, False)} / {_fmt(x.get('wall_per_solved_s'), 0, False)} | "
                     f"{_fmt(y.get('tokens_per_solved'), 0, False)} / {_fmt(y.get('wall_per_solved_s'), 0, False)} |")
    p = RESULTS / f"compare-{a}-vs-{b}.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    write_json(RESULTS / f"compare-{a}-vs-{b}.json", res)
    return p
