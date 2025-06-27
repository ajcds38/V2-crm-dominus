from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import pandas as pd
import os
from datetime import datetime, timedelta
from django.conf import settings
from diasuteis.models import DiasUteis

@login_required(login_url='/')
def dashboard_diaadia(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')

    # Caminhos
    adesao_path = os.path.join(base_path, 'adesao_realizado.xlsx')
    cancelamento_path = os.path.join(base_path, 'cancelamento_realizado.xlsx')
    metas_adesao_path = os.path.join(base_path, 'metas_adesao.xlsx')
    limite_path = os.path.join(base_path, 'limite_cancelamento.xlsx')
    ativacao_path = os.path.join(base_path, 'ativacao_realizado.xlsx')
    metas_ativacao_path = os.path.join(base_path, 'metas_ativacao.xlsx')

    # Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regional = request.GET.get('regional', '').strip().lower()
    coordenador = request.GET.get('coordenador', '').strip().lower()
    canais = [c.strip().lower() for c in request.GET.getlist('canais') if c.strip()]

    hoje = datetime.today()

    # Datas padrão
    if data_inicio:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim) if data_fim else (data_inicio + pd.DateOffset(months=1)).replace(day=24)
    else:
        if hoje.day < 25:
            data_inicio = (hoje.replace(day=1) - timedelta(days=1)).replace(day=25)
            data_fim = hoje.replace(day=24)
        else:
            data_inicio = hoje.replace(day=25)
            data_fim = (data_inicio + timedelta(days=40)).replace(day=24)

    if data_fim < data_inicio:
        data_inicio = data_fim - pd.DateOffset(months=1)

    intervalo_passado = data_fim.date() < hoje.date()
    data_meta_ref = data_inicio.replace(day=25)

    # Funções auxiliares
    def ler_df(path, padroes, data_col='data'):
        try:
            df = pd.read_excel(path)
        except Exception:
            return pd.DataFrame(columns=padroes + [data_col])

        df.columns = df.columns.str.strip().str.lower()
        for col in padroes:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
        if data_col in df.columns:
            df[data_col] = pd.to_datetime(df[data_col], dayfirst=True, errors='coerce')
            df = df[df[data_col].notna()]
        return df

    def ler_meta(path, padroes, nome_coluna='meta'):
        try:
            df = pd.read_excel(path)
        except Exception:
            return pd.DataFrame(columns=padroes + [nome_coluna])

        df.columns = df.columns.str.strip().str.lower()
        if 'data_meta' in df.columns:
            df['data_meta'] = pd.to_datetime(df['data_meta'], dayfirst=True, errors='coerce')
            df = df[df['data_meta'] == data_meta_ref]
        if df.empty:
            return pd.DataFrame(columns=padroes + [nome_coluna])
        for col in padroes:
            df[col] = df[col].astype(str).str.strip().str.lower()
        df[nome_coluna] = pd.to_numeric(df.get(nome_coluna), errors='coerce').fillna(0)
        return df

    def aplicar_filtros(df):
        if regional:
            df = df[df.get('regional') == regional]
        if coordenador:
            df = df[df.get('coordenador') == coordenador]
        if canais:
            df = df[df.get('canal').isin(canais)]
        return df

    # Leitura dos dados
    df_adesao = aplicar_filtros(ler_df(adesao_path, ['cidade', 'regional', 'coordenador', 'canal']))
    df_ativacao = aplicar_filtros(ler_df(ativacao_path, ['cidade', 'regional', 'coordenador', 'canal']))
    df_cancelamento = aplicar_filtros(ler_df(cancelamento_path, ['cidade', 'regional', 'coordenador', 'canal']))

    df_metas_adesao = aplicar_filtros(ler_meta(metas_adesao_path, ['cidade', 'canal', 'regional', 'coordenador']))
    df_metas_ativacao = aplicar_filtros(ler_meta(metas_ativacao_path, ['cidade', 'canal', 'regional', 'coordenador']))
    df_limite = aplicar_filtros(ler_meta(limite_path, ['cidade', 'regional', 'coordenador'], 'meta'))

    # Normalizações
    for df in [df_adesao, df_ativacao]:
        df['canal'] = df['canal'].replace('externo', 'pap')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['receita'] = pd.to_numeric(df.get('receita'), errors='coerce').fillna(0)

    df_cancelamento['canal'] = 'interno'
    df_cancelamento['volume'] = pd.to_numeric(df_cancelamento['volume'], errors='coerce').fillna(0)

    # Dias úteis
    dias = DiasUteis.objects.last()
    dias_uteis_passados = dias.dias_uteis_passados if dias else 1
    dias_uteis_restantes = dias.dias_uteis_restantes if dias else 1
    total_dias_uteis = dias_uteis_passados + dias_uteis_restantes

    # Geração de tabelas por canal
    def gerar_tabela(df_base, df_meta):
        df_base = df_base.copy()
        df_meta = df_meta.copy()
        grupo = df_base.groupby('canal', as_index=False).agg(
            realizado=('volume', 'sum'),
            receita=('receita', 'sum') if 'receita' in df_base.columns else ('volume', 'sum')
        )
        meta = df_meta.groupby('canal', as_index=False).agg(meta=('meta', 'sum'))
        canais = sorted(set(grupo['canal']) | set(meta['canal']))
        df_result = pd.DataFrame({'canal': canais}).merge(grupo, on='canal', how='left').merge(meta, on='canal', how='left')
        df_result.fillna(0, inplace=True)

        if intervalo_passado:
            df_result['projecao'] = df_result['realizado']
        else:
            df_result['projecao'] = (df_result['realizado'] / dias_uteis_passados) * total_dias_uteis

        df_result['projecao_percentual'] = (df_result['projecao'] / df_result['meta'].replace(0, 1)) * 100
        df_result['ticket_medio'] = df_result.apply(lambda r: r['receita'] / r['realizado'] if r['realizado'] else 0, axis=1)

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

    # Painel de risco
    cancelamento = df_cancelamento.groupby('cidade', as_index=False).agg(cancelamento_proj=('volume', 'sum'))
    cancelamento['cidade'] = cancelamento['cidade'].str.lower().str.strip()
    df_limite['cidade'] = df_limite['cidade'].str.lower().str.strip()
    cancelamento = cancelamento.merge(df_limite[['cidade', 'meta']], on='cidade', how='left').fillna(0)
    cancelamento['projecao_percentual'] = (cancelamento['cancelamento_proj'] / cancelamento['meta'].replace(0, 1)) * 100
    cancelamento = cancelamento.rename(columns={'meta': 'limite_cancelamento'})
    cancelamento['cidade'] = cancelamento['cidade'].str.title()
    painel_risco = cancelamento.sort_values(by='projecao_percentual', ascending=False).head(10).round(1).to_dict(orient='records')

    # Visão dia a dia por canal
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
        'canais_disponiveis': sorted(df_adesao['canal'].dropna().str.title().unique()),
        'canais_selecionados': request.GET.getlist('canais'),
        'regionais': sorted(df_adesao['regional'].dropna().str.title().unique()),
        'regionais_selecionadas': [regional] if regional else [],
        'coordenadores': sorted(df_adesao['coordenador'].dropna().str.title().unique()),
        'coordenadores_selecionadas': [coordenador] if coordenador else [],
        'tabela_canal': tabela_canal_adesao,
        'tabela_canal_ativacao': tabela_canal_ativacao,
        'painel_risco': painel_risco,
    }

    return render(request, 'dashboard/diaadia.html', context)
