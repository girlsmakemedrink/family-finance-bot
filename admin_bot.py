"""Admin panel Telegram bot for the Family Finance Bot.

Separate bot that connects to the same database and provides:
- Authentication by Telegram ID (ADMIN_USER_IDS)
- Global statistics
- Families list with pagination
- Family search
- Top families by expenses/incomes (month / all time)
- Family details: members, income/expense stats, activity by months, last transactions
"""

import asyncio
import html
import os
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import distinct, func, select, union
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.database import get_db, init_database
from bot.database.models import Category, CategoryTypeEnum, Expense, Family, FamilyMember, Income, User
from bot.handlers.errors import error_handler
from bot.handlers.middleware import enhanced_error_handler
from bot.utils.formatters import format_amount, format_date, format_datetime, truncate_text
from bot.utils.logging_config import get_logger, setup_logging
from config.settings import settings


setup_logging()
logger = get_logger(__name__)

PAGE_SIZE = 10
TOP_FAMILIES_LIMIT = 10
DETAIL_TRANSACTIONS_LIMIT = 10
MONTHLY_ACTIVITY_LIMIT = 12


def _get_admin_bot_token() -> str:
    """
    Backward-compatible token getter.

    Some deployments may have an older config/settings.py without ADMIN_BOT_TOKEN attribute.
    """
    token = getattr(settings, "ADMIN_BOT_TOKEN", "") or os.getenv("ADMIN_BOT_TOKEN", "")
    return token.strip()


@dataclass(frozen=True)
class SearchState:
    mode: str  # "id" | "name" | "username"


def _is_admin(update: Update) -> bool:
    if not update.effective_user:
        return False
    return update.effective_user.id in settings.ADMIN_USER_IDS


async def _deny_if_not_admin(update: Update) -> bool:
    if _is_admin(update):
        return False
    if update.effective_message:
        await update.effective_message.reply_text("⛔️ Доступ только для администраторов.")
    return True


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _prev_month_range(now: datetime) -> tuple[datetime, datetime]:
    this_start = _month_start(now)
    prev_end = this_start - timedelta(microseconds=1)
    prev_start = _month_start(prev_end)
    # [prev_start, this_start)
    return prev_start, this_start


def _safe(text: str) -> str:
    return html.escape(text, quote=False)


def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Статистика", callback_data="menu:stats")],
            [InlineKeyboardButton("👨‍👩‍👧‍👦 Все семьи", callback_data="menu:families")],
            [InlineKeyboardButton("🔍 Поиск семьи", callback_data="menu:search")],
            [InlineKeyboardButton("📈 Топ семей по расходам", callback_data="menu:top_exp")],
            [InlineKeyboardButton("📉 Топ семей по доходам", callback_data="menu:top_inc")],
        ]
    )


def _back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В меню", callback_data="menu:home")]])


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_not_admin(update):
        return
    text = (
        "🛠 <b>Админ-панель</b>\n\n"
        "Выберите раздел:"
    )
    await update.effective_message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=_home_kb(),
    )


async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_not_admin(update):
        return
    if not update.callback_query:
        return
    await update.callback_query.answer()

    action = (update.callback_query.data or "").split(":", 1)[-1]

    if action == "home":
        await update.callback_query.edit_message_text(
            "🛠 <b>Админ-панель</b>\n\nВыберите раздел:",
            parse_mode=ParseMode.HTML,
            reply_markup=_home_kb(),
        )
        return

    if action == "stats":
        await show_global_stats(update, context)
        return

    if action == "families":
        await show_families_page(update, context, page=0)
        return

    if action == "search":
        await show_search_menu(update, context)
        return

    if action == "top_exp":
        await show_tops_menu(update, context, kind="exp")
        return

    if action == "top_inc":
        await show_tops_menu(update, context, kind="inc")
        return


