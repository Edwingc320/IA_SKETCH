# Tórax y cintura escapular: especificación

Especificación de la caja torácica, la columna torácica y la cintura escapular de `anatomical-core`, con sus **puntos de unión** (articulaciones naturales, ligamentos e inserciones tendinosas) preparados para las poses y los músculos futuros.

Todo lo de este documento está implementado como datos y validado por pruebas. Fuentes de verdad:

| Qué | Archivo |
|---|---|
| Huesos del tórax (esternón, costillas) | `config/anatomy/thoracic_cage.json` |
| Vértebras T1–T12 (y el resto de la columna) | `config/anatomy/spine_head.json` |
| Escápula | `config/anatomy/long_bones.json` |
| Clavícula | base congelada (`config/skeleton_definition.json`) |
| Articulaciones, ligamentos, inserciones y fuentes | `config/articulations/thorax_shoulder.json` |

Coordenadas del proyecto: +X izquierda, **+Y atrás (anterior = −Y)**, +Z arriba. Valores aproximados para un adulto de 1,75 m que escalan con la altura; **no son medidas anatómicas exactas ni límites médicos**.

## 1. Huesos y jerarquía

| Hueso | Padre en el rig | Padre anatómico | Segmento base que lo mueve |
|---|---|---|---|
| `T12` … `T7` | vértebra inferior (`T12` cuelga de `spine_thoracic`) | vértebra inferior (`T12` → `L1`) | `spine_thoracic` |
| `T6` … `T1` | vértebra inferior (`T6` cuelga de `thorax`) | vértebra inferior (`T6` → `T7`) | `thorax` |
| `rib_01.L` … `rib_12.L` (y `.R`) | **su vértebra `T1` … `T12`** | su vértebra | el de su vértebra |
| `sternum` (manubrio + cuerpo + xifoides) | **`T4`** | `T4` | `thorax` |
| `clavicle.L/.R` | `thorax` (base) | — | `thorax` |
| `scapula.L/.R` | **`clavicle.L/.R`** | **`clavicle.L/.R`** (acromioclavicular) | `clavicle` |

