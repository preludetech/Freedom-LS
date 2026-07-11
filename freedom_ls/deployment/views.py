from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse


@staff_member_required
def trigger_error(request: HttpRequest) -> HttpResponse:
    _ = 1 / 0  # deliberate ZeroDivisionError to verify Sentry capture
    return HttpResponse()  # unreachable
