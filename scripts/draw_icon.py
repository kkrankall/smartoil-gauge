"""Draw the Smart Oil Gauge integration icon: a heating-oil tank part full of
oil, with a level sensor on top sending a signal. Drawn large, then scaled
down for smooth edges."""
import sys
from PIL import Image, ImageChops, ImageDraw

S = 2048 / 1024  # design in 1024 units, draw at 2048
def u(*v): return [round(x * S) for x in v]

DARK = len(sys.argv) > 2 and sys.argv[2] == "dark"
# Slate outline; a lighter one for dark themes.
OUTLINE = (144, 164, 174, 255) if DARK else (55, 71, 79, 255)
BODY    = (207, 216, 220, 255)  # light steel
OIL     = (232, 137, 12, 255)   # amber
OIL_TOP = (245, 176, 65, 255)
BLUE    = (30, 136, 229, 255)

img = Image.new("RGBA", u(1024, 1024), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Legs, behind the tank.
for x0 in (230, 724):
    d.rounded_rectangle(u(x0, 820, x0 + 70, 930), radius=round(14 * S), fill=OUTLINE)

# Tank: a stadium shape with a thick outline.
tank = u(80, 380, 944, 860)
d.rounded_rectangle(tank, radius=round(240 * S), fill=OUTLINE)
inner = u(116, 416, 908, 824)
d.rounded_rectangle(inner, radius=round(204 * S), fill=BODY)

# Oil: the inner shape below the oil line.
mask = Image.new("L", img.size, 0)
ImageDraw.Draw(mask).rounded_rectangle(inner, radius=round(204 * S), fill=255)
below = Image.new("L", img.size, 0)
ImageDraw.Draw(below).rectangle(u(0, 640, 1024, 1024), fill=255)
oil = ImageChops.multiply(mask, below)
img.paste(Image.new("RGBA", img.size, OIL), (0, 0), oil)
band = Image.new("L", img.size, 0)
ImageDraw.Draw(band).rectangle(u(0, 640, 1024, 668), fill=255)
img.paste(Image.new("RGBA", img.size, OIL_TOP), (0, 0), ImageChops.multiply(mask, band))

# Sensor on its fill pipe.
d.rectangle(u(486, 300, 538, 400), fill=OUTLINE)
d.rounded_rectangle(u(392, 222, 632, 318), radius=round(40 * S), fill=BLUE)

# Signal arcs.
for r in (88, 156):
    d.arc(u(512 - r, 222 - r, 512 + r, 222 + r), start=230, end=310,
          fill=BLUE, width=round(30 * S))

bbox = img.getbbox()
prefix = "dark_" if DARK else ""
for size, name in ((256, "icon.png"), (512, "icon@2x.png")):
    img.resize((size, size), Image.LANCZOS).save(f"{sys.argv[1]}/{prefix}{name}", optimize=True)
print("content bbox (2048 canvas):", bbox)
