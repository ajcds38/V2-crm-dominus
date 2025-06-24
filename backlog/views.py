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
    regional = request.GET.getlist('regional')
    coordenador = request.GET.getlist('coordenador')
    canal = request.GET.getlist('canal')
    cidade = request.GET.getlist('cidade')
    vendedor = request.GET.getlist('vendedor')

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
    df_adesao_filtrado = aplicar_filtro(df_adesao, 'regional', regional)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'coordenador', coordenador)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'canal', canal)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'município/uf', cidade)
    df_adesao_filtrado = aplicar_filtro(df_adesao_filtrado, 'consultor venda', vendedor)

    # Filtra ativação
    df_ativacao_filtrado = aplicar_filtro(df_ativacao, 'regional', regional)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'coordenador', coordenador)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'canal', canal)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'município/uf', cidade)
    df_ativacao_filtrado = aplicar_filtro(df_ativacao_filtrado, 'consultor venda', vendedor)

    # Coleta nomes únicos de ambas as bases
    nomes_adesao = set(df_adesao_filtrado['cliente'].dropna().unique())
    nomes_ativacao = set(df_ativacao_filtrado['cliente'].dropna().unique())
    todos_nomes = sorted(nomes_adesao.union(nomes_ativacao))

    # Lista de clientes com status
    resultado = []
    for nome in todos_nomes:
        resultado.append({
            'nome': nome.title(),
            'adesao': '✅' if nome in nomes_adesao else '<span style="color: white; background-color: red; padding: 2px 6px; border-radius: 4px;">❌</span>',
            'ativacao': '✅' if nome in nomes_ativacao else '<span style="color: white; background-color: red; padding: 2px 6px; border-radius: 4px;">❌</span>',
        })

    # Listas únicas para filtros
    lista_regionais = sorted(set(df_adesao['regional'].dropna()) | set(df_ativacao['regional'].dropna()))
    lista_coordenadores = sorted(set(df_adesao['coordenador'].dropna()) | set(df_ativacao['coordenador'].dropna()))
    lista_canais = sorted(set(df_adesao['canal'].dropna()) | set(df_ativacao['canal'].dropna()))
    lista_cidades = sorted(set(df_adesao['município/uf'].dropna()) | set(df_ativacao['município/uf'].dropna()))
    lista_vendedores = sorted(set(df_adesao['consultor venda'].dropna()) | set(df_ativacao['consultor venda'].dropna()))

    context = {
        'clientes': resultado,
        'filtros': {
            'data_inicio': request.GET.get('data_inicio', ''),
            'data_fim': request.GET.get('data_fim', ''),
            'regional': regional,
            'coordenador': coordenador,
            'canal': canal,
            'cidade': cidade,
            'vendedor': vendedor,
            'lista_regionais': lista_regionais,
            'lista_coordenadores': lista_coordenadores,
            'lista_canais': lista_canais,
            'lista_cidades': lista_cidades,
            'lista_vendedores': lista_vendedores,
        }
    }

    return render(request, 'backlog/index.html', context)
