# Plantilla de investigación por región

Guion para pulir una región del modelo con fuentes primarias. Se rellena **una región cada vez** (por ejemplo: extremidad inferior —muslo y cadera—, antebrazo y mano, o columna y cuello) y el resultado se anota en `docs/avances/`.

## Los cuatro ejes

1. **Dimensiones y morfometría reales**: rangos de longitud, diámetro y volumen óseo y muscular para un adulto de referencia (1,75 m / 70 kg). Volúmenes musculares en cm³ **solo de resonancia magnética publicada** (Holzbaur 2007, Ward 2009, Handsfield 2014…); donde no exista, convención visual declarada como tal.
2. **Ligamentos y puntos de tensado**: origen e inserción sobre hitos óseos y puntos intermedios para que no atraviesen el hueso al articular.
3. **Tendones y rutas de guía**: trayectoria del vientre a la inserción y guías óseas o retináculos (túnel carpiano, correderas maleolares, surco intertubercular…).
4. **Límites articulares y ROM**: grados de libertad y límites en grados para flexión, extensión, abducción, aducción y rotaciones.

## Entregables de cada región

1. Resumen con las fuentes consultadas, su fiabilidad (alta, media o baja) y los valores numéricos extraídos.
2. JSON en `config/anatomy/` (huesos), `config/articulations/` (articulaciones, ligamentos, hitos) o `config/muscles/` (tendones y volúmenes).
3. Pruebas: anclajes a **< 12 mm** de la superficie del hueso, mutaciones detectadas y suite completa en verde.
4. Actualizar el documento de la capa en `docs/avances/` (qué cambió y qué queda pendiente).

## Estado de partida y huecos conocidos

- Datos de volumen **medidos**: miembro superior, pectoral mayor y dorsal ancho (Holzbaur 2007).
- **Sin volúmenes medidos**: pierna (Handsfield 2014 y Ward 2009 no fueron accesibles), trapecio, pectoral menor, recto del abdomen y esternocleidomastoideo.
- Ligamentos sin puntos de tensado intermedios; tendones con longitud por convención visual.

## Región pedida

*(sin especificar todavía)*
