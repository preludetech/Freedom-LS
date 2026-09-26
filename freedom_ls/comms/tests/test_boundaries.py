"""comms never imports webhooks: this is what keeps the delivery seam generic
rather than webhooks-shaped."""

from __future__ import annotations

from pathlib import Path

import freedom_ls.comms


def test_no_file_under_comms_imports_webhooks() -> None:
    this_file = Path(__file__).resolve()
    comms_dir = Path(freedom_ls.comms.__file__).parent
    offenders = [
        path
        for path in comms_dir.rglob("*.py")
        if "migrations" not in path.parts
        and path.resolve() != this_file
        and "freedom_ls.webhooks" in path.read_text(encoding="utf-8")
    ]

    assert not offenders, (
        f"These files import freedom_ls.webhooks: {[str(path) for path in offenders]}"
    )
