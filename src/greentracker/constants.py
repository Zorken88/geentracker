# Factor de emisión del Sistema Eléctrico Nacional de Chile (SEN)
# Fuente: Programa HuellaChile — Ministerio del Medio Ambiente (2024),
# "Factores de emisión nivel básico". Mismo valor parametrizado en la
# tesis (Ecuación 4). Configurable con --carbon-intensity.
DEFAULT_CARBON_INTENSITY = 0.245  # kgCO₂eq/kWh

COUNTRY_ISO_CODE = "CHL"  # para OfflineEmissionsTracker

DEFAULT_INTERVAL = 2.0  # segundos
DEFAULT_CSV_FILE = "emissions.csv"
TIMELINE_CSV_FILE = "timeline.csv"

# Tarifa eléctrica promedio Chile (residencial)
# Configurable con --electricity-cost (varía según compañía y región)
# Extensión del prototipo (no forma parte del modelo de calidad)
DEFAULT_ELECTRICITY_COST_CLP = 150.0  # CLP/kWh
