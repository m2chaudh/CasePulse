"""Generate CasePulse app icons for macOS and Windows."""
from PIL import Image, ImageDraw, ImageFont
import sys


def create_icon(size: int = 512) -> Image.Image:
    """Create a simple CasePulse icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = size // 16
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(26, 26, 46, 255),
        outline=(0, 212, 255, 255),
        width=size // 32,
    )

    # "CP" text
    font_size = size // 3
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    text = "CP"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - size // 20
    draw.text((x, y), text, fill=(0, 212, 255, 255), font=font)

    return img


def main():
    img = create_icon(512)

    # PNG for tray icon
    img.save("icon.png")
    print("Created icon.png")

    # macOS .icns (requires iconutil on macOS)
    import platform
    if platform.system() == "Darwin":
        import subprocess
        import tempfile
        from pathlib import Path

        iconset = Path(tempfile.mkdtemp()) / "CasePulse.iconset"
        iconset.mkdir()

        sizes = [16, 32, 64, 128, 256, 512]
        for s in sizes:
            resized = img.resize((s, s), Image.LANCZOS)
            resized.save(iconset / f"icon_{s}x{s}.png")
            # @2x versions
            s2 = s * 2
            if s2 <= 1024:
                resized2 = img.resize((s2, s2), Image.LANCZOS)
                resized2.save(iconset / f"icon_{s}x{s}@2x.png")

        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", "icon.icns"], check=True)
        print("Created icon.icns")

    # Windows .ico
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save("icon.ico", sizes=ico_sizes)
    print("Created icon.ico")


if __name__ == "__main__":
    main()
