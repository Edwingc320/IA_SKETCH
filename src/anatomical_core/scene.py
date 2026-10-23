"""Representacion en Blender (unico modulo que importa bpy).

Separa dos cosas:
  * AC_Skeleton: la armadura REAL. Sus huesos (edit bones, "Rest Position") son el esqueleto
    NEUTRO; la pose A se aplica como rotaciones de pose bones (se puede alternar Rest/Pose).
  * AC_BoneVisuals / AC_JointMarkers / AC_JointAxes: geometria AUXILIAR de visualizacion
    (octaedros, esferas, flechas). No es una malla anatomica ni piel. Estan emparentadas a
    huesos (parent BONE) con el inverso de la matriz del hueso en reposo, por lo que coinciden
    con el neutro en Rest Position y siguen a la pose sin doble transformacion.
"""
from __future__ import annotations

import json
import math

import bpy
from mathutils import Vector

from . import geometry as geo
from .pose import PosedSkeleton
from .skeleton import SkeletonModel

ARMATURE_OBJECT = "AC_Armature"
COLLECTIONS = ("AC_Skeleton", "AC_BoneVisuals", "AC_JointMarkers", "AC_JointAxes")
META_KEY = "anatomical_core"
GENERATOR_VERSION = "0.2.0"

_COLORS = {  # color de visualizacion por lado (RGBA)
    "L": (0.20, 0.45, 0.95, 1.0),
    "R": (0.95, 0.30, 0.25, 1.0),
    "C": (0.80, 0.80, 0.75, 1.0),
    "joint": (1.0, 0.85, 0.15, 1.0),
}


