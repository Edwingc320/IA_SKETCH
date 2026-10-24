# Columna lumbar, sacro y pelvis: especificación

Especificación de L1–L5, el sacro, el cóccix y los huesos de la cadera (ilion, isquion y pubis) de `anatomical-core`, con sus **puntos de unión** (articulaciones naturales, ligamentos, inserciones e hito del centro de masas) preparados para las poses y los músculos futuros. Todo está implementado como datos y validado por pruebas.

| Qué | Archivo |
|---|---|
| Sacro, cóccix, ilion, isquion y pubis | `config/anatomy/pelvic_girdle.json` |
| Vértebras lumbares | `config/anatomy/spine_head.json` |
| Articulaciones, ligamentos, inserciones y fuentes | `config/articulations/lumbar_pelvis.json` |
| Pruebas | `tests/test_lumbar_pelvis.py`, `tests/test_anatomy_blender.py` (`test_05i`) |

Coordenadas del proyecto: +X izquierda, **+Y atrás (anterior = −Y)**, +Z arriba. Valores aproximados para un adulto de 1,75 m que escalan con la altura; **no son medidas anatómicas exactas ni límites médicos**.

## 1. Huesos y jerarquía

| Hueso | Padre en el rig | Padre anatómico | Lo mueve |
|---|---|---|---|
| `sacrum_fused` | `pelvis` (base) | `pelvis` | `pelvis` |
| `coccyx_fused` | `sacrum_fused` | `sacrum_fused` | `pelvis` |
| `ilium.L/.R` | **`sacrum_fused`** | `sacrum_fused` | `pelvis` |
| `ischium.L/.R` | `ilium` | `ilium` | `pelvis` |
| `pubis.L/.R` | `ilium` | `ilium` | `pelvis` |
| `L5` | `spine_lumbar` (base) | **`sacrum_fused`** | `spine_lumbar` |
| `L4` … `L1` | vértebra inferior | vértebra inferior | `spine_lumbar` |

- **Sacro = raíz del bloque pélvico** del nivel 1: el ilion y el cóccix cuelgan de él (articulaciones sacroilíaca y sacrococcígea); el isquion y el pubis cuelgan del ilion. La cadena lumbar va de abajo arriba (sacro → L5 → … → L1 → T12).
- **L5 asienta exactamente sobre la meseta de S1**: su cabeza coincide con la cabeza del sacro, que es la cola de la pelvis base.
- **Coxal separado en tres huesos**: `ilium` (sacroilíaca, cresta y espinas ilíacas), `ischium` (acetábulo → tuberosidad isquiática) y `pubis` (acetábulo → sínfisis). Los tres **coinciden en el acetábulo**, que es exactamente el pivote de la cadera de la base, y cada uno traza su nombre de la referencia.

## 2. Alineación: parámetros espinopélvicos

El sacro y la lordosis lumbar estaban fuera de lo publicado (pendiente sacra 28,6° y lordosis L1–S1 de 65,6°). Se recalibraron a la **media de dos cohortes asintomáticas**:

| Parámetro | Cohorte 1 | Cohorte 2 | Modelo |
|---|---|---|---|
| Pendiente sacra (SS) | 35,99° | 38,11° | **37,0°** |
| Lordosis lumbar (LL, L1–S1) | 48,84° | 54,9° | **51,9°** |
| Inclinación pélvica (PT) | 17,97° | 13,0° | **15,5°** |
| Incidencia pélvica (PI = SS + PT) | 55,48° | 50,95° | **52,5°** |

Cohorte 1: [Sudhir et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4771498), 101 adultos (PI 55,48 ± 5,31; PT 17,97 ± 7,16; SS 35,99 ± 7,53; LL 48,84 ± 9,82). Cohorte 2: [Cureus 2025](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12499943/), 250 adultos mayores de 50 (PI 50,95 ± 11,72; PT 13,0 ± 7,12; SS 38,11 ± 9,71; LL 54,9 ± 13,7). Las definiciones de LL varían entre estudios (L1–S1 frente a T12–S1) y no hay un «normal» universal.

