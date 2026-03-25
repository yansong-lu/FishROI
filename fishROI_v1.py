from ij import IJ, ImagePlus, ImageStack, CompositeImage, ImageListener
from ij.gui import GenericDialog, WaitForUserDialog, NonBlockingGenericDialog
from ij.io import FileSaver, OpenDialog
from ij.plugin.frame import RoiManager
from ij.measure import ResultsTable
from ij.process import FloatProcessor 
from array import zeros  
from ij import WindowManager as WM  
from java.awt.event import AdjustmentListener, ItemListener, KeyAdapter, MouseAdapter, KeyEvent, ActionListener, WindowAdapter  
from javax.swing.event import ListSelectionListener 
from java.lang import Thread, Integer, String, System, Runnable
import time
from datetime import datetime
import os
import json
import logging
from javax.swing import JPanel, JSlider, JCheckBox, JFrame, JTable, JScrollPane, JButton, JTextField, JTextArea, ListSelectionModel, SwingUtilities, JLabel, BorderFactory, JList, JComboBox
from java.awt import GridBagLayout, GridBagConstraints, Dimension, Font, Insets, Color  
import sys
from java.io import File
import threading


# Constants
LOG_WINDOW = "Log"
TIF_EXTENSION = ".tif"
HEATMAP_SUFFIX = " heatmap"
SEGMENTATION_SUFFIX = " segmentation"
CONFIG_FILENAME = "config.json"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_config():
    with open(config_path, "w") as f:
        json.dump(config, f)

def close_log():
    log_state = IJ.getLog()
    if log_state is not None:
        IJ.selectWindow("Log")
        IJ.run("Close")

def getTifTitle(imp):
    """ returns title without.tif """
    return imp.title.split(TIF_EXTENSION)[0]

def getHeatmapTifTitle(imp):
    """ returns title without heatmap.tif """
    return imp.title.split(HEATMAP_SUFFIX)[0]


######################################## Step 1: Image segmentation ##########################################


def extractChannel(imp, nChannel, nFrame):
    """ Extract a stack for a specific color channel and time frame """
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    stack = imp.getImageStack()
    ch = ImageStack(imp.width, imp.height)
    for i in range(1, imp.getNSlices() + 1):
        index = imp.getStackIndex(nChannel, i, nFrame)
        ch.addSlice(str(i), stack.getProcessor(index))
    return ImagePlus("Channel " + str(nChannel), ch)
 
def duplicate_membrane_staining(channel):
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    if channel < 0 or channel > imp.getNChannels():
        IJ.log("Channel not found, session aborted")
        sys.exit()
    else:
        imp_membrane = extractChannel(imp, channel, 1)
        imp_membrane.title = imp.title + " membrane"
        imp_membrane.show()
        IJ.resetMinAndMax(imp_membrane)

def segmentation_dialog():
   gd = NonBlockingGenericDialog("Labkit Instruction")
   gd.addHelp(r"https://imagej.github.io/plugins/labkit/pixel-classification-tutorial")

   gd.addMessage("Click help button to see a Labkit tutorial. \nTo produce Labkit Output: \nGo to segmentation -> Show Segmentation Result/Probability Map in ImageJ. \nWhen the segmentation map appears in FIJI, click 'ok' to proceed")
   gd.addCheckbox("Cancel", False)
   gd.showDialog()
   checkbox = gd.getNextBoolean()
   if checkbox or gd.wasCanceled():
       IJ.log("Segmentation image was not saved")
       sys.exit()
   else:
       if gd.wasCanceled():
           IJ.log("Segmentation image was not saved")
           sys.exit()     

def labkit_segmentation():
    """segments image, continues to loop until segmentation image is saved"""
    imp = IJ.getImage()
    original_ip = imp.getProcessor().duplicate()
    imp.title = getTifTitle(imp)
    global segmentation_title
    segmentation_title = imp.title
    channel = channel_numberfield.getText()
    config["channel"] = channel
    save_config()

    duplicate_membrane_staining(int(channel))
    
    IJ.run("Brightness/Contrast...")
    WaitForUserDialog("Instructions", "Adjust Brightness and Contrast, then click ok to start Labkit").show()
    membrane_image = IJ.getImage()
    IJ.run(membrane_image, "Apply LUT", "")
    IJ.run("Open Current Image With Labkit")
    segmentation_dialog()
    segmentation_to_be_saved = True
    membrane_image.changes = False
    membrane_image.close()
    imp.setProcessor(original_ip)
    while segmentation_to_be_saved:
       segmentation_to_be_saved = save_segmentation()

def save_segmentation():
    #saves segmentation and output false, if unsaved outputs true.
    IJ.log("Saving segmentation image...")
    imp_segment = IJ.getImage()
    if "mage" in imp_segment.title:
        global segmentation_title
        imp_segment.title = segmentation_title + " segmentation"
        fs = FileSaver(imp_segment)
        fs.saveAsTiff(savedir + imp_segment.title + TIF_EXTENSION)
        IJ.log("segmentation image saved! Please proceed to Step 2 with the segmentation image.")
        return False
    else:
        IJ.log("Cannot find Labkit output! Select it and try again")
        find_seg_again = segmentation_dialog()
        if not find_seg_again:
            IJ.log("Session aborted")
            return False
        else:
            return True


########################################  Step 2: Create ROIs + cleanup  ######################################## 

def simple_segmentation_to_fiji():
    """Threshold simple segmentation to enable analyze particles"""
    imp_segment = IJ.getImage()
    imp_segment.title = getTifTitle(imp_segment)
    IJ.setThreshold(imp_segment, 1, 255)
    IJ.run(imp_segment, "Convert to Mask", "")
    #IJ.selectWindow("Threshold")
    #IJ.run("Close")
    panel = JPanel()
    gb = GridBagLayout()  
    panel.setLayout(gb)  
    pc = GridBagConstraints()
    pc.anchor = GridBagConstraints.CENTER  
    pc.fill = GridBagConstraints.BOTH

    text = JLabel("<html>Ensure cell membranes are coloured white.<br/>If not, click the invert button below, then press ok<html/>")
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 2, 1, 1
    gb.setConstraints(text, pc)
    panel.add(text)

    button = JButton("invert", actionPerformed = invert_LUT_button)
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 1, 1, 1
    gb.setConstraints(button, pc)
    panel.add(button)

    button = JButton("ok", actionPerformed = analyse_particles_buton)
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 1, 1, 1, 1, 1
    gb.setConstraints(button, pc)
    panel.add(button)

    global temp_frame 
    temp_frame= JFrame("Instructions")
    temp_frame.getContentPane().add(panel)
    temp_frame.setLocationRelativeTo(None)
    temp_frame.pack()
    temp_frame.setVisible(True)
    
