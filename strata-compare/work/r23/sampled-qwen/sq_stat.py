#!/usr/bin/env python3
"""sq_stat.py - the statistic and the rule of the Qwen served-mode sampled-distribution test (work/r23/sampled-qwen/).
Written 2026-11-09 at the desk; never run on real data. No GPU, no engine, no network: this module only reads result
files and the test's spec (JSON). The CLI is sq.py; the request driver sq_client.py.

The test is DeepSeek gap D2's (results/ds41/C-SAMPLED-TEST-PLAN.md sections 2.4-2.6, Karl 11-08 FIXED) carried over to
the Qwen engine (Strata serving Qwen3.8-Flash-Next, or any later Qwen model whose tokenizer / template / vocabulary the
arm configs name). Every sampled answer of a served arm (server.py with STRATA_DEBUG=1 prints its generated ids) is
scored teacher-forced by one reference engine run (the scorer, the same for every arm). For each generated token x_t
the scorer's row gives the top-64 log-probabilities; the sampler's chain (src/kernels/cuda/sampler.cu: top_k 20 ->
top_p 0.95 over the 20 -> min_p 0.05 against the top -> temperature 1.0, ties to the lower id) rebuilt from them gives
p~_t. Features f(x) = (x is p~'s top-1, x is p~'s rank 2, log p(x) over the whole vocabulary); d_t = f(x_t) - E f.
If an arm draws from p~, sum d_t is a martingale. Per arm and prompt: mean m and its variance V (empirical); the arm's
vector: the equal-weight mean over the prompts. D2(A, B) = (m_A - m_B)' (V_A + V_B)^-1 (m_A - m_B), chi-square 3 df.

THE MATH IS sampled.py's, COPIED VERBATIM (not imported, so a later edit there cannot change this rule): the functions
in COPIED and the constants in CONSTS, from work/ds41/gate/sampled/sampled.py at sha256 DS_SAMPLED_SHA (the 11-08 file
gap D2 ran). math_identity() compares them by AST with that file while it is unchanged (sq.py selftest).

New here (not in sampled.py): the arms come from a spec (configs + env changes, any number of candidates), the
"exercise" checks (log patterns per arm, e.g. STRATA_ADAPT_FETCH really on) replace D2's drafting-share rule, the
read-back check (a verify start's log), and the overall rule per candidate.
"""
import ast
import copy
import hashlib
import json
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DS_SAMPLED = "/home/USER/ai-speed-testing/strata-compare/work/ds41/gate/sampled/sampled.py"
DS_SAMPLED_SHA = "368b45e50b8edfa120f262b3a48c9f2e8919f7eb690892252d7cbc20ad8bf4ef"   # the file of gap D2 (11-08 / 11-09)
COPIED = ("_gammainc_p", "chi2_sf", "chi2_ppf", "ncx2_sf", "lam_for_power", "kept", "token_terms", "inv3", "quad", "Acc",
          "combine", "d2", "parse_row")
CONSTS = ("SAMPLING", "K_FEAT", "ALPHA", "POWER", "DELTA_STAR", "N_MIN", "SAMPLES_MIN", "SANITY_D2", "MAX_INVALID")

# ---- the rule's constants: sampled.py's, Karl 11-08 FIXED (the same names and values; checked by math_identity)
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.05}
K_FEAT = 3                      # features: top-1, rank 2, log p
ALPHA = 0.01                    # the sampling-noise bound: chi2(3) 99th percentile
POWER = 0.80
DELTA_STAR = 0.02               # the smallest top-1 shift the test must see with POWER (else NOT DECIDED)
N_MIN = 4000                    # valid scored generated tokens per arm, at least
SAMPLES_MIN = 3                 # valid samples per prompt and arm, at least
SANITY_D2 = 100.0               # R1 vs the scorer: above this the scorer does not track the served reference
MAX_INVALID = 0.10              # at most this share of an arm's samples may be invalid


# ================================================================ COPIED VERBATIM from sampled.py (do not edit)
# ---- chi-square without scipy
def _gammainc_p(a, x):
    """regularized lower incomplete gamma P(a, x)"""
    if x <= 0:
        return 0.0
    if x < a + 1.0:   # series
        s = t = 1.0 / a
        n = a
        for _ in range(10000):
            n += 1.0
            t *= x / n
            s += t
            if abs(t) < abs(s) * 1e-15:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction (Lentz) for Q, then P = 1 - Q
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-15:
            break
    return 1.0 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x, k):
    return 1.0 - _gammainc_p(k / 2.0, x / 2.0)


def chi2_ppf(q, k):
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 1.0 - chi2_sf(mid, k) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def ncx2_sf(x, k, lam):
    """P(noncentral chi2(k, lam) > x): the Poisson(lam / 2) mixture of central chi-squares"""
    if lam <= 0:
        return chi2_sf(x, k)
    h = lam / 2.0
    j0 = int(h)
    tot = 0.0

    def w(j):
        return math.exp(-h + j * math.log(h) - math.lgamma(j + 1))

    j = j0
    while True:                      # upward from the Poisson mode
        wj = w(j)
        tot += wj * chi2_sf(x, k + 2 * j)
        if j > j0 + 10 and wj < 1e-17:
            break
        j += 1
    j = j0 - 1
    while j >= 0:                    # and downward
        wj = w(j)
        tot += wj * chi2_sf(x, k + 2 * j)
        if j < j0 - 10 and wj < 1e-17:
            break
        j -= 1
    return tot


def lam_for_power(c, k, power):
    lo, hi = 0.0, 500.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if ncx2_sf(c, k, mid) < power:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


C_BOUND = chi2_ppf(1.0 - ALPHA, K_FEAT)
LAM80 = lam_for_power(C_BOUND, K_FEAT, POWER)


# ---- the sampler's chain over a scored row (vendor/sampler.cu's order and tie rule)
def kept(top, top_k=20, top_p=0.95, min_p=0.05, temperature=1.0, min_keep=1):
    """top: [(id, logprob)] of a row (the scorer's 64). -> (ids, p, logprobs) of p~'s kept list, descending."""
    sel = sorted(top, key=lambda e: (-e[1], e[0]))
    k = top_k if 0 < top_k < 64 else 64
    sel = sel[:min(k, len(sel))]
    k = len(sel)
    lp = [e[1] for e in sel]
    mx = lp[0]
    n_keep = k
    if top_p < 1.0:
        ex = [math.exp(x - mx) for x in lp]
        s = sum(ex)
        cum, cut = 0.0, k
        for i in range(k):
            cum += ex[i] / s
            if cum >= top_p:
                cut = i + 1
                break
        if cut < min_keep:
            cut = min(min_keep, k)
        n_keep = cut
    if min_p > 0.0:
        th = lp[0] + math.log(min_p)
        for i in range(n_keep):
            if lp[i] < th:
                n_keep = i
                break
    sc = [lp[i] / temperature for i in range(n_keep)]
    smx = max(sc)
    w = [math.exp(x - smx) for x in sc]
    z = sum(w)
    return [e[0] for e in sel[:n_keep]], [x / z for x in w], lp[:n_keep]