async def show_global_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    now = datetime.utcnow()
    cutoff = now - timedelta(days=30)

    async for session in get_db():
        total_families = (await session.execute(select(func.count(Family.id)))).scalar() or 0
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0

        active_ids_stmt = union(
            select(distinct(Expense.family_id)).where(Expense.date >= cutoff),
            select(distinct(Income.family_id)).where(Income.date >= cutoff),
        ).subquery()
        active_families = (await session.execute(select(func.count()).select_from(active_ids_stmt))).scalar() or 0

        total_expenses = (
            await session.execute(select(func.coalesce(func.sum(Expense.amount), 0)))
        ).scalar() or Decimal("0")
        total_incomes = (
            await session.execute(select(func.coalesce(func.sum(Income.amount), 0)))
        ).scalar() or Decimal("0")

    avg_expense = (total_expenses / total_families) if total_families else Decimal("0")
    avg_income = (total_incomes / total_families) if total_families else Decimal("0")

    text = (
        "📊 <b>Статистика (в целом)</b>\n\n"
        f"👨‍👩‍👧‍👦 <b>Семей:</b> {total_families}\n"
        f"👤 <b>Пользователей:</b> {total_users}\n"
        f"✅ <b>Активных семей (30 дней):</b> {active_families}\n\n"
        f"📉 <b>Расходы (все семьи, всё время):</b> {format_amount(total_expenses)}\n"
        f"📈 <b>Доходы (все семьи, всё время):</b> {format_amount(total_incomes)}\n\n"
        f"➗ <b>Средний расход на семью:</b> {format_amount(avg_expense)}\n"
        f"➗ <b>Средний доход на семью:</b> {format_amount(avg_income)}\n"
    )

    await update.callback_query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=_back_to_menu_kb(),
    )


async def show_families_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    if not update.callback_query:
        return

    offset = max(page, 0) * PAGE_SIZE

    async for session in get_db():
        total = (await session.execute(select(func.count(Family.id)))).scalar() or 0

        stmt = (
            select(
                Family.id,
                Family.name,
                Family.created_at,
                func.count(FamilyMember.id).label("members_count"),
            )
            .outerjoin(FamilyMember, FamilyMember.family_id == Family.id)
            .group_by(Family.id, Family.name, Family.created_at)
            .order_by(Family.created_at.desc())
            .limit(PAGE_SIZE)
            .offset(offset)
        )
        rows = (await session.execute(stmt)).all()

    pages = max((total - 1) // PAGE_SIZE + 1, 1) if total else 1
    page = max(min(page, pages - 1), 0)

    lines = [f"👨‍👩‍👧‍👦 <b>Все семьи</b> (стр. {page + 1}/{pages})\n"]
    if not rows:
        lines.append("Пока нет ни одной семьи.")
    else:
        for fam_id, name, created_at, members_count in rows:
            lines.append(
                f"• <b>#{fam_id}</b> — {_safe(truncate_text(name, 40))} "
                f"(<b>участников:</b> {members_count}) — {format_date(created_at)}"
            )

    keyboard: list[list[InlineKeyboardButton]] = []
    for fam_id, name, *_ in rows:
        keyboard.append(
            [InlineKeyboardButton(f"Подробнее #{fam_id}", callback_data=f"family:detail:{fam_id}")]
        )

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"families:page:{page - 1}"))
    if page < pages - 1:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"families:page:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("⬅️ В меню", callback_data="menu:home")])

    await update.callback_query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


async def families_page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_not_admin(update):
        return
    if not update.callback_query:
        return
    await update.callback_query.answer()

    data = update.callback_query.data or ""
    try:
        page = int(data.split(":")[-1])
    except Exception:
        page = 0
    await show_families_page(update, context, page=page)


