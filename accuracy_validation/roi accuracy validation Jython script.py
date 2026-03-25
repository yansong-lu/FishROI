# roi accuracy validation Jython script (centroid/area only, no IoU)

import os
from ij.plugin.frame import RoiManager

def get_rois_from_zip(zip_path):
    """Load ROIs from a zip file using RoiManager and return as a list of Roi objects, with fill color removed."""
    rm = RoiManager.getRoiManager()
    rm.reset()
    rm.runCommand("Open", zip_path)
    rois = []
    for i in range(rm.getCount()):
        roi = rm.getRoi(i)
        if roi is not None:
            # Remove fill color if present
            try:
                roi.setFillColor(None)
            except Exception:
                pass
            rois.append(roi)
    rm.reset()
    return rois

def get_centroid(roi):
    """Return centroid (x, y) of a Roi."""
    stats = roi.getStatistics()
    return (stats.xCentroid, stats.yCentroid)

def get_area(roi):
    """Return area of a Roi."""
    stats = roi.getStatistics()
    return stats.area

def match_rois(gt_rois, pred_rois, area_agreement_threshold=0.65):
    """
    Match predicted rois to ground-truth rois based on centroid and area agreement.
    The centroid distance threshold is set dynamically to the radius of the ground-truth ROI (assuming a perfect circle).
    If area agreement > 65% and centroids are close, consider it a match.
    """
    matched_gt = set()
    matched_pred = set()
    matches = []
    for i, gt in enumerate(gt_rois):
        gt_centroid = get_centroid(gt)
        gt_area = get_area(gt)
        # Calculate radius assuming perfect circle: area = pi * r^2
        import math
        gt_radius = math.sqrt(gt_area / math.pi) if gt_area > 0 else 0
        best_j = -1
        best_agreement = 0
        for j, pred in enumerate(pred_rois):
            if j in matched_pred:
                continue
            pred_centroid = get_centroid(pred)
            pred_area = get_area(pred)
            # Area agreement: intersection over union of areas
            min_area = min(gt_area, pred_area)
            max_area = max(gt_area, pred_area)
            if max_area == 0:
                continue
            area_agreement = min_area / max_area
            # Centroid distance
            dx = gt_centroid[0] - pred_centroid[0]
            dy = gt_centroid[1] - pred_centroid[1]
            dist = (dx**2 + dy**2) ** 0.5
            if area_agreement > area_agreement_threshold and dist < gt_radius and area_agreement > best_agreement:
                best_agreement = area_agreement
                best_j = j
        if best_j >= 0:
            matched_gt.add(i)
            matched_pred.add(best_j)
            matches.append((i, best_j, best_agreement))
    print("No. of matches: " + str(len(matches)))
    return matches, matched_gt, matched_pred

def validate_rois(gt_folder, pred_folder, output_csv_path=None):
    """Main function to validate predicted rois against ground-truth. Outputs results to Fiji log and optionally as a CSV spreadsheet."""
    from ij import IJ
    import csv

    gt_files = [f for f in os.listdir(gt_folder) if f.endswith('.zip')]
    pred_files = [f for f in os.listdir(pred_folder) if f.endswith('.zip')]
    results = []
    IJ.log("Sample,Ground-truth ROIs,Predicted ROIs,Correctly identified,False positives")
    for gt_file in gt_files:
        # Find corresponding predicted file
        pred_file = None
        for pf in pred_files:
            if pf.startswith(gt_file.replace(' heatmap.zip', '_')) or pf.startswith(gt_file.replace(' heatmap.zip', ' ')):
                pred_file = pf
                break
        if pred_file is None:
            continue
        gt_rois = get_rois_from_zip(os.path.join(gt_folder, gt_file))
        pred_rois = get_rois_from_zip(os.path.join(pred_folder, pred_file))
        matches, matched_gt, matched_pred = match_rois(gt_rois, pred_rois)
        num_correct = len(matches)
        num_gt = len(gt_rois)
        num_pred = len(pred_rois)
        num_false_positives = num_pred - len(matched_pred)
        IJ.log("%s,%d,%d,%d,%d" % (gt_file, num_gt, num_pred, num_correct, num_false_positives))
        
        results.append({
            'sample': gt_file,
            'num_gt': num_gt,
            'num_pred': num_pred,
            'num_correct': num_correct,
            'num_false_positives': num_false_positives
        })
    IJ.log("Completed %d samples." % len(results))

    # Optionally write to CSV
    if output_csv_path is not None:
        with open(output_csv_path, "w") as f:
            writer = csv.DictWriter(f, fieldnames=["sample", "num_gt", "num_pred", "num_correct", "num_false_positives"])
            writer.writeheader()
            for row in results:
                writer.writerow(row)
        IJ.log("Results written to %s" % output_csv_path)
    return results

