from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import pandas as pd
import os
from django.conf import settings

@login_required(login_url='/login/')
def backlog_instalacoes(request):
    base_path = os.path.join(settings.BASE_DIR, 'crm_dominus', 'apps', 'dados')
    excel_path = os.path.join(base_path, 'Atualizacao_CRM.xlsx')

    df = pd.read_excel(excel_path)
    df.columns = df.columns.str.strip().str.lower()

    df = df.rename(columns={
        'nome do cliente': 'cliente',
        'adesao': 'adesao',
        'ativacao': 'ativacao',
        'município/uf': 'cidade',
        'consultor venda': 'vendedor'
    })

    # Padronização
    for col in ['cliente', 'cidade', 'vendedor', 'canal', 'regional', 'coordenador']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper().str.replace('\xa0', ' ')

    df['adesao'] = pd.to_datetime(df['adesao'], dayfirst=True, errors='coerce')
    df['ativacao'] = pd.to_datetime(df['ativacao'], dayfirst=True, errors='coerce')

    # Filtros GET
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regionais = request.GET.getlist('regional')
    coordenadores = request.GET.getlist('coordenador')
    canais = request.GET.getlist('canal')
    cidades = request.GET.getlist('cidade')
    vendedores = request.GET.getlist('vendedor')

    def aplicar_filtro(df, coluna, valores):
        valores_filtrados = [v.upper() for v in valores if v.strip().upper() not in ['', 'TODOS', 'TODAS']]
        if valores_filtrados:
            return df[df[coluna].isin(valores_filtrados)]
        return df

    # Filtro baseado apenas na coluna 'ativacao'
    if data_inicio and data_fim:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim)
        df = df[(df['ativacao'] >= data_inicio) & (df['ativacao'] <= data_fim)]

    df = aplicar_filtro(df, 'regional', regionais)
    df = aplicar_filtro(df, 'coordenador', coordenadores)
    df = aplicar_filtro(df, 'canal', canais)
    df = aplicar_filtro(df, 'cidade', cidades)
    df = aplicar_filtro(df, 'vendedor', vendedores)

    # Resultado final por cliente
    clientes = df['cliente'].dropna().unique()
    resultado = []

    for nome in sorted(clientes):
        cliente_df = df[df['cliente'] == nome]
        linha = cliente_df.iloc[0]

        adesao_formatada = linha['adesao'].strftime('%d/%m/%Y') if pd.notnull(linha['adesao']) else ''
        if pd.notnull(linha['ativacao']):
            ativacao_formatada = linha['ativacao'].strftime('%d/%m/%Y')
        else:
            ativacao_formatada = '<span style="color: white; background-color: red; padding: 2px 6px; border-radius: 4px;">❌</span>'

        resultado.append({
            'nome': nome.title(),
            'adesao': adesao_formatada,
            'ativacao': ativacao_formatada,
        })

    # Listas únicas para filtros
    lista_regionais = sorted(df['regional'].dropna().unique())
    lista_coordenadores = sorted(df['coordenador'].dropna().unique())
    lista_canais = sorted(df['canal'].dropna().unique())
    lista_cidades = sorted(df['cidade'].dropna().unique())
    lista_vendedores = sorted(df['vendedor'].dropna().unique())

    context = {
        'clientes': resultado,
        'filtros': {
            'data_inicio': request.GET.get('data_inicio', ''),
            'data_fim': request.GET.get('data_fim', ''),
            'regional': regionais,
            'coordenador': coordenadores,
            'canal': canais,
            'cidade': cidades,
            'vendedor': vendedores,
            'lista_regionais': lista_regionais,
            'lista_coordenadores': lista_coordenadores,
            'lista_canais': lista_canais,
            'lista_cidades': lista_cidades,
            'lista_vendedores': lista_vendedores,
        }
    }

    return render(request, 'backlog/index.html', context)
