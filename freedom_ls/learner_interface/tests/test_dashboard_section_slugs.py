"""The dashboard's built-in section slugs are the ones the validator reserves."""

from freedom_ls.content_engine.schema import RESERVED_SECTION_SLUGS
from freedom_ls.learner_interface.dashboard_sections import BuiltInSection


def test_built_in_sections_are_exactly_the_reserved_category_slugs():
    assert {section.value for section in BuiltInSection} == set(RESERVED_SECTION_SLUGS)
