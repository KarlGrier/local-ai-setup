// ess_test.cu - round 9 Phase A.1: the GPU kernels of EXACT SPECULATIVE SAMPLING (strata-r9e's sampler.cu:
// ess_draft_sample + sample_tokens_spec) against the exact target distribution, with tiny vocabularies (round 8's
// work/r8/specsamp_ref.py cases, now through the real kernels) and one full-size case.
//
// A trial is one verify window after a context c: the drafter samples x_0 .. x_{K-1} (step j from q(c + x_<j), the
// PROPOSAL stream at the verifying row's counter), the verify head gets the target's rows p(c + x_<t), t = 0..K, and
// the host keeps the prefix of rows whose out[t] == x_t (the engine's accept rule).  Recorded: the FIRST emitted token
// and the first TWO (a window that emits one token is followed by a fresh window at context (y0,), as the engine does),
// against p(()) and p(())(a) * p((a,))(b): chi-square, p-value.  Draft-length rules are decided on q alone (the max of
// q, BEFORE the draw).  The NEGATIVE CONTROL decides from the sampled draft and must be caught.
// Every trial has its own position block (counter), so the draws are independent across trials.
// Also: the bonus row (no draft) and sample_tokens give the same token, bit for bit, on full-size random logits.
#include "strata/kernels/sampler.hpp"
#include "strata/kernels/verify_kernels.hpp"

#include "strata/spec/cost_gate.hpp"
#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <random>
#include <string>
#include <vector>

using namespace strata::kernels;
using Ctx = std::vector<int>;
using Logits = std::function<std::vector<float>(const Ctx&)>;

static void ck(cudaError_t e, const char* w) { if (e != cudaSuccess) { std::fprintf(stderr, "%s: %s\n", w, cudaGetErrorString(e)); std::exit(1); } }

// ---- the chain on the host (double): penalties none; top_k -> softmax -> top_p cut -> min_p -> temperature softmax
static std::vector<double> chain(const std::vector<float>& l, const SamplerParams& p) {
    const int V = (int) l.size();
    std::vector<int> ord(V);
    for (int i = 0; i < V; ++i) ord[i] = i;
    std::stable_sort(ord.begin(), ord.end(), [&](int a, int b) { return l[a] > l[b]; });
    const int k = std::min(V, (p.top_k > 0 && p.top_k < 64) ? p.top_k : 64);
    std::vector<int> sel(ord.begin(), ord.begin() + k);
    int n = k;
    if (p.top_p < 1.0f) {
        double mx = l[sel[0]], s = 0; std::vector<double> e(k);
        for (int i = 0; i < k; ++i) { e[i] = std::exp((double) l[sel[i]] - mx); s += e[i]; }
        double cum = 0; int cut = k;
        for (int i = 0; i < k; ++i) { cum += e[i] / s; if (cum >= (double) p.top_p) { cut = i + 1; break; } }
        if (cut < p.min_keep) cut = std::min(p.min_keep, k);
        n = cut;
    }
    if (p.min_p > 0.0f) {
        const float th = l[sel[0]] + std::log(p.min_p);
        for (int i = 0; i < n; ++i) if (l[sel[i]] < th) { n = i; break; }
    }
    std::vector<double> out(V, 0.0);
    const double it = 1.0 / p.temperature;
    double mx = -1e300, s = 0;
    for (int i = 0; i < n; ++i) mx = std::max(mx, (double) l[sel[i]] * it);
    for (int i = 0; i < n; ++i) { out[sel[i]] = std::exp((double) l[sel[i]] * it - mx); s += out[sel[i]]; }
    for (auto& x : out) x /= s;
    return out;
}

