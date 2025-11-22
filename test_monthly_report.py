#!/usr/bin/env python3
"""
Тестовый скрипт для проверки месячного отчета.
Этот скрипт позволяет протестировать новый формат месячного отчета без ожидания 1-го числа месяца.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent / "family_finance_bot"))

from telegram import Bot
from bot.database import get_db, crud
from bot.scheduler import send_monthly_summary
from config.settings import BOT_TOKEN


async def test_monthly_report_for_user(user_id: int = None, telegram_id: int = None):
    """
    Тестирование месячного отчета для конкретного пользователя.
    
    Args:
        user_id: ID пользователя в базе данных (или telegram_id)
        telegram_id: Telegram ID пользователя
    """
    bot = Bot(token=BOT_TOKEN)
    
    # Вычисляем предыдущий месяц
    now = datetime.now()
    first_day_of_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)
    
    # Форматируем название месяца
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    month_name = f"{month_names[last_day_of_previous_month.month]} {last_day_of_previous_month.year}"
    
    print(f"Тестирование месячного отчета за {month_name}")
    print(f"Период: {first_day_of_previous_month.date()} - {last_day_of_previous_month.date()}")
    print()
    
    async for session in get_db():
        try:
            # Получаем пользователя
            if telegram_id:
                from sqlalchemy import select
                from bot.database.models import User
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                user = result.scalar_one_or_none()
            elif user_id:
                from sqlalchemy import select
                from bot.database.models import User
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
            else:
                # Получаем первого пользователя из базы
                from sqlalchemy import select
                from bot.database.models import User
                result = await session.execute(select(User).limit(1))
                user = result.scalar_one_or_none()
            
            if not user:
                print("❌ Пользователь не найден!")
                return
            
            print(f"✅ Найден пользователь: {user.name} (ID: {user.id}, Telegram ID: {user.telegram_id})")
            print()
            
            # Получаем семьи пользователя
            families = await crud.get_user_families(session, user.id)
            
            if not families:
                print("❌ У пользователя нет семей!")
                return
            
            print(f"✅ Найдено семей: {len(families)}")
            print()
            
            # Для каждой семьи генерируем и отправляем отчет
            for i, family in enumerate(families, 1):
                print(f"📊 Семья {i}: {family.name}")
                print("-" * 50)
                
                try:
                    # Получаем детализированный отчет
                    summary = await crud.get_user_expenses_detailed_monthly_report(
                        session,
                        user.id,
                        family.id,
                        start_date=first_day_of_previous_month,
                        end_date=last_day_of_previous_month
                    )
                    
                    print(f"Общая сумма: {summary['total']}")
                    print(f"Количество расходов: {summary['count']}")
                    print(f"Категорий: {len(summary['by_category'])}")
                    print()
                    
                    if summary['by_category']:
                        print("Категории:")
                        for cat in summary['by_category'][:5]:  # Показываем первые 5
                            print(f"  - {cat['category_icon']} {cat['category_name']}: "
                                  f"{cat['amount']} ({cat['percentage']:.1f}%), "
                                  f"расходов: {len(cat['expenses'])}")
                        if len(summary['by_category']) > 5:
                            print(f"  ... и еще {len(summary['by_category']) - 5} категорий")
                        print()
                    
                    # Отправляем отчет
                    print(f"📤 Отправка отчета пользователю...")
                    await send_monthly_summary(bot, user, summary, month_name)
                    print(f"✅ Отчет отправлен!")
                    print()
                    
                except Exception as e:
                    print(f"❌ Ошибка при обработке семьи {family.name}: {e}")
                    import traceback
                    traceback.print_exc()
                    print()
        
        except Exception as e:
            print(f"❌ Общая ошибка: {e}")
            import traceback
            traceback.print_exc()


async def list_users():
    """Показать список всех пользователей."""
    print("Список пользователей:")
    print("-" * 50)
    
    async for session in get_db():
        from sqlalchemy import select
        from bot.database.models import User
        
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            print("❌ Пользователей не найдено!")
            return
        
        for user in users:
            print(f"ID: {user.id}, Telegram ID: {user.telegram_id}, Имя: {user.name}")
        
        print()
        print(f"Всего пользователей: {len(users)}")


async def main():
    """Главная функция."""
    print("=" * 50)
    print("Тестирование месячного отчета")
    print("=" * 50)
    print()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            await list_users()
        elif command == "test":
            if len(sys.argv) > 2:
                # Если передан второй аргумент, используем его как telegram_id или user_id
                identifier = sys.argv[2]
                if identifier.isdigit():
                    telegram_id = int(identifier)
                    print(f"Тестирование для Telegram ID: {telegram_id}")
                    await test_monthly_report_for_user(telegram_id=telegram_id)
                else:
                    print("❌ ID должен быть числом!")
            else:
                print("Тестирование для первого пользователя из базы...")
                await test_monthly_report_for_user()
        else:
            print(f"❌ Неизвестная команда: {command}")
            print_usage()
    else:
        print_usage()


def print_usage():
    """Показать справку по использованию."""
    print("Использование:")
    print("  python test_monthly_report.py list                    - Показать список пользователей")
    print("  python test_monthly_report.py test                    - Тестировать для первого пользователя")
    print("  python test_monthly_report.py test <telegram_id>      - Тестировать для конкретного пользователя")
    print()
    print("Примеры:")
    print("  python test_monthly_report.py list")
    print("  python test_monthly_report.py test")
    print("  python test_monthly_report.py test 123456789")


if __name__ == "__main__":
    asyncio.run(main())

