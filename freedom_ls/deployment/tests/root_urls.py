"""Root URL configuration for the deployment tests that reverse its URLs.

Wraps freedom_ls.deployment.urls behind include() so its app_name is registered
as a namespace, and so the tests do not depend on a project's root URLconf
mounting it.
"""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("", include("freedom_ls.deployment.urls")),
]
