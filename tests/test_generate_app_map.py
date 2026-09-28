"""Tests for `claude_plugins/django-stack/scripts/generate_app_map.py`.

The script's directory is hyphenated and not importable, and `mypy` skips
`claude_plugins/`, so these tests run it as a subprocess against a throwaway
`tmp_path` project: a `pyproject.toml` plus a namespace package (`pkg/`, no
`__init__.py`) holding `pkg/users`, `pkg/alpha` and `pkg/beta`, each with its own
`apps.py`.
"""

from __future__ import annotations

from pathlib import Path

from tests._script_trees import run_script, write_tree

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT / "claude_plugins" / "django-stack" / "scripts" / "generate_app_map.py"
)


def configured_pyproject() -> str:
    return (
        "[tool.test_organisation]\n"
        'user_model_app = "pkg.users"\n'
        'declared_edges = "test_organisation/declared_edges.toml"\n'
        'import_contracts = "test_organisation/import_contracts.toml"\n'
        'import_baseline = "test_organisation/import_baseline.txt"\n'
        'mirroring_baseline = "test_organisation/mirroring_baseline.txt"\n'
        'mirroring_exemptions = "test_organisation/mirroring_exemptions.txt"\n'
    )


def unconfigured_pyproject() -> str:
    return '[project]\nname = "pkg"\n'


def app_config(dotted_name: str, class_name: str, label: str | None = None) -> str:
    label_line = f'    label = "{label}"\n' if label else ""
    return (
        "from django.apps import AppConfig\n\n\n"
        f"class {class_name}(AppConfig):\n"
        f'    name = "{dotted_name}"\n' + label_line
    )


def base_apps() -> dict[str, str]:
    return {
        "pkg/users/__init__.py": "",
        "pkg/users/apps.py": app_config("pkg.users", "UsersConfig"),
        "pkg/beta/__init__.py": "",
        "pkg/beta/apps.py": app_config("pkg.beta", "BetaConfig"),
    }


def alpha_fk_field(label: str) -> str:
    return (
        "from django.db import models\n\n\n"
        "class Thing(models.Model):\n"
        "    alpha_thing = models.ForeignKey(\n"
        f'        "{label}.Something", on_delete=models.CASCADE\n'
        "    )\n"
    )


def test_string_label_fk_to_app_label_adds_runtime_edge(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config(
            "pkg.alpha", "AlphaConfig", label="custom_alpha_label"
        ),
        "pkg/beta/models.py": alpha_fk_field("custom_alpha_label"),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "beta --> alpha" in doc


def test_string_label_fk_with_no_dot_adds_no_edge(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config(
            "pkg.alpha", "AlphaConfig", label="custom_alpha_label"
        ),
        "pkg/beta/models.py": (
            "from django.db import models\n\n\n"
            "class Thing(models.Model):\n"
            '    other_thing = models.ForeignKey("Something", on_delete=models.CASCADE)\n'
        ),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert "beta --> alpha" not in doc


def test_string_label_fk_in_test_module_adds_no_runtime_edge(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config(
            "pkg.alpha", "AlphaConfig", label="custom_alpha_label"
        ),
        "pkg/beta/tests/__init__.py": "",
        "pkg/beta/tests/test_models.py": alpha_fk_field("custom_alpha_label"),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert "beta --> alpha" not in doc


def test_missing_app_config_label_falls_back_to_module_last_segment(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/beta/models.py": alpha_fk_field("alpha"),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert "beta --> alpha" in doc


def test_project_rooted_under_test_named_directory_classifies_runtime_modules_as_runtime(
    tmp_path: Path,
) -> None:
    project = tmp_path / "test_project"
    project.mkdir()
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/services.py": "from pkg.beta import views\n",
    }
    write_tree(project, files)

    run_script(SCRIPT, project)

    doc = (project / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert "alpha --> beta" in doc


def user_model_fk_field() -> str:
    return (
        "from django.conf import settings\n"
        "from django.db import models\n\n\n"
        "class Thing(models.Model):\n"
        "    owner = models.ForeignKey(\n"
        "        settings.AUTH_USER_MODEL, on_delete=models.CASCADE\n"
        "    )\n"
    )


def get_user_model_call() -> str:
    return "from django.contrib.auth import get_user_model\n\nUser = get_user_model()\n"


def test_auth_user_model_relation_adds_edge_to_user_model_app(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/models.py": user_model_fk_field(),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "alpha --> users" in doc


def test_get_user_model_call_adds_edge_to_user_model_app(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/models.py": get_user_model_call(),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert "alpha --> users" in doc


def test_user_model_apps_own_get_user_model_call_adds_no_self_edge(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/users/forms.py": get_user_model_call(),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert "users --> users" not in doc


def test_unknown_user_model_app_fails_with_error_naming_it(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": (
            "[tool.test_organisation]\n"
            'user_model_app = "pkg.nonexistent"\n'
            'declared_edges = "test_organisation/declared_edges.toml"\n'
            'import_contracts = "test_organisation/import_contracts.toml"\n'
            'import_baseline = "test_organisation/import_baseline.txt"\n'
            'mirroring_baseline = "test_organisation/mirroring_baseline.txt"\n'
            'mirroring_exemptions = "test_organisation/mirroring_exemptions.txt"\n'
        ),
        **base_apps(),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "pkg.nonexistent" in result.stderr


def test_without_test_organisation_table_string_label_fk_adds_no_edge_and_header_is_unchanged(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": unconfigured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config(
            "pkg.alpha", "AlphaConfig", label="custom_alpha_label"
        ),
        "pkg/beta/models.py": alpha_fk_field("custom_alpha_label"),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert "beta --> alpha" not in doc
    assert (
        "- **Solid arrows** — runtime imports "
        "(one app imports from another outside of tests)."
    ) in doc
    assert "- `A --> B` — `A` imports from `B` at runtime." in doc
