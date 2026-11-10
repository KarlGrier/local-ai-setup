# Basalt 0.2.0 settings test - report (11-02)

Karl's brief 11-01 (settings only, in the gap after 7a, 1-2 h budget with 8080 down). Basalt v0.2.0 = f0bb833c, built
offline (CUDA 13.3, arch 120) in 4 min at the gap's start; the v2 IQ3_S pack (87,643,882,460 bytes, sha256 checked).
Everything in basalt-020/; every Basalt step inside `unshare -rn` (own loopback only), the RTX 5080 alone, 127.0.0.1.

**GPU time:** gap 1 02:52-03:13 (21 min with 8080 down: build, probe, defaults x3 by the preset and x3 by hand, 9
tries); gap 2 03:18-03:26 (8 min: the speed screen). 29 min in all. Guards never tripped: lowest 5080 free 578 MiB,
lowest MemAvailable 32.7 GiB, swap 0, kernel log clean before, between and after. P028x back both times (engine sha
f4c4f654fb24 checked, chat-cache policy on, queue released).

## 1. Basalt at its defaults vs P028x (gap 16, the same prompts, cold, 3 passes)

Gap 16's bp90 table ran Basalt's community fixtures on P028x (identical token ids, the same sampling, a fresh engine per
measurement, engine rates, KV int8). Basalt here: `basalt-bench --community` x3 (the defaults; the preset forces KV int8,
max context 66,661) and the same preset by hand x3 (identical engine command; 3 fresh engines per pass).

| measure | P028x (gap 16) | Basalt defaults, --community x3 | vs P028x | Basalt by hand x3 |
|---|---|---|---|---|
| decode blend | 198.4 (196.7-200.7) | **217.2** (216.0-217.8) | **+9.5 %** | 218.1 (215.3-221.6) |
| conv / struct / prose | 148.5 / 228.4 / 133.2 | 158.0 / 246.3 / 160.0 | +6.4 / +7.8 / +20.1 % | 153.8 / 247.3 / 159.4 |
| 16K prompt | 3,826.7 (3,792-3,858) | **5,063.5** (4,486-5,362) | **+32.3 %** | 5,355.6 (5,344-5,363) |
| 64K prompt | 4,382.5 (4,369-4,390) | **5,439.7** (5,438-5,442) | **+24.1 %** | 5,441.5 (5,440-5,443) |

- The 16K mean carries one slow pass (community pass 1: 4,486); the other five 16K runs were 5,343-5,363 (+40 %).
- Not the same hardware use: P028x keeps experts on both cards (5080 + 4060 Ti); Basalt runs on the 5080 alone
  (it refuses the 4060 Ti). Both KV int8.
- basalt-probe (29 s) suggested nothing beyond the defaults (it measured decode cold prose 135 / conv 160 / struct 205
  at a 4K context; experts 5,052 slots on the 5080, the rest in RAM).

## 2. Lossless tries (one pass each, against the by-hand defaults' 3-pass mean and spread)

Rule fixed before the gap (pick.py): a win needs a gain larger than the base's pass-to-pass spread and >= 2 %, with no
other measure down by more than its spread.

