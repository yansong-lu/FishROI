#!/usr/bin/env bash
#SBATCH --job-name=fishroi-seg
#SBATCH --array=0-0                       # <<< set to 0-(N-1) for N images (see README)
#SBATCH --partition=<<GPU_PARTITION>>     # <<< your GPU partition
#SBATCH --gres=gpu:1                      # 1 GPU per task (Cellpose uses one)
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=logs/seg_%A_%a.out
# Phase A (GPU): Cellpose segmentation only -> <outdir>/<base>_rois.zip
set -euo pipefail

source "${FISHROI_CACHE:-$HOME/.cache/fishroi}/env.sh"   # MODEL_PATH, FIJI_LAUNCHER, AUTO_DIR
# module load cuda/12.x                                  # <<< if your site needs it
# source /path/to/venv/bin/activate                      # <<< activate the fishroi env (cellpose<4, torch+CUDA)

IMG="$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" images.txt)"   # array index -> line (portable)
OUTDIR="results/$(basename "${IMG%.*}")"
mkdir -p "$OUTDIR" logs

echo "[seg task $SLURM_ARRAY_TASK_ID] $IMG -> $OUTDIR"
python "$AUTO_DIR/fishroi_run_all.py" \
    --image "$IMG" --outdir "$OUTDIR" \
    --model "$MODEL_PATH" --gpu on \
    --seg-channel 1 \
    --segment-only
