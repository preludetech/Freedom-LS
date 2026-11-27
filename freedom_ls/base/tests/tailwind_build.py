"""Run the Tailwind CLI on a scratch input file.

Used by tests that need a compiled stylesheet other than the one the project
builds: the framework alone, or FLS's input with a different active theme.
Everything is written under the directory the caller passes, never into the
working tree.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from django.conf import settings

_RELATIVE_PATH = re.compile(r'"\./([^"]+)"')
_ACTIVE_THEME_FILE = "tailwind.active_theme.css"


def run_tailwind(build_dir: Path, input_css: Path) -> str:
    """Compile `input_css` and return the CSS.

    Tailwind resolves `@import "tailwindcss"` from the input file's directory,
    so `build_dir` gets a `node_modules` link to the project's.
    """
    node_modules = build_dir / "node_modules"
    if not node_modules.exists():
        node_modules.symlink_to(Path(settings.BASE_DIR) / "node_modules")
    output_css = build_dir / "output.css"
    subprocess.run(  # noqa: S603
        ["npx", "@tailwindcss/cli", "-i", str(input_css), "-o", str(output_css)],  # noqa: S607
        check=True,
        cwd=settings.BASE_DIR,
    )
    return output_css.read_text()


def build_fls_css_with_theme(
    build_dir: Path,
    theme_slug: str,
    keep_relative: frozenset[str] = frozenset(),
) -> str:
    """FLS's `tailwind.input.css` compiled with `theme_slug` as the active theme.

    The input is copied into `build_dir` with every relative path made absolute,
    and the active-theme file is written there for `theme_slug`, so the cascade
    is the one a real build with that theme produces. A relative path named in
    `keep_relative` stays relative, so it resolves beside the copied input in
    `build_dir`.
    """
    base_dir = Path(settings.BASE_DIR)
    theme_css = (
        base_dir
        / f"freedom_ls/themes/{theme_slug}/static/themes/{theme_slug}/theme.css"
    )
    active_theme = build_dir / _ACTIVE_THEME_FILE
    active_theme.write_text(f'@import "{theme_css.as_posix()}";\n')

    def absolute(match: re.Match[str]) -> str:
        relative = match.group(1)
        if relative in keep_relative:
            return match.group(0)
        if relative == _ACTIVE_THEME_FILE:
            return f'"{active_theme.as_posix()}"'
        return f'"{(base_dir / relative).as_posix()}"'

    source = (base_dir / "tailwind.input.css").read_text()
    input_css = build_dir / "tailwind.input.css"
    input_css.write_text(_RELATIVE_PATH.sub(absolute, source))
    return run_tailwind(build_dir, input_css)
