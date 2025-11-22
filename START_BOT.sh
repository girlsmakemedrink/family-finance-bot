#!/bin/bash

# ==============================================
# Скрипт запуска Family Finance Bot
# ==============================================

set -e

BOT_DIR="/opt/family-finance-bot"
# Или используйте: BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/family_finance_bot"

echo "🚀 Запуск Family Finance Bot..."
echo "=================================="

# Проверка наличия метода запуска
if systemctl list-unit-files | grep -q family-finance-bot.service; then
    echo "📦 Запуск через systemd service"
    sudo systemctl start family-finance-bot
    sleep 2
    sudo systemctl status family-finance-bot --no-pager
    echo ""
    echo "✅ Бот запущен"
    echo "📊 Просмотр логов: sudo journalctl -u family-finance-bot -f"
    
elif [ -f "$BOT_DIR/docker-compose.yml" ] || [ -f "family_finance_bot/docker-compose.yml" ]; then
    echo "🐳 Запуск через Docker Compose"
    cd "$BOT_DIR" 2>/dev/null || cd "$(dirname "$0")/family_finance_bot"
    docker-compose up -d
    sleep 2
    docker-compose ps
    echo ""
    echo "✅ Бот запущен"
    echo "📊 Просмотр логов: docker-compose logs -f bot"
    
else
    echo "🔧 Ручной запуск"
    echo ""
    echo "Выберите метод:"
    echo "1) Запустить в текущем терминале"
    echo "2) Запустить в screen"
    echo "3) Запустить в tmux"
    read -p "Введите номер (1-3): " choice
    
    case $choice in
        1)
            cd "$BOT_DIR" 2>/dev/null || cd "$(dirname "$0")/family_finance_bot"
            source venv/bin/activate
            python main.py
            ;;
        2)
            cd "$BOT_DIR" 2>/dev/null || cd "$(dirname "$0")/family_finance_bot"
            screen -dmS family_bot bash -c "source venv/bin/activate && python main.py"
            echo "✅ Бот запущен в screen сессии 'family_bot'"
            echo "📺 Подключиться: screen -r family_bot"
            ;;
        3)
            cd "$BOT_DIR" 2>/dev/null || cd "$(dirname "$0")/family_finance_bot"
            tmux new-session -d -s family_bot "source venv/bin/activate && python main.py"
            echo "✅ Бот запущен в tmux сессии 'family_bot'"
            echo "📺 Подключиться: tmux attach -t family_bot"
            ;;
        *)
            echo "❌ Неверный выбор"
            exit 1
            ;;
    esac
fi

echo ""
echo "=================================="
echo "✨ Готово!"

