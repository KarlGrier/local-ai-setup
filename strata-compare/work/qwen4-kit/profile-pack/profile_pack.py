#!/usr/bin/env python3
"""profile_pack.py - write a "profile pack": one Markdown file that tells an outside researcher how a local MoE model runs
on this PC (model shape and quant, engine build and config, speeds, expert placement, MTP drafting, memory, the
per-window time split, what was already tried), every number with its source file:line.

    profile_pack.py run INPUTS.json [--out PATH] [--facts]    build the pack from existing measurement files
    profile_pack.py selftest                                  synthetic inputs in scratch/selftest-*/ (no GPU, no network)

Read-only on every input. Nothing here starts an engine, a server or a measurement. The inputs file names the config,
the engine folder, the model's first shard, the speed result files, the engine-log slice, the decode-timing report, the
monitor / guard / summary lines and the curated "already tried" list (see inputs-flashnext.json).

Privacy: the pack is for outside readers. Before writing, scrub() refuses (exit 3, nothing written) if the text still has
a username, a home path, the hostname, an IP other than 127.0.0.1, a UUID, an email, an API key or token, or the names of
the owner's other tools. Findings are printed as pattern name + line + column only, never the matched text.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import glob
import hashlib
import importlib.util
import json
import os
import pwd
import re
import shutil
import socket
import statistics
import struct
import sys

GEN_VERSION = "1 (2026-11-09)"
HERE = os.path.dirname(os.path.abspath(__file__))

# ======================================================================================================= GGUF header
# Built-in minimal GGUF v3 header reader (used by the selftest, and as the fallback when the tree's reader is not given).
GGML_TYPES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K",
    12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S",
    20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64",
    29: "IQ1_M", 30: "BF16", 34: "TQ1_0", 35: "TQ2_0", 39: "MXFP4", 40: "NVFP4", 42: "Q2_0",
}
BLOCK = {
    "F32": (1, 4), "F16": (1, 2), "BF16": (1, 2), "F64": (1, 8), "I8": (1, 1), "I16": (1, 2), "I32": (1, 4),
    "I64": (1, 8), "Q4_0": (32, 18), "Q4_1": (32, 20), "Q5_0": (32, 22), "Q5_1": (32, 24), "Q8_0": (32, 34),
    "Q8_1": (32, 36), "Q2_K": (256, 84), "Q3_K": (256, 110), "Q4_K": (256, 144), "Q5_K": (256, 176),
    "Q6_K": (256, 210), "Q8_K": (256, 292), "IQ2_XXS": (256, 66), "IQ2_XS": (256, 74), "IQ3_XXS": (256, 98),
    "IQ1_S": (256, 50), "IQ4_NL": (32, 18), "IQ3_S": (256, 110), "IQ2_S": (256, 82), "IQ4_XS": (256, 136),
    "IQ1_M": (256, 56), "Q2_0": (64, 18), "MXFP4": (32, 17), "NVFP4": (64, 36),
}
_META = {0: ("B", 1), 1: ("b", 1), 2: ("H", 2), 3: ("h", 2), 4: ("I", 4), 5: ("i", 4), 6: ("f", 4), 7: ("?", 1),
         10: ("Q", 8), 11: ("q", 8), 12: ("d", 8)}


def _gguf_builtin(path):
    with open(path, "rb") as fh:
        def rd(n):
            b = fh.read(n)
            if len(b) != n:
                raise ValueError(f"{os.path.basename(path)}: header ends early")
            return b

        def u(fmt):
            return struct.unpack("<" + fmt, rd(struct.calcsize("<" + fmt)))

        def s():
            (n,) = u("Q")
            return rd(n).decode("utf-8", "replace")

        def val(t):
            if t == 8:
                return s()
            if t == 9:
                et, cnt = u("IQ")
                if et == 8:
                    return [s() for _ in range(cnt)]
                if et not in _META:
                    raise ValueError("unsupported array type")
                f, sz = _META[et]
                return list(struct.unpack("<%d%s" % (cnt, f), rd(cnt * sz)))
            if t not in _META:
                raise ValueError(f"unknown metadata type {t}")
            return u(_META[t][0])[0]

        (magic,) = u("I")
        if magic != 0x46554747:
            raise ValueError(f"{os.path.basename(path)}: not a GGUF file")
        ver, nt, nkv = u("IQQ")
        meta = {}
        for _ in range(nkv):
            k = s()
            (t,) = u("I")
            meta[k] = val(t)
        tensors = []
        for _ in range(nt):
            name = s()
            (nd,) = u("I")
            shape = list(u("%dQ" % nd))
            tid, _off = u("IQ")
            tensors.append((name, shape, GGML_TYPES.get(tid, f"type{tid}")))
    return {"version": ver, "metadata": meta, "tensors": tensors, "reader": "built-in"}


def _gguf_tree(path, reader_dir):
    """The tree's tools/gguf_reader.py, loaded from its own file only (no folder on sys.path)."""
    f = os.path.join(reader_dir, "gguf_reader.py")
    spec = importlib.util.spec_from_file_location("pp_tree_gguf_reader", f)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # dataclasses look the module up by name
    spec.loader.exec_module(mod)
    g = mod.GGUFFile(path)
    return {"version": g.version, "metadata": dict(g.metadata),
            "tensors": [(t.name, list(t.shape), t.type_name) for t in g.tensors],
            "reader": "the tree's tools/gguf_reader.py"}


def read_gguf(path, reader_dir=None):
    if reader_dir and os.path.exists(os.path.join(reader_dir, "gguf_reader.py")):
        return _gguf_tree(path, reader_dir)
    return _gguf_builtin(path)


def nelem(shape):
    n = 1
    for d in shape:
        n *= d
    return n


def tbytes(shape, ty):
    g = BLOCK.get(ty)
    if g is None or nelem(shape) % g[0]:
        return None
    return nelem(shape) // g[0] * g[1]


def tensor_role(name):
    n = name.split(".")
    base = ".".join(n[2:]) if n[0] == "blk" else name
    if "_exps" in base:
        return "routed experts"
    if "_shexp" in base or "gate_inp_shexp" in base:
        return "shared expert"
    if base.startswith("ffn_gate_inp"):
        return "router"
    if base.startswith("attn_") or base.startswith("indexer."):
        return "attention (+ indexer)"
    if base.startswith("ssm_"):
        return "linear-attention (SSM / GDN)"
    if base.startswith("hc_") or base.startswith("output_hc"):
        return "hyper-connections"
    if base.startswith("per_layer_token_embd"):
        return "per-layer embedding table (lookup)"
    if base.startswith("ple_"):
        return "per-layer embedding (PLE) weights"
    if base.startswith("token_embd"):
        return "token embedding"
    if base.startswith("output"):
        return "output head"
    if base.startswith("nextn") or "mtp" in base:
        return "MTP block"
    return "other"


def shard_paths(first):
    m = re.search(r"-(\d{5})-of-(\d{5})\.gguf$", first)
    if not m:
        return [first]
    n = int(m.group(2))
    return [first[:m.start()] + "-%05d-of-%05d.gguf" % (i, n) for i in range(1, n + 1)]


def model_summary(first_shard, reader_dir, S):
    paths = shard_paths(first_shard)
    heads = []
    for p in paths:
        if os.path.exists(p):
            heads.append((p, read_gguf(p, reader_dir)))
    meta = dict(heads[0][1]["metadata"])
    tensors = []
    for p, h in heads:
        for t in h["tensors"]:
            tensors.append(t + (p,))
    arch = meta.get("general.architecture", "?")
    roles = {}
    types_by_role = {}
    for name, shape, ty, p in tensors:
        r = tensor_role(name)
        e = nelem(shape)
        b = tbytes(shape, ty) or 0
        d = roles.setdefault(r, [0, 0, 0])
        d[0] += e
        d[1] += b
        d[2] += 1
        tb = types_by_role.setdefault(r, {})
        tb[ty] = tb.get(ty, 0) + 1
    # routed-expert type mix per projection, counted in layers
    proj = {}
    for name, shape, ty, p in tensors:
        m = re.match(r"blk\.(\d+)\.ffn_(gate|up|down|gate_up)_exps\.weight$", name)
        if m:
            proj.setdefault(m.group(2), {}).setdefault(ty, set()).add(int(m.group(1)))
    layer_kinds = {}
    for name, shape, ty, p in tensors:
        m = re.match(r"blk\.(\d+)\.(\w+?)[\._]", name)
        if m:
            layer_kinds.setdefault(int(m.group(1)), set()).add(name.split(".")[2])
    n_ssm = sum(1 for k in layer_kinds.values() if any(x.startswith("ssm") for x in k))
    n_full = sum(1 for k in layer_kinds.values() if "attn_k" in k or "attn_q" in k)
    shard_info = []
    for p, h in heads:
        exp_b = sum((tbytes(t[1], t[2]) or 0) for t in h["tensors"])
        shard_info.append({"path": p, "file_bytes": os.path.getsize(p), "tensor_bytes": exp_b,
                           "n_tensors": len(h["tensors"]), "reader": h["reader"]})
        S.add(p, None, "GGUF header (metadata + tensor table; weights not read)")
    tok = meta.get("tokenizer.ggml.tokens")
    return {"meta": meta, "arch": arch, "roles": roles, "types_by_role": types_by_role, "proj": proj,
            "n_layers_seen": len(layer_kinds), "n_ssm_layers": n_ssm, "n_full_attn_layers": n_full,
            "shards": shard_info, "vocab": len(tok) if isinstance(tok, list) else None,
            "reader": heads[0][1]["reader"], "n_tensors": len(tensors)}


# ======================================================================================================= sources
class Sources:
    """Every number in the pack points at an entry here: S<n> = file[:line,...] - what."""

    def __init__(self, disp):
        self.disp = disp
        self.items = []
        self.index = {}

    def add(self, path, lines=None, what=""):
        if isinstance(lines, int):
            lines = [lines]
        key = (os.path.abspath(path), tuple(lines) if lines else None)
        if key in self.index:
            i = self.index[key]
            if what and what not in self.items[i][2]:
                self.items[i] = (self.items[i][0], self.items[i][1], self.items[i][2] + "; " + what)
            return "S%d" % (i + 1)
        self.items.append((os.path.abspath(path), list(lines) if lines else None, what))
        self.index[key] = len(self.items) - 1
        return "S%d" % len(self.items)

    def ref(self, path, lines=None, what=""):
        return "[%s]" % self.add(path, lines, what)

    @staticmethod
    def fmt_lines(lines):
        if not lines:
            return ""
        ls = sorted(set(lines))
        out, a, b = [], ls[0], ls[0]
        for x in ls[1:]:
            if x == b + 1:
                b = x
                continue
            out.append(str(a) if a == b else "%d-%d" % (a, b))
            a = b = x
        out.append(str(a) if a == b else "%d-%d" % (a, b))
        return ":" + ",".join(out)

    def resolved(self, sid):
        p, lines, what = self.items[int(sid[1:]) - 1]
        return self.disp(p) + self.fmt_lines(lines)


class Facts:
    """Key numbers, printed with their resolved sources by `run --facts` (for the session report)."""

    def __init__(self):
        self.rows = []

    def add(self, name, value, sref):
        self.rows.append((name, value, sref))
        return value


def make_disp(roots):
    roots = sorted(((os.path.abspath(a).rstrip("/") + "/", b) for a, b in roots), key=lambda x: -len(x[0]))

    def disp(p):
        ap = os.path.abspath(p)
        for a, b in roots:
            if ap.startswith(a) or ap + "/" == a:
                return b + ap[len(a):]
        return "<outside the listed roots>/" + os.path.basename(ap)

    def clean(text):
        for a, b in roots:
            text = text.replace(a, b if b else "./")
            text = text.replace(a.rstrip("/"), (b.rstrip("/") or "."))
        text = re.sub(r"GPU-[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", "<GPU UUID removed>", text)
        text = re.sub(r"/home/[^\s,;)'\"]+", "<path removed>", text)
        return text

    return disp, clean


# ======================================================================================================= readers
def lines_of(path):
    with open(path, errors="replace") as f:
        return f.read().splitlines()


