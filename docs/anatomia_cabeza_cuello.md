# Cabeza y columna cervical: especificación

Especificación de la columna cervical (C1–C7), el cráneo y la mandíbula de `anatomical-core`, con sus **puntos de unión** (articulaciones naturales, ligamentos, inserciones e hitos craneométricos) preparados para las poses y los músculos futuros. Todo está implementado como datos y validado por pruebas.

| Qué | Archivo |
|---|---|
| Vértebras, cráneo y mandíbula | `config/anatomy/spine_head.json` |
| Articulaciones, ligamentos, inserciones, hitos y fuentes | `config/articulations/head_neck.json` |
| Pruebas | `tests/test_head_neck.py`, `tests/test_anatomy_blender.py` (`test_05h`) |

Coordenadas del proyecto: +X izquierda, **+Y atrás (anterior = −Y)**, +Z arriba. Valores aproximados para un adulto de 1,75 m que escalan con la altura; **no son medidas anatómicas exactas ni límites médicos**.

## 1. Huesos y jerarquía

| Hueso | Padre en el rig | Padre anatómico | Lo mueve |
|---|---|---|---|
| `C7` | `neck` (base) | `T1` | `neck` |
| `C6` … `C1` | vértebra inferior | vértebra inferior | `neck` |
| `cranium` | `head` (base) | **`C1`** (cóndilos occipitales) | `head` |
| `mandible` | **`cranium`** | **`cranium`** (ATM) | `head` |

