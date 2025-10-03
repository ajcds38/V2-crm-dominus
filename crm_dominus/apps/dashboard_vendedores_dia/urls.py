from django.urls import path
from .views import diarias_vendedor

app_name = 'dashboard_vendedores_dia'

urlpatterns = [
    path('', diarias_vendedor, name='index'),
]
