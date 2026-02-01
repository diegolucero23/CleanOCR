import cv2
import numpy as np
from PIL import Image

def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """
    Applies production pre-processing to a PIL Image:
    1. Deskew (correct rotation)
    2. Add Padding (split center gutter)
    """
    # 1. Deskew
    # Convert PIL to CV2 (OpenCV uses BGR, PIL uses RGB)
    open_cv_image = np.array(pil_image) 
    # Convert RGB to BGR 
    open_cv_image = open_cv_image[:, :, ::-1].copy() 
    
    deskewed_cv = _deskew(open_cv_image)
    
    # 2. Add Padding
    padded_cv = _add_padding(deskewed_cv)
    
    # Convert back to PIL
    # Convert BGR to RGB
    final_rgb = cv2.cvtColor(padded_cv, cv2.COLOR_BGR2RGB)
    return Image.fromarray(final_rgb)

def _deskew(cv_image: np.ndarray) -> np.ndarray:
    """
    Detects text orientation and rotates the image to be vertical.
    """
    try:
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Invert colors (text must be white on black for contour detection)
        gray = cv2.bitwise_not(gray)
        
        # Thresholding
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        
        # Find all coordinates of white pixels (text)
        coords = np.column_stack(np.where(thresh > 0))
        
        if coords.size == 0:
            print("Warning: No text found for deskewing. Skipping.")
            return cv_image

        # Minimum Area Rectangle
        angle = cv2.minAreaRect(coords)[-1]
        
        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        # If angle is negligible, skip rotation to avoid interpolation artifacts
        if abs(angle) < 0.01:
            return cv_image
            
        # Rotate
        (h, w) = cv_image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(cv_image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        
        print(f"debug: Deskewed by {angle:.2f} degrees")
        return rotated
        
    except Exception as e:
        print(f"Error during deskew: {e}. Returning original.")
        return cv_image

def _add_padding(cv_image: np.ndarray, padding_px: int = 50) -> np.ndarray:
    """
    Splits the image vertically and adds a white gutter in the center.
    """
    try:
        height, width = cv_image.shape[:2]
        half_width = width // 2
        
        left_part = cv_image[0:height, 0:half_width]
        right_part = cv_image[0:height, half_width:width]
        
        # Create new white canvas
        new_width = width + padding_px
        # Initialize with white (255)
        new_img = np.full((height, new_width, 3), 255, dtype=np.uint8)
        
        # Paste left part
        new_img[0:height, 0:half_width] = left_part
        
        # Paste right part (shifted by padding)
        new_img[0:height, half_width+padding_px:new_width] = right_part
        
        return new_img
    except Exception as e:
        print(f"Error during padding: {e}. Returning original.")
        return cv_image
