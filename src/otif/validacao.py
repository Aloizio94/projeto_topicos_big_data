"""Verificações de qualidade dos dados (CSVs usados para gerar os relatórios) e relatório de qualidade (registra informações relevantes a partir dos dados)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from .config import mes_do_arquivo


@dataclass
class RelatorioQualidade:
    """Resultado das verificações de qualidade, salvo junto com a camada analítica."""

    arquivos_encontrados: int = 0
    arquivos_descartados: list[str] = field(default_factory=list)
    linhas_lidas: int = 0
    linhas_validas: int = 0
    datas_invalidas: int = 0
    linhas_fora_do_mes: int = 0
    violacoes_regra_otif: int = 0
    entregas_nao_realizadas: int = 0
    meses_faltantes: list[str] = field(default_factory=list)
    clientes_distintos: int = 0
    periodo_inicio: str = ""
    periodo_fim: str = ""

    def para_dicionario(self) -> dict:
        return asdict(self)


class ValidadorQualidade:
    """Aplica as regras de qualidade definidas a partir da análise do metadata."""

    def validar(self, df: pd.DataFrame, descartados: list[str]) -> tuple[pd.DataFrame, RelatorioQualidade]:
        """Remove as linhas com data inválida e conta os problemas encontrados."""
        rel = RelatorioQualidade(arquivos_encontrados=df["arquivo_origem"].nunique() + len(descartados),
                                 arquivos_descartados=list(descartados), linhas_lidas=len(df))
        invalidas = df["data_entrega"].isna()
        rel.datas_invalidas = int(invalidas.sum())
        validos = df[~invalidas].reset_index(drop=True)

        mes_linha = validos["data_entrega"].dt.strftime("%Y-%m")
        rel.linhas_fora_do_mes = int((mes_linha != validos["arquivo_origem"].map(mes_do_arquivo)).sum())
        rel.violacoes_regra_otif = int((validos["otif"] != (validos["ot"] & validos["if_"])).sum())
        rel.entregas_nao_realizadas = int((~validos["entrega_realizada"]).sum())

        meses = pd.PeriodIndex(mes_linha.unique(), freq="M")
        todos = pd.period_range(meses.min(), meses.max(), freq="M")
        rel.meses_faltantes = [str(m) for m in todos if m not in meses]

        rel.linhas_validas = len(validos)
        rel.clientes_distintos = int(validos["cod_cliente"].nunique())
        rel.periodo_inicio = validos["data_entrega"].min().strftime("%Y-%m-%d")
        rel.periodo_fim = validos["data_entrega"].max().strftime("%Y-%m-%d")
        return validos, rel

    @staticmethod
    def resumir_arquivos(df: pd.DataFrame, descartados: list[str]) -> pd.DataFrame:
        """Uma linha por arquivo: mês, quantidade de linhas e situação."""
        lidos = df.groupby("arquivo_origem").size().rename("linhas").reset_index()
        lidos = lidos.rename(columns={"arquivo_origem": "arquivo"})
        lidos["situacao"] = "Importado"
        fora = pd.DataFrame({"arquivo": descartados, "linhas": 0,
                             "situacao": "Descartado: nome sem o mês de referência"})
        r = pd.concat([lidos, fora], ignore_index=True)
        r.insert(1, "mes", r["arquivo"].map(mes_do_arquivo))
        return r.sort_values(["mes", "arquivo"], na_position="last").reset_index(drop=True)
