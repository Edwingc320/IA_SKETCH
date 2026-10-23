"""Pose A aplicada al esqueleto neutro por cinematica directa (FK). Python puro, sin bpy.

Convencion: cada hueso tiene una transformacion afin A_b (R_b, t_b) que lleva un punto del
esqueleto neutro a su posicion posada:  x -> R_b x + t_b.
  * raiz:   R = I, t = root_translation (traslacion vertical que apoya los pies)
  * hijo:   A_b = A_padre . Rot(pivote, Rl)   con   Rl = R_k(a_k) ... R_2(a_2) R_1(a_1)
    donde R_i gira `a_i` grados alrededor del eje i-esimo de la articulacion, definido en el
    neutro (ejes locales FIJOS del hueso en reposo; los dof se componen en el orden listado en
    joints.json). El padre posado arrastra al hijo y a sus ejes.
Los pivotes nunca se mueven en el modelo: la posicion posada de una cabeza es A_padre(cabeza_neutra).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from .config import ConfigError, PoseDef
from .geometry import (
    IDENTITY, Mat3, Quat, Vec3, add, dot, length, mat_mul, mat_vec, normalize,
    quat_from_axis_angle, quat_mul, rotation_matrix, sub,
)
from .skeleton import SkeletonModel


@dataclass(frozen=True)
class PosedBone:
    name: str
    head: Vec3
    tail: Vec3
    rotation: Mat3  # R_b
    translation: Vec3  # t_b
    local_quat: Quat  # rotacion local (ejes locales del hueso) para pose_bone.rotation_quaternion
    local_location: Vec3  # solo la raiz: traslacion en ejes locales (pose_bone.location)

    def apply(self, p: Vec3) -> Vec3:
        """Lleva un punto del espacio neutro al espacio posado de este hueso."""
        return add(mat_vec(self.rotation, p), self.translation)


@dataclass(frozen=True)
class PosedSkeleton:
    pose_name: str
    angles: dict  # nombre de articulacion con lado ("hip.L") -> {dof: grados}
    root_translation: Vec3
    bones: dict  # nombre -> PosedBone
    signature: str


def resolve_angles(model: SkeletonModel, pose: PoseDef) -> dict:
    """Expande las claves de la pose a articulaciones concretas (.L/.R) y valida su existencia."""
    resolved: dict[str, dict] = {}
    # primero las claves generales, luego las especificas de lado (que las sustituyen)
    for key in sorted(pose.rotations, key=lambda k: ("." in k, k)):
        dofs = pose.rotations[key]
        targets = [key] if key in model.joints else [f"{key}.L", f"{key}.R"]
        for jn in targets:
            if jn not in model.joints:
                raise ConfigError(f"Pose '{pose.name}': articulacion desconocida '{key}'")
            known = {d.name for d in model.joints[jn].dofs}
            for dof, deg in dofs.items():
                if dof not in known:
                    raise ConfigError(f"Pose '{pose.name}': '{jn}' no tiene el dof '{dof}' (validos: {sorted(known)})")
                resolved.setdefault(jn, {})[dof] = float(deg)
    return resolved


def _fk(model: SkeletonModel, angles: dict, root_translation: Vec3) -> dict:
    out: dict[str, PosedBone] = {}
    for name, bone in model.bones.items():
        joint = next((j for j in model.joints.values() if j.bone == name), None)
        if bone.parent is None:
            frame = bone.frame
            # traslacion global expresada en ejes locales de la raiz (rotacion de pose = I)
            loc = tuple(dot(root_translation, a) for a in frame)
            out[name] = PosedBone(name, add(bone.head, root_translation), add(bone.tail, root_translation),
                                  IDENTITY, root_translation, (1.0, 0.0, 0.0, 0.0), loc)  # type: ignore[arg-type]
            continue
        par = out[bone.parent]
        rl = IDENTITY
        quat: Quat = (1.0, 0.0, 0.0, 0.0)
        if joint is not None:
            for dof in joint.dofs:
                deg = angles.get(joint.name, {}).get(dof.name, 0.0)
                if deg == 0.0:
                    continue
                a = math.radians(deg)
                rl = mat_mul(rotation_matrix(dof.axis, a), rl)
                local_axis = tuple(dot(dof.axis, f) for f in bone.frame)  # el mismo eje, en ejes locales
                quat = quat_mul(quat_from_axis_angle(local_axis, a), quat)  # type: ignore[arg-type]
        pivot = bone.head
        r_b = mat_mul(par.rotation, rl)
        t_b = add(mat_vec(par.rotation, sub(pivot, mat_vec(rl, pivot))), par.translation)
        pb = PosedBone(name, (0, 0, 0), (0, 0, 0), r_b, t_b, quat, (0.0, 0.0, 0.0))
        out[name] = PosedBone(name, pb.apply(bone.head), pb.apply(bone.tail), r_b, t_b, quat, (0.0, 0.0, 0.0))
    return out


def apply_pose(model: SkeletonModel, pose: PoseDef) -> PosedSkeleton:
    """Calcula la pose posada. Despues apoya los pies: traslada la raiz en vertical para que el
    pivote de tobillo mas bajo quede exactamente a `ankle_height_m` sobre el suelo."""
    angles = resolve_angles(model, pose)
    first = _fk(model, angles, (0.0, 0.0, 0.0))
    ankles = [first[n].head[2] for n in ("foot.L", "foot.R")]
    root_t = (0.0, 0.0, model.ankle_height_m - min(ankles))
    bones = _fk(model, angles, root_t)
    payload = {
        "pose": pose.name,
        "angles": {j: dict(sorted(d.items())) for j, d in sorted(angles.items())},
        "root": [round(c, 6) for c in root_t],
        "bones": {n: [[round(c, 6) for c in b.head], [round(c, 6) for c in b.tail]] for n, b in sorted(bones.items())},
    }
    sig = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return PosedSkeleton(pose.name, angles, root_t, bones, sig)


def metrics(model: SkeletonModel, posed: PosedSkeleton) -> dict:
    """Medidas geometricas de la pose (para validar apoyo y separacion de los pies y para el reporte)."""
    hip_spacing = 2 * model.bones["thigh.L"].head[0]
    out = {"hip_spacing_m": hip_spacing, "root_translation_m": list(posed.root_translation)}
    left, right = posed.bones["foot.L"], posed.bones["foot.R"]
    out["ankle_spacing_m"] = length(sub(left.head, right.head))
    out["ankle_spacing_over_hip_spacing"] = out["ankle_spacing_m"] / hip_spacing
    out["ankle_spacing_over_height"] = out["ankle_spacing_m"] / model.height_m
    for side, pf in (("L", left), ("R", right)):
        neutral = model.bones[f"foot.{side}"]
        z_axis = tuple(mat_vec(pf.rotation, neutral.frame[2]))  # eje Z del pie posado (hacia el suelo)
        down = (0.0, 0.0, -1.0)
        out[f"foot_{side}_tilt_deg"] = math.degrees(math.acos(max(-1.0, min(1.0, dot(normalize(z_axis), down)))))
        out[f"foot_{side}_ankle_z_m"] = pf.head[2]
        out[f"foot_{side}_ankle_height_error_m"] = pf.head[2] - model.ankle_height_m
    out["ankle_level_diff_m"] = abs(left.head[2] - right.head[2])
    return out
