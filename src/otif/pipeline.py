"""Orquestra o fluxo completo: brutos -> tratados -> analíticos."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .config import Configuracao, mes_do_arquivo
from .modelo_dados import ConstrutorModeloEstrela
from .processamento import ProcessadorSpark
from .repositorio import RepositorioParquet
from .validacao import RelatorioQualidade, ValidadorQualidade

log = logging.getLogger(__name__)


class PipelineOTIF:
    """Executa cada etapa na ordem e grava o resultado de cada camada."""

    def __init__(self, config: Configuracao | None = None):
        self.config = config or Configuracao()
        self.tratados = RepositorioParquet(self.config.pasta_tratados)
        self.analiticos = RepositorioParquet(self.config.pasta_analiticos)

    def listar_arquivos(self) -> tuple[list[Path], list[str]]:
        """Separa os CSVs mensais (OTIF_MMMAA.CSV) dos arquivos sem mês de referência no nome."""
        pasta = self.config.pasta_brutos
        csvs = sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == ".csv")
        if not csvs:
            raise FileNotFoundError(f"Nenhum CSV encontrado em {pasta}. Copie os arquivos de OTIF para essa pasta.")
        mensais = [p for p in csvs if mes_do_arquivo(p.name)]
        descartados = [p.name for p in csvs if not mes_do_arquivo(p.name)]
        return mensais, descartados

    def executar(self) -> RelatorioQualidade:
        inicio = time.perf_counter()
        arquivos, descartados = self.listar_arquivos()
        log.info("1/4 Ingestão: %d arquivos mensais em %s", len(arquivos), self.config.pasta_brutos)
        for nome in descartados:
            log.info("    Descartado (nome sem o mês de referência): %s", nome)

        processador = ProcessadorSpark(self.config)
        try:
            tratado = processador.transformar(arquivos)
            mensal = processador.agregar_mensal()
        finally:
            processador.encerrar()
        log.info("2/4 Transformação com Spark (%s): %d linhas lidas", processador.java, len(tratado))

        validador = ValidadorQualidade()
        validos, relatorio = validador.validar(tratado, descartados)
        log.info("3/4 Qualidade: %d linhas válidas", relatorio.linhas_validas)

        tabelas = ConstrutorModeloEstrela().construir(validos)
        tabelas["agg_otif_mensal"] = mensal
        tabelas["resumo_arquivos"] = validador.resumir_arquivos(tratado, descartados)
        self.tratados.salvar("visitas_tratadas", validos)
        for nome, tabela in tabelas.items():
            self.analiticos.salvar(nome, tabela)
        self.analiticos.salvar_json("relatorio_qualidade", relatorio.para_dicionario())
        log.info("4/4 Camada analítica gravada: %s", ", ".join(tabelas))
        log.info("Concluído em %.1f s.", time.perf_counter() - inicio)
        return relatorio
