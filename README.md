# Anatomical Core — Fase 1: Skeleton Core

## ¿Qué estamos construyendo?

Un motor anatómico 3D reutilizable. A largo plazo servirá para crear personajes humanos (estilizados o realistas), ajustar proporciones, simular tejidos blandos y facilitar la animación. Se construye **por fases**; esta es la primera: un **esqueleto humano articulado de referencia**.

## Qué hace y qué NO hace esta versión

**Hace**
- Genera un esqueleto de **20 huesos** en **A-pose** con jerarquía coherente: pelvis, columna simplificada (lumbar, torácica, tórax), cuello, cabeza, clavículas, brazo/antebrazo/mano y muslo/pierna/pie (izquierda y derecha).
- Define **19 articulaciones** con pivote, ejes de rotación y límites configurables.
- Guarda un archivo `.blend`, un reporte JSON y vistas previas PNG.
- Valida todo automáticamente (29 pruebas) y **reabre el `.blend` guardado** para comprobar su contenido.

**No hace (todavía)**
- No hay malla de piel, músculos, tejidos blandos, IA, ni Unity.
- **No es anatómicamente exacto.** Es una estructura inicial *aproximada* pensada para ajustarse después.
- Los límites articulares son **aproximaciones configurables, no límites médicos universales**.
- Las formas que ves (octaedros, esferas, flechas) son **solo visualización**, no una malla anatómica.
- Manos y pies son un solo hueso (sin dedos). No hay hueso de cintura pélvica: las caderas parten de la pelvis con un desplazamiento lateral, por eso se ven "sueltas" en la vista previa.

## Requisitos

Windows con Blender instalado (probado con Blender 5.0.1, Python 3.11 integrado). No hace falta instalar nada más ni tener GPU dedicada. El script busca Blender por sí solo; si no lo encuentra:

```powershell
$env:ANATOMICAL_BLENDER = "C:\ruta\a\blender.exe"
```

## Ejecutar (PowerShell)

Desde la carpeta del proyecto:

```powershell
cd "C:\Users\EDWIN GC\Downloads\AI_SKETCH\anatomical-core"

# Generar + probar (lo habitual)
powershell -ExecutionPolicy Bypass -File scripts\run.ps1

# Solo generar / solo probar
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Test
```

El script termina con código de salida **0** si todo está bien y **distinto de 0** si algo falla (puedes comprobarlo con `$LASTEXITCODE`).

Resultados:

| Qué | Dónde |
|---|---|
| Archivo Blender | `output\skeleton_core.blend` |
| Reporte (huesos, pivotes, ejes, límites) | `output\skeleton_core_report.json` |
| Vistas previas | `output\preview_front.png`, `output\preview_side.png` |
| Registros de cada ejecución | `logs\generate_<fecha>.log`, `logs\tests_<fecha>.log` |

## Abrir el archivo en Blender

1. Abre Blender → **File ▸ Open** → selecciona `output\skeleton_core.blend`.
2. Pulsa `Home` con el cursor sobre la vista 3D para encuadrar todo; `1` (teclado numérico) da la vista frontal y `3` la lateral.
3. En el panel **Outliner** (arriba a la derecha) verás 4 colecciones; puedes ocultar/mostrar cada una con el ojo:
   - `AC_Skeleton`: la **armadura real** (huesos y jerarquía).
   - `AC_BoneVisuals`: octaedros de color (azul = izquierda, rojo = derecha, gris = centro). *Solo visualización.*
   - `AC_JointMarkers`: esferas amarillas en cada pivote articular.
   - `AC_JointAxes`: flechas que muestran cada eje de rotación (`AX_<articulación>_<movimiento>`).
4. Selecciona `AC_Armature`, ve a la pestaña **Object Data (icono verde de hueso)** ▸ Bones; en cada hueso, la sección **Custom Properties** muestra `ac_length_m` y `ac_joint` (pivote, ejes y límites en JSON).

Convención: +Z es arriba, el personaje **mira hacia −Y** y su lado **izquierdo es +X** (sufijo `.L`).

## Interpretar las pruebas

La suite corre **dentro de Blender** y verifica datos reales, no solo que Blender termine:

- **`test_model.py`** (datos puros): huesos requeridos, sin referencias rotas, jerarquía de una raíz y sin ciclos, longitudes positivas y finitas, pivotes/ejes/límites válidos, simetría izquierda/derecha, reproducibilidad, y que el validador **detecte** datos corruptos.
- **`test_blender.py`**: genera dos veces y compara, guarda, **reabre desde disco**, comprueba huesos/colecciones/propiedades/flechas, y ejecuta el script como proceso independiente (incluido un caso que debe fallar con código ≠ 0).

Lectura del resumen final: `[SUMMARY] ejecutadas=29 fallos=0 errores=0 omitidas=0` y `RESULTADO FINAL: OK`. Si algo falla, el log indica la prueba y el código del problema (p. ej. `LENGTH_MISMATCH`, `CYCLE`, `MISSING_BONE`). Una prueba "omitida" por falta de Blender cuenta como fallo a propósito.

Atajos: `-NoPreview` omite los renders; el registro completo siempre queda en `logs\`.

## Modificar las proporciones

**Rápido, por línea de comandos** (no toca archivos):

```powershell
# Altura total de 1.85 m y muslo más largo (fracción de la altura)
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Height 1.85 -Set thigh=0.25
```

**Permanente**: edita `config\proportions.json` (longitudes como fracción de la altura) y vuelve a ejecutar. Otros archivos de configuración:

| Archivo | Contiene |
|---|---|
| `config\proportions.json` | Altura de referencia y longitud de cada hueso (fracción de la altura). |
| `config\skeleton_definition.json` | Jerarquía, punto de anclaje, dirección en A-pose (p. ej. cambiar el ángulo de los brazos). |
| `config\joints.json` | Ejes de rotación y límites por articulación (aproximados). |

Tras editar, ejecuta `-Task Test`: la validación te avisa si algo queda inconsistente. Los archivos son JSON: usa comillas dobles, sin comas finales.

## Estructura del proyecto

```
config/            datos versionados (JSON, schema_version)
src/anatomical_core/
  config.py        carga y valida los JSON
  geometry.py      vectores y primitivas de visualización (sin Blender)
  skeleton.py      huesos, jerarquía, pose de reposo (sin Blender)
  joints.py        pivotes, ejes y límites (sin Blender)
  validation.py    comprobaciones y diagnósticos (sin Blender)
  scene.py         ÚNICO módulo que usa Blender (bpy): armadura + visualización
  pipeline.py      generar → guardar → reabrir → validar → reporte
scripts/           generate_skeleton.py (Blender) y run.ps1 (PowerShell)
tests/             pruebas automáticas
output/  logs/     resultados y registros (no se versionan; son reproducibles)
```

Los datos del modelo (longitudes, pivotes, restricciones) están separados de su representación en Blender: todo salvo `scene.py` y `pipeline.py` funciona sin Blender.

## Qué falta antes de pasar a la malla corporal

1. Revisión anatómica de proporciones y pivotes con referencias (hoy son aproximaciones).
2. Cintura pélvica y caja torácica con más huesos; manos con dedos; pies con antepié/dedos.
3. Roll de huesos y ejes locales definitivos para animación (hoy los ejes están en el espacio del modelo).
4. Aplicar los límites como restricciones en pose (hoy son datos consultables, no restricciones activas).
5. Pruebas de poses de ejemplo (rotar articulaciones dentro y fuera de límites).
6. Definir cómo se enlaza la malla (pesos/envolventes) con estos huesos.
