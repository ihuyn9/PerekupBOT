from aiogram.fsm.state import State, StatesGroup


class CommonStates(StatesGroup):
    waiting_search_query = State()
    waiting_stats_month = State()
    waiting_item_edit_value = State()
    waiting_custom_reminder = State()
