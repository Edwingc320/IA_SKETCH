"""Deslizamiento (tracking) de la rotula con la flexion de la rodilla (Python puro, sin bpy).

La rotula del nivel 1 cuelga del femur (`thigh`), pero no se queda quieta: al flexionar la rodilla desciende por delante de los condilos. El modelo es una
transformacion rigida en el sistema del femur, funcion SOLO del angulo de flexion de la rodilla f (grados):

    p' = P + R(c f) (p - P) + rho f R(c f) r0

con P el pivote de la rodilla, R(a) la rotacion de angulo a alrededor del eje de flexion de la rodilla (el mismo de la base), c la relacion entre la flexion
de la rotula y la de la rodilla (`pitch_ratio`), rho el desplazamiento radial en m por grado (`radial_mm_per_deg` a 1.75 m, que escala con la altura; negativo = hacia el eje) y r0 la direccion
unitaria del pivote al centro de la rotula en reposo. La inclinacion (pitch) de la rotula es c f. La posicion final en el mundo es la pose del femur
aplicada a p'.

En Blender se reproduce sin drivers: un hueso auxiliar `patella_carrier` con una restriccion Copy Rotation (influencia c) gira la rotula alrededor del pivote,
y una restriccion Transformation mueve la rotula en su eje radial local (rho f), que gira con el auxiliar. Los parametros c y rho se ajustaron a la geometria
del modelo (ligamento rotuliano de 27 mm) para que el ligamento cambie de longitud como mucho ~10 % sin que la rotula entre en el femur."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import Mat3, Vec3, add, mat_vec, normalize, rotation_matrix, scale, sub


@dataclass(frozen=True)
class PatellaTransform:
    pivot: Vec3
    rotation: Mat3  # R(c f)
    glide: Vec3  # rho f R(c f) r0
    pitch_deg: float  # c f

    def apply(self, p: Vec3) -> Vec3:
        """Punto de la rotula en reposo -> punto en el sistema del femur."""
        return add(add(self.pivot, mat_vec(self.rotation, sub(p, self.pivot))), self.glide)


def carrier_name(bone_name: str) -> str:
    """Nombre del hueso auxiliar de Blender que gira la rotula alrededor del pivote: patella.L -> patella_carrier.L."""
    stem, _, side = bone_name.rpartition(".")
    return f"{stem}_carrier.{side}"


def side_of(name: str) -> str:
    return "R" if name.endswith(".R") else "L"


def patella_transform(bone, base, flexion_deg: float) -> PatellaTransform:
    """Transformacion de la rotula `bone` (AnatomyBone con `tracking`) para una flexion de rodilla dada (la articulacion del lado de `bone`)."""
    t = bone.tracking
    joint = base.joints[f"{t['driver_joint']}.{side_of(bone.name)}"]
    dof = next(d for d in joint.dofs if d.name == t["driver_dof"])
    piv = joint.pivot
    pitch = float(t["pitch_ratio"]) * flexion_deg
    rot = rotation_matrix(dof.axis, math.radians(pitch))
    centre = scale(add(bone.head, bone.tail), 0.5)
    r0 = normalize(sub(centre, piv))
    k = base.height_m / 1.75  # el desplazamiento radial se define a 1.75 m y escala con la altura, como toda la geometria
    glide = scale(mat_vec(rot, r0), float(t["radial_mm_per_deg"]) / 1000.0 * k * flexion_deg)
    return PatellaTransform(piv, rot, glide, pitch)


def knee_flexion(posed, bone) -> float:
    """Flexion de la rodilla (grados) que mueve a `bone`, leida de la pose."""
    t = bone.tracking
    return float(posed.angles.get(f"{t['driver_joint']}.{side_of(bone.name)}", {}).get(t["driver_dof"], 0.0))
