"""Matematica vectorial minima y primitivas de visualizacion (Python puro, sin bpy).

Convencion de coordenadas (la de Blender): +Z arriba, el personaje mira hacia -Y,
su lado izquierdo es +X. Unidades: metros.
"""
from __future__ import annotations

import math

Vec3 = tuple[float, float, float]


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec3, k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def is_finite(a) -> bool:
    return all(isinstance(c, (int, float)) and math.isfinite(c) for c in a)


def normalize(a: Vec3) -> Vec3:
    if not is_finite(a):
        raise ValueError(f"vector no finito: {a!r}")
    n = length(a)
    if n < 1e-12:
        raise ValueError("no se puede normalizar un vector nulo")
    return scale(a, 1.0 / n)


def mirror_point(p: Vec3) -> Vec3:
    """Refleja un punto/vector polar respecto al plano YZ (lado izquierdo <-> derecho)."""
    return (-p[0], p[1], p[2])


def mirror_axis(a: Vec3) -> Vec3:
    """Refleja un eje de rotacion (pseudovector) respecto al plano YZ: (x, -y, -z)."""
    return (a[0], -a[1], -a[2])


def _perpendicular_basis(d: Vec3) -> tuple[Vec3, Vec3]:
    helper = (1.0, 0.0, 0.0) if abs(d[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = normalize(cross(d, helper))
    v = normalize(cross(d, u))
    return u, v


def bone_shape(head: Vec3, tail: Vec3, width_ratio: float = 0.12):
    """Malla de visualizacion de un hueso: octaedro alargado (6 vertices, 8 triangulos).

    No es anatomia: solo una forma para ver el hueso en renders y viewport.
    Devuelve (vertices, caras).
    """
    d = sub(tail, head)
    ln = length(d)
    dn = normalize(d)
    u, v = _perpendicular_basis(dn)
    w = ln * width_ratio
    ring_center = add(head, scale(dn, ln * 0.15))
    ring = [
        add(ring_center, add(scale(u, w), scale(v, 0.0))),
        add(ring_center, add(scale(u, 0.0), scale(v, w))),
        add(ring_center, add(scale(u, -w), scale(v, 0.0))),
        add(ring_center, add(scale(u, 0.0), scale(v, -w))),
    ]
    verts = [head, *ring, tail]
    faces = []
    for i in range(4):
        j = (i + 1) % 4
        faces.append((0, 1 + j, 1 + i))
        faces.append((5, 1 + i, 1 + j))
    return verts, faces


def icosphere(center: Vec3, radius: float, subdivisions: int = 1):
    """Esfera de baja resolucion (icosaedro subdividido). Devuelve (vertices, caras)."""
    t = (1.0 + math.sqrt(5.0)) / 2.0
    base = [
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ]
    verts = [normalize(tuple(float(c) for c in p)) for p in base]
    faces = [
        (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
        (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
        (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
        (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
    ]
    for _ in range(subdivisions):
        cache: dict[tuple[int, int], int] = {}

        def midpoint(a: int, b: int) -> int:
            key = (min(a, b), max(a, b))
            if key not in cache:
                m = normalize(scale(add(verts[a], verts[b]), 0.5))
                verts.append(m)
                cache[key] = len(verts) - 1
            return cache[key]

        new_faces = []
        for a, b, c in faces:
            ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
            new_faces += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new_faces
    return [add(center, scale(p, radius)) for p in verts], faces
