"""Capa de tendones en Blender (usa bpy; rama muscle-model): por cada unidad musculo-tendinosa, un tubo grueso y claro por extremo tendinoso
(TEN_origin_, TEN_insertion_) y un tubo fino y rojo para el vientre (TEN_belly_), emparentados al hueso de su extremo con el inverso de su
matriz en reposo. Son visualizacion de DATOS: no anaden movimiento al rig."""
from __future__ import annotations

import json

import bpy
from mathutils import Vector

from . import geometry as geo
from . import scene
from .tendons import TendonModel

COLLECTION = "AC_Tendons"
_COLORS = {"tendon": (0.96, 0.94, 0.86, 1.0), "belly": (0.72, 0.20, 0.20, 1.0)}
TUBE_SIDES = 4


def add_tendons(model: TendonModel) -> None:
    sc = bpy.context.scene
    arm_obj = bpy.data.objects[scene.ARMATURE_OBJECT]
    col = bpy.data.collections.new(COLLECTION)
    sc.collection.children.link(col)
    mats = {k: scene._material(f"AC_Mat_tendon_{k}", c) for k, c in _COLORS.items()}
    bones = {s.bone for t in model.tendons.values() for s in t.sites}
    inverses = scene._bone_parent_inverses(sc, arm_obj, sorted(bones))
    k = model.height_m / 1.75
    for name, t in model.tendons.items():
        parts = []
        if t.origin_class:
            parts.append((f"TEN_origin_{name}", t.origin_tendon, t.sites[0].bone, "tendon", 0.0030, "tendon_origin_data"))
        if t.insertion_class:
            parts.append((f"TEN_insertion_{name}", t.insertion_tendon, t.sites[-1].bone, "tendon", 0.0030, "tendon_insertion_data"))
        parts.append((f"TEN_belly_{name}", t.belly, t.sites[0].bone, "belly", 0.0018, "muscle_belly_data"))
        for obj_name, pts, bone, mat, radius, role in parts:
            verts, faces = geo.polyline_tube(list(pts), radius * k, closed=False, sides=TUBE_SIDES)
            o = scene._mesh_object(obj_name, verts, faces, col, mats[mat], role)
            o["ac_region"], o["ac_tendon"] = f"tendon_{t.region}", name
            o["ac_muscles"] = json.dumps(list(t.muscles), ensure_ascii=False)
            o["ac_sources"] = json.dumps(list(t.sources))
            scene._attach_to_bone(o, arm_obj, bone, inverses)
    bpy.context.view_layer.update()


def read_back_tendons() -> dict:
    bpy.context.view_layer.update()
    arm_obj = bpy.data.objects.get(scene.ARMATURE_OBJECT)
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in bpy.data.objects:
        if not o.name.startswith("TEN_"):
            continue
        ev = o.evaluated_get(dg)
        parent_bone = o.parent_bone if o.parent is arm_obj and o.parent_type == "BONE" else None
        verts = o.data.vertices
        ring = lambda lo: sum((ev.matrix_world @ verts[i].co for i in range(lo, lo + TUBE_SIDES)), Vector()) / TUBE_SIDES  # noqa: E731
        out[o.name] = {"parent_bone": parent_bone, "points": [tuple(ring(0)), tuple(ring(len(verts) - TUBE_SIDES))]}
    return out
