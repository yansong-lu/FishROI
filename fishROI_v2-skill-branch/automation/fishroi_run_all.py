#!/usr/bin/env python3
"""
fishroi_run_all.py - one command, FIJI-identical, fully headless FishROI pipeline.

    segment (Cellpose, local model)
      -> ImageJ ROI zip (Cellpose io.save_rois == the plugin's Cellpose route)
      -> FIJI-identical measurements CSV (headless FIJI, ImageJ definitions)
      -> FIJI area heatmap + LUT scale bar (headless FIJI, paper's phase LUT)
      -> Julia CoV / spatial-variance maps (MuscleMosaicism_v3.jl, headless GR)

Why this exists: it chains the pieces validated in this workstream and handles the two glue
problems by itself -- (a) the Julia script wants <base>.zip / <base>.csv side by side, and
(b) it needs a generated input block appended. Measurements come from FIJI (not scikit-image),
so absolute area / circularity / perimeter match the published plugin (see
skill/fishROI_v2/references/automation.md for the ~5-10% scikit-vs-FIJI gap this avoids).

Deps: the segmentation reuses fishroi_auto.py, so install its env first, and pin cellpose <4:
    pip install tifffile numpy pandas scikit-image scipy matplotlib roifile opencv-python-headless
    pip install "cellpose<4" torch
Also needs a FIJI install (for the two headless steps) and, for the CoV step, Julia with
DataFrames/CSV/Plots/PyCall and read-roi importable by PyCall's Python.

The pipeline has TWO phases with the ROI zip as the checkpoint between them:
    Phase A  segment                       -> <base>_rois.zip     [GPU-heavy: Cellpose]
       (optional) curate the zip in the FIJI GUI, or split GPU/CPU across HPC nodes here
    Phase B  analyze (--roizip <zip>)       -> measure + heatmap + CoV   [CPU only]

Usage:
    # whole pipeline in one go (model + FIJI auto-resolved):
    python fishroi_run_all.py --image "pSB test image.tif" --outdir out/ --seg-channel 1 \
        --julia-script ../skill/fishROI_v2/MuscleMosaicism_v3.jl        # omit to skip the CoV step

    # split for manual curation OR GPU/CPU separation on HPC:
    python fishroi_run_all.py --image img.tif --outdir out/ --segment-only          # Phase A (GPU)
    #   ... curate out/img_rois.zip in FIJI (see fishroi_curate.py) ...
    python fishroi_run_all.py --image img.tif --outdir out/ --roizip out/img_rois.zip \
        --julia-script ../skill/fishROI_v2/MuscleMosaicism_v3.jl                             # Phase B (CPU)

    # options: --model auto|/path  --fiji auto|/path  --gpu auto|on|off  --mem 48G
    #          --seg-channel 1  --diameter 0  --lut phase-inv-black  --pixel-um 0 (0 = read TIFF)
"""
import argparse, os, sys, shutil, subprocess
import numpy as np, tifffile  # noqa: F401  (tifffile used via fishroi_auto)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fishroi_auto import load_image, segment_cellpose      # reuse validated pieces
from fetch_model import resolve_model                       # --model auto -> fetched rerio
from fiji_setup import ensure_fiji                          # --fiji auto: find or install Fiji

MEASURE_IJM = os.path.join(HERE, "fishroi_measure_fiji.py")
HEATMAP_IJM = os.path.join(HERE, "fishroi_heatmap_fiji.py")


def sh(cmd, env=None, tag=""):
    """Run a subprocess, echoing it; exit on failure."""
    print("\n[%s] + %s" % (tag, " ".join(str(c) for c in cmd)))
    if subprocess.run(cmd, env=env).returncode != 0:
        sys.exit("step '%s' failed" % tag)


def fiji_args(**kw):
    """Build the single quoted arg string scijava --run expects: 'k1="v1",k2="v2"'."""
    return ",".join('%s="%s"' % (k, v) for k, v in kw.items())


