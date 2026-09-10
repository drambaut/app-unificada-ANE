"""Lanza y reutiliza subprocesos locales (FastAPI) para las sub-apps que no
son Streamlit, de forma que puedan embeberse vía iframe dentro del shell
unificado. El registro de procesos vive a nivel de módulo (no en
st.session_state) para sobrevivir a los reruns de Streamlit y para
compartirse entre pestañas/sesiones del navegador.
"""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, List

_PROCESSES: Dict[str, subprocess.Popen] = {}


def _port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            return sock.connect_ex((host, port)) == 0
        except OSError:
            return False


def ensure_running(
    name: str,
    cwd: Path,
    cmd: List[str],
    port: int,
    host: str = "127.0.0.1",
    startup_timeout: float = 15.0,
) -> bool:
    """Garantiza que el proceso `name` esté escuchando en `port`.

    Devuelve True si el puerto quedó disponible (proceso ya corría o se
    lanzó y respondió a tiempo), False si no se pudo confirmar.
    """
    if _port_open(host, port):
        return True

    proc = _PROCESSES.get(name)
    if proc is not None and proc.poll() is None:
        # El proceso sigue vivo pero el puerto aún no responde: esperar un poco.
        pass
    else:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _PROCESSES[name] = proc

    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.5)
    return _port_open(host, port)


def is_running(name: str) -> bool:
    proc = _PROCESSES.get(name)
    return proc is not None and proc.poll() is None
