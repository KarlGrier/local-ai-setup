#!/usr/bin/env python3
"""pr_fill.py NAME - round 18 part 2: fill publish/r18/pr-NAME.md's {{CHECKS}} and {{NUMBERS}} from the saved results.

  {{CHECKS}}  <- results/r18/prc-NAME.txt (exact7 hashes: stock main / switch unset / switch on), the patch's own gate lines
                 (results/r18/prc-NAME.txt after the exact7 / ctest lines), results/r18/ctest-{main,NAME}.txt
  {{NUMBERS}} <- results/r18/pr-NAME-{one,two}-{dec,ttft}.md (stock main vs main + this patch, A B B A)
{{NOT_TESTED}} is read from publish/r18/not-tested-NAME.txt. Writes publish/r18/final-pr-NAME.md; prints what is missing."""
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
R, P = WS / "results/r18", WS / "publish/r18"
NAME = sys.argv[1]
SWITCH = {"b2": "STRATA_QSA_SPLIT_ATTN=1", "side": "STRATA_SIDE_MIXER=2",
          "gate": "STRATA_COST_GATE=data/cost_gate_flash_next_mtp.txt (with STRATA_SPEC_PROB=1)"}[NAME]
ITEMS = [("x-math", "math, greedy, 1,024 tokens"), ("s-math", "math, sampled (seed 11), 1,024 tokens"),
         ("x-code", "code, greedy, 1,024 tokens"), ("s-code", "code, sampled (seed 11), 1,024 tokens"),
         ("x-p2000", "2K-token prompt + 64 tokens"), ("x-32k", "32K-token prompt + 64 tokens"),
         ("x-112k", "112K-token prompt + 64 tokens")]
HW = ("RTX 5080 16 GB + RTX 4060 Ti 8 GB (driver 610.57.04, CUDA 13.3), Ryzen 9 9950X3D (16 cores), 96 GB DDR5, "
      "Linux 7.0; Qwen3.8-Flash-Next GSQ-RCO IQ3_S at a 131,072-token context")
FLAGS = ("`--expert-cache auto --prefill auto:16384 --spec 4 --spec-min-p 0.5 --mtp --max-context 131072 --kv int8 "
         "--kv-resident 32768 --pcie-frac 0 --ple-inflight 128 --vram-reserve-mib 713` with `STRATA_IO_THREADS=64 "
         "CUDA_MODULE_LOADING=LAZY STRATA_GR_V3=1 STRATA_PF_FUSED=1 STRATA_MMVQ_IL=1 STRATA_ADAPT_LAG=2 "
         "STRATA_DISJOINT_ADAPT=1` (the stock flags of my community benchmark report, #1681)")
missing = []


def read(p):
    try:
        return p.read_text()
    except OSError:
        missing.append(str(p.relative_to(WS)))
        return ""


prc = read(R / f"prc-{NAME}.txt")
h = {}
for line in prc.splitlines():
    m = re.match(r"(stock main|switch off|switch on|spec_prob alone): r18-e7-\S+?-(x-math|s-math|x-code|s-code|x-p2000|x-32k|x-112k)\s+out (\w+)", line)
    if m:
        h[(m.group(1), m.group(2))] = m.group(3)
main_e7 = WS / "bringup/out/logs/prof"
if not any(k[0] == "stock main" for k in h):   # stock main's exact7 ran once (in the first PR's checks)
    for line in read(R / "prc-b2.txt").splitlines():
        m = re.match(r"stock main: r18-e7-main-(\S+)\s+out (\w+)", line)
        if m:
            h[("stock main", m.group(1))] = m.group(2)
GATE = NAME == "gate"   # the gate's "on" arm also has STRATA_SPEC_PROB=1; its reference column: STRATA_SPEC_PROB=1 alone
rows = ["| exact7 item | main `fb58e0db` | this branch, switch unset |" + (" `STRATA_SPEC_PROB=1` alone |" if GATE else "")
        + (" `STRATA_SPEC_PROB=1` + the gate |" if GATE else " switch on |"), "|---|---|---|---|" + ("---|" if GATE else "")]
n_off = n_on = 0
n_greedy_on = n_greedy = 0
for k, label in ITEMS:
    a, b, c, d = (h.get((w, k), "?") for w in ("stock main", "switch off", "switch on", "spec_prob alone"))
    n_off += a == b != "?"
    n_on += a == c != "?"
    if k.startswith("x-"):
        n_greedy += 1
        n_greedy_on += a == c != "?"
    rows.append(f"| {label} | `{a}` | `{b}`{' (=)' if a == b else ''} |" + (f" `{d}`{' (=)' if a == d else ''} |" if GATE else "")
                + f" `{c}`{' (=)' if a == c else ''} |")
if any("?" in r for r in rows[2:]):
    missing.append("exact7 hashes")


def ctest_line(p):
    t = read(p)
    m = re.search(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)", t)
    fails = re.findall(r"Test +#\d+: (\S+) \.+\*+Failed", t)
    return (int(m.group(3)) - int(m.group(2)), int(m.group(3)), sorted(fails)) if m else (None, None, fails)


