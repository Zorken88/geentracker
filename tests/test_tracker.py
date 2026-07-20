"""Tests del motor de tracking (con CodeCarbon simulado).

Verifica el cumplimiento del modelo de calidad:
- Ecuación 3 de la tesis: HC = E × I con I = 0.245 kgCO₂eq/kWh
- Línea base energética = primera ejecución (ISO 50001)
- SEU = componente de mayor consumo (ISO 50001)
- Persistencia según Tabla 15 (ISO 14001)
"""

import sys
import time
from types import SimpleNamespace

import pytest

from greentracker.config import TrackerConfig
from greentracker.csv_writer import read_sessions, read_timeline
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
        self.final_emissions_data = SimpleNamespace(
            cpu_energy=0.008, gpu_energy=0.0005, ram_energy=0.0015, energy_consumed=0.010
        )
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
        return 0.0


@pytest.fixture
def make_tracker(tmp_path, monkeypatch):
    def _make(project="demo", command=None, carbon_intensity=0.245):
        config = TrackerConfig(
            command=command or f'{sys.executable} -c "import time; time.sleep(0.8)"',
            project=project,
            interval=0.2,
            carbon_intensity=carbon_intensity,
            csv_file=tmp_path / "emissions.csv",
        )
        tracker = GreenTracker(config)
        monkeypatch.setattr(tracker, "_create_cc_tracker", FakeCodeCarbon)
        return tracker

    return _make


def run_session(tracker):
    tracker.start_process()
    tracker.start_tracking()
    tracker.process.wait(timeout=15)
    time.sleep(0.3)
    return tracker.stop()


def test_emissions_follow_ecuacion_3(make_tracker):
    """HC = E × I con el factor HuellaChile 0.245 kgCO₂eq/kWh."""
    summary = run_session(make_tracker())
    assert summary is not None
    assert summary.energy_consumed == pytest.approx(0.010)
    assert summary.emissions == pytest.approx(0.010 * 0.245)
    assert summary.carbon_intensity == 0.245


def test_seu_identifies_dominant_component(make_tracker):
    summary = run_session(make_tracker())
    assert summary.seu_component == "CPU"
    assert "CPU 80%" in summary.seu_breakdown


def test_measurement_mode_recorded(make_tracker):
    """Cada sesión registra el método de medición (trazabilidad)."""
    summary = run_session(make_tracker())
    # con el CodeCarbon simulado no hay hardware reconocible → "unknown";
    # con hardware real será PowerMetrics / RAPL / TDP...
    assert isinstance(summary.measurement_mode, str)
    assert summary.measurement_mode == "unknown"


def test_first_session_marked_as_baseline(make_tracker):
    tracker = make_tracker()
    assert tracker.is_baseline_session is True
    summary = run_session(tracker)
    assert summary.is_baseline is True

    second = make_tracker()
    assert second.is_baseline_session is False
    summary2 = run_session(second)
    assert summary2.is_baseline is False
    # misma energía que la base → delta 0%
    assert second.baseline_comparison is not None
    assert second.baseline_comparison["energy_delta_pct"] == pytest.approx(0.0)


def test_session_persisted_with_tabla_15_values(make_tracker, tmp_path):
    summary = run_session(make_tracker())
    rows = read_sessions(tmp_path / "emissions.csv")
    assert len(rows) == 1
    row = rows[0]
    assert float(row["cpu_energy"]) == pytest.approx(0.008)
    assert float(row["gpu_energy"]) == pytest.approx(0.0005)
    assert float(row["ram_energy"]) == pytest.approx(0.0015)
    assert float(row["energy_consumed"]) == pytest.approx(0.010)
    assert float(row["emissions"]) == pytest.approx(summary.emissions)


def test_timeline_snapshots_written(make_tracker, tmp_path):
    tracker = make_tracker()
    run_session(tracker)
    points = read_timeline(tmp_path / "timeline.csv", tracker.session_id)
    assert len(points) >= 2
    assert float(points[-1]["energy_kwh"]) == pytest.approx(0.010)
    assert points[-1]["seu_component"] == "CPU"


def test_stop_is_idempotent(make_tracker):
    tracker = make_tracker()
    summary = run_session(tracker)
    assert tracker.stop() is summary


def test_custom_carbon_intensity(make_tracker):
    summary = run_session(make_tracker(carbon_intensity=0.5))
    assert summary.emissions == pytest.approx(0.010 * 0.5)
