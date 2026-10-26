"""Настройки программы в settings.json. Секрет устройства и токен шифруются средствами Windows (DPAPI):
скопированный на другой ПК файл не расшифровать."""
import base64
import json
import logging
import threading

import win32crypt

from . import config

log = logging.getLogger(__name__)
_lock = threading.Lock()
_SECRET_KEYS = ("secret", "token")


def _protect(text):
    blob = win32crypt.CryptProtectData(text.encode(), config.APP_NAME, None, None, None, 0)
    return base64.b64encode(blob).decode()


def _unprotect(text):
    _, data = win32crypt.CryptUnprotectData(base64.b64decode(text), None, None, None, 0)
    return data.decode()


def load():
    with _lock:
        try:
            raw = json.loads(config.SETTINGS_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raw = {}
        except Exception:
            log.exception("settings.json повреждён - начинаем с чистых настроек")
            raw = {}
    data = dict(raw)
    for key in _SECRET_KEYS:
        if data.get(key):
            try:
                data[key] = _unprotect(data[key])
            except Exception:
                log.warning("Не удалось расшифровать %s - подключимся заново", key)
                data[key] = None
    data.setdefault("printers", {})
    return data


def save(data):
    raw = dict(data)
    for key in _SECRET_KEYS:
        if raw.get(key):
            raw[key] = _protect(raw[key])
    with _lock:
        config.INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = config.SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(config.SETTINGS_FILE)


def server_url(data):
    return (data.get("server_url") or config.SERVER_URL).rstrip("/")
