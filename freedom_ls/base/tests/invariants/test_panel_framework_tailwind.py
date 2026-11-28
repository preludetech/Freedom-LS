"""FLS's compiled stylesheet carries the panel framework's rules.

The framework stylesheet reaches the build through the generated
`tailwind.panel_framework.css`, so a selector missing from
`static/vendor/tailwind.output.css` means the import or the generated file broke.
"""

from __future__ import annotations

import shutil
import subprocess
from io import StringIO
from pathlib import Path

import panel_framework
import pytest

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings

from freedom_ls.base.tests.tailwind_build import (
    build_fls_css_with_theme,
    run_tailwind,
)
from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

COMPILED_CSS: Path = FREEDOM_LS_PACKAGE_DIR.parent / "static/vendor/tailwind.output.css"
REFERENCE_THEME: Path = Path(panel_framework.__file__).parent / "css/default_theme.css"
# Used by a framework template and by no FLS template, so it is emitted only if
# the build reads the framework's templates.
GENERATED_FILE_NAME = "tailwind.panel_framework.css"
DEFAULT_THEME_SLUG = "default"
FRAMEWORK_ONLY_CLASS = r".shadow-\[inset_0_-1px_0_var\(--color-border\)\]"


@pytest.mark.parametrize(
    "selector",
    [
        ".panel-surface",
        ".panel-canvas",
        ".panel-heading",
        ".panel-table-selection-bar",
        ".panel-data-table-compact",
        ".modal-backdrop-host::backdrop",
        ".bottom-sheet",
        ".bottom-sheet-bare",
        "@keyframes selection-bar-in",
    ],
)
def test_the_compiled_stylesheet_contains_the_framework_rule(selector: str) -> None:
    assert COMPILED_CSS.is_file(), (
        f"{COMPILED_CSS} is missing: run `npm run tailwind_build` first."
    )
    assert selector in COMPILED_CSS.read_text()


@pytest.fixture(scope="module")
def reference_only_build(tmp_path_factory: pytest.TempPathFactory) -> str:
    """The output of a build from the reference theme and the generated file alone.

    The generated file is written into the build directory, never the working
    tree, which other test workers' builds read."""
    build_dir = tmp_path_factory.mktemp("reference_only_build")
    with override_settings(BASE_DIR=build_dir):
        call_command("write_panel_framework_css", stdout=StringIO())
    input_css = build_dir / "input.css"
    generated = build_dir / GENERATED_FILE_NAME
    input_css.write_text(
        '@import "tailwindcss" source(none);\n'
        f'@import "{REFERENCE_THEME.as_posix()}";\n'
        f'@import "{generated.as_posix()}";\n'
    )
    return run_tailwind(build_dir, input_css)


@pytest.mark.parametrize("rule", [".panel-surface", FRAMEWORK_ONLY_CLASS])
def test_a_build_from_the_default_theme_alone_produces_the_framework_rule(
    reference_only_build: str, rule: str
) -> None:
    assert rule in reference_only_build


def test_the_compiled_stylesheet_contains_a_class_only_a_framework_template_uses() -> (
    None
):
    assert FRAMEWORK_ONLY_CLASS in COMPILED_CSS.read_text()


def test_a_generated_stylesheet_is_gitignored() -> None:
    result = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "-q", GENERATED_FILE_NAME],  # noqa: S607
        cwd=settings.BASE_DIR,
        check=False,
    )

    assert result.returncode == 0


@pytest.fixture(scope="module")
def temporary_copy_build(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """FLS's stylesheet built with the framework read from a directory outside the project.

    A framework linked from a package worktree lives at an absolute path
    the project does not contain, and the generated file then names that
    path instead of a relative one. Returns the copy's directory and the build."""
    copy_dir = tmp_path_factory.mktemp("framework_copy") / "panel_framework"
    shutil.copytree(Path(panel_framework.__file__).parent, copy_dir)
    build_dir = tmp_path_factory.mktemp("temporary_copy_build")
    app_config = apps.get_app_config("panel_framework")
    with pytest.MonkeyPatch.context() as patch, override_settings(BASE_DIR=build_dir):
        patch.setattr(app_config, "path", str(copy_dir))
        call_command("write_panel_framework_css", stdout=StringIO())
    css = build_fls_css_with_theme(
        build_dir, DEFAULT_THEME_SLUG, keep_relative=frozenset({GENERATED_FILE_NAME})
    )
    return build_dir, css


def test_the_generated_file_for_a_copy_outside_the_project_names_the_copy_absolutely(
    temporary_copy_build: tuple[Path, str],
) -> None:
    build_dir, _ = temporary_copy_build
    generated = (build_dir / GENERATED_FILE_NAME).read_text()

    assert '@import "/' in generated
    assert "/framework_copy" in generated


@pytest.mark.parametrize("rule", [".panel-surface", FRAMEWORK_ONLY_CLASS])
def test_a_build_with_a_framework_copy_outside_the_project_produces_the_framework_rule(
    temporary_copy_build: tuple[Path, str], rule: str
) -> None:
    _, css = temporary_copy_build

    assert rule in css
