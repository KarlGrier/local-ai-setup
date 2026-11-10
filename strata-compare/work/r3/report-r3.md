

## Round 3 — engine optimization (2026-09-27 23:21 → 2026-09-28)

**Result: C\*3 = Strata v0.1.12 + 8 patches (6 new) + C\*2's flags, with `--chat-cache 6` instead of `--side-stash`.**
It reads prompts **8.5 % faster** (32K: 17.5 s instead of 19.2 s; 120K: 68 s instead of 75 s), decodes **~2 % faster**
(exact A/B of the two decode patches +2.5 %; the sampled screens +1.6 %, inside their noise), and — the big change for
daily use — **going back to a chat you left no longer reads it again**: a 40K-token chat after pasting a 64K document
into another chat answers in 0.5 s instead of 23 s. Accuracy is unchanged (teacher-forced perplexity: the only
non-bit-exact change is inside the spread of a harmless chunk-size change). The chat page gets a chat list (it had
only one chat) and keeps attached files across a reload. Same VRAM; up to 16 GB more RAM for kept chats.
It passed a 37-minute soak shaped like the chat page (67 requests over 22 chats, 0 errors).
Config `configs/Cstar3.json` (default of `run-strata.sh` and `switch-model.sh`); `configs/Cstar2.json` and
`engine-cstar/` are unchanged for rollback (`STRATA_CONFIG=configs/Cstar2.json ./switch-model.sh strata`).

### The Codex wait
The PC had rebooted at 23:18 (a clean reboot, before I started). Codex's telemetry-variance run
(`~/ai-speed-testing/telemetry-variance/20260928T030836Z`, Strata IQ3S + Unsloth Q4, 10/10 trials) had finished at
23:05, and its restoration log says it stopped its own servers ("initial no-model state restored"), so **Codex left
8080 empty**. A read-only watcher (`work/r3/watch.sh` → `logs/r3/watch.log`, one line per minute) showed no Codex
process, no GPU compute app and no model server from 23:23 on; at the 23:42 check (the second, 21 minutes after the
first) the 15-minute rule was met and benchmarks started. Until then I only read code, wrote patches and compiled.
The benchmark queue re-checked before every job (a Codex process or a foreign GPU app would have stopped my test
server and waited for 15 quiet minutes); it never triggered. **At the end port 8080 is empty, as Codex left it**, and no model server, monitor or queue of mine is running
(C\*3 was started on 8080 once through `switch-model.sh` to test it, then stopped).

**Method notes (things you should know):** (a) some of the first screens ran while I was compiling other variants
(nice 5, all cores); prompt-reading times were unaffected (the reference and base screens agreed to 0.01 s), but to
be safe the final C\*2-vs-C\*3 comparison below was run on an otherwise idle machine, both alternately and twice.
(b) Installing two small Python packages into the workspace venv (for the web-app test) made pip write 18 cache files
under `~/.cache/pip` — outside the workspace; I removed exactly those files. Nothing else was written outside the
workspace (nsys used the workspace `tmp/`). (c) Round 2's profile table labelled "sampled" was in fact greedy (see
item 6); its conclusions about where the time goes still hold, and the screens and soak were sampled.

### 1. Chat page settings
What the chat page (v0.1.11/v0.1.12 `serve/web/app.js`) sends with its built-in settings (read from the source, then
run through the server's own request code offline — `work/r3/chatpage_check.py`):

| | the page sends | what the engine gets (C\*2 / C\*3 config) | your setting |
|---|---|---|---|
| thinking | `reasoning_effort: "high"` ("High" in the drawer) | **xhigh** — the template maps high → xhigh; the rendered prompt is token-identical to "xhigh" (98/98 tokens, the "Reasoning effort is set to xhigh" line) | xhigh ✔ |
| temperature / top-p / top-k | 0.6 / 0.95 / 20 (always sent, unless temperature 0) | 0.6 / 0.95 / 20 | ✔ |
| min-p | **not sent** (the page has no min-p field) | **0.05 from the config's `sampling` block**; without that block it would be 0 | 0.05 ✔ (via the config) |
| max tokens | not sent (drawer field empty) | the rest of the context (131,072 − 8 − prompt) | no cap ✔ |

So the page already used your settings — as long as the browser's saved drawer settings are the defaults and the
config has the `sampling` block (C\*2 and C\*3 do). No code change was needed. What I did, with Strata's own
mechanisms: kept the `sampling` block (0.6/0.95/20/0.05) in `configs/Cstar3.json` — the only place min-p can live —
and saved the same values as Strata's shared chat settings (`configs/Cstar3.shared-settings.json`: High, 0.6, 0.95,
20, no max; this is the file the drawer's "Use for other apps too" switch writes, so the switch shows as on and plain
API clients get the same). The shared settings cannot hold min-p or the word "xhigh" (only none/low/medium/high) —
suggestion for the author in `pr-drafts/08-web-min-p.md`.
**To check in your browser once:** open the chat page → Sampling (gear icon) → it should show Thinking **High**,
Temperature 0.60, Top-p 0.95, Top-k 20, Max tokens empty. If anything differs, press **Reset**, then **Apply**.

