import re


def normalize_person_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D+", "", value)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return digits


def normalize_telegram_contact(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    if normalized.startswith("https://t.me/"):
        normalized = normalized.removeprefix("https://t.me/")
    elif normalized.startswith("t.me/"):
        normalized = normalized.removeprefix("t.me/")
    if normalized and not normalized.startswith("@"):
        normalized = f"@{normalized}"
    return normalized
