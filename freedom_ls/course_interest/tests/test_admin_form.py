"""Regression test for CourseInterestAdminForm.

SiteAwareModelAdmin excludes ``site`` from every admin form, and
UniqueConstraint.validate() abandons a constraint whose field sits in that
exclusion set. CourseInterestAdminForm un-excludes ``site`` so a duplicate
interest surfaces as a form error instead of an IntegrityError.
"""

from __future__ import annotations

import pytest

from django.core.exceptions import NON_FIELD_ERRORS

from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.forms import CourseInterestAdminForm


@pytest.mark.django_db
def test_course_interest_admin_form_rejects_duplicate_user_course_pair(
    mock_site_context,
):
    interest = CourseInterestFactory()

    form = CourseInterestAdminForm(
        data={"user": interest.user_id, "course": interest.course_id}
    )

    assert form.is_valid() is False
    assert NON_FIELD_ERRORS in form.errors
