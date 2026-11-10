#!/usr/bin/env python3
"""shape_rules.py - the helper of the v0.2.13 SHAPE GAP (Karl 11-09 ~14:15: "the shape gap GO, as planned"; plan in
results/r23/port-0213/NOTES-0213.md, "The shape gap"). Information only: nothing switches, P028x stays served.

Used by work/r23/shape-gap/shape_prep.sh (the desk prep, under nogap-run), gap-shape0213.sh (the gap) and
cleanup-shape0213.sh (after it). Run as `.venv/bin/python -I -B shape_rules.py CMD ...`. Reads the port tree
(strata-r23p0213) read-only: q4geo_synth.py's own plan functions (sizes), strata_control/setup_config.py's neutral expert
profile writer, `ctest --show-only=json-v1` (a listing; nothing runs). It never starts an engine, a server or a GPU program.

  plan       the synthetic files' sizes from q4geo_synth.py's own layout + recipe + alignment (no file is written)
  disk       free space check: refuses (exit 1) when free - NEED would drop under the floor (150 GB)
  profile    a neutral expert profile for a synthetic file (setup's neutral_profile_if_other_shape, unchanged)
  cfg        the smoke config of one shape, derived from configs/P0213x.json (exe, model, pack, profile, no drafter, no
             picture reader, no fallback, STRATA_MANIFEST); checked
  ctestlist  the registered ctest entries whose program is one of GEO_TESTS (build-port0213.sh's list) in a build
  parity     a build's ctest results (junit + log) and the direct runs -> PASS / SKIP (77) / FAIL per test, counts
  envcheck   the running engine (by its exe) has the config's env exactly
  chat       one chat request (T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05, presence 0): completion tokens and a normal finish
  guards     the patch guard lines of a CLI probe, against what the shape should give
  manifest   STRATA_MANIFEST's gdn_tc / gdn_convl2 and its prefill paths
  record     prep/READY.json: what the prep made (files, sizes, sha256, heads)
  verify     the gap's preflight: READY.json against the disk now (exit 1 + why on any difference)
  verdict    decision.txt rows (per shape: builds, parity N pass / M skip / K fail, loads and answers yes/no)
  sizes      cleanup: the engine copies' and build directories' sizes and the keep/delete rule
  selftest   the parsers and the config derivation on fixtures (writes only under the given folder)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
TREE = WS / "strata-r23p0213"
BRANCH = "r23-port0213"
SG = WS / "work/r23/shape-gap"
MODELS = WS / "models/q4geo"
ISTA1 = WS / "models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"
BASE_CFG = WS / "configs/P0213x.json"
SHIPPED_PROFILE = WS / "strata-cstar18/data/expert-profile.bin"
SHAPES = ("q4_mid", "q4_big", "q4_deep")
LAYERS = 4
# see shape_prep.sh: IQ3_S gate/up (IQ4_XS in layer 0) + IQ4_NL down, two of the served file's pairs; SG_RECIPE=ud-q4k = upstream's mix
RECIPE = os.environ.get("SG_RECIPE", "fused-iq")
if RECIPE not in ("fused-iq", "ud-q4k"):
    raise SystemExit(f"SG_RECIPE={RECIPE}: fused-iq or ud-q4k only")
FLOOR_GB = 150
# build-port0213.sh's GEO_TESTS (the shape-following parity programs)
GEO_TESTS = ("gguf_geometry_test patch_guard_test prefill_fused_iq_test prefill_fused_moe_test native_dense_parity "
             "native_expert_parity native_grouped_parity gdn_parity gr_parity gr_multi_parity qsa_parity "
             "qsa_prompt_attn_parity router_top10_parity shared_expert_parity verify_parity spec_verify_parity").split()
UNREGISTERED = ("patch_guard_test", "qsa_prompt_attn_parity")   # built, no ctest entry: run directly by the gap
GUARDS = ("spec_exact", "side_mixer", "router_q8k", "qsa_split_attn", "gr_fork", "draft_cum", "prefill_v2")
FORK_TEXT = "the fork read is built for Flash-Next's 2560 / 4 / 320 only"


def say(*a):
    print(*a, flush=True)


def sha256(path: Path, full: bool = True) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(TREE), *a], capture_output=True, text=True, check=True).stdout.strip()


# ================================================================================================ the synthetic files
def synth_module():
    """q4geo_synth.py of the port tree, imported read-only (python -B: no bytecode is written there)."""
    sys.path.insert(0, str(TREE / "tools"))
    import q4geo_synth as m      # noqa: E402
    return m


def small_ple_primes() -> list[int]:
    """--small-ple's 16 head sizes, as q4geo_synth.main() computes them."""
    primes, n = [], 100003
    while len(primes) < 16:
        if all(n % d for d in range(2, int(n ** 0.5) + 1)):
            primes.append(n)
        n += 2
    return primes


def plan_shape(m, shape: str, layers: int, recipe: str, vocab: int, small_ple: bool, overrides: dict | None = None) -> dict:
    """The byte count write_gguf() will produce for this shape: the same header (metadata + tensor infos, padded) and the
    same data layout (each tensor padded to DEFAULT_ALIGNMENT). The PLE table is written as a hole (seek + 1 byte), so
    its bytes are apparent, not allocated."""
    if small_ple:
        p = small_ple_primes()
        m.PLE_VOCAB[:] = p
        m.PLE_ROWS = sum(p)
    s = m.shape(shape, layers, **(overrides or {}))
    label = f"{shape}_{layers}l"
    w = m.metadata(s, vocab, f"synthetic {label} ({recipe})")
    plan = []
    for n, sh, role in m.all_tensors(s, vocab):
        layer = int(n.split(".")[1]) if n.startswith("blk.") else -1
        ty = m.recipe_type(recipe, role, layer, s)
        if not m.row_ok(ty, sh[0]):
            raise SystemExit(f"{shape}: {n} {sh}: row length not a multiple of {m.QTYPES[ty][1]} ({ty}) - the tool would refuse")
        plan.append((n, sh, role, ty))
    plan.sort(key=lambda x: 0 if "_exps.weight" in x[0] else 1)
    A = m.DEFAULT_ALIGNMENT
    body = 4 + 4 + 8 + 8
    for k, (t, v) in w.metadata.items():
        body += len(w._kv_bytes(k, t, v))
    for n, sh, role, ty in plan:
        body += 8 + len(n.encode()) + 4 + 8 * len(sh) + 4 + 8
    body += (-body) % A
    data = hole = experts = 0
    types: dict[str, int] = {}
    pairs = set()
    for n, sh, role, ty in plan:
        nb = m.tensor_bytes(ty, sh)
        data += nb + ((-nb) % A)
        types[ty] = types.get(ty, 0) + 1
        if role == "ple_table":
            hole += nb
        if "_exps.weight" in n:
            experts += nb
    for l in range(s["n_layers"]):
        gu = m.recipe_type(recipe, "gate", l, s)
        d = m.recipe_type(recipe, "down", l, s)
        pairs.add(f"{gu}/{d}")
    total = body + data
    return {"shape": shape, "layers": s["n_layers"], "label": label, "recipe": recipe, "vocab": vocab, "small_ple": small_ple,
            "tensors": len(plan), "bytes": total, "header_bytes": body, "ple_hole_bytes": hole, "allocated_bytes": total - hole,
            "expert_bytes": experts, "types": types, "expert_pairs": sorted(pairs),
            "n_embd": s["n_embd"], "hc": s["hc"], "hc_lr": s["hc_lr"], "n_ff": s["n_ff"], "n_expert": s["n_expert"],
            "n_head": s["n_head"], "n_head_kv": s["n_head_kv"]}


