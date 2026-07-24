"""GreenTracker — Monitor de consumo energético y huella de carbono.

Prototipo del modelo de calidad extendido (ISO/IEC 25010 + ISO 50001 +
ISO 14001) para la medición de consumo de energía en ingeniería de software.

Uso como librería::

    import greentracker

    with greentracker.track(project="mi-api") as session:
        ...  # código a medir

    print(session.summary.emissions)  # kgCO₂eq
"""

from greentracker.api import track
from greentracker.config import TrackerConfig
from greentracker.metrics import MetricSnapshot, SessionSummary
from greentracker.tracker import GreenTracker

__version__ = "0.1.0"

__all__ = [
    "track",
    "GreenTracker",
    "TrackerConfig",
    "MetricSnapshot",
    "SessionSummary",
    "__version__",
]
