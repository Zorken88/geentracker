"""Configuración de una sesión de tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from greentracker.constants import (
    DEFAULT_CARBON_INTENSITY,
    DEFAULT_CSV_FILE,
    DEFAULT_ELECTRICITY_COST_CLP,
    DEFAULT_INTERVAL,
    TIMELINE_CSV_FILE,
)


@dataclass
class TrackerConfig:
    command: str
    project: str
    interval: float = DEFAULT_INTERVAL
    carbon_intensity: float = DEFAULT_CARBON_INTENSITY  # kgCO₂eq/kWh
    electricity_cost_clp: float = DEFAULT_ELECTRICITY_COST_CLP  # CLP/kWh
    csv_file: Path = field(default_factory=lambda: Path(DEFAULT_CSV_FILE))
    manual: bool = False
    # Medición de RAM (codecarbon >= 3). Por defecto la RAM se ESTIMA con el
    # modelo de capacidad de codecarbon (piso ~3 W ARM / ~10 W x86):
    # - force_ram_power: reemplaza el modelo por una potencia fija conocida (W)
    # - rapl_include_dram: Linux con dominio RAPL "dram" (mayormente Intel):
    #   suma la energía real de memoria DENTRO del componente CPU (RAPL)
    force_ram_power: float | None = None
    rapl_include_dram: bool = False

    @property
    def timeline_file(self) -> Path:
        return self.csv_file.with_name(TIMELINE_CSV_FILE)
