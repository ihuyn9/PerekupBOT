from decimal import Decimal


ITEM_KIND_REPAIR = "repair"
ITEM_KIND_RESALE = "resale"

STATUS_ACTIVE = "active"
STATUS_ISSUED = "issued"
STATUS_SOLD = "sold"

PRIORITY_NORMAL = "normal"
PRIORITY_URGENT = "urgent"

STAGE_NEW = "new"
STAGE_DIAGNOSTICS = "diagnostics"
STAGE_WAITING_PARTS = "waiting_parts"
STAGE_IN_PROGRESS = "in_progress"
STAGE_READY = "ready"
STAGE_BOUGHT = "bought"
STAGE_PREP = "prep"
STAGE_LISTED = "listed"
STAGE_RESERVED = "reserved"
STAGE_COMPLETED = "completed"

AVITO_CHAT_STAGE_NEW = "new"
AVITO_CHAT_STAGE_IN_PROGRESS = "in_progress"
AVITO_CHAT_STAGE_DEAL = "deal"
AVITO_CHAT_STAGE_CLOSED = "closed"

BUTTON_REPAIRS = "🔧 Ремонты"
BUTTON_RESALES = "💸 Перепродажи"
BUTTON_ACTIVE = "📦 Активные"
BUTTON_STATS = "📊 Статистика"
BUTTON_SEARCH = "🔎 Поиск"
BUTTON_AVITO_CHATS = "💬 Авито-чаты"
BUTTON_SETTINGS = "⚙️ Настройки"
BUTTON_MENU = "🏠 Меню"
BUTTON_ADMIN = "🛠 Админ-панель"

CANCEL_TEXT = "❌ Отмена"
SKIP_TEXT = "⏭ Пропустить"

ZERO = Decimal("0")

KIND_LABELS = {
    ITEM_KIND_REPAIR: "Ремонт",
    ITEM_KIND_RESALE: "Перепродажа",
}

STATUS_LABELS = {
    STATUS_ACTIVE: "Активное",
    STATUS_ISSUED: "Выдано",
    STATUS_SOLD: "Продано",
}

PRIORITY_LABELS = {
    PRIORITY_NORMAL: "Обычный",
    PRIORITY_URGENT: "Срочно",
}

ITEM_STAGE_LABELS = {
    STAGE_NEW: "Новый",
    STAGE_DIAGNOSTICS: "Диагностика",
    STAGE_WAITING_PARTS: "Ждет запчасть",
    STAGE_IN_PROGRESS: "В работе",
    STAGE_READY: "Готово",
    STAGE_BOUGHT: "Куплено",
    STAGE_PREP: "Подготовка",
    STAGE_LISTED: "Выставлено",
    STAGE_RESERVED: "В резерве",
    STAGE_COMPLETED: "Завершено",
}

AVITO_CHAT_STAGE_LABELS = {
    AVITO_CHAT_STAGE_NEW: "Новый лид",
    AVITO_CHAT_STAGE_IN_PROGRESS: "В работе",
    AVITO_CHAT_STAGE_DEAL: "Договорились",
    AVITO_CHAT_STAGE_CLOSED: "Закрыт",
}
