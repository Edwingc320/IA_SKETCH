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

from .config import PROJECT_ROOT, ConfigError, _read_json

SUBSURF_LEVELS = 2
CREASE_HARD = 0.65  # aristas del bloque
CREASE_RIM = 0.85  # bordes de las cavidades

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


def sweep_box(rings, chamfer=0.30, crease=CREASE_HARD, cap=True, closed=False):
    """Barrido de secciones rectangulares achaflanadas: `rings` = [(centro, eje_ancho, semi_ancho, semi_espesor)]. Las aristas longitudinales llevan crease.
    `closed=True` une la ultima seccion con la primera (anillo, sin tapas)."""
    bm = bmesh.new()
    _layer(bm)
    centres = [Vector(r[0]) for r in rings]
    grid = []
    for i, (c, ew, w, t) in enumerate(rings):
        if closed:
            a, b = centres[(i - 1) % len(rings)], centres[(i + 1) % len(rings)]
        else:
            a, b = centres[max(i - 1, 0)], centres[min(i + 1, len(rings) - 1)]
        tang = (b - a).normalized()
        ew = Vector(ew)
        ew = (ew - tang * ew.dot(tang)).normalized()
        et = tang.cross(ew).normalized()
        fw, ft = chamfer * w, chamfer * t
        pts = [(w - fw, t), (w, t - ft), (w, -(t - ft)), (w - fw, -t), (-(w - fw), -t), (-w, -(t - ft)), (-w, t - ft), (-(w - fw), t)]
        grid.append([bm.verts.new(Vector(c) + ew * p + et * q) for p, q in pts])
    longitudinal = []
    for i in range(len(grid) - (0 if closed else 1)):
        for k in range(8):
            j = (i + 1) % len(grid)
            bm.faces.new((grid[i][k], grid[i][(k + 1) % 8], grid[j][(k + 1) % 8], grid[j][k]))
            longitudinal.append(bm.edges.get((grid[i][k], grid[j][k])))
    if cap and not closed:
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


