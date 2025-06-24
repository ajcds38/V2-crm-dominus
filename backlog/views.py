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

    # Adiciona coluna de tipo
    df_adesao['tipo'] = 'adesao'
    df_ativacao['tipo'] = 'ativacao'

    # Junta as duas bases
    df_completo = pd.concat([df_adesao, df_ativacao], ignore_index=True)
    df = df_completo.copy()

    # Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    regionais = request.GET.getlist('regional')
    coordenadores = request.GET.getlist('coordenador')
    canais = request.GET.getlist('canal')
    cidades = request.GET.getlist('cidade')
    vendedores = request.GET.getlist('vendedor')

    if data_inicio and data_fim:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim)
        df = df[(df['data'] >= data_inicio) & (df['data'] <= data_fim)]

    def aplicar_filtro(df, coluna, valores):
        valores_filtrados = [v.upper() for v in valores if v.strip().upper() not in ['', 'TODOS', 'TODAS']]
        if valores_filtrados:
            return df[df[coluna].isin(valores_filtrados)]
        return df

    df = aplicar_filtro(df, 'regional', regionais)
    df = aplicar_filtro(df, 'coordenador', coordenadores)
    df = aplicar_filtro(df, 'canal', canais)
    df = aplicar_filtro(df, 'município/uf', cidades)
    df = aplicar_filtro(df, 'consultor venda', vendedores)

    # Cria lista final com status adesão/ativação
    clientes = df['cliente'].dropna().unique()
    resultado = []

    for nome in sorted(clientes):
        cliente_df = df[df['cliente'] == nome]
        tem_adesao = not cliente_df[cliente_df['tipo'] == 'adesao'].empty
        tem_ativacao = not cliente_df[cliente_df['tipo'] == 'ativacao'].empty

        resultado.append({
            'nome': nome.title(),
            'adesao': '✅' if tem_adesao else '<span style="color: white; background-color: red; padding: 2px 6px; border-radius: 4px;">❌</span>',
            'ativacao': '✅' if tem_ativacao else '<span style="color: white; background-color: red; padding: 2px 6px; border-radius: 4px;">❌</span>',
        })

    # Listas únicas SEM filtro para manter todas as opções no formulário
    lista_regionais = sorted(df_completo['regional'].dropna().unique())
    lista_coordenadores = sorted(df_completo['coordenador'].dropna().unique())
    lista_canais = sorted(df_completo['canal'].dropna().unique())
    lista_cidades = sorted(df_completo['município/uf'].dropna().unique())
    lista_vendedores = sorted(df_completo['consultor venda'].dropna().unique())

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
