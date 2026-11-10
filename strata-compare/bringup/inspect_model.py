#!/usr/bin/env python3
"""inspect_model.py MODEL-00001-of-0000N.gguf [--mtp DIR] [--tree ENGINE_TREE] [--series-tree TREE] [--json OUT] — what a
GGUF needs from this engine, from its HEADERS only (gguf_head.py: metadata + tensor table, never the tensor data; every
shard is read; a head-only file from bringup/fetch_model.py --heads works the same).

Reports:
  0. the engine path the release runs this architecture on (10-27, v0.2.6: three paths - `qwen4exp` = Flash-Next's path
     in `strata` (an iq_pack.py pack, --native / --ple-gguf / --mtp DIR); `qwen35moe` = the own path in `strata`
     (src/qwen35, chosen by the file at the top of main(): no pack, tokenizer only); `deepseek41` = `strata-dsv41`
     (-DSTRATA_BUILD_DSV41=ON, tools/dsv41/pack_gguf.py); read from the TREE's model_family.hpp, so a release that adds
     a family is seen without editing this file - its checks then are the engine's own, at load)
  1. tensor roles (blk.N.<role>): shapes, formats, bytes; routed experts per layer
  2. trunk layers vs an MTP / nextn block (block_count, nextn_predict_layers, blk indices, nextn tensors)
  3. tokenizer: model / pre-tokenizer, vocabulary, end-of-text / BOS / pad ids and their text, control (type 3) and
     always-special (type 4) tokens, the chat template's markers
  4. the n-gram (PLE) table: type, shape, ngram size / heads / row length
  5. against the engine: upstream's fixed geometry and formats (v0.2.6: include/strata/core/geometry.hpp
     kCompiledGeometry, pinned by gguf_reader.hpp geometry_unsupported(); the six keys read_geometry() requires; the
     kernels' format lists read from the tree), then each guarded local patch's assumption (patches/LEDGER.md; the
     guards and compiled constants are read from SERIES_TREE's own src/core/patch_guard.cpp, default the served P021m
     tree - a stock tree has no guards)
Verdict, one of:
  RUNS | RUNS WITH THESE PATCHES OFF: ... | NEEDS UPSTREAM SUPPORT FOR EXACTLY THIS: ...
#911 (setup --inspect) was the starting point; v0.2.6 ships its own header check (tools/strata_inspect.py, quantscope:
remote headers by range requests, compared with setup's known files) - run it too on day one, it knows the provider files."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_head import GGML_TYPES, read_model  # noqa: E402

WS = Path("/home/USER/ai-speed-testing/strata-compare")
TN = {k: v[0] for k, v in GGML_TYPES.items()}
STOCK_TREE = WS / "strata-v026"          # 10-27: the accepted release (baseline v0.2.6)
SERIES_TREE = WS / "strata-r22p021m"     # 10-27: the served P021m's tree (v0.2.1 + our 30 commits): the guards

# ---- fall-backs when a tree does not say (v0.2.6's lists; the code that decides, for the runbook's update step)
IS_IQ = {16, 17, 18, 20, 21, 22, 23, 29, 42, 11, 12, 13, 7, 6, 2, 3, 8, 40, 144, 145, 146}   # iq_kernels.cu is_iq()
EMBED_EXTRA = {30, 14}                                                      # embed_type_supported(): is_iq + BF16 + Q6_K
MMVQ_OK = {2, 6, 7, 8, 11, 12, 13, 14, 20, 23, 42, 16, 17, 18, 21, 22, 29}  # native_mmvq.cu native_mmvq_supported()
DENSE_FLOAT = {0, 1, 30}                                                    # F32 / F16 / BF16 (norms, hc, router, ...)
PLE_OK = {20: "IQ4_NL", 6: "Q5_0", 7: "Q5_1 (#896)", 8: "Q8_0 (#896)"}       # ngram.cpp PleTable (+ I8 = FP8)
MTP_LAYERS_SUPPORTED = 1                                                    # the drafter: one MTP layer (--mtp)
# geometry.hpp kCompiledGeometry (v0.2.6): Qwen3.8-Flash-Next's shape
FLASH_NEXT = {"n_embd": 2560, "n_layers": 48, "qsa_interval": 4, "ssm_state": 128, "ssm_groups": 16, "ssm_v_heads": 48,
              "ssm_conv": 4, "ssm_inner": 6144, "n_head": 24, "n_head_kv": 2, "head_dim": 256, "n_rot": 64,
              "idx_heads": 4, "idx_key": 128, "idx_block": 4, "idx_top_k": 2048, "hc": 4, "hc_lr": 320, "n_ff": 640,
              "rms_eps": 1e-6}
# gguf_reader.hpp geometry_unsupported() (v0.2.6): every key it pins, in its order (expert_count, expert_used_count and
# the vocabulary are free: the router and the head take them at run time)
PINS = [("block_count", "n_layers"), ("embedding_length", "n_embd"), ("full_attention_interval", "qsa_interval"),
        ("ssm.state_size", "ssm_state"), ("ssm.group_count", "ssm_groups"), ("ssm.time_step_rank", "ssm_v_heads"),
        ("ssm.conv_kernel", "ssm_conv"), ("ssm.inner_size", "ssm_inner"), ("attention.head_count", "n_head"),
        ("attention.head_count_kv", "n_head_kv"), ("attention.key_length", "head_dim"),
        ("rope.dimension_count", "n_rot"), ("attention.indexer.head_count", "idx_heads"),
        ("attention.indexer.key_length", "idx_key"), ("attention.indexer.top_k", "idx_top_k"),
        ("hyper_connection.count", "hc"), ("hyper_connection.low_rank", "hc_lr"), ("expert_feed_forward_length", "n_ff")]
REQUIRED = ("block_count", "embedding_length", "expert_count", "expert_used_count", "attention.head_count",
            "attention.head_count_kv")                                      # read_geometry(): the six required keys
# gguf_reader.hpp check_architecture_qwen35moe() (v0.2.6): every key Qwen3.6's geometry is read from
Q35_KEYS = ("block_count", "embedding_length", "attention.head_count", "attention.head_count_kv", "attention.key_length",
            "attention.value_length", "expert_count", "expert_used_count", "expert_feed_forward_length",
            "expert_shared_feed_forward_length", "ssm.conv_kernel", "ssm.state_size", "ssm.group_count",
            "ssm.time_step_rank", "ssm.inner_size", "full_attention_interval", "nextn_predict_layers")
Q36_EOS = {248044, 248046}            # src/qwen35/q36_engine.cu is_eos(): the Qwen3.5/3.6/3.8 tokenizer's ids, hard-coded
TURN_TOKEN = 248045                   # generate.cpp --turn-token default (<|im_start|>) on the qwen4exp path


def _read(p: Path) -> str:
    return p.read_text(errors="replace") if p.exists() else ""


def compiled_constants(tree: Path, series: Path | None = None) -> dict:
    """The constants upstream's (and our patches') code is compiled for, read from the source trees: the geometry from
    TREE (v0.2.x geometry.hpp, older trees layout.hpp), the patch kernels' constants from SERIES (else TREE)."""
    c = {}

    def grab(root, rel, names):
        s = _read(root / rel)
        for n, key in names.items():
            m = re.search(rf"\b{re.escape(n)}\s*=\s*(\d+)\s*;", s)
            if m and key not in c:
                c[key] = int(m.group(1))

    geo = {"n_embd": "n_embd", "n_layers": "n_layers", "qsa_interval": "qsa_interval", "ssm_state_size": "ssm_state",
           "ssm_k_heads": "ssm_groups", "ssm_v_heads": "ssm_v_heads", "ssm_d_conv": "ssm_conv",
           "ssm_value_dim": "ssm_inner", "n_head": "n_head", "n_head_kv": "n_head_kv", "head_dim": "head_dim",
           "n_rot": "n_rot", "idx_q_heads": "idx_heads", "idx_key_dim": "idx_key", "idx_block": "idx_block",
           "idx_top_k": "idx_top_k", "hc": "hc", "hc_lr": "hc_lr", "n_ff": "n_ff", "n_vocab": "n_vocab"}
    grab(tree, "include/strata/core/geometry.hpp", geo)          # v0.2.x: ModelGeometry's defaults = kCompiledGeometry
    grab(tree, "include/strata/core/layout.hpp", geo)            # <= v0.1.4x
    m = re.search(r"\brms_eps\s*=\s*([0-9.eE+-]+)\s*;", _read(tree / "include/strata/core/geometry.hpp"))
    if m:
        c["rms_eps"] = float(m.group(1))
    c["geometry_from_tree"] = "n_embd" in c                      # False: the fall-backs (FLASH_NEXT) were used
    grab(tree, "include/strata/kernels/ngram.hpp", {"PLE_HEAD_DIM": "ple_dim", "NGRAM_SIZE": "ple_ngram",
                                                    "HEADS_PER_NGRAM": "ple_heads", "PLE_CONV_KERNEL": "ple_conv",
                                                    "PLE_EOS_TOKEN_ID": "ple_eos"})
    k = series if series and series.exists() else tree
    grab(k, "src/kernels/cuda/fused_gr.cu", {"N": "gr_n", "HC": "gr_hc", "LR": "gr_lr"})
    grab(k, "src/kernels/cuda/qsa_prompt_attn.cu", {"HD": "attn_hd", "G": "attn_g"})
    m = re.search(r"native_embed\.load\([^;]*?g0\.n_embd,\s*(\d+)", _read(tree / "src/program/generate.cpp"), re.S)
    if m:
        c["embed_vocab"] = int(m.group(1))
    for key, v in FLASH_NEXT.items():
        c.setdefault(key, v)
    return c


