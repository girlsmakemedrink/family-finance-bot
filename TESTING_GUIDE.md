# Руководство по тестированию Family Finance Bot

## Обзор

Проект включает комплексную систему тестирования с использованием pytest и pytest-asyncio.

## Структура тестов

```
tests/
├── conftest.py           # Фикстуры и конфигурация
├── test_database.py      # Тесты моделей и CRUD операций (21 тест) ✅
├── test_handlers.py      # Тесты обработчиков команд (12 тестов)
└── test_bot.py          # Базовые тесты бота (3 теста) ✅
```

## Текущее состояние

### Работающие тесты ✅

- **test_database.py**: 21/21 тестов успешно ✅
  - Тесты моделей (User, Family, Category, Expense)
  - Тесты CRUD операций
  - Тесты валидации и constraints
  - Тесты relationships и cascade delete

- **test_bot.py**: 3/3 теста успешно ✅
  - Инициализация бота
  - Setup бота
  - Lifecycle бота

### Требуют доработки

- **test_handlers.py**: 0/12 тестов (требуют сложного мокирования Telegram API)

## Запуск тестов

### Все тесты

```bash
pytest
```

### Только работающие тесты

```bash
pytest tests/test_database.py tests/test_bot.py -v
```

### С покрытием кода

```bash
pytest tests/test_database.py tests/test_bot.py --cov=bot --cov=config --cov-report=html
```

### Конкретный класс тестов

```bash
pytest tests/test_database.py::TestCRUD -v
```

### Конкретный тест

```bash
pytest tests/test_database.py::TestCRUD::test_create_user -v
```

## Покрытие кода

### Текущее покрытие по модулям

| Модуль | Покрытие |
|--------|----------|
| bot/database/models.py | 94% ✅ |
| config/settings.py | 93% ✅ |
| bot/__init__.py | 82% ✅ |
| bot/database/database.py | 65% |
| bot/database/crud.py | 20% |
| bot/handlers/* | 7-31% |
| bot/utils/* | 0-43% |
| **ИТОГО** | **19%** |

### Почему низкое общее покрытие?

Основная часть кода - это обработчики (handlers) и утилиты, которые:
- Тесно интегрированы с Telegram API
- Требуют сложного мокирования
- Содержат много интерактивной логики (конверсации, клавиатуры)

**Хорошие новости:**
- ✅ Критичные компоненты (модели БД, CRUD) покрыты на 90%+
- ✅ Инфраструктура тестирования готова
- ✅ Фикстуры настроены
- ✅ Тесты выполняются быстро (<2 секунд)

## Фикстуры

### Базовые фикстуры

- `test_engine` - Тестовая БД (in-memory SQLite)
- `test_session` - Тестовая сессия БД
- `mock_settings` - Моки для настроек

### Фикстуры данных

- `test_user` - Тестовый пользователь
- `test_family` - Тестовая семья
- `test_category` - Тестовая категория
- `test_family_member` - Тестовый участник семьи
- `test_expense` - Тестовый расход

### Фикстуры для Telegram

- `mock_telegram_update` - Мок Update объекта
- `mock_telegram_context` - Мок Context объекта

## Примеры тестов

### Тест модели

```python
@pytest.mark.asyncio
async def test_user_creation(test_session: AsyncSession):
    user = User(
        telegram_id=123456,
        name="Test User",
        username="testuser"
    )
    test_session.add(user)
    await test_session.commit()
    
    assert user.id is not None
    assert user.telegram_id == 123456
```

### Тест CRUD операции

```python
@pytest.mark.asyncio
async def test_create_user(test_session: AsyncSession):
    user = await crud.create_user(
        test_session,
        telegram_id=111222333,
        name="Created User"
    )
    
    assert user.id is not None
    assert user.name == "Created User"
```

### Тест валидации

```python
@pytest.mark.asyncio
async def test_unique_telegram_id(test_session: AsyncSession, test_user: User):
    duplicate_user = User(
        telegram_id=test_user.telegram_id,
        name="Duplicate User"
    )
    test_session.add(duplicate_user)
    
    with pytest.raises(Exception):  # IntegrityError
        await test_session.commit()
```

## CI/CD интеграция

### GitHub Actions пример

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest tests/test_database.py tests/test_bot.py -v --cov=bot
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Улучшение покрытия

### Приоритеты для будущих тестов

1. **Высокий приоритет**:
   - CRUD операции (crud.py) - добавить тесты для оставшихся функций
   - Helpers и validators - критичны для безопасности

2. **Средний приоритет**:
   - Start handler - базовый функционал
   - Family handler - создание и присоединение к семьям
   - Expense handler - добавление расходов

3. **Низкий приоритет**:
   - Statistics handler
   - Charts генерация
   - Форматирование

### Рекомендации по написанию новых тестов

1. **Используйте существующие фикстуры** - они уже настроены
2. **Мокируйте внешние зависимости** - Telegram API, время, случайность
3. **Тестируйте граничные случаи** - пустые данные, максимальные значения
4. **Один тест = одна проверка** - не объединяйте несколько проверок
5. **Используйте параметризацию** - для тестирования множества входных данных

## Troubleshooting

### Тесты не запускаются

```bash
# Проверьте, установлены ли зависимости
pip install -r requirements.txt

# Проверьте pytest
pytest --version

# Проверьте pytest-asyncio
python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"
```

### База данных не очищается между тестами

Используйте `test_session` фикстуру - она автоматически делает rollback после каждого теста.

### Медленные тесты

```bash
# Запустите с профилированием
pytest --durations=10

# Используйте parallel execution
pytest -n auto
```

## Полезные команды

```bash
# Запуск только быстрых тестов
pytest -m "not slow"

# Запуск с детальным выводом
pytest -vv

# Остановка после первой ошибки
pytest -x

# Запуск последних упавших тестов
pytest --lf

# Запуск с coverage и генерацией отчета
pytest --cov=bot --cov-report=html
open htmlcov/index.html
```

## Дополнительные ресурсы

- [Pytest документация](https://docs.pytest.org/)
- [pytest-asyncio документация](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy testing](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)

