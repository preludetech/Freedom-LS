from django.urls import path
from . import views

app_name = 'content_engine'

urlpatterns = [
    path('topics/<uuid:pk>/', views.topic_detail, name='topic_detail'),
    path('forms/<uuid:pk>/', views.form_detail, name='form_detail'),
    path('form-pages/<uuid:pk>/', views.form_page_detail, name='form_page_detail'),
]
