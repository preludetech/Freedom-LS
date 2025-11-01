from django.urls import path
from . import views

app_name = 'content_engine'

urlpatterns = [
    path('topics/<uuid:pk>/', views.topic_detail, name='topic_detail'),
]