- **Cadena cervical** continua de abajo arriba (T1 → C7 → … → C1): cada vértebra nace exactamente en la cola de la inferior, y el cráneo en la cima de C1, que coincide con el pivote `head` de la base.
- **Lordosis cervical** (convexa hacia delante, −Y): ángulo de Cobb C2–C7 de **17,1°**, la media de 307 adultos asintomáticos (17,11° ± 6,31°, [Zhu et al. 2020](https://josr-online.biomedcentral.com/articles/10.1186/s13018-019-1526-x)). La curva anterior daba 33,4°, fuera de ese rango, y se recalibró.
- **Cráneo**: perfil medio-sagital con cóndilos/basion, opistion, inion, lambda, vértex, bregma, glabela, nasion, espina nasal y prostion. Mira hacia delante (−Y).
- **Plano de Frankfort horizontal**: porion (techo del conducto auditivo) y orbitale (borde inferior de la órbita) a la misma altura ([Wikipedia: Porion](https://en.wikipedia.org/wiki/Porion)).
- **Equilibrio**: el centro de gravedad de la cabeza (punto medio nasion–inion) queda **por delante** de los cóndilos occipitales y por encima del conducto auditivo, como en el estudio de 1986 ([Springer](https://link.springer.com/doi/10.1007/BF02427845)); los extensores y el ligamento nucal compensan ese momento.
- **Mandíbula**: nace en el **centro del eje de bisagra** entre las dos ATM (cóndilos a ±5 cm) y su eje local X es exactamente ese eje. Al abrir la boca (girar sobre X) los cóndilos no se mueven y el mentón baja (probado en Blender). Anchura bigoníaca 111 mm y bicigomática 133 mm ([Acta Odontologica](https://medicaljournalssweden.se/actaodontologica/article/download/37863/43029/95612)).

## 2. Articulaciones naturales independientes

| Articulación | Tipo | Rango publicado | Motor actual |
|---|---|---|---|
| Atlantooccipital (C0–C1) | sinovial elipsoidea | flexoextensión 14–18°; inclinación 4–6° y rotación 2–5° **por lado** ([Schöps 1997](https://www.thieme-connect.de/products/ejournals/pdf/10.1055/s-2008-1061881.pdf)); en cadáver: flexión 3,5°, extensión 21,0° ([Panjabi 1988](https://wbldb.lievers.net/10194076.html)) | `head` (pivote idéntico) |
| Atlantoaxial (C1–C2) | sinovial (pivote + planas) | flexoextensión 12–15°; inclinación 5–7° y **rotación 40–45° por lado** (Schöps); en cadáver 38,9° (Panjabi) | — (hoy se mueve con `neck`) |
| Intervertebrales C2/C3 … C6/C7 | disco + facetarias | flexoextensión 6,3 / 7,9 / 8,0 / 8,4 / 7,9° e inclinación 4,9 / 4,5 / 4,2 / 3,7 / 3,7° (modelo de elementos finitos, [Wo 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8317600/table/T2)); rotación 3,1 / 4,0 / 5,3 / 4,6 / 2,3° por lado (in vivo, [Zhao 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3701975)) | — |
| Temporomandibular (×2) | bicondílea con disco (rotación + traslación) | apertura interincisal 44,8 mm, protrusión 5,65 mm, lateralidad 8,2–8,7 mm por lado ([estudio de Nepal](https://nepmed.nhrc.gov.np/entities/publication/f36a70eb-584e-4926-a156-8f5572c5cff6/full)); rotación y traslación del cóndilo sin cifra en las fuentes | — |

C7/T1 está en la especificación del tórax (motor: `neck`). La rotación del cuello se concentra en C1–C2.

## 3. Ligamentos

| Ligamento | Origen → inserción | Función |
|---|---|---|
| Alar (×2) | diente del axis → cóndilo occipital | limita la rotación atlantoaxial |
| Transverso del atlas | masa lateral izquierda → derecha de C1 | estabilizador principal: sujeta el diente contra el arco anterior |
| Apical | diente → borde anterior del agujero magno | puede faltar hasta en el 20 % |
| Membrana tectoria | cuerpo de C2 → clivus | continuación del longitudinal posterior; protege la médula |
| Membranas atlantooccipitales anterior y posterior | arcos de C1 → bordes del agujero magno | la anterior limita la hiperextensión |
| Nucal | espinosa de C7 → protuberancia occipital externa | resiste la hiperflexión ([Kenhub](https://kenhub.com/en/library/anatomy/nuchal-ligament)) |
| Temporomandibular lateral (×2) | tubérculo articular → cuello del cóndilo | limita el desplazamiento posterior |
| Esfenomandibular (×2) | espina del esfenoides → língula | — |
| Estilomandibular (×2) | estiloides → ángulo mandibular | — |

Fuentes de los ligamentos craneovertebrales: [RadioGraphics](https://pubs.rsna.org/radiographics/doi/10.1148/rg.230137), [Kenhub](https://www.kenhub.com/en/start/craniovertebral-ligaments-and-joints); de la ATM: [TeachMeAnatomy](https://teachmeanatomy.info/head/temporomandibular-joint/), [USMF](https://stomortopedica.usmf.md/sites/default/files/inline-files/TEMPOROMANDIBULAR%20JOINT.pdf).

## 4. Hitos óseos

Plano de Frankfort (pórion y orbitario), nasion, centro de gravedad de la cabeza, protuberancia occipital externa, línea nucal superior, apófisis mastoides, arco cigomático, fosa temporal, apófisis coronoides, ángulo y cuello del cóndilo de la mandíbula y fosa digástrica. Los músculos y tendones **no forman parte del modelo óseo**: sus orígenes, inserciones y fuentes están en la rama `muscle-model` (donde sigue pendiente verificar en un atlas lo apoyado en fuentes débiles). Aquí quedan solo los accidentes óseos con nombre propio, que sirven de anclaje a ese modelo.

## 5. Lo que la especificación pidió y no se aplicó

| Pedido | Aplicado | Motivo |
|---|---|---|
| «Cadena cervical descendente C1 → C7» y «C1 hijo de C7» | cadena de **abajo arriba** (C7 → … → C1 → cráneo) | las dos frases se contradicen; la de abajo arriba es la aprobada y cumple «cranium hijo de C1» |
| Delante = «+Y» | delante = **−Y** | convención del proyecto (el personaje mira a −Y) |

## 6. Corrección de la base (v2)

El cuello de la v0.2 medía 0,045 H (79 mm para C1–C7, unos 11 mm por vértebra incluido el disco) y la cabeza 0,135 H (236 mm de los cóndilos al vértex). Los cóndilos quedaban bajos, la bóveda craneal alta y el mentón cerca del esternón. Se repartió de nuevo conservando la estatura exacta:

| Medida | Antes | Ahora |
|---|---|---|
| Cuello (C1–C7) | 79 mm (0,045 H) | **149 mm (0,085 H)**, ~21 mm por vértebra |
| Cabeza (cóndilos → vértex) | 236 mm (0,135 H) | **167 mm (0,095 H)** |
| Cóndilos occipitales (z) | 1,513 m | **1,582 m** |
| Separación vertical mentón – escotadura yugular | 68 mm | **137 mm** |
| Vértex | 1,749011 m | 1,749011 m (sin cambio) |

La lordosis cervical se recalibró para el cuello nuevo (Cobb C2–C7 = 17,1°) y la bóveda del cráneo (lambda y bregma) se acortó con la cabeza; la cara y la mandíbula, que cuelgan de los cóndilos, no cambian. **Limitación que queda:** la cabeza base sigue siendo unos 2 cm más larga que un cráneo real, porque conserva toda la estatura (la suma cuello + cabeza es la misma que antes).
