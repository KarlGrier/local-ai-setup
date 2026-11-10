#!/usr/bin/env python3
"""port_side_mixer.py — round 14: ledger rows 16 + 17 (STRATA_SIDE_MIXER=1 / =2, fork Eddoursul 34a35db + b063c13) ported
by hand onto v0.1.40.1's verify window, whose mixer #783 rewrote (PR-b exact-T gates, PR-d batched K/V and indexer
appends, PR-f fused per-head norm + RoPE) and S26 extended (QFUSE). The branches carry upstream's own operations; only
the stream they run on changes. Run in the strata-r14 worktree; edits verify.hpp / verify.cpp in place."""
from pathlib import Path


def sub(s, old, new, count=1):
    n = s.count(old)
    assert n == count, (n, old[:120])
    return s.replace(old, new)


H = Path("include/strata/core/verify.hpp")
h = H.read_text()
h = sub(h, "    cudaGraphExec_t exec_nr_[9] = {};   // #871: the doorbell variant of a stage that is all-resident otherwise\n",
        "    cudaGraphExec_t exec_nr_[9] = {};   // #871: the doorbell variant of a stage that is all-resident otherwise\n"
        "    // fork 34a35db (STRATA_SIDE_MIXER=1): the GDN gates and the QSA indexer on a branch of the window's graph beside the\n"
        "    // mixer's projections, joined before the recurrence / the attention\n"
        "    cudaStream_t side_ = nullptr;\n"
        "    cudaEvent_t mfork_ = nullptr, mjoin_ = nullptr;\n"
        "    // fork b063c13 (STRATA_SIDE_MIXER=2): a second branch for the GDN gate projection and the QSA queries' chain\n"
        "    cudaStream_t side2_ = nullptr;\n"
        "    cudaEvent_t pfork_ = nullptr, pjoin_ = nullptr;\n")
H.write_text(h)

V = Path("src/core/verify.cpp")
s = V.read_text()
# lifecycle
s = sub(s, "    if (copy_) { cudaStreamSynchronize(copy_); cudaStreamDestroy(copy_); }\n    if (commit_done_) cudaEventDestroy(commit_done_);\n",
        "    if (copy_) { cudaStreamSynchronize(copy_); cudaStreamDestroy(copy_); }\n"
        "    if (side_) cudaStreamDestroy(side_);\n"
        "    if (side2_) cudaStreamDestroy(side2_);\n"
        "    for (cudaEvent_t e : {mfork_, mjoin_, pfork_, pjoin_})\n"
        "        if (e) cudaEventDestroy(e);\n"
        "    if (commit_done_) cudaEventDestroy(commit_done_);\n")
s = sub(s, "    // E-6: a layer whose routed experts are all resident is planned on the device (STRATA_VERIFY_DEVICE_PLAN=1: on;\n",
        "    if (cudaStreamCreateWithFlags(&side_, cudaStreamNonBlocking) != cudaSuccess ||\n"
        "        cudaEventCreateWithFlags(&mfork_, cudaEventDisableTiming) != cudaSuccess ||\n"
        "        cudaEventCreateWithFlags(&mjoin_, cudaEventDisableTiming) != cudaSuccess ||\n"
        "        cudaStreamCreateWithFlags(&side2_, cudaStreamNonBlocking) != cudaSuccess ||\n"
        "        cudaEventCreateWithFlags(&pfork_, cudaEventDisableTiming) != cudaSuccess ||\n"
        "        cudaEventCreateWithFlags(&pjoin_, cudaEventDisableTiming) != cudaSuccess) {\n"
        "        err = \"verify: the mixer branch's stream / events could not be created\";\n"
        "        return false;\n"
        "    }\n"
        "    // E-6: a layer whose routed experts are all resident is planned on the device (STRATA_VERIFY_DEVICE_PLAN=1: on;\n")
