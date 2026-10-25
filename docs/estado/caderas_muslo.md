# Estado: caderas, pelvis y muslo

Plan: [../plan/30_caderas_muslo.md](../plan/30_caderas_muslo.md) · Prioridad **1** · Actualizado: 2026-10-25 · Estado general: **datos pendientes** (geometría y estructura completas).

## Por capa

| Capa | Estado | Detalle |
|---|---|---|
| Huesos | ✅ completo | pelvis cerrada, fémur con accidentes, rótula |
| Articulaciones | ✅ completo | rig `hip` con límites; ROM de extensión por revisar |
| Ligamentos | ✅ con envoltura | iliofemoral, pubofemoral e isquiofemoral con guías y sin atravesar el fémur en el barrido; sin valores mecánicos (convención declarada) |
| Tendones | 🟡 | 8 unidades en el muslo + cintilla iliotibial + 8 profundos y aductores; psoas-ilíaco, cintilla y profundos con ruta, fuentes (media o baja) y envoltura; el resto del muslo sin ruta ni fuente |
| Músculos (volumen) | 🟡 parcial | medidos (Ritsche 2025): vasto lateral y bíceps femoral en el muslo, gastrocnemios y tibial anterior en la pierna; el resto del muslo por convención; glúteos: mediano y menor medidos (Kajdi 2025, cohorte de 65 años: subestima), mayor por convención |
| Deuda de anclaje | 🟡 | 58 en el modelo (el trinquete bajó 3 con CM-5: cruzados y femororrotuliana, por las superficies de convención del fémur) |

## Lista de tareas

- [~] **CM-1** Conseguir volúmenes del muslo y la cadera con fuente de RM abierta — **parcial**: registro en `config/muscles/volume_measurements.json` (5 fuentes con DOI). Verificados: vasto lateral, una cabeza del bíceps femoral, gastrocnemio medial y lateral, tibial anterior (Ritsche 2025, adultos jóvenes), proporciones del cuádriceps (Trappe 2001) y glúteos mediano/menor (Kajdi 2025, pacientes de 65 años: no es la población de referencia). Sin encontrar: glúteo mayor, semitendinoso, semimembranoso, aductores, grácil, sartorio, TFL, psoas, ilíaco, sóleo, peroneos. Quedan abiertos Handsfield 2014, Ward 2009 y Lube 2016 (tablas inaccesibles)
- [x] **CM-2** Sustituir las clases por volúmenes medidos — aplicados los 5 verificados de Ritsche 2025 (vasto lateral 636,5; bíceps femoral 197,4 [cabeza larga, hipótesis]; gastrocnemio medial 224,7 y lateral 112,6; tibial anterior 119,4 cm³), con altura de referencia 1,75 m **asumida** porque la fuente no publica la de los sujetos. Recto femoral, vasto intermedio y medial siguen por convención (sus cifras son derivadas); el resto del muslo, igual
- [x] **CM-3** Volumen de los glúteos — mediano 339,1 y menor 92,15 cm³ (media simple de mujeres y hombres de Kajdi 2025; cohorte de 65 años con dolor trocantérico: **limitación declarada**, probablemente subestima; altura de referencia 1,75 m asumida); glúteo mayor por convención `muy_grande` (700 cm³, sin dato medido; probablemente se queda corto). Eje del vientre: centroide de los orígenes → inserción; sección aplanada (aspecto 3,0 / 2,5 / 2,5) es convención de forma
- [x] **CM-4** Puntos de tensado de los ligamentos de la cadera — guías de envoltura (`via`), obstáculos de cabeza y cuello del fémur, ligamentos deformados por la armadura en Blender; propiedades mecánicas como convención paramétrica declarada (ver `docs/avances/03_ligamentos.md`)
- [x] **CM-5** Rutas completas del psoas-ilíaco y la cintilla iliotibial — eminencia iliopúbica como polea, guías sobre trocánter mayor y epicóndilo lateral, obstáculos del fémur y la rama del pubis, lámina del ilion; barrido de 22 poses sin penetración en el modelo y en Blender (ver `docs/avances/04_tendones.md`)
- [x] **CM-6** Músculos que faltan (aductor corto, pectíneo, obturadores, piriforme, gemelos, cuadrado femoral) — 8 unidades por lado con hitos nuevos (`pectineal_crest`, `obturator_margin`, `trochanteric_fossa`, `intertrochanteric_crest`), guías de envoltura en la escotadura ciática mayor y menor, el borde del agujero obturador y el cuello del fémur, y barrido de 22 poses sin penetración (ver `docs/avances/04_tendones.md`)
- [ ] **CM-7** ROM de la cadera revisado
- [ ] **CM-8** Reducir la deuda de anclaje del muslo
- [ ] **CM-9** Cierre de la región

