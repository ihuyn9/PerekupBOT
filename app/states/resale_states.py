from aiogram.fsm.state import State, StatesGroup


class ResaleStates(StatesGroup):
    waiting_model = State()
    waiting_buy_price = State()
    waiting_note = State()
    waiting_expense_title = State()
    waiting_expense_amount = State()
    waiting_close_amount = State()
