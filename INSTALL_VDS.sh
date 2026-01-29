#!/bin/bash

# ==============================================
# Скрипт быстрой установки и настройки
# Family Finance Bot на VDS сервере
# ==============================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для красивого вывода
print_header() {
    echo ""
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Проверка прав root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Не запускайте этот скрипт от root!"
        print_info "Скрипт сам запросит sudo когда нужно"
        exit 1
    fi
}

# Проверка наличия необходимых команд
check_requirements() {
    print_header "Проверка зависимостей"
    
    local missing=0
    
    # Python
    if command -v python3 &> /dev/null; then
        print_success "Python 3 установлен: $(python3 --version)"
    else
        print_error "Python 3 не найден!"
        missing=1
    fi
    
    # Pip
    if command -v pip3 &> /dev/null; then
        print_success "pip3 установлен"
    else
        print_error "pip3 не найден!"
        missing=1
    fi
    
    # Systemd
    if command -v systemctl &> /dev/null; then
        print_success "systemd доступен"
    else
        print_warning "systemd не найден - некоторые функции будут недоступны"
    fi
    
    if [ $missing -eq 1 ]; then
        print_error "Установите недостающие зависимости и запустите снова"
        exit 1
    fi
}

# Главное меню
show_menu() {
    clear
    print_header "Family Finance Bot - Установка на VDS"
    
    echo "Выберите действие:"
    echo ""
    echo "1) Быстрая установка (рекомендуется)"
    echo "2) Установить только systemd service"
    echo "3) Настроить автоматизацию (health check + backup)"
    echo "4) Сделать скрипты исполняемыми"
    echo "5) Добавить alias в .bashrc/.zshrc"
    echo "6) Показать статус бота"
    echo "7) Выход"
    echo ""
    read -p "Введите номер (1-7): " choice
    
    case $choice in
        1) quick_install ;;
        2) install_systemd ;;
        3) setup_automation ;;
        4) make_executable ;;
        5) add_aliases ;;
        6) show_status ;;
        7) exit 0 ;;
        *) 
            print_error "Неверный выбор"
            sleep 2
            show_menu
            ;;
    esac
}

# Быстрая установка
quick_install() {
    print_header "Быстрая установка"
    
    print_info "Эта опция установит:"
    echo "  - Systemd service"
    echo "  - Health check в cron"
    echo "  - Ежедневный backup в cron"
    echo "  - Сделает все скрипты исполняемыми"
    echo ""
    read -p "Продолжить? (y/n): " confirm
    
    if [ "$confirm" != "y" ]; then
        show_menu
        return
    fi
    
    make_executable
    install_systemd
    setup_automation
    
    print_header "Установка завершена!"
    print_success "Все компоненты установлены"
    echo ""
    print_info "Проверьте статус: ./STATUS_BOT.sh"
    print_info "Просмотр логов: ./VIEW_LOGS.sh"
    echo ""
    read -p "Нажмите Enter для продолжения..."
    show_menu
}

