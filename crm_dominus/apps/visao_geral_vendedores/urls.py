from django.urls import path
from .views import visao_geral_vendedores

app_name = 'visao_geral_vendedores'

urlpatterns = [
    path('', visao_geral_vendedores, name='index'),
]
