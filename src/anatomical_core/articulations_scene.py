"""Puntos de union en Blender (usa bpy): marcadores de articulacion (ART_), ligamentos (LIG_) e
inserciones (ATT_), emparentados a su hueso con el inverso de su matriz en reposo (sin doble
transformacion). Son visualizacion de DATOS; no anaden movimiento al rig.

Un ligamento se emparenta a su hueso de origen: en reposo une exactamente sus dos puntos; al posar
huesos distintos no se estira (eso llegara con las poses)."""
from __future__ import annotations

import json

import bpy
from mathutils import Vector

from . import geometry as geo
from . import scene
from .articulations import ArticulationModel

COLLECTIONS = {"ART": "AC_Articulations", "LIG": "AC_Ligaments", "ATT": "AC_Attachments"}
_COLORS = {"ART": (0.10, 0.70, 0.70, 1.0), "LIG": (0.70, 0.25, 0.20, 1.0), "ATT": (0.60, 0.25, 0.75, 1.0)}
TUBE_SIDES = 4


def add_articulations(art: ArticulationModel, height_m: float) -> None:
    sc = bpy.context.scene
    arm_obj = bpy.data.objects[scene.ARMATURE_OBJECT]
    cols = {}
    for key, name in COLLECTIONS.items():
        cols[key] = bpy.data.collections.new(name)
        sc.collection.children.link(cols[key])
    mats = {k: scene._material(f"AC_Mat_{k.lower()}", c) for k, c in _COLORS.items()}
    bones_needed = {j.carrier for j in art.joints.values()} | {l.from_bone for l in art.ligaments.values()} | \
                   {a.bone for a in art.attachments.values()}
    inverses = scene._bone_parent_inverses(sc, arm_obj, sorted(bones_needed))
    k = height_m / 1.75
    for n, j in art.joints.items():
        verts, faces = geo.icosphere(j.center, 0.009 * k, subdivisions=1)
        o = scene._mesh_object(f"ART_{n}", verts, faces, cols["ART"], mats["ART"], "articulation_data")
        o["ac_joint_kind"] = j.kind
        o["ac_region"] = j.region
        o["ac_bones"] = json.dumps(list(j.bones))
        o["ac_dofs"] = json.dumps([{"name": d.name, "total_deg": d.total_deg, "source": d.source} for d in j.dofs])
        o["ac_rig_driver"] = j.rig_driver or ""
        o["ac_sources"] = json.dumps(list(j.sources))
        scene._attach_to_bone(o, arm_obj, j.carrier, inverses)
    for n, l in art.ligaments.items():
        verts, faces = geo.polyline_tube([l.a, l.b], 0.003 * k, closed=False, sides=TUBE_SIDES)
        o = scene._mesh_object(f"LIG_{n}", verts, faces, cols["LIG"], mats["LIG"], "ligament_data")
        o["ac_from_bone"], o["ac_to_bone"] = l.from_bone, l.to_bone
        o["ac_region"] = l.region
        o["ac_sources"] = json.dumps(list(l.sources))
        scene._attach_to_bone(o, arm_obj, l.from_bone, inverses)
    for n, a in art.attachments.items():
        verts, faces = geo.icosphere(a.point, 0.005 * k, subdivisions=1)
        o = scene._mesh_object(f"ATT_{n}", verts, faces, cols["ATT"], mats["ATT"], "attachment_data")
        o["ac_structures"] = json.dumps(list(a.structures), ensure_ascii=False)
        o["ac_region"] = a.region
        o["ac_sources"] = json.dumps(list(a.sources))
        scene._attach_to_bone(o, arm_obj, a.bone, inverses)
    bpy.context.view_layer.update()


def read_back_articulations() -> dict:
    """Posicion mundial evaluada y hueso padre de cada objeto ART_/LIG_/ATT_."""
    bpy.context.view_layer.update()
    arm_obj = bpy.data.objects.get(scene.ARMATURE_OBJECT)
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in bpy.data.objects:
        prefix = o.name.split("_", 1)[0]
        if prefix not in COLLECTIONS:
            continue
        ev = o.evaluated_get(dg)
        parent_bone = o.parent_bone if o.parent is arm_obj and o.parent_type == "BONE" else None
        verts = o.data.vertices
        if prefix == "LIG":  # tubo: los anillos de los dos extremos
            ends = [sum((ev.matrix_world @ verts[i].co for i in range(s, s + TUBE_SIDES)), Vector()) / TUBE_SIDES
                    for s in (0, TUBE_SIDES)]
            points = [tuple(p) for p in ends]
        else:
            points = [tuple(sum((ev.matrix_world @ v.co for v in verts), Vector()) / len(verts))]
        out[o.name] = {"parent_bone": parent_bone, "points": points}
    return out
