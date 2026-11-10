#!/usr/bin/env python3
"""verify_models.py - Round 19 integrity check after the RAM fault (bit errors at 6200 MT/s, fixed 2026-10-10).

Hashes every model file on this PC and compares it with its source:
  * Hugging Face downloads (the hub cache, models/ISTA-GSQ-RCO, models/r15): the LFS SHA-256 (or the git blob SHA-1 of a
    small file) recorded at download time AND the value the repo's API lists today at the same revision.
  * files we made (stand-ins, packs, MTP runtime files): a recorded hash where one exists (models/r15/splice-q5/SHA256,
    NOTES.md's MTP prefixes), else the copies that should be identical are compared with each other; the rest are listed
    as "no source hash".
Writes results/r19/integrity/models.tsv and prints a summary. Read-only on every model file.
    .venv/bin/python work/r19/integrity/verify_models.py [JOBS]"""
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

WS = Path("/home/USER/ai-speed-testing/strata-compare")
HUB = Path("/home/USER/.cache/huggingface/hub")
OUT = WS / "results/r19/integrity"
JOBS = int(sys.argv[1]) if len(sys.argv) > 1 else 12


def digest(args):
    path, kind = args
    h = hashlib.sha1() if kind == "gitsha1" else hashlib.sha256()
    size = os.stat(path).st_size
    if kind == "gitsha1":
        h.update(b"blob %d\0" % size)
    buf = bytearray(64 << 20)
    mv = memoryview(buf)
    with open(path, "rb", buffering=0) as f:
        while n := f.readinto(buf):
            h.update(mv[:n])
    return h.hexdigest()


