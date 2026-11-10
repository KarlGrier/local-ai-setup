#!/usr/bin/env python3
"""day1.py - Qwen4 day one for our Strata setup (Karl's item 1 (b), written 11-04 before any Qwen4 release).

One command, from a new model's GGUF HEADERS only (no download, no tensor data, no GPU, no engine):

  .venv/bin/python -I -B work/qwen4-kit/day1.py check GGUF [GGUF ...] [--name NAME] [--out DIR] [options]

  1. reads each file's header (every shard of a split file; head-only files with NAME.size work too): architecture,
     every <arch>.* shape key, the tokenizer / chat-template keys, MTP / n-gram / vision tensors, and every tensor's
     name, type, shape and size (bytes from ggml's block sizes, never from the data);
  2. checks every tensor against the type tables of the next port's engine tree (default strata-r22p0210, read from
     its source at run time and cited file:line): the expert kernels (one set for the 5080 sm_120 and the 4060 Ti sm_89
     helper), the prompt path, the CPU expert pool, dense / attention / embedding / head / n-gram forms, the pack tool's
     rules (tools/iq_pack.py) and the geometry the kernels are compiled for. Per tensor group: OK / OK with a build
     option / needs a pack conversion (which tool, exact or rounding) / REFUSED (why);
  3. computes the fit per Karl's quant rule (bench2/QWEN4-DAY1-PLAN.md "Quant choice"): the largest quant whose experts
     fit RAM + VRAM (about 72 GiB today; every input of that number is a parameter below), picks that quant among the
     given candidates (grouped per model), and prints expert / dense bytes, K/V at the served context, what spills to the
     SSD, and the expected tier split + decode with the model of results/sweep-1103/UPGRADE-ESTIMATE.md sections 8-9;
  4. writes the day-one pieces for each pick into OUT/day1/: a config (from configs/P028x.json as the template,
     read-only; a NEW file, configs/<name>.json only with --install-config), the model-specific test parameters, and the
     command sequence (Strata run -> KL vs the reference -> the graded set -> speed; target 40-60 tok/s decode).
     11-04 (the Unsloth v3.1 rehearsal, results/qwen4-kit/unsloth-v31/REPORT.md section 8):
     - same-model swap: a file with the served file's shape keys and tokenizer gets configs/P028x.json with only
       --pack / --native / --ple-gguf swapped (+ its own log, no fallback), not the new-model stock config (--no-swap);
     - --files-at DIR | GLOB=DIR: the paths point where the download will land, not at the header files;
     - ties: candidates whose expert bytes are equal within --tie-tol-gib print "tie: quality decides" and get one set
       of pieces each (the served file excepted) - the KL / NLL step chooses, never the list order;
     - per file: which down (and gate/up) types the expert width allows (n_ff % qk per block size), so a shape limit is
       never read as a missing kernel (#444); the layout lines: metadata-only shard 1, layers split across shards, the
       n-gram table as its own shard, MTP inside the file or as separate mtp-*.gguf files beside it.

Helpers for the tests' model-specific inputs (no engine is started by any of them):
  day1.py retok --new-gguf NEW --out DIR [--old-gguf FN] [--names math,code,...]
        re-tokenize the frozen prompt files (bringup/out/r20a/prompts: Flash-Next ids, template applied) for a model
        with another tokenizer: decode with Flash-Next's tokenizer, encode with the new one (special tokens parsed)
  day1.py pfy PROMPT_DIR [--check] [-- pf_yardstick.py ARGS]
        work/r22/pf_yardstick.py with its prompt folder (PR, hard-coded) replaced by PROMPT_DIR; --check only lists
        the long40 cuts against each text's length (a new tokenizer changes the lengths)
  day1.py kr3 PROMPT_DIR -- kernel_rule3.py ARGS
        work/r22/kernel_rule3.py (with the NLL check) reading its next tokens from PROMPT_DIR

Read-only on everything outside OUT (and configs/<name>.json with --install-config, which never overwrites a file and
refuses P028x* names). Run it CPU-light: nice -n 19 taskset -c 31 timeout 120 .venv/bin/python -I -B ...
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True   # never write __pycache__ into the trees this reads (gguf-py, work/r22, the engine tree)

import argparse  # noqa: E402
import ast  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
from collections import Counter, OrderedDict, defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
GGUF_PY = WS / "ext/llama.cpp-3cf03257/gguf-py"
sys.path.insert(0, str(GGUF_PY))
from gguf.constants import GGML_QUANT_SIZES, GGMLQuantizationType as QT, GGUFValueType as VT  # noqa: E402

TREE = WS / "strata-r22p0210"                    # the next port's base (branch r22-port0210), read-only
REF_GGUF = WS / "models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"   # served (P028x)
TEMPLATE_CFG = WS / "configs/P028x.json"         # the served config: the template, never written
CURVES = WS / "results/sweep-1103/scratch-estimate/curves.json"
ESTIMATE_DOC = "results/sweep-1103/UPGRADE-ESTIMATE.md"
PROMPTS = WS / "bringup/out/r20a/prompts"        # the frozen prompt token files (Flash-Next ids)
PLAN_DOC = "/home/USER/ai/deep-research/results/bench2/QWEN4-DAY1-PLAN.md"
GIB, MIB = 2 ** 30, 2 ** 20
VERSION = "day1.py 2026-11-04b"

# =====================================================================================================================
# 1. GGUF headers (gguf-py's enums and block sizes; Strata's extra types from the tree's tools/gguf_reader.py)
# =====================================================================================================================
VFMT = {int(VT.UINT8): "B", int(VT.INT8): "b", int(VT.UINT16): "H", int(VT.INT16): "h", int(VT.UINT32): "I",
        int(VT.INT32): "i", int(VT.FLOAT32): "f", int(VT.BOOL): "?", int(VT.UINT64): "Q", int(VT.INT64): "q",
        int(VT.FLOAT64): "d"}
TYPES: dict = {}          # ggml type id -> (name, values per block, bytes per block); filled by type_table()
NAME2ID: dict = {}


class Truncated(ValueError):
    pass


class _Rd:
    """A sequential reader over the header bytes; reading stops at the end of the tensor table."""

    def __init__(self, f):
        self.f = f

    def take(self, n):
        b = self.f.read(n)
        if len(b) != n:
            raise Truncated(f"truncated header (wanted {n} bytes at offset {self.f.tell()})")
        return b

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.take(8))[0]

    def s(self):
        n = self.u64()
        if n > 1 << 28:
            raise ValueError(f"a {n}-byte string: not a GGUF header")
        return self.take(n).decode("utf-8", errors="replace")

    def val(self, vt):
        if vt == VT.STRING:
            return self.s()
        if vt == VT.ARRAY:
            et, n = self.u32(), self.u64()
            if et == VT.STRING:
                return [self.s() for _ in range(n)]
            if et == VT.ARRAY:
                return [self.val(VT.ARRAY) for _ in range(n)]
            if et not in VFMT:
                raise ValueError(f"array of unknown value type {et}")
            fmt = VFMT[et]
            return list(struct.unpack(f"<{n}{fmt}", self.take(struct.calcsize(fmt) * n)))
        if vt not in VFMT:
            raise ValueError(f"unknown metadata value type {vt}")
        fmt = VFMT[vt]
        return struct.unpack("<" + fmt, self.take(struct.calcsize(fmt)))[0]


def type_table(tree: Path):
    """gguf-py's GGMLQuantizationType + GGML_QUANT_SIZES, plus the ids only Strata knows (the tree's
    tools/gguf_reader.py GGML_TYPES / BLOCK_GEOMETRY: the trellis types 143-149)."""
    TYPES.clear()
    for q in QT:
        if q in GGML_QUANT_SIZES:
            bs, tb = GGML_QUANT_SIZES[q]
            TYPES[int(q)] = (q.name, bs, tb)
    notes = []
    src = tree / "tools/gguf_reader.py"
    try:
        names, geom = {}, {}
        for node in ast.parse(src.read_text(encoding="utf-8")).body:
            tgt = node.targets[0] if isinstance(node, ast.Assign) else node.target if isinstance(node, ast.AnnAssign) else None
            if isinstance(tgt, ast.Name) and tgt.id in ("GGML_TYPES", "BLOCK_GEOMETRY") and node.value is not None:
                (names if tgt.id == "GGML_TYPES" else geom).update(ast.literal_eval(node.value))
        for tid, nm in names.items():
            if tid not in TYPES and nm in geom:
                TYPES[tid] = (nm, *geom[nm])
                notes.append(f"{nm} = {tid}")
    except (OSError, SyntaxError, ValueError) as e:
        notes.append(f"{src}: not read ({e}); gguf-py's types only")
    NAME2ID.clear()
    NAME2ID.update({v[0]: k for k, v in TYPES.items()})
    return notes


def tname(t: int) -> str:
    return TYPES.get(t, (f"type{t}", 0, 0))[0]


class Tensor:
    __slots__ = ("name", "shape", "type", "offset", "shard")

    def __init__(self, name, shape, typ, offset, shard):
        self.name, self.shape, self.type, self.offset, self.shard = name, tuple(shape), typ, offset, shard

    @property
    def tname(self):
        return tname(self.type)

    @property
    def n(self):
        v = 1
        for d in self.shape:
            v *= d
        return v

    @property
    def nbytes(self):
        info = TYPES.get(self.type)
        if not info or not info[1]:
            return None
        return self.n // info[1] * info[2]

    @property
    def whole_blocks(self):
        info = TYPES.get(self.type)
        return bool(info) and bool(self.shape) and self.shape[0] % info[1] == 0


SHARD_RE = re.compile(r"(.*)-(\d{5})-of-(\d{5})\.gguf$")


def shards_of(path: Path) -> list:
    m = SHARD_RE.match(path.name)
    if not m:
        return [path]
    return [path.with_name(f"{m.group(1)}-{i:05d}-of-{m.group(3)}.gguf") for i in range(1, int(m.group(3)) + 1)]


def read_shard(path: Path, index: int) -> dict:
    """One shard's header: version, metadata (key -> (value type, value)), tensor table; where the header ends; the
    file's real size (NAME.size beside a head-only file, as bringup/fetch_model.py --heads writes it)."""
    out = {"path": str(path), "kv": OrderedDict(), "tensors": [], "problems": []}
    side = Path(str(path) + ".size")
    out["head_only"] = side.exists()
    out["size"] = int(side.read_text().split()[0]) if side.exists() else path.stat().st_size
    with open(path, "rb", buffering=1 << 20) as f:
        r = _Rd(f)
        if f.read(4) != b"GGUF":
            raise ValueError(f"{path.name}: not a GGUF file")
        out["version"] = r.u32()
        nt, nkv = r.u64(), r.u64()
        for _ in range(nkv):
            k = r.s()
            vt = r.u32()
            out["kv"][k] = (vt, r.val(vt))
        for _ in range(nt):
            name = r.s()
            nd = r.u32()
            dims = [r.u64() for _ in range(nd)]
            typ = r.u32()
            off = r.u64()
            out["tensors"].append(Tensor(name, dims, typ, off, index))
        out["header_end"] = f.tell()
    align = out["kv"].get("general.alignment", (4, 32))[1] or 32
    out["alignment"] = align
    out["data_start"] = (out["header_end"] + align - 1) // align * align
    if out["data_start"] > out["size"] and nt:
        out["problems"].append("data section starts past EOF (the engine's reader refuses it)")
    end = max((out["data_start"] + t.offset + (t.nbytes or 0) for t in out["tensors"]), default=0)
    if end > out["size"]:
        out["problems"].append(f"the tensor table reaches {end:,} bytes, the file is {out['size']:,}: truncated")
    return out


class Model:
    def __init__(self, path):
        self.given = Path(path)
        self.paths = shards_of(self.given)
        self.missing = [str(p) for p in self.paths if not p.exists()]
        self.shards, self.kv, self.vt, self.tensors, self.problems = [], OrderedDict(), {}, OrderedDict(), []
        for i, p in enumerate(self.paths):
            if not p.exists():
                continue
            try:
                s = read_shard(p, i)
            except (OSError, ValueError) as e:
                self.problems.append(f"{p.name}: {e}")
                continue
            self.shards.append(s)
            for k, (vt, v) in s["kv"].items():
                if k not in self.kv:
                    self.kv[k], self.vt[k] = v, vt
            for t in s["tensors"]:
                if t.name in self.tensors:
                    self.problems.append(f"{t.name} is in two shards (the engine refuses duplicates)")
                self.tensors[t.name] = t
            self.problems += [f"{p.name}: {x}" for x in s["problems"]]
        if self.missing:
            self.problems.append(f"missing shard(s): {', '.join(Path(x).name for x in self.missing)}")

    @property
    def arch(self):
        return self.kv.get("general.architecture", "?")

    def get(self, k, d=None):
        return self.kv.get(k, d)

    def a(self, suffix, d=None):
        return self.kv.get(f"{self.arch}.{suffix}", d)

    def file_bytes(self):
        return sum(s["size"] for s in self.shards)

    @property
    def head_only(self):
        return any(s["head_only"] for s in self.shards)


# =====================================================================================================================
# 2. The engine's tables, read from the tree's source (cited file:line); fall-backs are marked
# =====================================================================================================================
class Src:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._t = {}

    def text(self, rel):
        if rel not in self._t:
            p = self.root / rel
            self._t[rel] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        return self._t[rel]

    def find(self, rel, pat, flags=0):
        t = self.text(rel)
        m = re.search(pat, t, flags)
        if not m:
            return None, f"{rel}: NOT FOUND"
        return m, f"{rel}:{t.count(chr(10), 0, m.start()) + 1}"


def _ids(names):
    return {NAME2ID[n] for n in names if n in NAME2ID}


