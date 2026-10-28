"""Mallas oseas solidas en Blender (usa bpy; nivel 2): un objeto BM_<hueso> por malla, emparentado a su hueso del nivel 1 con el inverso de su matriz en
reposo (sin doble transformacion), con el estilo de la imagen de referencia: relleno gris liso y contorno oscuro (casco invertido con un modificador Solidify).
Son cuerpos rigidos que siguen al rig."""
from __future__ import annotations

import bpy

from . import scene
from .bone_meshes import BoneMeshModel

COLLECTION = "AC_BoneMeshes"
_FILL = (0.86, 0.86, 0.85, 1.0)  # gris claro de la imagen (relleno 224-236 de 255)
_BONE = (0.95, 0.92, 0.84, 1.0)  # hueso claro (pelvis y sacro)
_JOINT = (0.80, 0.10, 0.10, 1.0)  # rojo: poligonos de union articular (copa acetabular)
_FILLS = {"grey": ("AC_Mat_bone_mesh", _FILL), "bone": ("AC_Mat_bone_mesh_bone", _BONE), "joint": ("AC_Mat_bone_mesh_joint", _JOINT)}
_LINE = (0.10, 0.10, 0.10, 1.0)  # contorno oscuro
OUTLINE_M = 0.0025  # espesor del contorno a 1.75 m


def add_bone_meshes(model: BoneMeshModel, anat) -> None:
    sc = bpy.context.scene
    arm_obj = bpy.data.objects[scene.ARMATURE_OBJECT]
    col = bpy.data.collections.new(COLLECTION)
    sc.collection.children.link(col)
    fills = {t: scene._material(n, c) for t, (n, c) in _FILLS.items()}
    line = scene._material("AC_Mat_bone_mesh_outline", _LINE)
    line.use_backface_culling = True  # solo se ve la cara trasera del casco: el contorno
    inverses = scene._bone_parent_inverses(sc, arm_obj, sorted({m.parent_bone for m in model.meshes.values()}))
    k = model.height_m / 1.75
    for n, m in model.meshes.items():
        o = scene._mesh_object(f"BM_{n}", m.verts, m.faces, col, fills[m.tone], "bone_mesh")
        o.data.materials.append(line)
        o.data.polygons.foreach_set("use_smooth", [m.smooth] * len(o.data.polygons))
        mod = o.modifiers.new("AC_Outline", "SOLIDIFY")
        mod.thickness, mod.offset, mod.use_flip_normals, mod.material_offset = OUTLINE_M * k, 1.0, True, 1
        o["ac_region"], o["ac_bone"], o["ac_volume_cm3"], o["ac_tone"] = anat.bones[m.parent_bone].region, m.parent_bone, m.volume_m3 * 1e6, m.tone
        scene._attach_to_bone(o, arm_obj, m.parent_bone, inverses)
    bpy.context.view_layer.update()


def read_back_bone_meshes() -> dict:
    bpy.context.view_layer.update()
    arm_obj = bpy.data.objects.get(scene.ARMATURE_OBJECT)
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in bpy.data.objects:
        if not o.name.startswith("BM_"):
            continue
        world = [o.matrix_world @ v.co for v in o.data.vertices]  # malla base (sin el contorno)
        ev = o.evaluated_get(dg)
        out[o.name] = {"parent_bone": o.parent_bone if o.parent is arm_obj and o.parent_type == "BONE" else None, "n_verts": len(world),
                       "bbox": [tuple(min(w[i] for w in world) for i in range(3)), tuple(max(w[i] for w in world) for i in range(3))]}
        del ev
    return out
