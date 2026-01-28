import argparse
import os
import shutil
import cv2
import numpy as np
from PIL import Image, ImageDraw

import config

OUTPUT_FOLDER = "experiment_images"

def ensure_folder():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

def get_images():
    source_folder = config.INPUT_IMAGE_FOLDER
    if not os.path.exists(source_folder):
        print(f"Error: Source folder {source_folder} does not exist.")
        return []
    return sorted([f for f in os.listdir(source_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])

def apply_redline(img_path, filename):
    img = Image.open(img_path).convert("RGB")
    width, height = img.size
    draw = ImageDraw.Draw(img)
    
    # Draw 5px red line down the center
    center_x = width // 2
    draw.line([(center_x, 0), (center_x, height)], fill="red", width=5)
    
    save_path = os.path.join(OUTPUT_FOLDER, filename)
    img.save(save_path)
    print(f"Saved Red Line: {save_path}")

def apply_padding(img_path, filename):
    img = Image.open(img_path).convert("RGB")
    width, height = img.size
    
    half_width = width // 2
    left_part = img.crop((0, 0, half_width, height))
    right_part = img.crop((half_width, 0, width, height))
    
    padding = 50
    new_width = width + padding
    new_img = Image.new("RGB", (new_width, height), (255, 255, 255))
    
    new_img.paste(left_part, (0, 0))
    new_img.paste(right_part, (half_width + padding, 0))
    
    save_path = os.path.join(OUTPUT_FOLDER, filename)
    new_img.save(save_path)
    print(f"Saved Padding: {save_path}")

def apply_split(img_path, filename):
    img = Image.open(img_path).convert("RGB")
    width, height = img.size
    
    half_width = width // 2
    left_part = img.crop((0, 0, half_width, height))
    right_part = img.crop((half_width, 0, width, height))
    
    base, ext = os.path.splitext(filename)
    
    left_path = os.path.join(OUTPUT_FOLDER, f"{base}_L{ext}")
    right_path = os.path.join(OUTPUT_FOLDER, f"{base}_R{ext}")
    
    left_part.save(left_path)
    right_part.save(right_path)
    print(f"Saved Split: {left_path}, {right_path}")

def apply_deskew(img_path, filename):
    # Read image using OpenCV
    image = cv2.imread(img_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Invert colors (text must be white on black for contour detection)
    gray = cv2.bitwise_not(gray)
    
    # Thresholding
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Find all coordinates of white pixels (text)
    coords = np.column_stack(np.where(thresh > 0))
    
    # Minimum Area Rectangle
    angle = cv2.minAreaRect(coords)[-1]
    
    # Adjust angle
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        
    # Rotate
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    save_path = os.path.join(OUTPUT_FOLDER, filename)
    cv2.imwrite(save_path, rotated)
    print(f"Saved Deskewed ({angle:.2f} deg): {save_path}")

def main():
    parser = argparse.ArgumentParser(description="Image Pre-processor for CleanOCR Experiments")
    parser.add_argument("--mode", required=True, choices=["redline", "padding", "split", "deskew"], help="Mode of operation")
    args = parser.parse_args()
    
    ensure_folder()
    images = get_images()
    
    if not images:
        print("No images found to process.")
        return
        
    print(f"Processing {len(images)} images in mode: {args.mode}")
    
    for filename in images:
        path = os.path.join(config.INPUT_IMAGE_FOLDER, filename)
        if args.mode == "redline":
            apply_redline(path, filename)
        elif args.mode == "padding":
            apply_padding(path, filename)
        elif args.mode == "split":
            apply_split(path, filename)
        elif args.mode == "deskew":
            apply_deskew(path, filename)

if __name__ == "__main__":
    main()
