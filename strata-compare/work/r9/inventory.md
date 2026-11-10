# Round 9, Phase 0.2 — inventory: what C\*10 changes against stock Strata v0.1.31

C\*10 = v0.1.31 (`9259cad`) + `patches/r9/0001–0013` (branch `r9-pr245`, tree `430fc30e`), engine `f3ff83cd…`.
`git diff --stat v0.1.31 r9-pr245`: **20 files changed, 2,378 insertions(+), 60 deletions(−)**
(engine, kernels and build: 1,580 + / 30 −; server and web app: 798 + / 30 −).

## 1. Patches (patches/r9)

Classes: (a) exact = bit-identical output; (b) rounding-level; UI/serve = no effect on the numbers the engine computes.

| # | what it does | files | lines + / − | measured effect (round) | class | upstream equivalent in v0.1.31? |
|---|---|---|---|---|---|---|
| 0001 | `--side-stash N`: a short unrelated request (a client's title/tag request) runs beside the cached chat instead of evicting it | generate.cpp | 131 / 0 | turn-7 TTFT 4.75 s vs 26.8 s with side requests (R1). **Dormant in C\*10's config:** with `--chat-cache` on, the chat cache parks instead (R3) | serve | partly: #189 conversation cache (opt-in) also survives side requests, by snapshotting |
| 0002 | `--chat-cache N` / `--chat-cache-mib`: parks other conversations' positional state in RAM, restores on return | generate.cpp | 166 / 1 | back to a chat 0.36–0.75 s instead of a full re-read (40K chat after a 64K paste elsewhere: 23 s before) (R3); vs upstream #189: switching 0.06–0.18 s faster, 3.5 GB less RAM, both exact (R8) | (a) exact (round trips 1,536/1,536) | **#189 `--conversation-cache-mib`** (0.1.30, opt-in): same job, measured slower to switch and +3.5 GB RAM (R8) |
| 0003 | web app: chat list (several chats, switch, delete + undo), attached files keep their text after a reload | app.js, app.css, index.html | 136 / 13 | UI | — | no: the stock page keeps one chat |
| 0004 | chat cache keeps the shared-prefix (root) checkpoint with the session when it parks | generate.cpp | 9 / 2 | keeps 0.1.20's root checkpoint working with our chat cache (R5) | (a) | n/a (fixes 0002 against upstream's root checkpoint) |
| 0005 | Web search switch: `web_search` / `fetch_page` run by the server against the local SearXNG; tool cards in the page | server.py, websearch.py (new), app.js/css, index.html, sprite.svg | 582 / 14 | feature (R5); browser test web checks pass; R9: live 3/3, replay 4/4 | serve | no built-in search; upstream has generic MCP tools (`serve/mcp.py`, opt-in) |
| 0006 | web search: today's date in `web_search`'s description; `www.host` = `host` in fetch_page's allow-list | websearch.py | 15 / 2 | fixed "July 28" stale-date searches and refused fetches (R5) | serve | — |
| 0007 | Stop during a long prompt read takes effect within one chunk (the server watches the socket every 0.25 s and sends STOP at once) | server.py | 56 / 6 | 120K paste stopped at 20 s: server idle 3.0 s after the close instead of 11 s; 32K: read stops in ~2 s instead of reading to the end (R5) | serve | no: stock notices only when a keep-alive write fails (2–3 chunks late) |
| 0008 | web app: two tabs keep each other's chats (index re-read before every change + `storage` event) | app.js | 22 / 8 | bug fix (R5 browser test) | UI | n/a (stock has one chat) |
| 0009 | GR v5: faster multi-token hyper-connection reads (down split over the rows' length, 4 partial sums in a fixed order; norm in registers) | fused_gr.cu, fused_gr.hpp, mtp.cpp, verify.cpp | 331 / 2 | one GR read 39.9 → 32.4 µs (T 1), engine decode +2.3 % (R4); `STRATA_GR_OLD=1` / `STRATA_GR_V3=1` switch back | (b) rounding (max 1.2e-4 relative; TF within spread) | **partly: v3 (`STRATA_GR_V3=1`, opt-in, "another summation order")** — Phase 0.3 measures it |
| 0010 | `--dump-routing` writes only the verify-window rows that are kept | generate.cpp | 38 / 7 | measurement tool fix, no runtime effect unless the flag is given (R6) | (a) | no |
| 0011 | the next window's first-token n-gram rows are read while the window commits and the drafter runs | verify.cpp/.hpp, ngram.cpp/.hpp | 35 / 1 | n-gram staging 0.61 → 0.28 ms per window; windows −1.0…−3.7 % (R6; part of C\*6's +4.1 %) | (a) exact (off = on = a wrong prefetch, bit for bit) | no |
| 0012 | prompt MMQ reads streamed experts in their ring slots (per-expert byte offsets below the weight address; no per-expert gather) | moe_mmq.cu/.hpp, prefill.cpp, CMakeLists.txt (edits ggml's mmq.cuh in the build tree) | 183 / 20 | TTFT −2.8 / −2.9 / −3.0 % at 32K / 64K / 120K (R8) | (a) exact | no |
| 0013 | upstream PR245 (fork Eddoursul `cf307ea` + `8208f3f`): the verify window's grouped GPU experts in two kernels (gate/up + SwiGLU + q8_1 in one, down 4 rows per warp) | iq_kernels.cu, iq_dot_pr245.cuh (new) | 690 / 0 | decode +4.5 % served (R8), bitwise kernel parity on sm_120 + sm_89, sanitizer-clean | (a) exact | **PR #245 itself is not merged**; v0.1.31's own "decode once" grouped path (8ec94aa) brings ~0 here (R8 Phase D: 6–9 % slower per round without 0013) |

## 2. Config: C\*10 vs stock defaults (S0 = what v0.1.31's setup writes for one 16 GB card)

| setting | stock default (S0) | C\*10 | measured effect | round |
|---|---|---|---|---|
| `--pcie-frac` | engine's probe → 0.55 | **0** (CPU computes every expert missing from VRAM) | decode ×1.9 at v0.1.6 (46.9 → 92.7 tok/s); upstream's own calibration picks 0.2 here (93.0 vs 82.3 at 0.55; 0 kept: equal or better in exact profiles and a full screen) | R1, R5 |
| `--expert-cache-device1 3300` + `CUDA_VISIBLE_DEVICES` = both cards | off (one card) | **4060 Ti as a helper cache** (3,300 more experts) | decode +4.1 % with our pin fix (89.9 → 93.6), loss without it; since 0.1.31 upstream pins on Linux too (#253) | R6, R8 |
| `CUDA_MODULE_LOADING` | EAGER (set by the engine since 0.1.15) | **LAZY** | +~250 MiB VRAM free (eager left 220 MiB after one request, < your 300 MiB floor) | R4 |
| `--vram-reserve-mib` | 700 | **713** | keeps C\*7's 4,560 slots / 490 MiB free after 0.1.28 moved the draft head into the cache | R8 |
| draft vocabulary (MTP folder) | **cjk** subset (setup's default since 0.1.27) | older **en/code** subset | upstream: en = ~110 MiB less VRAM, English answers 1–2 % faster; not measured here yet (S0 vs S1 includes it) | — |
| `STRATA_IO_THREADS` | 16 | **64** | n-gram reads p50 164 → 106 µs; prompt n-gram time 2.40 → 2.00 s at 32K (as STRATA_PLE_IO_THREADS) | R2 |
| `--ple-inflight` | 64 | **128** | (with the above) | R2 |
| `--chat-cache 6 --chat-cache-mib 16384` | — (needs patch 0002) | on | see 0002 | R3, R8 |
| web search block | — (needs 0005) | SearXNG on 127.0.0.1:8888 | see 0005 | R5 |
| your choices (both) | — | 131,072 context, sampling block (min-p 0.05) + shared settings (effort high = xhigh, T 1.0, top-p 0.95, top-k 20) | — | — |
| S0 only (guard) | — | — | S0 needs `--vram-reserve-mib 800` to keep 300 MiB free (stock 700: 284 MiB after one request) | R9 |

Settings that are the SAME as stock: `--expert-cache auto`, `--prefill auto` (8,192-token chunks here), `--spec 4`,
`--spec-min-p 0.5`, `--kv int8`, `--kv-resident 32768`, the expert profile, 15 pool workers (engine default), suffix
drafts on, adaptive tier on (adapt-every 4).

## 3. Patches retired because upstream shipped the same thing

| our patch | round added → retired | upstream's version |
|---|---|---|
| server default `max_tokens` (a client without max_tokens was cut at 1,024) | R1 → R1 | v0.1.7 |
| parallel O_DIRECT n-gram reads on Linux (`0001`, R1: 32K TTFT 31.8 → 22.7 s) | R1 → R5 | v0.1.22's n-gram reader thread pool (`STRATA_IO_THREADS`; we keep 64 threads) |
| batched layer-1 n-gram block (`0003`) and next chunk's rows read ahead (`0004`) | R3 → R4 | v0.1.13 |
| `--pool-workers 15` (Linux counted SMT siblings as cores) | R1 (flag) → R4 | v0.1.14: one worker per physical core |
| `--prefill 4096 / 8192` | R1/R3 (flag) → R4 | v0.1.13's `--prefill auto` (8,192 here) |
| verify: copy back only the CPU experts' rows (`0002`, draft 05); router + indexer q/k projections as one multi-token GEMV (`0003`) | R4 → R5 | v0.1.23 #109 (batched verify window) |
| Linux pin cap: register the whole expert arena with a helper GPU (`0011`) | R6 → R8 (Phase D) | v0.1.31 #253 |
| Stop during a prompt read made the next request fail (`0013`, stale error) | R7 → R8 | v0.1.28 #183/#205 |

Dropped for no gain (not upstream): THP for the expert arena (R1), the thread-affinity fix (R8).
