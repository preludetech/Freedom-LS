"""The shipped file scanner is a no-op, so a production deployment that never
configures a real one leaves every uploaded file pending until a superuser marks
it by hand. The check is what tells the operator that before an applicant hits it.
"""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.form_engine.checks import check_file_scan_backend_configured


@override_settings(DEBUG=False)
def test_the_shipped_no_op_scanner_warns_in_production():
    warnings = check_file_scan_backend_configured(None)

    assert [warning.id for warning in warnings] == ["freedom_ls_form_engine.W001"]


@override_settings(DEBUG=True)
def test_the_shipped_no_op_scanner_is_fine_in_development():
    assert check_file_scan_backend_configured(None) == []


@override_settings(DEBUG=False, FILE_SCAN_BACKEND="myproject.scanning.ClamAVScanner")
def test_a_configured_scanner_raises_nothing_in_production():
    assert check_file_scan_backend_configured(None) == []
