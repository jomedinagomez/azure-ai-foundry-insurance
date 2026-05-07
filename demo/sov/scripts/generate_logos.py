"""Generate simple broker logo PNGs (one per broker) for use in HTML email signatures."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from seed_data import ACCOUNTS, ROOT

LOGO_DIR = ROOT / "emails" / "signatures"


def _font(size: int) -> ImageFont.FreeTypeFont:
    # Try a common Windows font; fall back to PIL default.
    for path in (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def make_logo(name: str, color_hex: str, out_path: Path) -> None:
    """Render a 480x100 logo: colored bar + monogram + broker name."""
    W, H = 480, 100
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    color = _hex_to_rgb(color_hex)

    # Colored mark on the left
    draw.rectangle([(0, 0), (90, H)], fill=color)
    # Monogram (first letters of first two words)
    parts = name.split()
    monogram = "".join(p[0] for p in parts[:2]).upper()
    mono_font = _font(48)
    bbox = draw.textbbox((0, 0), monogram, font=mono_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((90 - tw) / 2, (H - th) / 2 - 4), monogram, fill="white", font=mono_font)

    # Broker name on the right
    name_font = _font(22)
    draw.text((105, 22), name, fill=color, font=name_font)
    sub_font = _font(14)
    draw.text((105, 56), "Insurance Brokerage", fill=(90, 90, 90), font=sub_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


def main() -> None:
    print("Generating broker logos...")
    for i, acc in enumerate(ACCOUNTS, start=1):
        out = LOGO_DIR / f"{i:02d}_{acc.key}_logo.png"
        make_logo(acc.broker.name, acc.broker.color, out)
        print(f"  wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
