"""Tests for `claude_plugins/django-stack/scripts/check_test_mirroring.py`.

The script's directory is hyphenated and not importable, and `mypy` skips
`claude_plugins/`, so these tests run it as a subprocess against a throwaway
`tmp_path` project: a `pyproject.toml` plus a namespace package (`pkg/`, no
`__init__.py`) holding one or more apps, each with its own `apps.py`.
"""

from __future__ import annotations

from pathlib import Path

from tests._script_trees import run_script, write_tree

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "claude_plugins"
    / "django-stack"
    / "scripts"
    / "check_test_mirroring.py"
)


def configured_pyproject() -> str:
    return (
        "[tool.test_organisation]\n"
        'user_model_app = "pkg.alpha"\n'
        'declared_edges = "test_organisation/declared_edges.toml"\n'
        'import_contracts = "test_organisation/import_contracts.toml"\n'
        'import_baseline = "test_organisation/import_baseline.txt"\n'
        'mirroring_baseline = "test_organisation/mirroring_baseline.txt"\n'
        'mirroring_exemptions = "test_organisation/mirroring_exemptions.txt"\n'
    )


def apps_py(dotted_name: str, class_name: str) -> str:
    return (
        "from django.apps import AppConfig\n\n\n"
        f"class {class_name}(AppConfig):\n"
        f'    name = "{dotted_name}"\n'
    )


def one_app() -> dict[str, str]:
    return {
        "pyproject.toml": configured_pyproject(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": apps_py("pkg.alpha", "AlphaConfig"),
    }


def test_flat_test_file_next_to_its_module_passes(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/models.py": "",
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_models.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_nested_test_file_next_to_its_subpackage_module_passes(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/templatetags/__init__.py": "",
        "pkg/alpha/templatetags/x.py": "",
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/templatetags/__init__.py": "",
        "pkg/alpha/tests/templatetags/test_x.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_test_file_next_to_a_package_target_passes(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/models/__init__.py": "",
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_models.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_flat_templatetag_test_fails_naming_expected_module(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/templatetags/__init__.py": "",
        "pkg/alpha/templatetags/x.py": "",
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_x.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/tests/test_x.py" in result.stderr
    assert "pkg/alpha/x.py" in result.stderr


def test_behaviour_named_test_file_fails_naming_expected_module(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_dashboard_ordering.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/tests/test_dashboard_ordering.py" in result.stderr
    assert "pkg/alpha/dashboard_ordering.py" in result.stderr


def test_underscore_tests_suffix_file_fails_naming_expected_path(
    tmp_path: Path,
) -> None:
    files = one_app() | {
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/foo_tests.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/tests/foo_tests.py" in result.stderr
    assert "pkg/alpha/tests/test_foo.py" in result.stderr


def test_app_level_tests_module_fails_naming_placeholder_path(tmp_path: Path) -> None:
    files = one_app() | {"pkg/alpha/tests.py": ""}
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/tests.py" in result.stderr
    assert "pkg/alpha/tests/test_<module>.py" in result.stderr


def test_colocated_test_file_fails_naming_expected_tests_package_path(
    tmp_path: Path,
) -> None:
    files = one_app() | {
        "pkg/alpha/sub/__init__.py": "",
        "pkg/alpha/sub/x.py": "",
        "pkg/alpha/sub/test_x.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/sub/test_x.py" in result.stderr
    assert "pkg/alpha/tests/sub/test_x.py" in result.stderr


def test_playwright_test_file_is_ignored(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/playwright/__init__.py": "",
        "pkg/alpha/tests/playwright/test_flow.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_helper_modules_are_never_violations(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/conftest.py": "",
        "pkg/alpha/tests/factories.py": "",
        "pkg/alpha/tests/_helpers.py": "",
        "pkg/alpha/tests/stub_panels.py": "",
        "pkg/alpha/tests/root_urls.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_test_file_outside_any_app_is_ignored(tmp_path: Path) -> None:
    files = one_app() | {"tests/test_something.py": ""}
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_violation_covered_by_baseline_passes(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_dashboard_ordering.py": "",
        "test_organisation/mirroring_baseline.txt": (
            "# alpha\npkg/alpha/tests/test_dashboard_ordering.py\n"
        ),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_baseline_line_whose_file_is_gone_fails_as_stale(tmp_path: Path) -> None:
    files = one_app() | {
        "test_organisation/mirroring_baseline.txt": (
            "# alpha\npkg/alpha/tests/test_dashboard_ordering.py\n"
        ),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/tests/test_dashboard_ordering.py" in result.stderr


def test_baseline_line_whose_file_now_conforms_fails_as_stale(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/models.py": "",
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_models.py": "",
        "test_organisation/mirroring_baseline.txt": (
            "# alpha\npkg/alpha/tests/test_models.py\n"
        ),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/tests/test_models.py" in result.stderr


def test_print_violations_output_written_as_baseline_makes_check_pass(
    tmp_path: Path,
) -> None:
    files = one_app() | {
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_dashboard_ordering.py": "",
    }
    write_tree(tmp_path, files)
    printed = run_script(SCRIPT, tmp_path, "--print-violations")
    write_tree(tmp_path, {"test_organisation/mirroring_baseline.txt": printed.stdout})

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_print_violations_writes_no_files(tmp_path: Path) -> None:
    files = one_app() | {
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_dashboard_ordering.py": "",
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path, "--print-violations")

    assert not (tmp_path / "test_organisation").exists()


def two_apps_each_with_a_violation() -> dict[str, str]:
    return {
        "pyproject.toml": configured_pyproject(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": apps_py("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_dashboard_ordering.py": "",
        "pkg/beta/__init__.py": "",
        "pkg/beta/apps.py": apps_py("pkg.beta", "BetaConfig"),
        "pkg/beta/tests/__init__.py": "",
        "pkg/beta/tests/foo_tests.py": "",
        "test_organisation/mirroring_baseline.txt": (
            "# alpha\n"
            "pkg/alpha/tests/test_dashboard_ordering.py\n"
            "\n"
            "# beta\n"
            "pkg/beta/tests/foo_tests.py\n"
        ),
    }


def test_deleting_one_apps_baseline_lines_fails_with_only_that_apps_files(
    tmp_path: Path,
) -> None:
    write_tree(tmp_path, two_apps_each_with_a_violation())
    write_tree(
        tmp_path,
        {
            "test_organisation/mirroring_baseline.txt": (
                "# beta\npkg/beta/tests/foo_tests.py\n"
            )
        },
    )

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg/alpha/tests/test_dashboard_ordering.py" in result.stderr
    assert "pkg/beta/tests/foo_tests.py" not in result.stderr


def test_unconfigured_project_exits_zero(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": '[project]\nname = "pkg"\n',
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": apps_py("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_dashboard_ordering.py": "",
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 0


def test_check_passes_on_live_tree() -> None:
    result = run_script(SCRIPT, REPO_ROOT)

    assert result.returncode == 0
