from aiogram.fsm.state import State, StatesGroup


class AvitoStates(StatesGroup):
    waiting_reply_text = State()
