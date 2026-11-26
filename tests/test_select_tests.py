"""Tests for `claude_plugins/django-stack/scripts/select_tests.py`.

The script's directory is hyphenated and not importable, and it finds its siblings through
`sys.path[0]`, so these tests run it as a subprocess against a throwaway `tmp_path` project:
a `pyproject.toml` plus a namespace package (`pkg/`, no `__init__.py`) holding apps.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest

from tests._script_trees import run_command, run_script, write_tree

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / "select_tests.py"

FULL_COMMAND = "command: uv run pytest -n auto"
WRAPPER = ".claude/ds/scripts/run_tests.sh"


def apps_py(dotted_name: str, class_name: str) -> str:
    return (
        "from django.apps import AppConfig\n\n\n"
        f"class {class_name}(AppConfig):\n"
        f'    name = "{dotted_name}"\n'
    )


APP_MAP_HEADER = "# App structure\n\n```mermaid\nflowchart TB\n"


def app_map(*lines: str) -> str:
    """A `docs/app_structure.md` in the form `generate_app_map.py` writes."""
    body = "".join(f"    {line}\n" for line in lines)
    return f"{APP_MAP_HEADER}{body}```\n"


def alpha_app() -> dict[str, str]:
    """An app with a module and a mirrored test file, and an app map listing it."""
    return {
        "pyproject.toml": "",
        "docs/app_structure.md": app_map("alpha"),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": apps_py("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/services.py": "",
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_services.py": "",
    }


def lines(output: str, kind: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith(f"{kind}:")]


def test_docs_path_alone_is_tier_none_without_a_command(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/guide.md")

    # Assert
    assert result.returncode == 0
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert lines(result.stdout, "command") == []
    assert lines(result.stdout, "why") == [
        "why: docs/guide.md -> none (matches docs/**)"
    ]


def test_migration_path_is_tier_full_with_the_whole_suite_command(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/migrations/0001_initial.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "command") == [FULL_COMMAND]
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/migrations/0001_initial.py -> full (matches **/migrations/**)"
    ]


def test_project_none_entry_makes_a_path_tier_none(tmp_path: Path) -> None:
    # Arrange
    write_tree(
        tmp_path,
        alpha_app() | {"pyproject.toml": '[tool.test_tiers]\nnone = ["notes/**"]\n'},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "notes/today.txt")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]


def test_project_escalation_entry_makes_a_path_tier_full(tmp_path: Path) -> None:
    # Arrange
    write_tree(
        tmp_path,
        alpha_app()
        | {"pyproject.toml": '[tool.test_tiers]\nescalation = ["pkg/alpha/**"]\n'},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert "matches pkg/alpha/**" in result.stdout


def test_generic_lists_apply_without_a_tool_test_tiers_table(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": "[tool.other]\nx = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "uv.lock")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]


@pytest.mark.parametrize(
    ("pyproject", "path"),
    [
        ("[tool.other]\nx = 1\n", "uv.lock"),
        ("", ".python-version"),
        ("", "package.json"),
        ("", "package-lock.json"),
        (
            '[tool.test_tiers]\ndependency_files = ["requirements/*.txt"]\n',
            "requirements/dev.txt",
        ),
    ],
)
def test_dependency_file_makes_a_path_tier_full(
    tmp_path: Path, pyproject: str, path: str
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": pyproject})

    # Act
    result = run_script(SCRIPT, tmp_path, path)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [f"why: {path} -> full (dependency file)"]


def test_generic_lists_apply_without_a_pyproject_file(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, {"docs/a.md": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]


@pytest.mark.parametrize("key", ["none", "escalation", "dependency_files"])
def test_non_list_value_exits_2_naming_the_key(tmp_path: Path, key: str) -> None:
    # Arrange
    write_tree(
        tmp_path, alpha_app() | {"pyproject.toml": f'[tool.test_tiers]\n{key} = "x"\n'}
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert result.returncode == 2
    assert key in result.stderr


def test_list_holding_a_non_string_exits_2_naming_the_key(tmp_path: Path) -> None:
    # Arrange
    write_tree(
        tmp_path,
        alpha_app() | {"pyproject.toml": "[tool.test_tiers]\nescalation = [1]\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert result.returncode == 2
    assert "escalation" in result.stderr


def test_malformed_pyproject_exits_2(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": "[tool.test_tiers\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert result.returncode == 2


def test_module_change_selects_the_owning_apps_test_directory(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)"
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests"
    ]


def test_owning_app_without_a_tests_directory_is_tier_none(tmp_path: Path) -> None:
    # Arrange
    write_tree(
        tmp_path,
        {
            "pyproject.toml": "",
            "docs/app_structure.md": app_map("beta"),
            "pkg/beta/__init__.py": "",
            "pkg/beta/apps.py": apps_py("pkg.beta", "BetaConfig"),
            "pkg/beta/services.py": "",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/beta/services.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert lines(result.stdout, "why") == [
        "why: pkg/beta/services.py -> none (owning app beta has no tests directory)"
    ]


def test_changed_test_file_selects_itself(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/tests/test_services.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/tests/test_services.py -> pkg/alpha/tests/test_services.py "
        "(changed test file)"
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests/test_services.py"
    ]


def test_deleted_test_file_selects_nothing(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/tests/test_gone.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/tests/test_gone.py -> none (deleted test file)"
    ]


def test_selected_test_directory_with_playwright_subdirectory_ignores_it(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pkg/alpha/tests/playwright/__init__.py": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov "
        "--ignore=pkg/alpha/tests/playwright pkg/alpha/tests"
    ]


def test_test_file_inside_a_selected_directory_is_dropped_from_the_command(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(
        SCRIPT, tmp_path, "pkg/alpha/services.py", "pkg/alpha/tests/test_services.py"
    )

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests"
    ]


def test_path_with_a_space_is_printed_shell_quoted(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pkg/alpha/tests/test_a b.py": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/tests/test_a b.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov 'pkg/alpha/tests/test_a b.py'"
    ]


def test_none_and_selected_paths_together_are_targeted(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md", "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert len(lines(result.stdout, "why")) == 2


def test_one_escalation_hit_among_selected_paths_is_full(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py", "pkg/urls.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "command") == [FULL_COMMAND]
    assert len(lines(result.stdout, "why")) == 2


def test_unmapped_path_is_full(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "scripts/deploy.sh")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        "why: scripts/deploy.sh -> full (unmapped path)"
    ]


@pytest.mark.parametrize(
    ("path", "tier"),
    [
        ("conftest.py", "full"),
        ("pkg/conftest.py", "full"),
        ("pkg/alpha/factories.py", "full"),
        ("pkg/alpha/fixtures/data.json", "full"),
        ("docs/x/y.md", "none"),
        ("docs/x.md", "none"),
        (".claude/settings.json", "none"),
        (".claude/ds/notes.md", "none"),
        (".github/workflows/ci.yml", "none"),
        ("README.md", "none"),
        ("pkg/README.md", "full"),
    ],
)
def test_glob_matching_facts(tmp_path: Path, path: str, tier: str) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, path)

    # Assert
    assert lines(result.stdout, "tier") == [f"tier: {tier}"]


def test_two_runs_over_the_same_tree_print_identical_output(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())
    args = ("pkg/alpha/services.py", "docs/a.md", "pkg/alpha/tests/test_services.py")

    # Act
    first = run_script(SCRIPT, tmp_path, *args)
    second = run_script(SCRIPT, tmp_path, *reversed(args))

    # Assert
    assert first.stdout == second.stdout


def test_working_tree_flag_picks_up_an_untracked_file(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())
    run_command(["git", "init"], tmp_path)
    run_command(["git", "add", "."], tmp_path)
    run_command(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-m",
            "init",
        ],
        tmp_path,
    )
    write_tree(tmp_path, {"docs/new.md": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree")

    # Assert
    assert lines(result.stdout, "why") == ["why: docs/new.md -> none (matches docs/**)"]


def test_working_tree_flag_picks_up_a_modified_tracked_file(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())
    run_command(["git", "init"], tmp_path)
    run_command(["git", "add", "."], tmp_path)
    run_command(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-m",
            "init",
        ],
        tmp_path,
    )
    write_tree(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]


def test_working_tree_flag_outside_a_repository_exits_2(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree")

    # Assert
    assert result.returncode == 2


def beta_gamma_apps(
    *, with_tests: tuple[str, ...] = ("beta", "gamma")
) -> dict[str, str]:
    """`alpha` plus `beta` (runtime importer) and `gamma` (test-only importer)."""
    tree = alpha_app() | {
        "docs/app_structure.md": app_map(
            "alpha", "beta", "gamma", "beta --> alpha", "gamma -.-> alpha"
        )
    }
    for name in ("beta", "gamma"):
        tree |= {
            f"pkg/{name}/__init__.py": "",
            f"pkg/{name}/apps.py": apps_py(f"pkg.{name}", f"{name.title()}Config"),
            f"pkg/{name}/views.py": "",
        }
        if name in with_tests:
            tree |= {f"pkg/{name}/tests/__init__.py": ""}
    return tree


def test_change_selects_the_test_directory_of_every_importer(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, beta_gamma_apps())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)",
        "why: pkg/alpha/services.py -> pkg/beta/tests (beta has a runtime dep on alpha)",
        "why: pkg/alpha/services.py -> pkg/gamma/tests "
        "(gamma has a test-only dep on alpha)",
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov "
        "pkg/alpha/tests pkg/beta/tests pkg/gamma/tests"
    ]


def test_change_in_an_app_nothing_imports_selects_only_that_app(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, beta_gamma_apps() | {"pkg/beta/tests/test_a.py": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/beta/models.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/beta/models.py -> pkg/beta/tests (owning app beta)"
    ]


def test_importer_without_a_tests_directory_selects_nothing_and_says_so(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, beta_gamma_apps(with_tests=("beta",)))

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert (
        "why: pkg/alpha/services.py -> none "
        "(gamma has a test-only dep on alpha; no tests directory)"
    ) in lines(result.stdout, "why")
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests pkg/beta/tests"
    ]


def test_importer_missing_from_the_app_list_selects_nothing_and_says_so(
    tmp_path: Path,
) -> None:
    # Arrange
    tree = alpha_app() | {
        "docs/app_structure.md": app_map("alpha", "ghost", "ghost --> alpha")
    }
    write_tree(tmp_path, tree)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert (
        "why: pkg/alpha/services.py -> none "
        "(ghost has a runtime dep on alpha; app not found)"
    ) in lines(result.stdout, "why")
    assert lines(result.stdout, "tier") == ["tier: targeted"]


def test_missing_app_map_makes_an_app_owned_change_full(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())
    (tmp_path / "docs/app_structure.md").unlink()

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/services.py -> full (docs/app_structure.md missing)"
    ]


def playwright_tree() -> dict[str, str]:
    return beta_gamma_apps() | {
        "pkg/alpha/tests/playwright/__init__.py": "",
        "pkg/beta/tests/playwright/__init__.py": "",
    }


@pytest.mark.parametrize(
    "path",
    [
        "pkg/alpha/templates/alpha/page.html",
        "pkg/alpha/static/alpha/x.js",
        "pkg/alpha/views.py",
        "pkg/alpha/views/x.py",
    ],
)
def test_ui_change_keeps_the_touched_apps_browser_tests_in_the_run(
    tmp_path: Path, path: str
) -> None:
    # Arrange
    write_tree(tmp_path, playwright_tree() | {path: ""})

    # Act
    result = run_script(SCRIPT, tmp_path, path)

    # Assert
    command = lines(result.stdout, "command")[0]
    assert "--ignore=pkg/alpha/tests/playwright" not in command
    assert "--ignore=pkg/beta/tests/playwright" in command
    assert "playwright: pkg/alpha/tests/playwright" in lines(result.stdout, "why")[0]


def test_non_ui_change_ignores_every_playwright_directory(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, playwright_tree())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    command = lines(result.stdout, "command")[0]
    assert "--ignore=pkg/alpha/tests/playwright" in command
    assert "--ignore=pkg/beta/tests/playwright" in command


def test_changed_playwright_test_selects_itself_and_lifts_the_ignore(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(
        tmp_path, playwright_tree() | {"pkg/alpha/tests/playwright/test_x.py": ""}
    )

    # Act
    result = run_script(
        SCRIPT, tmp_path, "pkg/alpha/tests/playwright/test_x.py", "pkg/alpha/models.py"
    )

    # Assert
    command = lines(result.stdout, "command")[0]
    assert "--ignore=pkg/alpha/tests/playwright" not in command
    assert "--ignore=pkg/beta/tests/playwright" in command


def test_changed_playwright_test_alone_runs_just_that_file(tmp_path: Path) -> None:
    # Arrange
    write_tree(
        tmp_path, playwright_tree() | {"pkg/alpha/tests/playwright/test_x.py": ""}
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/tests/playwright/test_x.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests/playwright/test_x.py"
    ]
    assert (
        "(changed test file; playwright: pkg/alpha/tests/playwright)"
        in lines(result.stdout, "why")[0]
    )


@pytest.mark.parametrize("path", [".claude/ds/scripts/x.sh", "tests/_helper.py"])
def test_generic_tooling_paths_select_the_top_level_tests(
    tmp_path: Path, path: str
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"tests/test_tool.py": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, path)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert lines(result.stdout, "why") == [f"why: {path} -> tests (tooling)"]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov tests"
    ]


def test_top_level_tests_directory_has_its_playwright_subdirectory_ignored(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(
        tmp_path,
        alpha_app() | {"tests/test_tool.py": "", "tests/playwright/__init__.py": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "tests/_helper.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov --ignore=tests/playwright tests"
    ]


TOOLING_TABLE = """
[[tool.test_tiers.tooling]]
glob = "plugins/*/scripts/**"
tests = ["tests", "pkg/alpha/tests", "missing/tests"]
"""


def test_project_tooling_entry_selects_existing_directories_and_reports_missing_ones(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(
        tmp_path, alpha_app() | {"pyproject.toml": TOOLING_TABLE, "tests/t.py": ""}
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "plugins/p/scripts/run.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: plugins/p/scripts/run.py -> tests, pkg/alpha/tests (tooling)",
        "why: plugins/p/scripts/run.py -> none (tooling; missing/tests does not exist)",
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests tests"
    ]


def test_project_tooling_entry_naming_only_missing_directories_selects_nothing(
    tmp_path: Path,
) -> None:
    # Arrange
    table = (
        '[[tool.test_tiers.tooling]]\nglob = "plugins/**"\ntests = ["missing/tests"]\n'
    )
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": table})

    # Act
    result = run_script(SCRIPT, tmp_path, "plugins/x.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert lines(result.stdout, "why") == [
        "why: plugins/x.py -> none (tooling; missing/tests does not exist)"
    ]


@pytest.mark.parametrize(
    "table",
    [
        '[tool.test_tiers]\ntooling = "x"\n',
        '[[tool.test_tiers.tooling]]\nglob = 1\ntests = ["a"]\n',
        '[[tool.test_tiers.tooling]]\nglob = "a"\ntests = "a"\n',
        '[[tool.test_tiers.tooling]]\ntests = ["a"]\n',
    ],
)
def test_malformed_tooling_entry_exits_2_naming_the_key(
    tmp_path: Path, table: str
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": table})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert result.returncode == 2
    assert "tooling" in result.stderr


MARKERS_TABLE = '[tool.test_tiers]\nmarkers = "not slow"\n'


def test_project_markers_entry_is_passed_to_the_full_command(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": MARKERS_TABLE})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/migrations/0001_initial.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto -m 'not slow'"
    ]


def test_project_markers_entry_is_passed_to_the_targeted_command(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": MARKERS_TABLE})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov -m 'not slow' pkg/alpha/tests"
    ]


def test_non_string_markers_entry_exits_2_naming_the_key(tmp_path: Path) -> None:
    # Arrange
    table = '[tool.test_tiers]\nmarkers = ["slow"]\n'
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": table})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert result.returncode == 2
    assert "markers" in result.stderr


NARROW_TABLE = "[tool.test_tiers]\nnarrow = true\n"


@pytest.mark.parametrize("value", ['"yes"', "1"])
def test_non_boolean_narrow_entry_exits_2_naming_the_key(
    tmp_path: Path, value: str
) -> None:
    # Arrange
    table = f"[tool.test_tiers]\nnarrow = {value}\n"
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": table})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert result.returncode == 2
    assert "[tool.test_tiers] 'narrow' must be true or false" in result.stderr


def test_narrow_false_gives_the_same_output_as_no_narrow_key(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app())
    without_key = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")
    write_tree(tmp_path, {"pyproject.toml": "[tool.test_tiers]\nnarrow = false\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert result.stdout == without_key.stdout


@pytest.mark.parametrize(
    ("pyproject", "args", "expects_mode_line"),
    [
        (NARROW_TABLE, (), True),
        ("", (), False),
        ("[tool.test_tiers]\nnarrow = false\n", (), False),
        (NARROW_TABLE, ("--wide",), False),
    ],
)
def test_mode_line_follows_the_tier_line_only_while_narrowing_is_in_effect(
    tmp_path: Path,
    pyproject: str,
    args: tuple[str, ...],
    expects_mode_line: bool,
) -> None:
    # Arrange
    git_repo(tmp_path, alpha_app() | {"pyproject.toml": pyproject})

    # Act
    result = run_script(SCRIPT, tmp_path, *args, "pkg/alpha/services.py")

    # Assert
    output_lines = result.stdout.splitlines()
    assert ("mode: narrow" in output_lines) is expects_mode_line
    if expects_mode_line:
        assert output_lines[1] == "mode: narrow"
        assert output_lines[0].startswith("tier:")


@pytest.mark.parametrize(
    "arguments",
    [
        ("pkg/alpha/services.py",),
        ("pkg/alpha/migrations/0001_initial.py",),
        ("--range", "HEAD~1..HEAD"),
    ],
)
def test_wide_with_narrow_true_gives_the_same_output_as_no_narrow_key(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})
    without_key = run_script(SCRIPT, tmp_path, *arguments)
    write_tree(tmp_path, {"pyproject.toml": NARROW_TABLE})

    # Act
    result = run_script(SCRIPT, tmp_path, "--wide", *arguments)

    # Assert
    assert result.returncode == 0
    assert result.stdout == without_key.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ("--working-tree",),
        ("--range", "HEAD~1..HEAD"),
        ("--upstream-range", "HEAD~2..HEAD~1"),
        ("--tests-changed-in", "HEAD~1..HEAD"),
    ],
)
def test_wide_combines_with_every_diff_source_flag(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        alpha_app(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/alpha/tests/test_services.py": "y = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "--wide", *arguments)

    # Assert
    assert result.returncode == 0


def commit_all(project: Path, message: str) -> None:
    run_command(["git", "add", "."], project)
    run_command(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-m",
            message,
        ],
        project,
    )


def repo_with_two_commits(tmp_path: Path, second_commit: dict[str, str]) -> None:
    """A repository whose HEAD~1..HEAD range holds exactly `second_commit`."""
    write_tree(tmp_path, alpha_app())
    run_command(["git", "init"], tmp_path)
    commit_all(tmp_path, "init")
    write_tree(tmp_path, second_commit)
    commit_all(tmp_path, "change")


def test_range_selects_the_test_directory_of_a_file_changed_in_it(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "--range", "HEAD~1..HEAD")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests"
    ]


def test_tests_changed_in_a_docs_only_range_stays_tier_none(tmp_path: Path) -> None:
    # Arrange
    repo_with_two_commits(
        tmp_path,
        {"docs/new.md": "", "pkg/alpha/tests/test_services.py": "x = 1\n"},
    )
    run_command(["git", "tag", "docs-only"], tmp_path)
    write_tree(tmp_path, {"docs/other.md": ""})
    commit_all(tmp_path, "docs")

    # Act
    result = run_script(
        SCRIPT,
        tmp_path,
        "--range",
        "HEAD~1..HEAD",
        "--tests-changed-in",
        "HEAD~2..docs-only",
    )

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert lines(result.stdout, "command") == []
    assert (
        "why: pkg/alpha/tests/test_services.py -> pkg/alpha/tests/test_services.py"
        " (branch test file; runs only with a targeted tier)"
    ) in lines(result.stdout, "why")


def test_tests_changed_in_adds_the_branch_test_file_to_a_selecting_range(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_two_commits(
        tmp_path,
        {"pkg/alpha/services.py": "x = 1\n", "pkg/alpha/tests/test_extra.py": ""},
    )
    write_tree(tmp_path, {"pkg/alpha/tests/test_late.py": ""})
    commit_all(tmp_path, "late test")
    run_command(["git", "tag", "late"], tmp_path)

    # Act
    result = run_script(
        SCRIPT,
        tmp_path,
        "--range",
        "HEAD~2..HEAD~1",
        "--tests-changed-in",
        "HEAD~1..late",
    )

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert (
        "why: pkg/alpha/tests/test_late.py -> pkg/alpha/tests/test_late.py"
        " (branch test file; runs only with a targeted tier)"
    ) in lines(result.stdout, "why")


def test_tests_changed_in_skips_a_test_file_deleted_in_the_checkout(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/tests/test_extra.py": ""})
    run_command(["git", "rm", "-q", "pkg/alpha/tests/test_extra.py"], tmp_path)
    commit_all(tmp_path, "remove")

    # Act
    result = run_script(
        SCRIPT,
        tmp_path,
        "--range",
        "HEAD~2..HEAD~2",
        "--tests-changed-in",
        "HEAD~1..HEAD",
    )

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert lines(result.stdout, "why") == []


@pytest.mark.parametrize(
    "value", ["--output=x", "HEAD~1..HEAD; ls", "HEAD", "a..b$(id)"]
)
@pytest.mark.parametrize(
    "option", ["--range", "--tests-changed-in", "--upstream-range"]
)
def test_range_value_that_is_not_a_plain_revision_range_exits_2(
    tmp_path: Path, option: str, value: str
) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, option, value)

    # Assert
    assert result.returncode == 2


def test_two_range_values_union_their_paths(tmp_path: Path) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})
    write_tree(tmp_path, {"docs/new.md": ""})
    commit_all(tmp_path, "docs")

    # Act
    result = run_script(
        SCRIPT, tmp_path, "--range", "HEAD~2..HEAD~1", "--range", "HEAD~1..HEAD"
    )

    # Assert
    assert lines(result.stdout, "why") == [
        "why: docs/new.md -> none (matches docs/**)",
        "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)",
    ]


def test_range_lists_both_sides_of_a_rename(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, beta_gamma_apps())
    run_command(["git", "init"], tmp_path)
    commit_all(tmp_path, "init")
    run_command(
        ["git", "mv", "pkg/alpha/services.py", "pkg/beta/services.py"], tmp_path
    )
    commit_all(tmp_path, "move")

    # Act
    result = run_script(SCRIPT, tmp_path, "--range", "HEAD~1..HEAD")

    # Assert
    why = lines(result.stdout, "why")
    assert "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)" in why
    assert "why: pkg/beta/services.py -> pkg/beta/tests (owning app beta)" in why
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov "
        "pkg/alpha/tests pkg/beta/tests pkg/gamma/tests"
    ]


def git_repo(tmp_path: Path, files: dict[str, str]) -> None:
    write_tree(tmp_path, files)
    run_command(["git", "init"], tmp_path)
    commit_all(tmp_path, "init")


def test_untracked_file_no_rule_knows_is_none_and_does_not_raise_the_tier(
    tmp_path: Path,
) -> None:
    # Arrange
    git_repo(tmp_path, alpha_app())
    write_tree(tmp_path, {"scratch.png": "", "docs/new.md": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert "why: scratch.png -> none (untracked and unmapped)" in lines(
        result.stdout, "why"
    )


def test_tracked_file_no_rule_knows_is_still_full(tmp_path: Path) -> None:
    # Arrange
    git_repo(tmp_path, alpha_app() | {"scratch.py": ""})
    write_tree(tmp_path, {"scratch.py": "x = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == ["why: scratch.py -> full (unmapped path)"]


def test_non_ascii_path_is_matched_to_its_app_whatever_git_quotes(
    tmp_path: Path,
) -> None:
    # Arrange
    git_repo(tmp_path, alpha_app())
    run_command(["git", "config", "core.quotePath", "true"], tmp_path)
    write_tree(tmp_path, {"pkg/alpha/café.py": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/café.py -> pkg/alpha/tests (owning app alpha)"
    ]


def test_changed_top_level_playwright_test_lifts_the_ignore(tmp_path: Path) -> None:
    # Arrange
    write_tree(
        tmp_path,
        alpha_app() | {"tests/test_tool.py": "", "tests/playwright/test_x.py": ""},
    )

    # Act
    result = run_script(
        SCRIPT, tmp_path, "tests/playwright/test_x.py", "tests/_helper.py"
    )

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov tests"
    ]
    assert (
        "why: tests/playwright/test_x.py -> tests/playwright/test_x.py "
        "(changed test file; playwright: tests/playwright)"
    ) in lines(result.stdout, "why")


FILE_TOOLING_TABLE = """
[[tool.test_tiers.tooling]]
glob = "plugins/**/*.md"
tests = ["tests/test_prompts.py", "tests/test_missing.py"]
"""


def test_project_tooling_entry_selects_a_test_file_and_reports_a_missing_one(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(
        tmp_path,
        alpha_app()
        | {"pyproject.toml": FILE_TOOLING_TABLE, "tests/test_prompts.py": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "plugins/p/commands/go.md")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: plugins/p/commands/go.md -> tests/test_prompts.py (tooling)",
        "why: plugins/p/commands/go.md -> none "
        "(tooling; tests/test_missing.py does not exist)",
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov tests/test_prompts.py"
    ]


def chain_apps() -> dict[str, str]:
    """`delta` imports `beta`, which imports `alpha`; `epsilon` imports test-only `gamma`."""
    tree = beta_gamma_apps() | {
        "docs/app_structure.md": app_map(
            "alpha",
            "beta",
            "gamma",
            "delta",
            "epsilon",
            "beta --> alpha",
            "gamma -.-> alpha",
            "delta --> beta",
            "epsilon --> gamma",
        )
    }
    for name in ("delta", "epsilon"):
        tree |= {
            f"pkg/{name}/__init__.py": "",
            f"pkg/{name}/apps.py": apps_py(f"pkg.{name}", f"{name.title()}Config"),
            f"pkg/{name}/tests/__init__.py": "",
        }
    return tree


def test_change_selects_apps_that_reach_it_through_a_runtime_dep(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, chain_apps())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)",
        "why: pkg/alpha/services.py -> pkg/beta/tests (beta has a runtime dep on alpha)",
        "why: pkg/alpha/services.py -> pkg/delta/tests "
        "(delta has a runtime dep on alpha through beta)",
        "why: pkg/alpha/services.py -> pkg/gamma/tests "
        "(gamma has a test-only dep on alpha)",
    ]


def test_dependency_cycle_lists_each_importer_once(tmp_path: Path) -> None:
    # Arrange
    cycle = app_map("alpha", "beta", "alpha --> beta", "beta --> alpha")
    write_tree(tmp_path, beta_gamma_apps() | {"docs/app_structure.md": cycle})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)",
        "why: pkg/alpha/services.py -> pkg/beta/tests (beta has a runtime dep on alpha)",
    ]


@pytest.mark.parametrize(
    "name",
    [
        "select_tests.py",
        "check_test_mirroring.py",
        "generate_app_map.py",
        "run_tests.py",
    ],
)
def test_plugin_script_starts_with_its_shebang(name: str) -> None:
    # Arrange
    script = SCRIPT.with_name(name)

    # Act
    first_line = script.read_text(encoding="utf-8").splitlines()[0]

    # Assert
    assert first_line == "#!/usr/bin/env python3"


def test_full_command_starts_with_the_runner_wrapper_when_installed(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {WRAPPER: ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/migrations/0001_initial.py")

    # Assert
    assert lines(result.stdout, "command") == [
        f"command: {WRAPPER} uv run pytest -n auto"
    ]


def test_targeted_command_starts_with_the_runner_wrapper_when_installed(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {WRAPPER: ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/services.py")

    # Assert
    assert lines(result.stdout, "command") == [
        f"command: {WRAPPER} uv run pytest -n auto --no-cov pkg/alpha/tests"
    ]


def repo_with_upstream_range(
    tmp_path: Path,
    base: dict[str, str],
    main_change: dict[str, str],
    branch_change: dict[str, str],
) -> None:
    """base -> main change -> branch change: the upstream range is HEAD~2..HEAD~1 and the
    branch's own diff is HEAD~1..HEAD."""
    write_tree(tmp_path, base)
    run_command(["git", "init"], tmp_path)
    commit_all(tmp_path, "base")
    write_tree(tmp_path, main_change)
    commit_all(tmp_path, "main change")
    write_tree(tmp_path, branch_change)
    commit_all(tmp_path, "branch change")