- **Lordosis lumbar** convexa hacia delante (−Y), con vértice en L3 y valor nulo en las uniones con el sacro y con T12.
- **Angulación lumbosacra**: L5 se inclina hacia delante sobre el sacro; el ángulo entre el eje de L5 y la normal de S1 es de 7,7° con la lordosis calibrada a los datos publicados (cota solo geométrica: el reparto de la lordosis por nivel no está validado con una fuente).
- **Pelvis en copa**: los coxales rodean el eje de las caderas con crestas ilíacas (a 0,075 H del centro), espinas ilíacas anteriores, sínfisis del pubis delante y tuberosidades isquiáticas debajo. El **centro de masas** del cuerpo se coloca al 55,7 % de la estatura, delante de S2 y entre el eje de las caderas y el promontorio, dentro de la copa ([revisión](https://atna-mam.utcluj.ro/index.php/Acta/article/download/2746/2161); el 55–57 % es coherente entre fuentes educativas).

**Corrección de la base (v2).** En la v0.2 la columna de la base pasaba justo por encima del eje de las caderas: la inclinación pélvica era 0° y la incidencia ≈ 37°, por debajo de lo publicado. Ahora la pelvis se inclina 15,5° (S1 queda 23 mm detrás del eje de las caderas) y el segmento lumbar la compensa inclinándose 8,4° hacia delante, de modo que **la columna torácica y todo lo que cuelga de ella no se mueven**. La lordosis L1–S1 se recalibró a 51,9° con ese segmento nuevo.

## 3. Articulaciones naturales independientes

| Articulación | Tipo | Rango publicado | Motor actual |
|---|---|---|---|
| Intervertebrales L1/L2 … L4/L5 | disco + facetarias | flexoextensión total 11,9 / 14,5 / 15,3 / 18,2° (Dvorak 1991, pasivo); Pearcy 1984 en 11 sanos: flexión 8–13°, extensión 1–5°. Inclinación y rotación sin cifra por nivel | — |
| Lumbosacra L5/S1 | disco + facetarias | flexoextensión 17,0° (Dvorak); Pearcy: flexión 9°, extensión 5° | `lumbar` (pivote idéntico) |
| Sacroilíacas (×2) | sinovial muy rígida | nutación/contranutación 1–4° ([ABMP](https://www.abmp.com/massage-and-bodywork-magazine/current-concepts-sacroiliac-joint-dysfunction)); en cadáver bajo carga solo 0,16° y 0,32 mm ([Fraunhofer](https://publica.fraunhofer.de/handle/publica/256609)) | — |
| Sacrococcígea | sínfisis | sin cifra en las fuentes | — |
| Sínfisis del pubis | sínfisis (disco interpúbico) | traslación total 1,4–3,1 mm (hasta 5 mm fisiológico, [JBJS 2008](https://pubmed.ncbi.nlm.nih.gov/18829908/)); vertical ~2 mm y rotación < 1,5° ([Acta Orthop 1984](https://actaorthop.org/actao/article/view/23359)) | — |
| Coxofemorales (×2) | esferoidea | flexión 120°, extensión 10°, abducción 45°, aducción 25°, rotación interna 15° y externa 35° (activos, [StatPearls](https://statpearls.com/sp/al/39/32220/)); otras referencias dan rotaciones de 35–50° | `hip` (pivote idéntico) |

Los rangos de Pearcy y Dvorak proceden de un protocolo de ensayo clínico que los resume ([NCT03737227](https://cdn.clinicaltrials.gov/large-docs/27/NCT03737227/Prot_SAP_000.pdf)), no de los artículos originales.

## 4. Ligamentos

| Ligamento | Origen → inserción | Función |
|---|---|---|
| Iliolumbar (×2) | apófisis transversa de L5 → cresta ilíaca | une L5 al ilion; parte del cuadrado lumbar nace en él ([estudio de disección](https://pmc.ncbi.nlm.nih.gov/articles/PMC9705086)) |
| Sacrotuberoso (×2) | sacro/cóccix → tuberosidad isquiática | se tensa en la nutación ([Taylor & Francis](https://taylorandfrancis.com/knowledge/Medicine_and_healthcare/Anatomy/Sacrotuberous_ligament)) |
| Sacroespinoso (×2) | sacro/cóccix → espina isquiática | impide que el promontorio bascule hacia delante ([Kenhub](https://kenhub.com/en/library/anatomy/sacrospinous-ligament)) |
| Iliofemoral (×2) | espina ilíaca anteroinferior → línea intertrocantérea | el más fuerte; limita extensión y rotación externa |
| Pubofemoral (×2) | rama superior del pubis → cuello femoral | limita abducción y extensión |
| Isquiofemoral (×2) | isquion → cuello femoral | principal freno de la rotación interna ([cadáver](https://vivo.weill.cornell.edu/display/pubid18237703)) |

## 5. Inserciones e hitos

Espinas ilíacas anterosuperior (sartorio) y anteroinferior (recto femoral), fosa ilíaca (ilíaco), cresta ilíaca (cuadrado lumbar), tuberosidad isquiática (isquiotibiales, sacrotuberoso), cuerpo del pubis (aductor largo), trocánter menor (psoas e ilíaco), tuberosidad glútea (glúteo mayor), cara posterior del sacro (glúteo mayor), cuerpos lumbares L1–L4 (psoas mayor) y el hito del centro de masas.

Cada fuente lleva su fiabilidad (`alta`, `media`, `baja`) en `lumbar_pelvis.json`. Lo apoyado solo en fuentes de fiabilidad baja (iliaco, cuadrado lumbar, psoas, glúteo mayor, trocánter menor) lo indica en su nota: **verificar en un atlas**. No pude verificar los orígenes de los glúteos medio y menor ni del recto del abdomen, por eso no están incluidos.

## 6. Lo que la especificación pidió y no se aplicó

| Pedido | Aplicado | Motivo |
|---|---|---|
| Nombres `sacrum`, `coccyx` | `sacrum_fused`, `coccyx_fused` | son los nombres de la referencia (trazabilidad 1:1); `ilium`, `ischium` y `pubis` sí van separados, como pides |
| «L5 hijo de L4 en orden descendente» | cadena de abajo arriba (L5 sobre el sacro) | cumple «sacro raíz» y «L5 sobre la meseta de S1» |
| «Lordosis hacia +Y» | convexa hacia **−Y** (delante) | convención del proyecto: el personaje mira a −Y |
| Los huesos ilíacos cuelgan del sacro | aplicado | el ilion cuelga de `sacrum_fused`; isquion y pubis, del ilion (el rig los sigue moviendo `pelvis`) |
