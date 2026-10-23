"""Nivel 1 en Blender: anade los huesos anatomicos a la armadura base como HIJOS de sus huesos.

Usa bpy. No modifica los huesos base (solo los asigna a una coleccion de huesos "L0_base" en el
archivo de anatomia). Cada hueso anatomico lleva una forma de visualizacion (ANA_<hueso>) y, si
tiene contorno, un tubo fino de referencia (ANA_outline_<hueso>), ambos emparentados al hueso.
"""
from __future__ import annotations

import json
import math

import bpy
from mathutils import Vector

from . import geometry as geo
from . import scene
from .anatomy import LAYER, AnatomyModel

COLLECTION_VISUALS = "AC_Anatomy_Visuals"
COLLECTION_OUTLINES = "AC_Anatomy_Outlines"
BASE_BONE_COLLECTION = "L0_base"
OUTLINE_SIDES = 4

_BONE_COLOR = (0.92, 0.88, 0.76, 1.0)  # hueso (marfil)
_OUTLINE_COLOR = (0.55, 0.45, 0.30, 1.0)


def add_anatomy(anat: AnatomyModel, base_bone_names) -> None:
    """Anade el nivel 1 a la escena actual (que ya contiene la base creada por scene.build_scene)."""
    sc = bpy.context.scene
    arm_obj = bpy.data.objects[scene.ARMATURE_OBJECT]
    arm = arm_obj.data
    vis_col = bpy.data.collections.new(COLLECTION_VISUALS)
    out_col = bpy.data.collections.new(COLLECTION_OUTLINES)
    sc.collection.children.link(vis_col)
    sc.collection.children.link(out_col)

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        eb = arm.edit_bones
        for b in anat.bones.values():
            e = eb.new(b.name)
            e.head, e.tail = b.head, b.tail
            e.align_roll(Vector(b.frame[2]))
        for b in anat.bones.values():
            e = eb[b.name]
            e.parent = eb[b.parent]
            e.use_connect = geo.length(geo.sub(eb[b.parent].tail, e.head)) < 1e-6
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    # colecciones de huesos: base (nivel 0) y una por region del nivel 1 (para mostrar/ocultar)
    base_coll = arm.collections.new(BASE_BONE_COLLECTION)
    for n in base_bone_names:
        base_coll.assign(arm.bones[n])
    region_colls = {r: arm.collections.new(f"L1_{r}") for r in anat.regions}
    for b in anat.bones.values():
        bone = arm.bones[b.name]
        region_colls[b.region].assign(bone)
        bone["ac_layer"] = LAYER
        bone["ac_region"] = b.region
        bone["ac_reference"] = json.dumps(list(b.reference))

    inverses = scene._bone_parent_inverses(sc, arm_obj, list(anat.bones))
    mat = scene._material("AC_Mat_anatomy", _BONE_COLOR)
    mat_outline = scene._material("AC_Mat_anatomy_outline", _OUTLINE_COLOR)
    k = anat.height_m / 1.75
    for b in anat.bones.values():
        verts, faces = geo.bone_shape(b.head, b.tail, width_ratio=0.08)  # fina: no tapa los contornos
        obj = scene._mesh_object(f"ANA_{b.name}", verts, faces, vis_col, mat, "visualization_only")
        scene._attach_to_bone(obj, arm_obj, b.name, inverses)
        if b.outline:
            verts, faces = geo.polyline_tube(b.outline, 0.004 * k, closed=b.outline_closed, sides=OUTLINE_SIDES)
            o = scene._mesh_object(f"ANA_outline_{b.name}", verts, faces, out_col, mat_outline, "reference_geometry")
            scene._attach_to_bone(o, arm_obj, b.name, inverses)

    meta = json.loads(sc.get(scene.META_KEY, "{}"))
    meta["anatomy"] = {
        "layer": LAYER,
        "regions": list(anat.regions),
        "bones": len(anat.bones),
        "anatomy_signature": anat.signature(),
        "base_signature": anat.base_signature,
    }
    sc[scene.META_KEY] = json.dumps(meta)
    bpy.context.view_layer.update()