// chi-square survival (regularized upper incomplete gamma Q(dof/2, x/2)), Numerical Recipes gammq
static double gammq(double a, double x) {
    if (x <= 0) return 1.0;
    const double gln = std::lgamma(a);
    if (x < a + 1.0) {   // series for P
        double ap = a, sum = 1.0 / a, del = sum;
        for (int n = 1; n < 1000; ++n) { ap += 1; del *= x / ap; sum += del; if (std::fabs(del) < std::fabs(sum) * 1e-15) break; }
        return 1.0 - sum * std::exp(-x + a * std::log(x) - gln);
    }
    double b = x + 1.0 - a, c = 1.0 / 1e-300, d = 1.0 / b, h = d;   // continued fraction for Q
    for (int i = 1; i < 1000; ++i) {
        const double an = -i * (i - a); b += 2.0;
        d = an * d + b; if (std::fabs(d) < 1e-300) d = 1e-300;
        c = b + an / c; if (std::fabs(c) < 1e-300) c = 1e-300;
        d = 1.0 / d; const double del = d * c; h *= del;
        if (std::fabs(del - 1.0) < 1e-15) break;
    }
    return std::exp(-x + a * std::log(x) - gln) * h;
}
static double chi2_p(const std::vector<double>& obs, const std::vector<double>& prob, double n, double* stat_out, int* dof_out) {
    double st = 0; int dof = 0;
    for (size_t i = 0; i < obs.size(); ++i) {
        const double e = prob[i] * n;
        if (e > 0) { st += (obs[i] - e) * (obs[i] - e) / e; ++dof; }
        else if (obs[i] > 0) { *stat_out = INFINITY; *dof_out = dof; return 0.0; }
    }
    dof = std::max(1, dof - 1);
    *stat_out = st; *dof_out = dof;
    return gammq(dof / 2.0, st / 2.0);
}

struct Dev {   // per-trial device buffers, B trials in flight
    int V, B, K;
    float *dlog, *tlog;          // drafter logits (B rows), target logits (B * (K+1) rows)
    int32_t *step, *top_sub, *top_id, *out_id, *ring, *drafts, *out;
    EssQList* q;                 // B * K
    SamplerParams* params;
    void* scratch;
    cudaStream_t st;
};

static Dev make(int V, int B, int K, const SamplerParams& sp) {
    Dev d{V, B, K};
    ck(cudaMalloc(&d.dlog, (size_t) B * V * 4), "dlog");
    ck(cudaMalloc(&d.tlog, (size_t) B * (K + 1) * V * 4), "tlog");
    ck(cudaMalloc(&d.step, B * 4 * 4), "step");
    ck(cudaMalloc(&d.top_sub, B * 4), "ts"); ck(cudaMalloc(&d.top_id, B * 4), "ti"); ck(cudaMalloc(&d.out_id, B * 4), "oi");
    ck(cudaMalloc(&d.ring, (4096 + 16) * 4), "ring");
    ck(cudaMalloc(&d.drafts, (size_t) B * (K + 1) * 4), "dr");
    ck(cudaMalloc(&d.out, (size_t) B * (K + 1) * 4), "out");
    ck(cudaMalloc(&d.q, (size_t) B * std::max(K, 1) * sizeof(EssQList)), "q");
    ck(cudaMalloc(&d.params, sizeof(SamplerParams)), "params");
    ck(cudaMemcpy(d.params, &sp, sizeof sp, cudaMemcpyHostToDevice), "params cp");
    ck(cudaMalloc(&d.scratch, (size_t) 64 * 64 * 8), "scratch");
    ck(cudaStreamCreate(&d.st), "stream");
    return d;
}

enum class Rule { Fixed, MaxQ, NegControl, Lookup, CostGate };

struct Case {
    std::string name;
    Logits P, Q;
    int K;
    Rule rule = Rule::Fixed;
    double gate = 0.5;          // MaxQ: draft while max q >= gate (decided before the draw); NegControl: drop if q(x) < gate
    SamplerParams sp;            // the chain for both p and q
    std::vector<int> lookup;     // Lookup: the fixed point-mass drafts
};