def families_of(tree: Path) -> dict:
    """10-27: architecture -> the engine path that runs it in TREE: {arch: {family, binary, cmake, pack, note}}.
    model_family.hpp model_family_from_arch() lists the families the reader knows (v0.2.6: qwen4exp, qwen35moe); a
    family whose path exists is runnable; deepseek41 when the tree has src/dsv41 (CMakeLists STRATA_BUILD_DSV41)."""
    out = {}
    s = _read(tree / "include/strata/artifact/model_family.hpp")
    pairs = re.findall(r'arch == "([A-Za-z0-9_.-]+)"\) return ModelFamily::(\w+)', s) if s else [("qwen4exp", "Qwen4Exp")]
    has_q35 = "STRATA_HAVE_QWEN35" in _read(tree / "CMakeLists.txt")
    for arch, fam in pairs:
        if fam == "Qwen4Exp":
            out[arch] = dict(family=fam, binary="strata", cmake=[], pack="iq_pack",
                             note="Flash-Next's path: tools/iq_pack.py pack, --native / --ple-gguf / --mtp DIR")
        elif fam == "Qwen35Moe" and has_q35:
            out[arch] = dict(family=fam, binary="strata", cmake=[], pack="tokenizer",
                             note="the own path src/qwen35 (generate.cpp's family switch, STRATA_HAVE_QWEN35): no pack, "
                                  "profile or RAM budget - the engine places the experts itself; --mtp N = drafts per step")
        else:
            out[arch] = dict(family=fam, binary="strata", cmake=[], pack="?",
                             note=f"ModelFamily::{fam}: known to this tree's reader; this inspector has no checks for it "
                                  "(the engine's own guard decides at load; read the release notes for its pack and flags)")
    if (tree / "src/dsv41").is_dir():
        out["deepseek41"] = dict(family="DeepSeek41", binary="strata-dsv41", cmake=["-DSTRATA_BUILD_DSV41=ON"],
                                 pack="dsv41", note="its own engine (src/dsv41): tools/dsv41/pack_gguf.py with the Engram "
                                                    "file and the DSpark drafter (work/ds41/pack.sh is ours)")
    return out


