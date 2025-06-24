from django.shortcuts import redirect
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from crm_dominus.apps.adesao.views_dashboard import dashboard_diaadia
from crm_dominus.apps.saldocidades.views import saldo_cidades
from backlog.views import backlog_instalacoes  # ✅ Nova importação

urlpatterns = [
    path('', lambda request: redirect('login/')),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('adesao/', include('crm_dominus.apps.adesao.urls')),
    path('ativacao/', include('crm_dominus.apps.ativacao.urls')),
    path('cancelamento/', include('crm_dominus.apps.cancelamento.urls')),
    path('metas/', include('crm_dominus.apps.metas.urls')),
    path('diasuteis/', include('diasuteis.urls')),
    path('dashboard/diaadia/', dashboard_diaadia, name='dashboard_diaadia'),
    path('saldo/', saldo_cidades, name='saldo_cidades'),
    
    # ✅ Nova rota para Backlog de Instalações
    path('backlog/', backlog_instalacoes, name='backlog_instalacoes'),
]
