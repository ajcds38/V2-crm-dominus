from django.urls import path
from . import views

urlpatterns = [
    path('', views.ativacao, name='ativacao_index'),
    path('vendedor/', views.ativacao_vendedor, name='ativacao_vendedor'),
]
