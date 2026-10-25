# MEMORY.md — memoria del proyecto `anatomical-core`

Estado y decisiones para retomar el trabajo sin perder contexto. Se **agrega** al final de cada sección; no se reescribe lo anterior.

## Qué es
Motor reproducible y configurable de esqueleto humano 3D en **Blender 5.0.1** (Python 3.11), ejecutado desde PowerShell en Windows. Base congelada (Nivel 0) + anatomía de Nivel 1 (185 huesos de referencia) + capa de uniones (articulaciones, ligamentos, hitos) + capa muscular en otra rama. Todo escala con la altura.

## Cómo se usa
- Generar base: `powershell -ExecutionPolicy Bypass -File scripts\run.ps1 -Task Generate [-Height 1.70|170cm|5ft7in]`
- Generar nivel 1: `-Task Anatomy` (escribe `output\anatomy_level1.blend` y vistas `anatomy_*.png`).
- Pruebas: `-Task Test` o `blender -b --factory-startup --python tests/run_tests.py`.
- Pruebas de Python puro: `python -B -m unittest discover -s tests -p "test_*.py" -t tests`.
- Congelar la base tras un cambio deliberado: `py scripts\freeze_base.py --update` y revisar el diff de `tests/golden/base_skeleton.json`.

## Estado (2026-10-25)
- `main`: modelo óseo. 292 pruebas en verde (Blender). 265 articulaciones naturales, 620 ligamentos, 156 hitos óseos, 124 fuentes. Todas las articulaciones tienen ligamentos salvo la escapulotorácica.
- `muscle-model`: `main` + glúteos (mayor, mediano, menor) + capa de tendones (86 unidades músculo-tendinosas por lado, todo el cuerpo) + volumen de los vientres de los grandes grupos (44 por lado). 320 pruebas.
- Remoto: `origin` = https://github.com/edwingalcol320-blip/AI_SKETCH.git configurado, **pero el push falla con «Repository not found»** (2026-10-25): el repositorio no existe todavía en GitHub o es privado y la sesión no tiene credenciales. Hay que crearlo vacío (sin README) en la cuenta `edwingalcol320-blip` o autenticarse, y luego `git push -u origin main` y `git push -u origin muscle-model`.

## Decisiones tomadas (cronológico)
1. **Base v2**: pelvis inclinada 15,5°, cuello/cabeza repartidos y clavícula del manubrio al acromion (cerró huecos esternoclavicular, acromioclavicular y costoclavicular). Golden actualizado a propósito.
2. **Coxal separado** en `ilium`, `ischium`, `pubis`; `sacrum_fused`/`coccyx_fused` → `sacrum`/`coccyx` (la referencia conserva su nombre y `normalize_reference_name` lo convierte).
3. **Padre del rig vs padre anatómico**: `parent` = segmento base que mueve el hueso; `anatomical_parent` = jerarquía articular (humero→escápula, radio/cúbito→húmero, carpo, tibia/peroné→fémur, astrágalo→tibia…).
4. **Codo**: dof `[pronation, flexion]` (la pronación gira sobre el eje real del antebrazo); pronación ±80°, `elbow.pronation = 70°` en pose A (palma medial y algo anterior). Cadera: extensión 15°.
5. **Modelo óseo limpio**: los orígenes/inserciones musculares salen de `main`; `main` conserva hitos óseos con nombre propio. Los datos musculares antiguos están en el historial (commit `81f52ee`).
6. **Restricciones Limit Rotation** reales por articulación; el acople «rotación axial de la rodilla solo con flexión» se exige en la validación de la pose, **no** en Blender (un driver crea ciclo de dependencias y es no determinista).
7. **Altura con unidades** (`170cm`, `5ft7in`); un número suelto fuera de 0,3–3 m se rechaza. Edad: viable pero **no implementada** (faltan tablas de proporciones por edad con fuente primaria).
8. **Cráneo con volumen** (bóveda paramétrica, índice cefálico 0,78), **cartílago costal** como trayecto propio (verdaderas al esternón, falsas al cartílago superior, flotantes libres), **anillo pélvico cerrado** y extremos libres con hito definido.
9. **Pelvis posterior**: cara auricular del ilion sobre el borde lateral del sacro; sacrotuberoso y sacroespinoso nacen en el borde lateral del sacro; la espina isquiática se modela como parte del isquion.
10. `bone_distance` cuenta también la cara de los contornos cerrados (láminas como el ilion).
11. **Ligamentos de todo el modelo** (2026-10-25): una prueba exige que toda articulación tenga ligamentos salvo la escapulotorácica (músculos y fascia). Secciones: columna (23 niveles ×5 ligamentos + cigapofisarias), tórax y hombro, suelo pélvico, mano y pie (con intercuneiformes 1-2 y 2-3 y cuneocuboidea nuevas). Los dedos del pie y varios ligamentos van por analogía con la mano o con fuentes débiles: «verificar».
12. **Regla de 12 mm con trinquete**: todo anclaje nuevo queda a < 12 mm de su hueso; los antiguos que no cumplen están fijados en `tests/test_anchor_debt.py` (solo puede disminuir; 61 al cierre). La distancia al hueso cuenta la cara de las láminas cerradas y el **volumen del cráneo** (dentro de la bóveda = sobre el hueso).
13. **Vértebras y huesos largos sin anchura**: los puntos se colocan a 8-11 mm del eje, en el orden anatómico correcto, no sobre la apófisis real (documentado en cada nota).
14. **Capa de tendones (`muscle-model`)**: unidad músculo-tendinosa = línea origen → vías óseas → inserción; la longitud del tendón es una **convención visual** declarada (corto 10 %, medio 25 %, largo 45 %), no una medida. Los músculos sin fuente consultada quedan «verificar en un atlas».

