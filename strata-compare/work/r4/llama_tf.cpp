// llama_tf.cpp — round 4: teacher-forced scoring with an as-is llama.cpp build (linked against its own libllama /
// libllama-common, compiled here; nothing in that build's folder is touched).  The same measurement as Strata's
// --teacher-force: a prompt is read as context (not scored), then every token of a fixed text is scored,
// NLL_i = -log p(text[i] | prompt, text[<i]), one value per line (the format of results/tf-*.nll).
//
//   llama_tf --tf PROMPT TEXT OUT [--tf PROMPT TEXT OUT ...] [llama-server's model/context flags: -m, -c, -b, -ub, -fa,
//            -ctk, -ctv, -ot, --fit, -ngl, -lm, --lazy-mode, ...]
//
// PROMPT / TEXT: comma-separated token ids (work/prof/tf-*.prompt / .text).  Several triples run in one process (the
// KV cache is cleared in between), so the model loads once.  Tokens are fed in n_batch pieces from position 0 like
// llama-server's prompt processing; logits are requested only for the positions that predict a text token.
#include "arg.h"
#include "common.h"
#include "llama.h"

#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

static std::vector<llama_token> read_ids(const std::string & path) {
    std::ifstream f(path);
    std::stringstream ss;
    ss << f.rdbuf();
    std::vector<llama_token> v;
    std::string s = ss.str(), cur;
    for (char c : s) {
        if (c == ',' || c == '\n' || c == ' ') {
            if (!cur.empty()) { v.push_back((llama_token) std::stol(cur)); cur.clear(); }
        } else {
            cur += c;
        }
    }
    if (!cur.empty()) v.push_back((llama_token) std::stol(cur));
    return v;
}

int main(int argc, char ** argv) {
    struct Job { std::string prompt, text, out; };
    std::vector<Job> jobs;
    std::vector<char *> rest{argv[0]};
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--tf") == 0 && i + 3 < argc) {
            jobs.push_back({argv[i + 1], argv[i + 2], argv[i + 3]});
            i += 3;
        } else {
            rest.push_back(argv[i]);
        }
    }
    if (jobs.empty()) { std::fprintf(stderr, "usage: llama_tf --tf PROMPT TEXT OUT [...] [llama flags]\n"); return 2; }
    common_params params;
    // the server's flag set, so llama-server's exact command line (placement, lazy n-gram table, KV types) parses
    if (!common_params_parse((int) rest.size(), rest.data(), params, LLAMA_EXAMPLE_SERVER)) return 1;
    llama_backend_init();
    llama_numa_init(params.numa);
    auto init = common_init_from_params(params);
    llama_model * model = init->model();
    llama_context * ctx = init->context();
    if (model == nullptr || ctx == nullptr) { std::fprintf(stderr, "llama_tf: model/context init failed\n"); return 1; }
    const llama_vocab * vocab = llama_model_get_vocab(model);
    const int n_vocab = llama_vocab_n_tokens(vocab);
    const int n_batch = (int) llama_n_batch(ctx);
    std::fprintf(stderr, "llama_tf: n_ctx %u, n_batch %d, n_ubatch %u, vocab %d\n", llama_n_ctx(ctx), n_batch,
                 llama_n_ubatch(ctx), n_vocab);

    for (const Job & job : jobs) {
        const std::vector<llama_token> P = read_ids(job.prompt), X = read_ids(job.text);
        std::vector<llama_token> all(P);
        all.insert(all.end(), X.begin(), X.end());
        const int n_p = (int) P.size(), N = (int) all.size();
        if (n_p < 1 || X.empty() || N > (int) llama_n_ctx(ctx)) { std::fprintf(stderr, "llama_tf: bad sizes\n"); return 1; }
        llama_memory_clear(llama_get_memory(ctx), true);
        std::vector<double> nll((size_t) X.size(), 0.0);
        std::vector<int> top1((size_t) X.size(), 0);
        llama_batch batch = llama_batch_init(n_batch, 0, 1);
        const auto t0 = ggml_time_us();
        for (int start = 0; start < N - 1; start += n_batch) {
            const int end = std::min(start + n_batch, N - 1);   // the last token only gets predicted, never fed
            common_batch_clear(batch);
            for (int j = start; j < end; ++j) common_batch_add(batch, all[j], j, {0}, j >= n_p - 1);
            if (llama_decode(ctx, batch) != 0) { std::fprintf(stderr, "llama_tf: decode failed at %d\n", start); return 1; }
            for (int j = std::max(start, n_p - 1); j < end; ++j) {
                const float * lg = llama_get_logits_ith(ctx, j - start);
                double mx = lg[0];
                int arg = 0;
                for (int v = 1; v < n_vocab; ++v) if (lg[v] > mx) { mx = lg[v]; arg = v; }
                double s = 0.0;
                for (int v = 0; v < n_vocab; ++v) s += std::exp((double) lg[v] - mx);
                const int k = j + 1 - n_p;                          // text index predicted at position j
                nll[(size_t) k] = (mx + std::log(s)) - (double) lg[all[j + 1]];
                top1[(size_t) k] = arg == all[j + 1];
            }
        }
        llama_batch_free(batch);
        const double secs = (ggml_time_us() - t0) / 1e6;
        FILE * f = std::fopen(job.out.c_str(), "w");
        double sum = 0.0;
        int hits = 0;
        for (size_t k = 0; k < nll.size(); ++k) { std::fprintf(f, "%.6f\n", nll[k]); sum += nll[k]; hits += top1[k]; }
        std::fclose(f);
        std::printf("llama_tf %s: prompt %d + text %zu tokens in %.1f s: teacher-forced ppl %.4f, mean NLL %.4f, "
                    "top-1 %.1f %%\n", job.text.c_str(), n_p, X.size(), secs, std::exp(sum / nll.size()),
                    sum / nll.size(), 100.0 * hits / nll.size());
        std::fflush(stdout);
    }
    llama_backend_free();
    return 0;
}