- **Cifosis torácica** (cóncava hacia delante): vértice en T6–T7, 1,75 cm hacia atrás (+Y).
- **Costillas**: cada cabeza costal está a media altura de su vértebra, a 0,012 H (2,1 cm) del eje vertebral. El arco va hacia delante (−Y) y hacia abajo (−Z) hasta el cartílago: las verdaderas (1–7) llegan al esternón, las falsas (8–10) al reborde costal y las flotantes (11–12) no tienen cartílago anterior.
- **Esternón**: escotadura yugular a la altura del disco T2–T3, ángulo esternal (unión manubrioesternal) a la altura del disco T4–T5 —donde llega el cartílago de la 2.ª costilla— y punta del xifoides a la altura de T10 ([Dartmouth](https://humananatomy.host.dartmouth.edu/BHA/public_html/part_4/chapter_19.html), [StatPearls](https://dev2.statpearls.com/articlelibrary/viewarticle/36706)).
- **Escápula**: de la cavidad glenoidea (= pivote del hombro de la base) al ángulo inferior (T7); ángulo superior a la altura de T2 ([GPnotebook](https://gpnotebook.com/pages/musculoskeletal-medicine/bony-palpation/borders-of-scapula-examination)). Queda sobre la cara posterior del tórax **sin tocar las costillas**: holgura mínima medida de 29 mm (exigido ≥ 10 mm).

## 2. Articulaciones naturales independientes

Cada articulación tiene un centro anclado a sus huesos, el hueso que lleva su marcador y, si existe, la articulación de la base que hoy la mueve (`rig_driver`). Los rangos son el **rango total** publicado por la fuente indicada; cuando la fuente no da cifra, se deja vacío (no se inventa).

| Articulación | Tipo | Une | Rango total publicado | Motor actual en la base |
|---|---|---|---|---|
| Esternoclavicular | sinovial en silla, con disco | clavícula – esternón | elevación/depresión 60°, protracción/retracción 35°, rotación axial 40° ([GPnotebook](https://gpnotebook.com/pages/musculoskeletal-medicine/sternoclavicular-joint-anatomy/movements); una sola fuente clínica) | `sternoclavicular` |
| Acromioclavicular | sinovial plana | clavícula – acromion | sin cifra fiable; deslizamiento y rotación limitados por conoide y trapezoide ([Kenhub](https://kenhub.com/en/library/anatomy/coracoclavicular-ligament), [AJSM 2012](https://www.ovid.com/journals/ajsm/pdf/10.1177/0363546512458571~the-function-of-the-acromioclavicular-and-coracoclavicular)) | — |
| Glenohumeral | esferoidea | húmero – escápula | flexión 160–180°, extensión 50–60°, abducción 170–180°, aducción 50–75°, rotación interna 60–100°, externa 80–90° (brazo con escápula libre, tabla basada en Magee); abducción solo glenohumeral ≈ 120° ([World J Orthop](https://wjgnet.com/2218-5836/abstract/v3/i6/87.htm)) | `shoulder` |
| Escapulotorácica | funcional (deslizamiento) | escápula – pared torácica | rotación superior ≈ 60° de 180° de abducción (ritmo 2:1); la proporción varía con el ángulo (2,34:1 de media, [Madokoro](https://kurume.repo.nii.ac.jp/record/136/files/37104A1215.pdf)) | — |
| Manubrioesternal | cartilaginosa (sínfisis) | manubrio – cuerpo | movimiento mínimo; ángulo esternal medio 163,4° (hombres) / 165,0° (mujeres) | — |
| Xifoesternal | cartilaginosa | cuerpo – xifoides | — | — |
| Costovertebral ×12 por lado | sinovial plana | cabeza costal – cuerpo vertebral | costillas 1–6: «bomba» 10–16°, «asa de cubo» 8–14° ([WikiMSK](https://wikimsk.org/wiki/Ribcage_Biomechanics)); 7–12: predomina el asa de cubo (sin cifra) | — |
| Costotransversa ×10 por lado | sinovial plana | tubérculo costal – apófisis transversa | acoplada a la costovertebral ([Kenhub](https://kenhub.com/en/library/anatomy/costovertebral-joints)) | — |
| Esternocostal ×7 por lado | 1.ª: sincondrosis; 2.ª–7.ª: sinovial plana | cartílago costal – esternón | — | — |
| Intercondral ×3 por lado (8–10) | sinovial plana | cartílago – cartílago | — | — |
| Intervertebral C7/T1 … T12/L1 (13) | disco + facetarias | vértebra – vértebra | por segmento, *in vitro* (±7,5 Nm): flexoextensión 6–8° (T1–T2: 14°), inclinación lateral 10–12° en T1–T7 y 8–9° en T7–T12, rotación axial 10–12° en T1–T10 y 7–8° en T10–T12 ([Wilke 2017](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5433776/)) | C7/T1: `neck`; T12/L1: `thoracic` |

Orientación escapular en reposo (para las poses): plano escapular unos 30° por delante del plano coronal; inclinación anterior 10–20° y rotación interna 30–40° ([Musculoskeletal Key](https://musculoskeletalkey.com/scapular-dyskinesis/)). En los primeros ~30° de elevación del brazo la escápula apenas gira ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC155505)).

## 3. Ligamentos

| Ligamento | Origen → inserción | Función |
|---|---|---|
| Costoclavicular | clavícula medial → cartílago de la 1.ª costilla | fulcro de la elevación y la protracción claviculares; presente en el 94 % de los lados disecados ([Rom J Morphol Embryol](https://rjme.ro/archive/50/3/22/)) |
| Interclavicular | clavícula izquierda → clavícula derecha (sobre el manubrio) | estabiliza ambas esternoclaviculares ([Kenhub](https://kenhub.com/en/library/anatomy/sternoclavicular-joint)) |
| Coracoclavicular conoide | clavícula lateral → base de la coracoides | restricción clave de la protracción y la inclinación posterior escapular |
| Coracoclavicular trapezoide | clavícula lateral → coracoides | contribuye a la rotación externa escapular (clásicamente, limita la rotación anterior) |
| Acromioclavicular | clavícula lateral → acromion | cápsula de la acromioclavicular |
| Coracoacromial | coracoides → acromion | techo del espacio subacromial |

Ligamentos que quedan descritos dentro de su articulación (sin línea propia): esternoclaviculares anterior y posterior, radiado e intraarticular (costovertebral), costotransversos, longitudinales, amarillo, interespinoso y supraespinoso.

## 4. Inserciones tendinosas y musculares

| Punto | Estructuras | Fuente |
|---|---|---|
| Apófisis coracoides | bíceps cabeza corta y coracobraquial (origen), pectoral menor (inserción) | [AnatomyZone](https://anatomyzone.com/articles/biceps-brachii-short-head/), [Shoulderdoc](https://shoulderdoc.co.uk/pages/muscles-of-the-shoulder-arm), [UW](https://rad.uw.edu/muscle-atlas/pectoralis-minor) |
| Tubérculo supraglenoideo / infraglenoideo | bíceps cabeza larga / tríceps cabeza larga (origen) | [TTUHSC](https://anatomy.ttuhscep.edu/anatomytables/bones_upperlimb.html) |
| Fosas supraespinosa, infraespinosa, subescapular; borde lateral | supraespinoso, infraespinoso, subescapular, redondo menor (origen) | [LibreTexts](https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Anatomy_Lab/09%3A_The_Appendicular_Muscles/9.01%3A_Muscles_of_the_Rotator_Cuff), [Radiopaedia](https://images.radiopaedia.org/articles/teres-minor) |
| Tubérculo mayor / menor del húmero | manguito rotador / subescapular (inserción) | LibreTexts |
| Ángulo superior; borde medial | elevador de la escápula; romboides menor y mayor, serrato anterior (inserción) | [Wikipedia](https://en.wikipedia.org/wiki/Levator_scapulae_muscle), [Wikipedia](https://en.wikipedia.org/wiki/Rhomboid_major_muscle) |
| Apófisis espinosas C7–T1 y T2–T5; transversas C1–C4 | romboides menor y mayor; elevador de la escápula (origen) | Wikipedia |
| Costillas 1–8 (cara lateral); 3–5 (cerca del cartílago) | serrato anterior; pectoral menor (origen) | [UW](https://rad.uw.edu/muscle-atlas/pectoralis-minor) / tarjetas de estudio |
| Acromion, espina, tercio lateral de la clavícula, tuberosidad deltoidea, ángulo inferior | deltoides, trapecio, redondo mayor | **solo tarjetas de estudio: verificar en un atlas** |
| Tuberosidad radial | bíceps (inserción) | Shoulderdoc |

Cada fuente lleva su fiabilidad (`alta`, `media`, `baja`) en `thorax_shoulder.json`; lo que solo se apoya en fuentes de fiabilidad baja lo indica en su nota.

## 5. Lo que la especificación pidió y no se aplicó (y por qué)

| Pedido | Aplicado | Motivo |
|---|---|---|
| Nombres `rib_L_01` | `rib_01.L` | normalización aprobada (lado como sufijo final); `rib_L_01` queda trazado en `config/reference/` |
| Cadena «descendente T1 → T12» | cadena de abajo arriba (`T12` → … → `T1`) | es la aprobada en la región 4; con ella girar un segmento arrastra lo que está por encima |
| Esternón en el plano anterior «+Y» | delante = **−Y** | convención del proyecto (el personaje mira a −Y) |
| La clavícula nace en el manubrio | no | la clavícula es de la base congelada; ver §6 |

## 6. Limitaciones heredadas de la base y cambio propuesto

La clavícula de la base nace casi en el plano de la columna y termina en el centro glenohumeral. Consecuencias medidas (avisos, no errores):

- hueco esternoclavicular de **86 mm** entre el pivote de la clavícula y el esternón;
- el acromion queda a **30 mm** de la clavícula;
- el ligamento costoclavicular mide **89 mm** (real ≈ 15 mm).

Corregirlo exige un **cambio deliberado de la base** (`py scripts\freeze_base.py --update` y revisar el diff del golden): mover el origen de la clavícula al manubrio manteniendo el pivote del hombro, y —por el mismo motivo— alargar el cuello base (0,045 H) para subir los cóndilos occipitales. No se ha hecho: requiere tu aprobación expresa.
