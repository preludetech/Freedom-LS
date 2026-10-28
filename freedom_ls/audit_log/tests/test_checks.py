from django.test import override_settings

from freedom_ls.audit_log.checks import check_extra_audit_actions


def test_a_code_that_is_already_an_fls_code_produces_e001():
    with override_settings(AUDIT_LOG_EXTRA_ACTIONS={"cohort.created": "Mine"}):
        errors = check_extra_audit_actions(None)

    assert [error.id for error in errors] == ["freedom_ls_audit_log.E001"]


def test_a_malformed_code_produces_e001():
    with override_settings(AUDIT_LOG_EXTRA_ACTIONS={"Invoice-Sent": "Sent"}):
        errors = check_extra_audit_actions(None)

    assert [error.id for error in errors] == ["freedom_ls_audit_log.E001"]


def test_a_code_with_a_trailing_newline_produces_e001():
    """`$` would match before the newline and let a code through that no
    caller's string ever equals."""
    with override_settings(AUDIT_LOG_EXTRA_ACTIONS={"invoice.sent\n": "Sent"}):
        errors = check_extra_audit_actions(None)

    assert [error.id for error in errors] == ["freedom_ls_audit_log.E001"]


def test_a_clean_setting_produces_no_error():
    with override_settings(AUDIT_LOG_EXTRA_ACTIONS={"invoice.sent": "Invoice sent"}):
        errors = check_extra_audit_actions(None)

    assert errors == []