async def _family_money_breakdown(
    session,
    family_id: int,
    kind: str,  # "expense" | "income"
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> tuple[Decimal, list[tuple[str, str, Decimal]]]:
    if kind == "expense":
        cat_type = CategoryTypeEnum.EXPENSE
        amount_col = Expense.amount
        date_col = Expense.date
        family_col = Expense.family_id
        join_col = Expense.category_id
    else:
        cat_type = CategoryTypeEnum.INCOME
        amount_col = Income.amount
        date_col = Income.date
        family_col = Income.family_id
        join_col = Income.category_id

    total_stmt = select(func.coalesce(func.sum(amount_col), 0)).where(family_col == family_id)
    if start:
        total_stmt = total_stmt.where(date_col >= start)
    if end:
        total_stmt = total_stmt.where(date_col < end)
    total = (await session.execute(total_stmt)).scalar() or Decimal("0")

    breakdown_stmt = (
        select(
            Category.name,
            Category.icon,
            func.coalesce(func.sum(amount_col), 0).label("total_amount"),
        )
        .join(Category, join_col == Category.id)
        .where(family_col == family_id)
        .where(Category.category_type == cat_type)
    )
    if start:
        breakdown_stmt = breakdown_stmt.where(date_col >= start)
    if end:
        breakdown_stmt = breakdown_stmt.where(date_col < end)
    breakdown_stmt = breakdown_stmt.group_by(Category.id, Category.name, Category.icon).order_by(
        func.sum(amount_col).desc()
    )

    breakdown_rows = (await session.execute(breakdown_stmt)).all()
    breakdown = [(r.name, r.icon, Decimal(str(r.total_amount))) for r in breakdown_rows]

    return Decimal(str(total)), breakdown


async def _family_members(session, family_id: int) -> list[tuple[str, Optional[str], str]]:
    stmt = (
        select(User.name, User.username, FamilyMember.role)
        .join(FamilyMember, FamilyMember.user_id == User.id)
        .where(FamilyMember.family_id == family_id)
        .order_by(FamilyMember.role, User.name)
    )
    rows = (await session.execute(stmt)).all()
    # role is enum, render value
    return [(r.name, r.username, getattr(r.role, "value", str(r.role))) for r in rows]


def _ym_extract(date_col):
    """Return (year_expr, month_expr) suitable for grouping for current DB."""
    if settings.is_sqlite:
        return (func.strftime("%Y", date_col), func.strftime("%m", date_col))
    return (func.extract("year", date_col), func.extract("month", date_col))


async def _family_monthly_activity(
    session,
    family_id: int,
    months: int = MONTHLY_ACTIVITY_LIMIT,
) -> list[tuple[int, int, int]]:
    now = datetime.utcnow()
    start = _month_start(now) - timedelta(days=31 * (months - 1))
    start = _month_start(start)

    exp_year, exp_month = _ym_extract(Expense.date)
    inc_year, inc_month = _ym_extract(Income.date)

    exp_stmt = (
        select(exp_year.label("y"), exp_month.label("m"), func.count(Expense.id).label("c"))
        .where(Expense.family_id == family_id)
        .where(Expense.date >= start)
        .group_by("y", "m")
    )
    inc_stmt = (
        select(inc_year.label("y"), inc_month.label("m"), func.count(Income.id).label("c"))
        .where(Income.family_id == family_id)
        .where(Income.date >= start)
        .group_by("y", "m")
    )

    exp_rows = (await session.execute(exp_stmt)).all()
    inc_rows = (await session.execute(inc_stmt)).all()

    counts: dict[tuple[int, int], int] = {}
    for r in exp_rows:
        y = int(r.y)
        m = int(r.m)
        counts[(y, m)] = counts.get((y, m), 0) + int(r.c)
    for r in inc_rows:
        y = int(r.y)
        m = int(r.m)
        counts[(y, m)] = counts.get((y, m), 0) + int(r.c)

    # Keep only last N months (in case DB has sparse/older data)
    result = sorted(((y, m, c) for (y, m), c in counts.items()), key=lambda x: (x[0], x[1]))
    return result[-months:]


async def _family_last_transactions(
    session,
    family_id: int,
    limit: int = DETAIL_TRANSACTIONS_LIMIT,
) -> list[str]:
    exp_stmt = (
        select(Expense)
        .options(selectinload(Expense.user), selectinload(Expense.category))
        .where(Expense.family_id == family_id)
        .order_by(Expense.date.desc())
        .limit(limit)
    )
    inc_stmt = (
        select(Income)
        .options(selectinload(Income.user), selectinload(Income.category))
        .where(Income.family_id == family_id)
        .order_by(Income.date.desc())
        .limit(limit)
    )
    expenses = list((await session.execute(exp_stmt)).scalars().all())
    incomes = list((await session.execute(inc_stmt)).scalars().all())

    items: list[tuple[datetime, str]] = []
    for e in expenses:
        items.append(
            (
                e.date,
                f"📉 <b>Расход</b> • {format_datetime(e.date)} • "
                f"{e.category.icon} {_safe(e.category.name)} • {format_amount(e.amount)} • "
                f"👤 {_safe(e.user.name)}"
                + (f" • 📝 {_safe(truncate_text(e.description, 60))}" if e.description else ""),
            )
        )
    for i in incomes:
        items.append(
            (
                i.date,
                f"📈 <b>Доход</b> • {format_datetime(i.date)} • "
                f"{i.category.icon} {_safe(i.category.name)} • {format_amount(i.amount)} • "
                f"👤 {_safe(i.user.name)}"
                + (f" • 📝 {_safe(truncate_text(i.description, 60))}" if i.description else ""),
            )
        )

    items.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in items[:limit]]


