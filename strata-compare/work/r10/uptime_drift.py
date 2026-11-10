#!/usr/bin/env python3
"""uptime_drift.py — round 10 Phase 0.4: does decode speed drift with server uptime?

(1) C*7's 48-hour monitor (logs/r7/uptime/requests.csv, server started 2026-09-30 04:09:09, never restarted): your
    requests 07:00-14:46 (mostly Local Deep Research); answers of 768+ tokens; decode tok/s = the server's own figure.
    Uptime 3-10.6 h.  Speed also depends on the request (context length, answer length, topic), so besides the raw
    trend a least-squares fit with log(prompt tokens) and log(answer tokens) as covariates gives the uptime slope.
(2) Round 9's 2-hour soak of C*11 (SOAK11-1002T0040, server started ~00:40:40): the 32K probe every ~10 min (the same
    prompt, 512 tokens decoded) and every other completed answer of 256+ tokens (client-side decode tok/s).
Output: results/r10/uptime-drift.md (+ the hand-written verdict, results/r10/uptime-drift-verdict.md, appended) + the PNG."""
import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
T = lambda s: datetime.fromisoformat(s[:19])  # noqa: E731


def fit(y, cols):
    X = np.column_stack([np.ones(len(y))] + cols)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    s2 = res @ res / max(1, len(y) - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    return b, np.sqrt(np.diag(cov))


def rolling_median(x, y, w):
    o = np.argsort(x); x, y = x[o], y[o]
    return x, np.array([np.median(y[max(0, i - w // 2): i + w // 2 + 1]) for i in range(len(y))])


out = ["# Decode speed vs server uptime (round 10, Phase 0.4)", ""]
# ---- (1) C*7 monitor
start7 = T("2026-09-30T04:09:09")
rows = [r for r in csv.DictReader(open(WS / "logs/r7/uptime/requests.csv"))
        if r["time"] >= "2026-09-30T07:00" and int(r["output_tokens"]) >= 768 and float(r["decode_tok_s"] or 0) > 0]
up = np.array([(T(r["time"]) - start7).total_seconds() / 3600 for r in rows])
tps = np.array([float(r["decode_tok_s"]) for r in rows])
lp = np.log(np.array([int(r["prompt_tokens"]) for r in rows], float))
lo = np.log(np.array([int(r["output_tokens"]) for r in rows], float))
b0, se0 = fit(tps, [up])
b1, se1 = fit(tps, [up, lp, lo])
mean = tps.mean()
half = up < np.median(up)
out += [f"## C\\*7's monitor (your requests, {len(rows)} answers of 768+ tokens, uptime {up.min():.1f}–{up.max():.1f} h)", "",
        f"- mean {mean:.1f} tok/s; first half of the uptime range (median uptime {np.median(up):.1f} h) "
        f"{tps[half].mean():.1f}, second half {tps[~half].mean():.1f} tok/s",
        f"- raw trend: **{b0[1]:+.2f} ± {se0[1]:.2f} tok/s per hour** ({100 * b0[1] / mean:+.2f} % per hour)",
        f"- with log(prompt tokens) and log(answer tokens) as covariates: **{b1[1]:+.2f} ± {se1[1]:.2f} tok/s per hour** "
        f"({100 * b1[1] / mean:+.2f} % per hour); prompt {b1[2]:+.2f} ± {se1[2]:.2f} per e-fold, answer {b1[3]:+.2f} ± "
        f"{se1[3]:.2f} per e-fold", ""]
# ---- (2) Round 9 soak
start9 = T("2026-10-02T00:40:40")
soak = [json.loads(l) for l in open(WS / "results/runs.jsonl", encoding="utf-8")]
soak = [r for r in soak if r.get("config") == "SOAK11-1002T0040" and not r.get("stopped") and r.get("decode_tps")
        and (r.get("completion_tokens") or 0) >= 256]
probe = [r for r in soak if r["scenario"] == "soak_probe"]
other = [r for r in soak if r["scenario"] != "soak_probe"]
pu = np.array([(T(r["started"]) - start9).total_seconds() / 3600 for r in probe])
pt = np.array([r["decode_tps"] for r in probe])
bp, sep = fit(pt, [pu])
ou = np.array([(T(r["started"]) - start9).total_seconds() / 3600 for r in other])
ot = np.array([r["decode_tps"] for r in other])
olo = np.log(np.array([r["completion_tokens"] for r in other], float))
bo, seo = fit(ot, [ou, olo]) if len(other) > 5 else (None, None)
out += [f"## Round 9's soak of C\\*11 (2 h, server fresh at the start)", "",
        f"- 32K probe ({len(probe)} runs, same prompt, 512 tokens): {', '.join(f'{v:.1f}' for v in pt)} tok/s; "
        f"first {pt[:4].mean():.1f}, last four {pt[-4:].mean():.1f}; trend **{bp[1]:+.2f} ± {sep[1]:.2f} tok/s per hour**"]
if bo is not None:
    out += [f"- other completed answers of 256+ tokens ({len(other)}; chats, follow-ups, web): trend with log(answer "
            f"tokens) as covariate **{bo[1]:+.2f} ± {seo[1]:.2f} tok/s per hour** (mean {ot.mean():.1f})"]
(WS / "results/r10/uptime-drift.md").write_text("\n".join(out) + "\n" + (WS / "results/r10/uptime-drift-verdict.md").read_text())
print("\n".join(out))

# ---- figure: two panels, one series each (blue points, the rolling median in the secondary ink)
BLUE, INK2, GRID = "#2a78d6", "#52514e", "#e6e5e0"
fig, ax = plt.subplots(1, 2, figsize=(11, 4), dpi=130, gridspec_kw={"width_ratios": [3, 2]})
for a in ax:
    a.set_facecolor("#fcfcfb"); a.grid(True, color=GRID, lw=0.8); a.set_axisbelow(True)
    for s in ("top", "right"): a.spines[s].set_visible(False)
    for s in ("left", "bottom"): a.spines[s].set_color(INK2)
ax[0].scatter(up, tps, s=14, color=BLUE, alpha=0.55, lw=0)
rx, ry = rolling_median(up, tps, 31)
ax[0].plot(rx, ry, color=INK2, lw=2, label="rolling median (31 answers)")
ax[0].set_title(f"C*7 on 8080: your requests, answers ≥ 768 tokens (n={len(rows)})", fontsize=10, loc="left")
ax[0].set_xlabel("server uptime (h)"); ax[0].set_ylabel("decode (tok/s)"); ax[0].legend(frameon=False, fontsize=8)
ax[1].plot(pu, pt, "-o", color=BLUE, lw=2, ms=6)
ax[1].set_title("Round 9 soak of C*11: one 32K probe every 10 min", fontsize=10, loc="left")
ax[1].set_xlabel("server uptime (h)"); ax[1].set_ylim(min(pt.min(), 95), max(pt.max(), 120))
fig.tight_layout()
fig.savefig(WS / "results/r10/uptime-drift.png", facecolor="#fcfcfb")
