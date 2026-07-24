"""Tests de la API de librería (greentracker.track).

Verifica que el modo librería cumple el mismo modelo que el CLI:
- mide el proceso actual (aspecto ambiental = intérprete anfitrión)
- persiste la sesión en el CSV (Tabla 15) con Ecuación 3 (HC = E × I)
- nunca termina el proceso anfitrión
"""

import os
import time
from types import SimpleNamespace

import pytest

import greentracker
from greentracker.csv_writer import read_sessions
from greentracker.tracker import GreenTracker


class FakeCodeCarbon:
    """Simula OfflineEmissionsTracker con energías conocidas (CPU dominante)."""

    def __init__(self):
        self._total_cpu_energy = SimpleNamespace(kWh=0.008)
        self._total_gpu_energy = SimpleNamespace(kWh=0.0005)
        self._total_ram_energy = SimpleNamespace(kWh=0.0015)
        self._total_energy = SimpleNamespace(kWh=0.010)
        self._cpu_power = SimpleNamespace(W=12.0)
        self._gpu_power = SimpleNamespace(W=0.5)
        self._ram_power = SimpleNamespace(W=1.5)

    def start(self):
        pass

    def stop(self):
        return 0.0


@pytest.fixture(autouse=True)
def fake_codecarbon(monkeypatch):
    monkeypatch.setattr(GreenTracker, "_create_cc_tracker", lambda self: FakeCodeCarbon())


def test_track_measures_current_process_and_persists(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    with greentracker.track(project="lib-demo", label="entrenamiento",
                            interval=0.2, csv_file=csv_file) as session:
        assert session.tracking_active
        # el árbol medido tiene como raíz al proceso anfitrión (este pytest)
        assert session.process.process_tree()[0].pid == os.getpid()
        time.sleep(0.5)

    assert session.summary is not None
    assert session.summary.energy_consumed == pytest.approx(0.010)
    # Ecuación 3 con el factor HuellaChile por defecto
    assert session.summary.emissions == pytest.approx(0.010 * 0.245)
    assert session.summary.command == "entrenamiento"

    sessions = read_sessions(csv_file, "lib-demo")
    assert len(sessions) == 1
    assert sessions[0]["project"] == "lib-demo"


def test_track_never_terminates_host_process(tmp_path):
    with greentracker.track(project="lib-demo", interval=0.2,
                            csv_file=tmp_path / "emissions.csv") as session:
        time.sleep(0.3)
    # tras el stop, la "sesión de proceso" queda cerrada pero el anfitrión vive
    assert not session.process.running
    assert os.getpid() > 0  # seguimos vivos


def test_track_defaults_project_to_cwd_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with greentracker.track(interval=0.2) as session:
        time.sleep(0.3)
    assert session.summary.project == tmp_path.name
    assert (tmp_path / "emissions.csv").exists()


def test_first_library_session_is_baseline(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    with greentracker.track(project="lib-demo", interval=0.2, csv_file=csv_file) as s1:
        time.sleep(0.3)
    assert s1.summary.is_baseline
    with greentracker.track(project="lib-demo", interval=0.2, csv_file=csv_file) as s2:
        time.sleep(0.3)
    assert not s2.summary.is_baseline
    assert s2.baseline_comparison is not None