def cmake_default_on(tree: Path | None, option: str) -> bool:
    """10-27: True when TREE's CMakeLists.txt declares OPTION with default ON (v0.2.6: STRATA_MMQ_KQUANTS and
    STRATA_Q6K_EXPERTS are ON by default, so the build needs no -D for them)."""
    return bool(tree) and bool(re.search(rf'option\({option}\s+"[^"]*"\s+ON\)', _read(tree / "CMakeLists.txt")))


def expert_types_of(tree: Path | None):
    """Round 15: the routed-expert formats the TREE's iq_kernels.cu is_iq() takes: (always, opt-in build -> its option).
    v0.1.40.2 puts Q6_K behind `#ifdef STRATA_Q6K_EXPERTS`; 10-27: v0.2.6 builds it by default (option ON), so the
    opt-in types count as always there; falls back to IS_IQ."""
    src = (tree / "src/kernels/cuda/iq_kernels.cu") if tree else None
    if not src or not src.exists():
        return set(IS_IQ), {}
    m = re.search(r"bool is_iq\(int t\)\s*\{(.*?)\n\}", src.read_text(errors="replace"), re.S)
    if not m:
        return set(IS_IQ), {}
    body = m.group(1)
    mi = re.search(r"#ifdef (\w+)\n(.*?)#else\n(.*?)#endif", body, re.S)
    nums = lambda x: {int(v) for v in re.findall(r"t == (\d+)", x)}  # noqa: E731
    if not mi:
        return nums(body), {}
    head = body[:mi.start()]
    base = nums(head) | nums(mi.group(3))
    opt = {t: "-D" + mi.group(1) + "=ON" for t in nums(head) | nums(mi.group(2)) if t not in base}
    if cmake_default_on(tree, mi.group(1)):
        return base | set(opt), {}
    return base, opt


def type_list(tree: Path | None, rel: str, fn: str, fallback: set) -> set:
    """10-27: the types a kernel entry point takes, read from the tree (`bool FN(int t) ... { return t == 2 || ...`)."""
    s = _read(tree / rel) if tree else ""
    m = re.search(rf"bool {fn}\(int \w+\)\s*(?:noexcept\s*)?\{{(.*?)\}}", s, re.S)
    if not m:
        return set(fallback)
    got = {int(v) for v in re.findall(r"== (\d+)", m.group(1))}
    if "is_iq(" in m.group(1):
        got |= expert_types_of(tree)[0]
    return got or set(fallback)


def role_of(name: str) -> str:
    return re.sub(r"^blk\.\d+\.", "blk.N.", name)


def shape_summary(m, roles) -> dict:
    """10-27: what kind of model this is, for an architecture no path runs yet (which path it resembles)."""
    has = lambda pat: any(re.search(pat, k) for k in roles)  # noqa: E731
    return {"moe": has(r"_exps\.weight$"), "gdn": has(r"ssm_(alpha|beta|a$|conv1d)"), "indexer": has(r"indexer\."),
            "hyper_connections": has(r"^blk\.N\.hc_"), "ple": "per_layer_token_embd.weight" in m.tensors,
            "nextn": has(r"nextn|\.mtp"), "dense_ffn": has(r"^blk\.N\.ffn_(gate|up|down)\.weight$")}


