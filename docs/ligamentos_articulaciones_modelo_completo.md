# Ligamentos y articulaciones de todo el modelo óseo

Auditoría y ampliación de las uniones del modelo óseo: cada articulación natural debe tener sus ligamentos. Antes de esta ampliación, **130 de 213 articulaciones no tenían ningún ligamento**. Se cubren por secciones (un commit por sección). Todo punto queda a menos de 12 mm de la superficie de su hueso; lo apoyado en fuentes débiles lo dice en su nota (**verificar en un atlas**). Los **tendones** no están aquí: pertenecen al modelo muscular (rama `muscle-model`).

## 1. Columna (C2 a sacro) — `config/articulations/spine.json`

En cada uno de los 23 niveles (C2/C3 … L5/S1) hay cinco ligamentos y, por lado, una articulación cigapofisaria:

| Ligamento | Dónde | Notas |
|---|---|---|
| Longitudinal anterior | cara anterior de los cuerpos y discos | el único que frena la extensión ([Taylor & Francis](https://taylorandfrancis.com/knowledge/medicine-and-healthcare/anatomy/anterior-longitudinal-ligament), [LearnMuscles](https://learnmuscles.com/glossary/ligaments-of-the-spine/)) |
| Longitudinal posterior | cara posterior de los cuerpos, dentro del canal | se tensa en la flexión |
| Amarillo | entre láminas | por detrás del longitudinal posterior; el más grueso en la región lumbar |
| Interespinoso | entre apófisis espinosas | se mezcla con el amarillo (delante) y el supraespinoso (detrás) |
| Intertransverso (×2) | entre apófisis transversas | frena la inclinación lateral; fino en la zona lumbar |
| Supraespinoso (uno solo) | de C7 al sacro | fuente débil en su extensión: **verificar** |

Las **articulaciones cigapofisarias** (`zygapophyseal_<sup>_<inf>.L/.R`, 46) son planas y no llevan cifra de rango (su orientación guía el movimiento de cada región; no hay cifra en las fuentes consultadas).

**Limitación**: los cuerpos vertebrales no tienen anchura en el modelo, así que cada punto se coloca a 8–11 mm del eje del hueso (cara anterior −10 mm; posterior +8 mm; lámina +10 mm; espinosa +11 mm; transversa 11 mm lateral), en el orden anatómico correcto, pero **no sobre la apófisis real**. En L5/S1 el sacro se recorre de arriba abajo, así que los puntos se ponen junto al promontorio.
