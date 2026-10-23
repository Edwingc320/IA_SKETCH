"""Carga y validacion de esquema de la configuracion versionada (config/*.json).

Los datos del modelo (longitudes, jerarquia, ejes, limites) viven en JSON y se
convierten aqui en dataclasses inmutables. Nada de esto depende de Blender.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"

ATTACH_MODES = ("origin", "parent_head", "parent_tail")


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


@dataclass(frozen=True)
class DofDef:
    name: str
    axis: tuple[float, float, float] | None  # None = eje largo del hueso ("long")
    min_deg: float
    max_deg: float
    description: str


@dataclass(frozen=True)
class JointDef:
    name: str
    bone: str
    mirror: bool
    dofs: tuple[DofDef, ...]


@dataclass(frozen=True)
class SkeletonConfig:
    height_m: float
    lengths: dict  # fraccion de la altura por length_key
    bone_defs: tuple[BoneDef, ...]
    joint_defs: tuple[JointDef, ...]
    signature: str  # sha256 de los datos efectivos (reproducibilidad)


def _read_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as fh:  # tolera BOM (Bloc de notas de Windows)
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"No existe el archivo de configuracion: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON invalido en {path}: {exc}") from exc
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ConfigError(
            f"{path.name}: schema_version {data.get('schema_version')!r} no soportado "
            f"(se esperaba {SCHEMA_VERSION})"
        )
    return data


def _vec3(value, where: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ConfigError(f"{where}: se esperaba [x, y, z], se obtuvo {value!r}")
    try:
        out = tuple(float(c) for c in value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{where}: componentes no numericos {value!r}") from exc
    return out  # type: ignore[return-value]


def _require(d: dict, key: str, where: str):
    if key not in d:
        raise ConfigError(f"{where}: falta la clave '{key}'")
    return d[key]


def load_config(
    config_dir: Path | str | None = None,
    height_m: float | None = None,
    length_overrides: dict | None = None,
) -> SkeletonConfig:
    """Lee config/*.json. `height_m` y `length_overrides` (fracciones) sustituyen valores."""
    cdir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    prop = _read_json(cdir / "proportions.json")
    skel = _read_json(cdir / "skeleton_definition.json")
    jnt = _read_json(cdir / "joints.json")

    height = float(height_m if height_m is not None else _require(prop, "reference_height_m", "proportions"))
    if not math.isfinite(height) or height <= 0:
        raise ConfigError(f"La altura debe ser positiva y finita (recibido {height!r})")

    lengths = dict(_require(prop, "lengths_fraction_of_height", "proportions"))
    for key, val in (length_overrides or {}).items():
        if key not in lengths:
            raise ConfigError(f"Override para longitud desconocida '{key}'. Validas: {sorted(lengths)}")
        lengths[key] = float(val)

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
            )
        )

    joint_defs = []
    for i, raw in enumerate(_require(jnt, "joints", "joints")):
        where = f"joints.joints[{i}]"
        dofs = []
        for j, d in enumerate(_require(raw, "dofs", where)):
            dw = f"{where}.dofs[{j}]"
            axis = _require(d, "axis", dw)
            dofs.append(
                DofDef(
                    name=_require(d, "name", dw),
                    axis=None if axis == "long" else _vec3(axis, f"{dw}.axis"),
                    min_deg=float(_require(d, "min_deg", dw)),
                    max_deg=float(_require(d, "max_deg", dw)),
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

    effective = {
        "height_m": height,
        "lengths": lengths,
        "skeleton": skel,
        "joints": jnt,
    }
    signature = hashlib.sha256(json.dumps(effective, sort_keys=True).encode("utf-8")).hexdigest()
    return SkeletonConfig(height, lengths, tuple(bone_defs), tuple(joint_defs), signature)
