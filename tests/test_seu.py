"""Tests del SEU — Uso Significativo de la Energía (ISO 50001)."""

from greentracker.seu import compute_seu


def test_cpu_dominant():
    result = compute_seu(cpu_kwh=0.008, gpu_kwh=0.0003, ram_kwh=0.002)
    assert result.component == "CPU"
    assert result.breakdown["CPU"] > result.breakdown["RAM"] > result.breakdown["GPU"]
    assert abs(sum(result.breakdown.values()) - 100.0) < 1e-6


def test_ram_dominant():
    result = compute_seu(cpu_kwh=0.001, gpu_kwh=0.0, ram_kwh=0.005)
    assert result.component == "RAM"


def test_gpu_dominant():
    result = compute_seu(cpu_kwh=0.001, gpu_kwh=0.01, ram_kwh=0.002)
    assert result.component == "GPU"


def test_zero_energy():
    result = compute_seu(0.0, 0.0, 0.0)
    assert result.component == "N/A"
    assert all(pct == 0.0 for pct in result.breakdown.values())


def test_format_breakdown_sorted_descending():
    result = compute_seu(cpu_kwh=0.78, gpu_kwh=0.03, ram_kwh=0.19)
    formatted = result.format_breakdown()
    assert formatted.startswith("CPU 78%")
    assert "RAM 19%" in formatted
    assert formatted.endswith("GPU 3%")
