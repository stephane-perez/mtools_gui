"""One-off script to draw packaging/appimage/icon.png with Pillow -
avoids depending on a working SVG renderer (rsvg-convert isn't
installed and ImageMagick's built-in SVG support is too limited to
render gradients/paths correctly). Run manually if the icon ever needs
regenerating: `python3 generate_icon.py`.
"""

from PIL import Image, ImageDraw

SIZE = 256
BG_TOP = (58, 110, 165, 255)
BG_BOTTOM = (31, 74, 115, 255)
FOLDER = (244, 247, 251, 255)


def folder_path(x: float, y: float, w: float, h: float, tab_w: float, tab_h: float):
    return [
        (x, y + tab_h),
        (x + tab_w, y + tab_h),
        (x + tab_w + 10, y),
        (x + w - 10, y),
        (x + w, y + tab_h),
        (x + w, y + h),
        (x, y + h),
    ]


def main() -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for row in range(SIZE):
        t = row / (SIZE - 1)
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(4))
        draw.line([(0, row), (SIZE, row)], fill=color)

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=40, fill=255)
    bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bg.paste(img, (0, 0), mask)
    img = bg
    draw = ImageDraw.Draw(img)

    # Two panes, a visible gap between them - reads as a two-pane file
    # manager without needing arrows (tried; at this size they either
    # overlapped the folders or vanished against the same fill color).
    left = folder_path(24, 88, 92, 96, 28, 16)
    right = folder_path(140, 88, 92, 96, 28, 16)
    draw.polygon(left, fill=FOLDER)
    draw.polygon(right, fill=FOLDER)

    img.save("mtools_gui.png")
    print("wrote mtools_gui.png")


if __name__ == "__main__":
    main()
