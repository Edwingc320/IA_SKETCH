# Plan: caderas, pelvis y muslo (prioridad 1)

Estado de partida: huesos, articulaciones y ligamentos completos; músculos del muslo con volumen **por convención**; tendones con fuentes débiles. Estado detallado: [../estado/caderas_muslo.md](../estado/caderas_muslo.md).

## Qué hay hoy

| Capa | Contenido |
|---|---|
| Huesos | sacro, cóccix, ilion, isquion y pubis separados; anillo pélvico cerrado; fémur (cabeza, trocánter mayor y menor, tuberosidad glútea, epicóndilos) y rótula |
| Articulaciones | coxofemoral (rig `hip`: flexión −15…120°, abducción −30…45°, axial −40…45°), sacroilíacas, sínfisis del pubis, sacrococcígea, lumbosacra, tibiofemoral y femororrotuliana |
| Ligamentos | iliofemoral, pubofemoral, isquiofemoral, iliolumbar, sacrotuberoso, sacroespinoso, sacroilíacos (3), pubianos (2), sacrococcígeos, cruzados, colaterales, rotuliano |
| Tendones y músculos | glúteos mayor, mediano y menor (capa anterior); cuádriceps (4), isquiotibiales (4), sartorio, grácil, aductores largo y mayor, tensor de la fascia lata, psoas, ilíaco |
| Volúmenes | convención visual en todo el muslo (clases 40/150/350/700 cm³); los glúteos aún sin volumen |

## Huecos concretos

1. **Volúmenes musculares medidos** (eje 1): ninguno en la cadera ni el muslo. Faltan glúteos (3), cuádriceps (4), isquiotibiales (4), sartorio, grácil, aductores (largo, corto, mayor), psoas, ilíaco, tensor de la fascia lata, pectíneo, obturadores, piriforme.
2. **Músculos no modelados**: aductor corto, pectíneo, obturador interno y externo, gemelos, piriforme, cuadrado femoral.
3. **Ligamentos sin puntos de tensado**: el iliofemoral rodea el cuello del fémur en flexión y extensión; el pubofemoral y el isquiofemoral envuelven el cuello. Hoy son segmentos rectos.
4. **Tendones con fuente débil o ninguna** en el muslo: sartorio, grácil, aductores, isquiotibiales, cuádriceps (4 sin fuente y 4 con fuente baja).
5. **Rutas de tendón**: el psoas-ilíaco gira sobre la rama púbica y la cápsula (guía ausente); la cintilla iliotibial no tiene vía intermedia sobre el trocánter mayor.
6. **ROM**: la extensión de cadera del modelo (15°) está entre 10° (StatPearls) y valores mayores en otras referencias; faltan límites coherentes de las rotaciones con la flexión de cadera. *CM-7 (2026-10-27): auditado; la extensión se mantiene en 15° (rango entre fuentes 10–30, media medida 17); queda pendiente la dependencia de las rotaciones con la flexión.*
7. **Deuda de anclaje del muslo**: 4 anclajes antiguos a más de 12 mm (ver `tests/test_anchor_debt.py`).

## Pasos

| ID | Paso | Entrega | Criterio de aceptación |
|---|---|---|---|
| CM-1 | Conseguir volúmenes del muslo y la cadera con fuente de RM abierta | tabla en `docs/avances/05_musculos.md` con valor, unidades, altura y masa de los sujetos | cada valor con DOI y fiabilidad; los no encontrados quedan como convención |
| CM-2 | Sustituir las clases por volúmenes medidos | `muscle_volumes.json` con `kind: medido` | prueba de que ninguno medido tiene clase y todos citan fuente |
| CM-3 | Volumen de los glúteos (hoy sin él) | tres unidades más en `muscle_volumes.json` | malla de volumen exacto, a < 12 mm |
| CM-4 (hecho) | Puntos de tensado de los ligamentos de la cadera | `waypoints` en los ligamentos (nuevo campo, con prueba) | el ligamento no atraviesa el cuello femoral en flexión de 0 a 120° |
| CM-5 (hecho) | Rutas completas del psoas-ilíaco y de la cintilla iliotibial | vías en `tendons_lower_limb.json` | cada vía a < 12 mm del hueso; longitud de la ruta crece con la flexión |
| CM-6 (hecho) | Músculos que faltan (aductor corto, pectíneo, obturadores, piriforme, cuadrado femoral) | unidades nuevas con hitos óseos | un origen y una inserción sobre hito; fuente o «verificar» |
| CM-7 (hecho) | ROM de la cadera revisado | rangos con fuente y límites en Blender | tabla de discrepancias resuelta; golden actualizado si cambia la base |
| CM-8 (hecho) | Reducir la deuda de anclaje del muslo | `KNOWN_DEBT` sin entradas del muslo | el trinquete baja de 61 |
| CM-9 (hecho) | Cierre de la región | actualizar `docs/estado/caderas_muslo.md` y `docs/avances/` | suite completa en verde y mutaciones detectadas |

