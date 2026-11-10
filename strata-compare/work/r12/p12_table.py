#!/usr/bin/env python3
"""p12_table.py LABEL [SESSION_PREFIX] — round 12 Phase 0: the profile tables from logs/r12/prof-LABEL.engine.log (the R12
window / block / draft-round / lead lines, the R11 per-layer profile, the decode timing and serve lines) joined in order
with the client's records in results/runs.jsonl (session LABEL-*: scenario, item, kind).
Items: 1 exposed CPU wait + helper wait per layer per window (LDR / decode); 2 window cost by size T (MTP / lookup):
mixers, HC reads, GPU experts, exposed CPU wait, head, gaps, and the between-window part (pre / commit / draft / post);
3 lookup vs MTP windows by request kind; 4 decode per 256-token block (after >= 16K prompts, after a chat switch,
steady state); 5 the draft round's parts; A2 leads (when the next window's tokens were known)."""
import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")


def engine_requests(LOG):
  reqs, cur = [], {"lines": []}
  for ln in LOG.read_text(errors="replace").splitlines():
    if ln.startswith("strata serve: R10A") and reqs:
        reqs[-1]["r10a"] = ln
        continue
    cur["lines"].append(ln)
    m = re.match(r"strata serve: prompt (\d+) tokens = (\d+) reused \+ (\S+) read in (\d+) ms .*?, (\d+) generated in (\d+) ms", ln)
    if m:
        cur.update(prompt=int(m[1]), reused=int(m[2]), gen=int(m[5]), dec_ms=int(m[6]))
        reqs.append(cur)
        cur = {"lines": []}
  return reqs


def parse_req(r):
    W = []
    for ln in r["lines"]:
        if ln.startswith("strata R12 windows:"):
            for g in re.findall(r"\{([^}]*)\}", ln):
                toks = g.split()
                d = {"kind": toks[0], "T": int(toks[1][1:])}
                for k, v in zip(toks[2::2], toks[3::2]):
                    if k == "|":
                        continue
                    try:
                        d[k] = float(v)
                    except ValueError:
                        pass
                # "| gn" breaks the pairing: re-parse the GPU part
                gp = g.split("|")[1].split()
                for k, v in zip(gp[0::2], gp[1::2]):
                    d["g_" + k] = float(v)
                W.append(d)
        elif ln.startswith("strata R12 blocks:"):
            r["blocks"] = [float(x) for x in ln.split("ms_at_256:")[1].split()]
        elif ln.startswith("strata R12 draft round:"):
            r["draft"] = ln
        elif ln.startswith("strata R12 lead"):
            r["lead"] = {k: (float(a), float(b)) for k, a, b in re.findall(r"(\S+) ([\d.]+) (\d+)", ln.split(":", 1)[1])}
        elif ln.startswith("strata R11 L"):
            m = re.match(r"strata R11 L(\d+) .*helper-finish ([\d.]+) .*waitA ([\d.]+) waitCPU ([\d.]+)", ln)
            pm = re.search(r"pool ([\d.]+)", ln)
            ce = re.search(r"cpu-entries ([\d.]+)", ln)
            if m:
                r.setdefault("layers", {})[int(m[1])] = (float(m[2]), float(m[4]), float(pm[1]) if pm else 0.0,
                                                         float(ce[1]) if ce else 0.0)
        elif ln.startswith("strata R11 layer profile:"):
            r["lp_windows"] = int(ln.split(":")[1].split()[0])
    r["W"] = W
    return r


def load_matched(label, sesp=None, log=None):
    sesp = sesp or label
    reqs = [parse_req(r) for r in engine_requests(Path(log) if log else WS / f"logs/r12/prof-{label}.engine.log")]
    recs = [json.loads(l) for l in open(WS / "results/runs.jsonl") if f'"session": "{sesp}' in l]
    recs = [r for r in recs if r.get("session", "").startswith(sesp)]
    i = 0
    for rec in recs:
        while i < len(reqs) and reqs[i]["prompt"] != rec.get("prompt_tokens"):
            i += 1
        if i >= len(reqs):
            break
        reqs[i]["rec"] = rec
        i += 1
    return reqs, recs, [r for r in reqs if "rec" in r]


def W_table(matched, grp_name):
    """per kind (mtp / lookup) and T: windows, accepted, ms per whole round (total; pre + run + commit + draft + post)"""
    agg = defaultdict(lambda: defaultdict(float))
    for r in matched:
        if group(r) != grp_name:
            continue
        for w in r["W"]:
            a = agg[(w["kind"], w["T"])]
            a["n"] += w["n"]; a["acc"] += w["a"]
            a["ms"] += (w["pre"] + w["run"] + w["commit"] + w["draft"] + w["post"]) * w["n"]
    return agg


