@echo off
chcp 65001 >nul
title Radar de Entregas
cd /d "%~dp0"

rem O Spark nao funciona no Windows se o Python estiver em pasta com espacos.
rem Por isso o ambiente virtual fica em uma pasta do usuario, sem espacos.
set "VENV=%LOCALAPPDATA%\RadarDeEntregas\venv"
if not "%VENV: =%"=="%VENV%" set "VENV=%PUBLIC%\RadarDeEntregas\venv"

if not exist "%VENV%\Scripts\python.exe" (
    echo Criando o ambiente do Python em %VENV% - so na primeira vez...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo ERRO: Python nao encontrado. Instale o Python 3.11 ou 3.12 marcando "Add python.exe to PATH".
        pause
        exit /b 1
    )
)

"%VENV%\Scripts\python.exe" iniciar.py %*
if errorlevel 1 pause
