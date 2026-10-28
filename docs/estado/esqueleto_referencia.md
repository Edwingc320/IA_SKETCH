# Estado: esqueleto sólido idéntico a la imagen de referencia

Plan: [../plan/70_esqueleto_referencia.md](../plan/70_esqueleto_referencia.md) · Prioridad: **nueva dirección (2026-10-28)**, por encima del orden regional de `00_plan_general.md` · Estado general: **F0 hecha; F1 sin empezar; a la espera de dos decisiones**.

## Lista de tareas

- [x] **F0** Banco de comparación y línea base (`scripts/render_bones_silhouette.py`, `scripts/compare_reference.py`): IoU medio 0,35 (frente 0,36, espalda 0,37, lado 0,32)
- [ ] **F1** Núcleo de mallas óseas (lofts, láminas, tubos), estilo de la imagen, validación
- [ ] **F2** Pelvis y sacro
- [ ] **F3** Caja torácica
- [ ] **F4** Columna
- [ ] **F5** Cráneo y mandíbula
- [ ] **F6** Cintura escapular, húmero, radio y cúbito
- [ ] **F7** Mano
- [ ] **F8** Fémur, rótula, tibia y peroné
- [ ] **F9** Pie
- [ ] **F10** Ensamblaje, pose y verificación final (IoU ≥ 0,75)

## Decisiones pendientes

1. Qué manda cuando la imagen y los datos antropométricos discrepan.
2. Alcance de «idéntico»: silueta y forma con relleno liso y contorno (recomendado) o también el sombreado del dibujo.

## Registro

| Fecha | Cambio |
|---|---|
| 2026-10-28 | Análisis de la imagen (3 vistas, 1083 × 1300, stock con marca de agua), comparador de siluetas y línea base (IoU 0,35). Hallazgo: las proporciones generales del modelo parecen coincidir con la imagen (a ojo; sin medir) pero los huesos son líneas y octaedros: falta toda la forma ósea. Plan por fases F0–F10. La imagen se añade a `.gitignore`. |