def expand(globs_, root):
    out = []
    for g in globs_:
        g2 = g if os.path.isabs(g) else os.path.join(root, g)
        hits = sorted(glob.glob(g2))
        out.extend(hits)
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def load_speed_set(spec, root):
    """Fixture (bp90-style) or screen (abarm-style) JSONL -> records with engine-clock numbers and their file:line."""
    recs = []
    for f in expand(spec["files"], root):
        for i, line in enumerate(lines_of(f), 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t = r.get("timings") or {}
            pn = t.get("prompt_n", r.get("prompt_n"))
            pms = t.get("prompt_ms", r.get("prompt_ms"))
            gn = t.get("predicted_n", r.get("predicted_n"))
            gms = t.get("predicted_ms", r.get("predicted_ms"))
            if pn is None or gn is None:
                continue
            recs.append({
                "set": spec["name"], "kind": spec.get("kind", "fixture"),
                "test": r.get("test") or r.get("id") or "?", "pass": r.get("pass", r.get("arm", "")),
                "prompt_n": pn, "prompt_ms": pms, "gen_n": gn, "gen_ms": gms,
                "cache_n": t.get("cache_n", r.get("cached", 0)) or 0,
                "draft_n": t.get("draft_n", r.get("draft_n")), "draft_acc": t.get("draft_n_accepted", r.get("draft_n_accepted")),
                "temp": (r.get("sampling") or {}).get("temperature", r.get("temperature")),
                "thinking": r.get("thinking"), "finish": r.get("finish"), "file": f, "line": i, "time": r.get("time") or r.get("t"),
            })
    return recs


def rate(n, ms):
    return 1000.0 * n / ms if ms else None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def group_records(recs):
    g = {}
    for r in recs:
        g.setdefault((r["set"], r["test"]), []).append(r)
    rows = []
    for (s, t), rs in g.items():
        pt = [rate(r["prompt_n"], r["prompt_ms"]) for r in rs]
        dt = [rate(r["gen_n"], r["gen_ms"]) for r in rs if r["gen_n"] and r["gen_n"] >= 2]
        acc = [r["draft_acc"] / r["draft_n"] for r in rs if r.get("draft_n")]
        rows.append({"set": s, "test": t, "n": len(rs), "prompt_n": med([r["prompt_n"] for r in rs]),
                     "gen_n": med([r["gen_n"] for r in rs]), "pt": med(pt), "pt_min": min([x for x in pt if x] or [0]),
                     "pt_max": max([x for x in pt if x] or [0]), "dt": med(dt), "dt_min": min(dt) if dt else None,
                     "dt_max": max(dt) if dt else None, "acc": med(acc), "temps": sorted({str(r["temp"]) for r in rs}),
                     "kind": rs[0]["kind"], "recs": rs, "cold": all((r["cache_n"] or 0) == 0 for r in rs)})
    return rows


# ---------------------------------------------------------------------------------------------- engine log (requests)
RX_PROMPT = re.compile(r"^strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+)(?: of \d+)? read in ([\d.]+) ms "
                       r"\(([\d.]+) tok/s\), (\d+) generated in ([\d.]+) ms \(([\d.]+) tok/s\), drafts accepted (\d+) of "
                       r"(\d+), (\d+) checkpoints(?: \(cancelled\))?(?:, (\d+) windows, ([\d.]+) drafts per window)?")
RX_HIT = re.compile(r"decode expert cache hit rate: [\d.]+% \((\d+) hits / (\d+) lookups\); (\d+) more read by the GPU "
                    r"over PCIe or from another GPU \([\d.]+% of all (\d+) routed\)")
RX_REMOTE = re.compile(r"^strata serve: CUDA(\d+): (\d+) expert entries")
RX_SFX = re.compile(r"^strata serve: suffix drafts: (\d+) windows, (\d+) of (\d+) drafts accepted")
RX_CUM = re.compile(r"cumulative draft length \(STRATA_DRAFT_CUM\): (\d+) MTP windows with drafts, ([\d.]+) drafts per "
                    r"MTP window")
RX_DEPTH = re.compile(r"spec depth: accepted/tested ((?:\d+/\d+\s*)+)")
RX_PCIE = re.compile(r"PCIe share: .*-> pcie_frac ([\d.]+) \(was")
RX_VWARN = re.compile(r"WARNING: only (\d+) MiB of VRAM free at the start of this request")
RX_TAIL = re.compile(r"route tail skip: (\d+) missed experts skipped")


def parse_requests(path, from_line=1, to_line=None):
    reqs, cur = [], None
    extra = {"pcie_frac": {}, "vram_warn": [], "starts": 0, "tail_skip_lines": 0, "first": None, "last": None,
             "pcie_lines": [], "vwarn_lines": []}
    with open(path, errors="replace") as f:
        for i, line in enumerate(f, 1):
            if i < from_line:
                continue
            if to_line and i > to_line:
                break
            if extra["first"] is None:
                extra["first"] = i
            extra["last"] = i
            if "engine started" in line:
                extra["starts"] += 1
                cur = None
                continue
            m = RX_PROMPT.search(line)
            if m:
                g = m.groups()
                cur = {"line": i, "prompt": int(g[0]), "reused": int(g[1]), "read": int(g[2]), "prompt_ms": float(g[3]),
                       "gen": int(g[5]), "gen_ms": float(g[6]), "acc": int(g[8]), "off": int(g[9]),
                       "windows": int(g[11]) if g[11] else None, "remote": 0, "sfx_w": 0, "sfx_ok": 0, "sfx_n": 0,
                       "cum_w": 0, "cum_d": 0.0, "depth": None}
                reqs.append(cur)
                continue
            if cur is None:
                m = RX_PCIE.search(line)
                if m:
                    extra["pcie_frac"][m.group(1)] = extra["pcie_frac"].get(m.group(1), 0) + 1
                    extra["pcie_lines"].append(i)
                m = RX_VWARN.search(line)
                if m:
                    extra["vram_warn"].append(int(m.group(1)))
                    extra["vwarn_lines"].append(i)
                continue
            m = RX_HIT.search(line)
            if m:
                cur.update(H=int(m.group(1)), L=int(m.group(2)), O=int(m.group(3)), R=int(m.group(4)))
                continue
            m = RX_REMOTE.search(line)
            if m:
                cur["remote"] += int(m.group(2))
                continue
            m = RX_SFX.search(line)
            if m:
                cur["sfx_w"], cur["sfx_ok"], cur["sfx_n"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
                continue
            m = RX_CUM.search(line)
            if m:
                cur["cum_w"], cur["cum_d"] = int(m.group(1)), float(m.group(2))
                continue
            m = RX_DEPTH.search(line)
            if m:
                cur["depth"] = [tuple(int(x) for x in p.split("/")) for p in m.group(1).split()]
                continue
            m = RX_PCIE.search(line)
            if m:
                extra["pcie_frac"][m.group(1)] = extra["pcie_frac"].get(m.group(1), 0) + 1
                extra["pcie_lines"].append(i)
                continue
            m = RX_VWARN.search(line)
            if m:
                extra["vram_warn"].append(int(m.group(1)))
                extra["vwarn_lines"].append(i)
                continue
            if RX_TAIL.search(line):
                extra["tail_skip_lines"] += 1
    return reqs, extra


def load_log_entry(lg, root):
    """An engine_logs / mtp_logs entry: {"path", "from_line", "to_line"} (one slice) or {"files": [globs]} (whole files)."""
    if "_data" in lg:
        return lg["_data"]
    if "path" in lg:
        files = [(lg["path"], lg.get("from_line", 1), lg.get("to_line"))]
    else:
        files = [(f, 1, None) for f in expand(lg["files"], root)]
    d = {"reqs": [], "ranges": [], "pcie": {}, "pcie_lines": [], "vwarn": [], "vwarn_lines": [], "tail": 0, "starts": 0}
    for f, a, b in files:
        reqs, ex = parse_requests(f, a, b)
        d["reqs"].extend(reqs)
        d["ranges"].append((f, ex["first"], ex["last"]))
        for k, v in ex["pcie_frac"].items():
            d["pcie"][k] = d["pcie"].get(k, 0) + v
        if ex["pcie_lines"]:
            d["pcie_lines"].append((f, ex["pcie_lines"]))
        d["vwarn"].extend(ex["vram_warn"])
        if ex["vwarn_lines"]:
            d["vwarn_lines"].append((f, ex["vwarn_lines"]))
        d["tail"] += ex["tail_skip_lines"]
        d["starts"] += ex["starts"]
    lg["_data"] = d
    return d


def placement(reqs, min_routed=0):
    rows = [r for r in reqs if "R" in r and r["R"] >= min_routed]
    H = sum(r["H"] for r in rows)
    C = sum(r["L"] - r["H"] for r in rows)
    N = sum(r["remote"] for r in rows)
    P = sum(r["O"] for r in rows) - N
    R = sum(r["R"] for r in rows)
    if not R:
        return None
    return {"requests": len(rows), "routed": R, "main": 100.0 * H / R, "helper": 100.0 * N / R, "pcie": 100.0 * P / R,
            "cpu": 100.0 * C / R, "gen": sum(r["gen"] for r in rows), "lines": [r["line"] for r in rows],
            "check": H + C + N + P - R}


def mtp_stats(reqs):
    rows = [r for r in reqs if r.get("windows")]
    if not rows:
        return None
    off = sum(r["off"] for r in rows)
    acc = sum(r["acc"] for r in rows)
    w = sum(r["windows"] for r in rows)
    sn = sum(r["sfx_n"] for r in rows)
    so = sum(r["sfx_ok"] for r in rows)
    sw = sum(r["sfx_w"] for r in rows)
    cw = sum(r["cum_w"] for r in rows)
    cd = sum(r["cum_w"] * r["cum_d"] for r in rows)
    gen = sum(r["gen"] for r in rows)
    depth = None
    ds = [r["depth"] for r in rows if r["depth"]]
    if ds:
        k = max(len(d) for d in ds)
        depth = []
        for j in range(k):
            a = sum(d[j][0] for d in ds if len(d) > j)
            t = sum(d[j][1] for d in ds if len(d) > j)
            depth.append((j + 1, a, t))
    return {"requests": len(rows), "offered": off, "accepted": acc, "windows": w, "sfx_offered": sn, "sfx_accepted": so,
            "sfx_windows": sw, "mtp_offered": off - sn, "mtp_accepted": acc - so, "mtp_windows_with_drafts": cw,
            "mtp_drafts": cd, "generated": gen, "depth": depth, "lines": [r["line"] for r in rows]}


# ---------------------------------------------------------------------------------------------- engine start lines
START_LINES = [
    ("engine_version", r"session is up \(engine ([\w.]+)\)", "engine's self-reported session version"),
    ("gpu0", r"GPU 0: (NVIDIA [^,]+), compute capability ([\d.]+)", "main GPU as the engine sees it"),
    ("guard", r"memory guard: limit ([\d.]+) GiB .*available ([\d.]+) GiB", "engine memory guard: limit / available at start"),
    ("cuda1_free", r"CUDA1 context ready, ([\d.]+) GiB free", "helper GPU free before its expert arena"),
    ("pcie_probe", r"PCIe probe: ([\d.]+) GB/s host->device.*-> pcie_frac ([\d.]+)", "PCIe probe and the start-up PCIe share"),
    ("dense_w", r"(\d+) MiB of weights loaded from", "dense weights from the native pack (MiB)"),
    ("proj_w", r"(\d+) native projection matrices, ([\d.]+) MiB of weights", "native projection matrices (count, MiB)"),
    ("profile", r"profile .*: (\d+) ranked pairs", "expert routing profile: ranked (layer, expert) pairs"),
    ("kv", r"KV streaming: (\d+) of (\d+) cells per QSA layer in VRAM, the K/V in ([\d.]+) GiB of pinned RAM",
     "KV cache: cells per attention layer in VRAM / total, K/V in pinned RAM (GiB)"),
    ("ple", r"PLE on, table (\d+) rows", "per-layer-embedding table rows (read from the second shard)"),
    ("mtp_layer", r"draft layer loaded, (\d+) MiB of VRAM \(experts (\d+), dense (\d+)\)", "MTP draft layer in VRAM (MiB: total, experts, dense)"),
    ("head", r"native Q\d_K head, (\d+) bytes", "output head as loaded (bytes)"),
    ("arena", r"loaded ([\d.]+) GiB at ([\d.]+) GiB/s", "expert arena loaded into pinned RAM (GiB, GiB/s)"),
    ("pool", r"CPU pool: (\d+) workers", "CPU expert-pool workers"),
    ("cache_auto", r"expert cache auto: ([\d.]+) GiB free, (\d+) MiB reserved", "main GPU free / reserve when sizing the expert cache"),
    ("cache", r"expert cache (\d+) slots, ([\d.]+) GiB of VRAM", "main GPU expert cache (slots, GiB)"),
    ("helper_cache", r"CUDA1: (\d+) additional experts, ([\d.]+) GiB", "helper GPU expert cache (experts, GiB)"),
    ("chunk", r"prompt chunk auto: (\d+) tokens", "prompt chunk"),
    ("borrow", r"the prompt path borrows (\d+) CUDA0 cache slots \(([\d.]+) GiB\)", "prompt path borrows main-cache slots (slots, GiB)"),
    ("window", r"verify: window up to (\d+) tokens", "verify window (tokens)"),
    ("draft_head", r"draft head over (\d+) tokens \(([\d.]+) MiB\)", "MTP draft head vocabulary (tokens, MiB)"),
    ("free_loaded", r"(\d+) MiB of VRAM free with everything loaded", "main GPU free with everything loaded (MiB)"),
    ("cum", r"cumulative draft length ON .*?threshold, ([\d.]+) falling to ([\d.]+)", "cumulative draft-length threshold (start, floor)"),
    ("cost_gate", r"cost-aware draft length ON \(.*: (\d+) bins", "cost gate table bins"),
]


def parse_start(path):
    found = {}
    for i, line in enumerate(lines_of(path), 1):
        for key, rx, what in START_LINES:
            if key in found:
                continue
            m = re.search(rx, line)
            if m:
                found[key] = (m.groups(), i, what)
    return found


# ---------------------------------------------------------------------------------------------- guard / monitor / summary
RX_GUARD = re.compile(r"srv-(\S+) exit=(\d+) (\d+)s (.*)$")


def parse_guard(paths):
    rows = []
    for p in paths:
        for i, line in enumerate(lines_of(p), 1):
            m = RX_GUARD.search(line)
            if not m:
                continue
            kv = {}
            for k, v, unit in re.findall(r"(\w+)=([\d.]+)(GiB|MiB)?", m.group(4)):
                kv[k] = (float(v), unit or "")
            rows.append({"label": m.group(1), "exit": int(m.group(2)), "secs": int(m.group(3)), "kv": kv,
                         "ok": m.group(4).strip().endswith("ok"), "file": p, "line": i})
    return rows


def parse_monitor(paths):
    out = []
    for p in paths:
        ls = lines_of(p)
        if not ls or not ls[0].startswith("t,"):
            continue
        hdr = ls[0].split(",")
        try:
            js, jm, jr = hdr.index("swapused_mib"), hdr.index("memavail_mib"), hdr.index("rss_mib")
        except ValueError:
            continue
        sw, ma, rs = [], [], []
        for line in ls[1:]:
            c = line.split(",")
            if len(c) != len(hdr):
                continue
            try:
                sw.append(int(c[js]))
                ma.append(int(c[jm]))
                rs.append(int(c[jr]))
            except ValueError:
                continue
        if not sw:
            continue
        ups = [b - a for a, b in zip(sw, sw[1:]) if b > a]
        downs = [a - b for a, b in zip(sw, sw[1:]) if b < a]
        out.append({"file": p, "samples": len(sw), "swap_first": sw[0], "swap_max": max(sw), "swap_last": sw[-1],
                    "swap_up_mib": sum(ups), "swap_up_steps": len(ups), "swap_down_mib": sum(downs),
                    "memavail_min": min(ma), "rss_max": max(rs), "lines": len(ls)})
    return out


def grep_lines(spec, root, clean):
    out = []
    for f in expand([spec["file"]], root):
        rx = re.compile(spec["pattern"])
        for i, line in enumerate(lines_of(f), 1):
            if rx.search(line):
                out.append((f, i, clean(line.strip())))
                if not spec.get("all"):
                    break
    return out


RX_T1 = re.compile(r"(\d+) requests, (\d+) windows: ([\d.]+) ms/window = GPU-reach ([\d.]+) \+ host ([\d.]+) \(plan "
                   r"([\d.]+), CPU ([\d.]+)\) \+ draft ([\d.]+) \+ tail ([-\d.]+); T ([\d.]+), ([\d.]+) tok/w")
RX_T2 = re.compile(r"per layer: GPU-reach ([\d.]+) us, CPU ([\d.]+) us, plan ([\d.]+) us; CPU experts ([\d.]+), PCIe "
                   r"([\d.]+), VRAM hits ([\d.]+) per layer-window")
RX_T3 = re.compile(r"helper: ([\d.]+) launches/window, host staging\+launching ([\d.]+) ms/window .*host waiting for it "
                   r"([\d.]+) ms/window")
RX_T4 = re.compile(r"GPU stages \(profiled windows\): serial stages ([\d.]+) ms/window, MoE branch incl\. the inline shared "
                   r"expert ([\d.]+) \(waitCPU ([\d.]+), hits ([\d.]+), PCIe groups ([\d.]+)\), head ([\d.]+)")
RX_TS = re.compile(r"^\s+([\d.]+)\s+(\w+ layers): (.+)$")


def parse_timing(path):
    d = {"stages": []}
    for i, line in enumerate(lines_of(path), 1):
        for key, rx in (("t1", RX_T1), ("t2", RX_T2), ("t3", RX_T3), ("t4", RX_T4)):
            m = rx.search(line)
            if m and key not in d:
                d[key] = ([float(x) for x in m.groups()], i)
        m = RX_TS.match(line)
        if m:
            d["stages"].append((float(m.group(1)), m.group(2), m.group(3).strip(), i))
    return d


# ---------------------------------------------------------------------------------------------- already-tried list
STATUSES = ("ADOPTED", "REJECTED", "PARKED", "NOT MEASURED", "DESK ONLY", "INFO")


def parse_tried(path, source_roots):
    sections, cur, problems = [], None, []
    for i, raw in enumerate(lines_of(path), 1):
        line = raw.strip()
        if not line or line.startswith("#") and not line.startswith("##"):
            continue
        if line.startswith("##"):
            cur = {"title": line.lstrip("#").strip(), "rows": []}
            sections.append(cur)
            continue
        parts = [p.strip() for p in line.split(" | ")]
        if len(parts) != 4:
            problems.append(f"line {i}: expected 4 fields 'STATUS | idea | result | sources', got {len(parts)}")
            continue
        st, idea, res, srcs = parts
        if st not in STATUSES:
            problems.append(f"line {i}: status '{st}' not one of {', '.join(STATUSES)}")
        checked = []
        for s in [x.strip() for x in srcs.split(";") if x.strip()]:
            m = re.match(r"^(.+?)(?::(\d+)(?:-(\d+))?)?$", s)
            rel, l1, l2 = m.group(1), m.group(2), m.group(3)
            absf = resolve_source(rel, source_roots)
            ok = absf is not None and os.path.isfile(absf)
            if not ok:
                problems.append(f"line {i}: source not found: {rel}")
            elif l1:
                n = sum(1 for _ in open(absf, errors="replace"))
                if int(l2 or l1) > n:
                    problems.append(f"line {i}: source line {l2 or l1} past the end of {rel} ({n} lines)")
            checked.append(s)
        if cur is None:
            cur = {"title": "Other", "rows": []}
            sections.append(cur)
        cur["rows"].append({"status": st, "idea": idea, "result": res, "sources": checked, "line": i})
    return sections, problems


def resolve_source(rel, source_roots):
    """'notes/x.md' or '../basalt-020/x' or a repo-relative path -> absolute path (source_roots: display prefix -> dir)."""
    for prefix, d in sorted(source_roots.items(), key=lambda x: -len(x[0])):
        if prefix and rel.startswith(prefix):
            return os.path.join(d, rel[len(prefix):])
    return os.path.join(source_roots.get("", "."), rel)


# ======================================================================================================= privacy scrub
def scrub_patterns(extra_words=()):
    pats = [
        ("home path", re.compile(r"/home/|/Users/|/root/|(?<![\w.])~/")),
        ("path leak (project folder or tool home)", re.compile(r"(?i)ai-speed-testing|\.claude/|\.dsh-deepseek")),
        ("UUID", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
        ("GPU UUID", re.compile(r"GPU-[0-9a-fA-F]{6}")),
        ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
        ("IP address (not 127.0.0.1)", re.compile(r"(?<![\w.])(?!127\.0\.0\.1(?![\w.]))(?<!v)(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")),
        ("API key / token", re.compile(r"\bsk-[A-Za-z0-9_-]{8,}|\btvly-[A-Za-z0-9_-]{8,}|\bhf_[A-Za-z0-9]{20,}|"
                                       r"\bgh[pousr]_[A-Za-z0-9]{20,}|\bAKIA[0-9A-Z]{16}\b|\bxox[abprs]-[A-Za-z0-9-]{8,}|"
                                       r"(?i:\b(?:api[_-]?key|bearer|authorization|x-api-key)\b\s*[:=])")),
        ("long mixed-case secret-like string", re.compile(
            r"\b(?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*[A-Z])(?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]{32,}\b")),
        ("owner's other tools", re.compile(r"\bJan\b|\bLDR\b|(?i:\bDS[ -]?Harness\b|\bOpenCode\b|deep[- ]research|"
                                           r"\bCodex\b|\bsearxng\b|\bntfy\b|\bdsh\b)")),
    ]
    words = set()
    for w in extra_words:
        if w and len(w) >= 3:
            words.add(w.lower())
    for w in sorted(words):
        pats.append(("username / hostname / private word", re.compile(re.escape(w), re.I)))
    return pats


def private_words(extra):
    ws = set(extra or [])
    try:
        ws.add(getpass.getuser())
    except Exception:
        pass
    try:
        ws.add(os.path.basename(pwd.getpwuid(os.getuid()).pw_dir))
    except Exception:
        pass
    for h in (socket.gethostname(), socket.getfqdn()):
        ws.add(h)
        ws.add(h.split(".")[0])
    try:
        ws.add(open("/etc/hostname").read().strip())
    except OSError:
        pass
    return [w for w in ws if w and w.lower() not in ("localhost", "localhost.localdomain")]


def scrub(text, words):
    findings = []
    pats = scrub_patterns(words)
    for n, line in enumerate(text.splitlines(), 1):
        for name, rx in pats:
            for m in rx.finditer(line):
                findings.append((name, n, m.start() + 1))
    return findings


# ======================================================================================================= helpers
def f1(x, nd=1):
    if x is None:
        return "-"
    return f"{x:,.{nd}f}"


def pct(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f} %"


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in r) + " |")
    return "\n".join(out)


def gib(b):
    return b / 2 ** 30


def describe_value(v, path_labels, disp):
    if isinstance(v, str) and v.startswith("/"):
        if v in path_labels:
            return path_labels[v]
        base = os.path.basename(v.rstrip("/"))
        return f"<{'folder' if os.path.isdir(v) else 'file'}: {base}>"
    return v


def parse_args_list(args):
    out, i = [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            out.append((a, args[i + 1]))
            i += 2
        else:
            out.append((a, ""))
            i += 1
    return out


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def find_line(path, pattern):
    rx = re.compile(pattern)
    for i, line in enumerate(lines_of(path), 1):
        if rx.search(line):
            return i
    return None


# ======================================================================================================= build
def build(inp, inputs_path):
    root = inp["root"]
    disp, clean = make_disp([tuple(x) for x in inp["display_roots"]])
    S = Sources(disp)
    F = Facts()
    ref = S.ref
    gaps = []          # release-day measurement list: (what, why)
    out = []
    w = out.append
    title = inp.get("title", "Profile pack")
    today = inp.get("date") or datetime.date.today().isoformat()
    sroots = dict(inp.get("source_roots", {"": root}))

    def cite(s):
        """Hand-written text may cite sources as [[src:PATH:LINE]] or [[src:PATH:A-B]] (PATH as in the already-tried list)."""
        def rep(m):
            p, a, b = m.group(1), m.group(2), m.group(3)
            absf = p if os.path.isabs(p) else resolve_source(p, sroots)
            if not os.path.isfile(absf):
                raise SystemExit(f"citation to a missing file: {p}")
            lines = list(range(int(a), int(b or a) + 1)) if a else None
            return ref(absf, lines, "cited in the text")
        return re.sub(r"\[\[src:([^\]:]+)(?::(\d+)(?:-(\d+))?)?\]\]", rep, s)

    def notes(key, src=None):
        for n in (src if src is not None else inp.get(key, [])):
            w("- " + cite(n))
        if (src if src is not None else inp.get(key)):
            w("")

    # ---------------------------------------------------------------- inputs
    cfg_path = inp["config"]
    cfg = json.load(open(cfg_path))
    eng = inp["engine_dir"]
    path_labels = inp.get("path_labels", {})
    hw = inp.get("hardware", {})
    model = model_summary(inp["model_first_shard"], inp.get("gguf_reader_dir"), S)
    sets = []
    for spec in inp["speed_sets"]:
        sets.extend(load_speed_set(spec, root))
    grouped = group_records(sets)
    set_label = {s["name"]: s.get("label", s["name"]) for s in inp["speed_sets"]}
    prim_f, prim_s = inp.get("primary_fixture_set"), inp.get("primary_screen_set")

    # ---------------------------------------------------------------- header
    w(f"# {title}")
    w("")
    w(f"Generated {today} by `profile_pack.py` {GEN_VERSION} from measurement files that already existed (nothing was "
      "run for this pack). Every number carries a source tag `[S<n>]`; Appendix A resolves each tag to a file and line "
      "(paths are relative to the project repository; `notes/` = the project's notes folder, `../` = a sibling project "
      "folder).")
    w("")
    if inp.get("intro"):
        w(cite(inp["intro"]))
        w("")
    glance = []                     # (what, value, refs) - rendered at GLANCE_AT once every section is built
    glance_at = len(out)

    # ---------------------------------------------------------------- 1 hardware
    w("## 1. Hardware and software")
    w("")
    hw_src = ref(*hw["source"]) if hw.get("source") else ""
    rows = []
    for k in ("main_gpu", "helper_gpu", "cpu", "ram", "storage"):
        if hw.get(k):
            rows.append((k.replace("_", " "), hw[k] + " " + hw_src))
    try:
        cpu_model = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
        rows.append(("cpu (this machine, /proc/cpuinfo)", cpu_model))
    except (OSError, StopIteration):
        pass
    try:
        mt = next(int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemTotal"))
        rows.append(("RAM visible to the OS (/proc/meminfo)", f"{mt / 2**20:.1f} GiB"))
    except (OSError, StopIteration):
        pass
    try:
        rows.append(("OS kernel", "Linux " + open("/proc/sys/kernel/osrelease").read().strip()))
    except OSError:
        pass
    libd = [os.path.basename(x.rstrip("/").replace("/lib64", "").replace("/bin", "")) for x in cfg.get("lib_dirs", [])]
    if libd:
        rows.append(("CUDA toolkit (the config's library folders)", ", ".join(sorted(set(libd))) + " " + ref(cfg_path, find_line(cfg_path, r'"lib_dirs"'), "config")))
    w(md_table(["", ""], rows))
    w("")

    # ---------------------------------------------------------------- 2 model
    meta, arch = model["meta"], model["arch"]
    sh0 = model["shards"][0]["path"]
    gref = ref(sh0, None, "GGUF header")
    w("## 2. The model")
    w("")
    w(f"Read from the GGUF header with {model['reader']} {gref}: {len(model['shards'])} shard(s), "
      f"{model['n_tensors']:,} tensors; no weights were read.")
    w("")
    rows = []
    for k in ("general.name", "general.description", "general.size_label", "general.quantized_by", "general.repo_url",
              "general.architecture", "general.file_type"):
        if k in meta:
            rows.append((k, meta[k]))
    rows.append(("vocabulary (tokenizer.ggml.tokens)", f"{model['vocab']:,}" if model["vocab"] else "-"))
    for k in ("tokenizer.ggml.model", "tokenizer.ggml.pre"):
        if k in meta:
            rows.append((k, meta[k]))
    for k in sorted(meta):
        if not k.startswith(arch + "."):
            continue
        v = meta[k]
        if isinstance(v, list):
            if len(v) <= 8:
                v = ", ".join(str(x) for x in v)
            else:
                vals = sorted(set(v)) if all(isinstance(x, (int, float)) for x in v) else []
                v = f"[{len(v)} values" + (f"; distinct: {', '.join(str(x) for x in vals[:6])}" if vals and len(vals) <= 6 else "") + "]"
        elif isinstance(v, float):
            v = f"{v:g}"
        rows.append((k[len(arch) + 1:], v))
    w(md_table(["header key", "value"], rows))
    w("")
    w(f"Layers seen in the tensor table: {model['n_layers_seen']}; with linear-attention (SSM / GDN) tensors: "
      f"{model['n_ssm_layers']}; with full-attention q/k tensors: {model['n_full_attn_layers']}. "
      "Sampling suggested by the header: "
      + ", ".join(f"{k.split('.')[-1]} {meta[k]:g}" if isinstance(meta[k], float) else f"{k.split('.')[-1]} {meta[k]}"
                  for k in ("general.sampling.temp", "general.sampling.top_p", "general.sampling.top_k") if k in meta) + f" {gref}.")
    w("")
    F.add("model layers / experts / experts per token",
          f"{meta.get(arch + '.block_count')} / {meta.get(arch + '.expert_count')} / {meta.get(arch + '.expert_used_count')}", gref)
    # parameters and quant by role
    roles = model["roles"]
    tot_e = sum(v[0] for v in roles.values())
    tot_b = sum(v[1] for v in roles.values())
    ne, nu = meta.get(arch + ".expert_count"), meta.get(arch + ".expert_used_count")
    lookups = ("token embedding", "per-layer embedding table (lookup)")
    routed = roles.get("routed experts", [0, 0, 0])[0]
    dense = sum(v[0] for k, v in roles.items() if k not in lookups and k != "routed experts")
    active = dense + (routed * nu / ne if ne and nu else 0)
    rows = []
    for r, (e, b, n) in sorted(roles.items(), key=lambda x: -x[1][1]):
        mix = ", ".join(f"{t} x{c}" for t, c in sorted(model["types_by_role"][r].items(), key=lambda x: -x[1]))
        rows.append((r, f"{e / 1e9:.2f} B", f"{gib(b):.2f}", f"{8 * b / e:.2f}" if e else "-", n, mix))
    rows.append(("**total**", f"**{tot_e / 1e9:.2f} B**", f"**{gib(tot_b):.2f}**", f"{8 * tot_b / tot_e:.2f}", sum(v[2] for v in roles.values()), ""))
    w("**Parameters and quantization by tensor role** (computed from the tensor table; GiB = the tensors' bytes) " + gref)
    w("")
    w(md_table(["role", "parameters", "GiB", "bits/weight", "tensors", "types (tensor count)"], rows))
    w("")
    w(f"Active per token: about **{active / 1e9:.2f} B** parameters = everything but the routed experts and the two "
      f"lookup tables ({dense / 1e9:.2f} B) + {nu} of {ne} routed experts per layer ({routed * nu / ne / 1e9:.2f} B); "
      "the token embedding and the per-layer embedding table are looked up one row per token. " + gref)
    w("")
    F.add("total / active parameters (B)", f"{tot_e / 1e9:.2f} / {active / 1e9:.2f}", gref)
    re_ = roles.get("routed experts", [0, 1, 0])
    glance.append(("model", f"{meta.get('general.name', '?')}: {meta.get(arch + '.block_count')} layers "
                   f"({model['n_ssm_layers']} linear-attention + {model['n_full_attn_layers']} full-attention), "
                   f"{ne} routed experts ({nu} per token) + a shared expert; {tot_e / 1e9:.1f} B parameters stored "
                   f"({routed / 1e9:.1f} B routed experts, {roles.get('per-layer embedding table (lookup)', [0])[0] / 1e9:.1f} B "
                   f"per-layer embedding table), about {active / 1e9:.1f} B active per token; routed experts at "
                   f"{8 * re_[1] / re_[0]:.2f} bits/weight ({gib(re_[1]):.2f} GiB)", gref))
    if model["proj"]:
        rows = []
        for pj in ("gate", "up", "gate_up", "down"):
            if pj in model["proj"]:
                rows.append((pj, ", ".join(f"{t} in {len(ls)} layer" + ("s" if len(ls) != 1 else "") for t, ls in sorted(model["proj"][pj].items(), key=lambda x: -len(x[1])))))
        w("Routed-expert quant mix per projection (the quant varies by layer): " + gref)
        w("")
        w(md_table(["projection", "types"], rows))
        w("")
    rows = [(os.path.basename(s["path"]), f"{s['file_bytes'] / 1e9:.2f} GB", f"{gib(s['tensor_bytes']):.2f} GiB", s["n_tensors"]) for s in model["shards"]]
    w(f"Shards {gref}:")
    w("")
    w(md_table(["shard", "file size", "tensor bytes", "tensors"], rows))
    w("")

    # ---------------------------------------------------------------- 3 engine + config
    w("## 3. Engine build and configuration")
    w("")
    src_f, sha_f = os.path.join(eng, "SOURCE"), os.path.join(eng, "SHA256")
    src_txt = clean(open(src_f).read().strip()) if os.path.exists(src_f) else "-"
    sha_txt = open(sha_f).read().split()[0] if os.path.exists(sha_f) else "-"
    exe = cfg["exe"]
    verified = None
    if inp.get("verify_engine_sha", True) and os.path.exists(exe) and sha_txt != "-":
        verified = sha256_file(exe) == sha_txt
    rows = [("engine source", f"{src_txt} {ref(src_f, 1, 'engine SOURCE')}"),
            ("engine binary sha256", f"`{sha_txt}` {ref(sha_f, 1, 'engine SHA256')}"
             + ("" if verified is None else (" (re-hashed for this pack: matches)" if verified else " (re-hashed: DOES NOT MATCH)")))]
    if inp.get("engine_label"):
        rows.insert(0, ("build label", inp["engine_label"]))
    start_log = inp.get("engine_start_log")
    st = parse_start(start_log) if start_log else {}
    if "engine_version" in st:
        rows.append(("engine's self-reported version", f"{st['engine_version'][0][0]} {ref(start_log, st['engine_version'][1])}"))
    if "gpu0" in st:
        rows.append(("main GPU (engine log)", f"{st['gpu0'][0][0]}, compute capability {st['gpu0'][0][1]} {ref(start_log, st['gpu0'][1])}"))
    w(md_table(["", ""], rows))
    w("")
    notes("engine_notes")
    cref = ref(cfg_path, None, "served config")
    w(f"**Engine arguments** (the served config {cref}; paths replaced by what they hold):")
    w("")
    arg_notes = inp.get("arg_notes", {})
    rows = []
    for a, v in parse_args_list(cfg["args"]):
        ln = find_line(cfg_path, r'^\s*"' + re.escape(a) + r'"')
        rows.append((f"`{a}`", f"`{describe_value(v, path_labels, disp)}`" if v else "", arg_notes.get(a, ""), f"l. {ln}" if ln else ""))
    w(md_table(["argument", "value", "what it does", f"line in {cref}"], rows))
    w("")
    env_notes = inp.get("env_notes", {})
    rows = []
    for k, v in cfg.get("env", {}).items():
        ln = find_line(cfg_path, r'^\s*"' + re.escape(k) + r'"\s*:')
        if k == "CUDA_VISIBLE_DEVICES":
            v = f"<{len(v.split(','))} GPUs by UUID; UUIDs removed>"
        else:
            v = describe_value(v, path_labels, disp)
            if isinstance(v, str) and len(v) > 60:
                v = v[:57] + "..."
        rows.append((f"`{k}`", f"`{v}`", env_notes.get(k, "(no note)"), f"l. {ln}" if ln else ""))
    w(f"**Environment switches** ({len(cfg.get('env', {}))} keys) {cref}:")
    w("")
    w(md_table(["switch", "value", "what it does / why", f"line in {cref}"], rows))
    w("")
    full_rows = cfg.get("env", {}).get("STRATA_MMVQ_IL_ROWS")
    if full_rows and len(full_rows) > 60:
        w(f"`STRATA_MMVQ_IL_ROWS` in full: `{full_rows}` {ref(cfg_path, find_line(cfg_path, 'STRATA_MMVQ_IL_ROWS'))}")
        w("")
    smp = cfg.get("sampling", {})
    w("**Sampling (served):** " + ", ".join(f"{k} {v}" for k, v in smp.items()) + " " + ref(cfg_path, find_line(cfg_path, r'"sampling"'))
      + (". " + cite(inp["sampling_note"]) if inp.get("sampling_note") else "."))
    w("")
    if inp.get("measurement_form_note"):
        w(cite(inp["measurement_form_note"]))
        w("")
    for extra in inp.get("compare_configs", []):
        c2 = json.load(open(extra["path"]))
        a1, a2 = set(cfg["args"]), set(c2["args"])
        e1, e2 = cfg.get("env", {}), c2.get("env", {})
        diffs = [f"args only in the served config: {sorted(a1 - a2) or 'none'}", f"args only in {extra['name']}: {sorted(a2 - a1) or 'none'}"]
        ed = {k: (e1.get(k), e2.get(k)) for k in sorted(set(e1) | set(e2)) if e1.get(k) != e2.get(k)}
        diffs.append("env differences (served, " + extra["name"] + "): " + (", ".join(f"{k} {a!r} vs {b!r}" for k, (a, b) in ed.items()) or "none"))
        w(f"- {extra['name']} ({extra.get('what', '')}) vs the served config {ref(extra['path'], None, extra['name'] + ' config')}: " + "; ".join(diffs) + ".")
    if inp.get("compare_configs"):
        w("")

    # ---------------------------------------------------------------- 4 speeds
    w("## 4. Speeds")
    w("")
    w(cite(inp.get("speed_note", "Engine clock (the engine's own prompt and decode timers), cold prompts (nothing reused), "
                                 "a fresh engine for each fixture test.")))
    w("")

    def rrefs(rs, what):
        byf = {}
        for r in rs:
            byf.setdefault(r["file"], []).append(r["line"])
        return " ".join(ref(f, ls, what) for f, ls in byf.items())

    def pick(pred, sets_):
        return [g for g in grouped if g["set"] in sets_ and pred(g)]

    head_rows = []
    ctx_targets = inp.get("context_targets", {"16K": 16384, "64K": 65536})
    tol = inp.get("context_tolerance", 0.15)
    min_dec = inp.get("min_decode_tokens", 256)
    # prompt, short
    shortp = pick(lambda g: g["kind"] == "screen" and g["cold"] and 512 <= (g["prompt_n"] or 0) <= 8192, [prim_s])
    for g in sorted(shortp, key=lambda g: g["prompt_n"]):
        head_rows.append(("prompt, short", f"{g['test']} ({g['prompt_n']:,.0f} tokens)", f"{f1(g['pt'])} [{f1(g['pt_min'])}-{f1(g['pt_max'])}]",
                          g["n"], g["set"], rrefs(g["recs"], "prompt speed")))
        F.add(f"prompt tok/s, {g['test']} ({g['prompt_n']:,.0f} tokens)", f1(g["pt"]), rrefs(g["recs"], ""))
    if not shortp:
        gaps.append(("Short-prompt reading speed", "no cold prompt of 512-8,192 tokens in the inputs"))
    for name, tgt in ctx_targets.items():
        ps = pick(lambda g, t=tgt: abs((g["prompt_n"] or 0) - t) / t <= tol, [prim_f])
        for g in ps:
            head_rows.append((f"prompt, {name}", f"{g['test']} ({g['prompt_n']:,.0f} tokens)", f"{f1(g['pt'])} [{f1(g['pt_min'])}-{f1(g['pt_max'])}]",
                              g["n"], g["set"], rrefs(g["recs"], "prompt speed")))
            F.add(f"prompt tok/s at {name} ({g['set']})", f1(g["pt"]), rrefs(g["recs"], ""))
        if not ps:
            gaps.append((f"Prompt reading at {name}", "no fixture within the context tolerance"))
    # decode, short
    shortd = pick(lambda g: (g["prompt_n"] or 0) <= 512 and (g["gen_n"] or 0) >= min_dec, [prim_s, prim_f])
    for g in sorted(shortd, key=lambda g: (g["kind"] != "screen", g["test"])):
        head_rows.append(("decode, short context", f"{g['test']} (prompt {g['prompt_n']:,.0f}, {g['gen_n']:,.0f} tokens, T {'/'.join(g['temps'])})",
                          f"{f1(g['dt'])} [{f1(g['dt_min'])}-{f1(g['dt_max'])}]", g["n"], g["set"], rrefs(g["recs"], "decode speed")))
        F.add(f"decode tok/s, {g['test']} ({g['set']})", f1(g["dt"]), rrefs(g["recs"], ""))
    for name, tgt in ctx_targets.items():
        ds = pick(lambda g, t=tgt: abs((g["prompt_n"] or 0) - t) / t <= tol and (g["gen_n"] or 0) >= min_dec, [prim_s, prim_f])
        if ds:
            for g in ds:
                head_rows.append((f"decode at {name}", f"{g['test']} (prompt {g['prompt_n']:,.0f}, {g['gen_n']:,.0f} tokens)", f"{f1(g['dt'])} [{f1(g['dt_min'])}-{f1(g['dt_max'])}]",
                                  g["n"], g["set"], rrefs(g["recs"], "decode speed")))
            continue
        import math
        cands = pick(lambda g: (g["gen_n"] or 0) >= min_dec and (g["prompt_n"] or 0) > 4096, [prim_s, prim_f])
        cands.sort(key=lambda g, t=tgt: abs(math.log(g["prompt_n"] / t)))
        near = cands[:1] + [g for g in cands[1:2] if abs(math.log(g["prompt_n"] / tgt)) <= 0.5]
        for g in near:
            head_rows.append((f"decode near {name} (APPROXIMATE)", f"{g['test']} (prompt {g['prompt_n']:,.0f}, {g['gen_n']:,.0f} tokens)",
                              f"{f1(g['dt'])} [{f1(g['dt_min'])}-{f1(g['dt_max'])}]", g["n"], g["set"], rrefs(g["recs"], "decode speed")))
            F.add(f"decode tok/s near {name}: {g['test']} (prompt {g['prompt_n']:,.0f})", f1(g["dt"]), rrefs(g["recs"], ""))
        tiny = pick(lambda g, t=tgt: abs((g["prompt_n"] or 0) - t) / t <= tol and 2 <= (g["gen_n"] or 0) < min_dec, [prim_f])
        for g in tiny:
            head_rows.append((f"decode at {name} (too few tokens to count)", f"{g['test']}: {g['gen_n']:,.0f} tokens after the prompt", f"{f1(g['dt'])}",
                              g["n"], g["set"], rrefs(g["recs"], "decode after the prompt fixture")))
        gaps.append((f"Decode speed at {name} context",
                     f"no decode of >= {min_dec} tokens after a ~{tgt:,}-token prompt in the inputs; the pack shows the nearest: "
                     + (", ".join(f"{g['test']} at {g['prompt_n']:,.0f}" for g in near) or "none")))
    w("**Headline speeds** (median over passes [min-max]; tok/s, engine clock):")
    w("")
    w(md_table(["what", "workload", "tok/s", "passes", "set", "src"], head_rows))
    w("")
    for kind in ("prompt", "decode"):
        parts, refs_ = [], []
        for r in head_rows:
            if r[0].startswith(kind) and "too few" not in r[0]:
                ctx = r[0].split(",", 1)[1].strip() if "," in r[0] else r[0][len(kind):].strip()
                parts.append(f"{ctx.replace(' (APPROXIMATE)', ' (approx.)')}: {r[1].split(' (')[0]} {r[2].split(' [')[0]}")
                refs_.append(r[5])
        if parts:
            glance.append((f"{kind} speed, tok/s (median of passes)", "; ".join(parts), " ".join(refs_)))
    # full per-workload table
    rows = []
    for g in sorted(grouped, key=lambda g: (g["set"], g["prompt_n"] or 0)):
        rows.append((g["set"], g["test"], f"{g['prompt_n']:,.0f}", f"{f1(g['pt'])} [{f1(g['pt_min'])}-{f1(g['pt_max'])}]",
                     f"{g['gen_n']:,.0f}", f"{f1(g['dt'])}" + (f" [{f1(g['dt_min'])}-{f1(g['dt_max'])}]" if g["dt"] is not None else ""),
                     pct(100 * g["acc"]) if g["acc"] is not None else "-", "/".join(g["temps"]), g["n"], rrefs(g["recs"], "speed record")))
    w("**Every workload in the inputs** (median [min-max] over passes; acceptance = drafts accepted / drafts offered, MTP and "
      "prompt-lookup drafts together):")
    w("")
    w(md_table(["set", "workload", "prompt tokens", "prompt tok/s", "generated", "decode tok/s", "draft acceptance", "temperature", "passes", "src"], rows))
    w("")
    w("Sets: " + "; ".join(f"**{s['name']}** = {s.get('label', '')}" for s in inp["speed_sets"]) + ".")
    w("")
    notes("speed_extra_notes")

    def quoted(key):
        for gl in inp.get(key, []):
            hits = grep_lines(gl, root, clean)
            if not hits:
                raise SystemExit(f"{key}: no line matches {gl['pattern']!r} in {gl['file']}")
            for f, i, txt in hits:
                w(f"- {gl.get('label', '')}: \"{txt}\" {ref(f, i, gl.get('label', ''))}")
        if inp.get(key):
            w("")

    quoted("speed_summary_lines")

    # ---------------------------------------------------------------- 5 placement
    w("## 5. Where the routed experts are served (decode)")
    w("")
    w("Per request the engine logs: `decode expert cache hit rate: X% (H hits / L lookups); O more read by the GPU over "
      "PCIe or from another GPU (p% of all R routed)` and, with a helper GPU, `CUDA1: N expert entries`. Counted per routed "
      "(token column x layer x expert) entry: **main GPU cache** = H; **helper GPU cache** = N; **PCIe share** (the main GPU "
      "reads the expert from pinned RAM over PCIe) = O - N; **CPU** (the CPU pool computes it) = L - H. The four add up to R. "
      "The parser is adapted from the project's earlier placement study.")
    w("")
    def lrefs(d, lab):
        return " ".join(ref(f, list(range(a, b + 1)), lab + " (per-request lines in this range)") for f, a, b in d["ranges"])

    rows = []
    for lg in inp.get("engine_logs", []):
        d_ = load_log_entry(lg, root)
        big = lg.get("big_routed", 200000)
        r_ = lrefs(d_, lg.get("label", "engine log"))
        for mr, lab in ((0, "all requests"), (big, f"requests with >= {big:,} routed entries")):
            pl = placement(d_["reqs"], mr)
            if not pl or (mr and lg.get("no_big")):
                continue
            rows.append((lg.get("label", ""), lab, f"{pl['requests']:,}", f"{pl['routed']:,}", pct(pl["main"]), pct(pl["helper"]),
                         pct(pl["pcie"]), pct(pl["cpu"]), r_))
            F.add(f"placement main/helper/PCIe/CPU ({lg.get('label', '')}, {lab})",
                  f"{pl['main']:.1f} / {pl['helper']:.1f} / {pl['pcie']:.1f} / {pl['cpu']:.1f} %", r_)
            if mr == 0 and not any(g_[0].startswith("routed experts served") for g_ in glance):
                glance.append(("routed experts served from (decode)", f"main GPU cache {pl['main']:.1f} %, helper GPU cache "
                               f"{pl['helper']:.1f} %, PCIe {pl['pcie']:.1f} %, CPU {pl['cpu']:.1f} % ({lg.get('label', '')}, "
                               f"{pl['requests']:,} requests)", r_))
    w(md_table(["log", "subset", "requests", "routed entries", "main GPU cache", "helper GPU cache", "PCIe share", "CPU", "src"], rows))
    w("")
    if "cache" in st and "helper_cache" in st:
        ne_ = meta.get(arch + ".expert_count") or 0
        nl_ = meta.get(arch + ".block_count") or 0
        if ne_ and nl_:
            tot = ne_ * nl_
            m1, m2 = int(st["cache"][0][0]), int(st["helper_cache"][0][0])
            w(f"Slots: the main GPU holds {m1:,} experts ({st['cache'][0][1]} GiB) {ref(start_log, st['cache'][1])} and the "
              f"helper {m2:,} ({st['helper_cache'][0][1]} GiB) {ref(start_log, st['helper_cache'][1])}, of {tot:,} routed experts "
              f"({nl_} layers x {ne_}) {gref}: {100 * m1 / tot:.1f} % + {100 * m2 / tot:.1f} % = {100 * (m1 + m2) / tot:.1f} % "
              "of the experts serve the shares above; the rest live in pinned RAM. The main cache is filled from a routing-frequency "
              "profile; an adaptive tier swaps experts in while decoding.")
            w("")
            F.add("expert slots main / helper / total experts", f"{m1:,} / {m2:,} / {tot:,}", ref(start_log, [st['cache'][1], st['helper_cache'][1]]))
    for lg in inp.get("engine_logs", []):
        d_ = lg.get("_data")
        if not lg.get("details"):
            continue
        if d_ and d_["pcie"]:
            tot_ = sum(d_["pcie"].values())
            w(f"- PCIe share setting: the engine re-prices it while serving (`PCIe share: ... -> pcie_frac X`), {tot_} times in "
              f"{lg.get('label', '')}: " + ", ".join(f"{k} x{v}" for k, v in sorted(d_["pcie"].items()))
              + " " + " ".join(ref(f, ls, "PCIe share re-pricing lines") for f, ls in d_["pcie_lines"]) + ".")
        if d_ and d_["tail"] == 0:
            w(f"- No `route tail skip` line in {lg.get('label', '')}: the lossy tail skip never acted {lrefs(d_, lg.get('label', ''))}.")
    w("")
    notes("placement_notes")
    quoted("placement_summary_lines")

    # ---------------------------------------------------------------- 6 MTP
    w("## 6. MTP speculative drafting")
    w("")
    if inp.get("mtp_note"):
        w(cite(inp["mtp_note"]))
        w("")
    rows = []
    depth_any = None
    for lg in inp.get("engine_logs", []) + inp.get("mtp_logs", []):
        if lg.get("no_mtp"):
            continue
        d_ = load_log_entry(lg, root)
        ms = mtp_stats(d_["reqs"])
        if not ms:
            continue
        r_ = lrefs(d_, lg.get("label") or "log")
        tpw = (ms["accepted"] + ms["windows"]) / ms["windows"]
        mtp_acc = ms["mtp_accepted"] / ms["mtp_offered"] if ms["mtp_offered"] else None
        rows.append((lg.get("label", ""), f"{ms['requests']:,}", f"{ms['windows']:,}", f"{ms['accepted']:,} / {ms['offered']:,} = {100 * ms['accepted'] / ms['offered']:.1f} %",
                     f"{ms['mtp_accepted']:,} / {ms['mtp_offered']:,} = {pct(100 * mtp_acc) if mtp_acc is not None else '-'}",
                     f"{ms['sfx_accepted']:,} / {ms['sfx_offered']:,} in {ms['sfx_windows']:,} windows",
                     f"{ms['mtp_drafts'] / ms['mtp_windows_with_drafts']:.2f}" if ms["mtp_windows_with_drafts"] else "-",
                     f"{tpw:.2f}", r_))
        F.add(f"tokens per verify window ({lg.get('label', '')})", f"{tpw:.2f}", r_)
        if mtp_acc is not None:
            F.add(f"MTP draft acceptance ({lg.get('label', '')})", f"{100 * mtp_acc:.1f} %", r_)
            if not any(g_[0].startswith("MTP drafting") for g_ in glance):
                glance.append(("MTP drafting", f"{100 * mtp_acc:.1f} % of MTP drafts accepted, {tpw:.2f} tokens per verify window "
                               f"({lg.get('label', '')}); per-position acceptance: "
                               + ("see section 6" if ms["depth"] else "not logged (section 6)"), r_))
        if ms["depth"]:
            depth_any = (lg, ms)
    w(md_table(["log", "requests", "verify windows", "all drafts accepted", "MTP drafts accepted", "prompt-lookup drafts accepted",
                "drafts per MTP window", "tokens per window", "src"], rows))
    w("")
    w("Tokens per window = (drafts accepted + windows) / windows: each verify window commits its accepted drafts plus one "
      "token of its own. MTP = all drafts minus the prompt-lookup (`suffix drafts`) lines.")
    w("")
    if depth_any:
        lg, ms = depth_any
        w("**Acceptance per draft position** (`STRATA_SPEC_DEPTH=1` lines; accepted / reached):")
        w("")
        w(md_table(["position", "accepted", "reached", "acceptance"], [(d, f"{a:,}", f"{t:,}", pct(100 * a / t) if t else "-") for d, a, t in ms["depth"]]))
        w("")
    else:
        w("**Acceptance per draft position: not in these logs.** The Qwen engine prints it only with `STRATA_SPEC_DEPTH=1` "
          "(serve mode, positions 1-5, accepted / tested), and no existing run had it on. What exists: the per-request totals "
          "above and the decode-timing pass's mean window width (section 8).")
        gaps.append(("MTP acceptance per draft position", "no log has STRATA_SPEC_DEPTH=1 lines; only per-request totals exist"))
        w("")
    notes("mtp_extra_notes")
    quoted("mtp_summary_lines")

    # ---------------------------------------------------------------- 7 memory
    w("## 7. Memory: RAM, VRAM and swap")
    w("")
    if st:
        rows = []
        sref = ref(start_log, None, "engine start lines of one start of the measured form")

        def nf(x):
            try:
                v = float(x)
            except ValueError:
                return x
            return f"{int(v):,}" if v.is_integer() and abs(v) >= 10000 else x

        for key, rx, what in START_LINES:
            if key in st and key not in ("engine_version", "gpu0"):
                rows.append((what, ", ".join(nf(x) for x in st[key][0]), f"l. {st[key][1]}"))
        w(f"**At engine start** (one start of the measured form {sref}):")
        w("")
        w(md_table(["what", "value", f"line in {sref}"], rows))
        w("")
    gl = expand(inp.get("guard_logs", []), root)
    grows = parse_guard(gl)
    if grows:
        keys = []
        for r in grows:
            for k in r["kv"]:
                if k not in keys:
                    keys.append(k)
        rows = []
        for r in grows:
            rows.append([r["label"], f"{r['secs']}"] + [f"{r['kv'][k][0]:g} {r['kv'][k][1]}" if k in r["kv"] else "-" for k in keys]
                        + ["ok" if r["ok"] else "NOT OK", ref(r["file"], r["line"], "server guard summary line")])
        w("**Per run, from the server guard's summary line** (whole process tree; GPU free memory from nvidia-smi):")
        w("")
        w(md_table(["run", "s"] + keys + ["guard", "src"], rows))
        w("")
        mm = {}
        for k in keys:
            vals = [r["kv"][k][0] for r in grows if k in r["kv"]]
            if vals:
                lo, hi = min(vals), max(vals)
                mm[k] = (lo, hi, grows[0]["kv"][k][1])
                F.add(f"guard {k} over {len(vals)} runs (min..max)", f"{lo:g}..{hi:g} {grows[0]['kv'][k][1]}", " ".join(ref(r["file"], r["line"]) for r in grows))
        parts = []
        labels = inp.get("guard_key_labels", {})
        for k, v in mm.items():
            lab = labels.get(k, k)
            if k.startswith("max_"):
                parts.append(f"{lab} up to {v[1]:g} {v[2]}")
            elif k.startswith("min_"):
                parts.append(f"{lab} never below {v[0]:g} {v[2]}")
        glance.append((f"memory over {len(grows)} measured runs (guard lines)", "; ".join(parts),
                       " ".join(ref(r["file"], r["line"]) for r in grows)))
    mons = parse_monitor(expand(inp.get("monitor_sys_csv", []), root))
    if mons:
        rows = []
        for m in mons:
            rows.append((os.path.basename(m["file"]).replace(".sys.csv", ""), m["samples"], f"{m['memavail_min'] / 1024:.1f}",
                         f"{m['rss_max'] / 1024:.1f}", f"{m['swap_first']} -> {m['swap_max']} -> {m['swap_last']}",
                         f"{m['swap_up_mib']} MiB in {m['swap_up_steps']} steps", ref(m["file"], list(range(2, m["lines"] + 1)), "1-s monitor samples")))
        w("**Swap during each run** (1-second system samples from the run's monitor; MiB of swap in use: first -> max -> last):")
        w("")
        w(md_table(["run", "samples", "min MemAvailable GiB", "max engine RSS GiB", "swap used MiB", "swap growth", "src"], rows))
        w("")
        grow = sum(m["swap_up_mib"] for m in mons)
        mref = " ".join(ref(m["file"], list(range(2, m["lines"] + 1))) for m in mons)
        F.add(f"swap growth inside {len(mons)} measured runs", f"{grow} MiB", mref)
        glance.append(("swap", f"{grow} MiB of swap growth inside {len(mons)} measured runs (1-s samples)", mref))
        gaps.append(("The engine's own swap (VmSwap) per run", "the monitors record system swap only; the owner's swap rule is about the engine's VmSwap"))
    quoted("memory_summary_lines")
    for lg in inp.get("engine_logs", []):
        d_ = lg.get("_data")
        if d_ and d_["vwarn"] and lg.get("details"):
            w(f"- The engine warned {len(d_['vwarn'])} times in the {lg.get('label', '')} that the main GPU "
              f"had under 512 MiB free at a request's start (lowest {min(d_['vwarn'])} MiB) "
              + " ".join(ref(f, ls, "low-VRAM warnings") for f, ls in d_["vwarn_lines"])
              + ": the cache is sized to leave only the configured reserve.")
    w("")
    notes("memory_notes")

    # ---------------------------------------------------------------- 8 timing
    w("## 8. Where a decode window's time goes (the slowest step)")
    w("")
    td = inp.get("decode_timing", {})
    if td.get("report") and os.path.exists(td["report"]):
        T = parse_timing(td["report"])
        rp = td["report"]
        if "t1" in T:
            v, ln = T["t1"]
            req, win, ms, reach, host, plan, cpu, draft, tail, Tw, tok = v
            r1 = ref(rp, ln, "decode timing: window split")
            parts = [("GPU-reach wait (dense layers + the GPU's own MoE branch, host-measured)", reach),
                     ("CPU pool (missed experts) inside the host's per-layer work", cpu),
                     ("host plan + other per-layer host work", host - cpu), ("MTP drafting between windows", draft),
                     ("tail (head, sampling, launch)", tail)]
            rows = [(n_, f"{x:.2f}", pct(100 * x / ms)) for n_, x in parts]
            rows.append(("**window**", f"**{ms:.2f}**", "100 %"))
            w(f"{int(req)} requests, {int(win):,} windows {r1}; window width {Tw:.2f} columns, {tok:.2f} tokens per window = "
              f"{ms / tok:.2f} ms per token ({1000 * tok / ms:.0f} tok/s inside the windows).")
            w("")
            w(md_table(["part of a window", "ms", "share"], rows))
            w("")
            slow = max(parts, key=lambda x: x[1])
            w(f"**Slowest step: {slow[0]}, {slow[1]:.2f} of {ms:.2f} ms ({100 * slow[1] / ms:.0f} %)** {r1}.")
            F.add("decode window ms / slowest part", f"{ms:.2f} / {slow[0]} {slow[1]:.2f}", r1)
            glance.append(("decode window (verify step)", f"{ms:.2f} ms for {tok:.2f} tokens; slowest part: {slow[0]} "
                           f"{slow[1]:.2f} ms ({100 * slow[1] / ms:.0f} %); the GPU-reach wait {reach:.2f} ms is close behind", r1))
            F.add("tokens per window (decode-timing pass)", f"{tok:.2f} (width {Tw:.2f})", r1)
            if "t2" in T:
                v2, ln2 = T["t2"]
                w(f"Per layer-window: GPU-reach {v2[0]:.1f} us, CPU {v2[1]:.1f} us, plan {v2[2]:.2f} us; distinct CPU experts "
                  f"{v2[3]:.2f}, PCIe experts {v2[4]:.2f}, VRAM hit entries {v2[5]:.1f} {ref(rp, ln2)}.")
            if "t3" in T:
                v3, ln3 = T["t3"]
                w(f"Helper GPU: {v3[0]:.1f} launches per window; the host spends {v3[1]:.3f} ms per window staging and launching "
                  f"them and {v3[2]:.3f} ms waiting for them {ref(rp, ln3)}.")
            if "t4" in T:
                v4, ln4 = T["t4"]
                w(f"GPU stage table (profiled windows): serial stages {v4[0]:.2f} ms per window, MoE branch with the inline "
                  f"shared expert {v4[1]:.2f} (of it waiting for the CPU rows {v4[2]:.2f}, VRAM hits {v4[3]:.2f}, PCIe groups "
                  f"{v4[4]:.2f}), head {v4[5]:.2f} {ref(rp, ln4)}.")
            w("")
        if T["stages"]:
            w("Largest GPU stages (ms per window):")
            w("")
            sr_ = ref(rp, [x[3] for x in T["stages"]], "GPU stage table")
            w(md_table(["ms/window", "layer kind", "stage", f"line in {sr_}"], [(f"{a:.2f}", b, c, f"l. {ln}") for a, b, c, ln in T["stages"]]))
            w("")
        if td.get("config"):
            c2 = json.load(open(td["config"]))
            e1, e2 = cfg.get("env", {}), c2.get("env", {})
            add = sorted(k for k in e2 if k not in e1)
            miss = sorted(k for k in e1 if k not in e2)
            w(f"The timing pass ran {ref(td['config'], None, 'timing config')} = the served form with the timing switches "
              f"{', '.join(add) or 'none'} and without {', '.join(miss) or 'nothing'}"
              + (" (and the picture reader off)" if "--vision" in cfg["args"] and "--vision" not in c2["args"] else "") + ".")
            if miss:
                gaps.append(("Decode-timing split on the served form", f"the timing pass lacks {', '.join(miss)}"))
        w("")
        notes(None, td.get("notes", []))
        quoted("timing_summary_lines")
    else:
        w("No decode-timing report in the inputs.")
        gaps.append(("Per-window time breakdown", "no decode-timing report given"))
        w("")

    # ---------------------------------------------------------------- 9 already tried
    w("## 9. Already tried on this model")
    w("")
    tried_path = inp.get("already_tried")
    tried_problems = []
    if tried_path:
        secs, tried_problems = parse_tried(tried_path, sroots)
        w(cite(inp.get("tried_intro", "One line per idea: status, the measured result, and where it was measured. "
                                 "ADOPTED = in the served config; REJECTED = measured and dropped; PARKED = measured or built, "
                                 "waiting; NOT MEASURED / DESK ONLY = estimate or reading only.")) + f" (List: {disp(tried_path)}.)")
        w("")
        counts = {}
        for s in secs:
            rows = []
            for r in s["rows"]:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
                refs_ = []
                for s_ in r["sources"]:
                    m = re.match(r"^(.+?)(?::(\d+)(?:-(\d+))?)?$", s_)
                    absf = resolve_source(m.group(1), sroots)
                    lines = list(range(int(m.group(2)), int(m.group(3) or m.group(2)) + 1)) if m.group(2) else None
                    refs_.append(ref(absf, lines, "already-tried source"))
                rows.append((f"**{r['status']}**", r["idea"], r["result"], " ".join(refs_)))
            w(f"### {s['title']}")
            w("")
            w(md_table(["status", "idea", "measured result", "src"], rows))
            w("")
        w("Totals: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + ".")
        w("")

    # ---------------------------------------------------------------- 10 release-day list
    w("## 10. What these files only approximate (measure on release day)")
    w("")
    seen = set()
    items = []
    for what, why in gaps:
        if what not in seen:
            seen.add(what)
            items.append((what, why))
    for what, why in inp.get("release_day_static", []):
        if what not in seen:
            seen.add(what)
            items.append((what, why))
    for i, (what, why) in enumerate(items, 1):
        w(f"{i}. **{what}** - {why}.")
    w("")

    # ---------------------------------------------------------------- at a glance (inserted after the intro)
    if glance:
        g_lines = ["## At a glance", "", md_table(["", "", "src"], glance), "",
                   f"Approximations (see section 10): {len(items)} measurements here stand in for ones release day takes directly.", ""]
        out[glance_at:glance_at] = g_lines

    # ---------------------------------------------------------------- appendices
    w("## Appendix A. Sources")
    w("")
    for i, (p, lines, what) in enumerate(S.items, 1):
        w(f"- **S{i}** `{disp(p)}{S.fmt_lines(lines)}`" + (f" - {what}" if what else ""))
    w("")
    w("## Appendix B. How this pack was made")
    w("")
    w(f"- Generator `profile_pack.py` {GEN_VERSION}; inputs `{disp(inputs_path)}`; GGUF header read with {model['reader']}.")
    w("- Read-only: configs, engine SOURCE / SHA256, GGUF headers, JSONL speed records, engine logs, server guard lines, "
      "1-second monitor CSVs, the decode-timing report, the project's notes. Nothing on the GPU.")
    w("- Privacy scrub before writing: no username, home path, hostname, IP other than 127.0.0.1, UUID, email, API key or "
      "token, or the owner's other tools; the generator refuses to write otherwise.")
    if tried_problems:
        w("- Already-tried list problems: " + "; ".join(tried_problems))
    w("")
    text = compact_refs(clean("\n".join(out))) + "\n"
    return text, S, F, items, tried_problems


def compact_refs(text):
    """'[S16] [S17] [S18]' -> '[S16-S18]' (runs of 3 or more consecutive tags; Appendix A still lists each one)."""
    def rep(m):
        ids = [int(x) for x in re.findall(r"\[S(\d+)\]", m.group(0))]
        out, i = [], 0
        while i < len(ids):
            j = i
            while j + 1 < len(ids) and ids[j + 1] == ids[j] + 1:
                j += 1
            out.append(f"[S{ids[i]}-S{ids[j]}]" if j - i >= 2 else " ".join(f"[S{x}]" for x in ids[i:j + 1]))
            i = j + 1
        return " ".join(out)
    return re.sub(r"\[S\d+\](?: \[S\d+\])+", rep, text)


def run(args):
    inp = json.load(open(args.inputs))
    text, S, F, items, problems = build(inp, os.path.abspath(args.inputs))
    words = private_words(inp.get("private_words", []))
    findings = scrub(text, words)
    if findings:
        print(f"REFUSED: the privacy scrub found {len(findings)} match(es); nothing written:", file=sys.stderr)
        for name, ln, col in findings[:60]:
            print(f"  {name}: line {ln}, column {col}", file=sys.stderr)
        return 3
    if problems and inp.get("strict_sources", True):
        print("REFUSED: the already-tried list has source problems:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 4
    out = args.out or inp["output"]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, out)
    rd = inp.get("release_day_list_out")
    if rd:
        with open(rd + ".tmp", "w") as f:
            f.write(f"# Release-day measurements that the profile pack built from {os.path.basename(args.inputs)} only approximates (profile_pack.py {GEN_VERSION})\n")
            for i, (what, why) in enumerate(items, 1):
                f.write(f"{i}. {what} - {why}\n")
        os.replace(rd + ".tmp", rd)
    print(f"wrote {out}: {len(text.splitlines())} lines, {len(S.items)} sources, scrub clean")
    if args.facts:
        for name, value, sref in F.rows:
            ids = re.findall(r"S\d+", sref)
            print(f"FACT {name} = {value} <- " + "; ".join(S.resolved(i) for i in ids))
        print("RELEASE-DAY:")
        for i, (what, why) in enumerate(items, 1):
            print(f"  {i}. {what} - {why}")
    return 0


# ======================================================================================================= selftest
def _w_gguf(path, meta, tensors):
    def s(x):
        b = x.encode()
        return struct.pack("<Q", len(b)) + b

    out = bytearray(struct.pack("<IIQQ", 0x46554747, 3, len(tensors), len(meta)))
    for k, v in meta.items():
        out += s(k)
        if isinstance(v, str):
            out += struct.pack("<I", 8) + s(v)
        elif isinstance(v, float):
            out += struct.pack("<If", 6, v)
        elif isinstance(v, list) and v and isinstance(v[0], str):
            out += struct.pack("<IIQ", 9, 8, len(v)) + b"".join(s(x) for x in v)
        elif isinstance(v, list):
            out += struct.pack("<IIQ", 9, 4, len(v)) + struct.pack("<%dI" % len(v), *v)
        else:
            out += struct.pack("<II", 4, v)
    tid = {v: k for k, v in GGML_TYPES.items()}
    off = 0
    for name, shape, ty in tensors:
        out += s(name) + struct.pack("<I", len(shape)) + struct.pack("<%dQ" % len(shape), *shape) + struct.pack("<IQ", tid[ty], off)
        off += tbytes(shape, ty) or 0
    with open(path, "wb") as f:
        f.write(out)


def selftest(_args):
    import tempfile
    base = os.path.join(HERE, "scratch")
    os.makedirs(base, exist_ok=True)
    d = tempfile.mkdtemp(prefix="selftest-", dir=base)
    fails = []

    def check(name, cond):
        print(("ok   " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    # --- a tiny 2-layer, 8-expert model in two shards
    meta = {"general.architecture": "toyexp", "general.name": "Toy MoE", "general.sampling.temp": 1.0,
            "toyexp.block_count": 2, "toyexp.embedding_length": 256, "toyexp.expert_count": 8, "toyexp.expert_used_count": 2,
            "toyexp.full_attention_interval": 2, "toyexp.ssm.state_size": 16, "toyexp.attention.compress_ratios": [0, 4],
            "tokenizer.ggml.tokens": ["a", "b", "c"], "split.count": 2}
    t = []
    for L in range(2):
        t += [(f"blk.{L}.ffn_gate_exps.weight", [256, 64, 8], "IQ3_S" if L == 0 else "IQ2_S"),
              (f"blk.{L}.ffn_up_exps.weight", [256, 64, 8], "IQ3_S" if L == 0 else "IQ2_S"),
              (f"blk.{L}.ffn_down_exps.weight", [64, 256, 8], "IQ4_NL"),
              (f"blk.{L}.ffn_gate_inp.weight", [256, 8], "BF16"), (f"blk.{L}.attn_norm.weight", [256], "F32")]
    t.append((f"blk.0.ssm_a", [16], "F32"))
    t.append((f"blk.1.attn_k.weight", [256, 256], "Q6_K"))
    t.append(("token_embd.weight", [256, 3], "F32"))
    g1, g2 = os.path.join(d, "toy-00001-of-00002.gguf"), os.path.join(d, "toy-00002-of-00002.gguf")
    _w_gguf(g1, meta, t)
    _w_gguf(g2, {"split.count": 2}, [("per_layer_token_embd.weight", [32, 1024], "IQ4_NL")])
    h = _gguf_builtin(g1)
    check("built-in GGUF reader: metadata and tensors", h["metadata"]["toyexp.expert_count"] == 8 and len(h["tensors"]) == len(t))
    tree = "/home/USER/ai-speed-testing/strata-compare/strata-v0213stock/tools"
    if os.path.exists(os.path.join(tree, "gguf_reader.py")):
        h2 = _gguf_tree(g1, tree)
        check("the tree's gguf_reader agrees with the built-in reader", h2["metadata"] == h["metadata"] and h2["tensors"] == h["tensors"])
    # --- engine, config
    eng = os.path.join(d, "engine")
    os.makedirs(eng)
    exe = os.path.join(eng, "strata")
    open(exe, "wb").write(b"toy engine")
    open(os.path.join(eng, "SOURCE"), "w").write("v9.9.9 + 3 commits (branch toy abc123)\n")
    open(os.path.join(eng, "SHA256"), "w").write(sha256_file(exe) + "  engine/strata\n")
    cfg = {"exe": exe, "args": ["--native", g1, "--spec", "7", "--expert-cache", "auto", "--vision"],
           "env": {"STRATA_X": "1", "CUDA_VISIBLE_DEVICES": "GPU-UUID"},
           "sampling": {"temperature": 1.0, "top_p": 0.95}, "lib_dirs": ["/usr/local/cuda-13.3/lib64"]}
    cp = os.path.join(d, "cfg.json")
    json.dump(cfg, open(cp, "w"), indent=1)
    cfg2 = dict(cfg, args=cfg["args"][:-1], env=dict(cfg["env"], STRATA_DECODE_TIMING="1"))
    cp2 = os.path.join(d, "cfg-timing.json")
    json.dump(cfg2, open(cp2, "w"), indent=1)
    # --- speed records
    fx = os.path.join(d, "F-pp16k-1.jsonl")
    open(fx, "w").write(json.dumps({"test": "pp16k", "pass": 1, "prompt_n": 16000, "prompt_ms": 4000.0, "predicted_n": 30,
                                    "predicted_ms": 300.0, "draft_n": 20, "draft_n_accepted": 10, "temperature": 1.0}) + "\n")
    fx2 = os.path.join(d, "F-pp64k-1.jsonl")
    open(fx2, "w").write(json.dumps({"test": "pp64k", "pass": 1, "prompt_n": 66000, "prompt_ms": 15000.0, "predicted_n": 1,
                                     "predicted_ms": 18.0, "temperature": 1.0}) + "\n")
    fx3 = os.path.join(d, "F-decode-1.jsonl")
    open(fx3, "w").write(json.dumps({"test": "conv", "pass": 1, "prompt_n": 38, "prompt_ms": 300.0, "predicted_n": 1000,
                                     "predicted_ms": 7000.0, "draft_n": 1000, "draft_n_accepted": 600, "temperature": 0.6}) + "\n")
    sc = os.path.join(d, "S1n.jsonl")
    with open(sc, "w") as f:
        for i_, (pn, gn) in enumerate(((110, 3072), (2600, 170), (24000, 3800))):
            f.write(json.dumps({"id": f"W{i_}", "rep": 0, "sampling": {"temperature": 1.0},
                                "timings": {"cache_n": 0, "prompt_n": pn, "prompt_ms": pn / 3.0, "predicted_n": gn,
                                            "predicted_ms": gn * 6.0, "draft_n": gn, "draft_n_accepted": gn // 2}}) + "\n")
    # --- engine log: 2 requests with helper, suffix, cum, a PCIe re-price
    el = os.path.join(d, "engine.log")
    open(el, "w").write("\n".join([
        "[strata] 2026-11-09 08:00:00 engine started: " + exe,
        "strata generate: GPU 0: NVIDIA GeForce RTX 5080, compute capability 12.0",
        "strata generate: expert cache 4585 slots, 8.75 GiB of VRAM; policy is",
        "strata generate: CUDA1: 3300 additional experts, 6.21 GiB; results return",
        "strata generate: session is up (engine 0.1.54)",
        "strata serve: 522 MiB of VRAM free with everything loaded",
        "strata serve: prompt 100 tokens = 0 reused + 100 read in 100 ms (1000.0 tok/s), 107 generated in 1000 ms (107.0 tok/s), drafts accepted 60 of 80, 1 checkpoints, 50 windows, 1.60 drafts per window",
        "strata serve: cumulative draft length (STRATA_DRAFT_CUM): 40 MTP windows with drafts, 1.75 drafts per MTP window; threshold 0.3 at the end (started at 0.371)",
        "strata serve: decode expert cache hit rate: 80.0% (800 hits / 1000 lookups); 400 more read by the GPU over PCIe or from another GPU (28.6% of all 1400 routed)",
        "strata serve: suffix drafts: 10 windows, 5 of 10 drafts accepted",
        "strata serve: CUDA1: 300 expert entries, 10 active layer launches, 1.0 MiB returned",
        "strata serve: PCIe share: the CPU pool takes 51 us per missed expert, the link 57.8 GB/s -> pcie_frac 0.45 (was 0.55; x)",
        "strata serve: WARNING: only 504 MiB of VRAM free at the start of this request (below 512 MiB)",
        "strata serve: prompt 50 tokens = 0 reused + 50 read in 50 ms (1000.0 tok/s), 300000 generated in 1000 ms (1.0 tok/s), drafts accepted 0 of 0, 1 checkpoints, 1 windows, 0.00 drafts per window",
        "strata serve: decode expert cache hit rate: 50.0% (100000 hits / 200000 lookups); 100000 more read by the GPU over PCIe or from another GPU (33.3% of all 300000 routed)",
        "strata serve: spec depth: accepted/tested 9/10 8/9 7/8 6/7 5/6",
    ]) + "\n")
    tr = os.path.join(d, "report.txt")
    open(tr, "w").write("11 requests, 5208 windows: 23.17 ms/window = GPU-reach 9.60 + host 10.41 (plan 0.64, CPU 9.67) + draft 2.35 + tail 0.77; T 4.55, 3.64 tok/w\n"
                        "  per layer: GPU-reach 199.9 us, CPU 201.6 us, plan 13.33 us; CPU experts 4.91, PCIe 2.37, VRAM hits 28.5 per layer-window\n"
                        "      5.08  GDN layers: waitB\n")
    gd = os.path.join(d, "server_x.log")
    open(gd, "w").write("2026-11-09T08:15:43 srv-x-pp64k-1 exit=0 61s min_MemAvailable=34.2GiB@29s min_5080_free=499MiB@29s max_tree_RSS=51.5GiB max_swap_used=2.87GiB min_4060Ti_free=1287MiB ok\n")
    mon = os.path.join(d, "monitor-x.sys.csv")
    open(mon, "w").write("t,pid,rss_mib,memavail_mib,cached_mib,swapused_mib,proc_read_mib,nvme_read_mib,cpu_busy_pct\n"
                         "1.0,1,100,90000,1,2940,0,0,1\n2.0,1,50000,40000,1,2950,0,0,1\n3.0,1,51000,39000,1,2950,0,0,1\n")
    sm = os.path.join(d, "summary.txt")
    open(sm, "w").write("x\n2026-11-09 11:39:07 port_gap4: WARNING: 22 MB swapped out while P028x started\n")
    notes = os.path.join(d, "notes")
    os.makedirs(notes)
    open(os.path.join(notes, "n.md"), "w").write("line1\nline2 +3.1 %\n")
    tried = os.path.join(d, "tried.txt")
    open(tried, "w").write("# comment\n## Prompt path\nADOPTED | toy switch | +3.1 % | notes/n.md:2\n"
                           "REJECTED | other | -2 % | summary.txt:2\n")
    inp = {"root": d, "title": "Toy pack", "date": "2026-11-09", "display_roots": [[d, ""], [notes, "notes/"]],
           "source_roots": {"": d, "notes/": notes}, "config": cp, "engine_dir": eng, "model_first_shard": g1,
           "gguf_reader_dir": None, "hardware": {"main_gpu": "RTX 5080 16 GB", "helper_gpu": "RTX 4060 Ti 8 GB"},
           "speed_sets": [{"name": "F", "kind": "fixture", "label": "fixtures", "files": ["F-*.jsonl"]},
                          {"name": "S", "kind": "screen", "label": "screen", "files": ["S1n.jsonl"]}],
           "primary_fixture_set": "F", "primary_screen_set": "S", "engine_start_log": el,
           "engine_logs": [{"path": el, "label": "toy log", "big_routed": 200000, "details": True}],
           "guard_logs": ["server_x.log"], "monitor_sys_csv": ["monitor-x.sys.csv"],
           "memory_summary_lines": [{"file": "summary.txt", "pattern": "swapped out", "label": "restart"}],
           "decode_timing": {"report": tr, "config": cp2}, "already_tried": tried, "output": os.path.join(d, "out", "PACK.md"),
           "release_day_list_out": os.path.join(d, "out", "release-day.txt"), "private_words": ["toyowner"],
           "intro": "Toy intro, cited [[src:notes/n.md:2]].", "memory_notes": ["a note citing a range [[src:summary.txt:1-2]]"]}
    ip = os.path.join(d, "inputs.json")
    json.dump(inp, open(ip, "w"), indent=1)
    text, S, F, items, problems = build(inp, ip)
    check("already-tried sources resolve", problems == [])
    check("compact_refs joins runs of 3+ consecutive tags only", compact_refs("a [S1] [S2] [S3] b [S5] [S6] c [S9] [S8]") == "a [S1-S3] b [S5] [S6] c [S9] [S8]")
    check("[[src:...]] citations in hand-written text resolve", "Toy intro, cited [S" in text and "[[src:" not in text
          and re.search(r"\*\*S\d+\*\* `summary\.txt:1-2`", text) is not None)
    check("placement: main/helper/PCIe/CPU from the two requests",
          re.search(r"\| toy log \| all requests \| 2 \| 301,400 \| 33\.4 % \| 0\.1 % \| 33\.2 % \| 33\.2 % \|", text) is not None)
    check("placement: the big-request subset", re.search(r"requests with >= 200,000 routed entries \| 1 \| 300,000 \| 33\.3 % \| 0\.0 % \| 33\.3 % \| 33\.3 %", text) is not None)
    check("MTP: all / MTP-only / prompt-lookup acceptance", "60 / 80 = 75.0 %" in text and "55 / 70 = 78.6 %" in text and "5 / 10 in 10 windows" in text)
    check("MTP: tokens per window = (accepted + windows) / windows", re.search(r"\| 1\.75 \| 2\.18 \|", text) is not None)
    check("MTP: per-position table from STRATA_SPEC_DEPTH lines", "| 1 | 9 | 10 | 90.0 % |" in text)
    check("speeds: 16K prompt row", re.search(r"prompt, 16K \| pp16k \(16,000 tokens\) \| 4,000\.0", text) is not None)
    check("speeds: short decode row (screen, prompt 110)", re.search(r"decode, short context \| W0 \(prompt 110", text) is not None)
    check("speeds: 16K decode flagged as approximate (nearest 24,000)", "decode near 16K (APPROXIMATE) | W2 (prompt 24,000" in text)
    check("speeds: 64K decode gap listed", any(w_ == "Decode speed at 64K context" for w_, _ in items))
    check("per-position gap not listed when depth lines exist", not any("per draft position" in w_ for w_, _ in items))
    check("timing: slowest step = the CPU pool, 9.67 of 23.17 ms", "Slowest step: CPU pool (missed experts) inside the host's per-layer work, 9.67 of 23.17 ms (42 %)" in text)
    check("timing: config difference reported", "STRATA_DECODE_TIMING" in text)
    check("guard line parsed", "| x-pp64k-1 | 61 | 34.2 GiB |" in text)
    check("monitor swap growth", "2940 -> 2950 -> 2950" in text and "10 MiB in 1 steps" in text)
    check("summary line quoted", "22 MB swapped out" in text)
    check("PCIe re-pricing and VRAM warning counted", "0.45 x1" in text and "lowest 504 MiB" in text)
    check("engine sha re-hashed and matched", "matches" in text)
    check("CUDA_VISIBLE_DEVICES UUIDs removed", "GPU-1111" not in text and "UUIDs removed" in text)
    check("slots line: 4,585 + 3,300 of 16 experts", "of 16 routed experts" in text)
    check("sources appendix has file:line", re.search(r"\*\*S\d+\*\* `tried\.txt|\*\*S\d+\*\* `notes/n\.md:2`", text) is not None)
    check("no absolute selftest path left in the text", d not in text)
    words = private_words(["toyowner"])
    check("scrub: the generated toy pack is clean", scrub(text, words) == [])
    bad = {"home path": "see /home/someone/x", "UUID": "id UUID",
           "GPU UUID": "CUDA_VISIBLE_DEVICES=GPU-UUID-RTX5080", "email": "mail a.b@example.com",
           "IP address (not 127.0.0.1)": "server 192.168.1.20:8080", "API key / token": "key sk-or-v1-abcdef0123456789",
           "owner's other tools": "used by Jan for chats", "username / hostname / private word": "by ToyOwner today",
           "long mixed-case secret-like string": "tok Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4zAb7c"}
    for name, s_ in bad.items():
        check(f"scrub catches: {name}", any(f[0] == name for f in scrub(s_, words)))
    ok_ = "served on 127.0.0.1:8081; engine v0.1.44.1; sha f4c4f654fb24e5e2c5d6ff92bcbe7ce0ac603c89e99b2930de9ff990f636801a; 0.2.8"
    check("scrub passes 127.0.0.1, v-versions, hex hashes", scrub(ok_, words) == [])
    # end to end: run() writes; a poisoned inputs file is refused and writes nothing
    ns = argparse.Namespace(inputs=ip, out=None, facts=False)
    rc = run(ns)
    check("run() writes the pack and the release-day list", rc == 0 and os.path.exists(inp["output"]) and os.path.exists(inp["release_day_list_out"]))
    inp2 = dict(inp, intro="Contact: someone@example.com", output=os.path.join(d, "out2", "PACK.md"))
    ip2 = os.path.join(d, "inputs2.json")
    json.dump(inp2, open(ip2, "w"))
    rc2 = run(argparse.Namespace(inputs=ip2, out=None, facts=False))
    check("run() refuses a pack that fails the scrub (exit 3, nothing written)", rc2 == 3 and not os.path.exists(inp2["output"]))
    open(tried, "a").write("PARKED | broken | x | notes/missing.md:3\n")
    rc3 = run(argparse.Namespace(inputs=ip, out=os.path.join(d, "out3", "P.md"), facts=False))
    check("run() refuses a missing already-tried source (exit 4)", rc3 == 4)
    print(f"selftest: {len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else "") + f" (scratch {os.path.relpath(d, HERE)})")
    if not fails:
        shutil.rmtree(d, ignore_errors=True)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("inputs")
    r.add_argument("--out")
    r.add_argument("--facts", action="store_true", help="print the key numbers with resolved file:line sources")
    sub.add_parser("selftest")
    a = ap.parse_args()
    return run(a) if a.cmd == "run" else selftest(a)


if __name__ == "__main__":
    sys.exit(main())