// One batch of B windows at contexts ctx[b], positions pos[b]: returns the emitted tokens per trial.
static std::vector<std::vector<int>> run_batch(Dev& d, const Case& c, const std::vector<Ctx>& ctx,
                                               const std::vector<uint64_t>& pos, std::vector<int>* n_drafted) {
    const int V = d.V, B = (int) ctx.size(), K = c.K;
    std::vector<Ctx> cur = ctx;
    std::vector<std::vector<int>> drafts(B);
    std::vector<int> live(B, 1);
    std::vector<std::vector<double>> qd(B);
    std::vector<double> cg_prod(B, 1.0);
    // ---- the drafter, step by step (each step's q depends on the drafts before it)
    if (c.rule == Rule::Lookup) {
        for (int b = 0; b < B; ++b) drafts[b] = std::vector<int>(c.lookup.begin(), c.lookup.begin() + K);
    } else {
        for (int j = 0; j < K; ++j) {
            std::vector<float> hl((size_t) B * V);
            std::vector<int32_t> hs((size_t) B * 4, 0);
            for (int b = 0; b < B; ++b) {
                const auto l = c.Q(cur[b]);
                std::copy(l.begin(), l.end(), hl.begin() + (size_t) b * V);
                hs[(size_t) b * 4] = (int32_t) (pos[b] + j) - 1;   // cell: counter = cell + 1 = pos0 + j (row j)
                if (live[b] && c.rule == Rule::MaxQ) {             // decided from q alone, before the draw
                    const auto q = chain(l, c.sp);
                    if (*std::max_element(q.begin(), q.end()) < c.gate) live[b] = 0;
                }
                if (live[b] && c.rule == Rule::CostGate) {         // round 12: the engine's cost-aware length rule -
                    // the raw top probability of this step's logits (before any chain or draw), the table's
                    // acceptance for it, the running product against theta(j) (strata/spec/cost_gate.hpp)
                    double mx = -1e30, s2 = 0;
                    for (float x : l) mx = std::max(mx, (double) x);
                    for (float x : l) s2 += std::exp((double) x - mx);
                    const float raw_top = (float) (1.0 / s2);
                    cg_prod[b] *= strata::spec::cost_gate().a(j, raw_top);
                    if (cg_prod[b] < strata::spec::cost_gate().th(j)) live[b] = 0;
                }
            }
            ck(cudaMemcpyAsync(d.dlog, hl.data(), hl.size() * 4, cudaMemcpyHostToDevice, d.st), "dlog cp");
            ck(cudaMemcpyAsync(d.step, hs.data(), hs.size() * 4, cudaMemcpyHostToDevice, d.st), "step cp");
            SamplerParams g; g.greedy = true; g.temperature = 0.0f;
            for (int b = 0; b < B; ++b) {
                if (!live[b]) continue;
                sample_tokens(d.dlog + (size_t) b * V, 1, V, nullptr, 0, g, d.top_sub + b, d.st);
                ess_draft_sample(d.dlog + (size_t) b * V, V, nullptr, nullptr, V, d.params, d.ring, 4096, j,
                                 d.step + b * 4, d.scratch, d.top_sub + b, d.top_id + b, d.out_id + b,
                                 d.q + (size_t) b * K + j, d.st);
            }
            std::vector<int32_t> ho(B);
            ck(cudaMemcpyAsync(ho.data(), d.out_id, B * 4, cudaMemcpyDeviceToHost, d.st), "out cp");
            ck(cudaStreamSynchronize(d.st), "draft sync");
            for (int b = 0; b < B; ++b) {
                if (!live[b]) continue;
                if (c.rule == Rule::NegControl) {   // WRONG on purpose: the decision reads the sampled draft
                    const auto q = chain(c.Q(cur[b]), c.sp);
                    if (q[ho[b]] < c.gate) { live[b] = 0; continue; }
                }
                drafts[b].push_back(ho[b]);
                cur[b].push_back(ho[b]);
            }
        }
    }
    // ---- the verify head: rows 0 .. n_b (n_b drafts), row t = p(ctx + drafts_<t)
    std::vector<std::vector<int>> out(B);
    for (int b = 0; b < B; ++b) {
        const int nb = (int) drafts[b].size(), T = nb + 1;
        std::vector<float> hl((size_t) T * V);
        Ctx cc = ctx[b];
        for (int t = 0; t < T; ++t) {
            const auto l = c.P(cc);
            std::copy(l.begin(), l.end(), hl.begin() + (size_t) t * V);
            if (t < nb) cc.push_back(drafts[b][t]);
        }
        ck(cudaMemcpyAsync(d.tlog + (size_t) b * (K + 1) * V, hl.data(), hl.size() * 4, cudaMemcpyHostToDevice, d.st), "t cp");
        std::vector<int32_t> hd(K + 1, 0);
        for (int t = 0; t < nb; ++t) hd[t] = drafts[b][t];
        ck(cudaMemcpyAsync(d.drafts + (size_t) b * (K + 1), hd.data(), (K + 1) * 4, cudaMemcpyHostToDevice, d.st), "d cp");
        SamplerParams sp = c.sp;
        sp.counter = pos[b];
        sample_tokens_spec(d.tlog + (size_t) b * (K + 1) * V, T, V, nullptr, 0, sp, d.drafts + (size_t) b * (K + 1),
                           d.q + (size_t) b * K, c.rule == Rule::Lookup ? 0 : nb, nb, d.out + (size_t) b * (K + 1), d.st);
        if (n_drafted) (*n_drafted)[b] = nb;
    }
    std::vector<int32_t> ho((size_t) B * (K + 1));
    ck(cudaMemcpyAsync(ho.data(), d.out, ho.size() * 4, cudaMemcpyDeviceToHost, d.st), "o cp");
    ck(cudaStreamSynchronize(d.st), "verify sync");
    for (int b = 0; b < B; ++b) {
        const int nb = (int) drafts[b].size();
        int a = 0;
        while (a < nb && ho[(size_t) b * (K + 1) + a] == drafts[b][a]) ++a;
        for (int t = 0; t <= a; ++t) out[b].push_back(ho[(size_t) b * (K + 1) + t]);
    }
    return out;
}

