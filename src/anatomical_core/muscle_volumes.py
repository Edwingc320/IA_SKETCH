"""Volumen de los vientres musculares (rama muscle-model; Python puro, sin bpy).

Cada vientre (el tramo de la unidad musculo-tendinosa entre sus dos uniones miotendinosas, ver `tendons.py`) se rellena con un husillo:
una malla cerrada que sigue la poligonal del vientre, con seccion circular o elíptica y un perfil fusiforme (cero en los extremos, maximo hacia
el centro). El radio maximo se ajusta para que la malla tenga EXACTAMENTE el volumen declarado.

Volumen declarado, a la altura de referencia: o bien MEDIDO (fuente citada) o bien una CONVENCION VISUAL de orden de magnitud en cuatro clases
(pequeno, medio, grande, muy_grande) que no es una medida. Con `--height` todas las longitudes escalan con k = H / H_ref y el volumen con k^3
(escalado isometrico: las secciones escalan con k y la longitud con k); en un adulto real la relacion con la talla es mas debil (R2 ~ 0.64 en el
muslo, Handsfield 2014), asi que es una hipotesis declarada, no un dato."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT, ConfigError, _read_json
from .geometry import Vec3, add, cross, dot, length, normalize, scale, sub
from .tendons import TendonModel
from .volumes import euler_characteristic, signed_volume

VOLUMES_DIR = PROJECT_ROOT / "config" / "muscles"
FILE = "muscle_volumes"
MODEL_REFERENCE_HEIGHT_M = 1.75
KINDS = ("medido", "convencion")
RINGS, SIDES = 24, 12  # anillos a lo largo del vientre y vertices por anillo
PROFILE_EXPONENT = 0.7  # f(u) = sin(pi u)^0.7: redondeado en los extremos, vientre ancho


@dataclass(frozen=True)
class MuscleVolume:
    unit: str  # nombre de la unidad musculo-tendinosa (p. ej. "vastus_lateralis.L")
    volume_ref_cm3: float  # volumen a la altura de referencia (medido) o de la clase (convencion)
    reference_height_m: float
    kind: str  # medido | convencion
    size_class: str | None
    source: str | None
    aspect: float  # relacion ancho/grosor de la seccion (1 = circular; > 1 = aplanado: pectoral, dorsal ancho, trapecio...)
    notes: str

    def volume_m3(self, height_m: float) -> float:
        """Volumen a la altura dada: isometrico, V ~ (H / H_ref)^3."""
        return self.volume_ref_cm3 * 1e-6 * (height_m / self.reference_height_m) ** 3


@dataclass(frozen=True)
class VolumeModel:
    sources: dict
    classes: dict
    volumes: dict
    height_m: float

    def signature(self) -> str:
        return hashlib.sha256(json.dumps({n: [v.volume_ref_cm3, v.aspect, v.kind] for n, v in sorted(self.volumes.items())}, sort_keys=True).encode()).hexdigest()


def load_volume_data(volumes_dir: Path | str | None = None):
    p = Path(volumes_dir or VOLUMES_DIR) / f"{FILE}.json"
    return _read_json(p) if p.exists() else None


def build_volumes(tendon_model: TendonModel, data) -> VolumeModel:
    if not data:
        return VolumeModel({}, {}, {}, tendon_model.height_m)
    classes = {k: float(v) for k, v in data["size_classes_cm3"].items()}
    out = {}
    for i, m in enumerate(data.get("muscles", [])):
        w = f"muscle_volumes.muscles[{i}]"
        name = str(m["unit"])
        sides = ("L", "R") if m.get("mirror", True) else (None,)
        if m.get("kind") not in KINDS:
            raise ConfigError(f"{w}: 'kind' debe ser medido o convencion")
        if m["kind"] == "medido":
            if not (m.get("source") and m.get("volume_cm3") and m.get("reference_height_m")):
                raise ConfigError(f"{w}: un volumen medido necesita volume_cm3, reference_height_m y source")
            vol, ref_h, cls = float(m["volume_cm3"]), float(m["reference_height_m"]), None
        else:
            cls = str(m.get("size_class"))
            if cls not in classes:
                raise ConfigError(f"{w}: clase de tamano desconocida '{cls}' (usa {sorted(classes)})")
            vol, ref_h = classes[cls], MODEL_REFERENCE_HEIGHT_M
        aspect = float(m.get("aspect", 1.0))
        if not 1.0 <= aspect <= 6.0 or vol <= 0:
            raise ConfigError(f"{w}: aspect debe estar entre 1 y 6 y el volumen ser positivo")
        for s in sides:
            uname = name if s in (None, "L") else name[:-2] + ".R"
            if uname not in tendon_model.tendons:
                raise ConfigError(f"{w}: la unidad musculo-tendinosa '{uname}' no existe")
            if uname in out:
                raise ConfigError(f"Volumen duplicado para '{uname}'")
            out[uname] = MuscleVolume(uname, vol, ref_h, m["kind"], cls, m.get("source"), aspect, str(m.get("notes", "")))
    return VolumeModel(data.get("sources", {}), classes, out, tendon_model.height_m)


def _profile(u: float) -> float:
    return math.sin(math.pi * u) ** PROFILE_EXPONENT


def _point_at(path: list, cum: list, s: float) -> tuple:
    """Punto y tangente de la poligonal a la distancia s del inicio."""
    for k in range(len(path) - 1):
        if s <= cum[k + 1] + 1e-15 or k == len(path) - 2:
            seg = cum[k + 1] - cum[k]
            u = 0.0 if seg < 1e-15 else min(1.0, max(0.0, (s - cum[k]) / seg))
            return add(path[k], scale(sub(path[k + 1], path[k]), u)), normalize(sub(path[k + 1], path[k]))
    raise AssertionError


def _frame(direction: Vec3) -> tuple:
    """(eje del ancho, eje del grosor): el grosor mira lo mas posible a Y (antero-posterior) y el ancho completa el sistema."""
    ref = (0.0, 1.0, 0.0)
    if abs(dot(direction, ref)) > 0.95:
        ref = (0.0, 0.0, 1.0)
    thick = normalize(sub(ref, scale(direction, dot(ref, direction))))
    return normalize(cross(direction, thick)), thick


def belly_mesh(path: tuple, volume_m3: float, aspect: float = 1.0) -> tuple:
    """(vertices, caras) del husillo que rellena `path` con exactamente `volume_m3`."""
    pts = list(path)
    if len(pts) < 2:
        raise ConfigError("El vientre necesita al menos dos puntos")
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + length(sub(b, a)))
    total = cum[-1]
    if total < 1e-6:
        raise ConfigError("Vientre de longitud nula")

    def build(r_max: float) -> tuple:
        verts = []
        for i in range(1, RINGS):
            u = i / RINGS
            c, d = _point_at(pts, cum, u * total)
            wd, th = _frame(d)
            r = r_max * _profile(u)
            w, t = math.sqrt(aspect) * r, r / math.sqrt(aspect)
            for j in range(SIDES):
                ph = 2 * math.pi * j / SIDES
                verts.append(add(c, add(scale(wd, w * math.cos(ph)), scale(th, t * math.sin(ph)))))
        a0, a1 = _point_at(pts, cum, 0.0)[0], _point_at(pts, cum, total)[0]
        south, north = len(verts), len(verts) + 1
        verts += [a0, a1]
        faces = []
        for i in range(RINGS - 2):
            for j in range(SIDES):
                a, b = i * SIDES + j, i * SIDES + (j + 1) % SIDES
                faces.append((a, b, b + SIDES, a + SIDES))
        last = (RINGS - 2) * SIDES
        for j in range(SIDES):
            j2 = (j + 1) % SIDES
            faces.append((south, j2, j))
            faces.append((north, last + j, last + j2))
        if signed_volume(verts, faces) < 0:
            faces = [tuple(reversed(f)) for f in faces]
        return verts, faces

    # el volumen es proporcional a r_max^2: una pasada de calibracion ajusta el radio para que la malla tenga exactamente el volumen pedido
    v1, f1 = build(0.01)
    r_max = 0.01 * math.sqrt(volume_m3 / signed_volume(v1, f1))
    return build(r_max)


def mesh_for(tendon_model: TendonModel, vol: MuscleVolume) -> tuple:
    t = tendon_model.tendons[vol.unit]
    return belly_mesh(t.belly, vol.volume_m3(tendon_model.height_m), vol.aspect)


def validate_volumes(tendon_model: TendonModel, model: VolumeModel) -> list:
    """Volumen exacto, malla cerrada, fuentes y marca de convencion."""
    from .validation import Issue

    out = []
    for key, s in model.sources.items():
        if not str(s.get("url", "")).startswith("https://") or s.get("reliability") not in ("alta", "media", "baja"):
            out.append(Issue("error", "VOL_SOURCE", f"Fuente de volumen '{key}' invalida"))
    for n, v in model.volumes.items():
        if v.kind == "medido" and v.source not in model.sources:
            out.append(Issue("error", "VOL_SOURCE_UNKNOWN", f"'{n}' cita la fuente desconocida '{v.source}'"))
        if v.kind == "convencion" and "convencion" not in v.notes.lower():
            out.append(Issue("error", "VOL_CONVENTION_NOTE", f"'{n}' es una convencion visual y su nota no lo dice"))
        verts, faces = mesh_for(tendon_model, v)
        if euler_characteristic(verts, faces) != 2 or signed_volume(verts, faces) <= 0:
            out.append(Issue("error", "VOL_NOT_CLOSED", f"'{n}': la malla del vientre no es una superficie cerrada"))
        elif abs(signed_volume(verts, faces) - v.volume_m3(model.height_m)) > 1e-9 * max(1.0, v.volume_m3(model.height_m)) + 1e-12:
            out.append(Issue("error", "VOL_MISMATCH", f"'{n}': el volumen de la malla no coincide con el declarado"))
    return out


def validate_volumes_snapshot(tendon_model: TendonModel, model: VolumeModel, snap: dict) -> list:
    """Compara los objetos de volumen leidos de Blender (numero de vertices y caja envolvente) con la malla del modelo."""
    from .validation import BLEND_TOL, Issue

    out, expected = [], {}
    for n, v in model.volumes.items():
        verts, _ = mesh_for(tendon_model, v)
        expected[f"MUV_{n}"] = (tendon_model.tendons[n].sites[0].bone, verts)
    for obj, (bone, verts) in expected.items():
        s = snap.get(obj)
        if s is None:
            out.append(Issue("error", "VOL_BLEND_MISSING", f"Falta el objeto '{obj}'"))
            continue
        lo, hi = tuple(min(v[i] for v in verts) for i in range(3)), tuple(max(v[i] for v in verts) for i in range(3))
        if s["parent_bone"] != bone:
            out.append(Issue("error", "VOL_BLEND_PARENT", f"'{obj}' no esta emparentado a '{bone}'"))
        if s["n_verts"] != len(verts) or any(abs(a - b) > BLEND_TOL for a, b in zip(lo + hi, tuple(s["bbox"][0]) + tuple(s["bbox"][1]))):
            out.append(Issue("error", "VOL_BLEND_SHAPE", f"'{obj}': la malla del .blend no coincide con la del modelo"))
    extra = set(snap) - set(expected)
    if extra:
        out.append(Issue("error", "VOL_BLEND_EXTRA", f"Objetos de volumen no esperados: {sorted(extra)[:5]}"))
    return out
