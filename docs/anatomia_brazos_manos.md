# Brazos, antebrazos, muñecas y manos: especificación

Especificación de las extremidades superiores de `anatomical-core` (húmero, radio, cúbito, carpo, metacarpo y falanges, lados `.L` y `.R`), con sus **puntos de unión** (articulaciones naturales independientes, ligamentos e inserciones de tendones) preparados para las poses y los músculos futuros.

| Qué | Archivo |
|---|---|
| Húmero, radio y cúbito | `config/anatomy/long_bones.json` |
| Carpo, metacarpo y falanges | `config/anatomy/hands_feet.json` |
| Articulaciones, ligamentos, inserciones y fuentes | `config/articulations/arm_hand.json` |
| Orientación de la palma en pose A | `config/pose_a.json` (`elbow.pronation`), `config/joints.json` (orden de los dof del codo) |
| Pruebas | `tests/test_arm_hand.py`, `tests/test_anatomy_blender.py` |

Coordenadas del proyecto: +X izquierda, **+Y atrás (anterior = −Y)**, +Z arriba. Valores aproximados para un adulto de 1,75 m que escalan con la altura; **no son medidas anatómicas exactas ni límites médicos**.

## 1. Huesos y jerarquía (30 por lado)

| Hueso | Padre en el rig | Padre anatómico |
|---|---|---|
| `humerus` | `upper_arm` (base) | **`scapula`** (articulación glenohumeral) |
| `radius`, `ulna` | `forearm` (base) | **`humerus`** (codo) |
| `scaphoid`, `lunate` | `hand` (base) | **`radius`** (fila proximal) |
| `triquetrum` | `hand` | **`ulna`** (fila proximal) |
| `pisiform` | `hand` | `triquetrum` (sesamoideo del flexor cubital del carpo) |
| `trapezium`, `trapezoid` | `hand` | `scaphoid` (fila distal) |
| `capitate` | `hand` | `lunate` |
| `hamate` | `hand` | `triquetrum` |
| `metacarpal_1` … `_5` | `trapezium`, `trapezoid`, `capitate`, `hamate`, `hamate` | igual |
| `thumb_proximal` → `thumb_distal` | cadena exacta desde `metacarpal_1` | igual |
| `index`, `middle`, `ring`, `little` `_proximal` → `_middle` → `_distal` | cadena exacta desde `metacarpal_2…5` | igual |

«Cadena exacta» significa que la cabeza de cada falange coincide con la cola del hueso anterior (verificado a 1e-12 m). El **padre del rig** es el que mueve el hueso en Blender (los carpos siguen a `hand`); el **padre anatómico** es la jerarquía articular que usarán las poses futuras.

## 2. Orientación en pose A

En la posición anatómica la palma mira al frente. En la pose A el brazo cuelga relajado con la palma hacia el cuerpo y algo adelantada: `elbow.pronation = 70°`, con `shoulder.abduction = 40°` y `elbow.flexion = 12°`. Medido con la cinemática directa, la normal de la palma queda en (−0,83; −0,31; −0,47) en el lado izquierdo: **medial** (x < −0,7), **ligeramente anterior** (−0,5 < y < 0) y simétrica en el derecho. Sin pronación (0°) la palma queda casi de frente (normal ≈ (−0,2; −0,95; 0,24)).

**Cambio de la base (Nivel 0), aprobado como parte de esta sección.** Los dof del codo pasan de `[flexion, pronation]` a `[pronation, flexion]`. Los dof se componen en el orden listado sobre ejes locales fijos, así que con el orden antiguo la pronación giraba sobre el eje del antebrazo **sin flexionar**, y al flexionar el codo 12° el eje real quedaba inclinado: la punta del antebrazo se desplazaba al pronar. Con el orden nuevo la pronación gira sobre el eje real del antebrazo (su punta no se mueve) y después se flexiona. El diff de `tests/golden/base_skeleton.json` solo reordena los dof del codo en los dos lados y cambia las dos firmas; pivotes, longitudes y límites no cambian.

## 3. Articulaciones naturales independientes (24 por lado)

