from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
import pandas as pd
import os
from django.conf import settings
from diasuteis.models import DiasUteis
from functools import lru_cache

# === CAMINHOS (reaproveita os seus) ===
CAMINHO_REALIZADO = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'Atualizacao_CRM.xlsx')
CAMINHO_METAS_ADESAO = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'metas_adesao.xlsx')
CAMINHO_METAS_ATIVACAO = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados', 'metas_ativacao.xlsx')

@lru_cache()
def get_df_realizado():
    return pd.read_excel(CAMINHO_REALIZADO, engine="openpyxl")

@lru_cache()
def get_df_metas_adesao():
    return pd.read_excel(CAMINHO_METAS_ADESAO, engine="openpyxl")

@lru_cache()
def get_df_metas_ativacao():
    return pd.read_excel(CAMINHO_METAS_ATIVACAO, engine="openpyxl")

@login_required(login_url='/')
def visao_geral_cidades(request):
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
    data_meta_referencia = data_inicio.replace(day=25)

    # Filtros (listas, caixa alta), igual sua view
    regionais = [r.strip().upper() for r in request.GET.getlist('regional') if r.strip()]
    coordenadores = [c.strip().upper() for c in request.GET.getlist('coordenador') if c.strip()]
    canais = [c.strip().upper() for c in request.GET.getlist('canal') if c.strip()]

    # === Leitura bases ===
    df_real = get_df_realizado().copy()
    df_meta_ad = get_df_metas_adesao().copy()
    df_meta_at = get_df_metas_ativacao().copy()

    # Normalizar colunas
    for df in (df_real, df_meta_ad, df_meta_at):
        df.columns = df.columns.str.strip().str.lower()

    for df in (df_real, df_meta_ad, df_meta_at):
        for col in ['cidade', 'canal', 'regional', 'coordenador']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.upper()

    # Mapear canal EXTERNO -> PAP (mesma regra da sua view)
    for df in (df_real, df_meta_ad, df_meta_at):
        if 'canal' in df.columns:
            df['canal'] = df['canal'].replace({'EXTERNO': 'PAP'})

    # Datas
    if 'adesao' in df_real.columns:
        df_real['adesao'] = pd.to_datetime(df_real['adesao'], errors='coerce')
    if 'ativacao' in df_real.columns:
        df_real['ativacao'] = pd.to_datetime(df_real['ativacao'], errors='coerce')

    for df in (df_meta_ad, df_meta_at):
        if 'data_meta' in df.columns:
            df['data_meta'] = pd.to_datetime(df['data_meta'], errors='coerce')

    # Filtrar metas por data_meta (dia 25 do mês)
    df_meta_ad = df_meta_ad[df_meta_ad['data_meta'] == data_meta_referencia] if 'data_meta' in df_meta_ad else df_meta_ad.iloc[0:0]
    df_meta_at = df_meta_at[df_meta_at['data_meta'] == data_meta_referencia] if 'data_meta' in df_meta_at else df_meta_at.iloc[0:0]

    # Filtro por período (adesão e ativação)
    df_ad = df_real[df_real['adesao'].notna()] if 'adesao' in df_real else df_real.iloc[0:0]
    df_ad = df_ad[(df_ad['adesao'] >= data_inicio) & (df_ad['adesao'] <= data_fim)]

    df_at = df_real[df_real['ativacao'].notna()] if 'ativacao' in df_real else df_real.iloc[0:0]
    df_at = df_at[(df_at['ativacao'] >= data_inicio) & (df_at['ativacao'] <= data_fim)]

    # Listas para selects (como na sua view)
    todas_regionais = sorted(set(df_real['regional'].dropna().unique()) | set(df_meta_ad['regional'].dropna().unique()) | set(df_meta_at['regional'].dropna().unique()))
    todos_coordenadores = sorted(set(df_real['coordenador'].dropna().unique()) | set(df_meta_ad['coordenador'].dropna().unique()) | set(df_meta_at['coordenador'].dropna().unique()))
    todos_canais = sorted(set(df_real['canal'].dropna().unique()) | set(df_meta_ad['canal'].dropna().unique()) | set(df_meta_at['canal'].dropna().unique()))

    # Aplicar filtros selecionados - nas três bases
    if regionais:
        df_ad = df_ad[df_ad['regional'].isin(regionais)]
        df_at = df_at[df_at['regional'].isin(regionais)]
        df_meta_ad = df_meta_ad[df_meta_ad['regional'].isin(regionais)]
        df_meta_at = df_meta_at[df_meta_at['regional'].isin(regionais)]

    if coordenadores:
        df_ad = df_ad[df_ad['coordenador'].isin(coordenadores)]
        df_at = df_at[df_at['coordenador'].isin(coordenadores)]
        df_meta_ad = df_meta_ad[df_meta_ad['coordenador'].isin(coordenadores)]
        df_meta_at = df_meta_at[df_meta_at['coordenador'].isin(coordenadores)]

    if canais:
        df_ad = df_ad[df_ad['canal'].isin(canais)]
        df_at = df_at[df_at['canal'].isin(canais)]
        df_meta_ad = df_meta_ad[df_meta_ad['canal'].isin(canais)]
        df_meta_at = df_meta_at[df_meta_at['canal'].isin(canais)]

    # === Agregar por CIDADE (consolidado) ===
    # Realizado
    ad_real_cid = df_ad.groupby('cidade').size().rename('realizado_adesao').reset_index() if not df_ad.empty else pd.DataFrame(columns=['cidade', 'realizado_adesao'])
    at_real_cid = df_at.groupby('cidade').size().rename('realizado_ativacao').reset_index() if not df_at.empty else pd.DataFrame(columns=['cidade', 'realizado_ativacao'])

    # Metas
    if not df_meta_ad.empty:
        meta_ad_cid = df_meta_ad.groupby('cidade')['meta'].sum().reset_index().rename(columns={'meta':'meta_adesao'})
    else:
        meta_ad_cid = pd.DataFrame(columns=['cidade', 'meta_adesao'])

    if not df_meta_at.empty:
        meta_at_cid = df_meta_at.groupby('cidade')['meta'].sum().reset_index().rename(columns={'meta':'meta_ativacao'})
    else:
        meta_at_cid = pd.DataFrame(columns=['cidade', 'meta_ativacao'])

    # Consolidar tabela base
    cidades = pd.DataFrame({'cidade': sorted(set(pd.concat([ad_real_cid['cidade'], at_real_cid['cidade'], meta_ad_cid['cidade'], meta_at_cid['cidade']], ignore_index=True).dropna().unique()))})
    tbl = (cidades
           .merge(ad_real_cid, on='cidade', how='left')
           .merge(at_real_cid, on='cidade', how='left')
           .merge(meta_ad_cid, on='cidade', how='left')
           .merge(meta_at_cid, on='cidade', how='left'))

    for c in ['realizado_adesao','realizado_ativacao','meta_adesao','meta_ativacao']:
        if c in tbl.columns:
            tbl[c] = tbl[c].fillna(0).astype(int)

    # === Projeções via DiasUteis (igual sua lógica) ===
    dias = DiasUteis.objects.last()
    dias_passados = dias.dias_uteis_passados if dias else 1
    dias_restantes = dias.dias_uteis_restantes if dias else 1
    total_dias_uteis = dias_passados + dias_restantes

    if data_fim < hoje:
        tbl['proj_adesao'] = tbl['realizado_adesao']
        tbl['proj_ativacao'] = tbl['realizado_ativacao']
    else:
        # evita divisão por zero
        base_div = dias_passados if dias_passados > 0 else 1
        tbl['proj_adesao'] = (tbl['realizado_adesao'] / base_div) * total_dias_uteis
        tbl['proj_ativacao'] = (tbl['realizado_ativacao'] / base_div) * total_dias_uteis

    # % (evitar zero)
    tbl['proj_adesao_pct']   = (tbl['proj_adesao']   / tbl['meta_adesao'].replace({0:1})) * 100
    tbl['proj_ativacao_pct'] = (tbl['proj_ativacao'] / tbl['meta_ativacao'].replace({0:1})) * 100

    # Classes de alerta (apenas amarelo/vermelho)
    def cls_alerta(p):
        if p < 80:   # vermelho
            return 'alerta-vermelho'
        if p < 100:  # amarelo
            return 'alerta-amarelo'
        return ''    # sem verde

    tbl['cls_adesao'] = tbl['proj_adesao_pct'].apply(cls_alerta)
    tbl['cls_ativ']   = tbl['proj_ativacao_pct'].apply(cls_alerta)

    # Totais
    total_meta_adesao = int(tbl['meta_adesao'].sum())
    total_realizado_adesao = int(tbl['realizado_adesao'].sum())
    total_proj_adesao = float(tbl['proj_adesao'].sum())

    total_meta_ativacao = int(tbl['meta_ativacao'].sum())
    total_realizado_ativacao = int(tbl['realizado_ativacao'].sum())
    total_proj_ativacao = float(tbl['proj_ativacao'].sum())

    total_proj_pct_adesao = (total_proj_adesao / total_meta_adesao * 100) if total_meta_adesao > 0 else 0.0
    total_proj_pct_ativ   = (total_proj_ativacao / total_meta_ativacao * 100) if total_meta_ativacao > 0 else 0.0

    context = {
        'tabela': tbl.to_dict(orient='records'),
        'total_meta_adesao': total_meta_adesao,
        'total_realizado_adesao': total_realizado_adesao,
        'total_proj_adesao': int(round(total_proj_adesao)),
        'total_proj_pct_adesao': f"{total_proj_pct_adesao:.2f}%",
        'total_meta_ativacao': total_meta_ativacao,
        'total_realizado_ativacao': total_realizado_ativacao,
        'total_proj_ativacao': int(round(total_proj_ativacao)),
        'total_proj_pct_ativacao': f"{total_proj_pct_ativ:.2f}%",

        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),

        'regionais': todas_regionais,
        'coordenadores': todos_coordenadores,
        'canais': todos_canais,
        'regionais_selecionadas': regionais,
        'coordenadores_selecionadas': coordenadores,
        'canais_selecionadas': canais,
    }
    return render(request, 'visao_geral_cidades/index.html', context)