## Registro

| Fecha | Cambio |
|---|---|
| 2026-10-25 | Plan y estado creados. Intento de obtener Handsfield 2014 y Ward 2009: sin acceso (de pago / servidor caído). |
| 2026-10-25 | CM-1 parcial: `volume_measurements.json` + `tests/test_volume_measurements.py` (9 pruebas, 4 mutaciones detectadas). Hallazgo: las clases de convención sobrestiman lo medido (tibial anterior 350 frente a 119,4 cm³). Cifras derivadas (RF, VI, VM) y la de Takahashi (aductor mayor) quedan marcadas como no verificadas. |
| 2026-10-25 | CM-2: 5 volúmenes medidos aplicados a `muscle_volumes.json` (fuente `ritsche_2025`, referencia 1,75 m asumida). Las convenciones de la pierna sobrestimaban: tibial anterior 350 → 119,4 cm³. 3 mutaciones detectadas. |
| 2026-10-25 | CM-3: `muscle_volumes` admite músculos de la capa `muscles` (glúteos) con eje, hueso (`ilium`) y región propios; 6 volúmenes nuevos (3 por lado). Registro: medias derivadas `applied_in_model`. 5 mutaciones detectadas. |
| 2026-10-25 | CM-4: `via`, `bone_surfaces`, `mechanics` y `deform` en los ligamentos; módulo `ligament_paths`; `bone_distance` acepta las superficies. Extremos del pubofemoral e isquiofemoral movidos del eje del cuello (dentro del hueso) a su superficie. Barrido de 13 poses × 3 alturas sin penetración. Nota: el rig permite extensión de 15° (límite de la base) mientras `articulations` documenta 10° (StatPearls): se revisa en CM-7. |

| 2026-10-25 | CM-5: unidad nueva `iliotibial_tract`; `via`, `deform` y `avoid` en psoas mayor, ilíaco y tensor de la fascia lata; hito `iliopubic_eminence`; superficies `femoral_greater_trochanter`, `femoral_shaft`, `femoral_lateral_condyle` y `pubic_ramus` (convención, solo el cóndilo tiene cifra publicada, de fiabilidad baja); tubos de tendón deformables en Blender; `validate_tendon_poses`. Origen del ilíaco desplazado 10,8 mm a la cara interna de la lámina del ilion. 4 mutaciones en el JSON y 10 en las pruebas. |
| 2026-10-25 | CM-6: 8 unidades nuevas (piriforme, obturador interno y externo, gemelos superior e inferior, cuadrado femoral, pectíneo, aductor corto), 4 hitos, obstáculo `ischial_ramus` (convención) y la lámina del sacro en el barrido. Hallazgo: la mezcla lineal de la armadura desvía el anillo de la unión miotendinosa de la recta exacta (hasta ≈ 23 mm); los nodos son exactos. Las pruebas de Blender de CM-5 y CM-6 comprueban ahora los nodos y acotan esa desviación. 13 pruebas puras y 6 de Blender nuevas; 12 mutaciones. |
