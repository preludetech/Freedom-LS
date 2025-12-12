import pytest
from content_engine.models import Form


test_data = [
    (
        "tutorial/02-understanding-the-graph-commits-and-checkout.md",
        "images/graph1.drawio.svg",
        "tutorial/images/graph1.drawio.svg",
    ),
    (
        "functionality_demo_course/3. quiz/1. page.yaml",
        "../images/graph1.drawio.svg",
        "functionality_demo_course/images/graph1.drawio.svg",
    ),
]


@pytest.fixture
def form(site):
    """Create a test form."""
    return Form.objects.create(
        site=site, title="Test Form", strategy="CATEGORY_VALUE_SUM"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("self_path,other_path,result", test_data)
def test_all(self_path, other_path, result, form):
    form.file_path = self_path
    form.save()

    expected = form.calculate_path_from_root(other_path)
    assert expected == result
