import hashlib
import json
import logging
import os
import re
import sys
import threading
import urllib.request
from pathlib import Path

from . import config, winutil
from .version import __version__

log = logging.getLogger(__name__)

SHA_ASSET = config.EXE_NAME + ".sha256"
_lock = threading.Lock()


def parse_version(text):
    nums = re.findall(r"\d+", text.split("-")[0])
    return tuple(int(n) for n in nums[:3]) if nums else (0,)


def _http_get(url, accept=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": config.APP_NAME})
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_latest_release():
    """{'version': '1.2.3', 'exe_url': ..., 'sha_url': ...} или None, если релиза нет."""
    url = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"
    data = json.loads(_http_get(url, accept="application/vnd.github+json"))
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    if config.EXE_NAME not in assets or SHA_ASSET not in assets:
        log.warning("В релизе %s нет %s или %s", data.get("tag_name"), config.EXE_NAME, SHA_ASSET)
        return None
    return {
        "version": data["tag_name"].lstrip("v"),
        "exe_url": assets[config.EXE_NAME],
        "sha_url": assets[SHA_ASSET],
    }


def can_self_update():
    # обновляем только собранный exe, и только из папки установки (там у нас есть права на запись)
    return getattr(sys, "frozen", False) and Path(sys.executable).resolve() == config.INSTALL_EXE.resolve()


def cleanup_old():
    old = config.INSTALL_DIR / (config.EXE_NAME + ".old")
    try:
        old.unlink(missing_ok=True)
    except OSError:
        pass  # ещё занят - удалим при следующем запуске


def check_and_update(on_restart):
    """Возвращает строку-статус для пользователя. on_restart() вызывается перед выходом процесса."""
    if not _lock.acquire(blocking=False):
        return "Проверка уже идёт"
    try:
        release = get_latest_release()
        if release is None:
            return "Релизов пока нет"
        if parse_version(release["version"]) <= parse_version(__version__):
            return f"Установлена последняя версия {__version__}"
        if not can_self_update():
            log.info("Есть версия %s, но запуск не из папки установки - пропускаем", release["version"])
            return f"Есть версия {release['version']} (в режиме разработки не обновляется)"

        log.info("Обновление %s -> %s", __version__, release["version"])
        expected = _http_get(release["sha_url"]).decode().split()[0].strip().lower()
        content = _http_get(release["exe_url"], timeout=300)
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            log.error("Хеш не совпал: ожидали %s, получили %s", expected, actual)
            return "Обновление скачалось с ошибкой, попробую позже"

        exe = config.INSTALL_EXE
        new = exe.with_name(config.EXE_NAME + ".new")
        old = exe.with_name(config.EXE_NAME + ".old")
        new.write_bytes(content)
        old.unlink(missing_ok=True)
        # запущенный exe нельзя перезаписать, но можно переименовать
        os.replace(exe, old)
        try:
            os.replace(new, exe)
        except OSError:
            os.replace(old, exe)  # вернуть как было
            raise

        log.info("Перезапуск в версию %s", release["version"])
        winutil.start_detached(exe, "--after-update")
        on_restart()
        os._exit(0)
    except Exception as e:
        log.exception("Ошибка проверки обновлений")
        return f"Не удалось проверить обновления: {e}"
    finally:
        _lock.release()


def start_background_loop(on_restart, stop_event):
    def loop():
        if stop_event.wait(config.UPDATE_FIRST_CHECK_DELAY):
            return
        while True:
            log.info(check_and_update(on_restart))
            if stop_event.wait(config.UPDATE_CHECK_INTERVAL):
                return

    threading.Thread(target=loop, name="updater", daemon=True).start()
