"""Processamento com PySpark: lê os CSVs mensais e gera a camada tratada.

O Spark faz o trabalho pesado (leitura paralela dos arquivos, transformações e agregação mensal) e
devolve o resultado como DataFrame do Pandas, que o resto do sistema usa.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .ambiente import preparar_spark
from .config import COLUNAS_PADRAO, SUFIXO_SEM_ENTREGA, Configuracao

COLUNAS_TRATADAS = [
    "arquivo_origem", "cod_puxada", "nome_unidade", "data_entrega", "id_visita",
    "cod_cliente", "entrega_realizada", "ot", "if_", "otif", "causa",
]


class ProcessadorSpark:
    """Lê os CSVs com PySpark, padroniza as colunas e agrega os indicadores por mês."""

    def __init__(self, config: Configuracao):
        self.config = config
        self.java = preparar_spark()  # escolhe o Java e ajusta as variáveis de ambiente
        from pyspark.sql import SparkSession

        self.spark = (
            SparkSession.builder.master("local[*]")
            .appName("RadarDeEntregas")
            .config("spark.ui.enabled", "false")
            .config("spark.ui.showConsoleProgress", "false")
            .config("spark.sql.session.timeZone", "UTC")
            # Arrow desligado: no Java 17+ ele exige ajustes na JVM que variam por máquina.
            .config("spark.sql.execution.arrow.pyspark.enabled", "false")
            .config("spark.driver.memory", "2g")
            .getOrCreate()
        )
        self.spark.sparkContext.setLogLevel("ERROR")
        self._tratado = None

    def transformar(self, arquivos: list[Path]) -> pd.DataFrame:
        """Lê os CSVs e devolve a camada tratada (uma linha por visita)."""
        from pyspark.sql import functions as F

        bruto = (
            self.spark.read.option("sep", self.config.separador)
            .option("header", True)
            .option("encoding", self.config.codificacao)
            .csv([str(a) for a in arquivos])
        )
        # O cabeçalho termina com ';', o que cria uma 8ª coluna vazia: usamos só as 7 primeiras.
        cols = bruto.columns
        df = bruto.select(
            *[F.col(f"`{cols[i]}`").alias(COLUNAS_PADRAO[i]) for i in range(7)],
            F.element_at(F.split(F.input_file_name(), "/"), -1).alias("arquivo_origem"),
        )
        sim = lambda c: F.col(c) == F.lit("Sim")  # noqa: E731
        df = (
            df.withColumn("arquivo_origem", F.expr("url_decode(arquivo_origem)"))
            .withColumn("nome_unidade", F.trim("nome_unidade"))
            .withColumn("data_entrega", F.to_date("data_entrega", "dd/MM/yyyy"))
            # Da chave "Visita OTIF" usamos só o código do cliente (2º trecho) e o mapa zerado.
            .withColumn("cod_cliente", F.split("id_visita", "-").getItem(1))
            .withColumn("entrega_realizada", ~F.col("id_visita").endswith(SUFIXO_SEM_ENTREGA))
            .withColumn("ot", sim("ot"))
            .withColumn("if_", sim("if_"))
            .withColumn("otif", sim("otif"))
            .withColumn(
                "causa",
                F.when(~F.col("entrega_realizada"), "Entrega não realizada")
                .when(F.col("otif"), "Sem falha")
                .when(F.col("if_"), "Prazo (OT)")
                .when(F.col("ot"), "Completude (IF)")
                .otherwise("Prazo e completude"),
            )
            .select(*COLUNAS_TRATADAS)
        )
        self._tratado = df.cache()
        return padronizar_tipos(self._tratado.toPandas())

    def agregar_mensal(self) -> pd.DataFrame:
        """Agrega visitas e percentuais de OT, IF e OTIF por mês (groupBy no Spark)."""
        from pyspark.sql import functions as F

        agg = (
            self._tratado.filter(F.col("data_entrega").isNotNull())
            .groupBy(F.date_format("data_entrega", "yyyy-MM").alias("ano_mes"))
            .agg(
                F.count("*").alias("visitas"),
                F.round(F.avg(F.col("ot").cast("int")) * 100, 2).alias("pct_ot"),
                F.round(F.avg(F.col("if_").cast("int")) * 100, 2).alias("pct_if"),
                F.round(F.avg(F.col("otif").cast("int")) * 100, 2).alias("pct_otif"),
            )
            .orderBy("ano_mes")
            .toPandas()
        )
        agg["visitas"] = agg["visitas"].astype("int64")
        return agg

    def encerrar(self) -> None:
        self.spark.stop()


def padronizar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Garante os mesmos tipos de coluna na camada tratada."""
    df = df.copy()
    df["data_entrega"] = pd.to_datetime(df["data_entrega"])
    for c in ["entrega_realizada", "ot", "if_", "otif"]:
        df[c] = df[c].astype(bool)
    return df.reset_index(drop=True)