static int g_bad = 0;

static void run_case(const Case& c, int V, int n_trials, uint64_t seed, bool expect_fail = false) {
    SamplerParams sp = c.sp;
    sp.seed = seed;
    Case cs = c; cs.sp = sp;
    const int B = 512;
    Dev d = make(V, B, std::max(c.K, 1), sp);
    std::vector<double> first(V, 0.0), pair((size_t) V * V, 0.0);
    uint64_t pos_next = 1000;
    double drafted = 0, accepted = 0, windows = 0;
    for (int done = 0; done < n_trials; done += B) {
        const int nb = std::min(B, n_trials - done);
        std::vector<Ctx> ctx(nb);
        std::vector<uint64_t> pos(nb);
        for (int b = 0; b < nb; ++b) { pos[b] = pos_next; pos_next += 64; }
        std::vector<int> ndr(nb);
        const auto o = run_batch(d, cs, ctx, pos, &ndr);
        std::vector<Ctx> ctx2;
        std::vector<uint64_t> pos2;
        std::vector<int> need;
        for (int b = 0; b < nb; ++b) {
            first[o[b][0]] += 1;
            drafted += ndr[b]; accepted += (double) o[b].size() - 1; windows += 1;
            if (o[b].size() >= 2) pair[(size_t) o[b][0] * V + o[b][1]] += 1;
            else { ctx2.push_back({o[b][0]}); pos2.push_back(pos[b] + 1); need.push_back(o[b][0]); }
        }
        if (!ctx2.empty()) {   // the next window, at the position after the emitted token
            const auto o2 = run_batch(d, cs, ctx2, pos2, nullptr);
            for (size_t i = 0; i < o2.size(); ++i) pair[(size_t) need[i] * V + o2[i][0]] += 1;
        }
    }
    const auto p1 = chain(c.P({}), sp);
    std::vector<double> pp((size_t) V * V);
    for (int a = 0; a < V; ++a) {
        const auto p2 = chain(c.P({a}), sp);
        for (int b = 0; b < V; ++b) pp[(size_t) a * V + b] = p1[a] * p2[b];
    }
    double s1, s2; int d1, d2;
    const double pv1 = chi2_p(first, p1, n_trials, &s1, &d1), pv2 = chi2_p(pair, pp, n_trials, &s2, &d2);
    double amin = 0;
    {
        const auto q1 = chain(c.Q({}), sp);
        for (int i = 0; i < V; ++i) amin += std::min(p1[i], q1[i]);
    }
    const bool fail = pv1 < 1e-3 || pv2 < 1e-3;
    if (fail != expect_fail) ++g_bad;
    std::printf("%-44s first chi2 %8.2f (dof %d) p=%.3f | first two chi2 %8.2f (dof %d) p=%.3f | drafts/window %.2f, "
                "accepted %.4f of drafted (sum min(p,q) at draft 1: %.4f) %s\n",
                c.name.c_str(), s1, d1, pv1, s2, d2, pv2, drafted / windows, drafted > 0 ? accepted / drafted : 0.0, amin,
                expect_fail ? (fail ? "-> CAUGHT (negative control)" : "-> NOT CAUGHT") : (fail ? "-> FAIL" : "-> pass"));
}

