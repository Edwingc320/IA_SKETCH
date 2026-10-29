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

## Estado (2026-10-27) — añadido tras CM-7
- `muscle-model`: **410 pruebas** en Blender (y Python puro). CM-1 (parcial) a CM-7 hechos; faltan CM-8 (deuda de anclaje del muslo) y CM-9 (cierre de la región).
- `main` no recibió CM-5 a CM-7 (hitos y obstáculos de apoyo, `range_deg`/`rig` y su validación están solo en `muscle-model`).

## Decisiones añadidas (CM-7)
23. **ROM de la cadera**: se auditaron los seis rangos contra StatPearls (registro previo; su página no apareció en la búsqueda), las medias normativas de la AAOS de 2020 (128/17 prono/33/14/42/44), una hoja con los valores redondeados de la AAOS (fuente secundaria, fiabilidad baja) y Physiotutors. Rangos entre fuentes: flexión 110–128, extensión 10–30, abducción 30–50, aducción 14–30, rotación interna 15–45, externa 35–60. Los límites del rig (flexión −15…120, abducción −30…45, axial −40…45) caen dentro. **Se mantiene la extensión de 15°**: bajarla a 10° (el mínimo de las fuentes) reduciría el rango validado sin respaldo y exigiría tocar el golden y las restricciones; no cambió `joints.json`, ni Limit Rotation, ni el golden. Se añadieron `other_sources`, `range_deg` y `rig` a los dof publicados y la validación `ART_ROM_RIG_OUTSIDE`.

## Lecciones técnicas añadidas (CM-7)
- Una discrepancia aparente entre el rig y la literatura puede ser un error de categoría (techo frente a valor típico): antes de cambiar el rig, definir qué significa cada cifra.
- Una prueba antigua que fija el valor de la fuente principal (`total_deg[0]`) obliga a no reutilizar ese campo para otro significado: se añadió un campo nuevo en lugar de reinterpretar el existente.
- El dof `axial` de la cadera: positivo = rotación interna (la punta del pie va a medial), comprobado con la FK; mi primera suposición estaba al revés.

## Pendiente añadido (CM-7)
- Coherencia de las rotaciones de la cadera con la flexión (los límites del rig son independientes por eje).
- Contrastar la hoja secundaria de la AAOS con la guía original; localizar la página de StatPearls de la cadera.
- Sigue pendiente: CM-8 (deuda de anclaje), CM-9 (cierre), y todo lo anotado en «Pendiente añadido (2026-10-27)».

## Estado (2026-10-27) — añadido tras CM-8
- `muscle-model`: **426 pruebas** en Blender (y Python puro). CM-1 (parcial) a CM-8 hechos; falta CM-9 (cierre de la región caderas y muslo).
- Trinquete de deuda de anclaje: **53** (61 → 58 con CM-5 → 53 con CM-8). Muslo y rodilla sin deuda; queda tobillo (sindesmosis y astragalino), columna, costillas, codo, muñeca y cráneo.

## Decisiones añadidas (CM-8)
24. **Obstáculos de la rodilla**: `tibial_proximal` (cápsula de 23 mm; profundidad AP de 46 mm entre 35 y 47 de las series), `patellar_body` (11 mm de radio; grosor de 22 mm, publicado 19–22; eje 11 mm por detrás de la línea del modelo, que es la cara anterior) y `fibular_head_body` (esfera de 10 mm sin cifra). Sanan la tuberosidad tibial, el extremo tibial del rotuliano, la femororrotuliana (lado rótula) y la tibioperonea proximal (tibia y peroné). Los de la tibia no entran en ningún `avoid` (varios anclajes quedan dentro por construcción).
25. **Ligamentos de la rodilla con `deform`**: cruzados, colateral tibial, colateral peroneo y rotuliano siguen a sus huesos en Blender; tolerancia 12 mm (antes 30–40). Los colaterales evitan el fémur; los cruzados llevan `avoid_reason` (intraarticulares). Nuevo `validate_knee_ligament_poses` (barrido de cadera y rodilla hasta 135°).
26. **Limitación conocida del ligamento rotuliano**: la rótula es rígida al fémur; el ligamento pasa de 27 mm a 81 mm a 135° y atraviesa el cóndilo y la diáfisis desde ~100°. Fijado en una prueba; falta un deslizamiento de la rótula.

