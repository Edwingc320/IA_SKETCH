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
4. Todo hito, extremo de ligamento o sitio muscular debe quedar a **menos de 12 mm** (a 1,75 m; escala con la altura) de la superficie de su hueso. Todo extremo de hueso debe terminar en otra estructura o en un hito definido. **Todo anclaje nuevo cumple los 12 mm**; los 64 anclajes antiguos restantes que aún no (cráneo lateral, vértebras, costillas, codo, rodilla…) están fijados en `tests/test_anchor_debt.py`, un trinquete: la lista solo puede disminuir.
5. Los nombres normalizados no se renombran sin aprobación: lado como sufijo, `little` (no `pinky`), `sternum_body`, `sacrum`, `coccyx`.

## 3. Datos y fuentes
1. Cada cifra con rango lleva su fuente (`sources`: url `https://`, fiabilidad `alta|media|baja`). Sin cifra en las fuentes consultadas → `no_numeric_source`; **no se inventan valores**.
2. Lo apoyado solo en fuentes de fiabilidad baja lo dice en su nota: **«verificar en un atlas»**.
3. Los JSON de `config/` son la fuente de verdad; los scripts generadores son auxiliares y no forman parte del repositorio.

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
5. Acciones difíciles de revertir o de cara al exterior (push, borrar ramas con trabajo único) solo con autorización explícita.
