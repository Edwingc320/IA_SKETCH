# Articulaciones, límites de rotación y puntos pivote

Especificación del rig articular de `anatomical-core`: qué se rota, hasta dónde, alrededor de qué punto y cómo se reutiliza el modelo a otras alturas. Es el **modelo óseo**; los músculos viven en la rama `muscle-model`.

| Qué | Dónde |
|---|---|
| 19 articulaciones de la base, ejes y límites (47 dof) | `config/joints.json` |
| Acoples entre ángulos (rodilla) | `config/rig_couplings.json` |
| Orden Euler, límites por eje y acoples (Python puro) | `src/anatomical_core/rig_limits.py` |
| Restricciones *Limit Rotation* en Blender | `scene.add_rotation_limits` |
| 213 articulaciones naturales (datos para poses futuras) | `config/articulations/*.json` |
| Pruebas | `tests/test_rig_limits.py`, `tests/test_connectivity.py`, `tests/test_height.py` |

Convenciones: +X izquierda, +Y atrás (anterior = −Y), +Z arriba. Cada grado de libertad gira `sign × grados` alrededor de un eje **local** del hueso; los dof se componen en el orden listado, que es el orden Euler de Blender (`euler_order`) con las letras de los ejes en ese orden. Los límites son aproximaciones configurables, no límites médicos.

## 1. Puntos pivote

- El pivote de cada articulación de la base es **exactamente** la cabeza del hueso hijo (distancia 0, comprobado en las 19 articulaciones).
- Ningún hueso de la base se separa de su padre: la cabeza del hijo está sobre el segmento del padre. Solo hay tres desfases, **laterales por diseño** (el padre es el eje medio y la articulación es par): clavícula (esternoclavicular, 103 mm), muslo (cadera, 91 mm) y brazo (hombro, 21 mm).
- En el nivel 1, cada hueso queda a ≤ 5 mm de su padre anatómico o se une a él mediante una articulación natural (rótula, escápula, costillas, huesos del carpo y el tarso…). Las dos excepciones documentadas son el esternón (cuelga de T4 por la jerarquía del tronco, pero se articula con costillas y clavículas) y el peroné (cuelga del fémur por la jerarquía pedida, pero se articula con la tibia). Una prueba falla si aparece un hueso nuevo separado sin articulación.
- La verificación encontró una articulación que faltaba: la **pisopiramidal**, ahora añadida.

## 2. Restricciones de rigging

Cada hueso que mueve una articulación lleva una restricción *Limit Rotation* (`AC_LimitRotation`) en espacio **local** con el orden Euler de sus dof, los límites de `joints.json` y *Affect Transform* activo (también limita al mover el hueso a mano). Los ejes sin grado de libertad quedan **bloqueados a 0** (la bisagra del codo no gira en Z). Probado en Blender: pedir 200° de flexión del codo da exactamente la pose a 145°, y girar el eje bloqueado no mueve el hueso. La pose A atraviesa las restricciones sin cambios.

