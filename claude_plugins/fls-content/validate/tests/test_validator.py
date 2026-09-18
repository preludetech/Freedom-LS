"""
Tests for the bundled standalone validator (fls-content/validate/validate.py).

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
UV_BASE = [
    "uv",
    "run",
    "--no-project",
    "--with",
    "pydantic",
    "--with",
    "pyyaml",
    "--with",
    "python-frontmatter",
    "--with",
    "babel",
]
UV_CMD = [*UV_BASE, "python", str(VALIDATE_SCRIPT)]

# Cap subprocess runtime so a cold uv cache fetching deps can't hang the suite.
_SUBPROCESS_TIMEOUT = 120


def _clean_env() -> dict[str, str]:
    """Minimal env: PATH so uv can find python, HOME for its cache, no Django settings."""
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", tempfile.gettempdir()),
    }


@pytest.fixture(scope="session", autouse=True)
def _require_validator_env() -> None:
    """Skip these subprocess tests if the bundled validator's uv env can't be built.

    The tests shell out to `uv run --no-project --with …`, which needs `uv` on PATH
    and the three deps resolvable (cached or via network). `--disable-socket` only
    covers the pytest process, not the subprocess, so on a cold cache without network
    this would otherwise hang or fail opaquely. Probe once and skip with a clear reason.
    """
    try:
        probe = subprocess.run(
            [*UV_BASE, "python", "-c", "import pydantic, yaml, frontmatter, babel"],
            capture_output=True,
            text=True,
            env=_clean_env(),
            timeout=_SUBPROCESS_TIMEOUT,
        )
    except FileNotFoundError:
        pytest.skip("`uv` is not installed or not on PATH")
    except subprocess.TimeoutExpired:
        pytest.skip(
            "Timed out building the bundled validator env "
            "(uv could not resolve pydantic/pyyaml/python-frontmatter offline)"
        )
    if probe.returncode != 0:
        pytest.skip(
            "Bundled validator env unavailable — uv could not resolve "
            f"pydantic/pyyaml/python-frontmatter.\nstderr: {probe.stderr.strip()}"
        )


def run_validator(
    path: Path, repo_root: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the bundled validator against *path* in a clean environment.

    The validator reads `.fls-content.yaml` from its working directory (the repo root),
    never by searching. *repo_root* sets that working directory; it defaults to the
    target's parent, which is the test repo root (``tmp_path``) for every scenario here.
    """
    cwd = repo_root if repo_root is not None else path.parent
    return subprocess.run(
        [*UV_CMD, str(path)],
        capture_output=True,
        text=True,
        env=_clean_env(),
        cwd=str(cwd),
        timeout=_SUBPROCESS_TIMEOUT,
    )


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


def write_course_with_access(directory: Path, access_block: str) -> Path:
    """Write a COURSE role file whose frontmatter includes the given access block.

    *access_block* is raw YAML inserted into the frontmatter (e.g.
    "access_config:\n  access_type: free\n").
    """
    path = directory / "course.md"
    path.write_text(
        f"---\ncontent_type: COURSE\ntitle: My Course\n{access_block}---\n",
        encoding="utf-8",
    )
    return path


def write_repo_config(directory: Path, access_types: list[str]) -> Path:
    """Write a .fls-content.yaml declaring the repo's valid access_types."""
    path = directory / ".fls-content.yaml"
    body = "access_types:\n" + "".join(f"  - {t}\n" for t in access_types)
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _repo_root_config(tmp_path: Path) -> None:
    """Give every test a repo-root `.fls-content.yaml` (the validator requires one).

    The validator reads it from its working directory, which `run_validator` sets to the
    target's parent — i.e. ``tmp_path``. Tests that exercise specific access-type behaviour
    overwrite or delete this file.
    """
    write_repo_config(tmp_path, ["free", "application_gated"])


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


