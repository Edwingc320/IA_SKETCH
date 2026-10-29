"""Renderiza el craneo `cp.*` en las tres vistas de las imagenes de referencia (frente, perfil con la cara a la IZQUIERDA y atras) de tres maneras:

    blender -b output\\cp_skeleton.blend --python scripts\\render_skull_views.py -- <carpeta> <etiqueta> [--set all|vault] [--mode silhouette|depth|parts|shaded]

* silhouette: negro sobre transparente (lo usa `scripts/compare_skull_reference.py`).
* depth: mapa de PROFUNDIDAD (gris = distancia a la camara: mas claro = mas cerca) por trazado de rayos; deja ver los hundimientos (orbitas, fosa nasal, fosas temporales).
* parts: un COLOR distinto por pieza independiente (las uniones entre grupos se ven como cambios de color).
* shaded: acabado en gris con luz de estudio y contorno.

`--set all` (por defecto) incluye cp.Skull*, cp.Mandible*, dientes, cigomaticos, temporales y condilos; `--set vault` omite la cara, la mandibula y los dientes (la vista posterior
de la referencia solo ve la boveda; la cara queda oculta tras ella)."""
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index("--") + 1:]
out_dir = Path(args[0]) if Path(args[0]).is_absolute() else ROOT / args[0]
label = args[1]
opt = {a: args[i + 1] for i, a in enumerate(args) if a.startswith("--") and i + 1 < len(args)}
SET, MODE = opt.get("--set", "all"), opt.get("--mode", "silhouette")
out_dir.mkdir(parents=True, exist_ok=True)

SKULL_PREFIXES = ("cp.Skull", "cp.Mandible", "cp.Teeth", "cp.Zygomatic", "cp.Temporal", "cp.Parietal", "cp.Sphenoid", "cp.Mastoid", "cp.Condyle")
VAULT_ONLY = ("cp.Skull", "cp.Zygomatic", "cp.Temporal", "cp.Parietal", "cp.Sphenoid", "cp.Mastoid", "cp.Condyle")  # sin cp.SkullFace
bpy.context.view_layer.update()


def wanted(name: str) -> bool:
    if SET == "vault":
        return name.startswith(VAULT_ONLY) and not name.startswith("cp.SkullFace")
    return name.startswith(SKULL_PREFIXES)


objs = [o for o in bpy.data.objects if o.type == "MESH" and wanted(o.name)]
if not objs:
    raise SystemExit("No hay piezas del craneo (cp.Skull*)")
for o in bpy.data.objects:
    o.hide_render = o not in objs
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
lo, hi = Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])
ctr, size = (lo + hi) / 2, hi - lo
DIRS = {"front": Vector((0, -1, 0)), "side": Vector((1, 0, 0)), "back": Vector((0, 1, 0))}
RIGHT = {"front": Vector((1, 0, 0)), "side": Vector((0, 1, 0)), "back": Vector((-1, 0, 0))}  # eje horizontal de la imagen, igual que en la camara de Blender (en el lado, la cara queda a la izquierda)
palette = [(0.90, 0.55, 0.30), (0.35, 0.65, 0.90), (0.55, 0.80, 0.40), (0.85, 0.40, 0.55), (0.95, 0.85, 0.35), (0.60, 0.50, 0.85), (0.40, 0.80, 0.75), (0.80, 0.65, 0.50), (0.70, 0.70, 0.70), (0.50, 0.60, 0.40)]

sc = bpy.context.scene
RES = 700
if MODE == "depth":
    deps = bpy.context.evaluated_depsgraph_get()
    trees = [(o, BVHTree.FromObject(o, deps)) for o in objs]
    for view, d in DIRS.items():
        horiz = max(size.x, size.y) * 1.1 if view != "front" and view != "back" else size.x * 1.1
        vert = size.z * 1.1
        scale = max(horiz, vert)
        n = 320
        right = RIGHT[view]
        up = Vector((0, 0, 1))
        depth = [[None] * n for _ in range(n)]
        zmin, zmax = 1e9, -1e9
        for j in range(n):
            for i in range(n):
                p = ctr + right * ((i / (n - 1) - 0.5) * scale) + up * ((0.5 - j / (n - 1)) * scale) + d * 3.0  # origen en el lado de la camara
                best = None
                for o, t in trees:
                    inv = o.matrix_world.inverted()
                    hit = t.ray_cast(inv @ p, (inv.to_3x3() @ (-d)).normalized())
                    if hit[0] is not None:
                        dist = (o.matrix_world @ hit[0] - p).length
                        best = dist if best is None else min(best, dist)
                depth[j][i] = best
                if best is not None:
                    zmin, zmax = min(zmin, best), max(zmax, best)
        pix = [0.0, 0.0, 0.0, 1.0] * (n * n)
        for j in range(n):
            for i in range(n):
                if depth[j][i] is not None:
                    g = (70 + 185 * (1.0 - (depth[j][i] - zmin) / max(1e-9, zmax - zmin))) / 255.0  # cerca = claro
                    k = ((n - 1 - j) * n + i) * 4  # las imagenes de Blender empiezan por la fila inferior
                    pix[k] = pix[k + 1] = pix[k + 2] = g
        im = bpy.data.images.new(f"depth_{view}", n, n)
        im.pixels = pix
        im.filepath_raw = str(out_dir / f"{label}_{view}_depth.png")
        im.file_format = "PNG"
        im.save()
    print(f"[OK] profundidad en {out_dir}")
    sys.exit(0)

sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x = sc.render.resolution_y = RES
sc.render.film_transparent = MODE in ("silhouette",)
sc.render.image_settings.file_format, sc.render.image_settings.color_mode = "PNG", "RGBA"
sh = sc.display.shading
if MODE == "silhouette":
    sh.light, sh.color_type, sh.single_color, sh.show_object_outline = "FLAT", "SINGLE", (0.0, 0.0, 0.0), False
elif MODE == "parts":
    sc.world = sc.world or bpy.data.worlds.new("w")
    sc.world.color = (1, 1, 1)
    sh.light, sh.color_type, sh.show_object_outline = "STUDIO", "OBJECT", True
    sh.object_outline_color = (0.1, 0.1, 0.1)
    for k, o in enumerate(sorted(objs, key=lambda o: o.name)):
        o.color = (*palette[k % len(palette)], 1.0)
else:
    sc.world = sc.world or bpy.data.worlds.new("w")
    sc.world.color = (1, 1, 1)
    sh.light, sh.color_type, sh.show_object_outline = "STUDIO", "MATERIAL", True
    sh.object_outline_color = (0.1, 0.1, 0.1)
sc.view_settings.view_transform = "Standard"
cd = bpy.data.cameras.new("SkullCam")
cd.type = "ORTHO"
cam = bpy.data.objects.new("SkullCam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
for view, d in DIRS.items():
    horiz = size.y if view == "side" else size.x
    cd.ortho_scale = max(horiz, size.z) * 1.12
    cam.location = ctr + d * 5.0
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(out_dir / f"{label}_{view}.png")
    bpy.ops.render.render(write_still=True)
print(f"[OK] {MODE} ({SET}) en {out_dir}: {sorted(o.name for o in objs)}")