def inspect(path: str, mtp: str | None = None, tree: str | None = None, series: str | None = None) -> dict:
    m = read_model(path)
    arch = m.arch()
    a = m.a
    T = Path(tree) if tree else STOCK_TREE
    S = Path(series) if series else SERIES_TREE
    C = compiled_constants(T, S)
    fams = families_of(T)
    eng = fams.get(arch)
    rep: dict = {"file": m.paths, "arch": arch, "gguf_version": m.version, "notes": [], "upstream": [], "patches": [],
                 "build": [], "tree": str(T), "series_tree": str(S) if S.exists() else None,
                 "engine": dict(eng, arch=arch) if eng else None, "head_only": any(m.head_only),
                 "file_gib": round(m.file_bytes() / 2**30, 2)}
    # ---- 1. roles
    roles = defaultdict(lambda: {"types": Counter(), "shape": None, "bytes": 0, "n": 0})
    layers = set()
    for t in m.tensors.values():
        r = roles[role_of(t.name)]
        r["types"][t.type_name] += 1
        r["shape"] = r["shape"] or list(t.shape)
        r["bytes"] += t.nbytes
        r["n"] += 1
        mm = re.match(r"blk\.(\d+)\.", t.name)
        if mm:
            layers.add(int(mm.group(1)))
    rep["roles"] = {k: {"types": dict(v["types"]), "shape": v["shape"], "gib": round(v["bytes"] / 2**30, 3), "n": v["n"]}
                    for k, v in sorted(roles.items())}
    rep["shape"] = shape_summary(m, rep["roles"])
    exp_bytes = sum(v["bytes"] for k, v in roles.items() if k.endswith("_exps.weight"))
    ple_t = m.tensors.get("per_layer_token_embd.weight")
    if ple_t is not None:
        rep["ple_shard"] = m.paths[ple_t.shard]           # the shard that holds the n-gram table (--ple-gguf)
    rep["bytes"] = {"experts_gib": round(exp_bytes / 2**30, 2),
                    "ngram_table_gib": round(ple_t.nbytes / 2**30, 2) if ple_t else 0,
                    "dense_gib": round((sum(t.nbytes for t in m.tensors.values()) - exp_bytes - (ple_t.nbytes if ple_t else 0)) / 2**30, 2),
                    "total_gib": round(sum(t.nbytes for t in m.tensors.values()) / 2**30, 2)}
    # ---- 2. trunk vs MTP
    bc = a("block_count", 0)
    nextn = a("nextn_predict_layers", 0)
    nextn_tensors = sorted({role_of(t.name) for t in m.tensors.values() if "nextn" in t.name or ".mtp" in t.name})
    trunk = bc - nextn
    beyond = sorted(i for i in layers if i >= trunk)
    rep["layers"] = {"block_count": bc, "nextn_predict_layers": nextn, "trunk": trunk,
                     "blk_indices": f"{min(layers) if layers else '-'}..{max(layers) if layers else '-'} ({len(layers)})",
                     "blocks_past_trunk": beyond, "nextn_roles": nextn_tensors}
    # ---- 3. tokenizer and template
    toks = m.get("tokenizer.ggml.tokens") or []
    ttype = m.get("tokenizer.ggml.token_type") or []
    ctl = [toks[i] for i, x in enumerate(ttype) if x == 3]
    always = [toks[i] for i, x in enumerate(ttype) if x == 4]
    tid = lambda k: m.get(f"tokenizer.ggml.{k}")  # noqa: E731
    tmpl = m.get("tokenizer.chat_template") or ""
    markers = ["<|im_start|>", "<|im_end|>", "<|endoftext|>", "<think>", "</think>", "<tool_call>", "</tool_call>",
               "<function=", "<parameter=", "<tool_response>", "<|vision_start|>", "<|image_pad|>"]
    ids = {t: i for i, t in enumerate(toks)} if toks else {}
    rep["tokenizer"] = {"model": m.get("tokenizer.ggml.model"), "pre": m.get("tokenizer.ggml.pre"), "vocab": len(toks),
                        "eos": [tid("eos_token_id"), toks[tid("eos_token_id")] if isinstance(tid("eos_token_id"), int) and tid("eos_token_id") < len(toks) else None],
                        "bos": [tid("bos_token_id"), toks[tid("bos_token_id")] if isinstance(tid("bos_token_id"), int) and tid("bos_token_id") < len(toks) else None],
                        "pad": tid("padding_token_id"), "im_start": ids.get("<|im_start|>"), "control_tokens": len(ctl),
                        "control_sample": ctl[:6], "always_special": always, "chat_template_chars": len(tmpl),
                        "template_markers": {k: (k in tmpl) for k in markers}}
    # ---- 4. n-gram table
    if ple_t is not None:
        fmt = PLE_OK.get(ple_t.type) or ("FP8 (I8)" if ple_t.type == 24 else None)
        rep["ngram_table"] = {"type": ple_t.type_name, "shape": list(ple_t.shape), "gib": round(ple_t.nbytes / 2**30, 2),
                              "ngram_size": a("ple.ngram_size"), "heads_per_ngram": a("ple.heads_per_ngram"),
                              "row": a("embedding_length_per_layer_input"), "supported": fmt is not None}
    else:
        rep["ngram_table"] = None
    # ---- the shards (round 15): a shard without tensors whose header is not padded to the alignment - the engine's
    # GGUF reader (gguf_reader.hpp) computes its data section at the aligned offset and refuses "data section starts past
    # EOF" (Unsloth's UD-Q5_K_XL shard 1: 10,946,618 bytes; llama.cpp / gguf-py read it)
    align = m.get("general.alignment", 32) or 32
    for i, (hend, fsize, nt) in enumerate(m.shard_layout):
        if nt == 0 and (hend + align - 1) // align * align > fsize:
            rep["upstream"].append(f"shard {i + 1} ({Path(m.paths[i]).name}) has no tensors and ends {((hend + align - 1) // align * align) - fsize} "
                                   f"byte(s) before its aligned data section: the engine's GGUF reader refuses it (\"data section "
                                   f"starts past EOF\") - your fallback 2 (splice) or 3 (a loader fix)")
    # ---- routed experts (shared by the qwen paths: iq_kernels.cu native_expert_supported(): gate/up and down in
    # is_iq(), n_embd % 256 == 0, rows whole blocks)
    exp_types = Counter()
    exp_ok, exp_opt = expert_types_of(T)
    n_embd, n_ff = a("embedding_length", 0), a("expert_feed_forward_length", 0)
    for t in m.tensors.values():
        if t.name.endswith("_exps.weight"):
            exp_types[t.type_name] += 1
    rep["expert_types"] = dict(exp_types)
    if eng is None:
        # ---- 0b. an architecture this release has no path for
        known = ", ".join(f"{k} [{v['binary']}{', ' + v['family'] if v['binary'] == 'strata' else ''}]" for k, v in fams.items())
        sh = rep["shape"]
        rep["upstream"].append(f"architecture '{arch}': {T.name} runs {known or 'qwen4exp'}")
        if not sh["moe"]:
            rep["upstream"].append("no routed experts (a dense model): every Strata path is a mixture-of-experts engine "
                                   "(experts offloaded to RAM / a helper card); a dense model needs llama.cpp or a new path")
        like = ("qwen4exp (GDN + QSA indexer + hyper-connections" + (" + PLE" if sh["ple"] else "") + ")"
                if sh["gdn"] and sh["indexer"] and sh["hyper_connections"] else
                "qwen35moe (GDN + dense attention, no hyper-connections)" if sh["gdn"] and not sh["hyper_connections"] else
                "none of the Qwen paths (no GDN layers)")
        rep["notes"].append(f"shape: {', '.join(k for k, v in sh.items() if v) or '-'} -> closest path: {like}")
    elif eng["family"] == "Qwen4Exp":
        _qwen4exp_checks(rep, m, a, C, T, ple_t, toks, ids, trunk, nextn, nextn_tensors, beyond, bc, exp_ok, exp_opt)
    elif eng["family"] == "Qwen35Moe":
        missing = [k for k in Q35_KEYS if a(k) is None]
        if missing:
            rep["upstream"].append(f"{arch}: missing {', '.join(arch + '.' + k for k in missing)} (gguf_reader.hpp "
                                   f"check_architecture_qwen35moe: every key the geometry is read from)")
        if bc and nextn >= bc:
            rep["upstream"].append(f"{arch}.nextn_predict_layers {nextn} is not smaller than block_count {bc}")
        if (a("full_attention_interval") or 0) < 2:
            rep["upstream"].append(f"{arch}.full_attention_interval must be at least 2 (the GDN / attention pattern)")
        bad_eos = sorted({x for x in (tid("eos_token_id"), tid("padding_token_id")) if isinstance(x, int)} - Q36_EOS)
        if bad_eos:
            rep["upstream"].append(f"end-of-text / pad id(s) {bad_eos}: the qwen35 path stops only at {sorted(Q36_EOS)} "
                                   f"(src/qwen35/q36_engine.cu is_eos(), hard-coded) - another tokenizer needs a new release")
        rep["notes"].append("qwen35 path: the geometry comes from the file (nothing pinned); the drafter is the file's own "
                            f"nextn block ({nextn} layer(s)); --mtp N = drafts per step (setup writes 2)")
    elif eng["family"] == "DeepSeek41":
        ef = a("engram.file")
        rep["notes"].append(f"deepseek41: strata-dsv41 path; the Engram table {ef or '-'} and the DSpark drafter are "
                            f"separate files (work/ds41/pack.sh: pack_gguf.py --engram / --engram-meta / --dspark-gguf)")
        if ef and not (Path(m.paths[0]).parent / ef).exists() and not any(m.head_only):
            rep["upstream"].append(f"the Engram file {ef} named by {arch}.engram.file is not beside the shards")
    # experts: every Qwen path computes them with the same native expert kernels
    if eng and eng["family"] in ("Qwen4Exp", "Qwen35Moe"):
        for t in m.tensors.values():
            if not t.name.endswith("_exps.weight"):
                continue
            if t.type in exp_opt:
                if exp_opt[t.type] not in rep["build"]:
                    rep["build"].append(exp_opt[t.type])
            elif t.type not in exp_ok:
                rep["upstream"].append(f"{t.name} is {t.type_name}: routed experts take {sorted(TN.get(x, x) for x in exp_ok)}"
                                       + (f" (+ {', '.join(TN[x] + ' with ' + o for x, o in exp_opt.items())})" if exp_opt else ""))
                break
        if n_embd % 256:
            rep["upstream"].append(f"embedding_length {n_embd} is not a multiple of 256 (iq_kernels.cu native_expert_supported)")
        dn = next((t for t in m.tensors.values() if t.name.endswith("ffn_down_exps.weight")), None)
        if dn is not None and n_ff and n_ff % GGML_TYPES.get(dn.type, ("", 1, 0))[1]:
            rep["upstream"].append(f"expert_feed_forward_length {n_ff} is not whole {dn.type_name} blocks (native_expert_supported)")
    # ---- 5b. the guarded patches (the same checks as the SERIES tree's patch_guard.cpp; a stock tree has none)
    if eng and eng["family"] == "Qwen4Exp":
        rep["patches"] = _series_guards(m, a, C, S, ple_t, toks, mtp, rep)
    # ---- verdict
    if rep["upstream"]:
        rep["verdict"] = "NEEDS UPSTREAM SUPPORT FOR EXACTLY THIS: " + " | ".join(rep["upstream"])
    elif rep["patches"]:
        rep["verdict"] = "RUNS WITH THESE PATCHES OFF: " + ", ".join(f"{p['guard']} ({p['why']})" for p in rep["patches"])
    else:
        rep["verdict"] = "RUNS"
    if rep["verdict"].startswith("RUNS") and eng:
        rep["verdict"] += f" [{eng['binary']}{' ' + ' '.join(eng['cmake']) if eng['cmake'] else ''}, {eng['family']} path]"
    if rep["build"]:
        rep["verdict"] += " [build option: " + " ".join(rep["build"]) + "]"
    return rep


