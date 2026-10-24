"""Course files written into a test directory, for tests that load content."""

from __future__ import annotations

import uuid
from pathlib import Path

COURSE_UUID = "70000000-0000-0000-0000-000000000001"


def _uuid_for(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def write_course(root: Path) -> None:
    """Write the course file that the parts below sit in."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "course.md").write_text(
        f"---\ncontent_type: COURSE\ntitle: Moving Course\nuuid: {COURSE_UUID}\n---\n"
    )


def write_part(root: Path, part: str, children: list[str] | None = None) -> Path:
    """Write a part directory; `children` are author paths relative to it, in order."""
    part_dir = root / part
    part_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "content_type: COURSE_PART",
        f"title: {part}",
        f"uuid: {_uuid_for(part)}",
    ]
    if children is not None:
        lines.append("children:")
        lines.extend(f"  - path: {child}" for child in children)
    (part_dir / "part.yaml").write_text("\n".join(lines) + "\n")
    return part_dir


def write_topic(part_dir: Path, name: str) -> Path:
    """Write a topic file with a stable uuid, so moving the file keeps its identity."""
    topic_file = part_dir / f"{name}.md"
    topic_file.write_text(
        f"---\ncontent_type: TOPIC\ntitle: {name}\nuuid: {_uuid_for(name)}\n---\n\nBody.\n"
    )
    return topic_file