def probability_to_fiji():
    """threshold probability output to enable analyze particles"""
    imp_segment = IJ.getImage()
    imp_segment.title = getTifTitle(imp_segment)
    IJ.run("Make Composite", "display=Color")
    duplicate_membrane_staining(1)
    imp_segment.changes = False # allows closing image without saving
    imp_segment.close()
    IJ.run("Threshold...")

    panel = JPanel()
    gb = GridBagLayout()  
    panel.setLayout(gb)  
    pc = GridBagConstraints()
    pc.anchor = GridBagConstraints.CENTER  
    pc.fill = GridBagConstraints.BOTH

    text = JLabel("<html>Use sliders to threshold Image, Apply -> Convert to Mask. Then ensure membranes are coloured white<br/>(use invert button to invert), then click ok.<html/>")
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 2, 1, 1
    gb.setConstraints(text, pc)
    panel.add(text)

    button = JButton("invert", actionPerformed = invert_LUT_button)
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 1, 1, 1
    gb.setConstraints(button, pc)
    panel.add(button)

    button = JButton("ok", actionPerformed = probability_to_fiji2)
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 1, 1, 1, 1, 1
    gb.setConstraints(button, pc)
    panel.add(button)

    global temp_frame 
    temp_frame= JFrame("Instructions")
    temp_frame.getContentPane().add(panel)
    temp_frame.pack()
    temp_frame.setLocationRelativeTo(None)
    temp_frame.setMinimumSize(Dimension(150, 100))
    temp_frame.setVisible(True)

def probability_to_fiji2(event):
    temp_frame.setVisible(False)
    IJ.selectWindow("Threshold")
    IJ.run("Close")
    analyse_particles()

def analyse_particles():
    """Generates ROIs in ROI manager from binary image"""
    roiManager = RoiManager.getRoiManager()
    roiManager.close()
    roiManager = RoiManager.getRoiManager()
    imp_segment = IJ.getImage()
    imp_segment.title = getTifTitle(imp_segment)
    IJ.run(imp_segment, "Options...", "iterations=1 count=1")
    panel = JPanel()
    gb = GridBagLayout()  
    panel.setLayout(gb)  
    pc = GridBagConstraints()
    pc.anchor = GridBagConstraints.CENTER  
    pc.fill = GridBagConstraints.BOTH

    text = JLabel("<html>Input minimum and maximum size and circularity for your desired Regions of Interests (ROIs).<br/>Ensure 'Clear results' and 'Add to Manager' are checked, then click ok<html/>")
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 2, 1, 1
    gb.setConstraints(text, pc)
    panel.add(text)

    global temp_frame 
    temp_frame= JFrame("Instructions")
    temp_frame.getContentPane().add(panel)
    temp_frame.pack()
    temp_frame.setLocationRelativeTo(None)
    temp_frame.setMinimumSize(Dimension(150, 100))
    temp_frame.setVisible(True)

    IJ.run("Analyze Particles...", "")
    IJ.run("Clear Results", "")
    # ROImanager will attempt to save 10 times before poping error message
    ROI_saved = saveROI_if_exist(imp_segment,"")
    save_attempt = 0
    while save_attempt < 10:
        save_attempt += 1
        if ROI_saved:
            break
        else:
            time.sleep(0.5)
            ROI_saved = saveROI_if_exist(imp_segment)
        if save_attempt == 9:
            IJ.log("ROIs could not be saved due to an error, please save ROIs manually")
            return

    IJ.log("ROIs have been generated. Please keep ROI manager open \nand proceed the analysis with cell/original images. \n(Or any file containing the correct dimensions)")
    temp_frame.setVisible(False)
    imp_segment.close()

def saveROI_if_exist(imp, name):
    """Saves ROI and returns true if ROI is saved"""
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    roiManager = RoiManager.getRoiManager() # select the correct ROI manager
    print(roiManager.getCount())
    if roiManager.getCount() > 0:
        roiManager.runCommand(imp,"Deselect")
        roiManager.save(savedir + imp.title + name + ".zip")
        IJ.log("Regions of Interests (ROIs) saved!")
        return True
    else:
        return False

def random_colour_ROI():
   """Randomly colours all ROIs in ROI manager"""
   roiManager = RoiManager.getRoiManager()
   n_roi = roiManager.getCount()
   if n_roi < 1:
      IJ.log("ROIs not found!")
   else:
      for i in range(n_roi):
         roiManager.select(i)
         random_colour_ROI_macro = """
         b = maxOf(0, 255 * random);
         r = maxOf(0, 255 * random);
         g = maxOf(50, 255 * random);
         Roi.setFillColor(r, g, b);
         """
         IJ.runMacro(random_colour_ROI_macro)

def detect_ROI_change(ROI_earlier_input, ROI_version):
   ROI_current = roiManager.getCount()
   ROI_earlier = ROI_earlier_input
   print("Loop ", ROI_version, " ROI current: ", ROI_current)
   print("Loop ", ROI_version, " ROI earlier: ", ROI_earlier)
   if (ROI_current - ROI_earlier) != 0:
        imp = IJ.getImage()
        imp.title = getTifTitle(imp)
        roiManager.save(dir + imp.title + "ROI_v" + ROI_version + ".zip")
        ROI_version += 1
        return ROI_current
   else:
        return ROI_current

def autosave_roi(save_interval):
    # requires testing
    """creates a new folder and autosaves ROI every x seconds, if number of roi changes in roi manager"""
    roiManager = RoiManager.getRoiManager()
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    ROI_earlier = roiManager.getCount()
    ROI_version = 1
    print("Loop ", ROI_version, " ROI_earlier: ", ROI_earlier)
    currenttime = datetime.now()
    dir = os.path.join(savedir, imp.title + " ROI_autosave " + currenttime.strftime('%Y%m%d'))
    while saving_status:
      time.sleep(save_interval)
      ROI_earlier = detect_ROI_change(ROI_earlier_input = ROI_earlier, ROI_version = ROI_version)
      print("Loop ", ROI_version + 1, " ROI_earlier: ", ROI_earlier)

