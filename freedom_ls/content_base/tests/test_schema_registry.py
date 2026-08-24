"""Guards the content-type schema registry against silent gaps.

If nothing ever imports a consumer app's `schema.py` module before this runs,
that app's content types register no schema — no error, no warning, just
content validation quietly treating `.yaml` files declaring them as
unrecognised. This test iterates the enum, so it adds no dependency on either
consumer app.
"""

from freedom_ls.content_base.schema import SCHEMAS, ContentType


def test_every_content_type_has_a_registered_schema() -> None:
    assert set(ContentType) == set(SCHEMAS)
