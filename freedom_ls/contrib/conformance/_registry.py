"""Downstream override registry for the conformance suite.

Lets a downstream project prune internal-tier probes it has customised while
keeping the app that owns them, without touching the contract-tier probes
other FLS code depends on.
"""

from __future__ import annotations

from django.apps import apps

_DROPPED: set[str] = set()


def drop(*probe_ids: str) -> None:
    """Prune internal-tier namespace probes a downstream has customised.

    Call from the downstream's conftest/test module before the run. Contract-tier
    ids cannot be pruned; the probe body enforces that.
    """
    _DROPPED.update(probe_ids)


def _is_dropped(probe_id: str) -> bool:
    return probe_id in _DROPPED


def _app_installed(app_label_dotted: str) -> bool:
    return apps.is_installed(app_label_dotted)