def quicksave_ROI():
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    roiManager = RoiManager.getRoiManager()
    currenttime = datetime.now()
    dir = os.path.join(savedir, imp.title + " ROI_autosave " + currenttime.strftime('%Y%m%d') + "/")
    if not os.path.exists(dir):
        os.mkdir(dir)
    roiManager.save(dir + imp.title + "ROI_v" + currenttime.strftime('%H:%M:%S') + ".zip")

def ROI_cleanup_frame(event):
    frame = JFrame("Clean up ROI tools")
    panel1 = JPanel()

    gb = GridBagLayout()  
    panel1.setLayout(gb)  
    pc = GridBagConstraints() # Component constraint
    pc.anchor = GridBagConstraints.WEST
    

    text = JLabel("    Colour all ROIs with random colours") 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 2, 1, 1
    gb.setConstraints(text, pc)
    panel1.add(text)
    
    button = JButton("Colour ROI!", actionPerformed = colour_button) 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 2, 0, 1, 2, 1, 1
    gb.setConstraints(button, pc)
    panel1.add(button)    
 
    text = JLabel("<html>&nbsp;&nbsp;&nbsp;&nbsp;Bulk remove ROIs in enclosed region.<br/>&nbsp;&nbsp;&nbsp;&nbsp;(Using rectangle, Oval, Polygon selection tools on FIJI toolbar)<html/>") 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 2, 1, 1
    gb.setConstraints(text, pc)
    panel1.add(text)

    button = JButton("Remove ROI!", actionPerformed = bulk_remove_roi_button) 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 2, 1, 1, 2, 1, 1
    gb.setConstraints(button, pc)
    panel1.add(button)
    """
    text = JLabel("Autosave ROIs every minute") 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 2, 1, 2, 1, 1
    gb.setConstraints(text, pc)
    panel1.add(text)

    global saving_status

    button = JButton("Turn on", actionPerformed = autosave_roi_button) 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 2, 2, 1, 1, 1, 1
    gb.setConstraints(button, pc)
    panel1.add(button)
    
    button = JButton("Turn off", actionPerformed = autosave_off_button) 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 3, 2, 1, 1, 1, 1
    gb.setConstraints(button, pc)
    panel1.add(button)
    """
    text = JLabel("<html>&nbsp;&nbsp;&nbsp;&nbsp;Quicksave ROI<br/>&nbsp;&nbsp;&nbsp;&nbsp;(Creates a folder with image name and current date,<br/>&nbsp;&nbsp;&nbsp;&nbsp;each save file displays hour/min/sec in filename<html/>)") 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 2, 1, 2, 1, 1
    gb.setConstraints(text, pc)
    panel1.add(text)

    button = JButton("QuickSave", actionPerformed = quicksave_ROI_button) 
    pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 2, 2, 1, 2, 1, 1
    gb.setConstraints(button, pc)
    panel1.add(button)

    frame.getContentPane().add(panel1)
    frame.setMinimumSize(Dimension(300, 200))
    frame.pack()
    frame.setVisible(True)

def bulk_remove_roi():
    imp = IJ.getImage()
    ip_original = imp.getProcessor().duplicate()
    imp.title = getTifTitle(imp)
    intensity_input = "value=" + str(255)
    IJ.run(imp, "Set...", intensity_input)
    bulk_remove_roi_macro = """"
    roiManager("Deselect");
    close("Results");
    close("Log");
    roiManager("Measure");
    n_to_remove = 0;
    for (i = 0; i < nResults; i++) {
        roiManager("select", i);
        intensity = getResult("Min", i);
        if (intensity == 255){
            roiManager("rename", "a_to_delete");
            n_to_remove++;
        }
        else {
            roiManager("rename", "ROI" + i);
        }
    }
        
        ROI_to_remove = newArray(n_to_remove);
        for (i = 0; i < n_to_remove; i++){
            ROI_to_remove[i] = i;
        }
    roiManager("sort");
    roiManager("select", ROI_to_remove);
    if (n_to_remove > 0) {
        roiManager("delete");
    }
    roiManager("Show None");
    roiManager("Show All");
"""
    IJ.runMacro(bulk_remove_roi_macro)
    imp.setProcessor(ip_original)

def ROI_to_mask():
   imp = IJ.getImage()
   roiManager = RoiManager.getRoiManager()
   n_roi = roiManager.getCount()
   if n_roi < 1:
      IJ.log("ROIs not found!")
   else:
      for i in range(n_roi):
         roiManager.select(i)
         IJ.run(imp, "Set...", "value=" + str(i))

def blank_canvas(width, height):
    """Creates 16 bit black canvas"""
    pixels = zeros('f', width * height)
    fp = FloatProcessor(width, height, pixels, None)
    imp_canvas = ImagePlus("blank canvas", fp)
    IJ.run(imp_canvas, "16-bit", "")
    IJ.run(imp_canvas, "16-bit", "")
    imp_canvas.show()  

def get_masks_single():
   roiManager = RoiManager.getRoiManager()
   imp = IJ.getImage()
   mask_title = getTifTitle(imp) + "_masks"
   blank_canvas(imp.width, imp.height)
   ROI_to_mask()
   imp = IJ.getImage()
   IJ.run("Brightness/Contrast...")
   IJ.run(imp, "Grays", "")
   IJ.run(imp, "Enhance Contrast", "saturated=0.35")
   imp.title = mask_title
   IJ.saveAs(imp, "PNG", "/Users/yluu0013/Desktop/Temporary files/" + mask_title + ".png")
   imp.close()

def get_masks_bulk():
   input_dir = IJ.getDirectory("Choose your work directory")
   for f in os.listdir(input_dir):
      # Skip if file doesn't end in .tif
      if f[-4:] == ".tif":
            path = input_dir + str(f)
            IJ.log(path)
            imp = IJ.openImage(path).show()
            roiManager = RoiManager.getRoiManager()
            # roiManager.runCommand("Open", input_dir + str(f)[:-4] + " heatmap.zip")
            roiManager.runCommand("Open", input_dir + str(f)[:-4] + ".zip")
            # IJ.log("Processing:" + str(f))
            get_masks_single()
            roiManager.close()
            imp = IJ.getImage()
            imp.close()
   with open(config_path, "w") as f:
      json.dump(config, f)


########################################   Step 3: Heatmap generation   ######################################## 



