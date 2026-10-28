"""Esqueleto AXIAL parametrico `cp.*` (usa bpy): columna toracica (T12-T1), columna cervical (C7-C1), craneo y mandibula, generados desde cero como continuacion de
`cp_skeleton` (pelvis, femures y columna lumbar). Mismas reglas: objetos independientes con el prefijo `cp.`, mallas locales a su origen articular (transformaciones
aplicadas, sin vertex groups), todo en fracciones de la altura H (`--height` conserva las proporciones) y mismo tono de hueso.

Cadena de emparentamiento (Keep Transform): cp.Pelvis > cp.LumbarSpine > cp.ThoracicSpine > cp.CervicalSpine > cp.Skull > cp.Mandible.

    cp.ThoracicSpine  T12..T1 con discos; origen en el centro del disco T12/L1; cifosis (convexa hacia atras)
    cp.CervicalSpine  C7..C1 con discos; origen en el centro del disco C7/T1; lordosis (convexa hacia delante); C2 con apofisis odontoides; C1 en anillo
    cp.Skull          neurocraneo, cara (orbitas y abertura nasal en profundidad), arcos cigomaticos, mastoides y arcada dental superior; origen en el centro de los
                      condilos occipitales (articulacion atlanto-occipital)
    cp.Mandible       cuerpo, mentón, ramas, coronoides, condilos y arcada dental inferior; origen en el centro del eje de las articulaciones temporomandibulares

Los LARGOS mandan los datos antropometricos (Drillis y Contini): hombro a 0.818 H, menton a ~0.87 H, vertice a 1.0 H. La FORMA (curvas sagitales de la columna,
craneo grande con occipucio y frente, apofisis espinosas inclinadas hacia abajo en el torax) sigue la imagen de referencia `esqueleto humano.jpg`, cuya cabeza es
mas pequeña que la antropometrica: gana la antropometria (decision del usuario)."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import cp_refine
from . import cp_skeleton as cp
from .cp_skeleton import ellipsoid, tube

THOR_DISC_H = 0.0020
CERV_DISC_H = 0.0030
LUMBAR_TOTAL = 5 * (cp.BODY_H + cp.DISC_H) - cp.DISC_H / 2  # altura de L5-L1 desde el centro del disco L5-S1
SPINE_Y = cp.LUMBAR_Y0  # plano sagital de los extremos de cada curva (H)
KYPHOSIS, LORDOSIS = 0.016, 0.009  # flechas maximas de las curvas (H)
SKULL_BASE_TO_VERTEX = 0.075  # centro de los condilos occipitales - vertice (H)
SKULL_BASE_TO_MENTON = 0.050  # centro de los condilos occipitales - menton (H)
TMJ = (0.0, -0.032, -0.012)  # centro del eje de las ATM relativo al origen del craneo (H)

THORACIC_LEVELS = [f"T{n}" for n in range(12, 0, -1)]  # de abajo (T12) a arriba (T1)
CERVICAL_LEVELS = ["C7", "C6", "C5", "C4", "C3", "C2", "C1"]


def _lerp(a, b, t):
    return a + (b - a) * t


def _thoracic_dims(i: int) -> tuple:
    """(altura del cuerpo, semieje a, semieje b) del nivel i (0 = T12 ... 11 = T1), en H."""
    t = i / 11
    return _lerp(0.0130, 0.0098, t), _lerp(0.0112, 0.0085, t), _lerp(0.0095, 0.0075, t)


def thoracic_total() -> float:
    return sum(_thoracic_dims(i)[0] + THOR_DISC_H for i in range(12)) - THOR_DISC_H / 2


CERVICAL_BODY_H = {"C7": 0.0090, "C6": 0.0088, "C5": 0.0086, "C4": 0.0084, "C3": 0.0082}
C2_H, C1_H = 0.0170, 0.0065


def cervical_total() -> float:
    return sum(CERVICAL_BODY_H.values()) + 6 * CERV_DISC_H - CERV_DISC_H / 2 + C2_H + C1_H


def thoracic_origin_z() -> float:
    return cp.LUMBAR_Z0 + LUMBAR_TOTAL + THOR_DISC_H / 2


def cervical_origin_z() -> float:
    return thoracic_origin_z() + thoracic_total() + CERV_DISC_H / 2


def skull_origin_z() -> float:
    return cervical_origin_z() + cervical_total() + 0.0010


# --- primitivas nuevas -----------------------------------------------------------------------------------------------------------------------
def torus(bm, centre, a, b, r, axes=None, nu=32, nv=10):
    """Toro eliptico (semiejes a, b en el plano local xy; radio del tubo r; normal local z), orientado por `axes` = (ex, ey, ez)."""
    rot = Matrix.Identity(4)
    if axes:
        rot = Matrix((Vector(axes[0]), Vector(axes[1]), Vector(axes[2]))).transposed().to_4x4()
    m = Matrix.Translation(Vector(centre)) @ rot
    grid = []
    for i in range(nu):
        u = 2 * math.pi * i / nu
        row = []
        for j in range(nv):
            v = 2 * math.pi * j / nv
            row.append(bm.verts.new(m @ Vector(((a + r * math.cos(v)) * math.cos(u), (b + r * math.cos(v)) * math.sin(u), r * math.sin(v)))))
        grid.append(row)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((grid[i][j], grid[(i + 1) % nu][j], grid[(i + 1) % nu][(j + 1) % nv], grid[i][(j + 1) % nv]))


def _finish_local(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def _append(bm, other):
    m = {v: bm.verts.new(v.co) for v in other.verts}
    for f in other.faces:
        bm.faces.new([m[v] for v in f.verts])
    other.free()


def _frame(origin, h, curve, s):
    """Marco de la vertebra a la altura s (H): x lateral, y posterior, z a lo largo de la tangente de la curva sagital."""
    c = lambda q: origin + Vector((0.0, curve(q) * h, q * h))  # noqa: E731
    t = (c(s + 1e-4) - c(s - 1e-4)).normalized()
    x = Vector((1, 0, 0))
    y = t.cross(x).normalized()
    return Matrix.Translation(c(s)) @ Matrix((x, y, t)).transposed().to_4x4()


def _stack(h, origin, items, curve):
    """Apila discos y vertebras hacia arriba desde el centro del primer disco (origen); `items` = [("disc", alto, a, b) | ("vert", alto, constructor)]."""
    bm = bmesh.new()
    z = -items[0][1] / 2
    for it in items:
        part = bmesh.new()
        if it[0] == "disc":
            _, hh, a, b = it
            tube(part, [Vector((0, 0, -hh / 2 * h)), Vector((0, 0, hh / 2 * h))], [(a * h, b * h)] * 2, caps=(0.0, 0.0))
        else:
            _, hh, build = it
            build(part, h)
        bmesh.ops.transform(part, matrix=_frame(origin, h, curve, z + it[1] / 2), verts=part.verts)
        _append(bm, part)
        z += it[1]
    return bm


# --- vertebras -------------------------------------------------------------------------------------------------------------------------------
def _arch(v, h, a, b, y_base, spine_len, spine_deg, transverse, process_z=0.0):
    """Pediculos, apofisis transversas y espinosa de una vertebra (coordenadas locales de la vertebra, en H * h)."""
    for sx in (1.0, -1.0):
        tube(v, [Vector((sx * 0.55 * a * h, 0.9 * b * h, 0.0)), Vector((sx * 0.45 * a * h, (y_base - 0.002) * h, 0.001 * h))], [(0.0030 * h, 0.0030 * h)] * 2, caps=(0.0, 0.0))
        tube(v, [Vector((sx * 0.4 * a * h, y_base * h, 0.0)), Vector((sx * (0.5 * a + transverse) * h, (y_base + 0.002) * h, process_z * h))],
             [(0.0034 * h, 0.0030 * h), (0.0024 * h, 0.0024 * h)], ref=(0, 0, 1), caps=(0.0, 0.0020 * h))
    th = math.radians(spine_deg)
    tube(v, [Vector((0, y_base * h, 0.001 * h)), Vector((0, (y_base + spine_len * math.cos(th)) * h, -spine_len * math.sin(th) * h))],
         [(0.0026 * h, 0.0050 * h), (0.0022 * h, 0.0045 * h)], ref=(1, 0, 0), caps=(0.0, 0.0020 * h))


def _body(v, h, bh, a, b):
    tube(v, [Vector((0, 0, -bh / 2 * h)), Vector((0, 0, bh / 2 * h))], [(a * h, b * h)] * 2, caps=(0.0015 * h, 0.0015 * h))


def _thoracic_builder(i: int):
    bh, a, b = _thoracic_dims(i)
    level = 12 - i  # T12 .. T1
    spine_len = {12: 0.022, 11: 0.026, 10: 0.029, 9: 0.032, 8: 0.034, 7: 0.034, 6: 0.034, 5: 0.033, 4: 0.030, 3: 0.026, 2: 0.022, 1: 0.020}[level]
    spine_deg = {12: 25, 11: 32, 10: 42, 9: 50, 8: 55, 7: 55, 6: 52, 5: 45, 4: 36, 3: 28, 2: 20, 1: 14}[level]

    def build(v, h):
        _body(v, h, bh, a, b)
        _arch(v, h, a, b, 1.9 * b, spine_len, spine_deg, 0.016, process_z=0.0)  # apofisis transversas romas, espinosa larga inclinada hacia abajo en T4-T9

    return build


def _cervical_builder(level: str):
    if level == "C1":
        def build(v, h):  # atlas: anillo alrededor de la odontoides, masas laterales y apofisis transversas
            torus(v, (0, 0, 0), 0.0125 * h, 0.0112 * h, 0.0030 * h)
            for sx in (1.0, -1.0):
                ellipsoid(v, (sx * 0.0125 * h, -0.001 * h, 0.0), (0.0050 * h, 0.0060 * h, 0.0036 * h))
                tube(v, [Vector((sx * 0.0140 * h, 0.001 * h, 0.0)), Vector((sx * 0.0230 * h, 0.003 * h, -0.001 * h))], [(0.0030 * h, 0.0030 * h), (0.0022 * h, 0.0022 * h)], ref=(0, 0, 1), caps=(0.0, 0.002 * h))
            ellipsoid(v, (0, 0.0138 * h, 0.0), (0.0032 * h, 0.0030 * h, 0.0030 * h))  # tuberculo posterior

        return build
    if level == "C2":
        def build(v, h):  # axis: cuerpo en la mitad inferior y apofisis odontoides arriba
            tube(v, [Vector((0, 0, -0.0085 * h)), Vector((0, 0, 0.0015 * h))], [(0.0080 * h, 0.0070 * h)] * 2, caps=(0.0015 * h, 0.0))
            tube(v, [Vector((0, -0.0008 * h, 0.0015 * h)), Vector((0, -0.0008 * h, 0.0085 * h))], [(0.0042 * h, 0.0040 * h), (0.0036 * h, 0.0034 * h)], caps=(0.0, 0.0030 * h))
            _arch(v, h, 0.0080, 0.0070, 0.0125, 0.018, 12, 0.008, process_z=-0.003)

        return build
    bh = CERVICAL_BODY_H[level]
    a = {"C7": 0.0090, "C6": 0.0086, "C5": 0.0082, "C4": 0.0078, "C3": 0.0075}[level]
    b = {"C7": 0.0075, "C6": 0.0071, "C5": 0.0068, "C4": 0.0065, "C3": 0.0062}[level]
    spine_len, spine_deg = (0.026, 8) if level == "C7" else (0.014, 15)

    def build(v, h):
        _body(v, h, bh, a, b)
        _arch(v, h, a, b, 1.7 * b, spine_len, spine_deg, 0.011 if level != "C7" else 0.014)

    return build


def build_thoracic(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia, nombre): T12-T1 con discos; cifosis; origen en el centro del disco T12/L1."""
    origin = Vector((0.0, cp.LUMBAR_Y0, thoracic_origin_z())) * h
    total = thoracic_total()
    items = []
    for i in range(12):
        bh, a, b = _thoracic_dims(i)
        items += [("disc", THOR_DISC_H, a * 0.95, b * 0.95), ("vert", bh, _thoracic_builder(i))]
    curve = lambda s: KYPHOSIS * math.sin(math.pi * min(max(s / total, 0.0), 1.0))  # noqa: E731 (convexa hacia atras: +y)
    bm = _stack(h, origin, items, curve)
    _finish_local(bm)
    bmesh.ops.translate(bm, vec=-origin, verts=bm.verts)
    zs = [v.co.z for v in bm.verts]
    return bm, origin, max(zs) - min(zs), "thoracic_height"


