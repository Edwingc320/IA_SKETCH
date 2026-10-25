# Estado: caderas, pelvis y muslo

Plan: [../plan/30_caderas_muslo.md](../plan/30_caderas_muslo.md) · Prioridad **1** · Actualizado: 2026-10-25 · Estado general: **datos pendientes** (geometría y estructura completas).

## Por capa

| Capa | Estado | Detalle |
|---|---|---|
| Huesos | ✅ completo | pelvis cerrada, fémur con accidentes, rótula |
| Articulaciones | ✅ completo | rig `hip` con límites; ROM de extensión por revisar |
| Ligamentos | ✅ con envoltura | iliofemoral, pubofemoral e isquiofemoral con guías y sin atravesar el fémur en el barrido; sin valores mecánicos (convención declarada) |
| Tendones | 🟡 | 8 unidades en el muslo; 4 sin fuente y 4 con fuente baja |
| Músculos (volumen) | 🔴 convención | cero medidos; glúteos sin volumen |
| Deuda de anclaje | 🟡 | 4 anclajes antiguos a > 12 mm |

## Lista de tareas

- [ ] **CM-1** Conseguir volúmenes del muslo y la cadera con fuente de RM abierta
- [ ] **CM-2** Sustituir las clases por volúmenes medidos
- [ ] **CM-3** Volumen de los glúteos
- [x] **CM-4** Puntos de tensado de los ligamentos de la cadera — guías de envoltura (`via`), obstáculos de cabeza y cuello del fémur, ligamentos deformados por la armadura en Blender; propiedades mecánicas como convención paramétrica declarada (ver `docs/avances/03_ligamentos.md`)
- [ ] **CM-5** Rutas completas del psoas-ilíaco y la cintilla iliotibial
- [ ] **CM-6** Músculos que faltan (aductor corto, pectíneo, obturadores, piriforme, cuadrado femoral)
- [ ] **CM-7** ROM de la cadera revisado
- [ ] **CM-8** Reducir la deuda de anclaje del muslo
- [ ] **CM-9** Cierre de la región

## Registro

| Fecha | Cambio |
|---|---|
| 2026-10-25 | Plan y estado creados. Intento de obtener Handsfield 2014 y Ward 2009: sin acceso (de pago / servidor caído). |
| 2026-10-25 | CM-4: `via`, `bone_surfaces`, `mechanics` y `deform` en los ligamentos; módulo `ligament_paths`; `bone_distance` acepta las superficies. Extremos del pubofemoral e isquiofemoral movidos del eje del cuello (dentro del hueso) a su superficie. Barrido de 13 poses × 3 alturas sin penetración. Nota: el rig permite extensión de 15° (límite de la base) mientras `articulations` documenta 10° (StatPearls): se revisa en CM-7. |
