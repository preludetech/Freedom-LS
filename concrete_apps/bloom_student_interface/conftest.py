import pytest
from datetime import date, timedelta
from bloom_student_interface.models import Child


@pytest.fixture
def child(user, mock_site_context):
    """Create a test child."""
    dob = date.today() - timedelta(days=365 * 4)
    return Child.objects.create(
        user=user, name="Test Child", date_of_birth=dob, gender="female"
    )