// the bonus row and sample_tokens: the same token, bit for bit (full vocabulary, random logits, the user's chain)
static void bonus_identity(int n) {
    const int V = 248320, T = 4;
    std::mt19937 rng(5);
    std::normal_distribution<float> nd(0.0f, 3.0f);
    float* dl; int32_t *o1, *o2, *dr;
    ck(cudaMalloc(&dl, (size_t) T * V * 4), "bl"); ck(cudaMalloc(&o1, T * 4), "o1"); ck(cudaMalloc(&o2, T * 4), "o2");
    ck(cudaMalloc(&dr, T * 4), "dr");
    cudaStream_t st; cudaStreamCreate(&st);
    int same = 0, total = 0;
    std::vector<float> h((size_t) T * V);
    for (int r = 0; r < n; ++r) {
        for (auto& x : h) x = nd(rng);
        cudaMemcpy(dl, h.data(), h.size() * 4, cudaMemcpyHostToDevice);
        SamplerParams sp; sp.top_k = 20; sp.top_p = 0.95f; sp.min_p = 0.05f; sp.temperature = 1.0f; sp.seed = 11 + r;
        sp.counter = 777 + 13 * r;
        std::vector<int32_t> hd = {-1, -1, -1, -1};   // drafts nobody will match: rows 0..2 reject, row 3 = bonus
        cudaMemcpy(dr, hd.data(), 16, cudaMemcpyHostToDevice);
        sample_tokens(dl, T, V, nullptr, 0, sp, o1, st);
        sample_tokens_spec(dl, T, V, nullptr, 0, sp, dr, nullptr, 0, T - 1, o2, st);
        cudaStreamSynchronize(st);
        int a[4], b[4];
        cudaMemcpy(a, o1, 16, cudaMemcpyDeviceToHost); cudaMemcpy(b, o2, 16, cudaMemcpyDeviceToHost);
        same += a[3] == b[3]; ++total;
        // rows with a rejected point-mass draft that is NOT in the list: the residual is p itself, so these rows are
        // draws from p with the residual stream - not today's uniform; only the bonus row must be identical
    }
    const bool ok = same == total;
    if (!ok) ++g_bad;
    std::printf("bonus row vs sample_tokens (248,320 logits, top_k 20 / top_p 0.95 / min_p 0.05 / T 1.0): %d of %d identical %s\n",
                same, total, ok ? "-> pass" : "-> FAIL");
}

