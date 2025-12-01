from config.urls import urlpatterns
from django.urls import include, path

urlpatterns = [path("", include("bloom_student_interface.urls"))] + urlpatterns
