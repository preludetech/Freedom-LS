from freedom_ls.icons.semantic_names import SEMANTIC_ICON_NAMES


def test_semantic_icon_names_is_non_empty_set_of_strings() -> None:
    assert isinstance(SEMANTIC_ICON_NAMES, set)
    assert len(SEMANTIC_ICON_NAMES) > 0
    for name in SEMANTIC_ICON_NAMES:
        assert isinstance(name, str)


def test_semantic_icon_names_contains_expected_names() -> None:
    expected = {"success", "next", "home"}
    assert expected.issubset(SEMANTIC_ICON_NAMES)
