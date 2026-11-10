| comparison | text | ppl A | ppl B | mean NLL A → B | B − A (nats/token) | tokens changed | flips A-good/B-bad · A-bad/B-good |
|---|---|---|---|---|---|---|---|
| llama.cpp: ubatch 4096 → 2048 | math | 1.3337 | 1.3337 | 0.288 → 0.288 | +0.0000 ± 0.0000 | 0 of 1536 | 0 · 0 |
| llama.cpp: ubatch 4096 → 2048 | corpus | 1.4729 | 1.4729 | 0.387 → 0.387 | +0.0000 ± 0.0000 | 0 of 1536 | 0 · 0 |
| llama.cpp: ubatch 4096 → 2048 | long16k | 14.2184 | 16.9500 | 2.655 → 2.830 | +0.1757 ± 0.0275 | 1519 of 1536 | 3 · 2 |
| llama.cpp: ubatch 4096 → 2048 | long24k | 24.4186 | 25.6488 | 3.195 → 3.244 | +0.0492 ± 0.0271 | 1535 of 1536 | 1 · 2 |