def test_course_validates_without_django(tmp_path: Path) -> None:
    """A COURSE file must validate without Django installed (icon stub works)."""
    write_valid_course(tmp_path)
    result = run_validator(tmp_path / "course.md")
    assert result.returncode == 0, (
        f"COURSE validation raised unexpectedly (icon stub may be broken).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


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


def test_empty_directory_exits_nonzero(tmp_path: Path) -> None:
    """A directory with no content files must not report success."""
    empty = tmp_path / "no-content"
    empty.mkdir()
    # README.md is skipped by the validator's file filter, so this dir has zero
    # content files — a typo'd path should not read as "validated".
    (empty / "README.md").write_text("# ignored\n", encoding="utf-8")

    result = run_validator(empty)
    assert result.returncode != 0, (
        f"Expected non-zero exit for a directory with no content files.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


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


# ---------------------------------------------------------------------------
# access_config validation
# ---------------------------------------------------------------------------


def test_course_no_access_config_exits_zero(tmp_path: Path) -> None:
    """A COURSE with no access_config is valid (defaults to free)."""
    write_course_with_access(tmp_path, "")
    result = run_validator(tmp_path / "course.md")
    assert result.returncode == 0, (
        f"Course without access_config should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.parametrize("access_type", ["free", "application_gated"])
def test_course_shipped_access_types_exit_zero(
    tmp_path: Path, access_type: str
) -> None:
    """A config that declares no `access_types` key falls back to the shipped vocabulary.

    The FLS shipped set (free, application_gated) must validate via that fallback, even
    though the repo config here declares no access_types of its own.
    """
    (tmp_path / ".fls-content.yaml").write_text(
        "admonition_types:\n  - note\n", encoding="utf-8"
    )
    write_course_with_access(
        tmp_path, f"access_config:\n  access_type: {access_type}\n"
    )
    result = run_validator(tmp_path / "course.md")
    assert result.returncode == 0, (
        f"access_type={access_type!r} should be valid by default.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_course_application_form_exits_zero(tmp_path: Path) -> None:
    """A gated course names its application form inside access_config."""
    write_course_with_access(
        tmp_path,
        "access_config:\n"
        "  access_type: application_gated\n"
        "  application_form: ../application_form/form.md\n",
    )
    result = run_validator(tmp_path / "course.md")
    assert result.returncode == 0, (
        f"An access_config naming an application_form should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_course_empty_application_form_exits_nonzero(tmp_path: Path) -> None:
    """An application_form with no path is a typo, not a course with no form."""
    write_course_with_access(
        tmp_path,
        "access_config:\n  access_type: application_gated\n  application_form: ''\n",
    )
    result = run_validator(tmp_path / "course.md")
    assert result.returncode != 0, (
        f"An empty application_form should fail validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )


def test_course_unknown_access_config_key_exits_nonzero(tmp_path: Path) -> None:
    """An unknown key under access_config is rejected."""
    write_course_with_access(
        tmp_path, "access_config:\n  access_type: free\n  price: 50\n"
    )
    result = run_validator(tmp_path / "course.md")
    assert result.returncode != 0, (
        f"Unknown access_config key should fail validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )


def test_course_invalid_access_type_exits_nonzero(tmp_path: Path) -> None:
    """An access_type outside the deployment vocabulary is rejected."""
    write_course_with_access(tmp_path, "access_config:\n  access_type: paid\n")
    result = run_validator(tmp_path / "course.md")
    assert result.returncode != 0, (
        f"Invalid access_type should fail validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )


def test_repo_config_narrows_access_types(tmp_path: Path) -> None:
    """A .fls-content.yaml declaring only `free` rejects application_gated courses."""
    write_repo_config(tmp_path, ["free"])
    write_course_with_access(
        tmp_path, "access_config:\n  access_type: application_gated\n"
    )
    result = run_validator(tmp_path / "course.md")
    assert result.returncode != 0, (
        f"application_gated should be rejected when the repo declares only `free`.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_repo_config_admits_custom_access_type(tmp_path: Path) -> None:
    """A .fls-content.yaml declaring a custom type accepts a course using it."""
    write_repo_config(tmp_path, ["free", "subscription"])
    write_course_with_access(tmp_path, "access_config:\n  access_type: subscription\n")
    result = run_validator(tmp_path / "course.md")
    assert result.returncode == 0, (
        f"A custom access_type declared in .fls-content.yaml should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_malformed_repo_config_fails(tmp_path: Path) -> None:
    """A malformed .fls-content.yaml is a hard error, not a silent fallback."""
    (tmp_path / ".fls-content.yaml").write_text(
        "access_types: [free\n  broken: : :\n", encoding="utf-8"
    )
    write_course_with_access(tmp_path, "access_config:\n  access_type: free\n")
    result = run_validator(tmp_path / "course.md")
    assert result.returncode != 0, (
        f"A malformed .fls-content.yaml should fail validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )


def test_missing_repo_config_fails(tmp_path: Path) -> None:
    """A missing repo-root .fls-content.yaml is a hard error pointing at /fls-content:init."""
    (tmp_path / ".fls-content.yaml").unlink()  # remove the autouse default
    write_course_with_access(tmp_path, "access_config:\n  access_type: free\n")
    result = run_validator(tmp_path / "course.md")
    assert result.returncode != 0, (
        f"A missing .fls-content.yaml should fail validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )
    assert "/fls-content:init" in combined, (
        f"Missing-config error should tell the author to run /fls-content:init.\n{combined}"
    )


# ---------------------------------------------------------------------------
# table_of_contents_in_development
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("visibility_block", ["", "visibility: coming_soon\n"])
def test_toc_in_development_exits_zero_for_any_visibility(
    tmp_path: Path, visibility_block: str
) -> None:
    """The flag is independent of visibility, including the default (published).

    An application-gated course can be open for applications while its contents
    are still being written, so the flag must not be coupled to visibility.
    """
    (tmp_path / "course.md").write_text(
        "---\n"
        "content_type: COURSE\n"
        "title: Open For Applications\n"
        f"{visibility_block}"
        "table_of_contents_in_development: true\n"
        "access_config:\n"
        "  access_type: application_gated\n"
        "---\n",
        encoding="utf-8",
    )
    result = run_validator(tmp_path / "course.md")
    assert result.returncode == 0, (
        f"table_of_contents_in_development must not be constrained by visibility.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def write_course_categories(directory: Path, body: str) -> Path:
    """Write a COURSE_CATEGORIES declaration whose `categories:` list is *body*."""
    path = directory / "course_categories.yaml"
    path.write_text(
        f"---\ncontent_type: COURSE_CATEGORIES\ncategories:\n{body}---\n",
        encoding="utf-8",
    )
    return path


def write_categorised_course(directory: Path, category_block: str) -> Path:
    """Write a COURSE role file whose frontmatter includes the given category block."""
    path = directory / "course.md"
    path.write_text(
        f"---\ncontent_type: COURSE\ntitle: My Course\n{category_block}---\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def declared_categories(tmp_path: Path) -> Path:
    """Declare `start-here` and `assessment` at the test repo root."""
    return write_course_categories(
        tmp_path,
        "  - slug: start-here\n    title: Start here\n"
        "  - slug: assessment\n    title: Assessment\n",
    )


def assert_validator_fails(
    result: subprocess.CompletedProcess[str], expected: str
) -> None:
    """The run failed, said *expected*, and did not spill a traceback."""
    combined = result.stdout + result.stderr
    assert result.returncode != 0, (
        f"Expected validation to fail.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert expected in combined, (
        f"Expected {expected!r} in the validator output.\n{combined}"
    )
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )


def test_single_category_needs_no_dashboard_category(
    tmp_path: Path, declared_categories: Path
) -> None:
    """One entry in `categories` resolves as the dashboard category on its own."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    write_categorised_course(course_dir, "categories:\n  - start-here\n")

    result = run_validator(tmp_path, repo_root=tmp_path)
    assert result.returncode == 0, (
        f"A course with a single declared category should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_two_categories_with_dashboard_category_validates(
    tmp_path: Path, declared_categories: Path
) -> None:
    """Two categories plus an explicit `dashboard_category` is valid."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    write_categorised_course(
        course_dir,
        "categories:\n  - start-here\n  - assessment\ndashboard_category: start-here\n",
    )

    result = run_validator(tmp_path, repo_root=tmp_path)
    assert result.returncode == 0, (
        f"Two categories with an explicit dashboard_category should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_two_categories_without_dashboard_category_fails(
    tmp_path: Path, declared_categories: Path
) -> None:
    """Two categories and no `dashboard_category` leaves the dashboard no choice to make."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    write_categorised_course(
        course_dir, "categories:\n  - start-here\n  - assessment\n"
    )

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path),
        "dashboard_category must name which one",
    )


def test_dashboard_category_outside_categories_fails(
    tmp_path: Path, declared_categories: Path
) -> None:
    """`dashboard_category` has to be one of the course's own `categories`."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    write_categorised_course(
        course_dir,
        "categories:\n  - start-here\ndashboard_category: assessment\n",
    )

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path),
        "has to be one the course belongs to",
    )


def test_undeclared_category_slug_fails(
    tmp_path: Path, declared_categories: Path
) -> None:
    """A slug no `course_categories.yaml` declares is caught across files."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    write_categorised_course(course_dir, "categories:\n  - nonexistent\n")

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path),
        "no category is declared with this slug in this content repo",
    )


def test_category_declared_after_the_course_in_walk_order_still_resolves(
    tmp_path: Path, declared_categories: Path
) -> None:
    """The cross-file pass runs after the whole walk, so file order cannot matter.

    `aaa-course/` sorts before `course_categories.yaml`, so the course is parsed
    first and its slug can only resolve once every file has been read.
    """
    course_dir = tmp_path / "aaa-course"
    course_dir.mkdir()
    write_categorised_course(course_dir, "categories:\n  - assessment\n")

    result = run_validator(tmp_path, repo_root=tmp_path)
    assert result.returncode == 0, (
        f"A course parsed before the declaration should still resolve.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_duplicate_category_slug_fails(tmp_path: Path) -> None:
    """Every entry needs its own slug."""
    write_course_categories(
        tmp_path,
        "  - slug: start-here\n    title: Start here\n"
        "  - slug: start-here\n    title: Start again\n",
    )

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path), "Duplicate category slug"
    )


def test_reserved_category_slug_fails(tmp_path: Path) -> None:
    """The dashboard's built-in section slugs are not available to categories."""
    write_course_categories(tmp_path, "  - slug: history\n    title: History\n")

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path),
        "reserved for the dashboard's built-in sections",
    )


def test_second_categories_declaration_fails(tmp_path: Path) -> None:
    """A repo declares its categories exactly once."""
    write_course_categories(tmp_path, "  - slug: start-here\n    title: Start here\n")
    other = tmp_path / "elsewhere"
    other.mkdir()
    write_course_categories(other, "  - slug: assessment\n    title: Assessment\n")

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path),
        "Multiple COURSE_CATEGORIES declarations found",
    )


def test_categories_declared_inside_a_course_directory_fails(tmp_path: Path) -> None:
    """The declaration belongs at the repo root, not inside a course."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    write_valid_course(course_dir)
    write_course_categories(course_dir, "  - slug: start-here\n    title: Start here\n")

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path),
        "declaration inside a course directory",
    )


def test_retired_singular_category_field_fails(tmp_path: Path) -> None:
    """A leftover `category:` on a course names its replacement in the error."""
    course_dir = tmp_path / "my-course"
    course_dir.mkdir()
    write_categorised_course(course_dir, "category: start-here\n")

    assert_validator_fails(
        run_validator(tmp_path, repo_root=tmp_path),
        "'category' is no longer a course field",
    )


def test_em_dash_in_a_value_does_not_split_the_document(tmp_path: Path) -> None:
    """Only a `---` alone on its line separates YAML documents.

    A `---` written inside a description used to be treated as a separator,
    cutting the value in half and leaving the tail as a bogus second document.
    """
    path = tmp_path / "01. page.yaml"
    path.write_text(
        "---\n"
        "content_type: FORM_PAGE\n"
        "title: A Page\n"
        "description: >-\n"
        "  A dash written in prose\n"
        "  ---\n"
        "  should not split this file.\n"
        "---\n",
        encoding="utf-8",
    )

    result = run_validator(path)
    assert result.returncode == 0, (
        f"A `---` inside a value should stay part of that value.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# FORM_QUESTION types and bounds


def write_question_page(tmp_path: Path, question_block: str) -> Path:
    """Write a FORM_PAGE yaml whose later documents are *question_block*.

    The page header is the first document; a later document carrying a `question`
    key is read as FORM_QUESTION, which is how an authored form page is shaped.
    """
    path = tmp_path / "01. questions.yaml"
    path.write_text(
        "---\ncontent_type: FORM_PAGE\ntitle: Questions\n---\n" + question_block,
        encoding="utf-8",
    )
    return path


def test_every_question_type_validates(tmp_path: Path) -> None:
    """All twelve question types are accepted, named one by one.

    The types are listed literally rather than derived, so adding a member to the
    live QuestionType without re-syncing this bundle fails here. `extra="forbid"`
    plus a strict enum means a stale copy rejects content that saves cleanly.
    """
    types = [
        "multiple_choice",
        "checkboxes",
        "short_text",
        "long_text",
        "number",
        "file_upload",
        "date",
        "time",
        "email",
        "url",
        "phone",
        "dropdown",
    ]
    block = "".join(f"---\nquestion: Q {t}\ntype: {t}\n" for t in types)

    result = run_validator(write_question_page(tmp_path, block))
    assert result.returncode == 0, (
        f"Every question type should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_bounds_and_decimal_places_are_accepted(tmp_path: Path) -> None:
    """min, max and decimal_places are known fields on the types that take them."""
    block = (
        "---\nquestion: Birth date\ntype: date\nmin: '1900-01-01'\nmax: '2010-12-31'\n"
        "---\nquestion: Years\ntype: number\nmin: 0\nmax: 70\ndecimal_places: 2\n"
        "---\nquestion: Preferred time\ntype: time\nmin: '09:00'\nmax: '17:00'\n"
    )

    result = run_validator(write_question_page(tmp_path, block))
    assert result.returncode == 0, (
        f"Bounds and decimal_places should be accepted.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_unquoted_date_bound_validates(tmp_path: Path) -> None:
    """An unquoted date bound reaches the model as a date and is coerced to str."""
    block = "---\nquestion: Birth date\ntype: date\nmin: 1900-01-01\n"

    result = run_validator(write_question_page(tmp_path, block))
    assert result.returncode == 0, (
        f"An unquoted date bound should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_non_zero_padded_date_bound_validates(tmp_path: Path) -> None:
    """`content_save` accepts a bound whose month and day are not zero-padded.

    Django's parse_date falls back to a permissive regex when date.fromisoformat
    refuses `2010-1-1`. A stdlib-only port of the bounds check would reject this
    here and pass it there — a validator that fails content which saves cleanly,
    which is the whole failure this bundle exists to avoid.
    """
    block = "---\nquestion: Birth date\ntype: date\nmin: 2010-1-1\n"

    result = run_validator(write_question_page(tmp_path, block))
    assert result.returncode == 0, (
        f"A non-zero-padded date bound should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_decimal_places_on_a_short_text_question_fails(tmp_path: Path) -> None:
    """Decimal places mean nothing on a question that has no numeric answer."""
    block = "---\nquestion: Why?\ntype: short_text\ndecimal_places: 2\n"

    result = run_validator(write_question_page(tmp_path, block))
    assert_validator_fails(result, "decimal_places is only valid on number questions")


def test_min_on_a_checkboxes_question_fails(tmp_path: Path) -> None:
    """A bound needs a type with an order; checkboxes has none."""
    block = "---\nquestion: Pick some\ntype: checkboxes\nmin: '5'\n"

    result = run_validator(write_question_page(tmp_path, block))
    assert_validator_fails(
        result, "min/max are only valid on date, time or number questions"
    )


def test_min_that_does_not_parse_as_a_date_fails(tmp_path: Path) -> None:
    """A bound that does not parse as its own type is an authoring mistake."""
    block = "---\nquestion: Birth date\ntype: date\nmin: banana\n"

    result = run_validator(write_question_page(tmp_path, block))
    assert_validator_fails(result, 'min "banana" is not a valid date')


def test_unquoted_time_bound_that_still_parses_fails(tmp_path: Path) -> None:
    """An unquoted `17:00` is read by YAML as the integer 1020 — i.e. 10:20.

    It parses, so nothing downstream would complain; it just means a different
    time than the author wrote. The shape check is the only thing that catches a
    mistake which silently changes meaning rather than failing.
    """
    block = "---\nquestion: Preferred time\ntype: time\nmax: 17:00\n"

    result = run_validator(write_question_page(tmp_path, block))
    assert_validator_fails(result, "is not written as HH:MM")


def test_a_number_bound_finer_than_the_allowed_decimal_places_fails(
    tmp_path: Path,
) -> None:
    """A bound may not be finer-grained than the answers it is bounding."""
    block = "---\nquestion: Years\ntype: number\nmax: '70.5'\n"

    result = run_validator(write_question_page(tmp_path, block))
    assert_validator_fails(result, "has more decimal places than this question allows")


# ---------------------------------------------------------------------------
# price
# ---------------------------------------------------------------------------


def write_course_with_price(directory: Path, price_block: str) -> Path:
    """Write a COURSE role file whose frontmatter includes the given price block.

    *price_block* is raw YAML inserted into the frontmatter (e.g.
    "price:\n  kind: fixed\n  amount: \"1499.00\"\n").
    """
    path = directory / "course.md"
    path.write_text(
        f"---\ncontent_type: COURSE\ntitle: My Course\n{price_block}---\n",
        encoding="utf-8",
    )
    return path


def test_spec_example_price_frontmatter_validates(tmp_path: Path) -> None:
    """The discounted price example given in the spec validates cleanly."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            "price:\n"
            "  kind: discounted\n"
            '  amount: "1499.00"\n'
            '  sale_amount: "999.00"\n'
            "  sale_ends_on: 2026-12-31\n"
            "  currency: ZAR\n"
            "  tax_note: incl. VAT\n",
        )
    )
    assert result.returncode == 0, (
        f"The spec's example price frontmatter should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_open_ended_range_price_validates(tmp_path: Path) -> None:
    """A range with a low amount and no high amount reads as "From X"."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            'price:\n  kind: range\n  low_amount: "500.00"\n  currency: ZAR\n',
        )
    )
    assert result.returncode == 0, (
        f"An open-ended range price should validate.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_price_unknown_currency_fails(tmp_path: Path) -> None:
    """An unrecognised currency code is rejected."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            'price:\n  kind: fixed\n  amount: "100.00"\n  currency: ZZZ\n',
        )
    )
    assert_validator_fails(result, "not a currency code Babel recognises")


def test_price_too_many_decimal_places_with_explicit_currency_fails(
    tmp_path: Path,
) -> None:
    """JPY has no minor units, so half a yen is rejected."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            'price:\n  kind: fixed\n  amount: "1500.50"\n  currency: JPY\n',
        )
    )
    assert_validator_fails(result, "more decimal places")


def test_price_amount_too_large_for_the_column_fails(tmp_path: Path) -> None:
    """The amount column holds at most nine digits before the decimal point."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            'price:\n  kind: fixed\n  amount: "1000000000"\n  currency: IDR\n',
        )
    )
    assert_validator_fails(result, "amount is too large")


