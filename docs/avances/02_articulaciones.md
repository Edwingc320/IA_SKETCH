# Articulaciones

**Rama:** `main` · **Estado:** completa.

## Qué hay

| Tipo | Cantidad | Dónde |
|---|---|---|
| Articulaciones de la base (rig) | 19, con 47 grados de libertad y límites en grados | `config/joints.json` |
| Articulaciones naturales independientes (datos para poses) | 265 (contando ambos lados) | `config/articulations/*.json` |

Naturales por región: tórax y hombro 87, pierna y pie 56, brazo y mano 50, columna 46 (cigapofisarias), pelvis y lumbar 11, cabeza y cuello 9, tarso 6 (intercuneiformes 1-2 y 2-3 y cuneocuboidea, por lado).
Solo 18 de las 265 se mueven hoy con una articulación de la base (`rig_driver`); el resto son datos con su rango y su fuente.

## Límites de rotación (Limit Rotation)

- Una restricción *Limit Rotation* local por articulación, con el orden Euler de sus grados de libertad (el primero se aplica primero) y los ejes sin grado de libertad bloqueados a 0.
- Pivote exactamente en la cabeza del hueso hijo en las 19 articulaciones.
- Cambios deliberados de la base: codo `[pronation, flexion]`, pronación ±80°; cadera extensión 15°.
- **Limitación honesta:** la rotación axial de la rodilla solo con flexión se exige en la validación de la pose, no en Blender (un driver que lee el propio hueso crea un ciclo de dependencias y es no determinista).
- No hay límites de rig para la ATM ni las intervertebrales: requieren la capa de poses del nivel 1 (viable, no construida).

## Rangos publicados (resumen)

Codo flexión 140–150°, pronosupinación 80–90° por lado; muñeca flexión 74–80°, extensión 66–70°, desviación radial 19–20° y cubital 28–30°; cadera flexión 120°, extensión 10–15° según la fuente; rodilla flexión 135–140°, rotación 25° interna y 18° externa a 30–40° de flexión; tobillo dorsiflexión 20–40°, flexión plantar 50°; hombro con ritmo escapulohumeral 2:1. Detalle y fuentes: `docs/articulaciones_limites_pivotes.md` y los `docs/anatomia_*.md`. Donde las fuentes no dan cifra, el rango queda vacío (`no_numeric_source`).

## Pruebas

`test_articulations`, `test_rig_limits`, `test_connectivity`, `test_spine_ligaments` (facetarias), `test_hand_foot_ligaments` (tarso).

## Pendiente

- Discrepancias a decidir (exigen actualizar el golden): protracción esternoclavicular del modelo 45° frente a 35° publicados; extensión de muñeca 60° frente a 66–70°.
- Capa extra de articulaciones para animación: FK genérica del nivel 1, reparto del movimiento y ATM e intervertebrales.
