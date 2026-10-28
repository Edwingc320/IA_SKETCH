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
    genus: int = 0  # numero de agujeros pasantes (agujeros sacros de una lamina): la caracteristica de Euler esperada es 2 - 2 genus
    smooth: bool = True  # sombreado suave (lofts) o plano (laminas de caras anchas: pelvis, sacro)
    bone: str = ""  # hueso del nivel 1 del que cuelga si la malla no lleva su nombre (copa acetabular, sinfisis, marco obturador); vacio = `name`
    tone: str = "grey"  # estilo: "grey" (gris liso de la imagen), "bone" (hueso claro) o "joint" (rojo: poligonos de union articular)

    @property
    def parent_bone(self) -> str:
        return self.bone or self.name

    @property
    def volume_m3(self) -> float:
        return signed_volume(list(self.verts), list(self.faces))


@dataclass(frozen=True)
class BoneMeshModel:
    meshes: dict  # nombre -> BoneMesh
    height_m: float

    def signature(self) -> str:
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        return hashlib.sha256(json.dumps({n: [[[r(s.point), round(s.a, 6), round(s.b, 6)] for s in m.stations], len(m.verts), m.genus] for n, m in sorted(self.meshes.items())}, sort_keys=True).encode()).hexdigest()


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


TONES = ("grey", "bone", "joint")


def cup(center: Vec3, axis: Vec3, r_in: float, r_out: float, theta_max: float, n_theta: int = 10, n_phi: int = 24) -> tuple:
    """(vertices, caras) de una copa: casquete esferico grueso (cascara entre r_in y r_out) de semiangulo `theta_max` (rad) alrededor de `axis`. Cerrada
    (genero 0, Euler 2) y orientada hacia fuera. La cara interior (r_in) es la superficie articular que abraza la cabeza del femur."""
    if not 0.0 < r_in < r_out:
        raise ConfigError("Copa articular: se exige 0 < r_in < r_out")
    if not 0.2 <= theta_max <= math.pi - 0.2:
        raise ConfigError("Copa articular: el semiangulo debe estar entre 0.2 rad y pi - 0.2 rad")
    ax = normalize(axis)
    u = normalize(cross(ax, (0.0, 0.0, 1.0)) if abs(ax[2]) < 0.9 else cross(ax, (1.0, 0.0, 0.0)))
    v = cross(ax, u)
    verts, poles = [], {}
    for tag, r in (("o", r_out), ("i", r_in)):
        verts.append(add(center, scale(ax, r)))
        poles[tag] = len(verts) - 1
        for i in range(1, n_theta + 1):
            th = theta_max * i / n_theta
            for k in range(n_phi):
                ph = 2 * math.pi * k / n_phi
                d = add(scale(ax, math.cos(th)), add(scale(u, math.sin(th) * math.cos(ph)), scale(v, math.sin(th) * math.sin(ph))))
                verts.append(add(center, scale(d, r)))
    ring = lambda tag, i, k: poles[tag] + 1 + (i - 1) * n_phi + (k % n_phi)  # noqa: E731
    faces = []
    for tag, flip in (("o", False), ("i", True)):
        f = [(poles[tag], ring(tag, 1, k + 1), ring(tag, 1, k)) for k in range(n_phi)]
        for i in range(1, n_theta):
            for k in range(n_phi):
                f.append((ring(tag, i, k), ring(tag, i, k + 1), ring(tag, i + 1, k + 1), ring(tag, i + 1, k)))
        faces += [tuple(reversed(q)) if flip else q for q in f]
    for k in range(n_phi):  # borde: une la cara exterior con la interior
        faces.append((ring("o", n_theta, k), ring("o", n_theta, k + 1), ring("i", n_theta, k + 1), ring("i", n_theta, k)))
    if signed_volume(verts, faces) < 0:
        faces = [tuple(reversed(q)) for q in faces]
    return verts, faces


def _tone(d: dict, w: str) -> str:
    t = str(d.get("tone", "grey"))
    if t not in TONES:
        raise ConfigError(f"{w}: tone '{t}' no valido (grey, bone o joint)")
    return t


