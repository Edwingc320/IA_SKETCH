"""Comprobaciones y diagnosticos (Python puro). Cada funcion devuelve una lista de Issue.

severity "error"   -> el esqueleto no es valido; el proceso debe fallar.
severity "warning" -> algo sospechoso pero no bloqueante.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import (
    cross, dot, is_finite, length, mat_vec, mirror_frame, mirror_point, normalize, rotation_matrix, scale, sub,
)
from . import rig_limits, volumes
from .pose import PosedSkeleton, metrics
from .skeleton import REQUIRED_BONES, SkeletonModel

LENGTH_TOL = 1e-4  # m
AXIS_TOL = 1e-6
FRAME_TOL = 1e-9  # los marcos y ejes se calculan en doble precision: tolerancia estricta
BLEND_TOL = 1e-4  # m: tolerancia al comparar con lo guardado en .blend (float32)
SEMANTICS_PROBE_DEG = 10.0
SEMANTICS_MIN_COS = 0.7
FOOT_TILT_WARN_DEG, FOOT_TILT_ERROR_DEG = 0.1, 1.0
FEET_LEVEL_TOL = 0.002  # m
STANCE_WARN = (1.0, 2.0)  # separacion de tobillos / separacion de caderas: rango esperado
STANCE_ERROR = (0.5, 3.0)


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


def _close(a, b, tol) -> bool:
    return length(sub(a, b)) <= tol


def check_frames(model: SkeletonModel) -> list:
    """Marcos locales: ortonormales, derechos, Y = direccion del hueso, R = espejo de L."""
    out = []
    for b in model.bones.values():
        x, y, z = b.frame
        if not all(is_finite(a) for a in b.frame):
            out.append(Issue("error", "FRAME_NON_FINITE", f"Marco no finito en '{b.name}'"))
            continue
        if any(abs(length(a) - 1.0) > FRAME_TOL for a in b.frame):
            out.append(Issue("error", "FRAME_NOT_UNIT", f"Ejes no unitarios en el marco de '{b.name}'"))
        if max(abs(dot(x, y)), abs(dot(y, z)), abs(dot(x, z))) > FRAME_TOL:
            out.append(Issue("error", "FRAME_NOT_ORTHOGONAL", f"Ejes no ortogonales en el marco de '{b.name}'"))
        if not _close(cross(x, y), z, FRAME_TOL):
            out.append(Issue("error", "FRAME_NOT_RIGHT_HANDED", f"Marco de '{b.name}' no es derecho (x cross y != z)"))
        direction = sub(b.tail, b.head)
        if is_finite(direction) and length(direction) > 0 and not _close(y, normalize(direction), FRAME_TOL):
            out.append(Issue("error", "FRAME_Y_NOT_BONE", f"El eje Y del marco de '{b.name}' no es head->tail"))
    for name, b in model.bones.items():
        if name.endswith(".L") and name[:-2] + ".R" in model.bones:
            expected = mirror_frame(b.frame)
            actual = model.bones[name[:-2] + ".R"].frame
            if not all(_close(e, a, FRAME_TOL) for e, a in zip(expected, actual)):
                out.append(Issue("error", "FRAME_NOT_MIRRORED", f"El marco de '{name[:-2]}.R' no es el espejo del de '{name}'"))
    return out


_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def check_joint_axes(model: SkeletonModel) -> list:
    """Cada eje es +-un eje local del hueso; los no axiales son perpendiculares al hueso y el
    axial es paralelo; los ejes de una articulacion son mutuamente ortogonales (E1/E4)."""
    out = []
    for j in model.joints.values():
        bone = model.bones.get(j.bone)
        if bone is None:
            continue
        y = bone.frame[1]
        for d in j.dofs:
            column = bone.frame[_AXIS_INDEX.get(d.axis_local, 0)]
            if d.axis_local not in _AXIS_INDEX or not _close(d.axis, scale(column, float(d.axis_sign)), FRAME_TOL):
                out.append(Issue("error", "AXIS_NOT_LOCAL", f"El eje '{j.name}.{d.name}' no coincide con +-el eje local {d.axis_local} del hueso"))
                continue
            if d.positive_motion == "axial":
                if abs(abs(dot(d.axis, y)) - 1.0) > FRAME_TOL:
                    out.append(Issue("error", "AXIAL_NOT_PARALLEL", f"El eje axial '{j.name}.{d.name}' no es paralelo al hueso"))
            elif abs(dot(d.axis, y)) > FRAME_TOL:
                out.append(Issue("error", "AXIS_NOT_PERPENDICULAR", f"El eje '{j.name}.{d.name}' no es perpendicular al hueso"))
        for i, a in enumerate(j.dofs):
            for b in j.dofs[i + 1:]:
                if abs(dot(a.axis, b.axis)) > FRAME_TOL:
                    out.append(Issue("error", "AXES_NOT_ORTHOGONAL", f"Ejes no ortogonales en '{j.name}': {a.name} y {b.name}"))
    return out


_MOTION_VECTORS = {
    "anterior": (0.0, -1.0, 0.0), "posterior": (0.0, 1.0, 0.0),
    "superior": (0.0, 0.0, 1.0), "inferior": (0.0, 0.0, -1.0),
    "left": (1.0, 0.0, 0.0), "right": (-1.0, 0.0, 0.0),
}


def dof_displacement(model: SkeletonModel, joint, dof, degrees: float):
    """Desplazamiento del extremo distal (cola del hueso) al girar `degrees` sobre el eje del dof."""
    bone = model.bones[joint.bone]
    rel = sub(bone.tail, joint.pivot)
    return sub(mat_vec(rotation_matrix(dof.axis, math.radians(degrees)), rel), rel)


def check_dof_semantics(model: SkeletonModel) -> list:
    """El movimiento positivo/negativo coincide con el declarado en `positive_motion`."""
    out = []
    for j in model.joints.values():
        if j.bone not in model.bones:
            continue  # ya se informa como JOINT_UNKNOWN_BONE
        side = model.bones[j.bone].side
        for d in j.dofs:
            if d.positive_motion == "axial":
                continue
            if d.positive_motion in ("lateral", "medial"):
                if side is None:
                    out.append(Issue("error", "MOTION_NEEDS_SIDE", f"'{j.name}.{d.name}': lateral/medial requiere un hueso con lado"))
                    continue
                sx = 1.0 if side == "L" else -1.0
                expected = (sx if d.positive_motion == "lateral" else -sx, 0.0, 0.0)
            elif d.positive_motion in _MOTION_VECTORS:
                expected = _MOTION_VECTORS[d.positive_motion]
            else:
                out.append(Issue("error", "MOTION_UNKNOWN", f"'{j.name}.{d.name}': positive_motion '{d.positive_motion}' desconocido"))
                continue
            for sign, label in ((1.0, "positivo"), (-1.0, "negativo")):
                v = dof_displacement(model, j, d, sign * SEMANTICS_PROBE_DEG)
                n = length(v)
                cos = dot(v, expected) / n if n > 0 else 0.0
                if cos * sign < SEMANTICS_MIN_COS:
                    out.append(Issue(
                        "error", "DOF_SEMANTICS",
                        f"'{j.name}.{d.name}': el movimiento {label} no va hacia '{d.positive_motion}' (cos={cos:+.2f})",
                    ))
    return out


def check_ground_neutral(model: SkeletonModel) -> list:
    """Apoyo del pie en el neutro: tobillos a la altura configurada, pie horizontal, nada mas bajo."""
    out = []
    for side in ("L", "R"):
        foot = model.bones.get(f"foot.{side}")
        if foot is None:
            continue
        if abs(foot.head[2] - model.ankle_height_m) > FRAME_TOL * 10:
            out.append(Issue("error", "ANKLE_HEIGHT", f"Tobillo {side} a z={foot.head[2]:.6f} != altura configurada {model.ankle_height_m:.6f}"))
        if abs(foot.tail[2] - foot.head[2]) > FRAME_TOL * 10:
            out.append(Issue("error", "FOOT_NOT_HORIZONTAL", f"El pie {side} no es horizontal en el neutro"))
    lowest = min(min(b.head[2], b.tail[2]) for b in model.bones.values())
    if lowest < model.ankle_height_m - 1e-6:
        out.append(Issue("error", "BELOW_FEET", f"Hay huesos por debajo del apoyo del pie (z={lowest:.4f} < {model.ankle_height_m:.4f})"))
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
    """Valida el esqueleto NEUTRO."""
    return (
        check_required_bones(model)
        + check_references(model)
        + check_hierarchy(model)
        + check_lengths(model)
        + check_frames(model)
        + check_pivots_and_axes(model)
        + check_joint_axes(model)
        + check_dof_semantics(model)
        + check_symmetry(model)
        + check_ground_neutral(model)
        + check_plausibility(model)
    )


def validate_pose(model: SkeletonModel, posed: PosedSkeleton) -> list:
    """Valida la pose aplicada: limites, rigidez, pivotes sin desplazar, simetria, pies y separacion."""
    out = []
    couplings = rig_limits.load_couplings(model)
    # 1. angulos dentro de los limites articulares (medidos desde el neutro)
    for jn, dofs in posed.angles.items():
        for dn, deg in dofs.items():
            d = next(x for x in model.joints[jn].dofs if x.name == dn)
            if not (d.min_deg <= deg <= d.max_deg):
                out.append(Issue("error", "POSE_OUT_OF_LIMITS", f"Pose: '{jn}.{dn}' = {deg} fuera de [{d.min_deg}, {d.max_deg}]"))
            else:
                lo, hi = rig_limits.allowed_range(model, couplings, jn, dn, dofs)
                if not (lo - 1e-9 <= deg <= hi + 1e-9):
                    out.append(Issue("error", "POSE_COUPLED_LIMIT", f"Pose: '{jn}.{dn}' = {deg} fuera de [{lo:.1f}, {hi:.1f}] con los demas angulos de la articulacion"))
    # 2. rigidez y pivotes: la cabeza posada es la imagen de la cabeza neutra por la transformacion del padre
    for name, b in model.bones.items():
        pb = posed.bones[name]
        if abs(length(sub(pb.tail, pb.head)) - b.length) > FRAME_TOL * 10:
            out.append(Issue("error", "POSE_LENGTH_CHANGED", f"La pose cambia la longitud de '{name}'"))
        parent = posed.bones[b.parent] if b.parent else None
        expected_head = parent.apply(b.head) if parent else tuple(c + t for c, t in zip(b.head, posed.root_translation))
        if not _close(pb.head, expected_head, FRAME_TOL * 10):
            out.append(Issue("error", "POSE_PIVOT_DISPLACED", f"El pivote de '{name}' se desplazo respecto a su padre"))
    # 3. simetria (solo si la pose es simetrica)
    left_right_same = all(
        posed.angles.get(n, {}) == posed.angles.get(n[:-2] + ".R", {}) for n in model.joints if n.endswith(".L")
    )
    if left_right_same:
        for name in model.bones:
            if name.endswith(".L"):
                a, b = posed.bones[name], posed.bones[name[:-2] + ".R"]
                if not (_close(mirror_point(a.head), b.head, FRAME_TOL * 10) and _close(mirror_point(a.tail), b.tail, FRAME_TOL * 10)):
                    out.append(Issue("error", "POSE_ASYMMETRIC", f"La pose simetrica produce asimetria en '{name}'"))
    # 4. pies: planos, a nivel y con separacion razonable
    m = metrics(model, posed)
    for side in ("L", "R"):
        tilt = m[f"foot_{side}_tilt_deg"]
        if tilt > FOOT_TILT_ERROR_DEG:
            out.append(Issue("error", "POSE_FOOT_TILTED", f"Pie {side} inclinado {tilt:.2f} grados; ajusta ankle.inversion para compensar la abduccion de cadera"))
        elif tilt > FOOT_TILT_WARN_DEG:
            out.append(Issue("warning", "POSE_FOOT_TILTED", f"Pie {side} inclinado {tilt:.2f} grados"))
        if m[f"foot_{side}_ankle_height_error_m"] < -1e-6:
            out.append(Issue("error", "POSE_FOOT_BELOW_GROUND", f"El tobillo {side} queda por debajo del apoyo"))
    if m["ankle_level_diff_m"] > FEET_LEVEL_TOL:
        out.append(Issue("error", "POSE_FEET_NOT_LEVEL", f"Los dos pies no estan a la misma altura (dif {m['ankle_level_diff_m'] * 1000:.1f} mm)"))
    r = m["ankle_spacing_over_hip_spacing"]
    eps = 1e-9  # el neutro (cociente exactamente 1) no debe avisar por ruido de coma flotante
    if not (STANCE_ERROR[0] <= r <= STANCE_ERROR[1]):
        out.append(Issue("error", "POSE_STANCE", f"Separacion de tobillos {r:.2f}x la de caderas, fuera de {STANCE_ERROR}"))
    elif not (STANCE_WARN[0] - eps <= r <= STANCE_WARN[1] + eps):
        out.append(Issue("warning", "POSE_STANCE", f"Separacion de tobillos {r:.2f}x la de caderas, fuera de lo esperado {STANCE_WARN}"))
    return out


def validate_blend_snapshot(model: SkeletonModel, snap: dict, posed: PosedSkeleton) -> list:
    """Compara lo leido de una escena de Blender (ver scene.read_back) con el modelo neutro y la pose."""
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
        # roll: los ejes locales del hueso en Blender deben ser los del marco del modelo
        for label, mine, theirs in zip("xyz", b.frame, s.get("frame", [(9, 9, 9)] * 3)):
            if length(sub(mine, tuple(theirs))) > BLEND_TOL:
                out.append(Issue("error", "BLEND_FRAME", f"'{n}': el eje local {label} en Blender no coincide con el marco del modelo (roll)"))
    meta = snap.get("meta", {})
    if meta.get("model_signature") != model.signature():
        out.append(Issue("error", "BLEND_SIGNATURE", "La firma del modelo guardada en el .blend no coincide"))
    if meta.get("pose_signature") != posed.signature:
        out.append(Issue("error", "BLEND_POSE_SIGNATURE", "La firma de la pose guardada en el .blend no coincide"))
    if snap.get("pose_position") != "POSE":
        out.append(Issue("error", "BLEND_POSE_POSITION", "La armadura no esta en modo POSE"))
    # pose: posiciones evaluadas de los huesos posados == cinematica directa del modelo
    spose = snap.get("pose_bones", {})
    for n, pb in posed.bones.items():
        s = spose.get(n)
        if s is None:
            out.append(Issue("error", "BLEND_POSE_MISSING", f"Falta el hueso posado '{n}'"))
            continue
        for label, mine, theirs in (("head", pb.head, s["head"]), ("tail", pb.tail, s["tail"])):
            if length(sub(mine, tuple(theirs))) > BLEND_TOL:
                out.append(Issue("error", "BLEND_POSE_POSITION", f"'{n}' {label} posado en Blender difiere de la FK del modelo"))
    # visualizacion: debe seguir a los huesos (emparentada, sin doble transformacion)
    vis = snap.get("visuals", {})
    for n, pb in posed.bones.items():
        v = vis.get(f"VIS_{n}")
        if v is None:
            continue
        if v["parent_bone"] != n:
            out.append(Issue("error", "VIS_PARENT", f"VIS_{n} no esta emparentado al hueso '{n}'"))
        if length(sub(pb.head, tuple(v["head"]))) > BLEND_TOL or length(sub(pb.tail, tuple(v["tail"]))) > BLEND_TOL:
            out.append(Issue("error", "VIS_POSITION", f"VIS_{n} no coincide con el hueso posado"))
    for jn, j in model.joints.items():
        parent = j.parent_bone
        if parent is None:
            continue
        expected_pivot = posed.bones[j.bone].head
        m = vis.get(f"JM_{jn}")
        if m is not None:
            if m["parent_bone"] != parent:
                out.append(Issue("error", "VIS_PARENT", f"JM_{jn} no esta emparentado a '{parent}'"))
            if length(sub(expected_pivot, tuple(m["center"]))) > BLEND_TOL:
                out.append(Issue("error", "VIS_POSITION", f"JM_{jn} no esta en el pivote posado"))
        for d in j.dofs:
            a = vis.get(f"AX_{jn}_{d.name}")
            if a is None:
                continue
            expected_dir = mat_vec(posed.bones[parent].rotation, d.axis)  # el padre posado arrastra los ejes
            if a["parent_bone"] != parent:
                out.append(Issue("error", "VIS_PARENT", f"AX_{jn}_{d.name} no esta emparentado a '{parent}'"))
            if length(sub(expected_pivot, tuple(a["location"]))) > BLEND_TOL or length(sub(expected_dir, tuple(a["direction"]))) > BLEND_TOL:
                out.append(Issue("error", "VIS_POSITION", f"AX_{jn}_{d.name} no coincide con el eje posado"))
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


# --- Nivel 1 (anatomia) ------------------------------------------------------------------------
ANCHOR_TOL = 1e-9
SCAPULA_RIB_CLEARANCE_M = 0.01  # holgura minima lamina escapular <-> arcos costales


def validate_anatomy(base: SkeletonModel, anat) -> list:
    """Valida el nivel 1 contra la base: jerarquia enraizada en la base, geometria, simetria,
    anclajes exactos y trazabilidad con la referencia. No modifica nada."""
    from types import SimpleNamespace

    from .anatomy import resolve_point_ref

    out = []
    if anat.base_signature != base.signature():
        out.append(Issue("error", "ANAT_BASE_MISMATCH", "El nivel 1 se construyo sobre otra base (firma distinta)"))
    names = set(anat.bones)
    for n, b in anat.bones.items():
        if n in base.bones:
            out.append(Issue("error", "ANAT_NAME_COLLISION", f"'{n}' choca con un hueso de la base"))
        if b.parent not in base.bones and b.parent not in names:
            out.append(Issue("error", "ANAT_PARENT_UNKNOWN", f"'{n}': padre inexistente '{b.parent}'"))
            continue
        seen, cur = set(), n
        while cur in names:  # subir hasta llegar a un hueso de la base
            if cur in seen:
                out.append(Issue("error", "ANAT_CYCLE", f"Ciclo en la jerarquia anatomica que incluye '{n}'"))
                break
            seen.add(cur)
            cur = anat.bones[cur].parent
        else:
            if cur not in base.bones:
                out.append(Issue("error", "ANAT_NOT_ROOTED", f"'{n}' no cuelga de ningun hueso de la base"))
        if not b.reference:
            out.append(Issue("error", "ANAT_NO_REFERENCE", f"'{n}' no indica que huesos de la referencia representa"))
        ap = b.anatomical_parent or b.parent
        if ap not in base.bones and ap not in names:
            out.append(Issue("error", "ANAT_ANATOMICAL_PARENT_UNKNOWN", f"'{n}': padre anatomico inexistente '{ap}'"))
        else:  # la jerarquia anatomica tambien debe ser un arbol sin ciclos que acaba en la base
            seen_a, cur_a = set(), n
            while cur_a in names:
                if cur_a in seen_a:
                    out.append(Issue("error", "ANAT_ANATOMICAL_CYCLE", f"Ciclo en la jerarquia anatomica que incluye '{n}'"))
                    break
                seen_a.add(cur_a)
                cur_a = anat.bones[cur_a].anatomical_parent or anat.bones[cur_a].parent
        if not all(is_finite(p) for p in b.outline):
            out.append(Issue("error", "ANAT_OUTLINE_NON_FINITE", f"Contorno no finito en '{n}'"))
    # geometria: mismas comprobaciones que la base (duck typing sobre .bones)
    view = SimpleNamespace(bones=anat.bones)
    for issue in check_lengths(view) + check_frames(view) + check_symmetry(view):
        out.append(Issue(issue.severity, "ANAT_" + issue.code, issue.message))
    for n, b in anat.bones.items():
        if n.endswith(".L") and n[:-2] + ".R" in anat.bones:
            r = anat.bones[n[:-2] + ".R"]
            if len(b.outline) != len(r.outline) or not all(_close(mirror_point(p), q, FRAME_TOL) for p, q in zip(b.outline, r.outline)):
                out.append(Issue("error", "ANAT_OUTLINE_ASYMMETRIC", f"El contorno de '{n[:-2]}.R' no es el espejo del de '{n}'"))
    # anclajes exactos (p. ej. cabeza femoral en el acetabulo)
    for point, equals, desc in anat.anchors:
        try:
            p = resolve_point_ref(point, base, anat.bones)
            q = resolve_point_ref(equals, base, anat.bones)
        except ValueError as exc:
            out.append(Issue("error", "ANAT_ANCHOR_UNKNOWN", str(exc)))
            continue
        if length(sub(p, q)) > ANCHOR_TOL:
            out.append(Issue("error", "ANAT_ANCHOR", f"{point} != {equals} ({length(sub(p, q)) * 1000:.3f} mm): {desc}"))
    # la escapula flota sobre la cara posterior del torax sin atravesar las costillas
    from .anatomy import scapula_rib_clearance
    for side in ("L", "R"):
        gap = scapula_rib_clearance(anat, side)
        if gap is not None and gap < SCAPULA_RIB_CLEARANCE_M:
            out.append(Issue("error", "ANAT_SCAPULA_RIB_COLLISION",
                             f"La escapula {side} queda a {gap * 1000:.1f} mm de las costillas (minimo {SCAPULA_RIB_CLEARANCE_M * 1000:.0f} mm)"))
    # trazabilidad
    known = set(anat.reference_names)
    claimed: dict[str, str] = {}
    for n, b in anat.bones.items():
        for r in b.reference:
            if r not in known:
                out.append(Issue("error", "ANAT_REFERENCE_UNKNOWN", f"'{n}' cita '{r}', que no esta en la referencia"))
            elif r in claimed:
                out.append(Issue("error", "ANAT_REFERENCE_DUPLICATE", f"'{r}' lo representan '{claimed[r]}' y '{n}'"))
            else:
                claimed[r] = n
            if r in base.bones:
                out.append(Issue("error", "ANAT_REFERENCE_IN_BASE", f"'{r}' ya es un hueso de la base; no se duplica en el nivel 1"))
    out += validate_closures(anat)
    return out


def validate_closures(anat) -> list:
    """Cierres estructurales del nivel 1: cartilagos costales, anillo pelvico y formas volumetricas."""
    from .anatomy import point_segment_distance

    out = []
    tol = 1e-6 * max(1.0, anat.height_m)
    st = anat.bones.get("sternum")
    for side in "LR":
        for k in range(1, 13):
            rib = anat.bones.get(f"rib_{k:02d}.{side}")
            if rib is None:
                continue
            if k > 10:  # flotantes: terminan libres en la pared abdominal
                if rib.cartilage:
                    out.append(Issue("error", "CLOSURE_FLOATING_RIB", f"'{rib.name}' es flotante y no debe llevar cartilago"))
                continue
            if len(rib.cartilage) < 2 or length(sub(rib.cartilage[0], rib.tail)) > tol:
                out.append(Issue("error", "CLOSURE_RIB_TAIL", f"'{rib.name}': el cartilago debe nacer exactamente en la cola del hueso"))
                continue
            end = rib.cartilage[-1]
            if k <= 7:  # verdaderas: terminan sobre el borde del esternon
                pts = list(st.outline) + [st.outline[0]]
                d = min(point_segment_distance(end, a, b) for a, b in zip(pts, pts[1:]))
                if d > 1e-5 * max(1.0, anat.height_m):
                    out.append(Issue("error", "CLOSURE_TRUE_RIB", f"'{rib.name}': el cartilago no termina en el borde del esternon ({d * 1000:.2f} mm)"))
            else:  # falsas: terminan sobre el cartilago de la costilla superior
                above = anat.bones[f"rib_{k - 1:02d}.{side}"].cartilage
                d = point_segment_distance(end, above[0], above[-1]) if len(above) >= 2 else float("inf")
                if d > tol:
                    out.append(Issue("error", "CLOSURE_FALSE_RIB", f"'{rib.name}': el cartilago no termina en el de la costilla {k - 1} ({d * 1000:.2f} mm)"))
    sac = anat.bones.get("sacrum")
    for side, sx in (("L", 1), ("R", -1)):
        ilium, pubis = anat.bones.get(f"ilium.{side}"), anat.bones.get(f"pubis.{side}")
        if sac is None or ilium is None or pubis is None:
            continue
        corner = min(sac.outline, key=lambda p: length(sub(p, ilium.head)))
        if length(sub(corner, ilium.head)) > tol or corner[0] * sx <= 0:
            out.append(Issue("error", "CLOSURE_SACROILIAC", f"'{ilium.name}': su cabeza no es la esquina lateral del sacro (anillo pelvico abierto)"))
        if abs(pubis.tail[0]) > tol:
            out.append(Issue("error", "CLOSURE_SYMPHYSIS", f"'{pubis.name}': su cola no esta en la linea media (anillo pelvico abierto)"))
    for n, b in anat.bones.items():
        if b.volume:
            try:
                verts, faces = volumes.volume_mesh(b)
            except volumes.VolumeError as exc:
                out.append(Issue("error", "VOLUME_INVALID", f"'{n}': {exc}"))
                continue
            if volumes.euler_characteristic(verts, faces) != 2 or volumes.signed_volume(verts, faces) <= 0:
                out.append(Issue("error", "VOLUME_NOT_CLOSED", f"'{n}': la forma volumetrica no es una superficie cerrada"))
    return out

JOINT_GAP_WARN_M = 0.02  # un centro articular mas lejos de uno de sus huesos se documenta como hueco
POINT_ON_BONE_TOL_M = 0.03  # inserciones y extremos de ligamento: distancia maxima a su hueso


def validate_articulations(base: SkeletonModel, anat, art) -> list:
    """Puntos de union: huesos existentes, centros sobre sus huesos, rangos con fuente, motor del rig
    coherente con su pivote, extremos de ligamentos e inserciones sobre su hueso, simetria L/R."""
    from .articulations import bone_distance

    out = []
    known = set(base.bones) | set(anat.bones)
    for key, s in art.sources.items():
        if not str(s.get("url", "")).startswith("https://"):
            out.append(Issue("error", "ART_SOURCE_URL", f"Fuente '{key}' sin URL https"))
        if s.get("reliability") not in ("alta", "media", "baja"):
            out.append(Issue("error", "ART_SOURCE_RELIABILITY", f"Fuente '{key}': reliability debe ser alta|media|baja"))

    def check_sources(owner, keys):
        for k in keys:
            if k not in art.sources:
                out.append(Issue("error", "ART_SOURCE_UNKNOWN", f"'{owner}' cita la fuente desconocida '{k}'"))

    for n, j in art.joints.items():
        check_sources(n, j.sources)
        for b in list(j.bones) + [j.carrier]:
            if b not in known:
                out.append(Issue("error", "ART_BONE_UNKNOWN", f"Articulacion '{n}': hueso inexistente '{b}'"))
        for b in j.bones:
            if b not in known:
                continue
            d = bone_distance(j.center, b, base, anat, art.surfaces)
            if d > j.tolerance_m:
                out.append(Issue("error", "ART_JOINT_FAR", f"'{n}': el centro esta a {d * 1000:.1f} mm de '{b}' (tolerancia {j.tolerance_m * 1000:.0f} mm)"))
            elif d > JOINT_GAP_WARN_M and j.known_limitation:
                out.append(Issue("warning", "ART_JOINT_GAP", f"'{n}': hueco de {d * 1000:.1f} mm hasta '{b}': {j.known_limitation}"))
        if j.rig_driver is not None:
            bj = base.joints.get(j.rig_driver)
            if bj is None:
                out.append(Issue("error", "ART_RIG_DRIVER_UNKNOWN", f"'{n}': la base no tiene la articulacion '{j.rig_driver}'"))
            elif length(sub(bj.pivot, j.center)) > ANCHOR_TOL:
                out.append(Issue("error", "ART_RIG_DRIVER_PIVOT", f"'{n}': su centro no coincide con el pivote de '{j.rig_driver}'"))
        names = [d.name for d in j.dofs]
        if len(names) != len(set(names)):
            out.append(Issue("error", "ART_DOF_DUPLICATE", f"'{n}': grados de libertad repetidos"))
        for d in j.dofs:
            if d.total_deg is not None:
                lo, hi = d.total_deg
                if not (0 < lo <= hi <= (360 if d.unit == "deg" else 100)):
                    out.append(Issue("error", "ART_DOF_RANGE", f"'{n}.{d.name}': rango invalido {d.total_deg}"))
                if not d.source:
                    out.append(Issue("error", "ART_DOF_NO_SOURCE", f"'{n}.{d.name}': cifra sin fuente"))
            if d.source:
                check_sources(f"{n}.{d.name}", [d.source])
    for n, lg in art.ligaments.items():
        check_sources(n, lg.sources)
        if lg.joint is not None and lg.joint not in art.joints:
            out.append(Issue("error", "ART_LIGAMENT_JOINT", f"Ligamento '{n}': articulacion inexistente '{lg.joint}'"))
        for label, bone, p in (("origen", lg.from_bone, lg.a), ("insercion", lg.to_bone, lg.b)):
            if bone not in known:
                out.append(Issue("error", "ART_BONE_UNKNOWN", f"Ligamento '{n}': hueso inexistente '{bone}'"))
            elif bone_distance(p, bone, base, anat, art.surfaces) > lg.tolerance_m:
                out.append(Issue("error", "ART_LIGAMENT_OFF_BONE", f"Ligamento '{n}': el {label} no esta sobre '{bone}'"))
        for k, w in enumerate(lg.via):  # guias de envoltura: sobre su hueso (< tolerancia) y con fuente de la trayectoria en el ligamento
            if w.bone not in known:
                out.append(Issue("error", "ART_BONE_UNKNOWN", f"Ligamento '{n}': la guia {k} cita el hueso inexistente '{w.bone}'"))
            elif bone_distance(w.point, w.bone, base, anat, art.surfaces) > lg.tolerance_m:
                out.append(Issue("error", "ART_VIA_OFF_BONE", f"Ligamento '{n}': la guia {k} no esta a menos de {lg.tolerance_m * 1000:.0f} mm de '{w.bone}'"))
        if lg.mechanics is not None:
            m = lg.mechanics
            if m.get("status") not in ("convencion_parametrica_declarada", "medido"):
                out.append(Issue("error", "ART_MECHANICS_STATUS", f"Ligamento '{n}': mechanics.status debe ser convencion_parametrica_declarada o medido"))
            elif m["status"] == "convencion_parametrica_declarada" and (m.get("stiffness_N_per_mm") is not None or m.get("slack_length_m") is not None):
                out.append(Issue("error", "ART_MECHANICS_INVENTED", f"Ligamento '{n}': una convencion declarada no puede traer valores mecanicos"))
            elif m["status"] == "medido" and (m.get("stiffness_N_per_mm") is None or not m.get("source")):
                out.append(Issue("error", "ART_MECHANICS_NO_SOURCE", f"Ligamento '{n}': una propiedad mecanica medida necesita valor y fuente"))
        if art.surfaces:  # en reposo ninguna poligonal atraviesa un obstaculo
            from . import ligament_paths as _lp

            if _lp.nodes(lg) and any(s.bone in (lg.from_bone, lg.to_bone, *[w.bone for w in lg.via]) for s in art.surfaces.values()):
                clear = min(s.signed_distance(p) for s in art.surfaces.values() for p in _lp.rest_samples(lg))
                if clear < -_lp.PENETRATION_TOL_M * base.height_m / 1.75:
                    out.append(Issue("error", "ART_LIGAMENT_PENETRATES", f"Ligamento '{n}': en reposo atraviesa el hueso {-clear * 1000:.1f} mm"))
        if lg.deform and not lg.via and lg.from_bone == lg.to_bone:
            out.append(Issue("error", "ART_DEFORM_USELESS", f"Ligamento '{n}': deform sin guias y con los dos extremos en el mismo hueso"))
        span = length(sub(lg.b, lg.a))
        if lg.typical_length_m and span > 3 * lg.typical_length_m:
            out.append(Issue("warning", "ART_LIGAMENT_LENGTH", f"Ligamento '{n}' mide {span * 1000:.0f} mm (tipico ~{lg.typical_length_m * 1000:.0f} mm): limitacion documentada"))
    for n, sf in art.surfaces.items():
        check_sources(n, sf.sources)
        if sf.bone not in known:
            out.append(Issue("error", "ART_BONE_UNKNOWN", f"Superficie '{n}': hueso inexistente '{sf.bone}'"))
        elif bone_distance(sf.a, sf.bone, base, anat) > 0.012 * base.height_m / 1.75:
            out.append(Issue("error", "ART_SURFACE_OFF_BONE", f"Superficie '{n}': su eje no nace sobre '{sf.bone}'"))
        if not sf.sources:
            out.append(Issue("error", "ART_SURFACE_NO_SOURCE", f"Superficie '{n}' sin fuente (el radio es una convencion con rango publicado)"))
    for n, at in art.attachments.items():
        check_sources(n, at.sources)
        if at.bone not in known:
            out.append(Issue("error", "ART_BONE_UNKNOWN", f"Insercion '{n}': hueso inexistente '{at.bone}'"))
        elif bone_distance(at.point, at.bone, base, anat, art.surfaces) > at.tolerance_m:
            out.append(Issue("error", "ART_ATTACHMENT_OFF_BONE", f"Insercion '{n}' no esta sobre '{at.bone}'"))
        if not at.structures:
            out.append(Issue("error", "ART_ATTACHMENT_EMPTY", f"Insercion '{n}' sin estructuras"))
    # simetria
    for store, pts in ((art.joints, lambda x: [x.center]), (art.ligaments, lambda x: [x.a, *[w.point for w in x.via], x.b]), (art.attachments, lambda x: [x.point]),
                       (art.surfaces, lambda x: [x.a, x.b])):
        for n, x in store.items():
            if ".L" in n and n.replace(".L", ".R") in store:
                for p, q in zip(pts(x), pts(store[n.replace(".L", ".R")])):
                    if length(sub(mirror_point(p), q)) > FRAME_TOL * 10:
                        out.append(Issue("error", "ART_ASYMMETRIC", f"'{n}' no es simetrico respecto a su .R"))
    return out


def validate_ligament_poses(base: SkeletonModel, anat, art, sides=("L", "R")) -> list:
    """Barrido de la cadera (ligament_paths.HIP_SWEEP): ningun ligamento de la cadera atraviesa la cabeza ni el cuello del femur en ninguna pose.
    Los nodos viajan con sus huesos por construccion, asi que un nodo no puede quedar atras; lo que se mide es la distancia a los obstaculos."""
    from . import ligament_paths as lp

    out = []
    tol = lp.PENETRATION_TOL_M * base.height_m / 1.75
    for side in sides:
        hip = art.joints.get(f"coxofemoral.{side}")
        if hip is None:
            continue
        for pose_name, posed in lp.hip_sweep_poses(base, side):
            surfaces = lp.posed_surfaces(art, base, anat, posed)
            for n in hip.ligaments:
                clear = lp.path_clearance(lp.posed_path(art.ligaments[n], base, anat, posed), surfaces)
                if clear < -tol:
                    out.append(Issue("error", "LIG_PENETRATES", f"'{n}' atraviesa el femur {-clear * 1000:.1f} mm en la pose '{pose_name}'"))
    return out


def validate_articulations_snapshot(art, snap: dict) -> list:
    """Compara los marcadores de union leidos de Blender con el modelo (posicion y padre)."""
    from . import ligament_paths

    out = []
    expected = {}
    for n, j in art.joints.items():
        expected[f"ART_{n}"] = (j.carrier, [j.center])
    for n, lg in art.ligaments.items():
        expected[f"LIG_{n}"] = (None if lg.deform else lg.from_bone, [p for _, p in ligament_paths.nodes(lg)])
    for n, at in art.attachments.items():
        expected[f"ATT_{n}"] = (at.bone, [at.point])
    for obj, (bone, pts) in expected.items():
        s = snap.get(obj)
        if s is None:
            out.append(Issue("error", "ART_BLEND_MISSING", f"Falta el objeto '{obj}'"))
            continue
        if s["parent_bone"] != bone:
            out.append(Issue("error", "ART_BLEND_PARENT", f"'{obj}' no esta emparentado a '{bone}'"))
        for p, q in zip(pts, s["points"]):
            if length(sub(p, tuple(q))) > BLEND_TOL:
                out.append(Issue("error", "ART_BLEND_POSITION", f"'{obj}' desplazado respecto al modelo"))
    extra = set(snap) - set(expected)
    if extra:
        out.append(Issue("error", "ART_BLEND_EXTRA", f"Objetos de union no esperados: {sorted(extra)[:5]}"))
    return out


def validate_anatomy_snapshot(anat, snap: dict) -> list:
    """Compara el nivel 1 leido de Blender (anatomy_scene.read_back_anatomy) con el modelo."""
    out = []
    sb = snap.get("bones", {})
    for n, b in anat.bones.items():
        s = sb.get(n)
        if s is None:
            out.append(Issue("error", "ANAT_BLEND_MISSING", f"El .blend no contiene el hueso anatomico '{n}'"))
            continue
        if s["parent"] != b.parent:
            out.append(Issue("error", "ANAT_BLEND_PARENT", f"'{n}': padre {s['parent']!r} != {b.parent!r}"))
        if s.get("layer") != "anatomy_L1":
            out.append(Issue("error", "ANAT_BLEND_LAYER", f"'{n}' no esta marcado como nivel 1"))
        if s.get("anatomical_parent") != (b.anatomical_parent or b.parent):
            out.append(Issue("error", "ANAT_BLEND_ANATOMICAL_PARENT", f"'{n}': padre anatomico en .blend {s.get('anatomical_parent')!r}"))
        for label, mine, theirs in (("head", b.head, s["head"]), ("tail", b.tail, s["tail"])):
            if length(sub(mine, tuple(theirs))) > BLEND_TOL:
                out.append(Issue("error", "ANAT_BLEND_POSITION", f"'{n}' {label} difiere en el .blend"))
        for label, mine, theirs in zip("xyz", b.frame, s["frame"]):
            if length(sub(mine, tuple(theirs))) > BLEND_TOL:
                out.append(Issue("error", "ANAT_BLEND_FRAME", f"'{n}': eje local {label} difiere (roll)"))
        v = snap.get("visuals", {}).get(f"ANA_{n}")
        if v is None or v["parent_bone"] != n:
            out.append(Issue("error", "ANAT_VIS_PARENT", f"ANA_{n} falta o no esta emparentado a '{n}'"))
        elif b.volume:  # forma volumetrica: se compara la caja envolvente y el numero de vertices con la malla del modelo
            verts, _ = volumes.volume_mesh(b)
            lo, hi = volumes.bounding_box(verts)
            if v.get("n_verts") != len(verts) or any(abs(x - y) > BLEND_TOL for x, y in zip(lo + hi, tuple(v["bbox"][0]) + tuple(v["bbox"][1]))):
                out.append(Issue("error", "ANAT_VOLUME_MISMATCH", f"ANA_{n}: la forma volumetrica del .blend no coincide con la del modelo"))
        elif length(sub(b.head, tuple(v["head"]))) > BLEND_TOL or length(sub(b.tail, tuple(v["tail"]))) > BLEND_TOL:
            out.append(Issue("error", "ANAT_VIS_POSITION", f"ANA_{n} no coincide con el hueso"))
        if b.cartilage:
            c = snap.get("cartilage", {}).get(f"ANA_cartilage_{n}")
            if c is None or c["parent_bone"] != n:
                out.append(Issue("error", "ANAT_CARTILAGE_PARENT", f"ANA_cartilage_{n} falta o no esta emparentado a '{n}'"))
            elif length(sub(b.cartilage[0], tuple(c["first"]))) > BLEND_TOL or length(sub(b.cartilage[-1], tuple(c["last"]))) > BLEND_TOL:
                out.append(Issue("error", "ANAT_CARTILAGE_POSITION", f"ANA_cartilage_{n} desplazado respecto al modelo"))
        if b.outline:
            o = snap.get("outlines", {}).get(f"ANA_outline_{n}")
            if o is None or o["parent_bone"] != n:
                out.append(Issue("error", "ANAT_OUTLINE_PARENT", f"ANA_outline_{n} falta o no esta emparentado a '{n}'"))
            elif length(sub(b.outline[0], tuple(o["first_point"]))) > BLEND_TOL:
                out.append(Issue("error", "ANAT_OUTLINE_POSITION", f"ANA_outline_{n} desplazado"))
    extra = [n for n, s in sb.items() if s.get("layer") == "anatomy_L1" and n not in anat.bones]
    if extra:
        out.append(Issue("error", "ANAT_BLEND_EXTRA", f"Huesos de nivel 1 no esperados: {extra}"))
    return out
