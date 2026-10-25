"""Trayectoria de los ligamentos con guias de envoltura, en reposo y posada (Python puro, sin bpy).

Un ligamento es una poligonal origen -> guias (`via`) -> insercion, y cada nodo viaja con SU hueso: al posar el rig, los nodos del femur se
mueven con el femur y los de la pelvis se quedan en la pelvis. Los huesos del nivel 1 no tienen articulaciones propias: siguen rigidamente al
hueso de la base que los carga, asi que la pose de un nodo es la del primer ancestro que sea hueso de la base.

Los obstaculos son las `BoneSurface` del modelo (esfera de la cabeza y capsula del cuello del femur): el ligamento no puede atravesarlas.
`path_clearance` devuelve la distancia con signo mas pequena entre la poligonal y los obstaculos (negativa = penetra)."""
from __future__ import annotations

from .articulations import ArticulationModel, Ligament
from .geometry import add, length, scale, sub
from .pose import PosedSkeleton
from .skeleton import SkeletonModel

PATH_SAMPLES = 40  # puntos por tramo para medir la distancia a los obstaculos
PENETRATION_TOL_M = 1e-6

# Barrido de la cadera para comprobar que ningun ligamento atraviesa el femur (grados; flexion negativa = extension, abduccion negativa = aduccion).
# Cubre el recorrido pedido (flexion 0-120, extension 15, abduccion 45) y, ademas, aduccion, rotaciones y combinaciones.
HIP_SWEEP = (
    ("rest", {}),
    ("flexion_30", {"flexion": 30.0}), ("flexion_60", {"flexion": 60.0}), ("flexion_90", {"flexion": 90.0}), ("flexion_120", {"flexion": 120.0}),
    ("extension_15", {"flexion": -15.0}),
    ("abduction_45", {"abduction": 45.0}), ("adduction_30", {"abduction": -30.0}),
    ("internal_rotation_40", {"axial": -40.0}), ("external_rotation_40", {"axial": 40.0}),
    ("flexion_90_abduction_30", {"flexion": 90.0, "abduction": 30.0}), ("flexion_120_adduction_20", {"flexion": 120.0, "abduction": -20.0}),
    ("extension_15_abduction_45", {"flexion": -15.0, "abduction": 45.0}),
)


def rig_bone(name: str, base: SkeletonModel, anat) -> str:
    """Hueso de la base que mueve a `name` (los huesos del nivel 1 cuelgan de el sin articulaciones propias)."""
    seen = set()
    while name not in base.bones:
        if name in seen or name not in anat.bones:
            raise KeyError(name)
        seen.add(name)
        name = anat.bones[name].parent
    return name


def nodes(lg: Ligament) -> list:
    """[(hueso, punto)] del origen, las guias y la insercion, en reposo."""
    return [(lg.from_bone, lg.a)] + [(w.bone, w.point) for w in lg.via] + [(lg.to_bone, lg.b)]


def rest_samples(lg: Ligament, samples: int = PATH_SAMPLES) -> list:
    """Puntos de la poligonal en reposo (todos los nodos y `samples` por tramo)."""
    pts = [p for _, p in nodes(lg)]
    return [add(a, scale(sub(b, a), i / samples)) for a, b in zip(pts, pts[1:]) for i in range(samples + 1)]


def posed_path(lg: Ligament, base: SkeletonModel, anat, posed: PosedSkeleton) -> list:
    return [posed.bones[rig_bone(b, base, anat)].apply(p) for b, p in nodes(lg)]


def posed_surfaces(art: ArticulationModel, base: SkeletonModel, anat, posed: PosedSkeleton) -> list:
    """[(BoneSurface posada)]: la misma superficie con sus extremos llevados a la pose de su hueso."""
    from dataclasses import replace

    out = []
    for s in art.surfaces.values():
        pb = posed.bones[rig_bone(s.bone, base, anat)]
        out.append(replace(s, a=pb.apply(s.a), b=pb.apply(s.b)))
    return out


def path_length(path: list) -> float:
    return sum(length(sub(b, a)) for a, b in zip(path, path[1:]))


def path_clearance(path: list, surfaces: list, samples: int = PATH_SAMPLES) -> float:
    """Distancia con signo minima de la poligonal a los obstaculos (m). Sin obstaculos: +inf."""
    best = float("inf")
    for a, b in zip(path, path[1:]):
        for i in range(samples + 1):
            p = add(a, scale(sub(b, a), i / samples))
            for s in surfaces:
                best = min(best, s.signed_distance(p))
    return best


def hip_sweep_poses(model: SkeletonModel, side: str = "L") -> list:
    """[(nombre, PosedSkeleton)] del barrido de la cadera `side`."""
    from .config import PoseDef
    from .pose import apply_pose

    return [(n, apply_pose(model, PoseDef(n, {f"hip.{side}": dict(rot)}))) for n, rot in HIP_SWEEP]


def sweep_clearance(art: ArticulationModel, base: SkeletonModel, anat, ligament: str, side: str = "L") -> dict:
    """{pose: distancia minima con signo} del ligamento a lo largo del barrido."""
    lg = art.ligaments[ligament]
    out = {}
    for n, posed in hip_sweep_poses(base, side):
        out[n] = path_clearance(posed_path(lg, base, anat, posed), posed_surfaces(art, base, anat, posed))
    return out
