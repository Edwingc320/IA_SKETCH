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

## Estado (2026-10-27) — añadido tras CM-6
- `main`: modelo óseo + ligamentos de la cadera con envoltura (CM-4). 311 pruebas en Blender.
- `muscle-model`: `main` + músculos. **397 pruebas** en Blender (y Python puro). 95 unidades músculo-tendinosas por lado (190), 47 volúmenes por lado (94, contando los glúteos), 58 anclajes antiguos en el trinquete.
- Remoto: `origin` = https://github.com/Edwingc320/IA_SKETCH.git (la nota de «Repository not found» de arriba quedó obsoleta: el push funciona; `main`, `muscle-model` y el tag `v0.1.0` están subidos).
- Región en curso: caderas y muslo (`docs/estado/caderas_muslo.md`). CM-1 (parcial) a CM-6 hechos; faltan CM-7 (ROM de la cadera), CM-8 (deuda de anclaje del muslo) y CM-9 (cierre).

## Decisiones añadidas (CM-1 a CM-6)
17. **CM-1/CM-2 (volúmenes)**: `config/muscles/volume_measurements.json` es el registro de la literatura (Ritsche 2025, Trappe 2001, Kajdi 2025; Takahashi 2025 sin verificar, «no usar»). Se aplicaron al modelo los cinco vientres de Ritsche (vasto lateral 636,5; bíceps femoral 197,4, cabeza larga como hipótesis; gastrocnemio medial 224,7 y lateral 112,6; tibial anterior 119,4 cm³) con altura de referencia 1,75 m **asumida**. Las clases de convención sobrestimaban (tibial anterior 350 frente a 119,4). Recto femoral, vasto intermedio y medial son derivados y siguen por convención.
18. **CM-3 (glúteos)**: `muscle_volumes` admite músculos de la capa `muscles` (eje centroide de los orígenes → inserción). Mediano 339,1 y menor 92,15 cm³ = media simple de mujeres y hombres de Kajdi (cohorte de 65 años con dolor trocantérico: subestima, declarado); el mayor, convención `muy_grande`.
19. **CM-4 (cadera, en `main`)**: `Ligament.via/mechanics/deform`, `bone_surfaces` y el módulo `ligament_paths`. Extremos del pubofemoral e isquiofemoral movidos del eje del cuello (dentro del hueso) a su superficie; guía de envoltura en el pubofemoral; mallas deformadas por la armadura. Rigidez y longitud sin tensión: convención paramétrica declarada, sin valores.
20. **CM-5 (rutas)**: eminencia iliopúbica como polea del psoas-ilíaco; cintilla iliotibial nueva y tensor de la fascia lata con guías sobre el trocánter mayor y el epicóndilo lateral; obstáculos nuevos del fémur y la rama del pubis (convención); `avoid` por unidad; barrido de 22 poses (`LEG_SWEEP`). El origen del ilíaco se desplazó 10,8 mm a la cara interna de la lámina del ilion (el hito `iliac_fossa.L` está 9,8 mm por fuera). La deuda de anclaje bajó 61 → 58 por las superficies de convención del fémur, no por datos nuevos.
21. **CM-6 (músculos profundos)**: piriforme, obturadores interno y externo, gemelos, cuadrado femoral, pectíneo y aductor corto; hitos `pectineal_crest`, `obturator_margin`, `trochanteric_fossa`, `intertrochanteric_crest`; obstáculo `ischial_ramus` (cápsula de 5 mm, convención); la lámina del sacro entra en el barrido. Las fuentes discrepan (inserción del cuadrado y del obturador externo, si los gemelos insertan en el tendón del obturador interno): se eligió la versión mayoritaria y se anotó.
22. **Política de ramas con ligamentos**: el trabajo de ligamentos va a `main` y se fusiona en `muscle-model`; lo que afecta a hitos y obstáculos de CM-5/CM-6 (capa ósea de apoyo) quedó solo en `muscle-model`, así que `main` no tiene el hito de la eminencia ni los obstáculos del fémur distal.

## Lecciones técnicas añadidas
- **Mezcla lineal de la armadura**: un punto interior de un tramo entre dos huesos que giran entre sí no queda sobre la recta entre los nodos posados (error ≈ u(1−u)(R_b−R_a)(B−A)). Comprobar la penetración sobre los nodos, no sobre los anillos intermedios. Se había sobreafirmado en CM-5 y se corrigió en CM-6.
- Un obstáculo nuevo cambia la distancia al hueso de anclajes antiguos: el trinquete exigió quitar tres entradas; los obstáculos que solapan una zona de inserción (p. ej. la esfera del trocánter sobre la base del cuello) deben quedar fuera del `avoid` de las rutas que insertan ahí.
- Un hito de la base puede estar al otro lado de la lámina del hueso (fosa ilíaca a 9,8 mm por fuera): comprobar los cortes de lámina antes de fiarse de un hito como origen.
- Una guía que no hace falta para esquivar un obstáculo se detecta quitándola; si la prueba no falla, se dice (epicóndilo lateral).
- Las búsquedas web solo dan resúmenes: las cifras y las fuentes leídas así se marcan «leído en el resumen de búsqueda» y de fiabilidad media o baja.
- En PowerShell un `foreach ($t in …)` dentro de una orden pasada por Bash se rompe por la expansión de `$`: usar la herramienta PowerShell.

## Pendiente añadido (2026-10-27)
- CM-7: ROM de la cadera (el rig permite 15° de extensión; `articulations` documenta 10° de StatPearls).
- CM-8: deuda de anclaje del muslo; CM-9: cierre de la región. Después: tren superior, torso, pierna y pie, cabeza y cuello, piel (`docs/plan/`).
- Volúmenes sin dato: glúteo mayor, semitendinoso, semimembranoso, aductores, grácil, sartorio, TFL, psoas, ilíaco, sóleo, peroneos y los nuevos profundos; Handsfield 2014, Ward 2009 y Lube 2016 siguen inaccesibles.
- Verificar en un atlas el origen del psoas (T12–L5; hoy L2), el paso de la cintilla sobre el trocánter mayor, la posición de la eminencia iliopúbica y de los cuatro hitos de CM-6.
- Llevar la deformación por la armadura al resto de ligamentos y tendones que cruzan una articulación (hoy solo los de la cadera y los seis tendones con envoltura).
- Eliminar la desviación visual del anillo de la unión miotendinosa (huesos auxiliares con restricciones).