# --- Usage example ---
# To also save as CSV, set a path like: output_csv_path = "/path/to/output.csv"
output_csv_path = None

gt_folder = os.path.expanduser("~/Desktop/FIJI_plugin_data/predictions/annotations/")

pred_folder = os.path.expanduser("~/Desktop/FIJI_plugin_data/predictions/cyto3")
results = validate_rois(gt_folder, pred_folder, output_csv_path)

pred_folder = os.path.expanduser("~/Desktop/FIJI_plugin_data/predictions/species_specific_model")
results = validate_rois(gt_folder, pred_folder, output_csv_path)

pred_folder = os.path.expanduser("~/Desktop/FIJI_plugin_data/predictions/rerio_model")
results = validate_rois(gt_folder, pred_folder, output_csv_path)











# --- Fiji overlay plot for the first sample with predictions ---
from ij import IJ, ImagePlus
from ij.gui import Overlay, Roi, ShapeRoi, RoiProperties, TextRoi, Line
from java.awt import Color

def plot_fiji_overlay(gt_rois, pred_rois, matches, matched_pred, false_positives, title="ROI Overlay", save_path=None):
    # Create a blank image (size based on all ROIs)
    all_rois = gt_rois + pred_rois
    if not all_rois:
        IJ.log("No ROIs to plot.")
        return
    bounds = [roi.getBounds() for roi in all_rois]
    min_x = min(b.x for b in bounds)
    min_y = min(b.y for b in bounds)
    max_x = max(b.x + b.width for b in bounds)
    max_y = max(b.y + b.height for b in bounds)
    width = max_x - min_x + 20
    height = max_y - min_y + 20
    imp = IJ.createImage(title, "RGB white", width, height, 1)
    overlay = Overlay()

    # Plot ground-truth ROIs in green
    for i, roi in enumerate(gt_rois):
        roi2 = roi.clone()
        roi2.setLocation(roi.getBounds().x - min_x + 10, roi.getBounds().y - min_y + 10)
        roi2.setStrokeColor(Color(0, 200, 0))
        roi2.setStrokeWidth(2)
        overlay.add(roi2)
        # Optionally, label
        label = TextRoi(roi2.getBounds().x, roi2.getBounds().y-10, "GT %d" % i)
        label.setStrokeColor(Color(0, 200, 0))
        # overlay.add(label)

    # Plot matched predicted ROIs in blue
    for _, j, _ in matches:
        roi = pred_rois[j]
        roi2 = roi.clone()
        roi2.setLocation(roi.getBounds().x - min_x + 10, roi.getBounds().y - min_y + 10)
        roi2.setStrokeColor(Color(0, 0, 255))
        roi2.setStrokeWidth(2)
        overlay.add(roi2)
        label = TextRoi(roi2.getBounds().x, roi2.getBounds().y-10, "Pred %d" % j)
        label.setStrokeColor(Color(0, 0, 255))
        # overlay.add(label)

    # Plot false positive predicted ROIs in red
    for j in false_positives:
        roi = pred_rois[j]
        roi2 = roi.clone()
        roi2.setLocation(roi.getBounds().x - min_x + 10, roi.getBounds().y - min_y + 10)
        roi2.setStrokeColor(Color(255, 0, 0))
        roi2.setStrokeWidth(2)
        overlay.add(roi2)
        label = TextRoi(roi2.getBounds().x, roi2.getBounds().y-10, "FP %d" % j)
        label.setStrokeColor(Color(255, 0, 0))
        # overlay.add(label)

    imp.setOverlay(overlay)
    imp.show()
    # Save the image if a path is provided
    if save_path is not None:
        IJ.saveAs(imp, "PNG", save_path)

# Plot for every sample with predictions and save the overlay in the prediction folder
if False:
    for gt_file in os.listdir(gt_folder):
        if not gt_file.endswith('.zip'):
            continue
        pred_file = None
        for pf in os.listdir(pred_folder):
            if pf.startswith(gt_file.replace(' heatmap.zip', ' ')) or pf.startswith(gt_file.replace(' heatmap.zip', '_')):
                pred_file = pf
                break
        if pred_file is None:
            continue
        gt_rois = get_rois_from_zip(os.path.join(gt_folder, gt_file))
        pred_rois = get_rois_from_zip(os.path.join(pred_folder, pred_file))
        matches, matched_gt, matched_pred = match_rois(gt_rois, pred_rois)
        false_positives = [j for j in range(len(pred_rois)) if j not in matched_pred]
        # Save as PNG in the prediction folder, using the same base name as the pred zip
        base_name = os.path.splitext(pred_file)[0]
        save_path = os.path.join(pred_folder, base_name + "_overlay.png")
        plot_fiji_overlay(
            gt_rois, pred_rois, matches, matched_pred, false_positives,
            title="ROI Overlay: %s" % gt_file,
            save_path=save_path
        )

