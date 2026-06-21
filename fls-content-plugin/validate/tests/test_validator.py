"""
Tests for the bundled standalone validator (fls-content-plugin/validate/validate.py).

The validator is invoked as a subprocess via uv to prove it runs without Django.
All sample content trees are built under pytest's tmp_path — no committed fixture files.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# Absolute path to the bundled validator script.
VALIDATE_SCRIPT = Path(__file__).parent.parent / "validate.py"

# uv invocation: isolated ephemeral env (--no-project) with only the listed deps.
# --no-project is required to prove Django-freedom: without it, uv discovers the
# FLS pyproject.toml and layers deps on top of the full project environment, making
# Django importable even in a "clean" subprocess.
UV_CMD = [
    "uv",
    "run",
    "--no-project",
    "--with",
    "pydantic",
    "--with",
    "pyyaml",
    "--with",
    "python-frontmatter",
    "python",
    str(VALIDATE_SCRIPT),
]


def run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    """Run the bundled validator against *path* in a clean environment."""
    env = {
        # Minimal env: PATH so uv can find python, no DJANGO_SETTINGS_MODULE.
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", tempfile.gettempdir()),
    }
    return subprocess.run(
        [*UV_CMD, str(path)],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Helpers that build minimal valid content files
# ---------------------------------------------------------------------------


def write_valid_topic(directory: Path, name: str = "01. intro.md") -> Path:
    """Write a minimal valid TOPIC markdown file."""
    path = directory / name
    path.write_text(
        "---\ncontent_type: TOPIC\ntitle: Introduction\n---\n\nSome body content.\n",
        encoding="utf-8",
    )
    return path


def write_valid_course(directory: Path) -> Path:
    """Write a minimal valid COURSE role file (course.md)."""
    path = directory / "course.md"
    path.write_text(
        "---\ncontent_type: COURSE\ntitle: My Course\n---\n",
        encoding="utf-8",
    )
    return path


def write_valid_form(directory: Path) -> Path:
    """Write a minimal valid FORM role file (form.md)."""
    path = directory / "form.md"
    path.write_text(
        "---\n"
        "content_type: FORM\n"
        "title: My Quiz\n"
        "strategy: QUIZ\n"
        "quiz_show_incorrect: true\n"
        "quiz_pass_percentage: 70\n"
        "---\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Test: valid sample tree exits 0
# ---------------------------------------------------------------------------


def test_valid_sample_tree_exits_zero(tmp_path: Path) -> None:
    """A tiny valid TOPIC + COURSE + FORM tree under tmp_path must exit 0."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()

    topic_dir = course_dir / "01. topics"
    topic_dir.mkdir()

    form_dir = course_dir / "02. quiz"
    form_dir.mkdir()

    write_valid_course(course_dir)
    write_valid_topic(topic_dir)
    write_valid_form(form_dir)

    result = run_validator(course_dir)
    assert result.returncode == 0, (
        f"Expected exit 0 for valid tree.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test: COURSE file validates without raising (icon stub works headless)
# ---------------------------------------------------------------------------


def test_course_validates_without_django(tmp_path: Path) -> None:
    """A COURSE file must validate without Django installed (icon stub works)."""
    write_valid_course(tmp_path)
    result = run_validator(tmp_path / "course.md")
    assert result.returncode == 0, (
        f"COURSE validation raised unexpectedly (icon stub may be broken).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Tests: broken samples exit non-zero
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("description", "content"),
    [
        (
            "missing_required_field_title",
            # TOPIC without the required 'title' field
            "---\ncontent_type: TOPIC\n---\n\nBody content.\n",
        ),
        (
            "unknown_field_extra_forbid",
            # TOPIC with an unknown field — extra="forbid" should reject it
            "---\n"
            "content_type: TOPIC\n"
            "title: Test\n"
            "totally_unknown_field: oops\n"
            "---\n"
            "\nBody.\n",
        ),
        (
            "wrong_type_for_field",
            # TOPIC with tags as a string instead of a list[str]
            "---\ncontent_type: TOPIC\ntitle: Test\ntags: not-a-list\n---\n\nBody.\n",
        ),
    ],
)
def test_broken_sample_exits_nonzero(
    tmp_path: Path, description: str, content: str
) -> None:
    """Deliberately broken content files must cause the validator to exit non-zero."""
    bad_file = tmp_path / f"broken_{description}.md"
    bad_file.write_text(content, encoding="utf-8")

    result = run_validator(bad_file)
    assert result.returncode != 0, (
        f"Expected non-zero exit for broken sample '{description}'.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_broken_sample_output_is_human_readable(tmp_path: Path) -> None:
    """The error output for a broken file must be human-readable, not a raw traceback."""
    bad_file = tmp_path / "missing_title.md"
    bad_file.write_text(
        "---\ncontent_type: TOPIC\n---\n\nBody.\n",
        encoding="utf-8",
    )
    result = run_validator(bad_file)
    assert result.returncode != 0

    # The output should describe the problem, not dump a Python traceback.
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw Python traceback:\n{combined}"
    )
    # Should contain something human-readable about the failure.
    assert len(combined.strip()) > 0, "Validator produced no output for a broken file"


# ---------------------------------------------------------------------------
# Test: golden converted-structure fixture (success criteria 3 & 6)
# ---------------------------------------------------------------------------


def _build_golden_tree(root: Path) -> None:
    """
    Build a small, correctly-converted content tree:
    a COURSE with a numbered TOPIC subdirectory and a numbered FORM subdirectory.
    Role files named per convention, no uuid fields.
    This is the shape the content-formatter agent is instructed to produce.
    """
    # Course role file (no uuid, no icon)
    (root / "course.md").write_text(
        "---\n"
        "content_type: COURSE\n"
        "title: Getting Started\n"
        "description: A short intro course.\n"
        "---\n"
        "\nWelcome to this course.\n",
        encoding="utf-8",
    )

    # Numbered topic subdirectory
    topic_dir = root / "01. introduction"
    topic_dir.mkdir()
    (topic_dir / "01. overview.md").write_text(
        "---\n"
        "content_type: TOPIC\n"
        "title: Overview\n"
        "---\n"
        "\n"
        "# What You Will Learn\n"
        "\n"
        "This topic covers the basics.\n",
        encoding="utf-8",
    )

    # Numbered form subdirectory
    form_dir = root / "02. check-your-knowledge"
    form_dir.mkdir()
    (form_dir / "form.md").write_text(
        "---\n"
        "content_type: FORM\n"
        "title: Check Your Knowledge\n"
        "strategy: QUIZ\n"
        "quiz_show_incorrect: true\n"
        "quiz_pass_percentage: 80\n"
        "---\n",
        encoding="utf-8",
    )


def test_golden_converted_structure_exits_zero(tmp_path: Path) -> None:
    """
    The golden correctly-converted structure must pass validation (exit 0).
    This ties the target shape documented in skills/agent to the actual schema.
    """
    golden_root = tmp_path / "golden-course"
    golden_root.mkdir()
    _build_golden_tree(golden_root)

    result = run_validator(golden_root)
    assert result.returncode == 0, (
        f"Golden converted structure failed validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_golden_structure_idempotent(tmp_path: Path) -> None:
    """
    Running the validator twice on the golden structure must produce the same
    result — structure-level idempotency.
    """
    golden_root = tmp_path / "golden-idempotent"
    golden_root.mkdir()
    _build_golden_tree(golden_root)

    result1 = run_validator(golden_root)
    result2 = run_validator(golden_root)

    assert result1.returncode == 0, (
        f"First run failed.\nstdout: {result1.stdout}\nstderr: {result1.stderr}"
    )
    assert result2.returncode == 0, (
        f"Second run failed.\nstdout: {result2.stdout}\nstderr: {result2.stderr}"
    )
    assert result1.stdout == result2.stdout, (
        "Validator output changed between runs (not idempotent)."
    )
