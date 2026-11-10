#!/bin/bash
# written by install-ldr-fixes.sh 2026-11-05 11:13:52: restores every file it changed
set -u
cp -p '/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages/local_deep_research/advanced_search_system/strategies/langgraph_agent_strategy.py.before-ldrfix' '/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages/local_deep_research/advanced_search_system/strategies/langgraph_agent_strategy.py'
cp -p '/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages/local_deep_research/advanced_search_system/tools/fetch/__init__.py.before-ldrfix' '/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages/local_deep_research/advanced_search_system/tools/fetch/__init__.py'
cp -p '/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages/local_deep_research/deep/checks.py.before-ldrfix' '/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages/local_deep_research/deep/checks.py'
rm -f '/home/USER/ai/deep-research/.venv/lib/python3.12/site-packages/local_deep_research/deep/memwatch.py'
cp -p '/home/USER/ai/deep-research/tools/research-runner.py.before-ldrfix' '/home/USER/ai/deep-research/tools/research-runner.py'
cp -p '/home/USER/ai/deep-research/tools/bench2-queue.sh.before-ldrfix' '/home/USER/ai/deep-research/tools/bench2-queue.sh'
cp -p '/home/USER/ai/deep-research/patches/ldr/0001-deep-package.patch.before-ldrfix' '/home/USER/ai/deep-research/patches/ldr/0001-deep-package.patch'
cp -p '/home/USER/ai/deep-research/patches/ldr/0002-langgraph-agent-deep-mode.patch.before-ldrfix' '/home/USER/ai/deep-research/patches/ldr/0002-langgraph-agent-deep-mode.patch'
cp -p '/home/USER/ai/deep-research/patches/ldr/0003-fetch-deep-mode.patch.before-ldrfix' '/home/USER/ai/deep-research/patches/ldr/0003-fetch-deep-mode.patch'
echo 'UNDO done: files restored (the *.before-ldrfix backups are kept)'
