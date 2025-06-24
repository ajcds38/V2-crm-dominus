from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import pandas as pd
import os
from django.conf import settings

@login_required(login_url='/login/')
def backlog_instalacoes(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')

    adesao_path = os.path.join(base_path, 'backlog_adesao.xlsx')
    ativacao_path = os.path.join(base_path, 'backlog_ativacao.xlsx')

    # Filtros da URL
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regional = request.GET.get('regional', '').strip().upper()
    coordenador = request.GET.get('coordenador', '').strip().upper()
    canal = request.GET.get('canal', '').strip().upper()
    cidade = request.GET.get('cidade', '').strip().upper()
    vendedor = request.GET.get('vendedor', '').strip().upper()

    df_adesao = pd.read_excel(adesao_path)
    df_ativacao = pd.read_excel(ativacao_path)

    for df in [df_adesao, df_ativacao]:
        df.columns = df.columns.str.strip().str.lower()
        for col in ['regional', 'coordenador', 'canal', 'cidade', 'vendedor', 'cliente']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.upper()
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')

    if data_inicio and data_fim:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim)
        df_adesao = df_adesao[(df_adesao['data'] >= data_inicio) & (df_adesao['data'] <= data_fim)]
        df_ativacao = df_ativacao[(df_ativacao['data'] >= data_inicio) & (df_ativacao['data'] <= data_fim)]

    for col, filtro in [('regional', regional), ('coordenador', coordenador), ('canal', canal), ('cidade', cidade), ('vendedor', vendedor)]:
        if filtro:
            df_adesao = df_adesao[df_adesao[col] == filtro]
            df_ativacao = df_ativacao[df_ativacao[col] == filtro]

    nomes_adesao = set(df_adesao['cliente'].unique())
    nomes_ativacao = set(df_ativacao['cliente'].unique())
    todos_nomes = sorted(nomes_adesao.union(nomes_ativacao))

    resultado = []
    for cliente in todos_nomes:
        resultado.append({
            'nome': cliente.title(),
            'adesao': '✅' if cliente in nomes_adesao else '❌',
            'ativacao': '✅' if cliente in nomes_ativacao else '❌',
        })

    context = {
        'clientes': resultado,
        'filtros': {
            'data_inicio': request.GET.get('data_inicio', ''),
            'data_fim': request.GET.get('data_fim', ''),
            'regional': regional,
            'coordenador': coordenador,
            'canal': canal,
            'cidade': cidade,
            'vendedor': vendedor,
        }
    }

    return render(request, 'backlog/index.html', context)
