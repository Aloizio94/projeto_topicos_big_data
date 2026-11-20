"""Testes das regras principais (rode com:  python -m pytest).

Os testes de regras usam uma camada tratada montada à mão e rodam em qualquer máquina.
O teste de transformação usa o Spark e é pulado automaticamente se o Java não estiver instalado.
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from otif.config import Configuracao, mes_do_arquivo  # noqa: E402
from otif.indicadores import CalculadoraOTIF  # noqa: E402
from otif.modelo_dados import ConstrutorModeloEstrela  # noqa: E402
from otif.processamento import COLUNAS_TRATADAS, padronizar_tipos  # noqa: E402
from otif.validacao import ValidadorQualidade  # noqa: E402

UNIDADE = "DISTRIBUIDORA TESTE    "
# (arquivo, data de entrega, Visita OTIF, OT, IF, OTIF)
LINHAS = [
    ("OTIF_JAN22.CSV", "03/01/2022", "0001-0000001-03/01/2022-100001", "Sim", "Sim", "Sim"),
    ("OTIF_JAN22.CSV", "03/01/2022", "0001-0000002-03/01/2022-100001", "Não", "Sim", "Não"),
    ("OTIF_JAN22.CSV", "05/01/2022", "0001-0000002-05/01/2022-100002", "Sim", "Não", "Não"),
    ("OTIF_JAN22.CSV", "04/01/2022", "0001-0000003-04/01/2022-000000", "Não", "Não", "Não"),
    ("OTIF_FEV22.CSV", "01/02/2022", "0001-0000001-01/02/2022-100003", "Sim", "Sim", "Sim"),
    ("OTIF_FEV22.CSV", "08/02/2022", "0001-0000001-08/02/2022-100004", "Não", "Não", "Não"),
]
CAUSA = {(True, True): "Sem falha", (False, True): "Prazo (OT)",
         (True, False): "Completude (IF)", (False, False): "Prazo e completude"}


def tratar_a_mao(linhas) -> pd.DataFrame:
    """Monta a camada tratada sem Spark, com as mesmas regras do ProcessadorSpark."""
    registros = []
    for arquivo, data, visita, ot, if_, otif in linhas:
        ot, if_ = ot == "Sim", if_ == "Sim"
        realizada = not visita.endswith("-000000")
        registros.append(dict(
            arquivo_origem=arquivo, cod_puxada="0296708", nome_unidade=UNIDADE.strip(),
            data_entrega=datetime.strptime(data, "%d/%m/%Y"), id_visita=visita,
            cod_cliente=visita.split("-")[1], entrega_realizada=realizada, ot=ot, if_=if_, otif=otif == "Sim",
            causa=CAUSA[(ot, if_)] if realizada else "Entrega não realizada",
        ))
    return padronizar_tipos(pd.DataFrame(registros, columns=COLUNAS_TRATADAS))


@pytest.fixture()
def validado():
    return ValidadorQualidade().validar(tratar_a_mao(LINHAS), ["OTIF_.CSV"])


@pytest.fixture()
def calc(validado):
    tabelas = ConstrutorModeloEstrela().construir(validado[0])
    return CalculadoraOTIF(tabelas["fato_visita"], tabelas["dim_data"])


# ------------------------------------------------------------------ Spark
@pytest.mark.skipif(shutil.which("java") is None, reason="Java não instalado: teste do Spark pulado")
def test_spark_gera_a_mesma_camada_tratada(tmp_path):
    from otif.processamento import ProcessadorSpark

    cabecalho = "Cód. Puxada;Nome da Unidade;Data;Visita OTIF;OT;IF;OTIF;"
    arquivos = []
    for nome in ["OTIF_JAN22.CSV", "OTIF_FEV22.CSV"]:
        linhas = [";".join(["0296708", UNIDADE, *l[1:]]) for l in LINHAS if l[0] == nome]
        caminho = tmp_path / nome
        caminho.write_bytes(("\r\n".join([cabecalho, *linhas]) + "\r\n").encode("latin-1"))
        arquivos.append(caminho)

    spark = ProcessadorSpark(Configuracao(pasta_brutos=tmp_path))
    try:
        obtido = spark.transformar(arquivos)
        mensal = spark.agregar_mensal()
    finally:
        spark.encerrar()

    ordem = ["arquivo_origem", "id_visita"]
    esperado = tratar_a_mao(LINHAS).sort_values(ordem).reset_index(drop=True)
    obtido = obtido.sort_values(ordem).reset_index(drop=True)
    pd.testing.assert_frame_equal(obtido[COLUNAS_TRATADAS], esperado, check_dtype=False)
    assert list(mensal["visitas"]) == [4, 2]
    assert list(mensal["pct_otif"]) == [25.0, 50.0]


# ------------------------------------------------------------------ regras
def test_mes_vem_do_nome_do_arquivo():
    assert mes_do_arquivo("OTIF_JAN22.CSV") == "2022-01"
    assert mes_do_arquivo("otif_dez23.csv") == "2023-12"
    assert mes_do_arquivo("OTIF_.CSV") is None
    assert mes_do_arquivo("OTIF_XYZ22.CSV") is None


def test_causas_e_entrega_nao_realizada():
    t = tratar_a_mao(LINHAS).set_index("id_visita")
    assert t.loc["0001-0000002-03/01/2022-100001", "causa"] == "Prazo (OT)"
    assert t.loc["0001-0000002-05/01/2022-100002", "causa"] == "Completude (IF)"
    assert t.loc["0001-0000001-08/02/2022-100004", "causa"] == "Prazo e completude"
    assert t.loc["0001-0000003-04/01/2022-000000", "causa"] == "Entrega não realizada"
    assert t["cod_cliente"].tolist()[:2] == ["0000001", "0000002"]


def test_relatorio_de_qualidade(validado):
    validos, rel = validado
    assert rel.arquivos_encontrados == 3 and rel.arquivos_descartados == ["OTIF_.CSV"]
    assert rel.linhas_validas == 6
    assert rel.entregas_nao_realizadas == 1
    assert rel.violacoes_regra_otif == 0 and rel.linhas_fora_do_mes == 0
    assert rel.clientes_distintos == 3


def test_indicadores(calc):
    r = calc.resumo()
    assert r["visitas"] == 6 and r["falhas"] == 4
    assert r["pct_otif"] == pytest.approx(33.33, abs=0.01)
    assert calc.filtrar("2022-02", "2022-02").resumo()["visitas"] == 2
    assert calc.filtrar(cliente="0000002").resumo()["falhas"] == 2
    causas = calc.por_causa().set_index("causa")["falhas"].to_dict()
    assert causas == {"Prazo (OT)": 1, "Completude (IF)": 1, "Prazo e completude": 1, "Entrega não realizada": 1}


def test_ranking_por_volume_e_por_taxa(calc):
    volume = calc.ranking_clientes(minimo_visitas=1)
    assert volume.iloc[0]["cliente"] == "0000002"            # 2 falhas
    assert volume["participacao_falhas"].sum() == pytest.approx(100.0)
    taxa = calc.ranking_clientes(minimo_visitas=1, ordenar_por="pct_falha").set_index("cliente")
    assert taxa.index[-1] == "0000001"                       # 1 falha em 3 visitas
    assert taxa.loc["0000001", "pct_falha"] == pytest.approx(33.33, abs=0.01)
    assert taxa.loc["0000003", "causa_principal"] == "Entrega não realizada"
    assert len(calc.ranking_clientes(minimo_visitas=3)) == 1


def test_pareto(calc):
    pareto = calc.curva_pareto_clientes()
    assert pareto["pct_falhas_acumuladas"].iloc[-1] == pytest.approx(100.0)
    assert calc.concentracao_falhas(0.34) == pytest.approx(50.0)
