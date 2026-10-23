"""Carga y validacion de esquema de la configuracion versionada (config/*.json).

Los datos del modelo (longitudes, jerarquia, ejes, limites, pose) viven en JSON y se
convierten aqui en dataclasses inmutables. Nada de esto depende de Blender.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 2
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"

ATTACH_MODES = ("origin", "parent_head", "parent_tail")
LOCAL_AXES = ("x", "y", "z")
POSITIVE_MOTIONS = ("anterior", "posterior", "superior", "inferior", "lateral", "medial", "left", "right", "axial")


class ConfigError(ValueError):
    """Configuracion invalida o inconsistente."""


@dataclass(frozen=True)
class BoneDef:
    name: str
    parent: str | None
    attach: str
    offset_h: tuple[float, float, float]
    direction: tuple[float, float, float]
    length_key: str
    mirror: bool
    frame_x_hint: tuple[float, float, float]


@dataclass(frozen=True)
class DofDef:
    name: str
    axis: str  # eje local del hueso: "x" | "y" | "z"
    sign: int  # 1 | -1
    min_deg: float
    max_deg: float
    positive_motion: str
    description: str


@dataclass(frozen=True)
class JointDef:
    name: str
    bone: str
    mirror: bool
    dofs: tuple[DofDef, ...]


@dataclass(frozen=True)
class PoseDef:
    name: str
    rotations: dict  # clave de articulacion ("shoulder" o "shoulder.L") -> {dof: grados}


@dataclass(frozen=True)
class SkeletonConfig:
    height_m: float
    ankle_height_fraction: float
    lengths: dict  # fraccion de la altura por length_key
    bone_defs: tuple[BoneDef, ...]
    joint_defs: tuple[JointDef, ...]
    pose: PoseDef
    signature: str  # sha256 de los datos del ESQUELETO NEUTRO (sin la pose)
    pose_signature: str  # sha256 de la pose


def _read_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as fh:  # tolera BOM (Bloc de notas de Windows)
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"No existe el archivo de configuracion: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON invalido en {path}: {exc}") from exc
    version = data.get("schema_version")
    if version == 1:
        raise ConfigError(
            f"{path.name}: schema_version 1 (v0.1) ya no es soportado. Esta version usa schema_version "
            f"{SCHEMA_VERSION} (esqueleto neutro + pose A separada). Para usar la v0.1: git checkout v0.1.0"
        )
    if version != SCHEMA_VERSION:
        raise ConfigError(f"{path.name}: schema_version {version!r} no soportado (se esperaba {SCHEMA_VERSION})")
    return data


def _vec3(value, where: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ConfigError(f"{where}: se esperaba [x, y, z], se obtuvo {value!r}")
    try:
        out = tuple(float(c) for c in value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{where}: componentes no numericos {value!r}") from exc
    if not all(math.isfinite(c) for c in out):
        raise ConfigError(f"{where}: componentes no finitos {value!r}")
    return out  # type: ignore[return-value]


def _finite(value, where: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{where}: valor no numerico {value!r}") from exc
    if not math.isfinite(out):
        raise ConfigError(f"{where}: valor no finito {value!r}")
    return out


def _require(d: dict, key: str, where: str):
    if key not in d:
        raise ConfigError(f"{where}: falta la clave '{key}'")
    return d[key]


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def load_config(
    config_dir: Path | str | None = None,
    height_m: float | None = None,
    length_overrides: dict | None = None,
    pose_overrides: dict | None = None,
) -> SkeletonConfig:
    """Lee config/*.json. `height_m` y `length_overrides` (fracciones) sustituyen valores del
    esqueleto neutro; `pose_overrides` ({"shoulder.abduction": 35.0}) sustituye angulos de la pose."""
    cdir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    prop = _read_json(cdir / "proportions.json")
    skel = _read_json(cdir / "skeleton_definition.json")
    jnt = _read_json(cdir / "joints.json")
    pose_raw = _read_json(cdir / "pose_a.json")

    height = _finite(height_m if height_m is not None else _require(prop, "reference_height_m", "proportions"), "altura")
    if height <= 0:
        raise ConfigError(f"La altura debe ser positiva y finita (recibido {height!r})")

    stance = _require(prop, "stance", "proportions")
    ankle_h = _finite(_require(stance, "ankle_height_fraction", "proportions.stance"), "ankle_height_fraction")
    if ankle_h <= 0:
        raise ConfigError(f"ankle_height_fraction debe ser positivo (recibido {ankle_h!r})")

    lengths = {k: _finite(v, f"proportions.lengths[{k}]") for k, v in _require(prop, "lengths_fraction_of_height", "proportions").items()}
    for key, val in (length_overrides or {}).items():
        if key not in lengths:
            raise ConfigError(f"Override para longitud desconocida '{key}'. Validas: {sorted(lengths)}")
        lengths[key] = _finite(val, f"override de longitud '{key}'")

    bone_defs = []
    for i, raw in enumerate(_require(skel, "bones", "skeleton_definition")):
        where = f"skeleton_definition.bones[{i}]"
        attach = _require(raw, "attach", where)
        if attach not in ATTACH_MODES:
            raise ConfigError(f"{where}: attach '{attach}' invalido (validos: {ATTACH_MODES})")
        bone_defs.append(
            BoneDef(
                name=_require(raw, "name", where),
                parent=raw.get("parent"),
                attach=attach,
                offset_h=_vec3(_require(raw, "offset_h", where), f"{where}.offset_h"),
                direction=_vec3(_require(raw, "direction", where), f"{where}.direction"),
                length_key=_require(raw, "length_key", where),
                mirror=bool(_require(raw, "mirror", where)),
                frame_x_hint=_vec3(raw.get("frame_x_hint", [1, 0, 0]), f"{where}.frame_x_hint"),
            )
        )

    joint_defs = []
    for i, raw in enumerate(_require(jnt, "joints", "joints")):
        where = f"joints.joints[{i}]"
        dofs = []
        for j, d in enumerate(_require(raw, "dofs", where)):
            dw = f"{where}.dofs[{j}]"
            axis = _require(d, "axis", dw)
            if axis not in LOCAL_AXES:
                raise ConfigError(f"{dw}: axis '{axis}' invalido (validos: {LOCAL_AXES})")
            sign = _require(d, "sign", dw)
            if sign not in (1, -1):
                raise ConfigError(f"{dw}: sign debe ser 1 o -1 (recibido {sign!r})")
            motion = _require(d, "positive_motion", dw)
            if motion not in POSITIVE_MOTIONS:
                raise ConfigError(f"{dw}: positive_motion '{motion}' invalido (validos: {POSITIVE_MOTIONS})")
            dofs.append(
                DofDef(
                    name=_require(d, "name", dw),
                    axis=axis,
                    sign=int(sign),
                    min_deg=_finite(_require(d, "min_deg", dw), f"{dw}.min_deg"),
                    max_deg=_finite(_require(d, "max_deg", dw), f"{dw}.max_deg"),
                    positive_motion=motion,
                    description=d.get("description", ""),
                )
            )
        joint_defs.append(
            JointDef(
                name=_require(raw, "name", where),
                bone=_require(raw, "bone", where),
                mirror=bool(_require(raw, "mirror", where)),
                dofs=tuple(dofs),
            )
        )

    rotations = {
        str(k): {str(dof): _finite(deg, f"pose_a.rotations_deg[{k}][{dof}]") for dof, deg in dict(v).items()}
        for k, v in _require(pose_raw, "rotations_deg", "pose_a").items()
    }
    for key, val in (pose_overrides or {}).items():
        joint, _, dof = str(key).rpartition(".")
        if not joint or not dof:
            raise ConfigError(f"Override de pose '{key}' invalido: usa articulacion.dof (p. ej. shoulder.abduction)")
        rotations.setdefault(joint, {})[dof] = _finite(val, f"override de pose '{key}'")
    pose = PoseDef(_require(pose_raw, "name", "pose_a"), rotations)

    neutral = {
        "height_m": height,
        "ankle_height_fraction": ankle_h,
        "lengths": lengths,
        "skeleton": skel,
        "joints": jnt,
    }
    return SkeletonConfig(
        height, ankle_h, lengths, tuple(bone_defs), tuple(joint_defs), pose,
        signature=_digest(neutral),
        pose_signature=_digest({"name": pose.name, "rotations": rotations}),
    )
