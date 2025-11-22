# ⚡ Быстрая справка по управлению ботом на VDS

## 🎯 Готовые скрипты (самый простой способ)

```bash
./START_BOT.sh      # Запуск бота
./STOP_BOT.sh       # Остановка бота
./RESTART_BOT.sh    # Перезапуск бота
./STATUS_BOT.sh     # Проверка статуса
./VIEW_LOGS.sh      # Просмотр логов
```

*Скрипты автоматически определяют метод запуска (systemd/Docker/screen/tmux) и выполняют нужные команды*

---

## 📦 Systemd Service (рекомендуется для VDS)

### Основные команды
```bash
sudo systemctl start family-finance-bot      # Запуск
sudo systemctl stop family-finance-bot       # Остановка
sudo systemctl restart family-finance-bot    # Перезапуск
sudo systemctl status family-finance-bot     # Статус
```

### Логи
```bash
sudo journalctl -u family-finance-bot -f              # Следить за логами
sudo journalctl -u family-finance-bot -n 100          # Последние 100 строк
sudo journalctl -u family-finance-bot --since today   # Логи за сегодня
```

### Автозапуск
```bash
sudo systemctl enable family-finance-bot     # Включить автозапуск
sudo systemctl disable family-finance-bot    # Выключить автозапуск
```

### Установка (первый раз)
```bash
cd family_finance_bot
make deploy-systemd    # Или смотрите VDS_MANAGEMENT_GUIDE.md
```

---

## 🐳 Docker Compose

### Основные команды
```bash
docker-compose up -d              # Запуск
docker-compose down               # Остановка
docker-compose restart bot        # Перезапуск
docker-compose ps                 # Статус
```

### Логи
```bash
docker-compose logs -f bot        # Следить за логами
docker-compose logs --tail=100 bot    # Последние 100 строк
```

### С пересборкой образа
```bash
docker-compose up -d --build      # Запуск с пересборкой
docker-compose down && docker-compose up -d --build    # Полная пересборка
```

---

## 📺 Screen (для простого фонового запуска)

### Запуск
```bash
screen -S family_bot
cd family_finance_bot
source venv/bin/activate
python main.py
# Нажмите Ctrl+A, затем D для отключения
```

### Управление
```bash
screen -ls                # Список сессий
screen -r family_bot      # Подключиться к сессии
# Ctrl+C для остановки бота внутри screen
screen -X -S family_bot quit    # Закрыть сессию извне
```

---

## 🔧 Makefile команды

```bash
cd family_finance_bot

make help              # Показать все команды
make run               # Запуск локально
make docker-up         # Запуск в Docker
make docker-down       # Остановка Docker
make docker-logs       # Логи Docker
make deploy-systemd    # Установить systemd service
make logs-systemd      # Логи systemd
```

---

## 🔍 Диагностика

### Проверить, работает ли бот
```bash
# Systemd
systemctl is-active family-finance-bot

# Docker
docker ps | grep family_finance

# Процесс
ps aux | grep main.py

# Или используйте
./STATUS_BOT.sh
```

### Проверить последние ошибки
```bash
# Systemd
sudo journalctl -u family-finance-bot -p err -n 20

# Docker
docker-compose logs --tail=50 bot | grep -i error

# Файловые логи
tail -50 family_finance_bot/logs/errors.log
```

### Проверить использование ресурсов
```bash
# Systemd
systemctl status family-finance-bot

# Docker
docker stats family_finance_bot

# Процесс
top -p $(pgrep -f "main.py")
```

---

## 🔄 Обновление бота

### Безопасное обновление
```bash
# 1. Остановить
sudo systemctl stop family-finance-bot

# 2. Бэкап БД
cp family_finance_bot/family_finance.db family_finance_bot/family_finance.db.backup

# 3. Обновить код
cd family_finance_bot
git pull

# 4. Обновить зависимости
source venv/bin/activate
pip install -r requirements.txt

# 5. Миграции
alembic upgrade head

# 6. Запустить
sudo systemctl start family-finance-bot

# 7. Проверить
sudo systemctl status family-finance-bot
```

---

## 📊 Мониторинг

### Просмотр логов в реальном времени
```bash
# Выберите ваш метод:
sudo journalctl -u family-finance-bot -f    # Systemd
docker-compose logs -f bot                   # Docker
tail -f family_finance_bot/logs/bot.log     # Файл
./VIEW_LOGS.sh                              # Универсальный скрипт
```

