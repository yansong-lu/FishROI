# fishROI — headless automation, HPC & Claude skill

Companion to the **fishROI** FIJI2/Jython plugin for semi-automated muscle morphometry in teleost
fish (validated in zebrafish): segment fibre cross-sections → ROIs → area heatmaps → spatial
coefficient-of-variation (CoV) maps that quantify mosaic hyperplasia.

This branch packages the **headless/batch automation** and a **Claude skill** around the workflow.
The interactive GUI plugin itself (`fishROI_v1.py`, `run_cellpose.py`) lives on the **`main`** branch
of this repository.

- Paper: https://doi.org/10.64898/2026.03.27.714781
- Models + test images (Zenodo): https://doi.org/10.5281/zenodo.19223252
- Contact: KLu@stowers.org · yansong.lu@monash.edu

## Quickstart (headless, FIJI-identical)

```bash
pip install tifffile numpy pandas scikit-image scipy matplotlib roifile opencv-python-headless
pip install "cellpose<4" torch      # pin <4: cellpose 4.x is SAM and breaks the rerio/cyto3 models

# one command: segment (Cellpose rerio) -> FIJI-identical measure -> area heatmap -> Julia CoV.
# rerio model is fetched + md5-verified automatically; Fiji is auto-detected (installed if absent).
python automation/fishroi_run_all.py \
    --image "DR test image.tif" --outdir out/ --seg-channel 1 \
    --julia-script skill/fishROI_v2/MuscleMosaicism_v3.jl        # omit to skip the CoV step
```

Outputs per image: `*_rois.zip`, a FIJI-identical `*_measurements.csv`, `*_area_heatmap.png/.tif`
(the paper's inverted `phase` LUT with a min/max scale bar), and Julia µ/σ/CoV maps in `out/julia/`.

## Manual curation (the plugin's Step 2)

Cellpose is rarely perfect. Split the run and curate ROIs between the halves:

```bash
python automation/fishroi_run_all.py --image img.tif --outdir out/ --segment-only          # Phase A
"$FIJI" --run automation/fishroi_curate.py 'image="img.tif",roizip="out/img_rois.zip"'      # curate (GUI)
python automation/fishroi_run_all.py --image img.tif --outdir out/ --roizip out/img_rois.zip \
    --julia-script skill/fishROI_v2/MuscleMosaicism_v3.jl                                                     # Phase B
```

Phase B auto-drops zero-area / stray ROIs, so an accidental curation click can't break the run.

## HPC

`automation/hpc/` has generic SLURM templates: Phase A as a GPU array, Phase B as a CPU array.

## Layout

```
automation/                            # headless pipeline (see automation/ and CLAUDE.md)
skill/fishROI_v2/                       # Claude skill: SKILL.md router + references
skill/fishROI_v2/MuscleMosaicism_v3.jl  # Julia CoV / spatial-variance analysis (CoV step)
example_outputs/                        # sample figures
CLAUDE.md                               # repo guide for AI agents / contributors
```

## Fidelity

`fishroi_run_all.py` measures in headless FIJI, so absolute area/circularity/perimeter match the
published plugin. The pure-Python fallback `automation/fishroi_auto.py` (no FIJI) uses scikit-image
and reads ~5–10% different on those definitions, though the CoV readout barely moves (~2%). See
`skill/fishROI_v2/references/automation.md`.

## Citation

Lu Y, Pan M, Jamwal V, Locop J, Ruparelia A, Currie P. *fishROI: A specialized workflow for
semi-automated muscle morphometry analysis in teleosts.* bioRxiv 2026.03.27.714781. See
`skill/fishROI_v2/references/paper-summary.md` for a condensed summary. License: `LICENSE`.
