#!/usr/bin/env bash
#SBATCH --job-name=fishroi-analyze
#SBATCH --array=0-0                       # <<< same range as 01_segment.sbatch
#SBATCH --partition=<<CPU_PARTITION>>     # <<< your CPU partition (no GPU needed here)
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G                         # large images: FIJI heap is set from --mem below
#SBATCH --time=01:00:00
#SBATCH --output=logs/analyze_%A_%a.out
# Phase B (CPU): FIJI-identical measure + heatmap + Julia CoV, from the (optionally curated) zip.
set -euo pipefail

source "${FISHROI_CACHE:-$HOME/.cache/fishroi}/env.sh"   # MODEL_PATH, FIJI_LAUNCHER, AUTO_DIR
# source /path/to/venv/bin/activate                      # <<< same fishroi env
# module load julia/1.10                                 # <<< if CoV step is wanted and Julia is a module
export GKSwstype=100                                     # headless GR (belt-and-suspenders; run_all also sets it)

IMG="$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" images.txt)"   # array index -> line (portable)
OUTDIR="results/$(basename "${IMG%.*}")"
ROIZIP="$OUTDIR/$(basename "${IMG%.*}")_rois.zip"

echo "[analyze task $SLURM_ARRAY_TASK_ID] $IMG  (roizip $ROIZIP)"
python "$AUTO_DIR/fishroi_run_all.py" \
    --image "$IMG" --outdir "$OUTDIR" \
    --roizip "$ROIZIP" \
    --fiji "$FIJI_LAUNCHER" \
    --mem 90% \
    --julia-script "$AUTO_DIR/../skill/fishROI_v2/MuscleMosaicism_v3.jl"   # drop this line to skip CoV
