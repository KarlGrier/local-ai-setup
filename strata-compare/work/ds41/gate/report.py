#!/usr/bin/env python3
"""report.py GATE_OUT - 11-03 (Karl's DeepSeek gate A / B / C): gate.sh's results -> GATE_OUT/report.md + report.json.
No GPU; reads only. GATE_OUT holds a link per arm (A, B, AL, BL, C0f, C1f, C2f, C0r, C0, C1, C2 -> the tunearm.sh run
folders in results/ds41/tuning/gate-*), kl/ (kl_b.py), greedy.json / greedy-repeat.json (greedy_compare.py).
  1 speed, A / B / C0 / C1 / C2: decode = the mean of W1-W3 over 3 passes, its spread = half the range of the three pass
    means (% of the mean); P4K / P20K = the mean of 3 prompts, spread = half their range (work/ds41/tune/summ.py's
    arm.json); placement, SSD, lowest MemAvailable, peak RSS / VRAM; against A, C1 / C2 against C0 and C0 against B
    with compare.py's rule (noise = the larger of the two spreads; a decode gain counts at >= 3 % beyond it, a prompt
    gain at >= 5 %)
  2 the long prompts, AL / BL (run with the daily services' memory load): per prompt its tokens, read speed (the
    engine's line), decode at that length, and MemAvailable before / lowest while it ran (0.5 s samples) / after;
    against the 14 GB daily rule, the 13 GB relief and the 12 GB floor; the services' RSS (svcmem.jsonl)
  3 C's exactness: the greedy texts of C1f / C2f vs C0f (placement frozen), and C0f's repeat if one ran; why C
    stopped, if it did (c-status.json: no download, a failed prep step, no start, or not exact)
  4 the drafter's acceptance, C1 / C2 (and under greedy C1f / C2f), next to unsloth's 1017 Q8_0 drafter's earlier 77 %
    (NOTES.md:8401, 10-24 00:25: "77 % of drafts kept", arm results/ds41/arm-dsp70-1024-0001 - drafter on the 5080,
    up to 5 drafts a round; and the 10-25 runs with it on the 4060 Ti, results/ds41/tuning/dspark4060-1025-0239 and
    conf-dspark4060-1025-1745), recomputed from their engine logs, position-matched (C1 can only keep position 1,
    C2 positions 1-2)
  5 B vs A teacher-forced KL (kl/kl-result.json; in gate.sh next a link to the first gate's), if it ran
  6 gate.sh next: B's KL under Karl's 11-04 rule (kl-noise/kl-noise-result.json: A vs Aa - 2 % fewer VRAM experts - and
    Ab - warmed by a W1 decode; B passes iff its changed picks and NLL distance are both <= the larger pair's), and B's
    daily status: that verdict, BL's memory verdict (L64 and L97 answered, no stop, lowest MemAvailable >= 14 GB with
    everything up), Karl's OK
"""
import json
import os
import re
import statistics as st
import subprocess
import sys

