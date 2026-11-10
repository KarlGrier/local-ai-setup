### Phase 0 — the update to Strata v0.1.30 (v0.1.28, v0.1.29, v0.1.30)

Round 8a never ran, so Phase 0 started from C\*7 (v0.1.27 + 13 patches). The tag watcher found **v0.1.30** (the newest
release; branches `main` and `rc/0.1.30`). v0.1.27 → v0.1.30 is 103 commits in 120 files.

**What matters for this PC and config** (release notes in `work/r8/release-notes.txt`):

| release | change | on our config |
|---|---|---|
| 0.1.28 | the expert cache reserves the draft head's VRAM (+86 MiB here) | applies: −47 cache slots at the same `--vram-reserve-mib`; compensated (below) |
| 0.1.28 | a request cancelled during its prompt read no longer fails the next one (#183/#205) | applies: the same bug as our patch 0013, fixed another way (clear the stale error per request and in `Prefill::run`) |
| 0.1.28 | `/status` needs the API key, constant-time key check, tool calls with `</parameter>` in values | applies (harmless; we bind 127.0.0.1 without a key) |
| 0.1.29 | **sampled answers: split top-k over the whole GPU (#197)** — the same tokens | **applies: the big win** (below) |
| 0.1.29 | QSA block scores read once per window (#187), GDN prompt recurrence pipelined (#188), both bit-identical | applies |
| 0.1.29 | correctness fixes (#154): NaN in bf16, the q8 split GEMV barrier, unresolved KV-streaming blocks masked | applies (no change on our texts: see accuracy) |
| 0.1.29 | pinning with a helper GPU still capped at 8 GiB | our Linux fix (patch 0011) kept and verified |
| 0.1.30 | every expert streams from 1,024-token chunks (was 2,048) | applies to prompts / appended reads of 1,024–2,047 tokens |
| 0.1.30 | conversation cache (#189, opt-in) | compared with ours (below) |
| 0.1.30 | `STRATA_IQ_MT_MIN=1` (opt-in), coupled draft sampling (opt-in), idle unload, rope scaling, resident low-RAM variant, shared arena, layer-split carve | off (as you asked); `STRATA_IQ_MT_MIN` / coupled drafting are Phase A test settings only |

**The port** (branch `r8-port`, `patches/r8/`): C\*7's patches 0001–0012 on v0.1.30; **0013 not ported** (upstream's
fix). Merges: `server.py` twice (both sides kept), our GR v5 kernel file (Round 7's merge + upstream's pre-Volta
capacity rule), and the pin-cap patch (upstream moved the code; re-applied where it now lives). **One real port bug,
found by the compiler:** upstream's new conversation cache declares a local `parked` that hid our chat cache's store of
the same name inside the request loop. Our store is renamed `chat_parked`.

**VRAM.** 0.1.28 now reserves the draft head (+86 MiB) inside the cache: 4,513 instead of 4,560 slots at our 800 MiB
reserve. `--vram-reserve-mib 713` gives exactly C\*7's 4,560 slots and 490 MiB free, so C\*8 keeps C\*7's memory
layout.

**Pinning (0.1.29 still caps it at 8 GiB with a helper GPU):** our fix keeps the whole arena registered on Linux.
Verified: the engine logs "cudaHostRegister PORTABLE ok" (not "limited to 8 GiB"), and every expert the prompt path
streams goes by DMA (32K: 89,692 of 89,692; 112K: 313,922 of 313,922), which is only possible from registered memory
(with the cap, Round 6: 15,120 of 88,032). The process's VmPin counter cannot show it: it reads 0 for C\*7 too, because
the NVIDIA driver's pins are not counted there.

**Measured on its own** (engine level, cold page cache, guarded; `results/r8/…`):

| check | result |
|---|---|
| greedy decode, exact flags, **binding fixed cache** (`--expert-cache 3500` = 4,551 experts), math / code, helper and one GPU | **bit-identical to C\*7** (ab1c7748 / 58cd4381 / one-GPU 9ad3650e), same window histograms, same ms per round |
| the same sampled (seed, T 1.0, top-p 0.95, top-k 20), all sampler variants | **the same tokens** in C\*7, the port's default split sampler, `STRATA_OLD_SAMPLER=1` and `STRATA_SAMPLER_ONE_BLOCK=1` |
| ms per verify round, sampled, math / code (2 runs each) | C\*7 34.31 / 22.36 → **split 32.06 / 19.80** (−2.4…−2.6 ms per round; old sampler = C\*7) |
| prompts 32K / 112K (cold, CLI) | 9.59–9.64 → 9.47–9.50 s (−1.3 %); 32.30 → 31.92–31.94 s (−1.1 %) |
| 1,024-token stream threshold, 1,100–4,000-token prompts, fixed cache | the same output at either threshold |

My mistake on the way: the first exact pairs looked different (first difference at tokens 345 / 89). The cause was my
method, not the update: in CLI runs the port sizes its draft-head reservation from the prompt length (85 or 86 MiB), so
its cache came out 1–2 slots bigger than C\*7's, and an explicit `--expert-cache N` larger than fits is capped by free
VRAM. With a binding explicit size the outputs are bit-identical. Every exact comparison this round uses
`--expert-cache 3500`.

**Served A/B, C\*7 vs the port, 4 alternating pairs** (fresh guarded server and cold page cache each; your settings;
`results/r8/ab-c7-r8.md`):

| | C\*7 (4 runs) | **v0.1.30 port (4 runs)** | change |
|---|---|---|---|
| decode, all 768+-token answers | 92.3–95.5 (93.7) tok/s | **105.2–106.1 (105.8)** | **+13 %**, no overlap |
| ms per verify round (≈ 2.0 tokens per round, acceptance 0.64–0.66 both) | 20.7–21.5 | 18.4–19.0 | −2.4 ms |
| long reasoning math / code (8K) | 104.3 / 86.7 tok/s | 116.6 / 98.9 | +12 % / +14 % |
| 32K / 64K / 120K prompt | 9.64–9.68 / 18.64–18.70 / 35.16–35.31 s | 9.51–9.54 / 18.38–18.42 / 34.75–34.78 s | −1.2…−1.4 % |
| 1K prompt | 0.96–0.98 s | 0.98–1.01 s | +3 % (below) |
| memory | 15,418 MiB, MemAvailable ≥ 27.3 GB, RSS 57.5 GB | the same | = |

**Short prompts (0.1.30's 1,024-token rule)**, served with warm-up, 2 fresh servers per arm, engine prompt time
(`results/r8/shortprompt-table.md`): 1,066 tokens 838 → 892 ms (+6 %, slower); 1,578: 1,011 → 909 ms (−10 %);
2,042: 1,208 → 957 ms (−21 %); 3K–5K unchanged; a 1,853-token tool result 1,147 → 1,051 ms (−8.5 %); short follow-ups
(60–145 tokens, read by verify windows) unchanged. The break-even on this PC is ~1.25K tokens (upstream measured 1,024
on an RTX 5070 with Q2_0). Output is the same either way, so the threshold is a free config choice (Phase A).

**Conversation cache: upstream's #189 vs ours** (same binary, KV streaming + helper; switch test + an 8-chat test;
3 runs each; `results/r8/conversation-cache-table.md`):

| | our chat cache | #189 |
|---|---|---|
| back to a parked chat | 0.36–0.75 s | 0.36–0.78 s |
| first request of the other chat: short / reasoning / 64K paste | **0.51–0.52 / 0.57–0.58 / 18.29–18.31 s** | 0.67–0.69 / 0.63–0.64 / 18.39–18.45 s |
| park 40K / 64K | 78 / 128 ms | 215 / 260 ms |
| 8 chats: 6 slots / 8 slots | LRU thrash / all kept | the same |
| engine peak RSS / lowest MemAvailable | **53.8–54.7 / 31.3–32.3 GB** | 57.3–58.4 / 27.4–28.6 GB |
| park → resume, resume + edit (static experts, 1,536 forced tokens) | **exact** | **exact** |

**Kept ours.** #189 snapshots the outgoing chat before every switch and every rewind (edit, regenerate), also for
tiny chats, 2–3× slower per park, and retains ~3.5 GB more RAM in this traffic — against your 20 GB MemAvailable floor
that matters. It does some things better (validation before restore, a RAM admission floor, keeping the pre-edit
branch). Written up for upstream: `pr-drafts/27-conversation-cache-vs-chat-cache.md`.

**Checks on the candidate** (C\*8 = v0.1.30 + `patches/r8/0001–0012`):

| check | result |
|---|---|
| accuracy: teacher-forced, 7 texts, one GPU and helper, binding fixed cache | **bit-identical to C\*7**: 1,536/1,536 NLL values equal on every text (`results/r8/tf-compare.txt`) |
| harder needle set (12 documents × 6 questions, 32K/64K/120K) | **72/72** (TTFT 9 / 18 / 35 s) |
| chat-cache round trip | **exact** |
| stop120k (Stop during a 120K read, next request, back to the parked chat) — upstream's fix alone | **7/7** (unfixed v0.1.27 failed "back to chat A") → 0013 dropped |
| headless-Chrome browser test (on a config copy) | **52/56**: the two known non-bugs (a 110-token chat is not parked by design; favicon 404) + 2 web checks blocked by SearXNG (both engines "too many requests": 0 results, so nothing to cite); all web mechanics pass; Stop during a 32K read → idle in 1.3 s, next request normal |
| clean build | `engine-cstar8/strata` sha256 `381892ab…`, tree `1bc2dce5` = the tested port (`work/r8/build-cstar8.sh`) |
| launcher fallback (4060 Ti short of memory) | pass |
| 2-hour soak | (below) |