def build_cervical(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia, nombre): C7-C1; lordosis; origen en el centro del disco C7/T1."""
    origin = Vector((0.0, cp.LUMBAR_Y0, cervical_origin_z())) * h
    total = cervical_total()
    items = [("disc", CERV_DISC_H, 0.0075, 0.0065)]
    for lv in ("C7", "C6", "C5", "C4", "C3"):
        items += [("vert", CERVICAL_BODY_H[lv], _cervical_builder(lv)), ("disc", CERV_DISC_H, 0.0070, 0.0060)]
    items += [("vert", C2_H, _cervical_builder("C2")), ("vert", C1_H, _cervical_builder("C1"))]
    curve = lambda s: -LORDOSIS * math.sin(math.pi * min(max(s / total, 0.0), 1.0))  # noqa: E731 (convexa hacia delante: -y)
    # el orden de la pila es: disco C7/T1, C7, disco, C6, ... C3, disco C2/3, C2, C1
    bm = _stack(h, origin, items, curve)
    _finish_local(bm)
    bmesh.ops.translate(bm, vec=-origin, verts=bm.verts)
    zs = [v.co.z for v in bm.verts]
    return bm, origin, max(zs) - min(zs), "cervical_height"


# --- craneo y mandibula ----------------------------------------------------------------------------------------------------------------------
def skull_origin(h: float) -> Vector:
    return Vector((0.0, cp.LUMBAR_Y0, skull_origin_z())) * h


_SKULL_CACHE: dict = {}
BOOL_SCALE = 1000.0  # el Boolean exacto se hace con el craneo a ~8 cm de lado (H x 1000): evita tolerancias de coordenadas diminutas


def _temp_object(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c * BOOL_SCALE for c in v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def _boolean(target, operand, operation):
    mod = target.modifiers.new("cp_bool", "BOOLEAN")
    mod.operation, mod.object, mod.solver, mod.use_self = operation, operand, "EXACT", False
    bpy.context.view_layer.update()
    with bpy.context.temp_override(object=target, active_object=target, selected_objects=[target]):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def carved_skull(path: str = "") -> tuple:
    """(vertices, caras) del craneo en H relativo a su origen: UNION del neurocraneo y la cara (parches de `cp_refine`) menos las cavidades (orbitas, abertura piriforme),
    con el Boolean EXACTO de Blender. El resultado se guarda en cache (la operacion tarda unos segundos): las reconstrucciones posteriores solo copian la malla."""
    if path in _SKULL_CACHE:
        return _SKULL_CACHE[path]
    parts = cp_refine.skull_parts(path)
    cutters, temps = cp_refine.carves(path), []
    try:
        skull = _temp_object("cp_tmp_skull", parts[0][1], parts[0][2])
        temps.append(skull)
        for _, v, f in parts[1:]:
            other = _temp_object("cp_tmp_part", v, f)
            temps.append(other)
            _boolean(skull, other, "UNION")
        for i, (c, r) in enumerate(cutters):
            bm = bmesh.new()
            ellipsoid(bm, Vector(c) * BOOL_SCALE, tuple(x * BOOL_SCALE for x in r), segments=64, rings=48)
            me = bpy.data.meshes.new(f"cp_tmp_cut{i}")
            bm.to_mesh(me)
            bm.free()
            cut = bpy.data.objects.new(f"cp_tmp_cut{i}", me)
            bpy.context.scene.collection.objects.link(cut)
            temps.append(cut)
            _boolean(skull, cut, "DIFFERENCE")
        me = skull.data
        if len(me.polygons) < 1000:
            raise RuntimeError("El Boolean del craneo no produjo una malla valida")
        verts = [tuple(c / BOOL_SCALE for c in v.co) for v in me.vertices]
        faces = [tuple(p.vertices) for p in me.polygons]
    finally:
        for o in temps:
            m = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(m)
    _SKULL_CACHE[path] = (verts, faces)
    return _SKULL_CACHE[path]


def build_skull(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia, nombre): craneo de alta densidad con origen en el centro de los condilos occipitales; referencia = longitud antero-posterior.
    La superficie estrellada (neurocraneo, occipucio, macizo facial, orbitas y abertura piriforme hundidas, arcos superciliares) viene de `cp_refine.skull`
    (config/cp/refine.json); aqui se le suman los arcos cigomaticos, las apofisis mastoides, los condilos occipitales y la arcada dental superior."""
    P = lambda x, y, z: Vector((x, y, z)) * h  # noqa: E731 (coordenadas relativas al origen, en H)
    bm = bmesh.new()
    verts, faces = carved_skull()
    cp.add_mesh(bm, verts, faces, h)
    for sx in (1.0, -1.0):
        tube(bm, [P(sx * 0.0300, -0.0560, -0.0090), P(sx * 0.0380, -0.0465, -0.0087), P(sx * 0.0395, -0.0300, -0.0075), P(sx * 0.0350, -0.0140, -0.0040)],
             [(0.0032 * h, 0.0028 * h), (0.0036 * h, 0.0030 * h), (0.0036 * h, 0.0030 * h), (0.0032 * h, 0.0028 * h)], ref=(0, 0, 1), caps=(0.002 * h, 0.002 * h),
             sides=cp.HI_SIDES, steps=cp.HI_STEPS)  # arco cigomatico (hito zygomatic_arch)
        ellipsoid(bm, P(sx * 0.0194, -0.0139, -0.0138), (0.0070 * h, 0.0085 * h, 0.0110 * h), segments=64, rings=40)  # apofisis mastoides (hito mastoid_process)
        ellipsoid(bm, P(sx * 0.012, 0.004, -0.004), (0.0060 * h, 0.0140 * h, 0.0050 * h), segments=48, rings=32)  # condilos occipitales (origen de la articulacion atlanto-occipital)
    tube(bm, [P(-0.022, -0.058, -0.033), P(-0.012, -0.074, -0.036), P(0, -0.079, -0.037), P(0.012, -0.074, -0.036), P(0.022, -0.058, -0.033)],
         [(0.0036 * h, 0.0046 * h)] * 5, ref=(0, 1, 0), caps=(0.003 * h, 0.003 * h), sides=cp.HI_SIDES, steps=cp.HI_STEPS)  # arcada dental superior
    _finish_local(bm)
    ys = [v.co.y for v in bm.verts]
    return bm, skull_origin(h), max(ys) - min(ys), "skull_length"