def token_terms(top, x, lp_x, sampling=SAMPLING):
    """-> (d, s, info): d = f(x) - E f, s = the predicted covariance (3x3, rows), info: rank of x in p~ (None = outside)"""
    ids, p, lps = kept(top, sampling["top_k"], sampling["top_p"], sampling["min_p"], sampling["temperature"])
    r = ids.index(x) if x in ids else None
    f = (1.0 if r == 0 else 0.0, 1.0 if r == 1 else 0.0, lp_x)
    mu = [p[0], p[1] if len(p) > 1 else 0.0, sum(pi * li for pi, li in zip(p, lps))]
    d = [f[0] - mu[0], f[1] - mu[1], f[2] - mu[2]]
    s = [[0.0] * 3 for _ in range(3)]
    for i, (pi, li) in enumerate(zip(p, lps)):
        fi = (1.0 if i == 0 else 0.0, 1.0 if i == 1 else 0.0, li)
        for a in range(3):
            for b in range(3):
                s[a][b] += pi * (fi[a] - mu[a]) * (fi[b] - mu[b])
    return d, s, {"rank": r, "p_top": p[0], "n_keep": len(p)}


# ---- small linear algebra (3x3)
def inv3(m):
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(3)] for i, row in enumerate(m)]
    tr = sum(abs(m[i][i]) for i in range(3)) or 1.0
    for i in range(3):
        a[i][i] += 1e-12 * tr
    for c in range(3):
        piv = max(range(c, 3), key=lambda r: abs(a[r][c]))
        if abs(a[piv][c]) < 1e-300:
            raise ValueError("singular variance")
        a[c], a[piv] = a[piv], a[c]
        f = a[c][c]
        a[c] = [v / f for v in a[c]]
        for r in range(3):
            if r != c:
                g = a[r][c]
                a[r] = [vr - g * vc for vr, vc in zip(a[r], a[c])]
    return [row[3:] for row in a]


def quad(v, m):
    return sum(v[i] * m[i][j] * v[j] for i in range(3) for j in range(3))


# ---- per-arm accumulation
class Acc:
    def __init__(self):
        self.n = 0
        self.sd = [0.0] * 3
        self.sdd = [[0.0] * 3 for _ in range(3)]
        self.ss = [[0.0] * 3 for _ in range(3)]
        self.top1 = self.top1_exp = self.outside = 0.0

    def add(self, d, s, info, p_top):
        self.n += 1
        for a in range(3):
            self.sd[a] += d[a]
            for b in range(3):
                self.sdd[a][b] += d[a] * d[b]
                self.ss[a][b] += s[a][b]
        self.top1 += 1.0 if info["rank"] == 0 else 0.0
        self.top1_exp += p_top
        self.outside += 1.0 if info["rank"] is None else 0.0

    def mean_var(self):
        n = self.n
        m = [x / n for x in self.sd]
        v = [[(self.sdd[a][b] / n - m[a] * m[b]) / n for b in range(3)] for a in range(3)]
        return m, v


def combine(accs, prompts):
    """equal weight per prompt: m = mean of the prompts' m, V = sum w^2 V_q"""
    w = 1.0 / len(prompts)
    m = [0.0] * 3
    v = [[0.0] * 3 for _ in range(3)]
    for q in prompts:
        mq, vq = accs[q].mean_var()
        for a in range(3):
            m[a] += w * mq[a]
            for b in range(3):
                v[a][b] += w * w * vq[a][b]
    return m, v


def d2(ma, va, mb=None, vb=None):
    if mb is None:
        return quad(ma, inv3(va))
    diff = [x - y for x, y in zip(ma, mb)]
    return quad(diff, inv3([[va[a][b] + vb[a][b] for b in range(3)] for a in range(3)]))


def parse_row(line):
    f = line.rstrip("\n").split("\t")
    top = []
    for e in f[8:]:
        i, _, v = e.partition(":")
        top.append((int(i), float(v)))
    return int(f[0]), int(f[1]), float(f[2]), top
# ================================================================ end of the verbatim copy


