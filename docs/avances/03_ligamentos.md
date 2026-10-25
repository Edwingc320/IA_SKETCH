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

- Origen e inserción sobre un hueso (o su cartílago, o la cara de una lámina cerrada) a **menos de 12 mm**: los nuevos lo cumplen todos; los antiguos incumplidores están fijados en un trinquete (58 desde CM-5: los cruzados y la articulación femororrotuliana pasaron a menos de 12 mm gracias a las superficies del cóndilo y la diáfisis del fémur, que son una convención).
- Sacrotuberoso y sacroespinoso nacen en el borde lateral del sacro y terminan en la tuberosidad y la espina isquiáticas.
- Los nombres de ligamentos y de articulaciones comparten espacio de nombres.

## Fuentes

126 fuentes en total (fiabilidad alta, media o baja). Los ligamentos de los dedos del pie van **por analogía con la mano** y varios se apoyan en tarjetas de estudio: todos dicen «verificar en un atlas».

## Ligamentos de la cadera con guías de envoltura (CM-4)

Iliofemoral, pubofemoral e isquiofemoral (`lumbar_pelvis.json`) son ahora poligonales **origen → guías (`via`) → inserción** donde cada nodo viaja con su hueso. La cabeza y el cuello del fémur se modelan como obstáculos analíticos (`bone_surfaces`: esfera de 22 mm y cápsula de 15 mm de radio a 1,75 m; **convención** con el centro de los rangos publicados de diámetro de cabeza 38–48 mm y de cuello 28–34 mm, leídos en resúmenes de búsqueda). Las inserciones pasan del eje del cuello (dentro del hueso) a su superficie, a 1 mm por fuera; el pubofemoral lleva una guía en la cara medial-inferior de la cabeza (a 6 mm de su superficie) para pasar bajo ella. En Blender estos tres ligamentos son mallas deformadas por la armadura (cada anillo pesa 100 % sobre el hueso de su nodo): siguen al fémur. El resto sigue rígido.

- Barrido de la cadera (`ligament_paths.HIP_SWEEP`): flexión 30/60/90/120, extensión 15, abducción 45, aducción 30, rotaciones ±40 y tres combinaciones. Ninguna poligonal entra en el hueso (margen mínimo ≈ 0,9 mm a 1,75 m) a 1,50, 1,75 y 2,05 m, ni en el modelo ni en el Blender evaluado.
- Propiedades mecánicas: **sin datos** de rigidez ni longitud sin tensión en fuentes abiertas; cada ligamento lleva `mechanics.status = convencion_parametrica_declarada` con valores nulos (una prueba impide rellenarlos sin fuente). El modelo da geometría y envoltura, no fuerzas.
- Las longitudes cambian mucho en el barrido (el iliofemoral se acorta en flexión; el isquiofemoral se alarga hasta un 40 % en abducción): son rectas entre nodos, no un modelo de tensión.

## Pruebas

`test_hip_ligament_paths` (barrido, mutaciones, validación), `test_hip_ligament_blender` (FK frente a Blender, control negativo), `test_spine_ligaments`, `test_thorax_ligaments`, `test_pelvic_floor`, `test_hand_foot_ligaments` (incluye la cobertura global), `test_pelvis_closure`, `test_anchor_debt`. Documento: `docs/ligamentos_articulaciones_modelo_completo.md`.

## Pendiente

- Guías de envoltura y deformación con la armadura solo en los tres ligamentos de la cadera; el resto de ligamentos que cruzan una articulación (rodilla, tobillo, hombro...) siguen siendo un segmento rígido emparentado al hueso de origen.
- Verificar en un atlas los costotransversos y los de los dedos del pie.
- Reducir los 58 anclajes antiguos a más de 12 mm.