**Limitación honesta: la rotación axial de la rodilla solo existe con flexión.** Se declara en `rig_couplings.json` (0 con la rodilla extendida, completa a 30° de flexión; [WikiMSK](https://wikimsk.org/wiki/Knee_Biomechanics)) y la **validación de la pose** la exige (`POSE_COUPLED_LIMIT`). En Blender solo rige el límite estático ±10°: un driver que lea la flexión del propio hueso que limita crea un ciclo de dependencias y el resultado deja de ser determinista (lo comprobé: la misma prueba fallaba en unas ejecuciones y pasaba en otras, y Blender avisaba del ciclo). Por eso el acople queda anotado en el hueso (`ac_coupling_axial`) y no hay drivers en el rig.

## 3. Validación de las propuestas

| Articulación | Propuesta | Modelo | Evidencia | Decisión |
|---|---|---|---|---|
| Esternoclavicular | ±15° en elevación y protracción | elevación −10…40°, protracción −20…25° | totales de 60° (elevación/depresión) y 35° (protracción/retracción), [GPnotebook](https://gpnotebook.com/pages/musculoskeletal-medicine/sternoclavicular-joint-anatomy/movements) | **No adoptado**: ±15° impediría elevar el hombro lo publicado. Pendiente tuyo: la protracción del modelo (45° en total) supera los 35° publicados |
| Glenohumeral | esférica, amplia | flexión −60…180°, abducción −50…180°, axial ±90° | Magee: flexión 160–180, extensión 50–60, abducción 170–180, aducción 50–75, rotaciones 60–100 / 80–90 | Sin cambios |
| Codo | bisagra 0–145°, rotación Z/Y bloqueada | flexión 0…145°; Z bloqueado | flexión 140–150° | Adoptado. Y no se bloquea: el rig tiene un solo hueso de antebrazo y la pronación es su dof (el radio y el cúbito del nivel 1 son rígidos) |
| Radiocubital | ±80° | ±90° → **±80°** | pronación y supinación 80–90° cada una | **Adoptado** (cambio de la base) |
| Muñeca | ±70° flexo/extensión, ±20° desviación | flexión 70°, extensión 60°, radial 20°, cubital 30° | flexión 74–80°, extensión 66–70°, radial 19–20°, cubital 28–30° | **No adoptado**: ±20° recortaría la desviación cubital publicada (28–30°). Pendiente: la extensión del modelo (60°) queda por debajo de la publicada |
| Cadera | flexión 120°, extensión 15°, abducción 45° | extensión 20° → **15°** | extensión 10° ([StatPearls](https://statpearls.com/sp/al/39/32220/)), otras referencias hasta 30° | **Adoptado** (cambio de la base) |
| Rodilla | bisagra 0–140°, rotación axial solo con flexión | flexión 0…140°, axial ±10° | flexión 135–140°; rotación 18° externa y 25° interna a 30–40° de flexión | Adoptado con la limitación de la sección 2. El rig limita la rotación axial a ±10°, menos que lo publicado |
| ATM | pivote inferior con traslación | **no está en la base** (la mandíbula es un hueso rígido del nivel 1 con el pivote en el eje de las dos ATM) | apertura interincisal 44,8 mm, protrusión 5,65 mm | Requiere la capa de poses del nivel 1 (sección 6) |
| Intervertebrales | 2–5° por disco | datos por nivel, no en el rig | flexoextensión por nivel: cervical 6,3–8,4°, lumbar 11,9–18,2°; **rotación axial** cervical 2,3–5,3° | **2–5° vale para rotación e inclinación, no para flexoextensión** (6–18°). La base reparte el movimiento en 5 segmentos (lumbar −20…40° frente a los 77° que suman los discos L1–S1) |

Dos cambios de la base (codo ±80°, cadera −15°) actualizan el golden con `freeze_base.py --update`; el diff solo toca esos cuatro límites y las firmas.

## 4. Reutilizable a cualquier altura

- **Entrada de altura**: `--height 1.70`, `170cm`, `5ft7in` o `5'7"` (`-Height 5ft7in` en `run.ps1`). Un número sin unidades son metros; `170` o `5.7` se rechazan en vez de adivinarse. 5 pies 7 pulgadas = 1,7018 m.
- **Todo lo óseo se deduce de la altura**: huesos de la base, 185 huesos del nivel 1, articulaciones, ligamentos y hitos escalan **linealmente** (comprobado punto por punto a 1,75 m y 1,7018 m) y el modelo completo es válido de 1,50 a 2,05 m. Las tolerancias de anclaje escalan con la altura; **los ángulos publicados no**.
- **Capas separadas**: `main` guarda el modelo óseo y `muscle-model` el muscular. El enlace entre ambos son los **hitos óseos** (`attachments`), anclados a huesos y por tanto escalados con ellos; los músculos se deducen de esos anclajes.
- **Edad (viable, no implementado)**: las proporciones cambian con la edad (según fuentes divulgativas la cabeza es ~1/4 de la altura al nacer, ~1/6 a los 6 años y ~1/7 desde los 15; son reglas de dibujo, no medidas), de modo que el factor lineal no basta. Hace falta una tabla de proporciones por edad con fuente primaria (p. ej. las referencias argentinas de 0 a 17 años, [SAP 2017](https://sap.org.ar/docs/publicaciones/archivosarg/2017/v115n3a05e.pdf)) y un factor de movilidad por edad. El diseño: `config/profiles/<perfil>/` con su `proportions.json` y un escalado de rangos, elegido con `--profile`; las restricciones, pruebas y validadores no cambian. Sin esas tablas inventaría cifras, por eso no lo implementé.

## 5. Lo que no se hace con scripts ni drivers

Ninguna restricción usa drivers ni Python embebido. Es un requisito de reutilización: el `.blend` abre y evalúa igual con la configuración de seguridad por defecto y sin dependencias de este paquete.

## 6. Viabilidad de una capa extra de articulaciones para poses dinámicas

**Estado**: hay 213 articulaciones naturales con datos (rangos con fuente, centro, huesos que unen, ligamentos), pero solo **18 se mueven** hoy con una articulación de la base (`rig_driver`: hombro, codo, muñeca, cadera, rodilla, tobillo, esternoclavicular, tres vértebras y la atlantooccipital). Los 195 restantes son datos: los huesos del nivel 1 son rígidos y siguen al segmento base que los lleva.

**Es viable y de riesgo moderado**, en tres pasos que se pueden validar por separado:

1. **FK genérica del nivel 1**: la cinemática directa de `pose.py` ya es genérica (pivote, ejes y padre); falta aplicarla a los huesos del nivel 1 con el pivote en la cabeza del hueso hijo, como la base.
2. **Reparto del movimiento**: una tabla `articulación de la base → articulaciones naturales + fracción` (p. ej. el segmento lumbar entre L1/L2 … L5/S1 con las fracciones por nivel publicadas), validando que la suma por nivel respeta el límite de la base.
3. **Restricciones del nivel 1**: *Limit Rotation* por hueso con los rangos de `config/articulations`, y *Copy Rotation* con la fracción como influencia. Misma regla que en la base: **sin drivers que lean el propio hueso** (ver sección 2).

**Riesgos**: cambiar el rig de rígido a articulado altera las pruebas de FK y los golden del nivel 1; hay que decidir qué articulaciones mueven realmente huesos (prioridad sugerida: columna, mandíbula, dedos) y cuáles quedan como datos. Los rangos sin cifra (carpometacarpianas, tarsometatarsianas…) deben quedar bloqueados hasta tener fuente.