## Lecciones técnicas añadidas (CM-8)
- Una auditoría de anclajes de una región debe incluir ligamentos, tendones, hitos y centros de articulación, y reconocer la deuda ajena (tobillo) comprobando que sigue en el trinquete.
- Un anclaje exactamente en el límite (`d == tol`) no es deuda para el trinquete (`> tol`); las pruebas de auditoría usan `<=`.
- Un nombre de superficie no puede coincidir con el de un hito (`fibular_head`): comparten espacio de nombres con articulaciones y ligamentos.
- El control negativo de un ligamento corto y junto al eje (los cruzados) deja el extremo a solo ≈ 12 mm: el umbral de la prueba depende de la geometría.

## Pendiente añadido (CM-8)
- Deslizamiento de la rótula (dof de la articulación femororrotuliana) para que el ligamento rotuliano mantenga su longitud y no atraviese el fémur; entonces pasa a evitar el fémur y se invierte la prueba de la limitación.
- CM-9: cierre de la región caderas y muslo (estado, avances y pruebas con mutaciones).
- Deuda restante (53): tobillo (pierna y pie), columna, costillas, codo, muñeca y cráneo.

## HITO COMPLETADO: caderas y muslo (CM-1 a CM-9), 2026-10-27
- **Estado final** (`muscle-model`): **434 pruebas** en verde en Blender. **190 unidades músculo-tendinosas** (95 por lado; la solicitud de cierre decía 172, que era el recuento antes de CM-5 y CM-6 — se registra la cifra real), **94 volúmenes** de vientres (47 por lado: 31 medidos —Holzbaur 24, Ritsche 5, Kajdi 2— y 16 por convención), 16 ligamentos y 24 tendones con envoltura, 20 superficies de obstáculo, 13 y 22 poses de barrido, trinquete de deuda **congelado en 53** (cero en muslo y rodilla).
- **Entregables**: informe de cierre `docs/estado/caderas_muslo_cierre.md`, pruebas de región `tests/test_region_closure_hips_thigh.py`, batería `scripts/mutation_battery.py` (**26 de 26 mutaciones detectadas, 0 sin detectar** (148 s).).

## Decisiones añadidas (CM-9)
27. **Cierre con limitaciones, no con perfección**: CM-1 sigue «parcial» y se dice. La región se considera cerrada porque todo lo construido cumple las reglas vigentes y las carencias están registradas con su causa.
28. **Verificación externa**: la comparación visual con Netter, Sobotta o Gray no es posible (obras con derechos, sin acceso a sus imágenes); se hizo una verificación dimensional y de relaciones anatómicas contra la literatura leída en resúmenes de búsqueda: centro de la cabeza a la línea media 91 mm (≈ 89), cabeza 44 mm (38–48), cuello 30 mm (28–34), ángulo cervicodiafisario 116,7° (119–133: ligero varo, limitación declarada), fémur 0,242 H. Escala isométrica comprobada punto a punto a 1,50, 1,75 y 2,05 m.

## Lecciones técnicas añadidas (CM-9)
- Un proceso lanzado con `&` desde la herramienta de shell sobrevive al comando: **no relanzar una batería que modifica archivos mientras otra sigue viva**; comprobar con `Get-CimInstance Win32_Process` y restaurar `config/` con `git checkout` si una mutación quedó a medias. La batería ahora se niega a empezar con `config/` sin confirmar y registra la restauración con `atexit`.
- Los números de una solicitud (172 unidades) pueden estar desactualizados: se verifican contra el código antes de escribirlos en la memoria del proyecto.

## Pendiente añadido (CM-9)
- Deslizamiento de la rótula; volúmenes medidos (Handsfield 2014, Ward 2009, Lube 2016); contrastar con artículos y atlas lo leído en resúmenes; ángulo cervicodiafisario (varo leve); envolturas por armadura para el resto de ligamentos y tendones; origen del psoas en L1–L5.
- Siguiente región según `docs/plan/00_plan_general.md`: tren superior y torso (planes `10_tren_superior.md` y `20_torso.md`).

## Estado (2026-10-28) — añadido tras CM-10
- `muscle-model`: deslizamiento de la rótula implementado. Verificación **dirigida** (no suite completa, por instrucción del 2026-10-28): 182 pruebas puras de los módulos afectados y los módulos de Blender `test_anatomy_blender` (20), `test_knee_anchors` (15) y `test_patellar_tracking` (16, con las 22 poses a 1,50/1,75/2,05 m) en verde; 7 mutaciones del deslizamiento y del cuádriceps detectadas (7/7). La última suite completa en Blender (450 pruebas) tuvo 3 fallos previstos que se corrigieron después y **no se reejecutó entera**; la cifra total de pruebas vigente es 450.
- Limitación de la rótula (CM-8/CM-9) **resuelta**: ligamento rotuliano 26,7 → 29,2 mm (antes 81,1), sin penetración; cuádriceps con dos guías troclears.

