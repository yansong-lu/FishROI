# Define input and output folders
input_folder = "input_folder_dir"  
output_folder = "outputs_folder_dir"  

# Define which channel to segment on (for single channel image, specify 1)
channel_for_segmentation = 1

# Specify cellpose model path
model = "rerio_model"

# Define muscle fibre diameter (0 = according to pre-trained model)
i = 0

########################################## Update parameters above ###################################################

import os
import glob
import numpy as np
from cellpose import models, io, utils
import torch

os.makedirs(output_folder, exist_ok=True)

# Load Cellpose model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print("PyTorch will use device:", device)

# model = models.Cellpose(model_type="cyto3", device=device)
model = models.CellposeModel(pretrained_model=model)

# print("Cellpose device:", model.cp.device)
# print("Cellpose is using GPU:", model.cp.device.type == "cuda")

# Get list of image files (adjust extensions if needed)
image_files = glob.glob(os.path.join(input_folder, "*.tif"))  # Adjust extension as needed

for img_path in image_files:
    img = io.imread(img_path)
    # print(f"Evaluating {img_path} on device: {model.cp.device}")

    # Run Cellpose segmentation
    masks, flows, styles, diams = model.eval(img, diameter=i, channels=[channel_for_segmentation, 0])

    # Skip if no objects were detected
    if masks is None or np.all(masks == 0):
        print(f"Warning: No objects detected in {os.path.basename(img_path)}. Skipping.")
        continue  # Move to the next image

    # Save outlines in ImageJ format
    base_name = os.path.basename(img_path).replace(".tif", "")  # Adjust for other formats
    save_path = os.path.join(output_folder, f"{base_name}_diameter_{str(i)}.zip")
    
    try:
        io.save_rois(masks, save_path)
        print(f"Saved: {save_path}")
    except Exception as e:
        print(f"Error saving {base_name}: {e}")

print("Processing complete. Outlines saved in:", output_folder)
