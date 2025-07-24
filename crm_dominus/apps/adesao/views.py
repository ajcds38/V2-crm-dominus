from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import pandas as pd
import os
from django.conf import settings
from diasuteis.models import DiasUteis
from functools import lru_cache

# CAMINHOS
CAMINHO_REALIZADO = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'Atualizacao_CRM.xlsx')
CAMINHO_METAS = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'metas_adesao.xlsx')

@lru_cache()
def get_df_realizado():
    return pd.read_excel(CAMINHO_REALIZADO, engine="openpyxl")

@lru_cache()
def get_df_metas():
    return pd.read_excel(CAMINHO_METAS, engine="openpyxl")

@login_required(login_url='/')
def adesao(request):
    hoje = datetime.today()
    primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
    data_inicio_padrao = (primeiro_dia_mes - timedelta(days=7)).replace(day=25)
    data_fim_padrao = primeiro_dia_mes.replace(day=24) if hoje.day < 25 else (primeiro_dia_mes + timedelta(days=31)).replace(day=24)

    data_inicio = pd.to_datetime(request.GET.get('inicio', data_inicio_padrao.strftime('%Y-%m-%d')))
    data_fim = pd.to_datetime(request.GET.get('fim', data_fim_padrao.strftime('%Y-%m-%d')))
    data_meta_referencia = data_inicio.replace(day=25)

    regionais = [r.strip().upper() for r in request.GET.getlist('regional') if r.strip()]
    coordenadores = [c.strip().upper() for c in request.GET.getlist('coordenador') if c.strip()]
    canais = [c.strip().upper() for c in request.GET.getlist('canal') if c.strip()]

    # Leitura das bases
    df_real = get_df_realizado()
    df_meta = get_df_metas()

    df_real.columns = df_real.columns.str.strip().str.lower()
    df_meta.columns = df_meta.columns.str.strip().str.lower()

    for col in ['cidade', 'canal', 'regional', 'coordenador']:
        if col in df_real.columns:
            df_real[col] = df_real[col].astype(str).str.strip().str.upper()
        if col in df_meta.columns:
            df_meta[col] = df_meta[col].astype(str).str.strip().str.upper()

    df_real['canal'] = df_real['canal'].replace({'EXTERNO': 'PAP'})
    df_meta['canal'] = df_meta['canal'].replace({'EXTERNO': 'PAP'})

    df_real['adesao'] = pd.to_datetime(df_real['adesao'], errors='coerce')
    df_meta['data_meta'] = pd.to_datetime(df_meta['data_meta'], errors='coerce')

    # Filtro por data da meta
    df_meta = df_meta[df_meta['data_meta'] == data_meta_referencia]
    if df_meta.empty:
        df_meta = pd.DataFrame(columns=['cidade', 'canal', 'regional', 'coordenador', 'meta'])

    # Filtro por período da adesão
    df_real = df_real[df_real['adesao'].notna()]
    df_real = df_real[(df_real['adesao'] >= data_inicio) & (df_real['adesao'] <= data_fim)]

    todas_regionais = sorted(set(df_real['regional'].dropna().unique()) | set(df_meta['regional'].dropna().unique()))
    todos_coordenadores = sorted(set(df_real['coordenador'].dropna().unique()) | set(df_meta['coordenador'].dropna().unique()))
    todos_canais = sorted(set(df_real['canal'].dropna().unique()) | set(df_meta['canal'].dropna().unique()))

    if regionais:
        df_real = df_real[df_real['regional'].isin(regionais)]
        df_meta = df_meta[df_meta['regional'].isin(regionais)]

    if coordenadores:
        df_real = df_real[df_real['coordenador'].isin(coordenadores)]
        df_meta = df_meta[df_meta['coordenador'].isin(coordenadores)]

    if canais:
        df_real = df_real[df_real['canal'].isin(canais)]
        df_meta = df_meta[df_meta['canal'].isin(canais)]

    colunas_chave = ['cidade', 'canal', 'regional', 'coordenador']
    df_agg = df_real.groupby(colunas_chave).agg({
        'receita': 'sum',
        'vendedores': 'nunique'
    }).reset_index()
    df_agg['volume'] = df_real.groupby(colunas_chave).size().values

    df_group = pd.merge(df_meta, df_agg, how='left', on=colunas_chave)

    for col in ['meta', 'volume', 'receita', 'vendedores']:
        df_group[col] = df_group.get(col, 0).fillna(0)

    dias_uteis = DiasUteis.objects.last()
    dias_passados = dias_uteis.dias_uteis_passados if dias_uteis else 1
    dias_restantes = dias_uteis.dias_uteis_restantes if dias_uteis else 1
    total_dias_uteis = dias_passados + dias_restantes

    if data_fim < hoje:
        df_group['projecao'] = df_group['volume']
    else:
        df_group['projecao'] = (df_group['volume'] / dias_passados) * total_dias_uteis

    df_group['proj_percentual'] = (df_group['projecao'] / df_group['meta'].replace({0: 1})) * 100
    df_group['ticket_medio'] = df_group['receita'] / df_group['volume'].replace({0: 1})
    df_group['produtividade'] = df_group['volume'] / df_group['vendedores'].replace({0: 1})
    media_produtividade = df_group['produtividade'].mean() if not df_group.empty else 0
    df_group['alerta_produtividade'] = df_group['produtividade'] < media_produtividade

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
        'regionais': todas_regionais,
        'coordenadores': todos_coordenadores,
        'canais': todos_canais,
        'regionais_selecionadas': regionais,
        'coordenadores_selecionadas': coordenadores,
        'canais_selecionadas': canais,
    }

    return render(request, 'adesao/index.html', context)

