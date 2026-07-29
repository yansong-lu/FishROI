#!/usr/bin/env bash
# Run ONCE on the login node (or any node with network) before submitting the arrays.
# Stages the rerio model + a Fiji install into a SHARED cache so the compute-node array
# tasks never download anything (avoids N concurrent downloads and install races).
set -euo pipefail

# --- edit these two lines ---
export FISHROI_CACHE="${FISHROI_CACHE:-$HOME/.cache/fishroi}"   # must be on shared storage
AUTO_DIR="$(cd "$(dirname "$0")/.." && pwd)"                    # the automation/ directory
# ----------------------------

mkdir -p "$FISHROI_CACHE"
echo "FISHROI_CACHE=$FISHROI_CACHE"

# rerio model -> $FISHROI_CACHE/rerio_model  (md5-verified)
MODEL_PATH="$(python "$AUTO_DIR/fetch_model.py")"
echo "MODEL_PATH=$MODEL_PATH"

# Fiji -> $FISHROI_CACHE/Fiji/...  (found if already installed, else downloaded, sha256-verified)
FIJI_LAUNCHER="$(python "$AUTO_DIR/fiji_setup.py")"
echo "FIJI_LAUNCHER=$FIJI_LAUNCHER"

# Persist the resolved paths for the sbatch scripts to source.
cat > "$FISHROI_CACHE/env.sh" <<EOF
export FISHROI_CACHE="$FISHROI_CACHE"
export MODEL_PATH="$MODEL_PATH"
export FIJI_LAUNCHER="$FIJI_LAUNCHER"
export AUTO_DIR="$AUTO_DIR"
EOF
echo "wrote $FISHROI_CACHE/env.sh  (sbatch scripts source this)"
echo "Now create images.txt (one image path per line) and submit (see README.md)."
