from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(
    exc: Exception, context: dict[str, object]
) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, ErrorDetail):
        # Field-keyed 400 bodies have no "detail" and keep DRF's shape.
        response.data = {"detail": str(detail), "code": detail.code}
    return response
