#!/usr/bin/env python3
"""
fishroi_auto.py - headless, batchable reimplementation of the FishROI downstream workflow.

Purpose: run the FishROI analysis (segmentation -> ROIs -> measurements -> area heatmap ->
spatial coefficient-of-variation map) with NO GUI and NO runtime downloads, so it can be
scripted on a workstation or an HPC node.

Design notes:
  * Segmentation is pluggable. The DEEP-LEARNING backend calls genuine Cellpose exactly as
    run_cellpose.py does, using a LOCAL model file (e.g. the Zenodo 'rerio' model) so nothing is
    downloaded at runtime. If no --model is given, it falls back to a classical watershed
    stand-in (lower quality; a warning is printed).
  * The CoV step is a faithful port of MuscleMosaicism_v3.jl (window_radius = 3x mean Feret,
    step = window_radius/10, NaN where a window holds < 5 fibres, CoV = sigma/mu).
  * ROIs are written in ImageJ .zip format (via roifile), so outputs are interoperable with the
    FIJI plugin, RoiManager, and read_roi / the Julia script.

Caveat: measurements here are a reimplementation (skimage), so ImageJ-specific definitions
(circularity, Feret) will be close but not bit-identical to FIJI. For FIJI-identical numbers,
run the plugin headlessly instead (see the automation reference in the skill).

Deps (all on PyPI, no conda):
    pip install tifffile numpy pandas scikit-image scipy matplotlib roifile opencv-python-headless
    # deep-learning backend additionally:  pip install cellpose torch
Usage:
    python fishroi_auto.py --image sample_2.tif --outdir out/ \
        --model /path/to/rerio            # omit --model to use watershed fallback
        [--seg-channel max|1] [--diameter 0] [--min-area-um2 1.5] \
        [--lut viridis] [--gamma 0.6]
"""
import argparse, os, sys, time, zipfile
import numpy as np, pandas as pd, tifffile
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from skimage.filters import gaussian, threshold_otsu
from skimage.morphology import h_maxima
from skimage.segmentation import watershed, find_boundaries
from skimage.measure import regionprops_table
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm, Normalize, ListedColormap

# FIJI 'phase' LUT (256 RGB triples, interleaved) embedded so this no-FIJI path reproduces the
# paper's area-heatmap colours without a FIJI install. Original order: blue(min)->gray->red(max).
PHASE_LUT_HEX = (
    "0000fc0000fc0000fc0404fc0404fc0404fc0808fc0808fc0c0cfc0c0cfc0c0cf81010f81010f81414f81414f8"
    "1414f81818f81818f81c1cf81c1cf81c1cf42020f42020f42424f42424f42424f42828f42828f42c2cf42c2cf4"
    "2c2cf03030f03030f03434f03434f03434f03838f03838f03c3cf03c3cec3c3cec4040ec4040ec4444ec4444ec"
    "4444ec4848ec4848ec4c4cec4c4ce84c4ce85050e85050e85454e85454e85454e85858e85858e85c5ce85c5ce4"
    "5c5ce46060e46060e46060e46464e46464e46868e46868e46868e06c6ce06c6ce07070e07070e07070e07474e0"
    "7474e07878e07878e07878dc7c7cdc7c7cdc8080dc8080dc8080dc8484dc8484dc8888dc8888dc8888d88c8cd8"
    "8c8cd89090d89090d89090d89494d89494d89898d89898d49898d49c9cd49c9cd4a0a0d4a0a0d4a0a0d4a4a4d4"
    "a4a4d4a8a8d4a8a8d0a8a8d0acacd0acacd0b0b0d0b0b0d0b0b0d0b4b4d0b4b4d0b8b8d0b8b8ccb8b8ccbcbccc"
    "bcbcccc0c0ccc0c0ccc0c0ccc4c4ccc4c4ccc8c8c8c8c8c8c8c8c8c8c4c4c8c4c4c8c4c4c8c0c0c8c0c0c8bcbc"
    "c8bcbcccbcbcccb8b8ccb8b8ccb4b4ccb4b4ccb4b4ccb0b0ccb0b0ccacacccacacd0acacd0a8a8d0a8a8d0a8a8"
    "d0a4a4d0a4a4d0a0a0d0a0a0d0a0a0d09c9cd49c9cd49898d49898d49898d49494d49494d49090d49090d49090"
    "d48c8cd88c8cd88888d88888d88888d88484d88484d88484d88080d88080d87c7cdc7c7cdc7c7cdc7878dc7878"
    "dc7474dc7474dc7474dc7070dc7070dc6c6ce06c6ce06c6ce06868e06868e06464e06464e06464e06060e06060"
    "e46060e45c5ce45c5ce45858e45858e45858e45454e45454e45050e45050e85050e84c4ce84c4ce84848e84848"
    "e84848e84444e84444e84444e84040ec4040ec3c3cec3c3cec3c3cec3838ec3838ec3434ec3434ec3434ec3030"
    "f03030f02c2cf02c2cf02c2cf02828f02828f02424f02424f02424f02020f42020f42020f41c1cf41c1cf41818"
    "f41818f41818f41414f41414f41010f81010f81010f80c0cf80c0cf80808f80808f80808f80404f80404fc0000"
    "fc0000")


