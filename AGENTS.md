# AGENTS.md — reglas del proyecto `anatomical-core`

Reglas para cualquier agente o desarrollador. **Regla principal: no se modifican las consideraciones existentes; solo se AGREGAN nuevas o se refinan.** Si un cambio las contradice, se pide aprobación explícita y se registra en `MEMORY.md`.

## 1. Capas y ramas
1. **Base (Nivel 0)**: 20 huesos neutros, 19 articulaciones, 47 dof. Congelada en `tests/golden/base_skeleton.json`. Solo se cambia a propósito con `py scripts\freeze_base.py --update` y revisando el diff del golden.
2. **Nivel 1 (modelo óseo)**: 185 huesos funcionales colgados de la base (`config/anatomy/`), más articulaciones naturales, ligamentos y hitos óseos (`config/articulations/`).
3. **`main` = modelo óseo.** No contiene músculos ni tendones (la prueba `TestBoneModelHasNoMuscles` lo vigila).
4. **`muscle-model` = `main` + capa muscular** (`config/muscles/`, `muscles.py`, `muscles_scene.py`, `tests/test_muscles.py`). Cada origen/inserción nace de un hito óseo de `main`. `main` se puede fusionar en `muscle-model`; nunca al revés.
5. Las ramas de trabajo se fusionan en su rama destino por avance rápido y se borran. El tag `v0.1.0` se conserva.

## 2. Restricciones técnicas
1. Sistema de coordenadas: +X izquierda, **+Y atrás (anterior = −Y)**, +Z arriba; el personaje mira a −Y; sufijo de lado `.L` / `.R`. Unidades: metros; la geometría se define en fracciones de la altura H (referencia 1,75 m) y escala linealmente con `--height` (`1.70`, `170cm`, `5ft7in`).
2. **Sin drivers ni scripts embebidos** en el `.blend`: un driver que lee el propio hueso que limita crea un ciclo de dependencias y deja de ser determinista.
3. Los dof se componen en el orden listado en `joints.json` (= orden Euler de las restricciones *Limit Rotation*); los ejes sin dof se bloquean a 0.
4. Todo hito, extremo de ligamento o sitio muscular debe quedar a **menos de 12 mm** (a 1,75 m; escala con la altura) de la superficie de su hueso. Todo extremo de hueso debe terminar en otra estructura o en un hito definido. **Todo anclaje nuevo cumple los 12 mm**; los 58 anclajes antiguos restantes (61 hasta CM-5) que aún no (cráneo lateral, vértebras, costillas, codo, rodilla…) están fijados en `tests/test_anchor_debt.py`, un trinquete: la lista solo puede disminuir.
5. Los nombres normalizados no se renombran sin aprobación: lado como sufijo, `little` (no `pinky`), `sternum_body`, `sacrum`, `coccyx`.

## 3. Datos y fuentes
1. Cada cifra con rango lleva su fuente (`sources`: url `https://`, fiabilidad `alta|media|baja`). Sin cifra en las fuentes consultadas → `no_numeric_source`; **no se inventan valores**.
2. Lo apoyado solo en fuentes de fiabilidad baja lo dice en su nota: **«verificar en un atlas»**.
3. Los JSON de `config/` son la fuente de verdad; los scripts generadores son auxiliares y no forman parte del repositorio.
4. En la capa de tendones (`muscle-model`) la **longitud del tendón es una convención visual** (corto 10 %, medio 25 %, largo 45 %), declarada en los datos; no se presenta como medida. Los músculos y tendones sin fuente consultada llevan «verificar en un atlas». El volumen de un vientre es **medido** (con su fuente y la altura de sus sujetos) o una **convención visual declarada** como tal; nunca se presenta una clase de tamaño como medida.

## 4. Pruebas (deben quedar en VERDE)
1. `python -B -m unittest discover -s tests -p "test_*.py" -t tests` (Python puro) y la suite completa dentro de Blender: `blender -b --factory-startup --python tests/run_tests.py` (línea `[SUMMARY] … fallos=0 errores=0`).
2. No se debilita una prueba para que pase. Si una prueba fija un diseño que se cambia a propósito, se adapta y se explica el motivo en el commit.
3. Toda función nueva lleva pruebas y se **comprueba con mutaciones** (cambiar el dato o el código, ver que la suite falla, restaurar los bytes exactos).
4. La verificación de aislamiento de un commit se hace extrayéndolo con `git archive` y ejecutando la suite allí.

