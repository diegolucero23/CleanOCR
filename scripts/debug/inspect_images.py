import os
import PIL.Image

img_dir = 'workspaces/06ebe4c7-33dd-404c-99a2-67b5fc305e64/images'
for fn in sorted(os.listdir(img_dir)):
    p = os.path.join(img_dir, fn)
    sz_mb = os.path.getsize(p) / (1024 * 1024)
    with PIL.Image.open(p) as img:
        print(f"{fn}: size={sz_mb:.2f} MB, dimensions={img.size} (w={img.width}, h={img.height}), mode={img.mode}")

