# Anatomical Core — Fase 1: Skeleton Core (v0.2: neutro + pose A)

## ¿Qué estamos construyendo?

Un motor anatómico 3D reutilizable. A largo plazo servirá para crear personajes humanos (estilizados o realistas), ajustar proporciones, simular tejidos blandos y facilitar la animación. Se construye **por fases**; esta es la primera: un **esqueleto humano articulado de referencia**.

## Qué cambió en la v0.2 (corrección del esqueleto)

La v0.1 tenía la pose A incrustada en la geometría de los huesos, lo que producía ejes no perpendiculares a los huesos, un "reposo" que no era el neutro articular y un quiebre en la rodilla. Ahora hay **tres capas separadas**:

1. **Esqueleto neutro** (`config/skeleton_definition.json`): posición anatómica. Brazos y piernas verticales, antebrazo y mano prolongando el brazo, pie horizontal a 90° de la pierna. Aquí viven los **pivotes y las longitudes** (una sola vez).
2. **Marcos locales** por hueso: ejes X, Y, Z ortonormales (Y = hueso, X = flexión, Z = X × Y). De ahí salen el `roll` en Blender y **todos los ejes articulares** (`config/joints.json`): cada eje es ±un eje local, así que es perpendicular a los demás y al hueso por construcción.
3. **Pose A** (`config/pose_a.json`): una tabla `articulación → grados`, medidos **desde el neutro**, aplicada por cinemática directa. No mueve ni duplica pivotes. En Blender es una rotación de cada *pose bone* (Rest Position = neutro, Pose Position = pose A).

Los **límites articulares** se miden desde el neutro (0° = posición anatómica). Sus valores numéricos no cambiaron respecto a la v0.1.

## Qué hace y qué NO hace esta versión

**Hace**
- Genera 20 huesos y 19 articulaciones (47 grados de libertad) en neutro y con pose A, con jerarquía coherente: pelvis, columna simplificada, cuello, cabeza, clavículas, brazos, manos, muslos, piernas y pies (izquierda/derecha).
- Guarda `.blend`, reporte JSON y vistas previas PNG (pose A y neutro).
- Valida todo automáticamente y **reabre el `.blend` guardado** para comparar huesos, roll, pose evaluada y visualización con el modelo.

**No hace (todavía)**
- No hay malla de piel, músculos, tejidos blandos, IA ni Unity.
- **No es anatómicamente exacto.** Es una estructura inicial *aproximada*.
- Los límites articulares son **aproximaciones configurables, no límites médicos universales**, y **no se aplican como restricciones** en Blender (son datos consultables y la pose se valida contra ellos al generar).
- Manos y pies son un solo hueso (sin dedos, sin talón ni antepié: el apoyo se comprueba con la altura del tobillo, `ankle_height_fraction`).
- No hay hueso de cintura pélvica: las caderas parten de la pelvis con un desplazamiento lateral.
- Se **conservan** las inclinaciones estructurales de la columna (2.3°, 3.4° y 1.1° hacia atrás por segmento), el cuello (6.8° hacia delante) y la clavícula (9.8° de elevación). Forman parte del neutro: su 0° es esa postura.

## Requisitos

Windows con Blender instalado (probado con Blender 5.0.1, Python 3.11 integrado). No hace falta instalar nada más ni GPU dedicada. El script busca Blender por sí solo; si no lo encuentra:

```powershell
$env:ANATOMICAL_BLENDER = "C:\ruta\a\blender.exe"
```

## Ejecutar (PowerShell)

```powershell
cd "C:\Users\EDWIN GC\Downloads\AI_SKETCH\anatomical-core"

# Generar + probar (lo habitual)
powershell -ExecutionPolicy Bypass -File scripts\run.ps1

# Solo generar / solo probar
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Test

# Cambiar la pose A sin tocar archivos, o generar solo el neutro
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate -Pose shoulder.abduction=35,elbow.flexion=20
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate -Neutral
```

El script termina con código **0** si todo está bien y **distinto de 0** si algo falla (`$LASTEXITCODE`).

