#!/usr/bin/env python3
"""Generate all favicon variants from the ARIIA logo icon."""
from PIL import Image, ImageDraw
import os

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")
ICON_SRC = os.path.join(BASE_DIR, "logo-icon-square.png")

def create_favicon_from_logo():
    """Create favicon variants from the square ARIIA logo."""
    img = Image.open(ICON_SRC).convert("RGBA")
    
    # The source image has a dark square on white background
    # We need to crop to just the dark square with the logo
    # Find the dark region
    width, height = img.size
    
    # Crop to the central dark square (approximately)
    # The image has white borders around a dark navy square
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    
    # Now find the actual dark content area
    pixels = img.load()
    w, h = img.size
    
    # Find bounds of the dark area
    left, top, right, bottom = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            # Dark pixels (navy/dark background)
            if r < 50 and g < 50 and b < 80 and a > 200:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)
    
    if right > left and bottom > top:
        # Add small padding
        pad = 5
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(w, right + pad)
        bottom = min(h, bottom + pad)
        img = img.crop((left, top, right, bottom))
    
    # Make it square
    w, h = img.size
    size = max(w, h)
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - w) // 2, (size - h) // 2)
    square.paste(img, offset)
    
    # Generate all sizes
    sizes = {
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "favicon-96x96.png": 96,
        "apple-touch-icon.png": 180,
        "web-app-manifest-192x192.png": 192,
        "web-app-manifest-512x512.png": 512,
    }
    
    for filename, size in sizes.items():
        resized = square.resize((size, size), Image.LANCZOS)
        output_path = os.path.join(BASE_DIR, filename)
        resized.save(output_path, "PNG", optimize=True)
        print(f"  Created {filename} ({size}x{size})")
    
    # Generate ICO file (multi-resolution)
    ico_sizes = [16, 32, 48, 64]
    ico_images = [square.resize((s, s), Image.LANCZOS) for s in ico_sizes]
    ico_path = os.path.join(BASE_DIR, "favicon.ico")
    ico_images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=ico_images[1:])
    print(f"  Created favicon.ico (multi-res: {ico_sizes})")
    
    # Also copy to app directory for Next.js
    app_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "app")
    import shutil
    shutil.copy2(ico_path, os.path.join(app_dir, "favicon.ico"))
    print(f"  Copied favicon.ico to app/")
    
    # Generate SVG favicon (simplified)
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0a0b1a;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#111233;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#7c5cfc;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#a78bfa;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="96" fill="url(#bg)"/>
  <text x="256" y="310" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-weight="900" font-size="200" fill="white" letter-spacing="-8">A</text>
  <circle cx="310" cy="200" r="18" fill="url(#glow)" opacity="0.9"/>
  <circle cx="370" cy="280" r="12" fill="url(#glow)" opacity="0.7"/>
  <line x1="310" y1="200" x2="370" y2="280" stroke="url(#glow)" stroke-width="4" opacity="0.6"/>
</svg>'''
    
    svg_path = os.path.join(BASE_DIR, "favicon.svg")
    with open(svg_path, "w") as f:
        f.write(svg_content)
    print(f"  Created favicon.svg")
    
    # Remove old oversized icon.svg
    old_icon = os.path.join(app_dir, "icon.svg")
    if os.path.exists(old_icon) and os.path.getsize(old_icon) > 1_000_000:
        os.remove(old_icon)
        print(f"  Removed oversized icon.svg (was {os.path.getsize(old_icon) if os.path.exists(old_icon) else 'N/A'})")

if __name__ == "__main__":
    print("Generating ARIIA favicons...")
    create_favicon_from_logo()
    print("Done!")