# ✅ Caminho correto para o arquivo consolidado
CAMINHO_CONSOLIDADO = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'Atualizacao_CRM.xlsx')

@lru_cache()
def get_df_unificado():
    return pd.read_excel(CAMINHO_CONSOLIDADO, engine="openpyxl")

@login_required(login_url='/')
def adesao_vendedor(request):
    hoje = datetime.today()
    primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
    data_inicio_padrao = (primeiro_dia_mes - timedelta(days=7)).replace(day=25)
    data_fim_padrao = primeiro_dia_mes.replace(day=24) if hoje.day < 25 else (primeiro_dia_mes + timedelta(days=31)).replace(day=24)

    data_inicio = pd.to_datetime(request.GET.get('inicio', data_inicio_padrao.strftime('%Y-%m-%d')))
    data_fim = pd.to_datetime(request.GET.get('fim', data_fim_padrao.strftime('%Y-%m-%d')))

    regionais_sel = [r.strip().upper() for r in request.GET.getlist('regional') if r.strip()]
    coordenadores_sel = [c.strip().upper() for c in request.GET.getlist('coordenador') if c.strip()]
    canais_sel = [c.strip().upper() for c in request.GET.getlist('canal') if c.strip()]

    df = get_df_unificado()
    df.columns = df.columns.str.strip().str.lower()

    for col in ['regional', 'coordenador', 'canal', 'vendedores']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()

    df['canal'] = df['canal'].replace({'EXTERNO': 'PAP'})
    df['adesao'] = pd.to_datetime(df['adesao'], errors='coerce')

    df = df[df['adesao'].notna()]
    df = df[(df['adesao'] >= data_inicio) & (df['adesao'] <= data_fim)]

    # ⬇️ Salva listas completas antes dos filtros
    lista_regionais = sorted(df['regional'].dropna().unique())
    lista_coordenadores = sorted(df['coordenador'].dropna().unique())
    lista_canais = sorted(df['canal'].dropna().unique())

    # ⬇️ Aplica filtros após capturar as listas completas
    if regionais_sel:
        df = df[df['regional'].isin(regionais_sel)]
    if coordenadores_sel:
        df = df[df['coordenador'].isin(coordenadores_sel)]
    if canais_sel:
        df = df[df['canal'].isin(canais_sel)]

    colunas_chave = ['vendedores', 'canal']
    df_agg = df.groupby(colunas_chave).agg({
        'receita': 'sum',
        'regional': 'first',
        'coordenador': 'first'
    }).reset_index()
    df_agg['volume'] = df.groupby(colunas_chave).size().values
    df_agg['meta'] = 25  # ✅ Meta fixa por vendedor

    dias_uteis = DiasUteis.objects.last()
    dias_passados = dias_uteis.dias_uteis_passados if dias_uteis else 1
    dias_restantes = dias_uteis.dias_uteis_restantes if dias_uteis else 1
    total_dias_uteis = dias_passados + dias_restantes

    if data_fim < hoje:
        df_agg['projecao'] = df_agg['volume']
    else:
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
        'regionais': lista_regionais,
        'coordenadores': lista_coordenadores,
        'canais': lista_canais,
        'regionais_selecionadas': request.GET.getlist('regional'),
        'coordenadores_selecionadas': request.GET.getlist('coordenador'),
        'canais_selecionadas': request.GET.getlist('canal'),
    }

    return render(request, 'adesao/vendedor.html', context)