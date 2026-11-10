#!/usr/bin/env python3
"""convert_lucebox_dspark.py SRC REF OUT [--plan] - 11-03 (Karl: the small DSpark test, arm C): rewrite Lucebox's
DSpark drafter (DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf, architecture "deepseek41-dflash-draft") into the layout
our engine's pack tool reads (tools/dsv41/pack_gguf.py --dspark-gguf: architecture "dflash", unsloth's names), with
unsloth's 1017 Q8_0 drafter (REF) as the template for the metadata. Nothing is requantized:
  - every blk.N.* tensor: the same name, the same bytes (Q2_K experts, Q4_K dense, F32 / F16 small tensors);
  - dflash.fc.weight -> fc.weight (same bytes); dflash.hidden_norm.weight -> enc.output_norm.weight; output_norm.weight
    as is;
  - dflash.dspark.confidence.weight (F16 [5376]) -> conf_proj.weight (F32 [5376, 1]: an exact widening);
    dflash.dspark.confidence.bias: REF has no such tensor and the pack maps none - printed, then dropped;
  - dflash.dspark.markov.w1 (F16) -> markov_w1.weight as BF16 (the engine wants a BF16 embed: F16 -> F32 -> BF16 with
    round-to-nearest-even - the only rounding step, in the drafter only); .w2 (F16) -> markov_w2.weight as F16 (allowed);
  - metadata: REF's (dflash.* geometry, tokenizer), general.name / description marked as this conversion.
The drafter's numbers can change only in the markov embed (and its drafts may differ); the target verifies every drafted
token, so the output distribution does not depend on the drafter. --plan prints the mapping and checks without writing.
Uses gguf-py from ext/llama.cpp-3cf03257 (read-only). Output must not exist.
"""
import os
import sys

sys.path.insert(0, "/home/USER/ai-speed-testing/strata-compare/ext/llama.cpp-3cf03257/gguf-py")
import numpy as np  # noqa: E402
import gguf  # noqa: E402

SRC, REF, OUT = sys.argv[1:4]
PLAN = "--plan" in sys.argv
HEAD = {"dflash.fc.weight": "fc.weight", "dflash.hidden_norm.weight": "enc.output_norm.weight",
        "output_norm.weight": "output_norm.weight"}


def f16_to_bf16(a16):
    f = a16.astype(np.float32)
    u = f.view(np.uint32)
    r = ((u >> 16) & 1) + 0x7FFF          # round to nearest even
    return ((u + r) >> 16).astype(np.uint16)


def main():
    src = gguf.GGUFReader(SRC, "r")
    ref = gguf.GGUFReader(REF, "r")
    ref_names = {t.name: t for t in ref.tensors}
    plan = []
    for t in src.tensors:
        n = t.name
        if n.startswith("blk."):
            plan.append((n, n, "copy"))
        elif n in HEAD:
            plan.append((n, HEAD[n], "copy"))
        elif n == "dflash.dspark.confidence.weight":
            plan.append((n, "conf_proj.weight", "f16->f32 [n,1]"))
        elif n == "dflash.dspark.markov.w1":
            plan.append((n, "markov_w1.weight", "f16->bf16"))
        elif n == "dflash.dspark.markov.w2":
            plan.append((n, "markov_w2.weight", "copy f16"))
        elif n == "dflash.dspark.confidence.bias":
            plan.append((n, None, f"drop (value {float(np.asarray(t.data).reshape(-1)[0]):.6g})"))
        else:
            raise SystemExit(f"unmapped tensor {n}")
    mapped = {o for _, o, _ in plan if o}
    missing = sorted(set(ref_names) - mapped); extra = sorted(mapped - set(ref_names))
    for s, o, how in plan:
        if not s.startswith("blk.") or s.startswith("blk.0."):
            rt = ref_names.get(o)
            print(f"{s:42s} -> {str(o):26s} {how:22s} ref: {rt.tensor_type.name if rt else '-'} {list(rt.shape) if rt else ''}")
    print(f"{len(plan)} source tensors; REF names not produced: {missing}; produced names not in REF: {extra}")
    if missing or extra:
        raise SystemExit("the mapping does not cover REF's names - not writing")
    if PLAN:
        return
    if os.path.exists(OUT):
        raise SystemExit(f"{OUT} exists")
    w = gguf.GGUFWriter(OUT + ".part", "dflash")
    for f in ref.fields.values():
        k = f.name
        if k.startswith("GGUF.") or k == "general.architecture":
            continue
        v = f.contents()
        if k == "general.name":
            v = "DeepSeek V4.1 Flash DSpark (Lucebox Q2K-Q4K, converted 11-03)"
        vt = f.types[0]
        sub = f.types[-1] if vt == gguf.GGUFValueType.ARRAY else None
        w.add_key_value(k, v, vt, sub_type=sub)
    w.add_string("general.description", "Lucebox/DeepSeek-V4.1-Flash-DSpark-GGUF @11403d34, Q2K-Q4K, renamed to unsloth's layout "
                 "(work/ds41/gate/convert_lucebox_dspark.py); markov embed F16 -> BF16")
    for s, o, how in plan:
        if o is None:
            continue
        t = next(x for x in src.tensors if x.name == s)
        raw = np.asarray(t.data)
        if how == "copy" or how == "copy f16":
            # 11-03 fix: no raw_shape - gguf-py derives the element shape from the reader's byte rows for every type
            # (the gate's first run failed: "bytes per row (5120) is not a multiple of Q4_K type size (144)")
            w.add_tensor(o, raw, raw_dtype=t.tensor_type)
        elif how.startswith("f16->f32"):
            a = raw.astype(np.float16).astype(np.float32).reshape(1, -1)
            w.add_tensor(o, a, raw_dtype=gguf.GGMLQuantizationType.F32)
        elif how == "f16->bf16":
            b = f16_to_bf16(raw.astype(np.float16))
            w.add_tensor(o, b, raw_dtype=gguf.GGMLQuantizationType.BF16)
    w.write_header_to_file(); w.write_kv_data_to_file(); w.write_tensors_to_file(progress=False); w.close()
    os.replace(OUT + ".part", OUT)
    print("written", OUT)


if __name__ == "__main__":
    main()
