"""Comprobaciones y diagnosticos (Python puro). Cada funcion devuelve una lista de Issue.

severity "error"   -> el esqueleto no es valido; el proceso debe fallar.
severity "warning" -> algo sospechoso pero no bloqueante.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import dot, is_finite, length, mirror_point, sub
from .skeleton import REQUIRED_BONES, SkeletonModel

LENGTH_TOL = 1e-4  # m
AXIS_TOL = 1e-6
BLEND_TOL = 1e-4  # m: tolerancia al comparar con lo guardado en .blend (float32)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.code}: {self.message}"


def errors(issues) -> list:
    return [i for i in issues if i.severity == "error"]


def check_required_bones(model: SkeletonModel) -> list:
    return [
        Issue("error", "MISSING_BONE", f"Falta el hueso requerido '{n}'")
        for n in REQUIRED_BONES
        if n not in model.bones
    ]


def check_references(model: SkeletonModel) -> list:
    out = []
    for b in model.bones.values():
        if b.parent is not None and b.parent not in model.bones:
            out.append(Issue("error", "UNKNOWN_PARENT", f"'{b.name}' referencia al padre inexistente '{b.parent}'"))
    for j in model.joints.values():
        if j.bone not in model.bones:
            out.append(Issue("error", "JOINT_UNKNOWN_BONE", f"Articulacion '{j.name}' referencia hueso inexistente '{j.bone}'"))
        elif j.parent_bone != model.bones[j.bone].parent:
            out.append(Issue("error", "JOINT_PARENT_MISMATCH", f"Articulacion '{j.name}': padre inconsistente con el hueso"))
    return out


def check_hierarchy(model: SkeletonModel) -> list:
    out = []
    roots = [b.name for b in model.bones.values() if b.parent is None]
    if len(roots) != 1:
        out.append(Issue("error", "ROOT_COUNT", f"Debe haber exactamente 1 raiz, hay {len(roots)}: {roots}"))
    for name in model.bones:
        seen = set()
        cur = name
        while cur is not None:
            if cur in seen:
                out.append(Issue("error", "CYCLE", f"Ciclo en la jerarquia que incluye '{name}'"))
                break
            seen.add(cur)
            parent = model.bones[cur].parent if cur in model.bones else None
            cur = parent if parent in model.bones else None
    return out


def check_lengths(model: SkeletonModel) -> list:
    out = []
    for b in model.bones.values():
        if not (is_finite(b.head) and is_finite(b.tail) and isinstance(b.length, (int, float)) and math.isfinite(b.length)):
            out.append(Issue("error", "NON_FINITE", f"'{b.name}' tiene valores no finitos"))
            continue
        if b.length <= 0:
            out.append(Issue("error", "LENGTH_NOT_POSITIVE", f"'{b.name}' longitud {b.length} <= 0"))
            continue
        real = length(sub(b.tail, b.head))
        if abs(real - b.length) > LENGTH_TOL:
            out.append(Issue("error", "LENGTH_MISMATCH", f"'{b.name}': |tail-head|={real:.6f} != length={b.length:.6f}"))
    return out


def check_pivots_and_axes(model: SkeletonModel) -> list:
    out = []
    for j in model.joints.values():
        if not is_finite(j.pivot):
            out.append(Issue("error", "PIVOT_NON_FINITE", f"Pivote no finito en '{j.name}'"))
        elif j.bone in model.bones and length(sub(j.pivot, model.bones[j.bone].head)) > LENGTH_TOL:
            out.append(Issue("error", "PIVOT_OFF_BONE", f"Pivote de '{j.name}' no coincide con la cabeza de '{j.bone}'"))
        if not j.dofs:
            out.append(Issue("error", "NO_DOF", f"Articulacion '{j.name}' sin grados de libertad"))
        for d in j.dofs:
            if not is_finite(d.axis) or abs(length(d.axis) - 1.0) > AXIS_TOL:
                out.append(Issue("error", "AXIS_INVALID", f"Eje no unitario/no finito en '{j.name}.{d.name}'"))
            if not (math.isfinite(d.min_deg) and math.isfinite(d.max_deg)) or d.min_deg >= d.max_deg:
                out.append(Issue("error", "LIMITS_INVALID", f"Limites invalidos en '{j.name}.{d.name}': [{d.min_deg}, {d.max_deg}]"))
            elif not (d.min_deg <= 0 <= d.max_deg):
                out.append(Issue("error", "REST_OUTSIDE_LIMITS", f"La pose de reposo (0 deg) queda fuera de los limites en '{j.name}.{d.name}'"))
        for i, a in enumerate(j.dofs):
            for b in j.dofs[i + 1:]:
                if is_finite(a.axis) and is_finite(b.axis) and abs(dot(a.axis, b.axis)) > 0.999:
                    out.append(Issue("error", "AXES_PARALLEL", f"Ejes paralelos en '{j.name}': {a.name} y {b.name}"))
    return out


def check_symmetry(model: SkeletonModel) -> list:
    out = []
    for name, b in model.bones.items():
        if not name.endswith(".L"):
            continue
        other = model.bones.get(name[:-2] + ".R")
        if other is None:
            out.append(Issue("error", "NO_MIRROR", f"'{name}' no tiene hueso .R"))
            continue
        for label, p, q in (("head", b.head, other.head), ("tail", b.tail, other.tail)):
            if length(sub(mirror_point(p), q)) > LENGTH_TOL:
                out.append(Issue("error", "ASYMMETRIC", f"'{name}' {label} no es simetrico respecto a su .R"))
    return out


def check_plausibility(model: SkeletonModel) -> list:
    """Avisos (no bloqueantes) de coherencia global."""
    out = []
    top = max(max(b.head[2], b.tail[2]) for b in model.bones.values())
    if abs(top - model.height_m) > 0.05 * model.height_m:
        out.append(Issue("warning", "HEIGHT_MISMATCH", f"Altura del esqueleto {top:.3f} m difiere >5% de la configurada {model.height_m:.3f} m"))
    return out


def validate_model(model: SkeletonModel) -> list:
    return (
        check_required_bones(model)
        + check_references(model)
        + check_hierarchy(model)
        + check_lengths(model)
        + check_pivots_and_axes(model)
        + check_symmetry(model)
        + check_plausibility(model)
    )


def validate_blend_snapshot(model: SkeletonModel, snap: dict) -> list:
    """Compara lo leido de una escena de Blender (ver scene.read_back) con el modelo."""
    out = []
    if not snap.get("armature_object"):
        return [Issue("error", "NO_ARMATURE", "La escena no contiene el objeto armadura")]
    if not snap.get("armature_transform_identity", False):
        out.append(Issue("error", "ARMATURE_TRANSFORM", "La armadura tiene una transformacion distinta de la identidad"))
    sbones = snap.get("bones", {})
    for n in model.bones:
        if n not in sbones:
            out.append(Issue("error", "BLEND_MISSING_BONE", f"El .blend no contiene el hueso '{n}'"))
    for n in sbones:
        if n not in model.bones:
            out.append(Issue("error", "BLEND_EXTRA_BONE", f"El .blend contiene un hueso no esperado '{n}'"))
    for n, b in model.bones.items():
        s = sbones.get(n)
        if s is None:
            continue
        if s["parent"] != b.parent:
            out.append(Issue("error", "BLEND_PARENT", f"'{n}': padre en .blend {s['parent']!r} != {b.parent!r}"))
        for label, mine, theirs in (("head", b.head, s["head"]), ("tail", b.tail, s["tail"])):
            if length(sub(mine, tuple(theirs))) > BLEND_TOL:
                out.append(Issue("error", "BLEND_POSITION", f"'{n}' {label} difiere del modelo en el .blend"))
        if abs(s["length"] - b.length) > BLEND_TOL:
            out.append(Issue("error", "BLEND_LENGTH", f"'{n}' longitud en .blend {s['length']:.6f} != {b.length:.6f}"))
    meta = snap.get("meta", {})
    if meta.get("model_signature") != model.signature():
        out.append(Issue("error", "BLEND_SIGNATURE", "La firma del modelo guardada en el .blend no coincide"))
    counts = snap.get("counts", {})
    expected = {
        "joint_markers": len(model.joints),
        "joint_axes": sum(len(j.dofs) for j in model.joints.values()),
        "bone_visuals": len(model.bones),
    }
    for key, want in expected.items():
        if counts.get(key) != want:
            out.append(Issue("error", "BLEND_COUNT", f"{key}: {counts.get(key)} != esperado {want}"))
    for needed in ("AC_Skeleton", "AC_BoneVisuals", "AC_JointMarkers", "AC_JointAxes"):
        if needed not in snap.get("collections", []):
            out.append(Issue("error", "BLEND_COLLECTION", f"Falta la coleccion '{needed}'"))
    return out