# record_window: the switch
s = sub(s, "    static const bool dec_batch = [] { const char* v = std::getenv(\"STRATA_DEC_BATCH\"); return v == nullptr || std::atoi(v) != 0; }();\n    auto stamp = [&](int64_t l, int i, int grp) {\n",
        "    static const bool dec_batch = [] { const char* v = std::getenv(\"STRATA_DEC_BATCH\"); return v == nullptr || std::atoi(v) != 0; }();\n"
        "    // fork 34a35db: the GDN gates and the QSA indexer beside the projections (STRATA_SIDE_MIXER=1; 0 / unset = in line)\n"
        "    static const int side_mixer_mode = [] { const char* v = std::getenv(\"STRATA_SIDE_MIXER\"); return v ? std::max(0, std::min(2, std::atoi(v))) : 0; }();\n"
        "    const bool side_mixer = side_mixer_mode >= 1;\n"
        "    const bool side_proj = side_mixer_mode >= 2 && !batch_rec_;   // fork b063c13: the GDN gate projection, the QSA queries\n"
        "    auto branch = [&](cudaEvent_t e, cudaStream_t from, cudaStream_t to, const char* what) {\n"
        "        if (cudaEventRecord(e, from) == cudaSuccess && cudaStreamWaitEvent(to, e, 0) == cudaSuccess) return true;\n"
        "        err = std::string(\"verify: the mixer branch could not \") + what;\n"
        "        return false;\n"
        "    };\n"
        "    // a batch window's rows each read their own slot's indexer: in line there\n"
        "    const bool sidem = side_mixer && !batch_rec_;\n"
        "    auto stamp = [&](int64_t l, int i, int grp) {\n")

# ---- GDN: the gates (and with =2 the gate projection) on branches
s = sub(s, """                float* beta = beta_L_ + (size_t) gi * MT * HV;
                if (!q8_attn) native_quantize_q8_1(xm, xq_, (int) N, n, cs);
                native_mmvq(wqkv->native_type, wqkv->native_data, xq_, qkv + (size_t) tb * C, (int) N, (int) C, n, cs);
""", """                float* beta = beta_L_ + (size_t) gi * MT * HV;
                if (sidem) {   // the gates (a few blocks, latency-bound) beside the projections, joined below
                    if (!branch(mfork_, cs, side_, "fork")) return false;
                    gdn_ab_multi(xm, (const uint16_t*) wa->data, (const uint16_t*) wb->data, (const float*) wdt->data,
                                 (const float*) wsa->data, gate + (size_t) tb * HV, beta + (size_t) tb * HV, (int) N,
                                 (int) HV, n, side_);
                    if (cudaEventRecord(mjoin_, side_) != cudaSuccess) { err = "verify: the GDN gates' branch could not join"; return false; }
                }
                if (!q8_attn) native_quantize_q8_1(xm, xq_, (int) N, n, cs);
                if (side_proj) {   // the gate projection (compute-bound for i-quants) beside qkv and the conv
                    if (!branch(pfork_, cs, side2_, "fork")) return false;
                    native_mmvq(wg->native_type, wg->native_data, xq_, z_ + (size_t) tb * ZV, (int) N, (int) ZV, n, side2_);
                    if (cudaEventRecord(pjoin_, side2_) != cudaSuccess) { err = "verify: the gate projection's branch could not join"; return false; }
                }
                native_mmvq(wqkv->native_type, wqkv->native_data, xq_, qkv + (size_t) tb * C, (int) N, (int) C, n, cs);
""")
s = sub(s, """                stamp(l, 3, grp);
                gdn_ab_multi(xm, (const uint16_t*) wa->data, (const uint16_t*) wb->data, (const float*) wdt->data,
                             (const float*) wsa->data, gate + (size_t) tb * HV, beta + (size_t) tb * HV, (int) N, (int) HV,
                             n, cs);
                stamp(l, 4, grp);
                native_mmvq(wg->native_type, wg->native_data, xq_, z_ + (size_t) tb * ZV, (int) N, (int) ZV, n, cs);
                stamp(l, 5, grp);
""", """                stamp(l, 3, grp);
                if (!sidem)
                    gdn_ab_multi(xm, (const uint16_t*) wa->data, (const uint16_t*) wb->data, (const float*) wdt->data,
                                 (const float*) wsa->data, gate + (size_t) tb * HV, beta + (size_t) tb * HV, (int) N,
                                 (int) HV, n, cs);
                stamp(l, 4, grp);
                if (!side_proj) native_mmvq(wg->native_type, wg->native_data, xq_, z_ + (size_t) tb * ZV, (int) N, (int) ZV, n, cs);
                stamp(l, 5, grp);
                if (side_proj && cudaStreamWaitEvent(cs, pjoin_, 0) != cudaSuccess) {
                    err = "verify: the gate projection's branch could not join";
                    return false;
                }
                if (sidem && cudaStreamWaitEvent(cs, mjoin_, 0) != cudaSuccess) {
                    err = "verify: the GDN gates' branch could not join";
                    return false;
                }
""")

