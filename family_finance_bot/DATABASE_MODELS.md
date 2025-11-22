# Модели базы данных

Документация по моделям базы данных для Telegram-бота учета расходов.

## Структура файлов

```
bot/database/
├── __init__.py       # Экспорт всех моделей и функций
├── models.py         # Определения моделей SQLAlchemy
└── database.py       # Настройка подключения и инициализация БД
```

## Модели

### 1. User (Пользователь)

Модель для хранения информации о пользователях Telegram.

**Поля:**
- `id` (Integer, PK) - Внутренний ID
- `telegram_id` (BigInteger, уникальный, индексированный) - ID пользователя в Telegram
- `name` (String) - Имя пользователя
- `username` (String, опционально) - Username в Telegram
- `created_at` (DateTime) - Время создания записи

**Relationships:**
- `family_memberships` → FamilyMember (один ко многим)
- `expenses` → Expense (один ко многим)

### 2. Family (Семья)

Модель для группы пользователей (семьи).

**Поля:**
- `id` (Integer, PK) - Внутренний ID
- `name` (String) - Название семьи
- `invite_code` (String, уникальный, индексированный) - Код приглашения (генерируется автоматически)
- `created_at` (DateTime) - Время создания

**Relationships:**
- `members` → FamilyMember (один ко многим)
- `expenses` → Expense (один ко многим)

**Примечание:** Invite code генерируется автоматически функцией `generate_invite_code()` при создании семьи (8 символов, буквы и цифры в верхнем регистре).

### 3. FamilyMember (Член семьи)

Связующая таблица между пользователями и семьями с ролями.

**Поля:**
- `id` (Integer, PK) - Внутренний ID
- `user_id` (Integer, FK → User.id) - ID пользователя
- `family_id` (Integer, FK → Family.id) - ID семьи
- `role` (Enum: admin/member) - Роль пользователя в семье
- `joined_at` (DateTime) - Время присоединения к семье

**Constraints:**
- Уникальная связка `user_id + family_id` (один пользователь не может дважды быть в одной семье)
- Составной индекс на `(user_id, family_id)` для быстрого поиска

**Relationships:**
- `user` → User (многие к одному)
- `family` → Family (многие к одному)

**Роли:**
- `RoleEnum.ADMIN` - Администратор семьи
- `RoleEnum.MEMBER` - Обычный участник

### 4. Category (Категория)

Модель для категоризации расходов.

**Поля:**
- `id` (Integer, PK) - Внутренний ID
- `name` (String) - Название категории
- `icon` (String) - Эмодзи для категории
- `is_default` (Boolean) - Системная категория (по умолчанию)

**Relationships:**
- `expenses` → Expense (один ко многим)

**Дефолтные категории:**
- 🛒 Продукты
- 🚗 Транспорт
- 🎮 Развлечения
- 💊 Здоровье
- 👕 Одежда
- 📦 Прочее

### 5. Expense (Расход)

Модель для отслеживания расходов семьи.

**Поля:**
- `id` (Integer, PK) - Внутренний ID
- `user_id` (Integer, FK → User.id) - Кто добавил расход
- `family_id` (Integer, FK → Family.id) - К какой семье относится
- `category_id` (Integer, FK → Category.id) - Категория расхода
- `amount` (Numeric(12, 2)) - Сумма расхода
- `description` (Text, опционально) - Описание расхода
- `date` (DateTime) - Дата расхода (по умолчанию текущая)
- `created_at` (DateTime) - Время создания записи

**Indexes:**
- `(user_id, family_id)` - для быстрой фильтрации по пользователю и семье
- `(family_id, date)` - для быстрой выборки расходов семьи по датам
- `(category_id)` - для фильтрации по категориям

**Relationships:**
- `user` → User (многие к одному)
- `family` → Family (многие к одному)
- `category` → Category (многие к одному)

## Инициализация базы данных

### Основные функции

```python
from bot.database import init_database, create_default_categories, reset_database

# Инициализация БД (создание таблиц + дефолтные категории)
await init_database()

# Создание только дефолтных категорий
await create_default_categories()

# Полный сброс БД (ВНИМАНИЕ: удаляет все данные!)
await reset_database()
```