## 5. Flujo de trabajo
1. Un commit por sección (mensaje en español, sin acentos, explicando el porqué), con el trailer de coautoría del entorno.
2. Rama de trabajo `feat/<tema>` o `fix/<tema>` → pruebas en verde → commit → fusión por avance rápido → borrar la rama → `git push`.
3. Los resultados regenerables (`output/`, `logs/`, `*.blend1`) no se versionan. `output/legacy/*.blend` no se toca.
4. Responder en español e informar con honestidad: fallos, límites y lo no verificado se dicen tal cual.
5. Al cerrar cada sesión se **agrega** una línea de avance en `docs/avances/` (capa afectada, fecha, qué cambió y qué queda pendiente); el índice es `docs/avances/00_indice.md`. Las casillas de la región trabajada se marcan en `docs/estado/` y el plan está en `docs/plan/`.
6. Acciones difíciles de revertir o de cara al exterior (push, borrar ramas con trabajo único) solo con autorización explícita.

## 6. Rutas con envoltura, obstáculos y volúmenes medidos (añadido 2026-10-27, CM-1 a CM-6)
1. **Nodos que viajan con su hueso.** Un ligamento (`via`) o una unidad músculo-tendinosa (`via`) es una poligonal origen → guías → inserción; cada nodo sigue a su hueso. `deform: true` hace que en Blender sus mallas cuelguen de la armadura (Armature + grupos de vértices); lo demás sigue rígido. Todo ligamento o unidad con `deform` declara `avoid` (las superficies que no puede atravesar); sin `avoid` la validación falla.
2. **Obstáculos (`bone_surfaces`)**: esferas y cápsulas analíticas (cabeza, cuello, trocánter mayor, diáfisis y cóndilo lateral del fémur, rama del pubis, isquion). Son **convención de obstáculo**: el hueso real del modelo es un esqueleto de líneas. Llevan fuente con rango publicado o `no_numeric_source: true` con la palabra «convención» en la nota. `bone_distance(..., surfaces)` las cuenta para la regla de 12 mm. Cada ruta evita solo las superficies de su `avoid`: no se aplican todas a todo (los ligamentos antiguos, p. ej. los cruzados, viven dentro del hueso).
3. **Barridos obligatorios.** Ligamentos de la cadera: 13 poses (`HIP_SWEEP`: flexión 0–120°, extensión 15°, abducción 45°, aducción, rotaciones y combinaciones). Tendones con envoltura: 22 poses (`LEG_SWEEP`, con rodilla hasta 135°). En todas, a 1,50, 1,75 y 2,05 m y en ambos lados: distancia con signo a los obstáculos ≥ 0 con margen, y las láminas del ilion y del sacro no se cortan (un tramo que empieza o acaba sobre la lámina la toca, no la atraviesa: margen de 1 mm).
4. **Propiedades mecánicas** (`mechanics`): sin datos publicados se declaran `convencion_parametrica_declarada` con valores nulos; una validación impide rellenarlas sin fuente. El modelo da geometría y envoltura, no fuerzas.
5. **Volúmenes musculares**: `config/muscles/volume_measurements.json` registra lo hallado con DOI, población y estado de verificación (`verified`, `derived`, `applied_in_model`). Solo las cifras verificadas con unidad de vientre pasan a `muscle_volumes.json`, con su fuente y la altura de referencia (si la fuente no la publica se asume 1,75 m y se dice). Los derivados y lo no verificado no se aplican, salvo la excepción declarada de las medias de Kajdi para el glúteo mediano y menor (cohorte de 65 años: subestima). Una prueba fija el conjunto de ids verificados.
6. **Blender y la mezcla lineal**: los anillos de los nodos son exactos; el anillo de la unión miotendinosa (dentro de un tramo entre dos huesos que giran entre sí) se desvía de la recta exacta. Las pruebas de penetración usan la poligonal de **nodos**, nunca los anillos intermedios, y acotan la desviación visual (30 mm). No se afirma que el tubo de Blender coincida con la recta del modelo.
7. **Mutaciones en las pruebas**: cada ruta nueva se comprueba quitando una guía, metiendo un extremo en el hueso, desplazando un extremo o hito fuera de los 12 mm y alterando el JSON; la prueba debe fallar. Una guía que no hace falta para esquivar un obstáculo se dice en la nota (p. ej. la del epicóndilo lateral).
8. **Documentación tras cada commit** (instrucción del 2026-10-27): después de cada commit se **agregan** los cambios a `AGENTS.md` (si hay reglas nuevas), `MEMORY.md` (estado, decisiones, lecciones, pendiente), `README.md` (recuentos de pruebas y archivos) y `docs/` (`avances/`, `estado/`, `plan/`) en un commit de documentación propio, y se sube con `git push`.

