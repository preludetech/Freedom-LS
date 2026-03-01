import pytest

from freedom_ls.content_engine.factories import FormFactory


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


@pytest.mark.django_db
@pytest.mark.parametrize("self_path,other_path,result", test_data)
def test_all(self_path, other_path, result, mock_site_context):
    form = FormFactory(title="Test Form")
    form.file_path = self_path
    form.save()

    expected = form.calculate_path_from_root(other_path)
    assert expected == result
