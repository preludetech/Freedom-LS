from django.utils.module_loading import autodiscover_modules

from .routers import router

app_name = "api"

# Each app's api.py registers its viewsets when imported; discovering them by
# name keeps this app free of an import of any endpoint app.
autodiscover_modules("api")

urlpatterns = [*router.urls]
