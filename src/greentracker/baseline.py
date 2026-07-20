"""Línea base energética y EnPI — ISO 50001, Tabla 9 de la tesis.

La primera ejecución registrada de cada proyecto se marca como línea base
(``is_baseline=True``). Cada sesión posterior se contrasta contra ella
(mejora continua). La línea base puede re-designarse manualmente con
``gtrack baseline --set <session_id>``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from greentracker.csv_writer import SESSION_FIELDS, read_sessions


def _as_bool(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


class BaselineManager:
    def __init__(self, csv_file: Path) -> None:
        self.csv_file = Path(csv_file)

    def sessions(self, project: str | None = None) -> list[dict]:
        return read_sessions(self.csv_file, project)

    def is_first_session(self, project: str) -> bool:
        return len(self.sessions(project)) == 0

    def get_baseline(self, project: str) -> dict | None:
        rows = self.sessions(project)
        if not rows:
            return None
        for row in rows:
            if _as_bool(row.get("is_baseline")):
                return row
        return rows[0]  # fallback: la primera ejecución registrada

    def compare_to_baseline(
        self, project: str, energy_kwh: float, emissions_kg: float
    ) -> dict | None:
        """Delta % de energía (EnPI) y emisiones vs la línea base del proyecto."""
        base = self.get_baseline(project)
        if base is None:
            return None
        try:
            base_energy = float(base["energy_consumed"])
            base_emissions = float(base["emissions"])
        except (KeyError, TypeError, ValueError):
            return None
        result = {"baseline_session_id": base.get("session_id")}
        result["energy_delta_pct"] = (
            ((energy_kwh - base_energy) / base_energy) * 100.0 if base_energy > 0 else None
        )
        result["emissions_delta_pct"] = (
            ((emissions_kg - base_emissions) / base_emissions) * 100.0
            if base_emissions > 0
            else None
        )
        return result

    def set_baseline(self, project: str, session_id: str) -> bool:
        """Re-designa la línea base del proyecto reescribiendo el CSV."""
        if not self.csv_file.exists():
            return False
        with self.csv_file.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fields = reader.fieldnames or SESSION_FIELDS
            rows = list(reader)
        found = False
        for row in rows:
            if row.get("project") != project:
                continue
            if row.get("session_id") == session_id:
                row["is_baseline"] = "True"
                found = True
            else:
                row["is_baseline"] = "False"
        if not found:
            return False
        with self.csv_file.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return True
