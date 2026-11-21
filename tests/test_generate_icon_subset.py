"""Tests for `scripts/generate_icon_subset.py`.

The file is split in two. The tests that build a fixture source in `tmp_path` test a developer
script and carry the `dev_tooling` marker. The tests at the bottom compare the committed bundled
data with the installed `node_modules/@iconify-json` packages and stay unmarked, so the default
run and CI catch data that has drifted from upstream.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from freedom_ls.icons.loader import (
    BUNDLED_DATA_DIR,
    PACKAGE_MAP,
    IconifyData,
)
from freedom_ls.icons.mappings import ICON_SETS, IconSetConfig, required_glyphs
from scripts import generate_icon_subset
from scripts.generate_icon_subset import DEFAULT_SOURCE, build_subset, main

REPO_ROOT = Path(__file__).resolve().parents[1]
REGENERATE_COMMAND = "uv run python scripts/generate_icon_subset.py"

# Parsed from JSON so it carries the upstream keys the loader's types do not name.
UPSTREAM: IconifyData = json.loads(
    json.dumps(
        {
            "prefix": "demo",
            "width": 24,
            "height": 24,
            "icons": {
                "house": {"body": "<path d='h'/>"},
                "house-solid": {"body": "<path d='hs'/>", "width": 20, "height": 20},
                "x": {"body": "<path d='x'/>"},
                "unused": {"body": "<path d='u'/>"},
            },
            "aliases": {"home": {"parent": "house"}},
            "info": {"name": "Demo"},
        }
    )
)


def write_package(
    source: Path, package: str, icons: dict[str, dict[str, object]]
) -> None:
    package_dir = source / package
    package_dir.mkdir(parents=True)
    (package_dir / "icons.json").write_text(
        json.dumps({"prefix": package, "width": 24, "height": 24, "icons": icons})
    )
    (package_dir / "package.json").write_text(
        json.dumps({"name": f"@iconify-json/{package}", "version": "9.9.9"})
    )
    (package_dir / "info.json").write_text(
        json.dumps({"license": {"spdx": "MIT", "url": "https://example.test/LICENSE"}})
    )


@pytest.fixture
def demo_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the real icon sets with one tiny set that has a '-solid' variant."""
    demo = IconSetConfig(
        mapping={"home": "house", "close": "x"},
        variants={"outline": None, "solid": "-solid"},
    )
    monkeypatch.setitem(ICON_SETS, "demo", demo)
    monkeypatch.setattr(generate_icon_subset, "ICON_SETS", {"demo": demo})
    monkeypatch.setattr(generate_icon_subset, "PACKAGE_MAP", {"demo": "demo"})


@pytest.fixture
def complete_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    write_package(
        source,
        "demo",
        {
            "house": {"body": "h"},
            "house-solid": {"body": "hs"},
            "x": {"body": "x"},
            "x-solid": {"body": "xs"},
        },
    )
    return source


@pytest.mark.dev_tooling
class TestBuildSubset:
    def test_keeps_prefix_and_root_size(self) -> None:
        result = build_subset(UPSTREAM, {"house"})

        assert result["prefix"] == "demo"
        assert result["width"] == 24
        assert result["height"] == 24

    def test_keeps_only_the_named_glyphs(self) -> None:
        result = build_subset(UPSTREAM, {"house", "x", "not-upstream"})

        assert sorted(result["icons"]) == ["house", "x"]

    def test_drops_aliases_and_info(self) -> None:
        result = build_subset(UPSTREAM, {"house"})

        assert sorted(result) == ["height", "icons", "prefix", "width"]

    def test_copies_an_entrys_own_size_verbatim(self) -> None:
        result = build_subset(UPSTREAM, {"house-solid"})

        assert result["icons"]["house-solid"] == {
            "body": "<path d='hs'/>",
            "width": 20,
            "height": 20,
        }

    def test_leaves_out_root_size_when_upstream_has_none(self) -> None:
        upstream: IconifyData = {"prefix": "p", "icons": {"a": {"body": "a"}}}

        result = build_subset(upstream, {"a"})

        assert result == {"prefix": "p", "icons": {"a": {"body": "a"}}}


