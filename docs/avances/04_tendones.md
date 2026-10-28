# Tendones

**Rama:** `muscle-model` (no existe en `main`) · **Estado:** 95 unidades músculo-tendinosas por lado (190), de todo el cuerpo.

## Qué hay

| Archivo | Unidades por lado | Contenido |
|---|---|---|
| `tendons_trunk_head.json` | 19 | esternocleidomastoideo, trapecio (3 porciones), elevador de la escápula, romboides, serrato, masetero, temporal, pectorales, dorsal ancho, redondo mayor, recto del abdomen, psoas, ilíaco, cuadrado lumbar, iliocostal |
| `tendons_upper_limb.json` | 37 | manguito rotador, deltoides (3), bíceps (2), tríceps (3), braquial, braquiorradial, pronador, flexores y extensores del carpo, flexores y extensor de los dedos (×4), pulgar |
| `tendons_lower_limb.json` | 39 | cuádriceps (4), isquiotibiales (4), sartorio, grácil, aductores (largo, corto y mayor), pectíneo, piriforme, obturadores (2), gemelos (2), cuadrado femoral, tensor de la fascia lata y cintilla iliotibial, gastrocnemio (2) y sóleo, tibial anterior y posterior, peroneos, flexores y extensores de los dedos |

## Modelo

Unidad = línea **origen óseo → vías óseas → inserción ósea**, con extremos tendinosos y vientre. Guías óseas incluidas: túnel carpiano (hueso grande, tubérculos del escafoides y del trapecio), dorso de la muñeca, surco intertubercular, maléolos, sustentáculo del astrágalo y cara anterior del tobillo. Todo anclaje a menos de 12 mm del hueso.

## Rutas con envoltura (CM-5)

Cuatro unidades llevan guías de envoltura y, en Blender, tubos deformados por la armadura (cada anillo mezcla linealmente los huesos de los dos sitios que lo rodean): **psoas mayor** y **ilíaco** (polea en la nueva eminencia iliopúbica → trocánter menor), **cintilla iliotibial** (nueva; cresta ilíaca → guía sobre el trocánter mayor → guía sobre el epicóndilo lateral → tubérculo de Gerdy) y **tensor de la fascia lata** (mismas guías). Cada unidad dice qué superficies de obstáculo evita (`avoid`: cabeza, cuello, trocánter mayor, diáfisis y cóndilo lateral del fémur, rama del pubis; **convención**, ver `docs/avances/03_ligamentos.md`) y la lámina del ilion no puede cortarse. Barrido de 22 poses (las 13 de cadera + rodilla hasta 135° sola y combinada): margen mínimo ≈ 1,6 mm a 1,75 m, ninguna penetración a 1,50, 1,75 y 2,05 m, en el modelo y en el Blender evaluado.

Límites declarados:
- El origen del psoas sigue en L2 (la especificación pide L1–L5; el cuerpo vertebral no tiene anchura y el rango T12–L5 no se confirmó en las fuentes consultadas).
- El hito `iliac_fossa.L` queda 9,8 mm por fuera de la lámina del ilion: el origen del ilíaco se desplaza 10,8 mm hacia la cara interna para que la ruta no la atraviese; el hito sigue siendo deuda.
- La guía del epicóndilo **no** es necesaria para evitar el cóndilo (sin ella la poligonal tampoco penetra); se mantiene porque la especificación pide el paso por el epicóndilo, y una prueba detecta una guía metida en el cóndilo.
- El paso de la cintilla sobre el trocánter mayor lo pide la especificación; las fuentes consultadas no lo confirman (verificar).
- La eminencia iliopúbica y todas las guías son posiciones aproximadas sobre un hueso de líneas; la rodilla no mueve ningún obstáculo de la tibia (solo Gerdy viaja con ella).

## Músculos profundos de la cadera y aductores (CM-6)