def invert_LUT_button(event):
    imp_segment = IJ.getImage()
    imp_segment.title = getTifTitle(imp_segment)
    IJ.run(imp_segment, "Invert LUT", "")

def grayscale_ROIheatmap(parameter):
    '''Generates 8 bit grayscale heatmap for given parameter, smallest ROI with intensity = 1'''
    roiManager = RoiManager.getRoiManager()
    close_log()
    imp = IJ.getImage()
    imp.title = getHeatmapTifTitle(imp)
    imp.changes = False
    pixelsize = getPixelSize(imp)
    roiManager.runCommand(imp, "Deselect")
    roiManager.runCommand(imp, "Measure")
    saveROI_if_exist(imp, " heatmap")
    IJ.saveAs("Results", savedir + imp.title + " heatmap.csv")
    IJ.run("Summarize", "")

    imp.close()
    print("Getting results table")
    results = ResultsTable.getResultsTable()
    n_ROI = roiManager.getCount()
    print("ROI count: ", n_ROI)
    print("Result table size: ", results.size())

    minArea = results.getValue(parameter, n_ROI + 2)
    maxArea = results.getValue(parameter, n_ROI + 3)
    IJ.log("Min - Max " + parameter + ": " + str(round(minArea, 2)) + " - " + str(round(maxArea, 2)))
    print("Generating new canvas")
    blank_canvas(imp.width, imp.height)
    imp_heatmap = IJ.getImage()
    imp_heatmap.title = imp.title + " heatmap"
    imp_heatmap.changes = False
    print("Setting image measurements")
    SetMeasurement = "distance=1 known=" + str(pixelsize) + " unit=microns"
    IJ.run(imp_heatmap, "Set Scale...", SetMeasurement)

    ip = imp_heatmap.getProcessor()

    for i in range(n_ROI):
        Area = results.getValue(parameter, i)
        ratio = (Area - minArea) / (maxArea - minArea)
        intensity = round(max(1, 255 * ratio))
        roiManager.select(i)
        ip.setValue(intensity)
        ip.fill(roiManager.getRoi(i))

    imp_heatmap.updateAndDraw()
    IJ.selectWindow("Results")
    IJ.run("Close")
        
def blank_canvas(width, height):
    """Creates 8 bit black canvas"""
    pixels = zeros('f', width * height)
    fp = FloatProcessor(width, height, pixels, None)
    imp_canvas = ImagePlus("blank canvas", fp)
    IJ.run(imp_canvas, "8-bit", "")
    IJ.run(imp_canvas, "8-bit", "")
    imp_canvas.show()  

def LUT_ROIheatmap(parameter, LUT, save):
    """Generates heatmap from ROIs and an image with dimension"""
    grayscale_ROIheatmap(parameter)
    imp_heatmap = IJ.getImage()
    IJ.log(imp_heatmap.title)
    IJ.run(imp_heatmap, LUT, "")
    if save:
        IJ.log("Saving heatmap image...")
        fs = FileSaver(imp_heatmap)
        fs.saveAsTiff(savedir + imp_heatmap.title + ".tif")
        IJ.log("heatmap image saved!")
    
def getPixelSize(imp):
    """Measures pixel size in current image"""
    IJ.run("Clear Results", "")
    imp = IJ.getImage()
    IJ.run(imp, "Specify...", "width=1 height=1 x=1 y=1 slice=1")
    IJ.run(imp, "Measure", "")
    results = ResultsTable.getResultsTable()
    pixel_size = results.getValue("Width", 0)
    IJ.run("Clear Results", "")
    return pixel_size

class HeatmapPreview(AdjustmentListener, ItemListener):  
  def __init__(self, imp, slider, choice, checkbox):  

    self.imp = imp  
    self.original_ip = imp.getProcessor().duplicate() # store a copy for later resets
    self.slider = slider   
    self.choice = choice
    self.checkbox = checkbox
    IJ.log("previewer initialised")
    global inversion_state
    inversion_state = self.checkbox.getState()  

  def adjustmentValueChanged(self, event):  
    """ event: an AdjustmentEvent with data on the state of the scroll bar. """  
    self.gamma()
    self.applyLUT() 

  def itemStateChanged(self, event):  
    """ event: an ItemEvent with data on what happened to the LUT selection. """
    IJ.log("State changed involked")
    global inversion_state
    if inversion_state != self.checkbox.getState():
        self.invertLUT()
        inversion_state = self.checkbox.getState()
    else:
        self.gamma()
        self.applyLUT()
    
  def reset_gamma(self):  
    """ Undo gamma and reset to original image (only works immediately after gamma is applied) """  
    IJ.run(self.imp, "Undo", "")
    # self.imp.setProcessor(self.original_ip)

  def reset_LUT(self):
    """ Restore LUT to grays"""
    IJ.run(self.imp, "Grays", "")
    self.imp.setProcessor(self.original_ip)

  def reset_inversion(self):
      global inversion_state
      if inversion_state == True:
          IJ.run(self.imp, "Invert LUT", "")

  def gamma(self):  
    """Set gamma value """  
    self.reset_gamma()
    gamma = float(self.slider.getValue())/50
    self.imp.setRoi(1, 1, self.imp.width-1, self.imp.height-1)
    IJ.run(self.imp, "Gamma...", "value=" + str(gamma)) 
  
  def applyLUT(self):
    """apply LUT to existing heatmap"""
    LUT_index = self.choice.getSelectedIndex()
    LUT = self.choice.getItem(LUT_index)
    IJ.log("Setting heatmap colour to: " + str(LUT))
    IJ.run(self.imp, LUT, "")
    if self.checkbox.getState():
        self.invertLUT()

    
  def invertLUT(self):
      IJ.run(self.imp, "Invert LUT", "")
    
