# Инструкции по деплою Family Finance Bot

## Содержание

1. [Деплой на VPS с systemd](#деплой-на-vps-с-systemd)
2. [Деплой с Docker](#деплой-с-docker)
3. [Переменные окружения](#переменные-окружения)
4. [Мониторинг и логи](#мониторинг-и-логи)
5. [Обновление бота](#обновление-бота)
6. [Резервное копирование](#резервное-копирование)

---

## Деплой на VPS с systemd

### Требования

- Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- Python 3.11+
- PostgreSQL 13+ (опционально, можно использовать SQLite)
- root или sudo доступ

### Шаг 1: Подготовка системы

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib git

# Создание пользователя для бота
sudo useradd -r -m -d /opt/family-finance-bot -s /bin/bash botuser
```

### Шаг 2: Установка PostgreSQL (опционально)

```bash
# Запуск PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Создание базы данных
sudo -u postgres psql
```

В psql выполните:

```sql
CREATE DATABASE family_finance;
CREATE USER familybot WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE family_finance TO familybot;
\q
```

### Шаг 3: Установка бота

```bash
# Переключение на пользователя botuser
sudo -u botuser -i

# Клонирование репозитория
cd /opt/family-finance-bot
git clone <your-repo-url> .

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt

# Для PostgreSQL дополнительно:
pip install "psycopg[binary]>=3.1.0"  # Для Python 3.13+
# ИЛИ
pip install psycopg2-binary>=2.9.10  # Для Python 3.12 и ниже
```

### Шаг 4: Конфигурация

```bash
# Создание .env файла
cp .env.example .env
nano .env
```

Заполните переменные окружения:

```env
BOT_TOKEN=your_bot_token_from_botfather
DATABASE_URL=postgresql://familybot:your_secure_password@localhost:5432/family_finance
DEBUG=False
LOG_LEVEL=INFO
ADMIN_USER_IDS=123456789,987654321
```

### Шаг 5: Миграции базы данных

```bash
# Выполнение миграций
alembic upgrade head
```

### Шаг 6: Установка systemd service

```bash
# Выход из пользователя botuser
exit

# Копирование service файла
sudo cp /opt/family-finance-bot/family-finance-bot.service /etc/systemd/system/

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable family-finance-bot

# Запуск бота
sudo systemctl start family-finance-bot

# Проверка статуса
sudo systemctl status family-finance-bot
```

### Шаг 7: Настройка логов

```bash
# Создание директории для логов
sudo mkdir -p /opt/family-finance-bot/logs
sudo chown botuser:botuser /opt/family-finance-bot/logs

# Просмотр логов через journald
sudo journalctl -u family-finance-bot -f

# Просмотр файлов логов
sudo tail -f /opt/family-finance-bot/logs/bot.log
```

---

## Деплой с Docker

### Требования

- Docker 20.10+
- Docker Compose 2.0+

### Шаг 1: Клонирование репозитория

```bash
git clone <your-repo-url>
cd family-finance-bot
```

### Шаг 2: Конфигурация

```bash
# Создание .env файла
cp .env.example .env
nano .env
```

Заполните переменные:

```env
BOT_TOKEN=your_bot_token_from_botfather
DB_USER=familybot
DB_PASSWORD=your_secure_password
DB_NAME=family_finance
DB_PORT=5432
DEBUG=False
LOG_LEVEL=INFO
ADMIN_USER_IDS=123456789
```

### Шаг 3: Запуск

```bash
# Сборка и запуск контейнеров
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Проверка статуса
docker-compose ps
```

### Шаг 4: Управление

```bash
# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Обновление
git pull
docker-compose build
docker-compose up -d

# Просмотр логов базы данных
docker-compose logs -f db

# Выполнение команд в контейнере
docker-compose exec bot bash
```

---

## Переменные окружения

### Обязательные

| Переменная | Описание | Пример |
|------------|----------|--------|
| `BOT_TOKEN` | Токен бота от BotFather | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |

### Опциональные

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | URL подключения к БД | `sqlite://./family_finance.db` |
| `DEBUG` | Режим отладки | `False` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `ADMIN_USER_IDS` | ID администраторов (через запятую) | пусто |

### Примеры DATABASE_URL

```env
# SQLite (для разработки)
DATABASE_URL=sqlite+aiosqlite:///./family_finance.db

# PostgreSQL с psycopg (Python 3.13+)
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/dbname

# PostgreSQL с psycopg2 (Python 3.12 и ниже)
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/dbname

# PostgreSQL в Docker
DATABASE_URL=postgresql://familybot:password@db:5432/family_finance
```

---

## Мониторинг и логи

### Просмотр логов (systemd)

```bash
# Все логи
sudo journalctl -u family-finance-bot

# Последние 100 строк
sudo journalctl -u family-finance-bot -n 100

# С момента запуска
sudo journalctl -u family-finance-bot --since today

# В реальном времени
sudo journalctl -u family-finance-bot -f

# Только ошибки
sudo journalctl -u family-finance-bot -p err
```

### Просмотр файлов логов

```bash
# Основной лог
tail -f /opt/family-finance-bot/logs/bot.log

# Только ошибки
tail -f /opt/family-finance-bot/logs/errors.log

# Поиск в логах
grep "ERROR" /opt/family-finance-bot/logs/bot.log
```

### Мониторинг здоровья (Docker)

```bash
# Проверка healthcheck
docker inspect --format='{{.State.Health.Status}}' family_finance_bot

# Детали healthcheck
docker inspect family_finance_bot | jq '.[0].State.Health'
```

### Настройка logrotate

Создайте `/etc/logrotate.d/family-finance-bot`:

```
/opt/family-finance-bot/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 botuser botuser
    sharedscripts
    postrotate
        systemctl reload family-finance-bot > /dev/null 2>&1 || true
    endscript
}
```

---

## Обновление бота

### С systemd

```bash
# Переключение на пользователя botuser
sudo -u botuser -i
cd /opt/family-finance-bot

# Получение обновлений
git pull

# Активация виртуального окружения
source venv/bin/activate

# Обновление зависимостей
pip install -r requirements.txt --upgrade

# Выполнение миграций
alembic upgrade head

# Выход
exit

# Перезапуск бота
sudo systemctl restart family-finance-bot

# Проверка статуса
sudo systemctl status family-finance-bot
```

### С Docker

```bash
cd /path/to/family-finance-bot

# Получение обновлений
git pull

# Пересборка и перезапуск
docker-compose down
docker-compose build
docker-compose up -d

# Проверка логов
docker-compose logs -f bot
```

---

## Резервное копирование

### Автоматическое резервное копирование (systemd)

Создайте скрипт `/opt/family-finance-bot/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/family-finance-bot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Бэкап базы данных PostgreSQL
pg_dump -U familybot family_finance | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Бэкап .env
cp /opt/family-finance-bot/.env "$BACKUP_DIR/env_$DATE"

# Удаление старых бэкапов (старше 30 дней)
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "env_*" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Добавьте в crontab:

```bash
sudo crontab -e
# Добавьте строку:
0 2 * * * /opt/family-finance-bot/backup.sh >> /var/log/family-finance-backup.log 2>&1
```

### Резервное копирование с Docker

```bash
# Создание backup директории
mkdir -p ./backups

# Бэкап базы данных
docker-compose exec -T db pg_dump -U familybot family_finance | gzip > ./backups/db_$(date +%Y%m%d_%H%M%S).sql.gz

# Восстановление из бэкапа
gunzip < ./backups/db_20231215_120000.sql.gz | docker-compose exec -T db psql -U familybot family_finance
```

---

## Troubleshooting

### Бот не запускается

```bash
# Проверка логов
sudo journalctl -u family-finance-bot -n 50

# Проверка конфигурации
sudo -u botuser -i
cd /opt/family-finance-bot
source venv/bin/activate
python -c "from config.settings import settings; print(settings.BOT_TOKEN)"
```

### Проблемы с базой данных

```bash
# Проверка подключения к PostgreSQL
sudo -u botuser psql -U familybot -d family_finance -h localhost

# Проверка миграций
sudo -u botuser -i
cd /opt/family-finance-bot
source venv/bin/activate
alembic current
alembic history
```

### Высокая нагрузка

```bash
# Мониторинг ресурсов
htop
# или
docker stats

# Проверка количества запросов
grep "Action:" /opt/family-finance-bot/logs/bot.log | wc -l
```

---

## Безопасность

### Рекомендации

1. **Firewall**: Открывайте только необходимые порты
   ```bash
   sudo ufw allow ssh
   sudo ufw allow 5432/tcp  # Только если PostgreSQL доступен извне
   sudo ufw enable
   ```

2. **Обновления**: Регулярно обновляйте систему
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **Мониторинг**: Настройте мониторинг логов на подозрительную активность

4. **Бэкапы**: Регулярно создавайте резервные копии

5. **SSL/TLS**: Используйте защищенные соединения для PostgreSQL

6. **Secrets**: Храните токены и пароли в .env, не коммитьте их в git

---

## Дополнительные материалы

- [README.md](README.md) - Основная документация
- [QUICKSTART.md](QUICKSTART.md) - Быстрый старт
- [DATABASE_MODELS.md](DATABASE_MODELS.md) - Модели базы данных

