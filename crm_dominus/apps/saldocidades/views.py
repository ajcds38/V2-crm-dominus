from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import pandas as pd
import os
from datetime import datetime, timedelta
from diasuteis.models import DiasUteis
from django.conf import settings

@login_required(login_url='/')
def saldo_cidades(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')
    ativ_path = os.path.join(base_path, 'ativacao_realizado.xlsx')
    cancel_path = os.path.join(base_path, 'cancelamento_realizado.xlsx')

    hoje = datetime.today()
    primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
    data_inicio_padrao = (primeiro_dia_mes - timedelta(days=7)).replace(day=25)
    data_fim_padrao = primeiro_dia_mes.replace(day=24) if hoje.day < 25 else (primeiro_dia_mes + timedelta(days=31)).replace(day=24)

    data_inicio = pd.to_datetime(request.GET.get('inicio', data_inicio_padrao.strftime('%Y-%m-%d')))
    data_fim = pd.to_datetime(request.GET.get('fim', data_fim_padrao.strftime('%Y-%m-%d')))

    regional = request.GET.get('regional', '').strip().upper()
    coordenador = request.GET.get('coordenador', '').strip().upper()
    canais = [c.strip().upper() for c in request.GET.getlist('canal') if c.strip()]

    df_ativ = pd.read_excel(ativ_path)
    df_cancel = pd.read_excel(cancel_path)

    for df in [df_ativ, df_cancel]:
        df.columns = df.columns.str.strip().str.lower()
        for col in ['cidade', 'regional', 'coordenador', 'canal']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.upper().str.replace('\xa0', ' ')
        df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['canal'] = 'INTERNO'  # 🔒 força todos como INTERNO

    # Geração de opções de filtro
    df_filtros = pd.concat([
        df_ativ[['regional', 'coordenador']],
        df_cancel[['regional', 'coordenador']]
    ], ignore_index=True)
    filtros = {
        'regional': sorted(df_filtros['regional'].dropna().unique()),
        'coordenador': sorted(df_filtros['coordenador'].dropna().unique()),
        'canal': ['INTERNO']
    }

    # Aplicação dos filtros de data e parâmetros
    df_ativ = df_ativ[(df_ativ['data'] >= data_inicio) & (df_ativ['data'] <= data_fim)]
    df_cancel = df_cancel[(df_cancel['data'] >= data_inicio) & (df_cancel['data'] <= data_fim)]

    if regional:
        df_ativ = df_ativ[df_ativ['regional'] == regional]
        df_cancel = df_cancel[df_cancel['regional'] == regional]
    if coordenador:
        df_ativ = df_ativ[df_ativ['coordenador'] == coordenador]
        df_cancel = df_cancel[df_cancel['coordenador'] == coordenador]
    if canais:
        df_ativ = df_ativ[df_ativ['canal'].isin(canais)]
        df_cancel = df_cancel[df_cancel['canal'].isin(canais)]

    dias_uteis = DiasUteis.objects.filter(data_inicio=data_inicio, data_fim=data_fim).first()
    dias_passados = dias_uteis.dias_uteis_passados if dias_uteis else 1
    dias_totais = dias_uteis.total_dias_uteis if dias_uteis else 1

    ativ_proj = df_ativ.groupby('cidade')['volume'].sum() / dias_passados * dias_totais
    cancel_proj = df_cancel.groupby('cidade')['volume'].sum() / dias_passados * dias_totais

    cidades = sorted(set(ativ_proj.index).union(set(cancel_proj.index)))
    saldo_df = pd.DataFrame({'cidade': cidades})
    saldo_df['projecao_ativacao'] = saldo_df['cidade'].map(ativ_proj).fillna(0).round(2)
    saldo_df['projecao_cancelamento'] = saldo_df['cidade'].map(cancel_proj).fillna(0).round(2)
    saldo_df['saldo_liquido'] = (saldo_df['projecao_ativacao'] - saldo_df['projecao_cancelamento']).round(2)
    saldo_df = saldo_df.sort_values('saldo_liquido')

    total_ativ = saldo_df['projecao_ativacao'].sum().round(2)
    total_cancel = saldo_df['projecao_cancelamento'].sum().round(2)
    total_saldo = saldo_df['saldo_liquido'].sum().round(2)

    return render(request, 'saldocidades/saldo.html', {
        'dados': saldo_df.to_dict(orient='records'),
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'regionais': filtros['regional'],
        'coordenadores': filtros['coordenador'],
        'canais': filtros['canal'],
        'regional_selecionado': regional,
        'coordenador_selecionado': coordenador,
        'canais_selecionadas': canais,
        'total_ativ': total_ativ,
        'total_cancel': total_cancel,
        'total_saldo': total_saldo,
    })
