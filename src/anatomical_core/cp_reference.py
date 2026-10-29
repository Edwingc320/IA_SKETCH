"""Planos de REFERENCIA del craneo dentro del `.blend` (usa bpy): las tres imagenes (`craneo frontal.jpg`, `craneo perfil.jpg`, `craneo atras.jpg`, en la raiz del proyecto; privadas,
no se versionan) como empties de imagen, mapeadas a la escala del craneo y a su posicion, para comparar a ojo la forma, el acabado y la profundidad en las vistas ortograficas
(numpad 1 frontal, 3 lateral, Ctrl+1 posterior).

El mapeo usa la caja de la silueta de cada imagen (`config/cp/skull_reference.json`, medida con `scripts/skull_reference.py`): frente y perfil se escalan para que la altura de
su silueta (coronilla a menton) iguale la del craneo con la mandibula del modelo; la vista posterior, para que la altura de la boveda iguale la de `cp.Skull`. Se alinean por la
linea media (frente y atras) o por el borde anterior (perfil) y por la coronilla. Las imagenes no tienen escala absoluta: la ESCALA se toma del modelo (la antropometria manda)
y la imagen aporta la FORMA. Quedan en la coleccion `CP_Reference` (no se renderizan)."""
from __future__ import annotations

import json
import math

import bpy
from mathutils import Vector

from .config import PROJECT_ROOT

REF_FILE = PROJECT_ROOT / "config" / "cp" / "skull_reference.json"
COLLECTION = "CP_Reference"
GAP_M = 0.12  # separacion del plano de la imagen respecto al craneo, hacia la camara


def _bbox(objs) -> tuple:
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def add_reference_images(parts: dict, alpha: float = 0.55) -> dict:
    """Crea los tres empties de imagen alineados con el craneo de `parts`; devuelve {vista: objeto} (omite las imagenes que no existan en el disco)."""
    ref = json.loads(REF_FILE.read_text(encoding="utf-8"))
    bpy.context.view_layer.update()
    group = [o for n, o in parts.items() if n.startswith(("cp.Skull", "cp.Zygomatic", "cp.Temporal", "cp.Mastoid", "cp.Condyle", "cp.TeethUpper"))]
    lo, hi = _bbox(group + [parts["cp.Mandible"]])  # craneo con mandibula
    vlo, vhi = _bbox([parts["cp.Skull"]])  # boveda
    col = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    out = {}
    for view in ("front", "side", "back"):
        info = ref[view]
        path = PROJECT_ROOT / info["file"]
        if not path.exists():
            continue
        img = bpy.data.images.load(str(path), check_existing=True)
        w, h = info["size"]
        x0, y0, x1, y1 = info["silhouette_bbox"]
        height_m = (vhi.z - vlo.z) if view == "back" else (hi.z - lo.z)
        k = height_m / (y1 - y0)  # metros por pixel
        top = vhi.z if view == "back" else hi.z
        cz = top - (h / 2 - y0) * k  # z del centro de la imagen (las filas crecen hacia abajo)
        mid = (lo + hi) / 2
        e = bpy.data.objects.new(f"CP_Ref_{view}", None)
        e.empty_display_type = "IMAGE"
        e.data = img
        e.empty_display_size = max(w, h) * k  # el lado mayor de la imagen
        e.empty_image_depth = "BACK"
        e.color = (1.0, 1.0, 1.0, alpha)
        if view == "front":
            e.rotation_euler = (math.pi / 2, 0.0, 0.0)
            e.location = Vector(((w / 2 - (x0 + x1) / 2) * k, mid.y - GAP_M, cz))  # derecha de la imagen = +x
        elif view == "side":
            e.rotation_euler = (math.pi / 2, 0.0, math.pi / 2)
            e.location = Vector((hi.x + GAP_M, lo.y + (w / 2 - x0) * k, cz))  # derecha = +y (la cara, a la izquierda = -y)
        else:
            e.rotation_euler = (math.pi / 2, 0.0, math.pi)
            e.location = Vector((-(w / 2 - (x0 + x1) / 2) * k, mid.y + GAP_M, cz))  # derecha = -x
        e.hide_render = True
        col.objects.link(e)
        e["cp_reference_view"], e["cp_m_per_px"] = view, k
        out[view] = e
    return out
