from django.urls import path
from . import views

urlpatterns = [
    path('', views.cancelamento, name='cancelamento_index'),
]
