from __future__ import annotations

from pathlib import Path


def test_show_answer_key_is_set_only_by_the_educator_preview() -> None:
    root = Path(__file__).resolve().parents[3]
    allowed_templates = {
        "form_engine/templates/form_engine/inputs/multiple_choice.html",
        "form_engine/templates/form_engine/inputs/checkboxes.html",
        "form_engine/templates/form_engine/inputs/dropdown.html",
    }
    guard = Path(__file__).resolve()
    mentions = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.suffix in {".py", ".html"}
        and path.resolve() != guard
        and "show_answer_key" in path.read_text()
    }

    assert mentions == allowed_templates | {"educator_interface/views.py"}
