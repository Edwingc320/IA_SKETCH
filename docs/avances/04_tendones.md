# Tendones

**Rama:** `muscle-model` (no existe en `main`) · **Estado:** 86 unidades músculo-tendinosas por lado (172), de todo el cuerpo.

## Qué hay

| Archivo | Unidades por lado | Contenido |
|---|---|---|
| `tendons_trunk_head.json` | 19 | esternocleidomastoideo, trapecio (3 porciones), elevador de la escápula, romboides, serrato, masetero, temporal, pectorales, dorsal ancho, redondo mayor, recto del abdomen, psoas, ilíaco, cuadrado lumbar, iliocostal |
| `tendons_upper_limb.json` | 37 | manguito rotador, deltoides (3), bíceps (2), tríceps (3), braquial, braquiorradial, pronador, flexores y extensores del carpo, flexores y extensor de los dedos (×4), pulgar |
| `tendons_lower_limb.json` | 30 | cuádriceps (4), isquiotibiales (4), sartorio, grácil, aductores, tensor de la fascia lata, gastrocnemio (2) y sóleo, tibial anterior y posterior, peroneos, flexores y extensores de los dedos |

## Modelo

Unidad = línea **origen óseo → vías óseas → inserción ósea**, con extremos tendinosos y vientre. Guías óseas incluidas: túnel carpiano (hueso grande, tubérculos del escafoides y del trapecio), dorso de la muñeca, surco intertubercular, maléolos, sustentáculo del astrágalo y cara anterior del tobillo. Todo anclaje a menos de 12 mm del hueso.

## Lo que NO es un dato

La **longitud del tendón** es una **convención visual** declarada en los archivos (corto 10 %, medio 25 %, largo 45 % de la unidad). No se mide.

## Fuentes y fiabilidad

Apuntes y tablas (Semmelweis, Pearson, GMCH, Universidad de Wisconsin, Wikipedia, Elsevier) y varias de fiabilidad baja. Los músculos sin ninguna fuente consultada (deltoides, bíceps, tríceps, aductores, sartorio, grácil, peroneos, psoas, ilíaco…) lo dicen: **verificar en un atlas**.

## Pruebas

`test_tendons` (Python puro y Blender). Documento: `docs/tendones.md`.

## Pendiente

- Longitudes reales de tendón (con fuente) para sustituir la convención.
- Rutas con más puntos de guía (retináculos extensor y flexor del tobillo, poleas de los dedos) y envainado.
- Músculos intrínsecos de la mano y del pie, fibras medias del trapecio completas, músculos de la cara, diafragma y suelo pélvico.
