from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    waiting_avito_client_id = State()
    waiting_avito_client_secret = State()
    waiting_avito_repair_ad_ids = State()
    waiting_template_title = State()
    waiting_template_text = State()
    waiting_template_edit_value = State()
    waiting_reset_confirmation = State()
