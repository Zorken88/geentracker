"""API de librería — medir código Python desde el propio proceso.

Permite usar GreenTracker sin CLI ni subprocesos, instalándolo con pip en el
entorno del proyecto a evaluar::

    import greentracker

    with greentracker.track(project="mi-api") as session:
        entrenar_modelo()          # el código a medir

    print(session.summary.energy_consumed)  # kWh (EnPI, ISO 50001)
    print(session.summary.emissions)        # kgCO₂eq (Ecuación 3: HC = E × I)
    print(session.summary.seu_component)    # SEU (ISO 50001)

Las sesiones se persisten en el mismo CSV (Tabla 15) que usa el CLI, por lo
que ``gtrack dashboard``, la línea base y la comparación histórica funcionan
igual para sesiones medidas como librería.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psutil

from greentracker.config import TrackerConfig
from greentracker.constants import (
    DEFAULT_CARBON_INTENSITY,
    DEFAULT_CSV_FILE,
    DEFAULT_ELECTRICITY_COST_CLP,
    DEFAULT_INTERVAL,
)
from greentracker.tracker import GreenTracker


class _CurrentProcess:
    """Adaptador con la interfaz de ProcessManager que apunta al proceso actual.

    En modo librería el aspecto ambiental (ISO 14001) es el propio intérprete
    Python que ejecuta el código del usuario, más sus procesos hijos. A
    diferencia del subproceso del CLI, el proceso anfitrión nunca se termina:
    su ciclo de vida pertenece al programa que importó la librería.
    """

    def __init__(self) -> None:
        self._root = psutil.Process(os.getpid())
        self._active = True

    @property
    def pid(self) -> int:
        return self._root.pid

    @property
    def running(self) -> bool:
        return self._active

    @property
    def returncode(self) -> None:
        return None

    def child_process_count(self) -> int:
        try:
            return len(self._root.children(recursive=True))
        except psutil.Error:
            return 0

    def process_tree(self) -> list[psutil.Process]:
        if not self._active:
            return []
        try:
            return [self._root, *self._root.children(recursive=True)]
        except psutil.Error:
            return []

    def read_new_lines(self) -> list[str]:
        return []

    def wait(self, timeout: float | None = None) -> None:
        return None

    def terminate(self, timeout: float = 5.0) -> None:
        # Nunca terminar el proceso anfitrión: solo cerrar la sesión.
        self._active = False


@contextmanager
def track(
    project: str | None = None,
    *,
    label: str | None = None,
    interval: float = DEFAULT_INTERVAL,
    carbon_intensity: float = DEFAULT_CARBON_INTENSITY,
    electricity_cost_clp: float = DEFAULT_ELECTRICITY_COST_CLP,
    csv_file: str | Path = DEFAULT_CSV_FILE,
    force_ram_power: float | None = None,
    rapl_include_dram: bool = False,
) -> Iterator[GreenTracker]:
    """Mide el consumo energético y la huella de carbono del bloque ``with``.

    Args:
        project: nombre del proyecto para la línea base y el dashboard
            (por defecto, el nombre del directorio actual).
        label: descripción de la sesión; ocupa la columna ``command`` del CSV.
        interval: segundos entre muestras (por defecto 2.0).
        carbon_intensity: factor de emisión en kgCO₂eq/kWh (por defecto
            0.245, SEN según Programa HuellaChile — Ecuación 4 de la tesis).
        electricity_cost_clp: tarifa eléctrica CLP/kWh (extensión, no modelo).
        csv_file: ruta del CSV de sesiones (por defecto ``emissions.csv``
            en el directorio actual, igual que el CLI).
        force_ram_power: potencia fija de RAM en watts; reemplaza el modelo
            de estimación de codecarbon (útil si se conoce el consumo real).
        rapl_include_dram: en Linux con dominio RAPL ``dram`` (mayormente
            Intel), suma la energía real de memoria dentro del componente
            CPU. Sin efecto si el hardware no expone ese dominio (ej. AMD).

    Yields:
        La instancia de :class:`GreenTracker`. Durante el bloque expone
        ``latest`` (último MetricSnapshot); al salir, ``summary`` contiene
        la SessionSummary persistida (Tabla 15).
    """
    config = TrackerConfig(
        command=label or "[librería] proceso actual",
        project=project or Path.cwd().name,
        interval=interval,
        carbon_intensity=carbon_intensity,
        electricity_cost_clp=electricity_cost_clp,
        csv_file=Path(csv_file),
        force_ram_power=force_ram_power,
        rapl_include_dram=rapl_include_dram,
    )
    tracker = GreenTracker(config, process_manager=_CurrentProcess())
    tracker.start_tracking()
    try:
        yield tracker
    finally:
        tracker.stop()