def preview_UI():
  imp = IJ.getImage()
  imp.title = getTifTitle(imp)
  gd = GenericDialog("Heatmap Preview")  
  gd.addMessage("See all available prebuilt heatmap LUTs and scalebars at: Image > Color > Display LUTs")
  heatmap_types = ["Fire", "Grays", "Ice", "Spectrum", "3-3-2 RGB", "Red", "Green", "Blue", "Cyan", "Magenta", "Yellow", "Red/Green", "16 colors", "5 ramps", "6 shades", "Cyan Hot", "Gren Fire Blue", "HiLo", "ICA", "ICA2", "ICA3", "Magenta Hot", "Orange Hot", "Rainbow RGB", "Red Hot", "Thermal", "Yellow Hot", "blue orange icb", "brgbcmyw", "cool", "edges", "gem", "glasbey", "glasbey inverted", "glasbey on dark", "glow", "mpl-inferno", "mpl-magma", "mpl-plasma", "mpl-viridis", "phase", "physics", "royal", "sepia", "smart", "thal", "thallium", "unionjack"]
  gd.addChoice("Heatmap type: ", heatmap_types, "Grays") # Choice 
  gd.addSlider("Gamma", 0.05, 5.00, 1.00)  # Slider 
  gd.addCheckbox("Invert LUT", False)
  
  # Add sliders and dropdowns for preview
  choice = gd.getChoices().get(0) 
  slider = gd.getSliders().get(0)
  checkbox = gd.getCheckboxes().get(0)
  IJ.log("Calling preview")
  previewer = HeatmapPreview(imp, slider, choice, checkbox) 
  IJ.log("Preview called")
  choice.addItemListener(previewer)
  slider.addAdjustmentListener(previewer)
  checkbox.addItemListener(previewer)
  IJ.log("Listeners added")  
  gd.showDialog()  

  #Retrieve user inputs
  parameter = parameter_list.getSelectedItem()
  config["param"] = parameter
  with open(config_path, "w") as f:
      json.dump(config, f)
  
  imp = WM.getCurrentImage()  
  if not imp:  
        IJ.log("Please open an image!")  
        return  
  
  if gd.wasCanceled():  
        previewer.reset_gamma()  
        previewer.reset_LUT()
        print("User canceled dialog!")

def custom_bin(create_input):
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    parameter = parameter_list.getSelectedItem()
    config["param"] = parameter
    with open(config_path, "w") as f:
        json.dump(config, f)
    if create_input:
        gd = GenericDialog("Custom Bin Parameters")
        gd.addMessage("Note: units of the threshold value depends on the units of your image (e.g. microns) \nIf your image does not have measurement, it will be in pixels")
        gd.addMessage("Bin colours accept a few text input (e.g. Green, Yellow, Red), or any HEX input \n(e.g. #485745), available on any colour pickers")
        bins = bin_number.getText()
        bins = int(bins)
        i = 0
        for i in range(bins):
            gd.addStringField("Select Bin" + str(i + 1) + " color", "none")
            gd.addNumericField("input lower threshold", 0)
            gd.addNumericField("input upper threshold", 0)
        gd.showDialog()
        
        cells_per_bin = [0] * bins
        lowerThreshold = [0] * bins
        upperThreshold = [0] * bins
        bincolor = [0] * bins

        i = 0
        for i in range(bins):
            bincolor[i] = gd.getNextString()
            lowerThreshold[i] = gd.getNextNumber()
            upperThreshold[i] = gd.getNextNumber()

        if gd.wasCanceled():
            return
    
    else:
        settings = OpenDialog("Load bin settings (.txt file)", None)
        settings = os.path.join(settings.getDirectory(), settings.getFileName())
        exec(open(settings).read())
        cells_per_bin = [0] * bins


    roiManager = RoiManager.getRoiManager()
    results = ResultsTable.getResultsTable()
    window_status = WM.getWindow("Results")
    if window_status is not None:
        IJ.run("Close")
    roiManager.runCommand(imp,"Deselect")
    roiManager.runCommand(imp,"Measure")
    saveROI_if_exist(imp, " heatmap")
    IJ.saveAs("Results", savedir + imp.title + " heatmap.csv")
    n_total = roiManager.getCount()

    i = 0
    for i in range(n_total):
        roiManager.select(i)
        roiManager.runCommand("Set Fill Color", "none")
    results = ResultsTable.getResultsTable()

    i = 0
    for i in range(n_total):
        roiManager.select(i)
        Area = results.getValue(parameter, i)
        j = 0
        for j in range(bins):
            if (Area > lowerThreshold[j]) & (Area <= upperThreshold[j]):
                roiManager.runCommand("Set Fill Color", str(bincolor[j]))
                cells_per_bin[j] += 1	


    pixelsize = getPixelSize(imp)
    blank_canvas(imp.width, imp.height)
    imp_heatmap = IJ.getImage()
    imp_heatmap.title = imp.title + " heatmap"
    heatmaptitle = imp_heatmap.title
    SetMeasurement = "distance=1 known=" + str(pixelsize) + " unit=microns"
    IJ.run(imp_heatmap, "Set Scale...", SetMeasurement)
    roiManager.runCommand(imp_heatmap,"Show None")
    roiManager.runCommand(imp_heatmap,"Show All")
    imp_bins = imp_heatmap.flatten()
    imp_heatmap.changes = False
    imp_heatmap.close()
    imp_bins.title = heatmaptitle
    IJ.log("Saving heatmap image...")
    fs = FileSaver(imp_bins)
    fs.saveAsTiff(savedir + imp_bins.title + ".tif")
    IJ.log("heatmap image saved!")
    IJ.selectWindow("Results")
    IJ.run("Close")

    IJ.selectWindow("Log")
    IJ.run("Close")
    bincolor = [str(i) for i in bincolor]
    IJ.log("#Select this text file with 'Use previous bin parameters' button to reuse settings for future analysis")
    IJ.log("bincolor = " + str(bincolor))
    IJ.log("lowerThreshold = " + str(lowerThreshold))
    IJ.log("upperThreshold = " + str(upperThreshold))
    IJ.log("bins = " + str(bins))
    i = 0
    for i in range(bins):
        IJ.log("#Cell count in Bin #" + str(i + 1) + ": " + str(cells_per_bin[i]))
    IJ.selectWindow("Log")
    IJ.saveAs("Text", savedir + imp_bins.title + " bin info.txt")
    IJ.openImage(savedir + imp_bins.title + ".tif").show()




########################################  Step 4: Generate Julia input code   ######################################## 


def generate_julia_input_bulk():
    input_dir = IJ.getDirectory("Choose your work directory")
    for f in os.listdir(input_dir):
        if f.endswith(".tif") and "heatmap" not in f:
            path = os.path.join(input_dir, f)
            imp = IJ.openImage(path)
            imp.show()
            generate_julia_input()
            imp.close()

