"""Constants for messages and mappings used across handlers."""

from typing import Dict

# ============================================================================
# User Messages
# ============================================================================

# Error Messages
ERROR_USER_NOT_REGISTERED = "❌ Вы не зарегистрированы. Используйте команду /start для регистрации."
ERROR_USER_NOT_FOUND = "❌ Ошибка: пользователь не найден. Используйте команду /start."
ERROR_TEXT_INPUT_REQUIRED = "❌ Пожалуйста, введите текстовое название семьи."
ERROR_GENERIC = "❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."

# Telegram message settings
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
HTML_PARSE_MODE = "HTML"

# Family Messages
FAMILY_NAME_MIN_LENGTH = 2
FAMILY_NAME_MAX_LENGTH = 100
INVITE_CODE_MIN_LENGTH = 6
INVITE_CODE_MAX_LENGTH = 16

MSG_FAMILY_NAME_TOO_SHORT = f"❌ Название семьи слишком короткое. Введите минимум {FAMILY_NAME_MIN_LENGTH} символа."
MSG_FAMILY_NAME_TOO_LONG = f"❌ Название семьи слишком длинное. Максимум {FAMILY_NAME_MAX_LENGTH} символов."
MSG_INVITE_CODE_INVALID = f"❌ Некорректный код приглашения. Код должен содержать от {INVITE_CODE_MIN_LENGTH} до {INVITE_CODE_MAX_LENGTH} символов."
MSG_FAMILY_NOT_FOUND = (
    "❌ Семья с таким кодом приглашения не найдена.\n\n"
    "Проверьте правильность кода и попробуйте снова."
)
MSG_ALREADY_MEMBER = "ℹ️ Вы уже состоите в семье <b>{family_name}</b>!"

# Welcome Messages
WELCOME_NEW_USER = (
    "👋 Привет, <b>{name}</b>!\n\n"
    "Добро пожаловать в <b>Family Finance Bot</b> — твой семейный "
    "финансовый помощник! 💰\n\n"
    "🔹 <b>Что я умею:</b>\n"
    "• 👨‍👩‍👧‍👦 Совместный учёт для всей семьи\n"
    "• 💵 Учёт расходов и доходов\n"
    "• 🏷️ Категории (свои + стандартные)\n"
    "• ⚡ Быстрые расходы — шаблоны\n"
    "• 📊 Детальная аналитика и графики\n"
    "• 📅 Автоматические месячные сводки\n"
    "• 📄 Экспорт: HTML отчёты\n\n"
)

WELCOME_RETURNING_USER = (
    "С возвращением, <b>{name}</b>! 👋\n\n"
    "Рад снова видеть тебя в <b>Family Finance Bot</b>! 💰\n\n"
)

MSG_WITH_FAMILIES = (
    "👨‍👩‍👧‍👦 <b>Ваши семьи:</b>\n"
    "{families_list}"
    "\n"
)

MSG_QUICK_ACTIONS_FOOTER = (
    "✨ <b>Быстрые действия:</b>\n"
    "Используйте кнопки ниже для быстрого доступа 👇"
)

MSG_WITHOUT_FAMILIES = (
    "🏠 <b>Для начала работы вам нужно:</b>\n"
    "• Создать свою семью, или\n"
    "• Присоединиться к существующей семье\n\n"
    "Выберите действие ниже 👇"
)

# ============================================================================
# Settings Mappings
# ============================================================================

CURRENCY_MAPPING: Dict[str, str] = {
    "currency_rub": "₽",
    "currency_usd": "$",
    "currency_eur": "€",
    "currency_uah": "₴"
}

TIMEZONE_MAPPING: Dict[str, str] = {
    "tz_europe_moscow": "Europe/Moscow",
    "tz_asia_yekaterinburg": "Asia/Yekaterinburg",
    "tz_asia_novosibirsk": "Asia/Novosibirsk",
    "tz_asia_vladivostok": "Asia/Vladivostok",
    "tz_europe_kiev": "Europe/Kiev",
    "tz_asia_almaty": "Asia/Almaty"
}

DATE_FORMAT_MAPPING: Dict[str, str] = {
    "date_format_dmy": "DD.MM.YYYY",
    "date_format_mdy": "MM/DD/YYYY",
    "date_format_ymd": "YYYY-MM-DD"
}

TIME_MAPPING: Dict[str, str] = {
    "summary_time_08": "08:00",
    "summary_time_10": "10:00",
    "summary_time_12": "12:00",
    "summary_time_18": "18:00"
}

# ============================================================================
# Validation Limits
# ============================================================================

MAX_AMOUNT = "999999999.99"
MSG_INVALID_AMOUNT = f"❌ Неверная сумма. Введите положительное число до {MAX_AMOUNT}"
MSG_INVALID_FORMAT = "❌ Неверный формат. Введите число (например: 5000 или 5000.50)"

