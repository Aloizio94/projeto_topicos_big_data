"""Prepara o ambiente do Spark: encontra um Java compatível e evita os problemas do Windows.

O Spark 3.5 funciona com Java 11, 17 ou 21. Versões mais novas (23 em diante) removeram recursos
que ele usa, e os scripts do Spark no Windows não aceitam espaços no caminho da instalação.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSOES_COMPATIVEIS = (17, 21, 11)
NO_WINDOWS = os.name == "nt"
EXECUTAVEL = "java.exe" if NO_WINDOWS else "java"


def versao_java(home: Path) -> int | None:
    """Versão principal do Java instalado em `home` (17, 21...), ou None se não houver Java ali."""
    java = home / "bin" / EXECUTAVEL
    if not java.exists():
        return None
    try:
        saida = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    achou = re.search(r'version "(\d+)(?:\.(\d+))?', saida.stderr + saida.stdout)
    if not achou:
        return None
    principal = int(achou.group(1))
    return int(achou.group(2)) if principal == 1 else principal  # "1.8" -> 8


def candidatos_java() -> list[Path]:
    """Pastas onde costuma haver Java: JAVA_HOME, o java do PATH e as pastas padrão de instalação."""
    pastas = []
    if os.environ.get("JAVA_HOME"):
        pastas.append(Path(os.environ["JAVA_HOME"]))
    no_path = shutil.which("java")
    if no_path:
        pastas.append(Path(no_path).resolve().parent.parent)
    if NO_WINDOWS:
        for base in [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramW6432", "")]:
            if base:
                for fornecedor in ["Eclipse Adoptium", "Java", "Microsoft", "Zulu", "Amazon Corretto", "OpenJDK"]:
                    pastas += [Path(p) for p in sorted(glob.glob(os.path.join(base, fornecedor, "*")))]
    else:
        pastas += [Path(p) for p in sorted(glob.glob("/usr/lib/jvm/*"))]
    return list(dict.fromkeys(pastas))  # sem repetidos, mantendo a ordem


def localizar_java() -> tuple[Path, int]:
    """Devolve (pasta do Java, versão) da melhor instalação compatível, ou explica o que falta."""
    encontrados = [(p, v) for p in candidatos_java() if (v := versao_java(p))]
    for preferida in VERSOES_COMPATIVEIS:
        for pasta, versao in encontrados:
            if versao == preferida:
                return pasta, versao
    if encontrados:
        lista = ", ".join(f"Java {v}" for _, v in encontrados)
        raise RuntimeError(f"Encontrei {lista}, mas o Spark 3.5 só funciona com Java 11, 17 ou 21. "
                           "Instale o Java 17 (Temurin, em adoptium.net) e rode de novo.")
    raise RuntimeError("Java não encontrado. Instale o Java 17 (Temurin, em adoptium.net) e rode de novo.")


def preparar_spark() -> str:
    """Configura as variáveis de ambiente do Spark e devolve uma descrição do Java usado."""
    import pyspark

    spark_home = os.path.dirname(pyspark.__file__)
    if NO_WINDOWS and " " in spark_home:
        raise RuntimeError(
            "O Spark não funciona no Windows quando as bibliotecas do Python estão em uma pasta com espaços "
            f"({spark_home}). Use o arquivo 'Iniciar Radar de Entregas.bat', que instala as bibliotecas em "
            "uma pasta sem espaços."
        )
    java_home, versao = localizar_java()
    os.environ["JAVA_HOME"] = str(java_home)
    os.environ["PATH"] = str(java_home / "bin") + os.pathsep + os.environ.get("PATH", "")
    os.environ["SPARK_HOME"] = spark_home
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    return f"Java {versao} em {java_home}"
