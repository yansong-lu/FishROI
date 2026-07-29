# Jython for FIJI (run WITH the GUI, i.e. NOT --headless): auto-open a "Clean up ROI tools"
# panel on an image + its ROI zip, for the pipeline's manual-curation checkpoint.
#
# Replicates the fishROI plugin's Step-2 cleanup tools (random colour, bulk-remove ROIs inside a
# drawn selection) but wires SAVE / QuickSave to overwrite the given zip path directly, so Phase B
# (--roizip) can pick the curated ROIs up. Stays open via a non-modal WaitForUserDialog (plain
# `--run` would System.exit as soon as the script returns and close the windows).
#
# Usage (GUI, NOT --headless):
#   FIJI=/Applications/Fiji/Fiji.app/Contents/MacOS/fiji-macos
#   "$FIJI" --run fishroi_curate.py 'image="img.tif",roizip="out/img_rois.zip"'
#   # optional savepath="..." to save somewhere other than roizip

#@ String image
#@ String roizip
#@ String (value="") savepath

from ij import IJ
from ij.plugin.frame import RoiManager
from ij.gui import WaitForUserDialog
from javax.swing import JFrame, JPanel, JButton, JLabel, BoxLayout
from java.awt import Dimension

SAVE_TO = savepath if savepath else roizip


def _rm():
    rm = RoiManager.getInstance()
    return rm if rm is not None else RoiManager()


def colour(evt):
    """Random-colour every ROI (spot merges), exactly like the plugin's Colour ROI!."""
    rm = _rm()
    n = rm.getCount()
    if n < 1:
        IJ.log("ROIs not found!")
        return
    for i in range(n):
        rm.select(i)
        IJ.runMacro("b=maxOf(0,255*random);r=maxOf(0,255*random);g=maxOf(50,255*random);"
                    "Roi.setFillColor(r,g,b);")
    rm.runCommand("Show All")
    IJ.log("Coloured %d ROIs." % n)


def remove(evt):
    """Bulk-remove ROIs fully inside the current image selection (plugin's Remove ROI!):
    fill the drawn selection with 255, delete ROIs whose Min == 255, restore the pixels."""
    imp = IJ.getImage()
    if imp is None or imp.getRoi() is None:
        IJ.log("Draw a selection (rectangle/oval/polygon) on the image first, then Remove ROI!")
        return
    ip_original = imp.getProcessor().duplicate()
    IJ.run(imp, "Set...", "value=255")                  # fill the drawn region
    IJ.runMacro('''
        roiManager("Deselect"); close("Results");
        roiManager("Measure");
        n_to_remove = 0;
        for (i = 0; i < nResults; i++) {
            roiManager("select", i);
            if (getResult("Min", i) == 255) { roiManager("rename", "a_to_delete"); n_to_remove++; }
            else { roiManager("rename", "ROI" + i); }
        }
        ROI_to_remove = newArray(n_to_remove);
        for (i = 0; i < n_to_remove; i++) ROI_to_remove[i] = i;
        roiManager("sort");
        if (n_to_remove > 0) { roiManager("select", ROI_to_remove); roiManager("delete"); }
        roiManager("Show None"); roiManager("Show All");
    ''')
    imp.setProcessor(ip_original)                       # undo the fill
    imp.updateAndDraw()


def save(evt):
    """QuickSave: overwrite the target zip directly (the path Phase B will read)."""
    rm = _rm()
    rm.runCommand("Deselect")
    ok = rm.save(SAVE_TO)
    IJ.log(("Saved %d ROIs -> %s" % (rm.getCount(), SAVE_TO)) if ok else "Save FAILED")


# --- open the image + ROIs ---
imp = IJ.openImage(image)
imp.show()
IJ.run("Set Measurements...", "min redirect=None decimal=3")   # bulk-remove needs Min
rm = _rm()
rm.reset()
rm.runCommand("Open", roizip)
rm.runCommand(imp, "Show All with labels")
IJ.setTool("freehand")

# --- the cleanup tools panel ---
frame = JFrame("Clean up ROI tools")
panel = JPanel()
panel.setLayout(BoxLayout(panel, BoxLayout.Y_AXIS))
panel.add(JLabel("Colour all ROIs (spot merged fibres):"))
panel.add(JButton("Colour ROI!", actionPerformed=colour))
panel.add(JLabel("Draw a selection on the image, then remove ROIs inside it:"))
panel.add(JButton("Remove ROI!", actionPerformed=remove))
panel.add(JLabel("Add a missed fibre: draw it, press 't'.  Delete: select + Delete key."))
panel.add(JLabel("QuickSave (overwrites the pipeline zip):"))
panel.add(JButton("QuickSave", actionPerformed=save))
frame.getContentPane().add(panel)
frame.setMinimumSize(Dimension(360, 240))
frame.pack()
frame.setVisible(True)

IJ.log("Loaded %d ROIs. Curate, then QuickSave (or just click OK to save + close)." % rm.getCount())
IJ.log("QuickSave / OK writes -> %s" % SAVE_TO)

# keep FIJI open until the user is done; non-modal so the tools + image stay usable
WaitForUserDialog("FishROI curation",
                  "Curate the ROIs with the cleanup tools.\n"
                  "Click OK when finished - the ROI set is saved to the pipeline zip.").show()
save(None)          # final save on OK
IJ.log("Curation done.")
