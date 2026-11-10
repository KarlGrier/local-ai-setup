#!/bin/bash
# make-patches.sh — regenerate the patch files from the edited install: diff of the pristine wheel (src/whl) against
# the venv's local_deep_research, one patch per area. Run after changing the installed code.
set -euo pipefail
WS=/home/USER/ai/deep-research
A=$WS/src/whl; B=$WS/.venv/lib/python3.12/site-packages
cd $WS/patches/ldr
mk() {  # name files...
  local name=$1; shift; : > $name
  for f in "$@"; do
    if [ -e "$A/$f" ]; then diff -uN --label "a/$f" --label "b/$f" "$A/$f" "$B/$f" >> $name || true
    else diff -uN --label "/dev/null" --label "b/$f" /dev/null "$B/$f" >> $name || true; fi
  done
  echo "$name: $(grep -c '^+[^+]' $name) added / $(grep -c '^-[^-]' $name) removed lines"
}
L=local_deep_research
mk 0001-deep-package.patch $(cd $B && ls $L/deep/*.py | sort)
mk 0002-langgraph-agent-deep-mode.patch $L/advanced_search_system/strategies/langgraph_agent_strategy.py
mk 0003-fetch-deep-mode.patch $L/advanced_search_system/tools/fetch/__init__.py
# anything else changed that is not in a patch?
diff -rq --exclude=__pycache__ --exclude=themes.css $A/$L $B/$L | grep -v -e 'deep' -e 'langgraph_agent_strategy.py' \
  -e 'tools/fetch/__init__.py' && echo "WARNING: changes above are not in any patch" || true
