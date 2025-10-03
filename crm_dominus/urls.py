from django.shortcuts import redirect
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from crm_dominus.apps.adesao.views_dashboard import dashboard_diaadia
from crm_dominus.apps.saldocidades.views import saldo_cidades
from backlog.views import backlog_instalacoes  # ✅ Nova importação
from crm_dominus.apps.produtividade.produtividade_vendedor import produtividade_vendedor  # ✅ Caminho corrigido

urlpatterns = [
    path('', lambda request: redirect('login/')),
    path('admin/', admin.site.urls),

    # 🔐 Autenticação
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # 📊 Apps principais
    path('adesao/', include('crm_dominus.apps.adesao.urls')),
    path('ativacao/', include('crm_dominus.apps.ativacao.urls')),
    path('cancelamento/', include('crm_dominus.apps.cancelamento.urls')),
    path('metas/', include('crm_dominus.apps.metas.urls')),
    path('diasuteis/', include('diasuteis.urls')),

    # 📈 Dashboards e Resultados
    path('dashboard/diaadia/', dashboard_diaadia, name='dashboard_diaadia'),
    path('saldo/', saldo_cidades, name='saldo_cidades'),
    path('backlog/', backlog_instalacoes, name='backlog_instalacoes'),
    path('receita-vendedor/', include('crm_dominus.apps.receitavendedor.urls')),
    path('produtividade-vendedor/', produtividade_vendedor, name='produtividade_vendedor'),

    # ✅ Rotas modulares de visões gerais
    path('visao-geral-cidades/', include('crm_dominus.apps.visao_geral_cidades.urls')),
    path('visao-geral-vendedores/', include('crm_dominus.apps.visao_geral_vendedores.urls')),

    # ✅ Nova rota para a aba "Diárias" (vendedores dia a dia)
    path('diarias/', include('crm_dominus.apps.dashboard_vendedores_dia.urls')),
]
