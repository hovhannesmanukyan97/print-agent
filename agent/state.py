"""Общее состояние программы между потоками (трей, работа с сервером, обновление, окно настроек)."""
import threading

# пока держим - идёт печать; обновление ждёт его, чтобы не перезапуститься посреди задания
print_lock = threading.Lock()


class Status:
    def __init__(self):
        self.connected = False
        self.workplace = ""   # «Приёмка 1»
        self.zone = ""        # склад
        self.text = "Запуск..."
        self.online = False   # последний запрос к серверу прошёл

    def line(self):
        if self.connected:
            where = f"{self.workplace} ({self.zone})" if self.zone else self.workplace
            return f"{where}" + ("" if self.online else " - нет связи")
        return self.text


status = Status()
