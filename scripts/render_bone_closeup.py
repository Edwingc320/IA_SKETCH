"""Primer plano de mallas oseas solidas (BM_*) con el estilo de la imagen de referencia (relleno gris liso y contorno oscuro), en vista frontal, trasera, lateral o
superior, para revisar la forma de una seccion.

    blender -b output\\anatomy_level1.blend --python scripts\\render_bone_closeup.py -- <vista> <salida.png> <prefijo> [<prefijo> ...]

Vistas: front, back, side, top. Los prefijos son del nombre del hueso (p. ej. `ilium ischium pubis sacrum coccyx`)."""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index("--") + 1:]
view, out = args[0], Path(args[1])
prefixes = args[2:] or [""]
if not out.is_absolute():
    out = ROOT / out
out.parent.mkdir(parents=True, exist_ok=True)

objs = [o for o in bpy.data.objects if o.name.startswith("BM_") and any(o.name[3:].startswith(p) for p in prefixes)]
if not objs:
    raise SystemExit("No hay mallas BM_ con esos prefijos: regenera output/anatomy_level1.blend")
for o in bpy.data.objects:
    o.hide_render = o not in objs
for o in objs:
    for m in o.modifiers:  # el casco invertido es el contorno para EEVEE/Cycles; en Workbench lo da el contorno de objeto
        m.show_render = False
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
lo, hi = Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])
centre, size = (lo + hi) / 2, hi - lo

sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.film_transparent = False
sc.render.image_settings.file_format = "PNG"
sc.world = sc.world or bpy.data.worlds.new("w")
sc.world.color = (1.0, 1.0, 1.0)
sh = sc.display.shading
sh.light, sh.color_type, sh.show_object_outline = "STUDIO", "MATERIAL", True
sh.object_outline_color = (0.1, 0.1, 0.1)
sc.view_settings.view_transform = "Standard"
dirs = {"front": Vector((0, -1, 0)), "back": Vector((0, 1, 0)), "side": Vector((1, 0, 0)), "top": Vector((0, 0, 1))}
horiz = {"front": size.x, "back": size.x, "side": size.y, "top": size.x}[view]
vert = {"front": size.z, "back": size.z, "side": size.z, "top": size.y}[view]
sc.render.resolution_x, sc.render.resolution_y = 900, int(900 * max(vert, 1e-6) / max(horiz, 1e-6) + 60)
sc.render.resolution_y = max(300, min(1400, sc.render.resolution_y))
cam_data = bpy.data.cameras.new("AC_CloseCam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max(horiz, vert * 900 / sc.render.resolution_y) * 1.15
cam = bpy.data.objects.new("AC_CloseCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
cam.location = centre + dirs[view] * 5.0
cam.rotation_euler = (-dirs[view]).to_track_quat("-Z", "Y" if view != "top" else "Y").to_euler()
sc.render.filepath = str(out)
bpy.ops.render.render(write_still=True)
print(f"[OK] {out}")