# Установка systemd service
install_systemd() {
    print_header "Установка systemd service"

    # Support both repo layouts:
    # - service files in repo root (current repo)
    # - service files inside ./family_finance_bot/ (older layout)
    local main_service_file="family-finance-bot.service"
    local admin_service_file="family-finance-admin-bot.service"

    if [ ! -f "$main_service_file" ] && [ -f "family_finance_bot/family-finance-bot.service" ]; then
        main_service_file="family_finance_bot/family-finance-bot.service"
    fi
    if [ ! -f "$admin_service_file" ] && [ -f "family_finance_bot/family-finance-admin-bot.service" ]; then
        admin_service_file="family_finance_bot/family-finance-admin-bot.service"
    fi

    if [ ! -f "$main_service_file" ]; then
        print_error "Файл family-finance-bot.service не найден!"
        read -p "Нажмите Enter для продолжения..."
        show_menu
        return
    fi
    
    print_warning "ВАЖНО: Перед установкой проверьте пути в service файле!"
    echo ""
    echo "Текущие настройки в файле:"
    grep -E "WorkingDirectory|ExecStart|EnvironmentFile" "$main_service_file" || true
    echo ""
    
    read -p "Хотите отредактировать файл сейчас? (y/n): " edit
    if [ "$edit" = "y" ]; then
        ${EDITOR:-nano} "$main_service_file"
        if [ -f "$admin_service_file" ]; then
            echo ""
            print_info "Также будет установлен админ-бот: $admin_service_file"
        fi
    fi
    
    print_info "Копирование service файла..."
    sudo cp "$main_service_file" /etc/systemd/system/family-finance-bot.service
    if [ -f "$admin_service_file" ]; then
        sudo cp "$admin_service_file" /etc/systemd/system/family-finance-admin-bot.service
    else
        print_warning "Файл админ-сервиса не найден — будет установлен только основной бот"
    fi
    
    print_info "Перезагрузка systemd..."
    sudo systemctl daemon-reload
    
    print_info "Включение автозапуска..."
    sudo systemctl enable family-finance-bot
    if [ -f "$admin_service_file" ]; then
        sudo systemctl enable family-finance-admin-bot
    fi
    
    print_info "Запуск бота..."
    sudo systemctl start family-finance-bot
    if [ -f "$admin_service_file" ]; then
        sudo systemctl start family-finance-admin-bot
    fi
    
    sleep 2
    
    print_success "Systemd services установлены!"
    echo ""
    sudo systemctl status family-finance-bot --no-pager || true
    if [ -f "$admin_service_file" ]; then
        echo ""
        sudo systemctl status family-finance-admin-bot --no-pager || true
    fi
    echo ""
    
    read -p "Нажмите Enter для продолжения..."
    show_menu
}

# Настройка автоматизации
setup_automation() {
    print_header "Настройка автоматизации"
    
    local current_dir=$(pwd)
    
    # Создать директории
    print_info "Создание директорий..."
    mkdir -p ~/backups/family_finance
    sudo mkdir -p /var/log/family_finance
    sudo chown $USER:$USER /var/log/family_finance
    
    # Health check
    print_info "Настройка health check..."
    
    # Проверяем есть ли уже задача
    if crontab -l 2>/dev/null | grep -q "HEALTH_CHECK.sh"; then
        print_warning "Health check уже настроен в cron"
    else
        (crontab -l 2>/dev/null; echo "# Family Finance Bot - Health Check") | crontab -
        (crontab -l; echo "*/5 * * * * $current_dir/HEALTH_CHECK.sh >> /var/log/family_finance/healthcheck.log 2>&1") | crontab -
        print_success "Health check добавлен в cron (каждые 5 минут)"
    fi
    
    # Backup
    print_info "Настройка backup..."
    
    # Создать backup скрипт
    cat > ~/backup_family_finance.sh << EOF
#!/bin/bash
BACKUP_DIR="\$HOME/backups/family_finance"
BOT_DIR="$current_dir/family_finance_bot"
DB_FILE="\$BOT_DIR/family_finance.db"

if [ -f "\$DB_FILE" ]; then
    cp "\$DB_FILE" "\$BACKUP_DIR/backup_\$(date +%Y%m%d_%H%M%S).db"
    echo "[\$(date)] ✅ Backup created"
    
    # Удалить старше 30 дней
    find "\$BACKUP_DIR" -name "*.db" -mtime +30 -delete
else
    echo "[\$(date)] ❌ Database not found"
fi
EOF
    
    chmod +x ~/backup_family_finance.sh
    
    if crontab -l 2>/dev/null | grep -q "backup_family_finance.sh"; then
        print_warning "Backup уже настроен в cron"
    else
        (crontab -l; echo "# Family Finance Bot - Daily Backup") | crontab -
        (crontab -l; echo "0 3 * * * \$HOME/backup_family_finance.sh >> /var/log/family_finance/backup.log 2>&1") | crontab -
        print_success "Backup добавлен в cron (каждый день в 3:00)"
    fi
    
    # Показать текущие задачи cron
    echo ""
    print_info "Текущие задачи cron:"
    crontab -l | grep -v "^#" || true
    echo ""
    
    print_success "Автоматизация настроена!"
    echo ""
    print_info "Логи health check: /var/log/family_finance/healthcheck.log"
    print_info "Логи backup: /var/log/family_finance/backup.log"
    print_info "Backup файлы: ~/backups/family_finance/"
    echo ""
    
    read -p "Нажмите Enter для продолжения..."
    show_menu
}

