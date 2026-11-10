# bench2.py - the two staged edits merged (10-29)
staging/phase5/bench2.py (the p5 question set, its answers in the string cross-check, `next` with each step's limits) and
staging/runner-bench/tools/bench2.py (item 7 test runs write run/paid-run.json, the search-fallback refusal lifted for
item 7 runs, `next --wide`, the model-profile check) both start from the live tools/bench2.py. `git merge-file` merged them
with no conflict into bench2.py here; install THIS file (not either single copy), backup tools/bench2.py.before-p5rb, in the
install that comes last of the two (runner-bench after C3; Phase 5 at its start). Line counts: merged diff = sum of both.
