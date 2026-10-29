"""Esqueleto pelvico-femoral-lumbar PARAMETRICO generado desde cero en Blender (usa bpy; independiente de las mallas oseas anteriores `BM_*`).

Genera objetos independientes con el prefijo `cp.` (indice de generacion):

    cp.Pelvis       ilion + pubis + isquion (anillo con agujero obturador) + sacro + coccix; origen en el punto medio de los dos centros acetabulares
    cp.FemurL/R     femur completo; origen en el CENTRO DE LA CABEZA (articulacion esferica de la cadera)
    cp.LumbarSpine  L1-L5 con discos, naciendo del sacro; origen en el centro del disco L5-S1 (articulacion lumbosacra)

Todo se define en fracciones de la altura H (por defecto 1.75 m), asi que `--height` reescala el conjunto con las mismas proporciones. Cada pieza guarda su
dimension de referencia (`cp_ref_dim_m`) y `cp_resize(obj, nueva_dimension_m)` la redimensiona de forma UNIFORME alrededor de su origen (misma estructura y
proporcion); al redimensionar la pelvis, los hijos (femures, columna) siguen a sus anclajes articulares.

Convenciones del proyecto: +X izquierda, -Y adelante, +Z arriba; metros. Las mallas se construyen directamente en coordenadas locales (transformaciones
aplicadas: escala 1, rotacion 0, origen en el centro articular), sin vertex groups, y los femures y la columna se emparentan a la pelvis conservando su
transformacion (Keep Transform)."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import cp_refine

PREFIX = "cp."
REF_HEIGHT_M = 1.75
# cadena de emparentamiento (hijo -> padre): todo cuelga de la pelvis; el orden es de la pelvis hacia fuera
PARENTS = {"cp.FemurL": "cp.Pelvis", "cp.FemurR": "cp.Pelvis", "cp.LumbarSpine": "cp.Pelvis", "cp.ThoracicSpine": "cp.LumbarSpine", "cp.CervicalSpine": "cp.ThoracicSpine",
           "cp.Skull": "cp.CervicalSpine", "cp.Mandible": "cp.Skull",
           # piezas independientes del craneo: cuelgan de la boveda (cp.Skull) y comparten su origen; no se unen en un solo solido
           "cp.SkullFace": "cp.Skull", "cp.ZygomaticL": "cp.Skull", "cp.ZygomaticR": "cp.Skull",
            "cp.CondyleL": "cp.Skull", "cp.CondyleR": "cp.Skull", "cp.TeethUpper": "cp.Skull", "cp.TeethLower": "cp.Mandible",
           # los cinco huesos de la boveda (cascaras independientes sobre el nucleo cp.Skull)
           "cp.SkullFrontal": "cp.Skull", "cp.SkullOccipital": "cp.Skull", "cp.ParietalL": "cp.Skull", "cp.ParietalR": "cp.Skull", "cp.TemporalL": "cp.Skull", "cp.TemporalR": "cp.Skull",
           "cp.SphenoidL": "cp.Skull", "cp.SphenoidR": "cp.Skull"}
FOLLOW_PARENT_SCALE = ("cp.SkullFace", "cp.ZygomaticL", "cp.ZygomaticR", "cp.CondyleL", "cp.CondyleR", "cp.TeethUpper",
                       "cp.TeethLower", "cp.SkullFrontal", "cp.SkullOccipital", "cp.ParietalL", "cp.ParietalR", "cp.TemporalL", "cp.TemporalR", "cp.SphenoidL", "cp.SphenoidR")  # cambian de tamano con su pieza madre (cp_resize)
# Colecciones por seccion, anidadas bajo CP_Skeleton: (ruta) -> objetos que contiene (cada objeto en UNA sola coleccion; el parentesco no cambia)
SECTIONS = {
    ("Pelvis",): ("cp.Pelvis",),
    ("Femures",): ("cp.FemurL", "cp.FemurR"),
    ("Columna", "Lumbar"): ("cp.LumbarSpine",),
    ("Columna", "Toracica"): ("cp.ThoracicSpine",),
    ("Columna", "Cervical"): ("cp.CervicalSpine",),
    ("Craneo", "Neurocraneo"): ("cp.Skull", "cp.SkullFrontal", "cp.ParietalL", "cp.ParietalR", "cp.TemporalL", "cp.TemporalR", "cp.SkullOccipital", "cp.SphenoidL", "cp.SphenoidR",
                                "cp.CondyleL", "cp.CondyleR"),
    ("Craneo", "Viscerocraneo"): ("cp.SkullFace", "cp.ZygomaticL", "cp.ZygomaticR", "cp.Mandible"),
    ("Craneo", "Dientes"): ("cp.TeethUpper", "cp.TeethLower"),
}
# Los 22 huesos principales del craneo (8 del neurocraneo + 14 del viscerocraneo): referencia de lo que falta por modelar, guardada en la coleccion (propiedad `cp_huesos_esperados`)
SKULL_BONES_EXPECTED = {
    "Neurocraneo": ("Frontal", "Parietal D", "Parietal I", "Temporal D", "Temporal I", "Occipital", "Esfenoides", "Etmoides"),
    "Viscerocraneo": ("Maxilar D", "Maxilar I", "Cigomatico D", "Cigomatico I", "Nasal D", "Nasal I", "Lagrimal D", "Lagrimal I", "Palatino D", "Palatino I",
                      "Cornete inferior D", "Cornete inferior I", "Vomer", "Mandibula"),
}
SIDES = 20
CAP_RINGS = 3
BONE_COLOR = (0.95, 0.92, 0.84, 1.0)
HI_SIDES, HI_STEPS = 48, 14  # resolucion de los tubos de la pelvis y la mandibula (alta densidad)

# --- proporciones (fracciones de H; derivadas de Drillis y Contini y de la anatomia de referencia) ------------------------------------------------
HIP_X, HIP_Z = 0.052, 0.530  # centro acetabular (x lateral, z altura)
THIGH_LENGTH = 0.245  # centro de la cabeza femoral - centro de la rodilla
HEAD_R = 0.0126
LUMBAR_Z0, LUMBAR_Y0 = 0.571, 0.020  # centro del disco L5-S1
BODY_H, DISC_H = 0.0156, 0.0058


def _v(x, y, z, h: float) -> Vector:
    return Vector((x, y, z)) * h


# --- primitivas ------------------------------------------------------------------------------------------------------------------------------
def _catmull(p0, p1, p2, p3, t):
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def tube(bm, pts, radii, ref=(1.0, 0.0, 0.0), caps=(None, None), sides=SIDES, steps=6):
    """Tubo de seccion eliptica (semiejes `radii[i] = (a, b)`) por la trayectoria Catmull-Rom de `pts`, cerrado con casquetes (longitud = `caps`, por defecto el
    semieje mayor del extremo). Marco por transporte paralelo; `ref` orienta el semieje `a`."""
    pts = [Vector(p) for p in pts]
    if len(pts) == 2:
        pts = [pts[0], pts[0].lerp(pts[1], 0.5), pts[1]]
        radii = [radii[0], tuple((a + b) / 2 for a, b in zip(*radii)), radii[1]]
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    samples = []
    for i in range(len(pts) - 1):
        for k in range(steps):
            t = k / steps
            s = t * t * (3 - 2 * t)
            samples.append((_catmull(ext[i], ext[i + 1], ext[i + 2], ext[i + 3], t), radii[i][0] + (radii[i + 1][0] - radii[i][0]) * s, radii[i][1] + (radii[i + 1][1] - radii[i][1]) * s))
    samples.append((pts[-1], radii[-1][0], radii[-1][1]))
    n = len(samples)
    tang = [(samples[min(i + 1, n - 1)][0] - samples[max(i - 1, 0)][0]).normalized() for i in range(n)]
    u = Vector(ref) - tang[0] * Vector(ref).dot(tang[0])
    u = u.normalized() if u.length > 1e-9 else tang[0].orthogonal().normalized()
    frames = []
    for i, t in enumerate(tang):
        if i:
            u = u - t * u.dot(t)
            u = u.normalized() if u.length > 1e-9 else t.orthogonal().normalized()
        frames.append((u.copy(), t.cross(u)))
    c0, a0, b0 = samples[0]
    c1, a1, b1 = samples[-1]
    cs = caps[0] if caps[0] is not None else max(a0, b0)
    ce = caps[1] if caps[1] is not None else max(a1, b1)
    rings = []
    for j in range(CAP_RINGS, 0, -1):
        ang = j / (CAP_RINGS + 1) * math.pi / 2
        rings.append((c0 - tang[0] * math.sin(ang) * cs, a0 * math.cos(ang), b0 * math.cos(ang), *frames[0]))
    rings += [(c, a, b, *f) for (c, a, b), f in zip(samples, frames)]
    for j in range(1, CAP_RINGS + 1):
        ang = j / (CAP_RINGS + 1) * math.pi / 2
        rings.append((c1 + tang[-1] * math.sin(ang) * ce, a1 * math.cos(ang), b1 * math.cos(ang), *frames[-1]))
    grid = []
    for c, a, b, uu, vv in rings:
        grid.append([bm.verts.new(c + uu * (a * math.cos(2 * math.pi * k / sides)) + vv * (b * math.sin(2 * math.pi * k / sides))) for k in range(sides)])
    for i in range(len(grid) - 1):
        for k in range(sides):
            bm.faces.new((grid[i][k], grid[i][(k + 1) % sides], grid[i + 1][(k + 1) % sides], grid[i + 1][k]))
    p0, p1 = bm.verts.new(c0 - tang[0] * cs), bm.verts.new(c1 + tang[-1] * ce)
    for k in range(sides):
        bm.faces.new((p0, grid[0][(k + 1) % sides], grid[0][k]))
        bm.faces.new((p1, grid[-1][k], grid[-1][(k + 1) % sides]))


def ellipsoid(bm, centre, radii, axes=None, segments=SIDES + 4, rings=14):
    """Elipsoide de semiejes `radii` orientado por `axes` = (ex, ey, ez) ortonormales (por defecto, los del mundo)."""
    rot = Matrix.Identity(4)
    if axes:
        rot = Matrix((Vector(axes[0]), Vector(axes[1]), Vector(axes[2]))).transposed().to_4x4()
    m = Matrix.Translation(Vector(centre)) @ rot @ Matrix.Diagonal((radii[0], radii[1], radii[2], 1.0))
    part = bmesh.new()  # (en un bmesh aparte: create_uvsphere sobre una malla grande es O(n) por llamada)
    bmesh.ops.create_uvsphere(part, u_segments=segments, v_segments=rings, radius=1.0, matrix=m)
    _append(bm, part)


def add_mesh(bm, verts, faces, scale=1.0, offset=(0.0, 0.0, 0.0)):
    """Anade a `bm` una malla (vertices en H, caras de 3 o 4 indices) multiplicada por `scale` (la altura) y desplazada por `offset`."""
    off = Vector(offset)
    bv = [bm.verts.new(Vector(v) * scale + off) for v in verts]
    for f in faces:
        bm.faces.new([bv[i] for i in f])


def mesh_to_bm(verts, faces, scale=1.0, offset=(0.0, 0.0, 0.0)):
    """bmesh nuevo a partir de una malla grande (vertices en H, caras de cualquier tamano), multiplicada por `scale` y desplazada por `offset`: pasa por un Mesh de
    Blender (from_pydata, en C), mucho mas rapido que crear vertices y caras uno a uno."""
    ox, oy, oz = offset
    me = bpy.data.meshes.new("cp_tmp_mesh")
    me.from_pydata([(x * scale + ox, y * scale + oy, z * scale + oz) for x, y, z in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return bm


def _finish(bm, origin):
    bmesh.ops.translate(bm, vec=-Vector(origin), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def _mirror_x(bm):
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=bm.faces)


# --- piezas ----------------------------------------------------------------------------------------------------------------------------------
def build_femur(h: float, side: str) -> tuple:
    """(bmesh, origen mundo, dimension de referencia): femur con origen en el centro de la cabeza. Eje mecanico vertical: la rodilla queda bajo la cabeza."""
    s = 1.0 if side == "L" else -1.0
    head = _v(s * HIP_X, 0.0, HIP_Z, h)
    bm = bmesh.new()
    rel = lambda x, y, z: head + _v(s * x, y, z, h)  # noqa: E731 (puntos relativos a la cabeza, en H)
    ellipsoid(bm, head, (HEAD_R * h,) * 3)  # cabeza
    tube(bm, [head, rel(0.0125, 0.0012, -0.0078), rel(0.0265, 0.0030, -0.0168)], [(0.0112 * h,) * 2, (0.0090 * h,) * 2, (0.0098 * h,) * 2], caps=(0.0, 0.0))  # cuello
    ellipsoid(bm, rel(0.0290, 0.0030, -0.0210), (0.0100 * h, 0.0115 * h, 0.0160 * h))  # trocanter mayor
    ellipsoid(bm, rel(-0.0030, 0.0075, -0.0300), (0.0060 * h,) * 3)  # trocanter menor
    tube(bm, [rel(0.0250, 0.0025, -0.030), rel(0.0140, 0.0030, -0.0440), rel(0.0075, -0.0050, -0.125), rel(0.0, 0.0, -0.215)],
         [(0.0100 * h, 0.0098 * h), (0.0082 * h, 0.0082 * h), (0.0080 * h, 0.0085 * h), (0.0105 * h, 0.0125 * h)], ref=(s, 0, 0), caps=(0.0, 0.0))  # diafisis con leve arco anterior
    for sx in (1.0, -1.0):  # condilos
        ellipsoid(bm, rel(sx * 0.0125, 0.0, -THIGH_LENGTH + 0.002), (0.0125 * h, 0.0185 * h, 0.0150 * h))
    _finish(bm, head)
    return bm, head, THIGH_LENGTH * h


def build_pelvis(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia): pelvis con origen en el punto medio de los centros acetabulares; dimension = ancho biiliaco."""
    origin = _v(0.0, 0.0, HIP_Z, h)
    bm = bmesh.new()
    p = lambda x, y, z: _v(x, y, z, h)  # noqa: E731
    # sacro (cuña curva concava hacia delante) y coccix
    tube(bm, [p(0.0, 0.0215, 0.566), p(0.0, 0.0300, 0.548), p(0.0, 0.0420, 0.528), p(0.0, 0.0510, 0.510)],
         [(0.0520 * h, 0.0125 * h), (0.0360 * h, 0.0105 * h), (0.0200 * h, 0.0085 * h), (0.0075 * h, 0.0060 * h)], ref=(1, 0, 0), caps=(0.0030 * h, 0.0020 * h), sides=HI_SIDES, steps=HI_STEPS)
    tube(bm, [p(0.0, 0.0510, 0.510), p(0.0, 0.0560, 0.495), p(0.0, 0.0560, 0.480)], [(0.0075 * h, 0.0060 * h), (0.0055 * h, 0.0050 * h), (0.0020 * h, 0.0020 * h)], caps=(0.0, 0.003 * h),
         sides=HI_SIDES, steps=HI_STEPS)
    for s in (1.0, -1.0):
        side = "L" if s > 0 else "R"
        wv, wf = cp_refine.wing(side)  # ala iliaca: lente solida con el contorno del ilion, fosa concava y cresta acampanada (config/cp/refine.json)
        add_mesh(bm, wv, wf, h)
        cv, cf = cp_refine.cup(side)  # copa acetabular que abraza la cabeza del femur
        add_mesh(bm, cv, cf, h)
        # isquion: acetabulo - espina - cuerpo - tuberosidad - rama isquiopubiana - sinfisis (cierra el agujero obturador con el pubis)
        tube(bm, [p(s * HIP_X, 0.0, HIP_Z), p(s * 0.0469, 0.0082, 0.5120), p(s * 0.0431, 0.0071, 0.5000), p(s * 0.0350, 0.0120, 0.4700), p(s * 0.0286, 0.0, 0.4689),
                  p(s * 0.0274, -0.0120, 0.4743), p(s * 0.0183, -0.0229, 0.4829), p(s * 0.0090, -0.0300, 0.4930), p(s * 0.0011, -0.0345, 0.5003)],
             [(0.0095 * h,) * 2, (0.0078 * h,) * 2, (0.0080 * h,) * 2, (0.0120 * h, 0.0130 * h), (0.0080 * h,) * 2, (0.0072 * h,) * 2, (0.0072 * h,) * 2, (0.0085 * h,) * 2, (0.0095 * h, 0.0140 * h)],
             ref=(0, 0, 1), caps=(0.006 * h, 0.004 * h), sides=HI_SIDES, steps=HI_STEPS)
        # pubis: rama superior del acetabulo a la sinfisis
        tube(bm, [p(s * HIP_X, 0.0, HIP_Z), p(s * 0.0400, -0.0090, 0.5230), p(s * 0.0260, -0.0171, 0.5150), p(s * 0.0130, -0.0270, 0.5070), p(s * 0.0011, -0.0345, 0.5003)],
             [(0.0095 * h,) * 2, (0.0072 * h,) * 2, (0.0068 * h, 0.0085 * h), (0.0075 * h, 0.0090 * h), (0.0095 * h, 0.0140 * h)], ref=(0, 0, 1), caps=(0.006 * h, 0.004 * h), sides=HI_SIDES, steps=HI_STEPS)
    _finish(bm, origin)
    xs = [v.co.x for v in bm.verts]
    return bm, origin, (max(xs) - min(xs))


