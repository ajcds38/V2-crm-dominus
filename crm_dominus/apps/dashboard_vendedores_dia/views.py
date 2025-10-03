from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from django.shortcuts import render
import pandas as pd
import os
from datetime import datetime
from django.conf import settings

@cache_page(120)
@login_required(login_url='/')
def diarias_vendedor(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')
    caminho_arquivo_unificado = os.path.join(base_path, 'Atualizacao_CRM.xlsx')

    # ----- Filtros (iguais ao dashboard) -----
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regional = request.GET.get('regional', '').strip().lower()
    coordenador = request.GET.get('coordenador', '').strip().lower()
    canais = [c.strip().lower() for c in request.GET.getlist('canais') if c.strip()]

    hoje = datetime.today()
    if data_inicio:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim) if data_fim else (data_inicio + pd.DateOffset(months=1)).replace(day=24)
    else:
        # mesmo fallback do dashboard (exemplo)
        data_inicio = pd.to_datetime("2025-06-25")
        data_fim = pd.to_datetime("2025-07-24")
    if data_fim < data_inicio:
        data_inicio = data_fim - pd.DateOffset(months=1)

    # ----- Base e normalizações -----
    df_base = pd.read_excel(caminho_arquivo_unificado)
    df_base.columns = df_base.columns.str.strip().str.lower()

    for col in ['vendedores', 'cidade', 'regional', 'coordenador', 'canal']:
        if col in df_base.columns:
            df_base[col] = df_base[col].astype(str).str.strip().str.lower()

    # datas
    df = df_base.copy()
    df['data'] = pd.to_datetime(df.get('adesao'), dayfirst=True, errors='coerce')
    df = df[(df['data'] >= data_inicio) & (df['data'] <= data_fim)]
    df = df[df['data'].notna()]

    # listas dos selects
    regionais_disponiveis = sorted(df['regional'].dropna().str.title().unique())
    coordenadores_disponiveis = sorted(df['coordenador'].dropna().str.title().unique())
    canais_disponiveis = sorted(df['canal'].dropna().str.title().unique())

    # filtros selecionados
    if regional:
        df = df[df['regional'] == regional]
    if coordenador:
        df = df[df['coordenador'] == coordenador]
    if canais:
        df = df[df['canal'].isin(canais)]

    # tratar volume (cada linha = 1 venda se não houver volume)
    if 'volume' in df.columns:
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        usa_volume = True
    else:
        usa_volume = False

    # ----- Pivot: vendedores x dia -----
    colunas_dias = pd.date_range(start=data_inicio, end=data_fim).strftime('%d/%m').tolist()
    df_tabela = pd.DataFrame(columns=colunas_dias)

    if not df.empty:
        df['data_formatada'] = df['data'].dt.strftime('%d/%m')
        if usa_volume:
            tabela_dia = df.groupby(['vendedores', 'data_formatada'])['volume'].sum().unstack(fill_value=0)
        else:
            tabela_dia = df.groupby(['vendedores', 'data_formatada']).size().unstack(fill_value=0)

        tabela_dia = tabela_dia.reindex(columns=colunas_dias, fill_value=0)
        df_tabela = tabela_dia.sort_index()
        df_tabela.index = df_tabela.index.str.upper()

    if df_tabela.shape[1] > 0:
        df_tabela.loc['Total Realizado'] = df_tabela.sum(axis=0)

    context = {
        # 🔧 Corrigido: garantir que a coluna do nome saia como "vendedor"
        'tabela': df_tabela.reset_index().rename(columns={'vendedores': 'vendedor'}).to_dict(orient='records'),
        'colunas_dias': colunas_dias,
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'canais_disponiveis': canais_disponiveis,
        'canais_selecionados': request.GET.getlist('canais'),
        'regionais': regionais_disponiveis,
        'regionais_selecionadas': [regional] if regional else [],
        'coordenadores': coordenadores_disponiveis,
        'coordenadores_selecionadas': [coordenador] if coordenador else [],
    }
    # Renderiza o template na pasta correta
    return render(request, 'dashboard_vendedores_dia/index.html', context)