int main(int argc, char** argv) {
    const int n = argc > 1 ? std::atoi(argv[1]) : 200000;
    const int V = 6;
    const std::vector<float> base = {2.0f, 1.2f, 0.3f, 0.0f, -0.5f, -1.0f};
    auto dep = [base](const Ctx& c) {
        std::vector<float> l = base;
        if (!c.empty()) l[(c.back() + 1) % 6] += 0.8f;
        return l;
    };
    auto logq = [](std::vector<double> q) { std::vector<float> l(q.size()); for (size_t i = 0; i < q.size(); ++i) l[i] = q[i] > 0 ? (float) std::log(q[i]) : -INFINITY; return l; };
    SamplerParams plain; plain.top_k = 64; plain.top_p = 1.0f; plain.min_p = 0.0f; plain.temperature = 1.0f;
    SamplerParams user; user.top_k = 4; user.top_p = 0.9f; user.min_p = 0.05f; user.temperature = 0.7f;
    std::vector<Case> cases;
    cases.push_back({"identical q = p", dep, dep, 3, Rule::Fixed, 0.5, plain});
    cases.push_back({"disjoint supports", dep, [&](const Ctx&) { return logq({0, 0, 0, 0.5, 0.5, 0}); }, 3, Rule::Fixed, 0.5, plain});
    cases.push_back({"swapped ranks", dep, [&](const Ctx& c) { auto l = dep(c); std::reverse(l.begin(), l.end()); return l; }, 3, Rule::Fixed, 0.5, plain});
    cases.push_back({"zero draft support (subset vocab)", dep, [&](const Ctx& c) { auto l = dep(c); l[0] = l[1] = -INFINITY; return l; }, 4, Rule::Fixed, 0.5, plain});
    cases.push_back({"extreme logits (+-80, near-tie)", [](const Ctx&) { return std::vector<float>{80.0f, 79.999f, -80, -80, 0, 1e-3f}; },
                     [](const Ctx&) { return std::vector<float>{80.0f, 80.0f, -80, -80, 0, 0}; }, 2, Rule::Fixed, 0.5, plain});
    cases.push_back({"penalized (same penalty in p and q)", [&](const Ctx& c) { auto l = dep(c); if (!c.empty()) l[c.back()] -= 1.5f; return l; },
                     [&](const Ctx& c) { auto l = dep(c); for (auto& x : l) x *= 0.8f; if (!c.empty()) l[c.back()] -= 1.5f; return l; }, 3, Rule::Fixed, 0.5, plain});
    cases.push_back({"q close to p (temperature 0.8 draft)", dep, [&](const Ctx& c) { auto l = dep(c); for (auto& x : l) x /= 0.8f; return l; }, 4, Rule::Fixed, 0.5, plain});
    cases.push_back({"the chain (top_k 4, top_p 0.9, min_p 0.05, T 0.7)", dep, [&](const Ctx& c) { auto l = dep(c); for (auto& x : l) x /= 0.8f; return l; }, 3, Rule::Fixed, 0.5, user});
    cases.push_back({"K from q alone (draft while max q >= 0.5)", dep, [&](const Ctx& c) { auto l = dep(c); for (auto& x : l) x /= 0.6f; return l; }, 6, Rule::MaxQ, 0.5, plain});
    if (strata::spec::cost_gate().on) {   // round 12: the cost-aware gate (STRATA_COST_GATE=configs/r12-cost-gate.txt)
        cases.push_back({"COST GATE (round 12 table; plain chain)", dep, [&](const Ctx& c) { auto l = dep(c); for (auto& x : l) x /= 0.6f; return l; }, 3, Rule::CostGate, 0.5, plain});
        cases.push_back({"COST GATE (round 12 table; top_k 4 / top_p 0.9 / min_p 0.05 / T 0.7)", dep, [&](const Ctx& c) { auto l = dep(c); for (auto& x : l) x /= 0.8f; return l; }, 3, Rule::CostGate, 0.5, user});
    }
    Case lk{"lookup drafts (point masses 0, 1, 2)", dep, dep, 3, Rule::Lookup, 0.5, plain};
    lk.lookup = {0, 1, 2};
    cases.push_back(lk);
    std::printf("exact speculative sampling, GPU kernels, %d windows per case, V = %d\n", n, V);
    uint64_t seed = 101;
    for (const auto& c : cases) run_case(c, V, n, seed++);
    run_case({"NEGATIVE CONTROL (drop x when q(x) < 0.3)", dep, [&](const Ctx& c) { auto l = dep(c); for (auto& x : l) x /= 0.8f; return l; }, 3, Rule::NegControl, 0.3, plain},
             V, n, 99, true);
    bonus_identity(200);
    std::printf("%s: %d failure(s)\n", g_bad ? "FAILED" : "ALL PASS", g_bad);
    return g_bad ? 1 : 0;
}
