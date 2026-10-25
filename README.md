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

- **`test_articulations.py`**: puntos de unión del tórax y la cintura escapular (articulaciones, ligamentos, hitos óseos), rangos con fuente, motores coincidentes con los pivotes de la base, hitos del esternón y holgura escápula–costillas.

- **`test_head_neck.py`**: cabeza y columna cervical: jerarquía, lordosis (Cobb C2–C7 = 17,1°), plano de Frankfort horizontal, centro de gravedad de la cabeza, pivote exacto de la mandíbula en la ATM y sus puntos de unión.

- **`test_lumbar_pelvis.py`**: columna lumbar, sacro y pelvis: jerarquía, parámetros espinopélvicos (pendiente sacra 37°, lordosis L1–S1 51,9°), centro de masas y puntos de unión.

- **`test_arm_hand.py`**: brazos y manos: jerarquía anatómica (húmero → escápula, radio y cúbito → húmero, filas del carpo, cadenas de falanges exactas), palma medial y algo anterior en pose A, pronación sobre el eje real del antebrazo y puntos de unión.

- **`test_rig_limits.py`**: orden Euler y límites por eje, restricciones *Limit Rotation* reales en Blender (recortan el codo a 145°, bloquean el eje de la bisagra) y acople de la rodilla en la validación de la pose.

- **`test_connectivity.py`**: el pivote es exactamente la cabeza del hueso hijo y ningún hueso del nivel 1 queda separado de su padre sin una articulación natural.

- **`test_height.py`**: altura con unidades (`170cm`, `5ft7in`) y escala lineal de todo el modelo óseo entre 1,50 y 2,05 m.

- **`test_closure.py`**: volumen del cráneo (cerrado, simétrico, escala con la altura, ancho = índice × longitud), cierre de costillas y cartílagos, anillo pélvico y ningún extremo de hueso sin término.

- **`test_spine_ligaments.py`**, **`test_thorax_ligaments.py`**, **`test_pelvic_floor.py`** y **`test_hand_foot_ligaments.py`**: ligamentos de la columna, el tórax y el hombro, el suelo pélvico y la mano y el pie; todas las articulaciones tienen ligamentos salvo la escapulotorácica.

- **`test_anchor_debt.py`**: trinquete de los anclajes antiguos a más de 12 mm de su hueso (solo puede disminuir).

- **`test_pelvis_closure.py`**: sacroilíaca sin hueco, ligamentos sacrotuberoso y sacroespinoso cerrando el piso posterior y todo hito pélvico o glúteo a menos de 12 mm de la superficie de su hueso.

- **`test_leg_foot.py`**: piernas y pies: jerarquía anatómica (fémur → ilion, tibia y peroné → fémur, rótula delante de la rodilla, astrágalo → tibia, tarso y metatarso, cadenas de dedos exactas con las puntas a menos de 12 mm del suelo) y puntos de unión.

