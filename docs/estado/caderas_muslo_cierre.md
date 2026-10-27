# Informe de cierre: caderas, pelvis y muslo (CM-1 a CM-9)

Rama `muscle-model` · Cierre: 2026-10-27 · Estado detallado y registro: [caderas_muslo.md](caderas_muslo.md) · Plan: [../plan/30_caderas_muslo.md](../plan/30_caderas_muslo.md)

## Resultado

La región queda **cerrada con limitaciones declaradas**. Todo lo construido tiene geometría anclada a < 12 mm, ruta sin penetración en el barrido de 22 poses a 1,50, 1,75 y 2,05 m, pruebas con mutaciones y fuentes anotadas. CM-1 sigue siendo **parcial** (faltan volúmenes medidos de varios músculos) y no se disfraza de completo.

## Cifras finales (verificadas por `tests/test_region_closure_hips_thigh.py`)

| Concepto | Valor |
|---|---|
| Unidades músculo-tendinosas | **190** (95 por lado). *Corrección:* la solicitud de cierre hablaba de 172; 172 era el recuento antes de CM-5 (cintilla iliotibial, +2) y de CM-6 (ocho músculos profundos y aductores, +16) |
| Volúmenes de vientres | **94** (47 por lado: 31 medidos —Holzbaur 24, Ritsche 5, Kajdi 2— y 16 por convención) |
| Ligamentos con envoltura (`deform`) | 16 (3 de la cadera + 5 de la rodilla, ×2) |
| Tendones con envoltura | 24 (12 por lado) |
| Superficies de obstáculo | 20 (10 por lado; todas convención) |
| Barridos | 13 poses de cadera (`HIP_SWEEP`) y 22 de cadera y rodilla (`LEG_SWEEP`, rodilla hasta 135°) |
| Trinquete de deuda de anclaje | **53** congelado (`DEBT_CEILING`); cero entradas de fémur, rótula, rodilla o muslo |
| Pruebas en Blender | **434** (426 antes del cierre + 8 de región) |

## Qué se hizo por paso

| Paso | Resultado |
|---|---|
| CM-1 (parcial) | registro de volúmenes de la literatura con DOI, población y verificación (Ritsche 2025, Trappe 2001, Kajdi 2025) |
| CM-2 | cinco volúmenes medidos del muslo y la pierna aplicados (altura de referencia 1,75 m asumida) |
| CM-3 | volumen de los glúteos (mediano y menor con Kajdi, cohorte de 65 años; mayor por convención) |
| CM-4 | ligamentos iliofemoral, pubofemoral e isquiofemoral con guías de envoltura y mallas deformadas por la armadura |
| CM-5 | psoas-ilíaco (polea en la eminencia iliopúbica) y cintilla iliotibial (trocánter mayor, epicóndilo lateral, Gerdy) |
| CM-6 | piriforme, obturadores, gemelos, cuadrado femoral, pectíneo y aductor corto; cuatro hitos nuevos |
| CM-7 | ROM de la cadera auditado: extensión de 15° mantenida (rango entre fuentes 10–30°) |
| CM-8 | trinquete 58 → 53; ligamentos de la rodilla siguen a sus huesos; limitación del rotuliano medida |
| CM-9 | este cierre: pruebas de región, batería de mutaciones, informe y memoria del proyecto |

## Verificación cruzada con la literatura

**Comparación con atlas (Netter, Sobotta, Gray): no se pudo hacer.** Son obras con derechos de autor y no tengo acceso a sus láminas; no se afirma que la reconstrucción coincida visualmente con ellas. La verificación es **dimensional y de relaciones anatómicas**, contra cifras de la literatura **leídas en resúmenes de búsqueda** (no en los artículos completos). Recomendación: abrir `output\anatomy_level1.blend`, ocultar las colecciones que estorben y comparar a ojo con el atlas que uses.

