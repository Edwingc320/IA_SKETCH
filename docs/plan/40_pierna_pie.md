# Plan: pierna y pie, prioridad 4

Depende de la misma investigación de volúmenes que la prioridad 1 (la RM del miembro inferior es un único conjunto de datos). Estado detallado: [../estado/pierna_pie.md](../estado/pierna_pie.md).

## Qué hay hoy

| Capa | Contenido |
|---|---|
| Huesos | tibia, peroné; 7 huesos del tarso, 5 metatarsianos y 14 falanges (puntas de los dedos a 10,3 mm del suelo) |
| Articulaciones | tibioperoneas, tobillo, subastragalina, talonavicular, calcaneocuboidea, cuneonavicular, intercuneiformes, cuneocuboidea, tarsometatarsianas (5), MTF e IF de los dedos |
| Ligamentos | cruzados y colaterales de la rodilla, sindesmosis, deltoideo, laterales del tobillo, resorte, bifurcado, plantares, Lisfranc, fascia plantar (5 bandas), transversos profundos y colaterales y placas de los dedos |
| Tendones y músculos | gastrocnemio (2 cabezas), sóleo, tibial anterior y posterior, peroneos largo y corto, flexor largo del dedo gordo y de los dedos (×4), extensor largo del dedo gordo y de los dedos (×4) |

## Huecos concretos

1. **Volumen**: toda la pierna por convención; ningún vientre medido.
2. **Fuentes**: 11 tendones del pie apoyados solo en fuentes de fiabilidad baja y 3 en la pierna sin fuente; los peroneos y el flexor largo del dedo gordo (paso por el sustentaculum tali) sin fuente consultada.
3. **Ligamentos de los dedos del pie** por analogía con la mano (sin fuente propia).
4. **Rutas**: los retináculos extensor y flexor del tobillo y las vainas de los peroneos no están como guías; el tibial posterior inserta solo en el navicular (las fuentes añaden cuneiformes y metatarsianos 2–4).
5. **Músculos que faltan**: poplíteo, peroneo tercero, plantar, extensor corto de los dedos, intrínsecos del pie (abductor del dedo gordo, flexor corto, interóseos, lumbricales).
6. **Sesamoideos** del primer metatarsiano: fuera de la lista de 185 huesos; no modelados.
7. **ROM**: dorsiflexión del tobillo (20° frente a 30–40° según la fuente) e inversión (30–60°) con rangos que discrepan; la rotación axial de la rodilla solo en flexión se exige en la validación, no en Blender.
8. **Deuda de anclaje**: 9 en la pierna (cruzados, rotuliano, sindesmosis) y 5 en el pie.

## Pasos

| ID | Paso | Criterio de aceptación |
|---|---|---|
| PP-1 | Volúmenes medidos de la pierna (misma fuente que CM-1) | pantorrilla y compartimento anterior con cm³ y fuente |
| PP-2 | Fuentes de los tendones del pie y la pierna | cada tendón con fuente de fiabilidad media o alta, o «verificar» |
| PP-3 | Retináculos y vainas como guías | tendones de los peroneos, tibial posterior y flexores con guías a < 12 mm |
| PP-4 | Músculos que faltan | unidades con hitos óseos |
| PP-5 | Puntos de tensado de los ligamentos del tobillo y la rodilla | el deltoideo y los cruzados no atraviesan hueso entre 0 y el máximo de flexión |
| PP-6 | ROM del tobillo y la subastragalina con una sola convención (activo o pasivo) | tabla de decisiones |
| PP-7 | Deuda de anclaje | el trinquete baja 14 anclajes |
| PP-8 | Cierre | estado y avances actualizados; suite en verde |

## Investigación

RM del miembro inferior (candidatos: Handsfield 2014, la base de 70 músculos de 2025), anatomía de los retináculos y las vainas (atlas abiertos), modelos del miembro inferior (Arnold 2010) para rutas, y goniometría del tobillo y el pie.
