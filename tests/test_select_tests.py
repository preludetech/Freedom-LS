"""Tests for `claude_plugins/django-stack/scripts/select_tests.py`.

The script's directory is hyphenated and not importable, and it finds its siblings through
`sys.path[0]`, so these tests run it as a subprocess against a throwaway `tmp_path` project:
a `pyproject.toml` plus a namespace package (`pkg/`, no `__init__.py`) holding apps.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._script_trees import run_command, run_script, write_tree

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / "select_tests.py"

FULL_COMMAND = "command: uv run pytest -n auto"


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


def test_generic_lists_apply_without_a_pyproject_file(tmp_path: Path) -> None:
    # Arrange
    write_tree(tmp_path, {"docs/a.md": ""})

    # Act
    result = run_script(SCRIPT, tmp_path, "docs/a.md")

    # Assert
    assert lines(result.stdout, "tier") == ["tier: none"]


@pytest.mark.parametrize("key", ["none", "escalation"])
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
@pytest.mark.parametrize("option", ["--range", "--tests-changed-in"])
def test_range_value_that_is_not_a_plain_revision_range_exits_2(
    tmp_path: Path, option: str, value: str
) -> None:
    # Arrange
    repo_with_two_commits(tmp_path, {"pkg/alpha/services.py": "x = 1\n"})

    # Act
    result = run_script(SCRIPT, tmp_path, option, value)

    # Assert
    assert result.returncode == 2
