from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import texts

BTN_NEW_LEAD = "📝 Оставить заявку"
BTN_MY_LEADS = "📋 Мои заявки"
BTN_PRICES = "💰 Услуги и цены"
BTN_ABOUT = "ℹ️ О нас"
BTN_ADMIN = "🛠 Админ-панель"
BTN_CANCEL = "❌ Отмена"
BTN_SKIP = "Пропустить"
BTN_SEND_CONTACT = "📱 Отправить мой номер"


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_NEW_LEAD)],
        [KeyboardButton(text=BTN_MY_LEADS), KeyboardButton(text=BTN_PRICES)],
        [KeyboardButton(text=BTN_ABOUT)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SEND_CONTACT, request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_SKIP)], [KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


def services_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, (title, price) in texts.SERVICES.items():
        builder.button(text=f"{title} · {price}", callback_data=f"svc:{code}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="lead:send")
    builder.button(text="✏️ Заполнить заново", callback_data="lead:restart")
    builder.button(text="❌ Отменить", callback_data="lead:cancel")
    builder.adjust(1)
    return builder.as_markup()


def status_kb(lead_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, title in texts.STATUSES.items():
        builder.button(text=title, callback_data=f"st:{lead_id}:{code}")
    builder.adjust(2)
    return builder.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Разослать", callback_data="bc:send")
    builder.button(text="❌ Отмена", callback_data="bc:cancel")
    return builder.as_markup()
