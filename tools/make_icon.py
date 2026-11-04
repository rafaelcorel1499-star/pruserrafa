"""Genera assets/icon.ico (círculo morado con una N blanca)."""
from pathlib import Path
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse((8, 8, S - 8, S - 8), fill=(139, 31, 232, 255))
d.line([(88, 180), (88, 76), (168, 180), (168, 76)], fill="white", width=26, joint="curve")
out = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
out.parent.mkdir(exist_ok=True)
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Icono generado:", out)