SC = "/home/USER/ai-speed-testing/strata-compare"
O = sys.argv[1]
DRAFTS = re.compile(r"maya ds4 serve: drafts (\d+) of (\d+) kept; per position \(kept / reached\):([^\n]*)")
POS = re.compile(r"(\d+): (\d+)/(\d+)")
REFS = [("10-24 dsp70 (NOTES.md:8401; drafter on the 5080, v0.2.4)", f"{SC}/results/ds41/arm-dsp70-1024-0001/engine-run.log"),
        ("10-25 dspark4060 (drafter on the 4060 Ti, v0.2.4)", f"{SC}/results/ds41/tuning/dspark4060-1025-0239/engine-run.log"),
        ("10-25 conf-dspark4060 (its confirm run)", f"{SC}/results/ds41/tuning/conf-dspark4060-1025-1745/engine-run.log")]


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def js(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None


def arm(n):
    d = f"{O}/{n}"
    if not os.path.exists(d):
        return None
    d = os.path.realpath(d)
    a = {"dir": d, "arm": js(f"{d}/arm.json") or {}, "disk": jl(f"{d}/disk.jsonl"), "recs": jl(f"{d}/ds41.jsonl")}
    stl = open(f"{d}/engine-start.log", errors="replace").read() if os.path.exists(f"{d}/engine-start.log") else ""
    m = re.search(r"experts per word: (\d+)", stl)
    a["experts_per_word"] = int(m.group(1)) if m else None
    a["placement"] = [l.strip()[:170] for l in stl.splitlines() if re.search(r"CUDA\d layers|routed experts on the CPU lane|DSpark", l)]
    a["ready"] = "ready after" in (open(f"{d}/summary.txt").read() if os.path.exists(f"{d}/summary.txt") else "")
    a["stops"] = {}
    sp_end = max([x.get("t_end") or 0 for x in a["disk"] if x["id"][:2] in ("W1", "W2", "W3", "P4", "P2")] + [0])
    for k in ("GUARD", "SOFTSTOP"):
        if os.path.exists(f"{d}/{k}"):
            when = os.path.getmtime(f"{d}/{k}")
            a["stops"][k] = {"text": open(f"{d}/{k}").read().strip(), "after_speed_requests": bool(sp_end) and when > sp_end}
    return a


def acc(rows):
    t = {"kept": 0, "offered": 0, "pos": {}}
    for r in rows:
        t["kept"] += r["kept"]; t["offered"] += r["offered"]
        for p, k, n in r["per_pos"]:
            x = t["pos"].setdefault(p, [0, 0]); x[0] += k; x[1] += n
    rounds = t["pos"].get(1, [0, 0])[1]
    t["rounds"] = rounds
    t["kept_pct"] = round(100 * t["kept"] / t["offered"], 1) if t["offered"] else None
    t["tokens_per_verify_round"] = round((t["kept"] + rounds) / rounds, 2) if rounds else None
    for k in (1, 2):
        ks = sum(t["pos"].get(p, [0, 0])[0] for p in range(1, k + 1)); rs = sum(t["pos"].get(p, [0, 0])[1] for p in range(1, k + 1))
        t[f"kept_pct_pos_le{k}"] = round(100 * ks / rs, 1) if rs else None
    # if every round offered k drafts: 1 + sum over i <= k of the chance that drafts 1..i are all kept (per-position rates)
    for k in (1, 2):
        e, c = 1.0, 1.0
        for p in range(1, k + 1):
            kk, rr = t["pos"].get(p, [0, 0])
            if not rr:
                break
            c *= kk / rr; e += c
        t[f"tokens_per_round_at_{k}_if_offered"] = round(e, 2)
    return t


def ref_acc(p):
    if not os.path.exists(p):
        return None
    rows = [{"kept": int(k), "offered": int(o), "per_pos": [[int(a), int(b), int(c)] for a, b, c in POS.findall(pp)]}
            for k, o, pp in DRAFTS.findall(open(p, errors="replace").read())]
    return acc(rows) if rows else None


def f1(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


def gain(a, b, key):
    """compare.py's numbers for b against a: gain %, noise % (the larger spread)"""
    if not a or not b:
        return None
    if key == "decode":
        x, y = a.get("decode"), b.get("decode")
    else:
        x, y = a.get(key), b.get(key)
    if not x or not y or not x.get("mean"):
        return None
    g = 100 * (y["mean"] / x["mean"] - 1)
    n = max(x.get("spread_pct") or 0, y.get("spread_pct") or 0)
    return round(g, 2), round(n, 2)


def verdict(a, b):
    """compare.py's keep rule, b against a"""
    d, p4, p20 = gain(a, b, "decode"), gain(a, b, "P4K"), gain(a, b, "P20K")
    if not d:
        return "no numbers"
    up = [k for k, v in (("P4K", p4), ("P20K", p20)) if v and v[0] - v[1] >= 5]
    down = [k for k, v in (("P4K", p4), ("P20K", p20)) if v and -v[0] - v[1] >= 5]
    if d[0] - d[1] >= 3 and not down:
        return "decode gain beyond noise"
    if up and not (-d[0] - d[1] > 0):
        return f"prompt gain beyond noise ({', '.join(up)}), decode not lower beyond noise"
    if -d[0] - d[1] >= 3:
        return "decode loss beyond noise"
    if down:
        return f"prompt loss beyond noise ({', '.join(down)})"
    return "trade-off: prompt up, decode down" if up else "no gain beyond noise"


def main():
    arms = {n: arm(n) for n in ("A", "B", "C0", "C1", "C2", "AL", "BL", "C0f", "C1f", "C2f", "C0r")}  # (+ BL64 / BS64 ... in section 7)
    R = {"arms": {}, "compare": {}, "long": {}, "acceptance": {}, "greedy": None, "kl": None}
    L = ["# DeepSeek V4.1 Flash gate: A (daily) vs B (the 5080 alone) vs C (+ Lucebox DSpark on the 4060 Ti)", "",
         f"Run folder: `{O}`. Profile snapshot: every arm started from a fresh copy of the gap's `logs/ds41/daily-profile.bin`.", ""]
    # 1 speed
    L += ["## 1. Speed (3 passes; spread = half the range, % of the mean)", "",
          "| arm | VRAM experts (per card) | decode tok/s (spread; pass means) | P4K (spread) | P20K (spread) | P20K SSD GB | "
          "SSD GB / token | lowest MemAvailable | peak RSS GB | peak VRAM MiB 5080 / 4060 Ti | experts / word | stops |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in ("A", "B", "C0", "C1", "C2"):
        a = arms[n]
        if not a:
            L.append(f"| {n} | not run | | | | | | | | | | |"); continue
        x = a["arm"]
        dec, p4, p20 = x.get("decode") or {}, x.get("P4K") or {}, x.get("P20K") or {}
        cards = " + ".join(f"{c['vram_experts']} (CUDA{c['dev']} [{c['layers']}])" for c in x.get("cards", [])) or "-"
        stops = "; ".join(f"{k}{' (after the speed requests)' if v['after_speed_requests'] else ''}: {v['text'][:60]}"
                          for k, v in a["stops"].items()) or "-"
        L.append(f"| {n} | {cards} | {f1(dec.get('mean'), 2)} ({f1(dec.get('spread_pct'), 2)} %; {dec.get('pass_means')}) | "
                 f"{f1(p4.get('mean'))} ({f1(p4.get('spread_pct'), 2)} %) | {f1(p20.get('mean'))} ({f1(p20.get('spread_pct'), 2)} %) | "
                 f"{f1(p20.get('disk_gb_mean'))} | {f1(x.get('disk_gb_per_token'), 4)} | {f1(x.get('lowest_memavail_gb'))} | "
                 f"{f1((x.get('peak_rss_mb') or 0) / 1024) if x.get('peak_rss_mb') else '-'} | {x.get('peak_vram_mib') or '-'} | "
                 f"{a['experts_per_word']} | {stops} |")
        R["arms"][n] = {"decode": dec, "P4K": p4, "P20K": p20, "cards": x.get("cards"), "stops": a["stops"],
                        "experts_per_word": a["experts_per_word"], "lowest_memavail_gb": x.get("lowest_memavail_gb"),
                        "dir": a["dir"]}
    L += ["", "Against (compare.py's rule: noise = the larger spread; decode counts at >= 3 % beyond it, prompts at >= 5 %):", ""]
    for ref, new, why in (("A", "B", "B vs A"), ("A", "C0", "C0 vs A"), ("A", "C1", "C1 vs A"), ("A", "C2", "C2 vs A"),
                          ("B", "C0", "C0 vs B: what the visible drafter card costs (no layer-major prompt path)"),
                          ("C0", "C1", "C1 vs C0: DSpark, 1 draft, same placement"), ("C0", "C2", "C2 vs C0: DSpark, 2 drafts, same placement")):
        a, b = arms[ref], arms[new]
        if not a or not b:
            continue
        g = {k: gain(a["arm"], b["arm"], k) for k in ("decode", "P4K", "P20K")}
        v = verdict(a["arm"], b["arm"])
        R["compare"][f"{new}_vs_{ref}"] = {"gain_noise_pct": g, "verdict": v}
        L.append(f"- {why}: decode {g['decode'][0] if g['decode'] else '-'} % (noise {g['decode'][1] if g['decode'] else '-'}), "
                 f"P4K {g['P4K'][0] if g['P4K'] else '-'} % ({g['P4K'][1] if g['P4K'] else '-'}), "
                 f"P20K {g['P20K'][0] if g['P20K'] else '-'} % ({g['P20K'][1] if g['P20K'] else '-'}) -> {v}")
    for n in ("A", "B", "C0", "C1", "C2"):
        if arms[n] and arms[n]["experts_per_word"] not in (6, None):
            L.append(f"- WARNING: {n} ran {arms[n]['experts_per_word']} experts per word (6 pinned) - lossy, its numbers do not count")
    # 2 long prompts
    L += ["", "## 2. Long prompts (own arms: a warm-up, one P20K, then ~64K and ~97K; MemAvailable every 0.5 s)", "",
          "| arm | prompt | tokens | read tok/s (engine) | TTFT s | decode at length tok/s | MemAvailable before / lowest / after GB | "
          "dip GB | engine RSS before / after GB | vs 14 / 13 / 12 GB |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n in ("AL", "BL"):
        a = arms[n]
        if not a:
            L.append(f"| {n} | not run | | | | | | | | |"); continue
        lj = js(f"{a['dir']}/long.json") or []
        R["long"][n] = {"prompts": lj, "lowest_memavail_gb_arm": a["arm"].get("lowest_memavail_gb"), "stops": a["stops"]}
        for p in lj:
            b, lo, af = p.get("memavail_before_gb"), p.get("memavail_low_gb"), p.get("memavail_after_gb")
            ok = "-" if lo is None else " / ".join("ok" if lo >= t else "UNDER" for t in (14, 13, 12))
            L.append(f"| {n} | {p['id']} | {p.get('prompt_tokens')} | {p.get('read_tps_engine')} | {p.get('ttft_s')} | "
                     f"{p.get('decode_tps')} | {b} / {lo} / {af} | {f1(b - lo, 1) if b is not None and lo is not None else '-'} | "
                     f"{f1((p.get('engine_rss_before_mb') or 0) / 1024)} / {f1((p.get('engine_rss_after_mb') or 0) / 1024)} | {ok}"
                     + (f" ERROR {p['error'][:60]}" if p.get("error") else "") + " |")
        stops = "; ".join(f"{k}: {v['text'][:90]}" for k, v in a["stops"].items())
        L.append(f"| {n} | (arm) | | | | | lowest in the arm {a['arm'].get('lowest_memavail_gb')} | | | {stops or 'no stop'} |")
        lows = [p.get("memavail_low_gb") for p in lj if p.get("memavail_low_gb") is not None] + \
               ([a["arm"]["lowest_memavail_gb"]] if a["arm"].get("lowest_memavail_gb") is not None else [])
        done = {p["id"] for p in lj if not p.get("error") and p.get("completion_tokens")}
        low = min(lows) if lows else None
        R["long"][n]["lowest_gb"] = low
        R["long"][n]["lines"] = {str(t): (low is not None and low >= t) for t in (14, 13, 12)}
        R["long"][n]["pass"] = (done >= {"L64", "L97"} and not a["stops"] and low is not None and low >= 14.0)
    for n in ("AL", "BL"):
        x = R["long"].get(n)
        if x:
            ln = x.get("lines") or {}
            L.append(f"- **{n}: {'PASS' if x.get('pass') else 'FAIL'}** (rule: L64 and L97 both answered, no guard, soft stop or "
                     f"swap failure, and the arm's lowest MemAvailable >= 14 GB with everything up - the daily rule); lowest "
                     f"{x.get('lowest_gb')} GB: 14 GB daily rule {'ok' if ln.get('14') else 'UNDER'}, 13 GB relief "
                     f"{'ok' if ln.get('13') else 'UNDER'}, 12 GB floor {'ok' if ln.get('12') else 'UNDER'}")
    sv = jl(f"{O}/svcmem.jsonl")
    R["services"] = sv
    L += ["", "AL / BL ran with the daily services' memory load (\"everything up\", as ctx128.py's 97K run: SearXNG 8889/8890 "
          "up, ballast.py holding LDR's 3.54 GiB and SearXNG 8889's 1.74 GiB less what they held), so these lows are the "
          "real ones (A's 10-27 97K run with everything up: lowest 18.9 GB). Services (svcmem.py):"]
    for r in sv:
        L.append(f"- {r.get('t')} {r.get('label')}: MemAvailable {r.get('MemAvailable_gib')} GiB; "
                 + ", ".join(f"{k} {v}" for k, v in (r.get('rss_gib') or {}).items() if v))
    # 3 greedy
    cs = js(f"{O}/c-status.json") or {}
    R["c_status"] = cs
    L += ["", "## 3. C's exactness: greedy, placement frozen (--no-expert-cache)", ""]
    if cs and not cs.get("c_ok"):
        L.append(f"- **C stopped: {cs.get('why')}**")
    g = js(f"{O}/greedy.json")
    R["greedy"] = g
    if not g:
        L.append("- not run" + ("" if arms["C0f"] else " (C0f did not run)"))
    else:
        L.append(f"- verdict: **{g.get('verdict')}** (C1f / C2f vs C0f, text for text, token counts too)")
        for d, rr in g["runs"].items():
            for pid, r in rr.items():
                L.append(f"  - {os.path.basename(d)} {pid}: {r['verdict'][:200]}" + (f" (tokens {r['tokens']})" if "tokens" in r else ""))
        gr = js(f"{O}/greedy-repeat.json")
        if gr:
            R["greedy_repeat"] = gr
            L.append(f"- C0f repeated (C0r): **{gr.get('verdict')}** - " + ("the reference is repeatable, so a difference above is the drafter's path"
                                                                          if gr.get("verdict") == "IDENTICAL" else
                                                                          "the reference itself is not repeatable: the difference above says nothing about DSpark"))
    # 4 acceptance
    L += ["", "## 4. The drafter's acceptance", "",
          "| run | requests | drafts kept / offered | kept % | position 1 kept % | positions 1-2 kept % | verify rounds | "
          "tokens a verify round | if every round offered k drafts (k = 1 / 2) |", "|---|---|---|---|---|---|---|---|---|"]

    def row(lab, req, t):
        if not t:
            L.append(f"| {lab} | {req} | - | | | | | | |"); return
        L.append(f"| {lab} | {req} | {t['kept']} / {t['offered']} | {t['kept_pct']} | {t['kept_pct_pos_le1']} | {t['kept_pct_pos_le2']} | "
                 f"{t['rounds']} | {t['tokens_per_verify_round']} | {t['tokens_per_round_at_1_if_offered']} / {t['tokens_per_round_at_2_if_offered']} |")
    for n in ("C1", "C2"):
        a = arms[n]
        if not a:
            continue
        dec = [x for x in a["disk"] if x["id"][:2] in ("W1", "W2", "W3")]
        t_dec = acc([r for x in dec for r in (x.get("engine") or {}).get("drafts", [])])
        t_all = acc([r for x in a["disk"] for r in (x.get("engine") or {}).get("drafts", [])])
        R["acceptance"][n] = {"W1-W3": t_dec, "all": t_all}
        row(f"{n} (Lucebox Q2K/Q4K, 4060 Ti)", "W1-W3, 3 passes", t_dec)
        row(f"{n}", "all requests", t_all)
    for n in ("C1f", "C2f"):
        a = arms[n]
        if a:
            ge = jl(f"{a['dir']}/greedy-engine.jsonl")
            t = acc([r for x in ge for r in (x.get("engine") or {}).get("drafts", [])])
            R["acceptance"][n] = t
            row(f"{n} (greedy, frozen)", "G-W1, G-W2, G-P4K0", t)
    for lab, p in REFS:
        t = ref_acc(p)
        R["acceptance"][lab] = t
        row(f"Q8_0 1017: {lab}", "all requests (block 5)", t)
    L += ["", "The 77 % (NOTES.md:8401) is drafts kept / offered over every request of that arm, up to 5 drafts a round. C1 "
          "keeps at most position 1, C2 positions 1-2: compare their \"kept %\" with the reference's position-matched columns. "
          "Lucebox's drafter was converted from DeepSeek's V4.1 Flash checkpoint, the trunk here is the 1017 revision: a "
          "lower position-1 rate than the Q8_0 1017 drafter's points at that mismatch."]
    # 5 KL
    L += ["", "## 5. B vs A, teacher-forced KL (the round's skipcheck form)", ""]
    k = js(f"{O}/kl/kl-result.json")
    R["kl"] = k
    if not k:
        L.append("- not run in this gap" + (" (it stopped part-way: see kl/kl.log; kl-b.sh resumes it)" if os.path.exists(f"{O}/kl") else
                                            ": run `work/ds41/gate/kl-b.sh gap` in a later gap (REQUIRED before any daily switch to B)"))
    else:
        L.append(f"- verdict: **{'PASS (rounding-level)' if k['pass'] else 'FAIL'}**")
        for kk, r in k["res"].items():
            L.append(f"  - {kk} vs A: KL mean {r['kl_mean']:.5f}, p90 {r['kl_p90']:.5f}, max {r['kl_max']:.3f}, KL>1 {r['kl_gt1']}, "
                     f"top-1 agree {r['top1_agree']} of {r['positions']}")
        L.append(f"  - changed top-1 picks {k['detail']['flips']} (B, R1, R2; bound {k['detail']['flips_bound']}); text NLL "
                 f"{k['detail'].get('nll')} (B, R1, R2, A)")
        L += [f"  - {'ok  ' if v else 'FAIL'} {c}" for c, v in k["checks"].items()]
        L.append(f"  - prompt-skip lines {k.get('prompt_skip_lines')}; run times {k.get('times')}")
        lm = (k.get("layer_major_lines") or {}).get("cand-B")
        L.append(f"  - B's one-device layer-major prompt path inside the check: {lm} of 8 segments"
                 + ("" if lm else " - NOT covered (the engine streamed the 12,000-token prefix per chunk); see kl/kl.md"))
        for lab, s in (k.get("report_only_vs_stock") or {}).items():
            L.append(f"  - report only: {lab} vs stock v0.2.6 (stored teacher/final-*): {'PASS' if s['pass'] else 'FAIL'}, "
                     f"changed picks {s['detail']['flips']}")
    aa = js(f"{O}/kl-noise/kl-noise-result.json")
    R["kl_noise"] = aa
    L += ["", "## 6. B's KL under Karl's 11-04 rule: the noise band of A's placement variants", ""]
    if not aa:
        L.append("- not run" + (" (rule written: kl-noise/rule.txt)" if os.path.exists(f"{O}/kl-noise/rule.txt") else ""))
    else:
        v = aa["variants"]
        row = lambda n, r: (f"| {n} | {r['top1_changed']} | {r['nll_distance']:.5f} | {r['kl_mean']:.5f} / {r['kl_p90']:.5f} / "  # noqa: E731
                            f"{r['kl_gt1']} | {(r.get('placement') or {}).get('total', '-')} | {r['byte_identical']} |")
        L += [f"- {aa['plan']}", "", "| vs A | changed top-1 picks | NLL distance | KL mean / p90 / KL>1 | VRAM experts | byte-identical |",
              "|---|---|---|---|---|---|", row("Aa: --vram-experts 0.98 (2 % fewer)", v["Aa"]),
              row("Ab: warmed by a W1 decode", v["Ab"]), row("B (first gate)", aa["b"]), "",
              f"- band (the larger of Aa / Ab): top-1 {aa['band']['top1']}, NLL {aa['band']['nll']:.5f}; Ab's warm-up changed "
              f"{v['Ab'].get('profile_counts_changed')} profile counts; A's VRAM experts in the harness {aa['a_placement']['total']}",
              f"- **B's KL check under Karl's rule: {'PASS (both numbers inside the band)' if aa['pass'] else 'FAIL - B stays off'}** "
              f"(top-1 {'inside' if aa['checks']['top1'] else 'outside'}, NLL {'inside' if aa['checks']['nll'] else 'outside'})"]
    bl = (R["long"].get("BL") or {}).get("pass")
    if aa or "BL" in R["long"]:
        L += ["", f"**B for daily use** (Karl 11-03: the KL check under his rule AND the long-prompt memory arms AND his OK): "
                  f"KL (noise-band rule) {'pass' if aa and aa.get('pass') else 'not passed' if aa else 'not judged'}; long prompts "
                  f"{'pass' if bl else 'not passed' if bl is not None else 'not run'}; Karl's OK pending."]
    # 7 gate.sh bstore: B with a smaller RAM store
    bs = [n for n in (64, 62, 60) if os.path.exists(f"{O}/BL{n}") or os.path.exists(f"{O}/BS{n}")]
    if bs or os.path.exists(f"{O}/kl-bstore"):
        L += ["", "## 7. B with a smaller RAM store (gate.sh bstore)", "",
              "| arm | prompt | tokens | read tok/s | MemAvailable before / lowest GB | dip GB | stops |", "|---|---|---|---|---|---|---|"]
        R["bstore"] = {}
        for n in bs:
            a = arm(f"BL{n}")
            if not a:
                continue
            lj = js(f"{a['dir']}/long.json") or []
            for x in lj:
                b, lo = x.get("memavail_before_gb"), x.get("memavail_low_gb")
                L.append(f"| BL{n} | {x['id']} | {x.get('prompt_tokens')} | {x.get('read_tps_engine')} | {b} / {lo} | "
                         f"{f1(b - lo, 1) if b is not None and lo is not None else '-'} | {'; '.join(a['stops']) or '-'} |")
            v = subprocess.run([sys.executable, "-I", f"{os.path.dirname(os.path.abspath(__file__))}/bl_verdict.py", a["dir"]],
                               capture_output=True, text=True)
            vv = json.loads(v.stdout or "{}") if v.stdout.strip().startswith("{") else {}
            R["bstore"][f"BL{n}"] = vv
            L.append(f"| BL{n} | **{'PASS' if vv.get('pass') else 'FAIL'}** (>= 14 GB, both answered, no stop) | | | lowest {vv.get('lowest_gb')} | | |")
        kb = js(f"{O}/kl-bstore/kl-bstore-result.json")
        R["bstore"]["kl"] = kb
        if kb:
            r = kb["vs_A"]
            L.append(f"- KL noise band (B{kb['n']} vs A): **{'PASS' if kb['pass'] else 'FAIL'}** - changed top-1 picks {r['top1_changed']} "
                     f"(band {kb['band']['top1']}), NLL distance {r['nll_distance']:.5f} (band {kb['band']['nll']:.5f}); "
                     f"byte-identical to B (68 GB): {kb['byte_identical_to_B']}")
        for n in bs:
            a = arm(f"BS{n}")
            if a and arms.get("A") and arms.get("B"):
                x = a["arm"]
                d = x.get("decode") or {}
                L.append(f"- BS{n} speed: decode {f1(d.get('mean'), 2)} ({f1(d.get('spread_pct'), 2)} %), P4K "
                         f"{f1((x.get('P4K') or {}).get('mean'))}, P20K {f1((x.get('P20K') or {}).get('mean'))}, SSD "
                         f"{f1(x.get('disk_gb_per_token'), 4)} GB / token; vs A: {verdict(arms['A']['arm'], x)} "
                         f"(decode {gain(arms['A']['arm'], x, 'decode')}); vs B (68 GB): {verdict(arms['B']['arm'], x)} "
                         f"(decode {gain(arms['B']['arm'], x, 'decode')})")
                R["bstore"][f"BS{n}"] = {"decode": d, "vs_A": verdict(arms["A"]["arm"], x), "vs_B": verdict(arms["B"]["arm"], x)}
    # 8 gate.sh csample: the near-tie check and C under sampling
    tj = js(f"{O}/tie/tie.json")
    R["tie"] = tj
    if tj or os.path.exists(f"{O}/tie"):
        L += ["", "## 8. C's greedy divergence: near-tie check (gate.sh csample)", ""]
        if not tj:
            L.append("- no verdict (see tie-run.out: not reproduced, or stopped)")
        else:
            w1 = tj["at_j"].get("w1") or {}
            L += [f"- generated token {tj['j']} (char {tj['char']}): C0f {tj['c0f_token_text']!r} vs C1f {tj['c1f_token_text']!r}; "
                  f"C0f's gap (window 1) {w1.get('gap_c0f_minus_c1f')} nats; rule: <= {tj['rule_max_gap']:.4f} (tie/rule.txt) -> "
                  f"**{'within rounding' if tj['within_rounding'] else 'NOT within rounding'}**",
                  "- 2-row windows: " + "; ".join(f"{n}: top-1 = C1f's token {r['top1'] == tj['c1f_token']}, gap {r['gap_c0f_minus_c1f']:.4f}"
                                                  for n, r in tj["at_j"].items() if n != "w1" and r)]
            c1 = R["compare"].get("C1_vs_A") or {}
            c2 = R["compare"].get("C2_vs_A") or {}
            beats = any(x.get("verdict") == "decode gain beyond noise" for x in (c1, c2))
            if arms.get("C1") or arms.get("C2"):
                L.append(f"- C under sampling vs A: C1 {c1.get('verdict')}, C2 {c2.get('verdict')} -> "
                         + ("**C beats A's decode beyond the noise: next (Karl's rule) - build the sampled distribution harness "
                            "and propose a 1017-matched small drafter**" if beats else "C does not beat A's decode beyond the noise: "
                            "no distribution harness, no drafter proposal (Karl's rule)"))
    # placement lines
    L += ["", "## Placement (engine start lines)", ""]
    for n, a in arms.items():
        if a:
            L.append(f"- {n} (`{a['dir']}`): " + " / ".join(a["placement"][:5]))
    open(f"{O}/report.md", "w").write("\n".join(L) + "\n")
    json.dump(R, open(f"{O}/report.json", "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
