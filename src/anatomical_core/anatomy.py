"""Nivel 1 (anatomia): huesos anatomicos construidos SOBRE la base (nivel 0) sin modificarla.

Python puro, sin bpy. La base (skeleton.SkeletonModel) es de solo lectura: este modulo la lee para
anclar cada hueso anatomico a puntos de la base (cabezas/colas de huesos) y nunca la modifica.

Cada hueso anatomico:
  * es hijo (directo o indirecto) de un hueso base;
  * define su cabeza y su cola como PUNTOS: un punto de un hueso ya construido ("pelvis.tail",
    "thigh.L.head"), o una interpolacion entre dos puntos, mas un desplazamiento opcional en
    unidades de altura H (ejes del modelo: +X izquierda, +Y atras, +Z arriba). Asi escala con las
    proporciones de la base y sigue a sus pivotes;
  * lleva `reference`: los nombres de config/reference que representa (trazabilidad);
  * `parent` es el padre en el RIG (el segmento que lo mueve: siempre la base o un hueso rigido de
    ella), y `anatomical_parent` la relacion anatomica/articular (p. ej. el humero cuelga
    anatomicamente de la escapula, pero en el rig lo mueve el segmento base upper_arm). Si no se
    indica, coincide con `parent`;
  * puede llevar un contorno (`outline`): geometria de referencia, solo visualizacion.
Los huesos con mirror=true se definen para el lado izquierdo; el derecho es su espejo exacto.
En este nivel los huesos son RIGIDOS respecto a su padre (sin articulaciones ni poses propias).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT, ConfigError, _read_json, _vec3
from .geometry import Frame, Vec3, add, frame_from_direction, length, mirror_frame, mirror_point, scale, sub
from .skeleton import SkeletonModel

REFERENCE_FILE = PROJECT_ROOT / "config" / "reference" / "human_skeleton_reference.json"
ANATOMY_DIR = PROJECT_ROOT / "config" / "anatomy"
# Orden de construccion del nivel 1: una region puede usar puntos de las anteriores.
REGION_ORDER = ("pelvic_girdle", "spine_head", "thoracic_cage", "hands_feet", "long_bones")  # costillas tras las vertebras
LAYER = "anatomy_L1"


# --- Referencia (config/reference) y normalizacion de nombres -------------------------------------
def _leaves(node) -> list:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [x for item in node for x in _leaves(item)]
    if isinstance(node, dict):
        return [x for v in node.values() for x in _leaves(v)]
    return []


def load_reference(path: Path | str | None = None) -> tuple:
    """Nombres de hueso del JSON de referencia, tal como estan escritos."""
    p = Path(path) if path else REFERENCE_FILE
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ConfigError(f"No existe la referencia de esqueleto: {p}") from exc
    return tuple(_leaves(data["bone_hierarchy"]))


def normalize_reference_name(name: str) -> str:
    """Reglas aprobadas: lado como sufijo final (.L/.R), 'little' en vez de 'pinky' y 'sternum_body'
    en vez del generico 'body'; 'sacrum_fused' y 'coccyx_fused' son 'sacrum' y 'coccyx'. El resto de nombres se conserva tal cual."""
    m = re.fullmatch(r"(.+)_([LR])_(\d+)", name)
    if m:
        name = f"{m.group(1)}_{m.group(3)}.{m.group(2)}"
    name = name.replace("pinky_", "little_")
    if name == "body":
        name = "sternum_body"
    if name in ("sacrum_fused", "coccyx_fused"):  # el hueso fusionado se llama simplemente sacrum / coccyx
        name = name.removesuffix("_fused")
    return name


# --- Configuracion ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PointSpec:
    at: str | None  # "hueso.head" | "hueso.tail"
    lerp: tuple | None  # ("a.head", "b.tail", t)
    offset_h: Vec3


@dataclass(frozen=True)
class AnatomyBoneDef:
    name: str
    parent: str
    mirror: bool
    region: str
    reference: tuple
    head: PointSpec
    tail: PointSpec
    frame_x_hint: Vec3
    outline: tuple  # PointSpec
    outline_closed: bool
    anatomical_parent: str


@dataclass(frozen=True)
class AnchorDef:
    point: str
    equals: str
    description: str


@dataclass(frozen=True)
class AnatomyConfig:
    regions: tuple  # regiones presentes, en orden de construccion
    bone_defs: tuple
    anchors: tuple
    reference_names: tuple  # nombres NORMALIZADOS de la referencia
    signature: str


def _point_spec(raw, where: str) -> PointSpec:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: se esperaba un punto {{'at': ...}} o {{'lerp': [...]}}")
    offset = _vec3(raw.get("offset_h", [0, 0, 0]), f"{where}.offset_h")
    if "at" in raw and "lerp" not in raw:
        return PointSpec(str(raw["at"]), None, offset)
    if "lerp" in raw and "at" not in raw:
        lp = raw["lerp"]
        if not (isinstance(lp, list) and len(lp) == 3):
            raise ConfigError(f"{where}.lerp: se esperaba [punto_a, punto_b, t]")
        return PointSpec(None, (str(lp[0]), str(lp[1]), float(lp[2])), offset)
    raise ConfigError(f"{where}: usa exactamente una de 'at' o 'lerp'")


def load_anatomy_config(anatomy_dir: Path | str | None = None, reference_path: Path | str | None = None) -> AnatomyConfig:
    adir = Path(anatomy_dir) if anatomy_dir else ANATOMY_DIR
    reference = tuple(normalize_reference_name(n) for n in load_reference(reference_path))
    regions, defs, anchors, raw_all = [], [], [], {}
    for region in REGION_ORDER:
        path = adir / f"{region}.json"
        if not path.exists():
            continue  # region pendiente
        data = _read_json(path)
        if data.get("region") != region:
            raise ConfigError(f"{path.name}: 'region' debe ser '{region}'")
        raw_all[region] = data
        regions.append(region)
        for i, b in enumerate(data.get("bones", [])):
            w = f"{path.name}.bones[{i}]"
            for key in ("name", "parent", "head", "tail", "reference"):
                if key not in b:
                    raise ConfigError(f"{w}: falta la clave '{key}'")
            defs.append(AnatomyBoneDef(
                name=str(b["name"]), parent=str(b["parent"]), mirror=bool(b.get("mirror", False)), region=region,
                reference=tuple(str(r) for r in b["reference"]),
                head=_point_spec(b["head"], f"{w}.head"), tail=_point_spec(b["tail"], f"{w}.tail"),
                frame_x_hint=_vec3(b.get("frame_x_hint", [1, 0, 0]), f"{w}.frame_x_hint"),
                outline=tuple(_point_spec(p, f"{w}.outline[{k}]") for k, p in enumerate(b.get("outline", []))),
                outline_closed=bool(b.get("outline_closed", True)),
                anatomical_parent=str(b.get("anatomical_parent", b["parent"])),
            ))
        for i, a in enumerate(data.get("anchors", [])):
            anchors.append(AnchorDef(str(a["point"]), str(a["equals"]), str(a.get("description", ""))))
    sig = hashlib.sha256(json.dumps(raw_all, sort_keys=True).encode("utf-8")).hexdigest()
    return AnatomyConfig(tuple(regions), tuple(defs), tuple(anchors), reference, sig)


# --- Modelo ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class AnatomyBone:
    name: str
    parent: str
    head: Vec3
    tail: Vec3
    length: float
    frame: Frame
    region: str
    reference: tuple
    outline: tuple  # puntos (Vec3) del contorno de referencia, en el neutro
    outline_closed: bool
    anatomical_parent: str | None = None  # relacion anatomica (None = igual que parent)

    @property
    def side(self) -> str | None:
        return "L" if self.name.endswith(".L") else "R" if self.name.endswith(".R") else None


@dataclass(frozen=True)
class AnatomyModel:
    base_signature: str  # firma de la base sobre la que se construyo
    height_m: float
    regions: tuple
    bones: dict  # nombre -> AnatomyBone, padres antes que hijos
    anchors: tuple  # (punto, igual_a, descripcion) ya expandidos a ambos lados
    reference_names: tuple
    config_signature: str

    def signature(self) -> str:
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        payload = {
            "base": self.base_signature,
            "bones": {n: [b.parent, r(b.head), r(b.tail), [r(a) for a in b.frame], list(b.reference), [r(p) for p in b.outline]]
                      + ([b.anatomical_parent] if b.anatomical_parent not in (None, b.parent) else [])
                      for n, b in sorted(self.bones.items())},
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _swap_side(text: str, side: str) -> str:
    """Cambia el sufijo .L por el del lado pedido en un nombre o referencia de punto."""
    if side != "R":
        return text
    return re.sub(r"\.L(?=\.|$)", ".R", text)


def resolve_point_ref(ref: str, base: SkeletonModel, built: dict) -> Vec3:
    name, _, which = ref.rpartition(".")
    if which not in ("head", "tail") or not name:
        raise ConfigError(f"Referencia de punto invalida '{ref}': usa hueso.head o hueso.tail")
    bone = built.get(name) or base.bones.get(name)
    if bone is None:
        raise ConfigError(f"Referencia de punto '{ref}': el hueso '{name}' no existe (o aun no se ha construido)")
    return bone.head if which == "head" else bone.tail


def _eval(spec: PointSpec, base: SkeletonModel, built: dict) -> Vec3:
    if spec.at is not None:
        p = resolve_point_ref(spec.at, base, built)
    else:
        a, b, t = spec.lerp
        pa, pb = resolve_point_ref(a, base, built), resolve_point_ref(b, base, built)
        p = add(pa, scale(sub(pb, pa), t))
    return add(p, scale(spec.offset_h, base.height_m))


def build_anatomy(base: SkeletonModel, cfg: AnatomyConfig) -> AnatomyModel:
    """Construye el nivel 1 sobre la base. No modifica `base` (sus dataclasses son inmutables)."""
    bones: dict[str, AnatomyBone] = {}
    for d in cfg.bone_defs:
        if d.name in base.bones:
            raise ConfigError(f"Hueso anatomico '{d.name}' choca con un hueso de la base")
        sides = ("L", "R") if d.mirror else (None,)
        if d.mirror and not d.name.endswith(".L"):
            raise ConfigError(f"Hueso con mirror '{d.name}' debe definirse con sufijo .L")
        left = None
        for side in sides:
            name = _swap_side(d.name, side or "L")
            if name in bones:
                raise ConfigError(f"Hueso anatomico duplicado '{name}'")
            parent = _swap_side(d.parent, side or "L")
            anat_parent = _swap_side(d.anatomical_parent, side or "L")
            reference = tuple(_swap_side(r, side or "L") for r in d.reference)
            if side == "R":
                b = left
                bone = AnatomyBone(name, parent, mirror_point(b.head), mirror_point(b.tail), b.length, mirror_frame(b.frame),
                                   d.region, reference, tuple(mirror_point(p) for p in b.outline), b.outline_closed, anat_parent)
            else:
                head, tail = _eval(d.head, base, bones), _eval(d.tail, base, bones)
                ln = length(sub(tail, head))
                if ln <= 1e-9:
                    raise ConfigError(f"Hueso anatomico '{name}' de longitud nula")
                try:
                    frame = frame_from_direction(sub(tail, head), d.frame_x_hint)
                except ValueError as exc:
                    raise ConfigError(f"Hueso anatomico '{name}': {exc}") from exc
                bone = AnatomyBone(name, parent, head, tail, ln, frame, d.region, reference, (), d.outline_closed, anat_parent)
                bones[name] = bone  # el contorno puede usar la cabeza/cola del propio hueso
                outline = tuple(_eval(p, base, bones) for p in d.outline)
                bone = AnatomyBone(name, parent, head, tail, ln, frame, d.region, reference, outline, d.outline_closed, anat_parent)
                left = bone
            bones[name] = bone
    anchors = []
    for a in cfg.anchors:
        anchors.append((a.point, a.equals, a.description))
        if ".L" in a.point or ".L" in a.equals:
            anchors.append((_swap_side(a.point, "R"), _swap_side(a.equals, "R"), a.description))
    return AnatomyModel(base.signature(), base.height_m, cfg.regions, bones, tuple(anchors), cfg.reference_names, cfg.signature)


def point_segment_distance(p: Vec3, a: Vec3, b: Vec3) -> float:
    ab = sub(b, a)
    den = sum(c * c for c in ab)
    t = 0.0 if den <= 0 else max(0.0, min(1.0, sum(x * y for x, y in zip(sub(p, a), ab)) / den))
    return length(sub(p, add(a, scale(ab, t))))


def scapula_rib_clearance(anat: AnatomyModel, side: str, samples: int = 12) -> float | None:
    """Distancia minima (m) entre la lamina de la escapula (triangulo glenoide - angulo superior -
    angulo inferior, muestreado) y los arcos costales (contornos de las costillas) de ese lado.
    None si falta la escapula o las costillas."""
    sc = anat.bones.get(f"scapula.{side}")
    ribs = [b for n, b in anat.bones.items() if n.startswith("rib_") and n.endswith(f".{side}")]
    if sc is None or not ribs or len(sc.outline) < 3:
        return None
    a, b, c = sc.head, sc.outline[2], sc.tail  # glenoide, angulo superior, angulo inferior
    pts = []
    for i in range(samples + 1):
        for j in range(samples + 1 - i):
            u, v = i / samples, j / samples
            w = 1.0 - u - v
            pts.append(tuple(w * x + u * y + v * z for x, y, z in zip(a, b, c)))
    segs = [(r.outline[i], r.outline[i + 1]) for r in ribs for i in range(len(r.outline) - 1)]
    return min(point_segment_distance(p, s0, s1) for p in pts for s0, s1 in segs)


def coverage(anat: AnatomyModel, base: SkeletonModel) -> dict:
    """Que nombres de la referencia estan representados: por un hueso anatomico, por un hueso de la
    base con el mismo nombre (p. ej. clavicle.L) o pendientes de una region futura."""
    implemented = {r: n for n, b in anat.bones.items() for r in b.reference}
    out = {"implemented": {}, "base": [], "pending": []}
    for r in anat.reference_names:
        if r in implemented:
            out["implemented"][r] = implemented[r]
        elif r in base.bones:
            out["base"].append(r)
        else:
            out["pending"].append(r)
    return out