async def family_detail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_not_admin(update):
        return
    if not update.callback_query:
        return
    await update.callback_query.answer()

    data = update.callback_query.data or ""
    try:
        family_id = int(data.split(":")[-1])
    except Exception:
        await update.callback_query.edit_message_text(
            "❌ Не удалось определить ID семьи.",
            reply_markup=_back_to_menu_kb(),
        )
        return

    now = datetime.utcnow()
    this_month_start = _month_start(now)
    prev_month_start, prev_month_end = _prev_month_range(now)

    async for session in get_db():
        fam = (
            await session.execute(select(Family).where(Family.id == family_id))
        ).scalar_one_or_none()
        if not fam:
            await update.callback_query.edit_message_text(
                "❌ Семья не найдена.",
                reply_markup=_back_to_menu_kb(),
            )
            return

        members = await _family_members(session, family_id)

        inc_all, inc_all_by_cat = await _family_money_breakdown(session, family_id, "income")
        inc_this, _inc_this_by_cat = await _family_money_breakdown(
            session, family_id, "income", start=this_month_start
        )
        inc_prev, _inc_prev_by_cat = await _family_money_breakdown(
            session, family_id, "income", start=prev_month_start, end=prev_month_end
        )

        exp_all, exp_all_by_cat = await _family_money_breakdown(session, family_id, "expense")
        exp_this, _exp_this_by_cat = await _family_money_breakdown(
            session, family_id, "expense", start=this_month_start
        )
        exp_prev, _exp_prev_by_cat = await _family_money_breakdown(
            session, family_id, "expense", start=prev_month_start, end=prev_month_end
        )

        activity = await _family_monthly_activity(session, family_id, months=MONTHLY_ACTIVITY_LIMIT)
        last_tx = await _family_last_transactions(session, family_id, limit=DETAIL_TRANSACTIONS_LIMIT)

    balance = inc_all - exp_all

    member_lines: list[str] = []
    for name, username, role in members:
        uname = f"@{username}" if username else "—"
        role_label = "админ" if role == "admin" else "участник"
        member_lines.append(f"• {_safe(name)} ({_safe(uname)}) — <i>{role_label}</i>")

    def _fmt_breakdown(items: Iterable[tuple[str, str, Decimal]], limit: int = 8) -> str:
        rows = list(items)[:limit]
        if not rows:
            return "—"
        return "\n".join(
            f"• {icon} {_safe(name)} — {format_amount(amount)}" for name, icon, amount in rows
        )

    activity_lines = (
        "\n".join(f"• {m:02d}.{y} — {c}" for y, m, c in activity) if activity else "—"
    )
    last_lines = "\n".join(last_tx) if last_tx else "—"
    members_block = "\n".join(member_lines) if member_lines else "—"

    text = (
        f"🏠 <b>{_safe(fam.name)}</b> (ID: <b>{fam.id}</b>)\n"
        f"📅 Создана: {format_date(fam.created_at)}\n\n"
        f"👥 <b>Участники ({len(members)}):</b>\n{members_block}\n\n"
        f"📈 <b>Доходы</b>\n"
        f"• Всё время: {format_amount(inc_all)}\n"
        f"• Текущий месяц: {format_amount(inc_this)}\n"
        f"• Предыдущий месяц: {format_amount(inc_prev)}\n"
        f"• Категории (всё время):\n{_fmt_breakdown(inc_all_by_cat)}\n\n"
        f"📉 <b>Расходы</b>\n"
        f"• Всё время: {format_amount(exp_all)}\n"
        f"• Текущий месяц: {format_amount(exp_this)}\n"
        f"• Предыдущий месяц: {format_amount(exp_prev)}\n"
        f"• Категории (всё время):\n{_fmt_breakdown(exp_all_by_cat)}\n\n"
        f"⚖️ <b>Баланс (доходы − расходы):</b> {format_amount(balance)}\n\n"
        f"📅 <b>Активность по месяцам (последние 12):</b>\n{activity_lines}\n\n"
        f"🧾 <b>Последние 10 транзакций:</b>\n{last_lines}"
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ К списку семей", callback_data="menu:families")],
            [InlineKeyboardButton("⬅️ В меню", callback_data="menu:home")],
        ]
    )

    await update.callback_query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True,
    )


