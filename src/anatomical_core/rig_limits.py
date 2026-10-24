"""Restricciones de rotacion del rig (Python puro, sin bpy): de joints.json salen los limites Euler locales de cada
pose bone y de config/rig_couplings.json los limites que dependen de otro angulo (p. ej. la rotacion axial de la rodilla
solo existe con la rodilla flexionada).

Un dof es una rotacion de `sign * grados` alrededor de un eje LOCAL del hueso. Los dof se componen en el orden listado
(el primero se aplica primero), que es exactamente el orden Euler de Blender con las letras de los ejes en ese orden:
una articulacion con dof [y, x] equivale a euler_order 'YXZ'. Los ejes sin dof quedan BLOQUEADOS a 0.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_CONFIG_DIR, ConfigError
from .skeleton import SkeletonModel

AXES = ("x", "y", "z")
COUPLINGS_FILE = "rig_couplings.json"


@dataclass(frozen=True)
class ChannelLimit:
    axis: str  # "x" | "y" | "z" del marco local del hueso
    min_deg: float
    max_deg: float
    locked: bool  # eje sin grado de libertad: fijo a 0


@dataclass(frozen=True)
class Coupling:
    joint: str  # articulacion sin lado ("knee")
    dof: str  # dof cuyo limite depende de otro angulo
    depends_on: str  # dof que lo habilita
    full_at_deg: float  # con |depends_on| >= full_at_deg el limite del dof es completo; por debajo crece linealmente desde 0
    source: str
    note: str = ""


def euler_order(joint) -> str:
    """Letras de los ejes en el orden de composicion de los dof; los ejes sin dof se anaden al final."""
    letters = [d.axis_local for d in joint.dofs]
    return "".join(letters + [a for a in AXES if a not in letters]).upper()


def channel_limits(joint) -> dict:
    """Limites Euler locales por eje del hueso: `sign * grados` dentro de [min, max]; los ejes sin dof, bloqueados."""
    out = {a: ChannelLimit(a, 0.0, 0.0, True) for a in AXES}
    for d in joint.dofs:
        lo, hi = (d.min_deg, d.max_deg) if d.axis_sign > 0 else (-d.max_deg, -d.min_deg)
        out[d.axis_local] = ChannelLimit(d.axis_local, lo, hi, False)
    return out


def load_couplings(model: SkeletonModel, config_dir=None) -> tuple:
    path = Path(config_dir or DEFAULT_CONFIG_DIR) / COUPLINGS_FILE
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    out = []
    for i, raw in enumerate(data.get("couplings", [])):
        where = f"{COUPLINGS_FILE}[{i}]"
        c = Coupling(str(raw["joint"]), str(raw["dof"]), str(raw["depends_on"]), float(raw["full_at_deg"]), str(raw["source"]), str(raw.get("note", "")))
        names = [f"{c.joint}.L" if f"{c.joint}.L" in model.joints else c.joint]
        for jn in names:
            if jn not in model.joints:
                raise ConfigError(f"{where}: articulacion desconocida '{c.joint}'")
            order = [d.name for d in model.joints[jn].dofs]
            if c.dof not in order or c.depends_on not in order:
                raise ConfigError(f"{where}: '{jn}' no tiene los dof '{c.depends_on}' y '{c.dof}' (tiene {order})")
            if order.index(c.depends_on) > order.index(c.dof):
                raise ConfigError(f"{where}: '{c.depends_on}' debe ir antes que '{c.dof}' en joints.json")
            if next(d for d in model.joints[jn].dofs if d.name == c.depends_on).axis_local != "x":
                raise ConfigError(f"{where}: el dof que habilita debe girar sobre el eje x local (bisagra)")
        if c.full_at_deg <= 0:
            raise ConfigError(f"{where}: full_at_deg debe ser positivo")
        out.append(c)
    return tuple(out)


def coupling_scale(coupling: Coupling, depends_on_deg: float) -> float:
    """Fraccion (0 a 1) del limite del dof acoplado que esta disponible con ese angulo del dof que lo habilita."""
    return max(0.0, min(1.0, abs(depends_on_deg) / coupling.full_at_deg))


def allowed_range(model: SkeletonModel, couplings, joint_name: str, dof_name: str, angles: dict) -> tuple:
    """(min, max) del dof dado el resto de angulos de la articulacion (aplica los acoples)."""
    d = next(x for x in model.joints[joint_name].dofs if x.name == dof_name)
    lo, hi = d.min_deg, d.max_deg
    for c in couplings:
        if joint_name.split(".")[0] == c.joint and c.dof == dof_name:
            k = coupling_scale(c, angles.get(c.depends_on, 0.0))
            lo, hi = lo * k, hi * k
    return lo, hi
