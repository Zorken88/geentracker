"""Tests de la gestión del subproceso."""

import sys
import time

from greentracker.process_manager import ProcessManager


def test_captures_output_and_returncode():
    pm = ProcessManager(f'{sys.executable} -c "print(\'hola\'); print(\'chao\')"')
    pm.start()
    pm.wait(timeout=15)
    time.sleep(0.3)  # dejar drenar al reader thread
    lines = pm.read_new_lines()
    assert "hola" in lines
    assert "chao" in lines
    assert pm.returncode == 0
    assert pm.running is False


def test_read_new_lines_drains():
    pm = ProcessManager(f'{sys.executable} -c "print(\'x\')"')
    pm.start()
    pm.wait(timeout=15)
    time.sleep(0.3)
    assert pm.read_new_lines() == ["x"]
    assert pm.read_new_lines() == []


def test_terminate_long_running_process():
    pm = ProcessManager(f'{sys.executable} -c "import time; time.sleep(60)"')
    pm.start()
    time.sleep(0.5)
    assert pm.running is True
    pm.terminate()
    assert pm.running is False
    assert pm.returncode is not None


def test_child_process_count_when_finished():
    pm = ProcessManager(f'{sys.executable} -c "print(1)"')
    pm.start()
    pm.wait(timeout=15)
    assert pm.child_process_count() == 0