def build_mandible(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia, nombre): mandibula de alta densidad con origen en el centro del eje de las ATM; referencia = anchura bicondilea.
    Condilo, cuello condilar, rama ascendente (lamina), apofisis coronoides, angulo mandibular, cuerpo con menton y arcada dental inferior."""
    P = lambda x, y, z: Vector((x - TMJ[0], y - TMJ[1], z - TMJ[2])) * h  # noqa: E731 (coordenadas del craneo, en H, relativas al eje de las ATM)
    bm = bmesh.new()
    hi = dict(sides=cp.HI_SIDES, steps=cp.HI_STEPS)
    for sx in (1.0, -1.0):
        ellipsoid(bm, P(sx * 0.0290, -0.0322, -0.0105), (0.0100 * h, 0.0048 * h, 0.0036 * h), segments=64, rings=40)  # condilo (alargado en sentido mediolateral)
        tube(bm, [P(sx * 0.0285, -0.0322, -0.0120), P(sx * 0.0295, -0.0300, -0.0220), P(sx * 0.0305, -0.0275, -0.0330), P(sx * 0.0317, -0.0236, -0.0430)],
             [(0.0042 * h, 0.0028 * h), (0.0075 * h, 0.0030 * h), (0.0095 * h, 0.0032 * h), (0.0090 * h, 0.0040 * h)], ref=(0, 1, 0), caps=(0.0, 0.002 * h), **hi)  # cuello y rama ascendente
        tube(bm, [P(sx * 0.0295, -0.0285, -0.0200), P(sx * 0.0292, -0.0345, -0.0060), P(sx * 0.0290, -0.0362, -0.0030)],
             [(0.0045 * h, 0.0026 * h), (0.0032 * h, 0.0023 * h), (0.0020 * h, 0.0018 * h)], ref=(0, 1, 0), caps=(0.0, 0.002 * h), **hi)  # apofisis coronoides
        ellipsoid(bm, P(sx * 0.0317, -0.0236, -0.0430), (0.0060 * h, 0.0090 * h, 0.0070 * h), segments=48, rings=32)  # angulo mandibular
        tube(bm, [P(sx * 0.0317, -0.0236, -0.0430), P(sx * 0.0305, -0.0390, -0.0465), P(sx * 0.0215, -0.0560, -0.0485), P(sx * 0.0080, -0.0705, -0.0490)],
             [(0.0070 * h, 0.0050 * h), (0.0068 * h, 0.0052 * h), (0.0066 * h, 0.0054 * h), (0.0064 * h, 0.0056 * h)], ref=(0, 0, 1), caps=(0.002 * h, 0.002 * h), **hi)  # cuerpo
    ellipsoid(bm, P(0, -0.0715, -0.0470), (0.0115 * h, 0.0075 * h, 0.0058 * h), segments=48, rings=32)  # menton
    tube(bm, [P(-0.021, -0.056, -0.0405), P(-0.011, -0.070, -0.042), P(0, -0.075, -0.0425), P(0.011, -0.070, -0.042), P(0.021, -0.056, -0.0405)],
         [(0.0034 * h, 0.0044 * h)] * 5, ref=(0, 1, 0), caps=(0.003 * h, 0.003 * h), **hi)  # arcada dental inferior
    _finish_local(bm)
    xs = [v.co.x for v in bm.verts]
    return bm, skull_origin(h) + Vector(TMJ) * h, max(xs) - min(xs), "mandible_width"
