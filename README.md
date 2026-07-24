# 🌿 GreenTracker

Monitor de consumo energético y huella de carbono para desarrollo de software. Prototipo del **modelo de calidad extendido** (ISO/IEC 25010 + ISO 50001 + ISO 14001) de la tesis *"Modelo de calidad como marco de referencia para la medición de consumo de energía en la ingeniería de software"*.

Lanza cualquier aplicación en desarrollo (Node.js, .NET, Java, Python, etc.) como subproceso y trackea en tiempo real su consumo energético (CPU/GPU/RAM vía CodeCarbon), convirtiéndolo en huella de carbono con el factor de emisión del Sistema Eléctrico Nacional de Chile (**0.245 kgCO₂eq/kWh**, Programa HuellaChile — MMA 2024).

## Guía de uso paso a paso

### 1. Requisitos previos (una sola vez)

- **Python 3.10 o superior** instalado.
  - macOS: `brew install python@3.13` (o desde [python.org](https://www.python.org/downloads/))
  - Linux (Debian/Ubuntu): `sudo apt install python3 python3-venv python3-pip`
  - Windows: instalador de [python.org](https://www.python.org/downloads/) (marcar *"Add Python to PATH"*)
- El código fuente del prototipo: `git clone https://github.com/Zorken88/greentracker.git` (o esta carpeta, si ya se tiene).

### 2. Instalación (una sola vez)

#### macOS / Linux

```bash
cd greentracker
python3 -m venv .venv                 # crear entorno virtual
source .venv/bin/activate             # activar el entorno
pip install -e ".[dev]"               # instalar GreenTracker y dependencias
```

#### Windows (PowerShell)

```powershell
cd greentracker
python -m venv .venv                  # crear entorno virtual
.venv\Scripts\Activate.ps1            # activar el entorno
pip install -e ".[dev]"               # instalar GreenTracker y dependencias
```

> Si PowerShell bloquea la activación por política de ejecución, ejecutar una vez:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
> (en **cmd.exe** la activación es `.venv\Scripts\activate.bat`)

La instalación registra los comandos `greentracker` y `gtrack` dentro del entorno virtual, junto con las dependencias: CodeCarbon (medición energética), psutil (recursos y procesos) y Textual (TUI).

### 2b. Instalación en el proyecto a medir (recomendado para proyectos Python)

`greentracker` es un paquete pip estándar: puede instalarse directamente en el entorno virtual **del proyecto que se quiere medir** — sin clonar este repositorio ni crear su venv (los pasos 1-2 son solo para desarrollar GreenTracker):

```bash
cd ~/proyectos/mi-api                      # el proyecto A MEDIR
source .venv/bin/activate                  # su propio venv
pip install git+https://github.com/Zorken88/greentracker.git       # desde git
# o, si se tiene el código local:  pip install /ruta/a/greentracker
gtrack run "python main.py"                # python = el del proyecto ✔
```

Para proyectos **no-Python** (Node.js, Java, .NET…) en un equipo nuevo, la forma más cómoda es [pipx](https://pipx.pypa.io) — instala el CLI una sola vez, aislado y disponible globalmente:

```bash
pipx install git+https://github.com/Zorken88/greentracker.git
cd ~/proyectos/mi-app-node
gtrack run "npm run dev"
```

> [!IMPORTANT]
> **Por qué importa (proyectos Python):** si se activa el venv de *GreenTracker* para obtener `gtrack` y luego se mide `python main.py`, ese `python` resuelve al intérprete del venv de GreenTracker — y el proyecto medido fallará por no encontrar **sus** dependencias. Instalar `greentracker` dentro del venv del proyecto medido (esta sección) hace que `gtrack` y `python` convivan en el mismo entorno.
>
> Para proyectos **no-Python** (Node.js, Java, .NET…) el problema no existe — `npm`, `java` o `dotnet` no dependen del venv activo — y sirve cualquiera de las dos formas de instalación.

### 3. Ejecutar una sesión de medición

En **cada terminal nueva** se activa primero el entorno virtual y luego se navega hasta el proyecto que se desea medir:

```bash
# macOS / Linux
source /ruta/a/greentracker/.venv/bin/activate
cd ~/proyectos/mi-api                 # ir al proyecto A MEDIR
gtrack run "npm run dev"              # lanzar y trackear

# Windows (PowerShell)
\ruta\a\greentracker\.venv\Scripts\Activate.ps1
cd $HOME\proyectos\mi-api
gtrack run "npm run dev"
```

> Para medir un **proyecto Python**, usar en su lugar el flujo de la sección 2b (instalar `greentracker` en el venv del propio proyecto).

Consideraciones importantes:

- El comando medido se ejecuta **en el directorio actual**: hay que situarse primero en el proyecto a evaluar.
- La **primera ejecución** de cada proyecto queda registrada automáticamente como **línea base energética** (ISO 50001).
- Al detener (tecla `S` en la TUI, o `Ctrl+C`) se muestra el resumen — energía por componente, huella de carbono, SEU, delta vs línea base — y se persisten `emissions.csv` y `timeline.csv` **en la carpeta del proyecto medido**: cada proyecto acumula su propio historial (Seguimiento, ISO 14001).

Variantes del comando `run`:

```bash
gtrack run --project "mi-api" "dotnet run"                    # nombre de proyecto explícito
gtrack run --interval 5 "java -jar app.jar"                   # intervalo de muestreo (s)
gtrack run --carbon-intensity 0.5 "python manage.py runserver" # otro factor de emisión
gtrack run --electricity-cost 180 "npm run dev"               # tarifa CLP/kWh
gtrack run --manual "npm run dev"                             # tracking inicia con tecla T
gtrack run --no-tui "python script.py"                        # modo consola (CI / tests)
```

### 4. Visualización y análisis

Desde la misma carpeta del proyecto medido:

```bash
gtrack dashboard                     # TUI: Sessions / Compare / Timeline
gtrack baseline                      # línea base y EnPI del proyecto
gtrack baseline --set <session_id>   # re-designar la línea base
gtrack export --json                 # exportar historial a JSON
```

### 5. Uso como librería Python

Además del CLI, `greentracker` se puede **importar** para medir bloques de código desde el propio programa, sin subprocesos. Con el paquete instalado en el venv del proyecto (sección 2b):

```python
import greentracker

with greentracker.track(project="mi-api", label="entrenamiento") as session:
    entrenar_modelo()              # el código a medir

r = session.summary
print(r.energy_consumed)   # EnPI en kWh (ISO 50001)
print(r.emissions)         # kgCO₂eq — Ecuación 3: HC = E × I
print(r.seu_component)     # SEU: componente de mayor consumo
print(r.measurement_mode)  # PowerMetrics / RAPL / TDP...
```

Las sesiones de librería se persisten en el **mismo `emissions.csv`** que el CLI, por lo que la línea base, `gtrack dashboard` y `gtrack baseline` funcionan igual sobre ellas. En este modo el aspecto medido es el **proceso Python anfitrión** (más sus hijos); el proceso nunca es terminado por GreenTracker.

#### Parámetros de `track()`

| Parámetro | Por defecto | Descripción |
|---|---|---|
| `project` | nombre del directorio actual | Agrupa la línea base y el historial del proyecto |
| `label` | `"[librería] proceso actual"` | Descripción de la sesión (columna `command` del CSV) |
| `interval` | `2.0` | Segundos entre muestras |
| `carbon_intensity` | `0.245` | Factor de emisión kgCO₂eq/kWh (SEN — HuellaChile, MMA 2024) |
| `electricity_cost_clp` | `150.0` | Tarifa eléctrica CLP/kWh (extensión, no modelo) |
| `csv_file` | `emissions.csv` | Ruta del CSV de sesiones (relativa al directorio actual) |

#### Durante el bloque `with` — `session.latest` (MetricSnapshot en vivo)

Snapshot actualizado en cada intervalo (puede ser `None` durante el primer muestreo):

| Campo | Unidad | Descripción |
|---|---|---|
| `cpu_percent` / `ram_used_mb` | % / MB | Uso agregado del árbol de procesos |
| `cpu_power_w` / `gpu_power_w` / `ram_power_w` / `total_power_w` | W | Potencia instantánea por componente |
| `cpu_energy_kwh` / `gpu_energy_kwh` / `ram_energy_kwh` / `energy_kwh` | kWh | Energía acumulada por componente y total |
| `emissions_kg_co2eq` | kgCO₂eq | Huella acumulada (propiedad `emissions_g_co2eq` = ×1000) |
| `seu_component` | — | Componente dominante hasta el momento |
| `disk_read_mb_s` / `disk_write_mb_s` | MB/s | E/S de disco (extensión) |
| `child_processes` / `duration_s` / `cost_clp` | — | Hijos, segundos transcurridos, costo CLP |

También está disponible `session.tracking_active` (bool).

#### Al salir del bloque — `session.summary` (SessionSummary, la fila persistida)

| Campo | Tipo | Descripción |
|---|---|---|
| `timestamp` | str | Fecha/hora ISO del cierre de la sesión |
| `session_id` | str | Identificador de 8 caracteres |
| `project` | str | Nombre del proyecto |
| `command` | str | Comando medido (en librería: el `label`) |
| `duration_s` | float | Duración en segundos |
| `cpu_energy` / `gpu_energy` / `ram_energy` | float (kWh) | Energía por componente (Tabla 15) |
| `energy_consumed` | float (kWh) | **Energía total — EnPI (ISO 50001)** |
| `emissions` | float (kgCO₂eq) | **Huella de carbono — Ecuación 3: HC = E × I** |
| `carbon_intensity` | float | Factor de emisión usado en el cálculo |
| `measurement_mode` | str | `PowerMetrics` / `RAPL` / `Power Gadget` / `TDP constant` / `TDP cpu_load` |
| `seu_component` | str | **SEU (ISO 50001)**: `"CPU"`, `"GPU"` o `"RAM"` |
| `seu_breakdown` | str | Desglose, ej. `"CPU 79% \| RAM 21% \| GPU 0%"` |
| `is_baseline` | bool | `True` si la sesión quedó como línea base ⭐ del proyecto |
| `cost_clp` | float | Costo eléctrico estimado en CLP (extensión) |

Tanto `summary` como `latest` exponen **`.to_row()`**, que devuelve un `dict` listo para serializar (JSON, pandas, logging…):

```python
import json

fila = session.summary.to_row()      # dict con las columnas del CSV
print(json.dumps(fila, indent=2))
```

#### Comparación contra la línea base — `session.baseline_comparison`

Si la sesión **no** es la línea base, tras el bloque queda disponible un `dict` (si no hay línea base previa, es `None`):

```python
{
    "baseline_session_id": "66b87ddb",   # sesión ⭐ de referencia
    "energy_delta_pct": -12.4,           # Δ% de energía vs línea base
    "emissions_delta_pct": -12.4,        # Δ% de huella vs línea base
}
```

Un delta negativo significa que esta sesión consumió/emitió **menos** que la línea base (mejora continua, ISO 50001).

### Modos de medición y permisos por plataforma

GreenTracker registra en cada sesión el **método de medición** utilizado (columna `measurement_mode` del CSV, "Modo" en el dashboard). Existen dos categorías:

- **Sensores de hardware** (medición real): `PowerMetrics` (Apple Silicon), `RAPL` (Intel/AMD en Linux), `Power Gadget` (Intel en Windows/macOS Intel, descontinuado).
- **Estimación** (modelo TDP × carga): `TDP constant` / `TDP cpu_load` — fallback cuando no hay acceso a sensores.

> [!IMPORTANT]
> **Solo se deben comparar sesiones medidas con el mismo modo.** Cambiar de estimación a sensores altera drásticamente los valores (energía, SEU, aparición de GPU); una línea base medida por estimación no es comparable con sesiones medidas por sensores. La columna `measurement_mode` existe precisamente para verificar esta homogeneidad.

#### macOS (Apple Silicon) — habilitar sensores reales

Por defecto CodeCarbon cae a estimación TDP (y la potencia de RAM queda fijada al piso del modelo, 3 W en ARM, lo que sesga el SEU hacia RAM en sesiones largas). Para medir con los sensores del chip vía `powermetrics`, autorizarlo **una sola vez** sin contraseña:

```bash
echo "$(whoami) ALL = (root) NOPASSWD: /usr/bin/powermetrics" | sudo tee /etc/sudoers.d/powermetrics
sudo chmod 440 /etc/sudoers.d/powermetrics
```

Luego ejecutar `gtrack run` **sin sudo** — los sensores se detectan automáticamente (`measurement_mode = PowerMetrics`, incluye CPU y GPU del chip).

> ⚠️ No ejecutar `sudo gtrack run ...`: la app medida correría como root y los CSV quedarían con dueño root (las siguientes sesiones sin sudo fallarían al escribir). Si ocurrió, recuperar con `sudo chown $(whoami) emissions.csv timeline.csv` o borrarlos.

#### Linux (Intel/AMD) — habilitar lectura de RAPL

El kernel expone los contadores RAPL en `/sys/class/powercap/intel-rapl`, pero desde kernel ~5.10 su lectura es solo-root por defecto (mitigación del side-channel *Platypus*). Habilitar la lectura para el usuario **de forma persistente** ejecutando **una sola vez**:

```bash
sudo chmod -R a+r /sys/class/powercap/intel-rapl* \
  && echo 'SUBSYSTEM=="powercap", ACTION=="add", RUN+="/bin/chmod -R a+r /sys/class/powercap"' | sudo tee /etc/udev/rules.d/99-rapl.rules \
  && sudo udevadm control --reload-rules
```

El comando hace tres cosas: aplica el permiso de lectura ahora (sin reiniciar), instala una regla udev que lo re-aplica automáticamente en cada arranque (el permiso por sí solo se restablece al reiniciar), y recarga las reglas de udev.

Verificar que quedó operativo (debe imprimir un número, sin sudo):

```bash
cat /sys/class/powercap/intel-rapl:0/energy_uj
```

Con acceso a RAPL, `measurement_mode = RAPL` — es la plataforma de mayor fidelidad para la validación experimental, con medición real de CPU desde sensores sin software adicional.

#### La RAM: modelo de estimación vs medición real

A diferencia de la CPU, **la RAM no se mide con sensores por defecto en ninguna plataforma**: CodeCarbon la *estima* con un modelo por capacidad/DIMM que aplica un piso de potencia (~3 W en ARM, ~10 W en x86). Consecuencias: la energía de RAM escala con la duración de la sesión (no con el uso real) y en sesiones largas el SEU tiende a sesgarse hacia RAM — especialmente visible en Linux x86.

GreenTracker expone las dos opciones que ofrece CodeCarbon (≥ 3.0) para mejorar esto, ambas **opt-in**:

```bash
# 1) Potencia de RAM fija y conocida (reemplaza el modelo de estimación).
#    Regla de codecarbon: nº de DIMMs × 5 W  (ver DIMMs: sudo lshw -C memory -short | grep DIMM)
gtrack run --ram-power 10 "python main.py"

# 2) Linux con dominio RAPL "dram": sumar la energía REAL de memoria a la medición RAPL
gtrack run --rapl-dram "python main.py"
```

En la librería: `greentracker.track(..., force_ram_power=10)` o `track(..., rapl_include_dram=True)`.

Letra chica de `--rapl-dram`:

- Solo funciona si el equipo **expone el dominio `dram` en RAPL** — principalmente procesadores Intel (sobre todo Xeon/servidores). Verificar con:
  ```bash
  cat /sys/class/powercap/intel-rapl*/name /sys/class/powercap/intel-rapl*/*/name 2>/dev/null | grep -i dram
  ```
  Si no aparece nada (caso típico en AMD, ej. Ryzen 4700U), la opción **no tiene efecto**.
- La energía DRAM medida se suma **dentro del componente CPU** (medición RAPL "CPU+DRAM"); la columna `ram_energy` del CSV sigue siendo el modelo de estimación. Evitar sumar ambos como si fueran independientes.
- Regla de siempre: **solo comparar sesiones con la misma configuración de medición** (es parte de lo que registra `measurement_mode`).

#### Windows

El procesador Intel tiene contadores RAPL, pero Windows no los expone nativamente; el puente era **Intel Power Gadget**, descontinuado por Intel en 2023. En la práctica, en Windows CodeCarbon opera por estimación (`TDP constant`/`cpu_load`). GPU NVIDIA sí se mide vía NVML si hay driver instalado.

En las tres plataformas la herramienta funciona **100% offline** y el cálculo de huella de carbono (HC = E × I, factor SEN 0.245) es idéntico — lo que cambia es la fuente del dato de energía.

### Limitaciones conocidas (relevantes para validez experimental)

- **Efecto observador**: en modo `process`, CodeCarbon mide el árbol de procesos completo de GreenTracker, que incluye a la propia herramienta (Python + Textual) además de la app medida. El overhead es aproximadamente constante entre sesiones, por lo que los **deltas vs línea base siguen siendo válidos**; los valores absolutos incluyen al instrumento.
- **RAM en modo estimación**: el modelo de CodeCarbon aplica un piso de potencia (3 W en ARM, 10 W en x86), por lo que la energía RAM estimada escala con la duración de la sesión, no con el uso real. Comparar sesiones de duración similar, fijar `--ram-power` con un valor conocido, o usar `--rapl-dram` en hardware Intel con dominio DRAM (ver *La RAM: modelo de estimación vs medición real*).
- **Duración de sesiones**: al comparar contra la línea base, usar sesiones de duración comparable para que los componentes de consumo fijo se cancelen en el delta.

## Cumplimiento del modelo de calidad

| Dimensión | Característica | Implementación |
|---|---|---|
| ISO/IEC 25010 | Eficiencia de desempeño | Energía total (kWh) por sesión |
| ISO/IEC 25010 | Utilización de recursos | CPU / GPU / RAM (%, W, kWh) |
| ISO/IEC 25010 | Analizabilidad | Dashboard con historial y sparklines |
| ISO/IEC 25010 | Mantenibilidad | Comparación entre sesiones |
| ISO 50001 | Línea base energética | Primera ejecución del proyecto (⭐) |
| ISO 50001 | EnPI | kWh / ejecución |
| ISO 50001 | SEU | Componente de mayor consumo (CPU/GPU/RAM) |
| ISO 50001 | Mejora continua | Delta vs línea base y vs sesión anterior |
| ISO 14001 | Aspecto ambiental | Ejecución del software trackeada |
| ISO 14001 | Impacto ambiental | Huella de carbono: HC = E × I (kgCO₂eq) |
| ISO 14001 | Seguimiento | `emissions.csv` (Tabla 15) + `timeline.csv` + JSON |
| ISO 14001 | Mejora continua | Historial comparativo para refactorización |

Funciona **100% offline**: usa `OfflineEmissionsTracker` de CodeCarbon (`country_iso_code="CHL"`), sin proveedores externos de intensidad de carbono.

## Archivos generados

- `emissions.csv` — una fila por sesión (columnas Tabla 15: `timestamp`, `cpu_energy`, `gpu_energy`, `ram_energy`, `energy_consumed`, `emissions` + `measurement_mode`, SEU, línea base, costo)
- `timeline.csv` — snapshots por intervalo (base de los sparklines)
- `emissions.json` — export opcional

## Tests

```bash
pytest
```
