# Estado: esqueleto sólido idéntico a la imagen de referencia

Plan: [../plan/70_esqueleto_referencia.md](../plan/70_esqueleto_referencia.md) · Prioridad: **nueva dirección (2026-10-28)**, por encima del orden regional de `00_plan_general.md` · Estado general: **F0 y F1 hechas; siguiente: F2 (pelvis y sacro)**.

## Lista de tareas

- [x] **F0** Banco de comparación y línea base (`scripts/render_bones_silhouette.py`, `scripts/compare_reference.py`): IoU medio 0,35 (frente 0,36, espalda 0,37, lado 0,32)
- [x] **F1** Núcleo de mallas óseas — `bone_meshes.py` (loft de secciones elípticas con trayectoria Catmull-Rom, casquetes, marco por transporte paralelo, isométrico), `bone_meshes_scene.py` (objetos `BM_<hueso>` colgados de su hueso, relleno gris y contorno oscuro por casco invertido), validación (cerrada, volumen, simetría, snapshot de Blender) y **primer hueso: el fémur** (514 cm³ a 1,75 m; los siete hitos del fémur a ≤ 9 mm de su superficie). Pendiente de F1 declarado: láminas (pelvis, escápula) y tubos aplanados (costillas) se añaden en sus fases
- [ ] **F2** Pelvis y sacro
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
