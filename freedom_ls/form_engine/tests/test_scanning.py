"""FLS ships no malware scanner. The default backend has to be inert and leave a
file pending, so nothing downstream mistakes an unscanned file for a cleared one.
"""

from __future__ import annotations

import pytest

from freedom_ls.form_engine.factories import QuestionAnswerFileFactory
from freedom_ls.form_engine.models import ScanStatus
from freedom_ls.form_engine.scanning import NoOpScanner, get_file_scanner


def test_the_default_scanner_is_the_no_op_one():
    assert isinstance(get_file_scanner(), NoOpScanner)


@pytest.mark.django_db
def test_the_no_op_scanner_leaves_a_file_pending(mock_site_context):
    answer_file = QuestionAnswerFileFactory()

    NoOpScanner().scan(answer_file)

    answer_file.refresh_from_db()
    assert answer_file.scan_status == ScanStatus.PENDING
