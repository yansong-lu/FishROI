# Jython script for FIJI (run headless): measure an ImageJ ROI zip with ImageJ's OWN
# definitions, producing a FIJI-identical measurement CSV. Use this instead of the
# scikit-image measurements in fishroi_auto.py when you need numbers that match the
# published plugin (absolute area, circularity, perimeter differ ~5-10% between the two;
# see references/automation.md).
#
# For the Cellpose route this is truly plugin-identical: the interactive plugin also loads
# the Cellpose ROI zip, so it measures these exact polygons.
#
# Columns written (ImageJ names): Area, X, Y, XM, YM, Perim., Circ., Feret, FeretX, FeretY,
# FeretAngle, MinFeret, AR, Round, Solidity. The Julia CoV step needs Area, XM, YM, Feret
# (and FeretX/FeretY only when transpose=true).
#
# Usage:
#   FIJI=/Applications/Fiji/Fiji.app/Contents/MacOS/fiji-macos-arm64   # adjust per platform
#   "$FIJI" --headless --run fishroi_measure_fiji.py \
#       'image="img.tif",roizip="img_ROIs.zip",outcsv="img.csv",pixel_um="0.27056"'
#
# Notes:
#   * Do NOT pass --console. ROIs are decoded with RoiDecoder because RoiManager cannot be
#     instantiated in a headless JVM (it extends an AWT Frame -> HeadlessException).
#   * pixel_um: microns per pixel. >0 calibrates so Area is um^2 and Feret/XM/YM are microns.
#     0 (default) leaves the image uncalibrated (Area in px^2, coords in px).

#@ String image
#@ String roizip
#@ String outcsv
#@ String (value="0") pixel_um

import jarray, os
from java.util.zip import ZipInputStream
from java.io import FileInputStream, ByteArrayOutputStream
from ij import IJ
from ij.io import RoiDecoder
from ij.measure import ResultsTable, Measurements
from ij.plugin.filter import Analyzer


def read_rois(zip_path):
    """Decode every ImageJ .roi entry from a RoiManager zip (no AWT/RoiManager)."""
    rois = []
    zis = ZipInputStream(FileInputStream(zip_path))
    buf = jarray.zeros(8192, 'b')
    e = zis.getNextEntry()
    while e is not None:
        baos = ByteArrayOutputStream()
        while True:
            c = zis.read(buf, 0, len(buf))
            if c == -1:
                break
            baos.write(buf, 0, c)
        r = RoiDecoder(baos.toByteArray(), e.getName()).getRoi()
        if r is not None:
            rois.append(r)
        e = zis.getNextEntry()
    zis.close()
    return rois


imp = IJ.openImage(image)
px = float(pixel_um)
if px > 0:                                   # calibrate -> Area in um^2, Feret/XM/YM in microns
    cal = imp.getCalibration()
    cal.pixelWidth = px
    cal.pixelHeight = px
    cal.setUnit("micron")

flags = (Measurements.AREA | Measurements.CENTROID | Measurements.CENTER_OF_MASS |
         Measurements.PERIMETER | Measurements.FERET | Measurements.SHAPE_DESCRIPTORS)
rt = ResultsTable()
an = Analyzer(imp, flags, rt)
for roi in read_rois(roizip):
    imp.setRoi(roi)
    an.measure()

d = os.path.dirname(outcsv)
if d and not os.path.isdir(d):
    os.makedirs(d)
rt.save(outcsv)
print("MEASURE_DONE n=%d -> %s" % (rt.size(), outcsv))
