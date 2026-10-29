"""Columna vertebral `cp.*` (etapa B de la reconstruccion central; usa bpy/bmesh): vertebras con forma propia por region, discos lenticulares y apilado sobre la curva sagital.

Cada vertebra es una JAULA (cuerpo + arco neural + apofisis) que despues se subdivide (Subdivision Surface):

  * CUERPO: loft de siete secciones en RINONES (pared posterior concava) con cintura y reborde en los platillos, y cuña (mas alto delante).
  * ARCO NEURAL: un barrido en U de secciones rectangulares (pediculos -> laminas -> apice) que deja abierto el FORAMEN VERTEBRAL junto a la pared posterior del cuerpo.
  * APOFISIS ESPINOSA: lamina que sale del apice hacia atras y hacia abajo (larga e inclinada en el torax, corta y bifida en C3-C6, alta y roma en la lumbar);
    TRANSVERSAS: laminas laterales; articulares: bloques sobre la union pedículo-lamina; carillas costales (torax) y ganchos uncinados (cervical).
  * DISCOS: lentes (convexos) con cuña en lumbar y cervical.
  * C1 (anillo cerrado con masas laterales) y C2 (cuerpo, odontoides y arco) tienen constructores propios.

Dimensiones: `config/cp/spine.json` (fracciones de H, aproximadas por convencion y declaradas): se interpolan por nivel dentro de cada region. Las alturas de los cuerpos y de los
discos las fijan los datos antropometricos (las pasa quien llama). Todo escala con la altura."""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

from .config import PROJECT_ROOT, ConfigError, _read_json
from .cp_skullbox import CREASE_HARD, _append, _layer, _set_crease, box_cage, subdivide, sweep_box

SPINE_FILE = PROJECT_ROOT / "config" / "cp" / "spine.json"
SECTION_POINTS = 16
BODY_RINGS = 7
SUBSURF_LEVELS = 1


def load_spine(path=None) -> dict:
    p = path or SPINE_FILE
    if not p.exists():
        raise ConfigError(f"Falta {p}")
    return _read_json(p)


def level_params(spine: dict, region: str, level: str) -> dict:
    """Parametros de un nivel: interpolacion lineal entre `start` y `end` de la region segun su posicion en la lista de niveles (+ tablas por nivel)."""
    r = spine["regions"][region]
    levels = r["levels"]
    t = levels.index(level) / max(1, len(levels) - 1)
    out = {}
    for k, a in r["start"].items():
        b = r["end"][k]
        if isinstance(a, list):
            out[k] = [x + (y - x) * t for x, y in zip(a, b)]
        elif isinstance(a, bool):
            out[k] = a if t < 0.5 else b
        else:
            out[k] = a + (b - a) * t
    if "bifid_levels" in r:
        out["bifid"] = level in r["bifid_levels"]  # espinosa bifida en C3-C6; C7 (vertebra prominente) no
    if "spinous_by_level" in r:
        length, ang = r["spinous_by_level"][level]
        out["sp"] = [length, float(ang)] + out["sp"][2:]
    if "transverse_by_level" in r:
        length, up = r["transverse_by_level"][level]
        out["tp"] = [length, up] + out["tp"][2:]
    return out


def kidney_section(bw: float, bd: float, notch: float, f: float = 1.0) -> list:
    """Seccion en riñon (x lateral, y posterior): elipse con la pared posterior hundida en el centro."""
    pts = []
    for k in range(SECTION_POINTS):
        t = 2 * math.pi * k / SECTION_POINTS
        c, s = math.cos(t), math.sin(t)
        y = bd * f * s
        if s > 0:
            y *= 1.0 - notch * (1.0 - c * c)
        pts.append(Vector((bw * f * c, y, 0.0)))
    return pts