def _pocket(bm, faces, thickness, depth, direction, crease=CREASE_RIM, ellipse=None, axes=(0, 2), smooth=0) -> list:
    """Inset + Extrude hacia dentro: inset de la region `faces`, hunde la region interior `depth` a lo largo de `direction`, marca con crease los bordes del anillo y
    devuelve las caras de la region interior (para encadenar otro escalon)."""
    if ellipse:
        _snap_to_ellipse(faces, *ellipse, axes=axes)
    if smooth:  # suaviza el contorno escalonado de la region sobre superficies curvas (relajacion laplaciana de su borde)
        fs = set(faces)
        loop = {v for e in {e for f in faces for e in f.edges} if sum(1 for g in e.link_faces if g in fs) == 1 for v in e.verts}
        for _ in range(smooth):
            bmesh.ops.smooth_vert(bm, verts=list(loop), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    region = list(faces)  # tras el inset estas caras son la region INTERIOR; las nuevas (`ring`) son el anillo del reborde
    ring = set(bmesh.ops.inset_region(bm, faces=faces, thickness=thickness, depth=0.0, use_even_offset=False, use_boundary=True)["faces"])
    loop = [e for f in ring for e in f.edges if sum(1 for g in e.link_faces if g in ring) == 1]
    inner = region
    bmesh.ops.translate(bm, vec=Vector(direction) * depth, verts=list({v for f in inner for v in f.verts}))
    _set_crease(bm, loop, crease)
    return list(inner)


SKULL_FILE = PROJECT_ROOT / "config" / "cp" / "skull.json"


def load_skull(path=None) -> dict:
    p = path or SKULL_FILE
    if not p.exists():
        raise ConfigError(f"Falta {p}")
    return _read_json(p)


def _cubesphere(x: float, y: float, z: float) -> tuple:
    """Cubo [-1, 1]^3 -> esfera unidad con los cuadrilateros casi uniformes (esfera de cubo), mejor repartida que una esfera UV."""
    x2, y2, z2 = x * x, y * y, z * z
    return (x * math.sqrt(1 - y2 / 2 - z2 / 2 + y2 * z2 / 3), y * math.sqrt(1 - z2 / 2 - x2 / 2 + z2 * x2 / 3), z * math.sqrt(1 - x2 / 2 - y2 / 2 + x2 * y2 / 3))


def vault_point(v: dict, x: float, y: float, z: float) -> Vector:
    """Punto de la boveda para el vertice (x, y, z) del cubo (y = -1 delante): superelipsoide ovoide (radios distintos delante/detras y arriba/abajo)."""
    d = _cubesphere(x, y, z)
    n = v["exponent"]
    s = (abs(d[0]) ** n + abs(d[1]) ** n + abs(d[2]) ** n) ** (1.0 / n) or 1.0
    d = tuple(c / s for c in d)
    a = v["half_width"] * (1.0 + v["width_skew"] * d[1])
    b = v["radius_front"] if d[1] < 0 else v["radius_back"]
    c = v["radius_up"] if d[2] > 0 else v["radius_down"]
    return Vector((a * d[0], v["center"][0] + b * d[1], v["center"][1] + c * d[2]))


def vault_cage(shape: dict | None = None) -> "bmesh.types.BMesh":
    """BOVEDA craneal (frontal, parietales y occipital): cubo subdividido mapeado a un ovoide, con la fosa temporal hundida por Inset + Extrude. Pieza independiente y cerrada."""
    sh = shape or load_skull()
    v = sh["vault"]
    bm = bmesh.new()
    _layer(bm)
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=v["segments"] - 1, use_grid_fill=True)
    _set_crease(bm, _cube_edges(bm), v["crease"])
    lateral = {sx: [f for f in bm.faces if all(abs(vt.co.x - sx) < 1e-6 for vt in f.verts)] for sx in (1.0, -1.0)}  # parche lateral del cubo (antes de mapear)
    for vert in bm.verts:
        vert.co = vault_point(v, vert.co.x, vert.co.y, vert.co.z)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    tf = v["temporal_fossa"]
    for sx in (1.0, -1.0):  # fosa temporal hundida en la pared lateral
        side = [f for f in lateral[sx] if ((f.calc_center_median().y - tf["centre_yz"][0]) / tf["radii_yz"][0]) ** 2 + ((f.calc_center_median().z - tf["centre_yz"][1]) / tf["radii_yz"][1]) ** 2 < 1.0]
        if side:
            _pocket(bm, side, 0.0020, tf["depth"], (-sx, 0, 0), crease=0.0, ellipse=(tuple(tf["centre_yz"]), tuple(tf["radii_yz"])), axes=(1, 2), smooth=3)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def face_cage(shape: dict | None = None) -> "bmesh.types.BMesh":
    """CARA (maxilares, nasales y reborde de las orbitas): bloque con planos duros y pomulos marcados, orbitas y abertura piriforme hundidas por Inset + Extrude hacia dentro.
    Pieza independiente y cerrada que queda en parte tapada por la boveda (sin unirse a ella)."""
    sh = shape or load_skull()
    f = sh["face"]
    table = [tuple(r) for r in f["profile"]]
    y0, y1 = table[0][0], table[-1][0]
    bm = bmesh.new()
    _layer(bm)
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=f["segments"] - 1, use_grid_fill=True)
    _set_crease(bm, _cube_edges(bm), CREASE_HARD)
    for v in bm.verts:
        u, w, vv = v.co.x, v.co.z, v.co.y
        y = y0 + (y1 - y0) * (vv + 1.0) / 2.0
        zt, zb, hw = _interp(table, y, 1), _interp(table, y, 2), _interp(table, y, 3)
        s = (w + 1.0) / 2.0
        lower = 0.56 + 0.44 * _smooth(s / 0.46)
        upper = 1.0 - f["upper_taper"] * _smooth((s - 0.56) / 0.44)
        width = hw * lower * upper
        fa = _smooth((-0.050 - y) / 0.014)  # cara plana: el maxilar se estrecha por debajo de las orbitas
        z = zb + s * (zt - zb)
        width *= 1.0 - f["lower_taper"] * 0.68 * fa * _smooth((-0.004 - z) / 0.028)
        cheek = math.exp(-(((y + 0.060) / 0.012) ** 2 + ((z + 0.004) / 0.012) ** 2))
        width *= 1.0 + f["cheek"] * cheek  # pomulos marcados
        v.co = Vector((u * width, y, z))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    front = [fc for fc in bm.faces if fc.normal.y < -0.5 and abs(fc.calc_center_median().y - y0) < 1e-6]
    for key in ("orbit", "nose"):
        cfg = f[key]
        cx, cz = cfg["centre_xz"]
        rx, rz = cfg["radii_xz"]
        for sx in ((1.0, -1.0) if key == "orbit" else (1.0,)):
            ccx = sx * cx if key == "orbit" else cx
            region = [fc for fc in front if ((fc.calc_center_median().x - ccx) / rx) ** 2 + ((fc.calc_center_median().z - cz) / rz) ** 2 < 1.0]
            if not region:
                continue
            step = _pocket(bm, region, 0.0016 if key == "orbit" else 0.0014, cfg["depth"][0], (0, 1, 0), ellipse=((ccx, cz), (rx, rz)))
            _pocket(bm, step, 0.0020 if key == "orbit" else 0.0016, cfg["depth"][1], (0, 1, 0), ellipse=((ccx, cz), (rx * 0.85, rz * 0.84)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _px_to_yz(m: dict, x: float, y: float) -> tuple:
    """Pixel de la lamina lateral (`config/cp/skull.json`: sutures.image_map) -> (y, z) del craneo en H (cara a la izquierda de la imagen = -y)."""
    sy = (m["y_back"] - m["y_front"]) / (m["x_back_px"] - m["x_front_px"])
    sz = (m["z_top"] - m["z_base"]) / (m["y_base_px"] - m["y_top_px"])
    return (m["y_front"] + (x - m["x_front_px"]) * sy, m["z_top"] - (y - m["y_top_px"]) * sz)


def _zigzag(pts: list, teeth: int, amp: float) -> list:
    """Sutura en W / triangulos: remuestrea la polilinea en 2 * `teeth` tramos de igual longitud de arco y desplaza alternativamente +-`amp` (perpendicular local) los puntos intermedios."""
    n = 2 * teeth
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1] or 1.0
    out = [pts[0]]
    for i in range(1, n):
        s = total * i / n
        k = max(j for j in range(len(cum) - 1) if cum[j] <= s)
        t = (s - cum[k]) / ((cum[k + 1] - cum[k]) or 1.0)
        ax, ay = pts[k]
        bx, by = pts[k + 1]
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy) or 1.0
        off = amp if i % 2 else -amp
        out.append((ax + dx * t - dy / ln * off, ay + dy * t + dx / ln * off))
    out.append(pts[-1])
    return out


