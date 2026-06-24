@echo off
title Sistema Tickets
echo ============================================================
echo   SISTEMA TICKETS - Iniciando servidor...
echo ============================================================
echo.
echo   Acesse no navegador: http://localhost:5000
echo.
echo   Usuarios padrao:
echo   admin       / admin123  (Administrador)
echo   supervisor  / super123  (Supervisor)
echo   funcionario / func123   (Funcionario)
echo.
echo   Pressione CTRL+C para encerrar o servidor.
echo ============================================================
echo.
cd backend
py app.py
pause
