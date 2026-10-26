import logging
import os
import shutil
import sys
import threading
import tkinter as tk
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from . import autostart, config, settings_window, updater, winutil
from .state import status
from .version import __version__
from .worker import Worker

log = logging.getLogger("agent")


def setup_logging():
    config.INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(config.LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def install_if_needed():
    """Первый запуск скачанного exe: копируем себя в папку установки, включаем автозапуск и
    запускаем оттуда. Возвращает True, если текущий процесс должен завершиться."""
    if not getattr(sys, "frozen", False):
        return False  # python app.py - режим разработки
    current = Path(sys.executable).resolve()
    if current == config.INSTALL_EXE.resolve():
        return False

    if not winutil.acquire_single_instance(config.APP_NAME):
        winutil.message_box("Print Agent уже запущен - значок в трее рядом с часами.", "Print Agent")
        return True

    config.INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, config.INSTALL_EXE)
    autostart.enable(config.INSTALL_EXE)
    log.info("Установлено в %s", config.INSTALL_EXE)
    winutil.message_box(
        "Print Agent установлен и будет запускаться вместе с Windows.\n"
        "Значок программы - в трее рядом с часами.\n\n"
        "Скачанный файл теперь можно удалить.",
        "Print Agent",
    )
    winutil.start_detached(config.INSTALL_EXE, "--after-update")  # подождёт, пока мы отпустим мьютекс
    return True


def make_icon_image():
    # простая иконка принтера, чтобы не возить с собой файл
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((16, 6, 48, 24), fill=(255, 255, 255), outline=(40, 40, 40), width=3)
    d.rounded_rectangle((4, 22, 60, 48), radius=6, fill=(33, 150, 83), outline=(40, 40, 40), width=3)
    d.rectangle((16, 38, 48, 60), fill=(255, 255, 255), outline=(40, 40, 40), width=3)
    return img


def run_tray():
    stop_event = threading.Event()
    icon = pystray.Icon(config.APP_NAME, make_icon_image(), f"Print Agent {__version__}")

    def on_restart():
        stop_event.set()
        icon.visible = False

    def check_updates(icon_, item):
        def worker():
            status = updater.check_and_update(on_restart)
            log.info(status)
            icon.notify(status, "Print Agent")
        threading.Thread(target=worker, daemon=True).start()

    def toggle_autostart(icon_, item):
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable(Path(sys.executable).resolve() if getattr(sys, "frozen", False) else config.INSTALL_EXE)

    def open_folder(icon_, item):
        os.startfile(config.INSTALL_DIR)

    def quit_app(icon_, item):
        stop_event.set()
        icon.stop()
        settings_window.call(root.quit)

    def notify(text):
        try:
            icon.notify(text, "Print Agent")
        except Exception:
            log.exception("Уведомление")

    worker = Worker(stop_event, notify, on_connected=lambda: settings_window.open_window(worker))

    icon.menu = pystray.Menu(
        pystray.MenuItem(f"Print Agent {__version__}", None, enabled=False),
        pystray.MenuItem(lambda item: status.line(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Настройки", lambda icon_, item: settings_window.open_window(worker), default=True),
        pystray.MenuItem("Привязать браузер", lambda icon_, item: threading.Thread(target=worker.bind_browser, daemon=True).start()),
        pystray.MenuItem("Проверить обновления", check_updates),
        pystray.MenuItem("Запускать при включении компьютера", toggle_autostart,
                         checked=lambda item: autostart.is_enabled()),
        pystray.MenuItem("Открыть папку программы", open_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Выход", quit_app),
    )

    def on_ready(icon_):
        icon_.visible = True
        if "--after-update" in sys.argv:
            icon_.notify(f"Работает версия {__version__}", "Print Agent")
        updater.start_background_loop(on_restart, stop_event)
        worker.start()

        # строка статуса в меню: pystray на Windows пересобирает меню только по update_menu()
        def refresh_menu():
            while not stop_event.wait(3):
                icon_.update_menu()
        threading.Thread(target=refresh_menu, name="menu", daemon=True).start()

    # tkinter работает только из главного потока (иначе падает при закрытии окна),
    # поэтому главный поток держит скрытое окно Tk, а значок в трее живёт в своём потоке
    root = tk.Tk()
    root.withdraw()
    settings_window.init(root)
    icon.run_detached(setup=on_ready)
    root.mainloop()


def main():
    setup_logging()
    log.info("Запуск версии %s, exe %s", __version__, sys.executable)

    if install_if_needed():
        return

    # после обновления/установки старый процесс ещё может держать мьютекс пару секунд
    wait = 20 if "--after-update" in sys.argv else 0
    if not winutil.acquire_single_instance(config.APP_NAME, wait_seconds=wait):
        log.info("Уже запущена другая копия - выходим")
        return

    updater.cleanup_old()
    run_tray()
    log.info("Выход")
