"""Articulaciones: pivotes, ejes de rotacion y limites configurables (Python puro).

Cada eje es un eje LOCAL del hueso (columna de su marco ortonormal) con un signo, por lo
que es perpendicular a los demas ejes del hueso y a su eje largo por construccion.
Los angulos se miden desde el esqueleto NEUTRO. Los limites son APROXIMACIONES
CONFIGURABLES de un esqueleto de referencia, no limites medicos universales.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import ConfigError
from .geometry import Vec3, dot, mirror_axis, scale

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


@dataclass(frozen=True)
class Dof:
    """Un grado de libertad. Angulo positivo = regla de la mano derecha sobre `axis`."""

    name: str
    axis: Vec3  # unitario, espacio del modelo, esqueleto neutro
    axis_local: str  # "x" | "y" | "z" del marco del hueso
    axis_sign: int  # +1 si `axis` = columna del marco, -1 si es su opuesta
    min_deg: float
    max_deg: float
    positive_motion: str
    description: str = ""


@dataclass(frozen=True)
class Joint:
    name: str  # p. ej. "hip.L"
    bone: str  # hueso hijo que gira; el pivote es su cabeza (en el neutro)
    parent_bone: str | None
    pivot: Vec3
    dofs: tuple[Dof, ...]


def build_joints(joint_defs, bones: dict) -> dict:
    """Resuelve JointDef (en dos lados si mirror) a Joint con pivotes y ejes concretos.

    Los ejes se definen para el lado izquierdo (o el hueso central). El lado derecho usa el
    pseudovector espejo del eje izquierdo, que coincide (salvo signo) con una columna del
    marco derecho porque F_R = espejo(F_L)."""
    joints: dict[str, Joint] = {}
    for jd in joint_defs:
        sides = ("L", "R") if jd.mirror else (None,)
        for side in sides:
            bone_name = f"{jd.bone}.{side}" if side else jd.bone
            if bone_name not in bones:
                raise ConfigError(f"Articulacion '{jd.name}': el hueso '{bone_name}' no existe")
            bone = bones[bone_name]
            ref = bones[f"{jd.bone}.L"] if jd.mirror else bone
            dofs = []
            for d in jd.dofs:
                axis = scale(ref.frame[_AXIS_INDEX[d.axis]], float(d.sign))
                if side == "R":
                    axis = mirror_axis(axis)
                column = bone.frame[_AXIS_INDEX[d.axis]]
                sign = 1 if dot(axis, column) >= 0 else -1
                dofs.append(Dof(d.name, axis, d.axis, sign, d.min_deg, d.max_deg, d.positive_motion, d.description))
            jname = f"{jd.name}.{side}" if side else jd.name
            joints[jname] = Joint(jname, bone_name, bone.parent, bone.head, tuple(dofs))
    return joints
