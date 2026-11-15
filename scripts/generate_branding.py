import os
import math
from PIL import Image

# 1. First process the uploaded image
src_path = r'C:\Users\HP\.gemini\antigravity\brain\61eeb599-c8ec-4527-90c7-b15d8e7d6b01\.user_uploaded\media_1794728566540_484ccae6.png'
img = Image.open(src_path).convert('RGBA')

# Content bbox was: 125 135 905 468
# Crop full logo with 16px padding
crop_full = img.crop((125 - 16, 135 - 16, 905 + 16, 468 + 16))

# Center of emblem: (297, 302), radius ~ 170
cx, cy = 297, 302
half_size = 175  # 350x350 box
crop_emblem = img.crop((cx - half_size, cy - half_size, cx + half_size, cy + half_size))

# Vector SVG Mark
# Center (175, 175)
scx, scy = 175, 175
r_inner_dot = 14
r_hub = 30
r_wheel = 126
r_arrow = 153
arrow_stroke = 14
gap = 4

svg_mark = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 350 350" width="350" height="350">
  <defs>
    <mask id="quad-mask">
      <rect width="350" height="350" fill="white" />
      <rect x="0" y="{scy - gap}" width="350" height="{gap * 2}" fill="black" />
      <rect x="{scx - gap}" y="0" width="{gap * 2}" height="350" fill="black" />
    </mask>
  </defs>

  <!-- 4 Quadrants -->
  <g mask="url(#quad-mask)">
    <!-- Top-Left (Forest Green) -->
    <path d="M {scx} {scy} L {scx - r_wheel} {scy} A {r_wheel} {r_wheel} 0 0 1 {scx} {scy - r_wheel} Z" fill="#2f7a3e" />
    <!-- Top-Right (Sun/Amber Gold) -->
    <path d="M {scx} {scy} L {scx} {scy - r_wheel} A {r_wheel} {r_wheel} 0 0 1 {scx + r_wheel} {scy} Z" fill="#e0a526" />
    <!-- Bottom-Right (Soil Brown) -->
    <path d="M {scx} {scy} L {scx + r_wheel} {scy} A {r_wheel} {r_wheel} 0 0 1 {scx} {scy + r_wheel} Z" fill="#8a5a2b" />
    <!-- Bottom-Left (Sprout Light Green) -->
    <path d="M {scx} {scy} L {scx} {scy + r_wheel} A {r_wheel} {r_wheel} 0 0 1 {scx - r_wheel} {scy} Z" fill="#8dbf5a" />
  </g>

  <!-- Center Hub: White ring and green center dot -->
  <circle cx="{scx}" cy="{scy}" r="{r_hub}" fill="#ffffff" />
  <circle cx="{scx}" cy="{scy}" r="{r_inner_dot}" fill="#2f7a3e" />

  <!-- Outer curved arrow -->
  <path d="M 240 37 A {r_arrow} {r_arrow} 0 1 1 22 {scy}" fill="none" stroke="#2f7a3e" stroke-width="{arrow_stroke}" stroke-linecap="round" />
  
  <!-- Arrow Head pointing up at (22, scy) -->
  <polygon points="22,142 6,178 38,178" fill="#2f7a3e" />
</svg>'''

# Full Logo SVG (Horizontal layout)
svg_logo = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 350" width="850" height="350">
  <!-- Mark on left -->
  <g transform="translate(0, 0)">
    {svg_mark[svg_mark.find('<defs>'):svg_mark.rfind('</svg>')]}
  </g>

  <!-- Typography on right -->
  <g transform="translate(400, 0)">
    <!-- Brand Title: Field Shift -->
    <text x="0" y="150" font-family="system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-weight="900" font-size="76" letter-spacing="-1">
      <tspan fill="#1e293b">Field </tspan>
      <tspan fill="#2f7a3e">Shift</tspan>
    </text>

    <!-- Golden underline -->
    <rect x="0" y="180" width="400" height="5" rx="2.5" fill="#e0a526" />

    <!-- Project Name: Rotara -->
    <text x="0" y="235" font-family="system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-weight="800" font-size="34" fill="#0f172a" letter-spacing="-0.5">
      Rotara
    </text>

    <!-- Subtitle: Crop rotation suggestion engine -->
    <text x="0" y="280" font-family="system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-weight="500" font-size="24" fill="#64748b">
      Crop rotation suggestion engine
    </text>
  </g>
</svg>'''

target_dirs = [
    r'c:\Users\HP\OneDrive\Desktop\field-shift\fieldshift\frontend\public',
    r'c:\Users\HP\OneDrive\Desktop\field-shift\fieldshift\public'
]

for tdir in target_dirs:
    os.makedirs(tdir, exist_ok=True)
    # PNGs
    crop_full.save(os.path.join(tdir, 'rotara-logo.png'), 'PNG')
    crop_full.save(os.path.join(tdir, 'logo.png'), 'PNG')
    crop_emblem.save(os.path.join(tdir, 'rotara-mark.png'), 'PNG')
    crop_emblem.save(os.path.join(tdir, 'logo-mark.png'), 'PNG')
    
    # Standard PWA and Favicon PNG sizes
    crop_emblem.resize((512, 512), Image.Resampling.LANCZOS).save(os.path.join(tdir, 'icon-512.png'), 'PNG')
    crop_emblem.resize((192, 192), Image.Resampling.LANCZOS).save(os.path.join(tdir, 'icon-192.png'), 'PNG')
    crop_emblem.resize((64, 64), Image.Resampling.LANCZOS).save(os.path.join(tdir, 'favicon.png'), 'PNG')
    crop_emblem.resize((32, 32), Image.Resampling.LANCZOS).save(os.path.join(tdir, 'favicon-32.png'), 'PNG')
    
    # SVGs
    with open(os.path.join(tdir, 'favicon.svg'), 'w', encoding='utf-8') as f:
        f.write(svg_mark)
    with open(os.path.join(tdir, 'icon-192.svg'), 'w', encoding='utf-8') as f:
        f.write(svg_mark)
    with open(os.path.join(tdir, 'icon-512.svg'), 'w', encoding='utf-8') as f:
        f.write(svg_mark)
    with open(os.path.join(tdir, 'logo-mark.svg'), 'w', encoding='utf-8') as f:
        f.write(svg_mark)
    with open(os.path.join(tdir, 'logo.svg'), 'w', encoding='utf-8') as f:
        f.write(svg_logo)
    with open(os.path.join(tdir, 'rotara-logo.svg'), 'w', encoding='utf-8') as f:
        f.write(svg_logo)

print("Branding generation complete!")
