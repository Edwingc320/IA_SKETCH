# Plan de construcción: visión general

Plan por regiones del cuerpo para completar y pulir el modelo. Cada región tiene su **plan detallado** (`docs/plan/`) y su **archivo de estado** con casillas (`docs/estado/`). Los avances por capa están en `docs/avances/`. Fecha: 2026-10-25.

## Orden de ejecución

| Prioridad | Región | Plan | Estado | Por qué en este orden |
|---|---|---|---|---|
| 1 | **Caderas, pelvis y muslo** | [30_caderas_muslo.md](30_caderas_muslo.md) | [caderas_muslo.md](../estado/caderas_muslo.md) | es la sugerencia: mayor hueco de datos (cero volúmenes medidos en la pierna) y la cadera es el pivote del tronco y la pierna |
| 2 | **Tren superior** (hombro, brazo, antebrazo, mano) | [10_tren_superior.md](10_tren_superior.md) | [tren_superior.md](../estado/tren_superior.md) | mejor dato disponible (Holzbaur 2007): se puede pulir con poco riesgo |
| 3 | **Torso** (columna, tórax, abdomen) | [20_torso.md](20_torso.md) | [torso.md](../estado/torso.md) | más deuda de anclaje (23 de 61) y sin volúmenes medidos |
| 4 | Pierna y pie | [40_pierna_pie.md](40_pierna_pie.md) | [pierna_pie.md](../estado/pierna_pie.md) | depende de los volúmenes de la pierna (misma investigación que la prioridad 1) |
| 5 | Cabeza y cuello | [50_cabeza_cuello.md](50_cabeza_cuello.md) | [cabeza_cuello.md](../estado/cabeza_cuello.md) | menos músculos modelados; ATM sin rig |
| 6 | Piel | [60_piel.md](60_piel.md) | [piel.md](../estado/piel.md) | depende de todo lo anterior y de la capa de poses |

## Estado actual por región

Cifras medidas del repositorio (lado izquierdo; el derecho es simétrico). Los huesos se cuentan en el nivel 1; articulaciones por hueso portador, ligamentos por hueso de origen, tendones por hueso de inserción. «Volumen medido/convención» cuenta los vientres con volumen. «Sin fuente / fuente baja» son tendones sin ninguna fuente consultada o apoyados solo en fuentes de fiabilidad baja. «Deuda 12 mm» son anclajes antiguos a más de 12 mm de su hueso.

| Región | Huesos | Articulaciones | Ligamentos | Hitos | Tendones | Volumen medido / convención | Sin fuente / fuente baja | Deuda 12 mm |
|---|---|---|---|---|---|---|---|---|
| Cabeza y cuello | 9 | 13 | 41 | 13 | 3 | 0 / 1 | 2 / 0 | 5 |
| Torso y columna | 30 | 69 | 158 | 1 | 3 | 0 / 1 | 2 / 0 | 23 |
| Hombro | 1 | 3 | 13 | 14 | 8 | 0 / 4 | 1 / 0 | 0 |
| Brazo | 1 | 0 | 3 | 5 | 11 | 11 / 0 | 5 / 0 | 0 |
| Antebrazo | 2 | 3 | 7 | 4 | 8 | 8 / 0 | 6 / 0 | 10 |
| Mano | 27 | 22 | 43 | 8 | 21 | 5 / 0 | 0 / 0 | 5 |
| Caderas y pelvis | 5 | 6 | 13 | 15 | 0 | 0 / 0 | 0 / 0 | 0 |
| Muslo | 2 | 1 | 5 | 6 | 8 | 0 / 4 | 4 / 4 | 4 |
| Pierna | 2 | 3 | 12 | 6 | 7 | 0 / 4 | 3 / 4 | 9 |
| Pie | 26 | 27 | 69 | 9 | 17 | 0 / 6 | 2 / 11 | 5 |

Lectura: los huesos, las articulaciones y los ligamentos están **completos** en todas las regiones; lo que falta es **calidad de dato** (fuentes, volúmenes medidos, puntos de tensado) y **la capa de poses**. «Caderas y pelvis» no tiene tendones porque los músculos pélvicos con inserción en la pelvis se cuentan en el muslo (por su hueso de inserción) y los glúteos viven en la capa muscular anterior.

## Capas y qué significa «hecho»

| Capa | Hecho cuando… |
|---|---|
| Huesos | los puntos clave del hueso (accidentes óseos con nombre) existen como hitos y escalan con `--height`; las longitudes y diámetros caen en el rango publicado para 1,75 m / 70 kg |
| Articulaciones | cada grado de libertad tiene rango con fuente primaria o `no_numeric_source`; pivote exacto en la cabeza del hueso hijo; límites en Blender |
| Ligamentos | origen e inserción sobre hitos a < 12 mm; **puntos de tensado intermedios** donde el ligamento rodea hueso; fuente alta o media (o nota «verificar») |
| Tendones | ruta completa vientre → inserción con **todas** las guías óseas o retináculos; longitud con fuente (si no, convención declarada) |
| Músculos | volumen **medido** en cm³ con fuente de resonancia, a la altura de sus sujetos, y la malla con volumen exacto |
| Piel | espesor y perímetros por región con fuente antropométrica y malla atada al rig |

## Fases transversales

1. **F0 — Infraestructura (hecha):** golden de la base, escala por altura, regla de 12 mm con trinquete, mutaciones, ramas `main` y `muscle-model`.
2. **F1 — Datos:** investigación por región con la plantilla (`docs/plantilla_investigacion_region.md`); se vuelcan las cifras a JSON con su fuente y fiabilidad.
3. **F2 — Geometría fina:** puntos de tensado de ligamentos, rutas de tendón con más guías, secciones con forma anatómica, colisión.
4. **F3 — Capa de poses del nivel 1:** FK genérica, reparto del movimiento (columna, ATM, dedos) y deformación de músculos, tendones y ligamentos con la pose. **Bloquea** la deformación de la piel.
5. **F4 — Piel.**

## Reglas que se mantienen en todo el plan

- Capas independientes: `main` es el modelo óseo; `muscle-model` añade músculos y tendones.
- Nada se inventa: sin cifra en las fuentes → vacío; convenciones visuales declaradas como tales.
- Todo anclaje nuevo a < 12 mm; mutaciones por cada comprobación; un commit por sección; suite completa en verde; actualizar `docs/estado/` y `docs/avances/`.
- La investigación se hace **una región cada vez** con la plantilla; sus resultados no se mezclan entre regiones.

## Riesgos

- **Volúmenes de la pierna inaccesibles** (Handsfield 2014 de pago; servidor de Ward 2009 caído): alternativas en `30_caderas_muslo.md`.
- La generación en Blender tarda ~29 s y la suite ~4 min: conviene optimizar el sondeo de emparentado antes de añadir más objetos.
- El escalado isométrico del volumen (k³) es una hipótesis: en adultos reales la talla explica solo parte del volumen muscular.
