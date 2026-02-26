"""Remove white/light background from logo-icon-square.png and make it transparent."""
from PIL import Image
import numpy as np

# Load the square icon
img = Image.open("frontend/public/logo-icon-square.png").convert("RGBA")
data = np.array(img)

# The image has a white border/background area
# We want to make all near-white pixels transparent
# and all near-black (dark navy) pixels transparent too (the dark bg area)

# Strategy: Keep only the ARIIA text (white) and the purple glow
# The background is either white (outer border) or very dark navy

# Step 1: Remove white outer border (pixels where R,G,B > 240)
white_mask = (data[:,:,0] > 230) & (data[:,:,1] > 230) & (data[:,:,2] > 230)
data[white_mask, 3] = 0

# Step 2: Also make very light gray pixels transparent (near-white border)
light_mask = (data[:,:,0] > 200) & (data[:,:,1] > 200) & (data[:,:,2] > 200) & (data[:,:,3] > 0)
# Fade these out proportionally
for y in range(data.shape[0]):
    for x in range(data.shape[1]):
        r, g, b, a = data[y, x]
        if a > 0 and r > 200 and g > 200 and b > 200:
            # Calculate how "white" this pixel is
            whiteness = min(r, g, b) / 255.0
            if whiteness > 0.78:
                data[y, x, 3] = int(255 * max(0, (1.0 - whiteness) / 0.22))

result = Image.fromarray(data)
result.save("frontend/public/logo-icon-square.png", "PNG")
print("Done: logo-icon-square.png background removed")

# Also create a clean version for the favicon
# Crop to content area (non-transparent)
bbox = result.getbbox()
if bbox:
    cropped = result.crop(bbox)
    # Add small padding
    pad = 8
    padded = Image.new("RGBA", (cropped.width + pad*2, cropped.height + pad*2), (0, 0, 0, 0))
    padded.paste(cropped, (pad, pad))
    padded.save("frontend/public/logo-icon-clean.png", "PNG")
    print(f"Done: logo-icon-clean.png created ({padded.width}x{padded.height})")
