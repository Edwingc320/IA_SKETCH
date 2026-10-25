# Volumen de los vientres musculares (rama `muscle-model`)

Los grandes grupos musculares tienen ahora **geometría y volumen**: cada vientre es una malla cerrada que sigue su línea músculo-tendinosa. Datos: `config/muscles/muscle_volumes.json`; código: `src/anatomical_core/muscle_volumes.py` y `muscle_volumes_scene.py`; pruebas: `tests/test_muscle_volumes.py`. Documentación de las capas anteriores: `docs/musculos_gluteos.md` y `docs/tendones.md`.

## Qué se modela

| Grupo | Unidades con volumen (por lado) | Volumen |
|---|---|---|
| **Cuádriceps** | recto femoral, vasto lateral, vasto medial, vasto intermedio | convención visual |
| **Isquiotibiales** | bíceps femoral (cabeza larga y **corta**), semitendinoso, semimembranoso | convención visual |
| **Pantorrilla y tobillo** | gastrocnemio medial y **lateral**, sóleo, tibial anterior, peroneo largo y corto | convención visual |
| **Hombro y brazo** | deltoides (clavicular, acromial, espinoso), bíceps (cabeza larga y corta), tríceps (**3 cabezas**), braquial, braquiorradial, coracobraquial, manguito rotador (4), redondo mayor | **medido** (Holzbaur 2007) |
| **Antebrazo** | pronador redondo, flexor radial y cubital del carpo, extensor radial largo y corto y cubital del carpo | **medido** |
| **Torso y cuello** | pectoral mayor y dorsal ancho | **medido** |
| | pectoral menor, trapecio (superior, **medio** e **inferior**), recto del abdomen, esternocleidomastoideo | convención visual |

44 vientres por lado (88 en total). Se **reutilizan las 160 unidades músculo-tendinosas** y sus guías óseas (túnel carpiano, maléolos, surco intertubercular…) y se **añaden 12** (6 por lado) que faltaban, con lo que la capa pasa a 172 unidades: tríceps lateral y medial (sustituyen a la cabeza humeral única), cabeza corta del bíceps femoral, gastrocnemio lateral, pectoral menor y trapecio medio e inferior.

## Geometría

El vientre es el tramo de la unidad entre sus dos uniones miotendinosas (los tendones quedan fuera). Se rellena con un husillo: anillos de sección circular o elíptica a lo largo de la poligonal, con perfil fusiforme `sin(πu)^0,7` (cero en los extremos y máximo hacia el centro). El **radio máximo se calibra para que la malla tenga exactamente el volumen declarado** (diferencia < 1e-9 en la prueba). Los músculos planos (pectoral, dorsal ancho, trapecio, recto del abdomen, infraespinoso, subescapular) llevan una sección aplanada con la relación ancho/grosor en `aspect` (el grosor mira a Y, antero-posterior; el volumen se conserva).

Las anclas siguen siendo las de la capa de tendones: sitios óseos a **menos de 12 mm de la superficie del hueso**; el husillo solo ocupa el tramo entre uniones. En Blender: `MUV_<unidad>`, suavizado, emparentado al hueso de origen. Es un dato: la malla no se deforma al mover los huesos todavía (al girar la cadera, el vasto lateral sigue al fémur entero).

## Volumen y `--height`

Las longitudes escalan con `k = H / H_ref` y **el volumen con k³** (escalado isométrico declarado): el radio del vientre escala con k, igual que la longitud. Probado: a 1,50 m el volumen es `(1,50/1,75)³` el de 1,75 m y los vértices son exactamente k veces los de 1,75 m. Hipótesis a revisar: en adultos reales la talla explica solo parte del volumen muscular (R² ≈ 0,64 en el muslo, [Handsfield 2014](https://pubmed.ncbi.nlm.nih.gov/24368144/)).

## De dónde salen los números

**Medidos** — tabla 2 de [Holzbaur et al. 2007, J Biomech 40:742-749](https://nmbl.stanford.edu/publications/pdf/Holzbaur2007a.pdf) (resonancia magnética de 10 adultos jóvenes, altura media 171,5 cm, volumen total medio 2554 cm³): deltoides 380,5; bíceps 143,7; tríceps 372,1; braquial 143,7; braquiorradial 65,1; pronador redondo 38,4; flexor radial del carpo 34,8; flexor cubital del carpo 37,1; extensor radial largo 37,5, corto 21,6 y cubital 17,0; pectoral mayor 290,0; dorsal ancho 262,3; supraespinoso 50,0; infraespinoso 118,6; subescapular 164,5; redondo menor 28,0 y mayor 32,7; coracobraquial 25,2 (cm³). El estudio da el deltoides, el bíceps y el tríceps **enteros**: se reparten **en partes iguales entre sus haces por convención**, y las notas lo dicen. Se escalan a la altura del modelo desde los 1,715 m de sus sujetos. Valores leídos del texto extraído del PDF; la maquetación a dos columnas del cuadro exige **verificar los volúmenes de braquial y bíceps** (ambos 143,7) con el artículo.

**Convención visual** (no son medidas): para todo lo que no se consiguió medido (pierna, trapecio, pectoral menor, recto del abdomen, esternocleidomastoideo) se usa una de cuatro clases de orden de magnitud a 1,75 m: **pequeño 40, medio 150, grande 350, muy grande 700 cm³**. No se consiguieron los volúmenes de la pierna: el artículo de Handsfield 2014 (35 músculos del miembro inferior por RM) no es de acceso abierto y el servidor del trabajo de Ward 2009 no respondió. Cuando se consigan, basta cambiar `kind` a `medido` y poner el volumen y la fuente; una prueba exige que todo lo convencional lo diga en su nota. **Las clases de la pierna son una estimación del orden de magnitud, no un dato.**

## Lo que no hace todavía

- No hay colisión entre músculos ni con el hueso: los husillos pueden solaparse en las zonas de origen común (p. ej. los tres vastos).
- La sección es circular o elíptica constante, sin forma anatómica propia (bipeniforme, multipeniforme, etc.).
- No se deforma con la pose.
