"""Scheduler for sending monthly summaries and other periodic tasks."""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from telegram import Bot
from telegram.error import TelegramError

from bot.database import crud, get_db
from bot.utils.formatters import format_amount, format_date
from bot.utils.charts import create_text_bar

logger = logging.getLogger(__name__)


async def send_long_message(bot: Bot, chat_id: int, text: str, parse_mode: str = "HTML") -> None:
    """Send a message, splitting it into multiple messages if it exceeds Telegram's limit.
    
    Args:
        bot: Telegram bot instance
        chat_id: Chat ID to send to
        text: Message text
        parse_mode: Parse mode (default: HTML)
    """
    MAX_MESSAGE_LENGTH = 4096
    
    if len(text) <= MAX_MESSAGE_LENGTH:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return
    
    # Split message into parts
    parts = []
    current_part = ""
    
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current_part:
                parts.append(current_part)
            current_part = line + '\n'
        else:
            current_part += line + '\n'
    
    if current_part:
        parts.append(current_part)
    
    # Send each part
    for part in parts:
        await bot.send_message(chat_id=chat_id, text=part.strip(), parse_mode=parse_mode)
        await asyncio.sleep(0.1)  # Small delay between messages


async def send_monthly_summary(bot: Bot, user, summary_data: dict, month_name: str) -> None:
    """Send monthly summary to user.
    
    Args:
        bot: Telegram bot instance
        user: User object
        summary_data: Dictionary with summary statistics (from get_user_expenses_detailed_monthly_report)
        month_name: Name of the month (e.g., "Октябрь 2025")
    """
    try:
        total = summary_data.get('total', Decimal('0'))
        count = summary_data.get('count', 0)
        by_category = summary_data.get('by_category', [])
        
        # Start with header and total
        message = (
            f"📊 <b>Месячный отчет за {month_name}</b>\n\n"
            f"💰 <b>Общая сумма расходов:</b> {format_amount(total)}\n\n"
        )
        
        if total == 0:
            message += "✨ В прошлом месяце не было расходов!\n\n"
        elif by_category:
            # Add category breakdown with chart
            message += "📈 <b>Расходы по категориям:</b>\n\n"
            
            # Get max amount for bar scaling
            max_amount = max(cat['amount'] for cat in by_category) if by_category else Decimal('0')
            
            for cat_data in by_category:
                cat_name = cat_data['category_name']
                cat_icon = cat_data['category_icon']
                amount = cat_data['amount']
                percentage = cat_data.get('percentage', 0)
                expenses = cat_data.get('expenses', [])
                
                # Category header with total and percentage
                message += f"{cat_icon} <b>{cat_name}</b>\n"
                message += f"💵 {format_amount(amount)} ({percentage:.1f}%)\n"
                
                # Add text bar chart
                bar = create_text_bar(float(amount), float(max_amount), length=15)
                message += f"{bar}\n\n"
                
                # Add detailed expenses within this category (limit to top 10)
                if expenses:
                    message += "📝 <i>Детализация:</i>\n"
                    expense_count = len(expenses)
                    for expense in expenses[:10]:  # Show max 10 expenses per category
                        exp_amount = expense['amount']
                        exp_description = expense['description']
                        exp_date = expense['date']
                        
                        # Format date
                        date_str = format_date(exp_date)
                        
                        # Truncate long descriptions
                        if len(exp_description) > 50:
                            exp_description = exp_description[:47] + "..."
                        
                        message += f"  • {date_str}: {format_amount(exp_amount)} - {exp_description}\n"
                    
                    # If there are more expenses, show a note
                    if expense_count > 10:
                        message += f"  <i>... и еще {expense_count - 10} расходов</i>\n"
                    
                    message += "\n"
            
            # Add visual chart summary at the end
            message += "━━━━━━━━━━━━━━━━━━━━━━\n"
            message += "📊 <b>Диаграмма расходов:</b>\n\n"
            
            for cat_data in by_category:
                cat_name = cat_data['category_name']
                cat_icon = cat_data['category_icon']
                percentage = cat_data.get('percentage', 0)
                
                # Create percentage bar
                bar = create_text_bar(percentage, 100, length=15)
                message += f"{cat_icon} {cat_name}\n"
                message += f"{bar} {percentage:.1f}%\n\n"
        
        message += (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>Команды:</b>\n"
            "/stats - Подробная статистика\n"
            "/my_expenses - Просмотр расходов\n"
            "/add_expense - Добавить расход"
        )
        
        # Send message (using send_long_message to handle long messages)
        await send_long_message(bot, user.telegram_id, message)
        
        logger.info(f"Sent monthly summary to user {user.id} ({user.telegram_id})")
        
    except TelegramError as e:
        logger.error(f"Failed to send monthly summary to user {user.id}: {e}")
    except Exception as e:
        logger.error(f"Error sending monthly summary to user {user.id}: {e}", exc_info=True)


