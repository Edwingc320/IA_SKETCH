# Capa de tendones (rama `muscle-model`)

Capa **muscular** sobre el modelo óseo; no existe en `main`. Cubre **todo el cuerpo** con las unidades músculo-tendinosas principales de cada región: **80 por lado** (160 en total).

| Archivo | Unidades por lado | Contenido |
|---|---|---|
| `config/muscles/tendons_trunk_head.json` | 16 | esternocleidomastoideo, trapecio superior, elevador de la escápula, romboides, serrato anterior, masetero, temporal, pectoral mayor, dorsal ancho, redondo mayor, recto del abdomen, psoas, ilíaco, cuadrado lumbar, iliocostal |
| `config/muscles/tendons_upper_limb.json` | 36 | manguito rotador (4), deltoides (3 haces), bíceps (2 cabezas), coracobraquial, tríceps (2), braquial, braquiorradial, pronador redondo, flexores y extensores del carpo, flexor superficial y profundo y extensor de los dedos (×4 dedos), flexor largo del pulgar, abductor largo y extensores del pulgar |
| `config/muscles/tendons_lower_limb.json` | 28 | cuádriceps (4), sartorio, grácil, isquiotibiales (3), aductores largo y mayor, tensor de la fascia lata, gastrocnemio y sóleo (tendón calcáneo), tibial anterior y posterior, peroneos largo y corto, flexor largo del dedo gordo y de los dedos (×4), extensor largo del dedo gordo y de los dedos (×4) |

## Cómo se modela

Una **unidad músculo-tendinosa** es una línea **origen óseo → vías óseas → inserción ósea**. Las vías son los puntos de hueso que la guían: túnel carpiano (hueso grande, tubérculos del escafoides y del trapecio), dorso de la muñeca, surco intertubercular, maléolos, sustentáculo del astrágalo y cara anterior del tobillo. Los **extremos tendinosos** son el tramo de la línea junto al origen y/o la inserción; el resto es el **vientre muscular** (siempre ≥ 20 % de la unidad).

- Todo anclaje (origen, vías, inserción) nace de un **hito óseo** del modelo óseo o de un punto de un hueso, y queda a **menos de 12 mm de su superficie** (dentro del volumen del cráneo cuenta como hueso).
- En Blender: tubo claro grueso por tendón (`TEN_origin_*`, `TEN_insertion_*`) y tubo rojo fino por vientre (`TEN_belly_*`), emparentados al hueso de su extremo; al mover la pierna, el tendón calcáneo sigue al calcáneo y el vientre se queda en el fémur (probado). Son datos: el tubo no se estira todavía.

## La única cifra que no es anatómica

La **longitud del tendón** no se mide en este modelo. Se usa una **convención visual** de tres clases declarada en cada archivo (`tendon_classes`): **corto 10 %, medio 25 %, largo 45 %** de la longitud de la unidad. No es un dato anatómico y no debe citarse como tal; si se consigue la longitud real de un tendón, se sustituye por su fuente.

## Fuentes y límites

Las fuentes son apuntes y tablas ([Semmelweis](https://semmelweis.hu/anatomia/files/2021/09/20211014_DrKatz_en.pdf), [Pearson](https://www.pearson.com/channels/anp/study-guides/muscles-of-the-forearm-origins-insertions-and), [GMCH](https://www.gmch.gov.in/sites/default/files/documents/Extensor%20compartment%20of%20forearmphysio.pdf), [Universidad de Wisconsin](https://wisc.pb.unizin.org/app/uploads/sites/520/2020/09/Complete-Chart-Muscles-Acting-on-the-Pectoral-Girdle-and-Shoulder.pdf), [Wikipedia](https://en.wikipedia.org/wiki/Greater_tubercle), [Elsevier](https://www.elsevier.com/resources/anatomy/muscular-system/muscles-of-lower-limb/flexor-digitorum-longus/19278)) y varias de fiabilidad baja (tarjetas de estudio y resúmenes). **Los músculos sin ninguna fuente consultada (deltoides, bíceps, tríceps, braquial, aductores, sartorio, grácil, peroneos, psoas, ilíaco…) lo dicen en su nota y quedan «verificar en un atlas».** Una prueba lo exige.

No incluido (falta fuente o geometría ósea): fibras medias e inferiores del trapecio, vientres con varios orígenes (dorsal ancho, glúteos en este archivo —están en `docs/musculos_gluteos.md`—), músculos intrínsecos de la mano y del pie, músculos de la cara salvo masetero y temporal, diafragma y músculos del suelo pélvico. La cintilla iliotibial y las aponeurosis son fascia: se anclan al hueso donde terminan (tubérculo de Gerdy, cresta ilíaca).
