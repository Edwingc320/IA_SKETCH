"""Capa MUSCULAR (rama muscle-model; Python puro, sin bpy): origenes e inserciones de musculos anclados a los hitos oseos del modelo
oseo, con sus fibras (origen -> insercion). El modelo oseo no contiene musculos: esta capa se construye SOBRE el, y cada punto
muscular nace de un hito oseo (`landmark`) o de un punto de un hueso, a menos de 12 mm de su superficie.

Un sitio muscular es {"kind": "origin"|"insertion", "structure", "landmark" | ("bone" + "point"), "offset_h"}. Los puntos usan la
misma sintaxis (at / lerp + offset_h en fraccion de la altura) que el nivel 1, y `.L` se refleja a `.R` como en el resto del modelo."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .anatomy import AnatomyModel, _eval, _point_spec, _swap_side
from .articulations import ArticulationModel, bone_distance
from .config import PROJECT_ROOT, ConfigError, _read_json, _vec3
from .geometry import Vec3, add, length, mirror_point, scale, sub
from .skeleton import SkeletonModel

MUSCLES_DIR = PROJECT_ROOT / "config" / "muscles"
FILES = ("gluteal",)
KINDS = ("origin", "insertion")
SITE_TOL_M = 0.012  # distancia maxima de un sitio a la superficie de su hueso (a 1.75 m; escala con la altura)


@dataclass(frozen=True)
class MuscleSite:
    muscle: str
    kind: str
    index: int  # posicion dentro del musculo
    bone: str
    point: Vec3
    structure: str
    landmark: str | None
    sources: tuple
    notes: str


@dataclass(frozen=True)
class Muscle:
    name: str
    sites: tuple
    fibers: tuple  # (indice del origen, indice de la insercion): cada fibra une un origen con una insercion
    sources: tuple
    notes: str
    region: str


@dataclass(frozen=True)
class MuscleModel:
    sources: dict
    muscles: dict
    height_m: float

    def signature(self) -> str:
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        payload = {n: [[s.kind, s.bone, r(s.point)] for s in m.sites] + [list(m.fibers)] for n, m in sorted(self.muscles.items())}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def load_muscle_data(muscles_dir: Path | str | None = None) -> list:
    d = Path(muscles_dir) if muscles_dir else MUSCLES_DIR
    return [_read_json(d / f"{f}.json") for f in FILES if (d / f"{f}.json").exists()]


def build_muscles(base: SkeletonModel, anat: AnatomyModel, art: ArticulationModel, data_list: list) -> MuscleModel:
    sources: dict = {}
    muscles: dict = {}
    for data in data_list:
        region = str(data.get("region", "muscle"))
        for key, s in data.get("sources", {}).items():
            if key in sources and sources[key] != s:
                raise ConfigError(f"Fuente muscular '{key}' definida dos veces con datos distintos")
            sources[key] = s
        for i, m in enumerate(data.get("muscles", [])):
            w = f"{region}.muscles[{i}]"
            name = str(m["name"])
            sides = ("L", "R") if m.get("mirror", False) else (None,)
            if m.get("mirror", False) and not name.endswith(".L"):
                raise ConfigError(f"{w}: un musculo con mirror debe llamarse con sufijo .L")
            left_sites = None
            for side in sides:
                mname = _swap_side(name, side or "L")
                if mname in muscles:
                    raise ConfigError(f"Musculo duplicado '{mname}'")
                sites = []
                for k, raw in enumerate(m["sites"]):
                    if raw.get("kind") not in KINDS:
                        raise ConfigError(f"{w}.sites[{k}]: 'kind' debe ser origin o insertion")
                    if side == "R" and left_sites is not None:
                        ls = left_sites[k]
                        sites.append(MuscleSite(mname, ls.kind, k, _swap_side(ls.bone, "R"), mirror_point(ls.point), ls.structure,
                                                _swap_side(ls.landmark, "R") if ls.landmark else None, ls.sources, ls.notes))
                        continue
                    if "landmark" in raw:
                        lm = art.attachments.get(str(raw["landmark"]))
                        if lm is None:
                            raise ConfigError(f"{w}.sites[{k}]: el hito oseo '{raw['landmark']}' no existe en el modelo oseo")
                        bone, point, landmark = lm.bone, lm.point, lm.name
                    else:
                        bone = str(raw["bone"])
                        if bone not in anat.bones and bone not in base.bones:
                            raise ConfigError(f"{w}.sites[{k}]: hueso inexistente '{bone}'")
                        point, landmark = _eval(_point_spec(raw["point"], f"{w}.sites[{k}].point"), base, anat.bones), None
                    offset = _vec3(raw.get("offset_h", [0, 0, 0]), f"{w}.sites[{k}].offset_h")
                    sites.append(MuscleSite(mname, str(raw["kind"]), k, bone, add(point, scale(offset, base.height_m)), str(raw.get("structure", "")),
                                            landmark, tuple(raw.get("sources", ())), str(raw.get("notes", ""))))
                if side != "R":
                    left_sites = sites
                origins = [s.index for s in sites if s.kind == "origin"]
                inserts = [s.index for s in sites if s.kind == "insertion"]
                muscles[mname] = Muscle(mname, tuple(sites), tuple((o, t) for o in origins for t in inserts), tuple(m.get("sources", ())),
                                        str(m.get("notes", "")), region)
    return MuscleModel(sources, muscles, base.height_m)


def validate_muscles(base: SkeletonModel, anat: AnatomyModel, art: ArticulationModel, model: MuscleModel) -> list:
    """Cada sitio sobre la superficie de su hueso (< 12 mm), con origen e insercion, fuentes validas y simetria L/R."""
    from .validation import FRAME_TOL, Issue

    out = []
    tol = SITE_TOL_M * model.height_m / 1.75
    for key, s in model.sources.items():
        if not str(s.get("url", "")).startswith("https://") or s.get("reliability") not in ("alta", "media", "baja"):
            out.append(Issue("error", "MUS_SOURCE", f"Fuente muscular '{key}' invalida"))
    for n, m in model.muscles.items():
        kinds = {s.kind for s in m.sites}
        if kinds != {"origin", "insertion"}:
            out.append(Issue("error", "MUS_KINDS", f"'{n}' necesita al menos un origen y una insercion"))
        for k in m.sources:
            if k not in model.sources:
                out.append(Issue("error", "MUS_SOURCE_UNKNOWN", f"'{n}' cita la fuente desconocida '{k}'"))
        for s in m.sites:
            if s.bone not in anat.bones and s.bone not in base.bones:
                out.append(Issue("error", "MUS_BONE_UNKNOWN", f"'{n}' sitio {s.index}: hueso inexistente '{s.bone}'"))
                continue
            d = bone_distance(s.point, s.bone, base, anat)
            if d > tol:
                out.append(Issue("error", "MUS_SITE_OFF_BONE", f"'{n}' {s.kind} {s.index}: a {d * 1000:.1f} mm de la superficie de '{s.bone}' (maximo {tol * 1000:.1f})"))
            for k in s.sources:
                if k not in model.sources:
                    out.append(Issue("error", "MUS_SOURCE_UNKNOWN", f"'{n}' sitio {s.index}: fuente desconocida '{k}'"))
        right = n.replace(".L", ".R") if n.endswith(".L") else None
        if right and right in model.muscles:
            for a, b in zip(m.sites, model.muscles[right].sites):
                if length(sub(mirror_point(a.point), b.point)) > FRAME_TOL * 10:
                    out.append(Issue("error", "MUS_ASYMMETRIC", f"'{n}' no es simetrico respecto a su .R"))
    return out


def validate_muscles_snapshot(model: MuscleModel, snap: dict) -> list:
    """Compara los marcadores y fibras leidos de Blender con el modelo (posicion y hueso padre)."""
    from .validation import BLEND_TOL, Issue

    out = []
    expected = {}
    for n, m in model.muscles.items():
        for s in m.sites:
            expected[f"MUS_site_{n}_{s.index}"] = (s.bone, [s.point])
        for i, (a, b) in enumerate(m.fibers):
            expected[f"MUS_fiber_{n}_{i}"] = (m.sites[a].bone, [m.sites[a].point, m.sites[b].point])
    for obj, (bone, pts) in expected.items():
        s = snap.get(obj)
        if s is None:
            out.append(Issue("error", "MUS_BLEND_MISSING", f"Falta el objeto '{obj}'"))
            continue
        if s["parent_bone"] != bone:
            out.append(Issue("error", "MUS_BLEND_PARENT", f"'{obj}' no esta emparentado a '{bone}'"))
        for p, q in zip(pts, s["points"]):
            if length(sub(p, tuple(q))) > BLEND_TOL:
                out.append(Issue("error", "MUS_BLEND_POSITION", f"'{obj}' desplazado respecto al modelo"))
    extra = set(snap) - set(expected)
    if extra:
        out.append(Issue("error", "MUS_BLEND_EXTRA", f"Objetos musculares no esperados: {sorted(extra)[:5]}"))
    return out
