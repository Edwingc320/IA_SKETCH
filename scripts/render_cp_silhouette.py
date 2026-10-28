"""Renderiza las siluetas (negro sobre transparente) de las piezas `cp.*` con la ESCALA EXACTA de la imagen de referencia, para compararlas por regiones.

    blender -b output\\cp_skeleton.blend --python scripts\\render_cp_silhouette.py -- <carpeta> <etiqueta> front:31:1261 back:53:1266 side:32:1261

Cada vista lleva `nombre:fila_superior:fila_inferior`: las filas de la figura de la imagen (de la coronilla a la planta del pie). Se asigna la coronilla del modelo
(0.998 H, antropometria) a la fila superior y el suelo (z = 0) a la inferior, asi que los pixeles por metro son los de la referencia y no hace falta reescalar.
Imagen de 700 x 1300 px; el eje x = 0 del modelo cae en la columna 350. Lo usa `scripts/compare_cp_regions.py`."""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(args[0]) if Path(args[0]).is_absolute() else ROOT / args[0]
label = args[1]
views = [a.split(":") for a in args[2:]]
out_dir.mkdir(parents=True, exist_ok=True)
Z_TOP_H = 0.998  # coronilla del craneo en fracciones de la altura
RES_X, RES_Y = 700, 1300

bpy.context.view_layer.update()
cp = [o for o in bpy.data.objects if o.name.startswith("cp.")]
if not cp:
    raise SystemExit("El archivo no contiene piezas cp.*")
height = max(o["cp_height_m"] for o in cp)
for o in bpy.data.objects:
    o.hide_render = o not in cp
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = RES_X, RES_Y, 100
sc.render.film_transparent = True
sc.render.image_settings.file_format, sc.render.image_settings.color_mode = "PNG", "RGBA"
sh = sc.display.shading
sh.light, sh.color_type, sh.single_color = "FLAT", "SINGLE", (0.0, 0.0, 0.0)
sh.show_object_outline = False
sc.view_settings.view_transform = "Standard"
cam_data = bpy.data.cameras.new("CP_RefCam")
cam_data.type = "ORTHO"
cam_data.clip_start, cam_data.clip_end = 0.01, 100.0
cam = bpy.data.objects.new("CP_RefCam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
for name, top, bottom in views:
    top, bottom = float(top), float(bottom)
    px_per_m = (bottom - top) / (Z_TOP_H * height)
    cam_data.ortho_scale = RES_Y / px_per_m  # el lado mayor (alto) abarca RES_Y pixeles
    zc = (bottom - RES_Y / 2) / px_per_m  # la fila central de la imagen; el suelo cae en la fila `bottom`
    direction = {"front": Vector((0, -1, 0)), "back": Vector((0, 1, 0)), "side": Vector((1, 0, 0))}[name]
    cam.location = Vector((0, 0, zc)) + direction * 6.0
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(out_dir / f"{label}_{name}.png")
    bpy.ops.render.render(write_still=True)
print(f"[OK] siluetas cp.* '{label}' en {out_dir} (altura {height:.3f} m)")
