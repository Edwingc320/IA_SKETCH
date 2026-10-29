"""Craneo y mandibula `cp.*` por BOX MODELING estilizado con Subdivision Surface (usa bpy/bmesh; reemplaza a las superficies estrelladas y los tubos inflados).

Flujo (el de un modelador hard-surface):
  1. JAULA de baja resolucion: un cubo subdividido en rejilla cuyos vertices se mapean con perfiles por secciones (anchura, techo y suelo segun la profundidad y un
     achaflanado de las esquinas): bloque con planos duros (frente plana, cara plana, pomulos marcados, base estrecha).
  2. INSET + EXTRUDE hacia dentro sobre las caras de la rejilla: orbitas (dos escalones), abertura piriforme y fosas temporales hundidas; sin anillos pegados por fuera.
  3. Piezas de caja barridas (`sweep_box`: secciones rectangulares achaflanadas a lo largo de un camino): arcos cigomaticos planos, arcada dental, y la MANDIBULA entera
     (condilo, rama ascendente recta, gonion en esquina, cuerpo y menton plano) como UN solo barrido en U sin costuras.
  4. CREASES (aristas duras) en las aristas clave y en los bordes de las cavidades, y Subdivision Surface nivel 2 (se aplica): silueta de dibujo animado sin redondear
     en exceso. El resultado es una superficie cerrada (manifold) de decenas de miles de caras.

Todo en fracciones de H, relativo al origen del craneo (centro de los condilos occipitales)."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

CAGE_SEGMENTS = 40  # divisiones por arista del cubo de la jaula del craneo (28 x 28 caras por lado)
SUBSURF_LEVELS = 2
CREASE_HARD = 0.65  # aristas del bloque
CREASE_RIM = 0.85  # bordes de las cavidades

# perfiles del bloque craneo-facial segun la profundidad y (H, relativo al origen del craneo; y negativa = adelante)
Y_FRONT, Y_BACK = -0.0762, 0.0455
PROFILE = [  # y, z_techo, z_suelo, semianchura
    (-0.0762, 0.0230, -0.0370, 0.0290),
    (-0.0700, 0.0400, -0.0370, 0.0325),
    (-0.0620, 0.0560, -0.0360, 0.0345),
    (-0.0500, 0.0680, -0.0310, 0.0385),
    (-0.0300, 0.0765, -0.0160, 0.0408),
    (-0.0100, 0.0775, -0.0100, 0.0412),
    (0.0100, 0.0745, -0.0110, 0.0400),
    (0.0250, 0.0715, -0.0120, 0.0352),
    (0.0360, 0.0590, -0.0090, 0.0285),
    (Y_BACK, 0.0310, -0.0030, 0.0150),
]


def _interp(table, y, col):
    if y <= table[0][0]:
        return table[0][col]
    for a, b in zip(table, table[1:]):
        if y <= b[0]:
            t = (y - a[0]) / (b[0] - a[0])
            return a[col] + (b[col] - a[col]) * t
    return table[-1][col]


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _layer(bm):
    """Capa de crease de las aristas (crearla invalida las referencias a aristas: se crea al empezar cada malla)."""
    return bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")


def _set_crease(bm, edges, value):
    layer = _layer(bm)
    for e in edges:
        e[layer] = max(e[layer], value)


def _append(bm, other):
    """Copia vertices, caras y creases de `other` en `bm` (piezas sueltas de un mismo objeto)."""
    src = other.edges.layers.float.get("crease_edge")
    dst = _layer(bm)
    m = {v: bm.verts.new(v.co) for v in other.verts}
    for f in other.faces:
        bm.faces.new([m[v] for v in f.verts])
    if src:
        for e in other.edges:
            if e[src] > 0:
                ne = bm.edges.get((m[e.verts[0]], m[e.verts[1]]))
                if ne:
                    ne[dst] = e[src]
    other.free()


def _cube_edges(bm):
    """Aristas del cubo original (las que quedan sobre una arista del cubo de lado 2 antes de mapearlo)."""
    out = []
    for e in bm.edges:
        a, b = e.verts[0].co, e.verts[1].co
        if sum(abs(abs(x) - 1.0) < 1e-6 and abs(abs(y) - 1.0) < 1e-6 and (x > 0) == (y > 0) for x, y in zip(a, b)) >= 2:
            out.append(e)
    return out


def box_cage(centre, half, segments=3, crease=CREASE_HARD):
    """Cubo de semilados `half` (x, y, z) centrado en `centre`, subdividido en `segments` + 1 por arista, con las aristas del cubo en crease."""
    bm = bmesh.new()
    _layer(bm)
    bmesh.ops.create_cube(bm, size=2.0)
    if segments:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=segments, use_grid_fill=True)
    edges = _cube_edges(bm)
    _set_crease(bm, edges, crease)
    for v in bm.verts:
        v.co = Vector((centre[0] + v.co.x * half[0], centre[1] + v.co.y * half[1], centre[2] + v.co.z * half[2]))
    return bm


def sweep_box(rings, chamfer=0.30, crease=CREASE_HARD, cap=True):
    """Barrido de secciones rectangulares achaflanadas: `rings` = [(centro, eje_ancho, semi_ancho, semi_espesor)]. Las aristas longitudinales llevan crease."""
    bm = bmesh.new()
    _layer(bm)
    centres = [Vector(r[0]) for r in rings]
    grid = []
    for i, (c, ew, w, t) in enumerate(rings):
        a, b = centres[max(i - 1, 0)], centres[min(i + 1, len(rings) - 1)]
        tang = (b - a).normalized()
        ew = Vector(ew)
        ew = (ew - tang * ew.dot(tang)).normalized()
        et = tang.cross(ew).normalized()
        fw, ft = chamfer * w, chamfer * t
        pts = [(w - fw, t), (w, t - ft), (w, -(t - ft)), (w - fw, -t), (-(w - fw), -t), (-w, -(t - ft)), (-w, t - ft), (-(w - fw), t)]
        grid.append([bm.verts.new(Vector(c) + ew * p + et * q) for p, q in pts])
    longitudinal = []
    for i in range(len(grid) - 1):
        for k in range(8):
            bm.faces.new((grid[i][k], grid[i][(k + 1) % 8], grid[i + 1][(k + 1) % 8], grid[i + 1][k]))
            longitudinal.append(bm.edges.get((grid[i][k], grid[i + 1][k])))
    if cap:
        bm.faces.new(grid[0])
        bm.faces.new(list(reversed(grid[-1])))
    _set_crease(bm, [e for e in longitudinal if e], crease)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _snap_to_ellipse(faces, centre, radii, axes=(0, 2)):
    """Lleva los vertices del borde de la region (en el plano de los ejes `axes`, por defecto x-z) sobre la elipse (centro, semiejes): el contorno del reborde queda liso."""
    a0, a1 = axes
    fs = set(faces)
    edges = {e for f in faces for e in f.edges}
    for v in {v for e in edges if sum(1 for g in e.link_faces if g in fs) == 1 for v in e.verts}:
        p, q = (v.co[a0] - centre[0]) / radii[0], (v.co[a1] - centre[1]) / radii[1]
        r = math.hypot(p, q)
        if r > 1e-9:
            co = v.co.copy()
            co[a0], co[a1] = centre[0] + p / r * radii[0], centre[1] + q / r * radii[1]
            v.co = co


def _pocket(bm, faces, thickness, depth, direction, crease=CREASE_RIM, ellipse=None, axes=(0, 2)) -> list:
    """Inset + Extrude hacia dentro: inset de la region `faces`, hunde la region interior `depth` a lo largo de `direction`, marca con crease los bordes del anillo y
    devuelve las caras de la region interior (para encadenar otro escalon)."""
    if ellipse:
        _snap_to_ellipse(faces, *ellipse, axes=axes)
    region = list(faces)  # tras el inset estas caras son la region INTERIOR; las nuevas (`ring`) son el anillo del reborde
    ring = set(bmesh.ops.inset_region(bm, faces=faces, thickness=thickness, depth=0.0, use_even_offset=False, use_boundary=True)["faces"])
    loop = [e for f in ring for e in f.edges if sum(1 for g in e.link_faces if g in ring) == 1]
    inner = region
    bmesh.ops.translate(bm, vec=Vector(direction) * depth, verts=list({v for f in inner for v in f.verts}))
    _set_crease(bm, loop, crease)
    return list(inner)


def skull_cage() -> "bmesh.types.BMesh":
    """Jaula del craneo: bloque con planos duros y cavidades por Inset/Extrude."""
    bm = bmesh.new()
    _layer(bm)
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=CAGE_SEGMENTS - 1, use_grid_fill=True)
    hard = _cube_edges(bm)
    _set_crease(bm, hard, CREASE_HARD)
    for v in bm.verts:
        u, w, vv = v.co.x, v.co.z, v.co.y  # u lateral, w vertical, vv profundidad (-1 delante)
        y = Y_FRONT + (Y_BACK - Y_FRONT) * (vv + 1.0) / 2.0
        zt, zb, hw = _interp(PROFILE, y, 1), _interp(PROFILE, y, 2), _interp(PROFILE, y, 3)
        s = (w + 1.0) / 2.0  # 0 abajo .. 1 arriba
        # achaflanado: la base y el techo de la seccion se estrechan (esquinas cortadas, no cilindro)
        lower = 0.56 + 0.44 * _smooth(s / 0.46)
        upper = 1.0 - 0.60 * _smooth((s - 0.56) / 0.44)
        width = hw * lower * upper
        # cara plana: bajo la linea de las orbitas y por delante de los pomulos la mitad inferior se estrecha (maxilar)
        face = _smooth((-0.050 - y) / 0.014)
        z = zb + s * (zt - zb)
        width *= 1.0 - 0.30 * face * _smooth((-0.004 - z) / 0.028)
        # pomulos marcados: salientes laterales a la altura de los malares
        cheek = math.exp(-(((y + 0.060) / 0.012) ** 2 + ((z + 0.004) / 0.012) ** 2))
        width *= 1.0 + 0.09 * cheek
        v.co = Vector((u * width, y, z))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    # --- cavidades por Inset + Extrude hacia dentro
    front = [f for f in bm.faces if f.normal.y < -0.5 and abs(f.calc_center_median().y - Y_FRONT) < 1e-6]
    for sx in (1.0, -1.0):
        orb = [f for f in front if ((f.calc_center_median().x - sx * 0.0183) / 0.0108) ** 2 + ((f.calc_center_median().z - 0.0040) / 0.0100) ** 2 < 1.0]
        step = _pocket(bm, orb, 0.0016, 0.0085, (0, 1, 0), ellipse=((sx * 0.0183, 0.0040), (0.0108, 0.0100)))  # reborde y primer escalon de la orbita
        _pocket(bm, step, 0.0020, 0.0110, (0, 1, 0), ellipse=((sx * 0.0183, 0.0040), (0.0092, 0.0084)))  # fondo de la orbita
    nose = [f for f in front if ((f.calc_center_median().x) / 0.0068) ** 2 + ((f.calc_center_median().z + 0.0135) / 0.0105) ** 2 < 1.0]
    step = _pocket(bm, nose, 0.0014, 0.0070, (0, 1, 0), ellipse=((0.0, -0.0135), (0.0068, 0.0105)))
    _pocket(bm, step, 0.0016, 0.0070, (0, 1, 0), ellipse=((0.0, -0.0135), (0.0054, 0.0091)))
    for sx in (1.0, -1.0):  # fosa temporal hundida
        side = [f for f in bm.faces if f.normal.x * sx > 0.5 and -0.044 < f.calc_center_median().y < -0.008 and 0.012 < f.calc_center_median().z < 0.046 and abs(f.calc_center_median().x) > 0.030]
        _pocket(bm, side, 0.0020, 0.0030, (-sx, 0, 0), crease=0.3)  # sin ajuste a elipse: la superficie lateral es curva y el ajuste la arruga
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def box_skull_cage() -> "bmesh.types.BMesh":
    """Cage completa del craneo: bloque + arcos cigomaticos planos + mastoides + condilos occipitales + arcada dental (todo en cajas)."""
    bm = skull_cage()
    for sx in (1.0, -1.0):
        arch = sweep_box([((sx * 0.0300, -0.0585, -0.0090), (0, 0, 1), 0.0040, 0.0017), ((sx * 0.0380, -0.0490, -0.0087), (0, 0, 1), 0.0044, 0.0018), ((sx * 0.0398, -0.0330, -0.0078), (0, 0, 1), 0.0044, 0.0018),
                          ((sx * 0.0385, -0.0190, -0.0060), (0, 0, 1), 0.0040, 0.0018), ((sx * 0.0345, -0.0100, -0.0040), (0, 0, 1), 0.0038, 0.0018)])
        _append(bm, arch)
        _append(bm, box_cage((sx * 0.0194, -0.0139, -0.0138), (0.0070, 0.0085, 0.0110), segments=5))  # apofisis mastoides
        _append(bm, box_cage((sx * 0.0120, 0.0040, -0.0045), (0.0060, 0.0140, 0.0050), segments=4))  # condilos occipitales
    teeth = sweep_box([((-0.0225, -0.0560, -0.0345), (0, 0, 1), 0.0046, 0.0034), ((-0.0120, -0.0710, -0.0365), (0, 0, 1), 0.0046, 0.0034), ((0.0, -0.0765, -0.0370), (0, 0, 1), 0.0046, 0.0034),
                       ((0.0120, -0.0710, -0.0365), (0, 0, 1), 0.0046, 0.0034), ((0.0225, -0.0560, -0.0345), (0, 0, 1), 0.0046, 0.0034)])
    _append(bm, teeth)
    return bm


def jaw_cage() -> "bmesh.types.BMesh":
    """Mandibula: UN barrido en U de secciones rectangulares (condilo -> rama recta -> gonion en esquina -> cuerpo -> menton plano -> lado opuesto)."""
    left = [  # centro, eje del ancho, semi_ancho, semi_espesor
        ((0.0290, -0.0322, -0.0085), (0, 1, 0), 0.0050, 0.0042),  # condilo
        ((0.0288, -0.0320, -0.0128), (0, 1, 0), 0.0040, 0.0030),  # cuello condilar
        ((0.0298, -0.0300, -0.0200), (0, 1, 0), 0.0075, 0.0030),  # rama (apofisis coronoides adelante)
        ((0.0306, -0.0278, -0.0320), (0, 1, 0), 0.0092, 0.0030),
        ((0.0302, -0.0240, -0.0420), (0, 1, 0), 0.0088, 0.0040),  # gonion (angulo)
        ((0.0302, -0.0262, -0.0452), (0, 0.6, 0.8), 0.0080, 0.0046),
        ((0.0296, -0.0310, -0.0468), (0, 0, 1), 0.0072, 0.0050),  # cuerpo
        ((0.0250, -0.0470, -0.0482), (0, 0, 1), 0.0070, 0.0052),
        ((0.0170, -0.0600, -0.0488), (0, 0, 1), 0.0068, 0.0054),
        ((0.0080, -0.0690, -0.0490), (0, 0, 1), 0.0068, 0.0056),
    ]
    mid = [((0.0, -0.0720, -0.0490), (0, 0, 1), 0.0070, 0.0058)]  # menton plano
    right = [((-c[0], c[1], c[2]), (-e[0], e[1], e[2]), w, t) for c, e, w, t in reversed(left)]
    bm = sweep_box(left + mid + right, chamfer=0.30, crease=CREASE_HARD)
    # arcada dental inferior
    teeth = sweep_box([((-0.0210, -0.0560, -0.0405), (0, 0, 1), 0.0044, 0.0034), ((-0.0110, -0.0700, -0.0420), (0, 0, 1), 0.0044, 0.0034), ((0.0, -0.0750, -0.0425), (0, 0, 1), 0.0044, 0.0034),
                       ((0.0110, -0.0700, -0.0420), (0, 0, 1), 0.0044, 0.0034), ((0.0210, -0.0560, -0.0405), (0, 0, 1), 0.0044, 0.0034)])
    _append(bm, teeth)
    return bm


def subdivide(bm, levels: int = SUBSURF_LEVELS, scale: float = 1000.0) -> tuple:
    """Aplica una Subdivision Surface (con creases) a la jaula y devuelve (vertices, caras) en H. Trabaja a escala x`scale` y libera `bm`."""
    me = bpy.data.meshes.new("cp_tmp_cage")
    for v in bm.verts:
        v.co *= scale
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("cp_tmp_cage", me)
    bpy.context.scene.collection.objects.link(obj)
    try:
        mod = obj.modifiers.new("cp_subsurf", "SUBSURF")
        mod.levels = mod.render_levels = levels
        mod.use_creases = True
        mod.subdivision_type = "CATMULL_CLARK"
        bpy.context.view_layer.update()
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier=mod.name)
        verts = [tuple(c / scale for c in v.co) for v in obj.data.vertices]
        faces = [tuple(p.vertices) for p in obj.data.polygons]
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(me)
    return verts, faces


_CACHE: dict = {}


def box_skull() -> tuple:
    if "skull" not in _CACHE:
        _CACHE["skull"] = subdivide(box_skull_cage())
    return _CACHE["skull"]


def box_mandible() -> tuple:
    if "jaw" not in _CACHE:
        _CACHE["jaw"] = subdivide(jaw_cage())
    return _CACHE["jaw"]
