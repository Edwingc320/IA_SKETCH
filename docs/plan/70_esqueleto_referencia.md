# Plan: esqueleto sólido idéntico a la imagen de referencia

Estado detallado: [../estado/esqueleto_referencia.md](../estado/esqueleto_referencia.md) · Referencia: `esqueleto humano.jpg` (en la raíz del proyecto, **no versionada**) · Comparador: `scripts/render_bones_silhouette.py` + `scripts/compare_reference.py`

## Qué es la imagen

Ilustración de stock en estilo dibujo animado (relleno gris claro y contorno oscuro), 1083 × 1300 px, **tres vistas ortográficas** del mismo esqueleto en posición anatómica: **frente** (x 56–362), **espalda** (x 430–728) y **lado izquierdo** (x 763–987, mirando hacia la izquierda de la imagen). Lleva marca de agua de 123RF: se usa **solo como referencia privada de modelado**, no se redistribuye (el archivo está en `.gitignore`).

Lo que muestra, por sección (es lo que hay que reproducir en 3D):

| Sección | Qué se ve en la imagen |
|---|---|
| Cráneo y mandíbula | bóveda ovalada; órbitas grandes y redondas, abertura nasal, maxilar y mandíbula con **dientes**; de lado, bóveda larga y redondeada, arco cigomático, ángulo mandibular; de espalda, cúpula occipital |
| Columna cervical | siete vértebras apiladas, con las apófisis espinosas visibles de espalda |
| Caja torácica | esternón (manubrio, cuerpo y xifoides), 12 pares de costillas con sus cartílagos, forma de barril (más ancha abajo); de lado, la curvatura de las costillas y el hueco entre ellas |
| Columna dorsal y lumbar | 12 + 5 vértebras con cuerpos grandes en la lumbar; curvas de lado (lordosis cervical, cifosis dorsal, lordosis lumbar) |
| Pelvis | alas ilíacas anchas, **sacro con cuatro agujeros sacros visibles como puntos**, cóccix, sínfisis del pubis, **agujeros obturadores** ovales |
| Cintura escapular | clavículas en S; escápulas triangulares muy visibles de espalda; acromion y coracoides |
| Brazo y antebrazo | húmero; radio y cúbito paralelos; brazos algo separados del tronco; manos con palmas hacia los muslos |
| Mano | carpo, cinco metacarpianos, todas las falanges |
| Muslo | fémur con cabeza, cuello y trocánteres, **convergiendo hacia las rodillas**; rótulas visibles de frente |
| Pierna | tibia gruesa y peroné fino, bien separados abajo; cabeza del peroné |
| Pie | tarso, metatarso y cinco dedos con falanges; puntas algo hacia fuera; de lado, el arco y el talón |

## Punto de partida (medido)

El modelo actual **no se parece a la imagen**: sus huesos son líneas, octaedros finos y volúmenes paramétricos (cráneo) sobre los que cuelgan ligamentos, músculos y marcadores; no hay costillas, vértebras, pelvis ni huesos largos con forma. Las **proporciones generales sí coinciden** (a ojo, en el encuadre común, las alturas de hombro, pelvis y rodilla quedan muy cercanas; **no está medido**). Medida con el comparador (siluetas ortográficas a la misma escala, huesos solos):

| Vista | IoU | Error del perfil de anchura | Área modelo / referencia |
|---|---|---|---|
| Frente | 0,36 | 4,4 % | 0,82 |
| Espalda | 0,37 | 4,1 % | 0,84 |
| Lado | 0,32 | 1,9 % | 0,66 |
| **Media** | **0,35** | | |

Lectura honesta: el IoU de partida (0,35) está **inflado hacia arriba por la máscara de la referencia** (el relleno gris y el sombreado de la imagen son ruidosos y la marca de agua mete píxeles sueltos) y **no es una meta absoluta**; sirve para ver la tendencia entre fases. La meta realista de la silueta con el mismo criterio es **≥ 0,75**, porque los huecos entre costillas y dedos no coinciden píxel a píxel.

## Enfoque

Se conserva **todo lo construido** (base congelada, rig, hitos, ligamentos, tendones, músculos, pruebas) y se añade una **capa de superficies óseas sólidas** (nivel 2) que:

1. genera cada hueso como una **malla cerrada** (sección variable a lo largo de un eje para los huesos largos, láminas con grosor para pelvis y escápula, tubos aplanados para costillas, cuerpo + arco + apófisis para vértebras, bóveda + cara + mandíbula con dientes para el cráneo, caja y falanges para mano y pie);
2. se ajusta a los **hitos y ejes que ya existen** (cabeza femoral, trocánteres, epicóndilos, espinas, etc.), de modo que los ligamentos, los tendones y las articulaciones siguen siendo válidos y la distancia al hueso pasa a medirse contra la **malla real** (se acaba la convención de obstáculos);
3. cuelga rígida del hueso del nivel 1 correspondiente (sigue al rig) y **escala con `--height`** (cada dimensión es una fracción de la altura);
4. se renderiza con el **estilo de la imagen** (gris liso y contorno oscuro) y se mide con el comparador en las tres vistas.

«3D» es el entregable; la comparación «2D» son las tres vistas ortográficas; la pose y el movimiento («4D») ya los da el rig (no se tocan en este plan).

## Fases

| Fase | Contenido | Criterio de aceptación |
|---|---|---|
| F0 ✅ | banco de comparación (render de siluetas + IoU y perfil de anchura contra la imagen) y línea base | scripts versionados; línea base de la tabla anterior |
| F1 | **núcleo de mallas óseas**: lofts, láminas, tubos; emparentado al hueso; escala; estilo de la imagen; validación (malla cerrada, volumen > 0, sin autointersección gruesa) | pruebas puras y de Blender; un hueso de ejemplo (fémur) en las tres vistas |
| F2 | pelvis y sacro (alas, agujeros sacros y obturadores, sínfisis, cóccix) | IoU de la sección y distancia de los anclajes a la malla < 12 mm |
| F3 | caja torácica (esternón, 12 pares de costillas con cartílago) | idem |
| F4 | columna (C1–L5, curvaturas, apófisis) | idem |
| F5 | cráneo y mandíbula con dientes | idem |
| F6 | cintura escapular, húmero, radio y cúbito | idem |
| F7 | mano | idem |
| F8 | fémur, rótula, tibia y peroné | idem |
| F9 | pie | idem |
| F10 | ensamblaje, pose A de la imagen y verificación final | IoU medio ≥ 0,75; ninguna sección fuera de ± 5 % en sus proporciones; todas las pruebas previas en verde |

Orden por impacto visual y dependencia: primero el tronco (pelvis, tórax, columna), que ancla muslo y brazos, después cráneo, miembros superiores y miembros inferiores. Un commit por fase, con pruebas y mutaciones, y los documentos al día después de cada commit.

## Riesgos y decisiones abiertas

- **Imagen frente a datos.** La imagen es una ilustración: sus proporciones (p. ej. brazos algo separados del tronco, cabeza, pies hacia fuera) pueden discrepar de las antropométricas del modelo (Drillis y Contini, escalado a 1,75 m). Hay que decidir cuál manda cuando discrepan.
- **«Idéntico».** Con un relleno liso y un contorno, la silueta se puede acercar mucho; replicar el **sombreado y las rugosidades** de la ilustración píxel a píxel no es un objetivo realista.
- **Tamaño.** Un esqueleto completo son ~200 mallas; la generación y las pruebas en Blender se alargarán (hoy 30 s por generación).
- **Derechos.** La imagen es de stock: no se versiona ni se redistribuye.
