import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from .. import texts
from ..config import Config
from ..db import Database
from ..notify import notify_admins
from ..states import LeadForm

router = Router(name="user")
# Клиентская часть работает только в личке, чтобы бот не отвечал на сообщения в админ-чате.
router.message.filter(F.chat.type == "private")


def normalize_phone(raw: str) -> str | None:
    """Приводит номер к виду +79001234567. Возвращает None, если это не похоже на телефон."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if not 11 <= len(digits) <= 15:
        return None
    return "+" + digits


async def show_main_menu(message: Message, config: Config, text: str) -> None:
    await message.answer(text, reply_markup=kb.main_menu(message.chat.id in config.admin_ids))


# ---------- главное меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database, config: Config) -> None:
    await state.clear()
    await db.upsert_user(message.from_user)
    await show_main_menu(message, config, texts.greeting(message.from_user.first_name))


@router.message(StateFilter("*"), Command("cancel"))
@router.message(StateFilter("*"), F.text == kb.BTN_CANCEL)
async def cancel(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    await show_main_menu(message, config, "Действие отменено.")


@router.message(F.text == kb.BTN_PRICES)
async def prices(message: Message) -> None:
    await message.answer(texts.price_list())


@router.message(F.text == kb.BTN_ABOUT)
async def about(message: Message) -> None:
    await message.answer(texts.ABOUT)


@router.message(F.text == kb.BTN_MY_LEADS)
async def my_leads(message: Message, db: Database) -> None:
    leads = await db.user_leads(message.from_user.id)
    if not leads:
        await message.answer("У вас пока нет заявок. Нажмите «📝 Оставить заявку», чтобы создать первую.")
        return
    lines = "\n".join(texts.user_lead_line(lead) for lead in leads)
    await message.answer(f"<b>Ваши последние заявки</b>\n\n{lines}")


# ---------- анкета заявки ----------

async def start_form(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(LeadForm.service)
    await message.answer("Оформляем заявку. Отменить можно в любой момент.", reply_markup=kb.cancel_kb())
    await message.answer("Выберите услугу:", reply_markup=kb.services_kb())


@router.message(Command("new"))
@router.message(F.text == kb.BTN_NEW_LEAD)
async def new_lead(message: Message, state: FSMContext, db: Database) -> None:
    await db.upsert_user(message.from_user)
    await start_form(message, state)


@router.callback_query(LeadForm.service, F.data.startswith("svc:"))
async def form_service(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    if code not in texts.SERVICES:
        await callback.answer("Неизвестная услуга", show_alert=True)
        return
    await state.update_data(service=code)
    await state.set_state(LeadForm.name)
    await callback.message.edit_text(f"Услуга: <b>{texts.service_title(code)}</b>")
    await callback.message.answer("Как к вам обращаться?")
    await callback.answer()


@router.message(LeadForm.service)
async def form_service_text(message: Message) -> None:
    await message.answer("Пожалуйста, выберите услугу кнопкой выше 👆")


@router.message(LeadForm.name, F.text)
async def form_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 64:
        await message.answer("Имя должно быть от 2 до 64 символов. Попробуйте ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)
    await message.answer(
        "Оставьте номер телефона: нажмите кнопку ниже или введите вручную.",
        reply_markup=kb.phone_kb(),
    )


@router.message(LeadForm.phone, F.contact)
@router.message(LeadForm.phone, F.text)
async def form_phone(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw)
    if phone is None:
        await message.answer("Не похоже на номер телефона. Пример: +7 900 123-45-67")
        return
    await state.update_data(phone=phone)
    await state.set_state(LeadForm.comment)
    await message.answer(
        "Опишите проблему или пожелания (модель устройства, что случилось). Можно пропустить.",
        reply_markup=kb.skip_kb(),
    )


@router.message(LeadForm.comment, F.text)
async def form_comment(message: Message, state: FSMContext) -> None:
    comment = None if message.text == kb.BTN_SKIP else message.text.strip()[:1000]
    await state.update_data(comment=comment)
    await state.set_state(LeadForm.confirm)
    await message.answer("Почти готово!", reply_markup=kb.cancel_kb())
    await message.answer(texts.lead_summary(await state.get_data()), reply_markup=kb.confirm_kb())


@router.callback_query(LeadForm.confirm, F.data == "lead:send")
async def form_send(callback: CallbackQuery, state: FSMContext, db: Database, config: Config, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    lead = await db.create_lead(
        user_id=callback.from_user.id,
        name=data["name"],
        phone=data["phone"],
        service=data["service"],
        comment=data.get("comment"),
    )
    await notify_admins(bot, config, texts.lead_card(lead), reply_markup=kb.status_kb(lead["id"]))
    await callback.message.edit_text(
        f"✅ Заявка №{lead['id']} отправлена! Мы свяжемся с вами в ближайшее время."
    )
    await show_main_menu(callback.message, config, "Статус заявки можно посмотреть в «📋 Мои заявки».")
    await callback.answer()


@router.callback_query(LeadForm.confirm, F.data == "lead:restart")
async def form_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_form(callback.message, state)
    await callback.answer()


@router.callback_query(LeadForm.confirm, F.data == "lead:cancel")
async def form_cancel(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    await state.clear()
    await callback.message.edit_text("Заявка отменена.")
    await show_main_menu(callback.message, config, "Чем ещё можем помочь?")
    await callback.answer()


@router.callback_query(F.data.startswith(("svc:", "lead:")))
async def stale_form_button(callback: CallbackQuery) -> None:
    await callback.answer("Эта анкета уже неактуальна. Начните новую заявку из меню.", show_alert=True)


@router.message(StateFilter(LeadForm))
async def form_wrong_input(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте ответ текстом.")


@router.message()
async def fallback(message: Message, config: Config) -> None:
    await show_main_menu(message, config, "Не понял вас. Воспользуйтесь меню ниже 👇")
