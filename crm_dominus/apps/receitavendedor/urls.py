from django.urls import path
from .views import receita_por_vendedor

urlpatterns = [
    path('', receita_por_vendedor, name='receita_vendedor'),
]
