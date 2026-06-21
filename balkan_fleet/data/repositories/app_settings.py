"""
Editable application settings (key/value).

Currently used for the business name, which a super-admin can change in Settings.
Reads fall back to the default from config so the app always has a name to show,
even before anything has been saved.
"""

from sqlalchemy import text
from core.db import get_engine
from config.settings import APP_NAME

BUSINESS_NAME_KEY = "business_name"
LOGO_KEY = "company_logo"


def get_setting(key: str, default: str = "") -> str:
    try:
        with get_engine().connect() as conn:
            val = conn.execute(
                text("SELECT value FROM app_settings WHERE key = :k"), {"k": key}
            ).scalar()
        return val if val not in (None, "") else default
    except Exception:
        return default


def set_setting(key: str, value: str):
    with get_engine().begin() as conn:
        conn.execute(
            text("""INSERT INTO app_settings (key, value, updated_at)
                    VALUES (:k, :v, datetime('now'))
                    ON CONFLICT(key) DO UPDATE SET value = :v, updated_at = datetime('now')"""),
            {"k": key, "v": value},
        )


def get_business_name() -> str:
    return get_setting(BUSINESS_NAME_KEY, APP_NAME)


def set_business_name(name: str):
    set_setting(BUSINESS_NAME_KEY, (name or "").strip() or APP_NAME)


def get_logo() -> str:
    return get_setting(LOGO_KEY, "")


def set_logo(b64: str):
    set_setting(LOGO_KEY, b64 or "")


def clear_logo():
    set_setting(LOGO_KEY, "")
