#!/bin/bash
# Скопируйте всё содержимое этого файла и вставьте в терминал на VDS сервере

cd ~/family_finance_bot && \
CURRENT_DIR=$(pwd) && \
CURRENT_USER=$(whoami) && \
echo "🚀 Установка systemd service для Family Finance Bot (основной + админ)" && \
echo "Пользователь: $CURRENT_USER" && \
echo "Директория: $CURRENT_DIR" && \
sudo tee /etc/systemd/system/family-finance-bot.service > /dev/null << EOF
[Unit]
Description=Family Finance Telegram Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$CURRENT_DIR/.env
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/main.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=family-finance-bot

[Install]
WantedBy=multi-user.target
EOF
sudo tee /etc/systemd/system/family-finance-admin-bot.service > /dev/null << EOF
[Unit]
Description=Family Finance Admin Panel Telegram Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$CURRENT_DIR/.env
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/admin_bot.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=family-finance-admin-bot

[Install]
WantedBy=multi-user.target
EOF
echo "" && \
echo "✅ Service файлы созданы" && \
sudo systemctl daemon-reload && \
echo "✅ systemd перезагружен" && \
sudo systemctl enable family-finance-bot && \
sudo systemctl enable family-finance-admin-bot && \
echo "✅ Автозапуск включен" && \
sudo systemctl start family-finance-bot && \
sudo systemctl start family-finance-admin-bot && \
echo "✅ Боты запущены" && \
sleep 2 && \
echo "" && \
echo "📊 Статус:" && \
sudo systemctl status family-finance-bot --no-pager && \
sudo systemctl status family-finance-admin-bot --no-pager && \
echo "" && \
echo "🎉 Готово! Используйте:" && \
echo "  sudo systemctl status family-finance-bot   # Статус" && \
echo "  sudo systemctl status family-finance-admin-bot   # Статус админки" && \
echo "  sudo systemctl restart family-finance-bot  # Перезапуск" && \
echo "  sudo systemctl restart family-finance-admin-bot  # Перезапуск админки" && \
echo "  sudo journalctl -u family-finance-bot -f   # Логи основного" && \
echo "  sudo journalctl -u family-finance-admin-bot -f   # Логи админки"

