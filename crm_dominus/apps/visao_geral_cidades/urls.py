from django.urls import path
from .views import visao_geral_cidades

app_name = 'visao_geral_cidades'

urlpatterns = [
    path('', visao_geral_cidades, name='index'),
]
