#!/bin/bash

# ==============================================
# Скрипт проверки статуса Family Finance Bot
# ==============================================

echo "📊 Статус Family Finance Bot"
echo "====================================="
echo ""

# Проверка systemd
if systemctl list-unit-files | grep -q family-finance-bot.service 2>/dev/null; then
    echo "📦 Systemd Service:"
    if systemctl is-active --quiet family-finance-bot; then
        echo "   Статус: ✅ Работает"
        echo "   Автозапуск: $(systemctl is-enabled family-finance-bot 2>/dev/null)"
        echo ""
        sudo systemctl status family-finance-bot --no-pager | head -n 15
    else
        echo "   Статус: ❌ Остановлен"
    fi
    echo ""
fi

# Проверка Docker
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    if docker ps | grep -q family_finance_bot 2>/dev/null; then
        echo "🐳 Docker Контейнер:"
        echo "   Статус: ✅ Работает"
        echo ""
        docker ps | grep family_finance
        echo ""
        docker stats --no-stream family_finance_bot 2>/dev/null || true
    else
        echo "🐳 Docker: ❌ Не запущен"
    fi
    echo ""
fi

# Проверка screen
if screen -ls 2>/dev/null | grep -q family_bot; then
    echo "📺 Screen сессия:"
    echo "   Статус: ✅ Работает"
    screen -ls | grep family_bot
    echo ""
fi

# Проверка tmux
if tmux ls 2>/dev/null | grep -q family_bot; then
    echo "📺 Tmux сессия:"
    echo "   Статус: ✅ Работает"
    tmux ls | grep family_bot
    echo ""
fi

# Проверка процесса
if pgrep -f "python.*main.py" > /dev/null; then
    echo "🔧 Процесс Python:"
    echo "   Статус: ✅ Работает"
    echo ""
    ps aux | grep "[p]ython.*main.py"
    echo ""
    
    # Использование ресурсов
    PID=$(pgrep -f "python.*main.py")
    if [ ! -z "$PID" ]; then
        echo "📈 Использование ресурсов:"
        top -b -n 1 -p $PID | tail -n 2
    fi
    echo ""
fi

# Проверка базы данных
echo "🗄️  База данных:"
BOT_DIR="/opt/family-finance-bot"
DB_FILE="$BOT_DIR/family_finance.db"

if [ ! -f "$DB_FILE" ]; then
    DB_FILE="$(dirname "$0")/family_finance_bot/family_finance.db"
fi

if [ -f "$DB_FILE" ]; then
    echo "   Файл: ✅ Найден"
    echo "   Размер: $(du -h "$DB_FILE" | cut -f1)"
    echo "   Последнее изменение: $(stat -f "%Sm" "$DB_FILE" 2>/dev/null || stat -c "%y" "$DB_FILE" 2>/dev/null)"
    
    # Количество записей (если доступен sqlite3)
    if command -v sqlite3 &> /dev/null; then
        EXPENSES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM expenses;" 2>/dev/null || echo "N/A")
        USERS=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "N/A")
        echo "   Пользователей: $USERS"
        echo "   Расходов: $EXPENSES"
    fi
else
    echo "   Файл: ❌ Не найден"
fi
echo ""

# Проверка логов
echo "📝 Последние логи (5 строк):"
if systemctl is-active --quiet family-finance-bot 2>/dev/null; then
    sudo journalctl -u family-finance-bot -n 5 --no-pager
elif docker ps | grep -q family_finance_bot 2>/dev/null; then
    docker-compose logs --tail=5 bot 2>/dev/null
else
    LOG_FILE="$BOT_DIR/logs/bot.log"
    if [ ! -f "$LOG_FILE" ]; then
        LOG_FILE="$(dirname "$0")/family_finance_bot/logs/bot.log"
    fi
    
    if [ -f "$LOG_FILE" ]; then
        tail -n 5 "$LOG_FILE"
    else
        echo "   ❌ Логи не найдены"
    fi
fi

echo ""
echo "====================================="
echo "✨ Готово!"

