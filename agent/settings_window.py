"""Окно «Настройки»: к какому складу/месту подключён ПК и какой принтер печатает какой формат.
tkinter живёт в своём потоке (основной поток занят иконкой в трее); одновременно открыто одно окно."""
import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import config, printing, settings
from .state import print_lock, status

log = logging.getLogger(__name__)
NONE = "- не печатать -"
_open = threading.Lock()


def open_window(worker):
    if not _open.acquire(blocking=False):
        return  # уже открыто
    threading.Thread(target=_run, args=(worker,), name="settings", daemon=True).start()


def _run(worker):
    try:
        _build(worker)
    except Exception:
        log.exception("Окно настроек")
    finally:
        _open.release()


def _build(worker):
    data = settings.load()
    printers = printing.list_printers()

    root = tk.Tk()
    root.title("Print Agent - настройки")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frame = ttk.Frame(root, padding=16)
    frame.grid()

    ttk.Label(frame, text="Рабочее место", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
    place = tk.StringVar(value=status.line() if status.connected else "Не подключено")
    ttk.Label(frame, textvariable=place).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

    ttk.Label(frame, text="Принтеры", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, columnspan=3, sticky="w")
    boxes = {}
    for i, (fmt, label) in enumerate(config.FORMATS):
        row = 3 + i
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        box = ttk.Combobox(frame, values=[NONE] + printers, state="readonly", width=34)
        box.set(data["printers"].get(fmt) or NONE)
        box.grid(row=row, column=1, pady=3)
        boxes[fmt] = box

        def test(fmt=fmt, label=label):
            name = boxes[fmt].get()
            if name == NONE:
                messagebox.showinfo("Print Agent", "Сначала выберите принтер", parent=root)
                return
            try:
                with print_lock:
                    printing.print_file(name, printing.test_page(label), "png", "Print Agent - пробная печать")
            except Exception as e:
                messagebox.showerror("Print Agent", f"Не удалось напечатать: {e}", parent=root)

        ttk.Button(frame, text="Пробная печать", command=test).grid(row=row, column=2, padx=(8, 0), pady=3)

    def save():
        fresh = settings.load()
        fresh["printers"] = {fmt: box.get() for fmt, box in boxes.items() if box.get() != NONE}
        settings.save(fresh)
        root.destroy()

    def reconnect():
        if messagebox.askyesno("Print Agent", "Подключить компьютер заново? Откроется браузер, где нужно будет выбрать склад и рабочее место.", parent=root):
            worker.reconnect()
            root.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(16, 0))
    ttk.Button(buttons, text="Привязать браузер", command=lambda: threading.Thread(target=worker.bind_browser, daemon=True).start()).pack(side="left")
    ttk.Button(buttons, text="Подключить заново", command=reconnect).pack(side="left", padx=8)
    ttk.Button(buttons, text="Отмена", command=root.destroy).pack(side="right")
    ttk.Button(buttons, text="Сохранить", command=save).pack(side="right", padx=8)

    def refresh():
        place.set(status.line() if status.connected else status.text)
        root.after(2000, refresh)

    refresh()
    root.mainloop()
