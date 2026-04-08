import json
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


class FeedbackMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # Only act on HTMX requests
        if request.headers.get("HX-Request") == "true":
            pending = request.session.get("pending_feedback")
            if pending:
                # Merge with any existing HX-Trigger header
                existing = response.get("HX-Trigger", "")
                if existing:
                    try:
                        triggers = json.loads(existing)
                    except (json.JSONDecodeError, TypeError):
                        triggers = {existing: None}
                else:
                    triggers = {}
                triggers["show-feedback-modal"] = pending
                response["HX-Trigger"] = json.dumps(triggers)

        return response
