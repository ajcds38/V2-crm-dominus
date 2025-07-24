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
    data_inicio = pd.to_datetime(request.GET.get('data_inicio') or '2025-06-25')
    data_fim = pd.to_datetime(request.GET.get('data_fim') or '2025-07-24')
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

    df = aplicar_filtro(df, 'regional', regionais)
    df = aplicar_filtro(df, 'coordenador', coordenadores)
    df = aplicar_filtro(df, 'canal', canais)
    df = aplicar_filtro(df, 'cidade', cidades)
    df = aplicar_filtro(df, 'vendedor', vendedores)

    # Filtro combinado por tipo de status
    df_filtro = pd.concat([
        df[df['ativacao'].isna() & df['adesao'].between(data_inicio, data_fim)],
        df[df['ativacao'].notna() & df['ativacao'].between(data_inicio, data_fim)]
    ])

    # Ordenar: primeiro ❌, depois datas mais antigas
    df_filtro['ordem_ativacao'] = df_filtro['ativacao'].isna().astype(int)
    df_filtro = df_filtro.sort_values(by=['ordem_ativacao', 'ativacao', 'adesao'])

    # Resultado final por cliente
    df_resultado = df_filtro[['cliente', 'adesao', 'ativacao']].drop_duplicates(subset='cliente')
    df_resultado['adesao'] = df_resultado['adesao'].dt.strftime('%d/%m/%Y').fillna('')
    df_resultado['ativacao'] = df_resultado['ativacao'].apply(
        lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '<span style="color: white; background-color: red; padding: 2px 6px; border-radius: 4px;">❌</span>'
    )

    resultado = df_resultado.rename(columns={'cliente': 'nome'}).to_dict(orient='records')

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
