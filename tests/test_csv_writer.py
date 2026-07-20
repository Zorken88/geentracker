"""Tests de persistencia (Seguimiento — ISO 14001; Tabla 15 de la tesis)."""

import csv
import json
from datetime import datetime

from greentracker.csv_writer import (
    SESSION_FIELDS,
    CsvWriter,
    export_json,
    read_sessions,
    read_timeline,
)
from greentracker.metrics import MetricSnapshot, SessionSummary


def make_summary(session_id="abc123", project="demo", is_baseline=True, energy=0.016):
    return SessionSummary(
        timestamp="2026-07-05T10:30:00",
        session_id=session_id,
        project=project,
        command="python app.py",
        duration_s=15.0,
        cpu_energy=0.012,
        gpu_energy=0.001,
        ram_energy=0.003,
        energy_consumed=energy,
        emissions=energy * 0.245,
        carbon_intensity=0.245,
        measurement_mode="PowerMetrics",
        seu_component="CPU",
        seu_breakdown="CPU 75% | RAM 19% | GPU 6%",
        is_baseline=is_baseline,
        cost_clp=energy * 150,
    )


def make_snapshot(session_id="abc123", project="demo"):
    return MetricSnapshot(
        timestamp=datetime(2026, 7, 5, 10, 30),
        session_id=session_id,
        project=project,
        cpu_percent=45.2,
        cpu_power_w=12.3,
        cpu_energy_kwh=0.012,
        ram_used_mb=234.0,
        ram_power_w=1.2,
        ram_energy_kwh=0.003,
        gpu_percent=0.0,
        gpu_power_w=0.0,
        gpu_energy_kwh=0.001,
        disk_read_mb_s=2.1,
        disk_write_mb_s=0.5,
        total_power_w=13.5,
        energy_kwh=0.016,
        emissions_kg_co2eq=0.00392,
        seu_component="CPU",
        is_baseline=True,
        cost_clp=2.4,
        child_processes=3,
        duration_s=15.0,
    )


def test_session_csv_has_tabla_15_columns(tmp_path):
    """El CSV canónico incluye las columnas de la Tabla 15 de la tesis."""
    csv_file = tmp_path / "emissions.csv"
    CsvWriter(csv_file).write_session_summary(make_summary())
    with csv_file.open() as fh:
        header = next(csv.reader(fh))
    for col in ("timestamp", "cpu_energy", "gpu_energy", "ram_energy", "energy_consumed", "emissions"):
        assert col in header
    assert "measurement_mode" in header  # trazabilidad del método de medición


def test_headers_written_once(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    writer = CsvWriter(csv_file)
    writer.write_session_summary(make_summary(session_id="s1"))
    writer.write_session_summary(make_summary(session_id="s2", is_baseline=False))
    rows = read_sessions(csv_file)
    assert len(rows) == 2
    assert rows[0]["session_id"] == "s1"
    assert set(rows[0].keys()) == set(SESSION_FIELDS)


def test_snapshot_appended_to_timeline(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    writer = CsvWriter(csv_file)
    writer.append_snapshot(make_snapshot())
    writer.append_snapshot(make_snapshot())
    rows = read_timeline(tmp_path / "timeline.csv", "abc123")
    assert len(rows) == 2
    assert float(rows[0]["cpu_energy_kwh"]) == 0.012


def test_read_sessions_filters_by_project(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    writer = CsvWriter(csv_file)
    writer.write_session_summary(make_summary(session_id="s1", project="api"))
    writer.write_session_summary(make_summary(session_id="s2", project="web"))
    assert len(read_sessions(csv_file, "api")) == 1
    assert len(read_sessions(csv_file)) == 2


def test_export_json(tmp_path):
    csv_file = tmp_path / "emissions.csv"
    writer = CsvWriter(csv_file)
    writer.write_session_summary(make_summary())
    writer.append_snapshot(make_snapshot())
    output = export_json(csv_file, tmp_path / "emissions.json")
    payload = json.loads(output.read_text())
    assert len(payload["sessions"]) == 1
    assert payload["sessions"][0]["session_id"] == "abc123"
    assert len(payload["timeline"]) == 1
