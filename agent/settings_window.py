"""Окно «Настройки»: к какому складу/месту подключён ПК и какой принтер печатает какой формат.
Все вызовы tkinter - только в главном потоке (app.run_tray держит там скрытое окно Tk);
другие потоки просят открыть окно через call(), очередь разбирается каждые 150 мс."""
import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import config, printing, settings
from .state import print_lock, status

log = logging.getLogger(__name__)
NONE = "- не печатать -"
_queue = queue.Queue()
_root = None
_win = None


def init(root):
    global _root
    _root = root
    _pump()


def _pump():
    while True:
        try:
            fn = _queue.get_nowait()
        except queue.Empty:
            break
        try:
            fn()
        except Exception:
            log.exception("Окно настроек")
    _root.after(150, _pump)


def call(fn):
    """Выполнить fn в главном потоке (из трея, из потока работы с сервером)."""
    _queue.put(fn)


def open_window(worker):
    call(lambda: _show(worker))


def _show(worker):
    global _win
    if _win is not None and _win.winfo_exists():
        _win.deiconify()
        _win.lift()
        _win.focus_force()
        return

    data = settings.load()
    printers = printing.list_printers()

    win = _win = tk.Toplevel(_root)
    win.title("Print Agent - настройки")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    frame = ttk.Frame(win, padding=16)
    frame.grid()

    ttk.Label(frame, text="Рабочее место", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
    place = tk.StringVar(win, value=status.line() if status.connected else status.text)
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
                messagebox.showinfo("Print Agent", "Сначала выберите принтер", parent=win)
                return
            try:
                with print_lock:
                    printing.print_file(name, printing.test_page(label), "png", "Print Agent - пробная печать")
            except Exception as e:
                messagebox.showerror("Print Agent", f"Не удалось напечатать: {e}", parent=win)

        ttk.Button(frame, text="Пробная печать", command=test).grid(row=row, column=2, padx=(8, 0), pady=3)

    def save():
        fresh = settings.load()
        fresh["printers"] = {fmt: box.get() for fmt, box in boxes.items() if box.get() != NONE}
        settings.save(fresh)
        win.destroy()

    def reconnect():
        if messagebox.askyesno("Print Agent", "Подключить компьютер заново? Откроется браузер, где нужно будет выбрать склад и рабочее место.", parent=win):
            worker.reconnect()
            win.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(16, 0))
    ttk.Button(buttons, text="Привязать браузер", command=lambda: threading.Thread(target=worker.bind_browser, daemon=True).start()).pack(side="left")
    ttk.Button(buttons, text="Подключить заново", command=reconnect).pack(side="left", padx=8)
    ttk.Button(buttons, text="Отмена", command=win.destroy).pack(side="right")
    ttk.Button(buttons, text="Сохранить", command=save).pack(side="right", padx=8)

    def refresh():
        if not win.winfo_exists():
            return
        place.set(status.line() if status.connected else status.text)
        win.after(2000, refresh)

    refresh()