def _build_cup(out: dict, d: dict, w: str, name: str, bone: str, k: float, base: SkeletonModel, anat: AnatomyModel) -> None:
    centre = _eval(_point_spec(d["center"], f"{w}.center"), base, anat.bones)
    axis = tuple(float(c) for c in d["axis"])
    r_in, r_out = float(d["r_in_m"]) * k, float(d["r_out_m"]) * k
    if not 0.005 <= r_in <= 0.1:
        raise ConfigError(f"{w}: r_in fuera de rango (5 mm - 10 cm)")
    for side in (("L", "R") if d.get("mirror") else (None,)):
        c, ax = (mirror_point(centre), (-axis[0], axis[1], axis[2])) if side == "R" else (centre, axis)
        verts, faces = cup(c, ax, r_in, r_out, math.radians(float(d["theta_max_deg"])), int(d.get("rings", 10)), int(d.get("sides", 24)))
        nm = _swap_side(name, side or "L")
        if nm in out:
            raise ConfigError(f"Malla duplicada '{nm}'")
        out[nm] = BoneMesh(nm, (), tuple(verts), tuple(faces), str(d.get("notes", "")), 0, bool(d.get("smooth", True)), _swap_side(bone, side or "L"), _tone(d, w))


def build_bone_meshes(base: SkeletonModel, anat: AnatomyModel, data) -> BoneMeshModel:
    """Malla de cada hueso de la especificacion (y de su espejo) a la altura de `base`."""
    if not data:
        return BoneMeshModel({}, base.height_m)
    k = base.height_m / 1.75
    out = {}
    for i, d in enumerate(data.get("bones", [])):
        w = f"bone_meshes.bones[{i}]"
        name = str(d["name"])
        bone = str(d.get("bone", name))
        if bone not in anat.bones:
            raise ConfigError(f"{w}: el hueso del nivel 1 '{bone}' no existe")
        if d.get("kind", "loft") == "cup":
            _build_cup(out, d, w, name, bone, k, base, anat)
            continue
        if d.get("kind", "loft") == "slab":
            _build_slab(out, d, w, name, bone, k, base, anat)
            continue
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
            wr = tuple(float(c) for c in d.get("width_ref", (1.0, 0.0, 0.0)))  # eje de referencia de la anchura de la seccion
            if side == "R":
                stations = tuple(Station(mirror_point(s.point), s.a, s.b) for s in left)
                ref = (-wr[0], wr[1], wr[2])
            else:
                stations, ref = tuple(left), wr
            verts, faces = loft(stations, sides, ref, cs, ce)
            nm = _swap_side(name, side or "L")
            if nm in out:
                raise ConfigError(f"Malla duplicada '{nm}'")
            out[nm] = BoneMesh(nm, stations, tuple(verts), tuple(faces), str(d.get("notes", "")), 0, bool(d.get("smooth", True)), _swap_side(bone, side or "L"), _tone(d, w))
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
        if s["parent_bone"] != m.parent_bone:
            out.append(Issue("error", "BMESH_BLEND_PARENT", f"'BM_{n}' no esta emparentado a '{m.parent_bone}'"))
        if s["n_verts"] != len(m.verts) or any(abs(a - b) > BLEND_TOL for a, b in zip(lo + hi, tuple(s["bbox"][0]) + tuple(s["bbox"][1]))):
            out.append(Issue("error", "BMESH_BLEND_SHAPE", f"'BM_{n}': la malla del .blend no coincide con la del modelo"))
    extra = {k for k in snap if k[3:] not in model.meshes}
    if extra:
        out.append(Issue("error", "BMESH_BLEND_EXTRA", f"Objetos de malla osea no esperados: {sorted(extra)[:5]}"))
    return out


