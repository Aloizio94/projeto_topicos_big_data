"""Inicia o Radar de Entregas com um único comando (ou com dois cliques no arquivo .bat).

O que ele faz, na ordem:
1. instala as bibliotecas que faltarem na primeira execução (e quando o requirements.txt mudar);
2. processa os CSVs com o Spark se houver arquivo novo ou alterado em dados/brutos;
3. abre o painel no navegador.

"""
import json
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BRUTOS = RAIZ / "dados" / "brutos"
ANALITICOS = RAIZ / "dados" / "analiticos"
CONTROLE = RAIZ / "dados" / "tratados" / "controle_arquivos.json"
ENDERECO = "http://localhost:8501"


def instalar_bibliotecas() -> None:
    """Instala as bibliotecas na primeira execução e sempre que o requirements.txt mudar."""
    requisitos = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    marcador = Path(sys.prefix) / "radar_requirements.txt"  # cópia do que já foi instalado neste ambiente
    if marcador.exists() and marcador.read_text(encoding="utf-8") == requisitos:
        return
    print("Instalando as bibliotecas (pode levar alguns minutos)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")], check=True)
    try:
        marcador.write_text(requisitos, encoding="utf-8")
    except OSError:
        pass  # sem permissão (Python fora de um ambiente virtual): só reinstala na próxima vez


def precisa_processar() -> bool:
    """True se houver CSV novo, alterado ou removido desde o último processamento."""
    sys.path.insert(0, str(RAIZ / "src"))  # importado aqui: as bibliotecas já estão instaladas
    from otif.config import assinatura_dos_csvs

    atual = assinatura_dos_csvs(BRUTOS)
    if not atual:
        return False
    if not (ANALITICOS / "fato_visita.parquet").exists() or not CONTROLE.exists():
        return True
    return json.loads(CONTROLE.read_text(encoding="utf-8")) != atual


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
