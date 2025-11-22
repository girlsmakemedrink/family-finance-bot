# 🐳 Запуск с Docker

Это руководство поможет вам запустить Family Finance Bot используя Docker и Docker Compose.

## 📋 Требования

- Docker 20.10 или выше
- Docker Compose 2.0 или выше

### Установка Docker

**macOS:**
```bash
brew install --cask docker
```

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Windows:**
Скачайте [Docker Desktop](https://www.docker.com/products/docker-desktop)

## 🚀 Быстрый старт

### 1. Подготовка окружения

```bash
# Скопируйте пример конфигурации
cp .env.docker.example .env

# Отредактируйте .env файл
nano .env
```

Настройте переменные в `.env`:

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_here

# Database
DB_USER=familybot
DB_PASSWORD=your_secure_password_here
DB_NAME=family_finance
DB_PORT=5432

# Application
DEBUG=False
LOG_LEVEL=INFO

# Admin Users
ADMIN_USER_IDS=123456789,987654321
```

### 2. Запуск контейнеров

```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

## 📊 Управление контейнерами

### Основные команды

```bash
# Запустить сервисы
docker-compose up -d

# Остановить сервисы
docker-compose down

# Перезапустить бота
docker-compose restart bot

# Просмотр статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f

# Просмотр логов только бота
docker-compose logs -f bot

# Просмотр логов только БД
docker-compose logs -f db
```

### Обновление бота

```bash
# Пересобрать образ после изменений в коде
docker-compose up -d --build

# Или пошагово:
docker-compose build bot
docker-compose up -d bot
```

## 🗄️ Работа с базой данных

### Подключение к PostgreSQL

```bash
# Войти в контейнер БД
docker-compose exec db psql -U familybot -d family_finance

# Или напрямую
docker-compose exec db psql postgresql://familybot:password@localhost/family_finance
```

### Резервное копирование

```bash
# Создать бэкап
docker-compose exec -T db pg_dump -U familybot family_finance > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановить из бэкапа
docker-compose exec -T db psql -U familybot family_finance < backup_20250115_120000.sql
```

### Миграции

```bash
# Применить миграции
docker-compose exec bot alembic upgrade head

# Создать новую миграцию
docker-compose exec bot alembic revision --autogenerate -m "description"

# Откатить миграцию
docker-compose exec bot alembic downgrade -1

# Посмотреть историю
docker-compose exec bot alembic history
```

## 🔧 Отладка

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Последние 100 строк
docker-compose logs --tail=100 bot

# Логи с временными метками
docker-compose logs -f -t bot
```

### Вход в контейнер

```bash
# Войти в контейнер бота
docker-compose exec bot /bin/bash

# Или с правами root
docker-compose exec -u root bot /bin/bash

# Выполнить команду
docker-compose exec bot python -c "from config.settings import settings; print(settings.BOT_TOKEN[:10])"
```

### Проверка работоспособности

```bash
# Проверить, что контейнеры запущены
docker-compose ps

# Проверить здоровье БД
docker-compose exec db pg_isready -U familybot

# Проверить подключение к БД из бота
docker-compose exec bot python -c "from bot.database import db_manager; import asyncio; asyncio.run(db_manager.create_tables())"
```

## 📦 Структура Docker

### Dockerfile

```dockerfile
# Multi-stage build для оптимизации размера
FROM python:3.11-slim as builder
# ... установка зависимостей

FROM python:3.11-slim
# ... финальный образ
```

### docker-compose.yml

```yaml
services:
  db:        # PostgreSQL база данных
  bot:       # Telegram бот
```

## 🔒 Безопасность

### Рекомендации

1. **Не храните секреты в репозитории**
   ```bash
   # .env файл должен быть в .gitignore
   echo ".env" >> .gitignore
   ```

2. **Используйте сильные пароли**
   ```bash
   # Генерация случайного пароля
   openssl rand -base64 32
   ```

3. **Ограничьте доступ к портам**
   ```yaml
   # В docker-compose.yml не публикуйте порт БД в продакшене
   # ports:
   #   - "5432:5432"  # Закомментируйте эту строку
   ```

4. **Регулярно обновляйте образы**
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

## 🌐 Продакшен

### Рекомендации для продакшена

1. **Используйте отдельную БД**
   - Настройте внешнюю PostgreSQL
   - Используйте managed database (AWS RDS, Google Cloud SQL)

2. **Настройте логирование**
   ```yaml
   services:
     bot:
       logging:
         driver: "json-file"
         options:
           max-size: "10m"
           max-file: "3"
   ```

3. **Используйте secrets**
   ```yaml
   services:
     bot:
       secrets:
         - bot_token
         
   secrets:
     bot_token:
       external: true
   ```

4. **Мониторинг**
   - Добавьте healthcheck
   - Используйте Prometheus/Grafana
   - Настройте алерты

### Пример production docker-compose.yml

```yaml
version: '3.8'

services:
  bot:
    image: ghcr.io/youruser/family-finance-bot:latest
    restart: always
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - BOT_TOKEN=${BOT_TOKEN}
      - LOG_LEVEL=WARNING
    volumes:
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

## 🚨 Troubleshooting

### Бот не запускается

```bash
# Проверьте логи
docker-compose logs bot

# Проверьте переменные окружения
docker-compose exec bot env | grep BOT_TOKEN

# Проверьте подключение к БД
docker-compose exec bot python -c "import asyncpg; print('OK')"
```

### БД недоступна

```bash
# Проверьте статус
docker-compose ps db

# Проверьте логи БД
docker-compose logs db

# Перезапустите БД
docker-compose restart db
```

### Проблемы с миграциями

```bash
# Проверьте текущую версию
docker-compose exec bot alembic current

# Сбросьте к начальному состоянию (ОСТОРОЖНО!)
docker-compose exec bot alembic downgrade base
docker-compose exec bot alembic upgrade head
```

## 📚 Дополнительные ресурсы

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Best practices for writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

## 💡 Советы

1. Используйте `.dockerignore` для исключения ненужных файлов
2. Оптимизируйте слои Dockerfile для кеширования
3. Используйте multi-stage builds для уменьшения размера образа
4. Настройте health checks для автоматического перезапуска
5. Регулярно чистите неиспользуемые образы и контейнеры:
   ```bash
   docker system prune -a
   ```

Удачи с развертыванием! 🚀