### Работа с сессиями

```python
from bot.database import get_db

# Использование сессии БД
async for session in get_db():
    # Ваши запросы к БД
    user = User(telegram_id=123456, name="Test User")
    session.add(user)
    # commit происходит автоматически
```

### Database Manager

```python
from bot.database import db_manager

# Инициализация движка
db_manager.init_engine()

# Создание таблиц
await db_manager.create_tables()

# Получение сессии
async for session in db_manager.get_session():
    # работа с БД
    pass

# Закрытие соединения
await db_manager.close()
```

## Примеры использования

### Создание пользователя

```python
from bot.database import get_db, User

async for session in get_db():
    user = User(
        telegram_id=123456789,
        name="Иван Иванов",
        username="ivan_ivanov"
    )
    session.add(user)
```

### Создание семьи

```python
from bot.database import get_db, Family

async for session in get_db():
    family = Family(name="Семья Ивановых")
    # invite_code генерируется автоматически
    session.add(family)
    await session.flush()  # чтобы получить ID и invite_code
    print(f"Invite code: {family.invite_code}")
```

### Добавление члена семьи

```python
from bot.database import get_db, FamilyMember, RoleEnum

async for session in get_db():
    member = FamilyMember(
        user_id=1,
        family_id=1,
        role=RoleEnum.ADMIN
    )
    session.add(member)
```

### Добавление расхода

```python
from decimal import Decimal
from bot.database import get_db, Expense

async for session in get_db():
    expense = Expense(
        user_id=1,
        family_id=1,
        category_id=1,  # Продукты
        amount=Decimal("1500.50"),
        description="Покупки в супермаркете"
    )
    session.add(expense)
```

### Запросы к БД

```python
from sqlalchemy import select
from bot.database import get_db, Expense, User, Category

async for session in get_db():
    # Получение расходов семьи за период
    result = await session.execute(
        select(Expense)
        .where(Expense.family_id == 1)
        .order_by(Expense.date.desc())
    )
    expenses = result.scalars().all()
    
    # Получение расходов с join
    result = await session.execute(
        select(Expense, User, Category)
        .join(User)
        .join(Category)
        .where(Expense.family_id == 1)
    )
    for expense, user, category in result:
        print(f"{user.name}: {expense.amount} ({category.name})")
    
    # Подсчет суммы расходов
    from sqlalchemy import func
    result = await session.execute(
        select(func.sum(Expense.amount))
        .where(Expense.family_id == 1)
    )
    total = result.scalar() or 0
```

## Миграции

Для управления миграциями используется Alembic. Миграции находятся в папке `alembic/versions/`.

### Создание новой миграции

```bash
# После изменения моделей
alembic revision --autogenerate -m "описание изменений"

# Применение миграций
alembic upgrade head

# Откат миграции
alembic downgrade -1
```

## Технические детали

### Async SQLAlchemy

Все операции с БД асинхронные:
- Используется `create_async_engine`
- Сессии типа `AsyncSession`
- Все запросы выполняются через `await session.execute()`

### Поддержка БД

- **SQLite** (разработка): `sqlite+aiosqlite:///path/to/db.db`
- **PostgreSQL** (продакшн): `postgresql+asyncpg://user:password@host:port/dbname`

URL подключения автоматически конвертируется в async-версию в `DatabaseManager.init_engine()`.

### Cascading Deletes

- При удалении User удаляются все связанные FamilyMember и Expense
- При удалении Family удаляются все связанные FamilyMember и Expense
- При удалении Category запрещено (RESTRICT), если есть связанные Expense

## Тестирование

Запустить тестовый скрипт:

```bash
python test_database.py
```

Скрипт проверяет:
- ✅ Создание всех таблиц
- ✅ Генерацию дефолтных категорий
- ✅ Создание пользователей
- ✅ Создание семьи с invite code
- ✅ Добавление членов семьи
- ✅ Создание расходов
- ✅ Запросы к БД

