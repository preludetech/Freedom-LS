"""Template rules that hold for any tree of panel templates.

Each function walks the files it is given and returns the offending lines. The
framework's own invariants call them on the framework's templates, and a host
project calls them on its own, so no function names a host path or a host
spelling: a tag, class or directory that differs between the two is an argument.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from pathlib import Path

import lxml.html

CONTROL_TAG = re.compile(r"<(a|button)\b([^>]*)>", re.DOTALL)
CLASS_ATTR = re.compile(r'class="([^"]*)"', re.DOTALL)
MODAL_BODY_BLOCK = re.compile(r"<c-modal-body\b.*?</c-modal-body>", re.DOTALL)
HAND_PADDED_BODY = re.compile(r'<div class="[^"]*\bpx-6\b[^"]*"')
EXTENDS_FRAMEWORK_DIALOG = re.compile(
    r'\{% extends "(panel_framework/modal/[a-z_]+\.html)" %\}'
)
STEP_BRANCH = re.compile(r"\bstep == ")
DROPDOWN_CHEVRON = re.compile(r'<c-(?:panel-)?icon name="dropdown"[^>]*>')
LOADING_TEXT = re.compile(r'loading_text="[^"]*"')
DISABLED_ELT = re.compile(r'hx-disabled-elt="[^"]*"')
OWN_SUBMIT_ONLY = "hx-disabled-elt=\"find button[type='submit']\""
TRIGGER_TEMPLATE_BY_HAND = re.compile(
    r'trigger_template_name\s*=\s*"panel_framework/partials/modal_trigger.html"'
)


def _html_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.html"))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def files_using_safe(root: Path) -> list[str]:
    """Each template under `root` that uses the `|safe` filter."""
    return [
        _relative(path, root)
        for path in _html_files(root)
        if "|safe" in path.read_text()
    ]


def hand_styled_control_links(root: Path, prose_exempt: Collection[str]) -> list[str]:
    """Each `<a>` or `<button>` under `root` styled by hand: the prose underline,
    a hand-typed `text-primary`, or an anchor that names no link style."""
    offenders: list[str] = []
    for path in _html_files(root):
        relative = _relative(path, root)
        if relative in prose_exempt:
            continue
        for match in CONTROL_TAG.finditer(path.read_text()):
            tag = match.group(0)
            classes = CLASS_ATTR.search(tag)
            tokens = set(classes.group(1).split()) if classes else set()
            if "underline" in tokens or "text-primary" in tokens:
                offenders.append(f"{relative}: {tag[:80]}")
            elif tag.startswith("<a") and "{{ attrs }}" not in tag:
                styled = "no-underline" in tokens or any(
                    token.startswith(("btn", "panel-btn")) for token in tokens
                )
                if not styled:
                    offenders.append(f"{relative}: {tag[:80]}")
    return offenders


def hand_written_tables(root: Path, table_components: Collection[str]) -> list[str]:
    """Each template under `root`, other than the table components themselves
    (named by file), that writes a `<table>` outside a comment."""
    offenders: list[str] = []
    for path in _html_files(root):
        if path.name in table_components:
            continue
        source = re.sub(
            r"{% comment %}.*?{% endcomment %}", "", path.read_text(), flags=re.S
        )
        if re.search(r"<table\b", source):
            offenders.append(_relative(path, root))
    return offenders


def anchors_without_classes(root: Path, prose_exempt: Collection[str]) -> list[str]:
    """Each `<a>` with visible text that carries no `class` and no `{{ attrs }}`,
    so it falls back to the prose style."""
    offenders: list[str] = []
    for path in _html_files(root):
        relative = _relative(path, root)
        if relative in prose_exempt:
            continue
        for match in re.finditer(r"<a\b([^>]*)>(.*?)</a>", path.read_text(), re.DOTALL):
            attributes, content = match.group(1), match.group(2)
            if "class=" in attributes or "{{ attrs }}" in attributes:
                continue
            if re.search(r"<c-(?:panel-)?icon\b", content) and not re.sub(
                r"<[^>]+>|\s", "", content
            ):
                continue
            offenders.append(f"{relative}: {match.group(0)[:80]}")
    return offenders


def hand_written_touch_heights(
    root: Path, button_tag: str, button_class: str, dropdown_tag: str
) -> list[str]:
    """Each button under `root` that carries `min-h-11` itself.

    `button_tag` and `dropdown_tag` are cotton tag names without the `c-`
    prefix, and `button_class` is the button's CSS class. A dropdown menu's own
    items keep `min-h-11`, so only a dropdown trigger variant is checked.
    """
    tag = re.escape(button_tag)
    css_class = re.escape(button_class)
    offenders: list[str] = []
    for path in _html_files(root):
        source = path.read_text()
        for found in re.findall(rf"<c-{tag}\b[^>]*>", source):
            if "min-h-11" in found and "dropdown=" not in found:
                offenders.append(f"{path.name}: {found[:80]}")
        for classes in re.findall(rf'class="({css_class} [^"]*)"', source):
            if "min-h-11" in classes:
                offenders.append(f"{path.name}: {classes}")
        for trigger in re.findall(rf'trigger_class="{css_class}[^"]*"', source):
            if "min-h-11" in trigger:
                offenders.append(f"{path.name}: {trigger}")
        for menu in re.findall(rf"<c-{re.escape(dropdown_tag)}\b[^>]*>", source):
            if "trigger_variant=" in menu and "min-h-11" in menu:
                offenders.append(f"{path.name}: {menu[:80]}")
    return offenders


def expand_chevrons_that_do_not_turn(root: Path) -> list[str]:
    """Each dropdown chevron under `root` with no `rotate-180` variant on itself
    or on the tag that wraps it."""
    offenders: list[str] = []
    for path in _html_files(root):
        text = path.read_text()
        for match in DROPDOWN_CHEVRON.finditer(text):
            wrapper = text[max(0, match.start() - 200) : match.start()]
            last_tag = wrapper[wrapper.rfind("<") :]
            if "rotate-180" not in match.group(0) and "rotate-180" not in last_tag:
                offenders.append(f"{_relative(path, root)}: {match.group(0)}")
    return offenders


def dialog_parts_source(path: Path, framework_templates: Path) -> str:
    """The template's text, with the parts of the framework dialog it extends
    (message.html, confirm.html) counted for it."""
    text = path.read_text()
    parent = EXTENDS_FRAMEWORK_DIALOG.search(text)
    if parent:
        text += dialog_parts_source(
            framework_templates / parent.group(1), framework_templates
        )
    return text


def dialogs_using_a_button_group(paths: Iterable[Path], group_tag: str) -> list[str]:
    """Each dialog that holds a button group, where its buttons belong in the
    modal footer. `group_tag` is the cotton tag name without the `c-` prefix."""
    pattern = re.compile(rf"<c-{re.escape(group_tag)}")
    return [path.name for path in paths if pattern.search(path.read_text())]


def dialogs_missing_a_part(
    paths: Iterable[Path], framework_templates: Path, exempt: Collection[str]
) -> list[str]:
    """Each dialog template missing its modal header, body or footer."""
    offenders: list[str] = []
    for path in paths:
        if path.name in exempt:
            continue
        text = dialog_parts_source(path, framework_templates)
        if "<c-modal-header" not in text and "{% include" in text:
            continue
        offenders.extend(
            f"{path.name}: no {part}>"
            for part in ("<c-modal-header", "<c-modal-body", "<c-modal-footer")
            if part not in text
        )
    return offenders


def dialogs_with_a_footer_inside_the_body(
    paths: Iterable[Path], framework_templates: Path
) -> list[str]:
    """Each dialog that puts `<c-modal-footer>` inside `<c-modal-body>`."""
    return [
        path.name
        for path in paths
        if any(
            "<c-modal-footer" in block
            for block in MODAL_BODY_BLOCK.findall(
                dialog_parts_source(path, framework_templates)
            )
        )
    ]


def dialogs_padding_their_own_body(
    paths: Iterable[Path], exempt: Collection[str]
) -> list[str]:
    """Each dialog that hand-pads a div where `<c-modal-body>` owns the padding."""
    return [
        path.name
        for path in paths
        if path.name not in exempt and HAND_PADDED_BODY.search(path.read_text())
    ]


def dialog_footer_problems(path: Path) -> list[str]:
    """A dialog holds one footer per step it renders, or none when it extends a
    template that supplies it, and the footer is never inside the body."""
    text = path.read_text()
    steps = max(1, len(STEP_BRANCH.findall(text)))
    footers = [m.start() for m in re.finditer(r"<c-modal-footer\b", text)]
    spans = list(MODAL_BODY_BLOCK.finditer(text))
    problems = [
        f"{path.name}: footer inside the body"
        for start in footers
        for span in spans
        if span.start() < start < span.end()
    ]
    if len(footers) > steps:
        problems.append(f"{path.name}: {len(footers)} footers for {steps} steps")
    if "{% extends" in text and footers:
        problems.append(f"{path.name}: a footer in a template that extends")
    return problems


def forbidden_in_dialogs(button_tag: str) -> dict[str, re.Pattern[str]]:
    """What a dialog must not write by hand because a component owns it, by
    description. The tag is a cotton tag name without the `c-` prefix."""
    return {
        "a hand-written Cancel button": re.compile(
            rf">\s*Cancel\s*</(?:c-{re.escape(button_tag)}|button)>"
        ),
        "text-sm": re.compile(r"(?<![\w-])text-sm\b"),
        "px-6 py-4": re.compile(r"px-6 py-4"),
        "a bg-error/10 box": re.compile(r"bg-error/10"),
    }


def dialogs_matching(paths: Iterable[Path], pattern: re.Pattern[str]) -> list[str]:
    """Each dialog whose source matches `pattern`."""
    return [path.name for path in paths if pattern.search(path.read_text())]


def loading_texts_ending_in_three_dots(paths: Iterable[Path]) -> list[str]:
    """Each `loading_text` written with three dots, not the ellipsis character."""
    return [
        f"{path.name}: {match}"
        for path in paths
        for match in LOADING_TEXT.findall(path.read_text())
        if "..." in match
    ]


def dialogs_disabling_more_than_their_submit_buttons(
    paths: Iterable[Path], exempt: Collection[str]
) -> list[str]:
    """Each `hx-disabled-elt` other than the one that finds the form's own
    submit buttons."""
    return [
        f"{path.name}: {match}"
        for path in paths
        if path.name not in exempt
        for match in DISABLED_ELT.findall(path.read_text())
        if match != OWN_SUBMIT_ONLY
    ]


def requesting_elements_inside_a_find_form(paths: Iterable[Path]) -> list[str]:
    """Each element inside a form that disables with a `find` selector and issues
    its own request, which inherits the selector and resolves it inside itself."""
    offenders: list[str] = []
    for path in paths:
        for form in lxml.html.fragment_fromstring(
            path.read_text(), create_parent="div"
        ).iter("form"):
            if not (form.get("hx-disabled-elt") or "").startswith("find "):
                continue
            offenders.extend(
                f"{path.name}: <{child.tag} id={child.get('id')}>"
                for child in form.iterdescendants()
                if child.get("hx-get") or child.get("hx-post")
            )
    return offenders


def dialogs_declaring_the_wide_size(
    paths: Iterable[Path], modal_host: Path
) -> set[str]:
    """The names of the dialogs, other than the host itself, that declare
    `data-modal-size="wide"`."""
    return {
        path.name
        for path in paths
        if 'data-modal-size="wide"' in path.read_text() and path != modal_host
    }


def python_files_setting_the_modal_trigger_by_hand(paths: Iterable[Path]) -> list[str]:
    """Each Python file that names the modal trigger template itself, where the
    framework's modal action classes own it."""
    return [
        path.name for path in paths if TRIGGER_TEMPLATE_BY_HAND.search(path.read_text())
    ]
