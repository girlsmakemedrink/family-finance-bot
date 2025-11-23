# Database Package

Пакет для работы с базой данных Telegram-бота учета расходов.

## Структура

```
bot/database/
├── __init__.py      # Экспорт моделей и функций
├── models.py        # Модели SQLAlchemy (User, Family, FamilyMember, Category, Expense)
├── database.py      # DatabaseManager и функции инициализации
└── README.md        # Эта документация
```

## Модели

### User
Пользователь Telegram с уникальным `telegram_id`.

### Family
Семья с автоматически генерируемым `invite_code`.

### FamilyMember
Связь пользователя и семьи с ролью (admin/member).

### Category
Категория расходов с иконкой (эмодзи).

### Expense
Расход с суммой (Decimal), описанием и привязкой к пользователю, семье и категории.

## Быстрый старт

```python
from bot.database import init_database, get_db, User, Family, Expense
from decimal import Decimal

# Инициализация
await init_database()

# Работа с данными
async for session in get_db():
    user = User(telegram_id=123456, name="Test")
    session.add(user)
```

## Документация

- **Полная документация**: `/DATABASE_MODELS.md`
- **Быстрый старт**: `/QUICK_START_DATABASE.md`
- **Резюме**: `/SUMMARY.md`

## Функции

### init_database()
Создает таблицы и дефолтные категории.

### create_default_categories()
Добавляет 6 системных категорий (Продукты, Транспорт, и т.д.).

### get_db()
Async generator для получения сессий БД.

### db_manager
Singleton для управления подключением к БД.

## Тестирование

```bash
python3 test_database.py
```

## Особенности

✅ Async SQLAlchemy  
✅ Автогенерация invite_code  
✅ Enum для ролей  
✅ Индексы для оптимизации  
✅ Cascading deletes  
✅ Поддержка SQLite и PostgreSQL  