def phase_cmap(invert=True, bad="black"):
    """matplotlib colormap from the embedded FIJI phase LUT. invert -> small=red, large=blue
    (the paper's area scheme); NaN/background renders as `bad`."""
    rgb = np.frombuffer(bytes.fromhex(PHASE_LUT_HEX), dtype=np.uint8).reshape(256, 3) / 255.0
    if invert:
        rgb = rgb[::-1]
    cm = ListedColormap(rgb)
    cm.set_bad(bad)
    return cm


def load_image(path):
    """Return (stack CxHxW float32, pixel_size_um). Reads ImageJ TIFF calibration if present."""
    arr = tifffile.imread(path).astype(np.float32)
    if arr.ndim == 2:
        arr = arr[None]
    pixel_um = None
    with tifffile.TiffFile(path) as t:
        p = t.pages[0]
        if "XResolution" in p.tags:
            num, den = p.tags["XResolution"].value          # pixels per unit
            if num:
                pixel_um = den / num                          # -> unit per pixel (micron)
    if pixel_um is None:
        pixel_um = 1.0
        print("WARNING: no pixel calibration found; areas will be in pixel units.", file=sys.stderr)
    return arr, pixel_um


def pick_channel(stack, seg_channel):
    """Return the 2D image used for segmentation. 'max' = max projection across channels."""
    if seg_channel == "max":
        return np.maximum.reduce(stack)
    idx = int(seg_channel) - 1                                # 1-based, like the plugin/run_cellpose
    return stack[idx]


def segment_cellpose(stack, seg_channel, model_path, diameter, gpu="auto"):
    """Genuine Cellpose segmentation with a LOCAL model file (mirrors run_cellpose.py).
    The image is reduced to a single 2D channel, so we segment it as grayscale (channels=[0,0]).
    gpu: 'auto' (use CUDA if available), 'on'/True (force), 'off'/False (force CPU)."""
    from cellpose import models
    import torch
    if gpu in ("auto", None):
        gpu = torch.cuda.is_available()
    else:
        gpu = gpu in (True, "on", "true", "1", "yes")
    if gpu and not torch.cuda.is_available():
        print("WARNING: --gpu on but no CUDA device found; Cellpose will fall back to CPU.",
              file=sys.stderr)
    print("Cellpose device:", "cuda" if gpu else "cpu")
    model = models.CellposeModel(pretrained_model=model_path, gpu=gpu)
    img = np.max(stack, axis=0) if seg_channel == "max" else stack[int(seg_channel) - 1]
    # diameter=0 -> use the model's trained diameter (diam_labels), exactly like run_cellpose.py
    masks = model.eval(img, diameter=(diameter or 0), channels=[0, 0])[0]
    return masks.astype(np.int32)


