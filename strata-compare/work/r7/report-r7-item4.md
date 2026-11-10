### 4. Item 4 — can two conversations run faster together than one after another? (feasibility, ~3 h; no engine change)

Everything ran on the promoted C\*7 (engine untouched: only flags, clients, and for nsys the trace twin of the same
source with the oracle off). Only accepted output tokens are counted; sampling and settings are the same in every
compared pair. **Evidence** (measured) and **estimates** (arithmetic on the evidence) are kept apart.

#### a) Where a decode window's time goes (evidence: nsys, 120 windows, math, greedy)

| | your served flags (adaptive tier, lookup drafts) | exact flags (static tier, `--adapt-swaps 0`) |
|---|---|---|
| window (wall) | **18.7 ms** (T1 13.4 … T4 22.3) | 31.1 ms (T1 19.0 … T4 40.3) |
| GPU working | **14.6 ms (78 %)** | 16.1 ms (52 %) |
| GPU waiting for the CPU (flag wait) | **2.7 ms (15 %)** | 16.8 ms (54 %) |
| gaps (host-only time: commit, drafting) | 0.2 ms | 0.2 ms |
| CPU expert pool per layer / per window | **133 µs / 6.4 ms**; the GPU works through 69 % of it | 404 µs / 19.4 ms; 36 % |

**Estimate — the ideal ceiling for interleaving two independent conversations** (one's GPU work during the other's CPU
phase, nothing else changes): the pair of windows cannot take less than the larger of the two resources' total work.
* Served flags: the GPU is the bottleneck, 2 × 14.6 = 29.2 ms vs 2 × 18.7 = 37.4 ms back to back → **at most +28 % total
  throughput** (1-token windows +22 %, 4-token +31 %). Each conversation would run ~36 % slower than alone.
* Static tier: CPU-bound, 2 × 19.4 = 38.8 vs 62.2 ms → +60 %. That is not the served configuration.

The second conversation's VRAM (its 32K resident K/V cells, recurrent state, window buffers: ~0.5 GiB) would come
out of the 5080's expert cache (~5 % of its experts), which lowers that ceiling a little.

#### b) `--spec-split` at the largest groups it supports (evidence)

8-token windows (4 + 4) and 6-token windows (3 + 3), every window full (`--spec-min-p 0`), math and code, ms per round:

| | static tier (exact, 2 identical repeats) math / code | **adaptive tier (served), 1 run** math / code |
|---|---|---|
| 8 tokens, unsplit | 59.7 / 54.4 | 41.6 / 39.2 |
| **8 tokens, split 4 + 4** | **53.1 (−11 %) / 46.1 (−15 %)** | **39.3 (−5.5 %) / 37.9 (−3.3 %)** |
| two 4-token windows back to back | 74.3 / 62.1 | 48.4 / 46.9 |
| 6 unsplit / split 3 + 3 / two 3-token windows | 48.5 / 42.0 / 62.9 · 42.1 / 34.9 / 54.4 | – |

Unlike rounds 3–4 (split −8.5 %), the split now wins at 8 tokens. v5 shrank the GPU's share, and the split hides the
GPU's wait for the CPU (static: 14.7 → 0.3 ms per round) even though its two groups duplicate experts (23.5 → 31.8
distinct CPU experts per layer). One window of 8 is also much cheaper than two windows of 4 (−14 to −16 %), because
the dense weights are read once.

#### c) One window with tokens of two unrelated conversations (evidence: the fixed `--dump-routing` traces)

Distinct CPU-side experts per layer (the math and code greedy runs, 1,024 accepted tokens each, static placement):

| window | same conversation (mean of the two) | **merged: half from each** | the two halves as separate windows |
|---|---|---|---|
| 4 tokens | 14.5 | **17.0 (+18 %)** | 18.4 (merged −7 %) |
| 8 tokens | 22.3 | **26.1 (+17 %)** | 29.0 (merged −10 %) |

Batching two conversations into one window costs ~17–18 % more CPU expert traffic than a same-conversation window of
the same size, but still saves 7–10 % against processing them in two windows.

#### d) Per-conversation state and one-conversation assumptions (evidence: the code)

See the table below the item (per-conversation state; every server and engine place that assumes one live
conversation; what the chat cache covers; the helper GPU). In short, the engine has one sequence (one SessionState,
one verify window with fixed mapped buffers, one drafter, one pool driver, one stop flag, and one error string —
tonight's Stop bug was exactly that). The chat cache time-multiplexes whole conversations between turns, but never
runs two at once. **The server already frees the engine between tool rounds.**

#### e) Two agents with web search, one after another vs overlapped through the queue (evidence)

`work/r7/agents2.py`: two agents, two turns each (Linux kernel releases; Node.js LTS and Python), web search through
the server's own tools, your settings, fixed seeds, 4,096 tokens max per turn, fresh server per run:

| run | total time | output tokens | total speed | per agent, end to end | first-token latency | tool time |
|---|---|---|---|---|---|---|
| one after another #1 | 80.0 s | 3,510 | 43.9 tok/s | 45.8 / 41.4 tok/s | 0.72–0.97 s | 33.6 s |
| **overlapped #1** | **55.8 s** | 3,561 | **63.9 tok/s (+46 %)** | 35.8 / 34.4 tok/s | 0.83–2.96 s | 31.1 s |
| one after another #2 | 83.5 s | 5,911 | 70.8 tok/s | 75.4 / 68.5 tok/s | 0.82–1.41 s | 14.6 s |
| overlapped #2 | 65.9 s | 4,885 | 74.1 tok/s (+5 %) | 34.0 / 53.3 tok/s | 1.00–3.12 s | 18.8 s |

Peak memory was the same either way (MemAvailable ≥ 34.9 GiB, engine RSS ≤ 51.9 GB, 5080 ≥ 462 MiB free). Every tool
round is its own engine request. In the overlapped runs the chat cache parked and restored the other agent's
conversation in 0–5 ms (≈ 100–230 tokens read again). The live web and sampling made the runs unequal. The gain
follows the tool time there was to hide: run #1 hid ~24 of its ~31 s of searching, and run #2 had little to hide (one
agent's searches returned in ~2 s). Per-agent speed and first-token latency get worse when overlapped: an agent waits
for the other's turn.

#### Recommendation: **useful only for overlapping tool waits**

* Overlapping agents' **tool waits already works today** (+5 % to +46 % total throughput here, no engine change). It
  costs each agent up to ~3 s of first-token latency and lowers its own speed. For agent workloads that is worth using
  (send agents through the same server concurrently); for your single-user chat it changes nothing.
* **Running two sequences in the engine is not worth prototyping for this PC and use:**
  * the measured ideal ceiling is +28 % total throughput on your configuration, with each conversation ~36 % slower;
  * batching into one window saves more GPU (one weight read) but carries 17–18 % more CPU expert traffic per token;
  * both need a second session (VRAM taken from the expert cache), per-sequence windows, drafters, stop and error
    state, and a server that runs two requests at once.
* **Biggest remaining unknown:** whether one host thread and one CPU pool can drive two conversations' windows without
  adding serial host time. Today the doorbell handling, plan, activation quantization and pool are single-threaded
  per window (~0.5 ms per window of serial host work), and the interleave needs the host to service both windows'
  layers in alternation. That, and not the GPU/CPU arithmetic above, decides how much of the +28 % would survive.

#### d) in full — per-conversation state and one-conversation assumptions
