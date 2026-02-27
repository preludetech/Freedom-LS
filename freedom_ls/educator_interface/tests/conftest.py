import pytest
from django.test import RequestFactory
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.student_management.factories import (
    CohortMembershipFactory,
    StudentFactory,
)
from freedom_ls.student_management.models import Cohort, Student


@pytest.fixture
def request_factory(mock_site_context):
    """Create a request factory."""
    return RequestFactory()


def make_student(mock_site_context, email: str, cohort: Cohort) -> Student:
    """Create a student with a user and cohort membership."""
    student = StudentFactory(user=UserFactory(email=email))
    CohortMembershipFactory(student=student, cohort=cohort)
    return student
