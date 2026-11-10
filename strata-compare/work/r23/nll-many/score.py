#!/usr/bin/env python3
"""score.py - round 23, item 6 (Karl): text NLL at MANY positions for the next revision of the KL gate.

Why: kernel_rule3.py scores the text NLL of one position per pf_yardstick long40 prompt (36 positions). One chaotic
copy token (NLL 0 <-> 8-14 nats between rounding-level builds, NOTES round 3/16) moves that mean by ~0.2 nats, so the
10-26 spread rule (candidate's distance <= 1.10 x the larger rounding reference's distance) decides on noise.

How (no engine change, no build): every engine we have (P021n, P021m, P027, P028, P028x, P0210 and the twins) has the
prompt path's debug hook STRATA_PREFILL_DUMP_R - the final residual (hc x n_embd fp32) of every 64th prompt row the
BATCHED path computes (rows at positions p = 0, 64, 128, ...; run_impl, and in v0.2.7+ the layer-major walk too) - and
STRATA_PREFILL_DUMP_R_ALL (every row, BF16; run_impl only, so it declines the layer-major walk, which our configs pin
off anyway). `run` reads each long text ONCE (one cold prompt, pf_yardstick's yardstick settings) and keeps those rows;
`compare` applies the model's own head offline (the final hyper-connection mixer output_hc_* + output.weight Q6_K, read
from the GGUF; layer.cpp lm_head_mix / gr.hpp gr_read's contract, BF16 activations) and gets the full-vocabulary
distribution at every kept row: the NLL of the text's own next token, the top-1 pick, and the exact KL against the
reference build at the same row. ~3,900 positions from the 11 long texts (every 64th row from 1,024 on, 2K-32K) for one
cold read each (~262K prompt tokens, ~5 min an arm on the 5080 alone); --rows all:K keeps every K-th row instead.

  score.py run CONFIG OUTDIR [--set long11|long8] [--rows dumpr|all:K] [--env K=V ...] [--kv fp16|int8]
                [--pcie-frac auto|X] [--min-free-gb 16] [--max-len 32768]
      one `strata --serve` engine (pf_yardstick.py run's engine and fixed settings: experts on the CPU, no adaptation,
      no PCIe share, FP16 K/V, STRATA_PREFILL_CPU_SHARE=0 unless --env sets it, --prefill auto, the 64-token short read),
      one GEN 1 request per text (and 4 short "check" requests for `validate`); the dump is moved to OUTDIR/r.<i>
      (or a.<i>.npy) after each request; first.<i> = the decode window's logits after each prompt; index.json.
  score.py validate OUTDIR
      the offline head against the engine's own head: each check request's window row (first.<i>, the logits at its
      last prompt token c-1, c-1 = 0 mod 64) vs the offline head on the full text's dumped row at the same position
      (another path - batched vs window - so rounding-level KL is expected, not 0; a wrong head gives KL >> 1).
  score.py compare ROOT --ref ref --refs R1,R2 --cands A,B [--format dump|pfy|logpos] [--block N|text|prompt|segment]
                [--min-pos 1024] [--stride 1] [--boot 10000] [--json OUT] [--rows-out OUT.tsv] [--se-cap 0.02]
      paired per-position NLL differences against the reference arm, the mean distance with a block-bootstrap CI
      (blocks of --block tokens inside a text - positions in one text correlate - resampled with replacement, the same
      blocks for every arm), the KL metrics of kernel_rule2/3 (mean, p90, KL > 1, changed top-1) on the same positions,
      and both NLL verdicts: rule3 (the 10-26 point rule) and the proposed CI rule (PLAN.md).
      --format pfy: pf_yardstick run dirs (first.<i> + index.json; long40 / long80b): reproduces kernel_rule3.py's
      numbers on the 36 (40) positions; several ROOTs are pooled (gap 8 long40 + gap 9 long80b).
      --format logpos: STRATA_LOGPOS / quant_quality TSV runs (score.tsv + score.tsv.seg.json, e.g. the DeepSeek gate's
      teacher dirs): KL over the reference's top 64 as skipcheck.kl_list.
  score.py selftest [--quick]     synthetic checks (Q6_K decoder, the mixer, the bootstrap, the dump pipeline)

Positions: a dumped row at position p predicts the token at p + 1 (teacher-forced: the text's own token); rows below
--min-pos (1,024; kernel_rule2/3 judge prompts > 1,000 tokens) are not scored. CPU: `compare` on dumps needs the head
dequantized in RAM (248,320 x 2,560 fp32 = 2.5 GB) and one 2,560 x 248,320 GEMM per row (BLAS; --threads N sets
OPENBLAS/OMP threads before numpy loads; default 1).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import time


sys.dont_write_bytecode = True   # the modules it loads live in trees this script must not write to (work/r22, strata-*)


def _threads_from_argv() -> None:
    n = "1"
    for i, a in enumerate(sys.argv):
        if a == "--threads" and i + 1 < len(sys.argv):
            n = sys.argv[i + 1]
        elif a.startswith("--threads="):
            n = a.split("=", 1)[1]
    for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(k, n)


_threads_from_argv()
import numpy as np  # noqa: E402

SC = pathlib.Path("/home/USER/ai-speed-testing/strata-compare")
PFY = SC / "work/r22/pf_yardstick.py"
PR = SC / "bringup/out/r20a/prompts"
GGUF = SC / "models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf"
GGUF_TOOLS = SC / "strata-r22p0210/tools"
TOL, KL_HIGH = 1.10, 1.0
Z_ONE_SIDED = 1.645         # the proposed NLL rule's one-sided 95 % noise margin (x the bootstrap se)
EVERY = 64                  # STRATA_PREFILL_DUMP_R's row spacing (positions = 0 mod 64)
N_EMBD, HC, HC_LR, EPS = 2560, 4, 320, 1e-6
D = HC * N_EMBD

# the long texts, each read once up to max_len (long40's cap: 32,768). long8 = long40's 8 texts; long11 adds long80b's
# three (pp32k, tf-long96k, pp8k - they partly share content with 32k.tokens / tf-long64k: blocks stay inside a text)
SETS = {
    "long8": ["32k.tokens", "tf-long28k.prompt", "tf-long40k.prompt", "tf-long64k.prompt", "tf-long112k.prompt",
              "pp4k.tokens", "ldrsyn20k.tokens", "rep9k.tokens"],
}
SETS["long11"] = SETS["long8"] + ["pp32k.tokens", "tf-long96k.prompt", "pp8k.tokens"]
SETS["mock"] = ["pp4k.tokens"]           # selftest only (mock_engine.py)
# validate: a short prompt whose last token c - 1 is a dumped row (0 mod 64) of the same text's full read
CHECKS = [("32k.tokens", 2049), ("tf-long28k.prompt", 4097), ("ldrsyn20k.tokens", 8193), ("tf-long64k.prompt", 12289),
          ("pp4k.tokens", 2049)]       # (only those whose text is in the set run)


def load_ids(f: str) -> list[int]:
    return [int(x) for x in (PR / f).read_text().replace("\n", ",").split(",") if x.strip()]


def module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ================================================================================================ the offline head
def bf16_round(x: np.ndarray) -> np.ndarray:
    """round-to-nearest-even to BF16, as gr_parity.cpp's to_bf16 / ref/quant.py::bf16 (finite inputs)"""
    u = np.ascontiguousarray(x, dtype=np.float32).view(np.uint32).astype(np.uint64)
    u = (u + ((u >> 16) & 1) + 0x7FFF) & 0xFFFF0000
    return u.astype(np.uint32).view(np.float32)


def bf16_to_f32(u16: np.ndarray) -> np.ndarray:
    return (np.ascontiguousarray(u16, dtype=np.uint16).astype(np.uint32) << 16).view(np.float32)


