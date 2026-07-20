"""TUI dashboard (modo ``dashboard``): visualización y análisis (etapa 6 del modelo).

Materializa la Analizabilidad (ISO/IEC 25010) mediante visualización
histórica, la mejora continua (ISO 50001/14001) mediante comparación contra
la línea base energética, y el SEU con desglose por componente.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Footer, Sparkline, Static, TabbedContent, TabPane

from greentracker.baseline import BaselineManager, _as_bool
from greentracker.csv_writer import read_sessions, read_timeline

BAR_WIDTH = 26


def _f(row: dict, key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_duration(seconds: float) -> str:
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d}"


def _bar(value: float, max_value: float) -> str:
    if max_value <= 0:
        return "░" * BAR_WIDTH
    filled = round((value / max_value) * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


class DashboardApp(App):
    CSS_PATH = "styles/app.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("left_square_bracket", "prev_session", "← Sesión", key_display="["),
        Binding("right_square_bracket", "next_session", "Sesión →", key_display="]"),
    ]

    def __init__(self, csv_file: Path, project: str | None = None) -> None:
        super().__init__()
        self.csv_file = Path(csv_file)
        self.project = project
        self.sessions = read_sessions(self.csv_file, project)
        self.timeline_file = self.csv_file.with_name("timeline.csv")
        self._timeline_index = len(self.sessions) - 1 if self.sessions else 0
        manager = BaselineManager(self.csv_file)
        projects = {s["project"] for s in self.sessions}
        self.baseline = (
            manager.get_baseline(next(iter(projects))) if len(projects) == 1 else None
        )

    # -- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        scope = self.project or "todos los proyectos"
        yield Static(f"🌿 GreenTracker Dashboard — {scope}", id="title-bar")
        with TabbedContent():
            with TabPane("Sessions", id="tab-sessions"):
                yield DataTable(id="sessions-table")
                yield Static(id="sessions-footer")
            with TabPane("Compare", id="tab-compare"):
                with VerticalScroll():
                    yield Static(id="compare-energy", classes="compare-block")
                    yield Static(id="compare-emissions", classes="compare-block")
                    yield Static(id="compare-seu", classes="compare-block")
            with TabPane("Timeline", id="tab-timeline"):
                with VerticalScroll():
                    yield Static(id="timeline-title", classes="timeline-label")
                    yield Static("CPU (W)", classes="timeline-label")
                    yield Sparkline([0.0], id="spark-cpu")
                    yield Static("RAM (MB)", classes="timeline-label")
                    yield Sparkline([0.0], id="spark-ram")
                    yield Static("Disk I/O (MB/s)", classes="timeline-label")
                    yield Sparkline([0.0], id="spark-disk")
                    yield Static("CO₂eq acumulado (g)", classes="timeline-label")
                    yield Sparkline([0.0], id="spark-co2")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_sessions()
        self._populate_compare()
        self._populate_timeline()

    # -- helpers -------------------------------------------------------------

    def _baseline_delta(self, row: dict) -> str:
        if self.baseline is None:
            return "—"
        if row.get("session_id") == self.baseline.get("session_id"):
            return "(base)"
        base_kwh = _f(self.baseline, "energy_consumed")
        if base_kwh <= 0:
            return "—"
        delta = (_f(row, "energy_consumed") - base_kwh) / base_kwh * 100.0
        arrow = "▼" if delta < 0 else "▲"
        return f"{arrow} {delta:+.0f}%"

    def _session_label(self, index: int, row: dict) -> str:
        star = "⭐" if _as_bool(row.get("is_baseline")) else "  "
        return f"Session {index + 1}{star}"

    # -- tab: sessions ---------------------------------------------------------

    def _populate_sessions(self) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.add_columns(
            "#", "Fecha", "Duración", "Energía (kWh)", "CO₂eq (g)", "SEU", "Modo", "Costo (CLP)", "vs Base"
        )
        for i, row in enumerate(self.sessions):
            table.add_row(
                str(i + 1) + (" ⭐" if _as_bool(row.get("is_baseline")) else ""),
                row.get("timestamp", ""),
                _fmt_duration(_f(row, "duration_s")),
                f"{_f(row, 'energy_consumed'):.6f}",
                f"{_f(row, 'emissions') * 1000:.4f}",
                row.get("seu_component", ""),
                row.get("measurement_mode", "—"),
                f"${_f(row, 'cost_clp'):.4f}",
                self._baseline_delta(row),
            )
        footer = self.query_one("#sessions-footer", Static)
        if not self.sessions:
            footer.update("Sin sesiones registradas.")
            return
        n = len(self.sessions)
        total_kwh = sum(_f(r, "energy_consumed") for r in self.sessions)
        total_co2 = sum(_f(r, "emissions") for r in self.sessions)
        total_clp = sum(_f(r, "cost_clp") for r in self.sessions)
        text = Text()
        if self.baseline is not None:
            text.append(
                f"⭐ Línea base: sesión {self.baseline['session_id']} | "
                f"EnPI: {_f(self.baseline, 'energy_consumed'):.6f} kWh/ejecución\n",
                style="cyan",
            )
        text.append(
            f"Promedio: {total_kwh / n:.6f} kWh | {total_co2 / n * 1000:.4f} gCO₂eq | ${total_clp / n:.4f} CLP\n"
        )
        text.append(
            f"Total acumulado: {total_kwh:.6f} kWh | {total_co2 * 1000:.4f} gCO₂eq | ${total_clp:.4f} CLP"
        )
        footer.update(text)

    # -- tab: compare ----------------------------------------------------------

    def _populate_compare(self) -> None:
        energy_block = self.query_one("#compare-energy", Static)
        emissions_block = self.query_one("#compare-emissions", Static)
        seu_block = self.query_one("#compare-seu", Static)
        if not self.sessions:
            energy_block.update("Sin sesiones registradas.")
            return

        max_kwh = max(_f(r, "energy_consumed") for r in self.sessions) or 1.0
        text = Text("📊 Comparación de Sesiones — Energía (kWh)\n\n", style="bold")
        for i, row in enumerate(self.sessions):
            kwh = _f(row, "energy_consumed")
            text.append(f"{self._session_label(i, row)}  ")
            text.append(_bar(kwh, max_kwh), style="yellow")
            text.append(f"  {kwh:.6f} kWh  {self._baseline_delta(row)}\n")
        energy_block.update(text)

        max_co2 = max(_f(r, "emissions") for r in self.sessions) or 1.0
        text = Text("📊 Comparación de Sesiones — Huella de Carbono (gCO₂eq)\n\n", style="bold")
        for i, row in enumerate(self.sessions):
            co2 = _f(row, "emissions")
            text.append(f"{self._session_label(i, row)}  ")
            text.append(_bar(co2, max_co2), style="green")
            text.append(f"  {co2 * 1000:.4f} g  {self._baseline_delta(row)}\n")
        emissions_block.update(text)

        latest = self.sessions[-1]
        text = Text(
            f"🔥 SEU — Desglose energético por componente (última sesión: {latest['session_id']})\n\n",
            style="bold",
        )
        components = {
            "CPU": _f(latest, "cpu_energy"),
            "RAM": _f(latest, "ram_energy"),
            "GPU": _f(latest, "gpu_energy"),
        }
        total = sum(components.values()) or 1.0
        for name, kwh in sorted(components.items(), key=lambda kv: kv[1], reverse=True):
            pct = kwh / total * 100.0
            marker = "  ← Uso Significativo de Energía" if name == latest.get("seu_component") else ""
            text.append(f"{name}  ")
            text.append(_bar(pct, 100.0), style="red")
            text.append(f"  {pct:4.0f}%{marker}\n")
        seu_block.update(text)

    # -- tab: timeline -----------------------------------------------------------

    def _populate_timeline(self) -> None:
        title = self.query_one("#timeline-title", Static)
        if not self.sessions:
            title.update("Sin sesiones registradas.")
            return
        row = self.sessions[self._timeline_index]
        session_id = row["session_id"]
        points = read_timeline(self.timeline_file, session_id)
        title.update(
            f"📈 Timeline — {self._session_label(self._timeline_index, row).strip()} "
            f"({row.get('timestamp', '')})  [{len(points)} muestras]  — usa [ ] para navegar"
        )
        def series(key: str) -> list[float]:
            data = [_f(p, key) for p in points]
            return data if data else [0.0]

        self.query_one("#spark-cpu", Sparkline).data = series("cpu_power_w")
        self.query_one("#spark-ram", Sparkline).data = series("ram_used_mb")
        disk = [
            _f(p, "disk_read_mb_s") + _f(p, "disk_write_mb_s") for p in points
        ] or [0.0]
        self.query_one("#spark-disk", Sparkline).data = disk
        self.query_one("#spark-co2", Sparkline).data = [
            _f(p, "emissions_kg_co2eq") * 1000 for p in points
        ] or [0.0]

    def action_prev_session(self) -> None:
        if self.sessions and self._timeline_index > 0:
            self._timeline_index -= 1
            self._populate_timeline()

    def action_next_session(self) -> None:
        if self.sessions and self._timeline_index < len(self.sessions) - 1:
            self._timeline_index += 1
            self._populate_timeline()