15. **Volumen muscular (`muscle-model`)**: cada vientre es un husillo cerrado a lo largo de la línea músculo-tendinosa, con el volumen exacto declarado; medido (Holzbaur 2007: miembro superior, pectoral mayor y dorsal ancho, escalado desde 171,5 cm) o por **convención visual de cuatro clases** (pequeño 40, medio 150, grande 350, muy grande 700 cm³ a 1,75 m) donde no hubo dato (pierna, trapecio, pectoral menor, recto del abdomen, esternocleidomastoideo). Con `--height` el volumen escala con k³ (isométrico, hipótesis declarada). Pendiente: conseguir volúmenes medidos de la pierna (Handsfield 2014, Ward 2009) y verificar braquial y bíceps (ambos 143,7).
16. **Generación en Blender lenta**: `scene._bone_parent_inverses` sondea cada hueso con una actualización completa de la escena (21 s de 32 por generación); la suite completa tarda ~4 min. No se tocó para no alterar el emparentado validado.


## Lecciones técnicas
- Los heredoc largos de Bash fallan: usar la herramienta de escritura de archivos para scripts largos; las barras invertidas se pierden al pasar scripts por la entrada estándar (usar `chr(92)`).
- Una mutación no detectada suele revelar código muerto o una comparación demasiado laxa (ya ocurrió con la conversión de pies y con el cruzado anterior).
- Las comparaciones estrictas entre flotantes necesitan margen mínimo (p. ej. ≥ 1 cm de separación entre cruzados).
- Con `--factory-startup` Blender no carga scripts de usuario; los drivers con expresión simple sí evalúan, pero evitar los que lean su propio hueso.

## Pendiente (no aprobado o sin fuente)
- Verificar en un atlas lo apoyado en fuentes débiles (cintilla iliotibial → tubérculo de Gerdy, deltoides, trapecio, masetero, etc.).
- Altura objetivo exacta y longitudes por lado; detección de intercambio L/R en el validador.
- Protracción esternoclavicular del modelo (45° en total) por encima de los 35° publicados; extensión de muñeca (60°) por debajo de la publicada (66–70°). Cambiarlas exige actualizar el golden.
- Capa de poses del Nivel 1 (FK genérica, reparto del movimiento, ATM e intervertebrales): viable, no construida.
- Perfiles por edad (`config/profiles/<perfil>/`).
- Un script que reescribe un trozo de código con `rindex` puede borrar lo que sigue (pasó con las constantes de `validation.py`): comprobar siempre el diff.
- Los nombres de ligamentos y de articulaciones comparten espacio de nombres (error «Nombre de unión duplicado»).
- Una prueba que "pasa a la primera" no basta: mutar el dato para ver que falla (una vez reveló código muerto y otra una comparación laxa).

## Pendiente añadido (2026-10-25)
- Crear el repositorio en GitHub o autenticar, y hacer `git push` de `main` y `muscle-model`.
- Verificar en un atlas los tendones sin fuente o con fuente débil, los ligamentos de los dedos del pie y los costotransversos.
- Reducir los 61 anclajes antiguos de `test_anchor_debt.py` (costillas–vértebra, codo, muñeca, rodilla, tobillo).
