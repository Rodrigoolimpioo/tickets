#!/bin/bash
# Script de deploy — executar na VM (Ubuntu) como usuário ubuntu
# Uso: bash deploy.sh
set -e

APP_DIR="/home/ubuntu/tickets"
BACKEND_DIR="$APP_DIR/backend"
VENV="$APP_DIR/venv"

echo "=== Atualizando código ==="
cd "$APP_DIR"
git pull origin master

echo "=== Instalando dependências Python ==="
"$VENV/bin/pip" install -r "$BACKEND_DIR/requirements.txt" --quiet

echo "=== Reiniciando serviço ==="
sudo systemctl restart tickets.service
sudo systemctl status tickets.service --no-pager

echo "=== Deploy concluído ==="
