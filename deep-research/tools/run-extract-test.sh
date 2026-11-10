#!/bin/bash
# run-extract-test.sh — the extraction-effort test as a background queue: run all tasks at low/medium/xhigh, then the
# blind judge, then the report. Resumable. Output: results/extract-effort/{outputs,judge}.jsonl, summary.{json,md}
cd /home/USER/ai/deep-research
export LDR_DEEP_TOKENIZER_DIR=$PWD/deep/tokenizer TMPDIR=$PWD/tmp PYTHONWARNINGS=ignore
D=results/extract-effort
.venv/bin/python tools/extract-effort-test.py run $D && .venv/bin/python tools/extract-effort-test.py judge $D && \
  .venv/bin/python tools/extract-effort-test.py report $D
echo "done $(date -Is)"
