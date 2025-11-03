from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import pandas as pd
import os
from django.conf import settings
from diasuteis.models import DiasUteis
from functools import lru_cache
import numpy as np  # <- usado para evitar divisão por zero

# === CAMINHOS (reaproveita os seus) ===
CAMINHO_REALIZADO = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'Atualizacao_CRM.xlsx')

# Metas FIXAS por vendedor
META_FIXA_ADESAO = 25
META_FIXA_ATIVACAO = 22

@lru_cache()
def get_df_realizado():
    return pd.read_excel(CAMINHO_REALIZADO, engine="openpyxl")

@login_required(login_url='/')
def visao_geral_vendedores(request):
    hoje = datetime.today()
    primeiro_dia_mes = datetime(hoje.year, hoje.month, 1)
    data_inicio_padrao = (primeiro_dia_mes - timedelta(days=7)).replace(day=25)
    data_fim_padrao = (
        primeiro_dia_mes.replace(day=24)
        if hoje.day < 25 else
        (primeiro_dia_mes + timedelta(days=31)).replace(day=24)
    )

    data_inicio = pd.to_datetime(request.GET.get('inicio', data_inicio_padrao.strftime('%Y-%m-%d')))
    data_fim = pd.to_datetime(request.GET.get('fim', data_fim_padrao.strftime('%Y-%m-%d')))

    # Filtros (listas, caixa alta)
    regionais = [r.strip().upper() for r in request.GET.getlist('regional') if r.strip()]
    coordenadores = [c.strip().upper() for c in request.GET.getlist('coordenador') if c.strip()]
    canais = [c.strip().upper() for c in request.GET.getlist('canal') if c.strip()]

    # === Leitura base única ===
    df_real = get_df_realizado().copy()
    df_real.columns = df_real.columns.str.strip().str.lower()

    # Normalizações de texto
    for col in ['vendedores', 'cidade', 'canal', 'regional', 'coordenador']:
        if col in df_real.columns:
            df_real[col] = df_real[col].astype(str).str.strip().str.upper()

    # EXTERNO -> PAP
    if 'canal' in df_real.columns:
        df_real['canal'] = df_real['canal'].replace({'EXTERNO': 'PAP'})

    # Datas
    if 'adesao' in df_real.columns:
        df_real['adesao'] = pd.to_datetime(df_real['adesao'], errors='coerce')
    if 'ativacao' in df_real.columns:
        df_real['ativacao'] = pd.to_datetime(df_real['ativacao'], errors='coerce')

    # Filtro por período
    df_ad = df_real[df_real['adesao'].notna()] if 'adesao' in df_real else df_real.iloc[0:0]
    df_ad = df_ad[(df_ad['adesao'] >= data_inicio) & (df_ad['adesao'] <= data_fim)]

    df_at = df_real[df_real['ativacao'].notna()] if 'ativacao' in df_real else df_real.iloc[0:0]
    df_at = df_at[(df_at['ativacao'] >= data_inicio) & (df_at['ativacao'] <= data_fim)]

    # Listas para selects
    todas_regionais = sorted(set(df_real['regional'].dropna().unique()))
    todos_coordenadores = sorted(set(df_real['coordenador'].dropna().unique()))
    todos_canais = sorted(set(df_real['canal'].dropna().unique()))

    # Aplicar filtros
    if regionais:
        df_ad = df_ad[df_ad['regional'].isin(regionais)]
        df_at = df_at[df_at['regional'].isin(regionais)]
    if coordenadores:
        df_ad = df_ad[df_ad['coordenador'].isin(coordenadores)]
        df_at = df_at[df_at['coordenador'].isin(coordenadores)]
    if canais:
        df_ad = df_ad[df_ad['canal'].isin(canais)]
        df_at = df_at[df_at['canal'].isin(canais)]

    # === Agregar por VENDEDOR ===
    ad_real_vend = (
        df_ad.groupby('vendedores').size().rename('realizado_adesao').reset_index()
        if not df_ad.empty else pd.DataFrame(columns=['vendedores', 'realizado_adesao'])
    )
    at_real_vend = (
        df_at.groupby('vendedores').size().rename('realizado_ativacao').reset_index()
        if not df_at.empty else pd.DataFrame(columns=['vendedores', 'realizado_ativacao'])
    )

    vendedores = sorted(
        set(pd.concat([ad_real_vend['vendedores'], at_real_vend['vendedores']], ignore_index=True).dropna().unique())
    )
    tbl = pd.DataFrame({'vendedores': vendedores})

    tbl = (tbl
           .merge(ad_real_vend, on='vendedores', how='left')
           .merge(at_real_vend, on='vendedores', how='left'))

    for c in ['realizado_adesao', 'realizado_ativacao']:
        if c in tbl.columns:
            tbl[c] = tbl[c].fillna(0).astype(int)

    # === Metas FIXAS ===
    tbl['meta_adesao'] = META_FIXA_ADESAO
    tbl['meta_ativacao'] = META_FIXA_ATIVACAO

    # === Projeções via DiasUteis ===
    dias = DiasUteis.objects.last()
    dias_passados = dias.dias_uteis_passados if dias else 1
    dias_restantes = dias.dias_uteis_restantes if dias else 1
    total_dias_uteis = dias_passados + dias_restantes

    if data_fim < hoje:
        tbl['proj_adesao'] = tbl['realizado_adesao']
        tbl['proj_ativacao'] = tbl['realizado_ativacao']
    else:
        base_div = dias_passados if dias_passados > 0 else 1
        tbl['proj_adesao'] = (tbl['realizado_adesao'] / base_div) * total_dias_uteis
        tbl['proj_ativacao'] = (tbl['realizado_ativacao'] / base_div) * total_dias_uteis

    # % projeção (por linha, em número)
    tbl['proj_adesao_pct']   = (tbl['proj_adesao']   / tbl['meta_adesao'].replace({0:1})) * 100
    tbl['proj_ativacao_pct'] = (tbl['proj_ativacao'] / tbl['meta_ativacao'].replace({0:1})) * 100

    # Classes de alerta
    def cls_alerta(p):
        if p < 80:
            return 'alerta-vermelho'
        if p < 100:
            return 'alerta-amarelo'
        return ''

    tbl['cls_adesao'] = tbl['proj_adesao_pct'].apply(cls_alerta)
    tbl['cls_ativ']   = tbl['proj_ativacao_pct'].apply(cls_alerta)

    # === NOVO: Aproveitamento por vendedor (Ativação ÷ Adesão) ===
    # Guardamos como percentual (0–100). Se adesão = 0, fica NaN.
    tbl['aproveitamento'] = np.where(
        tbl['realizado_adesao'] > 0,
        (tbl['realizado_ativacao'] / tbl['realizado_adesao']) * 100.0,
        np.nan
    )

    # ✅ ORDENAR: maior → menor Projeção % de Ativação (mantido)
    tbl = tbl.sort_values(by='proj_ativacao_pct', ascending=False)

    # Totais
    qtd_vendedores = len(tbl.index)
    total_meta_adesao = int(qtd_vendedores * META_FIXA_ADESAO)
    total_meta_ativacao = int(qtd_vendedores * META_FIXA_ATIVACAO)

    total_realizado_adesao = int(tbl['realizado_adesao'].sum())
    total_realizado_ativacao = int(tbl['realizado_ativacao'].sum())

    total_proj_adesao = float(tbl['proj_adesao'].sum())
    total_proj_ativacao = float(tbl['proj_ativacao'].sum())

    total_proj_pct_adesao = (total_proj_adesao / total_meta_adesao * 100) if total_meta_adesao > 0 else 0.0
    total_proj_pct_ativ   = (total_proj_ativacao / total_meta_ativacao * 100) if total_meta_ativacao > 0 else 0.0

    # === NOVO: Aproveitamento Total (Ativação ÷ Adesão no agregado) ===
    total_aproveitamento_pct = (total_realizado_ativacao / total_realizado_adesao * 100.0) if total_realizado_adesao > 0 else 0.0

    context = {
        'tabela': tbl.rename(columns={'vendedores': 'vendedor'}).to_dict(orient='records'),

        'total_meta_adesao': total_meta_adesao,
        'total_realizado_adesao': total_realizado_adesao,
        'total_proj_adesao': int(round(total_proj_adesao)),
        'total_proj_pct_adesao': f"{total_proj_pct_adesao:.2f}%",

        'total_meta_ativacao': total_meta_ativacao,
        'total_realizado_ativacao': total_realizado_ativacao,
        'total_proj_ativacao': int(round(total_proj_ativacao)),
        'total_proj_pct_ativacao': f"{total_proj_pct_ativ:.2f}%",

        # === NOVO: total de aproveitamento para exibir no rodapé
        'total_aproveitamento_pct': f"{total_aproveitamento_pct:.2f}%",

        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),

        'regionais': todas_regionais,
        'coordenadores': todos_coordenadores,
        'canais': todos_canais,
        'regionais_selecionadas': regionais,
        'coordenadores_selecionadas': coordenadores,
        'canais_selecionadas': canais,
    }
    return render(request, 'visao_geral_vendedores/index.html', context)
