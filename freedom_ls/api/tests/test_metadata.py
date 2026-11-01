from rest_framework.views import APIView

from freedom_ls.api.metadata import ApiMetadata


class StubView(APIView):
    pass


def test_metadata_holds_only_the_view_name():
    metadata = ApiMetadata().determine_metadata(None, StubView())

    assert metadata == {"name": "Stub"}
