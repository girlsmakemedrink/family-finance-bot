#!/bin/bash

# ==============================================
# Скрипт просмотра логов Family Finance Bot
# ==============================================

BOT_DIR="/opt/family-finance-bot"
# Или: BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/family_finance_bot"

echo "📊 Просмотр логов Family Finance Bot"
echo "====================================="
echo ""

# Определяем метод запуска
if systemctl is-active --quiet family-finance-bot 2>/dev/null; then
    echo "Источник: systemd journald"
    echo ""
    echo "Выберите вариант:"
    echo "1) Последние 50 строк"
    echo "2) Последние 100 строк"
    echo "3) Следить за логами в реальном времени"
    echo "4) Логи за последний час"
    echo "5) Логи за сегодня"
    read -p "Введите номер (1-5): " choice
    
    case $choice in
        1) sudo journalctl -u family-finance-bot -n 50 ;;
        2) sudo journalctl -u family-finance-bot -n 100 ;;
        3) sudo journalctl -u family-finance-bot -f ;;
        4) sudo journalctl -u family-finance-bot --since "1 hour ago" ;;
        5) sudo journalctl -u family-finance-bot --since today ;;
        *) echo "❌ Неверный выбор"; exit 1 ;;
    esac
    
elif docker ps | grep -q family_finance_bot 2>/dev/null; then
    echo "Источник: Docker контейнер"
    echo ""
    echo "Выберите вариант:"
    echo "1) Последние 50 строк"
    echo "2) Последние 100 строк"
    echo "3) Следить за логами в реальном времени"
    read -p "Введите номер (1-3): " choice
    
    case $choice in
        1) docker-compose logs --tail=50 bot ;;
        2) docker-compose logs --tail=100 bot ;;
        3) docker-compose logs -f bot ;;
        *) echo "❌ Неверный выбор"; exit 1 ;;
    esac
    
else
    echo "Источник: Файлы логов"
    echo ""
    
    LOG_FILE="$BOT_DIR/logs/bot.log"
    if [ ! -f "$LOG_FILE" ]; then
        LOG_FILE="$(dirname "$0")/family_finance_bot/logs/bot.log"
    fi
    
    if [ ! -f "$LOG_FILE" ]; then
        echo "❌ Файл логов не найден"
        echo "Попробуйте указать путь вручную:"
        echo "tail -f /path/to/family_finance_bot/logs/bot.log"
        exit 1
    fi
    
    echo "Выберите вариант:"
    echo "1) Последние 50 строк (bot.log)"
    echo "2) Последние 100 строк (bot.log)"
    echo "3) Следить за логами в реальном времени (bot.log)"
    echo "4) Последние 50 строк (errors.log)"
    echo "5) Следить за ошибками в реальном времени (errors.log)"
    read -p "Введите номер (1-5): " choice
    
    case $choice in
        1) tail -n 50 "$LOG_FILE" ;;
        2) tail -n 100 "$LOG_FILE" ;;
        3) tail -f "$LOG_FILE" ;;
        4) tail -n 50 "$(dirname "$LOG_FILE")/errors.log" ;;
        5) tail -f "$(dirname "$LOG_FILE")/errors.log" ;;
        *) echo "❌ Неверный выбор"; exit 1 ;;
    esac
fi

