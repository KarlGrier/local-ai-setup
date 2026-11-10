[90002] Title: Niko1221/Strata@v0.2.4: bench/results/2026-10-09-community-rtx-5080-4060ti-0.1.41/README.md lines 108-121 (source code)
URL: https://github.com/Niko1221/Strata/blob/v0.2.4/bench/results/2026-10-09-community-rtx-5080-4060ti-0.1.41/README.md#L108-L121
[OTHER ENGINE: this page describes Strata's Qwen engine; the task is about its DeepSeek engine - its flags, settings and numbers are not the DeepSeek engine's unless that engine's code shows them]

108: - One session each; TTFT from one fresh prompt per size (local prompts, not included). The needle check is a local
109:   120K-token document with six questions.
110: - Where a decode round went (Q8_0, the 5080 + 71 GiB, warm): about 127 ms = GPU ~20 ms + CPU on the RAM experts ~38 ms +
111:   reading the SSD ~68 ms (about 450 MB per round). The drive read 3.7 GB/s on average over the hour of the peer-tier session.
112: - The local file exists because UD-Q5_K_XL itself does not load here: its first shard ends 6 bytes before the aligned
113:   data start the engine's reader computes (#1612 proposes a fix). It is not a published file.
114: - Layer-split placements are not included in this report.
115: 
116: ## Correctness and limitations
117: 
118: - Needles: 6 of 6 at 32k and 128k on both v0.1.41 sets; 6 of 6 at 120K on the stand-ins.
119: - The answers themselves were not graded: temperature 0, a one-paragraph summary request, a 256-token cap.
120: - Not tested: vision, other quantizations of the IQ3_S model, Windows, setup's own configuration for this PC, contexts
121:   above 131,072, `--batch` slots, a layer split, and the 5080 without the helper card.
(bench/results/2026-10-09-community-rtx-5080-4060ti-0.1.41/README.md has 121 lines.)