def engine_tables(tree: Path) -> dict:
    S = Src(tree)
    E = {"tree": str(tree), "cite": {}, "fallback": []}
    try:
        E["head"] = subprocess.run(["git", "-C", str(tree), "rev-parse", "--short=9", "HEAD"], capture_output=True,
                                   text=True, timeout=20).stdout.strip()
        E["branch"] = subprocess.run(["git", "-C", str(tree), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,
                                     text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        E["head"] = E["branch"] = "?"
    # ---- build options: CMakeLists defaults, then the built tree's CMakeCache.txt
    opts = {}
    cm = S.text("CMakeLists.txt")
    for o in ("STRATA_Q6K_EXPERTS", "STRATA_MMQ_KQUANTS", "STRATA_ORCA_Q4KS_MMQ", "STRATA_MMQ_TQ_OVERLAY"):
        m = re.search(rf'option\({o}\s+"[^"]*"\s+(ON|OFF)\)', cm)
        opts[o] = (m.group(1) == "ON") if m else False
    cache = tree / "build/CMakeCache.txt"
    E["archs"] = "?"
    if cache.exists():
        ct = cache.read_text(errors="replace")
        for o in list(opts):
            m = re.search(rf"^{o}:BOOL=(\w+)", ct, re.M)
            if m:
                opts[o] = m.group(1).upper() in ("ON", "1", "TRUE", "YES")
        m = re.search(r"^CMAKE_CUDA_ARCHITECTURES:\w+=(.*)$", ct, re.M)
        E["archs"] = m.group(1).strip() if m else "?"
        E["cite"]["build"] = "build/CMakeCache.txt"
    E["opts"] = opts
    xs = lambda s: {int(v) for v in re.findall(r"X\((\d+)\)", s)}  # noqa: E731
    iq = "src/kernels/cuda/iq_kernels.cu"

    def ifdef_macro(macro, flag):
        m, c = S.find(iq, rf"#ifdef {flag}\s*\n#define {macro}\(X\)([^\n]*)\n#else\s*\n#define {macro}\(X\)([^\n]*)\n#endif")
        if m:
            on, off = xs(m.group(1)), xs(m.group(2))
            return (on if opts.get(flag) else off), (set() if opts.get(flag) else on - off), on - off, c
        m, c = S.find(iq, rf"#define {macro}\(X\)([^\n]*)")
        return (xs(m.group(1)) if m else set()), set(), set(), c

    E["gu"], E["gu_opt"], E["q6k_only_gu"], E["cite"]["gu"] = ifdef_macro("STRATA_GU_FMTS", "STRATA_Q6K_EXPERTS")
    E["d"], E["d_opt"], E["q6k_only_d"], E["cite"]["d"] = ifdef_macro("STRATA_D_FMTS", "STRATA_Q6K_EXPERTS")
    if not E["gu"]:
        E["gu"] = {16, 17, 18, 21, 22, 23, 29, 42, 12, 13, 14, 6, 2, 3, 8, 40, 144, 145, 147, 148, 149}
        E["fallback"].append("STRATA_GU_FMTS (v0.2.10's list used)")
    if not E["d"]:
        E["d"] = {20, 23, 42, 7, 6, 2, 3, 8, 13, 14, 40, 144, 146, 147, 148, 149}
        E["fallback"].append("STRATA_D_FMTS (v0.2.10's list used)")
    m, E["cite"]["is_iq"] = S.find(iq, r"bool is_iq\(int t\)\s*\{(.*?)\n\}", re.S)
    if m:
        body = m.group(1)
        mi = re.search(r"#ifdef (\w+)\n(.*?)#else\n(.*?)#endif", body, re.S)
        n_ = lambda x: {int(v) for v in re.findall(r"t == (\d+)", x)}  # noqa: E731
        E["is_iq"] = n_(body[:mi.start()]) | n_(mi.group(2) if opts.get(mi.group(1)) else mi.group(3)) if mi else n_(body)
    else:
        E["is_iq"] = {16, 17, 18, 20, 21, 22, 23, 29, 42, 11, 12, 13, 14, 7, 6, 2, 3, 8, 40, 144, 145, 146, 147, 148, 149}
        E["fallback"].append("is_iq")
    m, E["cite"]["embed"] = S.find(iq, r"bool embed_type_supported\(int t\) noexcept \{ return is_iq\(t\)((?:\s*\|\|\s*t == \d+)*)")
    E["embed"] = E["is_iq"] | ({int(v) for v in re.findall(r"t == (\d+)", m.group(1))} if m else {30, 14})
    m, E["cite"]["expert_rule"] = S.find(iq, r"bool native_expert_supported\(int gu_type, int d_type, int64_t n_embd, int64_t n_ff\) noexcept \{")
    mm = "src/kernels/cuda/native_mmvq.cu"
    m, E["cite"]["mmvq"] = S.find(mm, r"bool native_mmvq_supported\(int ggml_type\) noexcept \{(.*?)\}", re.S)
    E["mmvq"] = {int(v) for v in re.findall(r"== (\d+)", m.group(1))} if m else {2, 6, 7, 8, 11, 12, 13, 14, 20, 23, 42, 16, 17, 18, 21, 22, 29}
    m, E["cite"]["mmvq_il"] = S.find(mm, r"bool native_mmvq_il_supported\(int ggml_type, int ncols, int n_out\) \{(.*?)\n\}", re.S)
    E["mmvq_il"] = {int(v) for v in re.findall(r"ggml_type == (\d+)", m.group(1))} if m else {23, 12, 13, 14, 11}
    # ---- the prompt path: MMQ (moe_mmq.cu supported()), else the FP16 dequantizer (is_iq); fused / v2 (speed only)
    mq = "src/prefill/moe_mmq.cu"
    m, E["cite"]["mmq"] = S.find(mq, r"\nbool supported\(int t\) \{\n(.*?)\n\}", re.S)
    mmq = set()
    if m:
        defined = {"STRATA_MMQ_KQUANTS": opts.get("STRATA_MMQ_KQUANTS"), "STRATA_ORCA_Q4KS_MMQ": opts.get("STRATA_ORCA_Q4KS_MMQ"),
                   "STRATA_MMQ_TQ": opts.get("STRATA_MMQ_TQ_OVERLAY"), "STRATA_MMQ_TQP": False}
        stack = []
        for line in m.group(1).splitlines():
            s = line.strip()
            if s.startswith("#ifdef"):
                stack.append(bool(defined.get(s.split()[1], False)))
            elif s.startswith("#if"):
                stack.append("!defined(GGML_USE_HIP)" in s or "!defined(__HIPCC__)" in s)
            elif s.startswith("#else"):
                stack[-1] = not stack[-1]
            elif s.startswith("#endif"):
                stack.pop()
            elif all(stack):
                if s.startswith("default"):
                    break
                mmq |= _ids(re.findall(r"case GGML_TYPE_(\w+)", s))
    E["mmq"] = mmq or {42, 16, 17, 22, 18, 21, 20, 23, 8, 12, 13, 7, 14, 40}
    if not mmq:
        E["fallback"].append("MMQ list")
    fz = "src/prefill/moe_fused_iq.cu"
    m, E["cite"]["fused"] = S.find(fz, r"bool gu_covered\(int t\) \{\s*return ([^\n]*)")
    E["fused_gu"] = _ids(re.findall(r"T_(\w+)", m.group(1))) if m else {16, 17, 22, 18, 21, 23}
    E["fused_sm120"] = _ids(["IQ2_S", "IQ3_XXS", "IQ3_S", "IQ4_XS"])      # sm120_series.hpp: on by default there
    E["fused_down"] = _ids(["IQ4_NL", "Q2_0"])
    m, E["cite"]["v2"] = S.find(fz, r"return gate_up \? \(m == 1 \|\| m == 2\) && type == T_(\w+) : \(m == 1 \|\| m == 3\) && type == T_(\w+);")
    E["v2"] = (_ids([m.group(1)]), _ids([m.group(2)])) if m else (_ids(["IQ3_XXS"]), _ids(["IQ4_NL"]))
    # ---- the CPU expert pool: any ggml-cpu dot product + the trellis types; the fast paths by ISA
    ne = "src/kernels/cpu/native_expert.cpp"

    def cpu_set(rel, fn, var="type"):
        m, c = S.find(rel, rf"bool {fn}\(int {var}\) noexcept \{{\s*return ([^;]*);")
        return ({int(v) for v in re.findall(rf"{var} == (\d+)", m.group(1))} if m else set()), c

    E["cpu512"], E["cite"]["cpu512"] = cpu_set(ne, "iq512_supported")
    E["cpu256"], E["cite"]["cpu256"] = cpu_set(ne, "iq256_supported")
    E["cpukq"], E["cite"]["cpukq"] = cpu_set(ne, "kq256_supported")
    E["cpu512x"], E["cite"]["cpu512x"] = cpu_set("src/kernels/cpu/iq_avx512.cpp", "iq512x_supported")
    E["cputq"], E["cite"]["cputq"] = cpu_set("src/kernels/cpu/tq_cpu.cpp", "tq_supported", "t")
    m, E["cite"]["cpu_rule"] = S.find(ne, r"bool native_fmt\(int gu_type")
    # ---- the n-gram (PLE) table formats (ngram.cpp kPleFormats: name, GGUF type)
    ng = "src/kernels/ngram.cpp"
    m, E["cite"]["ple"] = S.find(ng, r"const PleFormatInfo kPleFormats\[\] = \{(.*?)\n\};", re.S)
    E["ple"] = re.findall(r'\{PleFormat::\w+, "([^"]+)", "([^"]+)",', m.group(1)) if m else \
        [("IQ4_NL", "IQ4_NL"), ("Q5_0", "Q5_0"), ("F8_E4M3", "I8"), ("Q5_1", "Q5_1"), ("Q8_0", "Q8_0"), ("Q4_0", "Q4_0"),
         ("BF16", "BF16"), ("NVFP4", "I8")]
    # ---- the pack tool's rules (tools/iq_pack.py, parsed, not imported)
    pk = "tools/iq_pack.py"
    lits = {}
    try:
        for node in ast.parse(S.text(pk)).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                try:
                    lits[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    except SyntaxError:
        pass
    E["form"] = lits.get("FORM") or {}
    E["native_ple_key"] = set(lits.get("NATIVE_PLE_KEY") or {"Q2_0", "Q8_0", "IQ3_XXS", "IQ4_XS"})
    E["float"] = set(lits.get("FLOAT") or {"BF16", "F32", "F16"})
    if not E["form"]:
        E["fallback"].append("iq_pack FORM table (not found: float roles unchecked)")
    m, E["cite"]["form"] = S.find(pk, r"\nFORM = \{")
    m, E["cite"]["gate_up_rule"] = S.find(pk, r"gate and up differ in type")
    m, E["cite"]["nvfp4_scale"] = S.find(pk, r"NVFP4 experts without their \.scale tensors")
    m, E["cite"]["compat_bf16"] = S.find(pk, r"but the engine requires BF16; use --compat-bf16")
    sx = {}
    try:
        for node in ast.parse(S.text("tools/q8_dense_gguf.py")).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "SUFFIXES":
                sx = ast.literal_eval(node.value)
    except (SyntaxError, ValueError):
        pass
    E["native_dense"] = tuple(sx) or (".attn_qkv.weight", ".attn_gate.weight", ".ssm_out.weight", ".attn_q.weight",
                                      ".attn_k.weight", ".attn_v.weight", ".attn_output.weight", ".ffn_gate_shexp.weight",
                                      ".ffn_up_shexp.weight", ".ffn_down_shexp.weight")
    m, E["cite"]["native_dense"] = S.find("src/core/native_dense.cpp", r"native_mmvq_supported\(tensor\.type\)")
    m, E["cite"]["head"] = S.find("src/core/native_head.cpp", r"expected a natively supported output\.weight")
    m, E["cite"]["embed_load"] = S.find("src/core/native_head.cpp", r"embed_type_supported\(\(int\) t->type\)")
    m, E["cite"]["expert_load"] = S.find("src/program/generate.cpp", r"which this \"\s*\n?\s*\"engine has no GPU kernels for")
    if not m:
        m, E["cite"]["expert_load"] = S.find("src/program/generate.cpp", r"engine has no GPU kernels for")
    m, E["cite"]["remote"] = S.find("src/core/remote_experts.cpp", r"native_expert_layout\(fmt\.gu_type")
    # ---- families, geometry, pins
    mf = "include/strata/artifact/model_family.hpp"
    E["families"] = dict(re.findall(r'if \(arch == "([^"]+)"\) return ModelFamily::(\w+);', S.text(mf))) or \
        {"qwen4exp": "Qwen4Exp", "qwen35moe": "Qwen35Moe"}
    E["cite"]["families"] = S.find(mf, r"if \(arch == ")[1]
    if (tree / "src/dsv41").is_dir():
        E["families"].setdefault("deepseek41", "DeepSeek41 (strata-dsv41, its own engine: not the Qwen path)")
    ge = "include/strata/core/geometry.hpp"
    gt = S.text(ge)
    E["geometry"] = {k: int(v) for k, v in re.findall(r"int64_t (\w+) = (\d+);", gt)}
    m = re.search(r"double rms_eps = ([0-9.eE+-]+);", gt)
    E["geometry"]["rms_eps"] = float(m.group(1)) if m else 1e-6
    E["cite"]["geometry"] = S.find(ge, r"int64_t n_embd = ")[1]
    gr = "include/strata/artifact/gguf_reader.hpp"
    m, E["cite"]["read_geometry"] = S.find(gr, r"inline std::string read_geometry\(")
    E["read_keys"] = [(k, f, r == "true") for k, f, r in
                      re.findall(r'\{"([a-z_.]+)", &core::ModelGeometry::(\w+), (true|false)\}', S.text(gr))]
    m, E["cite"]["pins"] = S.find(gr, r"inline std::string geometry_unsupported\(")
    body = S.text(gr)[m.start():m.start() + 4000] if m else ""
    E["pins"] = re.findall(r'\{"([a-z_.]+)", &core::ModelGeometry::(\w+)\}', body)
    if not E["pins"] or not E["read_keys"]:
        E["fallback"].append("geometry pins / read_geometry keys not parsed")
    m, E["cite"]["q35"] = S.find(gr, r"inline std::string check_architecture_qwen35moe\(const GgufFile& g\) \{(.*?)\};", re.S)
    E["q35_keys"] = re.findall(r'"qwen35moe\.([a-z_.]+)"', m.group(1)) if m else []
    q36 = "src/qwen35/q36_engine.cu"
    qt = S.text(q36)
    E["q35_f32"] = set(re.findall(r'f32\(L\(l, "([a-z_.]+)"\)', qt)) | set(re.findall(r'f32\("([a-z_.]+)"\)', qt))
    E["q35_mat"] = set(re.findall(r'mat\(L\(l, "([a-z_.]+)"\)', qt)) | set(re.findall(r'mat\("([a-z_.]+)"\)', qt))
    E["cite"]["q35_mat"] = S.find(q36, r"which the native MMVQ does not take")[1]
    E["cite"]["q35_f32"] = S.find(q36, r"auto f32 = \[&\]\(const std::string& name\)")[1]
    m, E["cite"]["q35_eos"] = S.find("src/qwen35/q36_engine.cu", r"bool is_eos\(int t\) \{ return ([^;]*);")
    E["q35_eos"] = {int(v) for v in re.findall(r"t == (\d+)", m.group(1))} if m else {248044, 248046}
    m, E["cite"]["router"] = S.find("src/kernels/cuda/native_router.cu", r"bool native_router_topk_supported\(int n_expert, int k\) \{ return ([^;]*);")
    E["router"] = [(int(a), int(b)) for a, b in re.findall(r"n_expert == (\d+) && k == (\d+)", m.group(1))] if m else [(512, 10), (256, 8)]
    # ---- setup.py's name check (setup refuses files by their quant NAME; our tests do not go through setup)
    E["setup_models"], E["setup_quant_re"], E["setup_text"] = set(), None, ""
    try:
        for node in ast.parse(S.text("setup.py")).body:
            if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)):
                continue
            nm = node.targets[0].id
            if nm == "MODELS" and isinstance(node.value, ast.Dict):
                E["setup_models"] = {ast.literal_eval(k) for k in node.value.keys}
            elif nm == "GGUF_QUANT" and isinstance(node.value, ast.Call) and node.value.args:
                E["setup_quant_re"] = re.compile(ast.literal_eval(node.value.args[0]), re.I)
            elif nm == "SUPPORTED_GGUFS":
                E["setup_text"] = ast.literal_eval(node.value)
    except (SyntaxError, ValueError):
        E["fallback"].append("setup.py name check")
    E["cite"]["setup"] = S.find("setup.py", r"\ndef gguf_unsupported\(")[1]
    fp = tree / "data/gguf_fingerprints.json"
    E["seen_roles"] = {}
    if fp.exists():
        try:
            E["seen_roles"] = json.loads(fp.read_text()).get("_roles", {})
        except ValueError:
            pass
    return E


# =====================================================================================================================
# 3. The checks
# =====================================================================================================================
LEVEL = {"OK": 0, "OK (build option)": 1, "PACK (exact)": 2, "PACK (exact if the values allow)": 3, "PACK (rounding)": 4,
         "TOOL (conversion)": 5, "IGNORED": 1, "UNKNOWN": 6, "REFUSED": 7}


def role_of(name):
    return re.sub(r"^blk\.\d+\.", "blk.N.", name)


def layer_of(name):
    m = re.match(r"blk\.(\d+)\.", name)
    return int(m.group(1)) if m else None


def tn(ids):
    return ", ".join(sorted(tname(i) for i in ids))


def num(v, d=0):
    """A metadata value as an int: per-layer arrays give their largest entry (some architectures store head counts per
    layer); anything else non-numeric gives d."""
    if isinstance(v, bool):
        return d
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, list):
        xs = [int(x) for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
        return max(xs) if xs else d
    return d


def ai(m, key, d=0):
    return num(m.a(key), d)


def trunk_of(m):
    return ai(m, "block_count") - ai(m, "nextn_predict_layers")


def group_of(name, trunk):
    base = re.sub(r"^blk\.\d+\.", "", name)
    lay = layer_of(name)
    if name.startswith(("v.", "mm.")) or ".vision" in name:
        return "vision"
    if "nextn" in name or name.startswith("mtp.") or (lay is not None and trunk and lay >= trunk):
        return "MTP / nextn"
    if name.endswith("_exps.weight") or name.endswith("_exps.scale"):
        return "routed experts"
    if "shexp" in base:
        return "shared expert"
    if base.startswith("ffn_gate_inp"):
        return "router"
    if base.startswith("attn_"):
        return "attention"
    if base.startswith("indexer."):
        return "attention indexer"
    if base.startswith("ssm_"):
        return "GDN (linear attention)"
    if base.startswith("hc_") or name.startswith("output_hc_"):
        return "hyper-connections"
    if name == "per_layer_token_embd.weight":
        return "n-gram (PLE) table"
    if base.startswith("ple_"):
        return "n-gram (PLE) projections"
    if name == "token_embd.weight":
        return "token embedding"
    if name == "output.weight":
        return "head"
    if base.startswith(("ffn_gate", "ffn_up", "ffn_down")):
        return "dense FFN"
    return "other"


def check_tensor(t, E, known_roles, family=None):
    """(verdict, why) for one non-expert tensor."""
    n, base, ty = t.name, re.sub(r"^blk\.\d+\.", "", t.name), t.tname
    if t.type not in TYPES:
        return "REFUSED", f"ggml type id {t.type} is unknown to gguf-py and to the tree's tools/gguf_reader.py"
    if family == "Qwen35Moe" and n != "token_embd.weight":
        # the own path (src/qwen35): no pack; q36_engine.cu loads the GGUF itself
        if base in E["q35_mat"]:
            return (("OK", f"qwen35 path: native MMVQ matrix ({E['cite']['q35_mat']})") if t.type in E["mmvq"] else
                    ("REFUSED", f"{ty}: the qwen35 path's mat() takes native_mmvq types only and exits ({E['cite']['q35_mat']})"))
        if base in E["q35_f32"]:
            return (("OK", f"qwen35 path: uploaded as F32 ({E['cite']['q35_f32']})") if ty in E["float"] else
                    ("UNKNOWN", f"{ty}: the qwen35 path uploads this as F32 ({E['cite']['q35_f32']}); a quantized one: check"))
        return "UNKNOWN", "a tensor the qwen35 path's loader does not name (q36_engine.cu): ignored or refused - check"
    if n == "per_layer_token_embd.weight":
        ok = [f for f, g in E["ple"] if g == ty]
        if ok:
            return "OK", f"n-gram table read from its GGUF ({'/'.join(ok)}; ngram.cpp kPleFormats {E['cite']['ple']})" + \
                (": I8 needs strata.ple.format" if ty == "I8" else "")
        return "TOOL (conversion)", (f"{ty} is not a table format ({', '.join(sorted({g for _, g in E['ple']}))}, "
                                     f"{E['cite']['ple']}); tools/ple_fp8_pack.py writes the FP8 table from the HF checkpoint")
    if n == "token_embd.weight":
        if t.type in E["embed"]:
            return "OK", f"native embedding from the GGUF (embed_type_supported {E['cite']['embed']})"
        return "TOOL (conversion)", (f"{ty} has no GPU dequantizer (embed takes {tn(E['embed'])}, {E['cite']['embed_load']}): "
                                     "tools/embd_bf16_pack.py --gguf -> BF16 copy (rounds unless the values are BF16), "
                                     "then --embd-gguf")
    if n == "output.weight":
        if t.type in E["mmvq"]:
            return "OK", f"native head (native_mmvq_supported {E['cite']['mmvq']})"
        return "PACK (rounding)", (f"{ty}: the head must be a native_mmvq type ({E['cite']['head']}); "
                                   "tools/q8_dense_gguf.py rewrites the head + dense projections as Q8_0 (offsets kept)")
    form = E["form"].get(base)
    if form:
        if ty == form:
            return "OK", f"in the pack (dense.bin) as stored: the engine reads {form} (iq_pack FORM {E['cite']['form']})"
        if base == "ple_key.weight" and ty in E["native_ple_key"]:
            return "OK", f"native PLE key ({ty}, iq_pack NATIVE_PLE_KEY)"
        if form == "BF16":
            if ty == "F32":
                return "PACK (exact if the values allow)", ("F32 -> BF16: exact when every value is BF16 (iq_pack checks the low 16 bits at "
                                        "pack time); else --compat-bf16 (nearest-even rounding)")
            return "PACK (rounding)", f"{ty} -> BF16 needs iq_pack --compat-bf16 ({E['cite']['compat_bf16']})"
        if form == "F16":
            if ty == "F32":
                return "PACK (exact if the values allow)", "F32 -> F16 by the loader (index kind 3, nearest-even): exact only if the values are F16's"
            return "PACK (rounding)", f"{ty} -> F16 needs iq_pack --compat-bf16"
        if form == "F32":
            if ty in ("F16", "BF16"):
                return "PACK (exact)", f"{ty} -> F32 widening (iq_pack default)"
            return "PACK (rounding)", f"{ty} -> F32 needs iq_pack --compat-bf16"
    if t.name.endswith(E["native_dense"]):
        if t.type in E["mmvq"]:
            il = " (+ the interleaved MMVQ_IL kernel)" if t.type in E["mmvq_il"] else ""
            return ("OK", f"native dense projection from the GGUF{il} ({E['cite']['native_dense']})") if t.whole_blocks else \
                ("REFUSED", f"rows of {t.shape[0]} values are not whole {ty} blocks")
        if ty in E["float"]:
            return "OK", f"{ty}: in the pack (dense.bin) as stored"
        return "PACK (rounding)", (f"{ty} is not a native_mmvq type ({tn(E['mmvq'])}); tools/q8_dense_gguf.py rewrites "
                                   "the natively served dense matrices as Q8_0")
    role = role_of(n)
    if role not in known_roles:
        return "UNKNOWN", (f"a tensor role no file Strata runs has ({role}): the engine may ignore or refuse it - read the "
                           "release's loader for it")
    if ty in E["float"] or len(t.shape) == 1:
        return "OK", f"{ty}: in the pack as stored (no FORM entry)"
    return "OK", f"{ty}: served from the GGUF (iq_pack: quantized, no FORM entry; a role Flash-Next files carry)"


def check_experts(m, E, trunk):
    """Per layer: the gate/up and down formats against the GPU expert kernels (both cards), the pack rule, the prompt
    path and the CPU pool. Returns (per-combination rows, per-layer problems)."""
    n_embd, n_ff, n_exp = ai(m, "embedding_length"), ai(m, "expert_feed_forward_length"), ai(m, "expert_count")
    combos = OrderedDict()
    problems = []
    for l in range(trunk):
        g, u, d = (m.tensors.get(f"blk.{l}.ffn_{p}_exps.weight") for p in ("gate", "up", "down"))
        if not (g and u and d):
            if g or u or d:
                problems.append(f"layer {l}: gate/up/down not all present")
            continue
        key = (g.type, u.type, d.type)
        c = combos.setdefault(key, {"layers": [], "verdict": "OK", "why": [], "prompt": "", "cpu": "", "notes": []})
        c["layers"].append(l)
    rows = []
    for (gt, ut, dt), c in combos.items():
        why, v = [], "OK"
        if gt not in TYPES or dt not in TYPES:
            v = "REFUSED"
            why.append("an unknown ggml type id")
        elif gt != ut:
            v = "REFUSED"
            why.append(f"gate {tname(gt)} and up {tname(ut)} differ: iq_pack refuses ({E['cite']['gate_up_rule']}) - the "
                       "engine runs one gate/up format per layer")
        else:
            for t, allowed, opt, what, cite in ((gt, E["gu"], E["gu_opt"], "gate/up", E["cite"]["gu"]),
                                                 (dt, E["d"], E["d_opt"], "down", E["cite"]["d"])):
                if t in allowed:
                    continue
                if t in opt:
                    v = max(v, "OK (build option)", key=LEVEL.get)
                    why.append(f"{tname(t)} {what} needs -DSTRATA_Q6K_EXPERTS=ON")
                else:
                    v = "REFUSED"
                    why.append(f"{tname(t)} {what}: no GPU expert kernel ({what} takes {tn(allowed)}; {cite}); the engine "
                               f"stops at load ({E['cite']['expert_load']})")
            bg, bd = TYPES[gt][1], TYPES[dt][1]
            if n_embd % 256 or n_embd % bg or n_ff % bd or (n_ff * n_embd) % 256:
                v = "REFUSED"
                why.append(f"n_embd {n_embd} / n_ff {n_ff} not whole blocks (native_expert_supported {E['cite']['expert_rule']})")
            if 40 in (gt, dt):
                miss = [p for p in ("gate", "up", "down") if f"blk.{c['layers'][0]}.ffn_{p}_exps.scale" not in m.tensors
                        and m.tensors[f"blk.{c['layers'][0]}.ffn_{p}_exps.weight"].type == 40]
                if miss:
                    v = "REFUSED"
                    why.append(f"NVFP4 without its .scale tensors ({E['cite']['nvfp4_scale']})")
                else:
                    c["notes"].append("NVFP4: iq_pack writes experts.bin (scale tails); the GGUF alone is not enough")
        if not why:
            why.append(f"GPU kernels on both cards (one iq_kernels.cu, built for {E['archs']}; the 4060 Ti helper uses "
                       f"the same native_expert_layout, {E['cite']['remote']})")
        pr = []
        for t, what in ((gt, "gate/up"), (dt, "down")):
            pr.append(f"{what} " + ("MMQ" if t in E["mmq"] else "FP16 dequant" if t in E["is_iq"] else "NONE"))
        extra = []
        if gt in E["fused_sm120"] and dt in E["fused_down"]:
            extra.append("fused int8 prompt kernels on the 5080 (sm_120, 84 SMs)")
        if gt in E["v2"][0] or dt in E["v2"][1]:
            extra.append("v2 prompt kernels (our STRATA_PREFILL_V2; compiled for 2560 / 640)")
        c["prompt"] = "; ".join(pr) + (" + " + ", ".join(extra) if extra else "")
        fast = lambda t: ("AVX-512 IQ" if t in E["cpu512"] else "AVX-512 IQ multi-token" if t in E["cpu512x"] else  # noqa: E731
                          "AVX2 IQ" if t in E["cpu256"] else "AVX2 K/Q" if t in E["cpukq"] else
                          "trellis" if t in E["cputq"] else "NVFP4 AVX-512" if t == 40 else
                          "IQ4_NL AVX2" if t == 20 else "ggml-cpu dot")
        c["cpu"] = f"gate/up {fast(gt)}, down {fast(dt)}"
        c["verdict"], c["why"] = v, why
        rows.append({"gate_up": tname(gt) if gt == ut else f"{tname(gt)}/{tname(ut)}", "down": tname(dt),
                     "layers": len(c["layers"]), "layer_list": c["layers"], "verdict": v, "why": "; ".join(why),
                     "prompt": c["prompt"], "cpu": c["cpu"], "notes": c["notes"]})
    if n_exp and m.a("expert_count") is None:
        problems.append("no expert_count key")
    return rows, problems


def geometry_check(m, E):
    arch, fam = m.arch, E["families"].get(m.arch)
    res = {"arch": arch, "family": fam, "refused": [], "notes": [], "values": {}}
    if fam is None:
        res["refused"].append(f"architecture '{arch}': this tree runs {', '.join(sorted(E['families']))} only "
                              f"({E['cite']['families']}): an architecture name this tree does not know needs the release "
                              "that adds it")
        return res
    if fam.startswith("DeepSeek41"):
        res["refused"].append("deepseek41 runs on strata-dsv41 (its own engine and pack), not on the Qwen path checked here")
        return res
    p = arch + "."
    if fam == "Qwen35Moe":
        miss = [k for k in E["q35_keys"] if m.get(p + k) is None]
        if miss:
            res["refused"].append(f"missing {', '.join(p + k for k in miss)} ({E['cite']['q35']})")
        bc, nx = ai(m, "block_count"), ai(m, "nextn_predict_layers")
        if bc and nx >= bc:
            res["refused"].append(f"{p}nextn_predict_layers {nx} is not smaller than block_count {bc}")
        if ai(m, "full_attention_interval") < 2:
            res["refused"].append(f"{p}full_attention_interval must be at least 2")
        eos = {x for x in (m.get("tokenizer.ggml.eos_token_id"), m.get("tokenizer.ggml.padding_token_id")) if isinstance(x, int)}
        if eos - E["q35_eos"]:
            res["refused"].append(f"end ids {sorted(eos - E['q35_eos'])}: the qwen35 path stops only at {sorted(E['q35_eos'])} "
                                  f"(hard-coded, {E['cite']['q35_eos']})")
        res["notes"].append("qwen35moe: the own path (src/qwen35), geometry read from the file; experts / dense take the "
                            "same native_expert_supported / native_mmvq_supported tables")
        return res
    comp = E["geometry"]
    g = dict(comp)
    for key, field, req in E["read_keys"]:
        v = m.get(p + key)
        if v is None:
            if req:
                res["refused"].append(f"missing {p}{key} (read_geometry requires it, {E['cite']['read_geometry']})")
            continue
        if isinstance(v, bool) or not isinstance(v, int):
            res["refused"].append(f"{p}{key} is not an integer")
            continue
        if v <= 0:
            res["refused"].append(f"{p}{key} = {v}: must be positive")
            continue
        g[field] = v
    vl, sh = m.a("attention.value_length"), m.a("expert_shared_feed_forward_length")
    if vl is not None and vl != g.get("head_dim"):
        res["refused"].append(f"{p}attention.value_length {vl} != key_length {g.get('head_dim')} (one head width)")
    if sh is not None and sh != g.get("n_ff"):
        res["refused"].append(f"{p}expert_shared_feed_forward_length {sh} != expert_feed_forward_length {g.get('n_ff')}")
    if g.get("n_head_kv") and g.get("n_head", 0) % g["n_head_kv"]:
        res["refused"].append(f"{p}attention.head_count {g['n_head']} is not a multiple of head_count_kv {g['n_head_kv']}")
    if g.get("ssm_value_dim") != g.get("ssm_state_size", 0) * g.get("ssm_v_heads", 0):
        res["refused"].append(f"{p}ssm.inner_size {g.get('ssm_value_dim')} != state x time_step_rank (square GDN heads)")
    if g.get("n_expert_used", 0) > min(g.get("n_expert", 0), 64):
        res["refused"].append(f"{p}expert_used_count {g.get('n_expert_used')}: the router takes 1..{min(g.get('n_expert', 0), 64)}")
    cr = m.a("attention.compress_ratios")
    if isinstance(cr, list) and any(cr):
        qi = g.get("qsa_interval", 4) or 4
        bad = [i for i, r in enumerate(cr) if (r != 0) != (i % qi == qi - 1)]
        if bad or len(cr) != g.get("n_layers"):
            res["refused"].append(f"{p}attention.compress_ratios does not match full_attention_interval {qi} (layer "
                                  f"{bad[0] if bad else '-'}; {len(cr)} entries for {g.get('n_layers')} layers)")
        else:
            g["idx_block"] = next(r for r in cr if r)
    for key, field in E["pins"]:
        if g.get(field) != comp.get(field):
            res["refused"].append(f"{p}{key} = {g.get(field)}, the kernels are compiled for {comp.get(field)} "
                                  f"({E['cite']['pins']}: needs a release built for this shape)")
    eps = m.a("attention.layer_norm_rms_epsilon")
    if eps is not None and abs(eps - comp["rms_eps"]) > 1e-6 * comp["rms_eps"]:
        res["refused"].append(f"{p}attention.layer_norm_rms_epsilon {eps:g}, the norm kernels are compiled for {comp['rms_eps']:g}")
    nx = m.a("nextn_predict_layers")
    if nx:
        res["notes"].append(f"{p}nextn_predict_layers = {nx}: read_geometry reads block_count as the trunk - an in-file MTP "
                            "block makes block_count larger than the compiled 48 (see SHAPES.md 3.11)")
    pair = (g.get("n_expert"), g.get("n_expert_used"))
    if pair not in E["router"]:
        res["notes"].append(f"router (experts, top-k) {pair}: the top-k kernel is compiled for {E['router']} "
                            f"({E['cite']['router']}); other pairs take the generic path")
    res["values"] = g
    return res


MARKERS = ["<|im_start|>", "<|im_end|>", "<|endoftext|>", "<think>", "</think>", "<tool_call>", "</tool_call>",
           "<tool_response>", "<|vision_start|>", "<|image_pad|>"]


def _h(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False).encode("utf-8")).hexdigest()[:16] if x else None