async def check_and_send_monthly_summaries(bot: Bot) -> None:
    """Check if today is 1st day of month and send summaries to users."""
    now = datetime.now()
    
    # Check if today is 1st day of month
    if now.day != 1:
        logger.debug(f"Today is not 1st day of month (day={now.day}), skipping monthly summaries")
        return
    
    logger.info("Today is 1st day of month, checking for monthly summaries to send")
    
    # Calculate previous month range
    first_day_of_current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)
    
    # Format month name
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    month_name = f"{month_names[last_day_of_previous_month.month]} {last_day_of_previous_month.year}"
    
    current_hour = now.hour
    current_minute = now.minute
    current_time = f"{current_hour:02d}:{current_minute:02d}"
    
    logger.info(
        f"Processing monthly summaries for {month_name} "
        f"(period: {first_day_of_previous_month.date()} to {last_day_of_previous_month.date()})"
    )
    
    sent_count = 0
    error_count = 0
    
    async for session in get_db():
        try:
            # Get all users with monthly summary enabled
            from sqlalchemy import select
            from bot.database.models import User
            
            result = await session.execute(
                select(User).where(User.monthly_summary_enabled == True)
            )
            users = result.scalars().all()
            
            logger.info(f"Found {len(users)} users with monthly summary enabled")
            
            for user in users:
                # Check if it's time to send (within 1 hour window)
                if user.monthly_summary_time:
                    target_hour = int(user.monthly_summary_time.split(':')[0])
                    if abs(current_hour - target_hour) > 1:
                        logger.debug(
                            f"Skipping user {user.id}: current time {current_time}, "
                            f"target time {user.monthly_summary_time}"
                        )
                        continue
                
                # Get user's families
                families = await crud.get_user_families(session, user.id)
                
                if not families:
                    logger.debug(f"User {user.id} has no families, skipping")
                    continue
                
                # For each family, get summary for previous month
                for family in families:
                    try:
                        summary = await crud.get_user_expenses_detailed_monthly_report(
                            session,
                            user.id,
                            family.id,
                            start_date=first_day_of_previous_month,
                            end_date=last_day_of_previous_month
                        )
                        
                        # Send summary
                        await send_monthly_summary(bot, user, summary, month_name)
                        sent_count += 1
                        
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        logger.error(
                            f"Error processing monthly summary for user {user.id}, "
                            f"family {family.id}: {e}"
                        )
                        error_count += 1
            
            logger.info(
                f"Monthly summaries processing complete: "
                f"sent={sent_count}, errors={error_count}"
            )
            
        except Exception as e:
            logger.error(f"Error in check_and_send_monthly_summaries: {e}", exc_info=True)


async def run_scheduler(bot: Bot) -> None:
    """Run the scheduler loop.
    
    Checks every hour if monthly summaries need to be sent.
    
    Args:
        bot: Telegram bot instance
    """
    logger.info("Scheduler started")
    
    while True:
        try:
            # Check if we need to send monthly summaries
            await check_and_send_monthly_summaries(bot)
            
            # Sleep for 1 hour
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            # Sleep a bit before retrying
            await asyncio.sleep(60)


async def start_scheduler(bot: Bot) -> asyncio.Task:
    """Start the scheduler in background.
    
    Args:
        bot: Telegram bot instance
        
    Returns:
        Asyncio task for the scheduler
    """
    task = asyncio.create_task(run_scheduler(bot))
    logger.info("Scheduler task created")
    return task

