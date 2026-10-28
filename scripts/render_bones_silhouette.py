"""Renderiza SOLO los huesos del nivel 1 como silueta negra sobre fondo transparente, en las tres vistas de la imagen de referencia (frente, espalda y lado).

    blender -b output\\anatomy_level1.blend --python scripts\\render_bones_silhouette.py -- output\\reference_compare

Camara ortografica con el mismo encuadre que la referencia (el esqueleto ocupa ~90 % del alto). La vista lateral mira a -Y hacia la izquierda de la imagen,
como la referencia. Despues `scripts/compare_reference.py` (Python con PIL) compara las siluetas con las de la imagen."""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
out_dir = Path(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "output/reference_compare")
if not out_dir.is_absolute():
    out_dir = ROOT / out_dir  # relativo a la raiz del proyecto (Blender resuelve las rutas relativas desde otra carpeta)
out_dir.mkdir(parents=True, exist_ok=True)
RES_X, RES_Y, FILL = 542, 650, 0.90  # mismo aspecto que la referencia (1083 x 1300); el esqueleto ocupa el 90 % del alto

sc = bpy.context.scene
bones = [o for o in bpy.data.objects if o.name.startswith("ANA_")]
if not bones:
    raise SystemExit("El archivo no contiene huesos del nivel 1 (ANA_*): usa output/anatomy_level1.blend")
for o in bpy.data.objects:
    o.hide_render = not o.name.startswith("ANA_")
    o.hide_viewport = o.hide_render
ys = [(o.matrix_world @ Vector(c)) for o in bones for c in o.bound_box]
zmin, zmax = min(v.z for v in ys), max(v.z for v in ys)
height = zmax - zmin
zc = (zmin + zmax) / 2

sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES_X, RES_Y, 100
sc.render.film_transparent = True
sc.render.image_settings.file_format, sc.render.image_settings.color_mode = "PNG", "RGBA"
sh = sc.display.shading
sh.light, sh.color_type, sh.single_color = "FLAT", "SINGLE", (0.0, 0.0, 0.0)
sh.show_object_outline = False
sc.view_settings.view_transform = "Standard"

cam_data = bpy.data.cameras.new("AC_RefCam")
cam_data.type, cam_data.ortho_scale = "ORTHO", height / FILL
cam_data.clip_start, cam_data.clip_end = 0.01, 100.0
cam = bpy.data.objects.new("AC_RefCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
D = 6.0
for name, direction in (("front", Vector((0, -1, 0))), ("back", Vector((0, 1, 0))), ("side", Vector((1, 0, 0)))):
    cam.location = Vector((0, 0, zc)) + direction * D  # la camara mira hacia el esqueleto
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(out_dir / f"model_{name}.png")
    bpy.ops.render.render(write_still=True)
print(f"[OK] siluetas en {out_dir}; alto del esqueleto {height:.3f} m")