# ---- QSA: norm_rope with a stream; the indexer chain and the queries' chain as steps that can run on a branch
s = sub(s, """                auto norm_rope = [&](float* data, const WeightRef* norm, int rows, int cols, const int32_t* pos) {
                    if (fuse_nr && native_norm_rope_usable(cols, (int) s.n_rot)) {
                        native_qsa_rms_norm_rope(data, cols, (const float*) norm->data, data, rows, cols, (int) s.n_rot, EPS,
                                                 rope_scaling(), pos, cs);
                        return;
                    }
                    if (native_qsa_enabled()) native_qsa_rms_norm_weighted(data, (const float*) norm->data, data, cols, rows, EPS, cs);
                    else rms_norm_weighted(data, (const float*) norm->data, rows, cols, EPS, cs);
                    if (native_rope_enabled()) native_rope_apply(data, data, rows, cols, (int) s.n_rot, rope_scaling(), pos, cs);
                    else rope_neox_apply(data, data, rows, cols, (int) s.n_rot, st.cos_tab, st.sin_tab, pos, cs);
                };
""", """                auto norm_rope_on = [&](float* data, const WeightRef* norm, int rows, int cols, const int32_t* pos,
                                        cudaStream_t ns) {
                    if (fuse_nr && native_norm_rope_usable(cols, (int) s.n_rot)) {
                        native_qsa_rms_norm_rope(data, cols, (const float*) norm->data, data, rows, cols, (int) s.n_rot, EPS,
                                                 rope_scaling(), pos, ns);
                        return;
                    }
                    if (native_qsa_enabled()) native_qsa_rms_norm_weighted(data, (const float*) norm->data, data, cols, rows, EPS, ns);
                    else rms_norm_weighted(data, (const float*) norm->data, rows, cols, EPS, ns);
                    if (native_rope_enabled()) native_rope_apply(data, data, rows, cols, (int) s.n_rot, rope_scaling(), pos, ns);
                    else rope_neox_apply(data, data, rows, cols, (int) s.n_rot, st.cos_tab, st.sin_tab, pos, ns);
                };
                auto norm_rope = [&](float* data, const WeightRef* norm, int rows, int cols, const int32_t* pos) {
                    norm_rope_on(data, norm, rows, cols, pos, cs);
                };
""")

OLD_QSA = s[s.index("                const bool qb = dec_batch && n > 1 && native_qsa_enabled() && native_rope_enabled() && !st.kv_q4;\n"):
            s.index("                stamp(l, 10, grp);\n")]