| Medida | Modelo (1,75 m) | Literatura | Veredicto |
|---|---|---|---|
| Centro de la cabeza femoral a la línea media | 91 mm | ≈ 89 mm (150 caderas, Bone & Joint 360); 104–109 mm según una serie de CT | dentro |
| Diámetro de la cabeza femoral | 44 mm | 38–48 mm | dentro (convención) |
| Diámetro del cuello | 30 mm | 28–34 mm | dentro (convención) |
| Ángulo cervicodiafisario | **116,7°** (≈ 121° con el eje vertical de la base) | 119–133° según la serie (cadáver 119,1°; radiografía 129–132°) | **ligeramente en varo**: por debajo de las series; limitación declarada |
| Longitud femoral (centro de la cabeza a los epicóndilos) | 0,242 H (42,4 cm) | el cociente 0,245 H del muslo es el de la base; no se pudo confirmar contra Drillis y Contini en la búsqueda | coherente con la base, sin verificar en la fuente |
| Relaciones (trocánter mayor lateral al menor, eminencia iliopúbica anterior, fosa trocantérica posterior, pecten medial a la eminencia, psoas por la eminencia, piriforme y obturador externo por detrás de la cabeza) | se cumplen | cualquier atlas | dentro |

La escala isométrica se comprobó punto a punto: nodos de ligamentos y tendones, superficies, hitos y volúmenes son proporcionales a la altura a 1,50, 1,75 y 2,05 m (los volúmenes con k³). No hay inconsistencias morfológicas graves detectadas; la única desviación dimensional es el varo leve.

## Limitaciones conocidas (registro formal)

1. **Deslizamiento de la rótula.** La rótula sigue rígida al fémur. El ligamento rotuliano pasa de 27 mm a 81 mm a 135° de flexión y atraviesa el cóndilo y la diáfisis desde unos **100°**. Solo se garantiza que sus extremos siguen a su hueso y quedan a < 12 mm. Pendiente: dof de deslizamiento de la rótula en la articulación femororrotuliana (cinemática articular del rig); entonces el ligamento pasará a evitar el fémur y se invertirá la prueba que lo fija.
2. **Mezcla lineal de la armadura en los tubos.** Los nodos de los tubos con envoltura son exactos, pero el anillo de la unión músculo-tendón se desvía de la recta exacta **hasta 23 mm** (obturador interno a 120° de flexión con aducción). Es visual: el modelo de datos es la recta entre nodos y las pruebas de penetración usan los nodos. La prueba acota el desvío en 30 mm.
3. **Obstáculos de convención.** Las veinte superficies (cabeza, cuello, trocánter, diáfisis, cóndilo, rama del pubis, isquion, tibia proximal, rótula y cabeza del peroné) dan cuerpo a huesos que son líneas; solo las de la cabeza, el cuello, el cóndilo, la tibia proximal y la rótula tienen una cifra publicada de apoyo y las demás dicen «convención». La deuda de anclaje baja en parte por ellas.
4. **Varo leve** del cuello femoral (116,7° frente a 119–133°).
5. **Fuentes de fiabilidad media o baja, leídas en resúmenes de búsqueda:** morfometría del fémur, rótula y tibia proximal; ROM de la AAOS (2020) y Physiotutors; hoja secundaria de la AAOS (baja); anatomía de los músculos profundos (flashcards y blogs, baja o media); sin acceso a StatPearls de la cadera (sus cifras vienen del registro previo). Las fuentes discrepan en la inserción del cuadrado femoral, del obturador externo y de los gemelos.
6. **CM-1 parcial:** sin volumen medido para el glúteo mayor, los isquiotibiales mediales, los aductores, el grácil, el sartorio, el TFL, el psoas, el ilíaco, el sóleo, los peroneos ni los ocho profundos; recto femoral, vasto intermedio y medial son derivados por convención. Handsfield 2014, Ward 2009 y Lube 2016 siguen inaccesibles.
7. **Origen del psoas** en L2 (la especificación pide L1–L5 / T12–L5) y paso de la cintilla sobre el trocánter mayor: no confirmados en las fuentes consultadas.
8. **Mecánica de los ligamentos de la cadera:** rigidez y longitud sin tensión sin datos (convención paramétrica declarada, valores nulos).
9. **Coherencia de las rotaciones de la cadera con la flexión:** los límites del rig son independientes por eje.
10. **`main`** no contiene CM-5 a CM-9 (hitos y obstáculos de apoyo, `range_deg`/`rig`): solo `muscle-model`.

## Reglas de validación vigentes (resumen; el detalle está en `AGENTS.md` §6)

Anclajes < 12 mm con superficies de obstáculo; `deform` exige `avoid` o `avoid_reason`; barridos de 13 y 22 poses sin penetración y sin cortar las láminas del ilion y del sacro; límites del rig dentro del rango entre fuentes; volúmenes medidos solo con fuente y altura declarada; trinquete con techo en 53; mutaciones en cada paso.

