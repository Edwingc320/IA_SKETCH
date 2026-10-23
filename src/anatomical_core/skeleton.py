"""Modelo del esqueleto NEUTRO: huesos, jerarquia, marcos locales y pivotes.

Es un modelo de DATOS, independiente de Blender. Representa la posicion anatomica de
referencia (extremidades verticales); la pose A se aplica aparte (ver pose.py).
Estructura inicial aproximada, no anatomicamente exacta.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .config import ConfigError, SkeletonConfig
from .geometry import Frame, Vec3, add, frame_from_direction, mirror_frame, mirror_point, normalize, scale
from .joints import build_joints

# Huesos que debe contener todo esqueleto valido de esta fase.
REQUIRED_BONES = (
    "pelvis", "spine_lumbar", "spine_thoracic", "thorax", "neck", "head",
    "clavicle.L", "upper_arm.L", "forearm.L", "hand.L",
    "clavicle.R", "upper_arm.R", "forearm.R", "hand.R",
    "thigh.L", "shin.L", "foot.L",
    "thigh.R", "shin.R", "foot.R",
)


@dataclass(frozen=True)
class Bone:
    name: str
    parent: str | None
    head: Vec3
    tail: Vec3
    length: float  # longitud configurada (m); debe coincidir con |tail - head|
    frame: Frame  # ejes locales (x, y, z) en el espacio del modelo; y = direccion head->tail

    @property
    def side(self) -> str | None:
        if self.name.endswith(".L"):
            return "L"
        if self.name.endswith(".R"):
            return "R"
        return None


@dataclass(frozen=True)
class SkeletonModel:
    height_m: float
    ankle_height_m: float  # altura del pivote del tobillo sobre el suelo (apoyo del pie)
    bones: dict  # nombre -> Bone (orden: padres antes que hijos)
    joints: dict  # nombre -> Joint
    config_signature: str

    def signature(self) -> str:
        """Hash de los datos del esqueleto neutro (redondeados): comprueba reproducibilidad."""
        r = lambda v: [round(c, 6) for c in v]  # noqa: E731
        payload = {
            "ankle_height_m": round(self.ankle_height_m, 6),
            "bones": {
                n: [b.parent, r(b.head), r(b.tail), round(b.length, 6), [r(a) for a in b.frame]]
                for n, b in sorted(self.bones.items())
            },
            "joints": {
                n: [
                    j.bone,
                    r(j.pivot),
                    [[d.name, r(d.axis), d.axis_local, d.axis_sign, d.min_deg, d.max_deg, d.positive_motion] for d in j.dofs],
                ]
                for n, j in sorted(self.joints.items())
            },
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_model(config: SkeletonConfig) -> SkeletonModel:
    """Construye el esqueleto neutro. La pelvis queda centrada en x=y=0 y el pivote del tobillo
    a `ankle_height_fraction * altura` sobre el suelo (z=0)."""
    H = config.height_m
    defs = {d.name: d for d in config.bone_defs}
    if len(defs) != len(config.bone_defs):
        raise ConfigError("Nombres de hueso duplicados en skeleton_definition")

    bones: dict[str, Bone] = {}
    left_frames: dict[str, Frame] = {}
    for bd in config.bone_defs:
        if bd.length_key not in config.lengths:
            raise ConfigError(f"Hueso '{bd.name}': length_key '{bd.length_key}' no existe en proportions")
        sides = ("L", "R") if bd.mirror else (None,)
        for side in sides:
            name = f"{bd.name}.{side}" if side else bd.name
            if bd.parent is None:
                parent_name = None
            else:
                if bd.parent not in defs:
                    raise ConfigError(f"Hueso '{name}': padre '{bd.parent}' no definido")
                pdef = defs[bd.parent]
                if pdef.mirror:
                    if side is None:
                        raise ConfigError(f"Hueso central '{name}' no puede colgar de '{bd.parent}' (lateral)")
                    parent_name = f"{bd.parent}.{side}"
                else:
                    parent_name = bd.parent
                if parent_name not in bones:
                    raise ConfigError(
                        f"Hueso '{name}': el padre '{parent_name}' debe definirse antes (o hay un ciclo)"
                    )

            offset = scale(bd.offset_h, H)
            direction = normalize(bd.direction)
            # El marco se calcula una vez (lado izquierdo / hueso central) y el derecho es su espejo.
            if side == "R":
                offset, direction = mirror_point(offset), mirror_point(direction)
                frame = mirror_frame(left_frames[bd.name])
            else:
                try:
                    frame = frame_from_direction(direction, bd.frame_x_hint)
                except ValueError as exc:
                    raise ConfigError(f"Hueso '{name}': {exc}") from exc
                if side == "L":
                    left_frames[bd.name] = frame

            if bd.attach == "origin" or parent_name is None:
                anchor = (0.0, 0.0, 0.0)
            elif bd.attach == "parent_head":
                anchor = bones[parent_name].head
            else:
                anchor = bones[parent_name].tail
            length = config.lengths[bd.length_key] * H
            head = add(anchor, offset)
            bones[name] = Bone(name, parent_name, head, add(head, scale(direction, length)), length, frame)

    if "foot.L" not in bones:
        raise ConfigError("Falta el hueso 'foot.L': no se puede definir el apoyo del pie")
    ankle_h = config.ankle_height_fraction * H
    dz = ankle_h - bones["foot.L"].head[2]  # apoyar: tobillo a ankle_h sobre el suelo
    bones = {
        n: Bone(n, b.parent, (b.head[0], b.head[1], b.head[2] + dz), (b.tail[0], b.tail[1], b.tail[2] + dz), b.length, b.frame)
        for n, b in bones.items()
    }
    joints = build_joints(config.joint_defs, bones)
    return SkeletonModel(H, ankle_h, bones, joints, config.signature)
