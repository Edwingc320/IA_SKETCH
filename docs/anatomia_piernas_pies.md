# Piernas y pies: especificación

Especificación de las extremidades inferiores de `anatomical-core` (fémur, rótula, tibia, peroné, tarso, metatarso y falanges, lados `.L` y `.R`), con sus **puntos de unión** (articulaciones naturales independientes, ligamentos y hitos óseos) preparados para las poses futuras. Es parte del **modelo óseo**: los músculos y tendones no están aquí, sino en la rama `muscle-model`.

| Qué | Archivo |
|---|---|
| Fémur, rótula, tibia y peroné | `config/anatomy/long_bones.json` |
| Tarso, metatarso y falanges | `config/anatomy/hands_feet.json` |
| Articulaciones, ligamentos, hitos y fuentes | `config/articulations/leg_foot.json` |
| Pruebas | `tests/test_leg_foot.py`, `tests/test_anatomy.py`, `tests/test_anatomy_blender.py` |

Coordenadas del proyecto: +X izquierda, **+Y atrás (anterior = −Y)**, +Z arriba. Valores aproximados para un adulto de 1,75 m que escalan con la altura; **no son medidas anatómicas exactas ni límites médicos**. La articulación coxofemoral y sus ligamentos están en `lumbar_pelvis.json`.

## 1. Huesos y jerarquía (30 por lado)

| Hueso | Padre en el rig | Padre anatómico |
|---|---|---|
| `femur` | `thigh` (base) | **`ilium`** (articulación coxofemoral) |
| `tibia`, `fibula` | `shin` (base) | **`femur`** (rodilla) |
| `patella` | `thigh` | **`femur`**; flota delante de la rodilla (≈ 45 mm por delante del eje) |
| `talus` | `foot` (base) | **`tibia`** (extremo distal de tibia y peroné: tobillo) |
| `calcaneus`, `navicular` | `talus` | `talus` |
| `cuboid` | `calcaneus` | `calcaneus` |
| `medial_cuneiform`, `intermediate_cuneiform`, `lateral_cuneiform` | `navicular` | `navicular` |
| `metatarsal_1`, `_2`, `_3` | cuneiforme medial, intermedio y lateral | igual |
| `metatarsal_4`, `_5` | `cuboid` | igual |
| `toe_1_proximal` → `toe_1_distal`; `toe_2…5_proximal` → `_middle` → `_distal` | cadena exacta desde su metatarsiano | igual |

«Cadena exacta»: la cabeza de cada falange coincide con la cola del hueso anterior (verificado a 1e-12 m). Las puntas de los cinco dedos quedan a **10,3 mm** del suelo (< 12 mm). Del cambio de esta sección solo el padre anatómico del astrágalo era nuevo (antes colgaba de `foot`); el rig lo sigue moviendo con `foot`.

**Nombres.** Los nombres pedidos coinciden con los del modelo, sin correcciones. Los dedos 2 a 5 incluyen la falange media (`toe_N_middle`), implícita en «`toe_2_proximal` a `toe_5_distal`»; el dedo gordo tiene solo dos falanges. Convención del proyecto: lado como sufijo `.L`/`.R`.

## 2. Articulaciones naturales independientes (28 por lado)