### 2. The GPU half of decode (nsys)
Traced with a measurement-only build (NVTX ranges on the host loop: per layer "wait" for the GPU's doorbell and
"pool" for the CPU experts; `nsys --cuda-graph-trace=node`; 120 windows after a 1K prompt; `work/r3/nsys.sh`,
`work/r3/nsys_analyze.py`, `logs/r3/nsys/*.analysis.txt`):

* **Launch overhead is not the problem.** Strata already runs each verify window as one CUDA graph (~3,000 nodes);
  the idle gaps between nodes total 0.6 ms per window. CUDA graphs: already there.
* A window (22.5 ms traced) = the 48-layer loop 20.5 ms + tail 0.83 ms (mostly the 521 MB output head) + outside it
  commit 0.54 ms and MTP drafting 1.16 ms. In the loop the GPU spends 14.5 ms working and 6.3 ms spinning for the CPU.
* **GPU critical path per layer** (from the CPU pool's flag to the next layer's doorbell): 205 µs into a GDN layer,
  265 µs into an attention (QSA) layer:

  | kernel group | µs per layer (GDN) | note |
  |---|---|---|
  | hyper-connection read (gr_down 37, gr_up 23, gr_norm 13) | **73** | 35 %; weights need ~29 µs at full bandwidth |
  | dense projections (native MMVQ) | 45 + 13 | ~700–900 GB/s = at bandwidth |
  | BF16 MMVF (router etc.) | 12 (QSA: 21) | one launch per token → fixed below |
  | GDN kernels | 15 | |
  | mapped copy of the CPU experts' rows | 8 | fixed below |
  | attention (QSA layers only) | 33 | |

* **Kept — patch 0005:** only the CPU's expert rows come back over PCIe (the GPU's own rows were zeros read over PCIe;
  now written on the device): 6.3 → 3.4 µs per layer, identical values.
* **Kept — patch 0006:** the router and the indexer projections as one multi-token MMVF per window instead of one
  launch per token, bit-identical (unit test), weights read once.
* Together, A/B on one binary (env switches), 3 runs each, identical windows run to run: **decode 112.5 → 115.35
  tok/s (+2.5 %), GPU wait per window 11.63 → 11.11 ms**; the trace shows the critical path −7.5 % (GDN 205 → 189 µs,
  QSA 265 → 245 µs).
* **Rejected — the hyper-connection kernels:** two restructurings with the same per-lane arithmetic (bit-identical by
  test) were slower (register pressure): the one real win (norm 4.6 → 2.9 µs) was eaten by `down` +14 % / `up` +7 %.
  This is the biggest GPU item left (~44 µs per layer above its bandwidth floor ≈ 2 ms per window ≈ 8–9 % decode);
  notes for the author in `pr-drafts/10-decode-trace-notes.md`.
* Also seen: the in-graph greedy sampler (~80 µs per window) runs even when the request samples — small.

