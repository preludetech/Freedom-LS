"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path


from ninja import NinjaAPI

api = NinjaAPI()

api.add_router("xapi/", "xapi_learning_record_store.api.router") 

urlpatterns = [
    path("admin/", admin.site.urls),
    path('api/', api.urls),
    # path("api/xapi/", include("xapi_learning_record_store.api_urls")),
    # path("api/", api.urls),

    path("__reload__/", include("django_browser_reload.urls")),
    path("content/", include("content_engine.urls")),
    path("", include("student_interface.urls")),

]