| Articulación | Tipo | Rango publicado | Motor actual |
|---|---|---|---|
| Codo (humerocubital + humerorradial) | bisagra + esferoidea | flexión 140–150° ([e3 Rehab](https://e3rehab.com/blog/elbow-range-of-motion/)); rango funcional 30–130° ([Acta Orthop Belg](https://actaorthopaedica.be/archive/volume-62/supplement/article/biomechanics-of-the-normal-elbow-and-following-total-semi-constrained-arthroplasty)) | `elbow` |
| Radiocubital proximal | pivote | pronación y supinación 80–90° cada una (por lado); funcional 50° | — (la pronación la mueve `elbow`) |
| Radiocubital distal | pivote | rotación total 150–180° ([StatPearls](https://www.statpearls.com/point-of-care/32401)) | — |
| Radiocarpiana | elipsoidea | flexión 73,9–80°, extensión 65,9–70°, desviación radial 18,6–20° y cubital 28,3–30° (medidas en [120 adultos](https://synapse.koreamed.org/articles/1122791); la cifra mayor es la de texto, [Enlyte](https://enlyte.com/print/pdf/node/33601)); funcional: 54 / 60 / 17 / 40° ([Ryu 1991](https://mayoclinic.elsevierpure.com/en/publications/functional-ranges-of-motion-of-the-wrist-joint/)) | `wrist` |
| Mediocarpiana | compuesta | sin cifra en las fuentes | — |
| Carpometacarpiana 1 (trapecio–1.er metacarpiano) | en silla | flexión 45–50°, abducción 60–70°; oposición sin cifra propia | — |
| Carpometacarpianas 2–5 | plana | sin cifra; la 2.ª y la 3.ª son casi fijas y la 4.ª y la 5.ª ganan movilidad hacia el borde cubital | — |
| MCF del pulgar / IF del pulgar | bisagra | flexión 50–61° / 80–81° | — |
| MCF de los dedos | condílea | flexión 80–90°, extensión 45°, abducción 20–30° | — |
| IFP / IFD de los dedos | bisagra | flexión 100–104° / 68–80° | — |

Las cifras de pulgar y dedos proceden de una página agregadora ([Physiotutors](https://www.physiotutors.com/wiki/wrist-hand-active-range-of-motion/)) que a su vez resume varias referencias, y solo se midió el índice: se aplican las mismas cifras a los demás dedos y cada nota dice **verificar contra AAOS o AMA Guides**. La glenohumeral está en `thorax_shoulder.json`.

## 4. Ligamentos (42 por lado)

| Grupo | Ligamentos | Fuente |
|---|---|---|
| Codo | colateral cubital (epicóndilo medial → coronoides/olécranon), colateral radial (epicóndilo lateral → anular), colateral cubital lateral, anular | [Wikipedia](https://en.wikipedia.org/wiki/Radial_collateral_ligament_of_elbow_joint), [AnatomyZone](https://anatomyzone.com/upper-limb/elbow/elbow-joint/) |
| Antebrazo | membrana interósea (banda central), fibrocartílago triangular (TFCC) | [StatPearls](https://www.statpearls.com/point-of-care/32401), [Kenhub](https://kenhub.com/en/library/anatomy/distal-radioulnar-joint) |
| Muñeca y carpo | colaterales radial y cubital, radiocarpianos palmar y dorsal, retináculo flexor (tubérculo del escafoides y trapecio → pisiforme y gancho del ganchoso), pisoganchoso, pisometacarpiano | [Kenhub](https://www.kenhub.com/en/library/anatomy/carpal-bones), [Wikipedia](https://en.wikipedia.org/wiki/Flexor_retinaculum_of_the_hand) |
| Pulgar | oblicuo anterior de la CMC | fuente débil |
| Dedos (×14) | un colateral (lado lateral; el medial es simétrico y no se modela) y una placa palmar en cada MCF, IF, IFP e IFD | fuente débil |

Los ligamentos del codo y las cápsulas de la muñeca se citan con fuentes de fiabilidad media; **los colaterales y placas de los dedos y el oblicuo anterior carecen de una fuente propia y están marcados «verificar en un atlas»**. Los extremos de los ligamentos de los dedos se sitúan a 0,85 y 0,15 de la longitud de cada hueso para que el segmento tenga longitud real (los huesos de la cadena se tocan en la articulación).

## 5. Inserciones de tendones y músculos (38 por lado)

Brazo: cabezas lateral y medial del tríceps, origen del braquial, olécranon (tríceps, ancóneo), coronoides (braquial), cresta del supinador, cresta supracondílea lateral (braquiorradial y extensor radial largo), epicóndilo medial (flexores y pronador redondo) y lateral (extensores, supinador). Antebrazo: pronador redondo y cuadrado, estiloides radial, origen del flexor profundo y del abductor largo del pulgar. Mano: pisiforme (flexor cubital del carpo), gancho del ganchoso, tubérculos del escafoides y el trapecio (retináculo), bases de los metacarpianos 1, 2, 3 y 5 (flexor y extensores radiales, extensor cubital, abductor largo), tendones del pulgar, y por cada dedo: flexor superficial (falange media), flexor profundo (falange distal) y capuchón extensor (falange proximal).

Fuentes: [Semmelweis](https://semmelweis.hu/anatomia/files/2021/09/20211014_DrKatz_en.pdf) (alta), [Pearson](https://www.pearson.com/channels/anp/study-guides/muscles-of-the-forearm-origins-insertions-and) y [GMCH](https://www.gmch.gov.in/sites/default/files/documents/Extensor%20compartment%20of%20forearmphysio.pdf) (media), y tarjetas de estudio (baja). Lo apoyado solo en fuentes débiles (abductor largo, extensor corto y largo del pulgar, capuchón extensor, gancho del ganchoso) lo dice en su nota: **verificar en un atlas**. Los orígenes de la mayoría de los músculos intrínsecos de la mano (lumbricales, interóseos, tenares e hipotenares) no están modelados por falta de fuente fiable; solo figuran, con fuente débil, el abductor corto y el oponente del pulgar (tubérculo del trapecio) y el flexor corto del meñique (gancho del ganchoso).

## 6. Lo que la especificación pidió y no se aplicó

| Pedido | Aplicado | Motivo |
|---|---|---|
| Fila proximal del carpo hija de radio y cúbito, fila distal de la proximal | aplicado como **padre anatómico** | el padre del rig sigue siendo `hand`, que es el segmento base que los mueve |
| «Falange meñique» | `little_*` | nombres normalizados confirmados |
| Pronación para la palma medial | 70° y reorden de los dof del codo | ver sección 2; es un cambio deliberado de la base |
| Músculos | solo puntos de inserción | los músculos quedan para el modelo muscular; este nivel no contiene ninguno |
| Pisiforme como hueso de la fila proximal | hijo del piramidal, con nota de sesamoideo | las fuentes lo tratan a la vez como fila proximal y como sesamoideo |