### 3. GPU/CPU overlap
Measured per layer: the CPU pool takes **208 µs**; GPU work runs beside it for **74 µs (36 %)** — the VRAM-hit experts
and the shared expert. The rest is strictly serial: layer l+1's mixer needs layer l's MoE output, so the host waits
~219 µs per layer for the GPU and the GPU waits ~134 µs per layer for the CPU. That is why round 2's window added up
to GPU wait + pool.
More overlap without new RAM traffic: the only way around the dependency is to interleave two groups of the window's
tokens (Strata's opt-in `--spec-split`). Traced: the GPU's wait for the CPU drops (T = 4: 10.9 → 2.8 ms per window) and
the extra RAM traffic is small (7.79 vs 7.40 distinct CPU experts per layer, +5 %), but the GPU's own work grows
17.8 → 25.1 ms (dense weights and hyper-connection kernels run once per group), so T = 2 windows get 30 % slower and
T = 4 break even. **Not usable today; it becomes worthwhile only after the GPU's per-layer work shrinks** (the
hyper-connection kernels above). The CPU side cannot shrink: the pool streams ~73 GB/s = the RAM bandwidth.

### 4. Multi-chat cache
**The chat page had only one chat.** v0.1.11/v0.1.12's page keeps one conversation in the browser ("New chat" clears
it), so "switching between chats" was not possible in it. Patch 0008 adds a **Chats** list (the button with the speech-bubble icon in the
message bar): switch, delete (with Undo); **New chat keeps the old one**. It also fixes a v0.1.12
issue: an attached file's text was not saved with the chat, so after a page reload the next turn lost the file (and
re-read the whole chat). Tested with a JS engine against a stub browser (`work/r3/test_webapp.py`: 15 checks; it found
two bugs in my first version, fixed). **Not tested in a real browser** — please try it; if anything is off, the old
page is one command away (see "Rollback").

**Engine (patch 0007, `--chat-cache 6`, 16 GiB):** up to 6 other conversations stay in RAM — their checkpoints plus
their KV cells and indexer rows (with KV streaming those live in host RAM anyway). Switching to a parked chat copies
them back (27–45 ms) and resumes from its checkpoint; parking copies them out (70–130 ms). A chat is parked when a
request shares (almost) nothing with it — another chat, a document pasted elsewhere, an unrelated API call — but not
on an edit or regenerate. Least recently used first; chats under 512 tokens are not kept (re-reading is cheaper).

Time to first token going back to a chat (`work/r3/chatsoak.py switch`, requests exactly like the chat page, chat A
built to 39.6K tokens):

| going back to … | C\*2-style (v0.1.12 + side stash) | C\*3 (chat cache) |
|---|---|---|
| A (40K) after a short new chat B | 0.77 s | 0.81 s |
| **A after pasting a 64K document into new chat C** | **22.9 s** (A read again) | **0.97 s** |
| A after long reasoning in chat D | 0.35 s | 0.81 s |
| **C (the 64K-document chat)** | **38.0 s** | **0.47 s** |
| **A again** | **22.9 s** | **0.80 s** |

The same sequence on the final clean build (C\*3): back to A after B 0.81 s, after the 64K paste **0.53 s**, after
reasoning 0.39 s, back to C (64K) **0.44 s**, A again 0.48 s; the 64K paste itself 35.0 s (38.2 s before, thanks to
item 5); 0 errors.
**`--side-stash` re-evaluated:** it was built for Open WebUI's title requests; without Open WebUI the only side
requests are your own API calls. The chat cache covers that case too (0.81 vs 0.77 s after a short other request)
and the big-paste case the stash could not; it is off in C\*3 (the chat cache disables it; the flag is gone from the
config).
**RAM:** each parked 40K chat is ~1.25 GB (6 checkpoints of 118 MB + its KV cells); the budget caps the total at
16 GiB, so the engine can grow from ~51 GB to ~67 GB RSS; with ~90 GB installed that leaves ≥ 20 GB available.

### 5. Prompt reading
* **Patch 0003 — the layer-1 n-gram (PLE) block for the whole chunk:** the prompt path ran it token by token (~10
  launches and 65 MB of weight reads per token). Now two GEMMs (BF16 activations, like every other prompt-path
  projection) and 7 batched kernels that reproduce the per-token post-ops **bit for bit** (unit test at T = 1, 5, 37,
  8,192). No extra VRAM (it reuses layer scratch).
* **Patch 0004 — the next chunk's n-gram rows are fetched while the current chunk computes** (a helper thread,
  joined before use).

