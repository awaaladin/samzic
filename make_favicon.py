"""Generate static/favicon.ico to match static/favicon.svg.

One-off helper. Browsers aggressively cache favicon.ico, and some (plus most
feed readers and Windows shortcuts) ignore SVG icons entirely, so the raster
fallback has to carry the same mark rather than whatever shipped before.

Run:  ./.venv/Scripts/python.exe make_favicon.py
"""

from PIL import Image, ImageDraw

INK = (20, 20, 20, 255)
EMBER = (194, 24, 7, 255)
BONE = (244, 242, 239, 255)

# Draw large, then downsample — cheap anti-aliasing.
SIZE = 256
SCALE = SIZE / 64  # the SVG uses a 64x64 viewBox


def s(value):
    """Scale an SVG coordinate up to the working canvas."""
    return value * SCALE


image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# Rounded ink tile.
draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=int(s(14)), fill=INK)

# Ember ring.
draw.ellipse(
    [s(11), s(11), s(53), s(53)],
    outline=(194, 24, 7, 140),
    width=int(s(2.5)),
)

# Bone "S": two arcs, drawn as thick strokes.
pen = int(s(5.2))
draw.arc([s(22.5), s(18.5), s(41.5), s(33.5)], start=310, end=170, fill=BONE, width=pen)
draw.arc([s(22.5), s(30.5), s(41.5), s(45.5)], start=190, end=20, fill=BONE, width=pen)

# Ember underline.
draw.line([s(21), s(46), s(43), s(46)], fill=EMBER, width=int(s(3.4)))

# Windows/browsers pick the best size from the bundle.
image.save(
    "static/favicon.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("Wrote static/favicon.ico with sizes 16-256.")
