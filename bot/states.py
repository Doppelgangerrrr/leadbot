from aiogram.fsm.state import State, StatesGroup


class LeadForm(StatesGroup):
    service = State()
    name = State()
    phone = State()
    comment = State()
    confirm = State()


class Broadcast(StatesGroup):
    text = State()
    confirm = State()