def _outline(m: dict, spec: list) -> list:
    """Contorno (y, z) de una region: tramos `{pts: [[x_px, y_px]...], zigzag: {teeth, amp}}` concatenados; el zigzag (px) convierte el tramo en una sutura en W."""
    poly = []
    for part in spec:
        pts = [tuple(p) for p in part["pts"]]
        if part.get("zigzag"):
            pts = _zigzag(pts, int(part["zigzag"]["teeth"]), float(part["zigzag"]["amp"]))
        poly += pts
    return [_px_to_yz(m, x, y) for x, y in poly]


def _inside(poly: list, y: float, z: float) -> bool:
    c = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, zi = poly[i]
        yj, zj = poly[j]
        if (zi > z) != (zj > z) and y < (yj - yi) * (z - zi) / (zj - zi + 1e-18) + yi:
            c = not c
        j = i
    return c


def _shell(verts: list, faces: list, keep: set, thickness: float) -> tuple:
    """Cascara cerrada de un trozo de superficie (las caras `keep`): la superficie exterior, la interior desplazada `thickness` a lo largo de la normal de cada vertice (hacia dentro)
    y las paredes del borde. Orientada hacia fuera."""
    vmap, nv, nf = {}, [], []
    for fi in keep:
        for vi in faces[fi]:
            if vi not in vmap:
                vmap[vi] = len(nv)
                nv.append(verts[vi])
    normal = [[0.0, 0.0, 0.0] for _ in nv]
    for fi in keep:
        f = faces[fi]
        a, b, c = verts[f[0]], verts[f[1]], verts[f[2]]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        for vi in f:
            k = vmap[vi]
            normal[k][0] += n[0]
            normal[k][1] += n[1]
            normal[k][2] += n[2]
    inner = []
    for p, n in zip(nv, normal):
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        inner.append((p[0] - n[0] / ln * thickness, p[1] - n[1] / ln * thickness, p[2] - n[2] / ln * thickness))
    outer_faces = [tuple(vmap[v] for v in faces[fi]) for fi in keep]
    verts_out = nv + inner
    off = len(nv)
    faces_out = list(outer_faces) + [tuple(off + v for v in reversed(f)) for f in outer_faces]
    edges = {}
    for f in outer_faces:
        for i in range(len(f)):
            edges.setdefault((f[i], f[(i + 1) % len(f)]), 0)
    for (a, b) in edges:
        if (b, a) not in edges:  # arista de borde: pared (b, a, a', b')
            faces_out.append((b, a, off + a, off + b))
    return verts_out, faces_out