## Investigación (eje 1 a 4), qué buscar y dónde

- **Volúmenes y arquitectura**: Handsfield 2014 (J Biomech 47:631–638; 35 músculos del miembro inferior por RM; relación con talla y masa); Ward 2009 (Clin Orthop Relat Res 467:1074; 27 músculos de 21 cadáveres: longitud de fibra y área de sección fisiológica); la base de 70 músculos de 2025 (J Appl Physiol, DOI 10.1152/japplphysiol.00772.2025). Ninguno de los tres ha sido leído hasta ahora: son **candidatos**. Rutas alternativas: versiones abiertas (PMC, repositorios institucionales, preprints) o los conjuntos de datos suplementarios.
- **Rutas y guías de tendón**: el modelo de miembro inferior de Arnold 2010 (puntos de paso y envolventes de los músculos), que es la referencia estándar para waypoints.
- **Ligamentos**: StatPearls y atlas de acceso abierto para el iliofemoral (haces superior e inferior) y su comportamiento en extensión.
- **ROM de cadera**: AAOS y los estudios de goniometría activa; separar activo y pasivo.

## Pruebas nuevas previstas

- Cada volumen medido cita fuente y reproduce el cm³ de la tabla (después de escalar a la altura del sujeto).
- Los ligamentos con puntos intermedios mantienen todos sus puntos a < 12 mm y su longitud no baja de la distancia recta.
- Mutación: mover un punto de tensado dentro del hueso debe fallar.

## Riesgos de la región

- Sin acceso a los artículos, el volumen de la pierna seguirá por convención: **no se debe presentar como medido**.
- Los puntos de tensado exigen un modelo de colisión simple (cilindro o esfera del cuello femoral) que hoy no existe.

## Hallazgos metodológicos de CM-7

- El rig y el registro «publicado» significan cosas distintas: el rig es un **techo** (lo máximo que la articulación puede dar) y StatPearls da un valor **típico** activo. Comparar uno con otro como si fueran lo mismo produce una falsa discrepancia; por eso ahora hay `range_deg` (rango entre fuentes) y `rig` (a qué límite corresponde) y una validación (`ART_ROM_RIG_OUTSIDE`).
- Bajar la extensión a 10° habría **reducido** el rango validado sin respaldo (10 es el mínimo de las fuentes), habría exigido actualizar el golden y las restricciones Limit Rotation, y habría dejado fuera la media medida (17°). Se decidió mantener 15°. Los barridos también se prueban con 5° y 10° de extensión, de modo que el cambio sería seguro si algún día se decide.
- Los signos del rig se comprobaron con la cinemática directa: axial positivo = rotación interna.
- Las fuentes nuevas se leyeron en resúmenes de búsqueda; la hoja que atribuye cifras a la AAOS es secundaria (fiabilidad baja): conviene contrastar con la guía de la AAOS.

## Hallazgos de CM-8

- Las tres superficies nuevas (tibia proximal, rótula y cabeza del peroné) sanan cinco anclajes antiguos, pero son **convención de obstáculo**: el trinquete baja porque el hueso gana cuerpo, no porque se hayan movido los puntos. Dos de ellas tienen una cifra publicada de apoyo (grosor de la rótula 19–22 mm; profundidad de la tibia proximal 35–47 mm) y la de la cabeza del peroné no.
- Los obstáculos de la tibia **no** se usan en los `avoid` de los ligamentos de la rodilla: varios de sus anclajes (colateral tibial, cruzados) quedan dentro del cuerpo de la tibia proximal por construcción. Solo los colaterales evitan el fémur.
- El **ligamento rotuliano** necesita el deslizamiento de la rótula (hoy la rótula es rígida al fémur): sin él, el ligamento se alarga 3× y atraviesa el fémur a flexiones altas. Queda como paso pendiente para la región (después de CM-9) y la prueba lo mide.
- Una auditoría completa de anclajes de la región debe excluir lo que sigue siendo deuda ajena (el tobillo), pero comprobar que sigue en el trinquete.

## Cierre (CM-9, 2026-10-27)

Región cerrada con limitaciones: ver [../estado/caderas_muslo_cierre.md](../estado/caderas_muslo_cierre.md). Lo que queda abierto de esta región, por orden: deslizamiento de la rótula (el ligamento rotuliano no mantiene su longitud ni evita el fémur por encima de ~100° de flexión); volúmenes medidos de los músculos sin dato (CM-1 sigue parcial); contrastar las fuentes leídas en resúmenes con los artículos y con un atlas; envolturas por armadura para el resto de ligamentos y tendones que cruzan una articulación; origen del psoas en L1–L5.

## CM-10 (2026-10-28): deslizamiento de la rótula

Resuelve la limitación pendiente de CM-8/CM-9. Ver [../estado/caderas_muslo_cierre.md](../estado/caderas_muslo_cierre.md#actualización-cm-10-2026-10-28-deslizamiento-de-la-rótula).