def test_price_more_decimal_places_than_the_column_fails(tmp_path: Path) -> None:
    """CLF allows four decimal places, but the amount column stores only three."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            'price:\n  kind: fixed\n  amount: "0.1234"\n  currency: CLF\n',
        )
    )
    assert_validator_fails(result, "at most 3 decimal places")


def test_price_sale_not_below_original_fails(tmp_path: Path) -> None:
    """A sale_amount that is not less than amount is an authoring mistake."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            "price:\n"
            "  kind: discounted\n"
            '  amount: "100.00"\n'
            '  sale_amount: "100.00"\n'
            "  currency: ZAR\n",
        )
    )
    assert_validator_fails(result, "sale_amount must be less than amount")


def test_price_low_not_below_high_fails(tmp_path: Path) -> None:
    """A low_amount that is not less than high_amount is an authoring mistake."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            "price:\n"
            "  kind: range\n"
            '  low_amount: "100.00"\n'
            '  high_amount: "100.00"\n'
            "  currency: ZAR\n",
        )
    )
    assert_validator_fails(result, "high_amount must be greater than low_amount")


def test_price_bare_number_amount_fails(tmp_path: Path) -> None:
    """An unquoted amount is read through YAML's float parser -- refused."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            "price:\n  kind: fixed\n  amount: 100.00\n  currency: ZAR\n",
        )
    )
    assert_validator_fails(result, "write amounts as quoted strings")


def test_price_unknown_kind_fails(tmp_path: Path) -> None:
    """A `kind` outside the four known shapes fails the discriminated union."""
    result = run_validator(
        write_course_with_price(
            tmp_path,
            'price:\n  kind: subscription\n  amount: "100.00"\n',
        )
    )
    assert result.returncode != 0, (
        f"An unknown price kind should fail validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )


def test_price_currency_on_on_request_fails(tmp_path: Path) -> None:
    """`on_request` carries no currency -- extra="forbid" rejects it."""
    result = run_validator(
        write_course_with_price(
            tmp_path, "price:\n  kind: on_request\n  currency: ZAR\n"
        )
    )
    assert result.returncode != 0, (
        f"A currency on an on_request price should fail validation.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Traceback" not in combined, (
        f"Validator output contains a raw traceback:\n{combined}"
    )


def test_price_no_currency_and_three_decimal_places_passes(tmp_path: Path) -> None:
    """With no currency anywhere, the standalone validator skips the decimal check."""
    result = run_validator(
        write_course_with_price(
            tmp_path, 'price:\n  kind: fixed\n  amount: "1499.123"\n'
        )
    )
    assert result.returncode == 0, (
        f"A price with no currency should skip the decimal-place check.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
