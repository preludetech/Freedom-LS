import pytest
from django.utils import timezone
from django.test import RequestFactory
from content_engine.models import Form
from student_progress.models import FormProgress
from bloom_student_interface.models import Child, ChildFormProgress
from bloom_student_interface.views import children


@pytest.fixture
def picky_eating_form(mock_site_context):
    """Create the picky eating form."""
    return Form.objects.create(slug="picky-eating", title="Picky Eating Assessment")


@pytest.mark.parametrize("site", ["Bloom"], indirect=True)
@pytest.mark.django_db
class TestChildrenView:
    """Test the children view with assessment buttons."""

    def test_no_assessment(self, user, mock_site_context, picky_eating_form):
        """Test that a child with no assessment shows 'Start Assessment' button."""
        # Create a child
        Child.objects.create(user=user, name="Test Child", age=5)

        # Create a request and call the view directly
        factory = RequestFactory()
        request = factory.get("/children")
        request.user = user

        response = children(request)

        assert response.status_code == 200
        assert "Start Assessment" in response.content.decode()

    def test_incomplete_assessment(self, user, mock_site_context, picky_eating_form):
        """Test that a child with incomplete assessment shows 'Continue Assessment' button."""
        # Create a child
        child = Child.objects.create(user=user, name="Test Child", age=5)

        # Create incomplete form progress
        form_progress = FormProgress.objects.create(user=user, form=picky_eating_form)
        ChildFormProgress.objects.create(form_progress=form_progress, child=child)

        # Create a request and call the view directly
        factory = RequestFactory()
        request = factory.get("/children")
        request.user = user

        response = children(request)

        assert response.status_code == 200
        assert "Continue Assessment" in response.content.decode()

    def test_complete_assessment(self, user, mock_site_context, picky_eating_form):
        """Test that a child with complete assessment shows 'View Assessment Results' button."""
        # Create a child
        child = Child.objects.create(user=user, name="Test Child", age=5)

        # Create complete form progress
        form_progress = FormProgress.objects.create(
            user=user,
            form=picky_eating_form,
            completed_time=timezone.now()
        )
        ChildFormProgress.objects.create(form_progress=form_progress, child=child)

        # Create a request and call the view directly
        factory = RequestFactory()
        request = factory.get("/children")
        request.user = user

        response = children(request)

        assert response.status_code == 200
        assert "View Assessment Results" in response.content.decode()
        assert "Retake Assessment" in response.content.decode()
