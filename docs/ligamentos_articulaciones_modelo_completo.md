# Ligamentos y articulaciones de todo el modelo óseo

Auditoría y ampliación de las uniones del modelo óseo: cada articulación natural debe tener sus ligamentos. Antes de esta ampliación, **130 de 213 articulaciones no tenían ningún ligamento**. Se cubren por secciones (un commit por sección). Todo punto queda a menos de 12 mm de la superficie de su hueso; lo apoyado en fuentes débiles lo dice en su nota (**verificar en un atlas**). Los **tendones** no están aquí: pertenecen al modelo muscular (rama `muscle-model`).

## 1. Columna (C2 a sacro) — `config/articulations/spine.json`

En cada uno de los 23 niveles (C2/C3 … L5/S1) hay cinco ligamentos y, por lado, una articulación cigapofisaria:

| Ligamento | Dónde | Notas |
|---|---|---|
| Longitudinal anterior | cara anterior de los cuerpos y discos | el único que frena la extensión ([Taylor & Francis](https://taylorandfrancis.com/knowledge/medicine-and-healthcare/anatomy/anterior-longitudinal-ligament), [LearnMuscles](https://learnmuscles.com/glossary/ligaments-of-the-spine/)) |
| Longitudinal posterior | cara posterior de los cuerpos, dentro del canal | se tensa en la flexión |
| Amarillo | entre láminas | por detrás del longitudinal posterior; el más grueso en la región lumbar |
| Interespinoso | entre apófisis espinosas | se mezcla con el amarillo (delante) y el supraespinoso (detrás) |
| Intertransverso (×2) | entre apófisis transversas | frena la inclinación lateral; fino en la zona lumbar |
| Supraespinoso (uno solo) | de C7 al sacro | fuente débil en su extensión: **verificar** |

Las **articulaciones cigapofisarias** (`zygapophyseal_<sup>_<inf>.L/.R`, 46) son planas y no llevan cifra de rango (su orientación guía el movimiento de cada región; no hay cifra en las fuentes consultadas).

**Limitación**: los cuerpos vertebrales no tienen anchura en el modelo, así que cada punto se coloca a 8–11 mm del eje del hueso (cara anterior −10 mm; posterior +8 mm; lámina +10 mm; espinosa +11 mm; transversa 11 mm lateral), en el orden anatómico correcto, pero **no sobre la apófisis real**. En L5/S1 el sacro se recorre de arriba abajo, así que los puntos se ponen junto al promontorio.

## 2. Tórax y hombro — `config/articulations/thorax_ligaments.json`

| Grupo | Ligamentos | Fuentes |
|---|---|---|
| Costillas | radiado de la cabeza de la costilla (12; más un haz superior en las costillas 2–10 por las hemifacetas), costotransverso, costotransverso superior y costotransverso lateral (10 cada uno) | [UAMS](https://medicine.uams.edu/neuroscience/education/medical-school-courses/human-structure-module/anatomy-tables/joint-tables/joints-and-ligaments-of-the-thorax/), [TTUHSC](https://anatomy.ttuhscep.edu/anatomytables/joints_thorax.html); el radiado, además [cuestionario](https://wiki.voka.io/anatomy-quizzes/thorax/thoracic-cage-connections/) (fiabilidad baja). **Verificar en un atlas el detalle de las inserciones costotransversas** |
| Esternón | radiado esternocostal anterior y posterior (costillas 1–7), interchondral (8–10), manubrioesternal y xifoesternal (anterior y posterior) | [Elsevier](https://www.elsevier.com/resources/anatomy/connective-tissue/connective-tissue-of-thorax/radiate-sternochondral-ligaments/23210), UAMS, TTUHSC |
| Hombro | glenohumeral superior, medio, inferior (bandas anterior y posterior) y coracohumeral | [Wikipedia](https://en.wikipedia.org/wiki/Glenohumeral_ligaments), [Radiopaedia](https://radiopaedia.org/articles/ighl?lang=gb), [Hand Therapy Academy](https://handtherapyacademy.com/evaluation/the-function-of-the-glenohumeral-joint-ligaments/); la inserción humeral del medio varía entre fuentes |
| Esternoclavicular | anterior y posterior (el costoclavicular y el interclavicular ya existían) | [Wikipedia anterior](https://en.wikipedia.org/wiki/Anterior_sternoclavicular_ligament), [posterior](https://en.wikipedia.org/wiki/Posterior_sternoclavicular_ligament) |

La **articulación escapulotorácica no tiene ligamentos**: se sostiene por músculos y fascia (excepción documentada y comprobada por una prueba).

Cambios de huesos para que los puntos queden sobre el hueso: la escápula añade el **borde lateral** (vuelve del ángulo inferior al glenoides) y la **apófisis coracoides** al contorno, y los tubérculos mayor y menor y la tuberosidad deltoidea se colocan a 11 mm del eje del húmero (que no tiene anchura en el modelo). Con ello cuatro ligamentos antiguos (coracoclavicular conoide y trapezoide, coracoacromial) y tres hitos pasaron a menos de 12 mm.

## 3. Suelo pélvico — `config/articulations/pelvic_floor.json`

| Articulación | Ligamentos | Fuentes |
|---|---|---|
| Sínfisis del pubis | pubiano superior y arqueado (inferior), cruzan la línea media por encima y por debajo del disco | [StatPearls](https://www.statpearls.com/point-of-care/32333) y [cuestionario](https://wiki.voka.io/anatomy-quizzes/abdomen-and-pelvis/pelvic-joints/) (fiabilidad baja) |
| Sacrococcígea | anterior, posterior (profundo y superficial en la realidad: una sola banda) y lateral (del ángulo inferolateral del sacro al cóccix) | [Anatomy Standard](https://www.anatomystandard.com/ossa-et-juncturae/columna-vertebralis/art-lumbosacralis-et-sacrococcygea.html) y cuestionario |
| Sacroilíaca (×2) | anterior, interóseo (corto, el más profundo) y posterior (llega a la espina ilíaca posterior); se suman al iliolumbar, sacrotuberoso y sacroespinoso de la sección pélvica | StatPearls y cuestionario |

Las inserciones concretas se apoyan en fuentes de fiabilidad media y baja: cada nota dice **verificar en un atlas**.

## Deuda de anclaje

Quedan **72 anclajes antiguos** a más de 12 mm de su hueso (cráneo lateral, costillas–vértebra, codo, muñeca, rodilla, tobillo…). Están fijados en `tests/test_anchor_debt.py`: la lista solo puede disminuir.

