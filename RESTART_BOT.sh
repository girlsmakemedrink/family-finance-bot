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
    if systemctl is-active --quiet family-finance-admin-bot 2>/dev/null; then
        echo "systemd"
        return
    fi
    
    # Проверка Docker
    if command -v docker-compose &> /dev/null; then
        if docker-compose ps | grep -q family_finance_bot 2>/dev/null; then
            echo "docker"
            return
        fi
        if docker-compose ps | grep -q family_finance_admin_bot 2>/dev/null; then
            echo "docker"
            return
        fi
    fi
    
    # Проверка screen
    if screen -ls | grep -q family_bot 2>/dev/null; then
        echo "screen"
        return
    fi
    if screen -ls | grep -q family_admin_bot 2>/dev/null; then
        echo "screen"
        return
    fi
    
    # Проверка tmux
    if tmux ls 2>/dev/null | grep -q family_bot; then
        echo "tmux"
        return
    fi
    if tmux ls 2>/dev/null | grep -q family_admin_bot; then
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
        sudo systemctl restart family-finance-admin-bot 2>/dev/null || true
        sleep 2
        sudo systemctl status family-finance-bot --no-pager
        if systemctl list-unit-files | grep -q family-finance-admin-bot.service; then
            echo ""
            sudo systemctl status family-finance-admin-bot --no-pager || true
        fi
        echo ""
        echo "✅ Боты перезапущены через systemd"
        echo "📊 Логи основного: sudo journalctl -u family-finance-bot -f"
        echo "📊 Логи админки:  sudo journalctl -u family-finance-admin-bot -f"
        ;;
        
    docker)
        echo "🐳 Обнаружен Docker Compose"
        cd "$BOT_DIR" || cd "$(dirname "$0")/family_finance_bot"
        echo "Перезапуск контейнера..."
        docker-compose restart bot admin_bot
        sleep 2
        docker-compose ps
        echo ""
        echo "✅ Боты перезапущены через Docker"
        echo "📊 Просмотр логов: docker-compose logs -f bot admin_bot"
        ;;
        
    screen)
        echo "📺 Обнаружена screen сессия"
        echo "⚠️  Для перезапуска в screen нужно:"
        echo "1. screen -r family_bot"
        echo "2. Остановить бота (Ctrl+C)"
        echo "3. Запустить снова: python main.py"
        echo "4. Отключиться: Ctrl+A, затем D"
        echo ""
        echo "Админ-бот:"
        echo "1. screen -r family_admin_bot"
        echo "2. Остановить бота (Ctrl+C)"
        echo "3. Запустить снова: python admin_bot.py"
        echo "4. Отключиться: Ctrl+A, затем D"
        ;;
        
    tmux)
        echo "📺 Обнаружена tmux сессия"
        echo "⚠️  Для перезапуска в tmux нужно:"
        echo "1. tmux attach -t family_bot"
        echo "2. Остановить бота (Ctrl+C)"
        echo "3. Запустить снова: python main.py"
        echo "4. Отключиться: Ctrl+B, затем D"
        echo ""
        echo "Админ-бот:"
        echo "1. tmux attach -t family_admin_bot"
        echo "2. Остановить бота (Ctrl+C)"
        echo "3. Запустить снова: python admin_bot.py"
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
                sudo systemctl restart family-finance-admin-bot 2>/dev/null || true
                echo "✅ Перезапущены через systemd"
                ;;
            2)
                cd "$BOT_DIR" || cd "$(dirname "$0")/family_finance_bot"
                docker-compose restart bot admin_bot
                echo "✅ Перезапущены через Docker"
                ;;
            3)
                echo "Запустите бота вручную:"
                echo "cd $BOT_DIR"
                echo "source venv/bin/activate"
                echo "python main.py"
                echo "python admin_bot.py"
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

