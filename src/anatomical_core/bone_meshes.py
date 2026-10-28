"""Mallas oseas SOLIDAS del esqueleto (nivel 2; Python puro, sin bpy).

El nivel 1 describe cada hueso con su eje, su contorno y unos hitos; esta capa le da CUERPO: una malla cerrada, con la forma que se ve en la imagen de
referencia (`esqueleto humano.jpg`), ajustada a esos mismos hitos y ejes, para que ligamentos, tendones y articulaciones sigan siendo validos. Plan en
`docs/plan/70_esqueleto_referencia.md`.

Forma: un LOFT. Una trayectoria (spline Catmull-Rom por estaciones) y, en cada estacion, una seccion eliptica de semiejes `a` (anchura) y `b` (profundidad)
con un marco por transporte paralelo. Los extremos se cierran con casquetes (media elipse de longitud `cap_*`). Cada estacion es un punto del modelo
(`at`/`lerp` + `offset_h`, como los hitos) y sus semiejes se dan en metros a 1,75 m y escalan con la altura (`--height`): la malla es isometrica.

Datos: `config/bones/bone_meshes.json`. Los datos antropometricos mandan en las longitudes (los ejes y los hitos ya las traen); la imagen manda en la forma
(secciones). Cada malla es un cuerpo rigido que cuelga de su hueso del nivel 1."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from .anatomy import AnatomyModel, _eval, _point_spec, _swap_side
from .config import PROJECT_ROOT, ConfigError, _read_json
from .geometry import Vec3, add, cross, dot, length, mirror_point, normalize, scale, sub
from .skeleton import SkeletonModel
from .volumes import euler_characteristic, signed_volume

MESHES_DIR = PROJECT_ROOT / "config" / "bones"
FILE = "bone_meshes"
DEFAULT_SIDES = 24  # vertices por anillo
STEPS_PER_SEGMENT = 8  # anillos entre dos estaciones
CAP_RINGS = 6


@dataclass(frozen=True)
class Station:
    point: Vec3
    a: float  # semieje de anchura (m)
    b: float  # semieje de profundidad (m)


@dataclass(frozen=True)
class BoneMesh:
    name: str  # hueso del nivel 1 del que cuelga (p. ej. "femur.L")
    stations: tuple
    verts: tuple
    faces: tuple  # cuadrilateros y triangulos (los polos)
    notes: str

    @property
    def volume_m3(self) -> float:
        return signed_volume(list(self.verts), list(self.faces))


@dataclass(frozen=True)
class BoneMeshModel:
    meshes: dict  # nombre -> BoneMesh
    height_m: float

    def signature(self) -> str:
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        return hashlib.sha256(json.dumps({n: [[r(s.point), round(s.a, 6), round(s.b, 6)] for s in m.stations] for n, m in sorted(self.meshes.items())}, sort_keys=True).encode()).hexdigest()


def load_mesh_data(meshes_dir: Path | str | None = None):
    p = Path(meshes_dir or MESHES_DIR) / f"{FILE}.json"
    return _read_json(p) if p.exists() else None


def _catmull_rom(p0, p1, p2, p3, t: float) -> Vec3:
    return tuple(0.5 * ((2 * p1[i]) + (-p0[i] + p2[i]) * t + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t * t + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * t ** 3) for i in range(3))


def _smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def loft(stations: tuple, sides: int = DEFAULT_SIDES, width_ref: Vec3 = (1.0, 0.0, 0.0), cap_start: float | None = None, cap_end: float | None = None) -> tuple:
    """(vertices, caras) de la malla cerrada que sigue la trayectoria de `stations`. Orientada hacia fuera (volumen positivo)."""
    if len(stations) < 2:
        raise ConfigError("Un loft necesita al menos dos estaciones")
    pts = [s.point for s in stations]
    ext = [add(pts[0], sub(pts[0], pts[1]))] + pts + [add(pts[-1], sub(pts[-1], pts[-2]))]
    samples = []  # (punto, a, b)
    for i in range(len(stations) - 1):
        for k in range(STEPS_PER_SEGMENT):
            t = k / STEPS_PER_SEGMENT
            s = _smooth(t)
            samples.append((_catmull_rom(ext[i], ext[i + 1], ext[i + 2], ext[i + 3], t), stations[i].a + (stations[i + 1].a - stations[i].a) * s,
                            stations[i].b + (stations[i + 1].b - stations[i].b) * s))
    samples.append((pts[-1], stations[-1].a, stations[-1].b))
    # tangentes y marco por transporte paralelo
    tang = []
    for i, (p, _, _) in enumerate(samples):
        q = samples[min(i + 1, len(samples) - 1)][0]
        o = samples[max(i - 1, 0)][0]
        tang.append(normalize(sub(q, o)))
    u = normalize(sub(width_ref, scale(tang[0], dot(width_ref, tang[0]))))
    frames = []
    for i, t in enumerate(tang):
        if i:
            u = sub(u, scale(t, dot(u, t)))
            u = normalize(u) if length(u) > 1e-9 else normalize(cross(t, (0.0, 0.0, 1.0)))
        frames.append((u, cross(t, u)))
    cs = stations[0].a if cap_start is None else cap_start
    ce = stations[-1].a if cap_end is None else cap_end
    rings = []  # lista de anillos; cada uno es (centro, a, b, u, v)
    for j in range(CAP_RINGS, 0, -1):  # casquete inicial: de la punta al ecuador
        f = j / (CAP_RINGS + 1)
        ang = f * math.pi / 2
        c0, a0, b0 = samples[0]
        shrink = math.cos(ang)
        rings.append((sub(c0, scale(tang[0], math.sin(ang) * min(cs, a0 + b0))), a0 * shrink, b0 * shrink, *frames[0]))
    for (c, a, b), (uu, vv) in zip(samples, frames):
        rings.append((c, a, b, uu, vv))
    for j in range(1, CAP_RINGS + 1):  # casquete final
        f = j / (CAP_RINGS + 1)
        ang = f * math.pi / 2
        c1, a1, b1 = samples[-1]
        shrink = math.cos(ang)
        rings.append((add(c1, scale(tang[-1], math.sin(ang) * min(ce, a1 + b1))), a1 * shrink, b1 * shrink, *frames[-1]))
    verts = []
    for c, a, b, uu, vv in rings:
        for k in range(sides):
            ph = 2 * math.pi * k / sides
            verts.append(add(c, add(scale(uu, a * math.cos(ph)), scale(vv, b * math.sin(ph)))))
    first, last = len(verts), len(verts) + 1
    verts.append(sub(samples[0][0], scale(tang[0], cs)))
    verts.append(add(samples[-1][0], scale(tang[-1], ce)))
    faces = []
    n = len(rings)
    for i in range(n - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            faces.append((i * sides + k, i * sides + k2, (i + 1) * sides + k2, (i + 1) * sides + k))
    for k in range(sides):
        k2 = (k + 1) % sides
        faces.append((first, k2, k))
        faces.append((last, (n - 1) * sides + k, (n - 1) * sides + k2))
    if signed_volume(verts, faces) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


def build_bone_meshes(base: SkeletonModel, anat: AnatomyModel, data) -> BoneMeshModel:
    """Malla de cada hueso de la especificacion (y de su espejo) a la altura de `base`."""
    if not data:
        return BoneMeshModel({}, base.height_m)
    k = base.height_m / 1.75
    out = {}
    for i, d in enumerate(data.get("bones", [])):
        w = f"bone_meshes.bones[{i}]"
        name = str(d["name"])
        if name not in anat.bones:
            raise ConfigError(f"{w}: el hueso del nivel 1 '{name}' no existe")
        raw = d.get("stations", [])
        if len(raw) < 2:
            raise ConfigError(f"{w}: hacen falta al menos 2 estaciones")
        left = []
        for j, s in enumerate(raw):
            a, b = float(s["a_m"]) * k, float(s["b_m"]) * k
            if not (0.001 * k <= a <= 0.2 and 0.001 * k <= b <= 0.2):
                raise ConfigError(f"{w}.stations[{j}]: semiejes fuera de rango (1 mm - 20 cm)")
            left.append(Station(_eval(_point_spec(s, f"{w}.stations[{j}]"), base, anat.bones), a, b))
        cs, ce = (float(d["cap_start_m"]) * k if "cap_start_m" in d else None), (float(d["cap_end_m"]) * k if "cap_end_m" in d else None)
        sides = int(d.get("sides", DEFAULT_SIDES))
        for side in (("L", "R") if d.get("mirror") else (None,)):
            if side == "R":
                stations = tuple(Station(mirror_point(s.point), s.a, s.b) for s in left)
                ref = (-1.0, 0.0, 0.0)
            else:
                stations, ref = tuple(left), (1.0, 0.0, 0.0)
            verts, faces = loft(stations, sides, ref, cs, ce)
            nm = _swap_side(name, side or "L")
            if nm in out:
                raise ConfigError(f"Malla duplicada '{nm}'")
            out[nm] = BoneMesh(nm, stations, tuple(verts), tuple(faces), str(d.get("notes", "")))
    return BoneMeshModel(out, base.height_m)


def validate_bone_meshes_snapshot(model: BoneMeshModel, snap: dict) -> list:
    """Compara los objetos BM_ leidos de Blender (padre, numero de vertices y caja envolvente) con las mallas del modelo."""
    from .validation import BLEND_TOL, Issue

    out = []
    for n, m in model.meshes.items():
        s = snap.get(f"BM_{n}")
        if s is None:
            out.append(Issue("error", "BMESH_BLEND_MISSING", f"Falta el objeto 'BM_{n}'"))
            continue
        lo, hi = tuple(min(v[i] for v in m.verts) for i in range(3)), tuple(max(v[i] for v in m.verts) for i in range(3))
        if s["parent_bone"] != n:
            out.append(Issue("error", "BMESH_BLEND_PARENT", f"'BM_{n}' no esta emparentado a '{n}'"))
        if s["n_verts"] != len(m.verts) or any(abs(a - b) > BLEND_TOL for a, b in zip(lo + hi, tuple(s["bbox"][0]) + tuple(s["bbox"][1]))):
            out.append(Issue("error", "BMESH_BLEND_SHAPE", f"'BM_{n}': la malla del .blend no coincide con la del modelo"))
    extra = {k for k in snap if k[3:] not in model.meshes}
    if extra:
        out.append(Issue("error", "BMESH_BLEND_EXTRA", f"Objetos de malla osea no esperados: {sorted(extra)[:5]}"))
    return out


def mesh_distance(p: Vec3, mesh: BoneMesh) -> float:
    """Distancia de un punto a la superficie de la malla (0 dentro de ella)."""
    from .anatomy import point_triangle_distance
    from .volumes import point_inside

    verts = list(mesh.verts)
    if point_inside(p, verts, [list(f) for f in mesh.faces]):
        return 0.0
    best = float("inf")
    for f in mesh.faces:
        for i in range(1, len(f) - 1):
            best = min(best, point_triangle_distance(p, verts[f[0]], verts[f[i]], verts[f[i + 1]]))
    return best


def validate_bone_meshes(base: SkeletonModel, anat: AnatomyModel, model: BoneMeshModel) -> list:
    """Malla cerrada (Euler 2), volumen positivo, simetria L/R, extremos sobre el eje del hueso del nivel 1 y sin vertices no finitos."""
    from .validation import FRAME_TOL, Issue

    out = []
    for n, m in model.meshes.items():
        if n not in anat.bones:
            out.append(Issue("error", "BMESH_BONE_UNKNOWN", f"La malla '{n}' no corresponde a un hueso del nivel 1"))
            continue
        verts, faces = list(m.verts), [list(f) for f in m.faces]
        if not all(math.isfinite(c) for v in verts for c in v):
            out.append(Issue("error", "BMESH_NON_FINITE", f"'{n}': vertices no finitos"))
            continue
        if euler_characteristic(verts, faces) != 2:
            out.append(Issue("error", "BMESH_NOT_CLOSED", f"'{n}': la malla no es una superficie cerrada (caracteristica de Euler != 2)"))
        if m.volume_m3 <= 1e-9:
            out.append(Issue("error", "BMESH_VOLUME", f"'{n}': volumen no positivo"))
        right = n[:-2] + ".R" if n.endswith(".L") else None
        if right and right in model.meshes:
            r = model.meshes[right]
            if len(r.verts) != len(m.verts) or abs(r.volume_m3 - m.volume_m3) > 1e-4 * m.volume_m3:  # los cuadrilateros alabeados se triangulan distinto al invertir el orden: ~4e-6 de diferencia
                out.append(Issue("error", "BMESH_ASYMMETRIC", f"'{n}' y '{right}' no son simetricas (vertices o volumen distintos)"))
            else:
                grid = {}
                for q in r.verts:
                    grid.setdefault(tuple(int(c // 1e-6) for c in q), []).append(q)
                for p in m.verts:
                    mp = mirror_point(p)
                    cell = tuple(int(c // 1e-6) for c in mp)
                    near = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) for q in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ())]
                    if not near or min(length(sub(mp, q)) for q in near) > FRAME_TOL:
                        out.append(Issue("error", "BMESH_ASYMMETRIC", f"'{n}' no es el espejo de '{right}'"))
                        break
    return out
