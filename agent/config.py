import os
from pathlib import Path

APP_NAME = "PrintAgent"
EXE_NAME = "PrintAgent.exe"

# Репозиторий, где лежат релизы (exe собирает GitHub Actions по тегу v*).
# Поменять при переносе в ConceptWebs.
GITHUB_REPO = "hovhannesmanukyan97/print-agent"

UPDATE_CHECK_INTERVAL = 60 * 60  # раз в час
UPDATE_FIRST_CHECK_DELAY = 15    # первая проверка через 15 сек после запуска

# Программа живёт в папке пользователя: права админа не нужны, exe можно заменять при обновлении
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
INSTALL_EXE = INSTALL_DIR / EXE_NAME
LOG_FILE = INSTALL_DIR / "agent.log"

AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