| Qué | Dónde |
|---|---|
| Archivo Blender | `output\skeleton_core.blend` |
| Reporte (neutro, marcos, ejes, límites, pose y métricas) | `output\skeleton_core_report.json` |
| Vistas previas, pose A | `output\preview_front.png`, `output\preview_side.png` |
| Vistas previas, neutro | `output\preview_neutral_front.png`, `output\preview_neutral_side.png` |
| Registros | `logs\generate_<fecha>.log`, `logs\tests_<fecha>.log` |

## Abrir y revisar el archivo en Blender

Comando para abrirlo directamente (ajusta la ruta de Blender si es otra):

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" "C:\Users\EDWIN GC\Downloads\AI_SKETCH\anatomical-core\output\skeleton_core.blend"
```

1. Pulsa `Home` sobre la vista 3D para encuadrar; `1` (teclado numérico) es la vista frontal y `3` la lateral.
2. **Alternar neutro y pose A:** selecciona `AC_Armature`, abre la pestaña **Object Data** (icono verde de hueso) ▸ **Skeleton** ▸ **Pose Position**: *Rest Position* = esqueleto neutro, *Pose Position* = pose A. La visualización sigue a los huesos en ambos casos.
3. **Revisar los ejes locales (roll):** los huesos muestran sus ejes X, Y, Z (azul = Z, verde = Y, rojo = X). Con `AC_Armature` seleccionada, `Ctrl+Tab` entra al modo Pose; la pestaña **Bone** ▸ **Transform** muestra la rotación local (cuaternión) de cada hueso.
4. **Outliner:** 4 colecciones con ojo para ocultar/mostrar: `AC_Skeleton` (armadura real), `AC_BoneVisuals` (octaedros, azul = izquierda, rojo = derecha, gris = centro; *solo visualización*), `AC_JointMarkers` (esferas amarillas en cada pivote) y `AC_JointAxes` (flechas = ejes de cada articulación, `AX_<articulación>_<movimiento>`).
5. En cada hueso, **Custom Properties** muestra `ac_length_m` y `ac_joint` (pivote, ejes locales, límites y `positive_motion` en JSON). En el objeto `AC_Armature`, `ac_pose` guarda los ángulos de la pose A.

Convención: +Z arriba, el personaje **mira hacia −Y**, su lado **izquierdo es +X** (sufijo `.L`).

### Cómo se leen los ejes y los signos

Un ángulo **positivo** es una rotación de regla de la mano derecha alrededor del eje. El campo `positive_motion` declara hacia dónde se mueve el extremo del hueso; el validador lo comprueba al generar (rotando ±10°).

| Articulación | dof (positivo) | Movimiento positivo |
|---|---|---|
| hombro, cadera | flexion / abduction | hacia delante (−Y) / hacia fuera |
| codo, muñeca | flexion / deviation | hacia delante / radial (hacia fuera) |
| rodilla | flexion | pantorrilla hacia atrás (+Y) |
| tobillo | dorsiflexion | puntera hacia arriba |
| clavícula | elevation / protraction | hombro arriba / hacia delante |
| columna, cuello, cabeza | flexion / lateral_bend | hacia delante / hacia la izquierda (+X) |
| todas | axial, pronation, inversion | giro sobre el eje largo (regla de la mano derecha) |

Los dof de una articulación se componen **en el orden en que aparecen en `joints.json`**, sobre ejes locales fijos. El lado derecho usa el espejo (pseudovector) del izquierdo.

## Interpretar las pruebas

La suite corre **dentro de Blender** y compara números reales, no solo que Blender termine:

- **`test_model.py`**: huesos requeridos, referencias, jerarquía, longitudes, pivotes, apoyo del pie, reproducibilidad y que el validador **detecte** datos corruptos.
- **`test_frames.py`**: marcos ortonormales y derechos, espejo L/R, miembros verticales en el neutro, ejes ortogonales y perpendiculares al hueso, signos positivos y negativos de cada articulación (tabla independiente de la configuración), límites y rechazo del schema 1.
- **`test_pose.py`**: cinemática directa (ángulos medidos = parámetros, cadena calculada a mano, longitudes y conexiones intactas, pivotes sin duplicar ni desplazar, simetría), cuaterniones locales, apoyo y planitud de los pies, separación de tobillos y límites de la pose.
- **`test_blender.py`**: roll y ejes locales **en Blender**, pose evaluada frente a la cinemática directa, Rest/Pose, visualización sin doble transformación, reapertura del `.blend` y scripts como proceso independiente (con casos que deben fallar con código ≠ 0).

- **`test_base_frozen.py`**: la **base** (esqueleto neutro de 20 huesos) debe ser idéntica a su instantánea `tests\golden\base_skeleton.json`; ni la pose ni un nivel posterior pueden modificarla.

- **`test_anatomy.py`** y **`test_anatomy_blender.py`**: nivel 1 (ver más abajo): referencia y nombres, jerarquía enraizada en la base, anclajes exactos, forma y simetría de pelvis y caja torácica, y en Blender que los huesos del nivel 1 son hijos reales de la base.

Resumen esperado: `[SUMMARY] ejecutadas=119 fallos=0 errores=0 omitidas=0` y `RESULTADO FINAL: OK`. Las pruebas fijan los valores **por defecto** de `config\`; si editas la configuración, ejecuta `-Task Generate` (la validación interna siempre corre) y, si un test de valores por defecto falla por tus cambios, es esperado.

## Modificar las proporciones y la pose

**Rápido, por línea de comandos** (no toca archivos):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate -Height 1.85 -Set thigh=0.25 -Pose shoulder.abduction=35
```

