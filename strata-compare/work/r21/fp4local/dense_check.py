#!/usr/bin/env python3
"""dense_check.py - r21 item 7: did FP4-Local's QAD change the non-expert weights?  Range-reads a few small BF16/F32
tensors of FP4-Local (layers 0 and 24: the router, the shared-expert gate, the GDN A_log) and compares them bit for bit with
the GPTQ pack's dense GGUF (the weights we serve FP4-Local's experts with)."""
import json, struct, sys, urllib.request
import numpy as np
sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/strata-cstar18/third_party/llama.cpp/gguf-py")
import gguf
URL = "https://huggingface.co/nvidia/Qwen3.8-Flash-Next-FP4-Local/resolve/main/tensors/model-00015-of-00021.safetensors"
def rng(a, b):
    return urllib.request.urlopen(urllib.request.Request(URL, headers={"Range": f"bytes={a}-{b - 1}"}), timeout=120).read()
n = struct.unpack("<Q", rng(0, 8))[0]; hdr = json.loads(rng(8, 8 + n)); base = 8 + n
G = {t.name: t for t in gguf.GGUFReader("/home/USER/ai-speed-testing/strata-compare/models/Maximilian228--Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata/qwen-nvfp4-gptq-dense.gguf").tensors}
for L in (0, 24):
    for hf, gg in ((f"model.language_model.layers.{L}.mlp.gate.weight", f"blk.{L}.ffn_gate_inp.weight"),
                   (f"model.language_model.layers.{L}.mlp.shared_expert_gate.weight", f"blk.{L}.ffn_gate_inp_shexp.weight"),
                   (f"model.language_model.layers.{L}.linear_attn.A_log", f"blk.{L}.ssm_a")):
        if hf not in hdr or gg not in G:
            print(f"{hf}: {'missing in FP4-Local' if hf not in hdr else 'no ' + gg + ' in the GGUF'}"); continue
        e = hdr[hf]; a, b = e["data_offsets"]
        raw = rng(base + a, base + b)
        t = G[gg]
        if e["dtype"] == "BF16":
            x = np.frombuffer(raw, np.uint16).astype(np.uint32) << 16
            x = x.view(np.float32)
        else:
            x = np.frombuffer(raw, np.float32)
        g = np.asarray(t.data)
        if t.tensor_type.name == "BF16":
            g = (g.view(np.uint16).astype(np.uint32) << 16).view(np.float32)
        g = np.asarray(g, np.float32).reshape(-1)
        if gg.endswith("ssm_a"):        # the converter stores A = -exp(A_log)
            x = -np.exp(x.astype(np.float32))
        x = x.reshape(-1)
        same = x.shape == g.shape and np.array_equal(x, g)
        d = float(np.abs(x - g).max()) if x.shape == g.shape else float("nan")
        rel = float(np.linalg.norm(x - g) / max(np.linalg.norm(g), 1e-30)) if x.shape == g.shape else float("nan")
        print(f"{hf} ({e['dtype']} {e['shape']}) vs {gg} ({t.tensor_type.name}): identical={same} max|diff|={d:.3g} rel={rel:.3g}")