# Сделать скрипты исполняемыми
make_executable() {
    print_header "Настройка скриптов"
    
    local scripts=(
        "START_BOT.sh"
        "STOP_BOT.sh"
        "RESTART_BOT.sh"
        "STATUS_BOT.sh"
        "VIEW_LOGS.sh"
        "HEALTH_CHECK.sh"
    )
    
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            chmod +x "$script"
            print_success "$script - исполняемый"
        else
            print_warning "$script - не найден"
        fi
    done
    
    echo ""
    print_success "Скрипты настроены!"
    
    if [ "$1" != "silent" ]; then
        echo ""
        read -p "Нажмите Enter для продолжения..."
        show_menu
    fi
}

# Добавить alias
add_aliases() {
    print_header "Добавление alias"
    
    local shell_rc=""
    
    if [ -f ~/.bashrc ]; then
        shell_rc=~/.bashrc
        print_info "Обнаружен bash"
    elif [ -f ~/.zshrc ]; then
        shell_rc=~/.zshrc
        print_info "Обнаружен zsh"
    else
        print_error "Не найден .bashrc или .zshrc"
        read -p "Нажмите Enter для продолжения..."
        show_menu
        return
    fi
    
    local current_dir=$(pwd)
    
    echo ""
    print_info "Будут добавлены alias:"
    echo "  bot-start   - Запуск бота"
    echo "  bot-stop    - Остановка бота"
    echo "  bot-restart - Перезапуск бота"
    echo "  bot-status  - Статус бота"
    echo "  bot-logs    - Просмотр логов"
    echo ""
    
    read -p "Продолжить? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        show_menu
        return
    fi
    
    # Проверить, не добавлены ли уже
    if grep -q "# Family Finance Bot aliases" "$shell_rc"; then
        print_warning "Alias уже добавлены в $shell_rc"
    else
        cat >> "$shell_rc" << EOF

# Family Finance Bot aliases
alias bot-start='cd $current_dir && ./START_BOT.sh'
alias bot-stop='cd $current_dir && ./STOP_BOT.sh'
alias bot-restart='cd $current_dir && ./RESTART_BOT.sh'
alias bot-status='cd $current_dir && ./STATUS_BOT.sh'
alias bot-logs='cd $current_dir && ./VIEW_LOGS.sh'
EOF
        print_success "Alias добавлены в $shell_rc"
    fi
    
    echo ""
    print_info "Чтобы активировать alias, выполните:"
    echo "  source $shell_rc"
    echo ""
    print_info "После этого можно использовать: bot-status, bot-logs и т.д."
    echo ""
    
    read -p "Активировать alias сейчас? (y/n): " activate
    if [ "$activate" = "y" ]; then
        source "$shell_rc"
        print_success "Alias активированы!"
    fi
    
    echo ""
    read -p "Нажмите Enter для продолжения..."
    show_menu
}

# Показать статус
show_status() {
    print_header "Статус бота"
    
    if [ -f "./STATUS_BOT.sh" ]; then
        ./STATUS_BOT.sh
    else
        print_error "STATUS_BOT.sh не найден"
    fi
    
    echo ""
    read -p "Нажмите Enter для продолжения..."
    show_menu
}

# Главная функция
main() {
    check_root
    check_requirements
    
    # Проверка что мы в правильной директории
    if [ ! -d "family_finance_bot" ]; then
        print_error "Директория family_finance_bot не найдена!"
        print_info "Запустите скрипт из корня проекта"
        exit 1
    fi
    
    show_menu
}

# Запуск
main "$@"

