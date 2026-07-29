# Jython script for FIJI (run headless): FishROI Step-3 area heatmap, FIJI-identical.
#
# Replicates grayscale_ROIheatmap() from fishROI_v1.py exactly -- linear-maps each ROI's
# measured area to gray round(max(1, 255*(area-min)/(max-min))) on a black 8-bit canvas --
# then applies a LUT. The DEFAULT LUT is the paper's Figure-2 area-heatmap scheme: FIJI's
# built-in "phase" LUT, INVERTED, with pixel value 0 forced to black (small fibres red,
# large blue, black background). Pass a different FIJI LUT name to override.
#
# Why Jython + headless FIJI: this keeps ImageJ's own area measurement and LUT rendering, so
# numbers/colours are identical to the interactive plugin (the "Option B" automation path).
#
# A LUT scale bar is drawn ABOVE the heatmap: a horizontal ramp in the same LUT with the
# SMALLEST fibre area labelled on the red (min) end and the LARGEST on the blue (max) end,
# in real units where a pixel size is known. Pass pixel_um to label in um^2 (else px^2).
#
# Usage (macOS example; adjust launcher/paths for your platform):
#   FIJI=/Applications/Fiji/Fiji.app/Contents/MacOS/fiji-macos-arm64
#   "$FIJI" --headless --run fishroi_heatmap_fiji.py \
#       'image="/path/img.tif",roizip="/path/img_ROIs.zip",outdir="/path/out",pixel_um="0.27056"'
#
# Notes:
#   * Do NOT pass --console (the newer Fiji launcher rejects it).
#   * ROIs are decoded directly from the .zip with RoiDecoder -- RoiManager cannot be
#     instantiated in a headless JVM (it extends an AWT Frame -> HeadlessException).
#   * pixel_um: microns per pixel. 0 (default) -> try the TIFF calibration; if still
#     uncalibrated, the scale bar is labelled in px^2 instead of um^2.
#   * lut values:
#       "phase-inv-black" (default) -> paper LUT (inverted phase, index 0 black)
#       "phase"                     -> stock phase LUT as-is
#       any other name              -> loaded from <Fiji>/luts/<name>.lut verbatim

#@ String image
#@ String roizip
#@ String outdir
#@ String (value="phase-inv-black") lut
#@ String (value="0") pixel_um

import jarray, re, os
from java.util.zip import ZipInputStream
from java.io import FileInputStream, ByteArrayOutputStream
from java.awt import Font, Color
from ij import IJ, ImagePlus
from ij.process import ByteProcessor, ColorProcessor, LUT
from ij.io import RoiDecoder

LUTDIR = os.path.join(IJ.getDirectory("imagej") or "", "luts")


def _signed(v):
    """Python 0..255 -> Java signed byte (-128..127)."""
    return v if v < 128 else v - 256


def _read_lut_triples(name):
    """Read <Fiji>/luts/<name>.lut (ASCII 'R G B' per line) -> (reds, greens, blues)."""
    path = os.path.join(LUTDIR, name + ".lut")
    nums = [int(x) for x in re.findall(r"\d+", open(path).read())][:768]
    return nums[0::3], nums[1::3], nums[2::3]


def build_lut(spec):
    """Return an ij.process.LUT for the requested spec (see header)."""
    if spec == "phase-inv-black":
        reds, greens, blues = _read_lut_triples("phase")
        reds = reds[::-1]; greens = greens[::-1]; blues = blues[::-1]   # Invert LUT
        reds[0] = greens[0] = blues[0] = 0                              # 0 -> black
    else:
        reds, greens, blues = _read_lut_triples(spec)
    rb = jarray.array([_signed(v) for v in reds], 'b')
    gb = jarray.array([_signed(v) for v in greens], 'b')
    bb = jarray.array([_signed(v) for v in blues], 'b')
    return LUT(rb, gb, bb)


def ramp_lut(spec):
    """LUT for the scale-bar ramp: same colours as `spec` but WITHOUT the 0->black
    override, so the ramp's left (min) end shows the real minimum-area colour (red)."""
    if spec == "phase-inv-black":
        reds, greens, blues = _read_lut_triples("phase")
        reds = reds[::-1]; greens = greens[::-1]; blues = blues[::-1]
    else:
        reds, greens, blues = _read_lut_triples(spec)
    rb = jarray.array([_signed(v) for v in reds], 'b')
    gb = jarray.array([_signed(v) for v in greens], 'b')
    bb = jarray.array([_signed(v) for v in blues], 'b')
    return LUT(rb, gb, bb)


