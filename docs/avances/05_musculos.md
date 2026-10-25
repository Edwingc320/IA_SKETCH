# Músculos (volumen de los vientres)

**Rama:** `muscle-model` · **Estado:** 47 vientres por lado con volumen (94): los 44 de las unidades músculo-tendinosas y los 3 glúteos.

## Qué hay

| Grupo | Volumen |
|---|---|
| Hombro, brazo, antebrazo, pectoral mayor, dorsal ancho, manguito rotador | **medido** (Holzbaur 2007; 10 adultos, altura media 171,5 cm) |
| **Vasto lateral, bíceps femoral (cabeza larga, hipótesis), gastrocnemio medial y lateral, tibial anterior** | **medido** (Ritsche 2025, RM, adultos jóvenes; altura de referencia 1,75 m **asumida**: la fuente no la publica) |
| **Glúteo mediano y menor** | **medido** (Kajdi 2025, media simple de mujeres y hombres; **cohorte de 65 años con dolor trocantérico: probablemente subestima**; 1,75 m asumida) |
| Glúteo mayor | **convención visual** (muy grande, 700 cm³) |
| Resto del cuádriceps (recto femoral, vasto intermedio y medial), isquiotibiales mediales, sóleo, trapecio, pectoral menor, recto del abdomen, esternocleidomastoideo | **convención visual** declarada (40 / 150 / 350 / 700 cm³ a 1,75 m): no se consiguieron volúmenes medidos |

Modelo: husillo cerrado a lo largo del vientre (sección circular o aplanada, perfil `sin(πu)^0,7`), con el radio calibrado para que el volumen sea exacto. Con `--height` el volumen escala con k³ (isométrico, hipótesis declarada). Sigue a su hueso de origen; no se deforma con la pose ni colisiona.

## Pruebas

`test_muscles` (glúteos), `test_muscle_volumes`. Documentos: `docs/musculos_gluteos.md`, `docs/volumenes_musculares.md`.

## Registro de mediciones de la literatura (CM-1)

`config/muscles/volume_measurements.json` recoge volúmenes con fuente, población y estado de verificación. Solo las cifras verificadas con unidad de vientre (los cinco de Ritsche) pasan a `muscle_volumes.json` (CM-2); los derivados y lo no verificado no, con una excepción declarada (CM-3): las medias de mujeres y hombres de Kajdi para el glúteo mediano (339,1) y el menor (92,15), marcadas `applied_in_model`. Verificados: vasto lateral 636,5, bíceps femoral (una cabeza) 197,4, gastrocnemio medial 224,7 y lateral 112,6, tibial anterior 119,4 cm³ (Ritsche 2025, jóvenes); proporciones del cuádriceps (Trappe 2001); glúteo mediano 270,1/408,1 y menor 77,2/107,1 cm³ en mujeres/hombres de 65 años con dolor trocantérico (Kajdi 2025). Derivados y marcados como estimación: recto femoral, vasto intermedio y medial. La convención actual sobrestima: tibial anterior 350 frente a 119,4.

## Pendiente (investigación por región)

- **Volúmenes medidos del resto de la pierna y el muslo** (Handsfield 2014, Ward 2009): los artículos no fueron accesibles; solo cinco vientres tienen dato (CM-2).
- Verificar braquial y bíceps (ambos 143,7 cm³ al extraer la tabla del PDF).
- Colisión entre músculos y con el hueso; secciones con forma anatómica; deformación con la pose.
- Músculos del resto del cuerpo (intrínsecos de la mano y del pie, cara, cuello profundo, diafragma, suelo pélvico).
