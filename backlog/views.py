from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import pandas as pd
import os
from django.conf import settings

@login_required(login_url='/login/')
def backlog_instalacoes(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')

    adesao_path = os.path.join(base_path, 'backlog_adesao.xlsx')
    ativacao_path = os.path.join(base_path, 'backlog_ativacao.xlsx')

    df_adesao = pd.read_excel(adesao_path)
    df_ativacao = pd.read_excel(ativacao_path)

    # Padroniza colunas
    for df in [df_adesao, df_ativacao]:
        df.columns = df.columns.str.strip().str.lower()
        for col in ['cliente', 'município/uf', 'consultor venda', 'canal', 'regional', 'coordenador']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.upper()
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'], dayfirst=True, errors='coerce')

    # Filtros da URL
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regionais = request.GET.getlist('regional')
    coordenadores = request.GET.getlist('coordenador')
    canais = request.GET.getlist('canal')
    cidades = request.GET.getlist('cidade')
    vendedores = request.GET.getlist('vendedor')

    # Aplicar filtros de data
    if data_inicio and data_fim:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim)
        df_adesao = df_adesao[(df_adesao['data'] >= data_inicio) & (df_adesao['data'] <= data_fim)]
        df_ativacao = df_ativacao[(df_ativacao['data'] >= data_inicio) & (df_ativacao['data'] <= data_fim)]

    # Função para aplicar múltiplos filtros
    def aplicar_filtro(df, coluna, valores):
        if valores:
            return df[df[coluna].isin([v.upper() for v in valores])]
        return df

    # Filtra adesão
    df_adesao_filtrado = aplicar_filtro(df_adesao, 'regional', regionais)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'coordenador', coordenadores)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'canal', canais)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'município/uf', cidades)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'consultor venda', vendedores)

    # Filtra ativação
    df_ativacao_filtrado = aplicar_filtro(df_ativacao, 'regional', regionais)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'coordenador', coordenadores)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'canal', canais)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'município/uf', cidades)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'consultor venda', vendedores)

    # Coleta nomes dos clientes mesmo que só estejam em uma base
    nomes_adesao = set(df_adesao_filtrado['cliente'].unique())
    nomes_ativacao = set(df_ativacao_filtrado['cliente'].unique())
    todos_nomes = sorted(nomes_adesao.union(nomes_ativacao))

    resultado = []
    for nome in todos_nomes:
        resultado.append({
            'nome': nome.title(),
            'adesao': '✅' if nome in nomes_adesao else '❌',
            'ativacao': '✅' if nome in nomes_ativacao else '❌',
        })

    # Listas únicas para montar os filtros
    lista_regionais = sorted(set(df_adesao['regional'].dropna().tolist() + df_ativacao['regional'].dropna().tolist()))
    lista_coordenadores = sorted(set(df_adesao['coordenador'].dropna().tolist() + df_ativacao['coordenador'].dropna().tolist()))
    lista_canais = sorted(set(df_adesao['canal'].dropna().tolist() + df_ativacao['canal'].dropna().tolist()))
    lista_cidades = sorted(set(df_adesao['município/uf'].dropna().tolist() + df_ativacao['município/uf'].dropna().tolist()))
    lista_vendedores = sorted(set(df_adesao['consultor venda'].dropna().tolist() + df_ativacao['consultor venda'].dropna().tolist()))

    context = {
        'clientes': resultado,
        'filtros': {
            'data_inicio': request.GET.get('data_inicio', ''),
            'data_fim': request.GET.get('data_fim', ''),
            'regionais': regionais,
            'coordenadores': coordenadores,
            'canais': canais,
            'cidades': cidades,
            'vendedores': vendedores,
            'lista_regionais': lista_regionais,
            'lista_coordenadores': lista_coordenadores,
            'lista_canais': lista_canais,
            'lista_cidades': lista_cidades,
            'lista_vendedores': lista_vendedores,
        }
    }

    return render(request, 'backlog/index.html', context)
