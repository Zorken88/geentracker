# 🌿 GreenTracker

Monitor de consumo energético y huella de carbono para desarrollo de software. Prototipo del **modelo de calidad extendido** (ISO/IEC 25010 + ISO 50001 + ISO 14001) de la tesis *"Modelo de calidad como marco de referencia para la medición de consumo de energía en la ingeniería de software"*.

Lanza cualquier aplicación en desarrollo (Node.js, .NET, Java, Python, etc.) como subproceso y trackea en tiempo real su consumo energético (CPU/GPU/RAM vía CodeCarbon), convirtiéndolo en huella de carbono con el factor de emisión del Sistema Eléctrico Nacional de Chile (**0.245 kgCO₂eq/kWh**, Programa HuellaChile — MMA 2024).

## Guía de uso paso a paso

### 1. Requisitos previos (una sola vez)

- **Python 3.10 o superior** instalado.
  - macOS: `brew install python@3.13` (o desde [python.org](https://www.python.org/downloads/))
  - Linux (Debian/Ubuntu): `sudo apt install python3 python3-venv python3-pip`
  - Windows: instalador de [python.org](https://www.python.org/downloads/) (marcar *"Add Python to PATH"*)
- El código fuente del prototipo (esta carpeta, `proyecto_titulo`).

### 2. Instalación (una sola vez)

#### macOS / Linux

```bash
cd proyecto_titulo
python3 -m venv .venv                 # crear entorno virtual
source .venv/bin/activate             # activar el entorno
pip install -e ".[dev]"               # instalar GreenTracker y dependencias
```

#### Windows (PowerShell)

```powershell
cd proyecto_titulo
python -m venv .venv                  # crear entorno virtual
.venv\Scripts\Activate.ps1            # activar el entorno
pip install -e ".[dev]"               # instalar GreenTracker y dependencias
```

> Si PowerShell bloquea la activación por política de ejecución, ejecutar una vez:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
> (en **cmd.exe** la activación es `.venv\Scripts\activate.bat`)

La instalación registra los comandos `greentracker` y `gtrack` dentro del entorno virtual, junto con las dependencias: CodeCarbon (medición energética), psutil (recursos y procesos) y Textual (TUI).

### 3. Ejecutar una sesión de medición

En **cada terminal nueva** se activa primero el entorno virtual y luego se navega hasta el proyecto que se desea medir:

```bash
# macOS / Linux
source /ruta/a/proyecto_titulo/.venv/bin/activate
cd ~/proyectos/mi-api                 # ir al proyecto A MEDIR
gtrack run "npm run dev"              # lanzar y trackear

# Windows (PowerShell)
\ruta\a\proyecto_titulo\.venv\Scripts\Activate.ps1
cd $HOME\proyectos\mi-api
gtrack run "npm run dev"
```

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

#### Windows

El procesador Intel tiene contadores RAPL, pero Windows no los expone nativamente; el puente era **Intel Power Gadget**, descontinuado por Intel en 2023. En la práctica, en Windows CodeCarbon opera por estimación (`TDP constant`/`cpu_load`). GPU NVIDIA sí se mide vía NVML si hay driver instalado.

En las tres plataformas la herramienta funciona **100% offline** y el cálculo de huella de carbono (HC = E × I, factor SEN 0.245) es idéntico — lo que cambia es la fuente del dato de energía.

### Limitaciones conocidas (relevantes para validez experimental)

- **Efecto observador**: en modo `process`, CodeCarbon mide el árbol de procesos completo de GreenTracker, que incluye a la propia herramienta (Python + Textual) además de la app medida. El overhead es aproximadamente constante entre sesiones, por lo que los **deltas vs línea base siguen siendo válidos**; los valores absolutos incluyen al instrumento.
- **RAM en modo estimación**: el modelo de CodeCarbon aplica un piso de potencia (3 W en ARM, 10 W en x86), por lo que la energía RAM estimada escala con la duración de la sesión, no con el uso real. Comparar sesiones de duración similar, o usar sensores.
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
