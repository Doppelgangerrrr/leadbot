"""Все тексты и справочники бота. Чтобы адаптировать бота под другой бизнес, достаточно поменять этот файл."""

from html import escape

COMPANY = "Мастерская «Ремонт за день»"

ABOUT = (
    f"<b>{COMPANY}</b>\n\n"
    "Ремонтируем смартфоны, ноутбуки и ПК. Бесплатная диагностика, гарантия на работы до 6 месяцев.\n\n"
    "📍 ул. Примерная, 1\n"
    "🕘 Ежедневно 10:00–20:00\n"
    "📞 +7 (900) 000-00-00"
)

# код услуги -> (название, цена)
SERVICES: dict[str, tuple[str, str]] = {
    "phone": ("Ремонт смартфона", "от 1 500 ₽"),
    "laptop": ("Ремонт ноутбука", "от 2 000 ₽"),
    "pc": ("Сборка и апгрейд ПК", "от 1 000 ₽"),
    "data": ("Восстановление данных", "от 2 500 ₽"),
    "other": ("Другое", "по договорённости"),
}

STATUSES: dict[str, str] = {
    "new": "🆕 Новая",
    "in_work": "🔧 В работе",
    "done": "✅ Выполнена",
    "rejected": "🚫 Отклонена",
}


def greeting(first_name: str) -> str:
    return (
        f"Здравствуйте, {escape(first_name)}! 👋\n\n"
        f"Это бот <b>{COMPANY}</b>. Здесь можно оставить заявку на ремонт, "
        "узнать цены и следить за статусом своих заявок."
    )


def price_list() -> str:
    lines = [f"• {title} — <b>{price}</b>" for title, price in SERVICES.values()]
    return "<b>Услуги и цены</b>\n\n" + "\n".join(lines) + "\n\nТочную стоимость назовём после диагностики."


def service_title(code: str) -> str:
    return SERVICES.get(code, (code, ""))[0]


def lead_summary(data: dict) -> str:
    """Черновик заявки, который клиент подтверждает перед отправкой."""
    return (
        "<b>Проверьте заявку</b>\n\n"
        f"Услуга: {escape(service_title(data['service']))}\n"
        f"Имя: {escape(data['name'])}\n"
        f"Телефон: {escape(data['phone'])}\n"
        f"Комментарий: {escape(data.get('comment') or '—')}"
    )


def lead_card(lead: dict) -> str:
    """Карточка заявки для администратора."""
    username = f"@{lead['username']}" if lead.get("username") else "—"
    return (
        f"<b>Заявка №{lead['id']}</b> · {STATUSES[lead['status']]}\n\n"
        f"Услуга: {escape(service_title(lead['service']))}\n"
        f"Имя: {escape(lead['name'])}\n"
        f"Телефон: <code>{escape(lead['phone'])}</code>\n"
        f"Telegram: {escape(username)} (id <code>{lead['user_id']}</code>)\n"
        f"Комментарий: {escape(lead['comment'] or '—')}\n\n"
        f"Создана: {lead['created_at']}\n"
        f"Обновлена: {lead['updated_at']}"
    )


def user_lead_line(lead: dict) -> str:
    return f"№{lead['id']} · {escape(service_title(lead['service']))} · {STATUSES[lead['status']]} · {lead['created_at']}"


def status_changed(lead: dict) -> str:
    return f"Статус вашей заявки №{lead['id']} изменён: <b>{STATUSES[lead['status']]}</b>"


def stats_text(stats: dict) -> str:
    by_status = "\n".join(f"{title}: {stats['by_status'].get(code, 0)}" for code, title in STATUSES.items())
    return (
        "<b>Статистика</b>\n\n"
        f"Пользователей: {stats['users']}\n"
        f"Заявок всего: {stats['total']}\n"
        f"Заявок сегодня: {stats['today']}\n\n"
        f"{by_status}"
    )


ADMIN_HELP = (
    "<b>Админ-панель</b>\n\n"
    "/stats — статистика по заявкам\n"
    "/export — выгрузка всех заявок в CSV\n"
    "/broadcast — рассылка всем пользователям\n\n"
    "Статус заявки меняется кнопками под её карточкой."
)
