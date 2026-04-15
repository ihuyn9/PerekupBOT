from aiogram.fsm.state import State, StatesGroup


class RepairStates(StatesGroup):
    waiting_model = State()
    waiting_client_name = State()
    waiting_client_phone = State()
    waiting_client_telegram = State()
    waiting_note = State()
    waiting_expense_title = State()
    waiting_expense_amount = State()
    waiting_prepayment_amount = State()
    waiting_close_amount = State()
