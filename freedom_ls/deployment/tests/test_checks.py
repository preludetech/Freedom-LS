from __future__ import annotations

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.deployment.checks import check_sentry_release_set_when_dsn_set


def test_check_is_registered_via_app_ready() -> None:
    # Guards against DeploymentAppConfig.ready() dropping the checks import: the
    # direct-call tests below would stay green even if the check were never
    # registered and so never ran on manage.py check / migrate.
    assert check_sentry_release_set_when_dsn_set in registry.registry.registered_checks


@override_settings(
    SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0", SENTRY_RELEASE=None
)
def test_dsn_set_and_release_unset_returns_one_warning() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert len(warnings) == 1
    assert warnings[0].id == "freedom_ls_deployment.W001"


@override_settings(
    SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0", SENTRY_RELEASE=""
)
def test_dsn_set_and_release_empty_string_returns_one_warning() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert len(warnings) == 1
    assert warnings[0].id == "freedom_ls_deployment.W001"


@override_settings(
    SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0",
    SENTRY_RELEASE="fls@1.2.3",
)
def test_dsn_set_and_release_set_returns_no_warnings() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert warnings == []


@override_settings(SENTRY_DSN=None, SENTRY_RELEASE=None)
def test_dsn_unset_and_release_unset_returns_no_warnings() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert warnings == []


@override_settings(SENTRY_DSN=None, SENTRY_RELEASE="fls@1.2.3")
def test_dsn_unset_and_release_set_returns_no_warnings() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert warnings == []
