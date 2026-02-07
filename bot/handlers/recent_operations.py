"""Recent operations handler (last 10 expenses + incomes)."""

import html
import logging
from typing import Optional

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.database import crud, get_db
from bot.utils.formatters import format_amount, format_datetime, truncate_text
from bot.utils.helpers import get_user_id
from bot.utils.keyboards import get_home_button

logger = logging.getLogger(__name__)


CALLBACK_RECENT_OPS = "recent_ops"


def _pick_family_scope(
    context: ContextTypes.DEFAULT_TYPE,
    families: list,
) -> tuple[list[int], str, Optional[int]]:
    """Pick family scope for recent operations.

    Returns:
        (family_ids, label, single_family_id)
    """
    family_ids = [f.id for f in families] if families else []
    selected_id = context.user_data.get("selected_family_id")

    if selected_id in family_ids:
        selected_family = next((f for f in families if f.id == selected_id), None)
        label = selected_family.name if selected_family else "Семья"
        return ([int(selected_id)], label, int(selected_id))

    if len(family_ids) == 1:
        return ([int(family_ids[0])], families[0].name, int(family_ids[0]))

    return (family_ids, "Все семьи", None)


async def recent_operations_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show last 10 operations for current user."""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = await get_user_id(update, context)
    if not user_id:
        if query:
            await query.edit_message_text(
                "❌ Вы не зарегистрированы. Используйте команду /start для регистрации.",
                reply_markup=get_home_button(),
            )
        elif update.message:
            await update.message.reply_text(
                "❌ Вы не зарегистрированы. Используйте команду /start для регистрации.",
                reply_markup=get_home_button(),
            )
        return

    async for session in get_db():
        try:
            families = await crud.get_user_families(session, user_id)
            if not families:
                text = (
                    "🕘 <b>Мои последние операции</b>\n"
                    "<i>(показываю последние 10)</i>\n\n"
                    "❌ Вы не состоите ни в одной семье.\n"
                    "Сначала создайте семью или присоединитесь к существующей."
                )
                if query:
                    await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_home_button())
                elif update.message:
                    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_home_button())
                return

            family_ids, label, single_family_id = _pick_family_scope(context, families)

            operations = await crud.get_recent_user_operations(
                session,
                user_id=user_id,
                family_ids=family_ids,
                limit=10,
            )

            lines: list[str] = [
                "🕘 <b>Мои последние операции</b>",
                "<i>(показываю последние 10)</i>",
                f"📌 Область: <b>{html.escape(label)}</b>",
                "",
            ]

            if not operations:
                lines.append("✨ Операций пока нет.")
            else:
                show_family_name = (single_family_id is None and len(family_ids) > 1)
                for i, op in enumerate(operations, start=1):
                    op_type = op.get("op_type")
                    is_income = op_type == "income"

                    kind_emoji = "💹" if is_income else "💸"
                    kind_text = "Доход" if is_income else "Расход"

                    amount_str = format_amount(op["amount"])
                    dt_str = format_datetime(op["date"])
                    category = f"{op['category_icon']} {op['category_name']}"

                    lines.append(f"{i}. {kind_emoji} <b>{kind_text}</b> — <b>{amount_str}</b>")
                    lines.append(f"   {html.escape(category)} • {html.escape(dt_str)}")

                    if show_family_name:
                        lines.append(f"   👨‍👩‍👧‍👦 {html.escape(op['family_name'])}")

                    desc = op.get("description")
                    if desc:
                        safe_desc = html.escape(truncate_text(str(desc), max_length=80))
                        lines.append(f"   📝 {safe_desc}")

                    lines.append("")

            text = "\n".join(lines).strip()
            reply_markup = get_home_button()

            if query:
                await query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
            elif update.message:
                await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

            logger.info("Shown recent operations to user_id=%s (ops=%s)", user_id, len(operations))
            return
        except Exception as e:
            logger.error("Error showing recent operations: %s", e, exc_info=True)
            text = "❌ Произошла ошибка при загрузке операций. Попробуйте позже."
            if query:
                await query.edit_message_text(text, reply_markup=get_home_button())
            elif update.message:
                await update.message.reply_text(text, reply_markup=get_home_button())
            return


recent_operations_callback_handler = CallbackQueryHandler(
    recent_operations_show,
    pattern=f"^{CALLBACK_RECENT_OPS}$",
)

recent_operations_command_handler = CommandHandler(
    "recent",
    recent_operations_show,
)