def _qwen4exp_checks(rep, m, a, C, T, ple_t, toks, ids, trunk, nextn, nextn_tensors, beyond, bc, exp_ok, exp_opt):
    """Flash-Next's path: the geometry the kernels are compiled for (v0.2.6 geometry_unsupported), the formats, the
    n-gram table, the token ids the serve path assumes."""
    arch = m.arch()
    if not C.get("geometry_from_tree"):
        rep["notes"].append(f"{T.name}: no geometry.hpp / layout.hpp constants found - the checks use v0.2.6's values")
    for key in REQUIRED:
        if a(key) is None:
            rep["upstream"].append(f"{arch}.{key} missing (read_geometry requires it)")
    # v0.2.6 pins block_count itself (read_geometry reads it as n_layers; nothing reads qwen4exp.nextn_predict_layers)
    reads_nextn = bool(re.search(r'"nextn_predict_layers"|qwen4exp\.nextn', re.sub(r'"qwen35moe\.[^"]*"', "",
                                 _read(T / "include/strata/artifact/gguf_reader.hpp"))))
    for key, ck in PINS:
        v = a(key)
        w = C.get(ck)
        if key == "block_count" and reads_nextn:
            v = trunk
        if v is None:
            if key not in REQUIRED:
                rep["notes"].append(f"{arch}.{key} absent: the compiled {w} is used")
        elif v != w:
            rep["upstream"].append(f"{arch}.{key} = {v}, the kernels are compiled for {w} (geometry.hpp kCompiledGeometry, "
                                   f"gguf_reader.hpp geometry_unsupported)")
    if nextn_tensors and not nextn:
        rep["upstream"].append(f"the file holds nextn / MTP tensors ({', '.join(nextn_tensors[:3])}) but declares no "
                               f"nextn_predict_layers: block_count {bc} would be read as a {bc}-layer trunk")
    if beyond and not nextn:
        rep["upstream"].append(f"blk.{beyond[0]}..{beyond[-1]} past a {trunk}-layer trunk with no nextn_predict_layers")
    if nextn:
        rep["notes"].append(f"an in-file MTP block of {nextn} layer(s): {T.name}'s qwen4exp path "
                            f"{'reads the trunk' if reads_nextn else 'pins block_count itself (no nextn read; our #619 read past it on v0.1.39)'}; "
                            f"the drafter still comes from --mtp DIR")
        if nextn > MTP_LAYERS_SUPPORTED:
            rep["upstream"].append(f"nextn_predict_layers = {nextn}: the drafter runs {MTP_LAYERS_SUPPORTED} MTP layer (--mtp)")
    vl, kl = a("attention.value_length"), a("attention.key_length")
    if vl is not None and kl is not None and vl != kl:
        rep["upstream"].append(f"{arch}.attention.value_length {vl} != key_length {kl} (one head width for both)")
    sh = a("expert_shared_feed_forward_length")
    if sh is not None and a("expert_feed_forward_length") is not None and sh != a("expert_feed_forward_length"):
        rep["upstream"].append(f"{arch}.expert_shared_feed_forward_length {sh} != expert_feed_forward_length (read with one width)")
    used, ne = a("expert_used_count", 0), a("expert_count", 0)
    if used > min(ne or 64, 64):
        rep["upstream"].append(f"{arch}.expert_used_count {used}: the router takes 1..{min(ne or 64, 64)}")
    if ne and ne != 512:
        rep["notes"].append(f"expert_count {ne} (512 in Flash-Next): free in v0.2.6 (the Coder ships 256); the expert "
                            f"profile and the helper slots must be made for it")
    eps = a("attention.layer_norm_rms_epsilon")
    if eps is not None and abs(eps - C["rms_eps"]) > 1e-6 * C["rms_eps"]:
        rep["upstream"].append(f"{arch}.attention.layer_norm_rms_epsilon {eps:g}, the norm kernels are compiled for {C['rms_eps']:g}")
    cr = a("attention.compress_ratios")
    if isinstance(cr, list) and any(cr):
        qi = a("full_attention_interval", C["qsa_interval"]) or C["qsa_interval"]
        bad = [i for i, r in enumerate(cr) if (r != 0) != (i % qi == qi - 1)]
        if bad or len(cr) != bc:
            rep["upstream"].append(f"{arch}.attention.compress_ratios does not match full_attention_interval {qi} "
                                   f"(layer {bad[0] if bad else '-'}; {len(cr)} entries for {bc} layers)")
    # the n-gram table
    if ple_t is not None:
        if ple_t.type not in PLE_OK and ple_t.type != 24:
            rep["upstream"].append(f"per_layer_token_embd.weight is {ple_t.type_name}: the n-gram table reader takes "
                                   f"IQ4_NL, Q5_0, Q5_1, Q8_0 or FP8 (I8)")
        for key, ck, where in (("ple.ngram_size", "ple_ngram", "ngram.hpp NGRAM_SIZE"),
                               ("ple.heads_per_ngram", "ple_heads", "ngram.hpp HEADS_PER_NGRAM"),
                               ("embedding_length_per_layer_input", "ple_dim", "ngram.hpp PLE_HEAD_DIM"),
                               ("ple.conv_kernel", "ple_conv", "ngram.hpp PLE_CONV_KERNEL"),
                               ("ple.eos_token_id", "ple_eos", "ngram.hpp PLE_EOS_TOKEN_ID")):
            v = a(key)
            if ck in C and v is not None and v != C[ck]:
                rep["upstream"].append(f"{arch}.{key} = {v}, the engine is built for {C[ck]} ({where})")
    else:
        rep["upstream"].append("no per_layer_token_embd (n-gram / PLE) table: the qwen4exp graph has a PLE stage")
    if "embed_vocab" in C and len(toks) != C["embed_vocab"]:
        rep["upstream"].append(f"vocabulary of {len(toks)}; the token embedding loader is called with {C['embed_vocab']} rows")
    if ids and ids.get("<|im_start|>") != TURN_TOKEN:
        rep["notes"].append(f"<|im_start|> is id {ids.get('<|im_start|>')}, not {TURN_TOKEN}: give the engine --turn-token "
                            f"{ids.get('<|im_start|>')} (its conversation checkpoints cut at that token)")
    # formats (read from the tree: iq_kernels.cu embed_type_supported, native_mmvq.cu native_mmvq_supported)
    embed_ok = type_list(T, "src/kernels/cuda/iq_kernels.cu", "embed_type_supported", IS_IQ | EMBED_EXTRA)
    mmvq_ok = type_list(T, "src/kernels/cuda/native_mmvq.cu", "native_mmvq_supported", MMVQ_OK)
    te = m.tensors.get("token_embd.weight")
    if te is None or te.type not in embed_ok:
        rep["upstream"].append(f"token_embd.weight is {te.type_name if te else 'missing'}: the embedding takes "
                               f"{sorted(TN.get(x, x) for x in embed_ok)} (iq_kernels.cu embed_type_supported)")
    out = m.tensors.get("output.weight")
    if out is None or out.type not in mmvq_ok:
        rep["upstream"].append(f"output.weight is {out.type_name if out else 'missing'}: the head takes "
                               f"native_mmvq_supported types")
    for t in m.tensors.values():
        if t.name.endswith("_exps.weight") or t.name in ("token_embd.weight", "output.weight", "per_layer_token_embd.weight"):
            continue
        if len(t.shape) >= 2 and t.type not in mmvq_ok and t.type not in DENSE_FLOAT:
            rep["upstream"].append(f"{t.name} is {t.type_name}: dense projections take native_mmvq types or F32/F16/BF16")
            break
    if rep["roles"].get("blk.N.ffn_down_exps.weight") and "Q6_K" in str(rep["expert_types"]) and not exp_opt:
        rep["notes"].append("Q6_K experts: built by default in this tree (STRATA_Q6K_EXPERTS ON)")


