"""No Alpine component is registered by two of the apps' component scripts.

The scripts load into one page, so a second registration of a name silently
replaces the first."""

from __future__ import annotations

import re
from collections import defaultdict

from freedom_ls.base.theming import FREEDOM_LS_PACKAGE_DIR

REGISTRATION = re.compile(r"""Alpine\.data\(\s*["']([\w$]+)["']""")


def test_no_component_name_is_registered_in_two_component_files() -> None:
    files_by_name: dict[str, list[str]] = defaultdict(list)
    for script in sorted(FREEDOM_LS_PACKAGE_DIR.glob("*/static/**/*.js")):
        for name in set(REGISTRATION.findall(script.read_text())):
            files_by_name[name].append(str(script.relative_to(FREEDOM_LS_PACKAGE_DIR)))

    duplicates = {
        name: files for name, files in files_by_name.items() if len(files) > 1
    }

    assert not duplicates, f"registered more than once: {duplicates}"
