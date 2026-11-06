import asyncio
import csv
import io
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message, TelegramObject

from .. import keyboards as kb
from .. import texts
from ..config import Config
from ..db import Database
from ..states import Broadcast

log = logging.getLogger(__name__)


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, config: Config) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in config.admin_ids


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
@router.message(F.text == kb.BTN_ADMIN)
async def admin_help(message: Message) -> None:
    await message.answer(texts.ADMIN_HELP)


@router.message(Command("stats"))
async def stats(message: Message, db: Database) -> None:
    await message.answer(texts.stats_text(await db.stats()))


@router.message(Command("export"))
async def export(message: Message, db: Database) -> None:
    leads = await db.all_leads()
    if not leads:
        await message.answer("Заявок пока нет.")
        return

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")  # ';' — чтобы Excel с русской локалью сразу разбил по колонкам
    writer.writerow(["№", "Статус", "Услуга", "Имя", "Телефон", "Telegram", "Комментарий", "Создана", "Обновлена"])
    for lead in leads:
        writer.writerow([
            lead["id"],
            texts.STATUSES[lead["status"]],
            texts.service_title(lead["service"]),
            lead["name"],
            lead["phone"],
            f"@{lead['username']}" if lead["username"] else lead["user_id"],
            lead["comment"] or "",
            lead["created_at"],
            lead["updated_at"],
        ])

    file = BufferedInputFile(buffer.getvalue().encode("utf-8-sig"), filename="leads.csv")
    await message.answer_document(file, caption=f"Всего заявок: {len(leads)}")


# ---------- смена статуса заявки ----------

@router.callback_query(F.data.startswith("st:"))
async def change_status(callback: CallbackQuery, db: Database, bot: Bot) -> None:
    _, lead_id, status = callback.data.split(":")
    if status not in texts.STATUSES:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    lead = await db.get_lead(int(lead_id))
    if lead is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if lead["status"] == status:
        await callback.answer("Статус уже установлен")
        return

    lead = await db.set_status(lead["id"], status)
    try:
        await callback.message.edit_text(texts.lead_card(lead), reply_markup=kb.status_kb(lead["id"]))
    except TelegramBadRequest as exc:
        log.warning("Не удалось обновить карточку заявки %s: %s", lead["id"], exc)

    try:
        await bot.send_message(lead["user_id"], texts.status_changed(lead))
    except TelegramAPIError:
        await callback.answer("Статус изменён, но клиент заблокировал бота", show_alert=True)
        return
    await callback.answer(f"Статус: {texts.STATUSES[status]}")


# ---------- рассылка ----------

@router.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext) -> None:
    await state.set_state(Broadcast.text)
    await message.answer("Отправьте текст рассылки (можно с HTML-разметкой). /cancel — отмена.")


@router.message(Broadcast.text, F.text)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.html_text)
    await state.set_state(Broadcast.confirm)
    await message.answer(f"<b>Предпросмотр:</b>\n\n{message.html_text}", reply_markup=kb.broadcast_confirm_kb())


@router.callback_query(Broadcast.confirm, F.data == "bc:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.")
    await callback.answer()


@router.callback_query(Broadcast.confirm, F.data == "bc:send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    text = (await state.get_data())["text"]
    await state.clear()
    await callback.message.edit_text("📤 Рассылка запущена…")
    await callback.answer()

    sent = failed = 0
    for user_id in await db.all_user_ids():
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(user_id, text)
                sent += 1
            except TelegramAPIError:
                failed += 1
        except TelegramAPIError:
            failed += 1
        await asyncio.sleep(0.05)  # держимся ниже лимита Telegram ~30 сообщений/сек

    await callback.message.answer(f"Рассылка завершена. Доставлено: {sent}, не доставлено: {failed}.")
