cd /home/USER/ai-speed-testing/strata-compare
SCREEN_EXTRA="edit mtside" scripts/screen.sh N-n3x configs/N-n3x.json /home/USER/ai-speed-testing/strata-compare/strata-v0111/serve/server.py
SCREEN_EXTRA="edit" scripts/screen.sh N-n3sd0 configs/N-n3sd0.json /home/USER/ai-speed-testing/strata-compare/strata-v0111/serve/server.py
scripts/screen.sh N-n3kv0 configs/N-n3kv0.json /home/USER/ai-speed-testing/strata-compare/strata-v0111/serve/server.py
scripts/screen.sh N-n3q4 configs/N-n3q4.json /home/USER/ai-speed-testing/strata-compare/strata-v0111/serve/server.py
SCREEN_EXTRA="mtside" scripts/screen.sh N-n3stash configs/N-n3stash.json /home/USER/ai-speed-testing/strata-compare/strata-v0111/serve/server.py
scripts/tf_run.sh N-n0 configs/N-n0.json math corpus
scripts/tf_run.sh N-n3 configs/N-n3.json math corpus
