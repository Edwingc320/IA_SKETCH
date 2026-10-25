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
from . import scene, volumes
from .anatomy import LAYER, AnatomyModel

COLLECTION_VISUALS = "AC_Anatomy_Visuals"
COLLECTION_OUTLINES = "AC_Anatomy_Outlines"
COLLECTION_CARTILAGE = "AC_Anatomy_Cartilage"
BASE_BONE_COLLECTION = "L0_base"
OUTLINE_SIDES = 4

_BONE_COLOR = (0.92, 0.88, 0.76, 1.0)  # hueso (marfil)
_OUTLINE_COLOR = (0.55, 0.45, 0.30, 1.0)
_CARTILAGE_COLOR = (0.62, 0.78, 0.86, 1.0)  # cartilago costal (azul palido)


def add_anatomy(anat: AnatomyModel, base_bone_names) -> None:
    """Anade el nivel 1 a la escena actual (que ya contiene la base creada por scene.build_scene)."""
    sc = bpy.context.scene
    arm_obj = bpy.data.objects[scene.ARMATURE_OBJECT]
    arm = arm_obj.data
    vis_col = bpy.data.collections.new(COLLECTION_VISUALS)
    out_col = bpy.data.collections.new(COLLECTION_OUTLINES)
    cart_col = bpy.data.collections.new(COLLECTION_CARTILAGE)
    sc.collection.children.link(vis_col)
    sc.collection.children.link(out_col)
    sc.collection.children.link(cart_col)

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
        bone["ac_anatomical_parent"] = b.anatomical_parent or b.parent  # relacion anatomica (el padre del rig es bone.parent)

    inverses = scene._bone_parent_inverses(sc, arm_obj, list(anat.bones))
    mat = scene._material("AC_Mat_anatomy", _BONE_COLOR)
    mat_outline = scene._material("AC_Mat_anatomy_outline", _OUTLINE_COLOR)
    mat_cartilage = scene._material("AC_Mat_anatomy_cartilage", _CARTILAGE_COLOR)
    k = anat.height_m / 1.75
    for b in anat.bones.values():
        if b.volume:  # forma volumetrica (boveda craneal) en lugar del octaedro fino
            verts, faces = volumes.volume_mesh(b)
            obj = scene._mesh_object(f"ANA_{b.name}", verts, faces, vis_col, mat, "visualization_volume")
            obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
        else:
            verts, faces = geo.bone_shape(b.head, b.tail, width_ratio=0.08)  # fina: no tapa los contornos
            obj = scene._mesh_object(f"ANA_{b.name}", verts, faces, vis_col, mat, "visualization_only")
        scene._attach_to_bone(obj, arm_obj, b.name, inverses)
        if b.outline:
            verts, faces = geo.polyline_tube(b.outline, 0.004 * k, closed=b.outline_closed, sides=OUTLINE_SIDES)
            o = scene._mesh_object(f"ANA_outline_{b.name}", verts, faces, out_col, mat_outline, "reference_geometry")
            scene._attach_to_bone(o, arm_obj, b.name, inverses)
        if b.cartilage:
            verts, faces = geo.polyline_tube(b.cartilage, 0.006 * k, closed=False, sides=OUTLINE_SIDES)
            c = scene._mesh_object(f"ANA_cartilage_{b.name}", verts, faces, cart_col, mat_cartilage, "costal_cartilage")
            scene._attach_to_bone(c, arm_obj, b.name, inverses)

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
    snap = {"bones": {}, "visuals": {}, "outlines": {}, "cartilage": {}, "bone_collections": {}, "meta": {}}
    if arm_obj is None:
        return snap
    for b in arm_obj.data.bones:
        m3 = b.matrix_local.to_3x3()
        snap["bones"][b.name] = {
            "parent": b.parent.name if b.parent else None,
            "head": tuple(b.head_local), "tail": tuple(b.tail_local),
            "frame": [tuple(m3.col[i]) for i in range(3)],
            "layer": b.get("ac_layer"),
            "anatomical_parent": b.get("ac_anatomical_parent"),
            "collections": [c.name for c in b.collections],
        }
    snap["bone_collections"] = {c.name: [b.name for b in c.bones] for c in arm_obj.data.collections_all}
    dg = bpy.context.evaluated_depsgraph_get()
    for o in bpy.data.objects:
        if not o.name.startswith("ANA_"):
            continue
        ev = o.evaluated_get(dg)
        parent_bone = o.parent_bone if o.parent is arm_obj and o.parent_type == "BONE" else None
        if o.name.startswith("ANA_cartilage_"):
            verts = [ev.matrix_world @ v.co for v in o.data.vertices]
            first, last = verts[:OUTLINE_SIDES], verts[-OUTLINE_SIDES:]
            snap["cartilage"][o.name] = {"parent_bone": parent_bone, "first": tuple(sum(first, Vector()) / len(first)),
                                         "last": tuple(sum(last, Vector()) / len(last))}
        elif o.name.startswith("ANA_outline_"):
            ring = [ev.matrix_world @ o.data.vertices[i].co for i in range(OUTLINE_SIDES)]
            snap["outlines"][o.name] = {"parent_bone": parent_bone, "first_point": tuple(sum(ring, Vector()) / len(ring))}
        else:
            world = [ev.matrix_world @ v.co for v in o.data.vertices]
            snap["visuals"][o.name] = {"parent_bone": parent_bone, "head": tuple(world[0]), "tail": tuple(world[5]) if len(world) > 5 else tuple(world[-1]),
                                       "n_verts": len(world), "bbox": [tuple(min(v[i] for v in world) for i in range(3)),
                                                                       tuple(max(v[i] for v in world) for i in range(3))]}
    raw = bpy.context.scene.get(scene.META_KEY)
    if raw:
        snap["meta"] = json.loads(raw)
    return snap


