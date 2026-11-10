### What changed upstream that matters (v0.1.40.2 → v0.1.41, 151 commits; full list results/r16/v041-defaults.md)

1. **The CPU prompt-read share is on by default — also on your two-card config** (its rule excludes only a layer split,
   batch slots and HIP; the helper cache is not a layer split). It reads short prompt chunks (below 1,024 tokens: short
   prompts, and every chat turn's new text after the cached conversation) 16–17 % faster here, but its `auto` mode picks the
   sharing layers by measured time, so those reads round differently run to run. **C\*16 turns it off** (step 1: it failed the
   acceptance suite's round-trip row); with it off v0.1.41 computes exactly what v0.1.40.2 did.
2. **Server fixes that reach your Open WebUI → 8080 path:** a frozen engine (no output, no CPU, no disk I/O for 90 s, GPU not
   busy) is ended and restarted by the next request (#1317 part 2; psutil is in the venv); a malformed request body gets a 400
   and an oversized one a 413 before it is read (a huge Content-Length used to be read until the client gave up); a tool call
   the model writes as `<function= NAME>` is parsed (it used to be kept as text inside the thinking, or reach the client under
   the name " NAME"); listen backlog 256.
3. **Pinned stage buffers (`STRATA_STAGE_PIN`) are opt-in** — upstream's own release gate found IQ3_S decode corrupted after a
   long prompt with them on. Off here (unset = off); they only act when experts are read from the files.
4. **File-tier work** (batched direct reads in the prompt path's stager, the mapping closed under direct reads, a RAM
   profile when the GGUF is cached, the watchdog's I/O allowance): only when experts come from the SSD — not on IQ3_S; in
   the Q4 check below only for the prompt path (its 66 GiB budget held every expert for decoding, but a 16K prompt chunk's
   borrowed cache slots read their experts from the SSD).
5. **Numerically silent here:** the q8_1 clamps (#606 / #1448) change only blocks whose scale overflows; the HC-norm
   scratch change is bitwise by upstream's note; the tokenizer piece cache gives the same ids; F4's per-architecture table
   keeps v0.1.40.2's rows on the 5080 and the 4060 Ti; the drafter's router guard matches this model (512 / 10).
6. **New opt-in switches, not used:** the Foresight swap space (`STRATA_FS_*`), chunked DeltaNet prompt recurrence
   (`STRATA_GDN_CHUNKED`, other bits), residency-biased routing (`STRATA_ROUTE_RESIDENT`: changes the output — not lossless),
   the no-P2P peer prompt path, debug hooks.
7. **Nothing restores the ~3 % Round 15 lost against C\*14** (step 2).
