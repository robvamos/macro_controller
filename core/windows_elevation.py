"""Helper Windows per rilevare privilegi elevati e proporre un riavvio admin."""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import psutil
import win32gui
import win32process


TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_CLASS = 20
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wintypes.DWORD)]


def is_current_process_elevated():
    """Restituisce True se il processo corrente gira come amministratore."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _get_process_elevation(pid):
    """Restituisce True/False se noto, altrimenti None."""
    process_handle = None
    token_handle = None
    try:
        kernel32 = ctypes.windll.kernel32
        advapi32 = ctypes.windll.advapi32

        process_handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not process_handle:
            return None

        token_handle = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(token_handle)):
            return None

        elevation = TOKEN_ELEVATION()
        size = wintypes.DWORD(ctypes.sizeof(elevation))
        return_length = wintypes.DWORD()
        success = advapi32.GetTokenInformation(
            token_handle,
            TOKEN_ELEVATION_CLASS,
            ctypes.byref(elevation),
            size,
            ctypes.byref(return_length),
        )
        if not success:
            return None
        return bool(elevation.TokenIsElevated)
    except Exception:
        return None
    finally:
        if token_handle and getattr(token_handle, "value", None):
            try:
                ctypes.windll.kernel32.CloseHandle(token_handle.value)
            except Exception:
                pass
        if process_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(process_handle)
            except Exception:
                pass


def get_process_ids_by_name(exe_name):
    """Restituisce i pid del processo con nome corrispondente."""
    target = (exe_name or "").lower()
    if not target:
        return []

    pids = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if (proc.info.get("name") or "").lower() == target:
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def target_requires_elevation(exe_name):
    """Valuta se il target in esecuzione richiede un riavvio elevato dell'app."""
    if is_current_process_elevated():
        return {
            "requires_restart": False,
            "reason": "current_process_already_elevated",
            "target_pids": [],
        }

    target_pids = get_process_ids_by_name(exe_name)
    if not target_pids:
        return {
            "requires_restart": False,
            "reason": "target_not_running",
            "target_pids": [],
        }

    for pid in target_pids:
        elevated = _get_process_elevation(pid)
        if elevated is True:
            return {
                "requires_restart": True,
                "reason": "target_process_elevated",
                "target_pids": target_pids,
            }

    return {
        "requires_restart": False,
        "reason": "target_not_elevated_or_unknown",
        "target_pids": target_pids,
    }


def build_restart_as_admin_message(exe_name):
    """Testo user-facing per la proposta di riavvio come amministratore."""
    return (
        f"'{exe_name}' risulta avviato come amministratore, mentre il macro manager no.\n\n"
        "In questa situazione mouse, click e tasti possono non arrivare al gioco.\n"
        "Vuoi riavviare ora l'applicazione come amministratore?"
    )


def relaunch_current_process_as_admin():
    """Rilancia il processo corrente come amministratore."""
    executable, parameters, working_directory = _build_relaunch_command()
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        executable,
        parameters,
        working_directory,
        1,
    )
    return result > 32


def close_duplicate_macro_manager_instances(*, current_pid=None, only_when_current_elevated=True, timeout_seconds=3.0):
    """Chiude altre istanze dello stesso Macro Manager.

    Quando l'istanza corrente e' elevata, elimina eventuali duplicati rimasti
    aperti dopo il riavvio admin.
    """
    if current_pid is None:
        current_pid = psutil.Process().pid

    if only_when_current_elevated and not is_current_process_elevated():
        return []

    current_script = _get_current_script_path()
    if not current_script:
        return []

    duplicate_processes = _collect_duplicate_macro_manager_processes(current_pid, current_script)

    closed_pids = []
    for proc in duplicate_processes:
        try:
            proc.terminate()
            closed_pids.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    deadline = time.monotonic() + timeout_seconds
    while duplicate_processes and time.monotonic() < deadline:
        still_running = []
        for proc in duplicate_processes:
            try:
                if proc.is_running():
                    still_running.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if not still_running:
            duplicate_processes = []
            break
        time.sleep(0.1)
        duplicate_processes = still_running

    for proc in duplicate_processes:
        try:
            proc.kill()
            if proc.pid not in closed_pids:
                closed_pids.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return closed_pids


def enforce_single_macro_manager_instance(*, current_pid=None, timeout_seconds=3.0):
    """Applica una policy di istanza unica.

    - se l'istanza corrente e' elevata, chiude i duplicati e resta viva
    - se l'istanza corrente non e' elevata e trova duplicati, si considera secondaria
    """
    if current_pid is None:
        current_pid = psutil.Process().pid

    current_script = _get_current_script_path()
    if not current_script:
        return {"keep_current": True, "closed_pids": [], "duplicate_pids": []}

    duplicates = _collect_duplicate_macro_manager_processes(current_pid, current_script)

    duplicate_pids = [proc.pid for proc in duplicates]
    if not duplicates:
        return {"keep_current": True, "closed_pids": [], "duplicate_pids": []}

    if not is_current_process_elevated():
        return {"keep_current": False, "closed_pids": [], "duplicate_pids": duplicate_pids}

    closed_pids = close_duplicate_macro_manager_instances(
        current_pid=current_pid,
        only_when_current_elevated=False,
        timeout_seconds=timeout_seconds,
    )
    return {"keep_current": True, "closed_pids": closed_pids, "duplicate_pids": duplicate_pids}


def _build_relaunch_command():
    """Costruisce il comando di riavvio rispettando exe congelato o script Python."""
    if getattr(sys, "frozen", False):
        executable = sys.executable
        parameters = " ".join(_quote_argument(arg) for arg in sys.argv[1:])
        working_directory = str(Path(executable).resolve().parent)
        return executable, parameters, working_directory

    executable = sys.executable
    script_path = str(Path(sys.argv[0]).resolve())
    argv = [script_path, *sys.argv[1:]]
    parameters = " ".join(_quote_argument(arg) for arg in argv)
    working_directory = str(Path(script_path).resolve().parent)

    pythonw_candidate = Path(executable).with_name("pythonw.exe")
    if pythonw_candidate.exists():
        executable = str(pythonw_candidate)

    return executable, parameters, working_directory


def _get_current_script_path():
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve()).lower()
    if not sys.argv:
        return None
    return str(Path(sys.argv[0]).resolve()).lower()


def _matches_macro_manager_instance(proc, current_script):
    try:
        cmdline = proc.info.get("cmdline") or []
        if getattr(sys, "frozen", False):
            exe_path = proc.exe()
            return str(Path(exe_path).resolve()).lower() == current_script

        normalized_cmdline = [str(Path(arg).resolve()).lower() if arg.endswith(".py") else str(arg).lower() for arg in cmdline]
        return current_script in normalized_cmdline
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return False


def _collect_duplicate_macro_manager_processes(current_pid, current_script):
    duplicate_processes = {}

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pid = proc.info["pid"]
            if pid == current_pid:
                continue
            if _matches_macro_manager_instance(proc, current_script):
                duplicate_processes[pid] = proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    for pid in get_macro_manager_window_process_ids():
        if pid == current_pid or pid in duplicate_processes:
            continue
        try:
            duplicate_processes[pid] = psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return list(duplicate_processes.values())


def get_macro_manager_window_process_ids(window_title="Macro Manager"):
    """Rileva i pid che possiedono una finestra principale Macro Manager."""
    process_ids = set()

    def _enum_window(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if title != window_title:
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid:
                process_ids.add(pid)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum_window, None)
    except Exception:
        return []
    return list(process_ids)


def _quote_argument(value):
    text = str(value)
    if not text:
        return '""'
    return subprocess.list2cmdline([text])