def segment_watershed(stack, seg_channel, pixel_um, min_area_um2, sigma=2.5, hfrac=0.07):
    """Classical fallback for cytoplasmic staining (bright fibres, dark boundaries)."""
    print("WARNING: no --model supplied -> using WATERSHED fallback (lower quality than Cellpose).",
          file=sys.stderr)
    img = pick_channel(stack, seg_channel)
    norm = lambda a: (a - a.min()) / (np.ptp(a) + 1e-9)
    sm = norm(gaussian(img, sigma, preserve_range=True))
    fg = ndi.binary_fill_holes(sm > threshold_otsu(sm))
    markers, _ = ndi.label(h_maxima(sm, hfrac) * fg)
    ws = watershed(-sm, markers, mask=fg)
    min_px = int(min_area_um2 / (pixel_um ** 2))
    ids, cnt = np.unique(ws, return_counts=True)
    ws[np.isin(ws, ids[(ids != 0) & (cnt < min_px)])] = 0
    return ws.astype(np.int32)


def measure(labels, stack, seg_channel, pixel_um):
    """Per-fibre morphometrics. Columns mirror the FishROI/Julia essentials."""
    intensity = pick_channel(stack, seg_channel)
    props = regionprops_table(
        labels, intensity_image=intensity,
        properties=("label", "area", "centroid", "feret_diameter_max",
                    "perimeter", "mean_intensity"))
    df = pd.DataFrame(props).rename(columns={
        "centroid-0": "cy", "centroid-1": "cx",
        "feret_diameter_max": "feret_px", "mean_intensity": "Mean"})
    df["Area"] = df["area"] * pixel_um ** 2                   # um^2
    df["XM"] = df["cx"] * pixel_um                            # um
    df["YM"] = df["cy"] * pixel_um                            # um
    df["Feret"] = df["feret_px"] * pixel_um                   # um
    df["Perim."] = df["perimeter"] * pixel_um
    df["Circ."] = np.clip(4 * np.pi * df["area"] / (df["perimeter"] ** 2 + 1e-9), 0, 1)
    return df[["label", "Area", "XM", "YM", "Feret", "Perim.", "Circ.", "Mean"]]


def write_roi_zip(labels, path):
    """Write ImageJ-format ROI zip (interoperable with FIJI RoiManager, read_roi, the Julia script)."""
    import cv2, roifile
    rois = []
    for i in [x for x in np.unique(labels) if x != 0]:
        cnts, _ = cv2.findContours((labels == i).astype(np.uint8),
                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea).squeeze()          # (N,2) as (x,y)
        if c.ndim != 2 or len(c) < 3:
            continue
        roi = roifile.ImagejRoi.frompoints(c.astype(np.float32))
        roi.name = "%04d" % int(i)
        roi.roitype = roifile.ROI_TYPE.FREEHAND
        rois.append(roi)
    if os.path.exists(path):
        os.remove(path)
    roifile.roiwrite(path, rois)
    return len(rois)