| Articulación | Tipo | Rango publicado | Motor actual |
|---|---|---|---|
| Tibiofemoral (rodilla) | bicondílea con meniscos | flexión 135–140° ([Brookbush](https://brookbushinstitute.com/video/knee-flexion-goniometry), [guía](https://www.ib.bioninja.com.au/downloads/25.%20Goniometry%20%28HL%29.pdf)), hiperextensión hasta 5°; rotación interna 25° y externa 18° a 30–40° de flexión ([WikiMSK](https://wikimsk.org/wiki/Knee_Biomechanics)) | `knee` (la rotación axial del rig está limitada a ±10°, menos que lo publicado) |
| Femororrotuliana | plana/en silla | deslizamiento sin cifra | — |
| Tibioperonea proximal | plana | traslación 1–3 mm ([TeachMeAnatomy](https://teachmeanatomy.info/lower-limb/joints/tibiofibular-joints)) | — |
| Tibioperonea distal | sindesmosis | sin cifra | — |
| Talocrural (tobillo) | bisagra | dorsiflexión 20–40° y flexión plantar 50° ([Physiotutors](https://book.physiotutors.com/?p=1149); [UW](https://uw.pressbooks.pub/fcmtextbook/?p=3087) da 30–40 de dorsiflexión) | `ankle` (dorsiflexión) |
| Subastragalina | sinovial | inversión 30–60° y eversión 15–30° (medida clínica del pie completo; las fuentes discrepan) | `ankle` (inversión) |
| Talonavicular | esferoidea | mediotarsiana 6° (una sola fuente débil: **verificar**) | — |
| Calcaneocuboidea | en silla | sin cifra | — |
| Cuneonavicular (con intercuneiformes y cuneocuboidea) | plana | sin cifra | — |
| Tarsometatarsianas 1–5 (Lisfranc) | planas | sin cifra | — |
| MTF del 1.er dedo | condílea | flexión 45°, extensión 70–90° ([QUT](https://podiatry-anatomy-app.qut.edu.au/content/joints/ankle-rom.html)) | — |
| IF del 1.er dedo | bisagra | flexión 90° | — |
| MTF, IFP e IFD de los dedos 2–5 | condílea / bisagras | sin cifra en las fuentes consultadas | — |

Los sesamoideos del 1.er metatarsiano no están en la lista de 185 huesos y no se modelan.

## 3. Ligamentos (29 por lado)

| Grupo | Ligamentos | Fuente |
|---|---|---|
| Rodilla | cruzado anterior y posterior, colateral tibial y peroneo, rotuliano | [OrthoBullets](https://www.orthobullets.com/knee-and-sports/3001/ligaments-of-the-knee) (el colateral tibial, con fuente débil: verificar) |
| Tibioperoneos | proximales anterior y posterior, membrana interósea, tibioperoneos anterior y posterior inferiores (sindesmosis), interóseo | [Kenhub](https://kenhub.com/en/library/anatomy/tibiofibular-joints), [OrthoBullets](https://www.orthobullets.com/foot-and-ankle/7005/ankle-ligaments) |
| Tobillo | deltoideo (tibiotalar, tibionavicular, tibiocalcáneo), peroneoastragalino anterior y posterior, peroneocalcáneo | [OrthoBullets](https://www.orthobullets.com/foot-and-ankle/7005/ankle-ligaments), [estudio anatómico](https://www.springermedizin.de/dimensions-and-attachments-of-the-ankle-ligaments-evaluation-for/9218400) |
| Pie | interóseo astragalocalcáneo (débil), calcaneonavicular plantar o «en resorte» ([Radiopaedia](https://images.radiopaedia.org/articles/spring-ligament-complex?lang=us)), bifurcado en dos ramas (débil), plantar largo y corto, Lisfranc ([estudio UTMB](https://researchexperts.utmb.edu/en/publications/three-dimensional-digital-and-gross-anatomy-of-the-lisfranc-ligam/): un haz en el 73 % de los pies, dos en el 27 %), cinco bandas de la fascia plantar ([UPenn](https://www.med.upenn.edu/orthoresidents/assets/user-content/documents/OITE_FA_Review.pdf)) |  |

No incluidos: meniscos (fibrocartílago, no ligamentos), retináculos, cápsulas y colaterales de los dedos del pie, porque no encontré fuente fiable. **Los ligamentos apoyados solo en tarjetas de estudio o páginas de entrenamiento llevan en su nota «verificar en un atlas».**

## 4. Hitos óseos (11 por lado)

Epicóndilos femorales medial y lateral, eminencia intercondílea, tuberosidad tibial, cabeza del peroné, maléolos medial y lateral, tuberosidad del calcáneo, sustentáculo del astrágalo, tuberosidad del navicular y base del 5.º metatarsiano. Los músculos y tendones que se insertan en ellos pertenecen a la rama `muscle-model`.

## 5. Lo que la especificación pidió y no se aplicó

| Pedido | Aplicado | Motivo |
|---|---|---|
| «Tendones» como uniones | no en `main` | pertenecen al modelo muscular (rama `muscle-model`); aquí solo hay ligamentos y hitos óseos |
| Astrágalo hijo de la tibia/peroné | padre anatómico `tibia` | el padre del rig sigue siendo `foot`, el segmento base que lo mueve |
| «Rotación tibial» con la rodilla | datos publicados, rig limitado | el rig de la base limita la rotación axial a ±10°; no se cambia la base |
