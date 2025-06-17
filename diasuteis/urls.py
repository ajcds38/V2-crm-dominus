from django.urls import path
from . import views

urlpatterns = [
    path('', views.configurar_dias_uteis, name='dias_uteis_configurar'),
    path('calcular/', views.calcular_dias_uteis_ajax, name='calcular_dias_uteis_ajax'),
]
