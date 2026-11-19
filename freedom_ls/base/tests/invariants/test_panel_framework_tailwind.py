"""FLS's compiled stylesheet carries the panel framework's rules.

The framework stylesheet reaches the build through the generated
`tailwind.panel_framework.css`, so a selector missing from
`static/vendor/tailwind.output.css` means the import or the generated file broke.
"""

from __future__ import annotations

import subprocess
from io import StringIO
from pathlib import Path

import pytest

from django.conf import settings
from django.core.management import call_command

from freedom_ls.base.tests.tailwind_build import run_tailwind
from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

pytestmark = pytest.mark.fls_internal

COMPILED_CSS: Path = FREEDOM_LS_PACKAGE_DIR.parent / "static/vendor/tailwind.output.css"
REFERENCE_THEME: Path = (
    FREEDOM_LS_PACKAGE_DIR / "panel_framework/css/reference_theme.css"
)
# Used by a framework template and by no FLS template, so it is emitted only if
# the build reads the framework's templates.
GENERATED_FILE_NAME = "tailwind.panel_framework.css"
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
    """The output of a build from the reference theme and the generated file alone."""
    call_command("write_panel_framework_css", stdout=StringIO())
    build_dir = tmp_path_factory.mktemp("reference_only_build")
    input_css = build_dir / "input.css"
    generated = Path(settings.BASE_DIR) / GENERATED_FILE_NAME
    input_css.write_text(
        '@import "tailwindcss" source(none);\n'
        f'@import "{REFERENCE_THEME.as_posix()}";\n'
        f'@import "{generated.as_posix()}";\n'
    )
    return run_tailwind(build_dir, input_css)


@pytest.mark.parametrize("rule", [".panel-surface", FRAMEWORK_ONLY_CLASS])
def test_a_build_from_the_reference_theme_alone_produces_the_framework_rule(
    reference_only_build: str, rule: str
) -> None:
    assert rule in reference_only_build


def test_the_compiled_stylesheet_contains_a_class_only_a_framework_template_uses() -> (
    None
):
    assert FRAMEWORK_ONLY_CLASS in COMPILED_CSS.read_text()


@pytest.mark.parametrize(
    "path",
    [
        GENERATED_FILE_NAME,
        "freedom_ls/panel_framework/static/panel_framework/css/reference.css",
    ],
)
def test_a_generated_stylesheet_is_gitignored(path: str) -> None:
    result = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "-q", path],  # noqa: S607
        cwd=settings.BASE_DIR,
        check=False,
    )

    assert result.returncode == 0