def _series_guards(m, a, C, S, ple_t, toks, mtp, rep) -> list:
    """The guards of our series (the SERIES tree's src/core/patch_guard.cpp: P021m has spec_exact, side_mixer,
    router_q8k, qsa_split_attn, gr_fork, draft_cum, prefill_v2), evaluated on this file."""
    f = {"n_embd": a("embedding_length", 0), "n_ff": a("expert_feed_forward_length", 0), "hc": a("hyper_connection.count", 0),
         "hc_lr": a("hyper_connection.low_rank", 0), "key": a("attention.key_length", 0),
         "g": (a("attention.head_count", 0) // a("attention.head_count_kv", 1)) if a("attention.head_count_kv") else 0,
         "fai": a("full_attention_interval", 0)}
    gdn = any(t.name.endswith(".ssm_alpha.weight") for t in m.tensors.values())
    qsa = any(t.name.endswith(".indexer.q_proj.weight") for t in m.tensors.values())
    bad_dense = [t.name for t in m.tensors.values() if t.type in (23, 12, 13, 14, 8) and len(t.shape) == 2 and "_exps" not in t.name
                 and t.name not in ("token_embd.weight", "per_layer_token_embd.weight") and t.shape[0] % (32 if t.type == 8 else 256)]
    gu_types = {t.type_name for t in m.tensors.values() if t.name.endswith("ffn_gate_exps.weight")}
    d_types = {t.type_name for t in m.tensors.values() if t.name.endswith("ffn_down_exps.weight")}
    pg = []
    if not (f["n_ff"] % 32 == 0 and f["n_embd"] % 32 == 0):
        pg.append(("pr245", "STRATA_EXPERTS_OLD=1", f"n_embd {f['n_embd']} / n_ff {f['n_ff']} not multiples of 32"))
    if ple_t is None or (a("ple.ngram_size"), a("ple.heads_per_ngram"), a("embedding_length_per_layer_input")) != (C.get("ple_ngram", 3), C.get("ple_heads", 8), C.get("ple_dim", 160)):
        pg.append(("ple_prefetch", "STRATA_PLE_PREFETCH=0", "the n-gram table's shape is not ngram.hpp's"))
    if not (gdn and qsa and f["fai"] == 4):
        pg.append(("side_mixer", "STRATA_SIDE_MIXER=0", "not 0.1.39's GDN x3 + QSA-with-indexer window"))
    if f["n_embd"] % 256:
        pg.append(("router_q8k", "STRATA_ROUTER_Q8K=0", f"n_embd {f['n_embd']} not a multiple of 256"))
    if (f["key"], f["g"]) != (C.get("attn_hd", 256), C.get("attn_g", 12)):
        pg.append(("qsa_split_attn", "STRATA_QSA_SPLIT_ATTN=0", f"head size {f['key']} / group {f['g']} vs compiled {C.get('attn_hd')} / {C.get('attn_g')}"))
    if bad_dense:
        pg.append(("mmvq_il", "STRATA_MMVQ_IL=0", f"{bad_dense[0]}: rows not whole blocks"))
    if (f["n_embd"], f["hc"], f["hc_lr"]) != (C.get("gr_n", 2560), C.get("gr_hc", 4), C.get("gr_lr", 320)):
        pg.append(("gr_fork", "STRATA_GR_FORK=0", f"n_embd / streams / low rank {f['n_embd']} / {f['hc']} / {f['hc_lr']} vs compiled "
                   f"{C.get('gr_n')} / {C.get('gr_hc')} / {C.get('gr_lr')}"))
    # r22 (P021m): Basalt's cumulative draft table is the qwen4exp drafter's; the v2 prompt kernels are compiled for
    # K = 2560 / 640 and IQ3_XXS gate/up or IQ4_NL down
    if m.arch() != "qwen4exp":
        pg.append(("draft_cum", "STRATA_DRAFT_CUM=0", f"architecture {m.arch()}: its table was measured on the qwen4exp drafter"))
    if (f["n_embd"], f["n_ff"]) != (2560, 640) or not ({"IQ3_XXS"} & gu_types or {"IQ4_NL"} & d_types):
        pg.append(("prefill_v2", "STRATA_PREFILL_V2=0", f"n_embd / n_ff {f['n_embd']} / {f['n_ff']} (compiled 2560 / 640), "
                   f"experts {sorted(gu_types)}/{sorted(d_types)} (needs IQ3_XXS gate/up or IQ4_NL down)"))
    # round 14: only the guards the series tree has (a stock tree has none: nothing to turn off)
    pgf = S / "src/core/patch_guard.cpp"
    if not pgf.exists():
        if pg:
            rep["notes"].append(f"series guards not checked ({S} has no src/core/patch_guard.cpp)")
        pg = []
    else:
        have = set(re.findall(r'\{"([a-z0-9_]+)", "', pgf.read_text(errors="replace")))
        pg = [g for g in pg if g[0] in have]
    # the drafter
    if mtp:
        dv = Path(mtp) / "draft_vocab.bin"
        dense = Path(mtp) / "dense.txt"
        if dv.exists():
            import struct
            raw = dv.read_bytes()
            ids = struct.unpack(f"<{len(raw) // 4}i", raw)
            rep["drafter"] = {"dir": mtp, "draft_vocab": len(ids), "max_id": max(ids)}
            if max(ids) >= len(toks):
                pg.append(("spec_exact", "STRATA_SPEC_EXACT=0", f"draft id {max(ids)} outside the vocabulary of {len(toks)}"))
                rep["upstream"].append(f"the drafter's draft vocabulary has ids up to {max(ids)}, past the model's {len(toks)}: "
                                       f"a drafter for another vocabulary")
        if dense.exists():
            fc = [l.split() for l in dense.read_text().splitlines() if l.startswith("fc_hidden.weight")]
            if fc and int(fc[0][2]) != f["n_embd"]:
                rep["upstream"].append(f"the drafter in {mtp} is {fc[0][2]} wide, the model {f['n_embd']}: another model's MTP layer")
    else:
        rep["notes"].append("no --mtp given: the drafter's fit was not checked (the qwen4exp path needs --mtp DIR; "
                            "tools/mtp_fetch.py fetches only Qwen3.8-Flash-Next's MTP block - a new model needs its own)")
    return [{"guard": g, "off": o, "why": w} for g, o, w in pg]


def show(rep: dict):
    e = rep.get("engine") or {}
    print(f"# {Path(rep['file'][0]).name} ({len(rep['file'])} shard(s){', HEAD-ONLY files' if rep['head_only'] else ''}, "
          f"GGUF v{rep['gguf_version']}, {rep['arch']}; {rep['file_gib']} GiB on disk / to download)")
    print(f"engine path ({Path(rep['tree']).name}): " + (f"{e['binary']} {' '.join(e['cmake'])} - {e['family']}: {e['note']}"
                                                          if e else "none"))
    b = rep["bytes"]
    print(f"bytes: experts {b['experts_gib']} GiB, n-gram table {b['ngram_table_gib']} GiB, the rest {b['dense_gib']} GiB, "
          f"total {b['total_gib']} GiB")
    print("roles:")
    for k, v in rep["roles"].items():
        print(f"  {k:42s} x{v['n']:<3d} {str(v['shape']):22s} {v['gib']:8.3f} GiB  {v['types']}")
    L = rep["layers"]
    print(f"layers: block_count {L['block_count']}, nextn {L['nextn_predict_layers']}, trunk {L['trunk']}, blk {L['blk_indices']}, "
          f"past the trunk {L['blocks_past_trunk'] or '-'}, nextn roles {L['nextn_roles'] or '-'}")
    t = rep["tokenizer"]
    print(f"tokenizer: {t['model']} / {t['pre']}, vocabulary {t['vocab']}, eos {t['eos']}, bos {t['bos']}, pad {t['pad']}, "
          f"<|im_start|> {t['im_start']}; {t['control_tokens']} control tokens ({', '.join(t['control_sample'])}, ...), "
          f"always-special {t['always_special']}")
    print(f"chat template: {t['chat_template_chars']} chars; markers " +
          " ".join(f"{k}{'+' if v else '-'}" for k, v in t["template_markers"].items()))
    print(f"n-gram table: {rep['ngram_table']}")
    print(f"routed experts: {rep['expert_types'] or '-'}")
    if rep.get("drafter"):
        print(f"drafter: {rep['drafter']}")
    for n in rep["notes"]:
        print(f"note: {n}")
    for u in rep["upstream"]:
        print(f"UPSTREAM: {u}")
    for p in rep["patches"]:
        print(f"PATCH OFF: {p['guard']} ({p['off']}): {p['why']}")
    print(f"VERDICT: {rep['verdict']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gguf")
    ap.add_argument("--mtp")
    ap.add_argument("--tree", default=str(STOCK_TREE), help="the release's tree (upstream's geometry, formats, families)")
    ap.add_argument("--series-tree", default=str(SERIES_TREE), help="our series' tree (its patch guards)")
    ap.add_argument("--json")
    a = ap.parse_args()
    rep = inspect(a.gguf, a.mtp, a.tree, a.series_tree)
    show(rep)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1))
    return 0 if rep["verdict"].startswith("RUNS") else 3


if __name__ == "__main__":
    sys.exit(main())