def loft_sections(rings: list, crease_ends: float = 0.7) -> "bmesh.types.BMesh":
    """Cierra una pila de secciones (listas de vertices iguales, de abajo arriba) con caras y tapas poligonales; las aristas de los platillos llevan crease."""
    bm = bmesh.new()
    _layer(bm)
    grid = [[bm.verts.new(p) for p in ring] for ring in rings]
    n = len(grid[0])
    for i in range(len(grid) - 1):
        for k in range(n):
            bm.faces.new((grid[i][k], grid[i][(k + 1) % n], grid[i + 1][(k + 1) % n], grid[i + 1][k]))
    bm.faces.new(list(reversed(grid[0])))
    bm.faces.new(grid[-1])
    edges = []
    for ring in (grid[0], grid[-1]):
        edges += [bm.edges.get((ring[k], ring[(k + 1) % n])) for k in range(n)]
    _set_crease(bm, [e for e in edges if e], crease_ends)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def body_cage(bw: float, bd: float, bh: float, waist: float, notch: float, wedge: float) -> "bmesh.types.BMesh":
    rings = []
    for i in range(BODY_RINGS):
        u = -1.0 + 2.0 * i / (BODY_RINGS - 1)  # -1 abajo .. 1 arriba
        f = 1.0 - waist * (1.0 - u * u) + (0.025 if abs(u) > 0.9 else 0.0)  # cintura y reborde del platillo
        sec = kidney_section(bw, bd, notch, f)
        z0 = u * bh / 2
        rings.append([Vector((p.x, p.y, z0 * (1.0 - wedge * p.y / bd))) for p in sec])  # cuña: mas alto delante (y < 0)
    return loft_sections(rings)


def disc_cage(bw: float, bd: float, hd: float, wedge: float, bulge: float, notch: float = 0.18) -> "bmesh.types.BMesh":
    rings = []
    for i in range(5):
        u = -1.0 + 0.5 * i
        f = bulge - 0.09 * u * u
        sec = kidney_section(bw, bd, notch, f)
        z0 = u * hd / 2
        rings.append([Vector((p.x, p.y, z0 * (1.0 - wedge * p.y / bd))) for p in sec])
    return loft_sections(rings, crease_ends=0.3)


def _dir_yz(back_deg: float, up_deg: float) -> Vector:
    """Direccion en el plano y-z: `back_deg` grados hacia atras desde el eje y... (0 = horizontal hacia atras; positivo = hacia arriba)."""
    a = math.radians(up_deg)
    return Vector((0.0, math.cos(a), math.sin(a)))


def neural_arch(p: dict, bw: float, bd: float) -> "bmesh.types.BMesh":
    """Barrido en U (pediculos + laminas) y apofisis: deja el foramen vertebral abierto detras del cuerpo."""
    ped_l, ped_w, ped_h = p["ped"]
    fw, fd = p["fz"]
    lam_h, lam_t = p["lam"]
    y0 = bd * 0.70
    y1 = bd + ped_l
    left = [
        (Vector((-0.55 * bw, y0, 0.0)), (0, 0, 1), ped_h / 2, ped_w / 2),
        (Vector((-(fw + ped_w * 0.5), y1, 0.0)), (0, 0, 1), ped_h / 2, ped_w / 2),
        (Vector((-(fw * 0.72), y1 + fd * 0.80, 0.0006)), (0, 0, 1), lam_h / 2, lam_t / 2),
        (Vector((-(fw * 0.30), y1 + fd * 0.98, 0.0012)), (0, 0, 1), lam_h / 2, lam_t / 2),
    ]
    mid = [(Vector((0.0, y1 + fd * 1.0 + lam_t * 0.4, 0.0014)), (0, 0, 1), lam_h / 2, lam_t / 2)]
    right = [(Vector((-c.x, c.y, c.z)), e, w, t) for c, e, w, t in reversed(left)]
    bm = sweep_box(left + mid + right, chamfer=0.30, crease=CREASE_HARD)
    apex = Vector((0.0, y1 + fd * 1.0 + lam_t * 0.4, 0.0014))
    # apofisis espinosa: lamina que sale hacia atras y abajo
    sp_len, sp_deg, sp_h, sp_t = p["sp"]
    d = _dir_yz(0, -sp_deg)
    ew = Vector((0.0, -d.z, d.y))  # perpendicular a la direccion, en el plano y-z (el alto de la lamina)
    bifid = p.get("bifid", False)
    offs = (-0.0020, 0.0020) if bifid else (0.0,)
    for dx in offs:
        rings = [(apex + Vector((dx * k, 0, 0)) + d * (sp_len * k), ew, sp_h / 2 * (1.0 - 0.25 * k), sp_t / 2 * (1.0 - 0.15 * k)) for k in (0.0, 0.5, 1.0)]
        _append(bm, sweep_box(rings, chamfer=0.25))
    # apofisis transversas: laminas laterales
    tp_len, tp_up, tp_back, tp_w, tp_t = p["tp"]
    for sx in (1.0, -1.0):
        j = Vector((sx * (fw + ped_w * 0.5), y1 + fd * 0.25, 0.0))
        dv = Vector((sx * math.cos(math.radians(tp_up)), math.sin(math.radians(tp_back)) * 0.5, math.sin(math.radians(tp_up)))).normalized()
        rings = [(j + dv * (tp_len * k), (0, 1, 0), tp_w / 2 * (1.0 - 0.15 * k), tp_t / 2) for k in (0.0, 0.5, 1.0)]
        _append(bm, sweep_box(rings, chamfer=0.25))
        fac = p["fac"]
        for sz in (1.0, -1.0):  # apofisis articulares superior e inferior
            _append(bm, box_cage((sx * fw * 0.95, y1 + fd * 0.45, sz * (ped_h / 2 + fac * 0.7)), (fac * 0.9, fac * 1.1, fac * 0.9), segments=0, crease=0.5))
    return bm