def tok_info(m):
    toks = m.get("tokenizer.ggml.tokens") or []
    tt = m.get("tokenizer.ggml.token_type") or []
    want = set(MARKERS)
    ids = {}
    for i, t in enumerate(toks):
        if t in want:
            ids[t] = i
    tpl = m.get("tokenizer.chat_template") or ""
    eff = []
    mm = re.search(r"reasoning_effort\s*\|\s*default\('(\w+)'\)", tpl)
    for x in re.finditer(r"reasoning_effort not in \(([^)]*)\)", tpl):
        eff += re.findall(r"'(\w+)'", x.group(1))
    alias = re.findall(r"reasoning_effort == '(\w+)' %\}\s*\{%-? set resolved_reasoning_effort = '(\w+)'", tpl)
    tid = lambda k: m.get(f"tokenizer.ggml.{k}")  # noqa: E731
    tx = lambda i: toks[i] if isinstance(i, int) and 0 <= i < len(toks) else None  # noqa: E731
    return {"model": m.get("tokenizer.ggml.model"), "pre": m.get("tokenizer.ggml.pre"), "vocab": len(toks),
            "tokens_sha": _h(toks), "merges_sha": _h(m.get("tokenizer.ggml.merges") or []), "types_sha": _h(tt),
            "eos": [tid("eos_token_id"), tx(tid("eos_token_id"))], "bos": [tid("bos_token_id"), tx(tid("bos_token_id"))],
            "pad": [tid("padding_token_id"), tx(tid("padding_token_id"))], "marker_ids": ids,
            "control_tokens": sum(1 for x in tt if x == 3), "template_chars": len(tpl), "template_sha": _h(tpl),
            "template_markers": {k: (k in tpl) for k in MARKERS}, "efforts": sorted(set(eff)),
            "effort_default": mm.group(1) if mm else None, "effort_aliases": dict(alias),
            "thinking_off": "enable_thinking" in tpl, "developer_role": "developer" in tpl,
            "tool_format": ("XML <function=...><parameter=...> in <tool_call>" if "<function=" in tpl else
                            "JSON in <tool_call>" if "<tool_call>" in tpl else "none in the template"),
            "context_length": m.a("context_length")}


def tok_compare(new, ref):
    same = {k: new[k] == ref[k] for k in ("tokens_sha", "merges_sha", "types_sha", "template_sha")}
    same["special_ids"] = new["marker_ids"] == ref["marker_ids"] and new["eos"] == ref["eos"]
    v = "same tokenizer: the frozen prompt token files are valid" if same["tokens_sha"] and same["merges_sha"] and \
        same["special_ids"] else "ANOTHER tokenizer: re-tokenize every frozen prompt (day1.py retok) before exact7 / pf_yardstick"
    if not same["template_sha"]:
        v += "; another chat template (re-check think tags, effort names, tool calls; the server renders it)"
    return same, v


def setup_name_check(path: Path, E):
    rx = E.get("setup_quant_re")
    if not rx:
        return None, None
    mq = rx.search(path.name)
    q = mq.group(1) if mq else None
    bad = q if q and q.upper() not in {k.upper() for k in E["setup_models"]} and not path.name.lower().startswith("mmproj") else None
    return q, bad


# ---- which expert types the widths allow (a shape limit is not a missing kernel: the #444 misreading, REPORT 8.6)
NOT_STORAGE = {"Q8_1", "Q8_K"}          # ggml's activation-side types: never a weight type in a GGUF
LOW_256 = ("IQ3_XXS", "IQ2_XS", "Q2_K", "Q3_K")   # the low-bit downs Unsloth's UD quants use when the width allows


def width_types(n, kernel, opt=frozenset()):
    """Per block size: does n split into whole blocks, and which types (with / without a GPU expert kernel here)."""
    by = defaultdict(list)
    for tid, (nm, bs, _tb) in TYPES.items():
        if bs > 1 and nm not in NOT_STORAGE:
            by[bs].append(tid)
    rows = []
    for bs in sorted(by):
        ids = sorted(by[bs], key=tname)
        rows.append({"block": bs, "ok": n > 0 and n % bs == 0, "rem": n % bs if n else None,
                     "types": [tname(i) for i in ids], "kernel": [tname(i) for i in ids if i in kernel],
                     "build_option": [tname(i) for i in ids if i in opt],
                     "no_kernel": [tname(i) for i in ids if i not in kernel and i not in opt]})
    return rows


def shape_types(m, E, exp_rows):
    """The 'which down / gate-up types the expert width allows' lines for one file (n_ff % qk per block size)."""
    trunk = trunk_of(m)
    n_ff = ai(m, "expert_feed_forward_length")
    n_embd = ai(m, "embedding_length")
    d0 = next((m.tensors.get(f"blk.{l}.ffn_down_exps.weight") for l in range(trunk)
               if f"blk.{l}.ffn_down_exps.weight" in m.tensors), None)
    if d0 is not None and d0.shape:
        n_ff = d0.shape[0]                  # the down rows' length is the expert width (ggml ne0)
    used = Counter()
    for r in exp_rows:
        used[r["down"]] += r["layers"]
    used_gu = Counter()
    for r in exp_rows:
        used_gu[r["gate_up"]] += r["layers"]
    down = width_types(n_ff, E["d"], E["d_opt"])
    gu = width_types(n_embd, E["gu"], E["gu_opt"])
    out = {"n_ff": n_ff, "n_embd": n_embd, "down": down, "gate_up": gu, "down_used": dict(used),
           "gate_up_used": dict(used_gu)}
    ok = [r for r in down if r["ok"]]
    bad = [r for r in down if not r["ok"]]
    allowed_k = sorted({t for r in ok for t in r["kernel"]})
    allowed_opt = sorted({t for r in ok for t in r["build_option"]})
    allowed_nok = sorted({t for r in ok for t in r["no_kernel"]})
    txt = (f"down types the expert width allows (n_ff {n_ff}, n_ff % qk): "
           + "; ".join(f"{r['block']}-value blocks {'OK' if r['ok'] else f'IMPOSSIBLE ({n_ff} % {r['block']} = {r['rem']})'}"
                       for r in down)
           + f". Allowed with a GPU down kernel here: {', '.join(allowed_k) or 'none'}"
           + (f"; allowed with -DSTRATA_Q6K_EXPERTS=ON: {', '.join(allowed_opt)}" if allowed_opt else "")
           + (f"; allowed by shape but NO down kernel here (the type-support patch, REPORT 7 (b)): {', '.join(allowed_nok)}"
              if allowed_nok else ""))
    if bad:
        imp = sorted({t for r in bad for t in r["types"]})
        txt += (f". Impossible BY SHAPE for this model (no file of it can carry such a down - a shape limit, not a "
                f"missing kernel): {', '.join(imp)}")
    if used:
        txt += f". This file's downs: {', '.join(f'{k} x{v}' for k, v in used.most_common())}"
    out["down_text"] = txt
    gbad = [r for r in gu if not r["ok"]]
    out["gate_up_text"] = (f"gate/up types the hidden width allows (n_embd {n_embd}): "
                           + ("every block size divides it" if not gbad else
                              "; ".join(f"{r['block']}-value blocks IMPOSSIBLE ({n_embd} % {r['block']} = {r['rem']})"
                                        for r in gbad))
                           + (f"; this file's gate/up: {', '.join(f'{k} x{v}' for k, v in used_gu.most_common())}"
                              if used_gu else ""))
    note = None
    if n_ff and n_ff % 256 == 0:
        k256 = [t for t in LOW_256 if NAME2ID.get(t) in E["d"]]
        nk = [t for t in LOW_256 if NAME2ID.get(t) not in E["d"]]
        note = (f"n_ff {n_ff} is a multiple of 256: {' / '.join(LOW_256)} downs are POSSIBLE for this model - Unsloth's "
                "low quants will carry them" + (f"; {', '.join(nk)} have no down kernel in this tree: such a file is "
                                               "REFUSED until the type-support patch (REPORT 7 (b)) - check "
                                               "expert_feed_forward_length first on Qwen4 day one" if nk else "")
                + (f"; {', '.join(k256)} already have one" if k256 else ""))
    elif n_ff:
        note = (f"n_ff {n_ff} is not a multiple of 256: {' / '.join(LOW_256)} downs cannot occur in any file of this model "
                "(a refusal naming one of them must come from another model or from setup.py's name list)")
    out["note_256"] = note
    return out


def _shard_no(path):
    mm = SHARD_RE.match(Path(path).name)
    return int(mm.group(2)) if mm else 1


def _sidecar_head(p: Path):
    """A sidecar GGUF's header summary (head-only files with NAME.size work); data only, never executed."""
    try:
        s = read_shard(p, 0)
    except (OSError, ValueError) as e:
        return {"path": str(p), "error": str(e)}
    kv = {k: v for k, (vt, v) in s["kv"].items()}
    arch = kv.get("general.architecture", "?")
    names = [t.name for t in s["tensors"]]
    lays = sorted({layer_of(n) for n in names if layer_of(n) is not None})
    return {"path": str(p), "size": s["size"], "head_only": s["head_only"], "arch": arch, "tensors": len(names),
            "block_count": kv.get(f"{arch}.block_count"), "nextn": kv.get(f"{arch}.nextn_predict_layers"),
            "layers": lays, "nextn_tensors": sum(1 for n in names if ".nextn." in n),
            "has_embd_head": [n for n in ("token_embd.weight", "output.weight") if n in names],
            "shared_flag": kv.get(f"{arch}.nextn_shared_target_tensors"),
            "types": dict(Counter(t.tname for t in s["tensors"]))}


def sidecars(m):
    """MTP / engram GGUFs published beside the quant (Unsloth: MTP/mtp-*.gguf, engram/*engram*): found in the shard's
    folder, its parent and their MTP/ and engram/ subfolders."""
    d = Path(m.paths[0]).resolve().parent
    seen, mtp, eng = {Path(x).resolve() for x in m.paths}, [], []     # never the file itself
    for dd in (d, d / "MTP", d / "engram", d.parent, d.parent / "MTP", d.parent / "engram"):
        if not dd.is_dir():
            continue
        for p in sorted(dd.iterdir()):
            nm = p.name.lower()
            if p.suffix == ".size" or not p.is_file() or p.resolve() in seen or not (".gguf" in nm):
                continue
            if nm.startswith("mtp-") or "-mtp-" in nm or nm.startswith("mtp_"):
                seen.add(p.resolve())
                mtp.append(_sidecar_head(p))
            elif "engram" in nm:
                seen.add(p.resolve())
                eng.append({"path": str(p), "size": int(Path(str(p) + ".size").read_text().split()[0])
                            if Path(str(p) + ".size").exists() else p.stat().st_size})
    return mtp, eng


