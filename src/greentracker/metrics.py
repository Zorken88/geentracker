"""Dataclasses de métricas del modelo de calidad extendido.

Las emisiones se persisten en kgCO₂eq (Ecuación 3 de la tesis: HC = E × I).
La TUI muestra gCO₂eq (×1000) por legibilidad, indicando siempre la unidad.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class MetricSnapshot:
    timestamp: datetime
    session_id: str
    project: str
    cpu_percent: float        # %
    cpu_power_w: float        # Watts
    cpu_energy_kwh: float     # kWh acumulado CPU (Tabla 15 tesis)
    ram_used_mb: float        # MB
    ram_power_w: float        # Watts
    ram_energy_kwh: float     # kWh acumulado RAM (Tabla 15 tesis)
    gpu_percent: float        # % (0 si no hay GPU)
    gpu_power_w: float        # Watts (0 si no hay GPU)
    gpu_energy_kwh: float     # kWh acumulado GPU (Tabla 15 tesis)
    disk_read_mb_s: float     # MB/s (extensión del prototipo)
    disk_write_mb_s: float    # MB/s (extensión del prototipo)
    total_power_w: float      # Watts
    energy_kwh: float         # kWh acumulado total (EnPI, ISO 50001)
    emissions_kg_co2eq: float # kgCO₂eq acumulado (Ecuación 3: HC = E × I)
    seu_component: str        # "CPU" | "GPU" | "RAM" — mayor consumo (ISO 50001)
    is_baseline: bool         # True si la sesión es la línea base del proyecto
    cost_clp: float           # Costo en CLP (extensión del prototipo)
    child_processes: int      # Número de procesos hijos
    duration_s: float         # Segundos desde inicio

    @property
    def emissions_g_co2eq(self) -> float:
        return self.emissions_kg_co2eq * 1000.0

    def to_row(self) -> dict:
        row = asdict(self)
        row["timestamp"] = self.timestamp.isoformat(timespec="seconds")
        return row


@dataclass
class SessionSummary:
    """Resumen de una sesión — una fila del CSV canónico (Tabla 15 + extras)."""

    timestamp: str
    session_id: str
    project: str
    command: str
    duration_s: float
    cpu_energy: float          # kWh (Tabla 15)
    gpu_energy: float          # kWh (Tabla 15)
    ram_energy: float          # kWh (Tabla 15)
    energy_consumed: float     # kWh total (Tabla 15 / EnPI)
    emissions: float           # kgCO₂eq (Tabla 15, Ecuación 3)
    carbon_intensity: float    # kgCO₂eq/kWh usado en el cálculo
    measurement_mode: str      # método de medición: PowerMetrics/RAPL/TDP...
    seu_component: str         # SEU (ISO 50001)
    seu_breakdown: str         # ej: "CPU 78% | RAM 19% | GPU 3%"
    is_baseline: bool          # línea base energética (ISO 50001)
    cost_clp: float            # extensión del prototipo

    def to_row(self) -> dict:
        return asdict(self)