def dequant_q6_k(raw: np.ndarray) -> np.ndarray:
    """ggml's dequantize_row_q6_K on (nb, 210) uint8 blocks -> (nb, 256) float32. Block: ql[128] (low 4 bits), qh[64]
    (high 2 bits), scales int8[16], d fp16. Output j of a block takes scale j // 16."""
    raw = np.ascontiguousarray(raw, dtype=np.uint8).reshape(-1, 210)
    ql, qh = raw[:, :128], raw[:, 128:192]
    sc = raw[:, 192:208].view(np.int8).astype(np.float32)
    d = raw[:, 208:210].copy().view(np.float16).astype(np.float32)        # (nb, 1)
    out = np.empty((raw.shape[0], 256), np.float32)
    for h in range(2):
        L, H = ql[:, 64 * h:64 * h + 64], qh[:, 32 * h:32 * h + 32]
        q = np.concatenate([(L[:, :32] & 0xF) | (((H >> 0) & 3) << 4), (L[:, 32:] & 0xF) | (((H >> 2) & 3) << 4),
                            (L[:, :32] >> 4) | (((H >> 4) & 3) << 4), (L[:, 32:] >> 4) | (((H >> 6) & 3) << 4)],
                           axis=1).astype(np.float32) - 32.0                # (nb, 128)
        s = np.repeat(sc[:, 8 * h:8 * h + 8], 16, axis=1)                  # (nb, 128)
        out[:, 128 * h:128 * h + 128] = (d * s) * q
    return out


def dequant_q6_k_scalar(blk: bytes) -> list[float]:
    """a line-by-line transcription of ggml's dequantize_row_q6_K for ONE block (the selftest's reference)"""
    ql, qh = list(blk[:128]), list(blk[128:192])
    sc = [x - 256 if x > 127 else x for x in blk[192:208]]
    d = float(np.frombuffer(blk[208:210], np.float16)[0])
    y = [0.0] * 256
    yo = qo = ho = so = 0
    for _ in range(2):
        for l in range(32):
            is_ = l // 16
            q1 = ((ql[qo + l] & 0xF) | (((qh[ho + l] >> 0) & 3) << 4)) - 32
            q2 = ((ql[qo + l + 32] & 0xF) | (((qh[ho + l] >> 2) & 3) << 4)) - 32
            q3 = ((ql[qo + l] >> 4) | (((qh[ho + l] >> 4) & 3) << 4)) - 32
            q4 = ((ql[qo + l + 32] >> 4) | (((qh[ho + l] >> 6) & 3) << 4)) - 32
            y[yo + l] = float(np.float32(np.float32(d) * np.float32(sc[so + is_])) * np.float32(q1))
            y[yo + l + 32] = float(np.float32(np.float32(d) * np.float32(sc[so + is_ + 2])) * np.float32(q2))
            y[yo + l + 64] = float(np.float32(np.float32(d) * np.float32(sc[so + is_ + 4])) * np.float32(q3))
            y[yo + l + 96] = float(np.float32(np.float32(d) * np.float32(sc[so + is_ + 6])) * np.float32(q4))
        yo += 128; qo += 64; ho += 32; so += 8
    return y


class Head:
    """output_hc_* (the final hyper-connection mixer, gr_read) + output.weight, from the model GGUF (the native pack's
    copies of output_hc_* are byte-identical, checked 11-04; output.weight is served from the GGUF natively)."""

    def __init__(self, gguf: pathlib.Path = GGUF, weights=None):
        if weights is not None:                       # selftest: (w_norm, w_down, w_up, W, n_embd, hc, lr)
            self.w_norm, self.w_down, self.w_up, self.W, self.n, self.hc, self.lr = weights
            return
        sys.path.insert(0, str(GGUF_TOOLS))
        import gguf_reader as G                       # header reader only (no ggml)
        g = G.GGUFFile(gguf)
        t = {x.name: x for x in g.tensors}
        need = {"output.weight": "Q6_K", "output_hc_norm.weight": "F32", "output_hc_down.weight": "BF16",
                "output_hc_up.weight": "BF16"}
        for k, ty in need.items():
            if k not in t or t[k].type_name != ty:
                raise SystemExit(f"{gguf.name}: {k} is not {ty} (found {t[k].type_name if k in t else 'none'})")
        self.n, self.hc, self.lr = N_EMBD, HC, HC_LR
        if t["output.weight"].shape != [N_EMBD, 248320] or t["output_hc_down.weight"].shape != [D, HC_LR]:
            raise SystemExit("unexpected head shapes")

        def rd(x, nbytes):
            with open(gguf, "rb") as f:
                f.seek(g.data_start + x.offset)
                b = f.read(nbytes)
            if len(b) != nbytes:
                raise SystemExit(f"{x.name}: short read")
            return b
        self.w_norm = np.frombuffer(rd(t["output_hc_norm.weight"], D * 4), np.float32).copy()
        self.w_down = bf16_to_f32(np.frombuffer(rd(t["output_hc_down.weight"], D * HC_LR * 2), np.uint16)).reshape(HC_LR, D)
        self.w_up = bf16_to_f32(np.frombuffer(rd(t["output_hc_up.weight"], D * HC_LR * 2), np.uint16)).reshape(D, HC_LR)
        V = t["output.weight"].shape[1]
        nb_row = N_EMBD // 256
        raw = np.frombuffer(rd(t["output.weight"], V * nb_row * 210), np.uint8).reshape(V * nb_row, 210)
        W = np.empty((V, N_EMBD), np.float32)
        step = 8192                                    # rows per piece (bounds the temporaries)
        for v0 in range(0, V, step):
            v1 = min(V, v0 + step)
            W[v0:v1] = dequant_q6_k(raw[v0 * nb_row:v1 * nb_row]).reshape(v1 - v0, N_EMBD)
        self.W = W

    def mix(self, R: np.ndarray, bf16_act: bool = True) -> np.ndarray:
        """gr_read for P tokens: R (P, hc * n) -> mixed (P, n). Per-stream RMSNorm (gamma as stored), lo = silu(
        (bf16(xn) @ w_down.T) / hc), gate = sigmoid(bf16(lo) @ w_up.T), mixed = mean over streams of xn * gate"""
        with np.errstate(over="ignore"):          # exp(-x) of a saturated gate: inf -> sigmoid 0, silu -0 (correct)
            return self._mix(R, bf16_act)

    def _mix(self, R: np.ndarray, bf16_act: bool) -> np.ndarray:
        P, n, hc = R.shape[0], self.n, self.hc
        R = np.asarray(R, np.float32).reshape(P, hc, n)
        ms = (R.astype(np.float64) ** 2).mean(axis=2, keepdims=True)
        rs = (1.0 / np.sqrt(ms + EPS)).astype(np.float32)
        xn = (R * rs) * self.w_norm.reshape(1, hc, n)
        act = bf16_round(xn) if bf16_act else xn
        p = act.reshape(P, hc * n).astype(np.float64) @ self.w_down.T.astype(np.float64)
        p = (p / hc).astype(np.float32)
        lo = p / (1.0 + np.exp(-p))
        lq = bf16_round(lo) if bf16_act else lo
        gate = (lq.astype(np.float64) @ self.w_up.T.astype(np.float64)).astype(np.float32)
        s = 1.0 / (1.0 + np.exp(-gate))
        return (xn * s.reshape(P, hc, n)).sum(axis=1) / np.float32(hc)

    def logits(self, R: np.ndarray) -> np.ndarray:
        """(P, hc * n) residual rows -> (P, vocab) float32 logits"""
        return self.mix(R) @ self.W.T

    def logp(self, R: np.ndarray) -> np.ndarray:
        """(P, hc * n) residual rows -> (P, vocab) log-probabilities (float64)"""
        lg = self.logits(R).astype(np.float64)
        lg -= lg.max(axis=1, keepdims=True)
        lg -= np.log(np.exp(lg).sum(axis=1, keepdims=True))
        return lg


def mix_scalar(R, w_norm, w_down, w_up, n, hc, lr):
    """gr_parity.cpp's reference(), transcribed loop by loop for one token (the selftest's reference)"""
    hd = hc * n
    xn = [0.0] * hd
    for c in range(hc):
        ms = sum(float(R[c * n + d]) ** 2 for d in range(n)) / n
        rs = float(np.float32(1.0 / math.sqrt(ms + EPS)))
        for d in range(n):
            xn[c * n + d] = float(np.float32(np.float32(R[c * n + d]) * np.float32(rs)) * np.float32(w_norm[c * n + d]))
    act = [float(bf16_round(np.array([x], np.float32))[0]) for x in xn]
    lo = []
    for k in range(lr):
        a = sum(act[i] * float(w_down[k, i]) for i in range(hd))
        p = float(np.float32(a)) / hc
        lo.append(p / (1.0 + math.exp(-p)))
    lq = [float(bf16_round(np.array([x], np.float32))[0]) for x in lo]
    mixed = []
    for d in range(n):
        m = 0.0
        for c in range(hc):
            i = c * n + d
            g = float(np.float32(sum(lq[k] * float(w_up[i, k]) for k in range(lr))))
            m += xn[i] * (1.0 / (1.0 + math.exp(-g)))
        mixed.append(m / hc)
    return mixed


