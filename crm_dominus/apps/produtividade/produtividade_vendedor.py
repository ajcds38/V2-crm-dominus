from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import pandas as pd
import os
from django.conf import settings
from datetime import datetime, timedelta

@login_required(login_url='/')
def produtividade_vendedor(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')
    excel_path = os.path.join(base_path, 'adesao_produtividade.xlsx')

    df_original = pd.read_excel(excel_path)
    df_original.columns = df_original.columns.str.strip().str.lower()
    df_original = df_original.rename(columns={
        'data da adesão': 'data',
        'consultor venda': 'vendedor',
        'município/uf': 'cidade'
    })
    for col in ['vendedor', 'canal', 'regional', 'coordenador', 'cidade']:
        if col in df_original.columns:
            df_original[col] = df_original[col].astype(str).str.strip().str.upper()

    regionais = sorted(df_original['regional'].dropna().unique())
    coordenadores = sorted(df_original['coordenador'].dropna().unique())
    canais_disponiveis = sorted(df_original['canal'].dropna().unique())
    vendedores_disponiveis = sorted(df_original['vendedor'].dropna().unique())

    df = df_original.copy()
    df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['data'])

    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if not data_inicio or not data_fim:
        data_inicio = datetime(2025, 3, 25)
        data_fim = datetime(2025, 7, 24)
    else:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim)

    regional = request.GET.get('regional', '').strip().upper()
    coordenador = request.GET.get('coordenador', '').strip().upper()
    canais = request.GET.getlist('canal')
    vendedores = request.GET.getlist('vendedor')

    df = df[(df['data'] >= data_inicio) & (df['data'] <= data_fim)]

    if regional:
        df = df[df['regional'] == regional]
    if coordenador:
        df = df[df['coordenador'] == coordenador]
    if canais:
        canais = [c.upper() for c in canais]
        df = df[df['canal'].isin(canais)]
    if vendedores:
        vendedores = [v.upper() for v in vendedores]
        df = df[df['vendedor'].isin(vendedores)]

    def gerar_periodos(d_inicio, d_fim):
        periodos = []
        atual = d_inicio.replace(day=25)
        if d_inicio.day < 25:
            atual -= pd.DateOffset(months=1)
        while atual <= d_fim:
            proximo = atual + pd.DateOffset(months=1)
            fim_periodo = proximo - timedelta(days=1)
            periodos.append((atual, fim_periodo))
            atual = proximo
        return periodos

    def nome_coluna_periodo(inicio, fim):
        meses_pt = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
            7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        dias = pd.date_range(inicio, fim)
        meses = dias.to_series().dt.to_period("M")
        mais_frequente = meses.value_counts().idxmax()
        nome = f"{meses_pt[mais_frequente.month]}/{mais_frequente.year}"
        return nome

    periodos = gerar_periodos(data_inicio, data_fim)

    colunas = []
    coluna_ordem = []
    resultado = {}

    for vendedor in df['vendedor'].unique():
        linha = {}
        df_vend = df[df['vendedor'] == vendedor]
        for inicio, fim in periodos:
            nome_coluna = nome_coluna_periodo(inicio, fim)
            colunas.append(nome_coluna)
            coluna_ordem.append((inicio.year, inicio.month, nome_coluna))
            count = df_vend[(df_vend['data'] >= inicio) & (df_vend['data'] <= fim)].shape[0]
            linha[nome_coluna] = count
        resultado[vendedor] = linha

    colunas = [x[2] for x in sorted(set(coluna_ordem))]

    df_final = pd.DataFrame.from_dict(resultado, orient='index').fillna(0).astype(int)
    df_final.index.name = 'Vendedor'
    df_final = df_final.reset_index()
    df_final = df_final[['Vendedor'] + colunas]

    # Adiciona coluna Total por vendedor
    df_final['Total'] = df_final[colunas].sum(axis=1)

    # Linha TOTAL (produtividade média por mês)
    total = {}
    for mes in colunas:
        vendas_mes = df_final[mes]
        total_vendas = vendas_mes.sum()
        vendedores_com_venda = (vendas_mes > 0).sum()
        media = round(total_vendas / vendedores_com_venda, 2) if vendedores_com_venda else 0
        total[mes] = media
    total['Total'] = 0  # Ou soma real de total_vendas se desejar

    df_total = pd.DataFrame([['TOTAL'] + [total[mes] for mes in colunas] + [total['Total']]], columns=['Vendedor'] + colunas + ['Total'])
    df_final = pd.concat([df_final, df_total], ignore_index=True)

    context = {
        'data_inicio': data_inicio.strftime('%Y-%m-%d'),
        'data_fim': data_fim.strftime('%Y-%m-%d'),
        'df_tabela': df_final.to_dict(orient='records'),
        'colunas': ['Vendedor'] + colunas + ['Total'],
        'regionais': regionais,
        'coordenadores': coordenadores,
        'canais': canais_disponiveis,
        'vendedores': vendedores_disponiveis,
        'filtros_selecionados': {
            'regional': regional,
            'coordenador': coordenador,
            'canais': canais,
            'vendedores': vendedores,
        }
    }

    return render(request, 'produtividade_vendedor.html', context)
