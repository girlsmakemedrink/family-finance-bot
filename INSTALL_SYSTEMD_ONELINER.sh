#!/bin/bash
# Скопируйте всё содержимое этого файла и вставьте в терминал на VDS сервере

cd ~/family_finance_bot && \
CURRENT_DIR=$(pwd) && \
CURRENT_USER=$(whoami) && \
echo "🚀 Установка systemd service для Family Finance Bot" && \
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
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/main.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=family-finance-bot

[Install]
WantedBy=multi-user.target
EOF
echo "" && \
echo "✅ Service файл создан" && \
sudo systemctl daemon-reload && \
echo "✅ systemd перезагружен" && \
sudo systemctl enable family-finance-bot && \
echo "✅ Автозапуск включен" && \
sudo systemctl start family-finance-bot && \
echo "✅ Бот запущен" && \
sleep 2 && \
echo "" && \
echo "📊 Статус:" && \
sudo systemctl status family-finance-bot --no-pager && \
echo "" && \
echo "🎉 Готово! Используйте:" && \
echo "  sudo systemctl status family-finance-bot   # Статус" && \
echo "  sudo systemctl restart family-finance-bot  # Перезапуск" && \
echo "  sudo journalctl -u family-finance-bot -f   # Логи"