def generate_julia_input():
    """Prints Julia input code using the current heatmap image to Log"""
    imp_heatmap = IJ.getImage()
    imp_heatmap.title = getTifTitle(imp_heatmap)
    path = imp_heatmap.getOriginalFileInfo().directory
    path = path.replace("\\", "/")
    
    IJ.run("Clear Results", "")
    IJ.run(imp_heatmap, "Measure", "")
    results = ResultsTable.getResultsTable()
    box_x_coord = round(results.getValue("X", 0),4)
    box_y_coord = round(results.getValue("Y", 0), 4)
    box_width = round(results.getValue("Width", 0),4)
    box_height = round(results.getValue("Height", 0),4)

    IJ.log("# Paste the following code into Julia script. Sample = " + imp_heatmap.title)
    IJ.log('image_dir = "' + path + '"')
    IJ.log('filename =  "' + imp_heatmap.title + '"')
    pixel_size = getPixelSize(imp_heatmap)
    IJ.log("pixel_length = " + str(round(pixel_size,4)))
    IJ.log("dims = (" + str(round(imp_heatmap.width * pixel_size,4)) + "," + str(round(imp_heatmap.height * pixel_size,4)) +")")
    IJ.log("region_summary = ((" + str(max(box_x_coord - box_width/2, 0)) + "," + str(max(box_x_coord + box_width/2, 0)) + "), (" + str(max(box_y_coord - box_height/2, 0)) + "," + str(max(box_y_coord + box_height/2, 0)) + "))")
    IJ.log("results = process_roi_data(image_dir,filename;pixel_length=pixel_length,dims=dims,region_summary=region_summary)")
    IJ.selectWindow("Log")
    IJ.saveAs("Text", savedir + imp_heatmap.title + " Julia input.txt")
    IJ.selectWindow("Results")
    IJ.run("Close")


########################################    Misc: UI buttons   ######################################## 

def heatmap_previewer_button(event):
    parameter = parameter_list.getSelectedItem()
    IJ.log("Heatmap for: " + parameter)
    grayscale_ROIheatmap(parameter)
    newThread = threading.Thread(target = preview_UI)
    newThread.start()
    IJ.log("Generating heatmap preview, this may take a minute.")

def generate_heatmap_bulk_button(event):
    input_dir = IJ.getDirectory("Choose your work directory")
    for f in os.listdir(input_dir):
        if f.endswith(".tif"):
            path = os.path.join(input_dir, f)
            roi_path = path[:-4] + ".zip"
            if os.path.exists(roi_path):
                imp = IJ.openImage(path)
                roiManager.open(roi_path)
                imp.show()
                generate_heatmap_button(None)
                roiManager.runCommand(imp, "Deselect")
                roiManager.runCommand(imp, "Delete")
                imp.close()
            else:
                print("ZIP file not found for", f)
            

def generate_heatmap_button(event):
    close_log()
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    parameter = parameter_list.getSelectedItem()
    config["param"] = parameter
    with open(config_path, "w") as f:
        json.dump(config, f)

    gamma = gamma_textbox.getText()
    config["gamma"] = gamma
    with open(config_path, "w") as f:
        json.dump(config, f)

    if float(gamma) < 0.05 or float(gamma) > 5:
        IJ.log("You chose gamma = " + str(gamma))
        IJ.log("Gamma must be between 0.05 and 5!")
        return
    LUT = LUT_dropdown.getSelectedItem()
    config["heatmap"] = LUT
    with open(config_path, "w") as f:
        json.dump(config, f)

    IJ.log("Generating heatmap, this may take a minute.")
    LUT_ROIheatmap(parameter, LUT, save = False)
    IJ.log("LUT: " + LUT)
    IJ.log("Gamma: " + gamma)
    imp = IJ.getImage()
    imp.title = getTifTitle(imp)
    imp.setRoi(1, 1, imp.width-1, imp.height-1)
    IJ.run(imp, "Gamma...", "value=" + gamma)
    IJ.log("Saving heatmap image...")
    fs = FileSaver(imp)
    fs.saveAsTiff(savedir + imp.title + ".tif")
    IJ.log("heatmap image saved!")
    imp.close()
    imp = IJ.openImage(savedir + imp.title + ".tif")
    imp.title = getTifTitle(imp)
    IJ.run(imp, LUT, "")
    imp.show()

def edit_LUT_button(event):
    def nonblockingdialog():
        gd = NonBlockingGenericDialog("edit LUT insturctions")
        gd.addMessage("Here you can edit the RGB colour value of your heatmap. You may save your custom heatmap Look Up Table (LUT) or open an existing saved LUT.")
        gd.addMessage("Note that the background has been designated with its own colour and changing the background colour does not change the colour of any ROIs")
        gd.addMessage("Remember to apply the same LUT to your scalebar!")
        gd.showDialog()
    def edit_lut():
        IJ.run("Edit LUT...")
    newThread = threading.Thread(target = edit_lut)
    newThread.start()
    newThread = threading.Thread(target = nonblockingdialog)
    newThread.start()

def custom_bin_button(event):
    close_log()
    custom_bin(create_input=True)

def load_bin_button(event):
    custom_bin(create_input=False)

def simple_segmentation_button(event):
   close_log()
   simple_segmentation_to_fiji()

def analyse_particles_buton(event):
    temp_frame.setVisible(False)
    analyse_particles()

def probability_button(event):
    close_log()
    probability_to_fiji()

def colour_button(event):
    IJ.log("Colouring ROIs... please wait")
    random_colour_ROI()
    IJ.log("...ROIs have been coloured")

def bulk_remove_roi_button(event):
    bulk_remove_roi()
    IJ.selectWindow("Results")
    IJ.run("Close")

def autosave_roi_button(event):
    global saving_status
    saving_status = True
    autosave_roi(save_interval = 1)
    IJ.log("Autosaving ROIs in progress...")
    
def autosave_off_button(event):
    saving_status = False
    IJ.log("Autosaving ROI cancelled")

def quicksave_ROI_button(event):
    quicksave_ROI()

def roi_to_mask_button(event):
    ROI_to_mask()

def convert_roi_to_mask_button(event):
    get_masks_single()

def labkit_button(event):
    newThread = threading.Thread(target = labkit_segmentation)
    newThread.start()
    IJ.log("Opening Labkit, please wait.")

