"""Leitura e gravação das camadas do data lake em arquivos Parquet."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class RepositorioParquet:
    """Guarda cada tabela como um arquivo Parquet dentro de uma pasta (uma camada)."""

    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)

    def salvar(self, nome: str, df: pd.DataFrame) -> None:
        # Gravação via PyArrow: evita depender do winutils do Hadoop no Windows.
        df.to_parquet(self.pasta / f"{nome}.parquet", index=False)

    def ler(self, nome: str) -> pd.DataFrame:
        return pd.read_parquet(self.pasta / f"{nome}.parquet")

    def existe(self, nome: str) -> bool:
        return (self.pasta / f"{nome}.parquet").exists()

    def salvar_json(self, nome: str, conteudo: dict) -> None:
        texto = json.dumps(conteudo, ensure_ascii=False, indent=2, default=str)
        (self.pasta / f"{nome}.json").write_text(texto, encoding="utf-8")

    def ler_json(self, nome: str) -> dict:
        return json.loads((self.pasta / f"{nome}.json").read_text(encoding="utf-8"))