def vault_outer(shape: dict | None = None) -> tuple:
    """Superficie EXTERIOR de la boveda ya subdividida (cache): la que se corta en huesos."""
    if "vault_outer" not in _CACHE:
        _CACHE["vault_outer"] = subdivide(vault_cage(shape), levels=SUBSURF_LEVELS)
    return _CACHE["vault_outer"]


def vault_core(shape: dict | None = None) -> "bmesh.types.BMesh":
    """NUCLEO del neurocraneo: el mismo ovoide encogido (`core_shrink`) y liso, que cierra por dentro los surcos entre los huesos. Es `cp.Skull`."""
    sh = shape or load_skull()
    v = dict(sh["vault"])
    k = v["core_shrink"]
    for key in ("half_width", "radius_front", "radius_back", "radius_up", "radius_down"):
        v[key] = v[key] - k
    bm = bmesh.new()
    _layer(bm)
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=v["segments"] // 2 - 1, use_grid_fill=True)
    for vert in bm.verts:
        vert.co = vault_point(v, vert.co.x, vert.co.y, vert.co.z)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def vault_bones(shape: dict | None = None) -> dict:
    """{nombre: (vertices, caras)} de los CINCO huesos de la boveda como cascaras cerradas independientes (frontal, parietal, temporal y esfenoides izquierdos y derechos, occipital), en H.
    Se cortan de la superficie exterior de la boveda por regiones de un MAPA de suturas (`config/cp/skull.json`, de la lamina lateral): sin cortes fractales, solo poligonos y
    W/triangulos. Entre dos huesos se quita una fila de caras (surco de la sutura); cada pieza se queda con su mayor trozo conexo y recibe grosor hacia dentro."""
    sh = shape or load_skull()
    v = sh["vault"]
    su = sh["sutures"]
    m = su["image_map"]
    regions = [(r["name"], _outline(m, r["outline"])) for r in su["regions"]]  # por orden de prioridad; el frontal es el resto
    verts, faces = vault_outer(sh)
    cen = []
    for f in faces:
        n = len(f)
        cen.append((sum(verts[i][0] for i in f) / n, sum(verts[i][1] for i in f) / n, sum(verts[i][2] for i in f) / n))
    label = []
    for (x, y, z) in cen:
        if z < su["base_clip_z"]:
            label.append(None)
            continue
        name = "parietal"  # el resto de la boveda (entre la sutura coronal, la escamosa y la lambdoidea)
        for rn, poly in regions:
            if _inside(poly, y, z):
                name = rn
                break
        if name == "frontal" and z < su["frontal_clip_z"]:
            label.append(None)
            continue
        if abs(x) < su["sagittal_gap"] and name in ("parietal",):
            label.append(None)
            continue
        side = "L" if x > 0 else "R"
        label.append(name if name in ("frontal", "occipital") else name + side)
    edge = {}
    for fi, f in enumerate(faces):
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            edge.setdefault((min(a, b), max(a, b)), []).append(fi)
    neigh = [[] for _ in faces]
    for fs in edge.values():
        if len(fs) == 2:
            neigh[fs[0]].append(fs[1])
            neigh[fs[1]].append(fs[0])
    for _ in range(int(su["groove_faces"])):  # surco: caras de borde entre dos huesos distintos
        cut = [fi for fi in range(len(faces)) if label[fi] and any(label[n] and label[n] != label[fi] for n in neigh[fi])]
        for fi in cut:
            label[fi] = None
    out = {}
    names = sorted({lb for lb in label if lb})
    for nm in names:
        members = {fi for fi in range(len(faces)) if label[fi] == nm}
        seen, best = set(), set()
        for s0 in members:  # mayor componente conexa (sin islotes sueltos)
            if s0 in seen:
                continue
            comp, stack = set(), [s0]
            while stack:
                x = stack.pop()
                if x in comp:
                    continue
                comp.add(x)
                stack += [n for n in neigh[x] if n in members and n not in comp]
            seen |= comp
            if len(comp) > len(best):
                best = comp
        sv, sf = _shell(verts, faces, best, float(su["shell_thickness"]))
        out[{"frontal": "SkullFrontal", "occipital": "SkullOccipital"}.get(nm, nm[:-1].capitalize() + nm[-1])] = (sv, sf)
    return out


