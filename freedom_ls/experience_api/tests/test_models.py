"""Phase 0 / Phase 1 / Phase 4 smoke tests for the experience_api app.

Phase 0 covers: the ready()-time task-backend guard, verb immutability.
Phase 1 covers: immutability rules (see test_immutability.py — separate file).
Phase 4 covers: maintain_event_partitions no-op.
Phase 7 covers: skill / resource doc existence.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from django.core.exceptions import ImproperlyConfigured

from freedom_ls.experience_api.apps import ExperienceApiConfig
from freedom_ls.experience_api.verbs import VIEWED


def test_verbs_are_immutable() -> None:
    """Verb instances are frozen dataclasses — attempting to mutate raises."""
    with pytest.raises(FrozenInstanceError):
        VIEWED.iri = "changed"


def _run_ready_check(settings, monkeypatch, *, backend: str, ack: bool) -> None:
    """Helper: simulate the app's ready()-time task backend check."""
    monkeypatch.setattr(
        settings, "TASKS", {"default": {"BACKEND": backend}}, raising=False
    )
    monkeypatch.setattr(
        settings,
        "EXPERIENCE_API_QUEUED_BACKEND_OBSERVABILITY_OK",
        ack,
        raising=False,
    )
    cfg = ExperienceApiConfig.create("freedom_ls.experience_api")
    cfg._check_task_backend()


def test_app_config_ready_raises_when_queued_backend_not_acknowledged(
    settings, monkeypatch
) -> None:
    with pytest.raises(ImproperlyConfigured):
        _run_ready_check(
            settings,
            monkeypatch,
            backend="django.tasks.backends.database.DatabaseBackend",
            ack=False,
        )


def test_app_config_ready_passes_with_flag(settings, monkeypatch) -> None:
    _run_ready_check(
        settings,
        monkeypatch,
        backend="django.tasks.backends.database.DatabaseBackend",
        ack=True,
    )


def test_app_config_ready_passes_with_immediate_backend(settings, monkeypatch) -> None:
    _run_ready_check(
        settings,
        monkeypatch,
        backend="django.tasks.backends.immediate.ImmediateBackend",
        ack=False,
    )


# -----------------------------------------------------------------------------
# Phase 7 — skill / resource doc existence tests.
PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "fls-claude-plugin"


def test_experience_api_skill_exists_and_parses() -> None:
    skill_path = PLUGIN_ROOT / "skills" / "experience-api" / "SKILL.md"
    assert skill_path.exists(), f"Expected {skill_path} to exist"
    text = skill_path.read_text(encoding="utf-8")
    # Frontmatter must be present and parseable as YAML.
    assert text.startswith("---\n"), "Expected YAML frontmatter block"
    end = text.find("\n---\n", 4)
    assert end != -1, "Expected closing frontmatter delimiter"
    import yaml

    meta = yaml.safe_load(text[4:end])
    assert "name" in meta
    assert "description" in meta
    assert "allowed-tools" in meta


def test_experience_api_resource_exists() -> None:
    resource = PLUGIN_ROOT / "resources" / "experience_api.md"
    assert resource.exists()
    assert resource.stat().st_size > 0


# -----------------------------------------------------------------------------
# Phase 4 — maintain_event_partitions smoke.
@pytest.mark.django_db
def test_maintain_event_partitions_no_op_on_unpartitioned_table(caplog) -> None:
    import io

    from django.core.management import call_command

    out = io.StringIO()
    call_command("maintain_event_partitions", stdout=out)
    # Either the log or the stdout carries "not partitioned".
    output = out.getvalue() + "\n".join(r.getMessage() for r in caplog.records)
    assert "not partitioned" in output.lower()
