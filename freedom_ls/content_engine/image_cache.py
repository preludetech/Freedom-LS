"""The _optimised/ cache beside a content repository's images.

No Django and no ORM imports, matching images.py's own constraint, so this is
testable against a tmp_path tree with no database. Does not import
content_save, which imports this module.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import yaml

from freedom_ls.content_engine.images import (
    ENCODE_CONSTANTS,
    SVG_SUFFIXES,
    WEBP_MIME_TYPE,
    WEBP_SUFFIX,
    ImageEncodeDecision,
    ImageEncodeStatus,
    optimise_image,
    store_source,
)

CACHE_DIR_NAME = "_optimised"
MANIFEST_NAME = "manifest.yaml"


def source_digest(raw: bytes) -> str:
    """The source bytes' identity, as an entry records it.

    Never mtime. Every clone, checkout and branch switch rewrites mtimes
    without touching a byte, so an mtime-keyed entry would miss on a fresh
    checkout and in CI, the two cases with the most to gain.
    """
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def entry_for(decision: ImageEncodeDecision, digest: str) -> dict[str, object]:
    """One entry, carrying only the fields its status calls for."""
    entry: dict[str, object] = {
        "digest": digest,
        # A copy per entry, not the module object. SafeDumper aliases a
        # repeated object, which would put an anchor on whichever entry
        # sorts first and rewrite it whenever an earlier-sorting image
        # is added.
        "encode_constants": copy.deepcopy(ENCODE_CONSTANTS),
        # PyYAML's SafeDumper has no representer for a StrEnum and raises on
        # one, so the value is taken here and the word turned back into a
        # member on the way in.
        "status": decision.status.value,
    }
    if decision.source_format is not None:
        entry["source_format"] = decision.source_format
    if decision.source_size is not None:
        # A list, not the decision's tuple. SafeDumper writes either as a
        # plain sequence, and a plain sequence is what reads back, so the
        # conversion happens once here rather than leaving the written entry
        # and the read entry different Python types.
        entry["source_size"] = list(decision.source_size)
    if (
        decision.status is ImageEncodeStatus.OPTIMISED
        and decision.stored_size is not None
    ):
        entry["lossless"] = decision.lossless
        entry["stored_size"] = list(decision.stored_size)
    if decision.status is ImageEncodeStatus.UNDECODABLE:
        entry["error"] = decision.error
    return entry


def read_manifest(manifest_path: Path) -> tuple[dict[str, object], str | None]:
    """Every entry in one manifest, plus the reason it could not be read.

    A manifest half-merged with conflict markers, truncated or hand-edited
    into nonsense cold-caches its own directory and nothing else. The cache
    is a speed optimisation over behaviour that is already correct without
    it, and a content_save that a typo in a cache file can wedge would be a
    worse failure than the slowness it was built to fix.
    """
    if not manifest_path.exists():
        return {}, None
    try:
        loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as err:
        return {}, str(err)
    if loaded is None:
        return {}, None
    if not isinstance(loaded, dict):
        return {}, f"expected a mapping of entries, found {type(loaded).__name__}"
    return loaded, None


def _pair(value: object) -> tuple[int, int] | None:
    """A recorded width and height, back as the dataclass declares them."""
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    ):
        return (value[0], value[1])
    return None


def entry_to_decision(
    entry: object, digest: str, cache_dir: Path, stored_name: str
) -> ImageEncodeDecision | None:
    """The decision this entry recorded, or None if it cannot be trusted.

    None is always a miss: re-encode from the pristine source and overwrite.
    """
    if not isinstance(entry, dict):
        return None
    if entry.get("digest") != digest:
        return None
    if entry.get("encode_constants") != ENCODE_CONSTANTS:
        return None
    try:
        status = ImageEncodeStatus(entry["status"])
    except (KeyError, ValueError):
        return None

    source_format = entry.get("source_format")
    if status is ImageEncodeStatus.UNDECODABLE:
        # The only status whose source_format is legitimately absent: a PNG
        # with a too-short IHDR fails before there is a format to name.
        if source_format is not None and not isinstance(source_format, str):
            return None
        if not isinstance(entry.get("error"), str):
            return None
    elif not isinstance(source_format, str):
        return None

    source_size = _pair(entry.get("source_size"))
    if entry.get("source_size") is not None and source_size is None:
        return None

    if status is not ImageEncodeStatus.OPTIMISED:
        return store_source(
            status,
            source_format=source_format,
            source_size=source_size,
            # Only UNDECODABLE carries one. Forwarding a stray error key on a
            # passthrough entry would break the dataclass's own contract.
            error=entry["error"] if status is ImageEncodeStatus.UNDECODABLE else None,
        )

    stored_size = _pair(entry.get("stored_size"))
    lossless = entry.get("lossless")
    if stored_size is None or source_size is None or not isinstance(lossless, bool):
        return None

    stored_path = cache_dir / stored_name
    if not stored_path.exists():
        return None
    data = stored_path.read_bytes()
    if not _webp_is_complete(data):
        return None

    return ImageEncodeDecision(
        status=status,
        source_format=source_format,
        source_size=source_size,
        data=data,
        suffix=WEBP_SUFFIX,
        mime_type=WEBP_MIME_TYPE,
        lossless=lossless,
        stored_size=stored_size,
        error=None,
    )


# RIFF: b"RIFF", a little-endian byte count that excludes those four bytes
# and its own four, then b"WEBP".
RIFF_HEADER_BYTES = 12


def _webp_is_complete(data: bytes) -> bool:
    """Whether a cached WebP is all there, from its own header.

    An interrupted checkout or a bad merge leaves a file shorter than the
    length it declares. Decoding it to find that out would cost the encode a
    hit exists to avoid.
    """
    if len(data) < RIFF_HEADER_BYTES or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False
    return len(data) >= int.from_bytes(data[4:8], "little") + 8


def _write_if_changed(target: Path, data: bytes) -> bool:
    """Write data unless the file already holds exactly it, and say whether it wrote.

    The encode is deterministic, so a run over an unchanged tree has to leave
    the working tree alone: no new bytes, no new mtimes, nothing for git
    status to show. That is what keeps the noise proportional to real image
    changes rather than to how often the command is run.
    """
    if target.exists() and target.read_bytes() == data:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return True


class ImageCache:
    """The _optimised/ cache for one run: consulted per image, written per directory.

    Holds entries, never encoded bytes. An optimised file is written the
    moment it is produced, so a run over hundreds of images does not carry
    every encode in memory to produce a manifest.
    """

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path
        self._read: dict[
            Path, dict[str, object]
        ] = {}  # cache dir -> entries found on disk
        self._entries: dict[
            Path, dict[str, object]
        ] = {}  # cache dir -> entries this run produced
        self._claims: dict[
            Path, dict[str, str]
        ] = {}  # cache dir -> stored name -> source name
        self._current: Path | None = None
        self.notices: list[str] = []
        self.written: set[Path] = set()
        self.removed: set[Path] = set()

    def decide(self, file_path: Path, raw: bytes) -> ImageEncodeDecision:
        if file_path.suffix.lower() in SVG_SUFFIXES:
            # Returns on the suffix before Pillow is ever called, so there is
            # no decode to skip and nothing to record.
            return optimise_image(raw, file_path.suffix)

        cache_dir = file_path.parent / CACHE_DIR_NAME
        if self._current is not None and self._current != cache_dir:
            # Written on the way out of a directory rather than at the end of
            # the run, so a run that fails on a later directory leaves every
            # earlier directory's cache usable and its retry fast.
            self._write_manifest(self._current)
        self._current = cache_dir

        stored_name = file_path.with_suffix(WEBP_SUFFIX).name
        self._check_claim(cache_dir, stored_name, file_path)
        entries = self._load(cache_dir)

        digest = source_digest(raw)
        decision = entry_to_decision(
            entries.get(file_path.name), digest, cache_dir, stored_name
        )
        if decision is None:
            decision = optimise_image(raw, file_path.suffix)
            # decision.data is set together with OPTIMISED and never left
            # None for it; the check narrows the type rather than a real
            # possibility.
            if (
                decision.status is ImageEncodeStatus.OPTIMISED
                and decision.data is not None
            ):
                stored_path = cache_dir / stored_name
                if _write_if_changed(stored_path, decision.data):
                    self.written.add(stored_path)

        self._entries.setdefault(cache_dir, {})[file_path.name] = entry_for(
            decision, digest
        )
        return decision

    def _load(self, cache_dir: Path) -> dict[str, object]:
        if cache_dir not in self._read:
            entries, error = read_manifest(cache_dir / MANIFEST_NAME)
            if error is not None:
                self.notices.append(
                    f"Could not read {self._relative(cache_dir / MANIFEST_NAME)}: {error}\n"
                    f"  Ignoring it. Nothing in this directory is read from the cache."
                )
            self._read[cache_dir] = entries
        return self._read[cache_dir]

    def _check_claim(self, cache_dir: Path, stored_name: str, file_path: Path) -> None:
        # Two sources differing only by extension both target one WebP name,
        # and quietly picking a winner would serve one image's bytes against
        # the other's content on every run afterwards. This fails the run
        # rather than resolving the collision, and needs no directory
        # listing: it fires for exactly the files the cache is asked about.
        #
        # Case-sensitive on purpose. Photo.JPG beside photo.png collides only
        # on a case-insensitive filesystem, where the git checkout collides
        # before the cache does, and folding the key here would fail runs on
        # the Linux repositories where those two files genuinely are distinct.
        claimed = self._claims.setdefault(cache_dir, {})
        owner = claimed.setdefault(stored_name, file_path.name)
        if owner != file_path.name:
            raise ValueError(
                f"{self._relative(file_path.parent)} holds both {owner} and "
                f"{file_path.name}, which both optimise to {stored_name}. Rename one: "
                f"an optimised file and its entry cannot belong to two source images."
            )

    def _relative(self, path: Path) -> str:
        """A path relative to the run's own root, so a notice reads the way the per-file lines already do."""
        try:
            return str(path.relative_to(self._base_path))
        except ValueError:
            return str(path)

    def write_manifests(self) -> None:
        """Write every manifest this run touched, and every one it inherited.

        Seeding from the manifests already on disk is what lets a directory
        whose last image is gone lose its manifest. Nothing in such a
        directory is scanned, because the scanner skips _optimised/ and there
        is no source image left, so nothing else would ever bring it up.
        """
        for manifest_path in self._base_path.rglob(f"{CACHE_DIR_NAME}/{MANIFEST_NAME}"):
            self._entries.setdefault(manifest_path.parent, {})
        for cache_dir in sorted(self._entries):
            self._write_manifest(cache_dir)

    def _write_manifest(self, cache_dir: Path) -> None:
        source_dir = cache_dir.parent
        carried = dict(self._entries.get(cache_dir, {}))
        # Read even for a directory nothing was scanned from, so a run
        # against one file cannot delete the rest of that directory's cache.
        # An entry survives on its source still existing, not on this run
        # having seen it.
        for name, entry in self._load(cache_dir).items():
            if name not in carried and (source_dir / name).exists():
                carried[name] = entry

        manifest_path = cache_dir / MANIFEST_NAME
        if carried:
            body = yaml.safe_dump(
                carried, sort_keys=True, default_flow_style=None, allow_unicode=True
            ).encode("utf-8")
            if _write_if_changed(manifest_path, body):
                self.written.add(manifest_path)
        elif manifest_path.exists():
            # The last image in this directory is gone, so the manifest goes too.
            manifest_path.unlink()
            self.removed.add(manifest_path)

        keep = {
            Path(name).with_suffix(WEBP_SUFFIX).name
            for name, entry in carried.items()
            if isinstance(entry, dict)
            and entry.get("status") == ImageEncodeStatus.OPTIMISED.value
        }
        for stale in sorted(cache_dir.glob(f"*{WEBP_SUFFIX}")):
            if stale.name not in keep:
                # An orphan's file is deleted when its entry is, and so is a
                # file a run that failed before its manifest was written left
                # behind.
                stale.unlink()
                self.removed.add(stale)
        if cache_dir.exists() and not any(cache_dir.iterdir()):
            cache_dir.rmdir()
