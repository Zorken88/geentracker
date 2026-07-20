"""Motor de tracking — módulo de adquisición y medición de métricas energéticas.

Implementa la captura definida por la tesis (Figura 4): CodeCarbon en modo
``OfflineEmissionsTracker`` con ``country_iso_code="CHL"`` para evitar
proveedores externos de intensidad de carbono (Electricity Maps / WattTime)
y garantizar funcionamiento 100% offline.

La huella de carbono se calcula con la Ecuación 3 de la tesis:
    HC (kgCO₂eq) = E (kWh) × I (kgCO₂eq/kWh)
usando el factor del SEN parametrizado según el Programa HuellaChile (0.245).
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime

import psutil

from greentracker.baseline import BaselineManager
from greentracker.config import TrackerConfig
from greentracker.constants import COUNTRY_ISO_CODE
from greentracker.csv_writer import CsvWriter
from greentracker.metrics import MetricSnapshot, SessionSummary
from greentracker.process_manager import ProcessManager
from greentracker.seu import compute_seu

_BYTES_PER_MB = 1024 * 1024


class GreenTracker:
    def __init__(self, config: TrackerConfig) -> None:
        self.config = config
        self.session_id = uuid.uuid4().hex[:8]
        self.process = ProcessManager(config.command)
        self.csv_writer = CsvWriter(config.csv_file, config.timeline_file)
        self.baseline = BaselineManager(config.csv_file)
        self.is_baseline_session = self.baseline.is_first_session(config.project)

        self.latest: MetricSnapshot | None = None
        self.summary: SessionSummary | None = None
        self.baseline_comparison: dict | None = None

        self._cc = None
        self._sampler: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._tracking_start: float | None = None
        self._stopped = False
        self._lock = threading.Lock()
        self._last_disk_io: tuple[float, float, float] | None = None  # (t, read_b, write_b)
        # psutil.Process cacheados por PID: cpu_percent() necesita el mismo
        # objeto entre llamadas para calcular el delta (si no, siempre da 0)
        self._proc_cache: dict[int, psutil.Process] = {}

    # -- ciclo de vida ------------------------------------------------------

    def start(self) -> None:
        """Inicio automático: tracking primero, luego el proceso.

        El tracker se inicia antes de lanzar el subproceso porque la
        inicialización de CodeCarbon toma varios segundos; si el proceso
        partiera primero, ese tiempo quedaría fuera de la medición.
        """
        self.start_tracking()
        self.start_process()

    def start_process(self) -> None:
        """Etapa 1 del modelo: evaluación del software (lanzar la aplicación)."""
        self.process.start()

    def start_tracking(self) -> None:
        """Etapas 2-4: captura de métricas, procesamiento energético y estimación."""
        if self._tracking_start is not None:
            return
        self._cc = self._create_cc_tracker()
        self._cc.start()
        self._tracking_start = time.monotonic()
        self._sampler = threading.Thread(target=self._sample_loop, daemon=True)
        self._sampler.start()

    @property
    def tracking_active(self) -> bool:
        return self._tracking_start is not None and not self._stopped

    def stop(self) -> SessionSummary | None:
        """Etapa 5: persistencia de resultados (fila CSV según Tabla 15)."""
        with self._lock:
            if self._stopped:
                return self.summary
            self._stopped = True
        self._stop_event.set()
        if self._sampler is not None:
            self._sampler.join(timeout=self.config.interval + 2)
        if self.process.running:
            self.process.terminate()
        if self._tracking_start is None:
            return None  # nunca se inició el tracking (modo manual abortado)

        duration = time.monotonic() - self._tracking_start
        try:
            self._cc.stop()
        except Exception:
            pass

        cpu_kwh, gpu_kwh, ram_kwh, total_kwh = self._final_energies()
        emissions = total_kwh * self.config.carbon_intensity  # Ecuación 3
        seu = compute_seu(cpu_kwh, gpu_kwh, ram_kwh)

        if not self.is_baseline_session:
            self.baseline_comparison = self.baseline.compare_to_baseline(
                self.config.project, total_kwh, emissions
            )

        self.summary = SessionSummary(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            session_id=self.session_id,
            project=self.config.project,
            command=self.config.command,
            duration_s=round(duration, 2),
            cpu_energy=cpu_kwh,
            gpu_energy=gpu_kwh,
            ram_energy=ram_kwh,
            energy_consumed=total_kwh,
            emissions=emissions,
            carbon_intensity=self.config.carbon_intensity,
            measurement_mode=self.measurement_mode(),
            seu_component=seu.component,
            seu_breakdown=seu.format_breakdown(),
            is_baseline=self.is_baseline_session,
            cost_clp=total_kwh * self.config.electricity_cost_clp,
        )
        self.csv_writer.write_session_summary(self.summary)
        return self.summary

    # -- codecarbon ---------------------------------------------------------

    def _create_cc_tracker(self):
        from codecarbon import OfflineEmissionsTracker

        kwargs = dict(
            country_iso_code=COUNTRY_ISO_CODE,
            tracking_mode="process",
            measure_power_secs=max(1, int(self.config.interval)),
            save_to_file=False,  # el CSV canónico lo escribe GreenTracker
            log_level="error",
        )
        try:
            return OfflineEmissionsTracker(allow_multiple_runs=True, **kwargs)
        except TypeError:  # versiones de codecarbon sin allow_multiple_runs
            return OfflineEmissionsTracker(**kwargs)

    def measurement_mode(self) -> str:
        """Método de medición usado por CodeCarbon (trazabilidad del modelo).

        "PowerMetrics" (sensores Apple Silicon), "RAPL" (sensores Intel/AMD
        en Linux), "Power Gadget" (Windows/mac Intel) o estimación por TDP.
        """
        for hw in getattr(self._cc, "_hardware", None) or []:
            name = type(hw).__name__
            if name == "AppleSiliconChip":
                return "PowerMetrics"
            if name == "CPU":
                mode = getattr(hw, "_mode", "unknown")
                return {
                    "intel_rapl": "RAPL",
                    "intel_power_gadget": "Power Gadget",
                    "constant": "TDP constant",
                    "cpu_load": "TDP cpu_load",
                }.get(mode, str(mode))
        return "unknown"

    def _cc_kwh(self, attr: str) -> float:
        energy = getattr(self._cc, attr, None)
        try:
            return float(getattr(energy, "kWh", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _cc_watts(self, attr: str) -> float:
        power = getattr(self._cc, attr, None)
        try:
            return float(getattr(power, "W", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _live_energies(self) -> tuple[float, float, float, float]:
        cpu = self._cc_kwh("_total_cpu_energy")
        gpu = self._cc_kwh("_total_gpu_energy")
        ram = self._cc_kwh("_total_ram_energy")
        total = self._cc_kwh("_total_energy") or (cpu + gpu + ram)
        return cpu, gpu, ram, total

    def _final_energies(self) -> tuple[float, float, float, float]:
        data = getattr(self._cc, "final_emissions_data", None)
        if data is not None:
            try:
                cpu = float(getattr(data, "cpu_energy", 0.0) or 0.0)
                gpu = float(getattr(data, "gpu_energy", 0.0) or 0.0)
                ram = float(getattr(data, "ram_energy", 0.0) or 0.0)
                total = float(getattr(data, "energy_consumed", 0.0) or 0.0)
                if total > 0:
                    return cpu, gpu, ram, total
            except (TypeError, ValueError):
                pass
        return self._live_energies()

    # -- muestreo -----------------------------------------------------------

    def _sample_loop(self) -> None:
        while not self._stop_event.wait(self.config.interval):
            try:
                snapshot = self._take_snapshot()
            except Exception:
                continue
            self.latest = snapshot
            self.csv_writer.append_snapshot(snapshot)

    def _take_snapshot(self) -> MetricSnapshot:
        cpu_kwh, gpu_kwh, ram_kwh, total_kwh = self._live_energies()
        cpu_w = self._cc_watts("_cpu_power")
        gpu_w = self._cc_watts("_gpu_power")
        ram_w = self._cc_watts("_ram_power")
        emissions = total_kwh * self.config.carbon_intensity  # Ecuación 3
        seu = compute_seu(cpu_kwh, gpu_kwh, ram_kwh)
        cpu_pct, ram_mb, children = self._process_tree_stats()
        disk_read, disk_write = self._disk_io_rates()

        return MetricSnapshot(
            timestamp=datetime.now(),
            session_id=self.session_id,
            project=self.config.project,
            cpu_percent=cpu_pct,
            cpu_power_w=cpu_w,
            cpu_energy_kwh=cpu_kwh,
            ram_used_mb=ram_mb,
            ram_power_w=ram_w,
            ram_energy_kwh=ram_kwh,
            gpu_percent=0.0,
            gpu_power_w=gpu_w,
            gpu_energy_kwh=gpu_kwh,
            disk_read_mb_s=disk_read,
            disk_write_mb_s=disk_write,
            total_power_w=cpu_w + gpu_w + ram_w,
            energy_kwh=total_kwh,
            emissions_kg_co2eq=emissions,
            seu_component=seu.component,
            is_baseline=self.is_baseline_session,
            cost_clp=total_kwh * self.config.electricity_cost_clp,
            child_processes=children,
            duration_s=time.monotonic() - (self._tracking_start or time.monotonic()),
        )

    def _process_tree_stats(self) -> tuple[float, float, int]:
        """CPU % y RAM (MB) agregados del árbol de procesos del comando."""
        tree = self.process.process_tree()
        pids = set()
        cpu_pct = 0.0
        ram_bytes = 0
        for proc in tree:
            pids.add(proc.pid)
            cached = self._proc_cache.setdefault(proc.pid, proc)
            try:
                cpu_pct += cached.cpu_percent(interval=None)
                ram_bytes += cached.memory_info().rss
            except psutil.Error:
                self._proc_cache.pop(proc.pid, None)
                continue
        # purgar procesos que ya no existen
        for pid in list(self._proc_cache):
            if pid not in pids:
                del self._proc_cache[pid]
        children = max(len(tree) - 1, 0)
        return cpu_pct, ram_bytes / _BYTES_PER_MB, children

    def _disk_io_rates(self) -> tuple[float, float]:
        """Disk I/O en MB/s. En macOS psutil no expone io_counters por proceso,
        por lo que se usa el contador global del sistema como aproximación."""
        try:
            io = psutil.disk_io_counters()
            if io is None:
                return 0.0, 0.0
            now = time.monotonic()
            read_b, write_b = float(io.read_bytes), float(io.write_bytes)
        except (psutil.Error, RuntimeError):
            return 0.0, 0.0
        if self._last_disk_io is None:
            self._last_disk_io = (now, read_b, write_b)
            return 0.0, 0.0
        last_t, last_r, last_w = self._last_disk_io
        elapsed = max(now - last_t, 1e-6)
        self._last_disk_io = (now, read_b, write_b)
        return (
            max(read_b - last_r, 0.0) / elapsed / _BYTES_PER_MB,
            max(write_b - last_w, 0.0) / elapsed / _BYTES_PER_MB,
        )