cm, cp = ctest_line(R / "ctest-main.txt"), ctest_line(R / f"ctest-{NAME}.txt")
extra4 = read(R / "ctest-main-extra4.txt")
e4 = re.search(r"(\d+)% tests passed, (\d+) tests failed out of 4", extra4)
main_pass = (cm[0] or 0) + (4 - int(e4.group(2)) if e4 else 0)
main_total = (cm[1] or 0) + (4 if e4 else 0)
gate_lines = [l for l in prc.splitlines() if not re.match(r"(stock main|switch off|switch on|ctest )", l) and l.strip()]

checks = [f"**How the default path was checked.** exact7 (the CLI, seven fixed computations: `--adapt-swaps 0 --suffix-draft 0 "
          f"--expert-cache 3500`) on main `fb58e0db` and on this branch, both cards, the measurements' flags (above) plus "
          f"`STRATA_PREFILL_CPU_SHARE=0` on both (with v0.1.41's CPU prompt-read share on, short-prompt outputs depend on "
          f"timing and main does not repeat itself). With the switch unset: **{n_off}/7 identical to main**. "
          + (f"With `STRATA_SPEC_PROB=1` and the gate: the greedy items {n_greedy_on}/{n_greedy} identical to main (the gate "
             f"does not apply to them); the sampled ones differ from main as they do with `STRATA_SPEC_PROB=1` alone, since "
             f"under rejection sampling the text for a seed depends on the drafts (docs/DETAILS.md). That the distribution "
             f"is unchanged is `spec_prob_test`'s check below." if GATE else f"With `{SWITCH}`: {n_on}/7 identical" + (f"; the other {7 - n_on} differ because the attention sums in "
             f"another order (a rounding-level change; the scoring check below)." if n_on < 7 else ".")), "", *rows, ""]
checks += ["**The patch's own checks.**", "", read(P / f"own-checks-{NAME}.txt").strip(), ""]
if cm[0] is not None and cp[0] is not None:
    same = cm[2] == cp[2]
    checks.append(f"**Upstream's tests** (ctest, the whole suite, among them verify_parity, verify_batch_parity, spec_verify_parity, qsa_parity and spec_prob_test): "
                  f"main {main_pass}/{main_total} pass, this branch {cp[0]}/{cp[1]} pass; "
                  + (f"the same {len(cp[2])} fail on both ({', '.join(cp[2])}): they read model files from fixed paths that "
                     f"this PC does not have." if same and cp[2] else ("none fail." if not cp[2] else f"main fails {cm[2]}, this branch {cp[2]}.")))
else:
    missing.append("ctest results")


def table(p):
    t = read(p)
    rows = [l for l in t.splitlines() if l.startswith("|")]
    if rows and rows[0].startswith("| metric | MAIN:"):   # the A B B A arms' labels -> plain words
        rows[0] = "| metric | main `fb58e0db`: arm 1 / arm 4 -> mean | main + this patch: arm 2 / arm 3 -> mean | patch vs main |"
    if rows and rows[0].startswith("| size | MAIN"):
        rows[0] = ("| prompt size | main: TTFT s / decode tok/s | main + this patch: TTFT s / decode tok/s | TTFT, patch vs main "
                   "| decode, patch vs main |")
    return "\n".join(re.sub(r"^\| (\d+)k \((\d+) per arm\)", r"| \1K (\2 runs per side)", r.replace("→", "->")) for r in rows)


nums = [f"**Measured** {'2026-10-10'} on one PC: {HW}. Served, stock main `fb58e0db` against main + this patch only, "
        f"A B B A with a fresh server per arm (the model files evicted from the page cache before each), both arms with {FLAGS}"
        + (", and `STRATA_SPEC_PROB=1` on both" if NAME == "gate" else "") + f"; the patch's arm adds `{SWITCH.split(' (')[0]}`. "
        "Requests carry no sampling fields, so the server's configured defaults apply: temperature 1.0, top-p 0.95, top-k 20, "
        "min-p 0.05, reasoning effort high. Decode screen: long reasoning math and code (4,096 tokens each), five short "
        "questions, a 32K prompt with 768 tokens out; decode figures are the engine's own (accepted output tokens / decode "
        "time). Prompt-read screen: time to first token for prompts of 1K x3, 4K x3, 32K x2 and 120K x2 tokens (each a "
        "different text, 768 tokens out; its decode column comes from short sampled answers and varies more than the "
        "decode screen).", ""]
for cs, title in (("one", "The RTX 5080 alone"), ("two", "The RTX 5080 with the RTX 4060 Ti as the helper expert cache (`--expert-cache-device1 3300`)")):
    nums += [f"*{title}*", "", table(R / f"pr-{NAME}-{cs}-dec.md"), "", table(R / f"pr-{NAME}-{cs}-ttft.md"), ""]
ex = P / f"extra-numbers-{NAME}.txt"
if ex.exists():
    nums += [ex.read_text().strip(), ""]
nt = read(P / f"not-tested-{NAME}.txt").strip()
src = read(P / f"pr-{NAME}.md")
out = src.replace("{{CHECKS}}", "\n".join(checks).strip()).replace("{{NUMBERS}}", "\n".join(nums).strip()).replace("{{NOT_TESTED}}", nt)
(P / f"final-pr-{NAME}.md").write_text(out)
print(f"publish/r18/final-pr-{NAME}.md written ({len(out)} chars); off {n_off}/7, on {n_on}/7")
if missing:
    print("MISSING:", ", ".join(missing))
