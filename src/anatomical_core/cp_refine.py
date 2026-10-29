"""Geometria de ALTA DENSIDAD del ala iliaca y la copa acetabular `cp.*` (Python puro: devuelve vertices y caras, sin bpy).

Datos: `config/cp/refine.json` (coordenadas en fracciones de la altura H, sistema del mundo).

* Ala iliaca: una LENTE solida con el contorno real del ilion (el del nivel 1, suavizado), no un elipsoide: la malla es un "UV sphere" cuya silueta es el contorno
  y cuyo espesor es una funcion de la posicion (delgada en la fosa, gruesa en la cresta, en la raiz acetabular y en el borde sacro). La lamina media se curva en un
  cuenco abierto hacia medial (fosa iliaca concava) y se acampana hacia lateral en la cresta (cresta iliaca acampanada). El borde rodeado es romo.
* Copa acetabular: casquete esferico grueso que abraza la cabeza del femur (holgura de interlinea) y por el que pasan el isquion y el pubis.
El craneo y la mandibula ya no salen de aqui: se modelan por box modeling con Subdivision Surface en `cp_skullbox`.

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


@lru_cache(maxsize=4)
def _cached(kind: str, key: str, path: str) -> tuple:
    spec = load_refine(path or None)
    if kind == "wing":
        return iliac_wing(spec["iliac_wing"], key)
    return acetabular_cup(spec["acetabular_cup"], key)


def wing(side: str = "L", path: str = "") -> tuple:
    return _cached("wing", side, path)


def cup(side: str = "L", path: str = "") -> tuple:
    return _cached("cup", side, path)