Resumen esperado: `[SUMMARY] ejecutadas=292 fallos=0 errores=0 omitidas=0` y `RESULTADO FINAL: OK`. Las pruebas fijan los valores **por defecto** de `config\`; si editas la configuración, ejecuta `-Task Generate` (la validación interna siempre corre) y, si un test de valores por defecto falla por tus cambios, es esperado.

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

El esqueleto neutro de 20 huesos y 19 articulaciones es la **base de referencia**: cualquier detalle anatómico posterior se construye *sobre* ella sin modificarla. Su instantánea vive en `tests\golden\base_skeleton.json` (huesos, marcos, pivotes, ejes y límites, con la firma `aa221b46014f…`). Un cambio **deliberado** de la base se hace así (y se revisa el diff del golden):

```powershell
py scripts\freeze_base.py --update
```

Sin `--update` el script se niega a sobrescribir la instantánea. Copias locales de los `.blend` anteriores (no se versionan): `output\legacy\skeleton_core_v0.1.blend` y `output\legacy\skeleton_core_v0.2.blend`.

**Historial de cambios deliberados de la base**

| Versión | Qué cambió | Qué se conserva exactamente |
|---|---|---|
| v2 | **Pelvis** inclinada 15,5° (PT) con el segmento lumbar compensando; **cuello** 79 → 149 mm y **cabeza** 236 → 167 mm; **clavícula** del manubrio al acromion (175 → 208 mm). Firma `aa221b46014f…` | Pivotes de hombro, codo, muñeca, cadera, rodilla y tobillo; inicio de la columna torácica; estatura (vértex en 1,749011 m); límites articulares |

Para volver a la base anterior: `git checkout main` (la rama de la v2 es `fix/base-level0-v2`) o la etiqueta `v0.1.0` para la v0.1.

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
| Vistas previas | `output\anatomy_front.png`, `anatomy_side.png`, `anatomy_pelvis_34.png`, `anatomy_thorax_34.png`; aisladas (solo nivel 1): `anatomy_level1_front.png`, `anatomy_level1_side.png`, `anatomy_spine_head_lateral.png`, `anatomy_hand_L_palmar.png`, `anatomy_foot_L_lateral.png`, `anatomy_foot_L_plantar.png` |

- **Referencia:** `config\reference\human_skeleton_reference.json` (185 huesos, tal como se entregó). Nombres normalizados: lado como sufijo final (`rib_01.L`), `little` en vez de `pinky`, `sternum_body` en vez de `body`.
- **Definición:** `config\anatomy\<region>.json`. Cabeza y cola de cada hueso son **puntos de la base** (`"at": "thigh.L.head"`) o interpolaciones entre ellos (`"lerp"`), más un desplazamiento en fracción de la altura; así siguen las proporciones de la base. `reference` indica qué nombres de la referencia representa cada hueso; `anchors` son uniones que deben coincidir exactamente.
- **En Blender:** colecciones de huesos `L0_base` y `L1_<region>` (panel *Object Data ▸ Bone Collections*, con ojo para mostrar/ocultar); formas `ANA_<hueso>` y contornos de referencia `ANA_outline_<hueso>` (colecciones `AC_Anatomy_Visuals` y `AC_Anatomy_Outlines`). Los huesos del nivel 1 son rígidos respecto a su padre (sin poses propias en este nivel).

Regiones (orden aprobado):

| # | Región | Estado | Huesos |
|---|---|---|---|
| 1 | Cintura pélvica + sacro | hecho | `sacrum`, `coccyx`, `ilium.L/R`, `ischium.L/R` y `pubis.L/R`. Los tres huesos de cada lado **coinciden en el acetábulo**, que es el pivote de la cadera de la base (anclaje exacto); el ilion cuelga del sacro y el isquion y el pubis, del ilion. |
| 2 | Caja torácica + esternón | hecho | `sternum` (manubrio + cuerpo + xifoides, una pieza) y `rib_01…rib_12.L/R`, cada costilla en su vértebra T1–T12 (hija de `thorax` las 1–6, de `spine_thoracic` las 7–12). Da profundidad anteroposterior al torso. |
| 3 | Manos y pies desglosados | hecho | 53 por lado (106): carpo (8), metacarpo (5) y falanges (14) de la mano, todos descendientes del hueso base `hand`; tarso (7), metatarso (5) y falanges (14) del pie, descendientes de `foot`. Pulgar y dedo gordo con 2 falanges. Mano en posición anatómica (palma al frente, pulgar lateral, dedos rectos); talón, cabezas metatarsianas y puntas de los dedos a pocos mm del suelo, con arco medial. |
| 4 | Columna + cabeza | hecho | `C1`–`C7`, `T1`–`T12`, `L1`–`L5` (C1/C2 representan `C1_atlas`/`C2_axis`), `cranium`, `mandible`. Cadena continua de abajo arriba (sacro → L5 → … → C1 → cráneo → mandíbula): cada vértebra nace en la cola de la inferior. Repartidas por igual sobre sus segmentos base; las torácicas coinciden con los niveles de las costillas. Curva en S sagital (lordosis lumbar y cervical, cifosis torácica), nula en las uniones con la base. |
| 5 | Huesos largos + cintura escapular | hecho | `scapula`, `humerus`, `radius`, `ulna`, `femur`, `patella`, `tibia`, `fibula` (.L/.R). Húmero, fémur y tibia coinciden con sus segmentos base; radio lateral y cúbito medial (supinación), la muñeca queda entre sus extremos distales; el tobillo, entre los maléolos de tibia y peroné; rótula delante de la rodilla; escápula detrás de las costillas, de la glenoide (= pivote del hombro) al ángulo inferior (T7). |

**Tórax y cintura escapular** (especificación completa con fuentes en `docs\anatomia_torax_cintura_escapular.md`): cada costilla cuelga de su vértebra T1–T12, el esternón de T4 y la escápula de la clavícula; el esternón sigue los niveles publicados (escotadura yugular T2–T3, ángulo esternal T4–T5 con la 2.ª costilla, xifoides T10) y la escápula no toca las costillas (holgura medida 29 mm).

**Cabeza y cuello** (especificación con fuentes en `docs\anatomia_cabeza_cuello.md`): lordosis cervical calibrada a 17,1° de Cobb (media publicada), cráneo mirando hacia delante con el plano de Frankfort horizontal y el centro de gravedad por delante de los cóndilos, y mandíbula con su pivote exactamente en el eje de las dos ATM.

**Columna lumbar, sacro y pelvis** (`docs\anatomia_lumbar_sacro_pelvis.md`): sacro como raíz del bloque pélvico (el ilion y el cóccix cuelgan de él; isquion y pubis, del ilion), L5 sobre la meseta de S1, pendiente sacra de 37° y lordosis L1–S1 de 51,9° (medias de dos cohortes asintomáticas). Con la base v2 la pelvis se inclina 15,5° (inclinación pélvica dentro de lo publicado).

**Brazos y manos** (`docs\anatomia_brazos_manos.md`): húmero hijo de la escápula, radio y cúbito hijos del húmero, fila proximal del carpo hija del radio y el cúbito, fila distal de la proximal y falanges en cadenas exactas (30 huesos por lado); en pose A la palma queda medial y algo anterior (`elbow.pronation = 70°`; los dof del codo pasan a `[pronation, flexion]`, cambio deliberado de la base).

**Avances por capa** (`docs\avances\00_indice.md`): un documento por capa (esqueleto, articulaciones, ligamentos, tendones, músculos y piel —aún no iniciada—) para consultar el estado de un vistazo; la plantilla para investigar una región es `docs\plantilla_investigacion_region.md`.

**Ligamentos y articulaciones de todo el modelo** (`docs\ligamentos_articulaciones_modelo_completo.md`): ligamentos de todos los niveles de la columna, de las costillas, el esternón, el hombro, el suelo pélvico y los dedos, y las articulaciones cigapofisarias e intercuneiformes. Una prueba exige que toda articulación tenga ligamentos salvo la escapulotorácica. Los tendones son del modelo muscular (`muscle-model`).

**Cráneo con volumen y cierres** (`docs\anatomia_cabeza_cuello.md`, `anatomia_torax_cintura_escapular.md`, `anatomia_lumbar_sacro_pelvis.md`): el cráneo es una bóveda redondeada paramétrica (ancho biparietal = índice cefálico × longitud, `volumes.py`); cada costilla 1–10 cierra con su cartílago (verdaderas en el esternón, falsas en el cartílago superior); el anillo pélvico es continuo (sacro, ilion, acetábulo, pubis, sínfisis) y todo extremo de hueso termina en otra estructura o en un hito definido (`test_closure.py`).

**Articulaciones, límites y pivotes** (`docs\articulaciones_limites_pivotes.md`): cada hueso que mueve una articulación lleva una restricción *Limit Rotation* local con los límites de `joints.json` (ejes sin dof bloqueados); el pivote es exactamente la cabeza del hueso hijo. La altura se da en metros o con unidades (`-Height 1.70`, `-Height 170cm`, `-Height 5ft7in`) y todo lo óseo se deduce de ella. Cambios deliberados de la base: pronación del codo ±80° y extensión de cadera 15°.

**Piernas y pies** (`docs\anatomia_piernas_pies.md`): fémur → ilion, tibia y peroné → fémur, rótula delante de la rodilla, astrágalo → tibia, calcáneo y navicular → astrágalo, cuboides → calcáneo, cuneiformes → navicular, metatarsianos en su hueso del tarso y cadenas de dedos exactas con las puntas a 10,3 mm del suelo (30 huesos por lado).

**Puntos de unión para poses futuras** (`config\articulations\thorax_shoulder.json`, `head_neck.json`, `lumbar_pelvis.json`, `arm_hand.json` y `leg_foot.json`): 265 articulaciones naturales (tórax y cintura escapular: esternoclavicular, acromioclavicular, glenohumeral, escapulotorácica, costovertebrales, costotransversas, esternocostales, intercondrales, intervertebrales C7/T1–T12/L1, manubrioesternal, xifoesternal; cabeza y cuello: atlantooccipital, atlantoaxial, intervertebrales C2–C7, temporomandibulares; lumbar y pelvis: intervertebrales L1–S1, sacroilíacas, sacrococcígea, sínfisis del pubis, coxofemorales; brazos y manos: codo, radiocubitales, radiocarpiana, mediocarpiana, carpometacarpianas, MCF, IFP e IFD; piernas y pies: tibiofemoral, femororrotuliana, tibioperoneas, tobillo, subastragalina, talonavicular, calcaneocuboidea, cuneonavicular, tarsometatarsianas, MTF e IF), 620 ligamentos y 156 hitos óseos, con 124 fuentes citadas y su fiabilidad. Las tolerancias de anclaje se definen para 1,75 m y escalan con la altura. Los rangos pueden ir en grados o en mm (mandíbula), y se marca cuando la fuente los da por lado. Cada rango numérico lleva su fuente; sin cifra publicada, el rango queda vacío. En Blender: colecciones `AC_Articulations`, `AC_Ligaments`, `AC_Attachments` (objetos `ART_`, `LIG_`, `ATT_`, emparentados a su hueso; propiedades con tipo, rangos y fuentes). Son datos: todavía no mueven el rig.

**Padre del rig y padre anatómico.** Cada hueso tiene dos relaciones:

- `parent` (la jerarquía real de Blender): el **segmento base que lo mueve** (o un hueso rígido que cuelga de él). Así todo el nivel 1 sigue cualquier pose de la base: girar `spine_lumbar` arrastra L1–L5 y todo lo que está encima (vértebras, cráneo, costillas, escápulas, brazos), girar `neck` arrastra C1–C7, cráneo y mandíbula, girar `upper_arm` arrastra húmero, radio, cúbito y mano.
- `anatomical_parent` (propiedad `ac_anatomical_parent` en Blender): la **relación anatómica** pedida: L5 → sacro, cadena vertebral, C1 → cráneo → mandíbula, escápula → T2, húmero → escápula, radio/cúbito → húmero, fémur → ilion, tibia/peroné/rótula → fémur.

Si coinciden (p. ej. dentro de un mismo segmento base: L5 → L4 → … → L1), el rig sigue la cadena anatómica. Si el hueso anatómico padre lo mueve otro segmento base (el húmero lo mueve `upper_arm`, no la escápula), el rig usa el segmento base para que la pose de la base no lo deje atrás.

**Limitaciones conocidas** (se miden en el reporte o en las pruebas):

- La clavícula (base v2) mide 208 mm, más que una real (≈ 150 mm), porque los hombros de la base son anchos; su extremo coincide con el acromion y su origen queda a 19 mm de la escotadura yugular.
- La cabeza base sigue siendo unos 2 cm más larga que un cráneo real (conserva toda la estatura; el cuello mide 149 mm).
- La mano y el pie base no se re-emparentan a radio/cúbito ni a tibia/peroné (cambiaría la base congelada): la unión es geométrica (muñeca entre radio y cúbito distales; tobillo entre los maléolos) y cinemática (los mueve el mismo segmento base).

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

## Ramas

Solo hay dos lineas de trabajo, una por cada parte del cuerpo:

- **`main`: modelo de estructura osea.** Base (nivel 0), huesos del nivel 1, articulaciones, ligamentos y hitos oseos. No contiene musculos ni tendones (una prueba lo vigila).
- **`muscle-model`: modelo de estructura muscular.** Es `main` mas una capa muscular propia (`config/muscles/`, `muscles.py`, `muscles_scene.py`, `tests/test_muscles.py`): cada origen e insercion nace de un hito oseo de `main`. Como esos archivos no existen en `main`, **`main` se puede fusionar en `muscle-model`** sin perder nada. Hoy contiene los gluteos (`docs/musculos_gluteos.md`) y la capa de tendones de todo el cuerpo (`docs/tendones.md`: 80 unidades musculo-tendinosas por lado). Pendiente: el resto de musculos, y verificar en un atlas lo apoyado en fuentes debiles (la cintilla iliotibial en el tuberculo de Gerdy, deltoides, trapecio, masetero, temporal, psoas, etc.; los datos antiguos estan en el historial, commit `81f52ee`).

Las ramas de trabajo se fusionan en `main` y se borran; el tag `v0.1.0` se conserva.