def group(r):
    s = r["rec"]["scenario"]
    if s.startswith("ldr-"):
        return "LDR"
    if s == "chatswitch":
        return "chatswitch"
    return "decode"


def kindof(r):
    rec = r["rec"]
    if rec["scenario"].startswith("ldr-"):
        return rec.get("note") or rec["item"].split("-")[-1]
    if rec["scenario"] == "chatswitch":
        return "chat-" + rec.get("note", "")
    return f"{rec['scenario']}:{rec['item']}"


def main():
    label = sys.argv[1]
    sesp = sys.argv[2] if len(sys.argv) > 2 else label
    reqs, recs, matched = load_matched(label, sesp)
    print(f"# {label}: {len(reqs)} engine requests, {len(recs)} client records, {len(matched)} matched")
    # ---- item 1: per layer, ms per window (window-weighted over requests)
    print("\n## 1. exposed CPU wait (GPU waitCPU) and the host's wait for the helper, per layer, ms per window")
    for grp in ("LDR", "decode"):
        acc = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        nw = 0
        for r in matched:
            if group(r) != grp or "layers" not in r:
                continue
            w = r.get("lp_windows", 0)
            nw += w
            for l, (hf, wc, pool, ce) in r["layers"].items():
                a = acc[l]
                a[0] += hf * w; a[1] += wc * w; a[2] += pool * w; a[3] += ce * w
        if nw == 0:
            continue
        tot = [sum(acc[l][k] for l in acc) / nw for k in range(4)]
        print(f"\n{grp}: {nw} windows; sum over 48 layers: waitCPU {tot[1]:.2f} ms, helper-finish {tot[0]:.2f} ms, CPU pool {tot[2]:.2f} ms, "
              f"CPU entries {tot[3]:.1f} per window")
        print("| layer | waitCPU | helper wait | CPU pool | CPU entries |\n|---|---|---|---|---|")
        for l in sorted(acc):
            a = acc[l]
            print(f"| {l} | {a[1]/nw:.3f} | {a[0]/nw:.3f} | {a[2]/nw:.3f} | {a[3]/nw:.2f} |")
        e12 = sum(acc[l][1] for l in acc if l < 12) / nw
        print(f"layers 0-11: waitCPU {e12:.3f} ms per window ({100*e12/tot[1]:.0f} % of the window's exposed CPU wait)")

    # ---- item 2: window cost by T
    print("\n## 2. window cost by size T (ms per window; served profile build)")
    for grp in ("LDR", "decode"):
        for kd in ("mtp", "lookup"):
            agg = defaultdict(lambda: defaultdict(float))
            for r in matched:
                if group(r) != grp:
                    continue
                for w in r["W"]:
                    if w["kind"] != kd:
                        continue
                    a = agg[w["T"]]
                    n = w["n"]
                    a["n"] += n
                    a["acc"] += w["a"]
                    for k in ("pre", "run", "commit", "draft", "post", "total"):
                        a[k] += w[k] * n
                    gn = w.get("g_gn", 0)
                    a["gn"] += gn
                    for k in ("mix", "hc", "exp", "waitCPU", "waitA", "waitB", "head", "gap", "gpu"):
                        a["g" + k] += w.get("g_" + k, 0) * gn
            if not agg:
                continue
            print(f"\n{grp} {kd} windows:")
            print("| T | windows | accepted/window | total | pre | verify (run) | commit | draft | post | GPU window | mixers | HC+router | GPU experts | waitCPU | waitA | head | gaps |")
            print("|" + "---|" * 17)
            for T in sorted(agg):
                a = agg[T]
                n, gn = a["n"], max(a["gn"], 1)
                print(f"| {T} | {n:.0f} | {a['acc']/n:.2f} | {a['total']/n:.2f} | {a['pre']/n:.2f} | {a['run']/n:.2f} | {a['commit']/n:.2f} | "
                      f"{a['draft']/n:.2f} | {a['post']/n:.2f} | {a['ggpu']/gn:.2f} | {a['gmix']/gn:.2f} | {a['ghc']/gn:.2f} | "
                      f"{a['gexp']/gn:.2f} | {a['gwaitCPU']/gn:.2f} | {a['gwaitA']/gn:.2f} | {a['ghead']/gn:.2f} | {a['ggap']/gn:.2f} |")

    # ---- item 3: lookup vs MTP windows by request kind
    print("\n## 3. lookup vs MTP windows by request kind (decode windows after the first)")
    kk = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])   # mtp windows, lookup windows, mtp tokens, lookup tokens
    for r in matched:
        k = kindof(r)
        for w in r["W"]:
            if w["kind"] == "mtp":
                kk[k][0] += w["n"]; kk[k][2] += w["n"] + w["a"]
            elif w["kind"] == "lookup":
                kk[k][1] += w["n"]; kk[k][3] += w["n"] + w["a"]
    print("| request kind | MTP windows | lookup windows | lookup share of windows | lookup share of tokens |\n|---|---|---|---|---|")
    for k in sorted(kk):
        m, l, mt, lt = kk[k]
        if m + l == 0:
            continue
        print(f"| {k} | {m:.0f} | {l:.0f} | {100*l/(m+l):.1f} % | {100*lt/max(mt+lt,1):.1f} % |")

    # ---- item 4: blocks
    print("\n## 4. decode per 256-token block (ms per block; tok/s)")
    cls = defaultdict(lambda: defaultdict(list))
    for r in matched:
        b = r.get("blocks") or []
        if not b:
            continue
        per = [b[0]] + [b[j] - b[j - 1] for j in range(1, len(b))]
        rec = r["rec"]
        fresh = r["prompt"] - r["reused"]
        if rec["scenario"] == "chatswitch" and rec.get("note") == "switchback":
            c = "after a chat switch"
        elif rec["scenario"] == "chatswitch":
            c = "after a >=16K prompt" if fresh >= 16384 else "other"
        elif fresh >= 16384:
            c = "after a >=16K prompt"
        elif r["prompt"] < 4096:
            c = "short prompt"
        else:
            c = "4-16K prompt"
        for j, ms in enumerate(per):
            cls[c][j].append(ms)
    print("| case | " + " | ".join(f"block {j+1}" for j in range(8)) + " | blocks 9+ |\n|" + "---|" * 10)
    for c in sorted(cls):
        row = []
        for j in range(8):
            v = cls[c].get(j, [])
            row.append(f"{256000/st.mean(v):.0f} (n {len(v)})" if v else "–")
        late = [x for j, v in cls[c].items() if j >= 8 for x in v]
        row.append(f"{256000/st.mean(late):.0f} (n {len(late)})" if late else "–")
        print(f"| {c} | " + " | ".join(row) + " |")
    steady = [x for c in cls for j, v in cls[c].items() if j >= 8 for x in v]
    if steady:
        print(f"steady state (blocks 9+ of every request): {256000/st.mean(steady):.1f} tok/s over {len(steady)} blocks")

    # ---- item 5: draft round
    print("\n## 5. the draft round (ms per round)")
    for grp in ("LDR", "decode"):
        tot = defaultdict(float)
        R = 0
        for r in matched:
            if group(r) != grp or "draft" not in r:
                continue
            m = re.search(r"rounds (\d+) host ([\d.]+)", r["draft"])
            if not m:
                continue
            n = int(m[1]); R += n
            tot["host"] += float(m[2]) * n
            for g, runs, gpu, gap in re.findall(r"g(\d) runs (\d+) gpu ([\d.]+) gap ([\d.]+)", r["draft"]):
                tot[f"g{g}runs"] += int(runs); tot[f"g{g}gpu"] += float(gpu) * int(runs); tot[f"g{g}gap"] += float(gap) * int(runs)
        if R == 0:
            continue
        parts = [f"host {tot['host']/R:.3f}"]
        gsum = 0.0
        for g in range(8):
            if tot[f"g{g}runs"]:
                gpu = tot[f"g{g}gpu"] / R; gap = tot[f"g{g}gap"] / R; gsum += gpu + gap
                parts.append(f"{'round graph' if g == 0 else 'step ' + str(g)}: {tot[f'g{g}runs']/R:.2f} runs/round, GPU {gpu:.3f} + gap {gap:.3f}")
        print(f"{grp}: {R} rounds; " + "; ".join(parts) + f"; host beyond GPU + gaps {tot['host']/R - gsum:.3f}")

    # ---- A2 leads
    print("\n## A2. how long before a window's verify its tokens were known (ms; mean over windows)")
    for grp in ("LDR", "decode"):
        acc = defaultdict(lambda: [0.0, 0.0])
        for r in matched:
            if group(r) != grp or "lead" not in r:
                continue
            for k, (v, n) in r["lead"].items():
                acc[k][0] += v * n; acc[k][1] += n
        print(f"{grp}: " + ", ".join(f"{k} {a[0]/a[1]:.3f} (n {a[1]:.0f})" for k, a in acc.items() if a[1]))


if __name__ == "__main__":
    main()
