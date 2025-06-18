from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import pandas as pd
import os
from django.conf import settings
from diasuteis.models import DiasUteis
from functools import lru_cache

# CAMINHOS ABSOLUTOS CORRETOS PARA PRODUÇÃO (Render)
CAMINHO_REALIZADO = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'adesao_realizado.xlsx')
CAMINHO_METAS_CIDADE = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'metas_adesao.xlsx')

@lru_cache()
def get_df_real():
    return pd.read_excel(CAMINHO_REALIZADO, engine="openpyxl")

@lru_cache()
def get_df_meta():
    return pd.read_excel(CAMINHO_METAS_CIDADE, engine="openpyxl")

@login_required
def adesao(request):
    hoje = datetime.today()
    primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
    data_inicio_padrao = (primeiro_dia_mes - timedelta(days=7)).replace(day=25)
    data_fim_padrao = primeiro_dia_mes.replace(day=24) if hoje.day < 25 else (primeiro_dia_mes + timedelta(days=31)).replace(day=24)

    data_inicio = pd.to_datetime(request.GET.get('inicio', data_inicio_padrao.strftime('%Y-%m-%d')))
    data_fim = pd.to_datetime(request.GET.get('fim', data_fim_padrao.strftime('%Y-%m-%d')))

    regionais = [r.strip().upper() for r in request.GET.getlist('regional') if r.strip()]
    coordenadores = [c.strip().upper() for c in request.GET.getlist('coordenador') if c.strip()]
    canais = [c.strip().upper() for c in request.GET.getlist('canal') if c.strip()]

    df_real = get_df_real()
    df_metas = get_df_meta()

    df_real.columns = df_real.columns.str.strip().str.lower()
    df_metas.columns = df_metas.columns.str.strip().str.lower()

    for col in ['cidade', 'canal', 'regional', 'coordenador']:
        if col in df_real.columns:
            df_real[col] = df_real[col].astype(str).str.strip().str.upper()
        if col in df_metas.columns:
            df_metas[col] = df_metas[col].astype(str).str.strip().str.upper()

    canal_padrao = {
        'EXTERNO': 'PAP',
        'PAP': 'PAP'
    }
    df_real['canal'] = df_real['canal'].map(canal_padrao).fillna(df_real['canal'])
    df_metas['canal'] = df_metas['canal'].map(canal_padrao).fillna(df_metas['canal'])

    df_real['data'] = pd.to_datetime(df_real['data'], dayfirst=True, errors='coerce')
    df_real = df_real[(df_real['data'] >= data_inicio) & (df_real['data'] <= data_fim)]

    if regionais:
        df_real = df_real[df_real['regional'].isin(regionais)]
    if coordenadores:
        df_real = df_real[df_real['coordenador'].isin(coordenadores)]
    if canais:
        df_real = df_real[df_real['canal'].isin(canais)]

    colunas_chave = ['cidade', 'canal', 'regional', 'coordenador']
    df_agg = df_real.groupby(colunas_chave).agg({
        'receita': 'sum',
        'vendedores': 'nunique'
    }).reset_index()
    df_agg['volume'] = df_real.groupby(colunas_chave).size().values

    df_group = pd.merge(df_metas, df_agg, how='left', on=colunas_chave)

    for col in ['meta', 'volume', 'receita', 'vendedores']:
        df_group[col] = df_group.get(col, 0).fillna(0)

    dias_uteis = DiasUteis.objects.last()
    dias_passados = dias_uteis.dias_uteis_passados if dias_uteis else 1
    dias_restantes = dias_uteis.dias_uteis_restantes if dias_uteis else 1
    total_dias_uteis = dias_passados + dias_restantes

    df_group['projecao'] = (df_group['volume'] / dias_passados) * total_dias_uteis
    df_group['proj_percentual'] = (df_group['projecao'] / df_group['meta'].replace({0: 1})) * 100
    df_group['ticket_medio'] = df_group['receita'] / df_group['volume'].replace({0: 1})
    df_group['produtividade'] = df_group['volume'] / df_group['vendedores'].replace({0: 1})
    media_produtividade = df_group['produtividade'].mean() if not df_group.empty else 0
    df_group['alerta_produtividade'] = df_group['produtividade'] < media_produtividade

    df_filtros_real = get_df_real()
    df_filtros_meta = get_df_meta()

    df_filtros_real.columns = df_filtros_real.columns.str.strip().str.lower()
    df_filtros_meta.columns = df_filtros_meta.columns.str.strip().str.lower()

    for col in ['regional', 'coordenador', 'canal']:
        if col in df_filtros_real.columns:
            df_filtros_real[col] = df_filtros_real[col].astype(str).str.strip().str.upper()
        if col in df_filtros_meta.columns:
            df_filtros_meta[col] = df_filtros_meta[col].astype(str).str.strip().str.upper()

    df_filtros_real['canal'] = df_filtros_real['canal'].map(canal_padrao).fillna(df_filtros_real['canal'])
    df_filtros_meta['canal'] = df_filtros_meta['canal'].map(canal_padrao).fillna(df_filtros_meta['canal'])

    df_filtros = pd.concat([df_filtros_real, df_filtros_meta], ignore_index=True)

    filtros = {}
    for col in ['regional', 'coordenador', 'canal']:
        if col in df_filtros.columns:
            filtros[col] = sorted(df_filtros[col].dropna().unique())

    context = {
        'cidades': df_group.to_dict(orient='records'),
        'total_meta': int(df_group['meta'].sum()),
        'total_realizado': int(df_group['volume'].sum()),
        'total_proj': int(df_group['projecao'].sum()),
        'total_proj_percent': f"{(df_group['projecao'].sum() / df_group['meta'].sum()) * 100:.2f}%" if df_group['meta'].sum() > 0 else "0.00%",
        'total_ticket': f"{(df_group['receita'].sum() / df_group['volume'].sum()):.2f}" if df_group['volume'].sum() > 0 else "0.00",
        'total_produtividade': f"{(df_group['volume'].sum() / df_group['vendedores'].sum()):.2f}" if df_group['vendedores'].sum() > 0 else "0.00",
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'regionais': filtros.get('regional', []),
        'coordenadores': filtros.get('coordenador', []),
        'canais': filtros.get('canal', []),
        'regionais_selecionadas': request.GET.getlist('regional'),
        'coordenadores_selecionadas': request.GET.getlist('coordenador'),
        'canais_selecionadas': request.GET.getlist('canal'),
    }

    return render(request, 'adesao/index.html', context)

