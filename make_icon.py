"""One-shot helper – generates assets/icon.ico (a purple prism)."""
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
ASSETS.mkdir(exist_ok=True)

img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
# Purple radial background circle
for r in range(128, 0, -1):
    color = (60 + r, 40, 120 + (128 - r) // 2, 255)
    d.ellipse((128 - r, 128 - r, 128 + r, 128 + r), fill=color)
# Prism diamond
d.polygon([(128, 40), (210, 128), (128, 216), (46, 128)],
          outline=(255, 255, 255, 255), width=5)
d.line([(128, 40), (128, 216)], fill=(255, 255, 255, 200), width=2)
d.line([(46, 128), (210, 128)], fill=(255, 255, 255, 200), width=2)
img.save(ASSETS / "icon.ico", format="ICO",
         sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Saved:", ASSETS / "icon.ico")
