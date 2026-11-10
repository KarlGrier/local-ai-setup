# Fetch guard (LDR patch 0006) — install notes

Staged 2026-11-03, **not installed**. Nothing under `.venv/`, `baseline/site/`, `patches/ldr/` or `tools/` was changed.
Why and the data behind the numbers: `REPORT.md`.

## What gets installed

| staged file | goes to | what |
|---|---|---|
| `0006-fetch-guard.patch` | `.venv/.../site-packages` (and `patches/ldr/`) | the guard: `extraction/fetch_guard.py` (new), `downloaders/html.py`, `downloaders/playwright_html.py`, `extraction/pipeline.py` |
| `apply.sh` | `patches/ldr/apply.sh` | knows 0006 (its three files + the new file) for `status` / `revert` / `apply` (diff: `apply.sh.patch`) |
| `tools/ldr-client.py` | `tools/ldr-client.py` | `summary.json` gets `"fetch_guard"` (diff: `tools/ldr-client.patch`) |

`site/` holds the four patched files as they will look after install (the patch is generated from them against
`src/whl`, LDR 1.10.7; the three changed files are pristine in the venv and in `baseline/site` today).

## How to install

1. No LDR running (no bench run, no runner job, no Jan research): `./run-ldr.sh stop` if needed.
2. `bash staging/fetchguard/install.sh` — or `bash staging/fetchguard/install.sh --baseline` to give the
   pristine-LDR baseline profile (`baseline/site`) the guard too, as was done with 0004 (my suggestion: yes — it
   only changes pages over 16 MiB / 400k tags, which hang the baseline the same way; say no if the baseline must stay
   byte-for-byte LDR 1.10.7 + 0004).
   The script refuses if port 5000 is in use or an `ldr-web` process exists, if `apply.sh status` is not `patched`,
   or if a target file is not pristine; it backs everything up to `tmp/backup-fetchguard-<time>/` and writes
   `UNDO.sh` there; it dry-runs the patch first; it ends with the offline tests (~10 s, one core, nice, 4 GiB cap).
3. Next `./run-ldr.sh start` picks it up. Check after the first run: `logs/fetch-guard.jsonl` has `page` records,
   the run's `summary.json` has `"fetch_guard": {"skipped": 0, ...}`.

Undo: `tmp/backup-fetchguard-<time>/UNDO.sh` (restores the files, removes 0006 and `fetch_guard.py`), or
`patches/ldr/apply.sh revert` + `apply` with the old `apply.sh`.

## Settings (environment, read when ldr-web starts; defaults need nothing)

| variable | default | meaning |
|---|---|---|
| `LDR_FETCH_GUARD` | `1` | `0` turns the skips off (watchdog + page records stay) |
| `LDR_FETCH_GUARD_MAX_MB` | `16` | decompressed HTML cap; the download stops past it (8 = worst passing page ~5 s instead of ~44 s) |
| `LDR_FETCH_GUARD_MAX_TAGS` | `400000` | `'<'` count cap checked before any parser runs |
| `LDR_FETCH_GUARD_SLOW_S` | `60` | watchdog: a page still extracting after this is logged and counted (not stopped) |
| `LDR_FETCH_GUARD_LOG` | `logs/fetch-guard.jsonl` | events + page records |
| `LDR_FETCH_GUARD_PAGES` | `1` | one record per parsed page (host, size, `'<'` count, seconds; no path) |

## What changes in behaviour

* Pages under both caps: the same text as before (tested byte-for-byte against pristine LDR on the G.Skill page and
  a 4 MiB slice of the Team Group page). The body is now read streamed; non-200 bodies are no longer read by
  `HTMLDownloader` (AutoHTMLDownloader's own SPA-check GET still reads them, unchanged).
* Over a cap: the fetch fails with `[FETCH-GUARD] skipped: <reason> (<size>, <tags>, <seconds>)`; the agent gets
  `Failed to fetch <url>: [FETCH-GUARD] skipped: ...` (the deep page cache keeps that, so a retry of the same URL
  does not download it again); no JS-rendering retry; a WARNING line `[FETCH-GUARD] skipped <url>: ...` in the
  ldr-web log and the research log; a `skipped` record in `logs/fetch-guard.jsonl`.
* `extract_content()` / `extract_content_with_metadata()` called directly (Wayback engine, full-content search;
  both off in our runs) return `None` over a cap (logged, counted).
* The DOC_SCHEDULER's library downloads do not go through `HTMLDownloader`: unaffected.
* Not covered: `deep/notyet.py` runs `trafilatura.extract` on its own `requests.get` (outside the fetch lock too);
  it is off since 10-28 (tried+notyet OFF). A total download deadline (slow-drip servers) is not added.
