"""Namespace and reference URL probes.

Verifies that the downstream project's URLconf actually wires up the routes
FLS depends on, and that it replicates FLS's reference sitemap/robots wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from django.urls import reverse

from ._registry import _app_installed, _is_dropped

__all__ = ["test_fls_namespace_reverses", "test_reference_url_reverses"]


@dataclass(frozen=True)
class _Probe:
    app: str
    viewname: str
    contract: bool
    kwargs: dict[str, str] = field(default_factory=dict)


FLS_NAMESPACE_PROBES: list[_Probe] = [
    _Probe("freedom_ls.student_interface", "student_interface:dashboard", True),
    _Probe(
        "freedom_ls.student_interface",
        "student_interface:course_detail",
        True,
        {"course_slug": "x"},
    ),
    _Probe(
        "freedom_ls.student_interface",
        "student_interface:course_home",
        True,
        {"course_slug": "x"},
    ),
    _Probe(
        "freedom_ls.student_interface",
        "student_interface:initiate_course_access",
        True,
        {"course_slug": "x"},
    ),
    _Probe("freedom_ls.student_interface", "student_interface:courses", False),
    _Probe(
        "freedom_ls.course_applications",
        "course_applications:apply",
        True,
        {"course_slug": "x"},
    ),
    _Probe(
        "freedom_ls.course_applications",
        "course_applications:status",
        True,
        {"pk": "00000000-0000-0000-0000-000000000000"},
    ),
    _Probe(
        "freedom_ls.course_interest",
        "course_interest:express_interest",
        True,
        {"course_slug": "x"},
    ),
    _Probe(
        "freedom_ls.educator_interface",
        "educator_interface:interface",
        True,
        {"path_string": ""},
    ),
    _Probe("freedom_ls.accounts", "accounts:account_profile", True),
    _Probe(
        "freedom_ls.accounts",
        "accounts:legal_doc",
        True,
        {"doc_type": "terms"},
    ),
]

REFERENCE_URL_NAMES: list[str] = ["sitemap", "robots_txt"]


@pytest.mark.parametrize(
    "probe",
    FLS_NAMESPACE_PROBES,
    ids=[p.viewname for p in FLS_NAMESPACE_PROBES],
)
def test_fls_namespace_reverses(probe: _Probe) -> None:
    if not _app_installed(probe.app):
        pytest.skip(f"{probe.app} not installed")
    if not probe.contract and _is_dropped(probe.viewname):
        pytest.skip(f"{probe.viewname} dropped by downstream")
    reverse(probe.viewname, kwargs=probe.kwargs or None)


@pytest.mark.parametrize("name", REFERENCE_URL_NAMES, ids=REFERENCE_URL_NAMES)
def test_reference_url_reverses(name: str) -> None:
    reverse(name)
