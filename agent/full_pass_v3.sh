#!/usr/bin/env bash
# Final full re-confirmation on the V3 image: public 6 + ported 8 (cloud on,
# default chain) + determinism. This is the "final submission image" evidence.
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "### PUBLIC (V3, cloud) ###"
bash agent/run_compenv.sh public
echo
echo "### PORTED (V3, cloud) ###"
bash agent/run_compenv.sh ported
echo
echo "### DETERMINISM (V3: offline N=3 + cloud cache replay) ###"
bash agent/det_check.sh
echo "FULL_PASS_V3_DONE"
