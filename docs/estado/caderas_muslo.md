# Estado: caderas, pelvis y muslo

Plan: [../plan/30_caderas_muslo.md](../plan/30_caderas_muslo.md) · Prioridad **1** · Actualizado: 2026-10-25 · Estado general: **datos pendientes** (geometría y estructura completas).

## Por capa

| Capa | Estado | Detalle |
|---|---|---|
| Huesos | ✅ completo | pelvis cerrada, fémur con accidentes, rótula |
| Articulaciones | ✅ completo | rig `hip` con límites; ROM de extensión por revisar |
| Ligamentos | 🟡 completo en estructura | sin puntos de tensado intermedios |
| Tendones | 🟡 | 8 unidades en el muslo; 4 sin fuente y 4 con fuente baja |
| Músculos (volumen) | 🔴 convención | registro CM-1 con 5 vientres de pierna/muslo y 2 glúteos medidos en la literatura, aún sin aplicar al modelo (CM-2); glúteos sin volumen en el modelo |
| Deuda de anclaje | 🟡 | 4 anclajes antiguos a > 12 mm |

## Lista de tareas

- [~] **CM-1** Conseguir volúmenes del muslo y la cadera con fuente de RM abierta — **parcial**: registro en `config/muscles/volume_measurements.json` (5 fuentes con DOI). Verificados: vasto lateral, una cabeza del bíceps femoral, gastrocnemio medial y lateral, tibial anterior (Ritsche 2025, adultos jóvenes), proporciones del cuádriceps (Trappe 2001) y glúteos mediano/menor (Kajdi 2025, pacientes de 65 años: no es la población de referencia). Sin encontrar: glúteo mayor, semitendinoso, semimembranoso, aductores, grácil, sartorio, TFL, psoas, ilíaco, sóleo, peroneos. Quedan abiertos Handsfield 2014, Ward 2009 y Lube 2016 (tablas inaccesibles)
- [ ] **CM-2** Sustituir las clases por volúmenes medidos
- [ ] **CM-3** Volumen de los glúteos
- [ ] **CM-4** Puntos de tensado de los ligamentos de la cadera
- [ ] **CM-5** Rutas completas del psoas-ilíaco y la cintilla iliotibial
- [ ] **CM-6** Músculos que faltan (aductor corto, pectíneo, obturadores, piriforme, cuadrado femoral)
- [ ] **CM-7** ROM de la cadera revisado
- [ ] **CM-8** Reducir la deuda de anclaje del muslo
- [ ] **CM-9** Cierre de la región

## Registro

| Fecha | Cambio |
|---|---|
| 2026-10-25 | Plan y estado creados. Intento de obtener Handsfield 2014 y Ward 2009: sin acceso (de pago / servidor caído). |
| 2026-10-25 | CM-1 parcial: `volume_measurements.json` + `tests/test_volume_measurements.py` (9 pruebas, 4 mutaciones detectadas). Hallazgo: las clases de convención sobrestiman lo medido (tibial anterior 350 frente a 119,4 cm³). Cifras derivadas (RF, VI, VM) y la de Takahashi (aductor mayor) quedan marcadas como no verificadas. |
