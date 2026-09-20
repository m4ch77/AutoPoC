#!/usr/bin/env bash
# Container entrypoint for the combined agent.
#
# If a local model runtime (ollama) was baked into the image, start it so the
# LocalLLMBrain can reach http://localhost:11434 offline. Otherwise the agent
# relies on the cloud LLM (ANTHROPIC_API_KEY, the grading sandbox's permitted
# LLM network exception) and/or the fully-offline fuzzer + heuristics.
set -euo pipefail

if command -v ollama >/dev/null 2>&1; then
  ollama serve >/tmp/ollama.log 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf http://localhost:11434/ >/dev/null 2>&1 && break
    sleep 1
  done
fi

exec python3 /opt/track04/agent/agent_combined.py "$@"
