"""Every template that uses an `fls_base_filters` filter loads the library itself.

A filter used inside a cotton component's attribute is compiled with the
template's own `{% load %}` libraries. django-cotton 2.6 hid a missing load;
from 2.7 the attribute renders as raw template text instead.
"""

import re
from pathlib import Path

from django.template import engines
from django.template.library import import_library

FREEDOM_LS_DIR = Path(__file__).resolve().parents[3]
LIBRARY_NAME = "fls_base_filters"
LOAD_PATTERN = re.compile(r"\{%\s*load\s+[^%]*\b" + LIBRARY_NAME + r"\b[^%]*%\}")


def _filters_only_this_library_registers() -> set[str]:
    engine = engines["django"].engine
    own = set(import_library(engine.libraries[LIBRARY_NAME]).filters)
    elsewhere: set[str] = set()
    for name, path in engine.libraries.items():
        if name != LIBRARY_NAME:
            elsewhere |= set(import_library(path).filters)
    for builtin in engine.template_builtins:
        elsewhere |= set(builtin.filters)
    return own - elsewhere


def test_templates_using_fls_base_filters_load_the_library() -> None:
    names = _filters_only_this_library_registers()
    assert "display_datetime" in names
    use_pattern = re.compile(r"\|\s*(" + "|".join(sorted(names)) + r")\b")
    violations = [
        str(path.relative_to(FREEDOM_LS_DIR))
        for path in FREEDOM_LS_DIR.glob("**/*.html")
        if use_pattern.search(text := path.read_text())
        and not LOAD_PATTERN.search(text)
    ]
    assert not violations, (
        f"Templates use an {LIBRARY_NAME} filter without "
        f"{{% load {LIBRARY_NAME} %}}:\n" + "\n".join(violations)
    )