UPSTREAM = ("--upstream-range", "HEAD~2..HEAD~1")


def app_b_tree() -> dict[str, str]:
    """`alpha` plus `app_b`, which no app imports."""
    return alpha_app() | {
        "docs/app_structure.md": app_map("alpha", "app_b"),
        "pkg/app_b/__init__.py": "",
        "pkg/app_b/apps.py": apps_py("pkg.app_b", "AppBConfig"),
        "pkg/app_b/tests/__init__.py": "",
    }


def test_upstream_migration_in_an_unrelated_app_is_dropped(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"pkg/app_b/migrations/0002_x.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]
    assert lines(result.stdout, "why") == [
        "why: pkg/app_b/migrations/0002_x.py -> none "
        "(from main; app_b meets no branch app)"
    ]


def imported_app_tree() -> dict[str, str]:
    """`beta` (runtime) and `gamma` (test-only) import `alpha`."""
    return beta_gamma_apps()


def test_upstream_module_in_an_app_a_branch_app_imports_selects_its_tests(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert (
        "why: pkg/alpha/services.py -> pkg/alpha/tests (from main; owning app alpha)"
    ) in lines(result.stdout, "why")


def test_upstream_module_selects_the_importing_branch_app(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert (
        "why: pkg/alpha/services.py -> pkg/beta/tests "
        "(from main; beta has a runtime dep on alpha)"
    ) in lines(result.stdout, "why")


def test_upstream_module_skips_an_importer_that_is_not_a_branch_app(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests pkg/beta/tests"
    ]


def test_upstream_module_in_a_branch_app_selects_its_tests(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/beta/models.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/beta/models.py -> pkg/beta/tests (from main; owning app beta)"
    ]


@pytest.mark.parametrize(
    ("pyproject", "path"),
    [
        ("", ".python-version"),
        ("", "package.json"),
        ("", "package-lock.json"),
        ("", "uv.lock"),
        (
            '[tool.test_tiers]\ndependency_files = ["requirements/*.txt"]\n',
            "requirements/dev.txt",
        ),
    ],
)
def test_upstream_dependency_file_is_full(
    tmp_path: Path, pyproject: str, path: str
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree() | {"pyproject.toml": pyproject},
        {path: ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        f"why: {path} -> full (from main; dependency file)"
    ]


def test_upstream_docs_path_is_none(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"docs/guide.md": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: docs/guide.md -> none (from main; matches docs/**)"
    ]


def test_upstream_path_no_rule_knows_is_none(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"scripts/x.sh": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: scripts/x.sh -> none (from main; unmapped path)"
    ]


def test_path_both_sides_changed_is_a_branch_path(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/alpha/services.py": "x = 2\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)"
    ]


def uncommitted_upstream_path_repo(tmp_path: Path) -> None:
    """Main changed alpha's services; the checkout also has it modified, uncommitted."""
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    )
    write_tree(tmp_path, {"pkg/alpha/services.py": "x = 3\n"})


def test_uncommitted_path_main_also_changed_is_upstream_without_working_tree(
    tmp_path: Path,
) -> None:
    # Arrange
    uncommitted_upstream_path_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert (
        "why: pkg/alpha/services.py -> pkg/alpha/tests (from main; owning app alpha)"
    ) in lines(result.stdout, "why")


def test_uncommitted_path_main_also_changed_is_a_branch_path_with_working_tree(
    tmp_path: Path,
) -> None:
    # Arrange
    uncommitted_upstream_path_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM, "--working-tree")

    # Assert
    assert (
        "why: pkg/alpha/services.py -> pkg/alpha/tests (owning app alpha)"
    ) in lines(result.stdout, "why")


def test_upstream_change_in_a_runtime_dep_of_a_test_only_dependency_selects_it(
    tmp_path: Path,
) -> None:
    # Arrange
    chain = app_map("alpha", "beta", "gamma", "beta -.-> gamma", "gamma --> alpha")
    repo_with_upstream_range(
        tmp_path,
        beta_gamma_apps() | {"docs/app_structure.md": chain},
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert (
        "why: pkg/alpha/services.py -> pkg/alpha/tests (from main; owning app alpha)"
    ) in lines(result.stdout, "why")


def test_branch_apps_come_from_the_branchs_own_diff(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "--upstream-range", "HEAD~2..HEAD~1")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]


def test_upstream_app_path_without_an_app_map_is_full(tmp_path: Path) -> None:
    # Arrange
    base = alpha_app()
    del base["docs/app_structure.md"]
    repo_with_upstream_range(
        tmp_path,
        base,
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/alpha/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]


def test_upstream_range_given_twice_exits_2(tmp_path: Path) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM, "--upstream-range", "HEAD~1..HEAD")

    # Assert
    assert result.returncode == 2


@pytest.mark.parametrize("value", ["HEAD~2...HEAD", "HEAD~2..HEAD~1..HEAD"])
def test_upstream_range_that_is_not_a_single_range_exits_2(
    tmp_path: Path, value: str
) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "--upstream-range", value)

    # Assert
    assert result.returncode == 2


def test_upstream_test_file_in_a_related_app_is_selected(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/alpha/tests/test_extra.py": ""},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/tests/test_extra.py -> pkg/alpha/tests/test_extra.py "
        "(from main; changed test file)"
    ]


def test_upstream_test_file_in_an_app_outside_the_related_apps_is_none(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"pkg/app_b/tests/test_extra.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/app_b/tests/test_extra.py -> none (from main; app_b meets no branch app)"
    ]


def test_upstream_top_level_test_file_with_a_branch_path_under_the_tooling_entry_is_selected(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"tests/test_extra.py": ""},
        {"tests/helper.py": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert "why: tests/test_extra.py -> tests (from main; tooling)" in lines(
        result.stdout, "why"
    )


def test_upstream_migration_in_a_related_app_selects_the_tests_of_every_related_app(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/beta/migrations/0002_x.py": ""},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/beta/migrations/0002_x.py -> pkg/alpha/tests, pkg/beta/tests "
        "(from main; matches **/migrations/**)"
    ]


def test_upstream_migration_in_a_related_app_is_tier_targeted(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/beta/migrations/0002_x.py": ""},
        {"pkg/beta/views.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]


def test_upstream_migration_with_no_app_in_the_branch_diff_is_tier_none(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"pkg/app_b/migrations/0002_x.py": ""},
        {"docs/guide.md": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]


def test_upstream_root_conftest_with_no_app_in_the_branch_diff_selects_nothing(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"conftest.py": ""},
        {"docs/guide.md": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: conftest.py -> none (from main; matches **/conftest.py)"
    ]


@pytest.mark.parametrize(
    ("pyproject", "path"),
    [
        ("", "conftest.py"),
        (
            '[tool.test_tiers]\nescalation = ["scripts/**"]\n',
            "scripts/release.sh",
        ),
    ],
)
def test_upstream_escalation_path_with_no_owning_app_selects_the_tests_of_every_related_app(
    tmp_path: Path, pyproject: str, path: str
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree() | {"pyproject.toml": pyproject},
        {path: ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests"
    ]


def test_upstream_factories_in_an_app_outside_the_related_apps_is_none(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"pkg/app_b/factories.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/app_b/factories.py -> none (from main; app_b meets no branch app)"
    ]


def test_upstream_tooling_path_with_no_branch_path_under_its_entry_is_none(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"tests/helper.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: tests/helper.py -> none (from main; its tests meet no branch path)"
    ]


def test_upstream_tooling_path_with_a_branch_path_under_its_entry_selects_the_entrys_tests(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"tests/helper.py": ""},
        {"tests/other.py": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert "why: tests/helper.py -> tests (from main; tooling)" in lines(
        result.stdout, "why"
    )


def test_tests_changed_in_file_under_an_app_outside_the_related_apps_is_selected(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"pkg/app_b/tests/test_extra.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(
        SCRIPT, tmp_path, *UPSTREAM, "--tests-changed-in", "HEAD~2..HEAD~1"
    )

    # Assert
    assert (
        "why: pkg/app_b/tests/test_extra.py -> pkg/app_b/tests/test_extra.py "
        "(branch test file; runs only with a targeted tier)"
    ) in lines(result.stdout, "why")


def test_tests_changed_in_file_alone_leaves_the_tier_none(tmp_path: Path) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree(),
        {"pkg/app_b/tests/test_extra.py": ""},
        {"docs/guide.md": ""},
    )

    # Act
    result = run_script(
        SCRIPT, tmp_path, *UPSTREAM, "--tests-changed-in", "HEAD~2..HEAD~1"
    )

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]


def test_upstream_tooling_path_whose_tests_a_branch_path_under_another_entry_reaches_is_selected(
    tmp_path: Path,
) -> None:
    # Arrange
    pyproject = '[[tool.test_tiers.tooling]]\nglob = "plugins/*/scripts/**"\ntests = ["tests"]\n'
    repo_with_upstream_range(
        tmp_path,
        app_b_tree() | {"pyproject.toml": pyproject, "tests/__init__.py": ""},
        {"tests/helper.py": ""},
        {"plugins/x/scripts/run.py": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert "why: tests/helper.py -> tests (from main; tooling)" in lines(
        result.stdout, "why"
    )


def test_upstream_tooling_path_whose_tests_are_a_branch_apps_tests_is_selected(
    tmp_path: Path,
) -> None:
    # Arrange
    pyproject = '[[tool.test_tiers.tooling]]\nglob = "content/**"\ntests = ["pkg/alpha/tests"]\n'
    repo_with_upstream_range(
        tmp_path,
        app_b_tree() | {"pyproject.toml": pyproject},
        {"content/page.txt": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert "why: content/page.txt -> pkg/alpha/tests (from main; tooling)" in lines(
        result.stdout, "why"
    )


def test_upstream_tooling_path_whose_test_directory_holds_a_branch_tooling_test_file_is_selected(
    tmp_path: Path,
) -> None:
    # Arrange
    pyproject = (
        '[[tool.test_tiers.tooling]]\nglob = "prompts/**"\n'
        'tests = ["tests/test_prompts.py"]\n'
    )
    repo_with_upstream_range(
        tmp_path,
        app_b_tree() | {"pyproject.toml": pyproject, "tests/test_prompts.py": ""},
        {"tests/helper.py": ""},
        {"prompts/a.txt": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert "why: tests/helper.py -> tests (from main; tooling)" in lines(
        result.stdout, "why"
    )


def test_upstream_conftest_under_a_tooling_entry_selects_the_tests_a_branch_path_reaches(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree() | {"tests/__init__.py": ""},
        {"tests/conftest.py": ""},
        {"tests/helper.py": ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert "why: tests/conftest.py -> tests (from main; tooling)" in lines(
        result.stdout, "why"
    )


def test_upstream_module_in_an_app_that_imports_a_branch_app_selects_its_tests(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/beta/views.py": "x = 1\n"},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert (
        "why: pkg/beta/views.py -> pkg/beta/tests (from main; owning app beta)"
    ) in lines(result.stdout, "why")


def test_upstream_test_file_in_an_app_that_imports_a_branch_app_is_selected(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/gamma/tests/test_extra.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert (
        "why: pkg/gamma/tests/test_extra.py -> pkg/gamma/tests/test_extra.py "
        "(from main; changed test file)"
    ) in lines(result.stdout, "why")


def test_upstream_migration_in_an_app_that_imports_a_branch_app_selects_its_tests_too(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/beta/migrations/0002_x.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/beta/migrations/0002_x.py -> pkg/alpha/tests, pkg/beta/tests "
        "(from main; matches **/migrations/**)"
    ]


def test_upstream_module_in_a_branch_app_selects_every_importer(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        imported_app_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/alpha/other.py": "x = 1\n"},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    assert (
        "why: pkg/alpha/services.py -> pkg/gamma/tests "
        "(from main; gamma has a test-only dep on alpha)"
    ) in lines(result.stdout, "why")


TAIL = "(narrow; the rest is left to a full run)"


def narrow_import_repo(tmp_path: Path, extra: dict[str, str] | None = None) -> None:
    """A committed `alpha`/`beta`/`gamma` tree, narrowing on, where one `beta` test file
    imports `pkg.alpha.leaf` and `gamma` imports a different `alpha` module."""
    tree = beta_gamma_apps() | {
        "pyproject.toml": NARROW_TABLE,
        "pkg/alpha/leaf.py": "",
        "pkg/alpha/other.py": "",
        "pkg/alpha/views.py": "",
        "pkg/alpha/tests/test_leaf.py": "from pkg.alpha import leaf\n",
        "pkg/beta/tests/test_uses_leaf.py": "from pkg.alpha import leaf\n",
        "pkg/gamma/other.py": "import pkg.alpha.other\n",
        "pkg/gamma/tests/test_other.py": "import pkg.gamma.other\n",
    }
    git_repo(tmp_path, tree | (extra or {}))


def test_leaf_module_change_selects_its_app_and_the_test_files_importing_it(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert lines(result.stdout, "why") == [
        f"why: pkg/alpha/leaf.py -> pkg/alpha/tests (owning app alpha) {TAIL}",
        "why: pkg/alpha/leaf.py -> pkg/beta/tests/test_uses_leaf.py "
        f"(1 test files through imports) {TAIL}",
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov "
        "pkg/alpha/tests pkg/beta/tests/test_uses_leaf.py"
    ]


def test_module_nothing_imports_selects_only_its_app_and_says_none_reach_it(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/views.py")

    # Assert
    assert lines(result.stdout, "why")[1] == (
        f"why: pkg/alpha/views.py -> none (0 test files through imports) {TAIL}"
    )
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests"
    ]


def test_module_imported_through_a_helper_selects_the_test_file_importing_the_helper(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pkg/gamma/helpers.py": "from pkg.alpha import leaf\n",
            "pkg/gamma/tests/test_x.py": "import pkg.gamma.helpers\n",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/alpha/tests "
        "pkg/beta/tests/test_uses_leaf.py pkg/gamma/tests/test_x.py"
    ]


def test_change_to_a_module_a_sibling_app_does_not_reach_leaves_that_app_out(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert "pkg/gamma/tests" not in result.stdout
    assert "pkg/beta/tests " not in result.stdout


@pytest.mark.parametrize(
    ("changed", "browser_test_kept"),
    [("pkg/alpha/leaf.py", False), ("pkg/alpha/views.py", True)],
)
def test_browser_test_reached_by_import_is_kept_only_for_a_change_a_browser_sees(
    tmp_path: Path, changed: str, browser_test_kept: bool
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pkg/beta/tests/playwright/test_ui.py": (
                "import pkg.alpha.leaf\nimport pkg.alpha.views\n"
            )
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, changed)

    # Assert
    assert ("pkg/beta/tests/playwright/test_ui.py" in result.stdout) is (
        browser_test_kept
    )


def test_unrelated_path_never_builds_the_graph(tmp_path: Path) -> None:
    # Arrange
    narrow_import_repo(tmp_path, {"pkg/alpha/broken.py": "def (:\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/guide.md")

    # Assert
    assert result.returncode == 0
    assert "could not parse" not in result.stderr


def test_module_change_builds_the_graph_and_warns_about_a_file_that_does_not_parse(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(tmp_path, {"pkg/alpha/broken.py": "def (:\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert result.returncode == 0
    assert "could not parse pkg/alpha/broken.py" in result.stderr


def command_args(result: subprocess.CompletedProcess[str]) -> list[str]:
    return lines(result.stdout, "command")[0].split()


@pytest.mark.parametrize(
    "import_line",
    [
        "import pkg.alpha.leaf\n",
        "from pkg.alpha import leaf\n",
        "from pkg.alpha.leaf import thing\n",
    ],
)
def test_each_absolute_import_form_selects_the_importing_test_file(
    tmp_path: Path, import_line: str
) -> None:
    # Arrange
    narrow_import_repo(tmp_path, {"pkg/gamma/tests/test_form.py": import_line})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert "pkg/gamma/tests/test_form.py" in command_args(result)


@pytest.mark.parametrize(
    ("module_path", "source"),
    [
        ("pkg/alpha/sub/mod.py", "from ..leaf import thing\n"),
        ("pkg/alpha/sub/mod.py", "from .. import leaf\n"),
        ("pkg/alpha/sub/__init__.py", "from ..leaf import thing\n"),
        ("pkg/alpha/mod.py", "from . import leaf\n"),
        ("pkg/alpha/__init__.py", "from . import leaf\n"),
        ("pkg/alpha/mod.py", "from .leaf import thing\n"),
    ],
)
def test_relative_import_resolves_to_the_module_it_names(
    tmp_path: Path, module_path: str, source: str
) -> None:
    # Arrange
    imported = path_to_import(module_path)
    narrow_import_repo(
        tmp_path,
        {
            module_path: source,
            "pkg/gamma/tests/test_rel.py": f"import {imported}\n",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert "pkg/gamma/tests/test_rel.py" in command_args(result)


def path_to_import(module_path: str) -> str:
    """The dotted name a test file imports to reach `module_path`."""
    stem = module_path.removesuffix(".py").removesuffix("/__init__")
    return stem.replace("/", ".")


def test_package_init_change_selects_test_files_importing_a_submodule_of_it(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pkg/gamma/tests/test_dotted.py": "import pkg.alpha.leaf\n",
            "pkg/gamma/tests/test_from.py": "from pkg.alpha import leaf\n",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/__init__.py")

    # Assert
    args = command_args(result)
    assert "pkg/gamma/tests/test_dotted.py" in args
    assert "pkg/gamma/tests/test_from.py" in args


@pytest.mark.parametrize(
    "source",
    [
        "def load():\n    from pkg.alpha import leaf\n",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg.alpha import leaf\n",
    ],
)
def test_import_inside_a_function_or_type_checking_block_counts(
    tmp_path: Path, source: str
) -> None:
    # Arrange
    narrow_import_repo(tmp_path, {"pkg/gamma/tests/test_lazy.py": source})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert "pkg/gamma/tests/test_lazy.py" in command_args(result)


def test_module_imported_only_by_a_conftest_selects_the_test_files_below_it(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pkg/alpha/fixture_helper.py": "",
            "pkg/beta/tests/conftest.py": "import pkg.alpha.fixture_helper\n",
            "pkg/beta/tests/sub/test_below.py": "",
            "pkg/gamma/tests/test_elsewhere.py": "",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/fixture_helper.py")

    # Assert
    args = command_args(result)
    assert "pkg/beta/tests/sub/test_below.py" in args
    assert "pkg/beta/tests/test_uses_leaf.py" in args
    assert not any(arg.startswith("pkg/gamma/tests") for arg in args)


def test_module_deleted_in_a_range_still_selects_the_test_file_importing_it(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(tmp_path)
    run_command(["git", "rm", "--quiet", "pkg/alpha/leaf.py"], tmp_path)
    commit_all(tmp_path, "delete leaf")

    # Act
    result = run_script(SCRIPT, tmp_path, "--range", "HEAD~1..HEAD")

    # Assert
    assert result.returncode == 0
    assert "pkg/beta/tests/test_uses_leaf.py" in command_args(result)


def test_module_deleted_in_the_working_tree_only_still_selects_its_importers(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(tmp_path)
    (tmp_path / "pkg/alpha/leaf.py").unlink()

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree")

    # Assert
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert "pkg/beta/tests/test_uses_leaf.py" in command_args(result)


def test_relative_import_deeper_than_the_package_adds_no_name_and_raises_nothing(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(tmp_path, {"top.py": "from ... import x\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert result.returncode == 0
    assert result.stderr == ""


def test_module_outside_any_app_selects_only_the_test_files_importing_it(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pkg/testing_helpers.py": "",
            "pkg/beta/tests/test_a.py": "import pkg.testing_helpers\n",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/testing_helpers.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert lines(result.stdout, "why") == [
        "why: pkg/testing_helpers.py -> pkg/beta/tests/test_a.py "
        f"(1 test files through imports) {TAIL}",
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/beta/tests/test_a.py"
    ]


def test_module_outside_any_app_under_a_tooling_entry_selects_its_targets_and_importers(
    tmp_path: Path,
) -> None:
    # Arrange
    tooling = (
        f"{NARROW_TABLE}\n[[tool.test_tiers.tooling]]\n"
        'glob = "scripts/**"\ntests = ["tests/test_tooling.py"]\n'
    )
    narrow_import_repo(
        tmp_path,
        {
            "pyproject.toml": tooling,
            "scripts/tool.py": "",
            "tests/test_tooling.py": "",
            "pkg/beta/tests/test_uses_tool.py": "import scripts.tool\n",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "scripts/tool.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: scripts/tool.py -> pkg/beta/tests/test_uses_tool.py "
        f"(1 test files through imports) {TAIL}",
        f"why: scripts/tool.py -> tests/test_tooling.py (tooling) {TAIL}",
    ]
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov "
        "pkg/beta/tests/test_uses_tool.py tests/test_tooling.py"
    ]


TESTPATHS_TABLE = '[tool.pytest.ini_options]\ntestpaths = ["pkg"]\n'


@pytest.mark.parametrize(
    ("importer", "selected"),
    [("scripts/select_tests.py", False), ("pkg/contrib/test_conformance.py", True)],
)
def test_file_named_like_a_test_is_selected_by_import_only_inside_pytest_testpaths(
    tmp_path: Path, importer: str, selected: bool
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pyproject.toml": f"{NARROW_TABLE}{TESTPATHS_TABLE}",
            importer: "import pkg.alpha.leaf\n",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert (importer in command_args(result)) is selected


def test_test_file_deleted_in_the_working_tree_is_not_selected_through_its_conftest(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pkg/gamma/tests/conftest.py": "import pkg.alpha.leaf\n",
            "pkg/gamma/tests/test_old.py": "",
        },
    )
    (tmp_path / "pkg/gamma/tests/test_old.py").unlink()

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert "pkg/gamma/tests/test_old.py" not in command_args(result)


def test_browser_test_reaching_a_module_outside_any_app_is_left_out_for_a_non_ui_change(
    tmp_path: Path,
) -> None:
    # Arrange
    narrow_import_repo(
        tmp_path,
        {
            "pkg/testing_helpers.py": "",
            "pkg/beta/tests/test_a.py": "import pkg.testing_helpers\n",
            "pkg/beta/tests/playwright/test_ui.py": "import pkg.testing_helpers\n",
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/testing_helpers.py")

    # Assert
    assert lines(result.stdout, "command") == [
        "command: uv run pytest -n auto --no-cov pkg/beta/tests/test_a.py"
    ]


@pytest.mark.parametrize(
    ("path", "tracked", "reason"),
    [
        ("loose.py", True, "full (unmapped path)"),
        ("notes/readme.txt", True, "full (unmapped path)"),
        ("loose.py", False, "none (untracked and unmapped)"),
    ],
)
def test_path_outside_any_app_that_nothing_reaches_is_decided_as_unmapped(
    tmp_path: Path, path: str, tracked: bool, reason: str
) -> None:
    # Arrange
    narrow_import_repo(tmp_path, {path: ""} if tracked else None)
    if not tracked:
        write_tree(tmp_path, {path: ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "--working-tree", path)

    # Assert
    assert f"why: {path} -> {reason}" in lines(result.stdout, "why")


def narrow_chain_tree() -> dict[str, str]:
    return (
        chain_apps()
        | {"pyproject.toml": NARROW_TABLE}
        | {"pkg/alpha/tests/playwright/__init__.py": "", "pkg/alpha/leaf.py": ""}
    )


def test_app_template_selects_its_app_and_the_direct_importers_without_the_chain(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, narrow_chain_tree())

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/templates/alpha/x.html")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/templates/alpha/x.html -> pkg/alpha/tests "
        f"(owning app alpha; playwright: pkg/alpha/tests/playwright) {TAIL}",
        "why: pkg/alpha/templates/alpha/x.html -> pkg/beta/tests "
        f"(beta has a runtime dep on alpha) {TAIL}",
        "why: pkg/alpha/templates/alpha/x.html -> pkg/gamma/tests "
        f"(gamma has a test-only dep on alpha) {TAIL}",
    ]
    assert "pkg/delta/tests" not in result.stdout
    assert "pkg/epsilon/tests" not in result.stdout


def test_app_template_without_an_app_map_is_full_while_app_python_still_narrows(
    tmp_path: Path,
) -> None:
    # Arrange
    tree = narrow_chain_tree()
    del tree["docs/app_structure.md"]
    git_repo(tmp_path, tree)

    # Act
    template = run_script(SCRIPT, tmp_path, "pkg/alpha/templates/alpha/x.html")
    module = run_script(SCRIPT, tmp_path, "pkg/alpha/leaf.py")

    # Assert
    assert lines(template.stdout, "tier") == ["tier: full"]
    assert (
        "why: pkg/alpha/templates/alpha/x.html -> full (docs/app_structure.md missing)"
        in lines(template.stdout, "why")
    )
    assert lines(module.stdout, "tier") == ["tier: targeted"]


def escalation_repo(tmp_path: Path, extra: dict[str, str] | None = None) -> None:
    """A committed, narrowing `alpha`/`beta`/`gamma` tree with one test file importing each
    escalation-named `alpha` module, and a conftest at every level."""
    modules = ("factories", "signals", "middleware", "urls", "apps")
    tree = narrow_chain_tree() | {
        f"pkg/beta/tests/test_{name}.py": f"import pkg.alpha.{name}\n"
        for name in modules
        if name != "apps"
    }
    tree |= {
        "pkg/beta/tests/test_apps.py": "import pkg.alpha.apps\n",
        "pkg/alpha/factories.py": "",
        "pkg/alpha/signals.py": "",
        "pkg/alpha/middleware.py": "",
        "pkg/alpha/urls.py": "",
        "pkg/alpha/fixtures/data.json": "{}",
        "pkg/alpha/migrations/0002_x.py": "",
        "pkg/factories.py": "",
        "pkg/urls.py": "",
        "pkg/beta/tests/conftest.py": "",
        "pkg/beta/tests/sub/conftest.py": "",
        "pkg/conftest.py": "",
        "conftest.py": "",
        "tests/conftest.py": "",
        "tests/test_imports_pkg_factories.py": "import pkg.factories\n",
        "tests/test_imports_pkg_urls.py": "import pkg.urls\n",
    }
    git_repo(tmp_path, tree | (extra or {}))


def test_project_escalation_glob_on_a_builtin_glob_path_is_full(
    tmp_path: Path,
) -> None:
    # Arrange
    table = f'{NARROW_TABLE}escalation = ["pkg/alpha/urls.py"]\n'
    escalation_repo(tmp_path, {"pyproject.toml": table})

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/urls.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/urls.py -> full (matches pkg/alpha/urls.py)"
    ]


@pytest.mark.parametrize(
    ("path", "scope"),
    [
        ("pkg/beta/tests/conftest.py", "pkg/beta/tests"),
        ("pkg/beta/tests/sub/conftest.py", "pkg/beta/tests/sub"),
        ("tests/conftest.py", "tests"),
    ],
)
def test_conftest_inside_a_tests_directory_selects_its_own_subtree(
    tmp_path: Path, path: str, scope: str
) -> None:
    # Arrange
    escalation_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, path)

    # Assert
    assert lines(result.stdout, "why") == [
        f"why: {path} -> {scope} (conftest scope {scope}) {TAIL}"
    ]
    assert lines(result.stdout, "command") == [
        f"command: uv run pytest -n auto --no-cov {scope}"
    ]


@pytest.mark.parametrize("path", ["conftest.py", "pkg/conftest.py"])
def test_conftest_above_every_app_is_full(tmp_path: Path, path: str) -> None:
    # Arrange
    escalation_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, path)

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        f"why: {path} -> full (matches **/conftest.py)"
    ]


@pytest.mark.parametrize("name", ["factories", "signals", "middleware"])
def test_app_module_named_by_an_escalation_glob_selects_its_app_and_its_importers(
    tmp_path: Path, name: str
) -> None:
    # Arrange
    escalation_repo(tmp_path)
    path = f"pkg/alpha/{name}.py"

    # Act
    result = run_script(SCRIPT, tmp_path, path)

    # Assert
    assert lines(result.stdout, "why") == [
        f"why: {path} -> pkg/alpha/tests (owning app alpha) {TAIL}",
        f"why: {path} -> pkg/beta/tests/test_{name}.py "
        f"(1 test files through imports) {TAIL}",
    ]


def test_ownerless_escalation_named_module_follows_the_loose_module_rule(
    tmp_path: Path,
) -> None:
    # Arrange
    escalation_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/factories.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/factories.py -> tests/test_imports_pkg_factories.py "
        f"(1 test files through imports) {TAIL}"
    ]
    assert "runtime dep" not in result.stdout


def test_ownerless_urls_module_is_full_since_settings_load_it_by_name(
    tmp_path: Path,
) -> None:
    # Arrange
    escalation_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/urls.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        "why: pkg/urls.py -> full (matches **/urls.py)"
    ]


def test_conftest_whose_helper_another_app_imports_also_selects_that_test_file(
    tmp_path: Path,
) -> None:
    # Arrange
    escalation_repo(
        tmp_path,
        {
            "pkg/gamma/tests/test_uses_helper.py": (
                "from pkg.beta.tests.conftest import make_thing\n"
            )
        },
    )

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/beta/tests/conftest.py")

    # Assert
    assert lines(result.stdout, "why") == [
        "why: pkg/beta/tests/conftest.py -> pkg/beta/tests "
        f"(conftest scope pkg/beta/tests) {TAIL}",
        "why: pkg/beta/tests/conftest.py -> pkg/gamma/tests/test_uses_helper.py "
        f"(1 test files through imports) {TAIL}",
    ]


TEMPLATE_TAGS = "pkg/alpha/templatetags/alpha_tags.py"


def test_app_template_tag_module_selects_its_importers_and_one_app_hop(
    tmp_path: Path,
) -> None:
    # Arrange
    git_repo(
        tmp_path,
        narrow_chain_tree()
        | {"pkg/alpha/templatetags/__init__.py": "", TEMPLATE_TAGS: ""},
    )

    # Act
    result = run_script(SCRIPT, tmp_path, TEMPLATE_TAGS)

    # Assert
    assert lines(result.stdout, "why") == [
        f"why: {TEMPLATE_TAGS} -> pkg/alpha/tests (owning app alpha) {TAIL}",
        f"why: {TEMPLATE_TAGS} -> none (0 test files through imports) {TAIL}",
        f"why: {TEMPLATE_TAGS} -> pkg/beta/tests "
        f"(beta has a runtime dep on alpha) {TAIL}",
        f"why: {TEMPLATE_TAGS} -> pkg/gamma/tests "
        f"(gamma has a test-only dep on alpha) {TAIL}",
    ]


def test_app_template_tag_module_without_an_app_map_is_full(tmp_path: Path) -> None:
    # Arrange
    tree = narrow_chain_tree() | {TEMPLATE_TAGS: ""}
    del tree["docs/app_structure.md"]
    git_repo(tmp_path, tree)

    # Act
    result = run_script(SCRIPT, tmp_path, TEMPLATE_TAGS)

    # Assert
    assert lines(result.stdout, "why") == [
        f"why: {TEMPLATE_TAGS} -> full (docs/app_structure.md missing)"
    ]


def test_app_urls_and_apps_modules_select_their_importers_and_one_app_hop(
    tmp_path: Path,
) -> None:
    # Arrange
    escalation_repo(tmp_path)

    # Act
    results = {
        name: run_script(SCRIPT, tmp_path, f"pkg/alpha/{name}.py")
        for name in ("urls", "apps")
    }

    # Assert
    for name, result in results.items():
        path = f"pkg/alpha/{name}.py"
        assert lines(result.stdout, "why") == [
            f"why: {path} -> pkg/alpha/tests (owning app alpha) {TAIL}",
            f"why: {path} -> pkg/beta/tests/test_{name}.py "
            f"(1 test files through imports) {TAIL}",
            f"why: {path} -> pkg/beta/tests (beta has a runtime dep on alpha) {TAIL}",
            f"why: {path} -> pkg/gamma/tests "
            f"(gamma has a test-only dep on alpha) {TAIL}",
        ]
        assert "pkg/delta/tests" not in result.stdout


@pytest.mark.parametrize("name", ["urls", "apps"])
def test_app_urls_and_apps_modules_without_an_app_map_are_full(
    tmp_path: Path, name: str
) -> None:
    # Arrange
    tree = narrow_chain_tree()
    del tree["docs/app_structure.md"]
    git_repo(tmp_path, tree | {"pkg/alpha/urls.py": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, f"pkg/alpha/{name}.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        f"why: pkg/alpha/{name}.py -> full (docs/app_structure.md missing)"
    ]


def test_app_fixture_data_file_selects_its_app_and_one_app_hop(tmp_path: Path) -> None:
    # Arrange
    escalation_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/fixtures/data.json")

    # Assert
    assert lines(result.stdout, "why") == [
        f"why: pkg/alpha/fixtures/data.json -> pkg/alpha/tests (owning app alpha) {TAIL}",
        "why: pkg/alpha/fixtures/data.json -> pkg/beta/tests "
        f"(beta has a runtime dep on alpha) {TAIL}",
        "why: pkg/alpha/fixtures/data.json -> pkg/gamma/tests "
        f"(gamma has a test-only dep on alpha) {TAIL}",
    ]


def test_app_migration_is_full(tmp_path: Path) -> None:
    # Arrange
    escalation_repo(tmp_path)

    # Act
    result = run_script(SCRIPT, tmp_path, "pkg/alpha/migrations/0002_x.py")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: full"]
    assert lines(result.stdout, "why") == [
        "why: pkg/alpha/migrations/0002_x.py -> full (matches **/migrations/**)"
    ]


def upstream_scenario(
    base: dict[str, str], main_change: dict[str, str], branch_change: dict[str, str]
) -> Callable[[Path], None]:
    return partial(
        repo_with_upstream_range,
        base=base,
        main_change=main_change,
        branch_change=branch_change,
    )


UPSTREAM_SCENARIOS = {
    "unrelated app migration": upstream_scenario(
        app_b_tree(),
        {"pkg/app_b/migrations/0002_x.py": ""},
        {"pkg/alpha/services.py": "x = 1\n"},
    ),
    "module in an app a branch app imports": upstream_scenario(
        imported_app_tree(),
        {"pkg/alpha/services.py": "x = 1\n"},
        {"pkg/beta/views.py": "x = 1\n"},
    ),
    "module in an app outside the branch apps": upstream_scenario(
        app_b_tree(),
        {"pkg/app_b/services.py": "x = 1\n"},
        {"pkg/alpha/services.py": "x = 1\n"},
    ),
    "migration in a related app": upstream_scenario(
        imported_app_tree(),
        {"pkg/alpha/migrations/0002_x.py": ""},
        {"pkg/beta/views.py": "x = 1\n"},
    ),
    "docs path": upstream_scenario(
        app_b_tree(), {"docs/guide.md": ""}, {"pkg/alpha/services.py": "x = 1\n"}
    ),
    "uncommitted path main also changed": uncommitted_upstream_path_repo,
}


@pytest.mark.parametrize(
    "scenario", UPSTREAM_SCENARIOS.values(), ids=list(UPSTREAM_SCENARIOS)
)
def test_upstream_decisions_are_the_same_with_and_without_narrow(
    tmp_path: Path, scenario: Callable[[Path], None]
) -> None:
    # Arrange
    scenario(tmp_path)

    # Act
    without_narrow = run_script(SCRIPT, tmp_path, *UPSTREAM)
    write_tree(tmp_path, {"pyproject.toml": NARROW_TABLE})
    with_narrow = run_script(SCRIPT, tmp_path, *UPSTREAM)

    # Assert
    from_main = [
        line for line in lines(with_narrow.stdout, "why") if "from main;" in line
    ]
    assert from_main == [
        line for line in lines(without_narrow.stdout, "why") if "from main;" in line
    ]


def test_tests_changed_in_with_narrow_adds_the_test_files_without_raising_the_tier(
    tmp_path: Path,
) -> None:
    # Arrange
    repo_with_upstream_range(
        tmp_path,
        app_b_tree() | {"pyproject.toml": NARROW_TABLE},
        {"pkg/app_b/tests/test_extra.py": ""},
        {"docs/guide.md": ""},
    )

    # Act
    result = run_script(
        SCRIPT, tmp_path, *UPSTREAM, "--tests-changed-in", "HEAD~2..HEAD~1"
    )

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]


REMOTE_TABLE = '[tool.test_tiers.remote]\ncommand = "remote-runner --flag"\n'
MIGRATION_PATH = "pkg/alpha/migrations/0001_initial.py"


def remote_environment(**variables: str) -> dict[str, str]:
    """The process environment without `DS_TEST_REMOTE`, plus `variables`."""
    environment = {k: v for k, v in os.environ.items() if k != "DS_TEST_REMOTE"}
    return environment | variables


def test_full_tier_with_a_remote_command_prints_it_and_the_local_command_as_fallback(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": REMOTE_TABLE})

    # Act
    result = run_script(
        SCRIPT, tmp_path, MIGRATION_PATH, environment=remote_environment()
    )

    # Assert
    assert lines(result.stdout, "command") == ["command: remote-runner --flag"]
    assert lines(result.stdout, "fallback") == ["fallback: uv run pytest -n auto"]


def test_remote_off_prints_only_the_local_full_command(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": REMOTE_TABLE})

    # Act
    result = run_script(
        SCRIPT,
        tmp_path,
        MIGRATION_PATH,
        environment=remote_environment(DS_TEST_REMOTE="off"),
    )

    # Assert
    assert lines(result.stdout, "command") == [FULL_COMMAND]
    assert lines(result.stdout, "fallback") == []


def ds_config(switch: str) -> str:
    """A ds config file that sets the remote switch to `switch`."""
    return f"# ds\n\n## Other\n\n- Remote full run: on\n\n## Test Tiers\n\n- Remote full run: {switch}\n"


@pytest.mark.parametrize(
    ("files", "variables", "expect_remote"),
    [
        ({}, {}, True),
        ({".claude/ds/config.md": ds_config("off")}, {}, False),
        ({".claude/ds/config.md": ds_config("on")}, {}, True),
        ({".claude/ds/config.md": ds_config("")}, {}, True),
        (
            {
                ".claude/ds/config.md": ds_config("off"),
                ".claude/ds/config.local.md": ds_config("on"),
            },
            {},
            True,
        ),
        (
            {
                ".claude/ds/config.md": ds_config("on"),
                ".claude/ds/config.local.md": ds_config("off"),
            },
            {},
            False,
        ),
        (
            {
                ".claude/ds/config.md": ds_config("off"),
                ".claude/ds/config.local.md": ds_config(""),
            },
            {},
            False,
        ),
        ({".claude/ds/config.md": ds_config("off")}, {"DS_TEST_REMOTE": "on"}, True),
        ({".claude/ds/config.md": ds_config("on")}, {"DS_TEST_REMOTE": "off"}, False),
    ],
    ids=[
        "no-config",
        "config-off",
        "config-on",
        "config-blank",
        "local-on-wins",
        "local-off-wins",
        "local-blank-defers",
        "env-on-wins",
        "env-off-wins",
    ],
)
def test_remote_switch_chooses_between_remote_and_local_full_command(
    tmp_path: Path,
    files: dict[str, str],
    variables: dict[str, str],
    expect_remote: bool,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": REMOTE_TABLE} | files)

    # Act
    result = run_script(
        SCRIPT,
        tmp_path,
        MIGRATION_PATH,
        environment=remote_environment(**variables),
    )

    # Assert
    assert result.returncode == 0, result.stderr
    if expect_remote:
        assert lines(result.stdout, "command") == ["command: remote-runner --flag"]
        assert lines(result.stdout, "fallback") == ["fallback: uv run pytest -n auto"]
    else:
        assert lines(result.stdout, "command") == [FULL_COMMAND]
        assert lines(result.stdout, "fallback") == []


@pytest.mark.parametrize(
    ("files", "variables", "message"),
    [
        (
            {".claude/ds/config.md": ds_config("maybe")},
            {},
            "'Remote full run' under '## Test Tiers' in .claude/ds must be 'on' or 'off'",
        ),
        ({}, {"DS_TEST_REMOTE": "yes"}, "DS_TEST_REMOTE must be 'on' or 'off'"),
    ],
)
def test_unknown_remote_switch_value_exits_2_naming_the_setting(
    tmp_path: Path, files: dict[str, str], variables: dict[str, str], message: str
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": REMOTE_TABLE} | files)

    # Act
    result = run_script(
        SCRIPT, tmp_path, "docs/a.md", environment=remote_environment(**variables)
    )

    # Assert
    assert result.returncode == 2
    assert message in result.stderr


def test_targeted_tier_with_a_remote_command_prints_no_fallback(
    tmp_path: Path,
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": REMOTE_TABLE})

    # Act
    result = run_script(
        SCRIPT, tmp_path, "pkg/alpha/services.py", environment=remote_environment()
    )

    # Assert
    assert lines(result.stdout, "tier") == ["tier: targeted"]
    assert lines(result.stdout, "fallback") == []


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (
            "[tool.test_tiers]\nremote = 3\n",
            "[tool.test_tiers] 'remote' must be a table",
        ),
        (
            "[tool.test_tiers.remote]\ncommand = 3\n",
            "[tool.test_tiers.remote] 'command' must be a non-empty string",
        ),
        (
            '[tool.test_tiers.remote]\ncommand = "  "\n',
            "[tool.test_tiers.remote] 'command' must be a non-empty string",
        ),
    ],
)
def test_malformed_remote_entry_exits_2_naming_the_key(
    tmp_path: Path, table: str, message: str
) -> None:
    # Arrange
    write_tree(tmp_path, alpha_app() | {"pyproject.toml": table})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md", environment=remote_environment())

    # Assert
    assert result.returncode == 2
    assert message in result.stderr