@lru_cache()
def get_df_real_vendedor():
    caminho = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'adesao_realizado.xlsx')
    return pd.read_excel(caminho, engine="openpyxl")

@login_required(login_url='/')
def adesao_vendedor(request):
    hoje = datetime.today()
    primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
    data_inicio_padrao = (primeiro_dia_mes - timedelta(days=7)).replace(day=25)
    data_fim_padrao = primeiro_dia_mes.replace(day=24) if hoje.day < 25 else (primeiro_dia_mes + timedelta(days=31)).replace(day=24)

    data_inicio = pd.to_datetime(request.GET.get('inicio', data_inicio_padrao.strftime('%Y-%m-%d')))
    data_fim = pd.to_datetime(request.GET.get('fim', data_fim_padrao.strftime('%Y-%m-%d')))

    regionais = [r.strip().upper() for r in request.GET.getlist('regional') if r.strip()]
    coordenadores = [c.strip().upper() for c in request.GET.getlist('coordenador') if c.strip()]
    canais = [c.strip().upper() for c in request.GET.getlist('canal') if c.strip()]

    df_base = get_df_real_vendedor()
    df_base.columns = df_base.columns.str.strip().str.lower()
    for col in ['regional', 'coordenador', 'canal', 'vendedores']:
        df_base[col] = df_base[col].astype(str).str.strip().str.upper()

    df_base['canal'] = df_base['canal'].replace({'EXTERNO': 'PAP', 'PAP': 'PAP'})
    df_base['data'] = pd.to_datetime(df_base['data'], dayfirst=True, errors='coerce')

    filtros = {
        'regional': sorted(df_base['regional'].dropna().unique()),
        'coordenador': sorted(df_base['coordenador'].dropna().unique()),
        'canal': sorted(df_base['canal'].dropna().unique()),
    }

    df = df_base[(df_base['data'] >= data_inicio) & (df_base['data'] <= data_fim)].copy()
    if regionais:
        df = df[df['regional'].isin(regionais)]
    if coordenadores:
        df = df[df['coordenador'].isin(coordenadores)]
    if canais:
        df = df[df['canal'].isin(canais)]

    colunas_chave = ['vendedores', 'canal']
    df_agg = df.groupby(colunas_chave).agg({
        'receita': 'sum',
        'regional': 'first',
        'coordenador': 'first'
    }).reset_index()

    df_agg['volume'] = df.groupby(colunas_chave).size().values
    df_agg['meta'] = 25

    dias_uteis = DiasUteis.objects.last()
    dias_passados = dias_uteis.dias_uteis_passados if dias_uteis else 1
    dias_restantes = dias_uteis.dias_uteis_restantes if dias_uteis else 1
    total_dias_uteis = dias_passados + dias_restantes

    df_agg['projecao'] = (df_agg['volume'] / dias_passados) * total_dias_uteis
    df_agg['proj_percentual'] = (df_agg['projecao'] / df_agg['meta'].replace({0: 1})) * 100
    df_agg['ticket_medio'] = df_agg['receita'] / df_agg['volume'].replace({0: 1})
    df_agg['produtividade'] = df_agg['volume']
    media_produtividade = df_agg['produtividade'].mean() if not df_agg.empty else 0
    df_agg['alerta_produtividade'] = df_agg['produtividade'] < media_produtividade

    df_agg = df_agg.sort_values(by='projecao', ascending=False)

    context = {
        'cidades': df_agg.to_dict(orient='records'),
        'total_meta': int(df_agg['meta'].sum()),
        'total_realizado': int(df_agg['volume'].sum()),
        'total_proj': int(df_agg['projecao'].sum()),
        'total_proj_percent': f"{(df_agg['projecao'].sum() / df_agg['meta'].sum()) * 100:.2f}%" if df_agg['meta'].sum() > 0 else "0.00%",
        'total_ticket': f"{(df_agg['receita'].sum() / df_agg['volume'].sum()):.2f}" if df_agg['volume'].sum() > 0 else "0.00",
        'total_produtividade': f"{(df_agg['volume'].sum() / len(df_agg)):.2f}" if len(df_agg) > 0 else "0.00",
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'regionais': filtros['regional'],
        'coordenadores': filtros['coordenador'],
        'canais': filtros['canal'],
        'regionais_selecionadas': request.GET.getlist('regional'),
        'coordenadores_selecionadas': request.GET.getlist('coordenador'),
        'canais_selecionadas': request.GET.getlist('canal'),
    }

    return render(request, 'adesao/vendedor.html', context)
