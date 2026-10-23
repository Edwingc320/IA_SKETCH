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


# --- Marcos locales, rotaciones y cuaterniones ------------------------------------
# Un marco es una tupla (x, y, z) de ejes unitarios del hueso expresados en el espacio
# del modelo; es derecho: x cross y = z. Y es siempre la direccion head->tail.
Frame = tuple[Vec3, Vec3, Vec3]
Mat3 = tuple[Vec3, Vec3, Vec3]  # filas
Quat = tuple[float, float, float, float]  # (w, x, y, z), como mathutils.Quaternion

IDENTITY: Mat3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def frame_from_direction(direction: Vec3, x_hint: Vec3) -> Frame:
    """Marco ortonormal derecho: Y = direccion; X = x_hint proyectado perpendicular a Y."""
    y = normalize(direction)
    x = sub(x_hint, scale(y, dot(x_hint, y)))
    if length(x) < 1e-6:
        raise ValueError(f"frame_x_hint {x_hint!r} es paralelo a la direccion {direction!r}")
    x = normalize(x)
    return (x, y, cross(x, y))


def mirror_frame(f: Frame) -> Frame:
    """Marco del lado derecho a partir del izquierdo: F_R = M F_L M con M = diag(-1,1,1).
    Equivale a x -> pseudovector espejo, y/z -> espejo polar (sigue siendo derecho)."""
    return (mirror_axis(f[0]), mirror_point(f[1]), mirror_point(f[2]))


def mat_vec(m: Mat3, v: Vec3) -> Vec3:
    return (dot(m[0], v), dot(m[1], v), dot(m[2], v))


def mat_mul(a: Mat3, b: Mat3) -> Mat3:
    cols = [(b[0][j], b[1][j], b[2][j]) for j in range(3)]
    return tuple(tuple(dot(row, col) for col in cols) for row in a)  # type: ignore[return-value]


def mat_transpose(m: Mat3) -> Mat3:
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def rotation_matrix(axis: Vec3, angle_rad: float) -> Mat3:
    """Rotacion de regla de la mano derecha alrededor de `axis` (formula de Rodrigues)."""
    x, y, z = normalize(axis)
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    t = 1.0 - c
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def quat_from_axis_angle(axis: Vec3, angle_rad: float) -> Quat:
    x, y, z = normalize(axis)
    s = math.sin(angle_rad / 2.0)
    return (math.cos(angle_rad / 2.0), x * s, y * s, z * s)


def quat_mul(a: Quat, b: Quat) -> Quat:
    """Producto de Hamilton a*b (aplica b primero, luego a)."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


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
