# Plan: torso (columna, tórax y abdomen), prioridad 3

Estado de partida: columna, costillas y esternón **completos** (huesos, 23 niveles de ligamentos, cartílago costal, facetarias); los músculos del torso tienen pocos vientres y todos con volumen por convención salvo el pectoral mayor y el dorsal ancho. Estado detallado: [../estado/torso.md](../estado/torso.md).

## Qué hay hoy

| Capa | Contenido |
|---|---|
| Huesos | C7 a L5 (T1–T12, L1–L5), 12 costillas con cartílago, esternón, sacro |
| Articulaciones | 46 cigapofisarias, intervertebrales, costovertebrales, costotransversas, esternocostales, interchondrales, manubrioesternal y xifoesternal |
| Ligamentos | 139 de la columna, 154 del tórax y el hombro |
| Tendones y músculos | recto del abdomen, dorsal ancho, pectorales, trapecio (3), romboides, serrato, elevador de la escápula, cuadrado lumbar, iliocostal, psoas |

## Huecos concretos

1. **Deuda de anclaje: 23 de los 61** anclajes antiguos están aquí (costovertebrales y costotransversas a 21–39 mm de la vértebra, que no tiene anchura).
2. **Vértebras sin anchura** (cuerpo, láminas, apófisis): los puntos van a 8–11 mm del eje. Sin ellas, las costotransversas, el amarillo y el interespinoso no están sobre el hueso real.
3. **Volúmenes**: el erector de la columna, el multífido, los oblicuos, el transverso, el diafragma y el psoas no tienen volumen; trapecio y recto del abdomen, por convención.
4. **Músculos que faltan**: oblicuos externo e interno, transverso del abdomen, diafragma, erector (espinoso, longísimo), multífidos, intercostales, serrato posterior, escalenos, pectoral menor ya añadido.
5. **ROM de la columna**: el rig la representa con 3 segmentos (lumbar, torácico, torácico alto) y no reparte el movimiento por disco; los rangos por nivel (Dvorak, cervical por nivel) están como datos.
6. **Ligamentos**: el supraespinoso y el nucal con fuente débil; el amarillo y los longitudinales sin puntos intermedios que sigan la lordosis.

## Pasos

| ID | Paso | Entrega | Criterio de aceptación |
|---|---|---|---|
| TO-1 | Anchura de las vértebras (cuerpo, pedículo, lámina y apófisis) paramétrica por nivel | contorno o volumen en `spine_head.json` | los puntos de los ligamentos y las costillas quedan sobre el hueso real a < 12 mm |
| TO-2 | Mover las costovertebrales y costotransversas a las facetas costales | centros sobre la vértebra | sale de `KNOWN_DEBT` (23 anclajes) |
| TO-3 | Volúmenes medidos del tronco | RM abierta (por ejemplo la base de 70 músculos de 2025, cuyo contenido no se ha leído) | cada valor con fuente, o convención declarada |
| TO-4 | Músculos de la pared abdominal y del dorso | unidades con hitos óseos en costillas, cresta ilíaca, línea alba (fascia) y apófisis espinosas | origen e inserción a < 12 mm; fascia anclada a su destino óseo |
| TO-5 | Diafragma | modelo simplificado con inserciones costales, vertebrales y esternal | cierra la cavidad sin atravesar costillas ni columna |
| TO-6 | Reparto del movimiento por nivel (capa de poses) | tabla segmento base → niveles con fracciones | la suma por nivel respeta el límite de la base |
| TO-7 | Cierre | estado y avances actualizados | suite en verde |

## Investigación

- **Morfometría vertebral**: dimensiones del cuerpo, pedículo y lámina por nivel (estudios de TC) para un adulto de 1,75 m.
- **ROM por nivel**: Dvorak 1991 y Pearcy 1984 (lumbar, ya usados), Panjabi y Zhao 2013 (cervical); torácica a buscar.
- **Volúmenes**: RM del tronco; erector y multífido tienen estudios propios (por ejemplo los de atrofia lumbar).

## Pruebas nuevas previstas

- Cada punto de ligamento y de costilla a < 12 mm de la vértebra con anchura; el cuerpo vertebral escala con la altura.
- Las costillas siguen articuladas con su faceta costal al variar la altura.
- Mutación: reducir la anchura de una vértebra a cero debe hacer fallar los ligamentos amarillo e interespinoso.
