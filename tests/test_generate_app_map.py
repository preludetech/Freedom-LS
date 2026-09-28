"""Tests for `claude_plugins/django-stack/scripts/generate_app_map.py`.

The script's directory is hyphenated and not importable, and `mypy` skips
`claude_plugins/`, so these tests run it as a subprocess against a throwaway
`tmp_path` project: a `pyproject.toml` plus a namespace package (`pkg/`, no
`__init__.py`) holding `pkg/users`, `pkg/alpha` and `pkg/beta`, each with its own
`apps.py`.
"""

from __future__ import annotations

import tomllib
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


def declared_edges_toml(from_app: str, to_app: str, reason: str = "some reason") -> str:
    return f'[[edge]]\nfrom = "{from_app}"\nto = "{to_app}"\nreason = "{reason}"\n'


def test_declared_edge_appears_as_runtime_edge(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "test_organisation/declared_edges.toml": declared_edges_toml("beta", "alpha"),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    doc = (tmp_path / "docs" / "app_structure.md").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "beta --> alpha" in doc


def test_declared_edge_with_unknown_from_app_fails_with_error_naming_it(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "test_organisation/declared_edges.toml": declared_edges_toml(
            "nonexistent", "alpha"
        ),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "nonexistent" in result.stderr


def test_declared_edge_with_unknown_to_app_fails_with_error_naming_it(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "test_organisation/declared_edges.toml": declared_edges_toml(
            "beta", "nonexistent"
        ),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "nonexistent" in result.stderr


def test_declared_edge_with_no_reason_fails(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "test_organisation/declared_edges.toml": '[[edge]]\nfrom = "beta"\nto = "alpha"\n',
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "reason" in result.stderr


def test_declared_edge_matching_an_existing_import_fails(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/beta/services.py": "from pkg.alpha import views\n",
        "test_organisation/declared_edges.toml": declared_edges_toml("beta", "alpha"),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1
    assert "beta" in result.stderr
    assert "alpha" in result.stderr


def test_declared_edge_matching_an_existing_string_label_relation_fails(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config(
            "pkg.alpha", "AlphaConfig", label="custom_alpha_label"
        ),
        "pkg/beta/models.py": alpha_fk_field("custom_alpha_label"),
        "test_organisation/declared_edges.toml": declared_edges_toml("beta", "alpha"),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1


def test_declared_edge_matching_an_existing_user_model_relation_fails(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/models.py": get_user_model_call(),
        "test_organisation/declared_edges.toml": declared_edges_toml("alpha", "users"),
    }
    write_tree(tmp_path, files)

    result = run_script(SCRIPT, tmp_path)

    assert result.returncode == 1


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


def test_check_on_freshly_generated_tree_exits_0(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": unconfigured_pyproject(),
        **base_apps(),
    }
    write_tree(tmp_path, files)
    run_script(SCRIPT, tmp_path)

    result = run_script(SCRIPT, tmp_path, "--check")

    assert result.returncode == 0


def test_check_after_new_runtime_edge_exits_1_names_doc_and_leaves_it_unchanged(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": unconfigured_pyproject(),
        **base_apps(),
    }
    write_tree(tmp_path, files)
    run_script(SCRIPT, tmp_path)
    doc_path = tmp_path / "docs" / "app_structure.md"
    before = doc_path.read_bytes()
    write_tree(tmp_path, {"pkg/beta/services.py": "from pkg.users import views\n"})

    result = run_script(SCRIPT, tmp_path, "--check")

    assert result.returncode == 1
    assert "docs/app_structure.md" in result.stderr
    assert "run /ds:app_map" in result.stderr
    assert doc_path.read_bytes() == before


def test_check_from_repo_root_exits_0() -> None:
    result = run_script(SCRIPT, REPO_ROOT, "--check")

    assert result.returncode == 0


def contract_for(tmp_path: Path, app_id: str) -> dict[str, object] | None:
    """The `[[tool.importlinter.contracts]]` entry with the given `id`, if any."""
    path = tmp_path / "test_organisation" / "import_contracts.toml"
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    tool = document["tool"]
    assert isinstance(tool, dict)
    importlinter = tool["importlinter"]
    assert isinstance(importlinter, dict)
    for contract in importlinter.get("contracts", []):
        assert isinstance(contract, dict)
        if contract.get("id") == app_id:
            return contract
    return None


def contract_list(contract: dict[str, object], key: str) -> list[str]:
    value = contract[key]
    assert isinstance(value, list)
    return [str(item) for item in value]


def alpha_with_test_modules() -> dict[str, str]:
    return {
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/services.py": "from pkg.beta import views\n",
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_services.py": "",
        "pkg/alpha/factories.py": "",
        "pkg/alpha/conftest.py": "",
        "pkg/alpha/test_root.py": "",
    }


def test_contract_source_modules_include_tests_package_factories_conftest_and_root_test_file(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        **alpha_with_test_modules(),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    contract = contract_for(tmp_path, "alpha")
    assert contract is not None
    assert sorted(contract_list(contract, "source_modules")) == [
        "pkg.alpha.conftest",
        "pkg.alpha.factories",
        "pkg.alpha.test_root",
        "pkg.alpha.tests",
    ]


def test_contract_forbidden_modules_exclude_app_and_runtime_deps_and_allow_indirect_imports_is_true(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        **alpha_with_test_modules(),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    contract = contract_for(tmp_path, "alpha")
    assert contract is not None
    assert contract_list(contract, "forbidden_modules") == ["pkg.users"]
    assert contract["allow_indirect_imports"] is True


def test_app_with_no_test_modules_gets_no_contract(tmp_path: Path) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    assert contract_for(tmp_path, "beta") is None


def test_app_whose_runtime_deps_cover_every_other_app_gets_no_contract(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/services.py": (
            "from pkg.beta import views\nfrom pkg.users import views\n"
        ),
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_services.py": "",
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    assert contract_for(tmp_path, "alpha") is None


def test_allowance_line_appears_for_test_module_importing_user_model_factories(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/users/factories.py": "",
        "pkg/beta/tests/__init__.py": "",
        "pkg/beta/tests/test_models.py": "from pkg.users import factories\n",
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    contract = contract_for(tmp_path, "beta")
    assert contract is not None
    assert "pkg.beta.tests.test_models -> pkg.users.factories" in contract_list(
        contract, "ignore_imports"
    )


def test_no_allowance_line_for_test_module_not_importing_user_model_factories(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/users/factories.py": "",
        "pkg/beta/tests/__init__.py": "",
        "pkg/beta/tests/test_models.py": "from django.db import models\n",
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    contract = contract_for(tmp_path, "beta")
    assert contract is not None
    assert "ignore_imports" not in contract


def test_module_import_and_symbol_import_of_user_model_factories_produce_same_allowance_line(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/users/factories.py": "class UserFactory:\n    pass\n",
        "pkg/beta/tests/__init__.py": "",
        "pkg/beta/tests/test_a.py": "from pkg.users import factories\n",
        "pkg/beta/tests/test_b.py": "from pkg.users.factories import UserFactory\n",
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    contract = contract_for(tmp_path, "beta")
    assert contract is not None
    ignore_imports = contract_list(contract, "ignore_imports")
    assert "pkg.beta.tests.test_a -> pkg.users.factories" in ignore_imports
    assert "pkg.beta.tests.test_b -> pkg.users.factories" in ignore_imports


def test_app_with_runtime_dep_on_user_model_app_gets_no_allowance_lines(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/users/factories.py": "",
        "pkg/beta/services.py": "from pkg.users import views\n",
        "pkg/beta/tests/__init__.py": "",
        "pkg/beta/tests/test_models.py": "from pkg.users import factories\n",
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    contract = contract_for(tmp_path, "beta")
    assert contract is not None
    assert "ignore_imports" not in contract


def test_check_exits_1_and_names_contracts_file_when_only_contracts_would_change(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": configured_pyproject(),
        **base_apps(),
        "pkg/alpha/__init__.py": "",
        "pkg/alpha/apps.py": app_config("pkg.alpha", "AlphaConfig"),
        "pkg/alpha/tests/__init__.py": "",
        "pkg/alpha/tests/test_models.py": "",
    }
    write_tree(tmp_path, files)
    run_script(SCRIPT, tmp_path)
    doc_path = tmp_path / "docs" / "app_structure.md"
    doc_before = doc_path.read_bytes()
    write_tree(tmp_path, {"pkg/alpha/test_extra.py": ""})

    result = run_script(SCRIPT, tmp_path, "--check")

    assert result.returncode == 1
    assert "import_contracts.toml" in result.stderr
    assert doc_path.read_bytes() == doc_before


def test_without_test_organisation_table_no_contracts_file_written(
    tmp_path: Path,
) -> None:
    files = {
        "pyproject.toml": unconfigured_pyproject(),
        **base_apps(),
    }
    write_tree(tmp_path, files)

    run_script(SCRIPT, tmp_path)

    assert not (tmp_path / "test_organisation" / "import_contracts.toml").exists()
