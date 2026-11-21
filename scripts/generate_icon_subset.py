"""Regenerate the bundled icon data from `node_modules/@iconify-json`.

Each icon set's `icons.json` is cut down to the glyphs `freedom_ls.icons.mappings` needs, and a
`manifest.json` records the upstream version and licence of every set. Run it after changing a
mapping or upgrading an `@iconify-json` package. `--check` reports drift without writing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Running the file by path puts scripts/ on sys.path, not the repo root, so freedom_ls is not
# importable until the root is added.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freedom_ls.icons.loader import (
    BUNDLED_DATA_DIR,
    PACKAGE_MAP,
    IconifyData,
)
from freedom_ls.icons.mappings import ICON_SETS, required_glyphs

DEFAULT_SOURCE = Path("node_modules/@iconify-json")


def build_subset(upstream: IconifyData, glyphs: set[str]) -> IconifyData:
    """The upstream prefix, root size and exactly the named glyphs' entries, copied verbatim.

    Aliases and info are dropped: the loader reads neither.
    """
    subset: IconifyData = {
        "prefix": upstream["prefix"],
        "icons": {
            name: upstream["icons"][name]
            for name in sorted(glyphs)
            if name in upstream["icons"]
        },
    }
    if "width" in upstream:
        subset["width"] = upstream["width"]
    if "height" in upstream:
        subset["height"] = upstream["height"]
    return subset


def missing_base_glyphs(set_name: str, upstream: IconifyData) -> list[str]:
    """'<semantic name> -> <glyph>' for each mapped glyph upstream lacks. These are fatal."""
    return [
        f"{semantic} -> {glyph}"
        for semantic, glyph in ICON_SETS[set_name].mapping.items()
        if glyph not in upstream["icons"]
    ]


def missing_variant_glyphs(set_name: str, upstream: IconifyData) -> list[str]:
    """Sorted required variant glyphs upstream lacks. They are recorded in the manifest.

    icons.E004 still reports them when the set is active.
    """
    base = set(ICON_SETS[set_name].mapping.values())
    return sorted(
        glyph
        for glyph in required_glyphs(set_name) - base
        if glyph not in upstream["icons"]
    )


def serialise(data: object) -> str:
    """Sorted keys, two-space indent, trailing newline, so unchanged input gives an empty diff."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=BUNDLED_DATA_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the committed files with a fresh build and write nothing.",
    )
    return parser.parse_args(argv)


def read_text_or_empty(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source: Path = args.source
    output: Path = args.output
    if not source.is_dir():
        print(f"Source directory {source} not found. Run npm install first.")
        return 1

    files: dict[Path, str] = {}
    manifest: dict[str, dict[str, object]] = {}
    new_glyph_counts: dict[str, int] = {}
    failed = False
    for set_name in ICON_SETS:
        package_dir = PACKAGE_MAP[set_name]
        upstream_dir = source / package_dir
        upstream: IconifyData = json.loads(
            (upstream_dir / "icons.json").read_text(encoding="utf-8")
        )
        package_json = json.loads(
            (upstream_dir / "package.json").read_text(encoding="utf-8")
        )
        info = json.loads((upstream_dir / "info.json").read_text(encoding="utf-8"))

        for line in missing_base_glyphs(set_name, upstream):
            print(f"{set_name}: {line} is not in {package_json['name']}")
            failed = True
        missing_variants = missing_variant_glyphs(set_name, upstream)
        for glyph in missing_variants:
            print(f"{set_name}: variant glyph {glyph} is not upstream (recorded)")

        subset = build_subset(upstream, required_glyphs(set_name))
        files[output / package_dir / "icons.json"] = serialise(subset)
        new_glyph_counts[set_name] = len(subset["icons"])
        manifest[set_name] = {
            "package": package_json["name"],
            "version": package_json["version"],
            "license": info["license"]["spdx"],
            "license_url": info["license"]["url"],
            "glyphs": sorted(subset["icons"]),
            "missing_glyphs": missing_variants,
        }
    if failed:
        return 1
    files[output / "manifest.json"] = serialise(manifest)

    if args.check:
        differing = [
            path for path, text in files.items() if read_text_or_empty(path) != text
        ]
        for path in differing:
            print(f"{path} differs from a fresh build")
        return 1 if differing else 0

    for set_name in ICON_SETS:
        old_path = output / PACKAGE_MAP[set_name] / "icons.json"
        old_text = read_text_or_empty(old_path)
        old_glyphs = len(json.loads(old_text)["icons"]) if old_text else 0
        old_version = _manifest_version(output, set_name)
        new_text = files[old_path]
        print(
            f"{set_name}: version {old_version} -> {manifest[set_name]['version']}, "
            f"glyphs {old_glyphs} -> {new_glyph_counts[set_name]}, "
            f"bytes {len(old_text.encode())} -> {len(new_text.encode())}"
        )
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return 0


def _manifest_version(output: Path, set_name: str) -> str:
    text = read_text_or_empty(output / "manifest.json")
    if not text:
        return "none"
    return str(json.loads(text).get(set_name, {}).get("version", "none"))


if __name__ == "__main__":
    raise SystemExit(main())
