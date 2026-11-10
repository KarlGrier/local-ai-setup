#!/usr/bin/env python3
"""synth_header.py SRC-00001-of-0000N.gguf OUT_DIR — header-only synthetic GGUFs (metadata + tensor table, NO tensor data)
from a real model's header, one change each, for testing inspect_model.py / fitplan.py (they read headers only):

  hidden3072      embedding_length 3072 and every 2560-wide tensor dimension -> 3072 (10240 -> 12288 for the 4 streams)
  mtp2            nextn_predict_layers 2, block_count 50, blk.48 / blk.49 carry #619's nextn tensors (an extra MTP layer)
  mtp1            nextn_predict_layers 1, block_count 49, blk.48 nextn tensors (#619's case: must still run)
  mtp_undeclared  block_count 49 and blk.48 nextn tensors, no nextn_predict_layers key
  embd_q4_0       token_embd.weight stored as Q4_0 (a type the embedding does not take)
Written as one-shard files (the source's shards merged); value types are re-inferred (ints u32 / u64, floats f32).

10-27 (v0.2.6 refresh): `synth_header.py --qwen4 SRC OUT_DIR` writes plausible Qwen4 shapes instead, built from
parameters (the tensor roles of SRC's qwen4exp layout or Qwen3.6's qwen35moe layout, the tokenizer copied from SRC), as
HEAD-ONLY split files: each shard is its header alone plus NAME.size = the size the real shard would have (tensor offsets
aligned as in a real file), so the inspector, the planner and the download / disk check read them like
bringup/fetch_model.py --heads output:
  q4x768     qwen4exp, Flash-Next's geometry with 768 experts (expert_count is free in v0.2.6): the drop-in case
  q4flash300 a new arch name "qwen4", the qwen4exp layer pattern scaled to ~300B (3072 wide, 64 layers, 512 x 1024 experts)
  q4a3b      qwen35moe (as if Qwen4's small MoE kept Qwen3.6's arch): 2048 wide, 40 layers + 1 MTP, 256 x 512 experts, top-8
  q4dense27  "qwen4", a ~27B dense model (5120 wide, 64 layers, FFN 20480): no routed experts
The shapes are guesses for testing the tools, not predictions."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_head import TYPE_BY_NAME, read_model  # noqa: E402


def w_str(b: bytearray, s: str):
    e = s.encode()
    b += struct.pack("<Q", len(e)) + e


def w_val(b: bytearray, v):
    if isinstance(v, bool):
        b += struct.pack("<I?", 7, v)
    elif isinstance(v, int):
        b += struct.pack("<Iq", 11, v) if v < 0 else (struct.pack("<II", 4, v) if v < 2**32 else struct.pack("<IQ", 10, v))
    elif isinstance(v, float):
        b += struct.pack("<If", 6, v)
    elif isinstance(v, str):
        b += struct.pack("<I", 8)
        w_str(b, v)
    elif isinstance(v, list):
        b += struct.pack("<I", 9)
        if v and isinstance(v[0], str):
            b += struct.pack("<IQ", 8, len(v))
            for x in v:
                w_str(b, x)
        elif v and isinstance(v[0], float):
            b += struct.pack("<IQ", 6, len(v)) + struct.pack(f"<{len(v)}f", *v)
        else:
            big = any(x >= 2**31 or x < -2**31 for x in v)
            b += struct.pack("<IQ", 11 if big else 5, len(v)) + struct.pack(f"<{len(v)}{'q' if big else 'i'}", *v)
    else:
        raise TypeError(type(v))


def write(path: Path, meta: dict, tensors: list):
    b = bytearray(b"GGUF") + struct.pack("<IQQ", 3, len(tensors), len(meta))
    for k, v in meta.items():
        w_str(b, k)
        w_val(b, v)
    off = 0
    for name, t, shape in tensors:
        w_str(b, name)
        b += struct.pack("<I", len(shape)) + b"".join(struct.pack("<Q", d) for d in shape)
        b += struct.pack("<IQ", t, off)
        off += 32
    path.write_bytes(bytes(b))


def main():
    if sys.argv[1] == "--qwen4":
        return qwen4_main(sys.argv[2], Path(sys.argv[3]))
    src, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    m = read_model(src)
    meta = {k: v for k, v in m.meta.items() if not k.startswith("split.")}
    base = [(t.name, t.type, list(t.shape)) for t in m.tensors.values()]
    arch = meta["general.architecture"]
    nextn_names = ["nextn.eh_proj.weight", "nextn.hc_head_down.weight", "nextn.hc_head_up.weight", "nextn.enorm.weight",
                   "nextn.hnorm.weight"]

    def layer48(i):
        return [(f"blk.{i}.{n}", 30 if n.endswith("proj.weight") or "hc_head" in n else 0,
                 [5120, 2560] if "eh_proj" in n else ([10240, 4] if "down" in n else [4, 10240]) if "hc_head" in n else [2560])
                for n in nextn_names] + [(f"blk.{i}.ffn_gate_exps.weight", 21, [2560, 640, 512])]

    cases = {}
    md = dict(meta); md[f"{arch}.embedding_length"] = 3072
    cases["hidden3072"] = (md, [(n, t, [3072 if d == 2560 else 12288 if d == 10240 else d for d in s]) for n, t, s in base])
    md = dict(meta); md[f"{arch}.nextn_predict_layers"] = 2; md[f"{arch}.block_count"] = 50
    cases["mtp2"] = (md, base + layer48(48) + layer48(49))
    md = dict(meta); md[f"{arch}.nextn_predict_layers"] = 1; md[f"{arch}.block_count"] = 49
    cases["mtp1"] = (md, base + layer48(48))
    md = dict(meta); md[f"{arch}.block_count"] = 49
    cases["mtp_undeclared"] = (md, base + layer48(48))
    cases["embd_q4_0"] = (meta, [(n, TYPE_BY_NAME["Q4_0"] if n == "token_embd.weight" else t, s) for n, t, s in base])
    for name, (md, tens) in cases.items():
        p = out / f"synth-{name}.gguf"
        write(p, md, tens)
        print(p, p.stat().st_size, "bytes")


# ---- 10-27: Qwen4-like shapes from parameters (head-only split files + NAME.size)
T = TYPE_BY_NAME
F32, F16, BF16 = T["F32"], T["F16"], T["BF16"]


def nbytes(t: int, shape) -> int:
    from gguf_head import GGML_TYPES
    _, bs, bb = GGML_TYPES[t]
    n = 1
    for d in shape:
        n *= d
    return n // bs * bb


def qwen4exp_tensors(E, L, X, F, H, KV, D, G, VH, V, gu, dn, dense=T["Q6_K"], ple_rows=320001536):
    """The qwen4exp roles (Qwen3.8-Flash-Next's IQ3_S file) at another size: GDN x3 + QSA-with-indexer, 4 hyper-connection
    streams (low rank 320), routed + shared experts, the PLE stage at blk.1; global tensors first."""
    inner, conv, hc = 128 * VH, 2 * 128 * G + 128 * VH, 4 * E
    g = [("token_embd.weight", T["IQ4_XS"], [E, V]), ("output.weight", dense, [E, V]),
         ("output_hc_down.weight", BF16, [hc, 320]), ("output_hc_norm.weight", F32, [hc]),
         ("output_hc_up.weight", BF16, [320, hc])]
    lay = []
    for i in range(L):
        b = f"blk.{i}."
        t = []
        if i % 4 == 3:
            t += [(b + "attn_q.weight", dense, [E, 2 * H * D]), (b + "attn_k.weight", dense, [E, KV * D]),
                  (b + "attn_v.weight", dense, [E, KV * D]), (b + "attn_output.weight", dense, [H * D, E]),
                  (b + "attn_q_norm.weight", F32, [D]), (b + "attn_k_norm.weight", F32, [D]),
                  (b + "indexer.k_norm.weight", F32, [128]), (b + "indexer.k_proj.weight", BF16, [E, 128]),
                  (b + "indexer.q_norm.weight", F32, [128]), (b + "indexer.q_proj.weight", BF16, [E, 512])]
        else:
            t += [(b + "attn_gate.weight", dense, [E, inner]), (b + "attn_qkv.weight", dense, [E, conv]),
                  (b + "ssm_a", F32, [VH]), (b + "ssm_alpha.weight", BF16, [E, VH]), (b + "ssm_beta.weight", BF16, [E, VH]),
                  (b + "ssm_conv1d.weight", F32, [4, conv]), (b + "ssm_dt.bias", F32, [VH]), (b + "ssm_norm.weight", F32, [128]),
                  (b + "ssm_out.weight", dense, [inner, E])]
        t += [(b + "ffn_gate_exps.weight", gu, [E, F, X]), (b + "ffn_up_exps.weight", gu, [E, F, X]),
              (b + "ffn_down_exps.weight", dn, [F, E, X]), (b + "ffn_gate_inp.weight", BF16, [E, X]),
              (b + "ffn_gate_inp_shexp.weight", BF16, [E]), (b + "ffn_gate_shexp.weight", dense, [E, F]),
              (b + "ffn_up_shexp.weight", dense, [E, F]), (b + "ffn_down_shexp.weight", T["IQ4_NL"], [F, E])]
        for h in ("attn", "ffn"):
            t += [(b + f"hc_{h}_down.weight", BF16, [hc, 320]), (b + f"hc_{h}_inject.weight", BF16, [hc, 4]),
                  (b + f"hc_{h}_norm.weight", F32, [hc]), (b + f"hc_{h}_up.weight", BF16, [320, hc])]
        if i == 1:
            t += [(b + "ple_conv1d.weight", F16, [4, hc]), (b + "ple_key.weight", BF16, [E, hc]),
                  (b + "ple_norm_conv.weight", F32, [hc]), (b + "ple_norm_key.weight", F32, [hc]),
                  (b + "ple_norm_query.weight", F32, [hc]), (b + "ple_value.weight", BF16, [E, E])]
        lay.append(t)
    return g, lay, [("per_layer_token_embd.weight", T["IQ4_NL"], [160, ple_rows])]


def qwen35moe_tensors(E, L, X, F, H, KV, D, G, VH, V, gu, dn, dense=T["Q8_0"], nextn=1):
    """Approximate qwen35moe roles (Qwen3.6-35B-A3B: GDN x3 + gated attention, plain pre-norm residual, routed + shared
    experts, an in-file nextn MTP block after the trunk)."""
    inner, conv = 128 * VH, 2 * 128 * G + 128 * VH
    g = [("token_embd.weight", dense, [E, V]), ("output.weight", dense, [E, V]), ("output_norm.weight", F32, [E])]
    lay = []
    for i in range(L + nextn):
        b = f"blk.{i}."
        t = [(b + "attn_norm.weight", F32, [E]), (b + "post_attention_norm.weight", F32, [E])]
        if i % 4 == 3 or i >= L:
            t += [(b + "attn_q.weight", dense, [E, 2 * H * D]), (b + "attn_k.weight", dense, [E, KV * D]),
                  (b + "attn_v.weight", dense, [E, KV * D]), (b + "attn_output.weight", dense, [H * D, E]),
                  (b + "attn_q_norm.weight", F32, [D]), (b + "attn_k_norm.weight", F32, [D])]
        else:
            t += [(b + "attn_gate.weight", dense, [E, inner]), (b + "attn_qkv.weight", dense, [E, conv]),
                  (b + "ssm_a", F32, [VH]), (b + "ssm_alpha.weight", dense, [E, VH]), (b + "ssm_beta.weight", dense, [E, VH]),
                  (b + "ssm_conv1d.weight", F32, [4, conv]), (b + "ssm_dt.bias", F32, [VH]), (b + "ssm_norm.weight", F32, [128]),
                  (b + "ssm_out.weight", dense, [inner, E])]
        t += [(b + "ffn_gate_exps.weight", gu, [E, F, X]), (b + "ffn_up_exps.weight", gu, [E, F, X]),
              (b + "ffn_down_exps.weight", dn, [F, E, X]), (b + "ffn_gate_inp.weight", F32, [E, X]),
              (b + "ffn_gate_inp_shexp.weight", F32, [E]), (b + "ffn_gate_shexp.weight", dense, [E, F]),
              (b + "ffn_up_shexp.weight", dense, [E, F]), (b + "ffn_down_shexp.weight", dense, [F, E])]
        if i >= L:
            t += [(b + "nextn.eh_proj.weight", dense, [2 * E, E]), (b + "nextn.enorm.weight", F32, [E]),
                  (b + "nextn.hnorm.weight", F32, [E]), (b + "nextn.shared_head_norm.weight", F32, [E])]
        lay.append(t)
    return g, lay, []


def dense_tensors(E, L, F, H, KV, D, V, w=T["Q4_K"], w2=T["Q6_K"]):
    """A plain dense transformer (attention + SwiGLU FFN), Q4_K_M-like: Q4_K with Q6_K for down / V / output."""
    g = [("token_embd.weight", w, [E, V]), ("output.weight", w2, [E, V]), ("output_norm.weight", F32, [E])]
    lay = []
    for i in range(L):
        b = f"blk.{i}."
        lay.append([(b + "attn_norm.weight", F32, [E]), (b + "ffn_norm.weight", F32, [E]),
                    (b + "attn_q.weight", w, [E, H * D]), (b + "attn_k.weight", w, [E, KV * D]),
                    (b + "attn_v.weight", w2, [E, KV * D]), (b + "attn_output.weight", w, [H * D, E]),
                    (b + "attn_q_norm.weight", F32, [D]), (b + "attn_k_norm.weight", F32, [D]),
                    (b + "ffn_gate.weight", w, [E, F]), (b + "ffn_up.weight", w, [E, F]), (b + "ffn_down.weight", w2, [F, E])])
    return g, lay, []


def write_split(out: Path, base: str, meta: dict, glob_t, layers, tail, shards: int, align=32):
    """Head-only shards: shard 1 = the metadata + the global tensors + the first layers, the last = the n-gram table;
    NAME.size = header (aligned) + every tensor at its aligned offset - what the real shard would weigh."""
    per = -(-len(layers) // shards)
    parts = [(glob_t if k == 0 else []) + [t for lay in layers[k * per:(k + 1) * per] for t in lay] for k in range(shards)]
    parts[-1] += tail
    total_t = sum(len(p) for p in parts)
    paths = []
    for k, tens in enumerate(parts):
        md = dict(meta) if k == 0 else {"general.architecture": meta["general.architecture"]}
        md.update({"split.no": k, "split.count": shards, "split.tensors.count": total_t})
        b = bytearray(b"GGUF") + struct.pack("<IQQ", 3, len(tens), len(md))
        for key, v in md.items():
            w_str(b, key)
            w_val(b, v)
        off = 0
        for name, t, shape in tens:
            w_str(b, name)
            b += struct.pack("<I", len(shape)) + b"".join(struct.pack("<Q", d) for d in shape)
            b += struct.pack("<IQ", t, off)
            off += (nbytes(t, shape) + align - 1) // align * align
        p = out / f"{base}-{k + 1:05d}-of-{shards:05d}.gguf"
        p.write_bytes(bytes(b))
        (out / (p.name + ".size")).write_text(f"{(len(b) + align - 1) // align * align + off}\n")
        paths.append(p)
    return paths


def qwen4_main(src: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    m = read_model(src)
    meta0 = {k: v for k, v in m.meta.items() if not k.startswith("split.")}
    arch0 = meta0["general.architecture"]
    tok = {k: v for k, v in meta0.items() if k.startswith("tokenizer.")}
    V = len(tok["tokenizer.ggml.tokens"])
    gen = {"general.type": "model", "general.description": "SYNTHETIC header for bringup tests (not a real model)"}

    def arch_meta(arch, over):
        md = {"general.architecture": arch, **gen}
        for k, v in meta0.items():
            if k.startswith(arch0 + "."):
                md[arch + k[len(arch0):]] = v
        md.update({f"{arch}.{k}": v for k, v in over.items()})
        md.update(tok)
        return md

    made = []
    # 1. drop-in: qwen4exp, Flash-Next's geometry, 768 experts (IQ3_XXS gate/up, IQ4_NL down)
    E, L, X, F = 2560, 48, 768, 640
    md = arch_meta("qwen4exp", {"expert_count": X})
    md["general.name"] = "SYNTH Qwen4-Flash (qwen4exp, 768 experts)"
    g, lay, tail = qwen4exp_tensors(E, L, X, F, 24, 2, 256, 16, 48, V, T["IQ3_XXS"], T["IQ4_NL"])
    made.append(write_split(out, "SYNTH-q4x768", md, g, lay, tail, 2))
    # 2. a ~300B Flash under a new arch name, the qwen4exp pattern scaled up (3 shards)
    E, L, X, F, H, KV, VH = 3072, 64, 512, 1024, 32, 4, 64
    md = arch_meta("qwen4", {"block_count": L, "embedding_length": E, "expert_count": X, "expert_used_count": 10,
                             "expert_feed_forward_length": F, "expert_shared_feed_forward_length": F,
                             "attention.head_count": H, "attention.head_count_kv": KV, "ssm.time_step_rank": VH,
                             "ssm.inner_size": 128 * VH, "attention.compress_ratios": [0, 0, 0, 4] * (L // 4)})
    md["general.name"] = "SYNTH Qwen4-Flash-300B (arch qwen4)"
    g, lay, tail = qwen4exp_tensors(E, L, X, F, H, KV, 256, 16, VH, V, T["IQ3_XXS"], T["IQ4_NL"])
    made.append(write_split(out, "SYNTH-q4flash300", md, g, lay, tail, 3))
    # 3. a 35B-A3B under qwen35moe (Qwen3.6's arch: v0.2.6's own path), Unsloth-like Q4_K / Q5_K experts, one file
    E, L, X, F, H, KV, VH = 2048, 40, 256, 512, 16, 2, 32
    keys = {"block_count": L + 1, "embedding_length": E, "attention.head_count": H, "attention.head_count_kv": KV,
            "attention.key_length": 256, "attention.value_length": 256, "expert_count": X, "expert_used_count": 8,
            "expert_feed_forward_length": F, "expert_shared_feed_forward_length": F, "ssm.conv_kernel": 4,
            "ssm.state_size": 128, "ssm.group_count": 16, "ssm.time_step_rank": VH, "ssm.inner_size": 128 * VH,
            "full_attention_interval": 4, "nextn_predict_layers": 1, "context_length": 262144,
            "attention.layer_norm_rms_epsilon": 1e-6, "rope.freq_base": 10000000.0}
    md = {"general.architecture": "qwen35moe", **gen, "general.name": "SYNTH Qwen4-35B-A3B (arch qwen35moe)",
          **{f"qwen35moe.{k}": v for k, v in keys.items()}, **tok}
    g, lay, tail = qwen35moe_tensors(E, L, X, F, H, KV, 256, 16, VH, V, T["Q4_K"], T["Q5_K"])
    made.append(write_split(out, "SYNTH-q4a3b", md, g, lay, tail, 1))
    # 4. a ~27B dense model, "qwen4", Q4_K_M-like (2 shards)
    E, L, F, H, KV, D = 5120, 64, 20480, 40, 8, 128
    keys = {"block_count": L, "embedding_length": E, "feed_forward_length": F, "attention.head_count": H,
            "attention.head_count_kv": KV, "attention.key_length": D, "attention.value_length": D,
            "context_length": 262144, "attention.layer_norm_rms_epsilon": 1e-6}
    md = {"general.architecture": "qwen4", **gen, "general.name": "SYNTH Qwen4-27B dense (arch qwen4)",
          **{f"qwen4.{k}": v for k, v in keys.items()}, **tok}
    g, lay, tail = dense_tensors(E, L, F, H, KV, D, V)
    made.append(write_split(out, "SYNTH-q4dense27", md, g, lay, tail, 2))
    for ps in made:
        for p in ps:
            print(p, p.stat().st_size, "header bytes;", int((out / (p.name + ".size")).read_text()), "bytes as a real shard")
    return 0


if __name__ == "__main__":
    main()
