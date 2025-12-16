from freedom_ls.site_aware_models.models import _thread_locals


class CurrentSiteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        response = self.get_response(request)
        if hasattr(_thread_locals, 'request'):
            delattr(_thread_locals, 'request')
        return response
