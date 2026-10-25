"""Capa de tendones en Blender (usa bpy; rama muscle-model): por cada unidad musculo-tendinosa, un tubo grueso y claro por extremo tendinoso
(TEN_origin_, TEN_insertion_) y un tubo fino y rojo para el vientre (TEN_belly_), emparentados al hueso de su extremo con el inverso de su
matriz en reposo. Son visualizacion de DATOS: no anaden movimiento al rig. Excepcion (`Tendon.deform`, p. ej. psoas-iliaco y cintilla iliotibial): los tubos
cuelgan de la armadura con un modificador Armature y cada anillo pesa entre los huesos de los dos sitios que lo rodean (interpolacion lineal), asi que el
recorrido sigue a los huesos."""
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
    bones = {s.bone for t in model.tendons.values() if not t.deform for s in t.sites}
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
            o["ac_deform"] = t.deform
            if t.deform:
                _skin(o, arm_obj, t, pts)
            else:
                scene._attach_to_bone(o, arm_obj, bone, inverses)
    bpy.context.view_layer.update()


def _skin(o, arm_obj, t, pts) -> None:
    """Armature modifier + grupos de vertices. El tubo tiene un prisma por segmento de `pts` (anillo de partida y de llegada, TUBE_SIDES vertices cada uno);
    cada anillo pesa segun donde cae su centro en el recorrido de la unidad (`Tendon.node_weights`)."""
    o.parent, o.parent_type = arm_obj, "OBJECT"
    groups = {b: o.vertex_groups.new(name=b) for b in dict.fromkeys(s.bone for s in t.sites)}
    ring_centers = [p for a, b in zip(pts, pts[1:]) if sum((x - y) ** 2 for x, y in zip(a, b)) > 1e-18 for p in (a, b)]
    for r, p in enumerate(ring_centers):
        for bone, w in t.node_weights(p):
            groups[bone].add(list(range(r * TUBE_SIDES, (r + 1) * TUBE_SIDES)), w, "REPLACE")
    mod = o.modifiers.new("AC_Armature", "ARMATURE")
    mod.object = arm_obj


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
        mesh = ev.to_mesh()  # malla evaluada: con el modificador Armature ya deformada
        try:
            world = [ev.matrix_world @ v.co for v in mesh.vertices]
        finally:
            ev.to_mesh_clear()
        ring = lambda lo: sum(world[lo:lo + TUBE_SIDES], Vector()) / TUBE_SIDES  # noqa: E731
        rings = [tuple(ring(lo)) for lo in range(0, len(world), TUBE_SIDES)]
        out[o.name] = {"parent_bone": parent_bone, "points": [rings[0], rings[-1]], "rings": rings}
    return out