def fmt_area(value_px, pxsz, unit):
    """Format an area (given in px) into a labelled unicode string, e.g. u'3 um^2'."""
    v = value_px * pxsz * pxsz
    return u"{:,.0f} {}".format(round(v), unit)


def make_scalebar(w, barh, spec, min_px, max_px, pxsz, unit):
    """Build a ColorProcessor: horizontal LUT ramp (red=min ... blue=max) with the
    smallest fibre area labelled on the left and the largest on the right."""
    ramp = ByteProcessor(w, barh)
    for x in range(w):
        ramp.setValue(1 + int(round(254.0 * x / (w - 1))))   # 1..255 left->right
        ramp.setRoi(x, 0, 1, barh)
        ramp.fill()
    ramp.resetRoi()
    ramp.setLut(ramp_lut(spec))
    cp = ramp.convertToRGB()

    font = Font("SansSerif", Font.BOLD, max(11, int(barh * 0.62)))
    cp.setFont(font)
    cp.setAntialiasedText(True)
    ty = int(barh * 0.5 + font.getSize() * 0.36)
    lo = fmt_area(min_px, pxsz, unit)
    hi = fmt_area(max_px, pxsz, unit)
    pad = max(4, int(w * 0.012))
    cp.setColor(Color.WHITE)
    cp.drawString(lo, pad, ty)                                # min on the red end
    cp.drawString(hi, w - cp.getStringWidth(hi) - pad, ty)    # max on the blue end
    return cp


def read_rois(zip_path):
    """Decode every ImageJ .roi entry in a RoiManager zip without touching AWT."""
    rois = []
    zis = ZipInputStream(FileInputStream(zip_path))
    buf = jarray.zeros(8192, 'b')
    entry = zis.getNextEntry()
    while entry is not None:
        baos = ByteArrayOutputStream()
        while True:
            count = zis.read(buf, 0, len(buf))
            if count == -1:
                break
            baos.write(buf, 0, count)
        roi = RoiDecoder(baos.toByteArray(), entry.getName()).getRoi()
        if roi is not None:
            rois.append(roi)
        entry = zis.getNextEntry()
    zis.close()
    return rois


imp = IJ.openImage(image)
title = os.path.splitext(imp.getTitle())[0]
ip = imp.getProcessor()
w, h = imp.getWidth(), imp.getHeight()

rois = read_rois(roizip)
areas = []
for roi in rois:
    ip.setRoi(roi)
    areas.append(ip.getStatistics().pixelCount)           # area in px (ratio is scale-invariant)
minA, maxA = min(areas), max(areas)

bp = ByteProcessor(w, h)                                   # black canvas
for roi, a in zip(rois, areas):
    ratio = (a - minA) / float(maxA - minA)
    bp.setValue(int(round(max(1, 255 * ratio))))          # plugin's exact mapping
    bp.fill(roi)

bp.setLut(build_lut(lut))
if not os.path.isdir(outdir):
    os.makedirs(outdir)

# raw heatmap (LUT baked in) as an 8-bit TIFF for re-use in FIJI
IJ.saveAs(ImagePlus(title + "_area_heatmap", bp), "Tiff",
          os.path.join(outdir, title + "_area_heatmap.tif"))

# pixel calibration for the scale-bar labels: explicit pixel_um > TIFF calibration > px
pxsz = float(pixel_um)
unit = u"µm²"                          # 'µm²'
if pxsz <= 0:
    pw = imp.getCalibration().pixelWidth
    if pw and pw != 1.0:
        pxsz = pw
    else:
        pxsz, unit = 1.0, u"px²"

# compose: LUT scale bar on top, heatmap below (both on black)
barh = max(24, int(round(h * 0.028)))
gap = max(6, int(round(h * 0.008)))
heat = bp.convertToRGB()
bar = make_scalebar(w, barh, lut, minA, maxA, pxsz, unit)
canvas = ColorProcessor(w, barh + gap + h)                # black background
canvas.insert(bar, 0, 0)
canvas.insert(heat, 0, barh + gap)
IJ.saveAs(ImagePlus(title + "_area_heatmap_scalebar", canvas), "PNG",
          os.path.join(outdir, title + "_area_heatmap.png"))

u = "px2" if unit == u"px²" else "um2"
print("HEATMAP_DONE n=%d lut=%s minArea=%d maxArea=%d min_%s=%.1f max_%s=%.1f" % (
    len(rois), lut, minA, maxA, u, minA * pxsz * pxsz, u, maxA * pxsz * pxsz))
