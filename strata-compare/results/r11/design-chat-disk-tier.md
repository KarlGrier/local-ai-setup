# Design note: a disk tier for dropped chats (Round 11 — design only, nothing built)

## What it would fix
`--chat-cache 16 --chat-cache-mib 12288` keeps up to 16 other conversations in RAM. When a new one does not fit, the
least recently used is **dropped**, and the next request that continues it re-reads its whole prompt.

Sizes from our own engine logs (C\*12.1, int8 KV, IQ3_S):

| conversation | parked size | park time |
|---|---|---|
| 1,020 tokens, 1 checkpoint | 127 MiB | 3 ms |
| 9,650 tokens, 1 checkpoint | 253 MiB | 20 ms |
| 32,764 tokens, 2 checkpoints | 702 MiB | 22 ms (restore 22 ms) |

That is about **110 MiB per checkpoint + ~14.6 KiB per token**. A 100K-token research chat would be ~1.7 GiB.
Re-reading such a chat costs ~25–30 s of prompt time on this machine. Reading 1.7 GiB from the NVMe takes about
0.3–0.6 s. So for long chats that come back after being pushed out of RAM, a disk tier would turn a ~30 s wait into
under 1 s.

## Design
1. **When to write.** Only when the RAM tier *drops* a conversation (LRU), never on park. The parked buffers move
   to a background writer thread, which writes them out and then frees them. Nothing is written on a request's
   critical path.
2. **Where.** One file per conversation under a workspace cache directory (e.g. `tmp/chat-tier/`), mode 0600,
   written to `.part` and renamed when complete. A size cap (`--chat-disk-mib`, e.g. 65,536) with LRU eviction of
   files.
3. **What.** Exactly the RAM tier's `Parked` record: the checkpoints (running state), the host-copy K/V blocks of
   every QSA layer and of the drafter's ring up to the longest checkpoint, and the indexer's pooled / dead /
   block-position rows. Header: engine binary SHA-256, pack hash, geometry, KV mode, the token count, and a hash of
   the token ids up to each checkpoint.
4. **Finding it.** The server already keeps each parked conversation's ids. Its index would also list the disk
   entries (ids hash per checkpoint boundary). When a prompt matches neither the live conversation nor a RAM entry
   but does match a disk entry, the server sends a new engine command (`UNPARK-DISK <file>`). The engine reads the
   file into pinned buffers and unparks it exactly like a RAM entry. The request then reads only what follows.
5. **Refusing stale entries.** An entry is used only if its header's engine SHA-256 and pack hash match the running
   ones. Another build may compute states that differ at rounding level, and a cached continuation must equal what
   this build would compute from scratch. On any mismatch the file is deleted and the prompt is re-read.

## Exactness class
(a) exact: the restore copies back the same bytes that were parked, as the RAM tier does. The existing round-trip
tests (direct / park / edit-reference with `STRATA_STATE_HASH=1`) extend directly: park → drop to disk → restore →
state hash equal to direct.

## Costs and risks
- Disk: ~14.6 KiB/token plus 110 MiB per checkpoint; capped. Writes are a few hundred MiB per drop, which is
  negligible NVMe wear at our request rate.
- RAM: the writer holds a dropped record until it is written (≤ one record at a time, or the drop waits).
- **Privacy.** The files are model state derived from your conversations. They are not readable text, but they
  are still a persistent record of your chats on disk. So this should be **off by default**, live only under the
  workspace, and offer a "delete on server stop" option. Your call before anything like it is built.
- Failure cases to test: disk full (skip the write and log it), a corrupt or truncated file (hash mismatch → delete,
  re-read), Stop during a disk restore (finish or abandon the restore cleanly, then the next request re-reads),
  two requests racing for the same entry.

## How it would be measured
Served LDR-shaped sessions with more than 16 conversations, or more than 12 GiB of them: TTFT of a returning
conversation (RAM hit / disk hit / re-read) at 10K / 32K / 100K tokens, decode right after the restore, and the
round-trip state hashes.
