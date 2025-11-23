#!/bin/bash

# ============================================
# Автоматическая установка systemd service
# для Family Finance Bot
# ============================================

set -e

echo "🚀 Установка Family Finance Bot как systemd service"
echo "===================================================="
echo ""

# Определяем текущую директорию
CURRENT_DIR=$(pwd)
BOT_DIR="$CURRENT_DIR"

# Проверяем, что мы в правильной директории
if [ ! -f "main.py" ]; then
    echo "❌ Ошибка: main.py не найден!"
    echo "ℹ️  Запустите скрипт из директории family_finance_bot"
    exit 1
fi

# Получаем текущего пользователя
CURRENT_USER=$(whoami)

echo "📋 Обнаруженные параметры:"
echo "   Пользователь: $CURRENT_USER"
echo "   Директория: $BOT_DIR"
echo "   Python: $(which python || which python3)"
echo ""

# Создаем временный service файл
SERVICE_FILE="/tmp/family-finance-bot.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Family Finance Telegram Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$BOT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$BOT_DIR/venv/bin/python $BOT_DIR/main.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=family-finance-bot

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service файл создан"
echo ""
echo "📄 Содержимое service файла:"
echo "-----------------------------------"
cat "$SERVICE_FILE"
echo "-----------------------------------"
echo ""

read -p "Продолжить установку? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Отменено"
    rm "$SERVICE_FILE"
    exit 0
fi

# Копируем service файл
echo "📦 Копирование service файла..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/family-finance-bot.service

# Перезагружаем systemd
echo "🔄 Перезагрузка systemd daemon..."
sudo systemctl daemon-reload

# Включаем автозапуск
echo "⚙️  Включение автозапуска..."
sudo systemctl enable family-finance-bot

# Запускаем службу
echo "🚀 Запуск бота..."
sudo systemctl start family-finance-bot

# Ждем пару секунд
sleep 3

# Показываем статус
echo ""
echo "✨ Установка завершена!"
echo ""
echo "📊 Статус службы:"
sudo systemctl status family-finance-bot --no-pager || true

echo ""
echo "===================================================="
echo "✅ Готово!"
echo ""
echo "Полезные команды:"
echo "  sudo systemctl status family-finance-bot   # Статус"
echo "  sudo systemctl stop family-finance-bot     # Остановить"
echo "  sudo systemctl start family-finance-bot    # Запустить"
echo "  sudo systemctl restart family-finance-bot  # Перезапустить"
echo "  sudo journalctl -u family-finance-bot -f   # Логи"
echo ""

# Удаляем временный файл
rm "$SERVICE_FILE"