def reset_scene() -> None:
    """Escena vacia y determinista (sin cubo/camara/luz por defecto)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _material(name: str, color) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def _collection(scene, name: str):
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    return col


def _mesh_object(name, verts, faces, collection, material, role):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    mesh.update()
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    obj["ac_role"] = role
    collection.objects.link(obj)
    return obj


def _bone_parent_inverses(scene, arm_obj, bone_names) -> dict:
    """Inverso de la matriz de padre-hueso de Blender para cada hueso, con la armadura en reposo.
    Se mide con un empty de prueba (sin suponer la convencion de Blender de que el padre-hueso
    esta en la cola del hueso): world = P * inverso(P) * local = local."""
    out = {}
    for name in bone_names:
        probe = bpy.data.objects.new("ac_probe", None)
        scene.collection.objects.link(probe)
        probe.parent, probe.parent_type, probe.parent_bone = arm_obj, "BONE", name
        bpy.context.view_layer.update()
        out[name] = probe.matrix_world.inverted()
        bpy.data.objects.remove(probe)
    return out


def _attach_to_bone(obj, arm_obj, bone_name, inverses) -> None:
    obj.parent, obj.parent_type, obj.parent_bone = arm_obj, "BONE", bone_name
    obj.matrix_parent_inverse = inverses[bone_name]


def build_scene(model: SkeletonModel, posed: PosedSkeleton) -> dict:
    """Crea armadura neutra + visualizacion y aplica la pose. Devuelve las colecciones por nombre."""
    scene = bpy.context.scene
    scene.name = "AnatomicalCore"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    cols = {n: _collection(scene, n) for n in COLLECTIONS}

    # --- Armadura real: esqueleto NEUTRO con roll tomado del marco local del modelo ----------
    arm_data = bpy.data.armatures.new("AC_ArmatureData")
    arm_data.display_type = "STICK"
    arm_data.show_axes = True  # muestra los ejes locales (X, Y, Z) de cada hueso: permite revisar el roll
    arm_obj = bpy.data.objects.new(ARMATURE_OBJECT, arm_data)
    arm_obj.show_in_front = True
    cols["AC_Skeleton"].objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        edit = arm_data.edit_bones
        for b in model.bones.values():
            eb = edit.new(b.name)
            eb.head = b.head
            eb.tail = b.tail
            eb.align_roll(Vector(b.frame[2]))  # el eje local Z del hueso = Z del marco => X y Y tambien
        for b in model.bones.values():
            if b.parent:
                eb = edit[b.name]
                eb.parent = edit[b.parent]
                eb.use_connect = geo.length(geo.sub(model.bones[b.parent].tail, b.head)) < 1e-6
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")

    # Datos del modelo como propiedades personalizadas (consultables desde Blender).
    for b in model.bones.values():
        arm_data.bones[b.name]["ac_length_m"] = b.length
    for j in model.joints.values():
        arm_data.bones[j.bone]["ac_joint"] = json.dumps(
            {
                "name": j.name,
                "pivot": list(j.pivot),
                "dofs": [
                    {
                        "name": d.name, "axis": list(d.axis), "axis_local": d.axis_local, "axis_sign": d.axis_sign,
                        "min_deg": d.min_deg, "max_deg": d.max_deg, "positive_motion": d.positive_motion,
                    }
                    for d in j.dofs
                ],
                "note": "pivote y ejes del esqueleto NEUTRO; angulos medidos desde el neutro; limites aproximados y configurables, no medicos",
            }
        )

    # --- Visualizacion auxiliar (geometria en el espacio del neutro) -----------------------
    inverses = _bone_parent_inverses(scene, arm_obj, list(model.bones))
    mats = {k: _material(f"AC_Mat_{k}", c) for k, c in _COLORS.items()}
    scale_k = model.height_m / 1.75
    for b in model.bones.values():
        verts, faces = geo.bone_shape(b.head, b.tail, width_ratio=0.12)
        obj = _mesh_object(f"VIS_{b.name}", verts, faces, cols["AC_BoneVisuals"], mats[b.side or "C"], "visualization_only")
        _attach_to_bone(obj, arm_obj, b.name, inverses)
    for j in model.joints.values():
        # Marcadores y ejes siguen al hueso PADRE: asi quedan en el pivote posado y los ejes rotan
        # con el padre pero no con el giro propio del hueso hijo (los ejes son fijos en el padre).
        carrier = j.parent_bone
        verts, faces = geo.icosphere(j.pivot, 0.012 * scale_k, subdivisions=1)
        marker = _mesh_object(f"JM_{j.name}", verts, faces, cols["AC_JointMarkers"], mats["joint"], "visualization_only")
        _attach_to_bone(marker, arm_obj, carrier, inverses)
        for d in j.dofs:
            arrow = bpy.data.objects.new(f"AX_{j.name}_{d.name}", None)
            arrow.empty_display_type = "SINGLE_ARROW"  # apunta a +Z local
            arrow.empty_display_size = 0.07 * scale_k
            arrow.location = j.pivot
            arrow.rotation_mode = "QUATERNION"
            arrow.rotation_quaternion = Vector(d.axis).to_track_quat("Z", "Y")
            arrow.show_in_front = True
            arrow["ac_role"] = "visualization_only"
            arrow["ac_axis"] = list(d.axis)
            cols["AC_JointAxes"].objects.link(arrow)
            _attach_to_bone(arrow, arm_obj, carrier, inverses)

    # --- Pose A: rotaciones locales de pose bones (los pivotes no se tocan) ------------------
    arm_data.pose_position = "POSE"
    for name, pb in posed.bones.items():
        pbone = arm_obj.pose.bones[name]
        pbone.rotation_mode = "QUATERNION"
        pbone.rotation_quaternion = pb.local_quat
        if model.bones[name].parent is None:
            pbone.location = pb.local_location
    arm_obj["ac_pose"] = json.dumps(
        {
            "name": posed.pose_name,
            "angles_deg": posed.angles,
            "root_translation_m": list(posed.root_translation),
            "note": "angulos medidos desde el esqueleto neutro (Rest Position = neutro; Pose Position = pose)",
        }
    )

    scene[META_KEY] = json.dumps(
        {
            "generator_version": GENERATOR_VERSION,
            "config_signature": model.config_signature,
            "model_signature": model.signature(),
            "pose_signature": posed.signature,
            "pose_name": posed.pose_name,
            "height_m": model.height_m,
            "disclaimer": "estructura inicial aproximada, no anatomicamente exacta",
        }
    )
    bpy.context.view_layer.update()
    return cols


def save_blend(path) -> None:
    bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)


def open_blend(path) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(path))


def _evaluated(obj):
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get())


def read_back() -> dict:
    """Lee de la escena abierta los datos esenciales (para validar un .blend reabierto): huesos en
    reposo con su marco local (roll), huesos posados evaluados y posicion mundial de la visualizacion."""
    bpy.context.view_layer.update()
    obj = bpy.data.objects.get(ARMATURE_OBJECT)
    snap = {
        "armature_object": obj.name if obj and obj.type == "ARMATURE" else None,
        "armature_transform_identity": False,
        "pose_position": None,
        "bones": {},
        "pose_bones": {},
        "visuals": {},
        "collections": [c.name for c in bpy.data.collections],
        "counts": {"joint_markers": 0, "joint_axes": 0, "bone_visuals": 0},
        "meta": {},
    }
    if snap["armature_object"]:
        snap["armature_transform_identity"] = (
            all(abs(c) < 1e-9 for c in obj.location)
            and all(abs(c) < 1e-9 for c in obj.rotation_euler)
            and all(abs(c - 1.0) < 1e-9 for c in obj.scale)
        )
        snap["pose_position"] = obj.data.pose_position
        for b in obj.data.bones:
            m3 = b.matrix_local.to_3x3()
            snap["bones"][b.name] = {
                "parent": b.parent.name if b.parent else None,
                "head": tuple(b.head_local),
                "tail": tuple(b.tail_local),
                "length": b.length,
                "frame": [tuple(m3.col[i]) for i in range(3)],  # ejes locales X, Y, Z (roll)
            }
        arm_eval = _evaluated(obj)
        for pb in arm_eval.pose.bones:
            snap["pose_bones"][pb.name] = {"head": tuple(pb.head), "tail": tuple(pb.tail)}
    for o in bpy.data.objects:
        if o.name == ARMATURE_OBJECT:
            continue
        ev = _evaluated(o)
        info = {"parent_bone": o.parent_bone if o.parent is obj and o.parent_type == "BONE" else None}
        if o.name.startswith("VIS_"):
            snap["counts"]["bone_visuals"] += 1
            info["head"] = tuple(ev.matrix_world @ o.data.vertices[0].co)  # bone_shape: v0 = cabeza, v5 = cola
            info["tail"] = tuple(ev.matrix_world @ o.data.vertices[5].co)
        elif o.name.startswith("JM_"):
            snap["counts"]["joint_markers"] += 1
            verts = o.data.vertices
            center = sum((ev.matrix_world @ v.co for v in verts), Vector()) / len(verts)
            info["center"] = tuple(center)
        elif o.name.startswith("AX_"):
            snap["counts"]["joint_axes"] += 1
            info["location"] = tuple(ev.matrix_world.translation)
            info["direction"] = tuple(ev.matrix_world.to_quaternion() @ Vector((0.0, 0.0, 1.0)))
        else:
            continue
        snap["visuals"][o.name] = info
    raw = bpy.context.scene.get(META_KEY)
    if raw:
        snap["meta"] = json.loads(raw)
    return snap


def render_previews(model: SkeletonModel, out_dir) -> list:
    """Renderiza vistas frontal y lateral (Workbench, sin GPU dedicada) de la pose y del neutro.
    Modifica la escena abierta (camara/luz/mundo/pose_position): NO guardar el .blend despues."""
    from pathlib import Path

    out_dir = Path(out_dir)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.resolution_x, scene.render.resolution_y = 600, 900
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("AC_World")
    world.color = (0.93, 0.93, 0.95)
    scene.world = world

    cam_data = bpy.data.cameras.new("AC_PreviewCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = model.height_m * 1.2
    cam = bpy.data.objects.new("AC_PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cz = model.height_m * 0.5
    views = {
        "front": ((0.0, -6.0, cz), (math.radians(90), 0.0, 0.0)),  # mira hacia +Y: ve el frente (personaje mira -Y)
        "side": ((6.0, 0.0, cz), (math.radians(90), 0.0, math.radians(90))),  # desde su izquierda
    }
    arm = bpy.data.objects[ARMATURE_OBJECT]
    paths = []
    for prefix, position in (("preview", "POSE"), ("preview_neutral", "REST")):
        arm.data.pose_position = position
        bpy.context.view_layer.update()
        for name, (loc, rot) in views.items():
            cam.location, cam.rotation_euler = loc, rot
            path = out_dir / f"{prefix}_{name}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            paths.append(path)
    return paths
