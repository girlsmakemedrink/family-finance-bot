#!/bin/bash

# ==============================================
# Скрипт остановки Family Finance Bot
# ==============================================

set -e

echo "🛑 Остановка Family Finance Bot..."
echo "=================================="

# Определяем метод запуска
detect_method() {
    if systemctl is-active --quiet family-finance-bot 2>/dev/null; then
        echo "systemd"
        return
    fi

    if systemctl is-active --quiet family-finance-admin-bot 2>/dev/null; then
        echo "systemd"
        return
    fi
    
    if command -v docker-compose &> /dev/null; then
        if docker ps | grep -q family_finance_bot 2>/dev/null; then
            echo "docker"
            return
        fi
        if docker ps | grep -q family_finance_admin_bot 2>/dev/null; then
            echo "docker"
            return
        fi
    fi
    
    if screen -ls | grep -q family_bot 2>/dev/null; then
        echo "screen"
        return
    fi
    if screen -ls | grep -q family_admin_bot 2>/dev/null; then
        echo "screen"
        return
    fi
    
    if tmux ls 2>/dev/null | grep -q family_bot; then
        echo "tmux"
        return
    fi
    if tmux ls 2>/dev/null | grep -q family_admin_bot; then
        echo "tmux"
        return
    fi
    
    if pgrep -f "python.*main.py" > /dev/null; then
        echo "process"
        return
    fi
    if pgrep -f "python.*admin_bot.py" > /dev/null; then
        echo "process"
        return
    fi
    
    echo "none"
}

METHOD=$(detect_method)

case $METHOD in
    systemd)
        echo "📦 Остановка systemd service..."
        sudo systemctl stop family-finance-bot
        sudo systemctl stop family-finance-admin-bot 2>/dev/null || true
        echo "✅ Бот остановлен"
        ;;
        
    docker)
        echo "🐳 Остановка Docker контейнера..."
        BOT_DIR="/opt/family-finance-bot"
        cd "$BOT_DIR" 2>/dev/null || cd "$(dirname "$0")/family_finance_bot"
        docker-compose down
        echo "✅ Боты остановлены"
        ;;
        
    screen)
        echo "📺 Остановка screen сессии..."
        screen -S family_bot -X quit 2>/dev/null || true
        screen -S family_admin_bot -X quit 2>/dev/null || true
        echo "✅ Screen сессии завершены"
        ;;
        
    tmux)
        echo "📺 Остановка tmux сессии..."
        tmux kill-session -t family_bot 2>/dev/null || true
        tmux kill-session -t family_admin_bot 2>/dev/null || true
        echo "✅ Tmux сессии завершены"
        ;;
        
    process)
        echo "🔧 Остановка процесса..."
        pkill -f "python.*main.py" 2>/dev/null || true
        pkill -f "python.*admin_bot.py" 2>/dev/null || true
        echo "✅ Процессы завершены"
        ;;
        
    none)
        echo "ℹ️  Бот не запущен"
        ;;
esac

echo ""
echo "=================================="
echo "✨ Готово!"