def _build_slab(out: dict, d: dict, w: str, name: str, bone: str, k: float, base: SkeletonModel, anat: AnatomyModel) -> None:
    outline = [_eval(_point_spec(p, f"{w}.outline[{i}]"), base, anat.bones) for i, p in enumerate(d.get("outline", []))]
    if len(outline) < 3:
        raise ConfigError(f"{w}: una lamina necesita al menos 3 puntos de contorno")
    thick = float(d["thickness_m"]) * k
    if not 0.001 * k <= thick <= 0.1:
        raise ConfigError(f"{w}: grosor fuera de rango (1 mm - 10 cm)")
    holes = [{"loop": [_eval(_point_spec(q, f"{w}.holes[{i}].loop"), base, anat.bones) for q in h["loop"]]} if "loop" in h else
             {"center": _eval(_point_spec(h["center"], f"{w}.holes[{i}]"), base, anat.bones), "radius": float(h["radius_m"]) * k} for i, h in enumerate(d.get("holes", []))]
    bend = None
    if d.get("bend"):
        b = d["bend"]
        bend = {"p0": _eval(_point_spec(b["p0"], f"{w}.bend.p0"), base, anat.bones), "p1": _eval(_point_spec(b["p1"], f"{w}.bend.p1"), base, anat.bones), "amount": float(b["amount_m"]) * k}
    for side in (("L", "R") if d.get("mirror") else (None,)):
        if side == "R":
            o = [mirror_point(p) for p in outline]
            hs = [{"loop": [mirror_point(q) for q in h["loop"]]} if "loop" in h else {"center": mirror_point(h["center"]), "radius": h["radius"]} for h in holes]
            bd = {"p0": mirror_point(bend["p0"]), "p1": mirror_point(bend["p1"]), "amount": bend["amount"]} if bend else None
        else:
            o, hs, bd = outline, holes, bend
        verts, faces = slab(o, thick, hs, bd)
        nm = _swap_side(name, side or "L")
        if nm in out:
            raise ConfigError(f"Malla duplicada '{nm}'")
        out[nm] = BoneMesh(nm, (), tuple(verts), tuple(faces), str(d.get("notes", "")), len(hs), bool(d.get("smooth", False)), _swap_side(bone, side or "L"), _tone(d, w))


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
        if m.parent_bone not in anat.bones or m.name != n:
            out.append(Issue("error", "BMESH_BONE_UNKNOWN", f"La malla '{n}' no cuelga de un hueso del nivel 1"))
            continue
        verts, faces = list(m.verts), [list(f) for f in m.faces]
        if not all(math.isfinite(c) for v in verts for c in v):
            out.append(Issue("error", "BMESH_NON_FINITE", f"'{n}': vertices no finitos"))
            continue
        if euler_characteristic(verts, faces) != 2 - 2 * m.genus:
            out.append(Issue("error", "BMESH_NOT_CLOSED", f"'{n}': la malla no es una superficie cerrada con {m.genus} agujeros (caracteristica de Euler != {2 - 2 * m.genus})"))
        if m.volume_m3 <= 1e-9:
            out.append(Issue("error", "BMESH_VOLUME", f"'{n}': volumen no positivo"))
        right = n[:-2] + ".R" if n.endswith(".L") else None
        if right and right in model.meshes:
            r = model.meshes[right]
            if len(r.verts) != len(m.verts) or abs(r.volume_m3 - m.volume_m3) > 2e-3 * m.volume_m3:  # los cuadrilateros alabeados se triangulan distinto al invertir el orden: hasta ~4e-4 de diferencia (los vertices se comparan aparte, exactos)
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


# --- Laminas con grosor (pelvis, sacro) ------------------------------------------------------------------------------------------------------------
def _newell_normal(pts: list) -> Vec3:
    n = (0.0, 0.0, 0.0)
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n = add(n, ((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]), (p[0] - q[0]) * (p[1] + q[1])))
    if length(n) < 1e-12:
        raise ConfigError("Contorno de lamina degenerado: area nula (puntos colineales o contorno que se cruza)")
    return normalize(n)


def _area2(poly: list) -> float:
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))


def _seg_cross(a, b, c, d) -> bool:
    """True si los segmentos ab y cd se cruzan en un punto interior (no cuenta compartir un extremo)."""
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if a == c or a == d or b == c or b == d:
        return False
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0


def triangulate(outer: list, holes: list) -> list:
    """Triangulacion (indices) de un poligono 2D con agujeros por puentes + recorte de orejas. `outer` es CCW y los agujeros CW. Los indices son los de la lista
    concatenada [outer + holes...]."""
    pts = list(outer) + [p for h in holes for p in h]
    ring = list(range(len(outer)))
    offs = len(outer)
    rings = []
    for h in holes:
        rings.append(list(range(offs, offs + len(h))))
        offs += len(h)
    for hr in sorted(rings, key=lambda r: -max(pts[i][0] for i in r)):  # agujeros de derecha a izquierda
        m = max(hr, key=lambda i: pts[i][0])
        order = sorted(range(len(ring)), key=lambda k: (pts[ring[k]][0] - pts[m][0]) ** 2 + (pts[ring[k]][1] - pts[m][1]) ** 2)
        for k in order:  # el vertice visible mas cercano: el puente no cruza ninguna arista
            v = ring[k]
            edges = [(ring[j], ring[(j + 1) % len(ring)]) for j in range(len(ring))] + [(hr[j], hr[(j + 1) % len(hr)]) for j in range(len(hr))]
            if all(not _seg_cross(pts[v], pts[m], pts[a], pts[b]) for a, b in edges):
                j = hr.index(m)
                rot = hr[j:] + hr[:j]
                ring = ring[:k + 1] + rot + [m] + ring[k:]
                break
        else:
            raise ConfigError("No se pudo unir un agujero al contorno de la lamina")
    tris, idx = [], list(ring)
    guard = 0
    while len(idx) > 3 and guard < 20000:
        guard += 1
        ear = False
        for k in range(len(idx)):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            pa, pb, pc = pts[a], pts[b], pts[c]
            if (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0]) <= 1e-18:
                continue  # vertice reflejo o degenerado
            inside = False
            for v in idx:
                if v in (a, b, c) or pts[v] in (pa, pb, pc):
                    continue
                q = pts[v]
                d1 = (pb[0] - pa[0]) * (q[1] - pa[1]) - (pb[1] - pa[1]) * (q[0] - pa[0])
                d2 = (pc[0] - pb[0]) * (q[1] - pb[1]) - (pc[1] - pb[1]) * (q[0] - pb[0])
                d3 = (pa[0] - pc[0]) * (q[1] - pc[1]) - (pa[1] - pc[1]) * (q[0] - pc[0])
                if d1 >= -1e-18 and d2 >= -1e-18 and d3 >= -1e-18:
                    inside = True
                    break
            if not inside:
                tris.append((a, b, c))
                idx.pop(k)
                ear = True
                break
        if not ear:
            raise ConfigError("Triangulacion de la lamina sin orejas: el contorno se cruza o es degenerado")
    tris.append(tuple(idx))
    return tris