def read_back_anatomy() -> dict:
    """Lee del .blend abierto los huesos de nivel 1 y su visualizacion (posicion mundial evaluada)."""
    bpy.context.view_layer.update()
    arm_obj = bpy.data.objects.get(scene.ARMATURE_OBJECT)
    snap = {"bones": {}, "visuals": {}, "outlines": {}, "bone_collections": {}, "meta": {}}
    if arm_obj is None:
        return snap
    for b in arm_obj.data.bones:
        m3 = b.matrix_local.to_3x3()
        snap["bones"][b.name] = {
            "parent": b.parent.name if b.parent else None,
            "head": tuple(b.head_local), "tail": tuple(b.tail_local),
            "frame": [tuple(m3.col[i]) for i in range(3)],
            "layer": b.get("ac_layer"),
            "collections": [c.name for c in b.collections],
        }
    snap["bone_collections"] = {c.name: [b.name for b in c.bones] for c in arm_obj.data.collections_all}
    dg = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.objects:
        if not o.name.startswith("ANA_"):
            continue
        ev = o.evaluated_get(dg)
        parent_bone = o.parent_bone if o.parent is arm_obj and o.parent_type == "BONE" else None
        if o.name.startswith("ANA_outline_"):
            ring = [ev.matrix_world @ o.data.vertices[i].co for i in range(OUTLINE_SIDES)]
            snap["outlines"][o.name] = {"parent_bone": parent_bone, "first_point": tuple(sum(ring, Vector()) / len(ring))}
        else:
            snap["visuals"][o.name] = {"parent_bone": parent_bone,
                                       "head": tuple(ev.matrix_world @ o.data.vertices[0].co),
                                       "tail": tuple(ev.matrix_world @ o.data.vertices[5].co)}
    raw = bpy.context.scene.get(scene.META_KEY)
    if raw:
        snap["meta"] = json.loads(raw)
    return snap


def render_anatomy_previews(height_m: float, out_dir, prefix: str = "anatomy") -> list:
    """Vistas frontal, lateral y 3/4 (Workbench). Modifica la escena abierta: NO guardar despues."""
    from pathlib import Path

    out_dir = Path(out_dir)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "MATERIAL"
    sc.render.resolution_x, sc.render.resolution_y = 700, 900
    sc.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("AC_World")
    world.color = (0.93, 0.93, 0.95)
    sc.world = world
    cam_data = bpy.data.cameras.new("AC_AnatomyCam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("AC_AnatomyCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    # vistas: (nombre, centro z, escala ortografica, posicion, rotacion)
    views = [
        ("front", 0.5 * height_m, 1.15 * height_m, (0.0, -6.0, 0.5 * height_m), (math.radians(90), 0.0, 0.0)),
        ("side", 0.5 * height_m, 1.15 * height_m, (6.0, 0.0, 0.5 * height_m), (math.radians(90), 0.0, math.radians(90))),
        ("pelvis_34", 0.55 * height_m, 0.35 * height_m, None, None),
        ("thorax_34", 0.73 * height_m, 0.40 * height_m, None, None),
    ]
    paths = []
    for name, cz, ortho, loc, rot in views:
        cam_data.ortho_scale = ortho
        if loc is None:  # vista 3/4 desde delante-izquierda y algo arriba, centrada en cz
            target = Vector((0.0, 0.0, cz))
            loc_v = target + Vector((3.0, -4.0, 2.0))
            cam.location = loc_v
            cam.rotation_euler = (target - loc_v).to_track_quat("-Z", "Y").to_euler()
        else:
            cam.location, cam.rotation_euler = loc, rot
        path = out_dir / f"{prefix}_{name}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        paths.append(path)
    return paths
