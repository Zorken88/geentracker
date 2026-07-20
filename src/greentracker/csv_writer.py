"""Persistencia y trazabilidad de datos (Seguimiento — ISO 14001, Tabla 10).

Dos archivos:
- ``emissions.csv``: una fila por sesión, columnas alineadas con la Tabla 15
  de la tesis (timestamp, cpu_energy, gpu_energy, ram_energy, energy_consumed,
  emissions) más columnas propias del prototipo.
- ``timeline.csv``: snapshots por intervalo, base de los sparklines del
  dashboard (Analizabilidad — ISO/IEC 25010).

Además provee export JSON (módulo de almacenamiento "CSV/JSON" de la tesis).
"""

from __future__ import annotations

import csv
import json
import threading
from pathlib import Path

from greentracker.metrics import MetricSnapshot, SessionSummary

# Columnas de la Tabla 15 de la tesis + columnas propias del prototipo
SESSION_FIELDS = [
    "timestamp",
    "session_id",
    "project",
    "command",
    "duration_s",
    "cpu_energy",
    "gpu_energy",
    "ram_energy",
    "energy_consumed",
    "emissions",
    "carbon_intensity",
    "measurement_mode",
    "seu_component",
    "seu_breakdown",
    "is_baseline",
    "cost_clp",
]

TIMELINE_FIELDS = [
    "timestamp",
    "session_id",
    "project",
    "cpu_percent",
    "cpu_power_w",
    "cpu_energy_kwh",
    "ram_used_mb",
    "ram_power_w",
    "ram_energy_kwh",
    "gpu_percent",
    "gpu_power_w",
    "gpu_energy_kwh",
    "disk_read_mb_s",
    "disk_write_mb_s",
    "total_power_w",
    "energy_kwh",
    "emissions_kg_co2eq",
    "seu_component",
    "is_baseline",
    "cost_clp",
    "child_processes",
    "duration_s",
]


class CsvWriter:
    """Escritura thread-safe con headers automáticos."""

    def __init__(self, csv_file: Path, timeline_file: Path | None = None) -> None:
        self.csv_file = Path(csv_file)
        self.timeline_file = (
            Path(timeline_file)
            if timeline_file is not None
            else self.csv_file.with_name("timeline.csv")
        )
        self._lock = threading.Lock()

    def _append(self, path: Path, fields: list[str], row: dict) -> None:
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            new_file = not path.exists() or path.stat().st_size == 0
            with path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                if new_file:
                    writer.writeheader()
                writer.writerow(row)

    def append_snapshot(self, snapshot: MetricSnapshot) -> None:
        self._append(self.timeline_file, TIMELINE_FIELDS, snapshot.to_row())

    def write_session_summary(self, summary: SessionSummary) -> None:
        self._append(self.csv_file, SESSION_FIELDS, summary.to_row())


def read_sessions(csv_file: Path, project: str | None = None) -> list[dict]:
    """Lee las sesiones del CSV canónico, opcionalmente filtradas por proyecto."""
    path = Path(csv_file)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if project:
        rows = [r for r in rows if r.get("project") == project]
    return rows


def read_timeline(timeline_file: Path, session_id: str | None = None) -> list[dict]:
    path = Path(timeline_file)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if session_id:
        rows = [r for r in rows if r.get("session_id") == session_id]
    return rows


def export_json(
    csv_file: Path,
    output: Path,
    project: str | None = None,
    include_timeline: bool = True,
) -> Path:
    """Exporta las sesiones (y su timeline) a JSON — almacenamiento CSV/JSON de la tesis."""
    sessions = read_sessions(csv_file, project)
    payload: dict = {"sessions": sessions}
    if include_timeline:
        timeline_file = Path(csv_file).with_name("timeline.csv")
        session_ids = {s["session_id"] for s in sessions}
        timeline = [
            r for r in read_timeline(timeline_file) if r.get("session_id") in session_ids
        ]
        payload["timeline"] = timeline
    output = Path(output)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return output
