"""Articulaciones: pivotes, ejes de rotacion y limites configurables (Python puro).

Los limites son APROXIMACIONES CONFIGURABLES de un esqueleto de referencia, no
limites medicos universales.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import ConfigError, JointDef
from .geometry import Vec3, mirror_axis, normalize, sub


@dataclass(frozen=True)
class Dof:
    """Un grado de libertad. Angulo positivo = regla de la mano derecha sobre `axis`."""

    name: str
    axis: Vec3  # unitario, en el espacio del modelo en reposo
    min_deg: float
    max_deg: float
    description: str = ""


@dataclass(frozen=True)
class Joint:
    name: str  # p. ej. "hip.L"
    bone: str  # hueso hijo que gira; el pivote es su cabeza
    parent_bone: str | None
    pivot: Vec3
    dofs: tuple[Dof, ...]


def build_joints(joint_defs, bones: dict) -> dict:
    """Resuelve JointDef (en dos lados si mirror) a Joint con pivotes y ejes concretos."""
    joints: dict[str, Joint] = {}
    for jd in joint_defs:
        sides = ("L", "R") if jd.mirror else (None,)
        for side in sides:
            bone_name = f"{jd.bone}.{side}" if side else jd.bone
            if bone_name not in bones:
                raise ConfigError(f"Articulacion '{jd.name}': el hueso '{bone_name}' no existe")
            bone = bones[bone_name]
            # Los ejes se definen para el lado izquierdo (o el hueso central).
            ref_name = f"{jd.bone}.L" if jd.mirror else jd.bone
            ref = bones[ref_name]
            dofs = []
            for d in jd.dofs:
                axis = normalize(sub(ref.tail, ref.head)) if d.axis is None else normalize(d.axis)
                if side == "R":
                    axis = mirror_axis(axis)
                dofs.append(Dof(d.name, axis, d.min_deg, d.max_deg, d.description))
            jname = f"{jd.name}.{side}" if side else jd.name
            joints[jname] = Joint(jname, bone_name, bone.parent, bone.head, tuple(dofs))
    return joints