def vertebra_cage(region: str, level: str, p: dict, body_h: float) -> "bmesh.types.BMesh":
    """Jaula de una vertebra tipica (C3-C7, T1-T12, L1-L5) en H, origen en el centro del cuerpo."""
    bw, bd = p["bw"], p["bd"]
    bm = body_cage(bw, bd, body_h, p["waist"], p["notch"], p["wedge"])
    _append(bm, neural_arch(p, bw, bd))
    if p.get("costal"):  # carillas costales: salientes laterales-posteriores del cuerpo y punta de la transversa
        for sx in (1.0, -1.0):
            for sz in (1.0, -1.0):
                _append(bm, box_cage((sx * bw * 0.96, bd * 0.35, sz * body_h * 0.36), (0.0016, 0.0032, 0.0026), segments=0, crease=0.5))
    if p.get("uncinate"):  # ganchos uncinados de la cara superior del cuerpo cervical
        for sx in (1.0, -1.0):
            _append(bm, box_cage((sx * bw * 0.82, -bd * 0.05, body_h * 0.5 + 0.0008), (0.0022, bd * 0.55, 0.0011), segments=0, crease=0.5))
    return bm


def atlas_cage() -> "bmesh.types.BMesh":
    """C1: anillo cerrado (arco anterior, masas laterales, arco posterior con tuberculo) y apofisis transversas anchas."""
    rings = []
    n = 16
    for k in range(n):
        t = 2 * math.pi * k / n
        c = Vector((0.0125 * math.cos(t), 0.0112 * math.sin(t), 0.0))
        wide = 1.0 + 0.55 * math.exp(-((abs(math.cos(t)) - 1.0) / 0.25) ** 2)  # masas laterales mas gruesas
        rings.append((c, (0, 0, 1), 0.0030 * wide, 0.0028 * (1.15 if math.sin(t) < -0.8 else 1.0)))
    bm = sweep_box(rings, chamfer=0.35, closed=True)
    for sx in (1.0, -1.0):
        r = [(Vector((sx * x, 0.002, -0.0005)), (0, 1, 0), 0.0030 - 0.0007 * k, 0.0016) for x, k in ((0.0140, 0.0), (0.0185, 0.5), (0.0230, 1.0))]
        _append(bm, sweep_box(r, chamfer=0.25))
    _append(bm, box_cage((0.0, 0.0145, 0.0), (0.0020, 0.0022, 0.0024), segments=0, crease=0.5))  # tuberculo posterior
    return bm