**Permanente**: edita los JSON de `config\` y regenera.

| Archivo | Contiene |
|---|---|
| `config\proportions.json` | Altura de referencia, `ankle_height_fraction` y longitud de cada hueso (fracción de la altura). |
| `config\skeleton_definition.json` | Jerarquía, anclaje, dirección **en el neutro** y `frame_x_hint` (orientación del eje X local). |
| `config\joints.json` | Ejes locales (`x`/`y`/`z` + signo), `positive_motion` y límites por articulación. |
| `config\pose_a.json` | Ángulos de la pose A (`articulación.dof`; `shoulder` = ambos lados, `shoulder.L` = solo uno). |

Ángulos iniciales de la pose A: abducción de hombro 40°, flexión de codo 12°, flexión de muñeca 6°, abducción de cadera 3° e inversión de tobillo −3°.

- **Abducción de cadera ↔ inversión de tobillo:** la inversión compensa la abducción para que el pie quede plano (ambas giran sobre el eje largo del pie y se suman exactamente). Si cambias `hip.abduction`, pon `ankle.inversion` con el valor opuesto; si no, el validador falla (pie inclinado > 1°).
- **Los 3° son provisionales.** Con ellos, la separación de tobillos es de 0.272 m (1.49 veces la de caderas; 0.155 de la altura) y la pelvis baja 1.18 mm para apoyar ambos pies. El validador exige el rango 1×–2× de la separación de caderas (aviso fuera de él, error fuera de 0.5×–3×).
- **Apoyo:** la raíz se desplaza en vertical (`root_translation`) para que el pivote de tobillo más bajo quede a `ankle_height_fraction × altura`. Se comprueba que ambos pies quedan planos y al mismo nivel (tolerancia 2 mm).

## La base congelada (nivel 0)

El esqueleto neutro de 20 huesos y 19 articulaciones es la **base de referencia**: cualquier detalle anatómico posterior se construye *sobre* ella sin modificarla. Su instantánea vive en `tests\golden\base_skeleton.json` (huesos, marcos, pivotes, ejes y límites, con la firma `e6f88af5c6c3…`). Un cambio **deliberado** de la base se hace así (y se revisa el diff del golden):

```powershell
py scripts\freeze_base.py --update
```

Sin `--update` el script se niega a sobrescribir la instantánea. Copias locales de los `.blend` anteriores (no se versionan): `output\legacy\skeleton_core_v0.1.blend` y `output\legacy\skeleton_core_v0.2.blend`.

## Nivel 1: anatomía sobre la base

El nivel 1 añade huesos anatómicos como **hijos de los segmentos de la base**, sin modificarla. Vive en su propio archivo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Anatomy
& "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" "C:\Users\EDWIN GC\Downloads\AI_SKETCH\anatomical-core\output\anatomy_level1.blend"
```

| Qué | Dónde |
|---|---|
| Archivo Blender del nivel 1 | `output\anatomy_level1.blend` (la base `skeleton_core.blend` no se toca) |
| Reporte (huesos, anclajes, cobertura de la referencia, limitaciones) | `output\anatomy_level1_report.json` |
| Vistas previas | `output\anatomy_front.png`, `anatomy_side.png`, `anatomy_pelvis_34.png`, `anatomy_thorax_34.png` |

