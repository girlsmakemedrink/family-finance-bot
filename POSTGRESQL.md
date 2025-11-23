# 🐘 PostgreSQL Setup Guide

Руководство по настройке PostgreSQL для Family Finance Bot.

## 📋 Совместимость с Python 3.13

**Важно:** Если вы используете Python 3.13, старый драйвер `psycopg2-binary` не совместим. Используйте один из современных драйверов:

| Драйвер | Python версия | Рекомендация |
|---------|---------------|--------------|
| `psycopg2-binary` 2.9.10+ | 3.12 и ниже | Стабильный |
| `psycopg` 3.x | 3.11+ | ⭐ Рекомендуется для 3.13+ |
| `asyncpg` | Любая | Только async |

## 🚀 Быстрая установка

### Для Python 3.13+ (Рекомендуется)

```bash
# Установите psycopg3
pip install "psycopg[binary]>=3.1.0"

# Обновите DATABASE_URL в .env
DATABASE_URL=postgresql+psycopg://user:password@localhost/family_finance_db
```

### Для Python 3.12 и ниже

```bash
# Установите psycopg2-binary
pip install psycopg2-binary>=2.9.10

# Обновите DATABASE_URL в .env  
DATABASE_URL=postgresql+psycopg2://user:password@localhost/family_finance_db
```

### Только Async (asyncpg)

```bash
# Установите asyncpg
pip install asyncpg

# Обновите DATABASE_URL в .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/family_finance_db
```

## 📦 Установка PostgreSQL

### macOS (Homebrew)

```bash
# Установка PostgreSQL
brew install postgresql@16

# Запуск службы
brew services start postgresql@16

# Создание базы данных
createdb family_finance_db
```

### Linux (Ubuntu/Debian)

```bash
# Установка
sudo apt update
sudo apt install postgresql postgresql-contrib

# Запуск службы
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создание пользователя и БД
sudo -u postgres psql
```

В psql:
```sql
CREATE DATABASE family_finance_db;
CREATE USER familybot WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE family_finance_db TO familybot;
\q
```

### Windows

1. Скачайте [PostgreSQL Installer](https://www.postgresql.org/download/windows/)
2. Запустите установщик
3. Следуйте инструкциям мастера
4. Запомните пароль суперпользователя

## ⚙️ Настройка проекта

### 1. Обновите requirements.txt

Добавьте нужный драйвер в `requirements.txt`:

**Для Python 3.13+:**
```txt
# PostgreSQL (Python 3.13+)
psycopg[binary]>=3.1.0
```

**Для Python 3.12 и ниже:**
```txt
# PostgreSQL
psycopg2-binary>=2.9.10
```

### 2. Настройте .env

```env
# PostgreSQL connection
DATABASE_URL=postgresql+psycopg://familybot:your_password@localhost:5432/family_finance_db

# Или для psycopg2
# DATABASE_URL=postgresql+psycopg2://familybot:your_password@localhost:5432/family_finance_db

# Или только async
# DATABASE_URL=postgresql+asyncpg://familybot:your_password@localhost:5432/family_finance_db
```

### 3. Примените миграции

```bash
# Создайте миграцию
alembic revision --autogenerate -m "Initial schema"

# Примените миграции
alembic upgrade head
```

## 🔍 Проверка подключения

Проверьте, что всё работает:

```bash
# Python 3.13+
python3 -c "import psycopg; print('psycopg3 работает!')"

# Python 3.12 и ниже  
python3 -c "import psycopg2; print('psycopg2 работает!')"
```

## 🐛 Troubleshooting

### Ошибка: "psycopg2-binary incompatible with Python 3.13"

**Решение:** Используйте psycopg3 вместо psycopg2:
```bash
pip uninstall psycopg2-binary
pip install "psycopg[binary]>=3.1.0"
```

Обновите DATABASE_URL:
```env
DATABASE_URL=postgresql+psycopg://user:password@localhost/dbname
```

### Ошибка: "peer authentication failed"

**Решение (Linux):** Отредактируйте `/etc/postgresql/*/main/pg_hba.conf`:
```
# Замените "peer" на "md5"
local   all   all   md5
```

Перезапустите PostgreSQL:
```bash
sudo systemctl restart postgresql
```

### Ошибка: "could not connect to server"

**Проверьте:**
1. PostgreSQL запущен: `pg_isready`
2. Порт доступен: `telnet localhost 5432`
3. Правильные учетные данные в `.env`

### Ошибка компиляции на macOS

**Решение:** Установите зависимости:
```bash
brew install postgresql@16
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
pip install psycopg2-binary
```

## 📚 Полезные команды

```bash
# Подключение к БД
psql -U familybot -d family_finance_db

# Список баз данных
psql -l

# Бэкап
pg_dump family_finance_db > backup.sql

# Восстановление
psql family_finance_db < backup.sql

# Просмотр таблиц
psql -U familybot -d family_finance_db -c "\dt"
```

## 🔒 Безопасность

1. **Используйте сильные пароли:**
```bash
# Генерация случайного пароля
openssl rand -base64 32
```

2. **Не храните пароли в git:**
```bash
# .env должен быть в .gitignore
echo ".env" >> .gitignore
```

3. **Используйте переменные окружения в продакшене:**
```bash
export DATABASE_URL="postgresql+psycopg://user:pass@host/db"
```

## 🎯 Production Checklist

- [ ] PostgreSQL установлен и запущен
- [ ] База данных создана
- [ ] Пользователь БД создан с правильными правами
- [ ] `.env` настроен с правильным DATABASE_URL
- [ ] Драйвер установлен (psycopg3 для Python 3.13+)
- [ ] Миграции применены (`alembic upgrade head`)
- [ ] Подключение протестировано
- [ ] Бэкапы настроены

## 📖 Дополнительные ресурсы

- [Документация psycopg3](https://www.psycopg.org/psycopg3/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)

Удачи! 🚀

