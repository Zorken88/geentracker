"""Resumen final de sesión mostrado al detener el tracking."""

from __future__ import annotations

from rich.table import Table
from textual.widgets import Static

from greentracker.metrics import SessionSummary


class SummaryPanel(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.border_title = "✅ Resumen de sesión"

    def show_summary(self, summary: SessionSummary, comparison: dict | None) -> None:
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="bold")
        table.add_column(justify="right")
        table.add_row("Duración", f"{summary.duration_s:.1f} s")
        table.add_row("Energía CPU", f"{summary.cpu_energy:.6f} kWh")
        table.add_row("Energía GPU", f"{summary.gpu_energy:.6f} kWh")
        table.add_row("Energía RAM", f"{summary.ram_energy:.6f} kWh")
        table.add_row("Energía total (EnPI)", f"{summary.energy_consumed:.6f} kWh")
        table.add_row("Huella de carbono", f"{summary.emissions * 1000:.4f} gCO₂eq")
        table.add_row("Medición", summary.measurement_mode)
        table.add_row("SEU", f"{summary.seu_component} — {summary.seu_breakdown}")
        table.add_row("Costo", f"${summary.cost_clp:.4f} CLP")
        if summary.is_baseline:
            table.add_row("Línea base", "⭐ Esta sesión")
        elif comparison and comparison.get("energy_delta_pct") is not None:
            table.add_row("vs línea base", f"{comparison['energy_delta_pct']:+.1f}% energía")
        self.update(table)
