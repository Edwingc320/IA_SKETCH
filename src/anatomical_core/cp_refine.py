"""Geometria de ALTA DENSIDAD del ala iliaca, la copa acetabular y el craneo `cp.*` (Python puro: devuelve vertices y caras, sin bpy).

Datos: `config/cp/refine.json` (coordenadas en fracciones de la altura H; el ala en el sistema del mundo, el craneo relativo al centro de los condilos occipitales).

* Ala iliaca: una LENTE solida con el contorno real del ilion (el del nivel 1, suavizado), no un elipsoide: la malla es un "UV sphere" cuya silueta es el contorno
  y cuyo espesor es una funcion de la posicion (delgada en la fosa, gruesa en la cresta, en la raiz acetabular y en el borde sacro). La lamina media se curva en un
  cuenco abierto hacia medial (fosa iliaca concava) y se acampana hacia lateral en la cresta (cresta iliaca acampanada). El borde rodeado es romo.
* Copa acetabular: casquete esferico grueso que abraza la cabeza del femur (holgura de interlinea) y por el que pasan el isquion y el pubis.
* Craneo: dos parches cerrados ESTRELLADOS (neurocraneo y cara), cada uno con su centro: radio R(direccion) = union de elipsoides + protuberancias + anclajes (puntos de
  hitos por los que la superficie debe pasar). Las cavidades (orbitas, abertura piriforme) son elipsoides `carves` que Blender resta con un Boolean exacto
  (ver `cp_axial`): cavidades reales de paredes nitidas, no marcas.

Todo escala con la altura: las funciones trabajan en H y quien construye multiplica por la altura."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from .config import PROJECT_ROOT, ConfigError, _read_json

CP_DIR = PROJECT_ROOT / "config" / "cp"
FILE = "refine"

Vec = tuple


def load_refine(path: Path | str | None = None) -> dict:
    p = Path(path or CP_DIR / f"{FILE}.json")
    if not p.exists():
        raise ConfigError(f"Falta {p}")
    return _read_json(p)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a))
    if n < 1e-12:
        raise ConfigError("Vector nulo")
    return (a[0] / n, a[1] / n, a[2] / n)


def _smoothstep(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def _mirror(p):
    return (-p[0], p[1], p[2])


def signed_volume(verts, faces) -> float:
    """Volumen con signo de una malla cerrada de caras de 3 o 4 vertices (triangulos en abanico)."""
    v = 0.0
    for f in faces:
        a = verts[f[0]]
        for i in range(1, len(f) - 1):
            b, c = verts[f[i]], verts[f[i + 1]]
            v += _dot(a, _cross(b, c)) / 6.0
    return v


def _orient_outwards(verts, faces):
    if signed_volume(verts, faces) < 0:
        faces = [tuple(reversed(f)) for f in faces]
    return faces


def _uv_faces(n_theta: int, n_rings: int) -> list:
    """Caras de una malla tipo UV sphere: polo 0, anillos 1..n_rings (n_theta vertices cada uno) y polo final. Orden de vertices: polo superior, anillos, polo inferior."""
    faces = []
    top, bottom = 0, 1 + n_rings * n_theta
    ring = lambda j, k: 1 + j * n_theta + (k % n_theta)  # noqa: E731
    for k in range(n_theta):
        faces.append((top, ring(0, k + 1), ring(0, k)))
    for j in range(n_rings - 1):
        for k in range(n_theta):
            faces.append((ring(j, k), ring(j, k + 1), ring(j + 1, k + 1), ring(j + 1, k)))
    for k in range(n_theta):
        faces.append((bottom, ring(n_rings - 1, k), ring(n_rings - 1, k + 1)))
    return faces


# --- ala iliaca ------------------------------------------------------------------------------------------------------------------------------
def _newell(pts):
    n = (0.0, 0.0, 0.0)
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n = _add(n, ((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]), (p[0] - q[0]) * (p[1] + q[1])))
    return _norm(n)


def _ray_polygon_far(poly2, ang):
    """Distancia maxima a la que un rayo desde el origen con angulo `ang` corta el poligono 2D (0 si no lo corta)."""
    dx, dy = math.cos(ang), math.sin(ang)
    best = 0.0
    n = len(poly2)
    for i in range(n):
        ax, ay = poly2[i]
        bx, by = poly2[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < 1e-14:
            continue
        t = (ax * ey - ay * ex) / den  # distancia a lo largo del rayo
        u = (ax * dy - ay * dx) / den  # parametro a lo largo de la arista (0..1)
        if t > 0 and -1e-9 <= u <= 1 + 1e-9:
            best = max(best, t)
    return best


def _smooth_periodic(vals, sigma_samples):
    n = len(vals)
    radius = int(3 * sigma_samples)
    ker = [math.exp(-0.5 * (i / sigma_samples) ** 2) for i in range(-radius, radius + 1)]
    s = sum(ker)
    return [sum(ker[i + radius] * vals[(k + i) % n] for i in range(-radius, radius + 1)) / s for k in range(n)]


def iliac_wing(spec: dict, side: str = "L") -> tuple:
    """(vertices, caras) del ala iliaca (lado L; el R es el espejo) en H, sistema del mundo: lente solida con el contorno del ilion, cuenco medial y cresta acampanada."""
    outline = [tuple(p) for p in spec["outline"]]
    nt, nr = int(spec.get("n_theta", 192)), int(spec.get("n_rings", 80))
    c0 = tuple(sum(p[i] for p in outline) / len(outline) for i in range(3))
    n = _newell(outline)
    if n[0] < 0:
        n = _mul(n, -1)  # la normal apunta hacia lateral (+x en el lado izquierdo)
    e1 = _norm(_cross(n, (0.0, 0.0, 1.0)))
    e2 = _cross(n, e1)
    if e2[2] < 0:
        e1, e2 = _mul(e1, -1), _mul(e2, -1)
    poly = [(_dot(_sub(p, c0), e1), _dot(_sub(p, c0), e2)) for p in outline]
    rim = [_ray_polygon_far(poly, 2 * math.pi * k / nt) for k in range(nt)]
    rim = _smooth_periodic(rim, float(spec.get("smooth_deg", 3.0)) * nt / 360.0)
    margin = float(spec.get("margin", 0.0))
    ext_u = max(abs(p[0]) for p in poly)
    ext_v = max(abs(p[1]) for p in poly)
    k_bowl, k_flare = float(spec["bowl"]), float(spec["flare"])
    twist = float(spec.get("twist", 0.0))
    t0, t_rim, t_crest = float(spec["thickness"]), float(spec["thickness_rim"]), float(spec["thickness_crest"])
    root = tuple(spec["root"])
    root_t, root_s = float(spec["root_thickness"]), float(spec["root_sigma"])
    sac = tuple(spec.get("sacral_edge", c0))
    sac_t, sac_s = float(spec.get("sacral_thickness", 0.0)), float(spec.get("sacral_sigma", 0.02))
    q = float(spec.get("rim_profile", 0.55))

    def thickness(pos, a, b, rho):
        crest = _smoothstep((b / ext_v - 0.15) / 0.8)
        t = t0 + t_rim * rho ** 6 + t_crest * crest * rho ** 3
        t += root_t * math.exp(-_dot(_sub(pos, root), _sub(pos, root)) / root_s ** 2)
        if sac_t:
            t += sac_t * math.exp(-_dot(_sub(pos, sac), _sub(pos, sac)) / sac_s ** 2)
        return t

    def dish(a, b):
        A, B = a / ext_u, b / ext_v
        flare = _smoothstep((B - 0.45) / 0.55) ** 1.6
        return -k_bowl * (A * A + B * B) + k_flare * flare + twist * A * B

    verts = [None]
    for j in range(nr):
        phi = math.pi * (j + 1) / (nr + 1)
        rho, cp_ = math.sin(phi), math.cos(phi)
        for k in range(nt):
            th = 2 * math.pi * k / nt
            a, b = rho * (rim[k] + margin) * math.cos(th), rho * (rim[k] + margin) * math.sin(th)
            mid = _add(c0, _add(_mul(e1, a), _mul(e2, b)))
            off = dish(a, b)
            pos = _add(mid, _mul(n, off))
            t = thickness(mid, a, b, rho)
            verts.append(_add(pos, _mul(n, math.copysign(abs(cp_) ** q, cp_) * t / 2)))
    top_t = thickness(c0, 0.0, 0.0, 0.0)
    verts[0] = _add(c0, _mul(n, dish(0.0, 0.0) + top_t / 2))
    verts.append(_add(c0, _mul(n, dish(0.0, 0.0) - top_t / 2)))
    faces = _uv_faces(nt, nr)
    if side == "R":
        verts = [_mirror(v) for v in verts]
    return verts, _orient_outwards(verts, faces)


# --- copa acetabular --------------------------------------------------------------------------------------------------------------------------
def acetabular_cup(spec: dict, side: str = "L") -> tuple:
    """(vertices, caras) de la copa acetabular en H (mundo): casquete esferico grueso (r_in..r_out) de semiangulo `theta_deg` alrededor de `axis`."""
    c = tuple(spec["center"])
    ax = _norm(tuple(spec["axis"]))
    r_in, r_out = float(spec["r_in"]), float(spec["r_out"])
    th_max = math.radians(float(spec["theta_deg"]))
    nr, ns = int(spec.get("rings", 48)), int(spec.get("sides", 96))
    if not 0 < r_in < r_out:
        raise ConfigError("Copa: se exige 0 < r_in < r_out")
    u = _norm(_cross(ax, (0.0, 0.0, 1.0)) if abs(ax[2]) < 0.9 else _cross(ax, (1.0, 0.0, 0.0)))
    v = _cross(ax, u)
    verts, base = [], {}
    for tag, r in (("o", r_out), ("i", r_in)):
        base[tag] = len(verts)
        verts.append(_add(c, _mul(ax, r)))
        for i in range(1, nr + 1):
            t = th_max * i / nr
            for k in range(ns):
                ph = 2 * math.pi * k / ns
                d = _add(_mul(ax, math.cos(t)), _add(_mul(u, math.sin(t) * math.cos(ph)), _mul(v, math.sin(t) * math.sin(ph))))
                verts.append(_add(c, _mul(d, r)))
    ring = lambda tag, i, k: base[tag] + 1 + (i - 1) * ns + (k % ns)  # noqa: E731
    faces = []
    for tag, flip in (("o", False), ("i", True)):
        f = [(base[tag], ring(tag, 1, k + 1), ring(tag, 1, k)) for k in range(ns)]
        for i in range(1, nr):
            for k in range(ns):
                f.append((ring(tag, i, k), ring(tag, i, k + 1), ring(tag, i + 1, k + 1), ring(tag, i + 1, k)))
        faces += [tuple(reversed(x)) if flip else x for x in f]
    for k in range(ns):
        faces.append((ring("o", nr, k), ring("o", nr, k + 1), ring("i", nr, k + 1), ring("i", nr, k)))
    if side == "R":
        verts = [_mirror(p) for p in verts]
    return verts, _orient_outwards(verts, faces)


# --- craneo (superficie estrellada) ----------------------------------------------------------------------------------------------------------
class _Ellipsoid:
    __slots__ = ("q", "r")

    def __init__(self, q, r):
        self.q, self.r = tuple(q), tuple(r)

    def far(self, c, d):
        """Distancia de salida de un rayo desde `c` (dentro o fuera) en direccion unitaria `d` (0 si no lo corta)."""
        ox, oy, oz = (c[0] - self.q[0]) / self.r[0], (c[1] - self.q[1]) / self.r[1], (c[2] - self.q[2]) / self.r[2]
        dx, dy, dz = d[0] / self.r[0], d[1] / self.r[1], d[2] / self.r[2]
        a = dx * dx + dy * dy + dz * dz
        b = ox * dx + oy * dy + oz * dz
        cc = ox * ox + oy * oy + oz * oz - 1.0
        disc = b * b - a * cc
        if disc < 0:
            return 0.0
        t = (-b + math.sqrt(disc)) / a
        return t if t > 0 else 0.0


def _symmetric(items: list) -> list:
    """Duplica los elementos con `mirror: true` (x -> -x) y devuelve la lista completa."""
    out = []
    for it in items:
        out.append(it)
        if it.get("mirror"):
            m = dict(it)
            for key in ("c", "q", "dir", "at"):
                if key in m:
                    m[key] = _mirror(tuple(m[key]))
            m["mirror"] = False
            out.append(m)
    return out


def _patch_surface(patch: dict) -> tuple:
    """(vertices, caras) de UN parche estrellado del craneo (H, relativo al origen): R(direccion) desde `patch['center']` = union de elipsoides + protuberancias + anclajes."""
    c = tuple(patch["center"])
    ells = [_Ellipsoid(e["c"], e["r"]) for e in _symmetric(patch["ellipsoids"])]
    bumps = []
    for b in _symmetric(patch.get("bumps", [])):
        at = tuple(b["at"])
        dist = math.sqrt(_dot(_sub(at, c), _sub(at, c)))
        bumps.append((_norm(_sub(at, c)), float(b["height"]), float(b["radius"]) / dist))
    anchors = []
    for a in _symmetric(patch.get("anchors", [])):
        at = tuple(a["at"])
        dist = math.sqrt(_dot(_sub(at, c), _sub(at, c)))
        anchors.append((_norm(_sub(at, c)), dist, float(a.get("radius", 0.008)) / dist, float(a.get("max", 0.03))))

    def base(d):
        r = max(e.far(c, d) for e in ells)
        for u, h, al in bumps:
            cs = _dot(d, u)
            if cs > 0.5:
                t = math.acos(min(1.0, cs)) / al
                if t < 1.0:
                    r += h * _smoothstep(1.0 - t) * (1.0 - t * t)
        return r

    deltas = []
    for d, dist, al, mx in anchors:
        delta = dist - base(d)
        if abs(delta) > mx:
            raise ConfigError(f"Anclaje del craneo a {abs(delta):.4f} H de la superficie (maximo {mx})")
        deltas.append((d, delta, al))

    def radius(d):
        r = base(d)
        for u, delta, al in deltas:
            cs = _dot(d, u)
            if cs > 0.9:
                ang = math.acos(min(1.0, cs))
                if ang < 3 * al:
                    r += delta * math.exp(-(ang / al) ** 2)
        return max(r, 0.005)

    nt, nr = int(patch.get("n_theta", 288)), int(patch.get("n_rings", 143))
    verts = [None]
    for j in range(nr):
        phi = math.pi * (j + 1) / (nr + 1)
        sp, cp_ = math.sin(phi), math.cos(phi)
        for k in range(nt):
            th = 2 * math.pi * k / nt
            d = (sp * math.cos(th), sp * math.sin(th), cp_)
            r = radius(d)
            verts.append((c[0] + d[0] * r, c[1] + d[1] * r, c[2] + d[2] * r))
    for d in ((0.0, 0.0, 1.0), (0.0, 0.0, -1.0)):
        r = radius(d)
        pt = (c[0] + d[0] * r, c[1] + d[1] * r, c[2] + d[2] * r)
        if d[2] > 0:
            verts[0] = pt
        else:
            verts.append(pt)
    return verts, _orient_outwards(verts, _uv_faces(nt, nr))


def skull_patches(spec: dict) -> list:
    """[(nombre, vertices, caras)] de los parches estrellados del craneo (neurocraneo y cara): cada uno con su centro, para que los rayos no incidan rasantes."""
    return [(p["name"], *_patch_surface(p)) for p in spec["patches"]]


def skull_carves(spec: dict) -> list:
    """Elipsoides (centro, semiejes) que se restan del craneo (orbitas, abertura piriforme), con sus espejos."""
    return [(tuple(e["c"]), tuple(e["r"])) for e in _symmetric(spec.get("carves", []))]


@lru_cache(maxsize=4)
def _cached(kind: str, key: str, path: str) -> tuple:
    spec = load_refine(path or None)
    if kind == "wing":
        return iliac_wing(spec["iliac_wing"], key)
    if kind == "cup":
        return acetabular_cup(spec["acetabular_cup"], key)
    return skull_patches(spec["skull"])


def wing(side: str = "L", path: str = "") -> tuple:
    return _cached("wing", side, path)


def cup(side: str = "L", path: str = "") -> tuple:
    return _cached("cup", side, path)


def skull_parts(path: str = "") -> list:
    return list(_cached("skull", "", path))


def carves(path: str = "") -> list:
    return skull_carves(load_refine(path or None)["skull"])
