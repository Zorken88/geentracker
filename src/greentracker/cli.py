"""CLI de GreenTracker (comandos: run, dashboard, baseline, export)."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from greentracker import __version__
from greentracker.baseline import BaselineManager
from greentracker.config import TrackerConfig
from greentracker.constants import (
    DEFAULT_CARBON_INTENSITY,
    DEFAULT_CSV_FILE,
    DEFAULT_ELECTRICITY_COST_CLP,
    DEFAULT_INTERVAL,
)
from greentracker.csv_writer import export_json, read_sessions
from greentracker.metrics import SessionSummary

app = typer.Typer(
    name="greentracker",
    help="🌿 Monitor de consumo energético y huella de carbono para desarrollo de software.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"greentracker {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", help="Muestra la versión.", is_eager=True, callback=_version_callback
    ),
) -> None:
    pass


def _default_project() -> str:
    return Path.cwd().name


@app.command()
def run(
    command: str = typer.Argument(..., help='Comando a ejecutar y trackear, ej: "npm run dev"'),
    project: str = typer.Option(None, "--project", "-p", help="Nombre del proyecto (default: directorio actual)."),
    interval: float = typer.Option(DEFAULT_INTERVAL, "--interval", "-i", help="Intervalo de muestreo en segundos."),
    carbon_intensity: float = typer.Option(
        DEFAULT_CARBON_INTENSITY,
        "--carbon-intensity",
        help="Factor de emisión en kgCO₂eq/kWh (default: 0.245, SEN Chile — HuellaChile).",
    ),
    electricity_cost: float = typer.Option(
        DEFAULT_ELECTRICITY_COST_CLP, "--electricity-cost", help="Tarifa eléctrica en CLP/kWh."
    ),
    file: Path = typer.Option(Path(DEFAULT_CSV_FILE), "--file", "-f", help="Archivo CSV de sesiones."),
    manual: bool = typer.Option(False, "--manual", help="El usuario controla el inicio del tracking (tecla T en la TUI)."),
    no_tui: bool = typer.Option(False, "--no-tui", help="Modo consola sin TUI (útil para CI/tests)."),
) -> None:
    """Ejecuta un comando y trackea su consumo energético y huella de carbono."""
    config = TrackerConfig(
        command=command,
        project=project or _default_project(),
        interval=interval,
        carbon_intensity=carbon_intensity,
        electricity_cost_clp=electricity_cost,
        csv_file=file,
        manual=manual,
    )
    from greentracker.tracker import GreenTracker

    tracker = GreenTracker(config)
    if no_tui:
        _run_console(tracker)
    else:
        from greentracker.tui.app import GreenTrackerApp

        GreenTrackerApp(tracker).run()
        if tracker.summary is not None:
            _print_summary(tracker.summary, tracker.baseline_comparison)


def _run_console(tracker) -> None:
    config = tracker.config
    console.print(f"🌿 [bold green]GreenTracker[/] — {config.project} (session {tracker.session_id})")
    if config.manual:
        console.print("[yellow]Modo manual: en consola el tracking inicia inmediatamente.[/]")
    console.print(f"▶ Ejecutando: [bold]{config.command}[/]\n")
    tracker.start()
    try:
        while tracker.process.running:
            for line in tracker.process.read_new_lines():
                console.print(f"  {line}")
            snap = tracker.latest
            if snap is not None:
                console.print(
                    f"[dim]⚡ {snap.energy_kwh:.6f} kWh | 🌍 {snap.emissions_g_co2eq:.4f} gCO₂eq "
                    f"| 🔥 SEU: {snap.seu_component} | CPU {snap.cpu_percent:.0f}% "
                    f"| RAM {snap.ram_used_mb:.0f}MB | 👶 {snap.child_processes}[/]"
                )
            time.sleep(config.interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Deteniendo tracking...[/]")
    for line in tracker.process.read_new_lines():
        console.print(f"  {line}")
    summary = tracker.stop()
    if summary is not None:
        _print_summary(summary, tracker.baseline_comparison)


def _print_summary(summary: SessionSummary, comparison: dict | None) -> None:
    table = Table(title=f"🌿 Resumen de sesión — {summary.project} ({summary.session_id})")
    table.add_column("Métrica", style="bold")
    table.add_column("Valor", justify="right")
    table.add_row("Duración", f"{summary.duration_s:.1f} s")
    table.add_row("Energía CPU", f"{summary.cpu_energy:.6f} kWh")
    table.add_row("Energía GPU", f"{summary.gpu_energy:.6f} kWh")
    table.add_row("Energía RAM", f"{summary.ram_energy:.6f} kWh")
    table.add_row("Energía total (EnPI)", f"{summary.energy_consumed:.6f} kWh")
    table.add_row(
        "Huella de carbono",
        f"{summary.emissions:.6f} kgCO₂eq ({summary.emissions * 1000:.4f} g)",
    )
    table.add_row("Factor de emisión", f"{summary.carbon_intensity} kgCO₂eq/kWh (SEN)")
    table.add_row("Modo de medición", summary.measurement_mode)
    table.add_row("SEU (ISO 50001)", f"{summary.seu_component} — {summary.seu_breakdown}")
    table.add_row("Costo estimado", f"${summary.cost_clp:.4f} CLP")
    if summary.is_baseline:
        table.add_row("Línea base", "⭐ Esta sesión es la línea base del proyecto")
    elif comparison:
        energy_delta = comparison.get("energy_delta_pct")
        emissions_delta = comparison.get("emissions_delta_pct")
        if energy_delta is not None:
            table.add_row("vs línea base (energía)", f"{energy_delta:+.1f}%")
        if emissions_delta is not None:
            table.add_row("vs línea base (CO₂eq)", f"{emissions_delta:+.1f}%")
    console.print(table)


@app.command()
def dashboard(
    project: str = typer.Option(None, "--project", "-p", help="Filtrar por proyecto."),
    file: Path = typer.Option(Path(DEFAULT_CSV_FILE), "--file", "-f", help="Archivo CSV de sesiones."),
) -> None:
    """Abre el dashboard TUI de visualización y análisis."""
    if not file.exists():
        console.print(f"[red]No existe {file}. Ejecuta primero: gtrack run \"<comando>\"[/]")
        raise typer.Exit(code=1)
    from greentracker.tui.dashboard import DashboardApp

    DashboardApp(csv_file=file, project=project).run()


@app.command()
def baseline(
    set_session: str = typer.Option(None, "--set", help="Re-designa la línea base a esta sesión."),
    project: str = typer.Option(None, "--project", "-p", help="Proyecto (default: directorio actual)."),
    file: Path = typer.Option(Path(DEFAULT_CSV_FILE), "--file", "-f", help="Archivo CSV de sesiones."),
) -> None:
    """Muestra o re-designa la línea base energética del proyecto (ISO 50001)."""
    project = project or _default_project()
    manager = BaselineManager(file)
    if set_session:
        if manager.set_baseline(project, set_session):
            console.print(f"⭐ Línea base de [bold]{project}[/] re-designada a la sesión {set_session}.")
        else:
            console.print(f"[red]No se encontró la sesión {set_session} para el proyecto {project}.[/]")
            raise typer.Exit(code=1)
        return
    base = manager.get_baseline(project)
    if base is None:
        console.print(f"[yellow]El proyecto {project} aún no tiene sesiones registradas.[/]")
        raise typer.Exit(code=1)
    console.print(
        f"⭐ Línea base de [bold]{project}[/]: sesión {base['session_id']} "
        f"({base['timestamp']}) — EnPI: {float(base['energy_consumed']):.6f} kWh/ejecución, "
        f"{float(base['emissions']):.6f} kgCO₂eq"
    )


@app.command()
def export(
    json_flag: bool = typer.Option(True, "--json", help="Exportar a JSON."),
    project: str = typer.Option(None, "--project", "-p", help="Filtrar por proyecto."),
    file: Path = typer.Option(Path(DEFAULT_CSV_FILE), "--file", "-f", help="Archivo CSV de sesiones."),
    output: Path = typer.Option(Path("emissions.json"), "--output", "-o", help="Archivo de salida."),
) -> None:
    """Exporta las sesiones a JSON (módulo de almacenamiento CSV/JSON de la tesis)."""
    if not json_flag:
        raise typer.Exit()
    if not read_sessions(file, project):
        console.print("[yellow]No hay sesiones que exportar.[/]")
        raise typer.Exit(code=1)
    path = export_json(file, output, project)
    console.print(f"✅ Exportado a [bold]{path}[/]")


if __name__ == "__main__":
    app()
