"""Cálculo dos indicadores OT, IF e OTIF sobre a camada analítica."""
from __future__ import annotations

import pandas as pd

from .config import CAUSAS_FALHA


class CalculadoraOTIF:
    """Responde às perguntas do painel: quanto, quando, com quem e por que as entregas falham."""

    def __init__(self, fato: pd.DataFrame, dim_data: pd.DataFrame):
        datas = dim_data[["data_key", "data", "ano_mes", "dia_semana", "nome_dia_semana"]]
        self.base = fato.merge(datas, on="data_key", how="left")
        self.base["falha"] = ~self.base["otif"]

    def filtrar(self, mes_inicio: str | None = None, mes_fim: str | None = None,
                cliente: str | None = None) -> "CalculadoraOTIF":
        """Devolve uma nova calculadora só com o período (AAAA-MM) e o cliente escolhidos."""
        b = self.base
        if mes_inicio:
            b = b[b["ano_mes"] >= mes_inicio]
        if mes_fim:
            b = b[b["ano_mes"] <= mes_fim]
        if cliente:
            b = b[b["cliente_key"] == cliente]
        nova = CalculadoraOTIF.__new__(CalculadoraOTIF)
        nova.base = b
        return nova

    def meses_disponiveis(self) -> list[str]:
        return sorted(self.base["ano_mes"].unique())

    # --------------------------------------------------------------- indicadores
    @staticmethod
    def _taxas(grupos) -> pd.DataFrame:
        """Visitas, falhas e percentuais de OT, IF e OTIF de cada grupo."""
        r = grupos.agg(visitas=("id_visita", "size"), falhas=("falha", "sum"),
                       pct_ot=("ot", "mean"), pct_if=("if_", "mean"), pct_otif=("otif", "mean"))
        for c in ["pct_ot", "pct_if", "pct_otif"]:
            r[c] = (r[c] * 100).round(2)
        r["pct_falha"] = (100 - r["pct_otif"]).round(2)
        return r

    def resumo(self) -> dict:
        b = self.base
        if b.empty:
            return {"visitas": 0, "falhas": 0, "clientes": 0, "pct_ot": 0.0, "pct_if": 0.0, "pct_otif": 0.0}
        return {
            "visitas": int(len(b)),
            "falhas": int(b["falha"].sum()),
            "clientes": int(b["cliente_key"].nunique()),
            "pct_ot": round(b["ot"].mean() * 100, 2),
            "pct_if": round(b["if_"].mean() * 100, 2),
            "pct_otif": round(b["otif"].mean() * 100, 2),
        }

    def por_mes(self) -> pd.DataFrame:
        return self._taxas(self.base.groupby("ano_mes")).reset_index()

    def por_dia_semana(self) -> pd.DataFrame:
        r = self._taxas(self.base.groupby(["dia_semana", "nome_dia_semana"])).reset_index()
        return r.sort_values("dia_semana").drop(columns="dia_semana").reset_index(drop=True)

    def por_causa(self) -> pd.DataFrame:
        """Quantidade e participação de cada causa nas falhas."""
        f = self.base[self.base["falha"]]
        r = f["causa"].value_counts().reindex(CAUSAS_FALHA, fill_value=0).rename_axis("causa")
        r = r.reset_index(name="falhas")
        r["participacao"] = (r["falhas"] / max(len(f), 1) * 100).round(2)
        return r

    def por_mes_e_causa(self) -> pd.DataFrame:
        f = self.base[self.base["falha"]]
        return f.groupby(["ano_mes", "causa"]).size().reset_index(name="falhas")

    # ------------------------------------------------------------------ clientes
    def ranking_clientes(self, minimo_visitas: int = 20, ordenar_por: str = "falhas") -> pd.DataFrame:
        """Clientes com pelo menos `minimo_visitas`, ordenados pelo número de falhas ("falhas")
        ou pela taxa de falha ("pct_falha", os clientes críticos), com a causa mais frequente."""
        r = self._taxas(self.base.groupby("cliente_key")).reset_index()
        falhas = self.base[self.base["falha"]]
        causa = falhas.groupby("cliente_key")["causa"].agg(lambda s: s.value_counts().index[0])
        r["causa_principal"] = r["cliente_key"].map(causa).fillna("-")
        r["participacao_falhas"] = (r["falhas"] / max(len(falhas), 1) * 100).round(2)
        r = r[r["visitas"] >= minimo_visitas]
        r = r.sort_values([ordenar_por, "visitas"], ascending=[False, False])
        colunas = ["cliente_key", "visitas", "falhas", "pct_falha", "causa_principal", "participacao_falhas"]
        return r[colunas].rename(columns={"cliente_key": "cliente"}).reset_index(drop=True)

    def curva_pareto_clientes(self) -> pd.DataFrame:
        """Percentual acumulado de falhas contra percentual acumulado de clientes."""
        f = self.base.groupby("cliente_key")["falha"].sum().sort_values(ascending=False)
        total = max(f.sum(), 1)
        return pd.DataFrame({
            "pct_clientes": (pd.RangeIndex(1, len(f) + 1) / len(f) * 100).round(3),
            "pct_falhas_acumuladas": (f.cumsum().values / total * 100).round(3),
        })

    def concentracao_falhas(self, fracao_clientes: float = 0.10) -> float:
        """Que parte das falhas vem da fração de clientes que mais falha."""
        f = self.base.groupby("cliente_key")["falha"].sum().sort_values(ascending=False)
        k = max(int(len(f) * fracao_clientes), 1)
        return round(f.head(k).sum() / max(f.sum(), 1) * 100, 2)
