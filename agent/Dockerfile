# TRUST404 Track 04 - combined exploit-proving agent (finished image).
#
# Build context MUST be the bundle root (parent of agent/ and harness/):
#   docker build -f agent/Dockerfile -t autopoc .
#
# Run (grading style): the exploit runs LOCALLY (no fork); the only permitted
# network is the LLM API call. Pass a key to enable the strong cloud brain:
#   docker run --rm -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
#     -v "$PWD/../trust404-track04-participant/targets/OpenVault:/work/target:ro" \
#     -v "$PWD/out:/work/out" autopoc \
#     --contract /work/target/src/OpenVault.sol \
#     --invariants /work/target/Invariants.sol \
#     --manifest  /work/target/manifest.json \
#     --out /work/out --timeout 300 --seed 42 --max-attempts 8
# With no key / no network it degrades to the offline fuzzer + heuristics.
#
# Brains at runtime: quick fuzzer -> cloud LLM (if key) -> local LLM (if baked)
# -> heuristics, all behind the forge verification gate.

FROM python:3.12-slim AS base

# Pin the toolchain for determinism (gate ②). Align FOUNDRY_VERSION with the
# grading image; the organizer baseline verified v1.0.0. solc 0.8.24 is fetched
# by `forge build` (harness/foundry.toml) and cached into the image.
ARG FOUNDRY_VERSION=v1.0.0
# Optional: bake a fully-offline local model (large image). Off by default; the
# default relies on the permitted cloud LLM API + offline fuzzer/heuristics.
ARG BAKE_LOCAL_MODEL=0
ARG LOCAL_MODEL=qwen2.5-coder:7b

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git build-essential bash \
    && rm -rf /var/lib/apt/lists/*

ENV FOUNDRY_DIR=/root/.foundry
ENV PATH="${FOUNDRY_DIR}/bin:${PATH}"
RUN curl -L https://foundry.paradigm.xyz | bash \
    && foundryup --install "${FOUNDRY_VERSION}" \
    && forge --version

WORKDIR /opt/track04
COPY harness /opt/track04/harness
COPY agent /opt/track04/agent

# Build the harness so solc 0.8.24 + forge-std are cached (offline at run time).
RUN cd /opt/track04/harness \
    && rm -rf lib/forge-std \
    && git clone --depth 1 https://github.com/foundry-rs/forge-std lib/forge-std \
    && forge build

# Optional: bake ollama + a local code model for a fully-offline LLM brain.
RUN if [ "${BAKE_LOCAL_MODEL}" = "1" ]; then \
      curl -fsSL https://ollama.com/install.sh | sh \
      && (ollama serve >/tmp/ollama.log 2>&1 &) \
      && sleep 5 \
      && ollama pull "${LOCAL_MODEL}"; \
    fi

ENV TRUST404_HARNESS_DIR=/opt/track04/harness
ENV FOUNDRY_OFFLINE=true
ENV TRUST404_LLM_MODEL=${LOCAL_MODEL}

RUN chmod +x /opt/track04/agent/entrypoint.sh
ENTRYPOINT ["bash", "/opt/track04/agent/entrypoint.sh"]
