import os
from pathlib import Path

APP_NAME = "PrintAgent"
EXE_NAME = "PrintAgent.exe"

# Репозиторий, где лежат релизы (exe собирает GitHub Actions по тегу v*).
# Поменять при переносе в ConceptWebs.
GITHUB_REPO = "hovhannesmanukyan97/print-agent"

# Сайт, с которого берём задания печати. Для разработки можно переопределить в settings.json ("server_url").
SERVER_URL = "https://seller.15min.store"

UPDATE_CHECK_INTERVAL = 60 * 60  # раз в час
UPDATE_FIRST_CHECK_DELAY = 15    # первая проверка через 15 сек после запуска

POLL_INTERVAL = 2         # опрос заданий, сек
CLAIM_INTERVAL = 3        # ожидание подключения в браузере, сек
ERROR_RETRY_INTERVAL = 10 # нет связи с сервером, сек

# Форматы, которые сайт присылает в заданиях, и подписи для окна настроек
FORMATS = [
    ("a4", "Документы (листы A4)"),
    ("58x40", "Этикетки 58×40"),
    ("30x40", "Этикетки 30×40"),
    ("75x120", "Этикетки 75×120"),
]

# Программа живёт в папке пользователя: права админа не нужны, exe можно заменять при обновлении
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
INSTALL_EXE = INSTALL_DIR / EXE_NAME
LOG_FILE = INSTALL_DIR / "agent.log"
SETTINGS_FILE = INSTALL_DIR / "settings.json"

AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
