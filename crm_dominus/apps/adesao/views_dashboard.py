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

    adesao_path = os.path.join(base_path, 'adesao_realizado.xlsx')
    cancelamento_path = os.path.join(base_path, 'cancelamento_realizado.xlsx')
    metas_adesao_path = os.path.join(base_path, 'metas_adesao.xlsx')
    limite_path = os.path.join(base_path, 'limite_cancelamento.xlsx')
    ativacao_path = os.path.join(base_path, 'ativacao_realizado.xlsx')
    metas_ativacao_path = os.path.join(base_path, 'metas_ativacao.xlsx')

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regional = request.GET.get('regional', '')
    coordenador = request.GET.get('coordenador', '')
    canais = request.GET.getlist('canais')

    hoje = datetime.today()

    if data_inicio:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim) if data_fim else (data_inicio + pd.DateOffset(months=1)).replace(day=24)
    else:
        if hoje.day < 25:
            data_inicio = (hoje.replace(day=1) - timedelta(days=1)).replace(day=25)
            data_fim = hoje.replace(day=24)
        else:
            data_inicio = hoje.replace(day=25)
            proximo_mes = (hoje.replace(day=28) + timedelta(days=4)).replace(day=1)
            data_fim = proximo_mes.replace(day=24)

    if data_fim < data_inicio:
        data_inicio = data_fim - pd.DateOffset(months=1)

    intervalo_passado = data_fim.date() < hoje.date()

    def preparar_df(path, colunas_padrao, data_col='data'):
        df = pd.read_excel(path)
        df.columns = df.columns.str.strip().str.lower()
        if data_col in df.columns:
            df[data_col] = pd.to_datetime(df[data_col], dayfirst=True, errors='coerce')
            df = df[df[data_col].notna()]
        for col in colunas_padrao:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
        return df

    df_real = preparar_df(adesao_path, ['cidade', 'regional', 'coordenador', 'canal'])
    df_ativacao = preparar_df(ativacao_path, ['cidade', 'regional', 'coordenador', 'canal'])
    df_cancelamento = preparar_df(cancelamento_path, ['cidade', 'regional', 'coordenador', 'canal'])

    df_real['canal'] = df_real['canal'].replace('externo', 'pap')
    df_real['volume'] = pd.to_numeric(df_real['volume'], errors='coerce').fillna(0)
    df_real['receita'] = pd.to_numeric(df_real['receita'], errors='coerce').fillna(0) if 'receita' in df_real.columns else 0

    df_ativacao['canal'] = df_ativacao['canal'].replace('externo', 'pap')
    df_ativacao['volume'] = pd.to_numeric(df_ativacao['volume'], errors='coerce').fillna(0)

    df_cancelamento['volume'] = pd.to_numeric(df_cancelamento['volume'], errors='coerce').fillna(0)
    df_cancelamento['canal'] = 'interno'

    data_meta_ref = data_inicio.replace(day=25)

    def preparar_meta(path, padroes, nome_coluna='meta'):
        df = pd.read_excel(path)
        df.columns = df.columns.str.strip().str.lower()
        df['data_meta'] = pd.to_datetime(df.get('data_meta'), dayfirst=True, errors='coerce')
        df = df[df['data_meta'] == data_meta_ref] if 'data_meta' in df.columns else df.iloc[0:0]
        if df.empty:
            df = pd.DataFrame(columns=padroes + [nome_coluna])
        for col in padroes:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
        df[nome_coluna] = pd.to_numeric(df.get(nome_coluna), errors='coerce').fillna(0)
        return df

    df_metas = preparar_meta(metas_adesao_path, ['cidade', 'canal', 'regional', 'coordenador'])
    df_metas['canal'] = df_metas['canal'].replace('externo', 'pap')

    df_metas_ativacao = preparar_meta(metas_ativacao_path, ['cidade', 'canal', 'regional', 'coordenador'])
    df_metas_ativacao['canal'] = df_metas_ativacao['canal'].replace('externo', 'pap')

    df_limite = preparar_meta(limite_path, ['cidade', 'regional', 'coordenador'])

    def aplicar_filtros(df, filtros):
        for col, valor in filtros.items():
            if valor:
                df = df[df[col] == valor.strip().lower()]
        return df

    filtros = {'regional': regional, 'coordenador': coordenador}
    df_real = aplicar_filtros(df_real, filtros)
    df_metas = aplicar_filtros(df_metas, filtros)
    df_cancelamento = aplicar_filtros(df_cancelamento, filtros)
    df_limite = aplicar_filtros(df_limite, filtros)
    df_ativacao = aplicar_filtros(df_ativacao, filtros)
    df_metas_ativacao = aplicar_filtros(df_metas_ativacao, filtros)

    canais_lower = [c.strip().lower() for c in canais]
    if canais_lower:
        df_real = df_real[df_real['canal'].isin(canais_lower)]
        df_metas = df_metas[df_metas['canal'].isin(canais_lower)]
        df_ativacao = df_ativacao[df_ativacao['canal'].isin(canais_lower)]
        df_metas_ativacao = df_metas_ativacao[df_metas_ativacao['canal'].isin(canais_lower)]

    dias = DiasUteis.objects.last()
    dias_uteis_passados = dias.dias_uteis_passados if dias else 1
    dias_uteis_restantes = dias.dias_uteis_restantes if dias else 1

    def gerar_tabela_canal(df_base, df_meta):
        canal_agrupado = df_base.groupby('canal', as_index=False).agg(
            realizado=('volume', 'sum'),
            receita=('receita', 'sum') if 'receita' in df_base.columns else ('volume', 'sum')
        )
        metas_agrupadas = df_meta.groupby('canal', as_index=False).agg(meta=('meta', 'sum'))
        df_canais = pd.DataFrame({'canal': sorted(set(df_base['canal']) | set(df_meta['canal']))})
        canal_agrupado = df_canais.merge(canal_agrupado, on='canal', how='left').merge(metas_agrupadas, on='canal', how='left')
        canal_agrupado = canal_agrupado.fillna(0)

        if intervalo_passado:
            canal_agrupado['projecao'] = canal_agrupado['realizado']
        else:
            canal_agrupado['projecao'] = (canal_agrupado['realizado'] / dias_uteis_passados) * (dias_uteis_passados + dias_uteis_restantes)

        canal_agrupado['projecao_percentual'] = (canal_agrupado['projecao'] / canal_agrupado['meta'].replace(0, 1)) * 100
        canal_agrupado['ticket_medio'] = canal_agrupado.apply(
            lambda row: row['receita'] / row['realizado'] if row['realizado'] > 0 else 0,
            axis=1
        )
        total_meta = canal_agrupado['meta'].sum()
        total_realizado = canal_agrupado['realizado'].sum()
        total_projecao = canal_agrupado['projecao'].sum()
        total_projecao_percentual = (total_projecao / total_meta * 100) if total_meta else 0
        total_ticket_medio = (
            (canal_agrupado['ticket_medio'] * canal_agrupado['realizado']).sum() / total_realizado
            if total_realizado > 0 else 0
        )
        totais = {
            'canal': 'total',
            'meta': round(total_meta, 1),
            'realizado': round(total_realizado, 1),
            'projecao': round(total_projecao, 1),
            'projecao_percentual': round(total_projecao_percentual, 1),
            'ticket_medio': round(total_ticket_medio, 2)
        }
        tabela = canal_agrupado.round(1).to_dict(orient='records')
        tabela.append(totais)
        return tabela

    tabela_canal_adesao = gerar_tabela_canal(df_real, df_metas)
    tabela_canal_ativacao = gerar_tabela_canal(df_ativacao, df_metas_ativacao)

    # Cancelamento (sem alteração na lógica de projeção)
    cancelamento_agrupado = df_cancelamento.groupby('cidade', as_index=False).agg(cancelamento_proj=('volume', 'sum'))
    cancelamento_agrupado['cidade'] = cancelamento_agrupado['cidade'].str.strip().str.lower()
    df_limite['cidade'] = df_limite['cidade'].str.strip().str.lower()
    cancelamento_agrupado = cancelamento_agrupado.merge(df_limite[['cidade', 'meta']], on='cidade', how='left')
    cancelamento_agrupado['meta'] = cancelamento_agrupado['meta'].fillna(0)
    cancelamento_agrupado['projecao_percentual'] = (cancelamento_agrupado['cancelamento_proj'] / cancelamento_agrupado['meta'].replace(0, 1)) * 100
    cancelamento_agrupado = cancelamento_agrupado.rename(columns={'meta': 'limite_cancelamento'})
    cancelamento_agrupado['cidade'] = cancelamento_agrupado['cidade'].str.title()
    painel_risco = cancelamento_agrupado.sort_values(by='projecao_percentual', ascending=False).head(10)
    painel_risco = painel_risco.fillna(0).round(1).to_dict(orient='records')

    todas_datas = pd.date_range(start=data_inicio, end=data_fim).date
    colunas_dias = [data.strftime('%d/%m') for data in todas_datas]
    df_tabela = pd.DataFrame(index=[], columns=colunas_dias)
    if not df_real.empty:
        df_real['data_formatada'] = df_real['data'].dt.strftime('%d/%m')
        df_temp = df_real.groupby(['canal', 'data_formatada'])['volume'].sum().unstack(fill_value=0)
        df_temp = df_temp.reindex(columns=colunas_dias, fill_value=0)
        df_tabela = df_temp.sort_index()
        df_tabela.index = df_tabela.index.str.title()
    if df_tabela.shape[1] > 0:
        df_tabela.loc['Total Realizado'] = df_tabela.sum(axis=0)

    context = {
        'tabela': df_tabela.reset_index().rename(columns={'index': 'canal'}).to_dict(orient='records'),
        'colunas_dias': colunas_dias,
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'canais_disponiveis': sorted(df_real['canal'].dropna().str.title().unique()),
        'canais_selecionados': canais,
        'regionais': sorted(df_real['regional'].dropna().str.title().unique()),
        'regionais_selecionadas': [regional] if regional else [],
        'coordenadores': sorted(df_real['coordenador'].dropna().str.title().unique()),
        'coordenadores_selecionadas': [coordenador] if coordenador else [],
        'tabela_canal': tabela_canal_adesao,
        'tabela_canal_ativacao': tabela_canal_ativacao,
        'painel_risco': painel_risco,
    }

    return render(request, 'dashboard/diaadia.html', context)