def math_identity(path=DS_SAMPLED):
    """-> (status, detail). status: "identical" (sampled.py is the 11-08 file and every copied function / constant is
    the same AST), "DIFFERENT" (it is that file and something here differs: a FAIL), "changed" (sampled.py was edited
    since the copy: INFO - the copy here stays the frozen one), "absent"."""
    if not os.path.exists(path):
        return "absent", f"{path} not found (the copy here stays the frozen one)"
    raw = open(path, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()

    def defs(tree):
        out = {}
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in COPIED:
                out[n.name] = ast.dump(n)
            elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                    and n.targets[0].id in CONSTS + ("C_BOUND", "LAM80"):
                out[n.targets[0].id] = ast.dump(n.value)
        return out
    theirs = defs(ast.parse(raw))
    mine = defs(ast.parse(open(os.path.abspath(__file__), "rb").read()))
    names = list(COPIED) + list(CONSTS) + ["C_BOUND", "LAM80"]
    diff = [n for n in names if theirs.get(n) != mine.get(n)]
    if sha != DS_SAMPLED_SHA:
        return "changed", (f"sampled.py changed since the copy (sha {sha[:12]}, copied from {DS_SAMPLED_SHA[:12]}); "
                           f"{len(diff)} of {len(names)} names differ from it now; the frozen copy here is unchanged")
    if diff:
        return "DIFFERENT", f"differs from sampled.py {sha[:12]} in: {', '.join(diff)}"
    return "identical", f"{len(COPIED)} functions and {len(names) - len(COPIED)} constants = sampled.py {sha[:12]} (AST)"


# ================================================================ the spec (JSON: the arms, the plan, the checks)
ROLES = ("reference", "noise", "candidate", "verify")


def load_spec(p):
    return json.load(open(p, encoding="utf-8"))


def spec_core(spec):
    """the spec without what `derive` adds (its "resolved" block): the part the rule and its sha are made of"""
    s = copy.deepcopy(spec)
    s.pop("resolved", None)
    return s


def spec_sha(spec):
    return hashlib.sha256(json.dumps(spec_core(spec), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def role_of(spec, role):
    return [n for n, a in spec["arms"].items() if a.get("role") == role]


def ref_of(spec):
    return role_of(spec, "reference")[0]


def noise_of(spec):
    n = role_of(spec, "noise")
    return n[0] if n else None


def prompts_of(spec):
    return [p["name"] for p in spec["plan"]["prompts"]]


def arm_k(spec, name):
    return int(spec["arms"][name].get("k") or spec["plan"]["k"])


def seeds_of(spec, name):
    a = spec["arms"][name]
    return [int(a["seed_base"]) + 1000 * qi + rnd for rnd in range(arm_k(spec, name)) for qi in range(len(prompts_of(spec)))]


def check_spec(spec):
    """-> [problem]: the spec's own consistency (no file is read)"""
    bad = []
    if not spec.get("name") or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", spec["name"]):
        bad.append("name: 1-64 of [A-Za-z0-9_.-]")
    pl = spec.get("plan") or {}
    pr = pl.get("prompts") or []
    if len(pr) < 2 or len({p.get("name") for p in pr}) != len(pr):
        bad.append("plan.prompts: at least 2, distinct names")
    if pl.get("thinking") is not False:
        bad.append("plan.thinking must be false (v1: with thinking on the server writes tokens of its own - the "
                   "budget wrap-up, the close retry - and its loop recovery raises temperature / presence_penalty)")
    if not isinstance(pl.get("max_tokens"), int) or not 16 <= pl["max_tokens"] <= 4096:
        bad.append("plan.max_tokens: an integer 16..4096")
    if not isinstance(pl.get("k"), int) or not 1 <= pl["k"] <= 999:
        bad.append("plan.k: an integer 1..999")
    arms = spec.get("arms") or {}
    for role, lo, hi in (("reference", 1, 1), ("noise", 0, 1), ("candidate", 1, 16), ("verify", 0, 8)):
        n = len(role_of(spec, role))
        if not lo <= n <= hi:
            bad.append(f"{n} arm(s) of role {role} (want {lo}..{hi})")
    ranges = []
    for name, a in arms.items():
        if not re.fullmatch(r"[A-Za-z0-9]{1,16}", name):
            bad.append(f"arm {name!r}: 1-16 of [A-Za-z0-9]")
        if a.get("role") not in ROLES:
            bad.append(f"{name}: role {a.get('role')!r}")
        if bool(a.get("base")) == bool(a.get("same_as")):
            bad.append(f"{name}: exactly one of base / same_as")
        if a.get("same_as") and a["same_as"] not in arms:
            bad.append(f"{name}: same_as {a['same_as']} is not an arm")
        if not isinstance(a.get("seed_base"), int) or a["seed_base"] < 1:
            bad.append(f"{name}: seed_base a positive integer")
        else:
            k = int(a.get("k") or pl.get("k") or 1)
            if k > 999:
                bad.append(f"{name}: k {k} > 999 (seeds = base + 1000 x prompt + round)")
            ranges.append((a["seed_base"], a["seed_base"] + 1000 * len(pr), name))
        for c in a.get("exercise") or []:
            if c not in (spec.get("exercise") or {}):
                bad.append(f"{name}: exercise check {c!r} is not in spec.exercise")
        if a.get("role") == "verify":
            if a.get("verify") not in (spec.get("verify") or {}):
                bad.append(f"{name}: verify {a.get('verify')!r} is not in spec.verify")
            for c in a.get("covers") or []:
                if arms.get(c, {}).get("role") != "candidate":
                    bad.append(f"{name}: covers {c}, not a candidate")
        seen, x = {name}, a
        while x.get("same_as"):
            if x["same_as"] in seen:
                bad.append(f"{name}: a same_as loop")
                break
            seen.add(x["same_as"])
            x = arms.get(x["same_as"], {})
    ranges.sort()
    for (a0, a1, n0), (b0, b1, n1) in zip(ranges, ranges[1:]):
        if b0 < a1:
            bad.append(f"seed ranges of {n0} and {n1} overlap")
    for k, v in (spec.get("verify") or {}).items():
        for f in ("mismatch_re", "summary_re"):
            try:
                re.compile(v.get(f) or "")
            except re.error as e:
                bad.append(f"verify.{k}.{f}: {e}")
        if not v.get("mismatch_re") or not v.get("summary_re") or re.compile(v["summary_re"]).groups < 2:
            bad.append(f"verify.{k}: mismatch_re and summary_re (2 groups: read back, differ) needed")
    for k, v in (spec.get("exercise") or {}).items():
        for rx in (v.get("require") or []) + (v.get("forbid") or []) + ([v["counter"]["re"]] if v.get("counter") else []):
            try:
                re.compile(rx)
            except re.error as e:
                bad.append(f"exercise.{k}: {rx!r}: {e}")
    sc = spec.get("scorer") or {}
    if not sc.get("base") or sc.get("spec") != 2 or sc.get("topk") != 64:
        bad.append("scorer: base config, spec 2 (2-row windows) and topk 64")
    for rx in spec.get("taint") or []:
        try:
            re.compile(rx)
        except re.error as e:
            bad.append(f"taint {rx!r}: {e}")
    return bad


def arm_changes(spec, name):
    """the arm's own declared changes, as text (relative to its base or same_as arm)"""
    a = spec["arms"][name]
    out = []
    for k, v in sorted((a.get("top") or {}).items()):
        out.append(f"{k} = {v}")
    for k, v in sorted((a.get("env") or {}).items()):
        out.append(f"env {k}={v}" if v is not None else f"env {k} removed")
    for k, v in sorted((a.get("args_set") or {}).items()):
        out.append(f"arg {k} {v}")
    for k in a.get("args_drop_value") or []:
        out.append(f"arg {k} dropped")
    return out


def rule_text(spec):
    """the frozen rule of this spec (sq.py rule writes it to OUTDIR/rule.txt before any engine starts)"""
    ref, noise = ref_of(spec), noise_of(spec)
    cands, verifs = role_of(spec, "candidate"), role_of(spec, "verify")
    pr = prompts_of(spec)
    pl = spec["plan"]
    L = [f"sq.py rule - the Qwen served-mode sampled-distribution test, fixed {spec.get('fixed', '(date)')} at the desk, "
         "before any engine run.",
         f"spec {spec['name']} (sha256 {spec_sha(spec)[:16]}): {spec.get('use', '')}",
         "question: under T 1.0 / top-p 0.95 / top-k 20 / min-p 0.05 (thinking off) the candidate must not change the served "
         "output distribution beyond rounding (DeepSeek gap D2's test, Karl 11-03 / 11-08, carried over to the Qwen engine).",
         "arms (one fresh served test server each; the same request plan; own seeds):"]
    for n, a in spec["arms"].items():
        if a.get("role") == "verify":
            continue
        src = f"{a['same_as']}'s config" if a.get("same_as") else os.path.basename(a["base"]) + (
            " without the picture reader, the fallback and the guard key" if a.get("strip", True) else "")
        ch = arm_changes(spec, n)
        L.append(f"  {n} ({a['role']}) = {a.get('desc', '')}: {src}{' + ' + ', '.join(ch) if ch else ''}; "
                 f"K {arm_k(spec, n)}; seed base {a['seed_base']:,}"
                 + (f"; engine sha256 {a['exe_sha12']}..." if a.get("exe_sha12") else ""))
    L.append("  every served arm's config also carries STRATA_DEBUG=1 (server.py prints each request's generated ids; the "
             "engine binary does not read it, checked) and an engine log of its own; nothing else differs from the above.")
    src_of = {p["name"]: (f"{p.get('set')} {p.get('id')}" if p.get("source") == "workloads" else "inline") for p in pl["prompts"]}
    L.append("prompts: " + ", ".join(f"{q} = {src_of[q]}" for q in pr)
             + (f" (from {pl['workloads']})" if pl.get("workloads") else "") + ".")
    L.append(f"plan: prompts {', '.join(pr)} (thinking off: chat_template_kwargs enable_thinking false; no nonce; the "
             f"rendered prompt ids the same in every arm, checked), rounds interleaved, max_tokens {pl['max_tokens']}, "
             "seed = arm base + 1000 x prompt index + round; every request sends temperature 1.0, top_p 0.95, top_k 20, "
             "min_p 0.05, presence_penalty 0, frequency_penalty 0, repetition_penalty 1 (server.py's model-card default "
             "for thinking off is presence_penalty 1.5; the request's own fields win).")
    sc = spec["scorer"]
    L.append(f"scorer: {os.path.basename(sc['base'])} under the yardstick's fixed settings (quant_quality.py FIXED / "
             "FIXED_ENV: experts on the CPU pool, no adaptation, no PCIe share, no suffix drafts, no prompt cache, FP16 "
             "K/V) with --spec 2 (2-row verify windows: decpath_rules.py's decode-path reference), STRATA_LOGPOS + "
             "STRATA_LOGPOS_TOPK=64, --short-read / --max-context from the plan; one teacher-forced reference, the "
             "same config for every arm.")
    L.append(f"statistic: D2(A, B) = Mahalanobis distance of the arms' calibration vectors (top-1 rate, rank-2 rate, log p - "
             "each minus what the scorer's p~ predicts per token; equal weight per prompt; empirical variance); "
             f"chi-square, {K_FEAT} df if A ~ B.")
    L.append(f"noise bound c = chi2({K_FEAT}) {100 * (1 - ALPHA):.0f}th percentile = {C_BOUND:.4f}.")
    nz = noise or "R2"
    L.append(f"band = max(c, D2({nz}, {ref}))   [the reference against itself: never below pure sampling noise]")
    L.append(f"per candidate X ({', '.join(cands)}): PASS iff D2(X, {ref}) <= band, the data are valid and the test has the "
             f"power below. FAIL iff D2(X, {ref}) > band and the data are valid ({nz} present and valid).")
    L.append(f"NOT DECIDED iff any of: an arm needed has < {N_MIN} valid scored generated tokens, or < {SAMPLES_MIN} valid "
             f"samples of one of {', '.join(pr)}, or > {MAX_INVALID:.0%} of its samples invalid (raw ids count != "
             "completion_tokens, rendered prompt length != prompt_tokens, prompt ids not the same in every arm, a "
             "request with a server line matching a taint pattern, score rows / targets not the sample's, an error or "
             f"cancel finish); an arm's exercise check fails; D2({ref}, scorer) > {SANITY_D2:.0f} (the scorer does not "
             f"track the reference); D2(X, {ref}) > c with {nz} missing or invalid; for a PASS: the least favourable "
             f"top-1 shift seen with {POWER:.0%} probability, sqrt(lambda80 * (V_X + V_{ref})[top-1]), above {DELTA_STAR} "
             f"(lambda80: the noncentrality that chi2({K_FEAT}) needs to pass c with probability {POWER:.0%} = "
             f"{LAM80:.3f}).")
    L.append("taint patterns (a request whose server log lines match one is invalid): "
             + "; ".join(f"/{t}/" for t in spec.get("taint") or []) + ".")
    L.append("exercise checks (on the arm's engine log of its start; a failed one = that arm NOT DECIDED):")
    for n, a in spec["arms"].items():
        if a.get("role") == "verify":
            continue
        parts = []
        for c in a.get("exercise") or []:
            e = spec["exercise"][c]
            parts += [f"has /{x}/" for x in e.get("require") or []] + [f"no /{x}/" for x in e.get("forbid") or []]
            if e.get("counter"):
                parts.append(f"sum of /{e['counter']['re']}/ group {e['counter'].get('group', 1)} >= {e['counter']['min_total']}")
        L.append(f"  {n}: " + ("; ".join(parts) if parts else "none"))
    if verifs:
        L.append("read-back check (a verify start: served like its arm, its own seeds, not scored):")
        for n in verifs:
            a, v = spec["arms"][n], spec["verify"][spec["arms"][n]["verify"]]
            ch = arm_changes(spec, n)
            L.append(f"  {n} = {a['same_as'] if a.get('same_as') else os.path.basename(a['base'])}"
                     f"{' + ' + ', '.join(ch) if ch else ''}, K {arm_k(spec, n)}, covers {', '.join(a.get('covers') or [])}: "
                     f"PASS iff no engine-log line matches /{v['mismatch_re']}/, a line /{v['summary_re']}/ shows >= "
                     f"{v.get('min_read_back', 1)} slots read back and every such line 0 differ, "
                     + "".join(f"it has /{x}/, " for x in v.get("require") or [])
                     + "".join(f"it has no /{x}/, " for x in v.get("forbid") or [])
                     + f"and >= {v.get('min_requests', 1)} request(s) finished; FAIL iff a mismatch line or a differ > 0; "
                     "else NOT DECIDED.")
        L.append("overall, per candidate: PASS iff its sampled verdict is PASS and every read-back check covering it is "
                 "PASS; FAIL iff either is FAIL; else NOT DECIDED.")
    L.append(f"stage 1 (without {nz}): a candidate passes if D2(X, {ref}) <= c and the rest holds ({nz} is not needed: band >= "
             f"c); one above c needs {nz}, then the final judgement.")
    L.append(f"INFO only (never in a verdict): D2({nz}, {ref}) above c is flagged (the reference pair is farther apart than "
             "sampling noise); D2(X, scorer); decode windows, drafts, PCIe share, counters per arm.")
    L.append("The statistic and its constants (c, lambda80, DELTA_STAR, N_MIN, the sample minimums, the invalid share, the "
             "sanity bound) are sampled.py's (gap D2, Karl 11-08 FIXED), the math copied verbatim into sq_stat.py; the arms, "
             "the exercise and read-back checks and the overall rule are this spec's and need Karl's OK.")
    return "\n".join(L)


# ================================================================ reading an arm
RAW = "[strata] raw ids: "                         # server.py:5803-5805 (STRATA_DEBUG=1), every generated id, stop included
DONE_RE = re.compile(r"^\[strata\] done: (\d+) tokens in .*?\((\w+), cancel=(\w+)\)(?:, expert cache ([\d.]+)% hit"
                     r"(?: \(\+([\d.]+)% of the routed experts over PCIe\))?)?")
REQ_RE = re.compile(r"^\[strata\] req openai: .*?max_new=(\d+) thinking=(\w+) .*?prompt_tokens=(\d+)")   # server.py:5964-5976
ENG_REQ_RE = re.compile(r"^strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in [\d.]+ ms .*?, (\d+) generated "
                        r"in ([\d.]+) ms(?:.*?drafts accepted (\d+) of (\d+))?(?:.*?, (\d+) windows)?")


def read_jsonl(p):
    out = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_arm(d, prompts, sampling=SAMPLING):
    """-> dict: accs per prompt, counts, validity notes. Reads d/sampled.jsonl, d/score-ids.json, d/score-ids.meta.json,
    d/score/score.tsv and .seg.json (the layout of sq.py ids / score)"""
    out = {"dir": d, "why": [], "samples": 0, "valid": 0, "invalid": [], "tokens": 0, "per_prompt": {}, "info": {}}
    recs = read_jsonl(f"{d}/sampled.jsonl")
    meta_p, ids_p = f"{d}/score-ids.meta.json", f"{d}/score-ids.json"
    tsv, segj = f"{d}/score/score.tsv", f"{d}/score/score.tsv.seg.json"
    for p in (meta_p, ids_p, tsv, segj):
        if not os.path.exists(p):
            out["why"].append(f"missing {os.path.relpath(p, d)}")
    if out["why"] or not recs:
        if not recs:
            out["why"].append("no sampled.jsonl records")
        return out
    mj = json.load(open(meta_p))
    meta = {s["name"]: s for s in mj["segments"]}
    out["info"] = mj.get("info") or {}
    idsf = {s["name"]: s["ids"] for s in json.load(open(ids_p))["segments"]}
    segs = json.load(open(segj))["segments"]
    lines = open(tsv).read().splitlines()
    out["samples"] = len(recs)
    accs = {q: Acc() for q in prompts}
    rec_by = {r["name"]: r for r in recs}
    seen = set()
    for sg in segs:
        name = sg["name"]
        seen.add(name)
        mt, r, ids = meta.get(name), rec_by.get(name), idsf.get(name)
        bad = None
        if mt is None or r is None or ids is None:
            bad = "no meta / record / ids"
        elif not mt.get("ok", False):
            bad = mt.get("why") or "marked invalid by ids"
        elif r.get("finish") not in ("length", "stop"):
            bad = f"finish {r.get('finish')}"
        elif mt["prompt"] not in accs:
            bad = f"prompt {mt['prompt']} not in the plan"
        rows = lines[sg["first_line"]:sg["end_line"]]
        pn, gn = (mt or {}).get("prompt_n", 0), (mt or {}).get("gen_n", 0)
        if bad is None and (len(rows) != len(ids) - 1 or len(ids) != pn + gn or gn < 1):
            bad = f"rows {len(rows)} / ids {len(ids)} / prompt {pn} + gen {gn} do not fit"
        terms = []
        if bad is None:
            for j, line in enumerate(rows):
                try:
                    pos, tgt, lt, top = parse_row(line)
                except (ValueError, IndexError):
                    bad = f"row {j}: not a LOGPOS row"
                    break
                if pos != j or ids[pos + 1] != tgt or len(top) < 1:
                    bad = f"row {j} (position {pos}): target {tgt} is not the sample's id at {j + 1}"
                    break
                if pos < pn - 1:
                    continue          # a prompt row
                d_, s, info = token_terms(top, tgt, lt, sampling)
                terms.append((d_, s, info))
            if bad is None and len(terms) != gn:
                bad = f"{len(terms)} generated rows, the sample has {gn}"
        if bad is not None:
            out["invalid"].append(f"{name}: {bad}")
            continue
        a = accs[mt["prompt"]]
        for d_, s, info in terms:
            a.add(d_, s, info, info["p_top"])
        out["valid"] += 1
        out["tokens"] += len(terms)
        pp = out["per_prompt"].setdefault(mt["prompt"], {"samples": 0, "tokens": 0})
        pp["samples"] += 1
        pp["tokens"] += len(terms)
    for r in recs:
        if r["name"] not in seen:
            out["invalid"].append(f"{r['name']}: {(meta.get(r['name']) or {}).get('why') or 'not in the score file'}")
    out["accs"] = accs
    return out


def arm_problems(a, prompts):
    w = list(a["why"])
    if w:
        return w
    if a["tokens"] < N_MIN:
        w.append(f"{a['tokens']} valid scored tokens < {N_MIN}")
    for q in prompts:
        ns = a["per_prompt"].get(q, {}).get("samples", 0)
        if ns < SAMPLES_MIN:
            w.append(f"{ns} valid samples of {q} < {SAMPLES_MIN}")
    if a["samples"] and len(a["invalid"]) > MAX_INVALID * a["samples"]:
        w.append(f"{len(a['invalid'])} of {a['samples']} samples invalid")
    return w


def read_text(p):
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


def exercise_problems(d, checks):
    """checks: [{"require": [re], "forbid": [re], "counter": {"re", "group", "min_total"}}] on d/engine.out (the engine
    log of the arm's start). -> (problems, info)"""
    text = read_text(f"{d}/engine.out")
    if text is None:
        return (["no engine.out (the engine log of this start)"] if checks else []), {}
    bad, info = [], {}
    for c in checks:
        for rx in c.get("require") or []:
            if not re.search(rx, text, re.M):
                bad.append(f"no engine-log line matches /{rx}/")
        for rx in c.get("forbid") or []:
            m = re.search(rx, text, re.M)
            if m:
                bad.append(f"an engine-log line matches /{rx}/: {m.group(0)[:120]!r}")
        cn = c.get("counter")
        if cn:
            g = int(cn.get("group", 1))
            tot = sum(int(m.group(g)) for m in re.finditer(cn["re"], text, re.M))
            info[f"counter /{cn['re'][:40]}/"] = tot
            if tot < int(cn["min_total"]):
                bad.append(f"counter /{cn['re']}/ sums to {tot} < {cn['min_total']}")
    return bad, info


def engine_info(d):
    """INFO from the engine log: per-request decode lines (generated, windows, drafts) and the server's done lines (PCIe)"""
    out = {}
    text = read_text(f"{d}/engine.out") or ""
    g = w = acc = off = n = 0
    ms = 0.0
    for line in text.splitlines():
        m = ENG_REQ_RE.match(line)
        if m:
            n += 1
            g += int(m.group(4))
            ms += float(m.group(5))
            acc += int(m.group(6) or 0)
            off += int(m.group(7) or 0)
            w += int(m.group(8) or 0)
    if n:
        out.update(engine_requests=n, generated=g, decode_windows=w, drafts_accepted=acc, drafts_offered=off,
                   decode_tok_s=round(g / (ms / 1000), 1) if ms > 0 else None,
                   tokens_per_window=round(g / w, 2) if w else None)
    srv = read_text(f"{d}/server.out") or ""
    pc, hit = [], []
    for line in srv.splitlines():
        m = DONE_RE.match(line)
        if m:
            if m.group(4):
                hit.append(float(m.group(4)))
            if m.group(5):
                pc.append(float(m.group(5)))
    if hit:
        out["expert_cache_hit_pct_mean"] = round(sum(hit) / len(hit), 2)
    if pc or hit:
        out["pcie_share_pct_mean"] = round(sum(pc) / len(hit or pc), 2) if pc else 0.0
    return out


def summary(a, prompts):
    if "accs" not in a:
        return {"why": a["why"]}
    ok = all(a["accs"][q].n > 1 for q in prompts)
    m, v = combine(a["accs"], prompts) if ok else (None, None)
    n = sum(a["accs"][q].n for q in prompts)
    t1 = sum(a["accs"][q].top1 for q in prompts)
    t1e = sum(a["accs"][q].top1_exp for q in prompts)
    out = {"samples": a["samples"], "valid": a["valid"], "invalid": a["invalid"][:20], "tokens": a["tokens"],
           "per_prompt": a["per_prompt"], "top1_rate": round(t1 / max(1, n), 5), "top1_expected": round(t1e / max(1, n), 5),
           "outside_kept": int(sum(a["accs"][q].outside for q in prompts))}
    if m is not None:
        out["m"] = [round(x, 6) for x in m]
        out["se"] = [round(math.sqrt(max(0.0, v[i][i])), 6) for i in range(3)]
        try:
            out["d2_vs_scorer"] = round(d2(m, v), 3)
        except ValueError:
            out["d2_vs_scorer"] = None
    return out


def verify_judge(d, v):
    """the read-back check of a verify start (its engine log d/engine.out, its records d/sampled.jsonl)"""
    res = {"dir": d, "mismatch_lines": 0, "read_back": None, "differ": None, "problems": []}
    text = read_text(f"{d}/engine.out")
    if text is None:
        res.update(verdict="NOT DECIDED", why="no engine.out (the verify start's engine log)")
        return res
    recs = read_jsonl(f"{d}/sampled.jsonl")
    done = sum(1 for r in recs if r.get("finish") in ("length", "stop"))
    mism = [m.group(0) for m in re.finditer(v["mismatch_re"], text, re.M)]
    sums = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(v["summary_re"], text, re.M)]
    res.update(mismatch_lines=len(mism), first_mismatches=[x[:200] for x in mism[:5]], summary_lines=len(sums),
               read_back=max((s[0] for s in sums), default=None), differ=max((s[1] for s in sums), default=None),
               requests_finished=done)
    for rx in v.get("require") or []:
        if not re.search(rx, text, re.M):
            res["problems"].append(f"no line matches /{rx}/")
    for rx in v.get("forbid") or []:
        m = re.search(rx, text, re.M)
        if m:
            res["problems"].append(f"a line matches /{rx}/: {m.group(0)[:120]!r}")
    if mism or any(s[1] > 0 for s in sums):
        res.update(verdict="FAIL", why=f"read-back mismatch: {len(mism)} mismatch line(s)"
                   + (f", first {mism[0][:160]!r}" if mism else "") + f"; summary differ max {res['differ']}")
    elif res["problems"] or not sums or (res["read_back"] or 0) < int(v.get("min_read_back", 1)) \
            or done < int(v.get("min_requests", 1)):
        why = res["problems"] + ([] if sums else ["no read-back summary line"])
        if sums and (res["read_back"] or 0) < int(v.get("min_read_back", 1)):
            why.append(f"{res['read_back']} slots read back < {v.get('min_read_back', 1)}")
        if done < int(v.get("min_requests", 1)):
            why.append(f"{done} request(s) finished < {v.get('min_requests', 1)}")
        res.update(verdict="NOT DECIDED", why="; ".join(why))
    else:
        res.update(verdict="PASS", why=f"{res['read_back']} admitted slots read back, 0 differ, no mismatch line")
    return res


def judge(o, spec, stage1=False):
    """-> (res, rc). rc 0 every candidate PASS (overall), 1 a FAIL, 2 otherwise; stage1: 3 = the noise arm is needed"""
    pr = prompts_of(spec)
    ref, noise = ref_of(spec), noise_of(spec)
    cands, verifs = role_of(spec, "candidate"), role_of(spec, "verify")
    res = {"spec": spec["name"], "spec_sha": spec_sha(spec)[:16], "c": round(C_BOUND, 4), "lambda80": round(LAM80, 4),
           "stage1": stage1, "arms": {}, "candidates": {}, "verify": {}, "overall": {}, "flags": []}
    arms = {}
    for n in [ref] + ([noise] if noise else []) + cands:
        p = f"{o}/{n}"
        arms[n] = load_arm(p, pr) if os.path.isdir(p) else None
        if arms[n] is not None:
            s = summary(arms[n], pr)
            probs = arm_problems(arms[n], pr)
            ex, exi = exercise_problems(p, [spec["exercise"][c] for c in spec["arms"][n].get("exercise") or []])
            s.update(problems=probs + ex, exercise_info=exi, engine=engine_info(p), info=arms[n].get("info") or {})
            res["arms"][n] = s
    ok = lambda n: arms.get(n) is not None and not res["arms"][n]["problems"]   # noqa: E731
    base_why = None
    if arms[ref] is None:
        base_why = f"{ref} missing"
    elif not ok(ref):
        base_why = f"{ref}: " + "; ".join(res["arms"][ref]["problems"])
    m1 = v1 = None
    if base_why is None:
        m1, v1 = combine(arms[ref]["accs"], pr)
        s1 = d2(m1, v1)
        res["d2_ref_scorer"] = round(s1, 3)
        if s1 > SANITY_D2:
            base_why = f"D2({ref}, scorer) {s1:.1f} > {SANITY_D2}: the scorer does not track the served reference"
    band, dr = C_BOUND, None
    nz_why = None
    if noise is None or arms.get(noise) is None:
        nz_why = f"{noise or 'the noise arm'} missing"
    elif not ok(noise):
        nz_why = f"{noise}: " + "; ".join(res["arms"][noise]["problems"])
    elif base_why is None:
        m2, v2 = combine(arms[noise]["accs"], pr)
        dr = d2(m2, v2, m1, v1)
        band = max(C_BOUND, dr)
        res.update(d2_noise_ref=round(dr, 4), band=round(band, 4))
        if dr > C_BOUND:
            res["flags"].append(f"INFO: D2({noise}, {ref}) {dr:.3f} > c {C_BOUND:.3f}: the reference pair is farther apart "
                                "than sampling noise (band = it)")
    need_noise = False
    for x in cands:
        cr = {}
        res["candidates"][x] = cr
        if base_why is not None:
            cr.update(verdict="NOT DECIDED", why=base_why)
            continue
        if arms.get(x) is None or not ok(x):
            cr.update(verdict="NOT DECIDED", why=f"{x} missing" if arms.get(x) is None
                      else f"{x}: " + "; ".join(res["arms"][x]["problems"]))
            continue
        mx, vx = combine(arms[x]["accs"], pr)
        dx = d2(mx, vx, m1, v1)
        mde = math.sqrt(LAM80 * (vx[0][0] + v1[0][0]))
        cr.update(d2_x_ref=round(dx, 4), mde_top1=round(mde, 5), d2_x_scorer=res["arms"][x].get("d2_vs_scorer"))
        if dx <= C_BOUND:
            if mde > DELTA_STAR:
                cr.update(verdict="NOT DECIDED", why=f"too few samples: the least favourable top-1 shift seen with "
                                                     f"{POWER:.0%} probability is {mde:.4f} > {DELTA_STAR}")
            else:
                cr.update(verdict="PASS", band=round(C_BOUND, 4),
                          why=f"D2({x}, {ref}) {dx:.3f} <= the noise bound {C_BOUND:.3f} (band >= it whatever {noise or 'R2'} gives)")
            continue
        if nz_why is not None:
            if stage1 and (noise is None or arms.get(noise) is None):
                need_noise = True
                cr.update(verdict="NOISE ARM NEEDED", why=f"D2({x}, {ref}) {dx:.3f} > the noise bound {C_BOUND:.3f}: run "
                                                          f"{noise or 'the noise arm'}, then judge again")
            else:
                cr.update(verdict="NOT DECIDED", why=f"D2({x}, {ref}) {dx:.3f} > the noise bound {C_BOUND:.3f} and {nz_why}")
            continue
        cr["band"] = round(band, 4)
        if dx <= band:
            if mde > DELTA_STAR:
                cr.update(verdict="NOT DECIDED", why=f"inside the band ({dx:.3f} <= {band:.3f}) but too few samples: the "
                                                     f"least favourable top-1 shift seen with {POWER:.0%} is {mde:.4f} > {DELTA_STAR}")
            else:
                cr.update(verdict="PASS", why=f"D2({x}, {ref}) {dx:.3f} <= band {band:.3f} = max(noise bound {C_BOUND:.3f}, "
                                              f"D2({noise}, {ref}) {dr:.3f})")
        else:
            cr.update(verdict="FAIL", why=f"D2({x}, {ref}) {dx:.3f} > band {band:.3f} = max(noise bound {C_BOUND:.3f}, "
                                          f"D2({noise}, {ref}) {dr:.3f})")
    if stage1:
        vs = [c["verdict"] for c in res["candidates"].values()]
        rc = 3 if need_noise else (0 if all(v == "PASS" for v in vs) else (1 if "FAIL" in vs else 2))
        res["verdict"] = {0: "ALL PASS (stage 1)", 1: "FAIL", 2: "NOT DECIDED", 3: "NOISE ARM NEEDED"}[rc]
        return res, rc
    for n in verifs:
        vspec = spec["verify"][spec["arms"][n]["verify"]]
        res["verify"][n] = verify_judge(f"{o}/{n}", vspec) if os.path.isdir(f"{o}/{n}") else \
            {"verdict": "NOT DECIDED", "why": f"{n} missing"}
    for x in cands:
        sv = res["candidates"][x]["verdict"]
        cov = [n for n in verifs if x in (spec["arms"][n].get("covers") or [])]
        vv = [res["verify"][n]["verdict"] for n in cov]
        if sv == "FAIL" or "FAIL" in vv:
            ov = "FAIL"
        elif sv == "PASS" and all(v == "PASS" for v in vv):
            ov = "PASS"
        else:
            ov = "NOT DECIDED"
        res["overall"][x] = {"verdict": ov, "sampled": sv, "read_back": dict(zip(cov, vv))}
    ovs = [v["verdict"] for v in res["overall"].values()]
    rc = 1 if "FAIL" in ovs else (0 if ovs and all(v == "PASS" for v in ovs) else 2)
    res["verdict"] = {0: "ALL PASS", 1: "FAIL", 2: "NOT DECIDED"}[rc]
    return res, rc


def decision_text(o, res):
    L = [f"Qwen sampled-distribution test {res['spec']} (spec sha256 {res['spec_sha']}): {res['verdict']}",
         f"folder {o}; rule: rule.txt (sq.py rule); c {res['c']}, lambda80 {res['lambda80']}"
         + (" - STAGE 1 (without the noise arm)" if res.get("stage1") else ""), ""]
    for k in ("d2_ref_scorer", "d2_noise_ref", "band"):
        if k in res:
            L.append(f"{k}: {res[k]}")
    L += [f"FLAG {f}" for f in res.get("flags") or []]
    L.append("")
    for x, c in res["candidates"].items():
        ov = res.get("overall", {}).get(x)
        L.append(f"{x}: sampled {c['verdict']} - {c.get('why', '')}"
                 + (f" | read-back {ov['read_back']} -> OVERALL {ov['verdict']}" if ov else ""))
    for n, v in (res.get("verify") or {}).items():
        L.append(f"read-back {n}: {v['verdict']} - {v.get('why', '')}")
    L += ["", "arm | samples (valid) | tokens | top-1 rate / expected | D2 vs scorer | decode windows | tok/window | "
          "PCIe share % | problems"]
    for n, s in res["arms"].items():
        e = s.get("engine") or {}
        if "tokens" not in s:
            L.append(f"{n} | - | - | - | - | - | - | - | {'; '.join(s.get('problems') or s.get('why') or [])}")
            continue
        L.append(f"{n} | {s['samples']} ({s['valid']}) | {s['tokens']} | {s['top1_rate']} / {s['top1_expected']} | "
                 f"{s.get('d2_vs_scorer')} | {e.get('decode_windows', '-')} | {e.get('tokens_per_window', '-')} | "
                 f"{e.get('pcie_share_pct_mean', '-')} | {'; '.join(s['problems']) or '-'}")
    return "\n".join(L) + "\n"


def write_decision(o, res):
    json.dump(res, open(f"{o}/decision.json", "w"), indent=1)
    open(f"{o}/decision.txt", "w").write(decision_text(o, res))


# ================================================================ synthetic data (selftest only; no real ids or sizes)
def synth_row(rng, vocab):
    """a random top-64 row over a SYNTHETIC vocabulary of `vocab` ids: log-softmax over 64 candidates plus a tail outside
    them, shaped like sampled.py's synth_row (mostly nearly certain, else a few candidates, now and then a flat head)"""
    u = rng.random()
    if u < 0.62:
        gaps = [rng.uniform(4.0, 12.0)] + [rng.expovariate(1.0) * 0.3 for _ in range(62)]
    else:
        tau = 0.15 if u > 0.95 else math.exp(rng.uniform(math.log(0.4), math.log(2.5)))
        gaps = [rng.expovariate(1.0) * tau for _ in range(63)]
    z = [0.0]
    for g in gaps:
        z.append(z[-1] - g)
    tail = rng.uniform(0.001, 0.05)
    lse = math.log(sum(math.exp(x) for x in z) * (1.0 + tail))
    ids = rng.sample(range(vocab), 64)
    return [(ids[i], z[i] - lse) for i in range(64)]


class SynthModel:
    """a deterministic synthetic 'model': the row at a context is a function of (the last two ids, the length) only, so
    a served stand-in and the mock scorer (another process) agree on every position"""
    def __init__(self, vocab=50000, salt=7):
        self.vocab, self.salt = vocab, salt

    def row_at(self, ids, t):
        """the row for the context ids[:t + 1] (the next token's distribution)"""
        a = ids[t]
        b = ids[t - 1] if t > 0 else 0
        s = ((((a * 1000003) ^ b) * 1000003 + t + 1) * 1000003 + self.salt) % (1 << 61)
        return synth_row(random.Random(s), self.vocab)

    def row(self, ctx):
        return self.row_at(ctx, len(ctx) - 1)


def jitter(top, rng, sd):
    return [(i, v + rng.gauss(0.0, sd)) for i, v in top]


def draw(top, rng, temperature=1.0, noise_share=0.0, noise_sd=0.0):
    """x from the sampler's chain over `top` at `temperature`; with noise_share > 0, at that share of positions the row's
    logits get Gaussian noise of noise_sd first (a stand-in for a corrupted expert slot)"""
    if noise_share > 0.0 and rng.random() < noise_share:
        top = jitter(top, rng, noise_sd)
    smp = dict(SAMPLING, temperature=temperature)
    ids, p, _ = kept(top, smp["top_k"], smp["top_p"], smp["min_p"], smp["temperature"])
    u, cum = rng.random(), 0.0
    for i, w in enumerate(p):
        cum += w
        if u < cum:
            return ids[i]
    return ids[-1]


def fmt_row(pos, tgt, top):
    """a STRATA_LOGPOS row (verify.cpp window_logprobs + STRATA_LOGPOS_TOPK): pos, target, logp(target), argmax,
    logp(argmax), hit, extra, without, then the top-k id:logprob"""
    top = sorted(top, key=lambda e: (-e[1], e[0]))
    lt = dict(top).get(tgt, top[-1][1] - 1.0)
    s = f"{pos}\t{tgt}\t{lt:.6f}\t{top[0][0]}\t{top[0][1]:.6f}\t{1 if top[0][0] == tgt else 0}\tnan\tnan"
    return s + "".join(f"\t{i}:{v:.6f}" for i, v in top)


ENGINE_EXACT = ("strata mtp: EXACT speculative sampling on (STRATA_SPEC_EXACT): sampled requests draft from q (their own "
                "chain over 40000 tokens, a proposal stream of its own) and verify by accept / residual / bonus")


def fetch_banner(mode):
    return (f"strata serve: STRATA_ADAPT_FETCH={mode}: the PCIe share takes each layer's most-routed misses and admits "
            f"those routed >= 1.00 and 0.50 more than a resident one{'; the tier own copies are off' if mode == 2 else ''}")


def synth_arm(d, prompts, rng, samples_per_prompt, gen_n, served_sd=0.02, temperature=1.0, noise_share=0.0,
              noise_sd=0.0, misalign=False, prompt_n=5, vocab=50000, engine_lines=(ENGINE_EXACT,)):
    """an arm folder in sq.py's layout: the served stand-in draws from jittered rows (its rounding; temperature != 1 or
    noise: a real shift), the scorer writes the unjittered ones"""
    os.makedirs(f"{d}/score", exist_ok=True)
    recs, segs, meta, lines, segj = [], [], [], [], []
    for rep in range(samples_per_prompt):
        for q in prompts:
            name = f"{os.path.basename(d)}-{q}-{rep:02d}"
            rows, gen = [], []
            pids = [rng.randrange(vocab) for _ in range(prompt_n)]
            for _ in range(gen_n):
                top = synth_row(rng, vocab)
                gen.append(draw(jitter(top, rng, served_sd), rng, temperature, noise_share, noise_sd))
                rows.append(top)
            ids = pids + gen
            first = len(lines)
            for a in range(len(ids) - 1):
                if a < prompt_n - 1:
                    top = synth_row(rng, vocab)
                    lines.append(fmt_row(a, ids[a + 1], [(ids[a + 1], -0.1)] + [e for e in top if e[0] != ids[a + 1]][:63]))
                else:
                    t = rows[a - (prompt_n - 1)]
                    if misalign and a + 2 < len(ids):
                        t = rows[min(len(rows) - 1, a - (prompt_n - 1) + 1)]
                    lines.append(fmt_row(a, ids[a + 1], t))
            segj.append({"name": name, "first_line": first, "end_line": len(lines)})
            recs.append({"name": name, "prompt": q, "seed": 1000 + len(recs), "prompt_tokens": prompt_n,
                         "completion_tokens": gen_n, "finish": "length"})
            segs.append({"name": name, "ids": ids})
            meta.append({"name": name, "prompt": q, "prompt_n": prompt_n, "gen_n": gen_n, "ok": True, "why": None})
    with open(f"{d}/sampled.jsonl", "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    json.dump({"segments": segs}, open(f"{d}/score-ids.json", "w"))
    json.dump({"segments": meta}, open(f"{d}/score-ids.meta.json", "w"))
    open(f"{d}/score/score.tsv", "w").write("\n".join(lines) + "\n")
    json.dump({"segments": segj}, open(f"{d}/score/score.tsv.seg.json", "w"))
    eng = list(engine_lines) + [f"strata serve: prompt {prompt_n} tokens = 0 reused + {prompt_n} read in 10 ms (100.0 tok/s), "
                                f"{gen_n} generated in {gen_n * 8} ms (125.0 tok/s), drafts accepted {gen_n // 2} of {gen_n}, "
                                f"1 checkpoints, {gen_n // 2} windows, 2.00 drafts per window"] * len(recs)
    open(f"{d}/engine.out", "w").write("\n".join(eng) + "\n")