async def show_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return
    context.user_data.pop("admin_search", None)
    text = "🔍 <b>Поиск семьи</b>\n\nВыберите тип поиска:"
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("По ID семьи", callback_data="search:mode:id")],
            [InlineKeyboardButton("По названию (частично)", callback_data="search:mode:name")],
            [InlineKeyboardButton("По username участника", callback_data="search:mode:username")],
            [InlineKeyboardButton("⬅️ В меню", callback_data="menu:home")],
        ]
    )
    await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def search_mode_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_not_admin(update):
        return
    if not update.callback_query:
        return
    await update.callback_query.answer()

    mode = (update.callback_query.data or "").split(":")[-1]
    if mode not in {"id", "name", "username"}:
        await show_search_menu(update, context)
        return

    context.user_data["admin_search"] = SearchState(mode=mode)
    prompt = {
        "id": "Введите <b>ID семьи</b> числом:",
        "name": "Введите часть <b>названия семьи</b>:",
        "username": "Введите <b>username</b> участника (можно с @):",
    }[mode]
    await update.callback_query.edit_message_text(
        f"🔍 <b>Поиск семьи</b>\n\n{prompt}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="menu:search")]]),
    )


async def search_text_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_not_admin(update):
        return
    state: Optional[SearchState] = context.user_data.get("admin_search")
    if not state:
        return
    if not update.message:
        return

    query_text = (update.message.text or "").strip()
    mode = state.mode
    context.user_data.pop("admin_search", None)

    async for session in get_db():
        families: list[Family] = []
        total_found = 0

        if mode == "id":
            try:
                fid = int(query_text)
            except ValueError:
                await update.message.reply_text("❌ Нужно число. Попробуйте снова через меню поиска.")
                return
            fam = (await session.execute(select(Family).where(Family.id == fid))).scalar_one_or_none()
            families = [fam] if fam else []
            total_found = len(families)

        elif mode == "name":
            stmt = (
                select(Family)
                .where(Family.name.ilike(f"%{query_text}%"))
                .order_by(Family.created_at.desc())
                .limit(10)
            )
            families = list((await session.execute(stmt)).scalars().all())
            total_found = len(families)

        else:  # username
            uname = query_text.lstrip("@")
            stmt = (
                select(Family)
                .join(FamilyMember, FamilyMember.family_id == Family.id)
                .join(User, User.id == FamilyMember.user_id)
                .where(User.username.is_not(None))
                .where(User.username.ilike(f"%{uname}%"))
                .distinct()
                .order_by(Family.created_at.desc())
                .limit(TOP_FAMILIES_LIMIT)
            )
            families = list((await session.execute(stmt)).scalars().all())
            total_found = len(families)

    if not families:
        await update.message.reply_text(
            "Ничего не найдено.",
            reply_markup=_back_to_menu_kb(),
        )
        return

    lines = [f"🔎 <b>Найдено:</b> {total_found}\n"]
    kb_rows: list[list[InlineKeyboardButton]] = []
    for fam in families:
        lines.append(f"• <b>#{fam.id}</b> — {_safe(truncate_text(fam.name, 50))} — {format_date(fam.created_at)}")
        kb_rows.append([InlineKeyboardButton(f"Подробнее #{fam.id}", callback_data=f"family:detail:{fam.id}")])
    kb_rows.append([InlineKeyboardButton("🔍 Новый поиск", callback_data="menu:search")])
    kb_rows.append([InlineKeyboardButton("⬅️ В меню", callback_data="menu:home")])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )


async def show_tops_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    if not update.callback_query:
        return
    title = "📈 <b>Топ семей по расходам</b>" if kind == "exp" else "📉 <b>Топ семей по доходам</b>"
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("За месяц", callback_data=f"tops:{kind}:month")],
            [InlineKeyboardButton("За всё время", callback_data=f"tops:{kind}:all")],
            [InlineKeyboardButton("⬅️ В меню", callback_data="menu:home")],
        ]
    )
    await update.callback_query.edit_message_text(title + "\n\nВыберите период:", parse_mode=ParseMode.HTML, reply_markup=kb)