## Decisiones añadidas (CM-10)
29. **Cinemática de la rótula**: rotación alrededor del eje de la rodilla de 0,9 × la flexión (121,5° a 135°) y acercamiento de 0,04 mm/° (5,4 mm), ambos AJUSTADOS a la geometría (ligamento de 27 mm; solo relaciones ≳ 0,85 mantienen su longitud). No se verificó la relación fisiológica; la literatura solo confirma que el tendón rotuliano casi no cambia de longitud entre 30 y 110°. No se modelan tilt ni spin.
30. **Implementación en Blender sin drivers** (hueso auxiliar + Copy Rotation + Transformation); el hueso auxiliar es capa `rig_helper` y el validador del nivel 1 acepta que la rótula cuelgue de él. Los cuatro vientres del cuádriceps pasan a `deform` con dos guías troclears.

## Lecciones técnicas añadidas (CM-10)
- Una prueba de escala a tres alturas detectó que un parámetro en mm/° no escalaba con la altura (0,7 mm de error a 1,50 m): todo parámetro absoluto de la geometría debe definirse a 1,75 m y escalarse.
- Una restricción Transformation de Blender solo mapea linealmente: para que el desplazamiento radial gire con la rotación hay que colgarlo de un hueso hijo del que gira (el auxiliar), no del mismo.
- Con una longitud de ligamento corta (27 mm), solo una inclinación ≳ 0,85 × la flexión mantiene su longitud: el dato geométrico limita la cinemática elegible.
- No lanzar baterías o suites con `&`/segundo plano sin comprobar procesos vivos; y respetar «solo lo modificado»: se detuvo una batería completa y se relanzó filtrada.

## Pendiente añadido (CM-10)
- Verificar la relación flexión de la rótula / flexión de la rodilla y la longitud real del ligamento rotuliano (~45–50 mm) y, si se corrige la longitud, reajustar los parámetros.
- Tilt y spin de la rótula; guías troclears con datos de superficie real.
- Reejecutar la suite completa en Blender cuando se cierre la siguiente región.

## Nueva dirección (2026-10-28): esqueleto sólido idéntico a la imagen
- El usuario pide volver a la estructura y trabajar el esqueleto **por secciones desde `esqueleto humano.jpg`** (stock, 3 vistas, 1083 × 1300), con resultado **idéntico a la imagen en 3D**. Plan `docs/plan/70_esqueleto_referencia.md` (F0–F10) y estado `docs/estado/esqueleto_referencia.md`.
- **Hallazgo**: el modelo actual no se parece a la imagen: sus huesos son líneas, octaedros finos y volúmenes paramétricos; no hay costillas, vértebras ni huesos con forma. Línea base con el comparador de siluetas: IoU medio 0,35 (frente 0,36, espalda 0,37, lado 0,32), máscara de la imagen ruidosa.
- **Hecho (F0)**: `scripts/render_bones_silhouette.py`, `scripts/compare_reference.py`, imagen en `.gitignore`.
- **Decisiones pendientes**: qué manda si la imagen y los datos antropométricos discrepan; alcance de «idéntico» (silueta y forma con relleno liso, o también sombreado). Las regiones pendientes del plan regional (tren superior, torso...) quedan en pausa.
- **Pendiente de verificación**: la suite completa en Blender no se reejecutó entera tras CM-10.
- Lección: un comando de Bash con `rm` fuera del proyecto fue bloqueado por seguridad (y con él el resto del comando): `C:\output` (ruta relativa mal resuelta por Blender) quedó sin borrar y lo debe borrar el usuario.

## Esqueleto de referencia: F1 hecha (2026-10-28)
- **Decisiones del usuario**: los datos antropométricos mandan en las longitudes de los segmentos; la imagen manda en la forma, la silueta y la postura; discrepancias por sección, documentadas; «idéntico» = forma y silueta + estilo (gris liso y contorno oscuro).
- **F1**: `bone_meshes.py` (loft), `bone_meshes_scene.py`, `config/bones/bone_meshes.json`, `tests/test_bone_meshes.py` (15 pruebas) y 4 mutaciones en `scripts/mutation_battery.py`. Primer hueso: fémur L/R; hitos a ≤ 9 mm. IoU medio 0,37 (antes 0,35).
- **Discrepancia para F8**: los fémures de la imagen convergen hacia las rodillas; el modelo tiene el eje mecánico vertical.
- Verificación dirigida (por la instrucción de solo lo modificado): pruebas puras y de Blender de `test_bone_meshes` y `test_anatomy_blender`; no se corrió la suite completa.
- Siguiente: F2 (pelvis y sacro: láminas con grosor, agujeros sacros y obturadores, sínfisis).