def _poly_area(c):
    c = np.asarray(c, float)
    if len(c) < 3:
        return 0.0
    x, y = c[:, 0], c[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def drop_degenerate_rois(inzip, outzip, min_area_px=0.5):
    """Remove zero-area / <3-point ROIs (e.g. stray clicks added during curation): they give a
    NaN centroid in FIJI and crash the Julia grid (Int64(NaN)). Returns the number dropped;
    writes outzip only if something was dropped (else downstream uses inzip unchanged)."""
    import roifile
    rois = roifile.roiread(inzip)
    if not isinstance(rois, list):
        rois = [rois]
    kept = [r for r in rois
            if len(np.asarray(r.coordinates())) >= 3 and _poly_area(r.coordinates()) >= min_area_px]
    dropped = len(rois) - len(kept)
    if dropped:
        if os.path.exists(outzip):
            os.remove(outzip)
        roifile.roiwrite(outzip, kept)
    return dropped


def main():
    ap = argparse.ArgumentParser(description="Headless FIJI-identical FishROI pipeline")
    ap.add_argument("--image", required=True)
    ap.add_argument("--outdir", default="fishroi_out")
    ap.add_argument("--model", default="auto",
                    help="local Cellpose model path, or 'auto' to fetch rerio to the cache (default)")
    ap.add_argument("--fiji", default=None,
                    help="FIJI launcher path; omit to auto-detect (and install Fiji if absent)")
    ap.add_argument("--seg-channel", default="1", help="'max' or 1-based channel index")
    ap.add_argument("--diameter", type=float, default=0.0, help="Cellpose diameter px (0=model default)")
    ap.add_argument("--gpu", default="auto", choices=["auto", "on", "off"],
                    help="Cellpose device: auto (CUDA if available), on (force), off (force CPU)")
    ap.add_argument("--lut", default="phase-inv-black",
                    help="area-heatmap LUT (default = paper's inverted phase, 0=black)")
    ap.add_argument("--pixel-um", type=float, default=0.0, help="override microns/px (0 = read TIFF)")
    ap.add_argument("--mem", default=None,
                    help="JVM heap for the FIJI steps, e.g. 48G or 64%% (for large images)")
    # phase control (checkpoint = the ROI zip): curate between the two, or split GPU/CPU on HPC
    ap.add_argument("--segment-only", action="store_true",
                    help="Phase A only: segment -> ROI zip, then stop (for manual curation / GPU stage)")
    ap.add_argument("--roizip", default=None,
                    help="Phase B: start from this (curated) ROI zip, skipping Cellpose segmentation")
    ap.add_argument("--julia-script", default=None,
                    help="path to MuscleMosaicism_v3.jl; provide to run the Step-4 CoV analysis")
    ap.add_argument("--julia", default="julia", help="julia executable")
    ap.add_argument("--no-julia", action="store_true", help="skip the CoV step even if --julia-script given")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.image))[0]
    op = lambda s: os.path.join(a.outdir, base + s)
    do_segment = a.roizip is None                 # Phase A runs unless resuming from a zip

    stack, pixel_um = load_image(a.image)
    if a.pixel_um > 0:
        pixel_um = a.pixel_um
    H, W = stack.shape[1], stack.shape[2]
    print("image=%s  pixel=%.5f um/px  W=%d H=%d" % (base, pixel_um, W, H))

    # ---- Phase A: segmentation -> ImageJ ROI zip (Cellpose io.save_rois = plugin's Cellpose route)
    if do_segment:
        model = resolve_model(a.model)            # 'auto' -> fetch rerio to the cache
        print("model=%s" % model)
        labels = segment_cellpose(stack, a.seg_channel, model, a.diameter, gpu=a.gpu)
        n = int(labels.max())
        if n == 0:
            sys.exit("No fibres detected - check channel/model/diameter.")
        from cellpose import io as cpio
        cpio.save_rois(labels, op(".zip"))        # writes <base>_rois.zip
        roizip = op("_rois.zip")
        if not os.path.exists(roizip):
            sys.exit("expected ROI zip not found: %s" % roizip)
        print("segmented %d fibres -> %s" % (n, roizip))
        if a.segment_only:
            print("\n[segment-only] ROI zip ready for review: %s\n"
                  "Curate it in the FIJI GUI (open the image, load the zip in ROI Manager, edit,\n"
                  "then More >> Save over the same file), or run it as-is. Then resume with:\n"
                  "  python fishroi_run_all.py --image %r --outdir %r --roizip %r%s\n"
                  % (roizip, a.image, a.outdir, roizip,
                     (" --julia-script %s" % a.julia_script) if a.julia_script else ""))
            return
    else:
        roizip = a.roizip                         # Phase B on a supplied / curated zip
        if not os.path.exists(roizip):
            sys.exit("--roizip not found: %s" % roizip)
        print("resuming from curated ROI zip: %s" % roizip)

    # drop degenerate ROIs (zero-area / stray curation clicks) before analysis -- they give a NaN
    # centroid in FIJI and crash the Julia grid. Uses a cleaned zip only if something was dropped.
    clean = op("_rois_clean.zip")
    ndrop = drop_degenerate_rois(roizip, clean)
    if ndrop:
        print("dropped %d degenerate ROI(s) -> %s" % (ndrop, clean))
        roizip = clean

    # ---- Phase B: FIJI-identical measurements + heatmap (+ Julia CoV) -- CPU only, no GPU needed
    fiji = ensure_fiji(a.fiji)                     # auto-detect / install
    print("fiji=%s" % fiji)
    fbase = [fiji] + (["--mem", a.mem] if a.mem else [])   # runtime opts (incl. heap) go first

    csv = op("_measurements.csv")
    sh(fbase + ["--headless", "--run", MEASURE_IJM,
        fiji_args(image=a.image, roizip=roizip, outcsv=csv, pixel_um=pixel_um)], tag="fiji-measure")

    sh(fbase + ["--headless", "--run", HEATMAP_IJM,
        fiji_args(image=a.image, roizip=roizip, outdir=a.outdir, lut=a.lut, pixel_um=pixel_um)],
       tag="fiji-heatmap")

    # 4) Julia CoV / spatial-variance maps
    if a.julia_script and not a.no_julia:
        jdir = os.path.join(a.outdir, "julia")
        os.makedirs(jdir, exist_ok=True)
        shutil.copy(roizip, os.path.join(jdir, base + ".zip"))   # Julia wants <base>.zip / <base>.csv
        shutil.copy(csv, os.path.join(jdir, base + ".csv"))
        jscript = os.path.join(jdir, "run_%s.jl" % base)
        shutil.copy(a.julia_script, jscript)
        block = (
            '\n\n# ---- auto-generated by fishroi_run_all.py ----\n'
            'image_dir = "%s"\n'
            'filename = "%s"\n'
            'pixel_length = %r\n'
            'dims = (%r, %r)\n'
            'results = process_roi_data(image_dir,filename;'
            'pixel_length=pixel_length,dims=dims)\n'
            'println("JULIA_RUN_COMPLETE")\n'
        ) % (jdir, base, pixel_um, W * pixel_um, H * pixel_um)
        with open(jscript, "a") as f:
            f.write(block)
        env = dict(os.environ)
        env["GKSwstype"] = "100"                                 # headless GR (no display)
        sh([a.julia, jscript], env=env, tag="julia-cov")
        print("Julia CoV outputs -> %s" % jdir)

    print("\nDONE -> %s" % a.outdir)


if __name__ == "__main__":
    main()