| try | result |
|---|---|
| --spec 7 / 10 / 6 | blend +2.2 % / +2.1 % / -0.5 % - inside the 2.9 % spread: no |
| --kv fp16 | blend -2.6 % (212.4; still +7.1 % over P028x's int8) |
| --prefill auto:8192 / auto:32768 | 16K -24.8 %, 64K -10.5 % / +0.1 %, +0.2 %: no |
| --prefill-cpu-share 0.4 / 0.8 | +-0.2 %: no |
| --vram-reserve-mib 400 / 256 (a bigger expert cache) | **not run**: at the default 700 the lowest 5080 free was 580-594 MiB, so 400 would leave ~294 MiB and 256 ~150 MiB, under our 300 MiB floor (block.sh refuses reserves under 460; the floor was not changed). A smaller cache would only be slower. |

**Best settings = the defaults.** Nothing measurable is left on the table among the lossless flags.

## 3. The 9-workload speed screen (basalt serve at the defaults vs gap 16's X arm = P028x)

Both through our client (abrun.py: W1-W3, agent x2, research4 x4; T 1.0 / 0.95 / 20 / min-p 0.05, effort medium),
131,072 context, KV int8, conversation cache off, 3 passes, a warm-up first. Rates on the client's clock (first to last
streamed token; prompt tokens / time to first token) - the same for both arms. Per pass the geometric mean over the 9
workloads (gap 16's form). Table: results/screen.md.

| | P028x (gap 16 X) | Basalt 0.2.0 | Basalt vs P028x |
|---|---|---|---|
| decode | 157.5 (spread 1.9 %) | 161.8 (spread 3.5 %) | **+2.8 %** (inside the spread) |
| prompt | 2,113.5 (spread 0.4 %) | 2,436.5 (spread 0.8 %) | **+15.3 %** |

- Prompts: long ones +21-27 % (R1 24K, R2 54K, R4 33K, W3 27K), short ones +5-17 %, A-edit level.
- Decode: chat and code +2-5 %, the long-context research calls -2 to -4 % (R1, R2, R4), A-edit +23 % (short,
  different completion lengths).
- Basalt's own stream timings agree with the client on the means (decode 162.4); one W1 row differed (server 163.9 vs
  client 199.1) and its prompt_ms is always 0, so its server-side prompt rate is not usable.
- Basalt's server ends long thinking itself (answer room: "thinking budget 2304 tokens, output cap 3072" on W1/W2),
  which changes the text, not the rate measured.

## 4. Basalt's default precision shortcuts - what a quality gate would have to check

Both are always on, with no switch, so Basalt at its defaults is **not lossless by our rule**:

1. **The int8 hyper-connection copy.** The pack stores the hc matrices in BF16; decode reads an int8 copy (one fp16
   scale per 32 inputs). The prompt path uses the BF16/fp16 numbers, so prompt and decode read different hc values.
   (Strata's equivalent, STRATA_HC_REQ8, is opt-in and off in all our configs.)
2. **The two-stage Q6_K output head.** Every verify window scores all 248,320 rows from a 2-bit copy and rescores
   exactly only the rows within 4 logits of the 64th-best approximate score; the rest keep approximate logits. The cap
   of 65,536 rescored rows per call (q6k_head.cu:354) is unchanged since 10-21, where our HEADCHECK found 2.2 % of
   verify rows with a true top-20 id not rescored (argmax different on 12). With spec 8 now the default, the cap can
   bind more often. **For our pack's Q6_K head** the two-stage head is recorded in every window; the exact re-run happens only for sampled requests with top_k 0 or above 64. logit_bias, penalties, grammar re-draws and scored (ppl) requests read the two-stage logits, approximate tail included (corrected 11-02 from the code - EXACT-HEAD-NOTES.md: the exact cases above are the docs' table for a Q8_0 head).

**Gate before any daily use:** (a) the head - over our workloads at spec 8, T 1.0 / top_k 20, count verify rows whose
top-20 ids or values differ from the exact Q6_K head, and the windows where the cap binds (zero for our rule, or a
fallback to the exact head when it binds); (b) the hc copy - teacher-forced decode-path logits (on the exact-head build, so the head does not mix in)
against P028x and the Q8_0 base on our yardstick (mean, p90, KL > 1, changed top-1, text NLL, within the references' spread); (c) seeded
spec 8 vs spec 0 texts plus our chi-square / near-tie sampling checks; (d) how often the thinking-loop safeguard (on by
default) fires on long thinking.

## What happened in the gaps (our side, fixed)

- The reserve tries would have broken the 5080 floor: refused in block.sh during gap 1 (before they were reached).
- pick.py read no by-hand run in the gap: guard.py appends its summary line to Basalt's JSON output. Reader fixed
  (first JSON object); the pick rerun offline from the saved files gives the same answer the gap used (best = defaults).
- Gap 1's screen got HTTP 404 on every request: 0.2.0's server answers before the engine has loaded, and it refuses a
  request that does not name the served model (our client sends "x"). block.sh now waits for /health "loaded" and names
  the model; gap 2 ran the screen.

Files: results/summary.txt, runs.md, pick.txt, screen.md, probe.txt, community-rows.json (local copy; nothing
submitted), comm-*.md, man-*.json, screen/*.jsonl, watch.tsv. Pack (82 GiB) and build kept; deleting them needs Karl's OK.
