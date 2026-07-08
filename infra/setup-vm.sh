#!/bin/bash
# Provisionamento inicial da VM Oracle Cloud (Ubuntu 22.04)
# Executar uma vez como ubuntu após criar a instância
set -e

APP_DIR="/home/ubuntu/tickets"
REPO_URL="https://github.com/rodrigo/tickets.git"   # ajustar se necessário

echo "=== 1. Dependências do sistema ==="
sudo apt update -y
sudo apt install -y python3 python3-pip python3-venv nginx git

echo "=== 2. Clonar repositório ==="
git clone "$REPO_URL" "$APP_DIR"

echo "=== 3. Ambiente virtual Python ==="
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

echo "=== 4. Arquivo .env ==="
echo "ATENÇÃO: copie o .env manualmente para $APP_DIR/backend/.env"
echo "         (nunca commitar credenciais no git)"

echo "=== 5. Wallet Oracle ==="
echo "ATENÇÃO: copie a pasta wallet/ para $APP_DIR/backend/wallet/"
echo "         (baixar no OCI Console > Autonomous Database > DB Connection > Download Wallet)"

echo "=== 6. Serviço systemd ==="
sudo cp "$APP_DIR/infra/systemd/tickets.service" /etc/systemd/system/tickets.service
sudo systemctl daemon-reload
sudo systemctl enable tickets.service
sudo systemctl start tickets.service

echo "=== 7. Nginx ==="
sudo cp "$APP_DIR/infra/nginx/tickets" /etc/nginx/sites-available/tickets
sudo ln -sf /etc/nginx/sites-available/tickets /etc/nginx/sites-enabled/tickets
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "=== Setup concluído ==="
echo "Verificar: sudo systemctl status tickets.service"
echo "Logs:      sudo journalctl -u tickets.service -f"
