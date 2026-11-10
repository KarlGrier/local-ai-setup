#!/usr/bin/env python3
"""splice.py OUT.gguf EXPERT_SHARD_GLOB REST_SHARD_GLOB [--dry] — round 15 (copy of work/r12/a7splice.py, made general):
one GGUF file whose routed experts (blk.N.ffn_{gate,up,down}_exps.weight) come from EXPERT files and every other tensor
from REST files (the same model: identical tensor names and shapes, checked). Metadata: the REST file's first shard
(minus the split.* keys); tensor bytes copied verbatim (memory-mapped reads). Your fallback 2 for a stand-in that does
not load: "this file's expert tensors plus every other tensor from a file that already runs".
gguf-py from strata-v0115/third_party/llama.cpp (knows Q2_0 / type 42 and IQ3_S)."""
import argparse
import glob
import re
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.path.insert(0, str(WS / "strata-v0115/third_party/llama.cpp/gguf-py"))
import gguf  # noqa: E402

EXPERTS = r"^blk\.\d+\.ffn_(gate|up|down)_exps\.weight$"
ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("experts_glob")
ap.add_argument("rest_glob")
ap.add_argument("--dry", action="store_true")
a = ap.parse_args()
EX = sorted(glob.glob(a.experts_glob))
RE = sorted(glob.glob(a.rest_glob))
r_ex = [gguf.GGUFReader(p) for p in EX]
r_re = [gguf.GGUFReader(p) for p in RE]
t_ex = {t.name: t for r in r_ex for t in r.tensors}
t_re = {t.name: t for r in r_re for t in r.tensors}
assert set(t_ex) == set(t_re), (len(t_ex), len(t_re), sorted(set(t_ex) ^ set(t_re))[:5])
order = [t.name for r in r_re for t in r.tensors]
for n in order:
    assert list(t_ex[n].shape) == list(t_re[n].shape), n
is_ex = lambda n: re.search(EXPERTS, n) is not None
take = {n: (t_ex[n] if is_ex(n) else t_re[n]) for n in order}
nex = sum(1 for n in order if is_ex(n))
by = lambda ex: sum(int(take[n].n_bytes) for n in order if is_ex(n) == ex)
print(f"{len(order)} tensors: {nex} routed experts from {Path(EX[0]).parent.name} ({by(True)/2**30:.2f} GiB), "
      f"{len(order)-nex} others from {Path(RE[0]).parent.name} ({by(False)/2**30:.2f} GiB); total "
      f"{sum(int(take[n].n_bytes) for n in order)/2**30:.2f} GiB", flush=True)
if a.dry:
    sys.exit(0)
src = r_re[0]
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
done, t0 = 0, time.time()
for i, n in enumerate(order):
    w.write_tensor_data(take[n].data, tensor_endianess=src.endianess)
    done += int(take[n].n_bytes)
    if i % 100 == 0:
        print(f"  {i}/{len(order)} tensors, {done/2**30:.1f} GiB, {done/2**30/max(1e-9, time.time()-t0):.2f} GiB/s", flush=True)
w.close()
print(f"wrote {a.out}: {done/2**30:.2f} GiB of tensor data in {time.time()-t0:.0f} s")
