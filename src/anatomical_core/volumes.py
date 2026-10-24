"""Formas volumetricas parametricas de los huesos del nivel 1 (Python puro, sin bpy).

Hoy solo la boveda craneal: una superficie redondeada cuyo corte medio-sagital es el contorno del craneo (redondeado con una
B-spline cubica cerrada) y cuya anchura maxima (ancho biparietal, en X) sale del indice cefalico: ancho = indice x longitud
sagital (frente-occipucio, en Y). Es un elipsoide generalizado: cada punto del perfil, a una distancia r del centro C del
perfil, se desplaza lateralmente x = W sin(psi) mientras (y, z) se acercan a C como cos(psi). La forma es cerrada, simetrica en
X y escala linealmente con el contorno (que ya depende de la altura).
"""
from __future__ import annotations

import math

from .geometry import Vec3


class VolumeError(ValueError):
    pass


def smooth_closed_profile(points_yz: list, samples_per_edge: int = 8) -> list:
    """B-spline cubica uniforme cerrada con los puntos (y, z) como puntos de control: perfil redondeado que APROXIMA el contorno
    (redondea las esquinas: el vertex y el prostion quedan algo por dentro) en lugar de pasar por cada vertice."""
    n = len(points_yz)
    if n < 4:
        raise VolumeError("El perfil necesita al menos 4 puntos")
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (points_yz[(i + k) % n] for k in (-1, 0, 1, 2))
        for s in range(samples_per_edge):
            t = s / samples_per_edge
            t2, t3 = t * t, t * t * t
            out.append(tuple(((-t3 + 3 * t2 - 3 * t + 1) * a + (3 * t3 - 6 * t2 + 4) * b + (-3 * t3 + 3 * t2 + 3 * t + 1) * c + t3 * d) / 6.0
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    return out


def _centroid(poly: list) -> tuple:
    a = cy = cz = 0.0
    for (y0, z0), (y1, z1) in zip(poly, poly[1:] + poly[:1]):
        cross = y0 * z1 - y1 * z0
        a += cross
        cy += (y0 + y1) * cross
        cz += (z0 + z1) * cross
    if abs(a) < 1e-18:
        raise VolumeError("Perfil degenerado (area nula)")
    return cy / (3 * a), cz / (3 * a)


def _ray_radius(center: tuple, direction: tuple, poly: list) -> float:
    best = None
    cy, cz = center
    dy, dz = direction
    for (y0, z0), (y1, z1) in zip(poly, poly[1:] + poly[:1]):
        ey, ez = y1 - y0, z1 - z0
        den = dy * ez - dz * ey
        if abs(den) < 1e-18:
            continue
        t = ((y0 - cy) * ez - (z0 - cz) * ey) / den
        u = ((y0 - cy) * dz - (z0 - cz) * dy) / den
        if t > 1e-12 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best):
            best = t
    if best is None:
        raise VolumeError("El perfil no es estrellado respecto a su centro")
    return best


def cranium_mesh(outline: tuple, spec: dict) -> tuple:
    """(vertices, caras) de la boveda craneal para el contorno medio-sagital `outline` (Vec3 en el plano x = 0)."""
    if any(abs(p[0]) > 1e-9 for p in outline):
        raise VolumeError("El contorno del craneo debe estar en el plano medio (x = 0)")
    profile = smooth_closed_profile([(p[1], p[2]) for p in outline])
    cy, cz = _centroid(profile)
    length_y = max(p[0] for p in profile) - min(p[0] for p in profile)
    half_width = float(spec["cephalic_index"]) * length_y / 2.0
    n_theta, m = int(spec["theta_segments"]), int(spec["lateral_segments"])
    if m % 2:
        raise VolumeError("lateral_segments debe ser par (el corte medio-sagital pasa por un anillo)")
    radii = []
    for k in range(n_theta):
        th = 2 * math.pi * k / n_theta
        d = (math.cos(th), math.sin(th))
        radii.append((d, _ray_radius((cy, cz), d, profile)))
    verts: list = []
    for j in range(1, m):  # anillos laterales sin los polos
        psi = -math.pi / 2 + math.pi * j / m
        cp, sp = math.cos(psi), math.sin(psi)
        for (dy, dz), r in radii:
            verts.append((half_width * sp, cy + r * dy * cp, cz + r * dz * cp))
    south, north = len(verts), len(verts) + 1
    verts += [(-half_width, cy, cz), (half_width, cy, cz)]
    faces: list = []
    for j in range(m - 2):
        for k in range(n_theta):
            a, b = j * n_theta + k, j * n_theta + (k + 1) % n_theta
            faces.append((a, b, b + n_theta, a + n_theta))
    for k in range(n_theta):
        k2 = (k + 1) % n_theta
        faces.append((south, k2, k))  # polo -X
        last = (m - 2) * n_theta
        faces.append((north, last + k, last + k2))  # polo +X
    if signed_volume(verts, faces) < 0:  # normales hacia fuera
        faces = [tuple(reversed(f)) for f in faces]
    return verts, faces


def signed_volume(verts: list, faces: list) -> float:
    """Volumen con signo (m3) de una malla cerrada de caras triangulares o cuadrangulares."""
    total = 0.0
    for f in faces:
        for i in range(1, len(f) - 1):
            a, b, c = verts[f[0]], verts[f[i]], verts[f[i + 1]]
            total += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return total


def euler_characteristic(verts: list, faces: list) -> int:
    edges = set()
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            edges.add((min(a, b), max(a, b)))
    return len(verts) - len(edges) + len(faces)


def bounding_box(verts: list) -> tuple:
    return tuple(min(v[i] for v in verts) for i in range(3)), tuple(max(v[i] for v in verts) for i in range(3))


def volume_mesh(bone) -> tuple:
    """Malla de la forma volumetrica de un AnatomyBone (None si el hueso no declara `volume`)."""
    if not bone.volume:
        return None
    return cranium_mesh(bone.outline, bone.volume)