# ================================================================================================ run (the engine)
def cmd_run(a) -> int:
    py = module("pf_yardstick", PFY)
    qq = py.tool()
    cfg = json.load(open(a.config, encoding="utf-8-sig"))
    out = pathlib.Path(a.outdir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for pat in ("first.*", "r.*", "a.*.npy", "dump.cur", "dumpall.cur"):
        for f in out.glob(pat):
            f.unlink()
    mode, K = (a.rows, 0) if a.rows == "dumpr" else ("all", int(a.rows.split(":", 1)[1]))
    reqs = []
    for f in SETS[a.set]:
        ids = load_ids(f)
        n = min(len(ids), a.max_len)
        reqs.append({"name": f"{f.split('.')[0]}-{n}", "file": f, "cut": n, "kind": "text"})
    for f, c in CHECKS:
        if f not in SETS[a.set]:
            continue
        reqs.append({"name": f"check-{f.split('.')[0]}-{c}", "file": f, "cut": c, "kind": "check"})
    env = dict(os.environ)
    env.update(cfg.get("env", {}))
    if cfg.get("lib_dirs"):
        env["LD_LIBRARY_PATH"] = ":".join(cfg["lib_dirs"] + [env.get("LD_LIBRARY_PATH", "")])
    env.update(qq.FIXED_ENV)
    for kv in a.env or []:
        k, _, v = kv.partition("=")
        env[k] = v
    env["STRATA_DUMP_FIRST_LOGITS"] = str(out / "first")
    cur = out / ("dump.cur" if mode == "dumpr" else "dumpall.cur")
    env["STRATA_PREFILL_DUMP_R" if mode == "dumpr" else "STRATA_PREFILL_DUMP_R_ALL"] = str(cur)
    if qq.mem_available_gb() < a.min_free_gb:
        raise SystemExit(f"only {qq.mem_available_gb():.0f} GB available (< {a.min_free_gb}): not starting an engine")
    args = qq.engine_args(cfg, False, max(r["cut"] for r in reqs))
    k = args.index("--short-read")
    del args[k:k + 2]                      # as pf_yardstick: the default 64-token short read, the batched prompt path
    k = args.index("--prefill")
    args[k + 1] = "auto"
    k = args.index("--kv")
    args[k + 1] = a.kv
    if a.pcie_frac is not None:
        k = args.index("--pcie-frac")
        if a.pcie_frac == "auto":
            del args[k:k + 2]
            env.pop("STRATA_PCIE_FRAC_DEFAULT", None)
        else:
            args[k + 1] = a.pcie_frac
    errf = open(out / "stderr.txt", "w")
    print("engine:", " ".join(args), flush=True)
    t0 = time.time()
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errf, text=True,
                         cwd=cfg.get("cwd"), env=env, bufsize=1)
    for line in p.stdout:
        if line.startswith("READY"):
            break
    else:
        raise SystemExit(f"the engine ended before READY (exit {p.wait()}); see {out}/stderr.txt")
    bad = []
    for i, r in enumerate(reqs):
        ids = load_ids(r["file"])[:r["cut"]]
        if cur.exists():
            cur.unlink()
        p.stdin.write("GEN 1 " + ",".join(map(str, ids)) + "\n")
        p.stdin.flush()
        done = None
        for line in p.stdout:
            if line.startswith(("DONE", "ERR")):
                done = line.strip()
                break
        if done is None or not done.startswith("DONE") or "nonfinite" in done:
            p.kill()
            raise SystemExit(f"{r['name']}: the engine answered {done!r}; see {out}/stderr.txt")
        r["tokens"] = len(ids)
        want = list(range(0, len(ids) - 1, EVERY if mode == "dumpr" else K))
        if r["kind"] == "check":           # only its window row (first.<i>) is used
            cur.unlink(missing_ok=True)
            r["rows"] = 0
            continue
        if not cur.exists():
            bad.append(f"{r['name']}: no dump (the hook did not fire)")
            r["rows"] = 0
            continue
        if mode == "dumpr":
            rec = np.fromfile(cur, dtype=np.dtype([("pos", "<i8"), ("r", "<f4", (D,))]))
            got = rec["pos"].tolist()
            shutil.move(str(cur), str(out / f"r.{i}"))
            r["dump"] = f"r.{i}"
        else:
            raw = np.fromfile(cur, dtype=np.uint16)
            nrow = raw.size // D
            if raw.size % D or nrow != len(ids) - 1:
                bad.append(f"{r['name']}: R_ALL holds {raw.size / D:.1f} rows, expected {len(ids) - 1}")
            keep = raw[:nrow * D].reshape(nrow, D)[::K]
            np.save(out / f"a.{i}.npy", keep)
            got = list(range(0, nrow, K))
            cur.unlink()
            r["dump"] = f"a.{i}.npy"
        r["rows"] = len(got)
        if got != want:                    # a prompt read in several batched calls truncates the hook's file
            bad.append(f"{r['name']}: rows at {got[:3]}..{got[-3:] if got else []} ({len(got)}), expected {len(want)} "
                       f"from 0 every {want[1] - want[0] if len(want) > 1 else '?'}")
        print(f"{r['name']}: {len(ids)} tokens, {r['rows']} rows, {time.time() - t0:.0f} s", flush=True)
    p.stdin.write("QUIT\n")
    p.stdin.flush()
    try:
        p.wait(timeout=600)
    except subprocess.TimeoutExpired:
        p.kill()
    errf.close()
    err = (out / "stderr.txt").read_text(errors="replace")
    path_lines = [l for l in err.splitlines() if any(s in l for s in ("layer-major", "LAYER_MAJOR", "small-card",
                                                                     "STRATA_PF_FUSED", "PREFILL_V2", "v2 kernels"))][:6]
    (out / "index.json").write_text(json.dumps({"requests": reqs, "set": a.set, "rows": a.rows, "D": D, "args": args,
                                                "env": a.env or [], "config": a.config, "kv": a.kv,
                                                "seconds": round(time.time() - t0), "problems": bad,
                                                "path_lines": path_lines}, indent=1))
    for b in bad:
        print("PROBLEM:", b)
    print(f"{sum(r['rows'] for r in reqs)} rows from {sum(r['kind'] == 'text' for r in reqs)} texts in "
          f"{time.time() - t0:.0f} s" + "".join(f"\n  {l}" for l in path_lines))
    return 1 if bad else 0


# ================================================================================================ arms -> positions
class Arms:
    """aligned per-position data: key[i] = (block text, position), block[i], target[i]; per arm nll[name][i]
    (nan: not scored), and against the reference kl[name][i] / flip[name][i] (nan / False where not defined)"""

    def __init__(self):
        self.keys, self.block, self.nll, self.kl, self.flip, self.note = [], None, {}, {}, {}, []


def rows_of(d: pathlib.Path, r: dict):
    """(positions, rows (P, D) float32) of one dumped request"""
    if r["dump"].startswith("r."):
        rec = np.fromfile(d / r["dump"], dtype=np.dtype([("pos", "<i8"), ("r", "<f4", (D,))]))
        return rec["pos"].astype(np.int64), rec["r"]
    a = np.load(d / r["dump"], mmap_mode="r")
    K = int(str(json.loads((d / "index.json").read_text())["rows"]).split(":")[1])
    return np.arange(a.shape[0], dtype=np.int64) * K, _Bf16Rows(a)


class _Bf16Rows:
    """R_ALL rows kept as BF16 bits: indexing decodes them to float32"""

    def __init__(self, a):
        self.a = a

    def __len__(self):
        return self.a.shape[0]

    def __getitem__(self, i):
        return bf16_to_f32(np.asarray(self.a[i]))