## Esqueleto de referencia: F2 hecha (2026-10-28)
- **F2**: ilion y sacro son láminas con grosor (`kind: slab`, plano de Newell, orejas con puentes a los agujeros, `bend`), pubis/isquion/cóccix lofts; 10 mallas; sacro de género 8; anillo pélvico cerrado; hitos a < 12 mm. IoU medio 0,40 (antes 0,37).
- Límites: interlínea sacroilíaca ~8 mm (tolerancia de prueba 10 mm); sacro simétrico a ±6 mm.
- Verificación dirigida: `test_bone_meshes` (28, con Blender) y `mutation_battery -k bmesh` (11/11). No se corrió la suite completa.
- Siguiente: F3 (caja torácica).

## Esqueleto de referencia: F2b articulación coxofemoral (2026-10-28)
- Añadidas `acetabulum` (copa roja, `kind: cup`), `acetabular_roof`, `obturator_frame` (slab con agujero poligonal) y `pubic_symphysis`; `BoneMesh` gana `bone` (padre) y `tone` (grey/bone/joint). Pelvis y sacro en tono hueso; femur gris. 17 mallas.
- Contrato `hip_contract` (tests): la cabeza entra en la copa con 0,5–3,5 mm de holgura, el cuello queda libre (≥ 2 mm del borde), la copa se funde con ilion/isquion/pubis (< 4 mm), el agujero obturador sigue vacío (≥ 15 mm de cualquier malla) y la sínfisis toca los dos pubis.
- IoU medio 0,402 (frente 0,425, espalda 0,434, lado 0,346). Verificación dirigida: `test_bone_meshes` (42) y `mutation_battery -k bmesh`.

## Línea cp.* (2026-10-28)
- A petición del usuario, esqueleto pélvico-femoral-lumbar generado desde cero e independiente de `BM_*`: `cp_skeleton.py` + `scripts/cp_skeleton.py`; objetos `cp.Pelvis`, `cp.FemurL/R`, `cp.LumbarSpine`.
- Origen articular: cabeza femoral, punto medio de acetábulos, disco L5-S1. Redimensionado uniforme por pieza (`cp_resize`, `--dim`) y global (`--height`).
- 12 pruebas de Blender y 9 mutaciones (1 equivalente). Comando: `blender -b --python scripts\cp_skeleton.py -- --height 1.75`.

## Línea cp.*: esqueleto axial (2026-10-28)
- `cp_axial.py`: `cp.ThoracicSpine`, `cp.CervicalSpine`, `cp.Skull`, `cp.Mandible` (origen: disco T12/L1, disco C7/T1, cóndilos occipitales, eje de las ATM). Mismo tono `cp_bone`; cadena Pelvis > Lumbar > Torácica > Cervical > Cráneo > Mandíbula.
- Largos antropométricos (vértice 1,00 H, mentón 0,87 H); forma de la imagen (curvas, espinosas). La imagen dibuja la cabeza más pequeña: gana la antropometría.
- 24 pruebas de Blender; límites: sin costillas, órbitas como depresión con reborde, vértebras sueltas dentro de cada objeto.

## Línea cp.*: pelvis y cráneo de alta densidad (2026-10-28)
- `cp_refine.py` + `config/cp/refine.json`: ala iliaca (lente con el contorno del ilion, fosa cóncava, cresta acampanada), copa acetabular y cráneo de dos parches estrellados; órbitas y abertura piriforme por Boolean exacto (caché en `cp_axial._SKULL_CACHE`, ~7 s la primera vez). Mandíbula con ángulo y pivote en las ATM (0, -0,032, -0,012) H.
- 69 hitos de pelvis, fémur, cráneo y mandíbula a < 12 mm (1,50 / 1,75 / 2,05 m). IoU por región (`scripts/compare_cp_regions.py`): 0,517 → 0,531 (pelvis 0,442 → 0,461; cráneo 0,593 → 0,601).
- Lección: `bmesh.ops.create_uvsphere` sobre una malla grande es O(n) por llamada: crear cada elipsoide en un bmesh aparte y añadirlo. El Boolean con `use_self=True` tardó 286 s; sin él, 7 s.
- 34 pruebas de Blender y 16 mutaciones (todas detectadas tras reforzar pruebas; algunas mutaciones solo se detectaban en la clase de pruebas que no corría la batería).

