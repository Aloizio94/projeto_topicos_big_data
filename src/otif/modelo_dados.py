"""Construção do modelo estrela da camada analítica (fato de visitas + dimensões)."""
from __future__ import annotations

import pandas as pd

from .config import DIAS_SEMANA, MESES


class ConstrutorModeloEstrela:
    """Transforma a camada tratada em uma tabela fato e três dimensões."""

    def construir(self, tratado: pd.DataFrame) -> dict[str, pd.DataFrame]:
        return {
            "fato_visita": self.fato_visita(tratado),
            "dim_data": self.dim_data(tratado),
            "dim_cliente": self.dim_cliente(tratado),
            "dim_unidade": self.dim_unidade(tratado),
        }

    @staticmethod
    def chave_data(serie: pd.Series) -> pd.Series:
        """Chave inteira no formato AAAAMMDD."""
        return serie.dt.strftime("%Y%m%d").astype("int64")

    def fato_visita(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({
            "id_visita": df["id_visita"],
            "data_key": self.chave_data(df["data_entrega"]),
            "cliente_key": df["cod_cliente"],
            "unidade_key": df["cod_puxada"],
            "ot": df["ot"],
            "if_": df["if_"],
            "otif": df["otif"],
            "entrega_realizada": df["entrega_realizada"],
            "causa": df["causa"],
            "arquivo_origem": df["arquivo_origem"],
        })

    def dim_data(self, df: pd.DataFrame) -> pd.DataFrame:
        datas = pd.Series(pd.date_range(df["data_entrega"].min(), df["data_entrega"].max(), freq="D"))
        return pd.DataFrame({
            "data_key": self.chave_data(datas),
            "data": datas,
            "ano": datas.dt.year,
            "mes": datas.dt.month,
            "nome_mes": datas.dt.month.map(lambda m: MESES[m - 1]),
            "ano_mes": datas.dt.strftime("%Y-%m"),
            "dia_semana": datas.dt.dayofweek,
            "nome_dia_semana": datas.dt.dayofweek.map(lambda d: DIAS_SEMANA[d]),
        })

    @staticmethod
    def dim_cliente(df: pd.DataFrame) -> pd.DataFrame:
        return (
            df.groupby("cod_cliente")
            .agg(primeira_visita=("data_entrega", "min"), ultima_visita=("data_entrega", "max"))
            .reset_index()
            .rename(columns={"cod_cliente": "cliente_key"})
        )

    @staticmethod
    def dim_unidade(df: pd.DataFrame) -> pd.DataFrame:
        return (
            df[["cod_puxada", "nome_unidade"]].drop_duplicates("cod_puxada")
            .rename(columns={"cod_puxada": "unidade_key"})
            .reset_index(drop=True)
        )
