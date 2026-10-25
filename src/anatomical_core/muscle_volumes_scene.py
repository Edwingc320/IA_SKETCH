"""Volumenes musculares en Blender (usa bpy; rama muscle-model): un objeto MUV_<unidad> por vientre, emparentado al hueso de origen con el inverso de
su matriz en reposo (sin doble transformacion). Es visualizacion de DATOS: la malla no se deforma al mover los huesos todavia."""
from __future__ import annotations

import bpy

from . import scene
from .muscle_volumes import VolumeModel, mesh_for
from .tendons import TendonModel

COLLECTION = "AC_MuscleVolumes"
_COLOR = (0.62, 0.16, 0.16, 1.0)  # rojo muscular


def add_muscle_volumes(tendon_model: TendonModel, model: VolumeModel) -> None:
    sc = bpy.context.scene
    arm_obj = bpy.data.objects[scene.ARMATURE_OBJECT]
    col = bpy.data.collections.new(COLLECTION)
    sc.collection.children.link(col)
    mat = scene._material("AC_Mat_muscle_volume", _COLOR)
    bones = {tendon_model.tendons[n].sites[0].bone for n in model.volumes}
    inverses = scene._bone_parent_inverses(sc, arm_obj, sorted(bones))
    for n, v in model.volumes.items():
        verts, faces = mesh_for(tendon_model, v)
        o = scene._mesh_object(f"MUV_{n}", verts, faces, col, mat, "muscle_volume")
        o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
        o["ac_region"], o["ac_tendon"], o["ac_volume_kind"] = f"muscle_volume_{tendon_model.tendons[n].region}", n, v.kind
        o["ac_volume_cm3"] = v.volume_m3(model.height_m) * 1e6
        scene._attach_to_bone(o, arm_obj, tendon_model.tendons[n].sites[0].bone, inverses)
    bpy.context.view_layer.update()


def read_back_muscle_volumes() -> dict:
    bpy.context.view_layer.update()
    arm_obj = bpy.data.objects.get(scene.ARMATURE_OBJECT)
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in bpy.data.objects:
        if not o.name.startswith("MUV_"):
            continue
        ev = o.evaluated_get(dg)
        world = [ev.matrix_world @ v.co for v in o.data.vertices]
        out[o.name] = {"parent_bone": o.parent_bone if o.parent is arm_obj and o.parent_type == "BONE" else None, "n_verts": len(world),
                       "bbox": [tuple(min(w[i] for w in world) for i in range(3)), tuple(max(w[i] for w in world) for i in range(3))]}
    return out
