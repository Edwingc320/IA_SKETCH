# Reconstrucción anatómica del esqueleto central (`cp.*`) — diagnóstico y plan

Estado: **etapa B (columna) en curso**. Alcance de esta fase: cráneo y mandíbula, columna C1–L5, sacro, caja torácica y esternón, pelvis y fémures hasta los cóndilos. Sin brazos, manos, tibias, peronés, pies, músculos ni piel.

## Diagnóstico (2026-10-29, auditoría previa a los cambios)

Tres capas conviven y se confunden visualmente:

1. **Nivel 1** (`config/anatomy/*.json`, `anatomy.py`): huesos como líneas y contornos. Las costillas son 12 polilíneas de 5 puntos (con espejo) y el esternón una sola pieza; con los músculos encima dan las «costillas salientes».
2. **`BM_*`** (`bone_meshes.py`): solo fémur y pelvis, para hitos y ligamentos. No se toca.
3. **`cp.*`** (`cp_skeleton.py`, `cp_axial.py`, `cp_skullbox.py`, `cp_refine.py`): el esqueleto paramétrico, origen de `output/cp_skeleton.blend`.

| Región (`cp.*`) | Defecto | Causa |
|---|---|---|
| Costillas y esternón | no existen | nunca se construyeron |
| Columna | cuerpos cilíndricos idénticos con palitos | `tube()` de sección elíptica y `_arch` con tubos finos; la curva sale de doblar una pila recta, no de cuerpos con cuña; una misma plantilla escalada |
| Sacro | cuña lisa sin forámenes ni alas | un solo `tube()` aplanado |
| Pelvis | coherente pero con costuras | piezas solapadas (ala, copa, tubos), no una superficie continua |
| Fémur | **los cóndilos flotan ~5 cm bajo la diáfisis** | la diáfisis acaba en −0,215 H y los cóndilos están en −0,243 H sin puente |
| Cráneo | bloque estilizado, no ovoide | silueta cuadrada en los hombros |

No hay problema de coordenadas, transformaciones ni reglas de ensamblaje (orígenes, cadena de emparentamiento, escala y simetría están probados). El problema es de **primitivas y topología**, y de **ausencia** del tórax.

Reutilizable: cadena de emparentamiento y `cp_resize`, marcos por tangente, `sweep_box`, jaula + Subdivision Surface (`cp_skullbox`), validación de manifold, comparador por regiones y los 69 hitos del nivel 1.

## Procedimiento real

- Regenerar: `blender -b --python scripts\cp_skeleton.py -- --height 1.75 --out output\cp_skeleton.blend`
- Esqueleto óseo actual (por defecto): `blender -b --factory-startup --python tests/run_tests.py`
- Modelo viejo: `... --python tests/run_tests.py -- --suite legacy`; todo: `-- --suite all`; módulos concretos: `-- --only test_cp_skeleton`.

## Plan por etapas (una región bien construida y comprobada antes de la siguiente)

| Etapa | Región | Estrategia propia |
|---|---|---|
| A | Estructura central | escala H, +X izquierda / −Y delante / +Z arriba, línea central y curvas sagitales; referencias por nivel (`config/cp/spine.json`) |
| **B** | Columna C1–L5 | cuerpos por lofts de sección en riñón con cintura y cuña; arco neural como barrido en U (foramen visible); apófisis espinosa y transversas en láminas; discos lenticulares; rasgos propios cervical / torácica / lumbar |
| C | Caja torácica | costillas como barridos curvos de sección aplanada con torsión por región; cartílago costal; esternón (manubrio, cuerpo, xifoides) |
| D | Pelvis y sacro | sacro con alas y forámenes; coxal unificado (ilion, isquion, pubis) |
| E | Fémures | cabeza, cuello, trocánteres, diáfisis y **cóndilos conectados** |
| F | Cráneo y mandíbula | silueta ovoide, arcos y mandíbula afinados |

## Convenciones declaradas

Las dimensiones por nivel de `config/cp/spine.json` son **aproximadas** (orden de magnitud de la anatomía descriptiva, interpoladas entre un nivel inicial y uno final de cada región); no están medidas en este proyecto ni proceden de una fuente numérica citada. Los largos de segmento siguen mandando los datos antropométricos (Drillis y Contini) y la forma, la imagen de referencia.
