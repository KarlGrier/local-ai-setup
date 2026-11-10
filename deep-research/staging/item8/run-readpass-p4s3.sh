#!/bin/bash
# Karl 10-29: item 6's read pass on p4s3's cited pages (o01-o03) before the item 8 merge - network only, no model, no GPU
for q in o01 o02 o03; do
  echo "$(date '+%m-%d %H:%M:%S') start $q" >> /home/USER/ai/deep-research/staging/item8/readpass-p4s3.log
  nice -n 19 /home/USER/ai/deep-research/.venv/bin/python -I /home/USER/ai/deep-research/tools/read-pass.py /home/USER/ai/deep-research/results/bench2/runs/screen-deep-p4s3/$q --out /home/USER/ai/deep-research/staging/item8/readpass-p4s3/$q --max-minutes 30 >> /home/USER/ai/deep-research/staging/item8/readpass-p4s3.log 2>&1
  echo "$(date '+%m-%d %H:%M:%S') end $q rc $?" >> /home/USER/ai/deep-research/staging/item8/readpass-p4s3.log
done
echo "$(date '+%m-%d %H:%M:%S') read pass p4s3 done" >> /home/USER/ai/deep-research/staging/item8/readpass-p4s3.log
