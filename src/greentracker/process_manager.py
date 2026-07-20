"""Gestión del subproceso del usuario (aspecto ambiental — ISO 14001).

Lanza el comando con ``subprocess.Popen``, captura stdout/stderr en tiempo
real y permite terminar limpiamente todo el árbol de procesos.
"""

from __future__ import annotations

import re
import subprocess
import threading
from collections import deque

import psutil

# Secuencias ANSI (colores, limpiar pantalla, mover cursor) que herramientas
# como tsx/next emiten y que descuadran el panel de output de la TUI
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|[\x00-\x08\x0b-\x1f]")


def _clean_line(line: str) -> str:
    return _ANSI_RE.sub("", line.rstrip("\r\n"))


class ProcessManager:
    def __init__(self, command: str, max_output_lines: int = 5000) -> None:
        self.command = command
        self._proc: subprocess.Popen | None = None
        self._lines: deque[str] = deque(maxlen=max_output_lines)
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            # sin stdin: si el hijo heredara la terminal competiría con la TUI
            # por las teclas (ej: tsx watch se "come" la tecla S de stop)
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    def _read_output(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in self._proc.stdout:
            cleaned = _clean_line(line)
            if not cleaned.strip():
                continue
            with self._lock:
                self._lines.append(cleaned)
        self._proc.stdout.close()

    def read_new_lines(self) -> list[str]:
        """Drena las líneas de output acumuladas desde la última llamada."""
        with self._lock:
            lines = list(self._lines)
            self._lines.clear()
        return lines

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode if self._proc else None

    def child_process_count(self) -> int:
        if not self.running:
            return 0
        try:
            return len(psutil.Process(self._proc.pid).children(recursive=True))
        except psutil.Error:
            return 0

    def process_tree(self) -> list[psutil.Process]:
        """Proceso raíz + hijos recursivos (para métricas de recursos)."""
        if not self.running:
            return []
        try:
            root = psutil.Process(self._proc.pid)
            return [root, *root.children(recursive=True)]
        except psutil.Error:
            return []

    def wait(self, timeout: float | None = None) -> int | None:
        if self._proc is None:
            return None
        try:
            return self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def terminate(self, timeout: float = 5.0) -> None:
        """Termina el árbol completo: hijos primero, luego el proceso raíz."""
        if self._proc is None or self._proc.poll() is not None:
            return
        procs: list[psutil.Process] = []
        try:
            root = psutil.Process(self._proc.pid)
            procs = [*root.children(recursive=True), root]
        except psutil.Error:
            self._proc.terminate()
            procs = []
        for proc in procs:
            try:
                proc.terminate()
            except psutil.Error:
                pass
        if procs:
            _, alive = psutil.wait_procs(procs, timeout=timeout)
            for proc in alive:
                try:
                    proc.kill()
                except psutil.Error:
                    pass
        try:
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
