# Plan: tren superior (hombro, brazo, antebrazo y mano), prioridad 2

Estado de partida: es la región con **mejor dato**: volúmenes medidos de la mayoría de los músculos (Holzbaur 2007). Estado detallado: [../estado/tren_superior.md](../estado/tren_superior.md).

## Qué hay hoy

| Parte | Huesos | Articulaciones | Ligamentos | Tendones | Volumen |
|---|---|---|---|---|---|
| Hombro | clavícula (base), escápula con borde lateral y coracoides | esternoclavicular, acromioclavicular, glenohumeral, escapulotorácica (sin ligamentos) | coracoclaviculares, coracoacromial, glenohumerales (4), coracohumeral, esternoclaviculares | manguito rotador, deltoides (3 haces) | rotadores y deltoides medidos |
| Brazo | húmero | (codo: ver antebrazo) | colaterales del codo | bíceps (2), tríceps (3), braquial, coracobraquial | medido |
| Antebrazo | radio, cúbito | humerocubital, radiocubitales, radiocarpiana | anular, membrana interósea, TFCC, colaterales | flexores y extensores del carpo, pronador, braquiorradial | medido |
| Mano | 8 carpianos, 5 metacarpianos, 14 falanges | mediocarpiana, pisopiramidal, carpometacarpianas, MCF, IFP, IFD | carpometacarpianos, transversos profundos, colaterales y placas | flexores superficial y profundo, extensor de los dedos (×4), pulgar | **sin volumen** de los flexores y extensores de los dedos |

## Huecos concretos

1. **Mano**: sin músculos intrínsecos (lumbricales, interóseos, tenares, hipotenares), sin poleas de los flexores y sin capuchón extensor como estructura. Falta el volumen de los músculos extrínsecos de los dedos (el estudio de Holzbaur los da, pero el cuadro extraído tiene columnas desplazadas y no se usaron: **hay que verificar** FDS, FDP, FPL, APL, EPB, EPL, EDC, EDM, EIP).
2. **Valores a verificar con el artículo**: braquial y bíceps salen idénticos (143,7 cm³).
3. **Deuda de anclaje del antebrazo**: 10 anclajes antiguos (codo, TFCC, radiocubital distal) y 5 de la mano (articulación mediocarpiana, pisopiramidal).
4. **Tendones del brazo sin fuente** (5) y del antebrazo (6): bíceps, tríceps, braquial, braquiorradial.
5. **Ligamentos sin puntos de tensado**: el anular rodea la cabeza del radio; el colateral cubital pasa sobre la tróclea; los colaterales de los dedos rodean la cabeza del hueso.
6. **ROM**: extensión de muñeca 60° frente a 66–70°; protracción esternoclavicular 45° frente a 35°; la desviación cubital publicada (28–30°) está recortada en las propuestas ±20°.
7. **Capa de poses**: dedos y muñeca solo se mueven como un bloque; los dof por falange no existen en el rig.

## Pasos

| ID | Paso | Entrega | Criterio de aceptación |
|---|---|---|---|
| TS-1 | Verificar la tabla de Holzbaur con el artículo y completar los extrínsecos de los dedos | `muscle_volumes.json` con FDS, FDP, FPL, APL, EPB, EPL, EDC, EDM, EIP medidos | suma de los 32 músculos ≈ 2554 cm³ (media del estudio) a su altura |
| TS-2 | Repartos por haces con fuente | volúmenes de las cabezas del bíceps y el tríceps y las porciones del deltoides si se encuentran publicados | reparto citado, o se mantiene el reparto en partes iguales y declarado |
| TS-3 | Poleas del flexor y capuchón extensor | puntos de guía en `tendons_upper_limb.json` (A1–A5, C1–C3) | cada guía a < 12 mm de la falange; el tendón no atraviesa el hueso |
| TS-4 | Músculos intrínsecos de la mano | unidades nuevas con hitos en metacarpianos y falanges | origen e inserción sobre hito; fuente o «verificar» |
| TS-5 | Puntos de tensado del anular, colaterales y TFCC | `waypoints` en esos ligamentos | longitud constante dentro del rango de pronosupinación |
| TS-6 | ROM: resolver las discrepancias | rangos con fuente; golden actualizado si cambia | tabla de decisiones en `docs/avances/02_articulaciones.md` |
| TS-7 | Deuda de anclaje (antebrazo y mano) | `KNOWN_DEBT` sin esas entradas | el trinquete baja de 61 |
| TS-8 | Cierre | estado y avances actualizados | suite en verde |

## Investigación

- **Volúmenes**: Holzbaur 2007 (ya extraído; verificar el cuadro y completar los extrínsecos) y trabajos de RM de la mano y el antebrazo para los intrínsecos.
- **Rutas y poleas**: atlas y estudios de anatomía de la mano (poleas anulares y cruciformes); modelos del miembro superior (Holzbaur 2005).
- **ROM**: AAOS, goniometría activa (muñeca 74–80° / 66–70°), ritmo escapulohumeral 2:1.

## Pruebas nuevas previstas

- La suma de los volúmenes medidos del estudio reproduce su total (tolerancia declarada).
- Cada polea de tendón a < 12 mm de la falange; mutación: sacar una polea del hueso debe fallar.
- Los intrínsecos de la mano no cruzan el hueso (distancia mínima de la poligonal al hueso > 0).