## Línea cp.*: cráneo y mandíbula por box modeling (2026-10-29)
- `cp_skullbox.py`: jaula de cubo mapeada por perfiles + Inset/Extrude (órbitas, fosa nasal, fosas temporales) + barridos de sección rectangular (arcos, arcada, mandíbula en U) + creases + Subdivision Surface nivel 2. Sin trimesh/Open3D (no instalados).
- **Error propio corregido**: `compare_cp_regions.figure_rows` medía la coronilla sobre la marca de agua (fila 31 en vez de ~72). Ahora usa el contorno oscuro de las columnas centrales. Cifras de IoU antiguas (0,442 / 0,461 / 0,593 / 0,601) eran absolutas erróneas; las nuevas: cráneo 0,784 (original) → 0,810 (elipsoides) → 0,806 (box); pelvis 0,445 → 0,472.
- El box modeling NO mejora significativamente el IoU frente a la versión de elipsoides (0,812/0,783 vs 0,816/0,788 de frente/lado); sí frente al original.
- Lecciones de bmesh: crear la capa `crease_edge` invalida las referencias a aristas (crearla al empezar); `inset_region` con `use_even_offset=True` produce picos tras ajustar a elipse (usar False); las caras de entrada pasan a ser la región interior y `ret['faces']` el anillo.

## Reconstrucción central, etapa B: columna (2026-10-29)
- Petición del usuario: reconstruir el esqueleto central (cráneo, columna, sacro, tórax, pelvis, fémures) por etapas; diagnóstico y plan en `docs/plan/71_reconstruccion_central.md`. Etapa B hecha: `cp_vertebra.py` + `config/cp/spine.json` (vértebras con cuerpo en riñón, arco con foramen, apófisis por región, discos lenticulares).
- Hallazgos del diagnóstico: el tórax NO existe en `cp.*` (las costillas que se ven son polilíneas del nivel 1); **los cóndilos del fémur flotan ~5 cm bajo la diáfisis** (defecto abierto, etapa E); el cráneo sigue siendo un bloque.
- Dimensiones de `spine.json` aproximadas y declaradas (no_numeric_source).
- Lección: una prueba de forma sobre la malla subdividida puede no discriminar (la subdivisión redondea los bordes); medir en la jaula. Otra: las carillas costales y las apófisis contaminan las franjas de medida del cuerpo.

## Pruebas aisladas por suite (2026-10-29)
- `blender -b --factory-startup --python tests/run_tests.py` ejecuta por defecto SOLO el esqueleto óseo actual (`tests/suites.py`: CURRENT = `test_cp_skeleton`, 43 pruebas). `-- --suite legacy` = modelo viejo (492), `-- --suite all` = todo (535), `-- --only a,b` = módulos concretos. `scripts/run.ps1 -Task Test [-Suite current|legacy|all]`.
- Las pruebas del modelo viejo NO se borran ni se relajan; solo dejan de ser la suite por defecto. Una prueba nueva del esqueleto actual se añade a `CURRENT`.
- `tests/support.py` (`build_reference`) da los 69 hitos a las pruebas actuales sin importar pruebas del modelo viejo.

## Cráneo en piezas independientes con bóveda ovoide (2026-10-29)
- `cp.Skull` (bóveda ovoide, superelipsoide ajustado a las 3 imágenes), `cp.SkullFace`, cigomáticos, temporales, mastoides, cóndilos, `cp.TeethUpper`, y `cp.Mandible` + `cp.TeethLower`: cada una una malla cerrada propia (NO unir en un solo sólido). Parámetros en `config/cp/skull.json`; medidas de forma de las imágenes en `config/cp/skull_reference.json`.
- Herramientas: `scripts/skull_reference.py` (siluetas), `scripts/compare_skull_reference.py --blend X` (IoU de forma + superposición), `scripts/render_skull_views.py -- carpeta etiqueta --mode silhouette|depth|parts|shaded`, `cp_skeleton.py --reference-images` (planos de las imágenes en el .blend).
- IoU de forma: frente 0,838 → 0,889; perfil 0,856 → 0,857; atrás 0,827. Las imágenes de referencia nuevas están en `.gitignore`.
- Lección: `bmesh.ops.inset_region` deja las caras de entrada como región interior y el anillo nuevo en `ret['faces']`; las máscaras de color (blanco casi puro) exigen umbral < 251, no 244; un plano con una mutación suave (solo un anillo del barrido) puede seguir tocando a su vecino: la mutación debe alejar toda la pieza.

## Bóveda en 5 huesos (2026-10-29)
- Frontal, parietal L/R, temporal L/R, esfenoides L/R y occipital son mallas independientes cortadas de la bóveda por un mapa de polígonos (`sutures` en `config/cp/skull.json`); `cp.Skull` es ahora el núcleo liso. Las imágenes de referencia no van en el modelo.