### Проверка базы данных
```bash
cd family_finance_bot
sqlite3 family_finance.db "SELECT COUNT(*) FROM expenses;"
sqlite3 family_finance.db "SELECT COUNT(*) FROM users;"
```

---

## 🆘 Быстрое решение проблем

### Бот не запускается
```bash
# 1. Проверьте логи
sudo journalctl -u family-finance-bot -n 50

# 2. Проверьте конфигурацию
cat family_finance_bot/.env

# 3. Проверьте БД
ls -la family_finance_bot/family_finance.db

# 4. Перезапустите
sudo systemctl restart family-finance-bot
```

### Бот не отвечает
```bash
# Жесткий перезапуск
sudo systemctl stop family-finance-bot
sleep 3
sudo systemctl start family-finance-bot
sudo systemctl status family-finance-bot
```

### Очистка логов (если диск заполнен)
```bash
# Systemd логи
sudo journalctl --vacuum-time=7d    # Оставить за 7 дней
sudo journalctl --vacuum-size=100M  # Оставить не более 100 МБ

# Файловые логи
> family_finance_bot/logs/bot.log   # Очистить файл
```

---

## 🔐 Безопасность

### Проверка прав доступа
```bash
# БД должна быть доступна только владельцу
chmod 600 family_finance_bot/family_finance.db

# .env файл должен быть защищен
chmod 600 family_finance_bot/.env
```

### Резервное копирование
```bash
# Ручной бэкап
cp family_finance_bot/family_finance.db ~/backups/family_finance_$(date +%Y%m%d).db

# Добавить в cron для автоматического бэкапа
crontab -e
# Добавить: 0 3 * * * cp /path/to/family_finance.db /path/to/backups/backup_$(date +\%Y\%m\%d).db
```

---

## 📱 Полезные alias для .bashrc

Добавьте в `~/.bashrc` или `~/.zshrc`:

```bash
# Family Finance Bot aliases
alias bot-start='sudo systemctl start family-finance-bot'
alias bot-stop='sudo systemctl stop family-finance-bot'
alias bot-restart='sudo systemctl restart family-finance-bot'
alias bot-status='sudo systemctl status family-finance-bot'
alias bot-logs='sudo journalctl -u family-finance-bot -f'
alias bot-errors='sudo journalctl -u family-finance-bot -p err -n 50'

# Или для Docker
# alias bot-start='docker-compose -f /path/to/docker-compose.yml up -d'
# alias bot-stop='docker-compose -f /path/to/docker-compose.yml down'
# alias bot-logs='docker-compose -f /path/to/docker-compose.yml logs -f bot'
```

После добавления выполните:
```bash
source ~/.bashrc    # или source ~/.zshrc
```

Теперь можно использовать короткие команды: `bot-start`, `bot-stop`, `bot-logs`

---

## 🎯 Рекомендованная настройка для VDS

1. **Метод запуска:** Systemd Service
2. **Автозапуск:** Включен (`systemctl enable`)
3. **Мониторинг:** Health check script в cron (каждые 5 минут)
4. **Backup:** Ежедневный через cron (3:00 ночи)
5. **Логи:** Ротация журналов (`vacuum-time=30d`)

### Полная настройка за 5 минут:

```bash
# 1. Установите service
cd family_finance_bot
sudo cp family-finance-bot.service /etc/systemd/system/
# Отредактируйте пути в файле!
sudo nano /etc/systemd/system/family-finance-bot.service

# 2. Запустите
sudo systemctl daemon-reload
sudo systemctl enable family-finance-bot
sudo systemctl start family-finance-bot

# 3. Проверьте
sudo systemctl status family-finance-bot

# 4. Настройте мониторинг
crontab -e
# Добавьте:
# */5 * * * * systemctl is-active family-finance-bot || systemctl restart family-finance-bot
# 0 3 * * * cp /path/to/family_finance.db /path/to/backups/backup_$(date +\%Y\%m\%d).db

# 5. Готово! ✨
```

---

## 📚 Дополнительная документация

- `VDS_MANAGEMENT_GUIDE.md` - Подробное руководство по всем методам
- `DEPLOYMENT_GUIDE.md` - Руководство по развертыванию
- `README.md` - Общая информация о проекте

---

**Версия:** 1.0  
**Дата:** 22.11.2025

*Для получения полной информации смотрите `VDS_MANAGEMENT_GUIDE.md`*

