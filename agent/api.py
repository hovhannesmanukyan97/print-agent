"""Запросы к сайту (controllers/print_agent.php в проекте 15min.store)."""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from . import config


class ApiError(Exception):
    def __init__(self, status, message, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


def _ssl_context(base_url):
    # локальный сайт разработки (*.loc) - с самоподписанным сертификатом
    if urllib.parse.urlparse(base_url).hostname.endswith(".loc"):
        return ssl._create_unverified_context()
    return None


def request(base_url, path, data=None, token=None, timeout=30, raw=False):
    """POST (если есть data) или GET. raw=True - вернуть (content_type, bytes) вместо JSON."""
    url = base_url + path
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": config.APP_NAME})
    if token:
        req.add_header("X-Print-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(base_url)) as resp:
            content = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            payload = json.loads(content)
            raise ApiError(e.code, payload.get("message") or str(e), payload.get("code")) from None
        except ValueError:
            raise ApiError(e.code, f"Сервер ответил {e.code}") from None

    if raw and "application/json" not in ctype:
        return ctype, content
    payload = json.loads(content)
    if raw:
        raise ApiError(200, payload.get("message") or "Файл не получен", payload.get("code"))
    return payload
