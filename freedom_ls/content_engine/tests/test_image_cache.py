"""Unit tests for ImageCache: bytes and files on a tmp_path tree, no database."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml
from PIL import Image

from freedom_ls.content_engine.image_cache import (
    CACHE_DIR_NAME,
    MANIFEST_NAME,
    ImageCache,
    read_manifest,
    source_digest,
)
from freedom_ls.content_engine.images import ENCODE_CONSTANTS, ImageEncodeStatus
from freedom_ls.tests.images import (
    already_minimal_png_bytes,
    animated_gif_bytes,
    break_png_chunk_crc,
    jpeg_bytes,
    photographic_jpeg_bytes,
    png_bytes,
)

# Large enough that optimise_image actually shrinks it, so tests that need a
# genuine OPTIMISED result don't depend on tuning noise levels to get there.
_PHOTO_WIDTH = 1800
_PHOTO_HEIGHT = 1350


def _distinguishable_webp_bytes() -> bytes:
    """A tiny, valid WebP that no encode of any fixture in this file could produce.

    Every real source here is either a large photograph or a small solid-fill
    image; a 3x3 lossless WebP of an arbitrary colour cannot come from
    optimising either, so getting these bytes back proves the encode was
    skipped.
    """
    buf = io.BytesIO()
    Image.new("RGB", (3, 3), (1, 2, 3)).save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def _plant_optimised_entry(
    cache_dir: Path,
    source_name: str,
    raw: bytes,
    *,
    encode_constants: dict[str, object] | None = None,
    source_format: str | None = "JPEG",
    include_source_format: bool = True,
) -> bytes:
    """Hand-write a manifest entry and stored WebP that entry_to_decision should accept for raw.

    Returns the planted WebP bytes, so a test can assert whether they do or
    do not come back from a later decide() call.
    """
    stored_name = Path(source_name).with_suffix(".webp").name
    planted = _distinguishable_webp_bytes()
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / stored_name).write_bytes(planted)
    entry: dict[str, object] = {
        "digest": source_digest(raw),
        "encode_constants": encode_constants
        if encode_constants is not None
        else dict(ENCODE_CONSTANTS),
        "status": ImageEncodeStatus.OPTIMISED.value,
        "source_size": [10, 10],
        "lossless": True,
        "stored_size": [3, 3],
    }
    if include_source_format:
        entry["source_format"] = source_format
    (cache_dir / MANIFEST_NAME).write_text(
        yaml.safe_dump({source_name: entry}, sort_keys=True), encoding="utf-8"
    )
    return planted


def test_cold_directory_optimises_and_writes_webp_and_manifest_entry(
    tmp_path: Path,
) -> None:
    raw = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(raw)

    cache = ImageCache(tmp_path)
    decision = cache.decide(file_path, raw)
    cache.write_manifests()

    assert decision.status is ImageEncodeStatus.OPTIMISED
    cache_dir = tmp_path / CACHE_DIR_NAME
    assert (cache_dir / "photo.webp").read_bytes() == decision.data
    entries, error = read_manifest(cache_dir / MANIFEST_NAME)
    assert error is None
    assert list(entries) == ["photo.jpg"]


def test_planted_valid_entry_returns_the_planted_bytes(tmp_path: Path) -> None:
    raw = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    planted = _plant_optimised_entry(cache_dir, "photo.jpg", raw)

    decision = ImageCache(tmp_path).decide(file_path, raw)

    assert decision.data == planted


def test_second_run_over_written_tree_writes_nothing_and_matches(
    tmp_path: Path,
) -> None:
    raw = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(raw)
    first = ImageCache(tmp_path)
    first_decision = first.decide(file_path, raw)
    first.write_manifests()
    manifest_path = tmp_path / CACHE_DIR_NAME / MANIFEST_NAME
    before = manifest_path.read_bytes()

    second = ImageCache(tmp_path)
    second_decision = second.decide(file_path, raw)
    second.write_manifests()

    assert second_decision == first_decision
    assert not second.written
    assert manifest_path.read_bytes() == before


def test_changed_source_bytes_do_not_return_the_planted_bytes(tmp_path: Path) -> None:
    original = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    changed = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(changed)
    cache_dir = tmp_path / CACHE_DIR_NAME
    planted = _plant_optimised_entry(cache_dir, "photo.jpg", original)

    decision = ImageCache(tmp_path).decide(file_path, changed)

    assert decision.data != planted


def test_stale_encode_constant_is_a_miss(tmp_path: Path) -> None:
    raw = png_bytes()
    file_path = tmp_path / "diagram.png"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    stale_constants = dict(ENCODE_CONSTANTS, lossy_quality=75)
    planted = _plant_optimised_entry(
        cache_dir,
        "diagram.png",
        raw,
        encode_constants=stale_constants,
        source_format="PNG",
    )

    decision = ImageCache(tmp_path).decide(file_path, raw)

    assert decision.data != planted


def test_stale_encode_version_is_a_miss(tmp_path: Path) -> None:
    raw = png_bytes()
    file_path = tmp_path / "diagram.png"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    stale_constants = dict(ENCODE_CONSTANTS, encode_version=999)
    planted = _plant_optimised_entry(
        cache_dir,
        "diagram.png",
        raw,
        encode_constants=stale_constants,
        source_format="PNG",
    )

    decision = ImageCache(tmp_path).decide(file_path, raw)

    assert decision.data != planted


def test_missing_webp_file_is_a_miss_and_is_written_again(tmp_path: Path) -> None:
    raw = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    _plant_optimised_entry(cache_dir, "photo.jpg", raw)
    (cache_dir / "photo.webp").unlink()

    decision = ImageCache(tmp_path).decide(file_path, raw)

    assert decision.status is ImageEncodeStatus.OPTIMISED
    assert (cache_dir / "photo.webp").read_bytes() == decision.data


def test_truncated_webp_file_is_a_miss_and_is_written_again(tmp_path: Path) -> None:
    raw = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    planted = _plant_optimised_entry(cache_dir, "photo.jpg", raw)
    stored = cache_dir / "photo.webp"
    stored.write_bytes(planted[: len(planted) // 2])

    decision = ImageCache(tmp_path).decide(file_path, raw)

    assert decision.status is ImageEncodeStatus.OPTIMISED
    assert (cache_dir / "photo.webp").read_bytes() == decision.data


def test_optimised_entry_without_source_format_is_a_miss(tmp_path: Path) -> None:
    raw = png_bytes()
    file_path = tmp_path / "diagram.png"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    planted = _plant_optimised_entry(
        cache_dir, "diagram.png", raw, include_source_format=False
    )

    decision = ImageCache(tmp_path).decide(file_path, raw)

    assert decision.data != planted


def test_kept_source_status_round_trips_across_runs(tmp_path: Path) -> None:
    raw = already_minimal_png_bytes()
    file_path = tmp_path / "tiny.png"
    file_path.write_bytes(raw)
    first = ImageCache(tmp_path)
    first_decision = first.decide(file_path, raw)
    first.write_manifests()

    second_decision = ImageCache(tmp_path).decide(file_path, raw)

    assert first_decision.status is ImageEncodeStatus.KEPT_SOURCE
    assert second_decision == first_decision


def test_undecodable_error_text_round_trips_across_runs(tmp_path: Path) -> None:
    raw = break_png_chunk_crc(png_bytes())
    file_path = tmp_path / "corrupt.png"
    file_path.write_bytes(raw)
    first = ImageCache(tmp_path)
    first_decision = first.decide(file_path, raw)
    first.write_manifests()

    second_decision = ImageCache(tmp_path).decide(file_path, raw)

    assert first_decision.status is ImageEncodeStatus.UNDECODABLE
    assert second_decision.error == first_decision.error


def test_passthrough_status_round_trips_across_runs(tmp_path: Path) -> None:
    raw = animated_gif_bytes()
    file_path = tmp_path / "animation.gif"
    file_path.write_bytes(raw)
    first = ImageCache(tmp_path)
    first_decision = first.decide(file_path, raw)
    first.write_manifests()

    second_decision = ImageCache(tmp_path).decide(file_path, raw)

    assert first_decision.status is ImageEncodeStatus.PASSTHROUGH
    assert second_decision == first_decision


def test_svg_gets_no_entry_and_no_cache_directory(tmp_path: Path) -> None:
    raw = b"<svg></svg>"
    file_path = tmp_path / "diagram.svg"
    file_path.write_bytes(raw)
    cache = ImageCache(tmp_path)

    cache.decide(file_path, raw)
    cache.write_manifests()

    assert not (tmp_path / CACHE_DIR_NAME).exists()


def test_orphan_entry_and_file_are_removed(tmp_path: Path) -> None:
    raw = already_minimal_png_bytes()
    file_path = tmp_path / "tiny.png"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    cache_dir.mkdir(parents=True)
    orphan_webp = cache_dir / "ghost.webp"
    orphan_webp.write_bytes(_distinguishable_webp_bytes())
    (cache_dir / MANIFEST_NAME).write_text(
        yaml.safe_dump(
            {
                "ghost.jpg": {
                    "digest": "sha256:deadbeef",
                    "encode_constants": dict(ENCODE_CONSTANTS),
                    "status": ImageEncodeStatus.OPTIMISED.value,
                    "source_format": "JPEG",
                    "source_size": [10, 10],
                    "lossless": True,
                    "stored_size": [3, 3],
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    cache = ImageCache(tmp_path)
    cache.decide(file_path, raw)
    cache.write_manifests()

    entries, error = read_manifest(cache_dir / MANIFEST_NAME)
    assert error is None
    assert "ghost.jpg" not in entries
    assert not orphan_webp.exists()


def test_entry_not_scanned_this_run_survives_when_its_source_still_exists(
    tmp_path: Path,
) -> None:
    raw_a = already_minimal_png_bytes()
    raw_b = png_bytes(width=5, height=5)
    file_a = tmp_path / "a.png"
    file_b = tmp_path / "b.png"
    file_a.write_bytes(raw_a)
    file_b.write_bytes(raw_b)
    populate = ImageCache(tmp_path)
    populate.decide(file_a, raw_a)
    populate.decide(file_b, raw_b)
    populate.write_manifests()

    single_file_run = ImageCache(tmp_path)
    single_file_run.decide(file_a, raw_a)
    single_file_run.write_manifests()

    entries, error = read_manifest(tmp_path / CACHE_DIR_NAME / MANIFEST_NAME)
    assert error is None
    assert set(entries) == {"a.png", "b.png"}


def test_last_source_gone_removes_manifest_and_cache_directory(tmp_path: Path) -> None:
    raw = already_minimal_png_bytes()
    file_path = tmp_path / "tiny.png"
    file_path.write_bytes(raw)
    first = ImageCache(tmp_path)
    first.decide(file_path, raw)
    first.write_manifests()
    file_path.unlink()

    ImageCache(tmp_path).write_manifests()

    assert not (tmp_path / CACHE_DIR_NAME).exists()


def test_unclaimed_webp_file_is_removed_by_write_manifests(tmp_path: Path) -> None:
    raw = photographic_jpeg_bytes(_PHOTO_WIDTH, _PHOTO_HEIGHT)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(raw)
    cache = ImageCache(tmp_path)
    cache.decide(file_path, raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    stray = cache_dir / "stray.webp"
    stray.write_bytes(_distinguishable_webp_bytes())

    cache.write_manifests()

    assert not stray.exists()
    assert (cache_dir / "photo.webp").exists()


def test_manifest_with_conflict_markers_re_encodes_and_reports_a_notice(
    tmp_path: Path,
) -> None:
    raw = already_minimal_png_bytes()
    file_path = tmp_path / "tiny.png"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    cache_dir.mkdir(parents=True)
    (cache_dir / MANIFEST_NAME).write_text(
        "<<<<<<< ours\ntiny.png:\n  digest: sha256:aaa\n"
        "=======\ntiny.png:\n  digest: sha256:bbb\n>>>>>>> theirs\n",
        encoding="utf-8",
    )

    cache = ImageCache(tmp_path)
    decision = cache.decide(file_path, raw)
    cache.write_manifests()

    assert decision.status is ImageEncodeStatus.KEPT_SOURCE
    assert len(cache.notices) == 1
    assert f"{CACHE_DIR_NAME}/{MANIFEST_NAME}" in cache.notices[0]
    entries, error = read_manifest(cache_dir / MANIFEST_NAME)
    assert error is None
    assert "tiny.png" in entries


def test_manifest_parsed_as_a_list_re_encodes_and_reports_a_notice(
    tmp_path: Path,
) -> None:
    raw = already_minimal_png_bytes()
    file_path = tmp_path / "tiny.png"
    file_path.write_bytes(raw)
    cache_dir = tmp_path / CACHE_DIR_NAME
    cache_dir.mkdir(parents=True)
    (cache_dir / MANIFEST_NAME).write_text("- one\n- two\n", encoding="utf-8")

    cache = ImageCache(tmp_path)
    decision = cache.decide(file_path, raw)
    cache.write_manifests()

    assert decision.status is ImageEncodeStatus.KEPT_SOURCE
    assert len(cache.notices) == 1
    entries, error = read_manifest(cache_dir / MANIFEST_NAME)
    assert error is None
    assert "tiny.png" in entries


def test_two_sources_targeting_the_same_webp_name_raises(tmp_path: Path) -> None:
    jpg_path = tmp_path / "photo.jpg"
    png_path = tmp_path / "photo.png"
    jpg_raw = jpeg_bytes()
    png_raw = png_bytes()
    jpg_path.write_bytes(jpg_raw)
    png_path.write_bytes(png_raw)
    cache = ImageCache(tmp_path)
    cache.decide(jpg_path, jpg_raw)

    with pytest.raises(ValueError, match=r"photo\.jpg") as exc_info:
        cache.decide(png_path, png_raw)

    assert "photo.png" in str(exc_info.value)
    assert "photo.webp" in str(exc_info.value)


def test_failure_in_second_directory_leaves_first_directorys_manifest_written(
    tmp_path: Path,
) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    raw_a = png_bytes()
    (dir_a / "diagram.png").write_bytes(raw_a)
    jpg_raw = jpeg_bytes()
    png_raw = png_bytes()
    (dir_b / "photo.jpg").write_bytes(jpg_raw)
    (dir_b / "photo.png").write_bytes(png_raw)

    cache = ImageCache(tmp_path)
    cache.decide(dir_a / "diagram.png", raw_a)
    cache.decide(dir_b / "photo.jpg", jpg_raw)
    with pytest.raises(ValueError, match=r"photo\.webp"):
        cache.decide(dir_b / "photo.png", png_raw)

    entries, error = read_manifest(dir_a / CACHE_DIR_NAME / MANIFEST_NAME)
    assert error is None
    assert "diagram.png" in entries


def test_manifest_with_multiple_entries_has_no_yaml_anchors_or_aliases(
    tmp_path: Path,
) -> None:
    """The approved deviation from entry_for's plain ENCODE_CONSTANTS reference.

    Recording the shared module dict object directly would make SafeDumper
    alias every repeated occurrence, anchoring whichever entry sorts first
    and rewriting that line whenever an earlier-sorting image is added.
    """
    raw_a = png_bytes(width=5, height=5)
    raw_b = png_bytes(width=6, height=6)
    file_a = tmp_path / "a.png"
    file_b = tmp_path / "b.png"
    file_a.write_bytes(raw_a)
    file_b.write_bytes(raw_b)
    cache = ImageCache(tmp_path)
    cache.decide(file_a, raw_a)
    cache.decide(file_b, raw_b)

    cache.write_manifests()

    manifest_text = (tmp_path / CACHE_DIR_NAME / MANIFEST_NAME).read_text(
        encoding="utf-8"
    )
    assert "&id" not in manifest_text
    assert "*id" not in manifest_text
    entries, error = read_manifest(tmp_path / CACHE_DIR_NAME / MANIFEST_NAME)
    assert error is None
    entry_a, entry_b = entries["a.png"], entries["b.png"]
    assert isinstance(entry_a, dict)
    assert isinstance(entry_b, dict)
    assert entry_a["encode_constants"] == ENCODE_CONSTANTS
    assert entry_b["encode_constants"] == ENCODE_CONSTANTS
