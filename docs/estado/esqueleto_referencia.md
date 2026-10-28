# Estado: esqueleto sólido idéntico a la imagen de referencia

Plan: [../plan/70_esqueleto_referencia.md](../plan/70_esqueleto_referencia.md) · Prioridad: **nueva dirección (2026-10-28)**, por encima del orden regional de `00_plan_general.md` · Estado general: **F0, F1 y F2 hechas; siguiente: F3 (caja torácica)**.

## Lista de tareas

- [x] **F0** Banco de comparación y línea base (`scripts/render_bones_silhouette.py`, `scripts/compare_reference.py`): IoU medio 0,35 (frente 0,36, espalda 0,37, lado 0,32)
- [x] **F1** Núcleo de mallas óseas — `bone_meshes.py` (loft de secciones elípticas con trayectoria Catmull-Rom, casquetes, marco por transporte paralelo, isométrico), `bone_meshes_scene.py` (objetos `BM_<hueso>` colgados de su hueso, relleno gris y contorno oscuro por casco invertido), validación (cerrada, volumen, simetría, snapshot de Blender) y **primer hueso: el fémur** (514 cm³ a 1,75 m; los siete hitos del fémur a ≤ 9 mm de su superficie). Pendiente de F1 declarado: láminas (pelvis, escápula) y tubos aplanados (costillas) se añaden en sus fases
- [x] **F2** Pelvis y sacro (+ **F2b articulación coxofemoral**: copa acetabular roja de 23,5–31,5 mm con 1,5 mm de interlínea sobre la cabeza femoral, techo acetabular que la funde con la lámina del ilion, marco poligonal del agujero obturador —`slab` con agujero poligonal—, disco de la sínfisis del pubis, unión cabeza-cuello del fémur más gradual y pelvis en tono hueso; 17 mallas) — ilion y sacro como láminas con grosor (`kind: slab`: contorno + agujeros, proyección al plano de Newell, triangulación por orejas con puentes a los agujeros, ±grosor/2, paredes, `bend` opcional); pubis, isquion y cóccix como lofts. 10 mallas con el fémur; género = número de agujeros (sacro 8: cuatro pares de agujeros sacros reales; Euler 2−2·género). Anillo pélvico cerrado (sínfisis, rama isquiopubiana, sacroilíaca), agujero obturador vacío, hitos pélvicos a < 12 mm a 1,50/1,75/2,05 m. Sombreado plano en láminas. Ligamentos y orígenes musculares sin tocar. IoU medio 0,37 → 0,40 (frente 0,42, espalda 0,43, lado 0,34). 28 pruebas (con Blender) y 11 mutaciones `bmesh_*` detectadas
- [ ] **F3** Caja torácica
- [ ] **F4** Columna
- [ ] **F5** Cráneo y mandíbula
- [ ] **F6** Cintura escapular, húmero, radio y cúbito
- [ ] **F7** Mano
- [ ] **F8** Fémur, rótula, tibia y peroné
- [ ] **F9** Pie
- [ ] **F10** Ensamblaje, pose y verificación final (IoU ≥ 0,75)

## Decisiones (2026-10-28, del usuario)

1. **Qué manda**: los **datos antropométricos** (Drillis y Contini a 1,75 m) mandan en las **longitudes de los segmentos óseos** (así el modelo sigue siendo 100 % parametrizable con `--height` y respeta la tolerancia de 12 mm y las pruebas); la **imagen** manda en la **forma, la silueta y la postura de referencia** (contornos, perfiles, alineamiento relativo). Cada discrepancia o caso límite (brazos separados del tronco, rotación de los pies) se evalúa **por sección** y se documenta como ajuste o limitación.
2. **Alcance de «idéntico»**: **forma y silueta + estilo** (relleno gris liso y contorno oscuro); no se imita el sombreado ni las rugosidades del dibujo. Se mide con la silueta en las tres vistas.

## Registro

| Fecha | Cambio |
|---|---|
| 2026-10-28 | Análisis de la imagen (3 vistas, 1083 × 1300, stock con marca de agua), comparador de siluetas y línea base (IoU 0,35). Hallazgo: las proporciones generales del modelo parecen coincidir con la imagen (a ojo; sin medir) pero los huesos son líneas y octaedros: falta toda la forma ósea. Plan por fases F0–F10. La imagen se añade a `.gitignore`. |
| 2026-10-28 | Decisiones del usuario: los datos antropométricos mandan en las longitudes y la imagen en la forma, silueta y postura (discrepancias por sección); «idéntico» = forma y silueta + estilo. F1: loft de secciones elípticas, primer hueso (fémur L/R), estilo de la imagen en Blender, 15 pruebas (13 puras y 2 de Blender) y 4 mutaciones detectadas. IoU medio con el fémur: 0,35 → 0,37 (frente 0,39, espalda 0,40, lado 0,32). **Discrepancia anotada para F8**: en la imagen los fémures convergen hacia las rodillas (ángulo bicondíleo), mientras el modelo tiene el eje mecánico vertical (cabeza y rodilla a la misma x); se decidirá en F8. |
| 2026-10-28 | F2 (pelvis y sacro): láminas (`slab`) para ilion y sacro, lofts para pubis, isquion y cóccix; 10 mallas, sacro de género 8. **Límites declarados**: la interlínea sacroilíaca del modelo es de ~8 mm (real 2–4 mm; la prueba tolera 10 mm); el contorno del sacro tiene un empuje lateral de hasta ~5 mm (simétrico a ±6 mm, no exacto); los hitos pélvicos de `body_center_of_mass` y centros de gravedad no son de hueso y se excluyen. IoU medio 0,37 → 0,40 (prev. 0,3683 → 0,3961). Una cota de la lámina degenerada ahora da `ConfigError` (antes `ValueError`). Solo se corrió lo modificado: `test_bone_meshes` (puras y Blender) y `-k bmesh`; no la suite completa. |
| 2026-10-28 | F2b (articulación coxofemoral): `kind: cup` (casquete esférico grueso, semiángulo 100°, polo hacia medial-atrás-arriba, abierta hacia lateral-delante-abajo), `acetabular_roof` (puente macizo entre la lámina del ilion y el polo de la copa), `obturator_frame` (lámina de 4 mm con borde poligonal de 12 lados, empotrada 7 mm y con labio de 3,5 mm; el agujero queda vacío) y `pubic_symphysis`. Cada malla lleva `bone` (hueso del que cuelga), `tone` (`grey`, `bone`, `joint`) y `smooth`. **Estilo (decisión del usuario para esta región)**: pelvis y sacro en tono hueso (0,95/0,92/0,84), copa en rojo (0,80/0,10/0,10), marco obturador y sínfisis en gris liso con contorno oscuro; el fémur sigue gris. **Límites declarados**: la copa no tiene la escotadura acetabular ni la fosa acetabular; el techo es un cilindro de ~12 mm, no una cresta; el marco obturador es una lámina plana (el anillo real es alabeado). IoU medio 0,396 → 0,402 (frente 0,425, espalda 0,434, lado 0,346). Pruebas: `test_bone_meshes` 42 (con Blender); mutaciones `bmesh_*` 22. No se corrió la suite completa. |