def axis_cage(body_h: float) -> "bmesh.types.BMesh":
    """C2: cuerpo, apofisis odontoides y arco con espinosa bifida gruesa."""
    bm = body_cage(0.0080, 0.0070, 0.0100, 0.05, 0.14, 0.0)
    bmesh.ops.translate(bm, vec=Vector((0, 0, -0.0035)), verts=bm.verts)
    dens = [(Vector((0.0, -0.0008, 0.0015 + 0.0035 * k)), (1, 0, 0), 0.0042 - 0.0007 * k, 0.0040 - 0.0006 * k) for k in (0.0, 0.5, 1.0, 1.6)]
    _append(bm, sweep_box(dens, chamfer=0.30))
    p = {"ped": [0.0038, 0.0036, 0.0054], "fz": [0.0080, 0.0070], "lam": [0.0060, 0.0030], "sp": [0.0180, 12.0, 0.0060, 0.0040], "tp": [0.0080, -10.0, 0.0, 0.0034, 0.0026], "fac": 0.0026, "bifid": True}
    arch = neural_arch(p, 0.0080, 0.0070)
    bmesh.ops.translate(arch, vec=Vector((0, 0, -0.0035)), verts=arch.verts)
    _append(bm, arch)
    return bm


def frame_matrix(origin: Vector, h: float, curve, s: float) -> Matrix:
    """Marco de la vertebra a la altura s (H): x lateral, y posterior, z a lo largo de la tangente de la curva sagital."""
    c = lambda q: origin + Vector((0.0, curve(q) * h, q * h))  # noqa: E731
    t = (c(s + 1e-4) - c(s - 1e-4)).normalized()
    x = Vector((1, 0, 0))
    y = t.cross(x).normalized()
    return Matrix.Translation(c(s)) @ Matrix((x, y, t)).transposed().to_4x4()


def build_column(h: float, origin: Vector, region: str, levels: list, curve, discs: dict, spine: dict | None = None) -> "bmesh.types.BMesh":
    """Apila discos y vertebras de abajo arriba desde el centro del primer disco (origen) sobre la curva `curve(s)`.
    `levels` = [(nombre, alto_del_cuerpo, alto_del_disco_debajo)] (alto de disco 0 = sin disco); `discs` = parametros del disco de la region. Devuelve la jaula ya con
    marcos aplicados, en metros (escala h)."""
    spine = spine or load_spine()
    bm = bmesh.new()
    _layer(bm)
    z = -levels[0][2] / 2
    for name, body_h, disc_h in levels:
        p = None
        if name not in ("C1", "C2"):
            p = level_params(spine, region, name)
        if disc_h > 0:
            q = p or level_params(spine, region, spine["regions"][region]["levels"][-1])  # C2 usa los parametros del ultimo nivel tipico (C3)
            d = disc_cage(q["bw"] * 0.97, q["bd"] * 0.97, disc_h, spine["regions"][region]["disc"]["wedge"], spine["regions"][region]["disc"]["bulge"])
            _place(bm, d, frame_matrix(origin, h, curve, z + disc_h / 2), h)
            z += disc_h
        if name == "C1":
            part = atlas_cage()
        elif name == "C2":
            part = axis_cage(body_h)
        else:
            part = vertebra_cage(region, name, p, body_h)
        _place(bm, part, frame_matrix(origin, h, curve, z + body_h / 2), h)
        z += body_h
    return bm


def _place(bm, part, matrix, h):
    """Escala la pieza (H -> metros), la coloca con `matrix` y la anade a `bm` conservando los creases."""
    bmesh.ops.scale(part, vec=Vector((h, h, h)), verts=part.verts)
    bmesh.ops.transform(part, matrix=matrix, verts=part.verts)
    _append(bm, part)


def subdivide_column(bm, levels: int = SUBSURF_LEVELS) -> tuple:
    """(vertices, caras) de la columna tras la Subdivision Surface (en metros; no cambia la escala)."""
    return subdivide(bm, levels=levels, scale=1.0)
