from rest_framework.metadata import BaseMetadata
from rest_framework.request import Request
from rest_framework.views import APIView


class ApiMetadata(BaseMetadata):
    def determine_metadata(self, request: Request, view: APIView) -> dict[str, str]:
        return {"name": view.get_view_name()}