Ocho unidades nuevas por lado, todas con envoltura (`deform`, `avoid`) y tubos deformados en Blender: **piriforme** (masa lateral del sacro → guía en la escotadura ciática mayor → borde superior del trocánter mayor), **obturador interno** (borde del agujero obturador, cara interna → guía en la escotadura ciática menor, donde el tendón gira ~90° sobre el isquion → cara medial del trocánter mayor), **obturador externo** (cara externa del borde obturador → guía bajo el acetábulo por fuera del isquion → guía en la cara posteroinferior del cuello del fémur → fosa trocantérica), **gemelos superior** (espina isquiática) **e inferior** (tuberosidad isquiática) hacia la misma zona, **cuadrado femoral** (tuberosidad isquiática → cresta intertrocantérea), **pectíneo** (pecten del pubis → línea pectínea, a 6 cm bajo el trocánter menor) y **aductor corto** (cuerpo del pubis → línea áspera proximal). Hitos nuevos: `pectineal_crest`, `obturator_margin`, `trochanteric_fossa`, `intertrochanteric_crest`; obstáculo nuevo: `ischial_ramus` (cápsula de 5 mm, **convención** sin cifra).

Barrido de 22 poses a 1,50, 1,75 y 2,05 m, ambos lados: ninguna penetración (margen mínimo ≈ 0,65 mm en el obturador interno junto al isquion; el obturador externo bajo el cuello ≈ 0,9 mm), y ni el ilion ni el sacro se cortan. Las fuentes (todas de fiabilidad media o baja, leídas en resúmenes de búsqueda) discrepan en: la inserción del cuadrado femoral (cresta frente a línea o tubérculo cuadrado), la del obturador externo (fosa frente a cuello), si los gemelos se insertan en el tendón del obturador interno o directamente, y la inserción del aductor corto. El obturador interno inserta hoy en la fosa trocantérica con un desplazamiento de 4 mm (la fuente dice «cara medial del trocánter, sobre la fosa»).

**Límite de la visualización en Blender (importante).** Los tubos deformados mezclan linealmente las poses de los huesos de los dos sitios que rodean a cada anillo. En los nodos eso es exacto (los anillos de los nodos coinciden con la cinemática directa a 0,1 mm y la poligonal de nodos no atraviesa nada), pero **el anillo de la unión miotendinosa, que cae dentro de un tramo entre dos huesos que giran entre sí, se desvía de la recta exacta** (efecto «caramelo» de la mezcla lineal): hasta ≈ 23 mm en el obturador interno a 120° de flexión con aducción (la prueba fija un máximo de 30 mm). Es un defecto visual del tubo entre ese anillo y los nodos, no del modelo de datos (que es la recta entre nodos). Las pruebas de penetración usan la poligonal de nodos.

## Lo que NO es un dato

La **longitud del tendón** es una **convención visual** declarada en los archivos (corto 10 %, medio 25 %, largo 45 % de la unidad). No se mide.

## Fuentes y fiabilidad

Apuntes y tablas (Semmelweis, Pearson, GMCH, Universidad de Wisconsin, Wikipedia, Elsevier) y varias de fiabilidad baja. Los músculos sin ninguna fuente consultada (deltoides, bíceps, tríceps, aductores, sartorio, grácil, peroneos, psoas, ilíaco…) lo dicen: **verificar en un atlas**.

## Pruebas

`test_tendons` (Python puro y Blender), `test_iliopsoas_itb_paths` (rutas, barrido, mutaciones), `test_iliopsoas_itb_blender` (FK frente a Blender, control negativo), `test_deep_hip_muscles` y `test_deep_hip_blender` (CM-6). Documento: `docs/tendones.md`.

## Pendiente

- Longitudes reales de tendón (con fuente) para sustituir la convención.
- Rutas con más puntos de guía (retináculos extensor y flexor del tobillo, poleas de los dedos) y envainado.
- Músculos intrínsecos de la mano y del pie, fibras medias del trapecio completas, músculos de la cara, diafragma y suelo pélvico.

## Tendón cuadricipital y deslizamiento de la rótula (CM-10)

Recto femoral y los tres vastos pasan a `deform` con dos guías troclears (cara anterior de la diáfisis y de los cóndilos, a 6 mm de las superficies de convención) y terminan en la rótula, que ahora se desliza con la flexión de la rodilla (`patella.tracking`). Sin las guías la recta atravesaba el fémur 10–15 mm a flexión profunda. Sus tubos de Blender acompañan a la rótula; las mallas de volumen siguen la nueva ruta.
