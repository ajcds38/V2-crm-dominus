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
        'cliente': 'cliente',
        'adesao': 'adesao',
        'ativacao': 'ativacao',
        'cidade': 'cidade',
        'vendedores': 'vendedor'  # <- CORREÇÃO AQUI
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
        if valores_filtrados and coluna in df.columns:
            return df[df[coluna].isin(valores_filtrados)]
        return df

    if data_inicio and data_fim:
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim)
        df = df[(df['ativacao'] >= data_inicio) & (df['ativacao'] <= data_fim)]

    df = aplicar_filtro(df, 'regional', regionais)
    df = aplicar_filtro(df, 'coordenador', coordenadores)
    df = aplicar_filtro(df, 'canal', canais)
    df = aplicar_filtro(df, 'cidade', cidades)
    df = aplicar_filtro(df, 'vendedor', vendedores)

    # Resultado
    df_resultado = df[['cliente', 'adesao', 'ativacao']].drop_duplicates(subset='cliente')
    df_resultado['adesao'] = df_resultado['adesao'].dt.strftime('%d/%m/%Y').fillna('')
    df_resultado['ativacao'] = df_resultado['ativacao'].apply(
        lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x)
        else '<span style="color: white; background-color: red; padding: 2px 6px; border-radius: 4px;">❌</span>'
    )

    resultado = df_resultado.rename(columns={'cliente': 'nome'}).to_dict(orient='records')

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
            'lista_regionais': sorted(df['regional'].dropna().unique()) if 'regional' in df.columns else [],
            'lista_coordenadores': sorted(df['coordenador'].dropna().unique()) if 'coordenador' in df.columns else [],
            'lista_canais': sorted(df['canal'].dropna().unique()) if 'canal' in df.columns else [],
            'lista_cidades': sorted(df['cidade'].dropna().unique()) if 'cidade' in df.columns else [],
            'lista_vendedores': sorted(df['vendedor'].dropna().unique()) if 'vendedor' in df.columns else [],
        }
    }

    return render(request, 'backlog/index.html', context)
