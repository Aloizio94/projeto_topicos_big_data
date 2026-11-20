"""Processa os CSVs de dados/brutos com PySpark e gera as camadas tratada e analítica.

Uso:
    python executar_pipeline.py

Precisa de Java 17 instalado (exigência do Spark). Basta rodar uma vez, sempre que entrarem
arquivos novos: o painel só lê o resultado e funciona em qualquer computador, mesmo sem Java.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from otif import PipelineOTIF  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        rel = PipelineOTIF().executar()
    except (RuntimeError, FileNotFoundError) as erro:
        print(f"\nERRO: {erro}")
        sys.exit(1)
    print()
    print(f"Linhas válidas: {rel.linhas_validas:,} | Clientes: {rel.clientes_distintos:,}".replace(",", "."))
    print(f"Período: {rel.periodo_inicio} a {rel.periodo_fim}")
    print("Para abrir o painel: streamlit run app.py  (ou dois cliques em \"Iniciar Radar de Entregas.bat\")")


if __name__ == "__main__":
    main()