def vocab_from(tok: str | None, default: int) -> tuple[int, object]:
    if not tok:
        return default, None
    sys.path.insert(0, str(TREE / "tools"))
    from gguf_reader import GGUFFile   # noqa: E402
    g = GGUFFile(Path(tok))
    return len(g.metadata["tokenizer.ggml.tokens"]), g


def cmd_plan(a):
    m = synth_module()
    vocab, tok = vocab_from(a.tokenizer_from, a.vocab)
    m.TOKENIZER_FROM = tok          # the tokenizer.* keys of the real file go into the header (its size)
    rows = [plan_shape(m, s, a.layers, a.recipe, vocab, a.small_ple) for s in a.shapes.split(",")]
    for r in rows:
        say(f"plan {r['label']}: {r['tensors']} tensors, {r['bytes'] / 1e9:.2f} GB ({r['bytes']} bytes; PLE hole "
            f"{r['ple_hole_bytes'] / 1e9:.2f} GB, allocated ~{r['allocated_bytes'] / 1e9:.2f} GB, experts {r['expert_bytes'] / 1e9:.2f} GB); "
            f"vocab {r['vocab']}, recipe {r['recipe']}, pairs {' '.join(r['expert_pairs'])}; types {r['types']}")
    tot = sum(r["allocated_bytes"] for r in rows)
    say(f"plan total: {tot / 1e9:.2f} GB allocated ({sum(r['bytes'] for r in rows) / 1e9:.2f} GB apparent)")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1) + "\n")
    return 0


def free_gb(path: Path) -> float:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / 1e9


def cmd_disk(a):
    free = free_gb(Path(a.path))
    after = free - a.need_gb
    ok = after >= a.floor
    say(f"disk {a.path}: {free:.1f} GB free, {a.need_gb:.1f} GB to write -> {after:.1f} GB after "
        f"({'OK' if ok else 'REFUSED'}: floor {a.floor} GB)")
    return 0 if ok else 1


def cmd_profile(a):
    """setup's own rule (strata_control/setup_config.py neutral_profile_if_other_shape): a profile of another shape is
    refused by the engine, so a file of another shape gets every (layer, expert) pair once, interleaved, in its pack."""
    sys.path.insert(0, str(TREE / "tools"))
    sys.path.insert(0, str(TREE))
    from gguf_reader import GGUFFile                    # noqa: E402
    from strata_control.setup_config import neutral_profile_if_other_shape   # noqa: E402
    out = neutral_profile_if_other_shape(Path(a.shipped), Path(a.gguf), Path(a.pack), GGUFFile, say=lambda s: say(s.strip()))
    out = Path(out)
    if out.resolve() == Path(a.shipped).resolve():
        say(f"PROFILE FAIL: the shipped profile fits {a.gguf}'s shape?! (expected another shape)")
        return 1
    b = out.read_bytes()[:24]
    ver, nl, ne, slots, n = struct.unpack_from("<5I", b, 4)
    say(f"profile {out}: {b[:4].decode()} v{ver}, {nl} layers x {ne} experts, {n} pairs")
    return 0


# ================================================================================================ the smoke config
def _val(args: list, flag: str):
    return args[args.index(flag) + 1] if flag in args else None