def area_heatmap(labels, df, pixel_um, path, lut, gamma):
    """Step 3: fill each fibre with its area value and apply a LUT.

    Default LUT ('phase-inv-black') = the paper's Figure-2 scheme: FIJI phase LUT inverted
    (small fibres red, large blue), NaN background black, linear scale, with a LUT scale bar
    above the heatmap labelling the smallest and largest fibre areas. Passing any matplotlib
    colormap name instead falls back to that cmap with the previous gamma/percentile scaling.
    """
    H, W = labels.shape
    lut_arr = np.zeros(int(labels.max()) + 1, np.float32)
    for l, a in df.set_index("label")["Area"].items():
        lut_arr[int(l)] = a
    amap = lut_arr[labels]; amap[labels == 0] = np.nan
    ext = [0, W * pixel_um, H * pixel_um, 0]
    vmin = float(np.nanmin(amap)); vmax = float(np.nanmax(amap))

    paper = lut in ("phase-inv-black", "phase")
    cmap = phase_cmap(invert=(lut != "phase")) if paper else lut
    norm = (Normalize(vmin=vmin, vmax=vmax) if paper
            else PowerNorm(gamma=gamma, vmin=0, vmax=np.nanpercentile(amap, 98)))

    fig, ax = plt.subplots(figsize=(9, 13)); fig.set_facecolor("black"); ax.set_facecolor("black")
    im = ax.imshow(amap, cmap=cmap, extent=ext, origin="upper", norm=norm)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    # LUT scale bar ABOVE the heatmap: smallest fibre on the red (min) end, largest on blue (max)
    cbar = fig.colorbar(im, ax=ax, orientation="horizontal", location="top",
                        fraction=0.045, pad=0.02)
    cbar.set_ticks([vmin, vmax])
    cbar.set_ticklabels(["{:,.0f} µm²".format(round(vmin)),
                         "{:,.0f} µm²".format(round(vmax))])
    cbar.ax.tick_params(colors="white", labelsize=13)
    cbar.outline.set_edgecolor("white")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="black"); plt.close()