def build_lumbar(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia): L5-L1 con sus discos naciendo del sacro, con lordosis; origen en el centro del disco L5-S1; dimension = altura.
    Vertebras lumbares (cuerpo en rinon grande con cuña, arco con foramen triangular, espinosa alta y roma, transversas finas) en `cp_vertebra`."""
    from . import cp_axial, cp_vertebra  # (import tardio: cp_axial usa las primitivas de este modulo)

    origin = _v(0.0, LUMBAR_Y0, LUMBAR_Z0, h)
    total = 5 * (BODY_H + DISC_H) - DISC_H / 2
    curve = lambda s: -0.010 * math.sin(math.pi * min(max(s / total, 0.0), 1.0))  # noqa: E731 (lordosis: L3 el mas adelantado)
    levels = [(name, BODY_H, DISC_H) for name in ("L5", "L4", "L3", "L2", "L1")]
    bm, o, d, _ = cp_axial._column(h, origin, "lumbar", levels, curve, "lumbar_height")
    return bm, o, d


def _append(bm, other):
    """Copia los vertices y caras de `other` en `bm` (partes sueltas de un mismo objeto)."""
    m = {}
    for v in other.verts:
        m[v] = bm.verts.new(v.co)
    for f in other.faces:
        bm.faces.new([m[v] for v in f.verts])
    other.free()


# --- escena ----------------------------------------------------------------------------------------------------------------------------------
def _material():
    mat = bpy.data.materials.get("cp_bone") or bpy.data.materials.new("cp_bone")
    mat.diffuse_color = BONE_COLOR
    return mat


def _object(name, bm, origin, ref_dim, ref_name, h, collection) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.materials.append(_material())
    o = bpy.data.objects.new(name, me)
    collection.objects.link(o)
    o.location = origin  # transformaciones aplicadas: rotacion 0, escala 1, la malla es local al origen articular
    o.vertex_groups.clear()
    o["cp_part"], o["cp_ref_dim_m"], o["cp_ref_dim_name"], o["cp_height_m"] = name[len(PREFIX):], ref_dim, ref_name, h
    return o


def _parent_keep_transform(child, parent):
    bpy.context.view_layer.update()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def remove_generated() -> None:
    for o in [o for o in bpy.data.objects if o.name.startswith(PREFIX)]:
        bpy.data.objects.remove(o, do_unlink=True)
    for m in [m for m in bpy.data.meshes if m.name.startswith(PREFIX) and m.users == 0]:
        bpy.data.meshes.remove(m)


def _subcollection(parent, name):
    c = bpy.data.collections.get(f"CP_{name}") or bpy.data.collections.new(f"CP_{name}")
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def organize_collections(parts: dict, root) -> dict:
    """Reparte los objetos en subcolecciones por seccion (`SECTIONS`) bajo `root`; devuelve {ruta: coleccion}. Cada objeto queda en una sola coleccion."""
    out = {}
    for path, names in SECTIONS.items():
        c = root
        for seg in path:
            c = _subcollection(c, seg)
        out[path] = c
        for n in names:
            o = parts[n]
            for old in list(o.users_collection):
                if old is not c:
                    old.objects.unlink(o)
            if o.name not in c.objects:
                c.objects.link(o)
    for key, bones in SKULL_BONES_EXPECTED.items():
        out[("Craneo", key)]["cp_huesos_esperados"] = ", ".join(bones)
    return out


def build_cp_skeleton(height_m: float = REF_HEIGHT_M, dims: dict | None = None, parent: bool = True) -> dict:
    """Genera cp.Pelvis, cp.FemurL/R, cp.LumbarSpine, cp.ThoracicSpine, cp.CervicalSpine, el craneo en PIEZAS INDEPENDIENTES (cp.Skull = boveda, cp.SkullFace, cigomaticos, temporales, mastoides, condilos, dientes), cp.Mandible y cp.TeethLower (y los redimensiona segun `dims`: {nombre: dimension_m}; `cp.Femur` aplica a ambos femures).
    Devuelve {nombre: objeto}."""
    if height_m <= 0.3:
        raise ValueError("La altura debe ser > 0.3 m")
    remove_generated()
    col = bpy.data.collections.get("CP_Skeleton") or bpy.data.collections.new("CP_Skeleton")
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    h = height_m
    parts = {}
    bm, o, d = build_pelvis(h)
    parts["cp.Pelvis"] = _object("cp.Pelvis", bm, o, d, "bi_iliac_width", h, col)
    for side in "LR":
        bm, o, d = build_femur(h, side)
        parts[f"cp.Femur{side}"] = _object(f"cp.Femur{side}", bm, o, d, "hip_knee_length", h, col)
    bm, o, d = build_lumbar(h)
    parts["cp.LumbarSpine"] = _object("cp.LumbarSpine", bm, o, d, "lumbar_height", h, col)
    from . import cp_axial as ax  # (import tardio: cp_axial usa las primitivas de este modulo)

    for name, builder in (("ThoracicSpine", ax.build_thoracic), ("CervicalSpine", ax.build_cervical), ("Mandible", ax.build_mandible), ("TeethLower", ax.build_teeth_lower)):
        bm, o, d, ref_name = builder(h)
        parts[f"cp.{name}"] = _object(f"cp.{name}", bm, o, d, ref_name, h, col)
    for name, (bm, o, d, ref_name) in ax.build_skull_parts(h).items():
        parts[name] = _object(name, bm, o, d, ref_name, h, col)
    for n in FOLLOW_PARENT_SCALE:
        parts[n]["cp_follows_parent_scale"] = True
    parts["cp.ThoracicSpine"]["cp_levels"] = " ".join(ax.THORACIC_LEVELS)  # de abajo (T12) a arriba (T1)
    parts["cp.CervicalSpine"]["cp_levels"] = " ".join(ax.CERVICAL_LEVELS)
    parts["cp.LumbarSpine"]["cp_levels"] = "L5 L4 L3 L2 L1"
    organize_collections(parts, col)
    bpy.context.view_layer.update()
    for n, ob in parts.items():
        if n in PARENTS:
            par = parts[PARENTS[n]]
            ob["cp_anchor_local"] = tuple(par.matrix_world.inverted() @ ob.matrix_world.translation)  # articulacion con su padre (en el espacio del padre)
    if parent:
        for n in PARENTS:  # de la pelvis hacia fuera: cada padre ya esta en su sitio
            _parent_keep_transform(parts[n], parts[PARENTS[n]])
    for key, value in (dims or {}).items():
        for n in (["cp.FemurL", "cp.FemurR"] if key == "cp.Femur" else [key]):
            if n not in parts:
                raise ValueError(f"Pieza desconocida '{n}' (validas: {sorted(parts)} y 'cp.Femur')")
            cp_resize(parts[n], float(value))
    bpy.context.view_layer.update()
    return parts


def cp_resize(obj, new_dim_m: float) -> float:
    """Redimensiona la pieza de forma UNIFORME alrededor de su origen articular hasta que su dimension de referencia (`cp_ref_dim_m`) valga `new_dim_m`; la
    estructura y la proporcion no cambian. Devuelve el factor. Al redimensionar la pelvis, los hijos siguen a sus anclajes articulares."""
    if new_dim_m <= 0:
        raise ValueError("La dimension debe ser positiva")
    f = new_dim_m / obj["cp_ref_dim_m"]
    obj.data.transform(Matrix.Scale(f, 4))
    obj.data.update()
    obj["cp_ref_dim_m"] = new_dim_m
    bpy.context.view_layer.update()
    for ch in obj.children:  # los hijos siguen a su anclaje articular (y, con ellos, toda su cadena)
        if ch.get("cp_follows_parent_scale"):  # piezas del mismo hueso (cara, cigomaticos, dientes...): se redimensionan con su madre
            ch.data.transform(Matrix.Scale(f, 4))
            ch.data.update()
            ch["cp_ref_dim_m"] = ch["cp_ref_dim_m"] * f
        anchor = Vector(ch["cp_anchor_local"]) * f
        ch["cp_anchor_local"] = tuple(anchor)
        ch.matrix_world.translation = obj.matrix_world @ anchor
    return f


def unparent_keep_transform(parts: dict) -> None:
    """Deshace el emparentamiento temporal dejando cada pieza donde esta."""
    for ob in parts.values():
        if ob.parent:
            mw = ob.matrix_world.copy()
            ob.parent = None
            ob.matrix_world = mw


def validate(parts: dict) -> list:
    """Problemas de las mallas: abiertas (aristas con un solo lado o con mas de dos), volumen no positivo, vertex groups o transformaciones sin aplicar."""
    out = []
    for n, o in parts.items():
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bad = [e for e in bm.edges if len(e.link_faces) != 2]
        if bad:
            out.append(f"{n}: {len(bad)} aristas no manifold")
        if bm.calc_volume(signed=True) <= 0:
            out.append(f"{n}: volumen no positivo")
        bm.free()
        if o.vertex_groups:
            out.append(f"{n}: tiene vertex groups")
        if any(x.parent for x in parts.values()) and n != PREFIX + "Pelvis":
            root = o
            while root.parent:
                root = root.parent
            if root.name != PREFIX + "Pelvis":
                out.append(f"{n}: no esta conectada a la pelvis")
        if any(abs(c - 1.0) > 1e-9 for c in o.scale) or any(abs(c) > 1e-9 for c in o.rotation_euler):
            out.append(f"{n}: transformaciones sin aplicar")
    return out
