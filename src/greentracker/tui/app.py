"""TUI principal (modo ``run``): output del proceso + métricas en tiempo real."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static

from greentracker.tracker import GreenTracker
from greentracker.tui.widgets.metrics_panel import MetricsPanel
from greentracker.tui.widgets.process_output import ProcessOutput
from greentracker.tui.widgets.summary import SummaryPanel


class GreenTrackerApp(App):
    CSS_PATH = "styles/app.tcss"
    BINDINGS = [
        Binding("s", "stop_tracking", "Stop tracking"),
        Binding("t", "start_tracking", "Track (manual)"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, tracker: GreenTracker) -> None:
        super().__init__()
        self.tracker = tracker
        self._finished = False      # stop solicitado
        self._stop_done = False     # sesión persistida, resumen visible
        self._exit_when_stopped = False

    def compose(self) -> ComposeResult:
        config = self.tracker.config
        yield Static(
            f"🌿 GreenTracker — {config.project}  |  Session: {self.tracker.session_id}",
            id="title-bar",
        )
        with Horizontal(id="main"):
            yield ProcessOutput(id="output")
            with Vertical(id="side"):
                baseline_ref = None
                if not self.tracker.is_baseline_session:
                    baseline_ref = self.tracker.baseline.get_baseline(config.project)
                yield MetricsPanel(baseline_ref=baseline_ref, id="metrics")
                yield SummaryPanel(id="summary")
        yield Footer()

    def on_mount(self) -> None:
        metrics = self.query_one(MetricsPanel)
        if self.tracker.config.manual:
            # en modo manual el proceso parte de inmediato y el tracking
            # espera a que el usuario presione T
            self.tracker.start_process()
            metrics.show_waiting(manual=True)
        else:
            self.tracker.start()
        self.set_interval(1.0, self._refresh)

    def _refresh(self) -> None:
        output = self.query_one(ProcessOutput)
        output.add_lines(self.tracker.process.read_new_lines())
        if self._finished:
            return
        snap = self.tracker.latest
        if snap is not None:
            self.query_one(MetricsPanel).update_metrics(snap)
        if not self.tracker.process.running:
            output.write(
                f"[proceso finalizado con código {self.tracker.process.returncode}]"
            )
            self._finish()

    def _finish(self, then_exit: bool = False) -> None:
        if self._finished:
            if self._stop_done:
                if then_exit:
                    self.exit()
            else:
                # stop en curso: no salir todavía para no perder la sesión
                if then_exit:
                    self._exit_when_stopped = True
                self.notify(
                    "⏳ Deteniendo... guardando la sesión (con sensores puede "
                    "tardar unos segundos)",
                    severity="warning",
                )
            return
        self._finished = True
        self._exit_when_stopped = then_exit
        self.notify("⏳ Deteniendo tracking y guardando la sesión...")
        self.query_one(MetricsPanel).border_title = "⏳ Deteniendo..."
        # tracker.stop() termina el árbol de procesos y espera la última
        # medición (powermetrics tarda segundos); corre en un worker para
        # no congelar la TUI
        self.run_worker(self._do_stop, thread=True)

    def _do_stop(self) -> None:
        summary = self.tracker.stop()
        self.call_from_thread(self._show_summary, summary)

    def _show_summary(self, summary) -> None:
        self._stop_done = True
        self.query_one(MetricsPanel).border_title = "📊 Metrics (final)"
        if summary is not None:
            panel = self.query_one(SummaryPanel)
            panel.show_summary(summary, self.tracker.baseline_comparison)
            panel.add_class("visible")
        if self._exit_when_stopped:
            self.exit()
        else:
            self.notify("✅ Sesión guardada — Q para salir", severity="information")

    def action_start_tracking(self) -> None:
        if self.tracker.config.manual and not self.tracker.tracking_active:
            self.tracker.start_tracking()

    def action_stop_tracking(self) -> None:
        self._finish()

    def action_quit_app(self) -> None:
        self._finish(then_exit=True)
