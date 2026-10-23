import ctypes
import os
import subprocess
import time

ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_mutex_handle = None


def acquire_single_instance(name, wait_seconds=0):
    """Именованный мьютекс: вторая копия программы не запустится.
    wait_seconds > 0 - подождать, пока старая копия закроется (нужно после обновления)."""
    global _mutex_handle
    deadline = time.time() + wait_seconds
    while True:
        handle = _kernel32.CreateMutexW(None, False, f"Local\\{name}")
        if handle and ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
            _mutex_handle = handle
            return True
        if handle:
            _kernel32.CloseHandle(ctypes.c_void_p(handle))
        if time.time() >= deadline:
            return False
        time.sleep(0.5)


def message_box(text, title):
    MB_ICONINFORMATION = 0x40
    ctypes.windll.user32.MessageBoxW(None, text, title, MB_ICONINFORMATION)


def start_detached(exe_path, *args):
    # PYINSTALLER_RESET_ENVIRONMENT - новый onefile-exe распакуется в свою temp-папку,
    # а не попробует использовать папку текущего процесса, которая удалится при его выходе
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(exe_path), *args], env=env, creationflags=flags, close_fds=True)
