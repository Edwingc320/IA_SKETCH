# Ligamentos

**Rama:** `main` · **Estado:** completa: 620 ligamentos (contando ambos lados); toda articulación tiene ligamentos salvo la escapulotorácica (músculos y fascia; una prueba lo exige).

## Qué hay (por archivo, con los .L y .R)

| Archivo | Ligamentos | Contenido |
|---|---|---|
| `spine.json` | 139 | longitudinal anterior y posterior, amarillo, interespinoso, intertransverso (23 niveles C2–sacro) y supraespinoso |
| `thorax_ligaments.json` | 154 | radiado de la cabeza de la costilla, costotransversos (3), radiado esternocostal, interchondral, esternales, glenohumerales, coracohumeral, esternoclaviculares |
| `hand_foot_ligaments.json` | 136 | carpometacarpianos, transversos profundos, cuneonavicular, intercuneiformes, cuneocuboideo, tarsometatarsianos, colaterales y placas de los dedos del pie |
| `arm_hand.json` | 84 | codo, antebrazo (membrana interósea, TFCC), muñeca, retináculo flexor, colaterales y placas de los dedos |
| `leg_foot.json` | 58 | cruzados, colaterales, rotuliano, sindesmosis, deltoideo, laterales del tobillo, resorte, plantares, Lisfranc, fascia plantar |
| `head_neck.json` | 14 | craneovertebrales, nucal, ATM |
| `pelvic_floor.json` | 12 | sínfisis del pubis, sacrococcígeos, sacroilíacos |
| `lumbar_pelvis.json` | 12 | iliolumbar, sacrotuberoso, sacroespinoso, ligamentos de la cadera |
| `thorax_shoulder.json` | 11 | costoclavicular, interclavicular, coracoclavicular, acromioclavicular, coracoacromial |

## Reglas que cumple

- Origen e inserción sobre un hueso (o su cartílago, o la cara de una lámina cerrada) a **menos de 12 mm**: los nuevos lo cumplen todos; los antiguos incumplidores están fijados en un trinquete (61).
- Sacrotuberoso y sacroespinoso nacen en el borde lateral del sacro y terminan en la tuberosidad y la espina isquiáticas.
- Los nombres de ligamentos y de articulaciones comparten espacio de nombres.

## Fuentes

124 fuentes en total (fiabilidad alta, media o baja). Los ligamentos de los dedos del pie van **por analogía con la mano** y varios se apoyan en tarjetas de estudio: todos dicen «verificar en un atlas».

## Pruebas

`test_spine_ligaments`, `test_thorax_ligaments`, `test_pelvic_floor`, `test_hand_foot_ligaments` (incluye la cobertura global), `test_pelvis_closure`, `test_anchor_debt`. Documento: `docs/ligamentos_articulaciones_modelo_completo.md`.

## Pendiente

- Puntos de tensado intermedios (para que un ligamento no atraviese el hueso al articular): hoy cada ligamento es un segmento recto entre dos hitos.
- Verificar en un atlas los costotransversos y los de los dedos del pie.
- Reducir los 61 anclajes antiguos a más de 12 mm.
