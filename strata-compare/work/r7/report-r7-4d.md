#### d) Per-conversation state and every one-conversation assumption (code reading; evidence = the code, nothing measured)

Source: `strata-r7` (branch r7-port). Line numbers are in `src/program/generate.cpp` unless a file is named.
Evidence = read in the code; nothing here was measured.

**Per-conversation state (what a second live conversation would need its own copy of)**

| state | where | size / note | chat cache covers it? |
|---|---|---|---|
| QSA K/V, 12 layers (int8) | `SessionState::qsa_states` (session.hpp), with KV streaming: authoritative copy in pinned host RAM, `n_slots` pages in VRAM | ~1 KiB per cell and layer pair (int8) | **yes**: host copies below the longest checkpoint are copied out on park (`park`, ~3727) |
| QSA indexer (pooled rows, dead row, block position, key tail) | `QsaState::idx_pooled / idx_dead / idx_block_pos / idx_tail` | small | **yes**: pooled/dead/bpos on park; the tail inside each checkpoint (`ConvCheckpoint::tails`) |
| GDN recurrent state + conv history, 36 layers | `SessionState::gdn_state` | fixed size per sequence | **yes**: `ConvCheckpoint::gdn` |
| residual `R`, block scratch | `SessionState::block`, `R` | per window, transient | n/a (recomputed) |
| n-gram (PLE) history | `ss.ple_prev[2]`, `ss.ple_hist` (NG_HIST rows) | small | **yes**: `ConvCheckpoint::ple` |
| n-gram prefetch in flight (patch 0012) | `PleTable::Impl::pf_pending / pf_ticket` (ngram.cpp) | ONE pending read | no (it is only a cache warm; a stale one is collected by the next gather) |
| MTP drafter K/V (a ring over a host copy with KV streaming) | `MtpDrafter::st_` (mtp.cpp) | ring = window + 4·max_t + 64 cells | **yes**: its host copy is one of `stash_arrays` (~3625), rebuilt by `mtp.kv_restore` on resume |
| prompt-lookup (suffix) drafter | `SuffixDrafter sfx` (~3597) | ONE instance | rebuilt per request from the prompt ids (`sfx.reset()` + append, ~4353) → effectively per request |
| draft policy (MTP vs lookup windows) | `DraftPolicy policy` (~3598) | process-wide, learned from measured round times | shared on purpose (it is not content) |
| sampler / RNG | `Verifier::sampling_`; draws are Philox(seed, position) (verify.hpp) | stateless per position; the seed is per request (`req_seed` or the clock, ~4264) | n/a |
| penalty history | per request (`set_history`) | – | n/a |
| cancellation | engine: ONE `stop_req` atomic (~3471, "STOP" line ~3507); server: a `cancel` Event per request, `stop_now(cancel)` stops the engine only if that request is the one running | – | n/a |
| the live conversation | `live`, `live_ok`, `checks` (~3271) | the session's own checkpoints | this IS what parks |
| side stash | `SideStash stash` (~3606) | one | separate mechanism (off when the chat cache is on) |

Process-wide and fine to share between conversations: the expert caches (5080 tier, 4060 Ti helper), the adaptive
tier's usage counts, the PLE row cache, the weights, the CPU pool, the draft policy.

**Every place that assumes ONE live conversation**

*Server (`serve/server.py`)*
1. `Service.run` holds `self.fifo` (a `threading.Lock`, ~580) for the whole of ONE model turn (~837): one request in the
   engine at a time; the others wait (`status["queued"]`).
2. The engine protocol is one command at a time over stdin/stdout (`GEN … REUSED … tokens … DONE`); the server drains
   to THIS request's `DONE` while still holding the FIFO (~887).
3. `status` (busy / phase / generated) describes one request.
4. **Tool rounds release the FIFO:** `run_with_mcp` (~978) calls `svc.run` once per model turn and executes the web /
   MCP tool calls *between* turns, outside the FIFO. So while one conversation waits for a web search, another request
   can already use the engine; the chat cache parks the first conversation and brings it back for its next turn.

*Engine (`strata --serve`)*
5. The serve loop reads one line at a time (`while (next_line(line))`, ~3830) and runs a request to its end.
6. ONE `SessionState ss`: one set of QSA/GDN/PLE state = one sequence position space.
7. ONE `Verifier ver`: the window graphs (one per window size T) are captured with fixed-address mapped buffers
   (`h_tok_`, `h_x_`, `h_ids_`, the plan block, flags A/B/M, `h_ymiss_`); one window in flight.
8. ONE `MtpDrafter` with one K/V ring; ONE `SuffixDrafter`.
9. ONE `ExpertDispatch` / `Drive` (job map `job_of`, `jobs_multi`, `act_multi`, the GPU plan sink) and ONE `ExpertPool`
   (a batch at a time, driven by the host thread pinned to core 0).
10. The helper GPU (`RemoteExperts`): one `begin`/`finish` pair per layer, its own staging buffers.
11. The prompt path (`Prefill`): one prompt at a time; with `--prefill auto` it BORROWS expert-cache slots for its
    buffers and refills them after (a second sequence decoding meanwhile would see a smaller cache).
12. `stop_req`: one flag for "the running request"; and the serve loop's error string `err` (generate.cpp:1353), one for
    the whole process and never cleared — tonight's Stop bug (item 0, patch 0013) was exactly this: one request's
    "cancelled" read by the next. Two live conversations would need both per sequence.
13. The chat cache has one live conversation; `park`/`unpark` swap it whole (measured in the soaks: park 1–115 ms,
    restore 14–44 ms for 7K–66K-token conversations; a conversation under 512 tokens is not parked but re-read).

**What the chat cache already gives, and what it does not**

* **Gives:** time-multiplexing at request (turn) granularity — several conversations stay warm in RAM and the engine
  switches between them in tens of milliseconds instead of re-reading them. Combined with (4), two agents that spend
  time in tool calls already overlap: one's tool wait can be filled by the other's generation, at the cost of a
  park/restore per switch.
* **Does not give:** two sequences in flight at once. Interleaving (A's GPU phase during B's CPU phase) or batching
  (A and B in one verify window) needs a second SessionState (+ its VRAM: the QSA slots and the GDN state), a second
  set of window buffers/flags (or a window graph whose rows belong to two sequences with two position sets and two
  K/V pools), per-sequence drafters, a per-sequence stop, and a server that runs two requests at once.

**How the helper GPU would fit**

The 4060 Ti computes ~5 % of the routed entries (its 3,300 cached experts) inside each layer's CPU phase
(`RemoteExperts::begin` before the pool, `finish` after). With two sequences interleaved it would serve both
sequences' CPU phases, so its per-layer work doubles; today it finishes 4–9 µs after the pool, so it stays off the
critical path only while its work stays below the pool's. It holds only experts (no dense weights, no K/V), so it
cannot run a second sequence's GPU phase; in a merged (batched) window it would see the union of both sequences'
experts like the CPU does.