- **Referencia:** `config\reference\human_skeleton_reference.json` (185 huesos, tal como se entregó). Nombres normalizados: lado como sufijo final (`rib_01.L`), `little` en vez de `pinky`, `sternum_body` en vez de `body`.
- **Definición:** `config\anatomy\<region>.json`. Cabeza y cola de cada hueso son **puntos de la base** (`"at": "thigh.L.head"`) o interpolaciones entre ellos (`"lerp"`), más un desplazamiento en fracción de la altura; así siguen las proporciones de la base. `reference` indica qué nombres de la referencia representa cada hueso; `anchors` son uniones que deben coincidir exactamente.
- **En Blender:** colecciones de huesos `L0_base` y `L1_<region>` (panel *Object Data ▸ Bone Collections*, con ojo para mostrar/ocultar); formas `ANA_<hueso>` y contornos de referencia `ANA_outline_<hueso>` (colecciones `AC_Anatomy_Visuals` y `AC_Anatomy_Outlines`). Los huesos del nivel 1 son rígidos respecto a su padre (sin poses propias en este nivel).

Regiones (orden aprobado):

| # | Región | Estado | Huesos |
|---|---|---|---|
| 1 | Cintura pélvica + sacro | hecho | `sacrum_fused`, `coccyx_fused`, `hip_bone.L/R` (ilion + isquion + pubis). La cola de cada coxal **es** la cabeza femoral de la base (anclaje exacto). |
| 2 | Caja torácica + esternón | hecho | `sternum` (manubrio + cuerpo + xifoides, una pieza) y `rib_01…rib_12.L/R`, cada costilla en su vértebra T1–T12 (hija de `thorax` las 1–6, de `spine_thoracic` las 7–12). Da profundidad anteroposterior al torso. |
| 3 | Manos y pies desglosados | pendiente | |
| 4 | Vértebras ajustadas + cráneo | pendiente | |

**Limitación conocida:** la clavícula de la base (congelada) nace casi en el plano de la columna, por lo que queda un hueco de unos 8 cm entre su pivote esternoclavicular y el manubrio (medido en el reporte como `sternoclavicular_gap_m`). Se corregirá al rehacer la cintura escapular.

## Versiones anteriores y compatibilidad

- Esta versión usa `schema_version: 2` y **rechaza el schema 1** con un error claro.
- La v0.1 está en la etiqueta Git `v0.1.0`: `git checkout v0.1.0` la restaura (con su suite de 29 pruebas).
- El `.blend` v0.1 no pasa la validación nueva (la firma no coincide) a propósito. Una copia local del original está en `output\legacy\skeleton_core_v0.1.blend` (no se versiona).

## Estructura del proyecto

```
config/            datos versionados (JSON, schema_version 2)
src/anatomical_core/
  config.py        carga y valida los JSON
  geometry.py      vectores, marcos, rotaciones, cuaterniones y primitivas (sin Blender)
  skeleton.py      esqueleto neutro: huesos, jerarquía, marcos, pivotes (sin Blender)
  joints.py        pivotes, ejes locales y límites (sin Blender)
  pose.py          pose A por cinemática directa (sin Blender)
  validation.py    comprobaciones y diagnósticos (sin Blender)
  scene.py         ÚNICO módulo que usa Blender (bpy): armadura, roll, pose y visualización
  pipeline.py      generar → guardar → reabrir → validar → reporte
scripts/           generate_skeleton.py (Blender) y run.ps1 (PowerShell)
tests/             pruebas automáticas
output/  logs/     resultados y registros (no se versionan; son reproducibles)
```

## Qué falta antes de pasar a la malla corporal y los músculos

1. Revisión anatómica de proporciones y pivotes con referencias (hoy son aproximaciones).
2. Cintura pélvica y caja torácica con más huesos; manos con dedos; pie con talón y antepié (y apoyo real sobre ellos).
3. Aplicar los límites como restricciones en pose (hoy son datos que se validan, no restricciones activas).
4. Altura objetivo exacta, asimetría por lado en las longitudes y ángulos de pose como parámetros nombrados (puntos E5–E10 del informe de inspección).
5. Definir cómo se enlaza la malla (pesos/envolventes) con estos huesos.
