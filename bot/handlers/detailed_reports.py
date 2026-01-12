"""Handlers for detailed expense reports."""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from bot.database import crud, get_db
from bot.utils.formatters import format_amount, format_date
from bot.utils.charts import create_text_bar
from bot.utils.helpers import get_user_id
from bot.utils.keyboards import get_home_button
from bot.handlers.expenses import CallbackPattern, ViewData

logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def send_long_message(update: Update, text: str, parse_mode: str = "HTML", reply_markup: InlineKeyboardMarkup = None) -> None:
    """Send a message, splitting it into multiple messages if it exceeds Telegram's limit.
    
    Args:
        update: Update object
        text: Message text
        parse_mode: Parse mode (default: HTML)
        reply_markup: Optional keyboard markup (will be attached to the last message part)
    """
    MAX_MESSAGE_LENGTH = 4096
    
    # Get the chat
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        bot = update.callback_query.message.get_bot()
    else:
        chat_id = update.effective_chat.id
        bot = update.get_bot()
    
    if len(text) <= MAX_MESSAGE_LENGTH:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
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
    for i, part in enumerate(parts):
        # Add keyboard only to the last part
        markup = reply_markup if i == len(parts) - 1 else None
        await bot.send_message(chat_id=chat_id, text=part.strip(), parse_mode=parse_mode, reply_markup=markup)


def format_detailed_report(summary_data: dict, period_name: str) -> str:
    """Format detailed report message.
    
    Args:
        summary_data: Dictionary with summary statistics (from get_user_expenses_detailed_monthly_report)
        period_name: Name of the period (e.g., "Октябрь 2025", "2025 год")
        
    Returns:
        Formatted report message
    """
    total = summary_data.get('total', Decimal('0'))
    count = summary_data.get('count', 0)
    by_category = summary_data.get('by_category', [])
    
    # Start with header and total
    message = (
        f"📊 <b>Детальный отчет за {period_name}</b>\n\n"
        f"💰 <b>Общая сумма расходов:</b> {format_amount(total)}\n\n"
    )
    
    if total == 0:
        message += "✨ За выбранный период не было расходов!\n\n"
    elif by_category:
        # Add category breakdown with chart
        message += "📈 <b>Расходы по категориям:</b>\n\n"
        
        # Get max amount for bar scaling
        max_amount = max(cat['amount'] for cat in by_category) if by_category else Decimal('0')
        
        for cat_data in by_category:
            cat_name = cat_data['category_name']
            amount = cat_data['amount']
            percentage = cat_data.get('percentage', 0)
            expenses = cat_data.get('expenses', [])
            
            # Category header with total and percentage
            message += f"• <b>{cat_name}</b>\n"
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
                    exp_description = expense['description'] or "—"
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
            percentage = cat_data.get('percentage', 0)
            
            # Create percentage bar
            bar = create_text_bar(percentage, 100, length=15)
            message += f"• {cat_name}\n"
            message += f"{bar} {percentage:.1f}%\n\n"
    
    message += "━━━━━━━━━━━━━━━━━━━━━━\n"
    
    return message


# ============================================================================
# DETAILED REPORT HANDLERS
# ============================================================================

