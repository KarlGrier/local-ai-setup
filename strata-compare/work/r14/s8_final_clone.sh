#!/bin/bash
# s8_final_clone.sh — round 14 step 8: the final series (patches/r14c34f: our Stop-watcher rows 7 / 10 dropped for
# upstream's #879 - server code only) cloned clean and built by the runbook. The engine's source is the 36-commit
# build's (only serve/server.py differs) -> compare the binary; C*14's checkout moves to r14-final; assets re-made;
# the server tests of the clean clone.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
bringup/runbook.sh r14f clone build
echo "engine: $(sha256sum bringup/out/r14f/engine-patched/strata | cut -c1-16) (the 36-commit build: $(sha256sum engine-cstar14/strata | cut -c1-16)); $(cmp -s bringup/out/r14f/engine-patched/strata engine-cstar14/strata && echo identical || echo 'different bytes (same C++ source)')"
echo "tree: $(git -C bringup/out/r14f/strata-patched rev-parse HEAD^{tree}) = r14-final $(git -C strata rev-parse r14-final^{tree})"
git -C strata-cstar14 checkout -q --detach r14-final
work/r14/build-cstar14.sh 2>&1 | grep -v '^[<>]' | tail -3
(cd bringup/out/r14f/strata-patched && timeout 900 $WS/.venv/bin/python -m unittest discover -s serve -t . 2>&1 | tail -1)
