#!/usr/bin/env python3
"""a7splice.py OUT.gguf [--from-q4 REGEX] [--dry] — round 12 A7: one GGUF file whose tensors come from two files of the
same model (identical names and shapes; checked): the served ISTA GSQ-RCO IQ3_S (2 shards) and Unsloth's UD-Q4_K_XL
(4 shards, read-only in ~/.cache). A tensor whose name matches REGEX comes from the Q4 file, every other from IQ3_S.
Default REGEX = every tensor that is NOT a routed expert (splice 3: "IQ3_S experts + every other tensor from the Q4 file").
Metadata: the IQ3_S file's first shard (minus the split.* keys); tensor bytes copied verbatim (memory-mapped reads).
gguf-py from strata-v0115/third_party/llama.cpp (knows Q2_0 / type 42 and IQ3_S)."""
import argparse
import glob
import re
import sys
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "strata-v0115/third_party/llama.cpp/gguf-py"))
import gguf  # noqa: E402

IQ3 = sorted(glob.glob(str(WS / "models/ISTA-GSQ-RCO/IQ3_S/*.gguf")))
Q4 = sorted(glob.glob("/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee*/UD-Q4_K_XL/*.gguf"))
EXPERTS = r"^blk\.\d+\.ffn_(gate|up|down)_exps\.weight$"

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--from-q4", default=None, help="regex of tensors taken from the Q4 file (default: all but the routed experts)")
ap.add_argument("--dry", action="store_true")
a = ap.parse_args()
pick_q4 = (lambda n: re.search(a.from_q4, n) is not None) if a.from_q4 else (lambda n: re.search(EXPERTS, n) is None)

r_iq3 = [gguf.GGUFReader(p) for p in IQ3]
r_q4 = [gguf.GGUFReader(p) for p in Q4]
t_iq3 = {t.name: t for r in r_iq3 for t in r.tensors}
t_q4 = {t.name: t for r in r_q4 for t in r.tensors}
assert set(t_iq3) == set(t_q4), (len(t_iq3), len(t_q4))
order = [t.name for r in r_iq3 for t in r.tensors]
for n in order:
    assert list(t_iq3[n].shape) == list(t_q4[n].shape), n
take = {n: (t_q4[n] if pick_q4(n) else t_iq3[n]) for n in order}
nq4 = sum(1 for n in order if pick_q4(n))
by = lambda src: sum(int(take[n].n_bytes) for n in order if (take[n] is t_q4[n]) == src)
print(f"{len(order)} tensors: {nq4} from Q4 ({by(True)/2**30:.2f} GiB), {len(order)-nq4} from IQ3_S ({by(False)/2**30:.2f} GiB); "
      f"total {sum(int(take[n].n_bytes) for n in order)/2**30:.2f} GiB")
# per group: bytes before (IQ3_S) and after
grp = lambda n: re.sub(r"blk\.\d+\.", "blk.N.", n)
gb = {}
for n in order:
    g = grp(n)
    b0, b1 = gb.get(g, (0, 0))
    gb[g] = (b0 + int(t_iq3[n].n_bytes), b1 + int(take[n].n_bytes))
for g, (b0, b1) in sorted(gb.items(), key=lambda kv: -(kv[1][1] - kv[1][0])):
    if b1 != b0:
        print(f"  {g:40s} {b0/2**20:10.1f} MiB -> {b1/2**20:10.1f} MiB ({(b1-b0)/2**20:+.1f})")
if a.dry:
    sys.exit(0)
src = r_iq3[0]
arch = src.fields[gguf.Keys.General.ARCHITECTURE].contents()
w = gguf.GGUFWriter(a.out, arch=arch, endianess=src.endianess)
for field in src.fields.values():
    if field.name == gguf.Keys.General.ARCHITECTURE or field.name.startswith("GGUF.") or field.name.startswith("split."):
        continue
    vt = field.types[0]
    st = field.types[-1] if vt == gguf.GGUFValueType.ARRAY else None
    w.add_key_value(field.name, field.contents(), vt, sub_type=st)
for n in order:
    t = take[n]
    w.add_tensor_info(t.name, t.data.shape, t.data.dtype, t.data.nbytes, t.tensor_type)
w.write_header_to_file()
w.write_kv_data_to_file()
w.write_ti_data_to_file()
done = 0
for n in order:
    w.write_tensor_data(take[n].data, tensor_endianess=src.endianess)
    done += int(take[n].n_bytes)
w.close()
print(f"wrote {a.out}: {done/2**30:.2f} GiB of tensor data")
