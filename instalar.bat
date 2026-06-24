@echo off
title Instalacao - Sistema Tickets
echo ============================================================
echo   SISTEMA TICKETS - Instalando dependencias...
echo ============================================================
echo.

py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado!
    echo Baixe em: https://www.python.org/downloads/
    echo Marque a opcao "Add Python to PATH" na instalacao.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.
echo Instalando pacotes necessarios...
py -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Falha ao instalar dependencias.
    echo Tente: py -m pip install Flask pytz Werkzeug
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Instalacao concluida! Execute "iniciar.bat" para rodar.
echo ============================================================
pause