def derive_cfg(base: dict, shape: str, exe: str, gguf: str, pack: str, profile: str, log: str, cwd: str, manifest: str,
               no_ple: bool = False) -> dict:
    c = json.loads(json.dumps(base))
    args = [str(x) for x in c["args"]]

    def setv(flag, val):
        if flag not in args:
            raise SystemExit(f"cfg: {flag} not in the base config's args")
        args[args.index(flag) + 1] = val

    def drop(flag, nval):
        while flag in args:
            i = args.index(flag)
            del args[i:i + 1 + nval]
    setv("--pack", pack)
    setv("--native", gguf)
    setv("--expert-profile", profile)
    if no_ple:
        drop("--ple-gguf", 1)
        drop("--ple-inflight", 1)
        args.append("--no-ple")
    else:
        setv("--ple-gguf", gguf)              # one file: its own (small) PLE table, as setup writes it for one shard
    # (11-09 smoke fix: a native (IQ) pack needs --spec T with T >= 2 - the engine refused the derived config at every shape;
    # no MTP head at another shape, so the windows draft by lookup only: 2 rows, the smallest verify window)
    setv("--spec", "2")
    # (11-09 smoke fix 2: with 4 layers the 5080's cache took every expert and the helper GPU exited "CUDA1 experts: no
    # unclaimed experts remain"; half of the shape's expert pairs go to the 5080, the rest to the 4060 Ti's helper cache,
    # so the helper's kernels run at the new shape too - the parity programs run on device 0 only)
    sh = synth_module().shape(shape, LAYERS)
    setv("--expert-cache", str(sh["n_layers"] * sh["n_expert"] // 2))
    drop("--spec-min-p", 1)
    drop("--mtp", 1)
    drop("--vision", 0)                       # no picture reader for a synthetic model
    c["args"] = args
    c["exe"] = exe
    c["cwd"] = cwd
    c["tokenizer"] = str(Path(pack) / "tokenizer")
    c["model_name"] = f"q4geo-{shape}-{LAYERS}l"
    c["log"] = log
    c["port"] = 8081
    c["host"] = "127.0.0.1"
    c["drafting"] = "off"
    c["mtp"] = False
    c["fallback"] = None                      # never a Flash-Next fallback start inside the gap
    for k in ("vision", "model_not_running"):
        c.pop(k, None)
    c["env"] = dict(c["env"], STRATA_MANIFEST=manifest)
    c["_comment"] = (f"shape gap 11-09 (work/r23/shape-gap): {shape}, {LAYERS} layers, synthetic random weights - derived from "
                     f"configs/P0213x.json by shape_rules.py cfg{' (--no-ple)' if no_ple else ''}; a test config, never served")
    return c


def cfg_problems(c: dict, base: dict, shape: str) -> list[str]:
    bad = []
    text = " ".join(str(x) for x in c["args"])
    for p in (str(ISTA1), str(ISTA1).replace("00001-of", "00002-of"), "/mtp/", "bringup/out/r20a/pack", str(SHIPPED_PROFILE)):
        if p in text:
            bad.append(f"a Flash-Next path is left in the args: {p}")
    if f"-{shape}-{LAYERS}l" not in c["exe"]:
        bad.append(f"exe {c['exe']} is not the {shape}-{LAYERS}l engine")
    if c.get("fallback") is not None or "vision" in c or "--vision" in c["args"]:
        bad.append("fallback / vision left in")
    if c.get("port") != 8081:
        bad.append("not the test port 8081")
    want_env = dict(base["env"], STRATA_MANIFEST=c["env"].get("STRATA_MANIFEST"))
    if c["env"] != want_env:
        bad.append("env differs from P0213x's beyond STRATA_MANIFEST")
    for f in ("--mtp", "--spec-min-p"):
        if f in c["args"]:
            bad.append(f"{f} left in")
    if c["args"].count("--spec") != 1 or c["args"][c["args"].index("--spec") + 1] != "2":
        bad.append("--spec is not exactly 2 (a native pack needs T >= 2; no MTP head here)")
    return bad


def cmd_cfg(a):
    base = json.loads(Path(a.base).read_text())
    c = derive_cfg(base, a.shape, a.exe, a.gguf, a.pack, a.profile, a.log, a.cwd, a.manifest, a.no_ple)
    bad = cfg_problems(c, base, a.shape)
    Path(a.out).write_text(json.dumps(c, indent=1) + "\n")
    changed = [k for k in sorted(set(base) | set(c)) if base.get(k) != c.get(k)]
    say(f"cfg {a.shape}{' --no-ple' if a.no_ple else ''} -> {a.out}: changed {', '.join(changed)}; args "
        f"{len(base['args'])} -> {len(c['args'])}")
    if bad:
        say("CFG FAIL: " + "; ".join(bad))
        return 1
    say("CFG OK")
    return 0


# ================================================================================================ ctest
def ctest_json(build: str) -> dict:
    r = subprocess.run(["ctest", "--test-dir", build, "--show-only=json-v1"], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise SystemExit(f"ctest --show-only failed in {build}: {r.stderr[-300:]}")
    return json.loads(r.stdout)


def geo_tests(j: dict) -> list[dict]:
    out = []
    for t in j.get("tests", []):
        cmd = t.get("command") or []
        prog = os.path.basename(cmd[0]) if cmd else ""
        if prog in GEO_TESTS:
            props = {p["name"]: p["value"] for p in t.get("properties", [])}
            out.append({"name": t["name"], "program": prog, "args": cmd[1:], "env": props.get("ENVIRONMENT", []),
                        "timeout": props.get("TIMEOUT"), "skip_rc": props.get("SKIP_RETURN_CODE")})
    return out


def cmd_ctestlist(a):
    j = json.loads(Path(a.json_in).read_text()) if a.json_in else ctest_json(a.build)
    ts = geo_tests(j)
    names = [t["name"] for t in ts]
    if len(set(names)) != len(names):
        say("CTESTLIST FAIL: duplicate test names")
        return 1
    if a.out:
        Path(a.out).write_text("".join(n + "\n" for n in names))
    per: dict[str, int] = {}
    for t in ts:
        per[t["program"]] = per.get(t["program"], 0) + 1
    missing = [p for p in GEO_TESTS if p not in per and p not in UNREGISTERED]
    say(f"ctestlist {a.build}: {len(names)} registered entries of {len(per)} GEO programs "
        f"({', '.join(f'{k} {v}' for k, v in sorted(per.items()))}); direct (no entry): {', '.join(UNREGISTERED)}"
        + (f"; NO ENTRY for {', '.join(missing)}" if missing else ""))
    return 1 if (missing or not names) else 0


LOG_RE = re.compile(r"^\s*\d+/\d+\s+Test\s+#\d+:\s+(\S+)\s+\.*\s*(?:\*{3})?(.*?)\s+([\d.]+)\s+sec\s*$")


def parse_ctest_log(text: str) -> dict:
    res = {}
    for line in text.splitlines():
        mm = LOG_RE.match(line)
        if not mm:
            continue
        name, st, secs = mm.group(1), mm.group(2).strip(), mm.group(3)
        if st.startswith("Passed"):
            s = "PASS"
        elif st.startswith("Skipped"):
            s = "SKIP"
        elif st.startswith("Not Run") or st.startswith("Disabled"):
            s = "NOTRUN"
        else:
            s = "FAIL"
        res[name] = (s, f"{st} {secs} s")
    return res


def parse_junit(text: str) -> dict:
    import xml.etree.ElementTree as ET
    res = {}
    root = ET.fromstring(text)
    for tc in root.iter("testcase"):
        name, st, t = tc.get("name"), tc.get("status", ""), tc.get("time", "?")
        sk, fl = tc.find("skipped"), tc.find("failure")
        if st == "run" and fl is None:
            res[name] = ("PASS", f"{t} s")
        elif sk is not None or st in ("notrun", "disabled"):
            msg = (sk.get("message") if sk is not None else st) or st
            res[name] = ("SKIP" if ("SKIP_RETURN_CODE" in msg or "SKIP_REGULAR" in msg or "Skipped" in msg) else "NOTRUN",
                         f"{msg} {t} s")
        else:
            res[name] = ("FAIL", f"{(fl.get('message') if fl is not None else st) or st} {t} s")
    return res


def cmd_parity(a):
    d = Path(a.dir)
    names = [n for n in (Path(a.names).read_text().split() if a.names and Path(a.names).exists() else [])]
    log = (d / "ctest.log").read_text(errors="replace") if (d / "ctest.log").exists() else ""
    jr = {}
    if (d / "junit.xml").exists():
        try:
            jr = parse_junit((d / "junit.xml").read_text(errors="replace"))
        except Exception as e:                      # noqa: BLE001 - a half-written file: the log decides
            say(f"(junit.xml unreadable: {e}; the log decides)")
    lr = parse_ctest_log(log)
    rows, notes = [], []
    for n in names or sorted(set(jr) | set(lr)):
        if n in jr:
            s, det = jr[n]
            if n in lr and lr[n][0] != s:
                notes.append(f"{n}: junit {s}, log {lr[n][0]}")
        elif n in lr:
            s, det = lr[n]
        else:
            s, det = "NOTRUN", "not reached (ctest stopped, or the deadline)"
        rows.append((n, s, det))
    if (d / "direct.txt").exists():
        for line in (d / "direct.txt").read_text().splitlines():
            p = line.split(None, 2)
            if len(p) >= 2:
                rows.append((p[0], p[1], p[2] if len(p) > 2 else ""))
    cnt = {k: sum(1 for r in rows if r[1] == k) for k in ("PASS", "SKIP", "FAIL", "NOTRUN")}
    k_fail = cnt["FAIL"] + cnt["NOTRUN"]
    with open(d / "results.txt", "w") as f:
        for n, s, det in rows:
            f.write(f"{n} {s} {det}\n")
        for x in notes:
            f.write(f"# note: {x}\n")
        f.write(f"# {a.label}: {cnt['PASS']} pass / {cnt['SKIP']} skip / {k_fail} fail"
                + (f" ({cnt['NOTRUN']} of them not run)" if cnt["NOTRUN"] else "") + f" of {len(rows)}\n")
    say(f"parity {a.label}: {cnt['PASS']} pass / {cnt['SKIP']} skip / {k_fail} fail of {len(rows)}"
        + (f" ({cnt['NOTRUN']} not run)" if cnt["NOTRUN"] else ""))
    for n, s, det in rows:
        if s in ("FAIL", "NOTRUN"):
            say(f"  {s} {n}: {det}")
    for x in notes:
        say(f"  (note) {x}")
    json.dump({"label": a.label, "pass": cnt["PASS"], "skip": cnt["SKIP"], "fail": k_fail, "notrun": cnt["NOTRUN"],
               "total": len(rows), "fails": [f"{n} ({s}: {det})" for n, s, det in rows if s in ("FAIL", "NOTRUN")]},
              open(d / "counts.json", "w"))
    return 0


# ================================================================================================ the smoke start
def proc_env(pid: str) -> tuple[dict, list]:
    env = {}
    raw = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    for kv in raw:
        if b"=" in kv:
            k, v = kv.split(b"=", 1)
            env[k.decode(errors="replace")] = v.decode(errors="replace")
    argv = [x.decode(errors="replace") for x in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if x]
    return env, argv


def cmd_envcheck(a):
    cfg = json.loads(Path(a.config).read_text())
    want = cfg.get("env", {})
    exe = os.path.realpath(a.exe)
    procs = []
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                if os.readlink(d / "exe") == exe:
                    procs.append((d.name, *proc_env(d.name)))
            except OSError:
                continue
    lines, bad_all = [], []
    if not procs:
        lines.append(f"ENV CHECK FAILED: no running engine {exe}")
        bad_all.append("no engine")
    for pid, env, argv in procs:
        bad = [f"{k}={env.get(k, 'unset')} (want {v})" for k, v in want.items() if env.get(k) != v]
        extra = sorted(k for k in env if k.startswith("STRATA_") and k not in want)
        n = len([x for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x])
        if n != 2:
            bad.append(f"{n} GPU(s) in CUDA_VISIBLE_DEVICES (want 2)")
        for flag in ("--native", "--pack", "--ple-gguf", "--expert-profile"):
            if _val(cfg["args"], flag) != _val(argv, flag):
                bad.append(f"{flag} {_val(argv, flag)} (want {_val(cfg['args'], flag)})")
        lines.append(f"engine pid {pid}: {len(want)} config env keys checked, {n} GPU(s), --native {_val(argv, '--native')}"
                     + (f"; STRATA_ keys beside the config (INFO): {' '.join(extra)}" if extra else "")
                     + (f"; MISMATCH {', '.join(bad)}" if bad else ""))
        bad_all += bad
    lines.append("ENV CHECK OK" if not bad_all else "ENV CHECK FAILED")
    text = "\n".join(lines)
    say(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0 if not bad_all else 1


def http_json(url: str, body: dict | None = None, timeout: float = 60):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 127.0.0.1 never through a proxy
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"} if data else {})
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read())


def judge_reply(reply: dict) -> list[str]:
    bad = []
    ch = (reply.get("choices") or [{}])[0]
    usage = reply.get("usage") or {}
    if not usage.get("completion_tokens"):
        bad.append("no completion tokens")
    if ch.get("finish_reason") not in ("length", "stop"):
        bad.append(f"finish_reason {ch.get('finish_reason')!r} (want length or stop)")
    if not isinstance(ch.get("message"), dict):
        bad.append("no message in the reply")
    return bad


def cmd_chat(a):
    t0 = time.time()
    rec = {"url": a.url}
    try:
        models = http_json(a.url + "/v1/models", timeout=30)
        mid = models["data"][0]["id"]
        body = {"model": mid, "messages": [{"role": "user", "content": "What is the capital of France?"}],
                "max_tokens": a.max_tokens, "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05,
                "presence_penalty": 0.0, "stream": False}
        rec["request"] = body
        reply = http_json(a.url + "/v1/chat/completions", body, timeout=a.timeout)
        rec["reply"] = reply
        bad = judge_reply(reply)
    except Exception as e:                           # noqa: BLE001
        bad = [f"the request failed: {type(e).__name__}: {e}"]
    rec["seconds"] = round(time.time() - t0, 2)
    rec["problems"] = bad
    Path(a.out).write_text(json.dumps(rec, indent=1) + "\n")
    r = rec.get("reply") or {}
    ch = (r.get("choices") or [{}])[0]
    say(f"chat: finish {ch.get('finish_reason')}, usage {r.get('usage')}, {rec['seconds']} s"
        + (f"; CHAT FAIL: {'; '.join(bad)}" if bad else "; CHAT OK"))
    return 0 if not bad else 1


def expected_guards(shape: str) -> dict:
    """What the guards should say for this shape's build (v0.2.13 port fixes A-C): gr_fork off, with the 'not built' reason,
    unless the compiled shape is Flash-Next's 2560 / 4 / 320; prefill_v2 on where kV2Shape holds and the experts have IQ4_NL down."""
    m = synth_module()
    s = m.shape(shape, LAYERS)
    fork = (s["n_embd"], s["hc"], s["hc_lr"]) == (2560, 4, 320)
    v2shape = (2 * s["n_ff"]) % 256 == 0 and s["n_embd"] % 256 == 0 and s["n_ff"] % 128 == 0
    v2types = any(m.recipe_type(RECIPE, "down", l, s) == "IQ4_NL" or m.recipe_type(RECIPE, "gate", l, s) == "IQ3_XXS"
                  for l in range(s["n_layers"]))
    return {"gr_fork_on": fork, "prefill_v2_on": v2shape and v2types, "kV2Shape": v2shape, "v2_types": v2types}


def judge_guards(text: str, exp: dict) -> tuple[list[str], list[str]]:
    """(record lines, unexpected lines)."""
    lines = [l.strip() for l in text.splitlines() if l.startswith("strata patch guard")]
    rec, bad = list(lines), []
    summ = next((l for l in lines if l.startswith("strata patch guards:")), None)
    if summ is None:
        return rec, ["no 'strata patch guards:' summary line (the probe did not reach the guards)"]
    mm = re.search(r"\[([^\]]*)\]", summ)
    state = {}
    for tok in (mm.group(1).split() if mm else []):
        state[tok.replace("(off)", "")] = "off" if tok.endswith("(off)") else "on"
    off_lines = {l.split()[3]: l for l in lines if " OFF (" in l}
    fork = state.get("gr_fork")
    if exp["gr_fork_on"]:
        if fork != "on":
            bad.append(f"gr_fork {fork} (want on: the fork is built for this shape): {off_lines.get('gr_fork', '')}")
    else:
        if fork != "off" or FORK_TEXT not in off_lines.get("gr_fork", ""):
            bad.append(f"gr_fork {fork} without the reason '{FORK_TEXT}' (want OFF with it)")
    v2 = state.get("prefill_v2")
    if exp["prefill_v2_on"] and v2 != "on":
        bad.append(f"prefill_v2 {v2} (want on: kV2Shape and IQ4_NL down): {off_lines.get('prefill_v2', '')}")
    if not exp["prefill_v2_on"] and v2 != "off":
        bad.append(f"prefill_v2 {v2} (want off: kV2Shape {exp['kV2Shape']}, v2 types {exp['v2_types']})")
    for g in GUARDS:
        if g in ("gr_fork", "prefill_v2"):
            continue
        if state.get(g) != "on":
            bad.append(f"{g} {state.get(g)} (want on): {off_lines.get(g, '')}")
    return rec, bad


def cmd_guards(a):
    text = Path(a.file).read_text(errors="replace") if Path(a.file).exists() else ""
    exp = expected_guards(a.shape)
    rec, bad = judge_guards(text, exp)
    out = [f"guards {a.shape}: expected gr_fork {'on' if exp['gr_fork_on'] else 'OFF (not built for this shape)'}, "
           f"prefill_v2 {'on' if exp['prefill_v2_on'] else 'off'} (kV2Shape {exp['kV2Shape']})"]
    out += [f"  {l}" for l in rec]
    out.append(f"GUARDS {'AS EXPECTED' if not bad else 'UNEXPECTED: ' + '; '.join(bad)}")
    say("\n".join(out))
    if a.out:
        Path(a.out).write_text("\n".join(out) + "\n")
    return 0 if not bad else 1


def cmd_manifest(a):
    p = Path(a.file)
    if not p.exists():
        say(f"MANIFEST MISSING: {p}")
        return 1
    d = json.loads(p.read_text())
    e = d.get("engine", {})
    tc, cv = e.get("gdn_tc"), e.get("gdn_convl2")
    out = [f"manifest {p.name}: stage {d.get('stage')}, gdn_tc {tc}, gdn_convl2 {cv} (P0213x pins 0 / 0), engine "
           f"{e.get('engine')}, drafter {e.get('drafter')}, kv {e.get('kv_format')}"]
    for x in d.get("paths", []):
        if x.get("area") in ("prefill", "dense", "experts") or "v2" in x.get("name", "") or "gdn" in x.get("name", ""):
            out.append(f"  path {x.get('area')}/{x.get('name')}: {'selected' if x.get('selected') else 'declined'}"
                       + (f" - {x.get('reason')}" if x.get("reason") else "") + (f" ({x.get('detail')})" if x.get("detail") else ""))
    ok = tc == "0" and cv == "0"
    out.append("MANIFEST GDN PINS " + ("AS CONFIGURED (0 / 0)" if ok else f"NOT 0 / 0 ({tc} / {cv})"))
    say("\n".join(out))
    if a.out:
        Path(a.out).write_text("\n".join(out) + "\n")
    return 0 if ok else 1


# ================================================================================================ the prep record
def engine_dir(shape: str) -> Path:
    return WS / f"engine-r23p0213-{shape}-{LAYERS}l"


def prep_paths(shape: str) -> dict:
    name = f"{shape}-{LAYERS}l"
    pack = MODELS / f"pack-{name}"
    return {"gguf": MODELS / f"{name}.gguf", "pack": pack, "header": SG / "geo" / f"{shape}_{LAYERS}l.hpp",
            "engine": engine_dir(shape) / "strata", "build4l": TREE / f"build-{name}", "buildfull": TREE / f"build-{shape}",
            "profile": next(iter(sorted(pack.glob("expert-profile-*.bin"))), pack / "expert-profile-missing.bin")}


PACK_FILES = ("native_experts.txt", "index.txt", "dense.bin", "conversions.json", "tokenizer/vocab.json")


def cmd_record(a):
    head = git("rev-parse", "HEAD")
    rec = {"written": time.strftime("%F %T"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "head": head,
           "tree": git("rev-parse", "HEAD^{tree}"), "recipe": RECIPE, "layers": LAYERS, "shapes": {}}
    bad = []
    for s in SHAPES:
        p = prep_paths(s)
        r = {}
        for k in ("gguf", "header", "engine", "profile"):
            f = p[k]
            if not f.exists():
                bad.append(f"{s}: {k} {f} missing")
                continue
            r[k] = {"path": str(f), "size": f.stat().st_size, "sha256": sha256(f)}
        r["pack"] = {}
        for pf in PACK_FILES:
            f = p["pack"] / pf
            if not f.exists():
                bad.append(f"{s}: pack file {f} missing")
                continue
            r["pack"][pf] = {"size": f.stat().st_size, "sha256": sha256(f)}
        src = engine_dir(s) / "SOURCE"
        r["engine_source"] = src.read_text().strip() if src.exists() else ""
        if head not in r["engine_source"]:
            bad.append(f"{s}: {src} does not name HEAD {head[:12]}")
        r["build4l"] = str(p["build4l"])
        r["buildfull"] = str(p["buildfull"])
        rec["shapes"][s] = r
    Path(a.out).write_text(json.dumps(rec, indent=1) + "\n")
    say(f"record -> {a.out}: head {head[:12]}, {len(SHAPES)} shapes" + (f"; PROBLEMS: {'; '.join(bad)}" if bad else ""))
    return 1 if bad else 0


def cmd_verify(a):
    """The gap's preflight: the prep record against the disk now - every file there with its size and sha256, the tree on
    the branch at the recorded HEAD and clean, each engine's SOURCE naming HEAD and its SHA256 file matching."""
    rec = json.loads(Path(a.ready).read_text())
    bad = []
    try:
        head = git("rev-parse", "HEAD")
        br = git("rev-parse", "--abbrev-ref", "HEAD")
        dirty = git("status", "--porcelain", "--untracked-files=no")
    except subprocess.CalledProcessError as e:
        say(f"VERIFY FAIL: git: {e}")
        return 1
    if br != BRANCH:
        bad.append(f"the tree is on {br}, not {BRANCH}")
    if head != rec["head"]:
        bad.append(f"HEAD {head[:12]} is not the prep's {rec['head'][:12]}")
    if dirty:
        bad.append("the tree is dirty")
    for s, r in rec["shapes"].items():
        for k in ("gguf", "header", "engine", "profile"):
            f = Path(r[k]["path"])
            if not f.exists():
                bad.append(f"{s}: {f} missing")
            elif f.stat().st_size != r[k]["size"]:
                bad.append(f"{s}: {f} size changed")
            elif not a.quick and sha256(f) != r[k]["sha256"]:
                bad.append(f"{s}: {f} sha256 changed")
        for pf, v in r["pack"].items():
            f = Path(prep_paths(s)["pack"]) / pf
            if not f.exists() or f.stat().st_size != v["size"] or (not a.quick and sha256(f) != v["sha256"]):
                bad.append(f"{s}: pack file {f} missing or changed")
        e = engine_dir(s)
        shaf = e / "SHA256"
        if not shaf.exists() or shaf.read_text().split()[0] != r["engine"]["sha256"]:
            bad.append(f"{s}: {shaf} does not match the engine")
        src_text = (e / "SOURCE").read_text() if (e / "SOURCE").exists() else ""
        if head not in src_text:
            bad.append(f"{s}: {e}/SOURCE missing or does not name HEAD")
    for line in bad:
        say(f"  VERIFY: {line}")
    say("VERIFY " + ("OK" if not bad else f"FAIL ({len(bad)})") + f": prep record {a.ready} ({'size only' if a.quick else 'sha256'})")
    return 0 if not bad else 1


# ================================================================================================ the verdict
def kv_file(p: Path) -> dict:
    d = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def cmd_verdict(a):
    o = Path(a.outdir)
    rows, fails, info = [], [], []
    builds = kv_file(o / "builds.txt")
    for row in ("flash_next",) + SHAPES:
        c = o / "parity" / row / "counts.json"
        if c.exists():
            cj = json.loads(c.read_text())
            par = f"parity programs {cj['pass']} pass / {cj['skip']} skip / {cj['fail']} fail"
            fails += [f"{row}: {x}" for x in cj["fails"]]
        else:
            par = "parity programs NOT RUN"
        b = builds.get(row, "?")
        if row == "flash_next":
            rows.append(f"flash_next (reference): builds {b}, {par}")
            continue
        sm = kv_file(o / "smoke" / row / "smoke.txt")
        loads = sm.get("answers", "not run")
        why = sm.get("why", "")
        rows.append(f"{row}: builds {b}, {par}, loads and answers {loads}" + (f" ({why})" if why and loads != "yes" else ""))
        for k in ("guards", "manifest", "env", "nople"):
            if sm.get(k):
                info.append(f"{row} {k}: {sm[k]}")
        if loads != "yes":
            fails.append(f"{row}: smoke - {why or loads}")
    text = ["SHAPE GAP 11-09 (v0.2.13 port, information only: nothing switches, P028x stays served)", ""] + rows + [""]
    text += ["FAILS (each with its program):"] + ([f"  {x}" for x in fails] or ["  none"]) + [""]
    text += ["guards / manifest / env (from the smoke records):"] + ([f"  {x}" for x in info] or ["  -"])
    (o / "decision.txt").write_text("\n".join(text) + "\n")
    say("\n".join(rows))
    short = "; ".join(r.replace(" (reference)", " (ref)") for r in rows)
    Path(o / "verdict-line.txt").write_text(short + "\n")
    return 0


# ================================================================================================ cleanup sizes
def du_bytes(p: Path) -> int:
    if not p.exists():
        return 0
    r = subprocess.run(["du", "-sb", str(p)], capture_output=True, text=True)
    try:
        return int(r.stdout.split()[0])
    except (IndexError, ValueError):
        return 0


def cmd_sizes(a):
    keep_max = int(a.keep_max_gb * 1e9)
    rows = []
    for name in ("q4_mid", "q4_big", "q4_deep", "q4_mid-4l", "q4_big-4l", "q4_deep-4l"):
        e = WS / f"engine-r23p0213-{name}"
        b = TREE / f"build-{name}"
        es, bs = du_bytes(e), du_bytes(b)
        rows.append({"name": name, "engine": str(e), "engine_bytes": es, "keep_engine": 0 < es < keep_max,
                     "build": str(b), "build_bytes": bs})
    b = TREE / "build-flash_next"
    rows.append({"name": "flash_next", "engine": "", "engine_bytes": 0, "keep_engine": False, "build": str(b),
                 "build_bytes": du_bytes(b)})
    for r in rows:
        say(f"{r['name']:12s} engine {r['engine_bytes'] / 1e9:6.2f} GB -> {'KEEP' if r['keep_engine'] else ('delete' if r['engine_bytes'] else '-')}"
            f"   build {r['build_bytes'] / 1e9:6.2f} GB -> {'delete' if r['build_bytes'] else '-'}   ({r['build']})")
    se = sum(r["engine_bytes"] for r in rows if r["keep_engine"])
    sb = sum(r["build_bytes"] for r in rows)
    say(f"rule: an engine copy is kept when under {a.keep_max_gb:g} GB (kept {se / 1e9:.2f} GB); every build directory above "
        f"is deleted ({sb / 1e9:.2f} GB)")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1) + "\n")
    return 0


# ================================================================================================ selftest
JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Linux" tests="4" failures="1" disabled="0" skipped="1" hostname="" time="3" timestamp="2026-11-09T14:00:00">
\t<testcase name="gr_parity" classname="gr_parity" time="0.36" status="run"><system-out>gr_parity OK</system-out></testcase>
\t<testcase name="prefill_fused_iq_test_ws" classname="prefill_fused_iq_test_ws" time="0.02" status="notrun">
\t\t<skipped message="SKIP_RETURN_CODE=77"/><system-out>skipped</system-out></testcase>
\t<testcase name="qsa_parity" classname="qsa_parity" time="0.40" status="fail"><failure message="Failed"/></testcase>
\t<testcase name="gdn_parity" classname="gdn_parity" time="0.00" status="notrun"><skipped message="Unable to find executable"/></testcase>
</testsuite>
"""
CTLOG = """Test project /x/build-q4_mid
      Start  54: gr_parity
 1/5 Test  #54: gr_parity ........................   Passed    0.36 sec
 2/5 Test #126: prefill_fused_iq_test_ws .........***Skipped   0.02 sec
 3/5 Test  #79: qsa_parity .......................***Failed    0.40 sec
 4/5 Test  #55: gdn_parity .......................***Not Run   0.00 sec
 5/5 Test  #60: native_dense_parity ..............***Timeout 300.01 sec
"""
GUARD_MID = """strata patch guard: gr_fork OFF (STRATA_GR_FORK=0; upstream's path): this build is compiled for n_embd 3072, 4 streams, low rank 384; the fork read is built for Flash-Next's 2560 / 4 / 320 only
strata patch guard: spec_exact on - x
strata patch guards: 7 checked, 1 off [spec_exact side_mixer router_q8k qsa_split_attn gr_fork(off) draft_cum prefill_v2]; model qwen4exp 3072 x 4 layers (+0 nextn), 256 experts of 1024, vocab 248320, draft vocab -1; experts IQ3_S/IQ4_NL IQ4_XS/IQ4_NL
"""
GUARD_DEEP_BAD = """strata patch guard: gr_fork OFF (STRATA_GR_FORK=0; upstream's path): n_embd 2560, 4 streams, low rank 320; compiled for 1 / 1 / 1
strata patch guards: 7 checked, 2 off [spec_exact side_mixer router_q8k qsa_split_attn gr_fork(off) draft_cum prefill_v2(off)]; model qwen4exp 2560 x 4 layers
"""


def selftest(d: Path) -> int:
    d.mkdir(parents=True, exist_ok=True)
    fails = []

    def ok(cond, what):
        if not cond:
            fails.append(what)
    # ctest parsers
    j = parse_junit(JUNIT)
    ok(j["gr_parity"][0] == "PASS" and j["prefill_fused_iq_test_ws"][0] == "SKIP" and j["qsa_parity"][0] == "FAIL"
       and j["gdn_parity"][0] == "NOTRUN", f"junit {j}")
    lg = parse_ctest_log(CTLOG)
    ok(lg["gr_parity"][0] == "PASS" and lg["prefill_fused_iq_test_ws"][0] == "SKIP" and lg["qsa_parity"][0] == "FAIL"
       and lg["gdn_parity"][0] == "NOTRUN" and lg["native_dense_parity"][0] == "FAIL", f"log {lg}")
    pd = d / "parity"
    pd.mkdir(exist_ok=True)
    (pd / "junit.xml").write_text(JUNIT)
    (pd / "ctest.log").write_text(CTLOG)
    (pd / "direct.txt").write_text("patch_guard_test PASS rc=0 0.3 s\nqsa_prompt_attn_parity SKIP rc=77 1 s\n")
    (pd / "names.txt").write_text("gr_parity\nprefill_fused_iq_test_ws\nqsa_parity\ngdn_parity\nnative_dense_parity\nverify_parity\n")
    cmd_parity(argparse.Namespace(dir=str(pd), names=str(pd / "names.txt"), label="selftest"))
    cj = json.loads((pd / "counts.json").read_text())
    # gr_parity + patch_guard_test pass; ws + qsa_prompt_attn skip; qsa_parity, native_dense (timeout) fail; gdn + verify not run
    ok((cj["pass"], cj["skip"], cj["fail"], cj["notrun"]) == (2, 2, 4, 2), f"parity counts {cj}")
    # ctest json selection
    fake = {"tests": [{"name": "gr_parity", "command": ["/b/gr_parity", "--selftest"], "properties": []},
                      {"name": "prefill_fused_v2_test", "command": ["/b/prefill_fused_iq_test", "--v2", "--no-timing"],
                       "properties": [{"name": "TIMEOUT", "value": 600.0}, {"name": "SKIP_RETURN_CODE", "value": 77}]},
                      {"name": "other_test", "command": ["/b/other_test"], "properties": []},
                      {"name": "unbuilt", "properties": []}]}
    g = geo_tests(fake)
    ok([t["name"] for t in g] == ["gr_parity", "prefill_fused_v2_test"] and g[1]["skip_rc"] == 77, f"geo_tests {g}")
    # guards
    exp_mid = {"gr_fork_on": False, "prefill_v2_on": True, "kV2Shape": True, "v2_types": True}
    rec, bad = judge_guards(GUARD_MID, exp_mid)
    ok(not bad and len(rec) == 3, f"guards mid {bad}")
    exp_deep = {"gr_fork_on": True, "prefill_v2_on": True, "kV2Shape": True, "v2_types": True}
    rec, bad = judge_guards(GUARD_DEEP_BAD, exp_deep)
    ok(len(bad) == 2, f"guards deep bad {bad}")
    rec, bad = judge_guards("nothing here\n", exp_deep)
    ok(len(bad) == 1 and "summary" in bad[0], "guards empty")
    for s in SHAPES:          # the real shapes' expectations (from q4geo_synth's own shape table)
        e = expected_guards(s)
        ok(e["gr_fork_on"] == (s == "q4_deep") and e["prefill_v2_on"] == (RECIPE == "fused-iq"), f"expected_guards {s} {e}")
    # chat judge
    ok(not judge_reply({"choices": [{"finish_reason": "length", "message": {"content": "x"}}], "usage": {"completion_tokens": 24}}),
       "reply ok")
    ok(len(judge_reply({"choices": [{"finish_reason": "error"}], "usage": {}})) == 3, "reply bad")
    # the config derivation on the real P0213x.json (read only), into the selftest folder
    base = json.loads(BASE_CFG.read_text())
    for s in SHAPES:
        p = prep_paths(s)
        for nople in (False, True):
            c = derive_cfg(base, s, str(p["engine"]), str(p["gguf"]), str(p["pack"]), str(p["pack"] / "expert-profile-4x256.bin"),
                           str(d / f"engine-{s}.log"), str(d / f"run-{s}"), str(d / f"manifest-{s}.json"), nople)
            b = cfg_problems(c, base, s)
            ok(not b, f"cfg {s} nople={nople}: {b}")
            ok(("--no-ple" in c["args"]) == nople and (_val(c["args"], "--ple-gguf") == (None if nople else str(p["gguf"]))),
               f"cfg ple {s} {nople}")
            ok(_val(c["args"], "--kv-resident") == "32768" and _val(c["args"], "--prefill") == "auto:16384", f"cfg kept args {s}")
            (d / f"cfg-{s}{'-nople' if nople else ''}.json").write_text(json.dumps(c, indent=1))
    bad_c = dict(derive_cfg(base, "q4_mid", "/x/engine-r23p0213-q4_mid-4l/strata", "/g", "/p", "/pr", "/l", "/c", "/m"), fallback="x")
    ok(cfg_problems(bad_c, base, "q4_mid"), "cfg_problems sees a fallback")
    # the plan arithmetic (a tiny shape, no tokenizer; nothing is written)
    m = synth_module()
    r = plan_shape(m, "q4_lite", 1, "ud-q4k", 2048, True, {"n_expert": 8, "n_expert_used": 2, "n_ff": 64})
    ok(r["bytes"] > r["allocated_bytes"] > r["expert_bytes"] > 0 and r["bytes"] % m.DEFAULT_ALIGNMENT == 0, f"plan tiny {r}")
    r2 = plan_shape(m, "q4_mid", LAYERS, "fused-iq", 248320, True)
    ok(r2["expert_pairs"] == ["IQ3_S/IQ4_NL", "IQ4_XS/IQ4_NL"], f"plan pairs {r2['expert_pairs']}")
    # verdict on a fake out dir
    o = d / "verdict"
    for row in ("flash_next",) + SHAPES:
        (o / "parity" / row).mkdir(parents=True, exist_ok=True)
        json.dump({"pass": 80, "skip": 3, "fail": 1 if row == "q4_big" else 0, "notrun": 0, "total": 84,
                   "fails": ["qsa_parity (FAIL: Failed)"] if row == "q4_big" else []}, open(o / "parity" / row / "counts.json", "w"))
    for s in SHAPES:
        (o / "smoke" / s).mkdir(parents=True, exist_ok=True)
        (o / "smoke" / s / "smoke.txt").write_text("answers=yes\n" if s != "q4_deep" else "answers=no\nwhy=the server did not start\n")
    (o / "builds.txt").write_text("flash_next=rc 0\nq4_mid=full rc 0, 4-layer rc 0\nq4_big=full rc 0, 4-layer rc 0\nq4_deep=full rc 0, 4-layer rc 0\n")
    cmd_verdict(argparse.Namespace(outdir=str(o)))
    dec = (o / "decision.txt").read_text()
    ok("q4_big: builds full rc 0, 4-layer rc 0, parity programs 80 pass / 3 skip / 1 fail, loads and answers yes" in dec
       and "q4_deep: smoke - the server did not start" in dec and "q4_big: qsa_parity" in dec, "verdict text")
    for f in fails:
        say(f"SELFTEST FAIL: {f}")
    say(f"shape_rules selftest: {'OK' if not fails else 'FAILED'} ({len(fails)} failure(s))")
    return 0 if not fails else 1


# ================================================================================================ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan")
    p.add_argument("--shapes", default=",".join(SHAPES))
    p.add_argument("--layers", type=int, default=LAYERS)
    p.add_argument("--recipe", default=RECIPE)
    p.add_argument("--vocab", type=int, default=8192)
    p.add_argument("--tokenizer-from")
    p.add_argument("--small-ple", action="store_true")
    p.add_argument("--json")
    p = sp.add_parser("disk")
    p.add_argument("--path", default=str(WS / "models"))
    p.add_argument("--need-gb", type=float, required=True)
    p.add_argument("--floor", type=float, default=FLOOR_GB)
    p = sp.add_parser("profile")
    p.add_argument("gguf")
    p.add_argument("pack")
    p.add_argument("--shipped", default=str(SHIPPED_PROFILE))
    p = sp.add_parser("cfg")
    p.add_argument("shape", choices=SHAPES)
    for x in ("--exe", "--gguf", "--pack", "--profile", "--log", "--cwd", "--manifest", "--out"):
        p.add_argument(x, required=True)
    p.add_argument("--base", default=str(BASE_CFG))
    p.add_argument("--no-ple", action="store_true")
    p = sp.add_parser("ctestlist")
    p.add_argument("build")
    p.add_argument("--out")
    p.add_argument("--json-in", help="a saved `ctest --show-only=json-v1` output instead of running it")
    p = sp.add_parser("parity")
    p.add_argument("dir")
    p.add_argument("--names")
    p.add_argument("--label", required=True)
    p = sp.add_parser("envcheck")
    p.add_argument("exe")
    p.add_argument("config")
    p.add_argument("--out")
    p = sp.add_parser("chat")
    p.add_argument("url")
    p.add_argument("--out", required=True)
    p.add_argument("--max-tokens", type=int, default=32)
    p.add_argument("--timeout", type=float, default=300)
    p = sp.add_parser("guards")
    p.add_argument("file")
    p.add_argument("--shape", required=True, choices=SHAPES)
    p.add_argument("--out")
    p = sp.add_parser("manifest")
    p.add_argument("file")
    p.add_argument("--out")
    p = sp.add_parser("record")
    p.add_argument("--out", required=True)
    p = sp.add_parser("verify")
    p.add_argument("ready")
    p.add_argument("--quick", action="store_true", help="sizes only, no sha256")
    p = sp.add_parser("verdict")
    p.add_argument("outdir")
    p = sp.add_parser("sizes")
    p.add_argument("--keep-max-gb", type=float, default=1.0)
    p.add_argument("--json")
    p = sp.add_parser("selftest")
    p.add_argument("dir")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest(Path(a.dir))
    return {"plan": cmd_plan, "disk": cmd_disk, "profile": cmd_profile, "cfg": cmd_cfg, "ctestlist": cmd_ctestlist,
            "parity": cmd_parity, "envcheck": cmd_envcheck, "chat": cmd_chat, "guards": cmd_guards, "manifest": cmd_manifest,
            "record": cmd_record, "verify": cmd_verify, "verdict": cmd_verdict, "sizes": cmd_sizes}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