## Verificación final

Se rellena al cierre del commit: ver la sección siguiente.

### Batería de mutaciones

`python scripts\mutation_battery.py` (restaura los bytes exactos de cada archivo tras cada mutación).

- ✔ gmed_volume_from_the_male_cohort  (muscle_volumes.json; test_muscle_volumes, test_volume_measurements)

- ✔ tibialis_anterior_back_to_the_convention  (muscle_volumes.json; test_muscle_volumes, test_volume_measurements)

- ✔ unverified_value_marked_verified  (volume_measurements.json; test_muscle_volumes, test_volume_measurements)

- ✔ a_derived_value_applied  (muscle_volumes.json; test_muscle_volumes, test_volume_measurements)

- ✔ pubofemoral_without_its_wrapping_guide  (lumbar_pelvis.json; test_hip_ligament_paths, test_hip_rom)

- ✔ femoral_head_radius_32_mm  (lumbar_pelvis.json; test_hip_ligament_paths, test_hip_rom)

- ✔ iliofemoral_loses_deform  (lumbar_pelvis.json; test_hip_ligament_paths, test_hip_rom)

- ✔ invented_stiffness  (lumbar_pelvis.json; test_hip_ligament_paths, test_hip_rom)

- ✔ published_extension_range_excludes_the_rig  (lumbar_pelvis.json; test_hip_ligament_paths, test_hip_rom)

- ✔ internal_rotation_mapped_to_the_wrong_side  (lumbar_pelvis.json; test_hip_ligament_paths, test_hip_rom)

- ✔ psoas_without_the_eminence_pulley  (tendons_trunk_head.json; test_iliopsoas_itb_paths)

- ✔ iliacus_origin_back_on_the_outer_side_of_the_plate  (tendons_trunk_head.json; test_iliopsoas_itb_paths)

- ✔ trochanter_sphere_radius_40_mm  (lumbar_pelvis.json; test_iliopsoas_itb_paths)

- ✔ itb_guide_pushed_into_the_trochanter  (tendons_lower_limb.json; test_iliopsoas_itb_paths)

- ✔ obturator_externus_without_its_neck_guide  (tendons_lower_limb.json; test_deep_hip_muscles)

- ✔ piriformis_loses_its_avoid_list  (tendons_lower_limb.json; test_deep_hip_muscles)

- ✔ pectineus_insertion_moved  (tendons_lower_limb.json; test_deep_hip_muscles)

- ✔ ischial_obstacle_radius_12_mm  (lumbar_pelvis.json; test_deep_hip_muscles)

- ✔ obturator_margin_landmark_far_from_the_bone  (lumbar_pelvis.json; test_deep_hip_muscles)

- ✔ piriformis_cites_an_unknown_source  (tendons_lower_limb.json; test_deep_hip_muscles)

- ✔ tibial_proximal_obstacle_removed  (leg_foot.json; test_knee_anchors, test_anchor_debt)

- ✔ patella_obstacle_5_mm  (leg_foot.json; test_knee_anchors, test_anchor_debt)

- ✔ patellar_ligament_back_to_rigid  (leg_foot.json; test_knee_anchors, test_anchor_debt)

- ✔ tibial_collateral_anchor_displaced  (leg_foot.json; test_knee_anchors, test_anchor_debt)

- ✔ fibular_head_obstacle_removed  (leg_foot.json; test_knee_anchors, test_anchor_debt)

- ✔ rig_extension_limit_lowered_to_5_degrees  (joints.json; test_hip_rom, test_base_frozen)



**26 de 26 mutaciones detectadas, 0 sin detectar** (148 s).

### Suite completa

Suite completa en Blender: `[SUMMARY] ejecutadas=434 fallos=0 errores=0 omitidas=0` (Python puro: mismas pruebas, las de Blender se omiten). 8 pruebas nuevas de región en `tests/test_region_closure_hips_thigh.py`.

## Siguiente

Región siguiente según `docs/plan/00_plan_general.md`: tren superior y torso (CM no aplica). Antes, conviene resolver el deslizamiento de la rótula y reintentar los volúmenes medidos (Handsfield 2014 si se consigue el PDF).
