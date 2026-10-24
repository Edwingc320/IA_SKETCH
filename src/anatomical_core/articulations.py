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
from dataclasses import dataclass
from pathlib import Path

from .anatomy import AnatomyModel, PointSpec, _eval, _point_spec, _swap_side, point_segment_distance
from .config import PROJECT_ROOT, ConfigError, _read_json
from .geometry import Vec3, mirror_point
from .skeleton import SkeletonModel

ARTICULATIONS_DIR = PROJECT_ROOT / "config" / "articulations"
FILES = ("thorax_shoulder", "head_neck", "lumbar_pelvis", "arm_hand", "leg_foot")


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

    def signature(self) -> str:
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        payload = {
            "j": {n: [j.kind, list(j.bones), j.carrier, r(j.center), [[d.name, d.total_deg] for d in j.dofs], j.rig_driver]
                  for n, j in sorted(self.joints.items())},
            "l": {n: [l.from_bone, l.to_bone, r(l.a), r(l.b)] for n, l in sorted(self.ligaments.items())},
            "a": {n: [a.bone, r(a.point), list(a.structures)] for n, a in sorted(self.attachments.items())},
        }
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
    sources, joints, ligaments, attachments = {}, {}, {}, {}

    def ev(spec: PointSpec, side, cache):
        # los puntos se definen para el lado izquierdo (o centrales); el derecho es su espejo
        p = _eval(spec, base, built)
        return mirror_point(p) if side == "R" else p

    def put(store, name, value):
        if name in joints or name in ligaments or name in attachments:
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
            for side in _sides(lg):
                sw = lambda t: _swap_side(t, side or "L")  # noqa: E731
                put(ligaments, sw(lg["name"]), Ligament(
                    sw(lg["name"]), sw(lg["from"]["bone"]), sw(lg["to"]["bone"]), ev(fa, side, None), ev(fb, side, None),
                    sw(lg["joint"]) if lg.get("joint") else None, lg.get("typical_length_m"),
                    tuple(lg.get("sources", [])), str(lg.get("notes", "")), float(lg.get("tolerance_m", 0.03)) * tol_k, region))
        for i, at in enumerate(data.get("attachments", [])):
            spec = _point_spec(at["point"], f"attachments[{i}].point")
            for side in _sides(at):
                sw = lambda t: _swap_side(t, side or "L")  # noqa: E731
                put(attachments, sw(at["name"]), Attachment(
                    sw(at["name"]), sw(at["bone"]), ev(spec, side, None), tuple(at.get("structures", [])),
                    tuple(at.get("sources", [])), str(at.get("notes", "")), float(at.get("tolerance_m", 0.03)) * tol_k, region))
    return ArticulationModel(sources, joints, ligaments, attachments)


def bone_distance(p: Vec3, bone: str, base: SkeletonModel, anat: AnatomyModel) -> float:
    """Distancia de un punto a la geometria de un hueso: su segmento y, en el nivel 1, su contorno y su cartilago."""
    b = anat.bones.get(bone) or base.bones.get(bone)
    if b is None:
        return float("inf")
    d = point_segment_distance(p, b.head, b.tail)
    outline = getattr(b, "outline", ())
    if outline:
        pts = list(outline) + ([outline[0]] if getattr(b, "outline_closed", False) else [])
        d = min([d] + [point_segment_distance(p, a, c) for a, c in zip(pts, pts[1:])])
    cartilage = getattr(b, "cartilage", ())  # el cartilago costal forma parte de la costilla
    if cartilage:
        d = min([d] + [point_segment_distance(p, a, c) for a, c in zip(cartilage, cartilage[1:])])
    return d