async def tops_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_not_admin(update):
        return
    if not update.callback_query:
        return
    await update.callback_query.answer()

    data = update.callback_query.data or ""
    try:
        _, kind, period = data.split(":")
    except ValueError:
        await update.callback_query.edit_message_text("❌ Некорректный запрос.", reply_markup=_back_to_menu_kb())
        return

    now = datetime.utcnow()
    start = _month_start(now) if period == "month" else None

    model = Expense if kind == "exp" else Income
    amount_col = model.amount
    date_col = model.date

    async for session in get_db():
        stmt = (
            select(
                Family.id,
                Family.name,
                func.coalesce(func.sum(amount_col), 0).label("total_amount"),
            )
            .join(model, model.family_id == Family.id)
        )
        if start:
            stmt = stmt.where(date_col >= start)
        stmt = stmt.group_by(Family.id, Family.name).order_by(func.sum(amount_col).desc()).limit(TOP_FAMILIES_LIMIT)
        rows = (await session.execute(stmt)).all()

    title = "📈 <b>Топ-10 семей по расходам</b>" if kind == "exp" else "📉 <b>Топ-10 семей по доходам</b>"
    subtitle = "за месяц" if period == "month" else "за всё время"

    if not rows:
        await update.callback_query.edit_message_text(
            f"{title}\n<i>({subtitle})</i>\n\nПока нет данных.",
            parse_mode=ParseMode.HTML,
            reply_markup=_back_to_menu_kb(),
        )
        return

    lines = [f"{title}\n<i>({subtitle})</i>\n"]
    kb_rows: list[list[InlineKeyboardButton]] = []
    for idx, (fid, name, total_amount) in enumerate(rows, start=1):
        amount = Decimal(str(total_amount))
        lines.append(f"{idx}. <b>#{fid}</b> — {_safe(truncate_text(name, 40))}: {format_amount(amount)}")
        kb_rows.append([InlineKeyboardButton(f"Подробнее #{fid}", callback_data=f"family:detail:{fid}")])
    kb_rows.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:{'top_exp' if kind=='exp' else 'top_inc'}")])
    kb_rows.append([InlineKeyboardButton("⬅️ В меню", callback_data="menu:home")])

    await update.callback_query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb_rows),
        disable_web_page_preview=True,
    )


class AdminBotRunner:
    def __init__(self) -> None:
        self.application: Optional[Application] = None
        self.shutdown_event: asyncio.Event = asyncio.Event()

    async def setup(self) -> None:
        admin_token = _get_admin_bot_token()
        if not admin_token:
            raise ValueError("ADMIN_BOT_TOKEN is not set. Please add it to .env")

        logger.info("Initializing database (admin bot)...")
        await init_database()

        self.application = Application.builder().token(admin_token).build()

        # Commands
        self.application.add_handler(CommandHandler("start", start_cmd))

        # Menu callbacks
        self.application.add_handler(CallbackQueryHandler(menu_cb, pattern=r"^menu:(home|stats|families|search|top_exp|top_inc)$"))

        # Families
        self.application.add_handler(CallbackQueryHandler(families_page_cb, pattern=r"^families:page:\d+$"))
        self.application.add_handler(CallbackQueryHandler(family_detail_cb, pattern=r"^family:detail:\d+$"))

        # Search
        self.application.add_handler(CallbackQueryHandler(search_mode_cb, pattern=r"^search:mode:(id|name|username)$"))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_text_msg))

        # Tops
        self.application.add_handler(CallbackQueryHandler(tops_cb, pattern=r"^tops:(exp|inc):(month|all)$"))

        # Error handling
        self.application.add_error_handler(enhanced_error_handler)
        self.application.add_error_handler(error_handler)

    async def start(self) -> None:
        if not self.application:
            await self.setup()
        assert self.application is not None

        logger.info("Starting admin bot polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=["message", "callback_query"])
        logger.info("Admin bot is running.")

    async def stop(self) -> None:
        if not self.application:
            return
        try:
            if self.application.updater and self.application.updater.running:
                await self.application.updater.stop()
            if self.application.running:
                await self.application.stop()
            await self.application.shutdown()
        except Exception as e:
            logger.warning(f"Error during admin bot shutdown: {e}")

    async def shutdown(self, sig: Optional[int] = None) -> None:
        if sig:
            logger.info(f"Received exit signal {sig}...")
        self.shutdown_event.set()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))

        try:
            await self.start()
            await self.shutdown_event.wait()
        finally:
            await self.stop()


async def main() -> None:
    logger.info("=" * 50)
    logger.info("Admin Panel Bot Starting")
    logger.info("=" * 50)
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info(f"Database: {settings.DATABASE_URL}")
    logger.info(f"Admins count: {len(settings.ADMIN_USER_IDS)}")
    logger.info(f"Admin bot token set: {bool(_get_admin_bot_token())}")
    logger.info("=" * 50)

    runner = AdminBotRunner()
    await runner.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