def slab(outline: list, thickness: float, holes: list | None = None, bend: dict | None = None) -> tuple:
    """(vertices, caras) de una lamina con grosor: el contorno 3D (y sus agujeros circulares {"center", "radius"}) se triangula en su plano medio, se desplaza
    +-thickness/2 a lo largo de la normal y se cierra con paredes. `bend` = {"p0", "p1", "amount"} curva la lamina a lo largo del eje p0-p1
    (amount * 4 s (1 - s), s en [0, 1]). Genero = numero de agujeros."""
    holes = holes or []
    n = _newell_normal(outline)
    centre = tuple(sum(p[i] for p in outline) / len(outline) for i in range(3))
    e1 = normalize(cross(n, (0.0, 0.0, 1.0)) if abs(n[2]) < 0.9 else cross(n, (1.0, 0.0, 0.0)))
    e2 = cross(n, e1)
    to2 = lambda p: (dot(sub(p, centre), e1), dot(sub(p, centre), e2))  # noqa: E731
    outer3 = list(outline)
    hole_loops3 = []
    for h in holes:
        if "loop" in h:  # agujero poligonal (marco del agujero obturador): puntos 3D en el plano de la lamina
            hole_loops3.append(list(h["loop"]))
            continue
        c, r = h["center"], h["radius"]
        hole_loops3.append([add(c, add(scale(e1, r * math.cos(2 * math.pi * k / 12)), scale(e2, r * math.sin(2 * math.pi * k / 12)))) for k in range(12)])
    o2 = [to2(p) for p in outer3]
    if _area2(o2) < 0:
        outer3, o2 = outer3[::-1], o2[::-1]
    h2 = []
    for loop in hole_loops3:
        pl = [to2(p) for p in loop]
        if _area2(pl) > 0:
            loop, pl = loop[::-1], pl[::-1]
        h2.append(pl)
    hole_loops3 = [lp if _area2([to2(p) for p in lp]) < 0 else lp[::-1] for lp in hole_loops3]
    allp = outer3 + [p for lp in hole_loops3 for p in lp]
    tris = triangulate(o2, h2)

    def shift(p):
        if not bend:
            return 0.0
        a, b = bend["p0"], bend["p1"]
        ab = sub(b, a)
        s = max(0.0, min(1.0, dot(sub(p, a), ab) / dot(ab, ab)))
        return float(bend["amount"]) * 4 * s * (1 - s)
    half = thickness / 2
    top = [add(p, scale(n, half + shift(p))) for p in allp]
    bot = [add(p, scale(n, -half + shift(p))) for p in allp]
    verts = top + bot
    off = len(allp)
    faces = [(a, b, c) for a, b, c in tris] + [(a + off, c + off, b + off) for a, b, c in tris]
    rings = [list(range(len(outer3)))]
    start = len(outer3)
    for lp in hole_loops3:
        rings.append(list(range(start, start + len(lp))))
        start += len(lp)
    for ring in rings:
        for k in range(len(ring)):
            a, b = ring[k], ring[(k + 1) % len(ring)]
            faces.append((a, a + off, b + off, b))
    if signed_volume(verts, faces) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces
