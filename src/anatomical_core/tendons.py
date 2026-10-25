"""Capa de TENDONES (rama muscle-model; Python puro, sin bpy). Una unidad musculo-tendinosa es una linea que va de su origen oseo, por
las vias oseas que la guian (surcos, retinaculos, maleolos), a su insercion osea. Los extremos tendinosos son el tramo de esa linea
junto al origen y/o la insercion; el resto es el vientre muscular.

Todos los anclajes (origen, vias e insercion) son puntos de la superficie de un hueso (< 12 mm, como los hitos y los ligamentos) y nacen de un
hito oseo del modelo oseo (`landmark`) o de un punto de un hueso. La unica cifra que no es anatomica es la LONGITUD del tendon: no se mide en
este modelo, asi que se usa una convencion visual en tres clases (corto, medio, largo; ver `CLASSES`), declarada como tal en los datos.

Sitio: {"landmark": nombre} o {"bone": hueso, "point": punto}, con "structure" y, opcional, "offset_h" (fraccion de la altura).
Unidad: {"name", "mirror", "muscles", "origin", "via": [...], "insertion", "origin_tendon", "insertion_tendon", "sources", "notes"}."""
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

TENDONS_DIR = PROJECT_ROOT / "config" / "muscles"
FILES = ("tendons_trunk_head", "tendons_upper_limb", "tendons_lower_limb")
CLASSES = {"corto": 0.10, "medio": 0.25, "largo": 0.45}  # fraccion de la longitud de la unidad: CONVENCION VISUAL, no medida
MIN_BELLY = 0.20  # el vientre muscular ocupa al menos el 20 % de la unidad
SITE_TOL_M = 0.012


@dataclass(frozen=True)
class TendonSite:
    kind: str  # origin | via | insertion
    bone: str
    point: Vec3
    structure: str
    landmark: str | None


@dataclass(frozen=True)
class Tendon:
    name: str
    muscles: tuple
    sites: tuple  # origen, vias..., insercion
    origin_class: str | None
    insertion_class: str | None
    sources: tuple
    notes: str
    region: str
    deform: bool = False  # True: en Blender cada nodo sigue a su hueso (tubos deformados por la armadura); False: rigidos, emparentados al hueso del extremo
    avoid: tuple = ()  # nombres de las `BoneSurface` que la trayectoria no puede atravesar

    @property
    def path(self) -> tuple:
        return tuple(s.point for s in self.sites)

    def node_weights(self, point: Vec3) -> tuple:
        """Pesos ((hueso, peso), ...) de un punto del recorrido: si esta en el tramo entre dos sitios, interpolacion lineal entre los huesos de sus
        extremos (es lo que hace la mezcla lineal de la armadura y reproduce la recta entre los nodos posados)."""
        best, bi = float("inf"), 0
        for i, (a, b) in enumerate(zip(self.path, self.path[1:])):
            seg = sub(b, a)
            ln2 = seg[0] ** 2 + seg[1] ** 2 + seg[2] ** 2
            u = 0.0 if ln2 < 1e-24 else max(0.0, min(1.0, sum((point[k] - a[k]) * seg[k] for k in range(3)) / ln2))
            d = length(sub(point, add(a, scale(seg, u))))
            if d < best - 1e-12:
                best, bi, bu = d, i, u
        a_bone, b_bone = self.sites[bi].bone, self.sites[bi + 1].bone
        if a_bone == b_bone:
            return ((a_bone, 1.0),)
        return ((a_bone, 1.0 - bu), (b_bone, bu))

    @property
    def total_length(self) -> float:
        p = self.path
        return sum(length(sub(b, a)) for a, b in zip(p, p[1:]))

    def _cut(self, s0: float, s1: float) -> tuple:
        """Poligonal del trayecto entre las distancias s0 y s1 medidas desde el origen."""
        p, out, acc = self.path, [], 0.0
        for a, b in zip(p, p[1:]):
            seg = length(sub(b, a))
            lo, hi = max(s0, acc), min(s1, acc + seg)
            if hi > lo + 1e-12:
                u0, u1 = (lo - acc) / seg, (hi - acc) / seg
                pa, pb = add(a, scale(sub(b, a), u0)), add(a, scale(sub(b, a), u1))
                if not out or length(sub(out[-1], pa)) > 1e-12:
                    out.append(pa)
                out.append(pb)
            acc += seg
        return tuple(out)

    @property
    def origin_tendon(self) -> tuple:
        """Poligonal del tendon de origen (origen -> union miotendinosa), vacia si no tiene."""
        return self._cut(0.0, CLASSES[self.origin_class] * self.total_length) if self.origin_class else ()

    @property
    def insertion_tendon(self) -> tuple:
        """Poligonal del tendon de insercion (union miotendinosa -> insercion), vacia si no tiene."""
        if not self.insertion_class:
            return ()
        total = self.total_length
        return self._cut((1.0 - CLASSES[self.insertion_class]) * total, total)

    @property
    def belly(self) -> tuple:
        """Poligonal del vientre muscular entre las dos uniones miotendinosas."""
        total = self.total_length
        s0 = CLASSES[self.origin_class] * total if self.origin_class else 0.0
        s1 = (1.0 - CLASSES[self.insertion_class]) * total if self.insertion_class else total
        return self._cut(s0, s1)


@dataclass(frozen=True)
class TendonModel:
    sources: dict
    tendons: dict
    height_m: float

    def signature(self) -> str:
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        payload = {n: [[s.kind, s.bone, r(s.point)] for s in t.sites] + [t.origin_class, t.insertion_class] for n, t in sorted(self.tendons.items())}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def load_tendon_data(tendons_dir: Path | str | None = None) -> list:
    d = Path(tendons_dir) if tendons_dir else TENDONS_DIR
    return [_read_json(d / f"{f}.json") for f in FILES if (d / f"{f}.json").exists()]


def _site(raw: dict, kind: str, w: str, base: SkeletonModel, anat: AnatomyModel, art: ArticulationModel) -> TendonSite:
    if "landmark" in raw:
        lm = art.attachments.get(str(raw["landmark"]))
        if lm is None:
            raise ConfigError(f"{w}: el hito oseo '{raw['landmark']}' no existe en el modelo oseo")
        bone, point, landmark = lm.bone, lm.point, lm.name
    else:
        bone = str(raw["bone"])
        if bone not in anat.bones and bone not in base.bones:
            raise ConfigError(f"{w}: hueso inexistente '{bone}'")
        point, landmark = _eval(_point_spec(raw["point"], f"{w}.point"), base, anat.bones), None
    point = add(point, scale(_vec3(raw.get("offset_h", [0, 0, 0]), f"{w}.offset_h"), base.height_m))
    return TendonSite(kind, bone, point, str(raw.get("structure", "")), landmark)


def build_tendons(base: SkeletonModel, anat: AnatomyModel, art: ArticulationModel, data_list: list) -> TendonModel:
    sources, tendons = {}, {}
    for data in data_list:
        region = str(data.get("region", "tendons"))
        for key, s in data.get("sources", {}).items():
            if key in sources and sources[key] != s:
                raise ConfigError(f"Fuente de tendones '{key}' definida dos veces con datos distintos")
            sources[key] = s
        for i, u in enumerate(data.get("tendons", [])):
            w = f"{region}.tendons[{i}]"
            name = str(u["name"])
            mirror = bool(u.get("mirror", False))
            if mirror and not name.endswith(".L"):
                raise ConfigError(f"{w}: una unidad con mirror debe llamarse con sufijo .L")
            for oc in (u.get("origin_tendon"), u.get("insertion_tendon")):
                if oc is not None and oc not in CLASSES:
                    raise ConfigError(f"{w}: clase de tendon desconocida '{oc}' (usa {sorted(CLASSES)})")
            left = None
            for side in (("L", "R") if mirror else (None,)):
                tname = _swap_side(name, side or "L")
                if tname in tendons:
                    raise ConfigError(f"Tendon duplicado '{tname}'")
                if side == "R" and left is not None:
                    sites = tuple(TendonSite(s.kind, _swap_side(s.bone, "R"), mirror_point(s.point), s.structure, _swap_side(s.landmark, "R") if s.landmark else None)
                                  for s in left.sites)
                else:
                    raws = [("origin", u["origin"])] + [("via", v) for v in u.get("via", [])] + [("insertion", u["insertion"])]
                    sites = tuple(_site(r, k, f"{w}.{k}", base, anat, art) for k, r in raws)
                t = Tendon(tname, tuple(u.get("muscles", ())), sites, u.get("origin_tendon"), u.get("insertion_tendon"), tuple(u.get("sources", ())),
                           str(u.get("notes", "")), region, bool(u.get("deform", False)), tuple(_swap_side(x, side or "L") for x in u.get("avoid", [])))
                if side != "R":
                    left = t
                tendons[tname] = t
    return TendonModel(sources, tendons, base.height_m)


def validate_tendons(base: SkeletonModel, anat: AnatomyModel, art: ArticulationModel, model: TendonModel) -> list:
    """Anclajes sobre el hueso (< 12 mm), tendones con longitud real y vientre suficiente, fuentes validas y simetria."""
    from .validation import FRAME_TOL, Issue

    out = []
    tol = SITE_TOL_M * model.height_m / 1.75
    for key, s in model.sources.items():
        if not str(s.get("url", "")).startswith("https://") or s.get("reliability") not in ("alta", "media", "baja"):
            out.append(Issue("error", "TEN_SOURCE", f"Fuente de tendones '{key}' invalida"))
    weak = {k for k, s in model.sources.items() if s.get("reliability") == "baja"}
    for n, t in model.tendons.items():
        if not t.muscles:
            out.append(Issue("error", "TEN_MUSCLES", f"'{n}' no dice a que musculo(s) pertenece"))
        if not (t.origin_class or t.insertion_class):
            out.append(Issue("error", "TEN_NO_TENDON", f"'{n}' no tiene ningun extremo tendinoso"))
        for k in t.sources:
            if k not in model.sources:
                out.append(Issue("error", "TEN_SOURCE_UNKNOWN", f"'{n}' cita la fuente desconocida '{k}'"))
        if (not t.sources or set(t.sources) <= weak) and "verificar" not in t.notes.lower():
            out.append(Issue("error", "TEN_WEAK_NOTE", f"'{n}' se apoya en fuentes debiles o ninguna y no dice 'verificar'"))
        for s in t.sites:
            if s.bone not in anat.bones and s.bone not in base.bones:
                out.append(Issue("error", "TEN_BONE_UNKNOWN", f"'{n}' {s.kind}: hueso inexistente '{s.bone}'"))
                continue
            d = bone_distance(s.point, s.bone, base, anat, art.surfaces)
            if d > tol:
                out.append(Issue("error", "TEN_SITE_OFF_BONE", f"'{n}' {s.kind}: a {d * 1000:.1f} mm de la superficie de '{s.bone}' (maximo {tol * 1000:.1f})"))
        total = t.total_length
        frac = (CLASSES[t.origin_class] if t.origin_class else 0.0) + (CLASSES[t.insertion_class] if t.insertion_class else 0.0)
        if total < 0.02 * model.height_m / 1.75:
            out.append(Issue("error", "TEN_TOO_SHORT", f"'{n}' mide solo {total * 1000:.1f} mm"))
        if 1.0 - frac < MIN_BELLY:
            out.append(Issue("error", "TEN_NO_BELLY", f"'{n}': los tendones ocupan {frac:.0%} de la unidad (el vientre debe quedar >= {MIN_BELLY:.0%})"))
        if art.surfaces and t.deform and t.avoid and all(a in art.surfaces for a in t.avoid):  # en reposo ninguna poligonal con envoltura atraviesa un obstaculo
            from . import ligament_paths as _lp

            pts = [p for _, p in _lp.tendon_nodes(t)]
            samples = [add(a, scale(sub(b, a), i / _lp.PATH_SAMPLES)) for a, b in zip(pts, pts[1:]) for i in range(_lp.PATH_SAMPLES + 1)]
            clear = min(art.surfaces[a].signed_distance(p) for a in t.avoid for p in samples)
            if clear < -_lp.PENETRATION_TOL_M * model.height_m / 1.75:
                out.append(Issue("error", "TEN_PENETRATES", f"'{n}': en reposo atraviesa el hueso {-clear * 1000:.1f} mm"))
        for a in t.avoid:
            if a not in art.surfaces:
                out.append(Issue("error", "TEN_AVOID_UNKNOWN", f"'{n}' evita la superficie desconocida '{a}'"))
        if t.deform and not t.avoid:
            out.append(Issue("error", "TEN_AVOID_EMPTY", f"'{n}' tiene envoltura (deform) y no dice que superficies evita"))
        if t.deform and len({s.bone for s in t.sites}) < 2:
            out.append(Issue("error", "TEN_DEFORM_USELESS", f"'{n}': deform con todos los sitios en el mismo hueso"))
        right = n[:-2] + ".R" if n.endswith(".L") else None
        if right and right in model.tendons:
            for a, b in zip(t.sites, model.tendons[right].sites):
                if length(sub(mirror_point(a.point), b.point)) > FRAME_TOL * 10:
                    out.append(Issue("error", "TEN_ASYMMETRIC", f"'{n}' no es simetrico respecto a su .R"))
    return out


def validate_tendon_poses(base: SkeletonModel, anat: AnatomyModel, art: ArticulationModel, model: TendonModel, sides=("L", "R")) -> list:
    """Barrido de cadera y rodilla (ligament_paths.LEG_SWEEP): las unidades `deform` no atraviesan ni el femur (cabeza, cuello, trocanter, diafisis,
    condilo) ni la rama del pubis, ni cortan la lamina del ilion, en ninguna pose. Los nodos viajan con sus huesos por construccion."""
    from . import ligament_paths as lp
    from .validation import Issue

    out = []
    tol = lp.PENETRATION_TOL_M * model.height_m / 1.75
    for side in sides:
        units = [t for t in model.tendons.values() if t.deform and t.name.endswith(f".{side}")]
        if not units:
            continue
        plates = [(b, lp.plate_triangles(anat, b)) for b in (f"ilium.{side}",) if b in anat.bones]
        for pose_name, posed in lp.leg_sweep_poses(base, side):
            surfaces = {s.name: s for s in lp.posed_surfaces(art, base, anat, posed)}
            for t in units:
                path = lp.posed_nodes(lp.tendon_nodes(t), base, anat, posed)
                clear = lp.path_clearance(path, [surfaces[a] for a in t.avoid])
                if clear < -tol:
                    out.append(Issue("error", "TEN_PENETRATES", f"'{t.name}' atraviesa el hueso {-clear * 1000:.1f} mm en la pose '{pose_name}'"))
                for bone, tris in plates:
                    pb = posed.bones[lp.rig_bone(bone, base, anat)]
                    if lp.plate_crossings(path, [tuple(pb.apply(p) for p in tri) for tri in tris]):
                        out.append(Issue("error", "TEN_CROSSES_PLATE", f"'{t.name}' atraviesa la lamina de '{bone}' en la pose '{pose_name}'"))
    return out


def validate_tendons_snapshot(model: TendonModel, snap: dict) -> list:
    """Compara los tubos leidos de Blender con el modelo (posicion y hueso padre)."""
    from .validation import BLEND_TOL, Issue

    out, expected = [], {}
    for n, t in model.tendons.items():
        if t.origin_class:
            expected[f"TEN_origin_{n}"] = (None if t.deform else t.sites[0].bone, t.origin_tendon)
        if t.insertion_class:
            expected[f"TEN_insertion_{n}"] = (None if t.deform else t.sites[-1].bone, t.insertion_tendon)
        expected[f"TEN_belly_{n}"] = (None if t.deform else t.sites[0].bone, t.belly)
    for obj, (bone, pts) in expected.items():
        s = snap.get(obj)
        if s is None:
            out.append(Issue("error", "TEN_BLEND_MISSING", f"Falta el objeto '{obj}'"))
            continue
        if s["parent_bone"] != bone:
            out.append(Issue("error", "TEN_BLEND_PARENT", f"'{obj}' no esta emparentado a '{bone}'"))
        for p, q in zip((pts[0], pts[-1]), s["points"]):
            if length(sub(p, tuple(q))) > BLEND_TOL:
                out.append(Issue("error", "TEN_BLEND_POSITION", f"'{obj}' desplazado respecto al modelo"))
    extra = set(snap) - set(expected)
    if extra:
        out.append(Issue("error", "TEN_BLEND_EXTRA", f"Objetos de tendon no esperados: {sorted(extra)[:5]}"))
    return out
