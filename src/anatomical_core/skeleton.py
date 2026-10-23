"""Modelo de esqueleto: huesos, jerarquia y posiciones en pose de reposo (A-pose).

Es un modelo de DATOS, independiente de Blender. Estructura inicial aproximada,
no anatomicamente exacta.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .config import ConfigError, SkeletonConfig
from .geometry import Vec3, add, mirror_point, normalize, scale
from .joints import Joint, build_joints

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
    bones: dict  # nombre -> Bone (orden: padres antes que hijos)
    joints: dict  # nombre -> Joint
    config_signature: str

    def signature(self) -> str:
        """Hash de los datos del modelo (redondeados): sirve para comprobar reproducibilidad."""
        payload = {
            "bones": {
                n: [b.parent, [round(c, 6) for c in b.head], [round(c, 6) for c in b.tail], round(b.length, 6)]
                for n, b in sorted(self.bones.items())
            },
            "joints": {
                n: [
                    j.bone,
                    [round(c, 6) for c in j.pivot],
                    [[d.name, [round(c, 6) for c in d.axis], d.min_deg, d.max_deg] for d in j.dofs],
                ]
                for n, j in sorted(self.joints.items())
            },
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_model(config: SkeletonConfig) -> SkeletonModel:
    """Construye el modelo a partir de la configuracion. Los pies quedan apoyados en z=0
    y la pelvis centrada en x=y=0."""
    H = config.height_m
    defs = {d.name: d for d in config.bone_defs}
    if len(defs) != len(config.bone_defs):
        raise ConfigError("Nombres de hueso duplicados en skeleton_definition")

    bones: dict[str, Bone] = {}
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
            if side == "R":
                offset, direction = mirror_point(offset), mirror_point(direction)

            if bd.attach == "origin" or parent_name is None:
                anchor = (0.0, 0.0, 0.0)
            elif bd.attach == "parent_head":
                anchor = bones[parent_name].head
            else:
                anchor = bones[parent_name].tail
            length = config.lengths[bd.length_key] * H
            head = add(anchor, offset)
            bones[name] = Bone(name, parent_name, head, add(head, scale(direction, length)), length)

    # Apoyar el esqueleto en el suelo (z minimo = 0).
    min_z = min(min(b.head[2], b.tail[2]) for b in bones.values())
    bones = {
        n: Bone(n, b.parent, (b.head[0], b.head[1], b.head[2] - min_z), (b.tail[0], b.tail[1], b.tail[2] - min_z), b.length)
        for n, b in bones.items()
    }
    joints = build_joints(config.joint_defs, bones)
    return SkeletonModel(H, bones, joints, config.signature)