async def detailed_report_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle detailed report button - show type selection (month/year)."""
    query = update.callback_query
    await query.answer()
    
    user_id = await get_user_id(update, context)
    view_data = ViewData.from_context(context)
    
    if not all([user_id, view_data.family_id]):
        await query.answer("❌ Ошибка: данные не найдены", show_alert=True)
        return
    
    # Get available months and years from expenses
    async def get_expense_periods(session):
        """Get unique months and years that have expenses."""
        from sqlalchemy import select, func, extract
        from bot.database.models import Expense
        
        # Get unique year-month combinations
        query_months = (
            select(
                extract('year', Expense.date).label('year'),
                extract('month', Expense.date).label('month')
            )
            .where(Expense.user_id == user_id)
            .where(Expense.family_id == view_data.family_id)
            .group_by('year', 'month')
            .order_by('year', 'month')
        )
        
        result = await session.execute(query_months)
        months = result.all()
        
        # Get unique years
        query_years = (
            select(extract('year', Expense.date).label('year'))
            .where(Expense.user_id == user_id)
            .where(Expense.family_id == view_data.family_id)
            .group_by('year')
            .order_by('year')
        )
        
        result = await session.execute(query_years)
        years = result.scalars().all()
        
        return months, years
    
    try:
        async for session in get_db():
            months, years = await get_expense_periods(session)
            break
    except Exception as e:
        logger.error(f"Error getting expense periods: {e}")
        await query.answer("❌ Ошибка при получении данных", show_alert=True)
        return
    
    # Save to context for later use
    context.user_data['dr_months'] = [(int(m.year), int(m.month)) for m in months]
    context.user_data['dr_years'] = [int(y) for y in years]
    
    # Build keyboard
    keyboard = [
        [InlineKeyboardButton("📅 Отчет за месяц", callback_data=f"{CallbackPattern.DETAILED_REPORT_TYPE_PREFIX}month")],
        [InlineKeyboardButton("📆 Отчет за год", callback_data=f"{CallbackPattern.DETAILED_REPORT_TYPE_PREFIX}year")],
        [InlineKeyboardButton("🔙 Назад", callback_data=CallbackPattern.NAV_BACK)],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="start")]
    ]
    
    await query.edit_message_text(
        "📊 <b>Выберите тип отчета:</b>\n\n"
        f"Доступно месяцев с расходами: {len(months)}\n"
        f"Доступно лет с расходами: {len(years)}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def detailed_report_select_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show month selection for detailed report."""
    query = update.callback_query
    await query.answer()
    
    months_data = context.user_data.get('dr_months', [])
    
    if not months_data:
        await query.answer("❌ Нет доступных месяцев с расходами", show_alert=True)
        return
    
    # Month names
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    # Build keyboard with recent months first (reversed)
    keyboard = []
    for year, month in reversed(months_data[-12:]):  # Show last 12 months max
        month_name = f"{month_names[month]} {year}"
        callback_data = f"{CallbackPattern.DETAILED_REPORT_MONTH_PREFIX}{year}_{month}"
        keyboard.append([InlineKeyboardButton(month_name, callback_data=callback_data)])
    
    # Check if it's family or personal report
    is_family = context.user_data.get('dr_is_family', False)
    back_button = CallbackPattern.FAMILY_DETAILED_REPORT if is_family else CallbackPattern.MY_DETAILED_REPORT
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=back_button)])
    
    await query.edit_message_text(
        "📅 <b>Выберите месяц для отчета:</b>\n\n"
        "Показаны последние 12 месяцев с расходами",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def detailed_report_select_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show year selection for detailed report."""
    query = update.callback_query
    await query.answer()
    
    years_data = context.user_data.get('dr_years', [])
    
    if not years_data:
        await query.answer("❌ Нет доступных лет с расходами", show_alert=True)
        return
    
    # Build keyboard with recent years first (reversed)
    keyboard = []
    for year in reversed(years_data):
        callback_data = f"{CallbackPattern.DETAILED_REPORT_YEAR_PREFIX}{year}"
        keyboard.append([InlineKeyboardButton(str(year), callback_data=callback_data)])
    
    # Check if it's family or personal report
    is_family = context.user_data.get('dr_is_family', False)
    back_button = CallbackPattern.FAMILY_DETAILED_REPORT if is_family else CallbackPattern.MY_DETAILED_REPORT
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=back_button)])
    
    await query.edit_message_text(
        "📆 <b>Выберите год для отчета:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def generate_monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send detailed monthly report."""
    query = update.callback_query
    await query.answer("📊 Генерирую отчет...")
    
    # Parse year and month from callback data
    callback_data = query.data
    year_month = callback_data.replace(CallbackPattern.DETAILED_REPORT_MONTH_PREFIX, "")
    year, month = map(int, year_month.split('_'))
    
    # Check if it's family or personal report
    is_family = context.user_data.get('dr_is_family', False)
    
    if is_family:
        view_data = ViewData.from_context(context, prefix="family_view")
        user_id = None  # Not needed for family reports
    else:
        user_id = await get_user_id(update, context)
        view_data = ViewData.from_context(context)
    
    if not view_data.family_id:
        await query.answer("❌ Ошибка: данные не найдены", show_alert=True)
        return
    
    # Calculate date range for the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)
    
    # Month name
    month_names = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    period_name = f"{month_names[month]} {year}"
    
    try:
        async for session in get_db():
            if is_family:
                # For family reports, get all expenses for the family
                summary = await crud.get_family_expenses_detailed_report(
                    session,
                    view_data.family_id,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # For personal reports, get user expenses
                summary = await crud.get_user_expenses_detailed_monthly_report(
                    session,
                    user_id,
                    view_data.family_id,
                    start_date=start_date,
                    end_date=end_date
                )
            break
        
        # Format and send report
        message = format_detailed_report(summary, period_name)
        
        # Delete the selection message
        try:
            await query.message.delete()
        except:
            pass
        
        # Send detailed report with home button
        keyboard = get_home_button()
        await send_long_message(update, message, reply_markup=keyboard)
        
        logger.info(f"Sent detailed monthly report for {'family' if is_family else 'user'} {view_data.family_id}, period {period_name}")
        
    except Exception as e:
        logger.error(f"Error generating monthly report: {e}", exc_info=True)
        await query.answer("❌ Ошибка при генерации отчета", show_alert=True)


async def generate_yearly_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send detailed yearly report."""
    query = update.callback_query
    await query.answer("📊 Генерирую годовой отчет...")
    
    # Parse year from callback data
    callback_data = query.data
    year = int(callback_data.replace(CallbackPattern.DETAILED_REPORT_YEAR_PREFIX, ""))
    
    # Check if it's family or personal report
    is_family = context.user_data.get('dr_is_family', False)
    
    if is_family:
        view_data = ViewData.from_context(context, prefix="family_view")
        user_id = None  # Not needed for family reports
    else:
        user_id = await get_user_id(update, context)
        view_data = ViewData.from_context(context)
    
    if not view_data.family_id:
        await query.answer("❌ Ошибка: данные не найдены", show_alert=True)
        return
    
    # Calculate date range for the year
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31, 23, 59, 59)
    
    period_name = f"{year} год"
    
    try:
        async for session in get_db():
            if is_family:
                # For family reports, get all expenses for the family
                summary = await crud.get_family_expenses_detailed_report(
                    session,
                    view_data.family_id,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # For personal reports, get user expenses
                summary = await crud.get_user_expenses_detailed_monthly_report(
                    session,
                    user_id,
                    view_data.family_id,
                    start_date=start_date,
                    end_date=end_date
                )
            break
        
        # Format and send report
        message = format_detailed_report(summary, period_name)
        
        # Delete the selection message
        try:
            await query.message.delete()
        except:
            pass
        
        # Send detailed report with home button
        keyboard = get_home_button()
        await send_long_message(update, message, reply_markup=keyboard)
        
        logger.info(f"Sent detailed yearly report for {'family' if is_family else 'user'} {view_data.family_id}, period {period_name}")
        
    except Exception as e:
        logger.error(f"Error generating yearly report: {e}", exc_info=True)
        await query.answer("❌ Ошибка при генерации отчета", show_alert=True)


# ============================================================================
# FAMILY DETAILED REPORT HANDLERS
# ============================================================================

async def family_detailed_report_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle family detailed report button - show type selection (month/year)."""
    query = update.callback_query
    await query.answer()
    
    view_data = ViewData.from_context(context, prefix="family_view")
    
    if not view_data.family_id:
        await query.answer("❌ Ошибка: данные не найдены", show_alert=True)
        return
    
    # Get available months and years from family expenses
    async def get_expense_periods(session):
        """Get unique months and years that have expenses."""
        from sqlalchemy import select, func, extract
        from bot.database.models import Expense
        
        # Get unique year-month combinations
        query_months = (
            select(
                extract('year', Expense.date).label('year'),
                extract('month', Expense.date).label('month')
            )
            .where(Expense.family_id == view_data.family_id)
            .group_by('year', 'month')
            .order_by('year', 'month')
        )
        
        result = await session.execute(query_months)
        months = result.all()
        
        # Get unique years
        query_years = (
            select(extract('year', Expense.date).label('year'))
            .where(Expense.family_id == view_data.family_id)
            .group_by('year')
            .order_by('year')
        )
        
        result = await session.execute(query_years)
        years = result.scalars().all()
        
        return months, years
    
    try:
        async for session in get_db():
            months, years = await get_expense_periods(session)
            break
    except Exception as e:
        logger.error(f"Error getting family expense periods: {e}")
        await query.answer("❌ Ошибка при получении данных", show_alert=True)
        return
    
    # Save to context for later use
    context.user_data['dr_months'] = [(int(m.year), int(m.month)) for m in months]
    context.user_data['dr_years'] = [int(y) for y in years]
    context.user_data['dr_is_family'] = True
    
    # Build keyboard
    keyboard = [
        [InlineKeyboardButton("📅 Отчет за месяц", callback_data=f"{CallbackPattern.DETAILED_REPORT_TYPE_PREFIX}month")],
        [InlineKeyboardButton("📆 Отчет за год", callback_data=f"{CallbackPattern.DETAILED_REPORT_TYPE_PREFIX}year")],
        [InlineKeyboardButton("🔙 Назад", callback_data=CallbackPattern.NAV_BACK)],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="start")]
    ]
    
    await query.edit_message_text(
        "📊 <b>Выберите тип отчета:</b>\n\n"
        f"Доступно месяцев с расходами: {len(months)}\n"
        f"Доступно лет с расходами: {len(years)}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

