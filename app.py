"""Radar de Entregas: painel em Streamlit sobre a camada analítica.

Rode antes (uma vez, precisa de Java):  python executar_pipeline.py
Depois (não precisa de Java):           streamlit run app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from otif import CalculadoraOTIF, Configuracao, RepositorioParquet  # noqa: E402
from otif.config import CAUSAS_FALHA, MESES  # noqa: E402

# Cores fixas por significado (paleta validada para daltonismo).
# OT = azul, IF = laranja, OTIF (indicador-síntese) = tinta neutra.
COR = {"OT": "#2a78d6", "IF": "#eb6834", "OTIF": "#3d3c38"}
COR_CAUSA = dict(zip(CAUSAS_FALHA, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))

st.set_page_config(page_title="Radar de Entregas", page_icon="🚚", layout="wide")


# ------------------------------------------------------------------ dados
@st.cache_data(show_spinner="Carregando a camada analítica...")
def carregar():
    repo = RepositorioParquet(Configuracao().pasta_analiticos)
    if not repo.existe("fato_visita"):
        return None
    tabelas = {n: repo.ler(n) for n in ["fato_visita", "dim_data", "agg_otif_mensal", "resumo_arquivos"]}
    tabelas["qualidade"] = repo.ler_json("relatorio_qualidade")
    return tabelas


def estilo(fig: go.Figure, altura: int = 360) -> go.Figure:
    fig.update_layout(
        height=altura, margin=dict(l=8, r=8, t=40, b=8), plot_bgcolor="white", paper_bgcolor="white",
        font=dict(size=13), legend=dict(orientation="h", y=1.12, x=0, title=None), hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, linecolor="#d4d3cf", title=None)
    fig.update_yaxes(gridcolor="#ecebe8", zeroline=False, title=None)
    return fig


def baixar(df: pd.DataFrame, nome: str) -> None:
    st.download_button("Baixar CSV", df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=f"{nome}.csv", mime="text/csv", key=f"dl-{nome}")


def rotulo_mes(ano_mes: pd.Series) -> pd.Series:
    """'2022-01' -> 'Jan/22'."""
    return ano_mes.map(lambda m: f"{MESES[int(m[5:7]) - 1]}/{m[2:4]}")


def pct(v: float) -> str:
    return f"{v:.1f}%".replace(".", ",")


def num(v: int) -> str:
    return f"{v:,}".replace(",", ".")


dados = carregar()
st.title("Radar de Entregas · Reposição de Mercadorias")
if dados is None:
    st.warning("A camada analítica ainda não existe. Rode `python executar_pipeline.py` e recarregue a página.")
    st.stop()

calc_total = CalculadoraOTIF(dados["fato_visita"], dados["dim_data"])
meses = calc_total.meses_disponiveis()

# ------------------------------------------------------------------ filtros
with st.sidebar:
    st.header("Filtros")
    inicio, fim = st.select_slider("Período (mês da entrega)", options=meses, value=(meses[0], meses[-1]),
                                   format_func=lambda m: rotulo_mes(pd.Series([m]))[0])
    cliente = st.text_input("Código do cliente (opcional)", placeholder="ex.: 0015111").strip()
    st.caption("Os arquivos de exemplo não têm dados de ago a dez/2023.")

calc = calc_total.filtrar(inicio, fim, cliente or None)
r = calc.resumo()
if r["visitas"] == 0:
    st.info("Nenhuma visita para os filtros escolhidos.")
    st.stop()

aba_geral, aba_clientes, aba_causas, aba_qualidade = st.tabs(
    ["Visão geral", "Clientes", "Causas das falhas", "Qualidade dos dados"]
)

# --------------------------------------------------------------- visão geral
with aba_geral:
    c = st.columns(5)
    c[0].metric("Visitas", num(r["visitas"]))
    c[1].metric("OTIF", pct(r["pct_otif"]))
    c[2].metric("No prazo (OT)", pct(r["pct_ot"]))
    c[3].metric("Completas (IF)", pct(r["pct_if"]))
    c[4].metric("Entregas com falha", num(r["falhas"]))

    mensal = calc.por_mes()
    st.subheader("OTIF, OT e IF por mês")
    fig = go.Figure()
    for col, nome in [("pct_otif", "OTIF"), ("pct_ot", "OT"), ("pct_if", "IF")]:
        fig.add_scatter(x=rotulo_mes(mensal["ano_mes"]), y=mensal[col], name=nome, mode="lines+markers",
                        line=dict(color=COR[nome], width=3 if nome == "OTIF" else 2),
                        marker=dict(size=8), hovertemplate="%{y:.1f}%")
    fig.update_xaxes(type="category")
    fig.update_yaxes(ticksuffix="%")
    st.plotly_chart(estilo(fig), use_container_width=True)

    dias = calc.por_dia_semana()
    pior = dias.loc[dias["pct_falha"].idxmax()]
    st.subheader(f"Falhas por dia da semana: {pior['nome_dia_semana'].lower()} é o pior dia "
                 f"({pct(pior['pct_falha'])} das visitas)")
    fig = px.bar(dias, x="nome_dia_semana", y="pct_falha", color_discrete_sequence=[COR["OTIF"]],
                 text=dias["pct_falha"].map(pct), hover_data={"visitas": ":,"})
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(ticksuffix="%", range=[0, dias["pct_falha"].max() * 1.25])
    fig = estilo(fig, 280)
    fig.update_layout(hovermode="closest")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Relatório mensal de OT, IF e OTIF (todos os clientes)")
    st.caption("Tabela agregada pelo Spark durante o processamento.")
    relatorio = dados["agg_otif_mensal"]
    relatorio = relatorio[relatorio["ano_mes"].between(inicio, fim)]
    st.dataframe(relatorio, use_container_width=True, hide_index=True, column_config={
        "ano_mes": "Mês", "visitas": "Visitas",
        "pct_ot": st.column_config.NumberColumn("OT %", format="%.2f"),
        "pct_if": st.column_config.NumberColumn("IF %", format="%.2f"),
        "pct_otif": st.column_config.NumberColumn("OTIF %", format="%.2f"),
    })
    baixar(relatorio, "relatorio_mensal_otif")

# ------------------------------------------------------------------- clientes
with aba_clientes:
    if cliente:
        st.info("Limpe o filtro de cliente para comparar os clientes entre si.")
    else:
        conc = calc.concentracao_falhas(0.10)
        st.subheader(f"10% dos clientes concentram {pct(conc)} das falhas")
        pareto = calc.curva_pareto_clientes()
        fig = go.Figure()
        fig.add_scatter(x=pareto["pct_clientes"], y=pareto["pct_falhas_acumuladas"], mode="lines",
                        line=dict(color=COR["OTIF"], width=2), name="Falhas acumuladas",
                        hovertemplate="%{x:.1f}% dos clientes → %{y:.1f}% das falhas<extra></extra>")
        fig.add_scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color="#b5b4ae", dash="dot", width=1),
                        name="Se as falhas fossem iguais entre clientes", hoverinfo="skip")
        fig.update_xaxes(ticksuffix="%", title="Clientes (do que mais falha ao que menos falha)")
        fig.update_yaxes(ticksuffix="%", range=[0, 101])
        fig = estilo(fig, 340)
        fig.update_layout(hovermode="closest")
        st.plotly_chart(fig, use_container_width=True)

        esq, dir_ = st.columns([1, 2])
        minimo = esq.slider("Mínimo de visitas do cliente", 1, 200, 20)
        ordem = dir_.radio("Ordenar por", ["Mais falhas (volume)", "Maior taxa de falha (clientes críticos)"],
                           horizontal=True)
        ranking = calc.ranking_clientes(minimo, "falhas" if ordem.startswith("Mais") else "pct_falha")
        st.dataframe(ranking.head(200), use_container_width=True, hide_index=True, column_config={
            "cliente": "Cliente", "visitas": "Visitas", "falhas": "Falhas", "causa_principal": "Causa principal",
            "pct_falha": st.column_config.ProgressColumn("% de falha", format="%.1f", min_value=0, max_value=100),
            "participacao_falhas": st.column_config.NumberColumn("% do total de falhas", format="%.2f"),
        })
        baixar(ranking, "ranking_clientes")

# ------------------------------------------------------------------- causas
with aba_causas:
    esq, dir_ = st.columns([1, 2])
    causas = calc.por_causa()
    with esq:
        st.subheader("Por que as entregas falham")
        fig = px.bar(causas, x="falhas", y="causa", orientation="h", color="causa",
                     color_discrete_map=COR_CAUSA, text=causas["participacao"].map(pct))
        fig.update_traces(textposition="outside", cliponaxis=False, hovertemplate="%{x:,} falhas")
        fig.update_layout(showlegend=False, hovermode="closest")
        fig.update_yaxes(categoryorder="array", categoryarray=CAUSAS_FALHA[::-1])
        fig.update_xaxes(range=[0, causas["falhas"].max() * 1.35], showticklabels=False)
        st.plotly_chart(estilo(fig, 320), use_container_width=True)
        st.caption("Entrega não realizada: visita com mapa 000000, contada como falha de OT, IF e OTIF.")
    with dir_:
        st.subheader("Falhas por mês e por causa")
        mc = calc.por_mes_e_causa()
        mc["mes"] = rotulo_mes(mc["ano_mes"])
        fig = px.bar(mc, x="mes", y="falhas", color="causa", color_discrete_map=COR_CAUSA,
                     category_orders={"causa": CAUSAS_FALHA})
        fig.update_xaxes(type="category")
        fig.update_traces(marker_line_color="white", marker_line_width=1)
        st.plotly_chart(estilo(fig, 320), use_container_width=True)

# ------------------------------------------------------------------ qualidade
with aba_qualidade:
    q = dados["qualidade"]
    st.subheader("O que foi encontrado nos arquivos")
    c = st.columns(4)
    c[0].metric("Arquivos importados", num(q["arquivos_encontrados"] - len(q["arquivos_descartados"])))
    c[1].metric("Linhas válidas", num(q["linhas_validas"]))
    c[2].metric("Entregas não realizadas", num(q["entregas_nao_realizadas"]))
    c[3].metric("Clientes", num(q["clientes_distintos"]))
    itens = [
        ("Arquivos descartados (nome sem o mês)", ", ".join(q["arquivos_descartados"]) or "nenhum"),
        ("Datas inválidas", q["datas_invalidas"]),
        ("Linhas com data fora do mês do arquivo", q["linhas_fora_do_mes"]),
        ("Linhas em que OTIF difere de OT e IF", q["violacoes_regra_otif"]),
        ("Meses sem arquivo", ", ".join(q["meses_faltantes"]) or "nenhum"),
        ("Período", f"{q['periodo_inicio']} a {q['periodo_fim']}"),
    ]
    st.table(pd.DataFrame(itens, columns=["Verificação", "Resultado"]).astype(str))
    st.subheader("Arquivos")
    st.dataframe(dados["resumo_arquivos"], use_container_width=True, hide_index=True, column_config={
        "arquivo": "Arquivo", "mes": "Mês", "linhas": "Linhas", "situacao": "Situação"})
