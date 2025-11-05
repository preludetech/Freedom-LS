import pytest

test_data = [
    (
        "tutorial/02-understanding-the-graph-commits-and-checkout.md",
        "images/graph1.drawio.svg",
        "tutorial/images/graph1.drawio.svg",
    )
]


@pytest.mark.django_db
@pytest.mark.parametrize("self_path,other_path,result", test_data)
def test_all(self_path, other_path, result, form):
    form.file_path = self_path
    form.save()

    expected = form.calculate_path_from_root(other_path)
    assert expected == result
