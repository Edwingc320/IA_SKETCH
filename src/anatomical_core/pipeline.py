"""Flujo completo: config -> modelo -> validar -> escena -> guardar -> reabrir -> validar -> reporte.

Se ejecuta DENTRO de Blender (usa scene.py). Lo invocan scripts/generate_skeleton.py y las pruebas.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import scene, validation
from .config import load_config
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
    issues: list
    previews: list = field(default_factory=list)


def generate(output_blend, config_dir=None, height_m=None, length_overrides=None, preview=True, log=print) -> GenerationResult:
    output_blend = Path(output_blend).resolve()
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    if output_blend.exists():
        log(f"[INFO] Se regenera (sobrescribe) el archivo generado: {output_blend}")

    config = load_config(config_dir, height_m, length_overrides)
    model = build_model(config)
    log(f"[INFO] Modelo: {len(model.bones)} huesos, {len(model.joints)} articulaciones, altura {model.height_m} m")
    log(f"[INFO] Firma de configuracion: {config.signature[:16]}  firma de modelo: {model.signature()[:16]}")

    issues = validation.validate_model(model)
    for i in issues:
        log(str(i))
    if validation.errors(issues):
        raise GenerationError("El modelo de datos no supera la validacion", issues)

    scene.reset_scene()
    scene.build_scene(model)
    scene.save_blend(output_blend)
    if not output_blend.is_file() or output_blend.stat().st_size == 0:
        raise GenerationError(f"No se guardo el .blend: {output_blend}")
    log(f"[INFO] Guardado: {output_blend} ({output_blend.stat().st_size} bytes)")

    # Reabrir desde disco y validar lo que realmente quedo guardado.
    scene.open_blend(output_blend)
    snapshot = scene.read_back()
    blend_issues = validation.validate_blend_snapshot(model, snapshot)
    for i in blend_issues:
        log(str(i))
    issues += blend_issues
    if validation.errors(blend_issues):
        raise GenerationError("El .blend reabierto no coincide con el modelo", blend_issues)
    log("[OK] .blend reabierto y verificado contra el modelo de datos")

    report_path = output_blend.with_name(output_blend.stem + "_report.json")
    report = {
        "generator_version": scene.GENERATOR_VERSION,
        "config_signature": config.signature,
        "model_signature": model.signature(),
        "height_m": model.height_m,
        "blend_file": output_blend.name,
        "bones": {
            n: {"parent": b.parent, "head": list(b.head), "tail": list(b.tail), "length_m": b.length}
            for n, b in model.bones.items()
        },
        "joints": {
            n: {
                "bone": j.bone,
                "pivot": list(j.pivot),
                "dofs": [{"name": d.name, "axis": list(d.axis), "min_deg": d.min_deg, "max_deg": d.max_deg} for d in j.dofs],
            }
            for n, j in model.joints.items()
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
    return GenerationResult(output_blend, report_path, model, issues, previews)