def remote_tree(repo, rev):
    try:
        from huggingface_hub import HfApi
        out = {}
        for it in HfApi().list_repo_tree(repo, revision=rev, recursive=True):
            if getattr(it, "blob_id", None) is None:
                continue
            lfs = getattr(it, "lfs", None)
            out[it.path] = lfs.sha256 if lfs else it.blob_id
        return out
    except Exception as e:  # noqa: BLE001
        print(f"remote tree {repo}@{rev[:8]}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
        return None


rows = []  # dict(path, expect, recorded_from, remote, kind)
trees = {}


def add(path, expect, src, repo=None, rev=None, rel=None):
    kind = "gitsha1" if expect and len(expect) == 40 else "sha256"
    remote = None
    if repo:
        key = (repo, rev)
        if key not in trees:
            trees[key] = remote_tree(repo, rev)
        t = trees[key]
        remote = "n/a" if t is None else t.get(rel, "absent")
    rows.append(dict(path=str(path), expect=expect, src=src, remote=remote, kind=kind))


# 1. the hub cache
for md in sorted(HUB.glob("models--*")):
    repo = md.name[len("models--"):].replace("--", "/")
    for snap in sorted((md / "snapshots").glob("*")):
        for p in sorted(snap.rglob("*")):
            if not p.is_symlink() and not p.is_file():
                continue
            oid = Path(os.readlink(p)).name if p.is_symlink() else None
            add(p, oid, "hub blob name", repo, snap.name, str(p.relative_to(snap)))
    for inc in md.glob("blobs/*.incomplete"):
        rows.append(dict(path=str(inc), expect=None, src="INCOMPLETE download", remote=None, kind="sha256"))

# 2. models/ISTA-GSQ-RCO (hf download --local-dir; metadata = commit, etag, time)
ista = WS / "models/ISTA-GSQ-RCO"
for meta in sorted((ista / ".cache/huggingface/download").rglob("*.metadata")):
    rel = str(meta.relative_to(ista / ".cache/huggingface/download"))[: -len(".metadata")]
    commit, etag = meta.read_text().split()[:2]
    add(ista / rel, etag, "local-dir metadata etag", "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF", commit, rel)

# 3. models/r15 (work/r15/download.sh: unsloth @ 38bb39ee, checked against the LFS SHA-256 at download)
REV15 = "38bb39ee97821de2c9009abb7e93950eec396e66"
for sub in ("Q8_0", "UD-Q5_K_XL"):
    rec = {i["path"]: i["lfs"]["oid"] for i in json.load(open(WS / f"tmp/r15/tree-{'q8' if sub == 'Q8_0' else 'q5'}.json")) if "lfs" in i}
    for p in sorted((WS / "models/r15" / sub).glob("*.gguf")):
        rel = f"{sub}/{p.name}"
        add(p, rec.get(rel), "tmp/r15 tree json (download time)", "unsloth/Qwen3.8-Flash-Next-GGUF", REV15, rel)

# 4. files we made, with a recorded hash
for line in (WS / "models/r15/splice-q5/SHA256").read_text().splitlines():
    h, rel = line.split()
    add(WS / rel, h, "models/r15/splice-q5/SHA256")
for d in ("strata/mtp", "strata-v0115/mtp"):
    for rel, pre in (("mtp-q2_0.gguf", "a22206a4"), ("rt/experts.bin", "09398406"), ("rt/dense.bin", "c724dc0b")):
        if (WS / d / rel).exists():
            add(WS / d / rel, "prefix:" + pre, "NOTES.md setup record (prefix)")

# 5. files we made, no recorded hash (hashed; copies compared below)
extra = [WS / "models/r11/ple-fp8.gguf", WS / "models/r11/token-embd-bf16.gguf", WS / "models/r12/splice3.gguf"]
for pk in ["strata-v0115/packs/iq3_s", "strata/packs/iq3_s", "strata-v0111/packs/iq3_s", "bringup/out/r19/pack",
           "bringup/out/r16z/pack", "bringup/out/r16/pack"]:
    for p in sorted((WS / pk).rglob("*")):
        if p.is_file():
            extra.append(p)
for d in ("strata-v0115/mtp/rt", "strata/mtp/rt"):
    for p in sorted((WS / d).glob("*")):
        if p.name not in ("experts.bin", "dense.bin"):
            extra.append(p)
for p in sorted(WS.glob("strata*/data/expert-profile.bin")):
    extra.append(p)
for p in [Path("/home/USER/ai/ComfyUI/models"), Path("/home/USER/ai/flash-next"), Path("/home/USER/ai-speed-testing/signal-3.8-opus/models")]:
    for q in sorted(p.rglob("*")):
        if q.is_file() and q.suffix in (".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx") and q.stat().st_size > 50e6:
            extra.append(q)
seen = {r["path"] for r in rows}
for p in extra:
    if p.exists() and str(p) not in seen:
        rows.append(dict(path=str(p), expect=None, src="made here / no source hash", remote=None, kind="sha256"))

# hash (once per inode), largest first
by_inode = {}
for r in rows:
    if Path(r["path"]).exists() and not r["path"].endswith(".incomplete"):
        st = os.stat(r["path"])
        by_inode.setdefault((st.st_dev, st.st_ino, r["kind"]), (r["path"], r["kind"], st.st_size))
todo = sorted(by_inode.values(), key=lambda x: -x[2])
print(f"{len(rows)} entries, {len(todo)} distinct files, {sum(x[2] for x in todo) / 1e9:.0f} GB to hash with {JOBS} jobs", flush=True)
with ProcessPoolExecutor(JOBS) as ex:
    got = dict(zip(((x[0], x[1]) for x in todo), ex.map(digest, [(x[0], x[1]) for x in todo])))
res = {}
for r in rows:
    if not Path(r["path"]).exists() or r["path"].endswith(".incomplete"):
        r["got"], r["verdict"] = None, "MISSING/INCOMPLETE"
        continue
    st = os.stat(r["path"])
    r["got"] = got[next((k for k in got if os.stat(k[0]).st_ino == st.st_ino and k[1] == r["kind"]), None)] if (r["path"], r["kind"]) not in got else got[(r["path"], r["kind"])]
    e = r["expect"]
    if e is None:
        r["verdict"] = "no source hash"
    elif e.startswith("prefix:"):
        r["verdict"] = "OK (prefix)" if r["got"].startswith(e[7:]) else "MISMATCH"
    else:
        r["verdict"] = "OK" if r["got"] == e else "MISMATCH"
    if r["remote"] not in (None, "n/a") and r["remote"] != r["got"]:
        r["verdict"] += " / REMOTE DIFFERS" if r["remote"] != "absent" else " / not in remote tree"
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "models.tsv", "w") as f:
    f.write("verdict\tpath\tbytes\tsha\texpected\trecorded_from\tremote_today\n")
    for r in rows:
        sz = os.stat(r["path"]).st_size if Path(r["path"]).exists() else 0
        f.write(f"{r['verdict']}\t{r['path']}\t{sz}\t{r['got']}\t{r['expect']}\t{r['src']}\t{r['remote']}\n")
from collections import Counter
print(Counter(r["verdict"] for r in rows))
for r in rows:
    if not r["verdict"].startswith("OK") or "REMOTE" in r["verdict"] or "remote" in r["verdict"]:
        if r["verdict"] != "no source hash":
            print("ATTENTION", r["verdict"], r["path"], r["got"], r["expect"], r["remote"])
# copies that should be identical
groups = {}
for r in rows:
    if r["src"] == "made here / no source hash" and r["got"]:
        p = r["path"]
        for pk in ("packs/iq3_s/", "/pack/", "mtp/rt/", "data/expert-profile.bin"):
            if pk in p:
                groups.setdefault(p.split(pk, 1)[1] if pk != "data/expert-profile.bin" else "expert-profile.bin", []).append((p, r["got"]))
with open(OUT / "copies.txt", "w") as f:
    for k, v in sorted(groups.items()):
        n = len({h for _, h in v})
        line = f"{'SAME' if n == 1 else 'DIFFER'}\t{k}\t" + "  ".join(f"{p.replace(str(WS) + '/', '')}={h[:12]}" for p, h in v)
        f.write(line + "\n")
        print(line)
