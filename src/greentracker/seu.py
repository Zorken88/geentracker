"""Uso Significativo de la Energía (SEU) — ISO 50001, Tabla 9 de la tesis.

Identifica el componente de hardware (CPU, GPU o RAM) con mayor demanda
energética durante la ejecución, con su desglose porcentual.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SEUResult:
    component: str              # "CPU" | "GPU" | "RAM" | "N/A"
    breakdown: dict[str, float] # porcentaje por componente

    def format_breakdown(self) -> str:
        ordered = sorted(self.breakdown.items(), key=lambda kv: kv[1], reverse=True)
        return " | ".join(f"{name} {pct:.0f}%" for name, pct in ordered)


def compute_seu(cpu_kwh: float, gpu_kwh: float, ram_kwh: float) -> SEUResult:
    energies = {"CPU": max(cpu_kwh, 0.0), "GPU": max(gpu_kwh, 0.0), "RAM": max(ram_kwh, 0.0)}
    total = sum(energies.values())
    if total <= 0:
        return SEUResult(component="N/A", breakdown={k: 0.0 for k in energies})
    breakdown = {k: (v / total) * 100.0 for k, v in energies.items()}
    component = max(energies, key=energies.get)
    return SEUResult(component=component, breakdown=breakdown)
