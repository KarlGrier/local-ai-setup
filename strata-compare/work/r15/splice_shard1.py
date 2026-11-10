#!/usr/bin/env python3
"""splice_shard1.py OUTDIR BASE --rest OUR_SHARD1 --experts SHARD... [--dry] [--min-free-gb 100] - r23 (11-04, Karl's
Unsloth Dynamic v3.1 test, arm S; results/qwen4-kit/unsloth-v31/REPORT.md section 7 (a)): the "~15-line variant" of
work/r15/splice.py (which stays as it is). splice.py writes ONE file with every tensor, the 28.8 GB n-gram table
included; this writes ONLY our shard 1 again - its 1,223 tensors in their order, the 144 routed-expert tensors
(blk.N.ffn_{gate,up,down}_exps.weight) taken from the EXPERT shards, every other tensor (dense, head, embedding) from
OUR shard 1, verbatim - with our shard 1's metadata INCLUDING its split.* keys (split.no 0, split.count 2,
split.tensors.count 1224), and puts our shard 2 (the n-gram table alone) beside it as a HARD LINK under the new name:
  OUTDIR/BASE-00001-of-00002.gguf   written (~54.8 GB; as BASE-...gguf.part, renamed only when complete)
  OUTDIR/BASE-00002-of-00002.gguf   hard link to OUR shard 2 (same filesystem; nothing copied)
  OUTDIR/BASE.splice.json           what went in (sources, sizes, the plan, the time)
The engine and tools/iq_pack.py find shard 2 by the name pattern, so the pair loads as a 2-shard file whose dense path
is ours byte for byte (no --compat-bf16 needed: our hyper-connections and PLE projections are BF16).

Checks before writing (headers only, strata-r22p0210/tools/gguf_reader.py - also what --dry does, so it runs on the
header-only files in work/qwen4-kit/unsloth-v31/headers/): our shard 1 + 2 hold 1,224 tensors with 144 experts, all in
shard 1; the expert shards hold every one of the 144 with the same shape (their whole name set must equal ours when it
covers all 1,224 names - the same model); free space minus the output >= --min-free-gb.
Writing: gguf-py from strata-v0115/third_party/llama.cpp (as splice.py; it knows Q2_0 / type 42), tensor bytes copied
verbatim from memory maps; every 1 GiB written: flush + fdatasync + POSIX_FADV_DONTNEED on the output, so the dirty
pages never pile up (Round 15: 123 GiB of dirty pages tripped the swap guard). The caller still syncs and evicts.
Verify (after writing, always): the output's header (gguf_reader) - 1,223 tensors in our order, the experts' types =
the expert shards', every other type ours, shapes, split.* keys, the file size; head tensors (output.weight,
output_hc_*) byte-identical to ours; the first and last MiB of the first / last tensor and of 3 expert tensors equal
their sources; shard 2 is the same inode as ours. Exit 0 = written + verified (or --dry planned), 1 = refused / failed.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
sys.dont_write_bytecode = True
sys.path.insert(0, str(WS / "strata-r22p0210/tools"))
import gguf_reader as GR  # noqa: E402  (header reader, standard library + struct)

EXPERTS = r"^blk\.\d+\.ffn_(gate|up|down)_exps\.weight$"
HEAD = ("output.weight", "output_hc_down.weight", "output_hc_norm.weight", "output_hc_up.weight")
MIB, GIB = 1 << 20, 1 << 30
is_ex = lambda n: re.search(EXPERTS, n) is not None
pad = lambda n, a: (n + a - 1) // a * a


def shards_of(first: Path):
    m = re.search(r"-(\d{5})-of-(\d{5})\.gguf$", first.name)
    if not m:
        return [first]
    n = int(m[2])
    return [first.with_name(first.name[:m.start()] + "-%05d-of-%05d.gguf" % (i, n)) for i in range(1, n + 1)]


def plan(a):
    rest = shards_of(Path(a.rest))
    if len(rest) != 2 or Path(a.rest) != rest[0]:
        raise SystemExit(f"--rest must be shard 1 of a 2-shard file (got {[p.name for p in rest]})")
    for p in rest + [Path(x) for x in a.experts]:
        if not p.exists():
            raise SystemExit(f"missing {p}")
    r1, r2 = GR.GGUFFile(rest[0]), GR.GGUFFile(rest[1])
    ex = [GR.GGUFFile(Path(p)) for p in a.experts]
    t_re = {t.name: t for g in (r1, r2) for t in g.tensors}
    t_ex = {}
    for g in ex:
        for t in g.tensors:
            if t.name in t_ex:
                raise SystemExit(f"{t.name} twice in the expert shards")
            t_ex[t.name] = t
    sk = {k: v for k, v in r1.metadata.items() if k.startswith("split.")}
    if sk.get("split.no") != 0 or sk.get("split.count") != 2 or sk.get("split.tensors.count") != len(t_re):
        raise SystemExit(f"our shard 1's split keys {sk} do not describe this 2-shard file of {len(t_re)} tensors")
    order = [t.name for t in r1.tensors]
    exps = [n for n in order if is_ex(n)]
    if len(exps) != 144 or any(is_ex(t.name) for t in r2.tensors):
        raise SystemExit(f"{len(exps)} routed-expert tensors in our shard 1 (want 144, none in shard 2)")
    miss = [n for n in exps if n not in t_ex]
    if miss:
        raise SystemExit(f"the expert shards lack {len(miss)} expert tensors, e.g. {miss[:3]}")
    shape = [n for n in set(t_ex) & set(t_re) if t_ex[n].shape != t_re[n].shape]
    if shape:
        raise SystemExit(f"shapes differ (not the same model): {sorted(shape)[:4]}")
    foreign = sorted(set(t_ex) - set(t_re))
    if foreign:
        raise SystemExit(f"the expert shards hold tensors our file does not: {foreign[:4]}")
    full = set(t_ex) == set(t_re)
    take = {n: (t_ex[n] if is_ex(n) else t_re[n]) for n in order}
    nbytes = {n: take[n].expected_bytes() for n in order}
    if any(v is None for v in nbytes.values()):
        raise SystemExit("a tensor type the header reader cannot size: " + ", ".join(n for n, v in nbytes.items() if v is None)[:200])
    align = int(r1.metadata.get("general.alignment", 32))
    data = sum(pad(v, align) for v in nbytes.values())
    types = {}
    for n in exps:
        types[take[n].type_name] = types.get(take[n].type_name, 0) + 1
    p = {"rest": [str(x) for x in rest], "experts": [str(x) for x in a.experts], "order": order, "take": take,
         "nbytes": nbytes, "align": align, "data_bytes": data, "header_bytes_ours": r1.data_start, "split": sk,
         "r1": r1, "t_ex": t_ex, "t_re": t_re, "full": full, "exp_bytes": sum(nbytes[n] for n in exps),
         "exp_bytes_ours": sum(t_re[n].expected_bytes() for n in exps), "types": types}
    print(f"{len(order)} tensors in our shard 1: {len(exps)} routed experts from {', '.join(Path(x).name for x in a.experts)} "
          f"({p['exp_bytes'] / GIB:.2f} GiB; ours {p['exp_bytes_ours'] / GIB:.2f} GiB; types {types}), "
          f"{len(order) - len(exps)} others ours; tensor data {data / 1e9:.2f} GB + ~{r1.data_start / 1e6:.1f} MB header; "
          f"name sets {'equal (all ' + str(len(t_re)) + ')' if full else 'cover the experts'}; split keys kept {sk}", flush=True)
    return p


def write(a, p):
    sys.path.insert(0, str(WS / "strata-v0115/third_party/llama.cpp/gguf-py"))
    import gguf  # noqa: E402
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    o1, o2 = out / f"{a.base}-00001-of-00002.gguf", out / f"{a.base}-00002-of-00002.gguf"
    part = o1.with_name(o1.name + ".part")
    if o1.exists() or part.exists():
        raise SystemExit(f"{o1} (or .part) exists - remove it first (the driver does)")
    need = p["data_bytes"] + p["header_bytes_ours"] + 64 * MIB
    st = os.statvfs(out)
    free = st.f_bavail * st.f_frsize
    if free - need < a.min_free_gb * 1e9:
        raise SystemExit(f"{free / 1e9:.1f} GB free, the output needs {need / 1e9:.1f}: under {a.min_free_gb} GB would be left")
    if os.stat(out).st_dev != os.stat(p["rest"][1]).st_dev:
        raise SystemExit(f"{out} is not on our shard 2's filesystem: no hard link possible")
    rr = gguf.GGUFReader(p["rest"][0])
    er = [gguf.GGUFReader(x) for x in p["experts"]]
    t_re = {t.name: t for t in rr.tensors}
    t_ex = {t.name: t for r in er for t in r.tensors}
    take = {n: (t_ex[n] if is_ex(n) else t_re[n]) for n in p["order"]}
    for n in p["order"]:                                   # the two readers agree on every byte count
        if int(take[n].n_bytes) != p["nbytes"][n]:
            raise SystemExit(f"{n}: gguf-py {int(take[n].n_bytes)} B, the header reader {p['nbytes'][n]} B")
    arch = rr.fields[gguf.Keys.General.ARCHITECTURE].contents()
    w = gguf.GGUFWriter(str(part), arch=arch, endianess=rr.endianess)
    w.data_alignment = p["align"]
    for field in rr.fields.values():                       # splice.py's loop, the split.* keys KEPT
        if field.name == gguf.Keys.General.ARCHITECTURE or field.name.startswith("GGUF."):
            continue
        vt = field.types[0]
        stt = field.types[-1] if vt == gguf.GGUFValueType.ARRAY else None
        w.add_key_value(field.name, field.contents(), vt, sub_type=stt)
    for n in p["order"]:
        t = take[n]
        w.add_tensor_info(t.name, t.data.shape, t.data.dtype, t.data.nbytes, t.tensor_type)
    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_ti_data_to_file()
    fo = w.fout[0]
    done, last, t0 = 0, 0, time.time()
    for i, n in enumerate(p["order"]):
        w.write_tensor_data(take[n].data, tensor_endianess=rr.endianess)
        done += int(take[n].n_bytes)
        if done - last >= GIB:                             # bounded dirty pages: flush, sync, drop what is written
            fo.flush()
            os.fdatasync(fo.fileno())
            os.posix_fadvise(fo.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            last = done
        if i % 100 == 0:
            print(f"  {i}/{len(p['order'])} tensors, {done / GIB:.1f} GiB, {done / GIB / max(1e-9, time.time() - t0):.2f} GiB/s",
                  flush=True)
    fo.flush()
    os.fdatasync(fo.fileno())
    os.posix_fadvise(fo.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    w.close()
    os.replace(part, o1)
    if o2.exists() and not os.path.samefile(o2, p["rest"][1]):
        raise SystemExit(f"{o2} exists and is not our shard 2")
    if not o2.exists():
        os.link(p["rest"][1], o2)
    secs = time.time() - t0
    print(f"wrote {o1}: {done / GIB:.2f} GiB of tensor data in {secs:.0f} s; {o2.name} -> hard link to {Path(p['rest'][1]).name}",
          flush=True)
    (out / f"{a.base}.splice.json").write_text(json.dumps({
        "tool": "work/r15/splice_shard1.py", "written": time.strftime("%F %T"), "seconds": round(secs),
        "rest": p["rest"], "experts": p["experts"],
        "sizes": {x: os.path.getsize(x) for x in p["rest"] + p["experts"]}, "out": [str(o1), str(o2)],
        "out_bytes": os.path.getsize(o1), "expert_types": p["types"], "split_keys": p["split"]}, indent=1) + "\n")
    return o1, o2


def same(f1, o1, f2, o2, n):
    with open(f1, "rb") as a, open(f2, "rb") as b:
        a.seek(o1)
        b.seek(o2)
        while n > 0:
            k = min(n, 64 * MIB)
            if a.read(k) != b.read(k):
                return False
            n -= k
    return True


def verify(p, o1, o2):
    bad = []
    g = GR.GGUFFile(o1)
    names = [t.name for t in g.tensors]
    if names != p["order"]:
        bad.append(f"tensor order / names differ ({len(names)} vs {len(p['order'])})")
    to = {t.name: t for t in g.tensors}
    for n in p["order"]:
        t = to.get(n)
        src = p["take"][n]
        if t is None:
            continue
        if t.type_name != src.type_name or t.shape != src.shape:
            bad.append(f"{n}: {t.type_name} {t.shape} (want {src.type_name} {src.shape})")
    sk = {k: v for k, v in g.metadata.items() if k.startswith("split.")}
    if sk != p["split"]:
        bad.append(f"split keys {sk} (want {p['split']})")
    last = g.tensors[-1]
    end = g.data_start + last.offset + last.expected_bytes()
    size = os.path.getsize(o1)
    if not (end <= size <= pad(end, p["align"])):
        bad.append(f"file size {size:,} vs the last tensor's end {end:,}")
    if g.data_start + sum(pad(v, p["align"]) for v in p["nbytes"].values()) != pad(end, p["align"]):
        bad.append("the data section is not the planned size")
    where = {}                                              # name -> (source file, absolute offset)
    for path in p["experts"]:
        gx = GR.GGUFFile(Path(path))
        for t in gx.tensors:
            if is_ex(t.name):
                where[t.name] = (path, gx.data_start + t.offset)
    r1 = p["r1"]
    for t in r1.tensors:
        if not is_ex(t.name):
            where[t.name] = (p["rest"][0], r1.data_start + t.offset)
    src_of = lambda n: where[n]
    exps = [n for n in p["order"] if is_ex(n)]
    for n in HEAD:                                          # the head S is scored with: ours, whole
        if n in to:
            f, off = src_of(n)
            if not same(o1, g.data_start + to[n].offset, f, off, p["nbytes"][n]):
                bad.append(f"{n} differs from ours")
    for n in [p["order"][0], p["order"][-1], exps[0], exps[len(exps) // 2], exps[-1]]:
        f, off = src_of(n)
        nb = p["nbytes"][n]
        oo = g.data_start + to[n].offset
        k = min(MIB, nb)
        if not (same(o1, oo, f, off, k) and same(o1, oo + nb - k, f, off + nb - k, k)):
            bad.append(f"{n}: bytes differ from {Path(f).name}")
    if not os.path.samefile(o2, p["rest"][1]):
        bad.append(f"{o2.name} is not our shard 2")
    print(("VERIFY OK: " if not bad else "VERIFY FAILED: ") + (
        f"{len(names)} tensors in our order, {len(exps)} experts with the expert shards' types, the rest ours; split keys "
        f"{sk}; size {size:,} B; head tensors = ours; spot checks equal; shard 2 = our inode" if not bad else "; ".join(bad)[:600]))
    return not bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir")
    ap.add_argument("base", help="the output name before -0000N-of-00002.gguf")
    ap.add_argument("--rest", required=True, help="our shard 1 (-00001-of-00002.gguf); shard 2 beside it")
    ap.add_argument("--experts", nargs="+", required=True, help="the shards holding the 144 routed-expert tensors")
    ap.add_argument("--dry", action="store_true", help="plan and check only (headers; no file written)")
    ap.add_argument("--min-free-gb", type=float, default=100)
    a = ap.parse_args()
    p = plan(a)
    if a.dry:
        print("dry run: nothing written")
        return 0
    o1, o2 = write(a, p)
    return 0 if verify(p, o1, o2) else 1


if __name__ == "__main__":
    sys.exit(main())