| | 32K prompt TTFT | 120K prompt TTFT |
|---|---|---|
| C\*2 (same night) | 19.15 s | 74.64 s |
| v0.1.12 base | 19.16 s | 74.72 s |
| + batched PLE | 17.86 s (−6.8 %) | 69.73 s (−6.7 %) |
| + prefetch (= C\*3's prompt path) | **17.51 s (−8.6 %)** | **68.31 s (−8.6 %)** |

(prompt noise between identical runs ±0.1 %)

### 6. Other things the traces and tests turned up
* **Upstream v0.1.12** (released last night) fixes a race in the CPU expert pool that could hang generation for good;
  C\*3 is built on it. Same speed as v0.1.11 here (prompt 19.16 vs 19.15 s).
* **`strata generate` ignores sampling in the speculative windows** (only `--serve` calls `set_sampling`), so every
  `generate --stats` profile — mine in round 2 included — ran **greedy**, although it passed `--temperature 0.6`.
  Correction to round 2: its "sampled" profile table was greedy (the screens and the soak, which go through the
  server, were sampled). Patch draft 0009 fixes it (not in C\*3's serving path). Upside: greedy profiles repeat the same
  windows, which made the decode A/B above exact to ±0.1 %.
* The Linux CPU-pool default (31 workers on SMT siblings) — patch draft 0010 (C\*3 sets `--pool-workers 15` anyway).

### Accuracy
Teacher-forced NLL (round-1 method: a fixed text scored through the same verify windows, expert cache and CPU pool as
decoding; `work/r3/tf.sh`, `work/r3/tf_table.py`, `results/tf-R3tf-*.nll`). New tonight: two long-context texts —
the first 16,384 / 24,576 tokens of the 32K test document as the prompt (read by the prompt path, so the batched PLE
is exercised) and the next 1,536 tokens scored.

| comparison | text | ppl A | ppl B | B − A (nats/token) | tokens that changed |
|---|---|---|---|---|---|
| determinism: v0.1.12 base run 1 vs run 2 | math | 1.3370 | 1.3370 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: v0.1.12 base run 1 vs run 2 | corpus | 1.4746 | 1.4746 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: v0.1.12 base run 1 vs run 2 | long16k | 16.1942 | 16.1942 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: C\*3 run a vs run b | math | 1.3366 | 1.3366 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: C\*3 run a vs run b | corpus | 1.4766 | 1.4766 | +0.0000 ± 0.0000 | 0 of 1536 |
| determinism: C\*3 run a vs run b | long16k | 14.3085 | 14.3085 | +0.0000 ± 0.0000 | 0 of 1536 |
| **C\*3 vs v0.1.12 base** | math | 1.3370 | 1.3366 | -0.0003 ± 0.0006 | 1418 of 1536 |
| **C\*3 vs v0.1.12 base** | corpus | 1.4746 | 1.4766 | +0.0013 ± 0.0016 | 1478 of 1536 |
| **C\*3 vs v0.1.12 base** | long16k | 16.1942 | 14.3085 | -0.1238 ± 0.0267 | 1529 of 1536 |
| **C\*3 vs v0.1.12 base** | long24k | 31.1768 | 23.0973 | -0.3000 ± 0.0309 | 1536 of 1536 |
| C\*3 with the old per-token PLE vs base (isolates patch 0003) | long16k | 16.1942 | 16.1942 | +0.0000 ± 0.0000 | 0 of 1536 |
| C\*3 with the old per-token PLE vs base (isolates patch 0003) | long24k | 31.1768 | 31.1768 | +0.0000 ± 0.0000 | 0 of 1536 |
| sensitivity: base, --prefill 4096 vs 8192 (a rounding change accepted in round 2) | long16k | 16.1942 | 15.3014 | -0.0567 ± 0.0225 | 1526 of 1536 |
| sensitivity: base, --prefill 4096 vs 8192 (a rounding change accepted in round 2) | long24k | 31.1768 | 21.7156 | -0.3616 ± 0.0284 | 1533 of 1536 |
| sensitivity: C\*3, --prefill 4096 vs 8192 | long16k | 14.3085 | 25.5158 | +0.5784 ± 0.0363 | 1534 of 1536 |
| sensitivity: C\*3, --prefill 4096 vs 8192 | long24k | 23.0973 | 35.7257 | +0.4362 ± 0.0336 | 1535 of 1536 |

* **Runs are deterministic** for a fixed build and config (both base runs and both C\*3 runs identical, every text), so
  "run-to-run drift" is zero here; the yardstick is the effect of a harmless rounding change instead (`--prefill`
  4096 vs 8192 — a change round 2 made to C\*2).
* **Everything in C\*3 except the batched PLE is bit-exact:** C\*3 run with the old per-token PLE reproduces v0.1.12
  exactly on both long texts (0 of 1,536 tokens differ).
* **Short texts** (the round-1/2 method): −0.0003 and +0.0013 nats/token — the same size as round 2's accepted
  changes (+0.0001 / +0.0021).
* **Long texts are chaotic:** the chunk-size change alone moves them by −0.06 to +0.58 nats/token (a few tokens copied
  from far back flip between NLL ≈ 0 and 8–14 — sparse attention's block choice). C\*3's shift (−0.12 / −0.30, i.e.
  slightly better) is inside that spread. **Accuracy criterion met.** (The sensitivity itself is a finding for the
  author: `pr-drafts/10-decode-trace-notes.md`.)

### C\*3 vs C\*2 (screens with your sampling, fresh server, cold page cache, quiet machine, 2 runs each)
Final comparison, run back to back on an otherwise idle machine (nothing compiling), sampled with your settings,
fresh server and cold page cache each time; C\*2 = `configs/Cstar2.json`'s engine and flags (R3-ref), C\*3 =
the clean build with `configs/Cstar3.json`'s flags (R3-final):

| | C\*2 (2 runs) | C\*3 (2 runs) | change |
|---|---|---|---|
| time to first token, 32K prompt | 19.15 / 19.15 s | **17.49 / 17.49 s** | **−8.7 %** |
| time to first token, 64K prompt (switch test) | 38.2 s (v0.1.12 base) | **35.0 s** | −8.5 % |
| time to first token, 120K prompt | 74.6 / 74.6 s | **68.3 / 68.3 s** | **−8.4 %** |
| going back to a 40K chat after a 64K paste elsewhere | 22.9 s (v0.1.12 + side stash = C\*2's behaviour) | **0.53 s** | −98 % |
| going back to the 64K-document chat | 38.0 s (same) | **0.44 s** | −99 % |
| decode, all requests (tokens ÷ decode time) | 92.1 / 90.0 tok/s | 91.6 / 93.5 tok/s | +1.6 % (noise ±1.5 %) |
| time per verify window at equal window size | 26.04 ms (2.34 tok/window) | 25.61 ms (2.35 tok/window) | −1.7 % |
| decode, exact A/B of the two decode patches (identical windows) | 112.5 tok/s | 115.35 tok/s | **+2.5 %** |
| long xhigh reasoning, 8,192 tokens (math) | 97.5 / 96.7 tok/s | 99.2 / 100.2 tok/s | +2.7 % (noise ±2.4 %) |
| short prompts (70–90 tokens) / 1K prompt TTFT | 0.68–0.77 s / 1.40–1.44 s | 0.67–0.74 s / 1.34–1.40 s | −0.04 s on 1K |
| peak VRAM used / free (desktop incl.) | 15,383 MiB / ~477 MiB | 15,381 MiB / ~477 MiB | = |
| engine RSS / lowest MemAvailable (screens) | 51.0 GB / 36.1 GB | 53.7 GB / 33.4 GB | +2.7 GB (parked chats) |

### Soak (chat-page-shaped, 35 min)
`work/r3/chatsoak.py soak` against C\*3 (the clean build on 8081, the same requests the chat page sends: whole
history, no thinking in earlier replies, xhigh, 0.6/0.95/20, no min-p, **no max_tokens**), random actions over 22 chats:
new chats, mt-set turns of ~5.6K tokens, short follow-ups, 10 pasted 32K/64K documents, 4 long reasoning chats (one
regenerate thought for 10.5 minutes, ~60K tokens, before its first answer token), 49 presses of Stop (1–8 s into an
answer), 9 regenerates, and switching between chats at random.

| | result |
|---|---|
| requests / errors | **67 / 0**; health OK at the end; engine log: no error, stall or watchdog lines |
| continuing a chat (48 requests) | TTFT median **0.70 s**, max 4.0 s (a turn that added a 5.6K-token message); prompts > 8K tokens: median 0.84 s with 86 % of the prompt reused |
| new chats / pasted documents (19) | median 0.83 s; a 64K paste 34.9 s |
| chat cache | 26 parks, 15 restores, 5 least-recently-used drops (22 chats > 6 slots) |
| memory | engine RSS 50.0 → 55.5 GB; lowest MemAvailable 31.5 GB; swap 0 |
| VRAM | 15,365–15,379 MiB used the whole time (~480 MiB free) |

### Rejected / not done
| tried | result | why not kept |
|---|---|---|
| CUDA graphs | already used (one graph per verify window, ~3,000 nodes); gaps between nodes 0.6 ms/window | nothing to gain |
| faster hyper-connection kernels (two bit-identical restructurings) | norm 4.6 → 2.9 µs, but down 20.2 → 23.0 µs, up 12.9 → 13.8–20.7 µs | slower overall (register pressure); the biggest GPU item left, handed to the author |
| `--spec-split` (overlap CPU and GPU across two token groups) | T = 2 windows +30 %, T = 4 even; +5 % RAM traffic | GPU-bound: dense weights and GR kernels run twice |
| `--side-stash` | superseded by the chat cache (same 0.8 s after a short other request, and it also covers big pastes) | removed from the config |
| skipping the in-graph greedy sampler when sampling | ~80 µs per window (0.3 %) | not attempted — too small for the risk |

### Files
* `configs/Cstar3.json` + `configs/Cstar3.shared-settings.json` — C\*3 (default of `run-strata.sh` and
  `switch-model.sh`). `configs/Cstar2.json`, `configs/Cstar.json`, `engine-cstar/` are unchanged (sha256 checked).
* `engine-cstar3/strata` (sha256 `050508dd…`, `SOURCE`), built by `work/r3/build-cstar3.sh` from a clean clone of
  v0.1.12 + `patches/r3/0001-0008`; `strata-cstar3/` = that checkout (the server and the chat page are served from it).
  Its tree is identical to the tested branch.
* `patches/r3/` — the 8 patches of C\*3. `pr-drafts/` — issue/PR drafts for the Strata author (README + 10 drafts +
  `patches/` with two more fixes: generate sampling, Linux physical cores). Nothing posted.
* Scripts: `work/r3/` (queue with the Codex guard, screen, nsys trace + analysis, TF, chat-page soak client, unit tests
  `test_ple_batch.cu`, `test_gr_multi.cu`, `test_mmvf_multi.cu`, `test_webapp.py`, config maker). Logs `logs/r3/`,
  traces `logs/r3/nsys/`, requests in `results/runs.jsonl` (configs `R3-*`), TF in `results/tf-R3tf-*`, notebook
  `NOTES.md` (round 3 section).
* Development tree: `strata-r3/` (git worktree, branches `r3-*`; `r3-final` = the C\*3 series, `r3-final-plus` = + the
  two extra fixes).

### Daily use and rollback
```
./switch-model.sh strata   # C*3 on 127.0.0.1:8080 — chat page http://127.0.0.1:8080, API http://127.0.0.1:8080/v1
./switch-model.sh signal   # signal-next on 8080 instead (unchanged)
./switch-model.sh status   # what runs on 8080
STRATA_CONFIG=configs/Cstar2.json ./switch-model.sh strata   # rollback: round 2's C*2 (v0.1.11, old one-chat page)
```
* **Chat page:** the new speech-bubble button next to "New chat" opens the **Chats** list (switch, delete with Undo).
  "New chat" now keeps the old chat. Chats live in your browser; your existing chat is moved into the list on first
  load. Switching is blocked while an answer is being written (press Stop first).
* **What stays fast:** the server keeps the last 6 other chats (up to 16 GB of RAM; least recently used dropped
  first), so going back to any of them starts in about a second. Chats under ~500 tokens are simply read again (~1 s).
  A server restart (or `switch-model.sh`) empties this cache; the first message in an old chat then reads it once.
* Sampling: nothing to set — the page's defaults are your settings (see item 1); check the drawer once.
