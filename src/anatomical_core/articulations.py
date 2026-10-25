"""Puntos de union anatomicos para las poses futuras (Python puro, sin bpy).

Tres tipos de datos, todos anclados a huesos de la base o del nivel 1 con la misma sintaxis de
puntos que anatomy.py (at / lerp + offset_h en fraccion de la altura):
  * articulaciones naturales independientes: centro, huesos que une, hueso que lleva el marcador,
    rangos de movimiento citados (con su fuente) y, si existe, la articulacion de la base que hoy
    la mueve (rig_driver);
  * ligamentos: segmento entre dos huesos (origen e insercion);
  * inserciones (tendones/musculos): un punto sobre un hueso.
Son DATOS para planificar poses y musculos; no anaden movimiento al rig. Los rangos son los que
publican las fuentes citadas (aproximados; no son limites medicos universales).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import volumes
from .anatomy import AnatomyModel, PointSpec, _eval, _point_spec, _swap_side, point_segment_distance, point_triangle_distance
from .config import PROJECT_ROOT, ConfigError, _read_json
from .geometry import Vec3, mirror_point
from .skeleton import SkeletonModel

ARTICULATIONS_DIR = PROJECT_ROOT / "config" / "articulations"
FILES = ("thorax_shoulder", "head_neck", "lumbar_pelvis", "arm_hand", "leg_foot", "spine", "thorax_ligaments", "pelvic_floor", "hand_foot_ligaments")


@dataclass(frozen=True)
class DofRange:
    name: str
    total_deg: tuple | None  # (min, max) de los valores publicados; None si no hay cifra (unidad en `unit`)
    source: str | None
    note: str = ""
    unit: str = "deg"  # "deg" (grados) o "mm" (p. ej. apertura de la boca)
    per_side: bool = False  # True: la fuente da el valor hacia UN lado (no el rango total)


@dataclass(frozen=True)
class Joint:
    name: str
    kind: str
    bones: tuple
    carrier: str  # hueso al que se emparenta el marcador
    center: Vec3
    tolerance_m: float
    dofs: tuple
    rig_driver: str | None  # articulacion de la base que hoy la mueve (si existe)
    ligaments: tuple
    sources: tuple
    notes: str
    known_limitation: str = ""  # si no esta vacio, un hueco entre el centro y un hueso se avisa (warning)
    region: str = ""  # archivo de origen (p. ej. thorax_shoulder, head_neck)


@dataclass(frozen=True)
class Waypoint:
    """Guia de envoltura de un ligamento: un punto que viaja con su hueso y obliga a la trayectoria a rodear la superficie ossea."""
    bone: str
    point: Vec3
    structure: str


@dataclass(frozen=True)
class BoneSurface:
    """Superficie analitica de un hueso (esfera o capsula) que los ligamentos no pueden atravesar. Es una CONVENCION de obstaculo: el modelo del
    hueso es un esqueleto de lineas sin anchura; esta superficie solo da cuerpo a la cabeza y el cuello del femur para envolver la capsula."""
    name: str
    bone: str
    kind: str  # sphere | capsule
    a: Vec3
    b: Vec3  # igual que `a` en la esfera
    radius_m: float
    sources: tuple
    notes: str
    no_numeric_source: bool = False  # True: el radio es una convencion sin cifra publicada consultada (se dice en las notas)

    def signed_distance(self, p: Vec3) -> float:
        """Distancia con signo a la superficie: negativa dentro del cuerpo."""
        return point_segment_distance(p, self.a, self.b) - self.radius_m


@dataclass(frozen=True)
class Ligament:
    name: str
    from_bone: str
    to_bone: str
    a: Vec3
    b: Vec3
    joint: str | None
    typical_length_m: float | None
    sources: tuple
    notes: str
    tolerance_m: float = 0.03  # distancia maxima de cada extremo a su hueso
    region: str = ""
    via: tuple = ()  # Waypoint(s) entre el origen y la insercion
    mechanics: dict | None = None  # propiedades mecanicas (rigidez, longitud sin tension): convencion parametrica declarada si no hay dato
    deform: bool = False  # True: en Blender cada nodo sigue a su hueso (malla deformada por la armadura); False: rigido, emparentado al hueso de origen
    avoid: tuple = ()  # nombres de las `BoneSurface` que la trayectoria no puede atravesar (cada ligamento con envoltura dice cuales)


@dataclass(frozen=True)
class Attachment:
    name: str
    bone: str
    point: Vec3
    structures: tuple
    sources: tuple
    notes: str
    tolerance_m: float = 0.03  # distancia maxima a su hueso (mas si la apofisis no esta modelada)
    region: str = ""


@dataclass(frozen=True)
class ArticulationModel:
    sources: dict  # clave -> {"url", "reliability", "title"}
    joints: dict
    ligaments: dict
    attachments: dict
    surfaces: dict = field(default_factory=dict)  # BoneSurface por nombre (obstaculos de envoltura)

    def signature(self) -> str:
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        payload = {
            "j": {n: [j.kind, list(j.bones), j.carrier, r(j.center), [[d.name, d.total_deg] for d in j.dofs], j.rig_driver]
                  for n, j in sorted(self.joints.items())},
            "l": {n: [l.from_bone, l.to_bone, r(l.a), r(l.b)] + ([[[w.bone, r(w.point)] for w in l.via]] if l.via else []) for n, l in sorted(self.ligaments.items())},
            "a": {n: [a.bone, r(a.point), list(a.structures)] for n, a in sorted(self.attachments.items())},
        }
        if self.surfaces:
            payload["s"] = {n: [x.bone, x.kind, r(x.a), r(x.b), round(x.radius_m, 6)] for n, x in sorted(self.surfaces.items())}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _sides(entry):
    return ("L", "R") if entry.get("mirror") else (None,)


def _dofs(raw, where) -> tuple:
    out = []
    for i, d in enumerate(raw or []):
        total = d.get("total_deg")
        if total is None:
            if not d.get("no_numeric_source"):
                raise ConfigError(f"{where}.dofs[{i}]: sin cifra; marca 'no_numeric_source': true si la fuente no da numero")
            rng = None
        else:
            rng = (float(total[0]), float(total[1])) if isinstance(total, list) else (float(total), float(total))
        unit = str(d.get("unit", "deg"))
        if unit not in ("deg", "mm"):
            raise ConfigError(f"{where}.dofs[{i}]: unit '{unit}' invalida (deg | mm)")
        out.append(DofRange(str(d["name"]), rng, d.get("source"), str(d.get("note", "")), unit, bool(d.get("per_side", False))))
    return tuple(out)


def load_articulation_data(directory: Path | str | None = None) -> list:
    d = Path(directory) if directory else ARTICULATIONS_DIR
    return [_read_json(d / f"{f}.json") for f in FILES if (d / f"{f}.json").exists()]


def build_articulations(base: SkeletonModel, anat: AnatomyModel, data_list) -> ArticulationModel:
    """Resuelve los puntos (lado izquierdo y su espejo) sobre la base y el nivel 1. No modifica nada."""
    built = dict(anat.bones)
    tol_k = base.height_m / 1.75  # las tolerancias se definen para 1.75 m y escalan con la altura, como la geometria
    sources, joints, ligaments, attachments, surfaces = {}, {}, {}, {}, {}

    def ev(spec: PointSpec, side, cache):
        # los puntos se definen para el lado izquierdo (o centrales); el derecho es su espejo
        p = _eval(spec, base, built)
        return mirror_point(p) if side == "R" else p

    def put(store, name, value):
        if name in joints or name in ligaments or name in attachments or name in surfaces:
            raise ConfigError(f"Nombre de union duplicado '{name}'")
        store[name] = value

    for data in data_list:
        region = str(data.get("region", ""))
        for k, s in data.get("sources", {}).items():
            if k in sources and sources[k] != s:
                raise ConfigError(f"La fuente '{k}' esta definida de dos formas distintas")
            sources[k] = s
        for i, j in enumerate(data.get("joints", [])):
            w = f"joints[{i}]"
            spec = _point_spec(j["center"], f"{w}.center")
            for side in _sides(j):
                sw = lambda t: _swap_side(t, side or "L")  # noqa: E731
                put(joints, sw(j["name"]), Joint(
                    sw(j["name"]), str(j["kind"]), tuple(sw(b) for b in j["bones"]), sw(j["carrier"]),
                    ev(spec, side, None), float(j.get("tolerance_m", 0.02)) * tol_k, _dofs(j.get("dofs"), w),
                    sw(j["rig_driver"]) if j.get("rig_driver") else None,
                    tuple(sw(x) for x in j.get("ligaments", [])), tuple(j.get("sources", [])), str(j.get("notes", "")),
                    str(j.get("known_limitation", "")), region))
        for i, lg in enumerate(data.get("ligaments", [])):
            w = f"ligaments[{i}]"
            fa, fb = _point_spec(lg["from"]["point"], f"{w}.from"), _point_spec(lg["to"]["point"], f"{w}.to")
            fv = [_point_spec(v["point"], f"{w}.via[{k}]") for k, v in enumerate(lg.get("via", []))]
            for side in _sides(lg):
                sw = lambda t: _swap_side(t, side or "L")  # noqa: E731
                via = tuple(Waypoint(sw(v["bone"]), ev(f, side, None), str(v.get("structure", ""))) for v, f in zip(lg.get("via", []), fv))
                put(ligaments, sw(lg["name"]), Ligament(
                    sw(lg["name"]), sw(lg["from"]["bone"]), sw(lg["to"]["bone"]), ev(fa, side, None), ev(fb, side, None),
                    sw(lg["joint"]) if lg.get("joint") else None, lg.get("typical_length_m"),
                    tuple(lg.get("sources", [])), str(lg.get("notes", "")), float(lg.get("tolerance_m", 0.03)) * tol_k, region,
                    via, dict(lg["mechanics"]) if lg.get("mechanics") else None, bool(lg.get("deform", False)), tuple(sw(x) for x in lg.get("avoid", []))))
        for i, at in enumerate(data.get("attachments", [])):
            spec = _point_spec(at["point"], f"attachments[{i}].point")
            for side in _sides(at):
                sw = lambda t: _swap_side(t, side or "L")  # noqa: E731
                put(attachments, sw(at["name"]), Attachment(
                    sw(at["name"]), sw(at["bone"]), ev(spec, side, None), tuple(at.get("structures", [])),
                    tuple(at.get("sources", [])), str(at.get("notes", "")), float(at.get("tolerance_m", 0.03)) * tol_k, region))
        for i, sf in enumerate(data.get("bone_surfaces", [])):
            w = f"bone_surfaces[{i}]"
            if sf.get("kind") not in ("sphere", "capsule"):
                raise ConfigError(f"{w}: kind debe ser sphere o capsule")
            fa = _point_spec(sf["a"], f"{w}.a")
            fb = _point_spec(sf["b"], f"{w}.b") if sf["kind"] == "capsule" else fa
            if not 0.0 < float(sf["radius_m"]) < 0.1:
                raise ConfigError(f"{w}: radius_m fuera de rango")
            for side in _sides(sf):
                sw = lambda t: _swap_side(t, side or "L")  # noqa: E731
                put(surfaces, sw(sf["name"]), BoneSurface(sw(sf["name"]), sw(sf["bone"]), sf["kind"], ev(fa, side, None), ev(fb, side, None),
                                                          float(sf["radius_m"]) * tol_k, tuple(sf.get("sources", [])), str(sf.get("notes", "")),
                                                          bool(sf.get("no_numeric_source", False))))
    return ArticulationModel(sources, joints, ligaments, attachments, surfaces)


def bone_distance(p: Vec3, bone: str, base: SkeletonModel, anat: AnatomyModel, surfaces: dict | None = None) -> float:
    """Distancia de un punto a la geometria de un hueso: su segmento y, en el nivel 1, su contorno (y su cara si es una lamina cerrada), su cartilago y,
    si se pasan `surfaces` (ArticulationModel.surfaces), la superficie analitica de ese hueso (cabeza y cuello del femur); dentro de ella la distancia es 0."""
    b = anat.bones.get(bone) or base.bones.get(bone)
    if b is None:
        return float("inf")
    d = point_segment_distance(p, b.head, b.tail)
    outline = getattr(b, "outline", ())
    if outline:
        pts = list(outline) + ([outline[0]] if getattr(b, "outline_closed", False) else [])
        d = min([d] + [point_segment_distance(p, a, c) for a, c in zip(pts, pts[1:])])
        if getattr(b, "outline_closed", False) and len(outline) >= 3:  # contorno cerrado = lamina: tambien su cara (abanico de triangulos)
            d = min([d] + [point_triangle_distance(p, outline[0], outline[i], outline[i + 1]) for i in range(1, len(outline) - 1)])
    cartilage = getattr(b, "cartilage", ())  # el cartilago costal forma parte de la costilla
    if cartilage:
        d = min([d] + [point_segment_distance(p, a, c) for a, c in zip(cartilage, cartilage[1:])])
    for sf in (surfaces or {}).values():
        if sf.bone == bone:
            d = min(d, max(0.0, sf.signed_distance(p)))
    if getattr(b, "volume", None):  # forma volumetrica (craneo): dentro de ella el punto esta en el hueso; fuera, a la distancia de su superficie
        verts, faces, tris = _volume_of(b)
        if volumes.point_inside(p, verts, faces):
            return 0.0
        for a, b2, c, lo, hi in tris:  # cota por caja envolvente: solo se calcula el triangulo si puede mejorar la distancia
            gap = max(max(lo[i] - p[i], p[i] - hi[i], 0.0) ** 2 for i in range(3)) ** 0.5
            if gap < d:
                d = min(d, point_triangle_distance(p, a, b2, c))
    return d


_VOLUME_CACHE: dict = {}


def _volume_of(b) -> tuple:
    key = (b.name, b.head, b.tail, b.outline, tuple(sorted(b.volume.items())))
    if key not in _VOLUME_CACHE:
        verts, faces = volumes.volume_mesh(b)
        tris = []
        for f in faces:
            for i in range(1, len(f) - 1):
                a, b2, c = verts[f[0]], verts[f[i]], verts[f[i + 1]]
                tris.append((a, b2, c, tuple(min(a[k], b2[k], c[k]) for k in range(3)), tuple(max(a[k], b2[k], c[k]) for k in range(3))))
        _VOLUME_CACHE[key] = (verts, faces, tris)
    return _VOLUME_CACHE[key]
