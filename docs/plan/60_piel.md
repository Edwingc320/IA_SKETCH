# Plan: piel, prioridad 6

Estado detallado: [../estado/piel.md](../estado/piel.md). **No iniciada**; es la última porque depende de todas las capas anteriores.

## Dependencias

| Necesita | Estado |
|---|---|
| Huesos, articulaciones y ligamentos | completos |
| Músculos con volumen medido | parciales: miembro superior y tronco superior medidos; **pierna por convención** |
| Capa de poses del nivel 1 (para que la piel siga a huesos y músculos) | viable, no construida |
| Datos antropométricos de espesor de piel y tejido subcutáneo y de perímetros | **sin consultar** |

## Decisiones previas

1. **Tipo de piel**: malla envolvente paramétrica (como el cráneo y los vientres) frente a malla externa atada con pesos. La envolvente paramétrica escala con `--height` por construcción; una malla externa exige reajustar pesos.
2. **Referencia**: adulto de 1,75 m / 70 kg; escalar con la altura y, si se quiere, con la masa (hoy solo hay altura).
3. **Qué se mide**: espesor de piel y de grasa subcutánea por región, perímetros del segmento (cuello, tórax, cintura, cadera, muslo, pantorrilla, brazo, antebrazo, muñeca) y su relación con la altura, siempre con fuente antropométrica.

## Pasos

| ID | Paso | Criterio de aceptación |
|---|---|---|
| PI-1 | Investigar espesores y perímetros con fuente | tabla con valor, unidad, población y fiabilidad; lo no encontrado, convención declarada |
| PI-2 | Piel como superficie envolvente de los volúmenes y huesos | malla cerrada que contiene todos los vientres y huesos con holgura ≥ espesor |
| PI-3 | Escala | a 1,50 y 2,05 m la piel escala con la altura y sigue conteniendo todo |
| PI-4 | Atado al rig | la piel sigue a la pose sin atravesar huesos |
| PI-5 | Cierre | rama propia, estado, avances y pruebas con mutaciones |

## Riesgos

- Sin volúmenes medidos de la pierna, la piel de la pierna heredará una convención: debe declararse.
- Sin la capa de poses del nivel 1 no hay deformación; solo se puede entregar piel estática en la pose A y en neutro.
