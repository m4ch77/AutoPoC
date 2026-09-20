#!/usr/bin/env bash
# Container entrypoint for the combined agent.
#
# The agent uses the cloud LLM (ANTHROPIC_API_KEY, the grading sandbox's
# permitted LLM network exception) when a key is present, and always keeps the
# fully-offline fuzzer + reentrancy + heuristics as deterministic fallbacks.
set -euo pipefail

exec python3 /opt/track04/agent/agent_combined.py "$@"
