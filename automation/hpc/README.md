# FishROI on HPC (generic SLURM)

Batch the pipeline over many images, using **GPU nodes only for Cellpose** and **CPU nodes for the
FIJI + Julia analysis**. The split is the same ROI-zip checkpoint the pipeline uses everywhere:

```
01_segment.sbatch   GPU array   Phase A: image -> <base>_rois.zip     (Cellpose, one GPU/task)
        │
02_analyze.sbatch   CPU array   Phase B: zip  -> measure + heatmap + CoV   (headless FIJI + Julia)
```

Because Cellpose over many images is embarrassingly parallel, each array task handles one image.
The GPU stays busy only during segmentation; the slower ImageJ/Julia work runs on cheap CPU nodes.

## One-time setup (login node, has network)

1. Install the env once (shared location): `pip install "cellpose<4" torch tifffile numpy pandas
   scikit-image scipy matplotlib roifile opencv-python-headless` (+ Julia with
   `DataFrames CSV Plots PyCall` and `read-roi` if you want CoV). Use a CUDA torch build for GPU.
2. Point the cache at **shared storage** and pre-stage the model + Fiji (avoids N concurrent
   downloads / install races on the compute nodes):
   ```bash
   export FISHROI_CACHE=/shared/path/fishroi        # must be visible from all nodes
   bash 00_prestage.sh                              # writes $FISHROI_CACHE/env.sh
   ```
3. List your images, one path per line:
   ```bash
   ls /data/mysamples/*.tif > images.txt
   N=$(wc -l < images.txt)
   ```

## Submit

Edit the `<<GPU_PARTITION>>` / `<<CPU_PARTITION>>` placeholders and set `--array=0-$((N-1))` in both
sbatch files, then:

```bash
export FISHROI_CACHE=/shared/path/fishroi
mkdir -p logs results
seg=$(sbatch --parsable --array=0-$((N-1)) 01_segment.sbatch)
# aftercorr: analyze task i starts as soon as segment task i finishes (per-image, not whole-array)
sbatch --dependency=aftercorr:$seg --array=0-$((N-1)) 02_analyze.sbatch
```

## Manual curation in the batch flow (optional)

To curate some images before analysis: run `01_segment.sbatch`, then on a desktop open the flagged
`results/<base>/<base>_rois.zip` with `fishroi_curate.py` (FIJI GUI), fix and re-save the zip,
and only then submit `02_analyze.sbatch` (drop the `--dependency` so it runs on your schedule).

## Notes / knobs

- **Large images (5-10 GB):** `02_analyze.sbatch` passes `--mem 90%` to FIJI so ImageJ's JVM heap
  scales with the SLURM `--mem`; raise `#SBATCH --mem` accordingly (the paper suggests up to 64 GB).
- **Model / Fiji:** taken from `$FISHROI_CACHE/env.sh` (staged in step 2). No per-task downloads.
- **GPU forcing:** `--gpu on` in the segment step; it warns and falls back to CPU if no CUDA device.
- **CoV optional:** delete the `--julia-script` line in `02_analyze.sbatch` to skip Step 4.
- Not SLURM? The two `python fishroi_run_all.py` commands are the whole contract — wrap them in
  PBS/LSF/SGE array jobs the same way, or the `hpc-slurm-script` skill can regenerate these.
