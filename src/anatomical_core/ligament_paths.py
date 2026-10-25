"""Trayectoria de los ligamentos y de los tendones con guias de envoltura, en reposo y posada (Python puro, sin bpy).

Un ligamento es una poligonal origen -> guias (`via`) -> insercion, y una unidad musculo-tendinosa es la poligonal de sus sitios; cada nodo viaja con SU hueso: al posar el rig, los nodos del femur se
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


# Barrido de la pierna para los tendones que cruzan la cadera y la rodilla (psoas-iliaco, cintilla iliotibial): las poses de la cadera mas la
# flexion de la rodilla sola y combinada con la cadera. La rodilla llega a 140 grados en el rig; se prueban hasta 135.
LEG_SWEEP = tuple((n, {"hip": dict(r)}) for n, r in HIP_SWEEP) + (
    ("knee_30", {"knee": {"flexion": 30.0}}), ("knee_60", {"knee": {"flexion": 60.0}}), ("knee_90", {"knee": {"flexion": 90.0}}),
    ("knee_120", {"knee": {"flexion": 120.0}}), ("knee_135", {"knee": {"flexion": 135.0}}),
    ("hip_90_knee_90", {"hip": {"flexion": 90.0}, "knee": {"flexion": 90.0}}),
    ("hip_120_knee_135", {"hip": {"flexion": 120.0}, "knee": {"flexion": 135.0}}),
    ("hip_ext_15_knee_5", {"hip": {"flexion": -15.0}, "knee": {"flexion": 5.0}}),
    ("hip_30_abduction_45_knee_30", {"hip": {"flexion": 30.0, "abduction": 45.0}, "knee": {"flexion": 30.0}}),
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


def leg_sweep_poses(model: SkeletonModel, side: str = "L") -> list:
    """[(nombre, PosedSkeleton)] del barrido de cadera + rodilla `side`."""
    from .config import PoseDef
    from .pose import apply_pose

    return [(n, apply_pose(model, PoseDef(n, {f"{j}.{side}": dict(r) for j, r in rot.items()}))) for n, rot in LEG_SWEEP]


def tendon_nodes(t) -> list:
    """[(hueso, punto)] de los sitios de una unidad musculo-tendinosa (origen, vias, insercion), en reposo."""
    return [(s.bone, s.point) for s in t.sites]


def posed_nodes(node_list, base: SkeletonModel, anat, posed: PosedSkeleton) -> list:
    return [posed.bones[rig_bone(b, base, anat)].apply(p) for b, p in node_list]


def plate_triangles(anat, bone: str) -> list:
    """Triangulos (abanico) de una lamina osea cerrada (p. ej. el ilion), en reposo."""
    b = anat.bones[bone]
    o = b.outline
    return [(o[0], o[i], o[i + 1]) for i in range(1, len(o) - 1)] if getattr(b, "outline_closed", False) and len(o) >= 3 else []


PLATE_MARGIN_M = 0.001  # un tramo que empieza o acaba sobre la lamina (su origen o insercion) la toca, no la atraviesa: el corte debe quedar a > 1 mm de los extremos


def segment_hits_triangle(p: tuple, q: tuple, tri: tuple, eps: float = 1e-12, margin: float = PLATE_MARGIN_M) -> bool:
    """True si el segmento pq corta el triangulo (Moller-Trumbore) en un punto a mas de `margin` de sus dos extremos."""
    a, b, c = tri
    d = sub(q, p)
    e1, e2 = sub(b, a), sub(c, a)
    h = (d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0])
    det = e1[0] * h[0] + e1[1] * h[1] + e1[2] * h[2]
    if abs(det) < 1e-18:
        return False
    inv = 1.0 / det
    s_ = sub(p, a)
    u = inv * (s_[0] * h[0] + s_[1] * h[1] + s_[2] * h[2])
    if u < -eps or u > 1 + eps:
        return False
    qv = (s_[1] * e1[2] - s_[2] * e1[1], s_[2] * e1[0] - s_[0] * e1[2], s_[0] * e1[1] - s_[1] * e1[0])
    v = inv * (d[0] * qv[0] + d[1] * qv[1] + d[2] * qv[2])
    if v < -eps or u + v > 1 + eps:
        return False
    t = inv * (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2])
    ln = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
    return t * ln > margin and (1.0 - t) * ln > margin


def plate_crossings(path: list, triangles: list) -> int:
    """Numero de (tramo, triangulo) que se cortan: la poligonal atraviesa la lamina osea."""
    return sum(segment_hits_triangle(a, b, t) for a, b in zip(path, path[1:]) for t in triangles)


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
        surfaces = {s.name: s for s in posed_surfaces(art, base, anat, posed)}
        out[n] = path_clearance(posed_path(lg, base, anat, posed), [surfaces[a] for a in lg.avoid])
    return out