def make_scalebar_button(event):
    def scalebar():
        gamma = gamma_textbox.getText()
        LUT = LUT_dropdown.getSelectedItem()
        imp = IJ.createImage("scalebar " + str(LUT) + " gamma" + str(gamma), "8-bit black", 256, 50, 1)
        i = 0
        for i in range(256):
            IJ.run(imp, "Specify...", "width=1 height=50 x=" + str(i) + " y=0")
            intensity_input = "value=" + str(i)
            IJ.run(imp, "Set...", intensity_input)

        IJ.run(imp, LUT, "")
        IJ.run(imp, "Gamma...", "value=" + gamma)
        imp.show()
    newThread = threading.Thread(target = scalebar)
    newThread.start()
    IJ.log("Generating scalebar, please wait.")

def cellpose_instruction_button(event):
    IJ.log("Feature in development.")
    
######################################################### Main UI ###############################################################



# Initialize configuration
def initialize_config():
    global savedir, config_path, config
    savedir = IJ.getDirectory("Choose your work directory")
    if savedir is None:
        logging.error("No work directory selected, session aborted")
        sys.exit()

    close_log()

    config_path = os.path.join(savedir, CONFIG_FILENAME)

    # Try to read saved settings
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            logging.info("Previous config: %s", config)
    except (IOError, ValueError):
        config = {
            "param": "Area",
            "channel": 1,
            "heatmap": "Please Select",
            "gamma": 1
        }
        logging.info("No config found, using default settings.")
        save_config()
        config = {
            "param": "Area",
            "channel": 1,
            "heatmap": "Please Select",
            "gamma": 1
        }
        logging.info("No config found, using default settings.")

initialize_config()

roiManager = RoiManager.getRoiManager()

IJ.run("Set Measurements...", "area mean standard modal min centroid center perimeter bounding fit shape feret's integrated median skewness kurtosis area_fraction stack display redirect=None decimal=4")

"""Master UI"""

all = JPanel() 
gb = GridBagLayout()  
all.setLayout(gb)  
c = GridBagConstraints() # Panel constraint 
pc = GridBagConstraints() # Component constraint

# Panel 1: Analysis parameter
panel1 = JPanel()
panel1.setLayout(gb)
text = JLabel("I am analysing... ") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 1, 0.33, 1
gb.setConstraints(text, pc)
panel1.add(text)

parameter_choices = ("Area", "Mean", "StdDev", "Mode", "Min", "Max", "X", "Y", "XM", "YM", "Perim.", "BX", "BY", "Width", "Height", "Major", "Minor", "Angle", "Circ.", "Feret", "IntDen", "Median", "Skew", "Kurt", "%Area", "RawIntDen", "Slice", "FeretX", "FeretY", "FeretAngle", "MinFeret", "AR", "Round", "Solidity")
parameter_list = JComboBox(parameter_choices)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 0, 1, 1, 1, 1
gb.setConstraints(parameter_list, pc)
panel1.add(parameter_list)
parameter_list.setSelectedItem(config["param"])

panel1.setBorder(BorderFactory.createTitledBorder("Analysis parameter"))
c.gridx, c.gridy, c.gridheight, c.gridwidth, c.weightx, c.weighty = 0, 0, 1, 2, 1, 0.1  
c.anchor = GridBagConstraints.CENTER  
c.fill = GridBagConstraints.BOTH
all.add(panel1, c)

# Panel 2.1: Image segmentation (Labkit)
panel2_1 = JPanel()
panel2_1.setLayout(gb)
text = JLabel("My cell/membrane staining is on channel...") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 1, 1, 1
pc.fill = GridBagConstraints.BOTH
gb.setConstraints(text, pc)
panel2_1.add(text)

channel_numberfield = JTextField(str(config["channel"]))
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 1, 1, 1
gb.setConstraints(channel_numberfield, pc)
panel2_1.add(channel_numberfield)