def ellipsoid_cage(centre, radii, segments: int = 8, crease: float = 0.0) -> "bmesh.types.BMesh":
    """Elipsoide REDONDEADO (esfera de cubo subdividida): para los huesos pequenos de forma ovoide (temporal, mastoides, condilos); sin aristas de caja."""
    bm = bmesh.new()
    _layer(bm)
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=segments - 1, use_grid_fill=True)
    for v in bm.verts:
        d = _cubesphere(v.co.x, v.co.y, v.co.z)
        v.co = Vector((centre[0] + radii[0] * d[0], centre[1] + radii[1] * d[1], centre[2] + radii[2] * d[2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def zygomatic_cage(sx: float) -> "bmesh.types.BMesh":
    """HUESO CIGOMATICO (pomulo tetrarradiado, laminas anatomicas): UN barrido con el APOFISIS FRONTAL (delgada, sube por el borde lateral de la orbita hasta la sutura cigomatico-frontal,
    por delante del ala mayor del esfenoides), el CUERPO malar (ancho; se apoya en el maxilar, borde y suelo de la orbita) y la APOFISIS TEMPORAL (arco largo y fino que baja ligeramente y
    entra en la apofisis cigomatica del temporal: arco cigomatico). Pieza independiente."""
    up, ac = (0, 1, 0), (0, 0, 1)
    return sweep_box([
        ((sx * 0.0308, -0.0562, 0.0152), up, 0.0040, 0.0017),  # extremo de la apofisis frontal (toca el frontal)
        ((sx * 0.0330, -0.0560, 0.0090), up, 0.0046, 0.0019),
        ((sx * 0.0352, -0.0550, 0.0020), (0, 1, 0.2), 0.0056, 0.0021),  # borde lateral de la orbita
        ((sx * 0.0368, -0.0525, -0.0050), (0, 1, 0.4), 0.0075, 0.0026),  # cuerpo malar (el mas ancho)
        ((sx * 0.0376, -0.0490, -0.0092), (0, 0.4, 1), 0.0062, 0.0024),  # angulo inferior
        ((sx * 0.0392, -0.0420, -0.0088), ac, 0.0046, 0.0020),  # inicio de la apofisis temporal
        ((sx * 0.0398, -0.0330, -0.0080), ac, 0.0040, 0.0017),  # arco largo y fino
        ((sx * 0.0393, -0.0230, -0.0068), ac, 0.0038, 0.0016),
        ((sx * 0.0365, -0.0125, -0.0048), ac, 0.0042, 0.0019),  # raiz temporal
        ((sx * 0.0335, -0.0040, -0.0038), ac, 0.0042, 0.0019),  # entra en el temporal
    ], chamfer=0.28)


def temporal_cage(sx: float) -> "bmesh.types.BMesh":
    """HUESO TEMPORAL (escama baja, oido y fosa glenoidea): bloque subdividido bajo la pared lateral de la boveda. Pieza independiente."""
    return ellipsoid_cage((sx * 0.0275, -0.0100, -0.0030), (0.0125, 0.0215, 0.0115), segments=10)


def mastoid_cage(sx: float) -> "bmesh.types.BMesh":
    """APOFISIS MASTOIDES (cuelga del temporal, hito mastoid_process). Pieza independiente."""
    return ellipsoid_cage((sx * 0.0194, -0.0139, -0.0138), (0.0072, 0.0088, 0.0115), segments=8)


def condyle_cage(sx: float) -> "bmesh.types.BMesh":
    """CONDILO OCCIPITAL (articula con C1; su centro es el origen del craneo). Pieza independiente."""
    return ellipsoid_cage((sx * 0.0120, 0.0040, -0.0045), (0.0062, 0.0145, 0.0052), segments=6)


def teeth_cage(lower: bool = False) -> "bmesh.types.BMesh":
    """ARCADA DENTAL (superior o inferior): barrido de seccion rectangular a lo largo del arco. Pieza independiente."""
    z = -0.0405 if lower else -0.0335
    zc = -0.0425 if lower else -0.0370
    r = 0.0044 if lower else 0.0046
    t = 0.0034
    pts = [(-0.0215, -0.056, z), (-0.0115, -0.070, zc + 0.0005), (0.0, -0.075 if lower else -0.0765, zc), (0.0115, -0.070, zc + 0.0005), (0.0215, -0.056, z)]
    return sweep_box([(p, (0, 0, 1), r, t) for p in pts])


SKULL_PARTS = {  # nombre del objeto -> constructor de su jaula
    "Skull": vault_core, "SkullFace": face_cage, "ZygomaticL": lambda: zygomatic_cage(1.0), "ZygomaticR": lambda: zygomatic_cage(-1.0),
    "TemporalBaseL": lambda: temporal_cage(1.0), "TemporalBaseR": lambda: temporal_cage(-1.0), "MastoidL": lambda: mastoid_cage(1.0), "MastoidR": lambda: mastoid_cage(-1.0),
    "CondyleL": lambda: condyle_cage(1.0), "CondyleR": lambda: condyle_cage(-1.0), "TeethUpper": lambda: teeth_cage(False),
}


def jaw_cage() -> "bmesh.types.BMesh":
    """Mandibula: UN barrido en U de secciones rectangulares (condilo -> rama recta -> gonion en esquina -> cuerpo -> menton plano -> lado opuesto)."""
    left = [  # centro, eje del ancho, semi_ancho, semi_espesor
        ((0.0290, -0.0322, -0.0085), (0, 1, 0), 0.0050, 0.0042),  # condilo
        ((0.0288, -0.0320, -0.0128), (0, 1, 0), 0.0040, 0.0030),  # cuello condilar
        ((0.0298, -0.0300, -0.0200), (0, 1, 0), 0.0075, 0.0030),  # rama (apofisis coronoides adelante)
        ((0.0306, -0.0278, -0.0320), (0, 1, 0), 0.0092, 0.0030),
        ((0.0302, -0.0240, -0.0420), (0, 1, 0), 0.0088, 0.0040),  # gonion (angulo)
        ((0.0302, -0.0262, -0.0452), (0, 0.6, 0.8), 0.0080, 0.0046),
        ((0.0286, -0.0310, -0.0445), (0, 0, 1), 0.0068, 0.0050),  # cuerpo
        ((0.0232, -0.0470, -0.0458), (0, 0, 1), 0.0066, 0.0052),
        ((0.0155, -0.0600, -0.0462), (0, 0, 1), 0.0064, 0.0054),
        ((0.0072, -0.0690, -0.0464), (0, 0, 1), 0.0064, 0.0056),
    ]
    mid = [((0.0, -0.0715, -0.0465), (0, 0, 1), 0.0066, 0.0058)]  # menton plano
    right = [((-c[0], c[1], c[2]), (-e[0], e[1], e[2]), w, t) for c, e, w, t in reversed(left)]
    bm = sweep_box(left + mid + right, chamfer=0.30, crease=CREASE_HARD)
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


def skull_parts() -> dict:
    """{nombre: (vertices, caras)} de las piezas INDEPENDIENTES del craneo (en H, relativo al origen), ya subdivididas (cache)."""
    if "parts" not in _CACHE:
        _CACHE["parts"] = {n: subdivide(f(), levels=1 if n == "Skull" else SUBSURF_LEVELS) for n, f in SKULL_PARTS.items()}
        _CACHE["parts"].update(vault_bones())  # los cinco huesos de la boveda, cascaras independientes sobre el nucleo (cp.Skull)
    return _CACHE["parts"]


def box_mandible() -> tuple:
    if "jaw" not in _CACHE:
        _CACHE["jaw"] = subdivide(jaw_cage())
    return _CACHE["jaw"]


def teeth_lower() -> tuple:
    if "teeth_lower" not in _CACHE:
        _CACHE["teeth_lower"] = subdivide(teeth_cage(True))
    return _CACHE["teeth_lower"]
