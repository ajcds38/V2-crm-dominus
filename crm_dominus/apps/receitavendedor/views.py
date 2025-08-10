import os
import pandas as pd
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_ATUALIZACAO = os.path.abspath(
    os.path.join(BASE_DIR, '..', 'dados', 'Atualizacao_CRM.xlsx')
)

def _norm(x):
    return str(x).strip().upper() if pd.notna(x) else ""

def _pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

@login_required
def receita_por_vendedor(request):
    # mesmos nomes esperados pelo template de ativação por vendedor
    data_inicio_str = request.GET.get('inicio', '2025-07-25')
    data_fim_str    = request.GET.get('fim', '2025-08-24')

    # selects simples (um valor) – manter listas *_selecionadas para compatibilidade
    regional_sel = request.GET.get('regional', '').strip()
    coordenador_sel = request.GET.get('coordenador', '').strip()
    canais_sel = [c.strip() for c in request.GET.getlist('canal') if c]

    data_inicio = pd.to_datetime(data_inicio_str)
    data_fim = pd.to_datetime(data_fim_str)

    erro_msg = None
    try:
        df = pd.read_excel(CAMINHO_ATUALIZACAO)
    except Exception as e:
        df = pd.DataFrame()
        erro_msg = f"Erro ao abrir {os.path.basename(CAMINHO_ATUALIZACAO)}: {e}"

    tabela = []
    regionais = coordenadores = canais = []
    if not df.empty:
        df.columns = [str(c).strip().lower() for c in df.columns]

        col_vendedor = _pick_col(df, ['vendedores', 'vendedor'])
        col_ativacao = _pick_col(df, ['ativacao', 'data_ativacao'])
        col_regional = _pick_col(df, ['regional'])
        col_coord    = _pick_col(df, ['coordenador', 'coord', 'coordenador_vendas'])
        col_canal    = _pick_col(df, ['canal'])
        col_receita  = _pick_col(df, ['receita', 'valor', 'valor_total', 'preco', 'faturamento'])

        faltas = []
        if not col_vendedor: faltas.append("vendedores/vendedor")
        if not col_ativacao: faltas.append("ativacao/data_ativacao")
        if not col_receita:  faltas.append("receita/valor/valor_total")
        if faltas:
            erro_msg = "Não encontrei colunas: " + ", ".join(faltas) + "."
        else:
            # normalização e filtros
            df[col_ativacao] = pd.to_datetime(df[col_ativacao], errors='coerce')
            df = df.dropna(subset=[col_ativacao])
            df = df[(df[col_ativacao] >= data_inicio) & (df[col_ativacao] <= data_fim)]

            df[col_vendedor] = df[col_vendedor].astype(str).str.strip()

            if col_regional:   df[col_regional] = df[col_regional].map(_norm)
            if col_coord:      df[col_coord]    = df[col_coord].map(_norm)
            if col_canal:      df[col_canal]    = df[col_canal].map(_norm)

            # opções para os selects
            regionais = sorted(df[col_regional].dropna().unique().tolist()) if col_regional else []
            coordenadores = sorted(df[col_coord].dropna().unique().tolist()) if col_coord else []
            canais = sorted(df[col_canal].dropna().unique().tolist()) if col_canal else []

            # aplica filtros selecionados
            if regional_sel and col_regional:
                df = df[df[col_regional] == _norm(regional_sel)]
            if coordenador_sel and col_coord:
                df = df[df[col_coord] == _norm(coordenador_sel)]
            if canais_sel and col_canal:
                df = df[df[col_canal].isin([_norm(x) for x in canais_sel])]

            # numérico
            df[col_receita] = pd.to_numeric(df[col_receita], errors='coerce').fillna(0)

            # agregação
            receita = df.groupby(col_vendedor, dropna=False)[col_receita].sum().rename('receita_total')
            volume  = df.groupby(col_vendedor, dropna=False).size().rename('volume')
            grp = (
                pd.concat([receita, volume], axis=1)
                .sort_values('receita_total', ascending=False)
                .reset_index()
                .rename(columns={col_vendedor: 'vendedor'})
            )
            grp['ticket_medio'] = grp.apply(lambda r: (r['receita_total'] / r['volume']) if r['volume'] else 0, axis=1)

            # totais
            total_row = pd.DataFrame([{
                'vendedor': 'TOTAL',
                'receita_total': float(grp['receita_total'].sum()),
                'volume': int(grp['volume'].sum()),
                'ticket_medio': float(grp['receita_total'].sum()) / int(grp['volume'].sum()) if int(grp['volume'].sum()) else 0.0
            }])

            tabela = pd.concat([grp, total_row], ignore_index=True).to_dict(orient='records')

    contexto = {
        # variáveis esperadas pelo template de ativação
        'data_inicio': data_inicio_str,
        'data_fim': data_fim_str,
        'regionais': regionais,
        'coordenadores': coordenadores,
        'canais': canais,
        'regionais_selecionadas': [ _norm(regional_sel) ] if regional_sel else [],
        'coordenadores_selecionadas': [ _norm(coordenador_sel) ] if coordenador_sel else [],
        'canais_selecionadas': [ _norm(x) for x in canais_sel ],
        # dados da tabela
        'tabela': tabela,
        # opcional: exibir mensagem se algo faltar
        'erro': erro_msg,
    }
    return render(request, 'receitavendedor/receita_por_vendedor.html', contexto)
