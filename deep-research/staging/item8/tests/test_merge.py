#!/usr/bin/env python3
"""Offline tests for tools/merge-evidence.py (item 8). No model, no network, no report writer.

  nice -n 19 .venv/bin/python -I -B staging/item8/tests/test_merge.py [--keep] [--claims] [--only NAME,...]
                                                                     [--verify MERGED_DIR ...]

1. unit tests: URL normalisation and the reference renumbering on made-up text;
2. real merges of saved bench2 runs (o01 and o03, two and three runs, one with the options) into tests/out/<name>;
3. each merged folder checked against its runs, read with the INSTALLED package's seed.load (read only):
   a. no index collision: every (run, old idx) has one new idx, every new idx one URL, no URL two new idx, and the
      merged store's sources are exactly the mapped ones;
   b. every [N] in the merged texts (subagent texts and topics, notes, lead answers) is the original's citation with
      the new numbers, and each new number's source has the original source's URL; nothing else in the texts changed;
      a match that was not a citation of its run does not cite a merged source;
   c. per source: page text (the longest of the run copies), snippets, fetches (focus + extraction), date, via,
      primaries, claims (every original quote kept, none twice, none new), unreadable only where no run read it;
      subagents, notes and queries all kept;
   d. tools/fix-replay.py's own run_store() (what `write --run` does before the model) on the merged folder:
      seed.load + fill_store; with --claims also LDR_DEEP_FIX=all,read,claims (the claim stores rebuilt, ~CPU);
4. determinism: one merge made twice, byte-identical;
5. a counts summary -> tests/test-results.json and stdout.
--verify DIR checks existing merged folders (e.g. staging/item8/merged/o01-3) the same way (no merging).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

WS = Path("/home/USER/ai/deep-research")
STAGE = WS / "staging" / "item8"
TOOL = STAGE / "tools" / "merge-evidence.py"
OUT = STAGE / "tests" / "out"
RUNS = WS / "results" / "bench2" / "runs"
READPASS = WS / "results" / "bench2" / "fixes" / "readpass"
PY = WS / ".venv" / "bin" / "python"

COMBOS = {
    "o01-2": ([RUNS / "screen-deep-p4s6/o01", RUNS / "screen-deep-p4s7/o01"], []),
    "o01-3": ([RUNS / "screen-deep-p4s3/o01", RUNS / "screen-deep-p4s6/o01", RUNS / "screen-deep-p4s7/o01"], []),
    "o03-2": ([RUNS / "screen-deep-p4s6/o03", RUNS / "screen-deep-p4s7/o03"], []),
    "o03-3": ([RUNS / "screen-deep-p4s3/o03", RUNS / "screen-deep-p4s6/o03", RUNS / "screen-deep-p4s7/o03"], []),
    # the options: a read-pass evidence override, lead answers cut to share 10K tokens, indices and subagents in run order
    "o01-3opt": ([RUNS / "screen-deep-p4base/o01", RUNS / "screen-deep-p4s6/o01", RUNS / "screen-deep-p4s4/o01"],
                 ["--evidence", f"{RUNS / 'screen-deep-p4s6/o01'}={READPASS / 'o01'}", "--lead-share-tokens", "10000",
                  "--subagent-order", "runs", "--index-order", "runs"]),
}


def load_tool():
    spec = importlib.util.spec_from_file_location("merge_evidence", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = load_tool()
os.environ.pop("LDR_DEEP_FIX", None)
from local_deep_research.deep import seed as SEED                       # noqa: E402  (installed, read only)
from local_deep_research.deep.evidence import CITE_RE, cited_indices    # noqa: E402

NEUT_RE = re.compile(r"[\[【] (\d+(?:\s*[,–-]\s*\d+)*)[\]】]")
ANY_RE = re.compile(CITE_RE.pattern + "|" + NEUT_RE.pattern)


class Fail(AssertionError):
    pass


def check(cond, msg):
    if not cond:
        raise Fail(msg)


# -- 1. unit tests ------------------------------------------------------------------------------------------------------
def unit() -> int:
    k = T.url_key
    same = [("HTTPS://Example.COM/a/", "https://example.com/a"), ("https://example.com:443/a#sec", "https://example.com/a"),
            ("https://github.com/x/y/blob/v1/f.cpp#L10-L20", "https://github.com/x/y/blob/v1/f.cpp#L1-L2"),
            ("https://x.org/a/?q=1#f", "https://x.org/a?q=1"), ("https://example.com", "https://example.com/"),
            ("http://x.org:80/p", "http://x.org/p"), ("https://a.eu/doc.pdf#page=420", "https://a.eu/doc.pdf"),
            ("https://o.eu/articles/5-115/v2#referee-response-1", "https://o.eu/articles/5-115/v2#referee-response-2")]
    diff = [("file:///p/NOTES.md#part=1", "file:///p/NOTES.md#part=2"), ("https://x.org/#!home;tab=browse", "https://x.org/"),
            ("http://x.org/a", "https://x.org/a"), ("https://x.org/A", "https://x.org/a"),
            ("https://x.org/a?q=1", "https://x.org/a?q=2"), ("https://x.org/#/docs/a", "https://x.org/#/docs/b")]
    n = 0
    for a, b in same:
        check(k(a) == k(b), f"url_key: {a} vs {b} should be one source ({k(a)} / {k(b)})")
        n += 1
    for a, b in diff:
        check(k(a) != k(b), f"url_key: {a} vs {b} should stay two sources")
        n += 1
    mp = {1: 10, 2: 11, 3: 12, 5: 3, 7: 10}
    cases = [("a [1] b", "a [10] b"), ("[1, 2]", "[10, 11]"), ("[1,2]", "[10,11]"), ("[1-3]", "[10-12]"),
             ("[1–3]", "[10–12]"), ("[1, 7]", "[10]"), ("[1][7]", "[10][10]"), ("[5-7]", "[ 5-7]"),
             ("[0, 2]", "[ 0, 2]"), ("[61317]", "[61317]"), ("`x[1]` [1]", "`x[1]` [10]"),
             ("```\nfoo[2]\n``` [2]", "```\nfoo[2]\n``` [11]"), ("【1】", "【10】"),
             ("[[1]](http://u/1)", "[[10]](http://u/1)"), ("[2-1]", "[11, 10]"), ("[1-2-3]", "[1-2-3]"),
             ("[99]", "[99]"), ("text without refs", "text without refs")]
    for src, want in cases:
        from collections import Counter as C
        got = T.renumber_text(src, mp, 20, C())
        check(got == want, f"renumber {src!r}: got {got!r}, want {want!r}")
        n += 1
    got = T.renumber_text("[1-3]", {1: 5, 2: 9, 3: 6}, 20, Counter())
    check(got == "[5, 9, 6]" and cited_indices(got) == [5, 9, 6], f"non-consecutive range: {got}")
    got = T.renumber_text("[3-5]", {3: 7, 4: 8, 5: 7}, 20, Counter())
    check(cited_indices(got) == [7, 8], f"range with a repeat: {got}")
    return n + 2


# -- 3. checking a merged folder -----------------------------------------------------------------------------------------
def matches(text: str):
    spans = T.code_spans(text)
    out = []
    for m in ANY_RE.finditer(text):
        incode = any(a <= m.start() < b for a, b in spans)
        out.append((m, incode))
    return out


def skeleton(text: str) -> str:
    return ANY_RE.sub("§", text)


def compare_text(o: str, m: str, run_ids: set[int], mp: dict[int, int], okey: dict[int, str], mkey: dict[int, str],
                 n_merged: int, st: Counter, where: str, prefix: bool = False) -> None:
    if prefix:            # a lead answer cut by --lead-share-tokens: the kept part, without its note and last line
        m = m.split("\n\n[... the rest of this run's lead answer is cut")[0]
        m = m[: m.rfind("\n")] if "\n" in m else ""
        so, sm = skeleton(o), skeleton(m)
        check(so.startswith(sm), f"{where}: the cut lead answer is not a prefix of the original")
    else:
        check(skeleton(o) == skeleton(m), f"{where}: text outside the citations changed")
    mo, mm = matches(o), matches(m)
    if prefix:
        mo = mo[: len(mm)]
    check(len(mo) == len(mm), f"{where}: {len(mo)} references before, {len(mm)} after")
    for (a, a_code), (b, b_code) in zip(mo, mm):
        if a_code:
            check(a.group(0) == b.group(0), f"{where}: code reference changed {a.group(0)} -> {b.group(0)}")
            st["refs_in_code"] += 1
            continue
        if NEUT_RE.fullmatch(a.group(0)):       # "[ N]" in the original: not a citation either way
            check(a.group(0) == b.group(0), f"{where}: {a.group(0)} changed")
            continue
        olds = cited_indices(a.group(0))
        parts = T.parse_parts(CITE_RE.fullmatch(a.group(0)).group(1))
        valid = olds and all(p[0] != "other" for p in parts) and all(n in run_ids for n in olds)
        news = cited_indices(b.group(0)) if CITE_RE.fullmatch(b.group(0)) else []
        if valid:
            want = list(dict.fromkeys(mp[n] for n in olds))
            check(news == want, f"{where}: {a.group(0)} -> {b.group(0)}, want {want}")
            for n in olds:
                check(okey[n] == mkey.get(mp[n]), f"{where}: [{n}] -> [{mp[n]}] changes the source: "
                                                  f"{okey[n]} vs {mkey.get(mp[n])}")
            st["citations_checked"] += 1
            st["citation_numbers_checked"] += len(olds)
        else:
            check(not [x for x in news if 1 <= x <= n_merged], f"{where}: non-citation {a.group(0)} -> {b.group(0)} "
                                                                f"cites a merged source")
            st["non_citations_checked"] += 1


def records(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def verify(out: Path, claims_rebuild: bool = False) -> dict:
    t0 = time.time()
    marks = json.loads((out / "marks.json").read_text(encoding="utf-8"))
    runs = marks["merged_from"]
    summary = json.loads((out / "merge-summary.json").read_text(encoding="utf-8"))
    share = summary["lead_answer"]["share_tokens"]
    st: Counter = Counter()

    # the map
    mp: dict[str, dict[int, int]] = defaultdict(dict)
    tsv_url: dict[tuple[str, int], str] = {}
    with open(out / "merge-map.tsv", encoding="utf-8") as f:
        next(f)
        for line in f:
            lab, old, new, url = line.rstrip("\n").split("\t", 3)
            check(int(old) not in mp[lab], f"map: {lab} {old} twice")
            mp[lab][int(old)] = int(new)
            tsv_url[(lab, int(old))] = url
    # the originals and the merge, read by the installed seed.load
    oseed = {r["label"]: SEED.load([str(Path(r["evidence"]).parent)]) for r in runs}
    mseed = SEED.load([str(out / "deep")])
    n_merged = len(mseed.sources)

    def key_of(lab, old, s):
        u = s["url"] or tsv_url.get((lab, old), "")
        return T.url_key(u) or f"(no url) {lab}#{old}"

    okeys: dict[str, dict[int, str]] = {}
    new_keys: dict[int, set[str]] = defaultdict(set)
    group: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for r in runs:
        lab = r["label"]
        okeys[lab] = {i: key_of(lab, i, s) for i, s in oseed[lab].sources.items()}
        check(set(oseed[lab].sources) <= set(mp[lab]), f"{lab}: {len(set(oseed[lab].sources) - set(mp[lab]))} "
                                                        f"source indices missing from the map")
        for i, k in okeys[lab].items():
            new_keys[mp[lab][i]].add(k)
            group[mp[lab][i]].append((lab, i))
    # a. no collision
    multi = {n: ks for n, ks in new_keys.items() if len(ks) > 1}
    check(not multi, f"collision: {len(multi)} new indices with several URLs, e.g. {next(iter(multi.items()), None)}")
    k2n: dict[str, int] = {}
    for n, ks in new_keys.items():
        k = next(iter(ks))
        check(k not in k2n, f"collision: URL {k} has new indices {k2n.get(k)} and {n}")
        k2n[k] = n
    mapped = {n for lab in mp for n in mp[lab].values()}
    check(set(mseed.sources) == mapped, f"merged store {len(mseed.sources)} sources vs {len(mapped)} mapped")
    mkey = {n: (T.url_key(s["url"]) or next(iter(new_keys.get(n, {""})))) for n, s in mseed.sources.items()}
    bad = [n for n in new_keys if mkey[n] != next(iter(new_keys[n]))]
    check(not bad, f"{len(bad)} merged sources whose URL is not the originals', e.g. {bad[:3]}")
    st["sources_checked"] = sum(len(v) for v in okeys.values())

    # b. the texts
    msubs: dict[str, list[dict]] = defaultdict(list)
    mnotes: dict[str, list[dict]] = defaultdict(list)
    mclaims: dict[int, list[str]] = defaultdict(list)
    munread: set[int] = set()
    for rec in records(out / "deep" / "evidence.jsonl"):
        t = rec.get("type")
        if t == "subagent":
            msubs[rec["run"]].append(rec)
        elif t == "note" and rec.get("run"):
            mnotes[rec["run"]].append(rec)
        elif t == "claims":
            mclaims[rec["idx"]] += [T.qnorm(c.get("quote", "")) for c in rec.get("claims") or []]
        elif t == "unreadable":
            munread.add(rec["idx"])
    lead_md = (out / "deep" / "lead_answer.md").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"(?ms)^===== Lead answer of run \d+ of \d+ \((.+?)\) =====\n\n(.*?)(?=^===== Lead "
                             r"answer of run |\Z)", lead_md))
    ocl: dict[str, dict[int, list[str]]] = {}
    ounread: dict[str, set[int]] = {}
    for r in runs:
        lab = r["label"]
        ids = set(mp[lab])
        osubs, onotes = [], []
        ocl[lab], ounread[lab] = defaultdict(list), set()
        for rec in records(Path(r["evidence"])):
            t = rec.get("type")
            if t == "subagent":
                osubs.append(rec)
            elif t == "note":
                onotes.append(rec)
            elif t == "claims" and rec.get("idx") is not None:
                ocl[lab][int(rec["idx"])] += [T.qnorm(c.get("quote", "")) for c in rec.get("claims") or []]
            elif t == "unreadable" and rec.get("idx") is not None:
                ounread[lab].add(int(rec["idx"]))
        check(len(osubs) == len(msubs[lab]), f"{lab}: {len(osubs)} subagents, merged {len(msubs[lab])}")
        check(len(onotes) == len(mnotes[lab]), f"{lab}: {len(onotes)} notes, merged {len(mnotes[lab])}")
        args = (ids, mp[lab], okeys[lab], mkey, n_merged, st)
        for k, (a, b) in enumerate(zip(osubs, msubs[lab])):
            for fld in ("text", "topic"):
                compare_text(a.get(fld) or "", b.get(fld) or "", *args, where=f"{lab} subagent {k} {fld}")
            st["texts_checked"] += 2
        for k, (a, b) in enumerate(zip(onotes, mnotes[lab])):
            check(a.get("kind") == b.get("kind"), f"{lab} note {k}: kind changed")
            for fld in ("text", "notes_text"):
                if isinstance(a.get(fld), str):
                    compare_text(a[fld], b.get(fld) or "", *args, where=f"{lab} note {k} {fld}")
                    st["texts_checked"] += 1
        lead = (Path(r["run"]) / "deep" / "lead_answer.md").read_text(encoding="utf-8").strip()
        check(lab in blocks, f"{lab}: no lead-answer block")
        compare_text(lead, blocks[lab].strip(), *args, where=f"{lab} lead answer", prefix=share > 0)
        st["texts_checked"] += 1
    # every reference outside code in the merged texts is a merged source or no source at all (never a wrong one:
    # checked per match above); count the ones that cite nothing
    for lab in msubs:
        for rec in msubs[lab]:
            st["dangling_after"] += len([n for n in cited_indices(rec.get("text") or "") if n not in mseed.sources])

    # c. per source
    for r in runs:
        lab = r["label"]
        for i, so in oseed[lab].sources.items():
            n = mp[lab][i]
            sm = mseed.sources[n]
            longest = max(len(oseed[l2].sources[i2]["page_text"]) for l2, i2 in group[n])
            check(len(sm["page_text"]) == longest, f"{lab} [{i}] -> [{n}]: page text {len(sm['page_text'])} chars, "
                                                   f"the longest copy {longest}")
            check(set(so["snippets"]) <= set(sm["snippets"]), f"{lab} [{i}] -> [{n}]: snippets lost")
            fo = Counter((f["focus"], f["extraction"]) for f in so["fetches"])
            fm = Counter((f["focus"], f["extraction"]) for f in sm["fetches"])
            check(not (fo - fm), f"{lab} [{i}] -> [{n}]: fetches lost")
            check(not so["date"] or sm["date"], f"{lab} [{i}] -> [{n}]: date lost")
            check(not so["title"] or sm["title"], f"{lab} [{i}] -> [{n}]: title lost")
            if so["via"] is not None:
                vias = {mp[l2][oseed[l2].sources[i2]["via"]] for l2, i2 in group[n]
                        if oseed[l2].sources[i2]["via"] is not None}
                check(sm["via"] in vias, f"{lab} [{i}] -> [{n}]: via {sm['via']} not one of {vias}")
            prim = {mp[lab][p] for p in so["primaries"]} - {n}
            check(prim <= set(sm["primaries"]), f"{lab} [{i}] -> [{n}]: primaries lost")
            st["page_texts_checked"] += bool(so["page_text"])
            st["fetches_checked"] += len(so["fetches"])
        for i, qs in ocl[lab].items():
            n = mp[lab][i]
            check(set(qs) <= set(mclaims[n]), f"{lab} [{i}] -> [{n}]: {len(set(qs) - set(mclaims[n]))} claims lost")
            st["claims_checked"] += len(qs)
        for i in ounread[lab]:
            n = mp[lab][i]
            if not mseed.sources[n]["page_text"]:
                check(n in munread, f"{lab} [{i}] -> [{n}]: unreadable lost")
    for n, qs in mclaims.items():
        check(len(qs) == len(set(qs)), f"[{n}]: a claim twice")
        allq = {q for l2, i2 in group[n] for q in ocl[l2].get(i2, [])}
        check(set(qs) <= allq, f"[{n}]: a claim no run had")
    check(not [n for n in munread if mseed.sources[n]["page_text"]], "unreadable kept for a page some run read")
    check(len(mseed.subagents) == sum(len(s.subagents) for s in oseed.values()), "subagents lost")
    check(len(mseed.notes) == sum(len(s.notes) for s in oseed.values()), "notes lost")
    check(set(mseed.queries) == {q for s in oseed.values() for q in s.queries}, "queries differ")

    # d. fix-replay.py's run_store (installed tool, imported read only) + fill_store
    spec = importlib.util.spec_from_file_location("fix_replay", WS / "tools" / "fix-replay.py")
    fr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fr)
    q, store, lead = fr.run_store(out)
    check(q == marks["question"] and q, "run_store: question")
    check(lead == lead_md, "run_store: lead answer")
    check(len(store.sources) == n_merged, f"run_store: {len(store.sources)} sources, want {n_merged}")
    check(len(store.subagents) == len(mseed.subagents), "run_store: subagents")
    check(sum(1 for s in store.sources.values() if s.page_text) == sum(1 for s in mseed.sources.values()
                                                                        if s["page_text"]), "run_store: page texts")
    stats = store.stats()
    res = {"merged": out.name, "runs": [r["label"] for r in runs], "sources_per_run": [len(oseed[r["label"]].sources)
                                                                                         for r in runs],
           "merged_sources": n_merged, "store_stats": {k: v for k, v in stats.items() if k != "elapsed_s"},
           "pages_with_text": sum(1 for s in store.sources.values() if s.page_text),
           "claims_records_kept": sum(len(v) for v in mclaims.values()), "unreadable_kept": len(munread),
           "lead_tokens": summary["lead_answer"]["tokens"], "lead_share_tokens": share,
           "tool_counts": summary["counts"], "checks": dict(sorted(st.items()))}
    if claims_rebuild:
        os.environ["LDR_DEEP_FIX"] = "all,read,claims"
        try:
            t1 = time.time()
            sd = SEED.load([str(out / "deep")])
            from local_deep_research.deep.evidence import EvidenceStore
            from local_deep_research.deep import claims as CL
            st2 = EvidenceStore(q, None)
            SEED.fill_store(sd, st2)
            res["claims_rebuilt"] = {**CL.stats(st2.all_sources()), "seconds": round(time.time() - t1, 1)}
        finally:
            os.environ.pop("LDR_DEEP_FIX", None)
    res["verify_s"] = round(time.time() - t0, 1)
    return res


def merge(name: str, dest: Path) -> tuple[Path, float]:
    runs, opts = COMBOS[name]
    if dest.exists():
        shutil.rmtree(dest)
    t0 = time.time()
    p = subprocess.run(["nice", "-n", "19", str(PY), "-I", "-B", str(TOOL), "--out", str(dest), *map(str, runs), *opts],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise Fail(f"merge {name}: rc {p.returncode}\n{p.stdout}\n{p.stderr}")
    print("   ", p.stdout.strip().replace("\n", "\n    "))
    return dest, time.time() - t0


def digest(d: Path) -> dict[str, str]:
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*"))
            if p.is_file()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep tests/out")
    ap.add_argument("--claims", action="store_true", help="also rebuild the claim stores (LDR_DEEP_FIX claims)")
    ap.add_argument("--only")
    ap.add_argument("--verify", nargs="*", default=None, help="check these merged folders instead of merging")
    a = ap.parse_args()
    results: dict = {"unit_tests": unit()}
    print(f"unit tests: {results['unit_tests']} passed")
    failed = 0
    if a.verify is not None:
        for d in a.verify:
            try:
                r = verify(Path(d).resolve(), a.claims)
                results[Path(d).name] = r
                print(f"OK {d}: {r['merged_sources']} sources; {r['checks']}")
            except Fail as e:
                failed += 1
                print(f"FAIL {d}: {e}")
        (STAGE / "tests" / "verify-results.json").write_text(json.dumps(results, indent=1) + "\n")
        return 1 if failed else 0
    names = a.only.split(",") if a.only else list(COMBOS)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        print(f"{name}:")
        try:
            d, secs = merge(name, OUT / name)
            r = verify(d, a.claims and name == names[0])
            r["merge_s"] = round(secs, 1)
            results[name] = r
            print(f"OK {name}: {r['merged_sources']} sources from {r['sources_per_run']}; checks {r['checks']}")
        except Fail as e:
            failed += 1
            results[name] = {"failed": str(e)}
            print(f"FAIL {name}: {e}")
    # 4. determinism
    name = names[0]
    try:
        d2, _ = merge(name, OUT / f"{name}-again")
        d1 = OUT / name
        h1, h2 = digest(d1), digest(d2)
        same = h1 == h2
        results["determinism"] = {"merge": name, "files": len(h1), "identical": same}
        print(f"determinism ({name} twice): {'identical' if same else 'DIFFERENT'} ({len(h1)} files)")
        failed += not same
    except Fail as e:
        failed += 1
        print(f"FAIL determinism: {e}")
    results["failed"] = failed
    (STAGE / "tests" / "test-results.json").write_text(json.dumps(results, indent=1) + "\n")
    if not a.keep:
        shutil.rmtree(OUT, ignore_errors=True)
    print("ALL PASSED" if not failed else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