def layout_info(m, trunk, present):
    """The publisher's file layout (REPORT 8.2): metadata-only shard 1, layers split across shards, the n-gram table
    as its own shard, MTP inside or as separate files. Info lines: none of these blocks a run by itself."""
    L, info = {}, []
    by_path = {s["path"]: s for s in m.shards}
    n = len(m.paths)
    L["shards"] = n
    L["tensors_per_shard"] = [len(by_path[str(p)]["tensors"]) if str(p) in by_path else None for p in m.paths]
    meta = []
    for p in m.paths:
        s = by_path.get(str(p))
        if s is not None and not s["tensors"]:
            meta.append({"shard": _shard_no(p), "bytes": s["size"], "short_of_data_start": s["data_start"] - s["size"]})
    L["metadata_only"] = meta
    for x in meta:
        info.append(f"shard {x['shard']}/{n} is metadata only (0 tensors, {x['bytes']:,} B"
                    + (f"; it ends {x['short_of_data_start']} B before its aligned data start - the loader fix "
                       "5fde38470 reads it, in both trees" if x["short_of_data_start"] > 0 else "") + ")")
    split = []
    for l in range(trunk):
        sh = OrderedDict()
        for p in ("gate", "up", "down"):
            t = m.tensors.get(f"blk.{l}.ffn_{p}_exps.weight")
            if t is not None:
                sh[p] = _shard_no(m.paths[t.shard])
        if len(set(sh.values())) > 1:
            split.append({"layer": l, "shards": dict(sh)})
    L["split_expert_layers"] = split
    other_split = []
    for l in range(trunk):
        shs = {_shard_no(m.paths[t.shard]) for t in m.tensors.values() if layer_of(t.name) == l}
        if len(shs) > 1 and l not in {x["layer"] for x in split}:
            other_split.append(l)
    L["split_other_layers"] = other_split
    if split:
        info.append("expert layers split across shards: " + "; ".join(
            f"layer {x['layer']} (" + ", ".join(f"{k} in {v}" for k, v in x["shards"].items()) + ")" for x in split)
            + " - iq_pack writes a v4 index with per-role shards (tools/iq_pack.py; the old UD-Q4_K_XL's layer 11 ran so)")
    if other_split:
        info.append(f"layers whose tensors span shards (the cut falls inside the layer; normal for split files): {other_split}")
    ple = m.tensors.get("per_layer_token_embd.weight")
    if ple is not None:
        k = _shard_no(m.paths[ple.shard])
        alone = all(t.shard != ple.shard or t is ple for t in m.tensors.values())
        L["ngram_shard"], L["ngram_alone"] = k, alone
        info.append(f"n-gram table (per_layer_token_embd, {ple.tname}, {(ple.nbytes or 0) / GIB:.2f} GiB) in shard {k}/{n}"
                    + (" ALONE (its own shard: --ple-gguf = that file; the publisher may share it between quants - "
                       "compare its size / sha256 across quants)" if alone else " (with other tensors)"))
    else:
        L["ngram_shard"] = None
        info.append("no n-gram table in this file (a separate engram file goes to --ple-gguf)")
    mtp, eng = sidecars(m)
    L["mtp_sidecars"], L["engram_sidecars"] = mtp, eng
    if present.get("mtp"):
        info.append(f"MTP / nextn IN the file: {present['mtp']}")
    elif mtp:
        info.append("MTP: not in this file; separate MTP GGUF(s) beside it: " + "; ".join(
            f"{Path(x['path']).name} ({x.get('arch')}, block_count {x.get('block_count')}, nextn layer(s) "
            f"{x.get('layers')}, {x.get('tensors')} tensors, {x.get('size', 0) / 1e9:.2f} GB, "
            + ("shared: no token_embd/output - takes them from the main model" if not x.get("has_embd_head")
               else f"standalone: own {', '.join(x['has_embd_head'])}") + ")" for x in mtp)
            + " -> work/qwen4-kit/mtp_from_gguf.py converts one to our rt format (BF16 for an exact drafter)")
    else:
        info.append("MTP: not in this file and no mtp-*.gguf beside it: the drafter comes from the checkpoint "
                    "(tools/mtp_fetch.py -> mtp_pack.py -> mtp_rt.py) or a publisher's MTP GGUF "
                    "(work/qwen4-kit/mtp_from_gguf.py)")
    if eng:
        info.append("engram (n-gram table) sidecars beside it: " + ", ".join(
            f"{Path(x['path']).name} ({x['size'] / 1e9:.1f} GB)" for x in eng) + " (a later --ple-gguf A/B)")
    L["info"] = info
    return L


# =====================================================================================================================
# 4. The fit (Karl's quant rule) and the tier split / decode model (UPGRADE-ESTIMATE.md sections 8-9)
# =====================================================================================================================
def is_mtp(name, trunk):
    lay = layer_of(name)
    return "nextn" in name or name.startswith("mtp.") or (lay is not None and trunk and lay >= trunk)


