# Músculos (volumen de los vientres)

**Rama:** `muscle-model` · **Estado:** 44 vientres por lado con volumen (88), más los glúteos de la capa anterior.

## Qué hay

| Grupo | Volumen |
|---|---|
| Hombro, brazo, antebrazo, pectoral mayor, dorsal ancho, manguito rotador | **medido** (Holzbaur 2007; 10 adultos, altura media 171,5 cm) |
| Cuádriceps, isquiotibiales, pantorrilla, trapecio, pectoral menor, recto del abdomen, esternocleidomastoideo | **convención visual** declarada (40 / 150 / 350 / 700 cm³ a 1,75 m): no se consiguieron volúmenes medidos |

Modelo: husillo cerrado a lo largo del vientre (sección circular o aplanada, perfil `sin(πu)^0,7`), con el radio calibrado para que el volumen sea exacto. Con `--height` el volumen escala con k³ (isométrico, hipótesis declarada). Sigue a su hueso de origen; no se deforma con la pose ni colisiona.

## Pruebas

`test_muscles` (glúteos), `test_muscle_volumes`. Documentos: `docs/musculos_gluteos.md`, `docs/volumenes_musculares.md`.

## Pendiente (investigación por región)

- **Volúmenes medidos de la pierna** (Handsfield 2014, Ward 2009): los artículos no fueron accesibles. Es el hueco más importante.
- Verificar braquial y bíceps (ambos 143,7 cm³ al extraer la tabla del PDF).
- Colisión entre músculos y con el hueso; secciones con forma anatómica; deformación con la pose.
- Músculos del resto del cuerpo (intrínsecos de la mano y del pie, cara, cuello profundo, diafragma, suelo pélvico).
