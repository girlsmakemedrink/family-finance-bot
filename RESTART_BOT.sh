#!/bin/bash

# ==============================================
# Скрипт перезапуска Family Finance Bot
# ==============================================

set -e  # Остановка при ошибке

# Определите путь к вашему боту
BOT_DIR="/opt/family-finance-bot"
# Или используйте текущую директорию
# BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/family_finance_bot"

echo "🔄 Перезапуск Family Finance Bot..."
echo "=================================="

# Определяем метод запуска
detect_method() {
    # Проверка systemd
    if systemctl is-active --quiet family-finance-bot 2>/dev/null; then
        echo "systemd"
        return
    fi
    
    # Проверка Docker
    if command -v docker-compose &> /dev/null; then
        if docker-compose ps | grep -q family_finance_bot 2>/dev/null; then
            echo "docker"
            return
        fi
    fi
    
    # Проверка screen
    if screen -ls | grep -q family_bot 2>/dev/null; then
        echo "screen"
        return
    fi
    
    # Проверка tmux
    if tmux ls 2>/dev/null | grep -q family_bot; then
        echo "tmux"
        return
    fi
    
    echo "unknown"
}

METHOD=$(detect_method)

case $METHOD in
    systemd)
        echo "📦 Обнаружен systemd service"
        echo "Перезапуск службы..."
        sudo systemctl restart family-finance-bot
        sleep 2
        sudo systemctl status family-finance-bot --no-pager
        echo ""
        echo "✅ Бот перезапущен через systemd"
        echo "📊 Просмотр логов: sudo journalctl -u family-finance-bot -f"
        ;;
        
    docker)
        echo "🐳 Обнаружен Docker Compose"
        cd "$BOT_DIR" || cd "$(dirname "$0")/family_finance_bot"
        echo "Перезапуск контейнера..."
        docker-compose restart bot
        sleep 2
        docker-compose ps
        echo ""
        echo "✅ Бот перезапущен через Docker"
        echo "📊 Просмотр логов: docker-compose logs -f bot"
        ;;
        
    screen)
        echo "📺 Обнаружена screen сессия"
        echo "⚠️  Для перезапуска в screen нужно:"
        echo "1. screen -r family_bot"
        echo "2. Остановить бота (Ctrl+C)"
        echo "3. Запустить снова: python main.py"
        echo "4. Отключиться: Ctrl+A, затем D"
        ;;
        
    tmux)
        echo "📺 Обнаружена tmux сессия"
        echo "⚠️  Для перезапуска в tmux нужно:"
        echo "1. tmux attach -t family_bot"
        echo "2. Остановить бота (Ctrl+C)"
        echo "3. Запустить снова: python main.py"
        echo "4. Отключиться: Ctrl+B, затем D"
        ;;
        
    unknown)
        echo "❓ Не удалось определить метод запуска бота"
        echo ""
        echo "Выберите метод вручную:"
        echo "1) systemd service"
        echo "2) Docker Compose"
        echo "3) Ручной запуск"
        echo ""
        read -p "Введите номер (1-3): " choice
        
        case $choice in
            1)
                sudo systemctl restart family-finance-bot
                echo "✅ Перезапущен через systemd"
                ;;
            2)
                cd "$BOT_DIR" || cd "$(dirname "$0")/family_finance_bot"
                docker-compose restart bot
                echo "✅ Перезапущен через Docker"
                ;;
            3)
                echo "Запустите бота вручную:"
                echo "cd $BOT_DIR"
                echo "source venv/bin/activate"
                echo "python main.py"
                ;;
            *)
                echo "❌ Неверный выбор"
                exit 1
                ;;
        esac
        ;;
esac

echo ""
echo "=================================="
echo "✨ Готово!"

