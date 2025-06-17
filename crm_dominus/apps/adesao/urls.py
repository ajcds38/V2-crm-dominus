from django.urls import path
from . import views
from .views_dashboard import dashboard_diaadia

urlpatterns = [
    path('cidade/', views.adesao, name='adesao'),
    path('vendedor/', views.adesao_vendedor, name='adesao_vendedor'),
    path('dashboard/diaadia/', dashboard_diaadia, name='dashboard_diaadia'),
]
