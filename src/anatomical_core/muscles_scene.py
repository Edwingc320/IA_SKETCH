"""Capa muscular en Blender (usa bpy; rama muscle-model): un marcador por sitio (MUS_site_) y un tubo por fibra (MUS_fiber_), emparentados
a su hueso con el inverso de su matriz en reposo (sin doble transformacion). Son visualizacion de DATOS: no anaden movimiento al rig."""
from __future__ import annotations

import json

import bpy
from mathutils import Vector

from . import geometry as geo
from . import scene
from .muscles import MuscleModel

COLLECTION = "AC_Muscles"
_COLORS = {"site": (0.85, 0.15, 0.20, 1.0), "fiber": (0.80, 0.35, 0.30, 1.0)}
TUBE_SIDES = 4


def add_muscles(model: MuscleModel) -> None:
    sc = bpy.context.scene
    arm_obj = bpy.data.objects[scene.ARMATURE_OBJECT]
    col = bpy.data.collections.new(COLLECTION)
    sc.collection.children.link(col)
    mats = {k: scene._material(f"AC_Mat_muscle_{k}", c) for k, c in _COLORS.items()}
    bones = {s.bone for m in model.muscles.values() for s in m.sites}
    inverses = scene._bone_parent_inverses(sc, arm_obj, sorted(bones))
    k = model.height_m / 1.75
    for mname, m in model.muscles.items():
        for s in m.sites:
            verts, faces = geo.icosphere(s.point, 0.005 * k, subdivisions=1)
            o = scene._mesh_object(f"MUS_site_{mname}_{s.index}", verts, faces, col, mats["site"], "muscle_site_data")
            o["ac_region"], o["ac_muscle"], o["ac_kind"] = f"muscle_{m.region}", mname, s.kind
            o["ac_structure"] = s.structure
            o["ac_landmark"] = s.landmark or ""
            o["ac_sources"] = json.dumps(list(s.sources))
            scene._attach_to_bone(o, arm_obj, s.bone, inverses)
        for i, (a, b) in enumerate(m.fibers):
            sa, sb = m.sites[a], m.sites[b]
            verts, faces = geo.polyline_tube([sa.point, sb.point], 0.0025 * k, closed=False, sides=TUBE_SIDES)
            o = scene._mesh_object(f"MUS_fiber_{mname}_{i}", verts, faces, col, mats["fiber"], "muscle_fiber_data")
            o["ac_region"], o["ac_muscle"] = f"muscle_{m.region}", mname
            scene._attach_to_bone(o, arm_obj, sa.bone, inverses)
    bpy.context.view_layer.update()


def read_back_muscles() -> dict:
    bpy.context.view_layer.update()
    arm_obj = bpy.data.objects.get(scene.ARMATURE_OBJECT)
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in bpy.data.objects:
        if not o.name.startswith("MUS_"):
            continue
        ev = o.evaluated_get(dg)
        parent_bone = o.parent_bone if o.parent is arm_obj and o.parent_type == "BONE" else None
        verts = o.data.vertices
        if o.name.startswith("MUS_fiber_"):
            pts = [tuple(sum((ev.matrix_world @ verts[i].co for i in range(s, s + TUBE_SIDES)), Vector()) / TUBE_SIDES) for s in (0, TUBE_SIDES)]
        else:
            pts = [tuple(sum((ev.matrix_world @ v.co for v in verts), Vector()) / len(verts))]
        out[o.name] = {"parent_bone": parent_bone, "points": pts}
    return out
