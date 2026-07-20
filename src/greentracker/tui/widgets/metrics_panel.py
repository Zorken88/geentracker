"""Panel de métricas en tiempo real (utilización de recursos — ISO/IEC 25010)."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from greentracker.metrics import MetricSnapshot


class MetricsPanel(Static):
    def __init__(self, baseline_ref: dict | None = None, **kwargs) -> None:
        super().__init__("Esperando métricas...", **kwargs)
        self.border_title = "📊 Metrics"
        self.baseline_ref = baseline_ref  # sesión línea base (dict del CSV) o None

    def show_waiting(self, manual: bool) -> None:
        if manual:
            self.update("Modo manual — presiona [bold]T[/bold] para iniciar el tracking.")
        else:
            self.update("Esperando métricas...")

    def update_metrics(self, snap: MetricSnapshot) -> None:
        text = Text()
        text.append(f"CPU:  {snap.cpu_percent:5.1f}% | {snap.cpu_power_w:.1f}W\n")
        text.append(f"RAM:  {snap.ram_used_mb:5.0f}MB | {snap.ram_power_w:.1f}W\n")
        gpu = "N/A" if snap.gpu_power_w <= 0 else f"{snap.gpu_power_w:.1f}W"
        text.append(f"GPU:  {gpu}\n")
        text.append(f"Disk: {snap.disk_read_mb_s:.1f}/{snap.disk_write_mb_s:.1f} MB/s\n")
        text.append("─" * 24 + "\n", style="dim")
        text.append(f"⚡ {snap.energy_kwh:.6f} kWh\n", style="yellow")
        text.append(f"🌍 {snap.emissions_g_co2eq:.4f} gCO₂eq\n", style="green")
        text.append(f"🔥 SEU: {snap.seu_component}\n", style="red")
        if snap.is_baseline:
            text.append("⭐ Sesión línea base\n", style="cyan")
        elif self.baseline_ref is not None:
            try:
                base_kwh = float(self.baseline_ref["energy_consumed"])
                text.append(f"⭐ Base: {base_kwh:.6f} kWh\n", style="cyan")
                if base_kwh > 0:
                    delta = (snap.energy_kwh - base_kwh) / base_kwh * 100.0
                    style = "green" if delta <= 0 else "red"
                    text.append(f"📉 vs base: {delta:+.0f}%\n", style=style)
            except (KeyError, TypeError, ValueError):
                pass
        text.append(f"💰 ${snap.cost_clp:.4f} CLP\n", style="magenta")
        text.append(f"👶 {snap.child_processes} child processes\n")
        mins, secs = divmod(int(snap.duration_s), 60)
        hours, mins = divmod(mins, 60)
        text.append(f"⏱  {hours:02d}:{mins:02d}:{secs:02d}", style="dim")
        self.update(text)
