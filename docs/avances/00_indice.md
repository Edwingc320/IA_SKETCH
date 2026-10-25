# Avances del proyecto por capa

Un documento por capa para consultar el estado de un vistazo. Se **agrega** al final de cada sesión de trabajo (fecha, qué cambió, qué quedó pendiente); no se reescribe el historial. Última actualización: **2026-10-25**.

| Capa | Documento | Rama | Estado |
|---|---|---|---|
| Esqueleto / huesos | [01_esqueleto_huesos.md](01_esqueleto_huesos.md) | `main` | completa: 185 huesos de la referencia (181 del nivel 1 más los de la base) |
| Articulaciones | [02_articulaciones.md](02_articulaciones.md) | `main` | completa: 19 de la base con 47 dof y 265 naturales |
| Ligamentos | [03_ligamentos.md](03_ligamentos.md) | `main` | completa: 620; todas las articulaciones tienen, salvo la escapulotorácica |
| Tendones | [04_tendones.md](04_tendones.md) | `muscle-model` | 86 unidades músculo-tendinosas por lado; longitud del tendón por convención |
| Músculos (volumen) | [05_musculos.md](05_musculos.md) | `muscle-model` | 44 vientres por lado; medido en miembro superior y tronco, convención en la pierna |
| Piel | [06_piel.md](06_piel.md) | — | **no iniciada** |

## Pruebas (2026-10-25)

| Rama | Pruebas en Blender | Pruebas de Python puro |
|---|---|---|
| `main` | 292 / 292 en verde | 292 (las que requieren Blender se omiten) |
| `muscle-model` | 320 / 320 en verde | 320 |

Remoto: `https://github.com/Edwingc320/IA_SKETCH.git` (`main`, `muscle-model` y el tag `v0.1.0`). Reglas: `AGENTS.md`. Decisiones y lecciones: `MEMORY.md`.

## Plan y estado por región

El plan de construcción por regiones (orden de ejecución, huecos, pasos y criterios de aceptación) está en [`docs/plan/00_plan_general.md`](../plan/00_plan_general.md) y el estado con casillas de cada región en `docs/estado/` (caderas y muslo, tren superior, torso, pierna y pie, cabeza y cuello, piel).

## Cómo se lee cada documento

Cada capa explica **qué hay** (con cifras reales), **dónde está** (archivos), **cómo se prueba**, **de dónde salen los números** (fuentes y su fiabilidad) y **qué falta**.
