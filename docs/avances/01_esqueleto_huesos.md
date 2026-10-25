# Esqueleto y huesos

**Rama:** `main` · **Estado:** completo respecto a la referencia de 185 huesos funcionales (0 pendientes).

## Qué hay

| Nivel | Contenido | Archivos |
|---|---|---|
| Base (nivel 0) | 20 huesos neutros, congelados en un golden (`tests/golden/base_skeleton.json`); solo cambia con `freeze_base.py --update` | `config/skeleton_definition.json`, `proportions.json` |
| Nivel 1 | 181 huesos colgados de la base: mano y pie 106, columna y cabeza 26, caja torácica 25, huesos largos 16, cintura pélvica 8 | `config/anatomy/*.json` |
| Referencia | 185 huesos funcionales (183 implementados en el nivel 1 y 2 en la base) | `config/reference/human_skeleton_reference.json` |

## Lo que se ha resuelto

- Jerarquía doble: `parent` (segmento base que mueve el hueso) y `anatomical_parent` (húmero → escápula, radio y cúbito → húmero, carpo, tibia y peroné → fémur, astrágalo → tibia…).
- Coxal separado en `ilium`, `ischium` y `pubis`; `sacrum` y `coccyx` normalizados.
- **Cráneo con volumen** (bóveda paramétrica, índice cefálico 0,78); mandíbula con el pivote en el eje de las ATM.
- **Cartílago costal** como trayecto propio (verdaderas al esternón, falsas al cartílago superior, flotantes libres).
- **Anillo pélvico cerrado** (sacro–ilion–acetábulo–pubis–sínfisis) y cara auricular sin hueco.
- Todo extremo de hueso termina en otra estructura o en un hito definido (puntas de dedos, ápice del cóccix, escotadura yugular, base de la rótula).
- Todo escala linealmente con `--height` (`1.70`, `170cm`, `5ft7in`), válido de 1,50 a 2,05 m.

## Pruebas y documentos

`test_model`, `test_frames`, `test_base_frozen`, `test_anatomy`, `test_closure`, `test_connectivity`, `test_height`, `test_arm_hand`, `test_leg_foot`, `test_head_neck`, `test_lumbar_pelvis`, `test_pelvis_closure`.
Documentos: `docs/anatomia_*.md`.

## Fuentes

Medidas de partida aproximadas (no anatómicas exactas); las cifras con fuente están en los documentos de cada región. El índice cefálico sale de estudios de cabeza viva (fiabilidad media), no de cráneo seco.

## Pendiente

- Perfiles por edad (faltan tablas de proporciones por edad con fuente primaria).
- Altura objetivo exacta y longitudes por lado; detección de intercambio L/R en el validador.
- 61 anclajes antiguos a más de 12 mm de su hueso (ver `tests/test_anchor_debt.py`).
- Vértebras y huesos largos sin anchura: sus puntos se colocan a 8–11 mm del eje, no sobre la apófisis real.
