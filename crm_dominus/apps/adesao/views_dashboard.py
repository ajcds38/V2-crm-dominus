from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import pandas as pd
import os
from datetime import datetime, timedelta
from django.conf import settings
from diasuteis.models import DiasUteis
from functools import lru_cache

@lru_cache()
def get_df_real():
    caminho = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'adesao_realizado.xlsx')
    return pd.read_excel(caminho)

@lru_cache()
def get_df_meta():
    caminho = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'metas_adesao.xlsx')
    return pd.read_excel(caminho)

@login_required(login_url='/')
def dashboard_diaadia(request):
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regional = request.GET.get('regional', '').strip().lower()
    coordenador = request.GET.get('coordenador', '').strip().lower()
    canais = [c.strip().lower() for c in request.GET.getlist('canais')]

    df_real = get_df_real()
    df_meta = get_df_meta()

    df_real.columns = df_real.columns.str.strip().str.lower()
    df_meta.columns = df_meta.columns.str.strip().str.lower()
    df_real = df_real.loc[:, ~df_real.columns.str.contains('^unnamed')]
    df_real['data'] = pd.to_datetime(df_real['data'], dayfirst=True, errors='coerce')
    df_real = df_real[df_real['data'].notna()]
    df_real['volume'] = pd.to_numeric(df_real['volume'], errors='coerce').fillna(0)

    for col in ['cidade', 'regional', 'coordenador', 'canal']:
        if col in df_real.columns:
            df_real[col] = df_real[col].astype(str).str.strip().str.lower().str.replace('\xa0', ' ')
        if col in df_meta.columns:
            df_meta[col] = df_meta[col].astype(str).str.strip().str.lower().str.replace('\xa0', ' ')

    if data_inicio:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim) if data_fim else (data_inicio + pd.DateOffset(months=1)).replace(day=24)
    else:
        hoje = datetime.today()
        if hoje.day < 25:
            data_inicio = (hoje.replace(day=1) - timedelta(days=1)).replace(day=25)
            data_fim = hoje.replace(day=24)
        else:
            data_inicio = hoje.replace(day=25)
            proximo_mes = (hoje.replace(day=28) + timedelta(days=4)).replace(day=1)
            data_fim = proximo_mes.replace(day=24)

    if data_fim < data_inicio:
        data_inicio = data_fim - pd.DateOffset(months=1)

    df_real = df_real[(df_real['data'] >= data_inicio) & (df_real['data'] <= data_fim)]

    if regional:
        df_real = df_real[df_real['regional'] == regional]
        df_meta = df_meta[df_meta['regional'] == regional]
    if coordenador:
        df_real = df_real[df_real['coordenador'] == coordenador]
        df_meta = df_meta[df_meta['coordenador'] == coordenador]
    if canais:
        df_real = df_real[df_real['canal'].isin(canais)]
        df_meta = df_meta[df_meta['canal'].isin(canais)]

    dias_row = DiasUteis.objects.filter(data_inicio=data_inicio, data_fim=data_fim).first()
    feriados = dias_row.feriados.split(',') if dias_row and dias_row.feriados else []
    incluir_feriados = dias_row.incluir_feriados if dias_row else False
    ignorar_domingos = dias_row.ignorar_domingos if dias_row else True

    total_dias = (data_fim - data_inicio).days + 1
    dias_uteis_lista = [
        (data_inicio + timedelta(days=i)).strftime('%d/%m')
        for i in range(total_dias)
        if (not ignorar_domingos or (data_inicio + timedelta(days=i)).weekday() != 6)
        and (incluir_feriados or (data_inicio + timedelta(days=i)).strftime('%d/%m/%Y') not in feriados)
    ]

    todas_datas = pd.date_range(start=data_inicio, end=data_fim).date
    colunas_dias = [data.strftime('%d/%m') for data in todas_datas]
    df_tabela = pd.DataFrame(index=[], columns=colunas_dias)

    if not df_real.empty:
        df_temp = df_real.groupby(['canal', df_real['data'].dt.strftime('%d/%m')])['volume'].sum().unstack(fill_value=0)
        df_temp = df_temp.reindex(columns=colunas_dias, fill_value=0)
        df_tabela = df_temp.sort_index()
        df_tabela.index = df_tabela.index.str.title()

    meta_total = df_meta['meta'].sum()

    diaria_necessaria_por_dia = {
        dia: round(meta_total / len(dias_uteis_lista), 2) if dia in dias_uteis_lista else 0
        for dia in colunas_dias
    }

    diaria_entregue_por_dia = {
        dia: (df_tabela[dia].sum() / diaria_necessaria_por_dia[dia]) * 100 if diaria_necessaria_por_dia[dia] > 0 else 0
        for dia in colunas_dias
    }

    if df_tabela.shape[1] > 0:
        df_tabela.loc['Total Realizado'] = df_tabela.sum(axis=0)

    alerta_por_data = {
        dia: (
            'vermelho' if diaria_entregue_por_dia.get(dia, 0) < 80 else
            'amarelo' if diaria_entregue_por_dia.get(dia, 0) < 100 else ''
        ) for dia in colunas_dias
    }

    regionais = sorted(df_real['regional'].dropna().unique())
    coordenadores = sorted(df_real['coordenador'].dropna().unique())
    canais_disponiveis = sorted(df_real['canal'].dropna().unique())

    context = {
        'tabela': df_tabela.reset_index().rename(columns={'index': 'canal'}).to_dict(orient='records'),
        'colunas_dias': colunas_dias,
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'canais_disponiveis': canais_disponiveis,
        'canais_selecionados': canais,
        'regionais': regionais,
        'regionais_selecionadas': [regional] if regional else [],
        'coordenadores': coordenadores,
        'coordenadores_selecionadas': [coordenador] if coordenador else [],
        'alerta_por_data': alerta_por_data,
    }

    return render(request, 'dashboard/diaadia.html', context)
