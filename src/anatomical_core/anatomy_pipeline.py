"""Nivel 1: base -> anatomia -> validar -> escena -> guardar -> reabrir -> validar -> reporte.

Genera un archivo PROPIO (por defecto output/anatomy_level1.blend); el archivo de la base
(output/skeleton_core.blend) no se toca. Se ejecuta dentro de Blender. Las poses quedan fuera de
este nivel: la base se construye en su neutro.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import anatomy, anatomy_scene, articulations, articulations_scene, muscle_volumes, muscle_volumes_scene, muscles, muscles_scene, scene, tendons, tendons_scene, validation
from . import pose as pose_mod
from .config import PoseDef, load_config
from .skeleton import build_model


class AnatomyGenerationError(RuntimeError):
    def __init__(self, message: str, issues=()):
        super().__init__(message)
        self.issues = list(issues)


@dataclass
class AnatomyResult:
    blend_path: Path
    report_path: Path
    base: object
    anatomy: object
    issues: list
    previews: list = field(default_factory=list)


def base_part_of_snapshot(snap: dict, base) -> dict:
    """Restringe un snapshot de scene.read_back a los huesos de la base, para validarla con el
    validador de la base sin tocarlo (los huesos de nivel 1 no son 'extra' de la base)."""
    return dict(
        snap,
        bones={n: v for n, v in snap["bones"].items() if n in base.bones},
        pose_bones={n: v for n, v in snap["pose_bones"].items() if n in base.bones},
    )


def known_limitations(base, anat) -> dict:
    """Medidas de limitaciones conocidas (no son errores): se documentan en el reporte."""
    from .geometry import length, sub

    out = {}
    if "sternum" in anat.bones:
        gap = length(sub(base.bones["clavicle.L"].head, anat.bones["sternum"].head))
        out["sternoclavicular_gap_m"] = gap
        out["sternoclavicular_note"] = ("La clavicula base (congelada) nace casi en el plano de la columna; el manubrio "
                                        "esta delante. Se corregira al rehacer la cintura escapular.")
    for side in ("L", "R"):
        gap = anatomy.scapula_rib_clearance(anat, side)
        if gap is not None:
            out[f"scapula_rib_clearance_{side}_m"] = gap
    return out


def generate(output_blend, config_dir=None, anatomy_dir=None, reference_path=None, preview=True, log=print,
             articulations_dir=None, height_m=None) -> AnatomyResult:
    output_blend = Path(output_blend).resolve()
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    if output_blend.exists():
        log(f"[INFO] Se regenera (sobrescribe) el archivo de anatomia: {output_blend}")

    base = build_model(load_config(config_dir, height_m))
    base_issues = validation.validate_model(base)
    if validation.errors(base_issues):
        raise AnatomyGenerationError("La base no supera la validacion", base_issues)
    neutral = pose_mod.apply_pose(base, PoseDef("neutral", {}))
    acfg = anatomy.load_anatomy_config(anatomy_dir, reference_path)
    anat = anatomy.build_anatomy(base, acfg)
    issues = validation.validate_anatomy(base, anat)
    for i in issues:
        log(str(i))
    if validation.errors(issues):
        raise AnatomyGenerationError("El nivel 1 no supera la validacion", issues)
    cov = anatomy.coverage(anat, base)
    log(f"[INFO] Nivel 1: regiones {list(anat.regions)}, {len(anat.bones)} huesos; referencia: "
        f"{len(cov['implemented'])} representados, {len(cov['base'])} en la base, {len(cov['pending'])} pendientes")

    art = None
    art_data = articulations.load_articulation_data(articulations_dir)
    if art_data:
        art = articulations.build_articulations(base, anat, art_data)
        art_issues = validation.validate_articulations(base, anat, art)
        art_issues += validation.validate_ligament_poses(base, anat, art)  # barrido de la cadera: ningun ligamento atraviesa el femur
        art_issues += validation.validate_knee_ligament_poses(base, anat, art)  # barrido de cadera y rodilla: ligamentos de la rodilla
        art_issues += validation.validate_patella_tracking(base, anat, art)  # deslizamiento de la rotula: sin penetracion, a < 12 mm de los condilos, ligamento estable
        for i in art_issues:
            log(str(i))
        issues += art_issues
        if validation.errors(art_issues):
            raise AnatomyGenerationError("Los puntos de union no superan la validacion", art_issues)
        log(f"[INFO] Puntos de union: {len(art.joints)} articulaciones, {len(art.ligaments)} ligamentos, "
            f"{len(art.attachments)} inserciones, {len(art.sources)} fuentes")

    mus = None
    mus_data = muscles.load_muscle_data()
    if mus_data and art is not None:
        mus = muscles.build_muscles(base, anat, art, mus_data)
        mus_issues = muscles.validate_muscles(base, anat, art, mus)
        for i in mus_issues:
            log(str(i))
        issues += mus_issues
        if validation.errors(mus_issues):
            raise AnatomyGenerationError("La capa muscular no supera la validacion", mus_issues)
        log(f"[INFO] Capa muscular: {len(mus.muscles)} musculos, {sum(len(m.sites) for m in mus.muscles.values())} sitios, {len(mus.sources)} fuentes")

    ten = None
    ten_data = tendons.load_tendon_data()
    if ten_data and art is not None:
        ten = tendons.build_tendons(base, anat, art, ten_data)
        ten_issues = tendons.validate_tendons(base, anat, art, ten) + tendons.validate_tendon_poses(base, anat, art, ten)
        for i in ten_issues:
            log(str(i))
        issues += ten_issues
        if validation.errors(ten_issues):
            raise AnatomyGenerationError("La capa de tendones no supera la validacion", ten_issues)
        log(f"[INFO] Capa de tendones: {len(ten.tendons)} unidades musculo-tendinosas, {len(ten.sources)} fuentes")

    mvol = None
    mvol_data = muscle_volumes.load_volume_data()
    if mvol_data and ten is not None:
        mvol = muscle_volumes.build_volumes(ten, mvol_data, mus)
        mvol_issues = muscle_volumes.validate_volumes(ten, mvol)
        for i in mvol_issues:
            log(str(i))
        issues += mvol_issues
        if validation.errors(mvol_issues):
            raise AnatomyGenerationError("Los volumenes musculares no superan la validacion", mvol_issues)
        measured = sum(1 for v in mvol.volumes.values() if v.kind == "medido")
        log(f"[INFO] Volumenes musculares: {len(mvol.volumes)} vientres ({measured} con volumen medido, {len(mvol.volumes) - measured} por convencion visual)")

    scene.reset_scene()
    scene.build_scene(base, neutral)
    anatomy_scene.add_anatomy(anat, list(base.bones), base)
    if art is not None:
        articulations_scene.add_articulations(art, base.height_m)
    if mus is not None:
        muscles_scene.add_muscles(mus)
    if ten is not None:
        tendons_scene.add_tendons(ten)
    if mvol is not None:
        muscle_volumes_scene.add_muscle_volumes(ten, mvol)
    scene.save_blend(output_blend)
    log(f"[INFO] Guardado: {output_blend} ({output_blend.stat().st_size} bytes)")

    scene.open_blend(output_blend)
    base_blend = validation.validate_blend_snapshot(base, base_part_of_snapshot(scene.read_back(), base), neutral)
    anat_blend = validation.validate_anatomy_snapshot(anat, anatomy_scene.read_back_anatomy())
    if art is not None:
        anat_blend += validation.validate_articulations_snapshot(art, articulations_scene.read_back_articulations())
    if mus is not None:
        anat_blend += muscles.validate_muscles_snapshot(mus, muscles_scene.read_back_muscles())
    if ten is not None:
        anat_blend += tendons.validate_tendons_snapshot(ten, tendons_scene.read_back_tendons())
    if mvol is not None:
        anat_blend += muscle_volumes.validate_volumes_snapshot(ten, mvol, muscle_volumes_scene.read_back_muscle_volumes())
    for i in base_blend + anat_blend:
        log(str(i))
    issues += base_blend + anat_blend
    if validation.errors(base_blend + anat_blend):
        raise AnatomyGenerationError("El .blend reabierto no coincide con la base o con el nivel 1", base_blend + anat_blend)
    log("[OK] .blend reabierto: base intacta y nivel 1 verificado (jerarquia, roll, posiciones, visualizacion)")

    report_path = output_blend.with_name(output_blend.stem + "_report.json")
    report = {
        "base_signature": base.signature(),
        "anatomy_signature": anat.signature(),
        "regions": list(anat.regions),
        "bones": {n: {"parent": b.parent, "anatomical_parent": b.anatomical_parent or b.parent, "region": b.region, "reference": list(b.reference), "head": list(b.head),
                      "tail": list(b.tail), "length_m": b.length, "outline": [list(p) for p in b.outline]}
                  for n, b in anat.bones.items()},
        "anchors": [{"point": p, "equals": q, "description": d} for p, q, d in anat.anchors],
        "coverage": cov,
        "known_limitations": known_limitations(base, anat),
        "articulations": None if art is None else {
            "signature": art.signature(),
            "sources": art.sources,
            "joints": {n: {"kind": j.kind, "bones": list(j.bones), "carrier": j.carrier, "center": list(j.center),
                           "rig_driver": j.rig_driver, "known_limitation": j.known_limitation,
                           "dofs": [{"name": d.name, "total_deg": d.total_deg, "source": d.source, "note": d.note} for d in j.dofs],
                           "ligaments": list(j.ligaments), "sources": list(j.sources), "notes": j.notes}
                       for n, j in art.joints.items()},
            "ligaments": {n: {"from": l.from_bone, "to": l.to_bone, "a": list(l.a), "b": list(l.b), "joint": l.joint,
                              "sources": list(l.sources), "notes": l.notes} for n, l in art.ligaments.items()},
            "attachments": {n: {"bone": a.bone, "point": list(a.point), "structures": list(a.structures),
                                "sources": list(a.sources), "notes": a.notes} for n, a in art.attachments.items()},
        },
        "issues": [str(i) for i in issues],
        "disclaimer": "Nivel 1 aproximado sobre la base; no es anatomicamente exacto.",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"[INFO] Reporte: {report_path}")

    previews = []
    if preview:
        try:
            previews = anatomy_scene.render_anatomy_previews(base, output_blend.parent, anat=anat)
            for p in previews:
                log(f"[INFO] Vista previa: {p}")
        except Exception as exc:  # noqa: BLE001
            log(f"[WARNING] No se pudo renderizar la vista previa: {exc}")
    return AnatomyResult(output_blend, report_path, base, anat, issues, previews)
