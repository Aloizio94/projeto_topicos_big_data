"""Configurações gerais do Radar de Entregas: caminhos das camadas e constantes do layout."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Configuracao:
    """Caminhos das camadas do data lake e parâmetros do layout dos CSVs."""

    pasta_brutos: Path = RAIZ_PROJETO / "dados" / "brutos"
    pasta_tratados: Path = RAIZ_PROJETO / "dados" / "tratados"
    pasta_analiticos: Path = RAIZ_PROJETO / "dados" / "analiticos"
    separador: str = ";"
    codificacao: str = "ISO-8859-1"


# Nomes das colunas originais e os nomes adotados no sistema.
COLUNAS_ORIGINAIS = ["Cód. Puxada", "Nome da Unidade", "Data", "Visita OTIF", "OT", "IF", "OTIF"]
COLUNAS_PADRAO = ["cod_puxada", "nome_unidade", "data_entrega", "id_visita", "ot", "if_", "otif"]

# Visita com mapa "000000" no fim da chave: a entrega não foi feita.
SUFIXO_SEM_ENTREGA = "-000000"

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Causas das falhas, na ordem em que aparecem nos gráficos.
CAUSAS_FALHA = ["Prazo (OT)", "Completude (IF)", "Prazo e completude", "Entrega não realizada"]

# Cada arquivo traz um mês: OTIF_JAN22.CSV, OTIF_FEV22.CSV, ...
_NOME_ARQUIVO = re.compile(r"^OTIF_([A-Z]{3})(\d{2})\.CSV$", re.IGNORECASE)


def mes_do_arquivo(nome: str) -> str | None:
    """Devolve o mês do arquivo no formato AAAA-MM, ou None se o nome não seguir o padrão."""
    achou = _NOME_ARQUIVO.match(nome)
    if not achou or achou.group(1).capitalize() not in MESES:
        return None
    mes = MESES.index(achou.group(1).capitalize()) + 1
    return f"20{achou.group(2)}-{mes:02d}"