def lse_rows(z: np.ndarray):
    """float32 logits -> (unnormalised exp rows float32, log-sum-exp float64): sums in float64"""
    m = z.max(axis=1)
    e = np.exp(z - m[:, None])
    s = e.sum(axis=1, dtype=np.float64)
    return e, m.astype(np.float64) + np.log(s), s


def load_dump(root: pathlib.Path, ref: str, arms: list[str], a, head: Head | None = None) -> Arms:
    head = head or Head()
    idx = {x: json.loads((root / x / "index.json").read_text()) for x in [ref] + arms}
    out = Arms()
    texts = [r for r in idx[ref]["requests"] if r["kind"] == "text" and r.get("rows")]
    cols = {x: {"nll": [], "kl": [], "flip": []} for x in [ref] + arms}
    blocks, bid, spacings = [], {}, set()
    for r in texts:
        ids = load_ids(r["file"])[:r["cut"]]
        ri = {x: next((q for q in idx[x]["requests"] if q["name"] == r["name"] and q.get("rows")), None) for x in arms}
        for x, q in ri.items():
            if q is None:
                raise SystemExit(f"{x}: no dump for {r['name']}")
        pos_ref, R_ref = rows_of(root / ref, r)
        spacing = int(pos_ref[1] - pos_ref[0]) if len(pos_ref) > 1 else EVERY
        sel = np.nonzero((pos_ref >= a.min_pos) & (pos_ref + 1 < len(ids)) & (pos_ref % (spacing * a.stride) == 0))[0]
        spacings.add(spacing * a.stride)
        data = {}
        for x in arms:
            pa, Ra = rows_of(root / x, ri[x])
            where = {int(v): j for j, v in enumerate(pa)}
            miss = [int(pos_ref[j]) for j in sel if int(pos_ref[j]) not in where]
            if miss:
                raise SystemExit(f"{x} {r['name']}: rows missing at {miss[:5]}")
            data[x] = (Ra, [where[int(pos_ref[j])] for j in sel])
        for c0 in range(0, len(sel), a.chunk):
            js = sel[c0:c0 + a.chunk]
            tg = np.array([ids[int(pos_ref[j]) + 1] for j in js])
            P_ = np.arange(len(js))
            zr = head.logits(np.asarray(R_ref[js], np.float32))
            er, lser, sr = lse_rows(zr)
            pr = (er / sr[:, None].astype(np.float32))                # p_ref (float32)
            del er
            cols[ref]["nll"] += (lser - zr[P_, tg]).tolist()
            ar = zr.argmax(axis=1)
            for x in arms:
                Ra, wj = data[x]
                za = head.logits(np.asarray(Ra[wj[c0:c0 + a.chunk]], np.float32))
                _, lsea, _ = lse_rows(za)
                cols[x]["nll"] += (lsea - za[P_, tg]).tolist()
                # KL(ref || arm) = sum p_ref (z_ref - z_arm) + lse_arm - lse_ref (exactly 0 for identical rows)
                kl = (pr * (zr - za)).sum(axis=1, dtype=np.float64) + (lsea - lser)
                cols[x]["kl"] += np.maximum(kl, 0.0).tolist()
                cols[x]["flip"] += (za.argmax(axis=1) != ar).tolist()
            for j in js:
                p = int(pos_ref[j])
                out.keys.append((r["name"], p))
                b = (r["name"], p // a.block_tokens) if a.block_tokens > 0 else (r["name"],)
                blocks.append(bid.setdefault(b, len(bid)))
        print(f"  {r['name']}: {len(sel)} positions", flush=True)
    out.block = np.array(blocks)
    for x in [ref] + arms:
        out.nll[x] = np.array(cols[x]["nll"])
        if x != ref:
            out.kl[x], out.flip[x] = np.array(cols[x]["kl"]), np.array(cols[x]["flip"], bool)
    out.note.append(f"dump rows (offline head), positions >= {a.min_pos}, every {'/'.join(map(str, sorted(spacings)))}th "
                    f"row; blocks: {'whole text' if a.block_tokens <= 0 else f'{a.block_tokens} tokens'}")
    return out


def pfy_next(idx_reqs: list[dict]) -> list:
    """per request: the text's next token after the cut (None at the text's end) - long40 / long80b order, as
    kernel_rule3.next_tokens"""
    py = module("pf_yardstick", PFY)
    for name, table in (("long40", py.LONG40), ("long80b", py.LONG80B)):
        cuts = [(f, n) for f, cs in table for n in cs]
        if len(cuts) != len(idx_reqs):
            continue
        out = []
        for (f, n), rq in zip(cuts, idx_reqs):
            ids = load_ids(f)
            m = n or len(ids)
            if rq["tokens"] != m:
                break
            out.append((f.split(".")[0], ids[n] if n and n < len(ids) else None))
        else:
            return out
    raise SystemExit(f"index.json has {len(idx_reqs)} requests that match neither long40 nor long80b")


def load_pfy(roots: list[pathlib.Path], ref: str, arms: list[str], a) -> Arms:
    out = Arms()
    cols = {x: {"nll": [], "kl": [], "flip": []} for x in [ref] + arms}
    blocks, bid = [], {}

    def logp(d, i):
        x = np.fromfile(d / f"first.{i}", dtype=np.float32).astype(np.float64)
        x -= x.max()
        return x - np.log(np.exp(x).sum())
    for root in roots:
        idx = json.loads((root / ref / "index.json").read_text())["requests"]
        nxt = pfy_next(idx)
        for i, rq in enumerate(idx):
            if rq["tokens"] <= 1000 or not all((root / x / f"first.{i}").exists() for x in [ref] + arms):
                continue
            lr = logp(root / ref, i)
            pr = np.exp(lr)
            tg = nxt[i][1]
            cols[ref]["nll"].append(-lr[tg] if tg is not None else np.nan)
            for x in arms:
                la = logp(root / x, i)
                cols[x]["nll"].append(-la[tg] if tg is not None else np.nan)
                cols[x]["kl"].append(float((pr * (lr - la)).sum()))
                cols[x]["flip"].append(bool(lr.argmax() != la.argmax()))
            out.keys.append((f"{root.parent.name}/{rq['name']}", rq["tokens"]))
            b = (str(root), nxt[i][0]) if a.block == "text" else (str(root), i)
            blocks.append(bid.setdefault(b, len(bid)))
    out.block = np.array(blocks)
    for x in [ref] + arms:
        out.nll[x] = np.array(cols[x]["nll"], float)
        if x != ref:
            out.kl[x], out.flip[x] = np.array(cols[x]["kl"]), np.array(cols[x]["flip"], bool)
    out.note.append(f"pf_yardstick rows (one per prompt > 1,000 tokens; NLL where the text goes on), "
                    f"blocks: {'text' if a.block == 'text' else 'prompt'}")
    return out


def read_logpos(path: pathlib.Path) -> dict:
    """quant_quality.read_run: {segment: {pos: (target, logp_target, argmax, [(id, logp) x 64])}}"""
    rows = path.read_text().splitlines()
    segs = json.load(open(str(path) + ".seg.json"))["segments"]
    out = {}
    for s in segs:
        d = {}
        for line in rows[s["first_line"]:s["end_line"]]:
            f = line.split("\t")
            if len(f) < 8 + 64:
                continue
            d[int(f[0])] = (int(f[1]), float(f[2]), int(f[3]), [(int(x), float(y)) for x, y in
                                                                (z.split(":") for z in f[8:8 + 64])])
        out[s["name"]] = d
    return out


def load_logpos(root: pathlib.Path, ref: str, arms: list[str], a) -> Arms:
    runs = {x: read_logpos(root / x / "score.tsv") for x in [ref] + arms}
    out = Arms()
    cols = {x: {"nll": [], "kl": [], "flip": []} for x in [ref] + arms}
    blocks, bid = [], {}
    for name, rr in runs[ref].items():
        common = sorted(set(rr).intersection(*[set(runs[x].get(name, {})) for x in arms]))
        for q in common:
            tr, lt_r, top_r, kr = rr[q]
            cols[ref]["nll"].append(-lt_r)
            for x in arms:
                ta, lt_a, top_a, ka = runs[x][name][q]
                if ta != tr:
                    raise SystemExit(f"{x} {name} pos {q}: target differs (not the same text)")
                da = dict(ka)
                floor = min(v for _, v in ka)
                pr = [math.exp(v) for _, v in kr]
                pa = [math.exp(da.get(i, floor)) for i, _ in kr]
                sr, sa = sum(pr), sum(pa)
                cols[x]["kl"].append(sum((u / sr) * math.log((u / sr) / (w / sa)) for u, w in zip(pr, pa) if u > 0))
                cols[x]["nll"].append(-lt_a)
                cols[x]["flip"].append(top_a != top_r)
            out.keys.append((name, q))
            b = (name, (q - min(rr)) // a.block_tokens) if a.block_tokens > 0 else (name,)
            blocks.append(bid.setdefault(b, len(bid)))
    out.block = np.array(blocks)
    for x in [ref] + arms:
        out.nll[x] = np.array(cols[x]["nll"], float)
        if x != ref:
            out.kl[x], out.flip[x] = np.array(cols[x]["kl"]), np.array(cols[x]["flip"], bool)
    out.note.append(f"STRATA_LOGPOS rows (KL over the reference's top 64, as skipcheck.kl_list), blocks: "
                    f"{'segment' if a.block_tokens <= 0 else f'{a.block_tokens} positions inside a segment'}")
    return out


def load_rows(path: pathlib.Path, ref: str, arms: list[str], a) -> Arms:
    """a --rows-out table back (no head, no engine files): blocks recomputed from --block, every --stride-th position
    of each text kept (a dump table's positions are rows; stride 2 on an all:8 table = every 16th row)"""
    lines = path.read_text().splitlines()
    hdr = lines[0].split("\t")
    col = {h: i for i, h in enumerate(hdr)}
    for x in arms:
        if f"nll_{x}" not in col:
            raise SystemExit(f"{path}: no arm {x} (has {', '.join(h[4:] for h in hdr if h.startswith('nll_'))})")
    out = Arms()
    cols = {x: {"nll": [], "kl": [], "flip": []} for x in [ref] + arms}
    seen, blocks, bid, first = {}, [], {}, {}
    for line in lines[1:]:
        f = line.split("\t")
        t, pos = f[1], int(f[2])
        k = seen.get(t, 0)
        seen[t] = k + 1
        if k % a.stride:
            continue
        first.setdefault(t, pos)
        if pos < a.min_pos:
            continue
        out.keys.append((t, pos))
        b = (t,) if a.block_tokens <= 0 else (t, (pos - (first[t] if a.rows_kind == "logpos" else 0)) // a.block_tokens)
        blocks.append(bid.setdefault(b, len(bid)))
        cols[ref]["nll"].append(float(f[col[f"nll_{ref}"]]))
        for x in arms:
            cols[x]["nll"].append(float(f[col[f"nll_{x}"]]))
            cols[x]["kl"].append(float(f[col[f"kl_{x}"]]))
            cols[x]["flip"].append(float(f[col[f"flip_{x}"]]) > 0.5)
    out.block = np.array(blocks)
    for x in [ref] + arms:
        out.nll[x] = np.array(cols[x]["nll"], float)
        if x != ref:
            out.kl[x], out.flip[x] = np.array(cols[x]["kl"]), np.array(cols[x]["flip"], bool)
    out.note.append(f"rows table {path.name}, every {a.stride}th stored position, blocks: "
                    f"{'text' if a.block_tokens <= 0 else f'{a.block_tokens}'}")
    return out


# ================================================================================================ the statistics
def boot_counts(nb: int, B: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.multinomial(nb, np.full(nb, 1.0 / nb), size=B).astype(np.float64)     # (B, nb)


def analyse(A: Arms, ref: str, refs: list[str], cands: list[str], B: int = 10000, seed: int = 20261104,
            se_cap: float = 0.01, floor: float = 0.0) -> dict:
    arms = refs + cands
    res = {"ref": ref, "refs": refs, "cands": cands, "note": A.note, "tol": TOL, "boot": B}
    # ---- KL metrics (kernel_rule3 form) on the positions where KL is defined
    kl = {}
    for x in arms:
        k = A.kl[x]
        ok = np.isfinite(k)
        k = k[ok]
        kl[x] = {"n": int(k.size), "mean": float(k.mean()), "p90": float(np.percentile(k, 90)),
                 "high": int((k > KL_HIGH).sum()), "max": float(k.max()), "flips": int(A.flip[x][ok].sum())}
    bnd = {"mean": TOL * max(kl[x]["mean"] for x in refs), "p90": TOL * max(kl[x]["p90"] for x in refs),
           "high": max(kl[x]["high"] for x in refs) + 1, "flips": TOL * max(kl[x]["flips"] for x in refs)}
    # ---- NLL: positions scored in every arm
    m = np.isfinite(A.nll[ref])
    for x in arms:
        m &= np.isfinite(A.nll[x])
    nll_ref = A.nll[ref][m]
    blk = A.block[m]
    ub, inv = np.unique(blk, return_inverse=True)
    nb = len(ub)
    nblk = np.bincount(inv, minlength=nb).astype(np.float64)
    C = boot_counts(nb, B, seed)
    den = C @ nblk
    d, dboot, diff = {}, {}, {}
    for x in arms:
        df = A.nll[x][m] - nll_ref
        diff[x] = df
        d[x] = float(df.mean())
        dboot[x] = (C @ np.bincount(inv, weights=df, minlength=nb)) / den
    # per-position spread and the design effect (block variance / iid variance)
    nll = {"n": int(m.sum()), "blocks": int(nb), "base": float(nll_ref.mean()), "arms": {}}
    for x in arms:
        sd = float(diff[x].std(ddof=1)) if diff[x].size > 1 else float("nan")
        se = float(dboot[x].std(ddof=1))
        nll["arms"][x] = {"d": d[x], "lo": float(np.percentile(dboot[x], 2.5)), "hi": float(np.percentile(dboot[x], 97.5)),
                          "se": se, "sd_pos": sd, "mean_abs": float(np.abs(diff[x]).mean()),
                          "frac_gt05": float((np.abs(diff[x]) > 0.5).mean()), "frac_exact0": float((diff[x] == 0).mean()),
                          "deff": float((se / (sd / math.sqrt(diff[x].size))) ** 2) if sd > 0 else float("nan")}
    allow = TOL * max(abs(d[x]) for x in refs)
    allow_b = TOL * np.max(np.abs(np.stack([dboot[x] for x in refs])), axis=0)
    nll["bound_rule3"] = allow
    verdicts = {}
    for x in cands:
        S = d[x] - max(allow, floor)
        Sb = dboot[x] - np.maximum(allow_b, floor)
        q05, q95 = float(np.percentile(Sb, 5)), float(np.percentile(Sb, 95))
        se_c = nll["arms"][x]["se"]
        # the proposed rule (PLAN.md): Karl's 10-26 spread bound plus a one-sided 95 % noise margin on the candidate's
        # own distance - FAIL when d_cand > 1.10 x max |d_R| + 1.645 se(d_cand); a rounding-level candidate fails <= 5 %
        # of the time at any number of positions (the point rule: ~15 %), a loss of 5 se over the bound is caught ~99 %
        if S > Z_ONE_SIDED * se_c:
            ci = "FAIL"
        elif se_c > se_cap:
            ci = "UNDERPOWERED"              # not beyond the bound, but too few positions to see a 5 x se_cap loss
        else:
            ci = "PASS"
        fails = [w for w, b in (("mean", kl[x]["mean"] > bnd["mean"]), ("p90", kl[x]["p90"] > bnd["p90"]),
                                ("KL>1 rows", kl[x]["high"] > bnd["high"]), ("top-1", kl[x]["flips"] > bnd["flips"])) if b]
        verdicts[x] = {"S": S, "S_q05": q05, "S_q95": q95, "z": S / se_c if se_c > 0 else float("nan"),
                       "margin": Z_ONE_SIDED * se_c, "rule3": "PASS" if S <= 0 else "FAIL", "ci": ci,
                       "kl_fails": fails}
    res.update({"kl": kl, "kl_bounds": bnd, "nll": nll, "verdicts": verdicts})
    return res


def report(res: dict) -> str:
    L = []
    nl, kb = res["nll"], res["kl_bounds"]
    L.append(f"reference {res['ref']}; rounding references {', '.join(res['refs'])}; {nl['n']} NLL positions in "
             f"{nl['blocks']} blocks ({'; '.join(res['note'])}); bootstrap {res['boot']} replicates")
    L.append(f"KL bounds (rule3 form): mean <= {kb['mean']:.6f}, p90 <= {kb['p90']:.6f}, rows KL > 1 <= {kb['high']}, "
             f"changed top-1 <= {kb['flips']:.1f}")
    L.append(f"NLL of {res['ref']} on these positions {nl['base']:.4f}; rule3 bound (1.10 x the larger reference "
             f"distance) {nl['bound_rule3']:.4f}")
    L.append(f"{'arm':14s} {'n':>6s} {'KL mean':>9s} {'p90':>9s} {'>1':>4s} {'top1':>6s} | {'NLL d':>8s} "
             f"{'95% CI':>19s} {'se':>7s} {'sd/pos':>6s} {'|d|>.5':>6s} {'deff':>5s}")
    for x in res["refs"] + res["cands"]:
        k, q = res["kl"][x], nl["arms"][x]
        L.append(f"{x:14s} {k['n']:6d} {k['mean']:9.6f} {k['p90']:9.6f} {k['high']:4d} {k['flips']:6d} | {q['d']:+8.4f} "
                 f"[{q['lo']:+8.4f},{q['hi']:+8.4f}] {q['se']:7.4f} {q['sd_pos']:6.3f} {q['frac_gt05']:6.3f} {q['deff']:5.1f}")
    for x in res["cands"]:
        v = res["verdicts"][x]
        z = f"{v['z']:+.1f} se" if math.isfinite(v["z"]) else "identical rows, se 0"
        L.append(f"  {x}: NLL excess over the spread bound S = {v['S']:+.4f} (= {z}; bootstrap 90% "
                 f"{v['S_q05']:+.4f} .. {v['S_q95']:+.4f}; noise margin {v['margin']:.4f}) -> rule3 {v['rule3']}, "
                 f"proposed rule {v['ci']}; KL checks "
                 f"{'PASS' if not v['kl_fails'] else 'FAIL (' + ', '.join(v['kl_fails']) + ')'}")
    return "\n".join(L)


def cmd_compare(a) -> int:
    refs, cands = a.refs.split(","), [c for c in a.cands.split(",") if c]
    roots = [pathlib.Path(r) for r in a.root]
    fmt = a.format
    if fmt == "auto" and a.from_rows:
        fmt = "dump"
    if fmt == "auto":
        r0 = roots[0] / a.ref
        fmt = "logpos" if (r0 / "score.tsv").exists() else "dump" if \
            "rows" in json.loads((r0 / "index.json").read_text()) else "pfy"
    a.block_tokens = -1 if a.block in ("text", "segment", "prompt") else int(a.block)
    if a.from_rows:
        a.rows_kind = fmt
        A = load_rows(pathlib.Path(a.from_rows), a.ref, refs + cands, a)
    elif fmt == "pfy":
        A = load_pfy(roots, a.ref, refs + cands, a)
    elif fmt == "logpos":
        A = load_logpos(roots[0], a.ref, refs + cands, a)
    else:
        A = load_dump(roots[0], a.ref, refs + cands, a)
    res = analyse(A, a.ref, refs, cands, a.boot, a.seed, a.se_cap, a.floor)
    res["format"], res["roots"] = fmt, [str(r) for r in roots]
    print(report(res))
    if a.block_scan and fmt != "pfy":
        res["block_scan"] = {}
        keep = A.block
        for spec in a.block_scan.split(","):
            bt = -1 if spec in ("text", "segment") else int(spec)
            first = {}
            for t, p in A.keys:
                first.setdefault(t, p)
            ids = {}
            A.block = np.array([ids.setdefault((t,) if bt <= 0 else (t, (p - (first[t] if fmt == "logpos" else 0)) // bt),
                                               len(ids)) for t, p in A.keys])
            r2 = analyse(A, a.ref, refs, cands, min(a.boot, 4000), a.seed, a.se_cap, a.floor)
            res["block_scan"][spec] = {x: r2["nll"]["arms"][x]["se"] for x in refs + cands}
            print(f"  blocks {spec:>5s} ({r2['nll']['blocks']:4d}): se " + "  ".join(
                f"{x} {r2['nll']['arms'][x]['se']:.4f}" for x in refs + cands))
        A.block = keep
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=1))
    if a.rows_out:
        with open(a.rows_out, "w") as f:   # (pfy: KL rows without a next token have nll nan)
            f.write("\t".join(["block", "text", "pos", f"nll_{a.ref}"] + [f"{h}_{x}" for x in refs + cands
                                                                        for h in ("nll", "kl", "flip")]) + "\n")
            for i, (t, p) in enumerate(A.keys):
                f.write("\t".join([str(A.block[i]), t, str(p), f"{A.nll[a.ref][i]:.6f}"] +
                                  [f"{v:.6g}" for x in refs + cands for v in (A.nll[x][i], A.kl[x][i], float(A.flip[x][i]))]) + "\n")
    return 1 if any(v["ci"] == "FAIL" for v in res["verdicts"].values()) else 0


# ================================================================================================ validate
def validation_pairs(d: pathlib.Path) -> list:
    """per check request: (name, its window row first.<i>, the full read's dumped row at the same position c - 1, the
    text's token c); None for the files / row when missing"""
    idx = json.loads((d / "index.json").read_text())["requests"]
    out = []
    for i, r in enumerate(idx):
        if r["kind"] != "check":
            continue
        full = next((q for q in idx if q["kind"] == "text" and q["file"] == r["file"] and q.get("rows")), None)
        p = r["cut"] - 1
        row = None
        if full is not None:
            pos, R = rows_of(d, full)
            j = np.nonzero(pos == p)[0]
            row = np.asarray(R[j[0]], np.float32) if len(j) else None
        fw = d / f"first.{i}"
        out.append((r["name"], fw if fw.exists() else None, row, load_ids(r["file"])[r["cut"]]))
    return out


def cmd_validate(a) -> int:
    d = pathlib.Path(a.outdir)
    head = Head()
    rows = []
    for name, fw, row, tg in validation_pairs(d):
        if fw is None or row is None:
            rows.append((name, None))
            continue
        lw = np.fromfile(fw, dtype=np.float32).astype(np.float64)
        lw -= lw.max()
        lw -= np.log(np.exp(lw).sum())
        lh = head.logp(row[None, :])[0]
        r = {"name": name}
        kl = float((np.exp(lw) * (lw - lh)).sum())
        rows.append((r["name"], {"kl": kl, "top1_same": bool(lw.argmax() == lh.argmax()), "nll_window": float(-lw[tg]),
                                 "nll_head": float(-lh[tg])}))
    ok = [v for _, v in rows if v]
    for n, v in rows:
        print(f"{n:32s} " + ("no data" if v is None else f"KL(window || offline head) {v['kl']:.5f}  top-1 "
                                                         f"{'same' if v['top1_same'] else 'DIFFERS'}  NLL window {v['nll_window']:.4f} head {v['nll_head']:.4f}"))
    good = bool(ok) and len(ok) == len(rows) and np.mean([v["kl"] for v in ok]) <= a.kl_mean and \
        all(v["kl"] <= a.kl_max for v in ok)
    print(f"offline head {'AGREES' if good else 'DOES NOT AGREE'} with the engine's window rows (mean KL <= {a.kl_mean}, "
          f"each <= {a.kl_max}; rounding level between the batched and the window path is ~0.01-0.02)")
    return 0 if good else 1


# ================================================================================================ selftest
def selftest(a) -> int:
    global D
    rng = np.random.default_rng(7)
    fails = []

    def check(name, ok, detail=""):
        print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")
        if not ok:
            fails.append(name)
    # 1 BF16 rounding (ties to even) against the C++ rule, bit for bit
    x = np.concatenate([rng.standard_normal(5000).astype(np.float32),
                        np.array([1.0 + 2 ** -8, 1.0 + 3 * 2 ** -8, -2.5, 0.0], np.float32)])
    want = []
    for v in x:
        i = int(np.array([v], np.float32).view(np.uint32)[0])
        i = (i + ((i >> 16) & 1) + 0x7FFF) & 0xFFFF0000
        want.append(np.array([i], np.uint32).view(np.float32)[0])
    check("bf16 rounding = gr_parity.cpp to_bf16", np.array_equal(bf16_round(x), np.array(want, np.float32)))
    # 2 Q6_K: the vectorised decoder against the scalar transcription of ggml's loop
    blk = rng.integers(0, 256, size=(40, 210), dtype=np.uint8)
    blk[:, 208:210] = np.frombuffer(rng.uniform(-3e-5, 3e-5, 40).astype(np.float16).tobytes(), np.uint8).reshape(40, 2)
    vec = dequant_q6_k(blk)
    ref = np.array([dequant_q6_k_scalar(bytes(b)) for b in blk], np.float32)
    check("Q6_K decoder = ggml dequantize_row_q6_K (40 random blocks)", np.array_equal(vec, ref),
          f"max |diff| {np.abs(vec - ref).max():.3g}")
    # 2b the real head tensor: its first 64 rows through both decoders; the mixer's gammas as the engine reads them
    try:
        sys.path.insert(0, str(GGUF_TOOLS))
        import gguf_reader as G
        g = G.GGUFFile(GGUF)
        t = {x.name: x for x in g.tensors}
        with open(GGUF, "rb") as f:
            f.seek(g.data_start + t["output.weight"].offset)
            raw = np.frombuffer(f.read(64 * 10 * 210), np.uint8).reshape(640, 210)
            f.seek(g.data_start + t["output_hc_norm.weight"].offset)
            gam = np.frombuffer(f.read(D * 4), np.float32)
        vec = dequant_q6_k(raw)
        ref = np.array([dequant_q6_k_scalar(bytes(b)) for b in raw[:40]], np.float32)
        w = vec.reshape(64, N_EMBD)
        check("real output.weight rows 0-63: decoders agree, values sane", np.array_equal(vec[:40], ref) and
              0.005 < float(w.std()) < 0.2 and abs(float(w.mean())) < 0.01, f"std {w.std():.4f}, mean {w.mean():+.5f}")
        check("real output_hc_norm: positive gammas (stored as 1 + w; pack copy byte-identical, 11-04)",
              float(gam.min()) > 0, f"mean {gam.mean():.3f}, min {gam.min():.3f}")
    except OSError as e:
        print(f"skip real-weights check ({e})")
    # 3 the mixer against gr_parity.cpp's reference, transcribed loop by loop
    n, hc, lr = 32, 4, 8
    wn = rng.uniform(0.5, 4.0, hc * n).astype(np.float32)
    wd = bf16_round(rng.standard_normal((lr, hc * n)).astype(np.float32) * 0.05)
    wu = bf16_round(rng.standard_normal((hc * n, lr)).astype(np.float32) * 0.2)
    Wv = rng.standard_normal((50, n)).astype(np.float32)
    h = Head(weights=(wn, wd, wu, Wv, n, hc, lr))
    R = rng.standard_normal((3, hc * n)).astype(np.float32) * 3
    mv = h.mix(R)
    ms = np.array([mix_scalar(R[t], wn, wd, wu, n, hc, lr) for t in range(3)], np.float64)
    rel = float(np.abs(mv - ms).max() / np.abs(ms).mean())
    check("mixer = gr_read's reference (per-stream norm, /hc inside silu, sigmoid gate, mean)", rel < 1e-5, f"rel {rel:.2e}")
    # the rival readings must differ materially (the test can tell them apart)
    alt = (np.asarray(R, np.float32).reshape(3, hc, n) * h.w_norm.reshape(1, hc, n)).mean(axis=1)
    check("  (a plain stream mean differs from it)", float(np.abs(alt - mv).max()) > 1e-2)
    # 4 the statistics: rounding-level arms (iid heavy-tailed paired noise, correlated inside texts) - false-fail rates
    def synth(shift=0.0, nb=150, per=26, rho_blk=0.15):
        A = Arms()
        A.block = np.repeat(np.arange(nb), per)
        N = nb * per
        A.keys = [(f"t{b}", i) for b in range(nb) for i in range(per)]
        base = rng.exponential(1.0, N)
        A.nll["ref"] = base
        for x in ("R1", "R2", "cand"):
            e = rng.standard_t(3, N) * 0.6 + np.repeat(rng.standard_normal(nb) * rho_blk, per)
            A.nll[x] = base + e + (shift if x == "cand" else 0.0)
            A.kl[x] = np.abs(rng.normal(0.01, 0.005, N))
            A.flip[x] = rng.random(N) < 0.01
        A.note = ["synthetic"]
        return A
    trials = 60 if a.quick else 200
    r3 = ci = 0
    for t in range(trials):
        res = analyse(synth(), "ref", ["R1", "R2"], ["cand"], B=600, seed=t, se_cap=1.0)
        r3 += res["verdicts"]["cand"]["rule3"] == "FAIL"
        ci += res["verdicts"]["cand"]["ci"] == "FAIL"
    check(f"H0 (candidate = one more rounding variant): rule3 false-fail {r3}/{trials} (expected ~15 %), proposed "
          f"CI rule {ci}/{trials} (expected <= 5 %)", ci <= 0.08 * trials and r3 >= 0.05 * trials)
    res = analyse(synth(), "ref", ["R1", "R2"], ["cand"], B=600, seed=1, se_cap=1.0)
    se = res["nll"]["arms"]["cand"]["se"]
    for k, need in ((3, 0.3), (5, 0.9)):
        det = sum(analyse(synth(shift=k * se), "ref", ["R1", "R2"], ["cand"], B=600, seed=100 + t, se_cap=1.0)
                  ["verdicts"]["cand"]["ci"] == "FAIL" for t in range(trials // 2))
        check(f"H1 (candidate worse by {k} se = {k * se:.3f} nats): the proposed rule catches {det}/{trials // 2}",
              det >= need * (trials // 2))
    # 5 the dump pipeline end to end on synthetic dumps (tiny head): an identical arm gives exactly 0
    scr = SC / "work/r23/nll-many/scratch/selftest-root"
    if scr.exists():
        shutil.rmtree(scr)
    n2, V = 64, 300
    wn2 = rng.uniform(0.5, 4.0, HC * n2).astype(np.float32)
    wd2 = bf16_round(rng.standard_normal((16, HC * n2)).astype(np.float32) * 0.05)
    wu2 = bf16_round(rng.standard_normal((HC * n2, 16)).astype(np.float32) * 0.2)
    h2 = Head(weights=(wn2, wd2, wu2, rng.standard_normal((V, n2)).astype(np.float32) * 0.5, n2, HC, 16))
    D_saved, D = D, HC * n2
    try:
        txt = SETS["long8"][7]            # rep9k: a real token file (targets), positions every 64
        L = len(load_ids(txt))
        pos = np.arange(0, L - 1, EVERY, dtype=np.int64)
        R0 = rng.standard_normal((len(pos), D)).astype(np.float32)
        arms = {"ref": R0, "same": R0.copy(), "R1": R0 + 0.01 * rng.standard_normal(R0.shape).astype(np.float32),
                "R2": R0 + 0.01 * rng.standard_normal(R0.shape).astype(np.float32),
                "noisy": R0 + 0.3 * rng.standard_normal(R0.shape).astype(np.float32)}
        rec_t = np.dtype([("pos", "<i8"), ("r", "<f4", (D,))])
        for name, Rr in arms.items():
            dd = scr / name
            dd.mkdir(parents=True)
            rec = np.zeros(len(pos), rec_t)
            rec["pos"], rec["r"] = pos, Rr
            rec.tofile(dd / "r.0")
            (dd / "index.json").write_text(json.dumps({"rows": "dumpr", "requests": [
                {"name": f"rep9k-{L}", "file": txt, "cut": L, "kind": "text", "rows": len(pos), "dump": "r.0"}]}))
        ns = argparse.Namespace(min_pos=1024, stride=1, chunk=32, block_tokens=2048)
        ids = load_ids(txt)
        # targets beyond the tiny vocabulary: the head is folded so they index it (the pipeline needs consistent ids)
        A = load_dump(scr, "ref", ["same", "R1", "R2", "noisy"], ns, head=_FoldHead(h2, V))
        res = analyse(A, "ref", ["R1", "R2"], ["same", "noisy"], B=500)
        q = res["nll"]["arms"]
        check("dump pipeline: an identical arm has d = 0, KL = 0, 0 changed picks",
              q["same"]["d"] == 0 and res["kl"]["same"]["mean"] == 0 and res["kl"]["same"]["flips"] == 0)
        check("dump pipeline: a perturbed arm has KL > the rounding references'",
              res["kl"]["noisy"]["mean"] > 5 * res["kl"]["R1"]["mean"] > 0, f"{res['kl']['noisy']['mean']:.4f} vs "
                                                                             f"{res['kl']['R1']['mean']:.6f}")
        want_n = int(((pos >= 1024) & (pos + 1 < len(ids))).sum())
        check(f"dump pipeline: {want_n} positions (every 64th row from 1,024)", res["nll"]["n"] == want_n)
        tsv = scr / "rows.tsv"
        with open(tsv, "w") as f:
            f.write("\t".join(["block", "text", "pos", "nll_ref"] + [f"{h}_{x}" for x in ("same", "R1", "R2", "noisy")
                                                                      for h in ("nll", "kl", "flip")]) + "\n")
            for i, (t, p_) in enumerate(A.keys):
                f.write("\t".join([str(A.block[i]), t, str(p_), f"{A.nll['ref'][i]:.6f}"] + [f"{v:.6g}" for x in
                        ("same", "R1", "R2", "noisy") for v in (A.nll[x][i], A.kl[x][i], float(A.flip[x][i]))]) + "\n")
        B2 = load_rows(tsv, "ref", ["same", "R1", "R2", "noisy"], argparse.Namespace(stride=1, min_pos=1024,
                                                                                      block_tokens=2048, rows_kind="dump"))
        r2 = analyse(B2, "ref", ["R1", "R2"], ["same", "noisy"], B=500)
        check("rows table round trip: the same positions, blocks and distances (6 digits)", r2["nll"]["n"] ==
              res["nll"]["n"] and r2["nll"]["blocks"] == res["nll"]["blocks"] and
              abs(r2["nll"]["arms"]["noisy"]["d"] - res["nll"]["arms"]["noisy"]["d"]) < 1e-5)
    finally:
        D = D_saved
        shutil.rmtree(scr, ignore_errors=True)
    # 6 the engine driver (`run`) against mock_engine.py: protocol, the hooks' files, row checks, index.json, the
    #   validation pairing; a truncated dump must be reported
    scr = SC / "work/r23/nll-many/scratch/selftest-run"
    shutil.rmtree(scr, ignore_errors=True)
    scr.mkdir(parents=True)
    cfgp = scr / "mock.json"
    cfgp.write_text(json.dumps({"exe": str(SC / "work/r23/nll-many/mock_engine.py"), "args": ["--pack", "none"],
                                "cwd": str(scr), "env": {}}))
    mock = module("mock_engine", SC / "work/r23/nll-many/mock_engine.py")
    ids = load_ids("pp4k.tokens")
    try:
        for rows_mode, K in (("dumpr", EVERY), ("all:8", 8)):
            out = scr / rows_mode.replace(":", "")
            ns = argparse.Namespace(config=str(cfgp), outdir=str(out), set="mock", rows=rows_mode, env=None, kv="fp16",
                                    pcie_frac=None, min_free_gb=0, max_len=32768)
            rc = cmd_run(ns)
            idx = json.loads((out / "index.json").read_text())
            text = idx["requests"][0]
            pos, R = rows_of(out, text)
            want = np.arange(0, len(ids) - 1, K)
            exact = all(np.array_equal(np.asarray(R[j]), mock.row(int(p_), ids[int(p_)]) if rows_mode == "dumpr" else
                                       bf16_round(mock.row(int(p_), ids[int(p_)]))) for j, p_ in
                        list(enumerate(pos))[:3] + [(len(pos) - 1, pos[-1])])
            pairs = validation_pairs(out)
            pr_ok = len(pairs) == 1 and pairs[0][1] is not None and pairs[0][3] == ids[2049] and \
                np.array_equal(pairs[0][2], np.asarray(R[int(np.nonzero(pos == 2048)[0][0])], np.float32))
            check(f"run ({rows_mode}) on the mock engine: rc 0, {len(pos)} rows at 0, {K}, ..., the rows' values, "
                  f"the check pairing", rc == 0 and not idx["problems"] and np.array_equal(pos, want) and exact and pr_ok,
                  f"rc {rc}, problems {idx['problems']}")
        os.environ["MOCK_TRUNCATE"] = "1"
        out = scr / "trunc"
        rc = cmd_run(argparse.Namespace(config=str(cfgp), outdir=str(out), set="mock", rows="dumpr", env=None,
                                        kv="fp16", pcie_frac=None, min_free_gb=0, max_len=32768))
        check("run: a dump that lost its first chunk is reported (rc 1)", rc == 1 and
              json.loads((out / "index.json").read_text())["problems"])
    finally:
        os.environ.pop("MOCK_TRUNCATE", None)
        shutil.rmtree(scr, ignore_errors=True)
    print("SELFTEST " + ("PASS" if not fails else f"FAIL ({', '.join(fails)})"))
    return 1 if fails else 0


class _FoldHead:
    """selftest only: a tiny head whose vocabulary is folded so real token ids index it"""

    def __init__(self, h, V):
        self.h, self.V = h, V

    def logits(self, R):
        rep = int(math.ceil(250000 / self.V))
        return np.ascontiguousarray(np.tile(self.h.logits(R), (1, rep))[:, :250000])   # V tokens copied


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threads", dest="threads_top", default="1", help="BLAS threads (read before numpy loads)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("config"); r.add_argument("outdir")
    r.add_argument("--set", default="long11", choices=sorted(SETS))
    r.add_argument("--rows", default="dumpr", help="dumpr (every 64th row, fp32) or all:K (every K-th row, BF16)")
    r.add_argument("--env", action="append")
    r.add_argument("--kv", default="fp16", choices=["fp16", "int8"])
    r.add_argument("--pcie-frac", default=None)
    r.add_argument("--min-free-gb", type=float, default=16)
    r.add_argument("--max-len", type=int, default=32768)
    v = sub.add_parser("validate")
    v.add_argument("outdir")
    v.add_argument("--kl-mean", type=float, default=0.05)
    v.add_argument("--kl-max", type=float, default=0.5)
    c = sub.add_parser("compare")
    c.add_argument("root", nargs="+")
    c.add_argument("--ref", default="ref")
    c.add_argument("--refs", default="unfused,cpushare")
    c.add_argument("--cands", default="")
    c.add_argument("--format", default="auto", choices=["auto", "dump", "pfy", "logpos"])
    c.add_argument("--block", default="2048", help="dump: tokens per block (or 'text'); pfy: prompt|text; logpos: "
                                                   "segment or N positions")
    c.add_argument("--min-pos", type=int, default=1024)
    c.add_argument("--stride", type=int, default=1, help="keep every N-th dumped row")
    c.add_argument("--chunk", type=int, default=128, help="rows per head GEMM")
    c.add_argument("--boot", type=int, default=10000)
    c.add_argument("--seed", type=int, default=20261104)
    c.add_argument("--se-cap", type=float, default=0.01, help="the proposed rule's power floor: the bootstrap se of "
                   "the candidate's distance must be <= this (nats; 5 x it is the loss the check is sure to catch)")
    c.add_argument("--block-scan", default="", help="also print each arm's se at these block sizes, e.g. "
                   "1024,2048,4096,8192,text (dump / logpos)")
    c.add_argument("--floor", type=float, default=0.0, help="a fixed NLL tolerance under the spread bound (nats)")
    c.add_argument("--json"); c.add_argument("--rows-out")
    c.add_argument("--from-rows", help="re-analyse a --rows-out table (ROOT is then only a label); --stride, --block, "
                                       "--min-pos apply")
    s_ = sub.add_parser("selftest")
    s_.add_argument("--quick", action="store_true")
    for p_ in (r, v, c, s_):
        p_.add_argument("--threads", default=None, help="BLAS threads (read before numpy loads)")
    a = ap.parse_args()
    if a.cmd == "compare" and a.format == "pfy" and a.block == "2048" and not a.from_rows:
        a.block = "prompt"
    if a.cmd == "compare" and a.format == "logpos" and a.block == "2048":
        a.block = "segment"
    return {"run": cmd_run, "validate": cmd_validate, "compare": cmd_compare, "selftest": selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
