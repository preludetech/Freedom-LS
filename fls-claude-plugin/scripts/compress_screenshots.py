# ruff: noqa: T201
#!/usr/bin/env python3
"""Compress PNG screenshots in spec_dd/ to stay under the pre-commit 1024KB limit.

Usage:
    uv run --with pillow python compress_screenshots.py [--max-kb 1024] [--quality 85]
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

MAX_KB = 1024
MAX_DIMENSION = 3000  # Max width/height for screenshots


def _fit_within(img: Image.Image, max_dim: int) -> Image.Image:
    """Downscale image so neither dimension exceeds max_dim."""
    if img.width <= max_dim and img.height <= max_dim:
        return img
    ratio = min(max_dim / img.width, max_dim / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    return img.resize(new_size, Image.LANCZOS)


def compress_png(path: Path, max_kb: int, quality: int) -> bool:
    """Compress a PNG file. Returns True if the file was modified."""
    original_size = path.stat().st_size
    if original_size <= max_kb * 1024:
        return False

    img = Image.open(path)
    img = _fit_within(img, MAX_DIMENSION)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Try optimized PNG first
    png_tmp = path.with_suffix(".tmp.png")
    img.save(png_tmp, format="PNG", optimize=True)
    if png_tmp.stat().st_size <= max_kb * 1024:
        png_tmp.replace(path)
        new_size = path.stat().st_size
        print(f"  PNG optimize: {original_size // 1024}KB -> {new_size // 1024}KB")
        return True
    png_tmp.unlink()

    # Save as JPEG with decreasing quality until it fits
    jpeg_path = path.with_suffix(".jpg")
    for q in [quality, 70, 50]:
        img.save(jpeg_path, format="JPEG", quality=q, optimize=True)
        if jpeg_path.stat().st_size <= max_kb * 1024:
            path.unlink()
            new_size = jpeg_path.stat().st_size
            print(
                f"  -> JPEG (q={q}): {original_size // 1024}KB -> {new_size // 1024}KB ({jpeg_path.name})"
            )
            return True

    # Last resort: scale down further
    for scale in [0.75, 0.5, 0.35]:
        scaled = img.resize(
            (int(img.width * scale), int(img.height * scale)), Image.LANCZOS
        )
        scaled.save(jpeg_path, format="JPEG", quality=quality, optimize=True)
        if jpeg_path.stat().st_size <= max_kb * 1024:
            path.unlink()
            new_size = jpeg_path.stat().st_size
            print(
                f"  -> JPEG scaled {scale:.0%}: {original_size // 1024}KB -> {new_size // 1024}KB ({jpeg_path.name})"
            )
            return True

    jpeg_path.unlink(missing_ok=True)
    print(f"  WARNING: Could not compress below {max_kb}KB")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compress large screenshots in spec_dd/"
    )
    parser.add_argument(
        "--max-kb",
        type=int,
        default=MAX_KB,
        help=f"Maximum file size in KB (default: {MAX_KB})",
    )
    parser.add_argument(
        "--quality", type=int, default=85, help="JPEG quality 1-100 (default: 85)"
    )
    args = parser.parse_args()

    spec_dir = Path(__file__).parent / "spec_dd"
    if not spec_dir.exists():
        print("spec_dd/ directory not found")
        sys.exit(1)

    large_files = sorted(
        p for p in spec_dir.rglob("*.png") if p.stat().st_size > args.max_kb * 1024
    )

    if not large_files:
        print(f"No PNG files over {args.max_kb}KB found in spec_dd/")
        return

    print(f"Found {len(large_files)} file(s) over {args.max_kb}KB:\n")
    modified = 0
    for path in large_files:
        print(f"{path.relative_to(spec_dir)} ({path.stat().st_size // 1024}KB)")
        if compress_png(path, args.max_kb, args.quality):
            modified += 1
        print()

    print(f"Done. {modified}/{len(large_files)} files compressed.")


if __name__ == "__main__":
    main()
