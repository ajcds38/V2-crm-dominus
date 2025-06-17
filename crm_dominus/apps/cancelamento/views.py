from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime
import pandas as pd
import os

from diasuteis.models import DiasUteis

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_REALIZADO = os.path.join(BASE_DIR, '..', 'dados', 'cancelamento_realizado.xlsx')
CAMINHO_METAS = os.path.join(BASE_DIR, '..', 'dados', 'limite_cancelamento.xlsx')

@login_required
def cancelamento(request):
    data_inicio = request.GET.get('inicio', '2025-05-25')
    data_fim = request.GET.get('fim', '2025-06-24')

    regionais = [r.strip().upper() for r in request.GET.getlist('regional') if r]
    coordenadores = [c.strip().upper() for c in request.GET.getlist('coordenador') if c]

    df_real = pd.read_excel(CAMINHO_REALIZADO)
    df_metas = pd.read_excel(CAMINHO_METAS)

    for col in ['cidade', 'regional', 'coordenador']:
        if col in df_real.columns:
            df_real[col] = df_real[col].astype(str).str.strip().str.upper()
        if col in df_metas.columns:
            df_metas[col] = df_metas[col].astype(str).str.strip().str.upper()

    data_inicio = pd.to_datetime(data_inicio)
    data_fim = pd.to_datetime(data_fim)
    df_real['data'] = pd.to_datetime(df_real['data'], dayfirst=True, errors='coerce')

    # Cria base auxiliar para manter todos os filtros visíveis
    df_filtros = pd.read_excel(CAMINHO_METAS)
    for col in ['regional', 'coordenador']:
        if col in df_filtros.columns:
            df_filtros[col] = df_filtros[col].astype(str).str.strip().str.upper()

    # Aplica filtros na base principal
    if regionais:
        df_real = df_real[df_real['regional'].isin(regionais)]
        df_metas = df_metas[df_metas['regional'].isin(regionais)]

    if coordenadores:
        df_real = df_real[df_real['coordenador'].isin(coordenadores)]
        df_metas = df_metas[df_metas['coordenador'].isin(coordenadores)]

    # Filtra por data somente na base de realizado
    df_real = df_real[(df_real['data'] >= data_inicio) & (df_real['data'] <= data_fim)]

    # Agrupamento das metas
    df_metas_group = df_metas.groupby(['cidade'], as_index=False).agg({'meta': 'sum'})
    df_metas_group = df_metas_group.rename(columns={'meta': 'limite_cancelamento'})

    # Agrupamento dos realizados (se houver)
    if not df_real.empty:
        df_real_group = df_real.groupby(['cidade']).agg({'volume': 'sum'}).reset_index()
    else:
        df_real_group = pd.DataFrame(columns=['cidade', 'volume'])

    # Merge com todas as cidades com meta (mesmo que não tenham realizado)
    df_group = pd.merge(df_metas_group, df_real_group, how='left', on='cidade')
    df_group['volume'] = df_group['volume'].fillna(0)

    # Projeções com base nos dias úteis
    dias_uteis = DiasUteis.objects.last()
    dias_passados = dias_uteis.dias_uteis_passados if dias_uteis else 1
    dias_restantes = dias_uteis.dias_uteis_restantes if dias_uteis else 1
    total_dias_uteis = dias_passados + dias_restantes

    df_group['projecao'] = (df_group['volume'] / dias_passados) * total_dias_uteis
    df_group['proj_percentual'] = (df_group['projecao'] / df_group['limite_cancelamento'].replace({0: 1})) * 100

    def definir_cor_alerta(percentual):
        if percentual > 119.99:
            return 'vermelho'
        elif 100.00 <= percentual <= 119.99:
            return 'amarelo'
        return ''

    df_group['cor_alerta'] = df_group['proj_percentual'].apply(definir_cor_alerta)

    totais = {
        'limite': df_group['limite_cancelamento'].sum(),
        'realizado': df_group['volume'].sum(),
        'projecao': df_group['projecao'].sum(),
        'proj_percentual': f"{(df_group['projecao'].sum() / df_group['limite_cancelamento'].sum()) * 100:.2f}%" if df_group['limite_cancelamento'].sum() > 0 else "0.00%",
    }

    context = {
        'cidades': df_group.to_dict(orient='records'),
        'total_limite': int(totais['limite']),
        'total_realizado': int(totais['realizado']),
        'total_proj': int(totais['projecao']),
        'total_proj_percent': totais['proj_percentual'],
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'regionais': sorted(df_filtros['regional'].dropna().unique()),
        'coordenadores': sorted(df_filtros['coordenador'].dropna().unique()),
        'regionais_selecionadas': request.GET.getlist('regional'),
        'coordenadores_selecionadas': request.GET.getlist('coordenador'),
    }

    return render(request, 'cancelamento/index.html', context)
