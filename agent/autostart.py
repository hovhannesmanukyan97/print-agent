import winreg

from . import config


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, config.AUTOSTART_REG_KEY) as key:
            winreg.QueryValueEx(key, config.APP_NAME)
            return True
    except FileNotFoundError:
        return False


def enable(exe_path):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, config.AUTOSTART_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, config.APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, config.AUTOSTART_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, config.APP_NAME)
    except FileNotFoundError:
        pass
