# Round 16 — summary

**Status (2026-10-08 22:50) — done. C\*16 (Strata v0.1.41 + our 27 patches) is on 127.0.0.1:8080**, promoted 22:24 after
every gate, the acceptance suite (11 pass / 0 fail), a 2-hour soak (439 requests, 0 errors) and a real rollback test (C\*15
answered, then C\*16 again). Rollback: stop 8080, `STRATA_CONFIG=configs/Cstar15.json ./switch-model.sh strata`. Full
report: REPORT.md "Round 16". The monitor stayed on the motherboard output all round. Base v0.1.41 (fb58e0db) = the newest
tag at the start and at the promotion (no v0.1.41.x appeared); nothing was fetched or downloaded.

**What changed upstream that matters**
1. **A CPU prompt-read share, on by default — also on your two-card config.** Short prompts and every chat turn's new text
   read 16–17 % faster, but with rounding that depends on timing (outputs don't repeat run to run). **Off in C\*16** (below).
2. **Server fixes on your Open WebUI → 8080 path:** a frozen engine is ended and restarted (#1317 part 2), malformed /
   oversized request bodies get a 400 / 413, `<function= NAME>` tool calls are parsed, listen backlog 256.
3. Pinned stage buffers are opt-in (upstream's gate saw them corrupt IQ3_S decode): off here. File-tier work acts only when
   experts come from the SSD. Everything else is numerically silent here or opt-in.

**Step 1 — the share (`STRATA_PREFILL_CPU_SHARE`)**: on vs off, A B B A, 12 prompts per size per build:

| prompt | share on | share off | C\*15 |
|---|---|---|---|
| 512 tokens | **581 ms** | 694 ms | 692 ms |
| 1,000 tokens | **717 ms** | 861 ms | 864 ms |

Long-text NLL check: PASS (it moves long texts exactly as much as two known rounding-level switches do; no bias, −0.010
nats). **Acceptance suite: 10 pass, 1 FAIL** (chat-cache round trip — the share's timing-dependent rounding makes two
identical builds of a chat differ). **Your rule → set to 0.**

**Step 2 — C\*16 vs C\*15 and C\*14** (A B C C B A, two arms each):

| | C\*15 | **C\*16** | vs C\*15 | C\*14 | vs C\*14 |
|---|---|---|---|---|---|
| LDR screen tok/s | 137.8 | **138.4** | +0.4 % | 141.8 | −2.4 % |
| decode screen tok/s | 140.8 | **138.8** | −1.4 % | 143.8 | −3.5 % |
| full screen tok/s | 141.7 | **142.3** | +0.5 % | 144.8 | −1.7 % |
| TTFT 8K / 32K / 120K (s) | 2.20 / 7.73 / 29.90 | **2.19 / 7.69 / 29.74** | −0.4 / −0.6 / −0.6 % | 2.20 / 7.74 / 29.91 | −0.4 / −0.7 / −0.6 % |

**The 2–3 % gap to C\*14 has not closed.**

**Step 3 — promoted as C\*16** — not ≥ 1 % faster, but it carries the server fixes (your rule). It computes exactly what
C\*15 computes (exact7 7/7 = C\*15's hashes). Gates as C\*15's: needles 12 × 6/6, Stop at 120K, follow-ups, stops, #931 control
text, repeat 3/3, round trips identical, browser 41 / 2 (the same two). Acceptance suite 11 / 0. Soak 439 requests, 0
errors, back to a big chat 0.61 s median, MemAvailable ≥ 22.2 GB, soaked decode = fresh (+1.6 %). A 48-hour monitor runs.

**Q4 check (not promoted; configs/r16-q4.json)** — UD-Q4_K_XL on the same build, the 5080 + 66 GiB RAM (every expert the
5080 does not hold; prompt chunks still read their borrowed slots' experts from the SSD → unbuffered reads), your 6 GiB
floor (min 12.9 GiB):

| | IQ3_S (C\*16, served) | UD-Q4_K_XL |
|---|---|---|
| decode screen | 138.8 tok/s | **68.7 tok/s** (−51 %) |
| LDR screen | 138.3 tok/s | **64.0 tok/s** (−54 %) |
| TTFT 32K / 120K | 7.69 / 29.74 s | **11.66 / 34.35 s** |
| needle 120K | 6/6 | **6/6** |

**My slips** (all recorded): `pkill -f` matched my own shell again; a prompt-builder loop; two dead starts of step 1 (a
non-executable script, the wrong config tool); a first long-text check whose forced text no longer continued its prompt;
two waits that returned early; the Q4 run started buffered and was restarted with unbuffered reads after a minute.
