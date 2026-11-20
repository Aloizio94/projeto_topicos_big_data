"""Inicia o Radar de Entregas com um único comando (ou com dois cliques no arquivo .bat).

O que ele faz, na ordem:
1. instala as bibliotecas que faltarem (só na primeira vez);
2. processa os CSVs com o Spark se houver arquivo novo ou alterado em dados/brutos;
3. abre o painel no navegador.

Uso:  python iniciar.py              (processa só se houver CSV novo)
      python iniciar.py --processar  (força o processamento)
"""
import importlib.util
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BRUTOS = RAIZ / "dados" / "brutos"
ANALITICOS = RAIZ / "dados" / "analiticos"
ENDERECO = "http://localhost:8501"


def instalar_bibliotecas() -> None:
    faltando = [m for m in ("pandas", "pyarrow", "pyspark", "streamlit", "plotly")
                if importlib.util.find_spec(m) is None]
    if faltando:
        print("Instalando as bibliotecas (só na primeira vez, pode levar alguns minutos)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")], check=True)


def precisa_processar() -> bool:
    """True se houver CSV que ainda não foi processado ou que mudou depois do último processamento."""
    csvs = [p for p in BRUTOS.iterdir() if p.is_file() and p.suffix.lower() == ".csv"] if BRUTOS.exists() else []
    if not csvs:
        return False
    fato, resumo = ANALITICOS / "fato_visita.parquet", ANALITICOS / "resumo_arquivos.parquet"
    if not fato.exists() or not resumo.exists():
        return True
    import pandas as pd

    processados = set(pd.read_parquet(resumo)["arquivo"])
    if {p.name for p in csvs} != processados:
        return True
    return max(p.stat().st_mtime for p in csvs) > fato.stat().st_mtime


def processar() -> bool:
    print("Processando os CSVs com o Spark...")
    resultado = subprocess.run([sys.executable, str(RAIZ / "executar_pipeline.py")], cwd=RAIZ)
    if resultado.returncode != 0:
        print("ERRO no processamento (veja a mensagem acima). O painel vai usar os dados anteriores.")
        return False
    return True


def abrir_painel() -> None:
    if not (ANALITICOS / "fato_visita.parquet").exists():
        print("Ainda não há dados processados. Copie os CSVs para dados\\brutos e instale o Java 17.")
        sys.exit(1)  # o .bat pausa para a mensagem poder ser lida
    print(f"Abrindo o painel em {ENDERECO}  (para encerrar, feche esta janela ou aperte Ctrl+C)")
    painel = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(RAIZ / "app.py")], cwd=RAIZ)
    time.sleep(4)
    webbrowser.open(ENDERECO)
    try:
        painel.wait()
    except KeyboardInterrupt:
        painel.terminate()


def main() -> None:
    instalar_bibliotecas()
    if "--processar" in sys.argv or precisa_processar():
        processar()
    else:
        print("Nenhum CSV novo: usando os dados já processados.")
    abrir_painel()


if __name__ == "__main__":
    main()