def _descendants(anat: AnatomyModel, root: str) -> set:
    """Huesos del nivel 1 que cuelgan (directa o indirectamente) del hueso `root`."""
    out = set()
    for n, b in anat.bones.items():
        cur = b.parent
        while cur is not None:
            if cur == root:
                out.add(n)
                break
            cur = anat.bones[cur].parent if cur in anat.bones else None
    return out


def render_anatomy_previews(base, out_dir, prefix: str = "anatomy", anat: AnatomyModel | None = None) -> list:
    """Vistas frontal, lateral, 3/4 de pelvis y torax, y de cerca de mano y pie (Workbench).
    Modifica la escena abierta: NO guardar despues."""
    from pathlib import Path

    height_m = base.height_m
    out_dir = Path(out_dir)
    sc = bpy.context.scene
    # en las vistas, los octaedros base de mano/pie taparian el detalle del nivel 1 (solo render)
    for n in ("hand.L", "hand.R", "foot.L", "foot.R"):
        obj = bpy.data.objects.get(f"VIS_{n}")
        if obj is not None:
            obj.hide_render = True
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
    hand = base.bones["hand.L"]
    foot = base.bones["foot.L"]
    hand_c = Vector(hand.head).lerp(Vector(hand.tail), 0.5)
    foot_c = Vector(foot.head).lerp(Vector(foot.tail), 0.4) + Vector((0.0, 0.0, -0.03 * height_m / 1.75))
    # vistas aisladas: (nombre, objetivo, direccion objetivo->camara, escala ortografica, huesos del nivel 1 visibles)
    every = set(anat.bones) if anat is not None else set()
    spine = {n for n, b in anat.bones.items() if b.region == "spine_head"} | {"sacrum", "coccyx"} if anat else set()
    spine_c = Vector((0.0, 0.0, 0.5 * (base.bones["pelvis"].tail[2] + base.bones["head"].tail[2])))
    body_c = Vector((0.0, 0.0, 0.5 * height_m))
    close = [
        ("hand_L_palmar", hand_c, Vector((0.0, -1.0, 0.0)), 1.5 * hand.length, _descendants(anat, "hand.L") if anat else set()),
        ("foot_L_lateral", foot_c, Vector((1.0, 0.0, 0.0)), 1.6 * foot.length, _descendants(anat, "foot.L") if anat else set()),
        ("foot_L_plantar", foot_c, Vector((0.0, 0.0, -1.0)), 1.6 * foot.length, _descendants(anat, "foot.L") if anat else set()),
        ("spine_head_lateral", spine_c, Vector((1.0, 0.0, 0.0)), 0.48 * height_m, spine),
        ("level1_front", body_c, Vector((0.0, -1.0, 0.0)), 1.15 * height_m, every),
        ("level1_side", body_c, Vector((1.0, 0.0, 0.0)), 1.15 * height_m, every),
    ]
    if anat is not None:  # torax + cintura escapular con sus puntos de union (articulaciones, ligamentos, inserciones)
        thorax = {n for n, b in anat.bones.items() if b.region == "thoracic_cage" or (n.startswith("T") and n[1:].isdigit())
                  or n.startswith(("scapula", "humerus", "C7"))}
        unions = {o.name for o in bpy.data.objects if o.get("ac_region") == "thorax_shoulder"}
        thorax_c = Vector((0.0, 0.0, base.bones["thorax"].head[2]))
        close.append(("thorax_shoulder_34", thorax_c, Vector((1.2, -1.6, 0.9)), 0.42 * height_m,
                      {*thorax, "__objects__", *(f"__obj__{u}" for u in unions), "__obj__VIS_clavicle.L", "__obj__VIS_clavicle.R"}))
        # pelvis posterior y region glutea: huesos de la pelvis y el femur con sus hitos y ligamentos (lateral, superior e inferior)
        pelvis = {"sacrum", "coccyx", "L5", "femur.L", "femur.R"} | {f"{n}.{s}" for n in ("ilium", "ischium", "pubis") for s in "LR"}
        pv_unions = {o.name for o in bpy.data.objects if o.get("ac_region") == "lumbar_pelvis" or str(o.get("ac_region", "")).startswith(("muscle_", "tendon_"))}
        pelvis_c = Vector((0.0, 0.03 * height_m, base.bones["pelvis"].tail[2] + 0.01 * height_m))
        for vname, direction in (("pelvis_lateral", Vector((1.0, 0.0, 0.0))), ("pelvis_superior", Vector((0.0, -0.001, 1.0))),
                                 ("pelvis_inferior", Vector((0.0, -0.001, -1.0)))):
            close.append((vname, pelvis_c, direction, 0.30 * height_m, {*pelvis, *(f"__obj__{u}" for u in pv_unions)}))
        # cabeza + columna cervical con sus puntos de union (vista lateral izquierda, algo de frente)
        head_neck = {f"C{k}" for k in range(1, 8)} | {"cranium", "mandible"}
        hn_unions = {o.name for o in bpy.data.objects if o.get("ac_region") == "head_neck"}
        head_c = Vector(base.bones["head"].head) + Vector((0.0, 0.0, 0.04 * height_m))
        close.append(("head_neck_lateral", head_c, Vector((1.0, -0.35, 0.1)), 0.26 * height_m,
                      {*head_neck, *(f"__obj__{u}" for u in hn_unions)}))
    views += [(n, None, o, None, (t, d, keep)) for n, t, d, o, keep in close]
    paths = []
    for name, cz, ortho, loc, rot in views:
        cam_data.ortho_scale = ortho
        hidden = {}
        if isinstance(rot, tuple) and len(rot) == 3 and isinstance(rot[0], Vector):  # vista de cerca
            target, direction, bones_kept = rot
            if anat is not None:  # aislar: solo se renderizan esos huesos del nivel 1 (y sus contornos)
                keep = {f"ANA_{n}" for n in bones_kept} | {f"ANA_outline_{n}" for n in bones_kept} | \
                       {n[len("__obj__"):] for n in bones_kept if n.startswith("__obj__")}  # objetos extra por nombre
                for o in bpy.data.objects:
                    if o.type == "MESH" and o.name not in keep:
                        hidden[o.name] = o.hide_render
                        o.hide_render = True
            loc_v = target + direction.normalized() * 3.0
            cam.location = loc_v
            cam.rotation_euler = (target - loc_v).to_track_quat("-Z", "Y").to_euler()
        elif loc is None:  # vista 3/4 desde delante-izquierda y algo arriba, centrada en cz
            target = Vector((0.0, 0.0, cz))
            loc_v = target + Vector((3.0, -4.0, 2.0))
            cam.location = loc_v
            cam.rotation_euler = (target - loc_v).to_track_quat("-Z", "Y").to_euler()
        else:
            cam.location, cam.rotation_euler = loc, rot
        path = out_dir / f"{prefix}_{name}.png"
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        for oname, was in hidden.items():  # restaurar la visibilidad de render
            bpy.data.objects[oname].hide_render = was
        paths.append(path)
    return paths
