"""Работа с сайтом: подключение ПК и печать заданий.

Подключение: uid + секрет -> api_register -> браузер на странице подключения (сотрудник там залогинен,
выбирает склад/место) -> api_claim каждые 3 сек, пока сайт не выдаст токен.
Дальше каждые 2 сек api_poll: «я на связи» + новые задания -> api_file -> печать -> api_result.
"""
import json
import logging
import platform
import secrets
import threading
import webbrowser

from . import api, config, printing, settings
from .state import print_lock, status
from .version import __version__

log = logging.getLogger(__name__)


class Worker(threading.Thread):
    def __init__(self, stop_event, notify, on_connected):
        super().__init__(name="worker", daemon=True)
        self.stop_event = stop_event
        self.notify = notify              # notify(text) - уведомление в трее
        self.on_connected = on_connected  # открыть окно настроек после первого подключения
        self.wake = threading.Event()     # разбудить цикл раньше (после «Подключить заново»)

    # ---------- подключение ----------

    def _register(self, data):
        if not data.get("uid") or not data.get("secret"):
            data["uid"] = secrets.token_hex(16)
            data["secret"] = secrets.token_hex(32)
        res = api.request(settings.server_url(data), "/print_agent/api_register", {
            "uid": data["uid"], "secret": data["secret"], "pc_name": platform.node(),
        })
        data["connect_url"] = res["connect_url"]
        settings.save(data)
        log.info("Ждём подключения в браузере: %s", res["connect_url"])
        webbrowser.open(res["connect_url"])
        self.notify("Подтвердите подключение компьютера в открывшемся браузере")

    def _wait_connect(self, data):
        if not data.get("connect_url"):
            self._register(data)
        status.text = "Ждёт подключения в браузере"
        try:
            res = api.request(settings.server_url(data), "/print_agent/api_claim",
                              {"uid": data["uid"], "secret": data["secret"]})
        except api.ApiError as e:
            if e.code == "unknown_device":
                # строку ожидания удалили (устарела) - регистрируемся заново
                data.pop("connect_url", None)
                settings.save(data)
                return config.CLAIM_INTERVAL
            raise
        status.online = True
        if res["status"] != "connected":
            return config.CLAIM_INTERVAL

        data["token"] = res["token"]
        for key in ("uid", "secret", "connect_url"):
            data.pop(key, None)
        settings.save(data)
        self._set_workplace(res["workplace"])
        log.info("Подключено: %s", status.line())
        self.notify(f"Подключено: {status.line()}. Выберите принтеры в настройках.")
        self.on_connected()
        return 0

    def _set_workplace(self, w):
        status.connected = True
        status.workplace = w.get("name") or ""
        status.zone = w.get("zone") or ""

    def reconnect(self):
        """Меню «Подключить заново»: забыть токен и пройти подключение через браузер."""
        data = settings.load()
        for key in ("token", "uid", "secret", "connect_url"):
            data.pop(key, None)
        settings.save(data)
        status.connected = False
        self.wake.set()

    def bind_browser(self):
        data = settings.load()
        if not data.get("token"):
            self.notify("Компьютер ещё не подключён к складу")
            return
        try:
            res = api.request(settings.server_url(data), "/print_agent/api_bind", {}, token=data["token"])
            webbrowser.open(res["url"])
        except Exception as e:
            log.exception("Привязка браузера")
            self.notify(f"Не удалось привязать браузер: {e}")

    # ---------- печать ----------

    def _poll(self, data):
        base = settings.server_url(data)
        try:
            res = api.request(base, "/print_agent/api_poll", {
                "version": __version__,
                "printers": json.dumps(data.get("printers", {}), ensure_ascii=False),
            }, token=data["token"])
        except api.ApiError as e:
            if e.status == 401:
                log.warning("Сайт не принимает токен (место отключено) - подключаемся заново")
                self.notify("Компьютер отключён на сайте - подключите его заново")
                self.reconnect()
                return 0
            raise
        status.online = True
        self._set_workplace(res["workplace"])
        for job in res.get("jobs", []):
            self._print_job(base, data, job)
        return config.POLL_INTERVAL

    def _print_job(self, base, data, job):
        token = data["token"]
        printer = data.get("printers", {}).get(job["format"])
        ok, error = True, None
        if not printer:
            ok, error = False, f"На компьютере не выбран принтер для формата {job['format']}"
            self.notify(error)
        else:
            try:
                with print_lock:
                    ctype, content = api.request(base, f"/print_agent/api_file/{job['id']}", token=token, timeout=90, raw=True)
                    kind = "pdf" if "pdf" in ctype else "png"
                    printing.print_file(printer, content, kind, job["title"])
                log.info("Напечатано: %s -> %s", job["title"], printer)
            except Exception as e:
                ok, error = False, str(e)
                log.exception("Ошибка печати задания %s", job["id"])
        api.request(base, "/print_agent/api_result",
                    {"id": job["id"], "ok": 1 if ok else 0, "error": error or ""}, token=token)

    # ---------- цикл ----------

    def run(self):
        while not self.stop_event.is_set():
            data = settings.load()
            try:
                delay = self._poll(data) if data.get("token") else self._wait_connect(data)
            except Exception as e:
                status.online = False
                status.text = "Нет связи с сайтом"
                log.warning("Сервер недоступен: %s", e)
                delay = config.ERROR_RETRY_INTERVAL
            self.wake.wait(delay)
            self.wake.clear()