NEW_QSA = '''                const bool qb = dec_batch && n > 1 && native_qsa_enabled() && native_rope_enabled() && !st.kv_q4;
                // the indexer: its key projection, the tail's snapshot, its keys appended, its query projection, norm and
                // RoPE, the block scores and the top-k - all of it needs only the mixer's input and the indexer's own
                // state, so with STRATA_SIDE_MIXER=1 it runs on a branch beside the attention's projections (fork 34a35db;
                // round 14: each step is v0.1.40's own - #783 PR-d's batched append, PR-f's fused norm + RoPE)
                auto idx_key = [&](cudaStream_t ns) {
                    if (qb) bf16_gemv_fp32_mmvf_multi(mixed_ + tb * N, N, (const uint16_t*) wik->data, idx_raw + tb * ID, ID, N, ID, n, ns);
                    else for (int t = tb; t < te; ++t)
                        bf16_gemv_fp32_mmvf(mixed_ + t * N, (const uint16_t*) wik->data, idx_raw + t * ID, (int) N, (int) ID, ns);
                };
                auto idx_snap = [&](cudaStream_t ns) {
                    if (batch_rec_) {   // snapshot each slot's indexer tail before its first proposed row
                        for (int t = tb; t < te; ++t)
                            if (t == tb || brow_[t] != brow_[t - 1])
                                copy_from_mapped(tail_snap_b_ + ((size_t) brow_[t] * nQall + qi) * TS,
                                                 slot_ss(t).qsa_states[qi].idx_tail, TS, ns);
                    } else
                    if (grp == 0) copy_from_mapped(tail_snap_ + (size_t) qi * TS, st.idx_tail, TS, ns);
                };
                auto idx_append = [&](cudaStream_t ns) {
                    if (dec_batch && !g_no_batch_kv && !batch_rec_) {
                        const QsaIndexerBuffers ib{st.idx_tail, st.idx_dead, st.idx_pooled, st.idx_block_pos};
                        native_qsa_indexer_append_steps(idx_raw + tb * ID, step_ + tb * kStepCount + kStepPos, kStepCount,
                                                        n, 0, (const float*) wikn->data, EPS, ib, s, st.max_cells,
                                                        rope_scaling(), ns);
                    } else {
                        for (int t = tb; t < te; ++t) {
                            const QsaState& sx = slot_ss(t).qsa_states[qi];
                            const QsaIndexerBuffers ib{sx.idx_tail, sx.idx_dead, sx.idx_pooled, sx.idx_block_pos};
                            native_qsa_indexer_append(idx_raw + t * ID, step_ + t * kStepCount + kStepPos, 0,
                                                      (const float*) wikn->data, EPS, ib, s, sx.max_cells,
                                                      rope_scaling(), ns);
                        }
                    }
                };
                auto idx_query = [&](cudaStream_t ns) {
                    if (qb) {
                        bf16_gemv_fp32_mmvf_multi(mixed_ + tb * N, N, (const uint16_t*) wiq->data, qidx_ + tb * IQ * ID, IQ * ID,
                                                  N, IQ * ID, n, ns);
                        norm_rope_on(qidx_ + tb * IQ * ID, wiqn, (int) (n * IQ), (int) ID, pos_i + tb * IQ, ns);
                    } else
                        for (int t = tb; t < te; ++t) {
                            float* qx = qidx_ + t * IQ * ID;
                            bf16_gemv_fp32_mmvf(mixed_ + t * N, (const uint16_t*) wiq->data, qx, (int) N, (int) (IQ * ID), ns);
                            norm_rope_on(qx, wiqn, (int) IQ, (int) ID, pos_ + t * NH, ns);
                        }
                };
                auto idx_select = [&](cudaStream_t ns) {
                    qsa_block_scores(st.idx_pooled, st.idx_dead, qidx_ + tb * IQ * ID, step_ + tb * kStepCount, n, max_blocks_,
                                     s, scores_ + (size_t) tb * max_blocks_, ns);
                    qsa_block_topk(scores_ + (size_t) tb * max_blocks_, step_ + tb * kStepCount, n, max_blocks_, cap_, s,
                                   sel_ + (size_t) tb * cap_, ns);
                };
                // the attention's queries: projection, the q / gate split, norm and RoPE (#783 PR-f: in one launch that
                // reads q out of the q|gate rows), rotated for a rotated KV
                auto q_chain = [&](cudaStream_t ns) -> bool {
                    native_mmvq(wq->native_type, wq->native_data, xq_, qfull_ + tb * NH * 2 * HD, (int) N, (int) (NH * 2 * HD),
                                n, ns);
                    if (qb) {
                        if (fuse_nr) {   // the q/gate split reads q straight out of the q|gate rows (stride 2 * HD)
                            native_qsa_rms_norm_rope(qfull_ + tb * NH * 2 * HD, (int) (2 * HD), (const float*) wqn->data,
                                                     qcur_ + tb * NH * HD, (int) (n * NH), (int) HD, (int) s.n_rot, EPS,
                                                     rope_scaling(), pos_ + tb * NH, ns);
                        } else {
                            if (cudaMemcpy2DAsync(qcur_ + tb * NH * HD, (size_t) HD * 4, qfull_ + tb * NH * 2 * HD, (size_t) HD * 2 * 4,
                                                  (size_t) HD * 4, (size_t) (n * NH), cudaMemcpyDeviceToDevice, ns) != cudaSuccess) {
                                err = "verify: the q/gate split failed";
                                return false;
                            }
                            norm_rope_on(qcur_ + tb * NH * HD, wqn, (int) (n * NH), (int) HD, pos_ + tb * NH, ns);
                        }
                        if (st.kv_rot) fwht256_inplace_cuda(qcur_ + tb * NH * HD, (int64_t) n * NH, ns);   // <Hq, Hk> = <q, k>
                    } else {
                        for (int t = tb; t < te; ++t) {
                            float* qc = qcur_ + t * NH * HD;
                            if (fuse_nr) {
                                native_qsa_rms_norm_rope(qfull_ + t * NH * 2 * HD, (int) (2 * HD), (const float*) wqn->data, qc,
                                                         (int) NH, (int) HD, (int) s.n_rot, EPS, rope_scaling(), pos_ + t * NH, ns);
                            } else {
                                if (cudaMemcpy2DAsync(qc, (size_t) HD * 4, qfull_ + t * NH * 2 * HD, (size_t) HD * 2 * 4,
                                                      (size_t) HD * 4, (size_t) NH, cudaMemcpyDeviceToDevice, ns) != cudaSuccess) {
                                    err = "verify: the q/gate split failed";
                                    return false;
                                }
                                norm_rope_on(qc, wqn, (int) NH, (int) HD, pos_ + t * NH, ns);
                            }
                            if (st.kv_rot) fwht256_inplace_cuda(qc, NH, ns);   // <Hq, Hk> = <q, k>
                        }
                    }
                    return true;
                };
                if (sidem) {
                    if (!branch(mfork_, cs, side_, "fork")) return false;
                    idx_key(side_);
                    idx_snap(side_);
                    idx_append(side_);
                    idx_query(side_);
                    idx_select(side_);
                    if (cudaEventRecord(mjoin_, side_) != cudaSuccess) { err = "verify: the indexer's branch could not join"; return false; }
                }
                if (!q8_attn) native_quantize_q8_1(xm, xq_, (int) N, n, cs);
                if (side_proj) {   // the queries beside the keys and values (fork b063c13)
                    if (!branch(pfork_, cs, side2_, "fork") || !q_chain(side2_)) return false;
                    if (cudaEventRecord(pjoin_, side2_) != cudaSuccess) { err = "verify: the queries' branch could not join"; return false; }
                }
                if (!sidem) idx_key(cs);
                stamp(l, 7, grp);
                native_mmvq(wk->native_type, wk->native_data, xq_, kcur_ + tb * NKV * HD, (int) N, (int) (NKV * HD), n, cs);
                native_mmvq(wv->native_type, wv->native_data, xq_, vcur_ + tb * NKV * HD, (int) N, (int) (NKV * HD), n, cs);
                if (qb) norm_rope(kcur_ + tb * NKV * HD, wkn, (int) (n * NKV), (int) HD, pos_k + tb * NKV);
                else for (int t = tb; t < te; ++t) norm_rope(kcur_ + t * NKV * HD, wkn, (int) NKV, (int) HD, pos_ + t * NH);
                if (st.kv_rot) {   // K and V rotated before they are stored (kv_q4.hpp)
                    fwht256_inplace_cuda(kcur_ + tb * NKV * HD, (int64_t) n * NKV, cs);
                    fwht256_inplace_cuda(vcur_ + tb * NKV * HD, (int64_t) n * NKV, cs);
                } else if (st.kv_hybrid) {   // K8V4: only V is rotated
                    fwht256_inplace_cuda(vcur_ + tb * NKV * HD, (int64_t) n * NKV, cs);
                }
                stamp(l, 8, grp);
                if (!sidem) idx_snap(cs);
'''
# the K/V append block (upstream's, unchanged) sits between the snapshot and the indexer append
kv_start = OLD_QSA.index("                // #783 PR-d (stuchapin909): the window's K/V cells in one launch per pool")
kv_end = OLD_QSA.index("                if (dec_batch && !g_no_batch_kv && !batch_rec_) {\n                    const QsaIndexerBuffers ib{")
KV = OLD_QSA[kv_start:kv_end]
NEW_QSA += KV + '''                if (!sidem) idx_append(cs);
                stamp(l, 9, grp);
                if (!side_proj && !q_chain(cs)) return false;
                if (!sidem) idx_query(cs);
'''
s = s.replace(OLD_QSA, NEW_QSA, 1)

# the selection: on the branch (joined here) or in line
s = sub(s, """                } else {
                qsa_block_scores(st.idx_pooled, st.idx_dead, qidx_ + tb * IQ * ID, step_ + tb * kStepCount, n, max_blocks_,
                                 s, scores_ + (size_t) tb * max_blocks_, cs);
                qsa_block_topk(scores_ + (size_t) tb * max_blocks_, step_ + tb * kStepCount, n, max_blocks_, cap_, s,
                               sel_ + (size_t) tb * cap_, cs);
                stamp(l, 11, grp);
""", """                } else {
                if (!sidem) idx_select(cs);
                else if (cudaStreamWaitEvent(cs, mjoin_, 0) != cudaSuccess) {
                    err = "verify: the indexer's branch could not join";
                    return false;
                }
                if (side_proj && cudaStreamWaitEvent(cs, pjoin_, 0) != cudaSuccess) {
                    err = "verify: the queries' branch could not join";
                    return false;
                }
                stamp(l, 11, grp);
""")
V.write_text(s)
print("side mixer ported")