button = JButton("Segment with Labkit", actionPerformed = labkit_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 0, 2, 1, 1, 1
pc.anchor = GridBagConstraints.NORTHEAST  
pc.fill = GridBagConstraints.BOTH
gb.setConstraints(button, pc)
panel2_1.add(button)

text = JLabel("Select the correct segmentation output type") 
pc.anchor = GridBagConstraints.CENTER
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 2, 1, 2, 1, 1
gb.setConstraints(text, pc)
panel2_1.add(text)

button = JButton("Generate ROIs from simple segmentation output", actionPerformed = simple_segmentation_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 3, 1, 2, 1, 1
gb.setConstraints(button, pc)
panel2_1.add(button)

button = JButton("Generate ROIs from probability output", actionPerformed = probability_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 4, 1, 2, 1, 1
gb.setConstraints(button, pc)
panel2_1.add(button)

panel2_1.setBorder(BorderFactory.createTitledBorder("Step 1: Labkit segmentation"))
c.gridx, c.gridy, c.gridheight, c.gridwidth, c.weightx, c.weighty = 0, 1, 1, 1, 1, 1  
c.anchor = GridBagConstraints.CENTER  
c.fill = GridBagConstraints.BOTH
all.add(panel2_1, c)



# Panel 2.2: Convert ROI to Cellpose Masks
panel2_2 = JPanel()
panel2_2.setLayout(gb) 

button = JButton("Cellpose instructions", actionPerformed = cellpose_instruction_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 1, 1, 1
gb.setConstraints(button, pc)
panel2_2.add(button)

button = JButton("Convert ROI to Mask", actionPerformed = roi_to_mask_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 1, 1, 1
gb.setConstraints(button, pc)
panel2_2.add(button)

panel2_2.setBorder(BorderFactory.createTitledBorder("Step 1: Cellpose segmentation"))
c.gridx, c.gridy, c.gridheight, c.gridwidth, c.weightx, c.weighty = 1, 1, 1, 2, 1, 1  
c.anchor = GridBagConstraints.CENTER  
c.fill = GridBagConstraints.BOTH
all.add(panel2_2, c)

# Panel 3 ROI cleanup

panel3 = JPanel()
panel3.setLayout(gb)

button = JButton("Open ROI cleanup tools", actionPerformed = ROI_cleanup_frame)

pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 1, 1, 1
gb.setConstraints(button, pc)
panel3.add(button)

panel3.setBorder(BorderFactory.createTitledBorder("Step 2 (Optional): manual ROI cleanup"))
c.gridx, c.gridy, c.gridheight, c.gridwidth, c.weightx, c.weighty = 0, 3, 1, 2, 1, 1  
c.anchor = GridBagConstraints.CENTER  
c.fill = GridBagConstraints.BOTH
all.add(panel3, c)



# Panel 4: Generate heatmap
panel4 = JPanel()
panel4.setLayout(gb)
c.gridx, c.gridy, c.gridheight, c.gridwidth, c.weightx, c.weighty = 0, 4, 1, 1, 1, 1
panel4.setBorder(BorderFactory.createTitledBorder("Step 3: Generate ROI heatmaps"))
c.anchor = GridBagConstraints.CENTER  
c.fill = GridBagConstraints.BOTH

text = JLabel("<html>Select heatmap type and image gamma,<br/>then Generate Heatmap<html/>") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 3, 1, 1
pc.anchor = GridBagConstraints.CENTER  
gb.setConstraints(text, pc)
panel4.add(text)

text = JLabel("Heatmap type:") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 1, 1, 1
pc.anchor = GridBagConstraints.EAST
gb.setConstraints(text, pc)
panel4.add(text)

heatmap_types = ("Please Select", "Fire", "Grays", "Ice", "Spectrum", "3-3-2 RGB", "Red", "Green", "Blue", "Cyan", "Magenta", "Yellow", "Red/Green", "16 colors", "5 ramps", "6 shades", "Cyan Hot", "Gren Fire Blue", "HiLo", "ICA", "ICA2", "ICA3", "Magenta Hot", "Orange Hot", "Rainbow RGB", "Red Hot", "Thermal", "Yellow Hot", "blue orange icb", "brgbcmyw", "cool", "edges", "gem", "glasbey", "glasbey inverted", "glasbey on dark", "glow", "mpl-inferno", "mpl-magma", "mpl-plasma", "mpl-viridis", "phase", "physics", "royal", "sepia", "smart", "thal", "thallium", "unionjack")
LUT_dropdown = JComboBox(heatmap_types)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 1, 1, 1, 1, 1
pc.anchor = GridBagConstraints.WEST
gb.setConstraints(LUT_dropdown, pc)
panel4.add(LUT_dropdown)
LUT_dropdown.setSelectedItem(config["heatmap"])

button = JButton("Preview", actionPerformed = heatmap_previewer_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 2, 1, 2, 1, 1, 1
pc.anchor = GridBagConstraints.CENTER 
gb.setConstraints(button, pc)
panel4.add(button)

text = JLabel("Image gamma (0.05-5.00):") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 2, 1, 1, 1, 1
pc.anchor = GridBagConstraints.EAST
gb.setConstraints(text, pc)
panel4.add(text)

gamma_textbox = JTextField(str(config["gamma"]))
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 2, 1, 1, 1, 1
pc.anchor = GridBagConstraints.WEST
gb.setConstraints(gamma_textbox, pc)
panel4.add(gamma_textbox)

button = JButton("Generate Heatmap", actionPerformed = generate_heatmap_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 3, 2, 2, 0.5, 1
gb.setConstraints(button, pc)
panel4.add(button)

button = JButton("Bulk Generate Heatmaps", actionPerformed = generate_heatmap_bulk_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 2, 3, 2, 1, 0.5, 1
gb.setConstraints(button, pc)
panel4.add(button)

button = JButton("Make Scalebar", actionPerformed = make_scalebar_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 5, 1, 1, 1, 1
gb.setConstraints(button, pc)
panel4.add(button)

button = JButton("Edit Heatmap LUT", actionPerformed = edit_LUT_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 5, 1, 2, 1, 1
gb.setConstraints(button, pc)
panel4.add(button)

all.add(panel4, c)


# Panel 5: Colour with custom bins
panel5 = JPanel()
panel5.setLayout(gb)
c.gridx, c.gridy, c.gridheight, c.gridwidth, c.weightx, c.weighty = 1, 4, 1, 1, 1, 1
c.anchor = GridBagConstraints.CENTER  
c.fill = GridBagConstraints.BOTH
panel5.setBorder(BorderFactory.createTitledBorder("Step 3: Heatmap with bins"))

text = JLabel("Number of bins needed:") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 1, 1, 1
pc.anchor = GridBagConstraints.CENTER  
gb.setConstraints(text, pc)
panel5.add(text)

bin_number = JTextField("1") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 1, 1, 1
pc.anchor = GridBagConstraints.CENTER  
gb.setConstraints(bin_number, pc)
panel5.add(bin_number)

button = JButton("Design my bins", actionPerformed = custom_bin_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 2, 1, 1, 1, 1
pc.anchor = GridBagConstraints.CENTER  
gb.setConstraints(button, pc)
panel5.add(button)

button = JButton("Use previous bin parameters", actionPerformed = load_bin_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 3, 1, 1, 1, 1
pc.anchor = GridBagConstraints.CENTER  
gb.setConstraints(button, pc)
panel5.add(button)

all.add(panel5, c)


# Panel 6: Julia input code
panel6 = JPanel()
panel6.setLayout(gb)
c.gridx, c.gridy, c.gridheight, c.gridwidth, c.weightx, c.weighty = 0, 5, 1, 2, 1, 1
c.anchor = GridBagConstraints.CENTER  
c.fill = GridBagConstraints.BOTH 

text = JLabel("Geneate Julia input code for variation analysis with Julia") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 0, 1, 1, 1, 1
gb.setConstraints(text, pc)
panel6.add(text)

text = JLabel("<html>To analyse a specific region only: enclose the region with rectange tool,<br/>then click Generate Julia input code</html>") 
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 0, 1, 1, 1, 1, 1
gb.setConstraints(text, pc)
panel6.add(text)

def julia_button(event):
    generate_julia_input()

button = JButton("Generate Julia input code", actionPerformed = julia_button)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 0, 1, 1, 0.5, 1
gb.setConstraints(button, pc)
panel6.add(button)

button = JButton("Bulk Generate Julia Code", actionPerformed = generate_julia_input_bulk)
pc.gridx, pc.gridy, pc.gridheight, pc.gridwidth, pc.weightx, pc.weighty = 1, 1, 1, 1, 0.5, 1
gb.setConstraints(button, pc)
panel6.add(button)

panel6.setBorder(BorderFactory.createTitledBorder("Step 4 (Optional): Generate Julia input code"))
all.add(panel6, c)



frame = JFrame("fishROI")  
frame.setMinimumSize(Dimension(600, 500))
frame.getContentPane().add(all)  
frame.pack()  
frame.setVisible(True)  





with open(config_path, "w") as f:
    json.dump(config, f)