@pytest.mark.dev_tooling
@pytest.mark.usefixtures("demo_set")
class TestMain:
    def test_writes_manifest(self, complete_source: Path, tmp_path: Path) -> None:
        output = tmp_path / "out"

        exit_code = main(["--source", str(complete_source), "--output", str(output)])

        manifest = json.loads((output / "manifest.json").read_text())
        assert exit_code == 0
        assert manifest == {
            "demo": {
                "package": "@iconify-json/demo",
                "version": "9.9.9",
                "license": "MIT",
                "license_url": "https://example.test/LICENSE",
                "glyphs": ["house", "house-solid", "x", "x-solid"],
                "missing_glyphs": [],
            }
        }

    def test_writes_subset_icons_file(
        self, complete_source: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out"

        main(["--source", str(complete_source), "--output", str(output)])

        written = json.loads((output / "demo" / "icons.json").read_text())
        assert sorted(written["icons"]) == ["house", "house-solid", "x", "x-solid"]

    def test_missing_base_glyph_fails_naming_semantic_name_set_and_glyph(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = tmp_path / "source"
        write_package(source, "demo", {"house": {"body": "h"}})

        exit_code = main(["--source", str(source), "--output", str(tmp_path / "out")])

        assert exit_code == 1
        assert "demo: close -> x" in capsys.readouterr().out

    def test_missing_base_glyph_writes_nothing(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        write_package(source, "demo", {"house": {"body": "h"}})

        main(["--source", str(source), "--output", str(tmp_path / "out")])

        assert not (tmp_path / "out" / "manifest.json").exists()

    def test_missing_variant_glyph_is_recorded_and_succeeds(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "source"
        write_package(
            source,
            "demo",
            {"house": {"body": "h"}, "house-solid": {"body": "hs"}, "x": {"body": "x"}},
        )
        output = tmp_path / "out"

        exit_code = main(["--source", str(source), "--output", str(output)])

        manifest = json.loads((output / "manifest.json").read_text())
        assert exit_code == 0
        assert manifest["demo"]["missing_glyphs"] == ["x-solid"]

    def test_missing_source_fails_telling_the_maintainer_to_install(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = main(
            ["--source", str(tmp_path / "absent"), "--output", str(tmp_path / "out")]
        )

        assert exit_code == 1
        assert "Run npm install first." in capsys.readouterr().out

    def test_check_writes_nothing_and_fails_after_a_byte_changes(
        self, complete_source: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out"
        main(["--source", str(complete_source), "--output", str(output)])
        committed = output / "demo" / "icons.json"
        committed.write_text(committed.read_text().replace('"hs"', '"hX"'))
        changed = committed.read_text()

        exit_code = main(
            ["--source", str(complete_source), "--output", str(output), "--check"]
        )

        assert exit_code == 1
        assert committed.read_text() == changed

    def test_check_succeeds_when_files_match(
        self, complete_source: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out"
        main(["--source", str(complete_source), "--output", str(output)])

        exit_code = main(
            ["--source", str(complete_source), "--output", str(output), "--check"]
        )

        assert exit_code == 0

    def test_second_run_gives_byte_identical_icons_file(
        self, complete_source: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out"
        main(["--source", str(complete_source), "--output", str(output)])
        first = (output / "demo" / "icons.json").read_bytes()

        main(["--source", str(complete_source), "--output", str(output)])

        assert (output / "demo" / "icons.json").read_bytes() == first

    def test_second_run_gives_byte_identical_manifest(
        self, complete_source: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out"
        main(["--source", str(complete_source), "--output", str(output)])
        first = (output / "manifest.json").read_bytes()

        main(["--source", str(complete_source), "--output", str(output)])

        assert (output / "manifest.json").read_bytes() == first

    def test_never_writes_a_license_file(
        self, complete_source: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "out"

        main(["--source", str(complete_source), "--output", str(output)])

        assert not (output / "demo" / "LICENSE").exists()


def upstream_dir(set_name: str) -> Path:
    return REPO_ROOT / DEFAULT_SOURCE / PACKAGE_MAP[set_name]


@pytest.mark.parametrize("set_name", list(ICON_SETS))
class TestCommittedDataMatchesUpstream:
    def test_committed_icons_equal_the_subset_of_installed_upstream(
        self, set_name: str
    ) -> None:
        upstream_file = upstream_dir(set_name) / "icons.json"
        assert upstream_file.exists(), (
            f"{upstream_file} is missing. Run npm install, then {REGENERATE_COMMAND}"
        )
        upstream: IconifyData = json.loads(upstream_file.read_text())
        committed = json.loads(
            (BUNDLED_DATA_DIR / PACKAGE_MAP[set_name] / "icons.json").read_text()
        )

        expected = build_subset(upstream, required_glyphs(set_name))

        assert committed == expected, f"Bundled data is stale. Run {REGENERATE_COMMAND}"

    def test_installed_version_equals_the_manifest_version(self, set_name: str) -> None:
        package_json = upstream_dir(set_name) / "package.json"
        assert package_json.exists(), (
            f"{package_json} is missing. Run npm install, then {REGENERATE_COMMAND}"
        )
        installed = json.loads(package_json.read_text())["version"]
        manifest = json.loads((BUNDLED_DATA_DIR / "manifest.json").read_text())

        assert installed == manifest[set_name]["version"], (
            f"Installed version differs from the bundled data. Run {REGENERATE_COMMAND}"
        )