def cov_map(labels, df, pixel_um, path_cov, path_panels):
    """Step 4: spatial mean/SD/CoV of fibre area - faithful port of MuscleMosaicism_v3.jl."""
    H, W = labels.shape
    mean_feret = df["Feret"].mean()
    window_radius = 3 * mean_feret                            # Julia: 3 * mean(Feret)
    step = window_radius / 10                                 # Julia: window_radius/10
    xs = np.arange(0, W * pixel_um, step); ys = np.arange(0, H * pixel_um, step)
    GX, GY = np.meshgrid(xs, ys)
    tree = cKDTree(df[["XM", "YM"]].values); areas = df["Area"].values
    neigh = tree.query_ball_point(np.column_stack([GX.ravel(), GY.ravel()]), window_radius)
    meanM = np.full(GX.size, np.nan); stdM = np.full(GX.size, np.nan)
    for i, idx in enumerate(neigh):
        if len(idx) >= 5:                                     # Julia: NaN if < 5 cells in window
            a = areas[idx]; meanM[i] = a.mean(); stdM[i] = a.std(ddof=1)
    meanM = meanM.reshape(GX.shape); stdM = stdM.reshape(GX.shape); covM = stdM / meanM
    gext = [0, xs[-1] + step, ys[-1] + step, 0]
    bnd = np.zeros((H, W, 4), np.float32); bnd[find_boundaries(labels, mode="outer")] = [1, 1, 1, 0.35]
    iext = [0, W * pixel_um, H * pixel_um, 0]

    fig, ax = plt.subplots(figsize=(9, 13)); ax.set_facecolor("black")
    im = ax.imshow(covM, cmap="viridis", extent=gext, origin="upper", vmin=0, vmax=1.1)
    ax.imshow(bnd, extent=iext, origin="upper")
    ax.set_title("FishROI Step 4 - CoV of fibre area (σ/µ), r = 3× mean Feret = %.0f µm" % window_radius)
    ax.set_xlabel("x (µm)"); ax.set_ylabel("y (µm)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02).set_label("CoV (σ/µ)")
    plt.tight_layout(); plt.savefig(path_cov, dpi=150, bbox_inches="tight", facecolor="black"); plt.close()

    fig, axs = plt.subplots(1, 3, figsize=(20, 10))
    for ax, (M, ttl, vm) in zip(axs, [(meanM, "µ", np.nanpercentile(meanM, 95)),
                                      (stdM, "σ", np.nanpercentile(stdM, 95)), (covM, "σ/µ", 1.1)]):
        ax.set_facecolor("black")
        im = ax.imshow(M, cmap="viridis", extent=gext, origin="upper", vmin=0, vmax=vm)
        ax.imshow(bnd, extent=iext, origin="upper"); ax.set_title(ttl); ax.axis("off")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    plt.tight_layout(); plt.savefig(path_panels, dpi=140, bbox_inches="tight", facecolor="black"); plt.close()
    return mean_feret, window_radius, float(np.nanmedian(covM))


def main():
    ap = argparse.ArgumentParser(description="Headless FishROI-style pipeline")
    ap.add_argument("--image", required=True)
    ap.add_argument("--outdir", default="fishroi_out")
    ap.add_argument("--model", default=None,
                    help="local Cellpose model path, or 'auto' to fetch rerio (omit -> watershed fallback)")
    ap.add_argument("--seg-channel", default="max", help="'max' or 1-based channel index")
    ap.add_argument("--diameter", type=float, default=0.0, help="Cellpose diameter px (0=auto)")
    ap.add_argument("--min-area-um2", type=float, default=1.5, help="watershed min fibre area")
    ap.add_argument("--lut", default="phase-inv-black",
                    help="area heatmap LUT: 'phase-inv-black' (default, paper's) / 'phase' / any mpl cmap")
    ap.add_argument("--gamma", type=float, default=0.6, help="gamma (only for non-phase mpl cmaps)")
    ap.add_argument("--segment-only", action="store_true", help="run segmentation, save labels, exit")
    ap.add_argument("--labels-npy", default=None, help="skip segmentation; load labels from this .npy")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.image))[0]
    op = lambda s: os.path.join(a.outdir, base + s)
    t0 = time.time()

    stack, pixel_um = load_image(a.image)
    print("image %s  channels=%d  pixel=%.5f µm/px" % (stack.shape, stack.shape[0], pixel_um))

    if a.labels_npy:
        labels = np.load(a.labels_npy).astype(np.int32)
        print("loaded labels from %s" % a.labels_npy)
    elif a.model:
        if a.model in ("auto", "rerio"):                     # fetch the rerio model to the cache
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from fetch_model import resolve_model
            a.model = resolve_model(a.model)
            print("model -> %s" % a.model)
        labels = segment_cellpose(stack, a.seg_channel, a.model, a.diameter)
    else:
        labels = segment_watershed(stack, a.seg_channel, pixel_um, a.min_area_um2)
    n = len(np.unique(labels)) - 1
    print("segmented %d fibres  (%.1fs)" % (n, time.time() - t0))
    if n == 0:
        sys.exit("No fibres detected - check channel/model/diameter.")
    np.save(op("_labels.npy"), labels)
    if a.segment_only:
        print("segment-only: labels saved -> %s" % op("_labels.npy"))
        return

    df = measure(labels, stack, a.seg_channel, pixel_um)
    df.to_csv(op("_measurements.csv"), index=False)
    nroi = write_roi_zip(labels, op("_ROIs.zip"))
    area_heatmap(labels, df, pixel_um, op("_area_heatmap.png"), a.lut, a.gamma)
    mf, wr, covmed = cov_map(labels, df, pixel_um, op("_cov_map.png"), op("_variance_panels.png"))

    with open(op("_area_statistics.txt"), "w") as f:
        f.write("fishroi_auto  image=%s\n" % base)
        prov = ("cellpose:" + a.model if a.model
                else ("reused:" + a.labels_npy if a.labels_npy else "watershed_fallback"))
        f.write("segmentation=%s\n" % prov)
        f.write("pixel_um=%.5f\nn_fibres=%d\n" % (pixel_um, len(df)))
        f.write("mean_area_um2=%.3f\nsd_area_um2=%.3f\nwhole_CoV=%.3f\n"
                % (df.Area.mean(), df.Area.std(ddof=1), df.Area.std(ddof=1) / df.Area.mean()))
        f.write("mean_feret_um=%.3f\nwindow_radius_um=%.3f\nlocal_CoV_median=%.3f\n" % (mf, wr, covmed))
    print("done in %.1fs  ->  %s (%d ROIs in zip)" % (time.time() - t0, a.outdir, nroi))


if __name__ == "__main__":
    main()
