from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_page
from django.shortcuts import render
import pandas as pd
import os
from datetime import datetime
from django.conf import settings
from diasuteis.models import DiasUteis

@cache_page(120)
@login_required(login_url='/')
def dashboard_diaadia(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')

    caminho_arquivo_unificado = os.path.join(base_path, 'Atualizacao_CRM.xlsx')
    cancelamento_path = os.path.join(base_path, 'cancelamento_realizado.xlsx')
    metas_adesao_path = os.path.join(base_path, 'metas_adesao.xlsx')
    metas_ativacao_path = os.path.join(base_path, 'metas_ativacao.xlsx')
    limite_path = os.path.join(base_path, 'limite_cancelamento.xlsx')

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
        data_inicio = pd.to_datetime("2025-06-25")
        data_fim = pd.to_datetime("2025-07-24")
    if data_fim < data_inicio:
        data_inicio = data_fim - pd.DateOffset(months=1)

    intervalo_passado = data_fim.date() < hoje.date()
    data_meta_ref = data_inicio.replace(day=25)

    # Leitura da única aba (Planilha 1)
    df_base = pd.read_excel(caminho_arquivo_unificado)
    df_base.columns = df_base.columns.str.strip().str.lower()

    for col in ['cidade', 'regional', 'coordenador', 'canal']:
        if col in df_base.columns:
            df_base[col] = df_base[col].astype(str).str.strip().str.lower()

    # Separar adesão e ativação pela coluna de datas
    df_adesao_original = df_base.copy()
    df_ativacao_original = df_base.copy()

    df_adesao_original['data'] = pd.to_datetime(df_adesao_original['adesao'], dayfirst=True, errors='coerce')
    df_ativacao_original['data'] = pd.to_datetime(df_ativacao_original['ativacao'], dayfirst=True, errors='coerce')

    df_adesao_original = df_adesao_original[(df_adesao_original['data'] >= data_inicio) & (df_adesao_original['data'] <= data_fim)]
    df_ativacao_original = df_ativacao_original[(df_ativacao_original['data'] >= data_inicio) & (df_ativacao_original['data'] <= data_fim)]

    regionais_disponiveis = sorted(df_adesao_original['regional'].dropna().str.title().unique())
    coordenadores_disponiveis = sorted(df_adesao_original['coordenador'].dropna().str.title().unique())
    canais_disponiveis = sorted(df_adesao_original['canal'].dropna().str.title().unique())

    def aplicar_filtros(df):
        if regional:
            df = df[df.get('regional') == regional]
        if coordenador:
            df = df[df.get('coordenador') == coordenador]
        if canais:
            df = df[df.get('canal').isin(canais)]
        return df

    df_adesao = aplicar_filtros(df_adesao_original)
    df_ativacao = aplicar_filtros(df_ativacao_original)

    df_cancelamento = aplicar_filtros(pd.read_excel(cancelamento_path))
    df_cancelamento.columns = df_cancelamento.columns.str.strip().str.lower()
    df_cancelamento['data'] = pd.to_datetime(df_cancelamento['data'], dayfirst=True, errors='coerce')
    df_cancelamento = df_cancelamento[(df_cancelamento['data'] >= data_inicio) & (df_cancelamento['data'] <= data_fim)]

    def ler_meta(path, padroes, nome_coluna='meta', referencia=None):
        try:
            df = pd.read_excel(path)
        except Exception:
            return pd.DataFrame(columns=padroes + [nome_coluna])
        df.columns = df.columns.str.strip().str.lower()
        if 'data_meta' in df.columns:
            df['data_meta'] = pd.to_datetime(df['data_meta'], dayfirst=True, errors='coerce')
            if referencia is not None:
                df = df[df['data_meta'] == referencia]
        for col in padroes:
            df[col] = df[col].astype(str).str.strip().str.lower()
        df[nome_coluna] = pd.to_numeric(df.get(nome_coluna), errors='coerce').fillna(0)
        return aplicar_filtros(df)

    df_metas_adesao = ler_meta(metas_adesao_path, ['cidade', 'canal', 'regional', 'coordenador'], referencia=data_meta_ref)
    df_metas_ativacao = ler_meta(metas_ativacao_path, ['cidade', 'canal', 'regional', 'coordenador'], referencia=data_meta_ref)
    df_limite = ler_meta(limite_path, ['cidade', 'regional', 'coordenador'], referencia=data_meta_ref)

    for df in [df_adesao, df_ativacao]:
        df['canal'] = df['canal'].replace('externo', 'pap')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['receita'] = pd.to_numeric(df.get('receita'), errors='coerce').fillna(0)

    df_cancelamento['canal'] = 'interno'
    df_cancelamento['volume'] = pd.to_numeric(df_cancelamento['volume'], errors='coerce').fillna(0)

    dias = DiasUteis.objects.last()
    dias_uteis_passados = dias.dias_uteis_passados if dias else 1
    dias_uteis_restantes = dias.dias_uteis_restantes if dias else 1
    total_dias_uteis = dias_uteis_passados + dias_uteis_restantes

    def gerar_tabela(df_base, df_meta):
        grupo = df_base.groupby('canal', as_index=False).agg(realizado=('volume', 'sum'), receita=('receita', 'sum'))
        meta = df_meta.groupby('canal', as_index=False).agg(meta=('meta', 'sum'))
        canais = sorted(set(grupo['canal']) | set(meta['canal']))
        df_result = pd.DataFrame({'canal': canais}).merge(grupo, on='canal', how='left').merge(meta, on='canal', how='left')
        df_result.fillna(0, inplace=True)

        if intervalo_passado:
            df_result['projecao'] = df_result['realizado']
        else:
            df_result['projecao'] = (df_result['realizado'] / dias_uteis_passados) * total_dias_uteis

        df_result['projecao_percentual'] = (df_result['projecao'] / df_result['meta'].replace(0, 1)) * 100
        df_result['ticket_medio'] = df_result['receita'] / df_result['realizado'].replace(0, 1)
        df_result['ticket_medio'] = df_result['ticket_medio'].fillna(0)

        total = {
            'canal': 'total',
            'meta': df_result['meta'].sum(),
            'realizado': df_result['realizado'].sum(),
            'projecao': df_result['projecao'].sum(),
            'projecao_percentual': (df_result['projecao'].sum() / df_result['meta'].sum() * 100) if df_result['meta'].sum() else 0,
            'ticket_medio': (df_result['ticket_medio'] * df_result['realizado']).sum() / df_result['realizado'].sum() if df_result['realizado'].sum() else 0
        }

        tabela = df_result.round(1).to_dict(orient='records')
        tabela.append({k: round(v, 1) if isinstance(v, (float, int)) else v for k, v in total.items()})
        return tabela

    tabela_canal_adesao = gerar_tabela(df_adesao, df_metas_adesao)
    tabela_canal_ativacao = gerar_tabela(df_ativacao, df_metas_ativacao)

    cancelamento = df_cancelamento.groupby('cidade', as_index=False).agg(cancelamento_proj=('volume', 'sum'))
    cancelamento['cidade'] = cancelamento['cidade'].str.lower().str.strip()
    df_limite['cidade'] = df_limite['cidade'].str.lower().str.strip()
    cancelamento = cancelamento.merge(df_limite[['cidade', 'meta']], on='cidade', how='left').fillna(0)
    cancelamento['projecao_percentual'] = (cancelamento['cancelamento_proj'] / cancelamento['meta'].replace(0, 1)) * 100
    cancelamento = cancelamento.rename(columns={'meta': 'limite_cancelamento'})
    cancelamento['cidade'] = cancelamento['cidade'].str.title()
    painel_risco = cancelamento.sort_values(by='projecao_percentual', ascending=False).head(10).round(1).to_dict(orient='records')

    colunas_dias = pd.date_range(start=data_inicio, end=data_fim).strftime('%d/%m').tolist()
    df_tabela = pd.DataFrame(columns=colunas_dias)
    if not df_adesao.empty:
        df_adesao['data_formatada'] = df_adesao['data'].dt.strftime('%d/%m')
        tabela_dia = df_adesao.groupby(['canal', 'data_formatada'])['volume'].sum().unstack(fill_value=0)
        tabela_dia = tabela_dia.reindex(columns=colunas_dias, fill_value=0)
        df_tabela = tabela_dia.sort_index()
        df_tabela.index = df_tabela.index.str.title()
    if df_tabela.shape[1] > 0:
        df_tabela.loc['Total Realizado'] = df_tabela.sum(axis=0)

    context = {
        'tabela': df_tabela.reset_index().rename(columns={'index': 'canal'}).to_dict(orient='records'),
        'colunas_dias': colunas_dias,
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'canais_disponiveis': canais_disponiveis,
        'canais_selecionados': request.GET.getlist('canais'),
        'regionais': regionais_disponiveis,
        'regionais_selecionadas': [regional] if regional else [],
        'coordenadores': coordenadores_disponiveis,
        'coordenadores_selecionadas': [coordenador] if coordenador else [],
        'tabela_canal': tabela_canal_adesao,
        'tabela_canal_ativacao': tabela_canal_ativacao,
        'painel_risco': painel_risco,
    }

    return render(request, 'dashboard/diaadia.html', context)