def sizes(m, E):
    """Bytes per part, from the tensor table (fitplan.py's accounting: the pack's BF16/F32 forms for FORM roles)."""
    trunk = trunk_of(m)
    n_exp = ai(m, "expert_count")
    blobs, per_exp_params = [], []
    for l in range(trunk):
        ts = [m.tensors.get(f"blk.{l}.ffn_{p}_exps.weight") for p in ("gate", "up", "down")]
        if not all(ts) or not n_exp or any(t.nbytes is None for t in ts):
            continue
        b = sum(t.nbytes // n_exp for t in ts) + (16 if any(t.type == 40 for t in ts) else 0)
        blobs.append((b + 255) // 256 * 256)
        per_exp_params.append(sum(t.n // n_exp for t in ts))
    exp_b = sum(blobs) * n_exp
    dense_gpu = embed = ple = mtp = vision = 0
    dense_params = 0
    for t in m.tensors.values():
        n = t.name
        if n.endswith(("_exps.weight", "_exps.scale")) and not is_mtp(n, trunk):
            continue
        nb = t.nbytes or 0
        if n.startswith(("v.", "mm.")):
            vision += nb
            continue
        if is_mtp(n, trunk):
            mtp += nb
            continue
        if n == "per_layer_token_embd.weight":
            ple += nb
            continue
        if n == "token_embd.weight":
            embed += nb
            continue
        form = E["form"].get(re.sub(r"^blk\.\d+\.", "", n))
        if form in ("BF16", "F16") and len(t.shape) >= 2 and t.tname != form and not (n.endswith("ple_key.weight") and t.tname in E["native_ple_key"]):
            nb = t.n * 2
        elif form == "F32" and t.tname != "F32":
            nb = t.n * 4
        dense_gpu += nb
        dense_params += t.n
    top_k = ai(m, "expert_used_count")
    active = dense_params + top_k * sum(per_exp_params)
    return {"trunk": trunk, "n_expert": n_exp, "top_k": top_k, "experts": exp_b, "blobs": blobs,
            "blob_mean": (sum(blobs) / len(blobs)) if blobs else 0, "blob_max": max(blobs) if blobs else 0,
            "dense_gpu": dense_gpu, "embed": embed, "ple": ple, "mtp_infile": mtp, "vision": vision,
            "active_params": active, "dense_params": dense_params, "routed_params": active - dense_params,
            "expert_elems": sum(per_exp_params) * n_exp}


def kv_cell_bytes(m, kv="int8"):
    """K/V bytes per context cell: full-attention layers x KV heads x (K + V). int8 = 2 x head_dim values + an fp16 scale
    per 64 values each (fitplan.py); fp16 = 4 bytes a value pair. Without full_attention_interval every layer counts."""
    trunk = trunk_of(m)
    fai = ai(m, "full_attention_interval")
    n_attn = trunk // fai if fai > 0 else trunk
    kvh = ai(m, "attention.head_count_kv")
    hd = ai(m, "attention.key_length") or (ai(m, "embedding_length") // max(1, ai(m, "attention.head_count", 1)))
    per = 2 * hd + 2 * 2 * (hd // 64) if kv == "int8" else 4 * hd
    return n_attn * kvh * per, n_attn


def budget(P, s_new, s_ref, kv_new, kv_ref, drafter_new):
    """Expert room today (GiB), every input explicit (UPGRADE-ESTIMATE 7.3 / 8.2 and fitplan.py's calibration):
       5080:     vram_main - overhead (CUDA context, scratch, GDN state, Flash-Next's drafter) - dense weights on the GPU
                 - the resident K/V - the reserve - the draft head - (this drafter - Flash-Next's)
       helpers:  each card's free VRAM before the arena - the 512 MiB the engine keeps free
       RAM tier: MemTotal - the MemAvailable floor - everything else (measured at the 64 GiB splice arms' guard stop:
                 engine, pinned K/V, chat cache, OS + desktop + the daily services; adjusted here for this model's K/V,
                 embedding table and the chat-cache cap) - headroom (so today's inputs give the 58 GiB tier that ran clean)"""
    ctx, kres = P.ctx, P.kv_resident
    kv_vram = min(ctx, kres or ctx) * kv_new
    kv_host = ctx * kv_new
    kv_host_ref = 131072 * kv_ref
    main = (P.vram_main_mib * MIB - P.overhead_main_gib * GIB - s_new["dense_gpu"] - kv_vram
            - (P.reserve_mib + P.draft_head_mib) * MIB - (drafter_new - P.drafter_ref_gib * GIB))
    helpers = [max(0.0, h[0] * GIB - P.helper_keep_mib * MIB) for h in P.helpers]
    other = (P.other_gib * GIB - kv_host_ref + kv_host + (s_new["embed"] - s_ref["embed"])
             + (P.chat_cache_gib - P.chat_cache_ref_gib) * GIB)
    ram = P.memtotal_gib * GIB - P.floor_gib * GIB - other - P.headroom_gib * GIB
    return {"main": max(0.0, main), "helpers": helpers, "ram": max(0.0, ram), "other": other, "kv_vram": kv_vram,
            "kv_host": kv_host, "total": max(0.0, main) + sum(helpers) + max(0.0, ram)}


def tiers(s, B, P, C, ratio):
    """Section 8's centre case + range (scratch-estimate/qwen4.py) and section 9's helper work (lc_placement.py), on
    this model's numbers. The miss curve (the splice's main-only fit, 24,576 experts) is used at the same FRACTION of
    the experts held (N x 24,576 / experts): an assumption for another expert count."""
    a2, b2 = C["splice_fit_off"]
    as_, bs = C["ssd_fit"]
    NE = s["trunk"] * s["n_expert"]
    blob = s["blob_mean"]
    if not NE or not blob:
        return None
    sc = 24576 / NE
    miss = lambda N: min(1.0, math.exp(a2) * max(1.0, N * sc) ** b2)  # noqa: E731
    Nm = int(B["main"] // blob)
    Nh = [int(h // blob) for h in B["helpers"]]
    N = min(NE, Nm + sum(Nh))
    all_in_ram = s["experts"] <= B["ram"]
    Nram = NE if all_in_ram else min(NE - N, int(B["ram"] // blob))
    cold = 0.0 if all_in_ram else max(0.0, (NE - N - Nram) / NE)
    R = s["trunk"] * s["top_k"] * 1.25                      # routed experts per token (window rows ~1.25; Flash-Next 600)
    smb = blob / 1e6
    gain = miss(Nm) - miss(N)
    out = {"slots_main": Nm, "slots_helpers": Nh, "slots_ram": Nram if not all_in_ram else "all (arena)", "NE": NE,
           "cold_frac": cold, "R": R, "expert_mb": smb, "compute_ratio": ratio}
    f = 1.0                                                 # RAM speed factor (96 GB at 6000)
    cases = {}
    for name, (g, sh, cc, ser, ov) in {
            "centre": (1 - miss(Nm) + P.helper_eff * gain, math.exp(as_) * cold ** bs if cold > 0 else 0.0, P.cpu_us / 1000,
                       P.serial_ms * ratio, 0.4),
            "best": (min(0.97, 1 - miss(Nm) + 0.85 * gain), 0.0511 * (cold / 0.194) ** 1.6 if cold > 0 else 0.0, 0.055,
                     1.9 * ratio, 0.2),
            "worst": (1 - miss(Nm) + 0.55 * gain, 0.0511 * (cold / 0.194) ** 1.0 if cold > 0 else 0.0, 0.079,
                      2.5 * ratio, 0.6)}.items():
        sh = min(sh, max(0.0, 1 - g))
        comp = ser + R * 0.78 * (1 - g) * cc * (smb / 4.0) * f + ov
        ssd = (2.33 + 0.80 * R * sh * (smb / 3.1)) if sh > 0 else 0.0
        t = (comp ** 4 + ssd ** 4) ** 0.25
        cases[name] = {"gpu": g, "ssd": sh, "ms": t, "tok_s": 1000 / t, "ssd_mb_tok": R * sh * smb, "compute_ms": comp,
                       "ssd_ms": ssd}
    c = cases["centre"]
    out["split"] = {"main": 1 - miss(Nm), "helpers": P.helper_eff * gain, "pcie_ram": 0.22 * max(0.0, 1 - c["gpu"] - c["ssd"]),
                    "cpu_ram": 0.78 * max(0.0, 1 - c["gpu"] - c["ssd"]), "ssd": c["ssd"]}
    # section 9: each helper's entries / token and its exposed wait (explicit counts: the stripe deal alternates until the
    # smaller card is full, then the rest goes to the larger; a helper slot = helper_eff of a main slot)
    hw = []
    if Nh:
        order = sorted(range(len(Nh)), key=lambda i: Nh[i])
        lo = Nm
        mass = lambda a, b: miss(lo + a) - miss(lo + b)  # noqa: E731
        if len(Nh) == 1:
            shares = [mass(0, Nh[0])]
        else:
            small = Nh[order[0]]
            shares = [0.0] * len(Nh)
            per = mass(0, small * len(Nh)) / len(Nh)
            for i in range(len(Nh)):
                shares[i] = per
            shares[order[-1]] += mass(small * len(Nh), sum(Nh))
        for i, sh_ in enumerate(shares):
            ent = R * P.helper_eff * sh_
            ms = ent * smb / P.helpers[i][1]                    # MB / (GB/s) = ms
            hw.append({"entries_tok": ent, "ms_tok": ms, "wait_ms": 0.26 * ms})
    out["helper_work"] = hw
    out["cases"] = cases
    return out


# =====================================================================================================================
# 5. Day-one pieces: config (P028x as the template), test parameters, command sequence
# =====================================================================================================================
MACHINE_ENV = ("STRATA_IO_THREADS", "CUDA_MODULE_LOADING", "CUDA_VISIBLE_DEVICES")
# fitplan.py LOSSLESS_ENV (the stock config's pins, 10-27) + g17_rules.py PINS (v0.2.10's new defaults off, 11-02)
LOSSLESS_ENV = {"STRATA_ROUTE_TAIL_SKIP": "0", "STRATA_ADAPT_ASYNC": "0", "STRATA_PREFILL_CPU_SHARE": "0",
                "STRATA_DEFAULTS": "026", "STRATA_ROUTE_PRIOR": "0", "STRATA_PROMPT_ATTN_IMMA": "0", "STRATA_GR_V3": "0",
                "STRATA_PREFILL_LAYER_MAJOR": "0", "STRATA_PLE_AUTO_RAM": "0"}
V0210_PINS = {"STRATA_LOOKUP_MAX_T": "0", "STRATA_GDN_TC": "0", "STRATA_GDN_CONVL2": "0", "STRATA_GR_V3_PF": "0",
              "STRATA_GR_R2": "0", "STRATA_SMALL_UNR": "0", "STRATA_QSA_FUSE_NR": "0", "STRATA_IL_PAD": "0",
              "STRATA_DF_PDL": "0", "STRATA_PCIE_START": "old", "STRATA_ARENA_RAM_FALLBACK": "0", "STRATA_MTP_KEEP": "1",
              "STRATA_SPILL_OFF": "1", "STRATA_PENALTY_PROMPT": "1"}
SERIES_ENV_WHY = "our series' switch or a Flash-Next-tuned value: only after the port (its guards and gates)"


def profile_for(path, s):
    """(path or None, note): a STRP expert profile (bringup/fitplan.py read_profile: "STRP", version, layers, experts,
    ...) is used only when its layers x experts shape is this model's; only its 24-byte header is read."""
    if not path or not Path(path).exists():
        return None, "no expert profile given"
    with open(path, "rb") as f:
        raw = f.read(24)
    if len(raw) < 24 or raw[:4] != b"STRP":
        return None, f"{path}: not a STRP profile"
    _ver, nl, ne, _want, n = struct.unpack("<5I", raw[4:24])
    if (nl, ne) != (s["trunk"], s["n_expert"]):
        return None, f"{Path(path).name} is for {nl} x {ne}, the model is {s['trunk']} x {s['n_expert']}: not used"
    return str(path), f"{Path(path).name}: {n} ranked pairs for {nl} x {ne}"


# measured points the tier / decode model is checked against (when such a file is in the run)
MEASURED = {
    "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf":
        ("P028x screen, 5080 + 4060 Ti (UPGRADE-ESTIMATE.md 6.5, fn_tiers.py): main 63.0 %, 4060 Ti 17.4 %, PCIe 5.5 %, "
         "CPU 14.1 %; 158.9 tok/s engine clock (client ~0.97x)", 158.9),
    "Qwen3.8-Flash-Next-r15splice-Q5experts-IQ3S.gguf":
        ("splice58 on-100, 2,371 + 1,893 slots, 58 GiB tier (UPGRADE-ESTIMATE.md 4.1): main 54.2 %, 4060 Ti 10.6 %, "
         "PCIe 7.8 %, CPU 22.3 %, SSD 5.1 %; 37.3 tok/s", 37.3),
}


_FAMILIES = {}


def P_family(m):
    return _FAMILIES.get(m.arch, "?")


def tpl_arg(tpl, flag):
    a = tpl.get("args") or []
    return a[a.index(flag) + 1] if flag in a[:-1] else None


def make_swap_config(name, m, s, fitres, B, P, tpl, sm, need_compat, s_ref=None):
    """The same-model swap (REPORT 8.4): configs/P028x.json as it is, with only the three model paths swapped
    (--pack, --native = shard 1, --ple-gguf = the n-gram table's shard). The series' switches, the drafter, the
    expert profile, the helper slot count and the 12 GiB chat cache stay: same shapes and tokenizer, so they apply.
    Two bookkeeping fields change so a test cannot touch the served instance: "log" (not logs/engine-P028x.log) and
    "fallback" (dropped: a failed helper check must stop the test, not start Cstar18-single's model)."""
    paths, at = final_paths(m, P)
    ple_t = m.tensors.get("per_layer_token_embd.weight")
    pack = WS / f"bringup/out/{name}/pack"
    cfg = json.loads(json.dumps(tpl), object_pairs_hook=OrderedDict)
    args = cfg["args"]
    swapped = OrderedDict()
    for flag, new in (("--pack", str(pack)), ("--native", paths[0]),
                      ("--ple-gguf", paths[ple_t.shard] if ple_t is not None else None)):
        if flag in args[:-1] and new is not None:
            i = args.index(flag) + 1
            swapped[flag] = [args[i], new]
            args[i] = new
    changed = OrderedDict()
    old_log = cfg.get("log")
    cfg["log"] = str(WS / f"logs/engine-{name}.log")
    changed["log"] = [old_log, cfg["log"], "a test must not write into the served instance's log"]
    if "fallback" in cfg:
        changed["fallback"] = [cfg.pop("fallback"), None, "a failed helper check must stop the test, not start another model"]
    helpers = fitres.get("room_helpers_gib") or []
    hslots = tpl_arg(tpl, "--expert-cache-device1")
    checks = []
    if hslots and helpers:
        need = int(hslots) * s["blob_mean"] / GIB
        was = int(hslots) * s_ref["blob_mean"] / GIB if s_ref else None
        checks.append(f"--expert-cache-device1 {hslots} (kept, a count) x {s['blob_mean'] / MIB:.2f} MiB mean blob = {need:.2f} GiB"
                      + (f" (the served file: {was:.2f} GiB; the profile decides which experts go there - P028x logs 6.21)"
                         if was is not None else "")
                      + f" vs the helper's {helpers[0]:.2f} GiB: "
                      + ("fits" if need <= helpers[0] else "MAY NOT FIT - check the helper's arena line at the first start"))
    cc = tpl_arg(tpl, "--chat-cache-mib")
    if cc:
        extra = int(cc) / 1024 - P.chat_cache_gib
        mg = fitres["room_total_gib"] - fitres["experts_gib"] - max(0.0, extra)
        checks.append(f"--chat-cache-mib {cc} (kept) is {extra:.1f} GiB more than the fit's {P.chat_cache_gib:g} GiB: margin "
                      f"{mg:.2f} GiB{' (TIGHT)' if mg < 2 else ''}")
    tok = cfg.get("tokenizer")
    cfg["_comment"] = (f"{name}: same-model swap of {Path(paths[0]).name}, written by work/qwen4-kit/day1.py "
                       f"{datetime.date.today()}: configs/P028x.json with only --pack / --native / --ple-gguf swapped "
                       "(+ log, fallback: see _day1). Same shape keys and tokenizer as the served file, so the series' "
                       "switches, the drafter and the helper count apply. NOT RUN.")
    cfg["_day1"] = OrderedDict([
        ("mode", "same-model swap (P028x + three paths)"),
        ("swapped", swapped), ("changed", changed),
        ("kept", ["exe", "server", "env (every switch)", "--mtp " + str(tpl_arg(tpl, "--mtp")),
                  "--expert-profile", "--expert-cache-device1 " + str(hslots), "--chat-cache-mib " + str(cc),
                  "tokenizer " + str(tok) + " (same tokenizer: tokens / merges / special ids equal)", "port", "vision"]),
        ("checks", checks), ("warnings", sm["warnings"]),
        ("files_at", at or "the given paths" + (" - HEADER FILES: rerun with --files-at DIR (where the download lands)"
                                                 if m.head_only else "")),
        ("pack", f"nice -n 5 .venv/bin/python -I -B {Path(tpl['server']).parents[1] / 'tools/iq_pack.py'} --gguf {paths[0]} "
                 f"--out {pack}" + (" --compat-bf16" if need_compat else ""))])
    if not sm["template_same"]:
        cfg["_day1"]["warnings"].append("the template differs: the kept tokenizer dir renders P028x's template - set "
                                        f"\"tokenizer\" to {pack}/tokenizer if the new template is wanted")
    shared = OrderedDict([("reasoning_effort", "medium"), ("temperature", 1.0), ("top_p", 0.95), ("top_k", 20)])
    sp = TEMPLATE_CFG.with_name(TEMPLATE_CFG.stem + ".shared-settings.json")
    if sp.exists():
        shared = json.loads(sp.read_text(encoding="utf-8-sig"), object_pairs_hook=OrderedDict)
    return cfg, shared


def make_config(name, m, s, fitres, B, P, tpl):
    a = m.a
    shards = [Path(x) for x in final_paths(m, P)[0]]
    ple_t = m.tensors.get("per_layer_token_embd.weight")
    pack = WS / f"bringup/out/{name}/pack"
    ctx = min(P.ctx, ai(m, "context_length") or P.ctx)
    args = ["--pack", str(pack), "--native", str(shards[0])]
    if ple_t is not None:
        args += ["--ple-gguf", str(shards[ple_t.shard])]
    prof, prof_note = profile_for(P.expert_profile, s)
    if prof:
        args += ["--expert-profile", prof]
    args += ["--expert-cache", "auto", "--prefill", "auto:16384"]
    if P.mtp:
        args += ["--spec", "7", "--spec-min-p", "0.5", "--mtp", P.mtp]
    args += ["--max-context", str(ctx), "--kv", P.kv, "--kv-resident", str(P.kv_resident)]
    if ple_t is not None:
        args += ["--ple-inflight", "128"]
    args += ["--vram-reserve-mib", str(P.reserve_mib), "--chat-cache", "16", "--chat-cache-mib",
             str(int(P.chat_cache_gib * 1024))]
    hs = fitres["tiers"]["slots_helpers"] if fitres.get("tiers") else []
    for i, n in enumerate(hs):
        args += [f"--expert-cache-device{i + 1}", str(n)]
    args += ["--conversation-cache-mib", "0"]
    if s["experts"] > B["ram"]:
        args += ["--resident-budget-gib", str(int(B["ram"] / GIB))]
    env, dropped = {}, {}
    for k, v in (tpl.get("env") or {}).items():
        if k in MACHINE_ENV:
            env[k] = v
        elif k not in LOSSLESS_ENV and k not in V0210_PINS:
            dropped[k] = v
    env.update(LOSSLESS_ENV)
    env.update(V0210_PINS)
    cfg = OrderedDict()
    cfg["exe"] = P.exe or "<SET: the Qwen4 release's stock engine (built for 89;120); day one runs the stock build>"
    cfg["args"] = args
    cfg["cwd"] = str(WS / f"bringup/out/{name}")
    cfg["tokenizer"] = P.tokenizer_dir or str(pack / "tokenizer")
    cfg["model_name"] = f"strata-{name}"
    cfg["log"] = str(WS / f"logs/engine-{name}.log")
    for k in ("lib_dirs", "port", "sampling", "host"):
        if k in tpl:
            cfg[k] = tpl[k]
    cfg["port"] = 8081
    cfg["env"] = env
    cfg["server"] = P.server or "<SET: the release tree's serve/server.py>"
    for k in ("web_search", "mcp"):
        if k in tpl:
            cfg[k] = tpl[k]
    cfg["tool_call_recovery"] = False
    cfg["_comment"] = (f"{name}: Qwen4 day one, written by work/qwen4-kit/day1.py {datetime.date.today()} from the headers of "
                       f"{shards[0].name}, with configs/P028x.json as the template (read-only). Stock build, lossless pins "
                       "(fitplan LOSSLESS_ENV + v0.2.10's 14 pins), our series' switches dropped, no --vision, no fallback, "
                       "test port 8081, explicit helper slots (UPGRADE-ESTIMATE 9.3). NOT RUN.")
    cfg["_day1"] = {"dropped_env": {k: [v, SERIES_ENV_WHY] for k, v in dropped.items()},
                    "dropped_args": ["--vision (no Qwen4 projector yet)",
                                     "--expert-cache-device1 3300 -> this model's count from the fit"] +
                    ([] if P.mtp else ["--spec / --spec-min-p / --mtp (no drafter given: --mtp DIR)"]) +
                    ([] if prof else [f"--expert-profile ({prof_note}; pf_yardstick / quant_quality need one of this "
                                      "shape)"]),
                    "set_before_running": [x for x, ok in (("exe", P.exe), ("server", P.server)) if not ok],
                    "files_at": final_paths(m, P)[1] or ("the given paths" + (" - HEADER FILES: rerun with --files-at DIR "
                                                                          "(where the download lands)" if m.head_only else ""))}
    fam = P_family(m)
    if fam != "Qwen4Exp":
        cfg["_day1"]["warning"] = (f"{m.arch} runs on the {fam} path, not Flash-Next's: these args follow the qwen4exp "
                                   "layout (pack, --native, --ple-gguf). Take that path's flags from the release (setup.py "
                                   "--family, bringup/inspect_model.py: qwen35moe = no pack, tokenizer only, --mtp N = drafts "
                                   "per step) before using this file.")
    shared = OrderedDict([("reasoning_effort", "medium"), ("temperature", 1.0), ("top_p", 0.95), ("top_k", 20)])
    return cfg, shared


def prompt_lengths():
    """Flash-Next token counts of the frozen prompt files (what exact7 / pf_yardstick / run.sh read)."""
    out = OrderedDict()
    for p in sorted(PROMPTS.glob("*.tokens")) + sorted(PROMPTS.glob("*.prompt")):
        out[p.name] = sum(1 for x in p.read_text().replace("\n", ",").split(",") if x.strip())
    return out


def make_params(name, m, s, tk, tcmp, fitres, B, P, E, swap=None, tie=None):
    """The model-specific inputs of every day-one test, in one place. swap = the served config (same-model swap)."""
    ctx = min(P.ctx, ai(m, "context_length") or P.ctx)
    shards = final_paths(m, P)[0]
    pin = int(0.7 * B["main"] / s["blob_max"]) // 50 * 50 if s["blob_max"] else None
    same_tok = tcmp[0]["tokens_sha"] and tcmp[0]["merges_sha"] and tcmp[0]["special_ids"]
    pdir = str(PROMPTS) if same_tok else str(WS / f"bringup/out/{name}/prompts")
    mtp_dir = (tpl_arg(swap, "--mtp") if swap else None) or P.mtp
    prof = (tpl_arg(swap, "--expert-profile"), "the served config's profile (same shape)") if swap else \
        profile_for(P.expert_profile, s)
    return OrderedDict([
        ("name", name), ("mode", "same-model swap (configs/P028x.json + three paths)" if swap else "stock (new model)"),
        ("tie", tie), ("arch", m.arch), ("files", shards), ("general.name", m.get("general.name")),
        ("served_context", ctx), ("model_context_length", m.a("context_length")),
        ("chat_template", {"sha": tk["template_sha"], "markers": tk["template_markers"], "efforts": tk["efforts"],
                           "effort_default": tk["effort_default"], "effort_aliases": tk["effort_aliases"],
                           "thinking_off_kwarg": "chat_template_kwargs.enable_thinking" if tk["thinking_off"] else None,
                           "developer_role": tk["developer_role"], "tool_format": tk["tool_format"],
                           "same_as_flash_next": tcmp[0]["template_sha"]}),
        ("tokenizer", {"vocab": tk["vocab"], "same_as_flash_next": same_tok, "tokens_sha": tk["tokens_sha"],
                       "merges_sha": tk["merges_sha"], "eos": tk["eos"], "bos": tk["bos"], "pad": tk["pad"],
                       "think_tags": {k: tk["marker_ids"].get(k) for k in ("<think>", "</think>")},
                       "turn_token": tk["marker_ids"].get("<|im_start|>"),
                       "engine_flags": ([] if tk["marker_ids"].get("<|im_start|>") == 248045 else
                                        [f"--turn-token {tk['marker_ids'].get('<|im_start|>')}"])}),
        ("prompts", {"dir": pdir, "retok_needed": not same_tok, "lengths_flash_next_tokens": prompt_lengths(),
                     "note": "the frozen prompt files are Flash-Next token ids with the template applied; with another "
                             "tokenizer: day1.py retok, then PROMPT_DIR= for exact7/run.sh, day1.py pfy/kr3 for the KL rules; "
                             "the tf-*.text.nll baselines are Flash-Next's (recompute)"}),
        ("drafter", {"mtp_dir": mtp_dir, "in_file_nextn_bytes": s["mtp_infile"],
                     "note": ("same model: our drafter (strata-v0115/mtp/rt, from Qwen's checkpoint) applies unchanged" if swap
                              else "the qwen4exp path takes the drafter from --mtp DIR (tools/mtp_pack.py + mtp_rt.py of the "
                              "release, or a publisher's MTP GGUF via work/qwen4-kit/mtp_from_gguf.py); without one, run "
                              "--spec off and say so in the speed numbers")}),
        ("expert_profile", {"path": prof[0], "check": prof[1],
                            "shape": [s["trunk"], s["n_expert"]],
                            "note": "a STRP profile of this layers x experts shape (the release's data/expert-profile.bin); "
                                    "without one the cache fills in a layer-interleaved order"}),
        ("exact7", {"PIN_CACHE": pin, "REF": f"{name}-e7a (its own first run: no older hashes apply)",
                    "EVICT_GLOB": " ".join(shards), "PROMPT_DIR": pdir,
                    "note": "--expert-cache N is a byte budget (N x the LARGEST blob) capped by free VRAM: 70 % of the "
                            "5080's room in largest blobs, as Flash-Next's pin 2500 is 71 % of its 3,527 (exact7.sh, gap 8); "
                            "both runs must print MATCHED"}),
        ("kl", {"reference": P.kl_ref or "published: the quant publisher's KLD / top-1 table for this file (record the "
                                         "number and its source here)",
                "local_reference_config": P.kl_ref_config,
                "pf_yardstick": "long40 (40 cuts, 2K-32K tokens) through day1.py pfy with PROMPT_DIR; top-1 / KL mean / "
                                "median / max vs the reference run",
                "kernel_rules": "kernel_rule2 + kernel_rule3 (NLL) compare BUILDS of this model (a port vs its stock "
                                "release) against the model's own rounding references (unfused = STRATA_PF_FUSED=0, "
                                "cpushare = STRATA_PREFILL_CPU_SHARE=0.4): after the port, not on day one",
                "quant_quality": "tools/quant_quality.py ids --tokenizer <pack>/tokenizer, then run / compare vs a Q8_0 run"}),
        ("screen", {"workloads": ["W1-think", "W2-code", "W3-research", "A-edit", "B-write", "R1-verify20k",
                                  "R2-report54k", "R3-extract5k", "R4-agent33k"],
                    "effort": "medium" if "medium" in tk["efforts"] or not tk["efforts"] else tk["efforts"][0],
                    "note": "frozen messages (model-agnostic text); token lengths change with the tokenizer - R2 (~54K "
                            "Flash-Next tokens) must fit the served context; abrun.py sends reasoning_effort and "
                            "chat_template_kwargs.enable_thinking=false: both must be names this template takes"}),
        ("bp90", {"gguf_for_fixture_text": str(REF_GGUF), "tree_for_fixture_template": str(WS / "strata-r22p021m"),
                  "note": "Basalt's fixtures are Flash-Next ids: keep --gguf / --tree at Flash-Next's to decode them; with "
                          "another tokenizer every 'PROMPT TOKENS != expected' line is expected and pp16k / pp64k are "
                          "no longer 16,384 / 65,536 of this model's tokens"}),
        ("speed_target_tok_s", [40, 60]),
        ("sampling", {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}),
    ])


def make_commands(name, m, s, fitres, B, P, params, cfg_path, need_compat, tools, swap=None):
    shards = final_paths(m, P)[0]
    L = []
    w = L.append
    w(f"# Day one for {name} ({m.get('general.name')}, {Path(shards[0]).name}) - written by work/qwen4-kit/day1.py "
      f"{datetime.date.today()}.")
    w("# NOT a script: run each step by hand, in order, after Karl's go. GPU steps hold tmp/gpu-test.lock (with_server.sh")
    w("# takes it; the CLI steps take it with flock -s). Test port 8081; 8080 goes down by Karl's decision first.")
    w("WS=/home/USER/ai-speed-testing/strata-compare; P=$WS/.venv/bin/python; K=$WS/work/qwen4-kit/day1.py")
    w(f"CFG={cfg_path}")
    if swap:
        w(f"REL={Path(swap['server']).parents[1]}        # the served tree: same model, so its tools and engine apply")
    else:
        w("REL=<the Qwen4 release's worktree>        # stock build of the release that adds Qwen4 (engine path = cfg exe)")
    w(f"OUT=$WS/results/qwen4-kit/{name}; mkdir -p $OUT")
    if swap:
        w(f"# MODE: same-model swap - $CFG is {TEMPLATE_CFG.name} with only --pack / --native / --ple-gguf swapped (+ log,")
        w("#       fallback); every switch, the drafter and the helper count apply: compare each number with P028x's")
    if params.get("tie"):
        w("# TIE under Karl's rule (equal expert bytes): QUALITY DECIDES - step 3 runs the KL / NLL of every tied file")
        w(f"#     against ONE reference and the lower KL wins; the list order is not a choice. Tied: {', '.join(params['tie'])}")
    w(f"export PROMPT_DIR={params['prompts']['dir']} EVICT_GLOB=\"{' '.join(shards)}\"")
    w("")
    w("# 0. no GPU: this report (headers), then the files: bringup/fetch_model.py pins / heads / plan / unit (>= 100 GB")
    w("#    free after, sha256 against the pins); kcheck before the first GPU step:  $WS/bringup/lib/kcheck.sh q4d1-pre")
    w(f"#    gap: work/r22/port_gap4.sh begin \"Qwen4 day one {name}\"   (Karl decides when 8080 goes down)")
    if P_family(m) != "Qwen4Exp":
        w(f"# NOTE: {m.arch} runs on the {P_family(m)} path: no iq_pack pack there; build the config from the release's "
          "own flags first (see the config's _day1.warning)")
    w("# 1. the pack (CPU, no GPU; ~1.5-5 GB written):")
    w(f"nice -n 5 $P -I -B $REL/tools/iq_pack.py --gguf {shards[0]} --out $WS/bringup/out/{name}/pack"
      + (" --compat-bf16" if need_compat[0] else ""))
    if need_compat[0]:
        w("#    --compat-bf16: quantized float-form tensors are rounded to BF16 (iq_pack records each in conversions.json)")
    elif need_compat[1]:
        w("#    F32 tensors the engine reads as BF16: exact if their values are BF16, else iq_pack refuses with a message;")
        w("#    then rerun with --compat-bf16 (a rounding: record it)")
    for t in tools:
        w(f"#    + {t}")
    if params["prompts"]["retok_needed"]:
        w("# 1b. another tokenizer: re-tokenize the frozen prompts (CPU; pure-Python BPE, minutes for the 120K files)")
        w(f"nice -n 19 $P -I -B $K retok --new-gguf {shards[0]} --out {params['prompts']['dir']}")
    w("# 2. Strata run (CLI smoke + exact7 twice = repeatable at matched slots):")
    w(f"flock -s $WS/tmp/gpu-test.lock $WS/bringup/lib/run.sh {name}-smoke $CFG math 256; $WS/bringup/lib/kcheck.sh q4d1-smoke")
    pin = params["exact7"]["PIN_CACHE"]
    w(f"PIN_CACHE={pin} flock -s $WS/tmp/gpu-test.lock $WS/bringup/lib/exact7.sh {name}-e7a $CFG")
    w(f"PIN_CACHE={pin} REF={name}-e7a flock -s $WS/tmp/gpu-test.lock $WS/bringup/lib/exact7.sh {name}-e7b $CFG"
      "   # 7/7 + MATCHED")
    w("# 3. KL vs the reference (published table first; a local reference only if a larger quant is on disk):")
    w(f"flock -s $WS/tmp/gpu-test.lock $P $WS/bringup/lib/guard.py pfy-{name} -- $P -I -B $K pfy $PROMPT_DIR -- run $CFG "
      f"$OUT/pfy/{name} --set long40")
    if P.kl_ref_config:
        w(f"flock -s $WS/tmp/gpu-test.lock $P $WS/bringup/lib/guard.py pfy-ref -- $P -I -B $K pfy $PROMPT_DIR -- run "
          f"{P.kl_ref_config} $OUT/pfy/ref --set long40")
        w(f"$P -I -B $K pfy $PROMPT_DIR -- compare $OUT/pfy/ref $OUT/pfy/{name}")
        if params.get("tie") and swap:
            w(f"#    the tie: the served file against the same reference (its config is {TEMPLATE_CFG}):")
            w(f"flock -s $WS/tmp/gpu-test.lock $P $WS/bringup/lib/guard.py pfy-served -- $P -I -B $K pfy $PROMPT_DIR -- run "
              f"{TEMPLATE_CFG} $OUT/pfy/served --set long40")
            w("$P -I -B $K pfy $PROMPT_DIR -- compare $OUT/pfy/ref $OUT/pfy/served")
    else:
        w(f"#    local reference config: none given (--kl-ref-config); record the published KLD in $OUT/params.json")
        if params.get("tie"):
            w("#    the tie needs a LOCAL reference run for every tied file (published KLDs are on the publisher's data, not")
            w("#    comparable across publishers): rerun day1.py check with --kl-ref-config <a larger local quant's config>")
    if params.get("tie"):
        w("#    + the text NLL of each tied file on the frozen corpus (tf-corpus.text; Karl's v3.1 gap: work/r23/gap-ud31.sh)")
    w("#    upstream's yardstick (decode windows, vs a Q8_0 run when one exists):")
    w(f"#    $P -I -B $REL/tools/quant_quality.py ids --tokenizer $WS/bringup/out/{name}/pack/tokenizer --out $OUT/qq.ids.json")
    w(f"#    $P -I -B $REL/tools/quant_quality.py run --config $CFG --ids $OUT/qq.ids.json --out $OUT/qq-{name}.tsv")
    w("# 4. the graded set (suite quick, effort medium):")
    eff = params["screen"]["effort"]
    w(f"$WS/bringup/lib/with_server.sh q4d1-suite $CFG -- \"$WS/suite/run.sh --label {name}-{eff} --endpoint "
      f"http://127.0.0.1:8081 --mode quick --extra-body '{{\\\"reasoning_effort\\\": \\\"{eff}\\\"}}'\"; $WS/bringup/lib/kcheck.sh q4d1-suite")
    w("# 5. speed (Karl's target 40-60 tok/s decode): the 9-workload screen, 3 passes, then Basalt's cold fixtures:")
    w("EL=$($P -c \"import json; print(json.load(open('$CFG'))['log'])\"); touch $EL")
    for k in (1, 2, 3):
        w(f"off=$(stat -c %s $EL); $WS/bringup/lib/with_server.sh q4d1-s{k} $CFG -- \"bash $WS/work/r22/abarm.sh "
          f"http://127.0.0.1:8081 $off $OUT/speed s{k} s{k}n=normal:1:W1,W2,W3 s{k}a=agent:1 s{k}r=research4:1\"; "
          f"$WS/bringup/lib/kcheck.sh q4d1-s{k}")
    if swap:
        w(f"#    swap: the same three passes on {TEMPLATE_CFG} in this gap (labels p1..p3, interleaved with s1..s3) give the")
        w("#    no-loss comparison (the series' screen rule); both arms' start lines must show T 1.0 / 0.95 / 20 / min-p 0.05")
    w("$P -I -B /home/USER/ai-speed-testing/basalt-ab/scripts/abreport.py --dir $OUT/speed s1n s1a s1r s2n s2a s2r s3n s3a "
      "s3r > $OUT/speed/table.md")
    w("mkdir -p $OUT/bp90   # Basalt's cold fixtures: a fresh engine per pass (gap 17's bprun)")
    for k in (1, 2, 3):
        w(f"$WS/bringup/lib/with_server.sh q4d1-bp{k} $CFG -- \"$P -I -B $WS/work/r22/basalt-pr90/bp90_client.py "
          f"http://127.0.0.1:8081 --label {name} --sets decode,pp16k,pp64k --passes 1 --first-pass {k} --tree "
          f"$WS/strata-r22p021m --gguf {REF_GGUF} --out $OUT/bp90/cold-H.jsonl\"; $WS/bringup/lib/kcheck.sh q4d1-bp{k}")
    w(f"BP90_NAME_H={name} $P -I -B $WS/work/r22/basalt-pr90/bp90_report.py $OUT/bp90")
    w("# end: work/r22/port_gap4.sh end   (P028x back on 8080; the rules: MemAvailable >= 12 GB, swap rule, kcheck after")
    w("#      every run, page-allocation-failure-only = drop the run and go on)")
    return "\n".join(L) + "\n"


# =====================================================================================================================
# 6. The check command
# =====================================================================================================================
def gib(x):
    return f"{x / GIB:.2f}"


def analyse(path, E, ref, P, C):
    m = Model(path)
    rep = {"file": str(m.given), "shards": [{"path": x["path"], "size": x["size"], "head_only": x["head_only"],
                                              "header_end": x["header_end"], "tensors": len(x["tensors"])} for x in m.shards],
           "missing": m.missing, "problems": list(m.problems), "arch": m.arch, "name": m.get("general.name"),
           "basename": m.get("general.basename"), "file_bytes": m.file_bytes(), "head_only": m.head_only}
    if not m.shards:
        rep["verdict"] = "UNREADABLE"
        return m, rep
    trunk = trunk_of(m)
    rep["shape_keys"] = OrderedDict((k, v if not isinstance(v, list) or len(v) <= 16 else f"[{len(v)} items] {v[:6]} ...")
                                    for k, v in m.kv.items() if k.startswith(m.arch + "."))
    rep["general"] = OrderedDict((k, v) for k, v in m.kv.items() if k.startswith(("general.", "split.", "quantize.")))
    other = [k for k in m.kv if not k.startswith((m.arch + ".", "general.", "split.", "quantize.", "tokenizer."))]
    rep["other_keys"] = other
    rep["tokenizer_keys"] = [k for k in m.kv if k.startswith("tokenizer.")]
    # ---- tensor groups
    known = set(E["seen_roles"]) | ({role_of(t) for t in ref.tensors} if ref else set())
    groups = OrderedDict()
    per_tensor = []
    for t in m.tensors.values():
        g = group_of(t.name, trunk)
        if g == "routed experts":
            v, why = ("OK", "see the expert table") if t.name.endswith("_exps.weight") else \
                ("OK", "NVFP4 per-expert scale: iq_pack moves it into the blob tail")
        elif g == "MTP / nextn":
            v, why = (("OK", "qwen35 path: the file's own nextn block is the drafter (--mtp N = drafts per step)")
                      if E["families"].get(m.arch) == "Qwen35Moe" else
                      ("IGNORED", "the qwen4exp path reads the trunk; the drafter comes from --mtp DIR (tools/mtp_pack.py)"))
        elif g == "vision":
            v, why = "IGNORED", "a vision projector: Strata's vision path takes a separate mmproj GGUF"
        else:
            v, why = check_tensor(t, E, known, E["families"].get(m.arch))
        per_tensor.append((t, g, v, why))
        G = groups.setdefault(g, {"n": 0, "bytes": 0, "types": Counter(), "verdicts": Counter(), "why": OrderedDict()})
        G["n"] += 1
        G["bytes"] += t.nbytes or 0
        G["types"][t.tname] += 1
        G["verdicts"][v] += 1
        G["why"].setdefault((v, why), []).append(t.name)
    exp_rows, exp_problems = check_experts(m, E, trunk)
    lv = {l: (r["verdict"], r["why"]) for r in exp_rows for l in r["layer_list"]}
    per_tensor = [(t, g, *(lv.get(layer_of(t.name), (v, why)) if g == "routed experts" and t.name.endswith("_exps.weight")
                           else (v, why))) for t, g, v, why in per_tensor]
    worst = "OK"
    for r in exp_rows:
        worst = max(worst, r["verdict"], key=LEVEL.get)
    if "routed experts" in groups:
        groups["routed experts"]["verdicts"] = Counter({r["verdict"]: r["layers"] for r in exp_rows})
    rep["groups"] = OrderedDict()
    for g, G in groups.items():
        vs = max(G["verdicts"], key=LEVEL.get) if G["verdicts"] else "OK"
        rep["groups"][g] = {"tensors": G["n"], "gib": round(G["bytes"] / GIB, 3), "types": dict(G["types"]),
                            "verdict": vs, "verdicts": dict(G["verdicts"]),
                            "why": [{"verdict": v, "why": w, "n": len(ns), "example": ns[0]} for (v, w), ns in G["why"].items()]}
    rep["experts"] = exp_rows
    rep["problems"] += exp_problems
    geo = geometry_check(m, E)
    rep["geometry"] = geo
    tk = tok_info(m)
    rep["tokenizer"] = tk
    tref = tok_info(ref) if ref else tk
    rep["tok_compare"] = tok_compare(tk, tref)
    q, bad = setup_name_check(m.given, E)
    rep["setup_name"] = {"quant": q, "setup_refuses": bad}
    mt = [t for t in m.tensors.values() if is_mtp(t.name, trunk)]
    rep["present"] = {"mtp": (f"{len(mt)} tensors, {sum(t.nbytes or 0 for t in mt) / GIB:.2f} GiB, layers "
                              f"{sorted({layer_of(t.name) for t in mt if layer_of(t.name) is not None}) or '-'}") if mt else None,
                      "ngram": "per_layer_token_embd.weight" in m.tensors,
                      "ngram_projections": sorted({role_of(t.name) for t in m.tensors.values() if ".ple_" in t.name}),
                      "vision": sum(1 for t in m.tensors.values() if t.name.startswith(("v.", "mm."))),
                      "nvfp4_scales": sum(1 for t in m.tensors.values() if t.name.endswith("_exps.scale")),
                      "prism": [k for k in m.kv if k.startswith("prism.")]}
    # ---- verdict
    refused = [f"{g}: {w['why']}" for g, G in rep["groups"].items() for w in G["why"] if w["verdict"] == "REFUSED"]
    refused += [f"experts {r['gate_up']}/{r['down']} ({r['layers']} layers): {r['why']}" for r in exp_rows if r["verdict"] == "REFUSED"]
    refused += [f"geometry: {x}" for x in geo["refused"]]
    if not exp_rows and m.arch in E["families"]:
        refused.append("no routed experts in this file (a dense model, or experts kept in a ready-made pack)")
    refused += [p for p in rep["problems"] if "truncated" in p or "past EOF" in p or "missing shard" in p or "two shards" in p]
    convs = sorted({f"{g}: {w['why']}" for g, G in rep["groups"].items() for w in G["why"]
                    if w["verdict"].startswith(("PACK", "TOOL"))})
    build = sorted({r["why"] for r in exp_rows if r["verdict"] == "OK (build option)"})
    unknown = sorted({w["example"] for G in rep["groups"].values() for w in G["why"] if w["verdict"] == "UNKNOWN"})
    rep["refused"], rep["conversions"], rep["build_options"], rep["unknown"] = refused, convs, build, unknown
    rep["verdict"] = ("REFUSED" if refused else "RUNS WITH A PACK CONVERSION" if convs else
                      "RUNS (build option)" if build else "RUNS")
    n_unk = sum(1 for _, _, v, _ in per_tensor if v == "UNKNOWN")
    if n_unk and not refused:
        rep["verdict"] += f" - CHECK {n_unk} tensor(s) of unknown handling"
    rep["need_compat_bf16"] = any(w["verdict"] == "PACK (rounding)" and "--compat-bf16" in w["why"]
                                  for G in rep["groups"].values() for w in G["why"])
    rep["maybe_compat_bf16"] = any(w["verdict"] == "PACK (exact if the values allow)" for G in rep["groups"].values()
                                   for w in G["why"])
    rep["_per_tensor"] = per_tensor
    # ---- layout, the widths' type limits, the same-model signature (for the swap mode)
    rep["layout"] = layout_info(m, trunk, rep["present"])
    rep["shape_types"] = shape_types(m, E, exp_rows)
    rep["_arch_kv"] = {k: v for k, v in m.kv.items() if k.startswith(m.arch + ".")}
    rep["_tensor_shapes"] = {t.name: tuple(t.shape) for t in m.tensors.values()}
    rep["mtp_only"] = bool(mt) and not any(layer_of(t.name) is not None and layer_of(t.name) < trunk
                                           for t in m.tensors.values())
    if rep["mtp_only"]:
        rep["verdict"] = "MTP FILE (a drafter, not a model: work/qwen4-kit/mtp_from_gguf.py)"
    # ---- fit
    s = sizes(m, E)
    sref = sizes(ref, E) if ref else s
    kvc, n_attn = kv_cell_bytes(m, P.kv)
    kvc_ref, _ = kv_cell_bytes(ref, P.kv) if ref else (kvc, n_attn)
    drafter = s["mtp_infile"] if s["mtp_infile"] else P.drafter_gib * GIB
    B = budget(P, s, sref, kvc, kvc_ref, drafter)
    ratio = (s["active_params"] / sref["active_params"]) if sref["active_params"] else 1.0
    fit = {"experts_gib": s["experts"] / GIB, "dense_gpu_gib": s["dense_gpu"] / GIB, "embed_gib": s["embed"] / GIB,
           "ple_gib": s["ple"] / GIB, "mtp_infile_gib": s["mtp_infile"] / GIB, "vision_gib": s["vision"] / GIB,
           "blob_mean_mib": s["blob_mean"] / MIB, "blob_max_mib": s["blob_max"] / MIB,
           "experts_bpw": 8 * s["experts"] / s["expert_elems"] if s["expert_elems"] else None,
           "active_params_b": s["active_params"] / 1e9, "dense_params_b": s["dense_params"] / 1e9,
           "kv_cell_bytes": kvc, "attn_layers": n_attn, "kv_ctx_gib": B["kv_host"] / GIB, "kv_vram_gib": B["kv_vram"] / GIB,
           "ctx": P.ctx, "room_main_gib": B["main"] / GIB, "room_helpers_gib": [h / GIB for h in B["helpers"]],
           "room_ram_gib": B["ram"] / GIB, "other_gib": B["other"] / GIB, "room_total_gib": B["total"] / GIB,
           "fits": bool(s["experts"]) and s["experts"] <= B["total"],
           "spill_gib": max(0.0, s["experts"] - B["total"]) / GIB,
           "all_in_ram": bool(s["experts"]) and s["experts"] <= B["ram"]}
    fit["spill_frac"] = (fit["spill_gib"] / fit["experts_gib"]) if fit["experts_gib"] else 0.0
    fit["locked_gib"] = min(s["experts"], B["ram"]) / GIB
    try:
        fit["tiers"] = tiers(s, B, P, C, ratio) if C else None
    except (ValueError, OverflowError, ZeroDivisionError):
        fit["tiers"] = None
    du = shutil.disk_usage(WS / "models")
    need = 0 if not m.head_only else m.file_bytes()
    fit["disk"] = {"download_gb": round(m.file_bytes() / 1e9, 1), "on_disk": not m.head_only,
                   "free_gb": round(du.free / 1e9, 1), "free_after_gb": round((du.free - need) / 1e9, 1),
                   "ok": (du.free - need) / 1e9 >= 100}
    rep["fit"] = fit
    rep["_sizes"], rep["_budget"] = s, B
    return m, rep


def group_key(m, rep, by="shape"):
    """Candidates are quants of one model: the same architecture, layers x experts, widths and tokenizer (fine-tunes of
    the same shape join the group: --group-by name also splits by general.basename / name)."""
    s = rep.get("_sizes") or {}
    k = (m.arch, s.get("trunk"), s.get("n_expert"), ai(m, "embedding_length"), ai(m, "expert_feed_forward_length"),
         (rep.get("tokenizer") or {}).get("tokens_sha"))
    return k + ((m.get("general.basename") or m.get("general.name") or "?",) if by == "name" else ())


def same_model(rep, served):
    """The swap mode's test (REPORT 8.4): every <arch>.* shape key and the tokenizer (tokens, merges, special ids) equal
    to the served file's -> P028x's config applies with the three model paths swapped. The tensor table (names, shapes),
    the chat template and general.name are compared too and reported (warnings, not blockers)."""
    if not served or rep is served or rep.get("verdict") in (None, "UNREADABLE") or rep.get("mtp_only"):
        return None
    a, b = rep.get("_arch_kv") or {}, served.get("_arch_kv") or {}
    why = []
    if rep["arch"] != served["arch"]:
        why.append(f"architecture {rep['arch']} != {served['arch']}")
    diff_keys = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    if diff_keys:
        why.append(f"{len(diff_keys)} shape key(s) differ: {', '.join(diff_keys[:6])}{' ...' if len(diff_keys) > 6 else ''}")
    same, _v = rep["tok_compare"]
    tok_same = same["tokens_sha"] and same["merges_sha"] and same["special_ids"]
    if not tok_same:
        why.append("another tokenizer (" + ", ".join(k for k in ("tokens_sha", "merges_sha", "special_ids") if not same[k]) + ")")
    ta, tb = rep.get("_tensor_shapes") or {}, served.get("_tensor_shapes") or {}
    only_new, only_old = sorted(set(ta) - set(tb)), sorted(set(tb) - set(ta))
    shape_diff = sorted(n for n in set(ta) & set(tb) if ta[n] != tb[n])
    warn = []
    if only_new or only_old or shape_diff:
        warn.append(f"tensor table differs from the served file: {len(only_new)} new, {len(only_old)} missing, "
                    f"{len(shape_diff)} reshaped (e.g. {(only_new + only_old + shape_diff)[:3]})")
    if "per_layer_token_embd.weight" in tb and "per_layer_token_embd.weight" not in ta:
        why.append("no n-gram table in the file (P028x's --ple-gguf has nothing to point at)")
    if not same["template_sha"]:
        warn.append("another chat template (the server renders it from the pack's tokenizer dir: re-check think tags, "
                    "efforts, tool calls)")
    norm = lambda x: re.sub(r"[^a-z0-9]", "", (x or "").lower())  # noqa: E731
    na, nb = norm(rep.get("basename") or rep.get("name")), norm(served.get("basename") or served.get("name"))
    if na != nb and not (na and nb and (na in nb or nb in na)):
        warn.append(f"general.name {rep.get('name')!r} vs the served {served.get('name')!r}: a requant of the same "
                    "checkpoint, or a fine-tune of the same shape (then our drafter's acceptance may be lower - measure it)")
    return {"swap": not why, "why_not": why, "warnings": warn, "diff_keys": diff_keys, "tensors_new": only_new[:20],
            "tensors_missing": only_old[:20], "tensors_reshaped": shape_diff[:20], "template_same": same["template_sha"]}


def final_paths(m, P):
    """Where the config / pack / evict lines point: the shard paths, or (--files-at) where the download will land.
    --files-at DIR applies to head-only files; --files-at GLOB=DIR to every file whose shard-1 name matches GLOB."""
    import fnmatch
    base = Path(m.paths[0]).name
    specs = list(getattr(P, "files_at", None) or [])
    target = next((s.split("=", 1)[1] for s in specs if "=" in s and fnmatch.fnmatch(base, s.split("=", 1)[0])), None)
    if target is None and m.head_only:
        target = next((s for s in specs if "=" not in s), None)
    if target is None:
        return [str(p) for p in m.paths], None
    return [str(Path(target) / Path(p).name) for p in m.paths], target


def stem_of(path):
    n = Path(path).name
    n = SHARD_RE.sub(lambda mm: mm.group(1), n) if SHARD_RE.match(n) else n
    return re.sub(r"\.gguf$", "", n)


def fmt_pct(x):
    return f"{100 * x:.1f} %"


def write_report(out, E, P, reps, picks, type_notes, ref_rep):
    L = []
    w = L.append
    w(f"# Qwen4 day one: header check ({datetime.datetime.now():%Y-%m-%d %H:%M}, {VERSION})")
    w("")
    w(f"Headers only: no tensor data read, no download, no GPU, no engine. Engine tables from `{Path(E['tree']).name}` "
      f"@ {E['head']} (branch {E['branch']}; build options {', '.join(f'{k}={'ON' if v else 'OFF'}' for k, v in E['opts'].items())}; "
      f"CUDA archs {E['archs']}), read from its source at run time. Reference model: `{REF_GGUF.name}` (served, P028x).")
    if E["fallback"]:
        w(f"**Fall-backs used (a table was not found in the tree):** {'; '.join(E['fallback'])}")
    w("")
    w("## The engine's type tables (what Strata actually runs)")
    w("")
    w("| path | types | source |")
    w("|---|---|---|")
    w(f"| routed experts, gate/up (both cards: one kernel set for sm_120 + sm_89) | {tn(E['gu'])} | {E['cite']['gu']} |")
    w(f"| routed experts, down (both cards) | {tn(E['d'])} | {E['cite']['d']} |")
    if E["q6k_only_gu"] or E["q6k_only_d"]:
        w(f"| ... only with -DSTRATA_Q6K_EXPERTS=ON (here {'ON' if E['opts'].get('STRATA_Q6K_EXPERTS') else 'OFF'}) | "
          f"{tn(E['q6k_only_gu'] | E['q6k_only_d'])} | CMakeLists.txt / build/CMakeCache.txt |")
    w(f"| expert rule | same gate/up type a layer (pack), n_embd % 256 == 0, rows whole blocks, NVFP4 with .scale | "
      f"{E['cite']['expert_rule']}, {E['cite']['gate_up_rule']} |")
    w(f"| expert prompt path, MMQ | {tn(E['mmq'])} (else the FP16 dequantizer: {tn(E['is_iq'] - E['mmq'])}) | {E['cite']['mmq']} |")
    w(f"| expert prompt path, fused int8 (5080 only: sm_120, 80+ SMs) | gate/up {tn(E['fused_gu'] & E['fused_sm120'])} with down "
      f"{tn(E['fused_down'])} | {E['cite']['fused']}, include/strata/core/sm120_series.hpp |")
    w(f"| CPU expert pool | any ggml-cpu dot product + trellis {tn(E['cputq'])}; fast: AVX-512 {tn(E['cpu512'])}, multi-token "
      f"{tn(E['cpu512x'])}, AVX2 {tn(E['cpu256'])}, K/Q {tn(E['cpukq'])}, IQ4_NL down, NVFP4 | {E['cite']['cpu_rule']}, "
      f"{E['cite']['cpu512']} |")
    w(f"| dense projections (attn, ssm_out, shared expert) + head | {tn(E['mmvq'])} (interleaved: {tn(E['mmvq_il'])}) or "
      f"F32/F16/BF16 | {E['cite']['mmvq']}, {E['cite']['native_dense']} |")
    w(f"| token embedding | {tn(E['embed'])} | {E['cite']['embed']} |")
    w(f"| float forms (router, hyper-connections, indexer, GDN gates, PLE key/value BF16; norms F32; PLE conv F16) | "
      f"{len(E['form'])} roles | tools/iq_pack.py FORM ({E['cite']['form']}) |")
    w(f"| n-gram table | {', '.join(f'{a} ({b})' for a, b in E['ple'])} | {E['cite']['ple']} |")
    w(f"| architectures | {', '.join(f'{k} -> {v}' for k, v in E['families'].items())} | {E['cite']['families']} |")
    w(f"| compiled geometry (pinned keys) | {', '.join(k for k, _ in E['pins'])} | {E['cite']['pins']} |")
    w(f"| router top-k kernel | {E['router']} | {E['cite']['router']} |")
    w(f"| setup.py name check (setup only) | refuses quant names not in its MODELS: {E['setup_text'][:200]}... | {E['cite']['setup']} |")
    w("")
    w(f"Extra type ids from the tree's tools/gguf_reader.py: {', '.join(type_notes) or '-'}.")
    w("")
    # ---- budget
    b0 = next((r for r in reps if r.get("fit")), None)
    w("## Expert room today (Karl's quant rule: the largest quant whose experts fit RAM + VRAM)")
    w("")
    w("Every input is a parameter of `day1.py check` (defaults: this PC, measured). Per model the dense weights, the K/V at "
      "the served context, the embedding and the drafter change the 5080's share and the RAM tier:")
    w("")
    w("| input | value | where it comes from |")
    w("|---|---|---|")
    w(f"| RAM: MemTotal | {P.memtotal_gib} GiB (now {P.meminfo_now}) | 96 GB DDR5-6000; the engine's guard line \"limit 92.0 GiB (source: meminfo)\" (logs/engine-P028x.log) |")
    w(f"| RAM: MemAvailable floor | {P.floor_gib} GiB | Karl's rule since 10-19 (memory: MemAvailable floor 12 GB) |")
    w(f"| RAM: everything else | {P.other_gib} GiB at Flash-Next's K/V and a {P.chat_cache_ref_gib:g} GiB chat cache | "
      "engine outside the tier + pinned K/V 1.55 GiB + chat cache 2 GiB + OS, desktop and the daily services (SearXNG x3, "
      "LDR, Jan, watchers): the 64 GiB splice arms hit the 12 GiB guard (results/sweep-1103/summary.txt, 11.7-12.0 GiB; "
      f"{ESTIMATE_DOC} 7.3) |")
    w(f"| RAM: headroom | {P.headroom_gib} GiB | the 58 GiB tier ran clean (splice58 arms); chat parking grows ~3 GiB/h; the "
      "NVFP4 pack's 63.3 GiB arena dipped to 6.7 GiB MemAvailable (10-16) |")
    w(f"| RAM: chat cache cap | {P.chat_cache_gib:g} GiB | the splice58 arms' --chat-cache-mib 2048 (P028x serves 12288: up to 10 GiB less tier) |")
    w(f"| 5080 | {P.vram_main_mib} MiB - {P.overhead_main_gib} GiB overhead - dense - resident K/V ({P.kv_resident} cells) - "
      f"{P.reserve_mib} + {P.draft_head_mib} MiB | bringup/fitplan.py's calibration (P021m/P028x start: 9.53 GiB free before "
      "the cache, 4,585 slots = 8.75 GiB); the overhead holds Flash-Next's 0.82 GiB drafter |")
    w(f"| helpers | {', '.join(f'{h[0]} GiB free @ {h[1]} GB/s' for h in P.helpers)} - {P.helper_keep_mib} MiB each | the "
      "4060 Ti's \"7.56 GiB free before expert arena registration\"; the engine keeps 512 MiB free (remote_experts.cpp) |")
    w(f"| context | {P.ctx} cells, K/V {P.kv} | the served --max-context |")
    if ref_rep and ref_rep.get("fit"):
        f = ref_rep["fit"]
        w("")
        w(f"For Flash-Next (the served IQ3_S, as a check of the inputs): 5080 {f['room_main_gib']:.2f} GiB (measured 8.75) + "
          f"helper {sum(f['room_helpers_gib']):.2f} + RAM tier {f['room_ram_gib']:.2f} = **{f['room_total_gib']:.1f} GiB**. "
          f"With section 8's Qwen4 guess (dense 3.7-4.6 GiB, more K/V and a larger drafter: 5080 ~7.3 GiB) the same sum is "
          "the plan's **about 72 GiB**.")
    w("")
    # ---- candidates
    w("## Candidates and the pick")
    w("")
    for key, (pick, members, why, tie) in picks.items():
        w(f"### Model group: {members[0]['arch']}, {members[0]['_sizes']['trunk']} layers x {members[0]['_sizes']['n_expert']} experts, "
          f"n_embd {key[3]}")
        w("")
        w("| file | general.name | quant | experts | dense (GPU) | fits | runs | verdict |")
        w("|---|---|---|---|---|---|---|---|")
        for r in members:
            f = r["fit"]
            w(f"| `{Path(r['file']).name}` | {r['name']} | {r['setup_name']['quant'] or '-'} | {f['experts_gib']:.2f} GiB"
              f"{f' ({f['experts_bpw']:.2f} bpw)' if f['experts_bpw'] else ''} | {f['dense_gpu_gib']:.2f} GiB | "
              f"{'-' if not f['experts_gib'] else 'yes' if f['fits'] else f'no: {f['spill_gib']:.1f} GiB to the SSD'} | "
              f"{'no' if r['verdict'] == 'REFUSED' else 'yes'} | {r['verdict']}"
              f"{' **<- TIE**' if any(r is x for x in tie) else ' **<- PICK**' if pick is r else ''} |")
        w("")
        w(f"**Pick:** {why}")
        w("")
    # ---- per file
    for r in reps:
        w(f"## `{Path(r['file']).name}`")
        w("")
        if r.get("verdict") == "UNREADABLE":
            w(f"Unreadable: {'; '.join(r['problems'])}")
            w("")
            continue
        sh = r["shards"]
        w(f"- **{r['verdict']}** - arch `{r['arch']}`, name {r['name']!r}, {len(sh)} shard(s){' (HEAD-ONLY: sizes from NAME.size)' if r['head_only'] else ''}, "
          f"{r['file_bytes'] / 1e9:.1f} GB; per-tensor table: `files/{stem_of(r['file'])}.tensors.tsv`, keys: `files/{stem_of(r['file'])}.keys.txt`")
        if r["problems"]:
            w(f"- problems: {'; '.join(r['problems'])}")
        for x in r["refused"]:
            w(f"- REFUSED: {x}")
        for x in r["build_options"]:
            w(f"- build option: {x}")
        for x in r["conversions"]:
            w(f"- conversion: {x}")
        if r["unknown"]:
            w(f"- unknown roles (not in any file Strata runs): {', '.join(r['unknown'][:8])}")
        sn = r["setup_name"]
        if sn["setup_refuses"]:
            w(f"- setup.py would refuse this file by its name ({sn['setup_refuses']}); our configs do not go through setup")
        p = r["present"]
        w(f"- present: MTP/nextn {p['mtp'] or 'none'}; n-gram table {'yes' if p['ngram'] else 'no'} ({', '.join(p['ngram_projections']) or '-'}); "
          f"vision tensors {p['vision']}; NVFP4 scales {p['nvfp4_scales']}; prism keys {p['prism'] or '-'}")
        for x in (r.get("layout") or {}).get("info", []):
            w(f"- layout: {x}")
        st_ = r.get("shape_types") or {}
        if st_.get("down_text") and r.get("experts"):
            w(f"- {st_['down_text']}")
            w(f"- {st_['gate_up_text']}")
            if st_.get("note_256"):
                w(f"- shape note: {st_['note_256']}")
        sm = r.get("same_model")
        if sm:
            w(f"- vs the served file ({REF_GGUF.name}): " + (
                "**same model** (every shape key and the tokenizer equal) -> day one uses the SWAP config: "
                f"{TEMPLATE_CFG.name} with only --pack / --native / --ple-gguf swapped" if sm["swap"] else
                "not a same-model swap: " + "; ".join(sm["why_not"]))
              + (f"; warnings: {'; '.join(sm['warnings'])}" if sm["warnings"] else ""))
        g = r["geometry"]
        sk = r["shape_keys"]
        w(f"- shape keys ({len(sk)}): " + ", ".join(f"{k.split('.', 1)[1]}={v}" for k, v in list(sk.items())[:60]))
        for x in g["notes"]:
            w(f"- geometry note: {x}")
        tk, (same, verdict) = r["tokenizer"], r["tok_compare"]
        w(f"- tokenizer: {tk['model']} / {tk['pre']}, vocab {tk['vocab']}, eos {tk['eos']}, bos {tk['bos']}, pad {tk['pad']}, "
          f"think tags {[tk['marker_ids'].get('<think>'), tk['marker_ids'].get('</think>')]}, im_start {tk['marker_ids'].get('<|im_start|>')}; "
          f"template {tk['template_chars']} chars, efforts {tk['efforts'] or '-'} (default {tk['effort_default']}), "
          f"thinking off {'yes' if tk['thinking_off'] else 'no'}, tools {tk['tool_format']}, context_length {tk['context_length']}")
        w(f"- vs Flash-Next: {verdict} ({', '.join(f'{k} {'=' if v else 'differs'}' for k, v in same.items())})")
        w("")
        w("| tensor group | tensors | GiB | types | verdict | why |")
        w("|---|---|---|---|---|---|")
        for gname, G in r["groups"].items():
            if gname == "routed experts":
                why = "per layer: see below"
            else:
                why = "; ".join(f"{x['verdict']}: {x['why']} ({x['n']}x, e.g. {x['example']})" for x in G["why"])
            w(f"| {gname} | {G['tensors']} | {G['gib']:.3f} | {', '.join(f'{k} {v}' for k, v in G['types'].items())} | "
              f"{G['verdict']} | {why} |")
        w("")
        if r["experts"]:
            w("| routed experts gate/up | down | layers | verdict | why | prompt path | CPU pool |")
            w("|---|---|---|---|---|---|---|")
            for x in r["experts"]:
                w(f"| {x['gate_up']} | {x['down']} | {x['layers']} | {x['verdict']} | {x['why']} | {x['prompt']} | {x['cpu']} |")
            w("")
        f = r["fit"]
        w(f"**Fit:** experts **{f['experts_gib']:.2f} GiB** (blob {f['blob_mean_mib']:.2f} MiB mean / {f['blob_max_mib']:.2f} max"
          f"{f', {f['experts_bpw']:.2f} bpw' if f['experts_bpw'] else ''}), dense on the GPU {f['dense_gpu_gib']:.2f} GiB, "
          f"embedding {f['embed_gib']:.2f} GiB (host), n-gram table {f['ple_gib']:.2f} GiB (read from the file), in-file MTP "
          f"{f['mtp_infile_gib']:.2f} GiB; active parameters {f['active_params_b']:.2f} B (dense {f['dense_params_b']:.2f} B); "
          f"K/V at {f['ctx']:,} cells {f['kv_ctx_gib']:.2f} GiB ({f['attn_layers']} attention layers; "
          f"{f['kv_vram_gib']:.2f} GiB resident in VRAM). Room: 5080 {f['room_main_gib']:.2f} + helpers "
          f"{' + '.join(f'{h:.2f}' for h in f['room_helpers_gib'])} + RAM tier {f['room_ram_gib']:.2f} = "
          f"**{f['room_total_gib']:.2f} GiB** -> "
          + (f"**fits**{' (every expert in the RAM arena, page-locked)' if f['all_in_ram'] else ' (RAM budget mode: --resident-budget-gib)'}"
             if f["fits"] else f"**does not fit: {f['spill_gib']:.2f} GiB ({fmt_pct(f['spill_frac'])}) of the experts on the SSD tier**")
          + f". Disk: {f['disk']['download_gb']} GB, {'on disk' if f['disk']['on_disk'] else 'to download'}, "
          f"{f['disk']['free_after_gb']} GB free after{' (OK)' if f['disk']['ok'] else ' (UNDER 100 GB: ask Karl)'}."
          + (f" Page-locked {f['locked_gib']:.1f} GiB > 60: stressapptest first (memory: RAM fault rule)." if f['locked_gib'] > 60 else ""))
        t = f.get("tiers")
        if t:
            c, sp = t["cases"], t["split"]
            hw = "; ".join(f"helper {i + 1}: {h['entries_tok']:.1f} entries/token, {h['ms_tok']:.2f} ms, exposed wait "
                           f"{h['wait_ms']:.2f} ms" for i, h in enumerate(t["helper_work"]))
            w("")
            w(f"**Tier split and decode** ({ESTIMATE_DOC} sections 8-9: the splice's hit curve at this model's fraction of "
              f"experts held, helper slot = {P.helper_eff} of a main slot, CPU {P.cpu_us:g} us per 4.0 MB entry, SSD 0.80 ms "
              f"per 3.1 MB read, serial GPU part {P.serial_ms:g} ms x the active-parameter ratio {t['compute_ratio']:.2f} vs "
              f"Flash-Next): slots 5080 {t['slots_main']:,} + helpers {t['slots_helpers']} + RAM {t['slots_ram']} of "
              f"{t['NE']:,}; cold set {fmt_pct(t['cold_frac'])}; {t['R']:.0f} routed lookups per token. Decode lookups: "
              f"5080 {fmt_pct(sp['main'])}, helpers {fmt_pct(sp['helpers'])}, PCIe from RAM {fmt_pct(sp['pcie_ram'])}, CPU "
              f"from RAM {fmt_pct(sp['cpu_ram'])}, SSD {fmt_pct(sp['ssd'])} ({c['centre']['ssd_mb_tok']:.0f} MB/token). "
              f"**Decode ~{c['centre']['tok_s']:.0f} tok/s** (range {c['worst']['tok_s']:.0f}-{c['best']['tok_s']:.0f}; "
              f"{'SSD-bound' if c['centre']['ssd_ms'] > c['centre']['compute_ms'] else 'compute-bound'}) against Karl's "
              f"40-60 target: {'above' if c['centre']['tok_s'] > 60 else 'inside' if c['centre']['tok_s'] >= 40 else 'BELOW'}. "
              + (f"Section 9: {hw}." if hw else ""))
            meas = MEASURED.get(Path(r["file"]).name)
            if meas:
                w("")
                w(f"*Model check on a measured point:* {meas[0]}. The model gives {c['centre']['tok_s']:.0f} tok/s "
                  f"({100 * (c['centre']['tok_s'] / meas[1] - 1):+.0f} %).")
        w("")
        if r.get("_day1"):
            d = r["_day1"]
            w(f"**Day-one pieces ({'same-model swap of ' + TEMPLATE_CFG.name if d.get('mode') == 'swap' else 'stock config'}):** "
              f"config `{d['config']}` (+ `.shared-settings.json`), parameters `{d['params']}`, commands `{d['commands']}`.")
            w("")
    w("## Notes")
    w("")
    w(f"- The tier/decode numbers are {ESTIMATE_DOC}'s model (guesses on guesses, its section 8.5): use them to compare "
      "quants and layouts, not as forecasts. On the served Flash-Next the main-card curve under-predicts the measured hits "
      "(section 4.1: 73.7-79 % at 4,790 slots vs the curve's 68 %).")
    w("- Shapes the kernels are compiled for: the other helper's results/qwen4-kit/SHAPES.md lists every hard-coded site; "
      "this report only applies the load gate (read_geometry + geometry_unsupported).")
    w(f"- The quant rule and the day-one order are Karl's ({PLAN_DOC}, \"Quant choice\" 11-03).")
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, set):
        return sorted(jsonable(v) for v in x)
    if isinstance(x, float):
        return round(x, 6)
    return x


def _pieces(p, tie):
    xs = [x.get("_day1") for x in (tie or [p]) if x is not None and x.get("_day1")]
    return xs[0] if len(xs) == 1 else (xs or None)


def cmd_check(a):
    P = a
    P.helpers = [tuple(float(v) for v in h.split(":")) for h in (a.helper or ["7.56:288"])]
    try:
        mt = re.search(r"^MemTotal:\s+(\d+) kB", Path("/proc/meminfo").read_text(), re.M)
        P.meminfo_now = f"{int(mt.group(1)) / 2 ** 20:.1f} GiB" if mt else "?"
    except OSError:
        P.meminfo_now = "?"
    tree = Path(a.tree)
    type_notes = type_table(tree)
    E = engine_tables(tree)
    _FAMILIES.update(E["families"])
    C = json.loads(CURVES.read_text()) if CURVES.exists() else None
    out = Path(a.out)
    (out / "files").mkdir(parents=True, exist_ok=True)
    ref = Model(a.ref_gguf) if a.ref_gguf and Path(a.ref_gguf).exists() else None
    ref_rep = None
    reps, models = [], []
    paths = list(dict.fromkeys(str(Path(p)) for p in a.gguf))
    if ref and str(ref.given) not in paths:
        _, ref_rep = analyse(ref.given, E, ref, P, C)
    for p in paths:
        m, rep = analyse(p, E, ref, P, C)
        if ref and str(m.given) == str(ref.given):
            ref_rep = rep
        reps.append(rep)
        models.append(m)
        st = stem_of(p)
        with open(out / "files" / f"{st}.tensors.tsv", "w", encoding="utf-8") as fo:
            fo.write("name\ttype\tshape\tbytes\tshard\tgroup\tverdict\twhy\n")
            for t, g, v, why in rep.get("_per_tensor", []):
                fo.write(f"{t.name}\t{t.tname}\t{list(t.shape)}\t{t.nbytes}\t{t.shard + 1}\t{g}\t{v}\t{why}\n")
        with open(out / "files" / f"{st}.keys.txt", "w", encoding="utf-8") as fo:
            for k, v in m.kv.items():
                vt = VT(m.vt[k]).name if m.vt.get(k) in set(int(x) for x in VT) else m.vt.get(k)
                if isinstance(v, list) and len(v) > 16:
                    v = f"[{len(v)} items, sha256 {_h(v)}] {json.dumps(v[:8], ensure_ascii=False)} ..."
                elif isinstance(v, str) and len(v) > 400:
                    v = f"<{len(v)} chars, sha256 {_h(v)}> {v[:160]!r} ..."
                fo.write(f"{k}\t{vt}\t{v}\n")
    # ---- the same-model test against the served file (the swap mode)
    tpl = json.loads(TEMPLATE_CFG.read_text(encoding="utf-8-sig"), object_pairs_hook=OrderedDict)
    served_native = tpl_arg(tpl, "--native")
    swap_ok_tpl = bool(ref_rep) and served_native and Path(served_native).resolve() == Path(ref.given).resolve()
    for r in reps:
        r["same_model"] = same_model(r, ref_rep) if ref_rep else None
        if r["same_model"] and not swap_ok_tpl:
            r["same_model"]["why_not"].append(f"{TEMPLATE_CFG.name}'s --native is not --ref-gguf: no swap template")
            r["same_model"]["swap"] = False
        if r["same_model"] and a.no_swap and r["same_model"]["swap"]:
            r["same_model"]["swap"] = False
            r["same_model"]["why_not"].append("--no-swap")
    # ---- groups and picks (Karl's rule: the largest experts that fit RAM + VRAM and run)
    groups = OrderedDict()
    for m, r in zip(models, reps):
        if r.get("verdict") == "UNREADABLE" or r.get("mtp_only"):
            continue
        groups.setdefault(group_key(m, r, a.group_by), []).append(r)
    model_of = {id(r): m for m, r in zip(models, reps)}
    is_served = lambda r: bool(ref) and Path(r["file"]).resolve() == Path(ref.given).resolve()  # noqa: E731
    picks = OrderedDict()
    tol = a.tie_tol_gib
    for key, mem in groups.items():
        mem.sort(key=lambda r: -r["fit"]["experts_gib"])
        runnable = [r for r in mem if r["verdict"] != "REFUSED" and r["fit"]["experts_gib"] > 0]
        fitting = [r for r in runnable if r["fit"]["fits"]]
        tie = []
        if fitting:
            pk = fitting[0]
            tie = [r for r in fitting if abs(r["fit"]["experts_gib"] - pk["fit"]["experts_gib"]) <= tol]
            skipped = [f"`{Path(r['file']).name}` ({'refused' if r['verdict'] == 'REFUSED' else f'{r['fit']['spill_gib']:.1f} GiB over'})"
                       for r in mem if mem.index(r) < mem.index(pk)]
            mg = pk['fit']['room_total_gib'] - pk['fit']['experts_gib']
            if len(tie) > 1:
                d = max(r["fit"]["experts_gib"] for r in tie) - min(r["fit"]["experts_gib"] for r in tie)
                why = (f"**tie: quality decides** - {', '.join(f'`{Path(r['file']).name}`' for r in tie)} have equal expert "
                       f"bytes ({pk['fit']['experts_gib']:.2f} GiB, spread {d * 1024:.2f} MiB <= the {tol:g} GiB tolerance) "
                       f"and all fit (margin {mg:.2f} GiB): Karl's rule cannot choose, and the list order is not a choice. "
                       "Next: the KL / NLL step (commands step 3: pf_yardstick long40 of EACH tied file against one local "
                       "reference via --kl-ref-config, + the text NLL); the lower KL wins"
                       + ("; the served file is one of them (its config is configs/P028x.json)" if any(map(is_served, tie)) else "")
                       + (f"; larger ones skipped: {', '.join(skipped)}" if skipped else ""))
            else:
                why = (f"`{Path(pk['file']).name}` - the largest that fits and runs: {pk['fit']['experts_gib']:.2f} GiB of experts "
                       f"in {pk['fit']['room_total_gib']:.2f} GiB of room (margin {mg:.2f} GiB"
                       + (": TIGHT - the chat-cache cap, the K/V and the headroom decide it; watch MemAvailable in a full-context "
                          "prompt before trusting it" if mg < 2.0 else "") + ")"
                       + (f"; larger ones skipped: {', '.join(skipped)}" if skipped else ""))
                nxt = next((r for r in fitting[1:]), None)
                if nxt is not None and pk["fit"]["experts_gib"] - nxt["fit"]["experts_gib"] < 4 * tol:
                    why += (f" (close: `{Path(nxt['file']).name}` is {1024 * (pk['fit']['experts_gib'] - nxt['fit']['experts_gib']):.0f} "
                            "MiB smaller - outside the tie tolerance)")
        elif runnable:
            pk = runnable[-1]
            why = (f"none fits; the smallest runnable one, `{Path(pk['file']).name}`, needs {pk['fit']['spill_gib']:.1f} GiB "
                   "of experts on the SSD tier. Karl's rule: then measure it and, only if its quality is not enough, compare "
                   "the IQ3-class quants and price the upgrades (UPGRADE-ESTIMATE.md 6-8)")
        else:
            pk = None
            why = "nothing in this group runs: " + "; ".join(f"`{Path(r['file']).name}`: {(r['refused'] or ['no experts'])[0]}" for r in mem)
        picks[key] = (pk, mem, why, tie if len(tie) > 1 else [])
    # ---- day-one pieces for each pick (each tied file but the served one, whose config is P028x.json)
    d1 = out / "day1"
    n_pieces = sum(len([r for r in (t or [p]) if r is not None and not is_served(r)]) for p, _, _, t in picks.values())
    for key, (pk, mem, why, tie) in picks.items():
        if pk is None:
            continue
        todo = [r for r in (tie or [pk]) if not is_served(r)]
        tie_names = [Path(r["file"]).name for r in tie] if tie else None
        for r in todo:
            m = model_of[id(r)]
            name = a.name if a.name and n_pieces == 1 else \
                re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{a.name or 'q4d1'}-{stem_of(r['file'])[:48]}").strip("-")
            d1.mkdir(parents=True, exist_ok=True)
            sm = r.get("same_model")
            swap = bool(sm and sm["swap"])
            if swap:
                cfg, shared = make_swap_config(name, m, r["_sizes"], r["fit"], r["_budget"], P, tpl, sm, r["need_compat_bf16"],
                                               (ref_rep or {}).get("_sizes"))
            else:
                cfg, shared = make_config(name, m, r["_sizes"], r["fit"], r["_budget"], P, tpl)
                if sm:
                    cfg["_day1"]["not_a_swap"] = sm["why_not"]
            if tie:
                cfg["_day1"]["tie"] = f"tie under Karl's rule with {', '.join(x for x in tie_names if x != Path(r['file']).name)}: quality decides (KL / NLL step)"
            cfg_file = d1 / f"{name}.json"
            cfg_file.write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8")
            (d1 / f"{name}.shared-settings.json").write_text(json.dumps(shared, indent=1) + "\n", encoding="utf-8")
            params = make_params(name, m, r["_sizes"], r["tokenizer"], r["tok_compare"], r["fit"], r["_budget"], P, E,
                                 swap=tpl if swap else None, tie=tie_names)
            (d1 / f"params-{name}.json").write_text(json.dumps(jsonable(params), indent=1) + "\n", encoding="utf-8")
            cfg_target = WS / f"configs/{name}.json"
            installed = None
            if a.install_config:
                if name.startswith("P028x") or cfg_target.exists():
                    print(f"--install-config: refused for {cfg_target} (exists or a P028x name); kept in {cfg_file}")
                else:
                    shutil.copyfile(cfg_file, cfg_target)
                    shutil.copyfile(d1 / f"{name}.shared-settings.json", WS / f"configs/{name}.shared-settings.json")
                    installed = cfg_target
            tools = []
            for c in r["conversions"]:
                if "embd_bf16_pack" in c:
                    tools.append(f"$P -I -B $REL/tools/embd_bf16_pack.py --gguf {final_paths(m, P)[0][0]} --out $WS/bringup/out/{name}/token-embd-bf16.gguf (then --embd-gguf)")
                if "q8_dense_gguf" in c:
                    tools.append(f"$P -I -B $REL/tools/q8_dense_gguf.py {final_paths(m, P)[0][0]} $WS/models/<new folder> (then --native / --ple-gguf there)")
                if "ple_fp8_pack" in c:
                    tools.append("$P -I -B $REL/tools/ple_fp8_pack.py --model <HF checkpoint dir> --out <ple-fp8.gguf> (needs the checkpoint)")
            cmds = make_commands(name, m, r["_sizes"], r["fit"], r["_budget"], P, params,
                                 installed or f"{cfg_target}   # after day1.py check --install-config (now: {cfg_file})",
                                 (r["need_compat_bf16"], r["maybe_compat_bf16"]), sorted(set(tools)),
                                 swap=tpl if swap else None)
            (d1 / f"commands-{name}.txt").write_text(cmds, encoding="utf-8")
            r["_day1"] = {"config": str(cfg_file), "params": str(d1 / f"params-{name}.json"),
                          "commands": str(d1 / f"commands-{name}.txt"), "installed": str(installed) if installed else None,
                          "mode": "swap" if swap else "stock"}
    write_report(out, E, P, reps, picks, type_notes, ref_rep)
    js = {"version": VERSION, "tree": {"path": E["tree"], "head": E["head"], "branch": E["branch"], "opts": E["opts"],
                                       "archs": E["archs"], "cite": E["cite"], "fallback": E["fallback"]},
          "tables": {k: sorted(tname(i) for i in E[k]) for k in ("gu", "d", "is_iq", "embed", "mmvq", "mmvq_il", "mmq",
                                                                 "fused_gu", "cpu512", "cpu256", "cpukq", "cpu512x", "cputq")},
          "params": {k: getattr(P, k) for k in ("memtotal_gib", "floor_gib", "other_gib", "headroom_gib", "chat_cache_gib",
                                                "chat_cache_ref_gib", "vram_main_mib", "overhead_main_gib", "reserve_mib",
                                                "draft_head_mib", "drafter_gib", "drafter_ref_gib", "helpers", "helper_keep_mib",
                                                "ctx", "kv", "kv_resident", "helper_eff", "cpu_us", "serial_ms")},
          "files": [jsonable(r) for r in reps],
          "picks": [{"group": list(map(str, k)), "pick": (p["file"] if p else None), "why": w,
                     "tie": [x["file"] for x in tie] or None,
                     "day1": _pieces(p, tie)}
                    for k, (p, _, w, tie) in picks.items()]}
    (out / "report.json").write_text(json.dumps(js, indent=1, default=str) + "\n", encoding="utf-8")
    # ---- short stdout summary
    print(f"engine tree {Path(E['tree']).name} @ {E['head']} ({E['branch']}); report: {out / 'report.md'}")
    if ref_rep and ref_rep.get("fit"):
        f = ref_rep["fit"]
        print(f"room today (Flash-Next's dense/K/V): 5080 {f['room_main_gib']:.2f} + helpers {sum(f['room_helpers_gib']):.2f} + "
              f"RAM {f['room_ram_gib']:.2f} = {f['room_total_gib']:.1f} GiB")
    for r in reps:
        f = r.get("fit") or {}
        t = (f.get("tiers") or {}).get("cases", {}).get("centre", {})
        print(f"  {Path(r['file']).name}: {r.get('verdict')}; experts {f.get('experts_gib', 0):.2f} GiB, room "
              f"{f.get('room_total_gib', 0):.2f}, {'fits' if f.get('fits') else 'spill %.1f GiB' % f.get('spill_gib', 0)}"
              + (f", decode ~{t['tok_s']:.0f} tok/s" if t else ""))
        st_ = r.get("shape_types") or {}
        if r.get("experts") and st_:
            bad = [x for x in st_["down"] if not x["ok"]]
            print(f"      downs by shape (n_ff {st_['n_ff']}): "
                  + (", ".join(f"{x['block']}-value blocks impossible" for x in bad) or "every block size fits")
                  + f"; this file's: {', '.join(f'{k} x{v}' for k, v in st_['down_used'].items())}")
        lay = r.get("layout") or {}
        bits = []
        if lay.get("metadata_only"):
            bits.append("shard " + ", ".join(str(x["shard"]) for x in lay["metadata_only"]) + " metadata only")
        if lay.get("split_expert_layers"):
            bits.append(f"expert layers split across shards: {[x['layer'] for x in lay['split_expert_layers']]}")
        if lay.get("ngram_shard"):
            bits.append(f"n-gram table in shard {lay['ngram_shard']}{' alone' if lay.get('ngram_alone') else ''}")
        if lay.get("mtp_sidecars"):
            bits.append(f"{len(lay['mtp_sidecars'])} separate MTP GGUF(s) beside it")
        if bits:
            print("      layout: " + "; ".join(bits))
        sm = r.get("same_model")
        if sm:
            print("      vs the served file: " + ("same model -> swap config (P028x + three paths)" if sm["swap"] else
                                                  "not a same-model swap (" + "; ".join(sm["why_not"])[:160] + ")"))
    for k, (p, _, w, tie) in picks.items():
        print(f"  PICK [{k[0]}, {k[1]}x{k[2]}]: {w.replace('**', '')}")
        for x in (tie or [p]):
            if x is not None and x.get("_day1"):
                print(f"    day one ({x['_day1']['mode']}): {x['_day1']['config']}")
    return 0


# =====================================================================================================================
# 7. Helpers for the tests' model-specific inputs
# =====================================================================================================================
def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_retok(a):
    sys.path.insert(0, str(Path(a.tree) / "tools"))
    import strata_tokenizer as ST  # noqa: E402  (the tree's own BPE; GGUF headers only)
    old = ST.Tokenizer.from_gguf(a.old_gguf)
    new = ST.Tokenizer.from_gguf(a.new_gguf)
    src, out = Path(a.src), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    names = [n.strip() for n in a.names.split(",")] if a.names else sorted(p.name for p in src.glob("*.tokens")) + \
        sorted(p.name for p in src.glob("*.prompt"))
    report = []
    for n in names:
        p = src / n if (src / n).exists() else src / f"{n}.tokens"
        ids = [int(x) for x in p.read_text().replace("\n", ",").split(",") if x.strip()]
        text = old.decode(ids)
        back = new.encode(text, parse_special=True)
        (out / p.name).write_text(",".join(map(str, back)) + "\n")
        tt = old.token_types or []
        ctl = sorted({old.tokens[i] for i in ids if i < len(tt) and tt[i] == 3})      # the template's control tokens
        lost = [c for c in ctl if c not in new.ids]
        report.append({"file": p.name, "old_tokens": len(ids), "new_tokens": len(back), "identical": back == ids,
                       "control_tokens": ctl, "not_in_new_vocab": lost})
        print(f"{p.name}: {len(ids)} -> {len(back)} tokens{' (identical ids)' if back == ids else ''}"
              + (f"; WARNING: {', '.join(lost)} not in the new vocabulary - encoded as text: render these prompts with "
                 "the new template instead" if lost else ""))
    for t in ("tf-corpus.text", "tf-math.text") if not a.names else ():
        if (src / t).exists():
            shutil.copyfile(src / t, out / t)
    (out / "retok.json").write_text(json.dumps({"old": a.old_gguf, "new": a.new_gguf, "files": report}, indent=1) + "\n")
    return 0


def cmd_pfy(a):
    Y = load_module("pf_yardstick", WS / "work/r22/pf_yardstick.py")
    Y.PR = Path(a.prompt_dir)
    if a.check or a.rest in ([], ["--check"]):
        bad = 0
        for f, cuts in Y.LONG40:
            ids = [int(x) for x in (Y.PR / f).read_text().replace("\n", ",").split(",") if x.strip()]
            short = [n for n in cuts if n and n > len(ids)]
            bad += len(short)
            print(f"{f}: {len(ids)} tokens; cuts {list(cuts)}" + (f"  BEYOND THE TEXT: {short}" if short else ""))
        print(f"long40 from {Y.PR}: {sum(len(c) for _, c in Y.LONG40)} prompts, {bad} cut(s) beyond their text")
        return 1 if bad else 0
    sys.argv = ["pf_yardstick.py"] + a.rest
    Y.main()
    return 0


def cmd_kr3(a):
    Y = load_module("pf_yardstick", WS / "work/r22/pf_yardstick.py")
    Y.PR = Path(a.prompt_dir)
    K = load_module("kernel_rule3", WS / "work/r22/kernel_rule3.py")
    K.pfy_module = lambda: Y
    sys.argv = ["kernel_rule3.py"] + a.rest
    return K.main()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="headers -> types, fit, pick, day-one pieces")
    c.add_argument("gguf", nargs="+", help="GGUF files (any shard of a split file; head-only files with NAME.size work)")
    c.add_argument("--name", help="label for the day-one config (default q4d1-<arch>-<quant>)")
    c.add_argument("--out", default=str(WS / "results/qwen4-kit/day1"), help="output folder (report, files, day1/)")
    c.add_argument("--tree", default=str(TREE), help="engine source tree whose tables are read (default strata-r22p0210)")
    c.add_argument("--ref-gguf", default=str(REF_GGUF), help="the served Flash-Next file: tokenizer / dense / compute reference")
    c.add_argument("--install-config", action="store_true", help="also copy each config to configs/<name>.json (new files only)")
    c.add_argument("--group-by", default="shape", choices=["shape", "name"], help="how candidates are grouped into models")
    c.add_argument("--files-at", action="append", metavar="DIR | GLOB=DIR",
                   help="where the download will land: config / pack / evict paths become DIR/<shard name> (DIR: every "
                        "head-only file; GLOB=DIR: files whose shard-1 name matches GLOB); repeat")
    c.add_argument("--no-swap", action="store_true",
                   help="write the new-model stock config even when a file is the served model's (same shape keys and "
                        "tokenizer); default: the same-model swap (configs/P028x.json + three paths)")
    c.add_argument("--tie-tol-gib", type=float, default=0.10,
                   help="expert bytes within this many GiB tie under Karl's rule (then quality decides; default 0.10)")
    g = c.add_argument_group("the day-one config")
    g.add_argument("--exe", help="the release's engine binary for the config")
    g.add_argument("--server", help="the release tree's serve/server.py")
    g.add_argument("--mtp", help="the model's drafter dir (--mtp); none: --spec off")
    g.add_argument("--expert-profile", default=str(WS / "strata-cstar18/data/expert-profile.bin"),
                   help="a STRP expert profile; used only when its layers x experts shape is the model's (default: "
                        "the served Flash-Next profile, 48 x 512)")
    g.add_argument("--tokenizer-dir", help="tokenizer dir for the config (default <pack>/tokenizer)")
    g.add_argument("--kl-ref", help="the published KL reference (text: table and source)")
    g.add_argument("--kl-ref-config", help="a config of a larger local quant as the KL reference run")
    b = c.add_argument_group("the expert room (defaults: this PC, measured; see the report's input table)")
    b.add_argument("--memtotal-gib", type=float, default=92.0)
    b.add_argument("--floor-gib", type=float, default=12.0)
    b.add_argument("--other-gib", type=float, default=16.3)
    b.add_argument("--headroom-gib", type=float, default=5.7)
    b.add_argument("--chat-cache-gib", type=float, default=2.0)
    b.add_argument("--chat-cache-ref-gib", type=float, default=2.0, help="the chat cache inside --other-gib")
    b.add_argument("--vram-main-mib", type=float, default=16303)
    b.add_argument("--overhead-main-gib", type=float, default=2.11)
    b.add_argument("--reserve-mib", type=int, default=713)
    b.add_argument("--draft-head-mib", type=float, default=89)
    b.add_argument("--drafter-gib", type=float, default=0.817, help="this model's drafter in VRAM (default Flash-Next's 837 MiB)")
    b.add_argument("--drafter-ref-gib", type=float, default=0.817, help="the drafter inside --overhead-main-gib")
    b.add_argument("--helper", action="append", help="helper card FREE_GIB:GBPS (repeat; default 7.56:288 = the 4060 Ti)")
    b.add_argument("--helper-keep-mib", type=float, default=512)
    b.add_argument("--ctx", type=int, default=131072)
    b.add_argument("--kv", default="int8", choices=["int8", "fp16"])
    b.add_argument("--kv-resident", type=int, default=32768)
    e = c.add_argument_group("the tier / decode model (UPGRADE-ESTIMATE.md sections 8-9)")
    e.add_argument("--helper-eff", type=float, default=0.7)
    e.add_argument("--cpu-us", type=float, default=65.0, help="us per CPU-pool entry of a 4.0 MB expert")
    e.add_argument("--serial-ms", type=float, default=2.2, help="Flash-Next's serial GPU part per token (1.9-2.5)")
    r = sub.add_parser("retok", help="re-tokenize the frozen prompt files for another tokenizer")
    r.add_argument("--new-gguf", required=True)
    r.add_argument("--old-gguf", default=str(REF_GGUF))
    r.add_argument("--src", default=str(PROMPTS))
    r.add_argument("--out", required=True)
    r.add_argument("--names", help="comma-separated file names (default: every *.tokens and *.prompt)")
    r.add_argument("--tree", default=str(TREE))
    y = sub.add_parser("pfy", help="pf_yardstick.py with another prompt folder")
    y.add_argument("prompt_dir")
    y.add_argument("--check", action="store_true")
    y.add_argument("rest", nargs=argparse.REMAINDER)
    k = sub.add_parser("kr3", help="kernel_rule3.py with another prompt folder")
    k.add_argument("prompt_dir")
    k.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    if getattr(a, "rest", None) and a.rest[:1] == ["--"]:
        a.rest = a.rest[1:]
    if a.cmd == "check":
        return cmd_check(a)
    if a.cmd == "retok":
        return cmd_retok(a)
    if a.cmd == "pfy":
        return cmd_pfy(a)
    if a.cmd == "kr3":
        return cmd_kr3(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
