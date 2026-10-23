"""Flujo completo: config -> neutro -> pose -> validar -> escena -> guardar -> reabrir -> validar -> reporte.

Se ejecuta DENTRO de Blender (usa scene.py). Lo invocan scripts/generate_skeleton.py y las pruebas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import pose as pose_mod
from . import scene, validation
from .config import PoseDef, load_config
from .pose import PosedSkeleton
from .skeleton import SkeletonModel, build_model


class GenerationError(RuntimeError):
    def __init__(self, message: str, issues=()):
        super().__init__(message)
        self.issues = list(issues)


@dataclass
class GenerationResult:
    blend_path: Path
    report_path: Path
    model: SkeletonModel
    posed: PosedSkeleton
    issues: list
    previews: list = field(default_factory=list)


def generate(output_blend, config_dir=None, height_m=None, length_overrides=None, pose_overrides=None,
             neutral_only=False, preview=True, log=print) -> GenerationResult:
    output_blend = Path(output_blend).resolve()
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    if output_blend.exists():
        log(f"[INFO] Se regenera (sobrescribe) el archivo generado: {output_blend}")

    config = load_config(config_dir, height_m, length_overrides, pose_overrides)
    model = build_model(config)
    posed = pose_mod.apply_pose(model, PoseDef("neutral", {}) if neutral_only else config.pose)
    log(f"[INFO] Esqueleto neutro: {len(model.bones)} huesos, {len(model.joints)} articulaciones, altura {model.height_m} m")
    log(f"[INFO] Pose: {posed.pose_name}  (firma neutro {model.signature()[:12]}, firma pose {posed.signature[:12]})")

    issues = validation.validate_model(model) + validation.validate_pose(model, posed)
    for i in issues:
        log(str(i))
    if validation.errors(issues):
        raise GenerationError("El modelo de datos no supera la validacion", issues)
    metrics = pose_mod.metrics(model, posed)
    log(f"[INFO] Separacion de tobillos: {metrics['ankle_spacing_m']:.4f} m "
        f"({metrics['ankle_spacing_over_hip_spacing']:.2f}x caderas, {metrics['ankle_spacing_over_height']:.3f} H); "
        f"inclinacion de pies L/R: {metrics['foot_L_tilt_deg']:.3f}/{metrics['foot_R_tilt_deg']:.3f} deg; "
        f"traslacion de raiz: {metrics['root_translation_m'][2] * 1000:.2f} mm")

    scene.reset_scene()
    scene.build_scene(model, posed)
    scene.save_blend(output_blend)
    if not output_blend.is_file() or output_blend.stat().st_size == 0:
        raise GenerationError(f"No se guardo el .blend: {output_blend}")
    log(f"[INFO] Guardado: {output_blend} ({output_blend.stat().st_size} bytes)")

    # Reabrir desde disco y validar lo que realmente quedo guardado (huesos, roll, pose evaluada, visualizacion).
    scene.open_blend(output_blend)
    snapshot = scene.read_back()
    blend_issues = validation.validate_blend_snapshot(model, snapshot, posed)
    for i in blend_issues:
        log(str(i))
    issues += blend_issues
    if validation.errors(blend_issues):
        raise GenerationError("El .blend reabierto no coincide con el modelo", blend_issues)
    log("[OK] .blend reabierto y verificado contra el esqueleto neutro y la pose (FK)")

    report_path = output_blend.with_name(output_blend.stem + "_report.json")
    report = {
        "generator_version": scene.GENERATOR_VERSION,
        "config_signature": config.signature,
        "model_signature": model.signature(),
        "pose_signature": posed.signature,
        "height_m": model.height_m,
        "ankle_height_m": model.ankle_height_m,
        "blend_file": output_blend.name,
        "neutral_bones": {
            n: {"parent": b.parent, "head": list(b.head), "tail": list(b.tail), "length_m": b.length,
                "frame": {"x": list(b.frame[0]), "y": list(b.frame[1]), "z": list(b.frame[2])}}
            for n, b in model.bones.items()
        },
        "joints": {
            n: {
                "bone": j.bone,
                "pivot": list(j.pivot),
                "dofs": [
                    {"name": d.name, "axis": list(d.axis), "axis_local": d.axis_local, "axis_sign": d.axis_sign,
                     "min_deg": d.min_deg, "max_deg": d.max_deg, "positive_motion": d.positive_motion}
                    for d in j.dofs
                ],
            }
            for n, j in model.joints.items()
        },
        "pose": {
            "name": posed.pose_name,
            "angles_deg": posed.angles,
            "root_translation_m": list(posed.root_translation),
            "posed_bones": {n: {"head": list(pb.head), "tail": list(pb.tail)} for n, pb in posed.bones.items()},
            "metrics": metrics,
        },
        "issues": [str(i) for i in issues],
        "disclaimer": "Estructura inicial aproximada; limites articulares configurables, no medicos.",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"[INFO] Reporte: {report_path}")

    previews = []
    if preview:
        try:  # la vista previa es opcional: no debe tumbar la generacion
            previews = scene.render_previews(model, output_blend.parent)
            for p in previews:
                log(f"[INFO] Vista previa: {p}")
        except Exception as exc:  # noqa: BLE001
            log(f"[WARNING] No se pudo renderizar la vista previa: {exc}")
    return GenerationResult(output_blend, report_path, model, posed, issues, previews)
