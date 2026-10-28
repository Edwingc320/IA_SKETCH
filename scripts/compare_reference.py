"""Compara las siluetas del modelo con las de la imagen de referencia `esqueleto humano.jpg` (frente, espalda y lado). Python con PIL, sin numpy.

    python scripts\\compare_reference.py [carpeta_de_siluetas] [imagen_de_referencia]

Metrica: ambas siluetas se recortan a su caja, se escalan al mismo alto y se centran en horizontal; se mide el IoU (interseccion sobre union) y el error del
perfil de anchura (media del |ancho_modelo - ancho_referencia| / alto en 50 filas). Escribe `<carpeta>/report.json` y una imagen lado a lado.
La imagen de referencia es una ilustracion de stock con marca de agua: se usa solo como referencia privada de modelado y NO se versiona (ver .gitignore)."""
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "output" / "reference_compare"
REF = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "esqueleto humano.jpg"
VIEWS = ("front", "back", "side")
NORM_H = 600  # alto de comparacion en pixeles


def reference_masks(path: Path) -> dict:
    """Separa las tres figuras de la imagen (fondo blanco con marca de agua clara) y devuelve una mascara L (255 = hueso) por vista."""
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    cols = [sum(1 for y in range(h) if px[x, y] < 205) for x in range(w)]
    segs, start = [], None
    for x in range(w + 1):
        on = x < w and cols[x] > 3
        if on and start is None:
            start = x
        if not on and start is not None:
            if x - start > 40:
                segs.append((start, x))
            start = None
    merged = []
    for a, b in segs:
        if merged and a - merged[-1][1] < 25:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    if len(merged) != 3:
        raise SystemExit(f"Se esperaban 3 figuras y se encontraron {len(merged)}")
    out = {}
    for name, (a, b) in zip(VIEWS, merged):
        out[name] = im.crop((a, 0, b, h)).point(lambda v: 255 if v < 238 else 0)  # cuenta el relleno gris del hueso (224-236); la marca de agua es mas clara (>= 240)
    return out


def model_mask(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA").split()[3].point(lambda v: 255 if v > 127 else 0)


def normalise(mask: Image.Image) -> Image.Image:
    """Recorta a la caja y escala a NORM_H de alto, sin deformar."""
    box = mask.getbbox()
    if box is None:
        return Image.new("L", (1, NORM_H), 0)
    m = mask.crop(box)
    return m.resize((max(1, round(m.width * NORM_H / m.height)), NORM_H), Image.NEAREST)


def centre(m: Image.Image, width: int) -> Image.Image:
    canvas = Image.new("L", (width, NORM_H), 0)
    canvas.paste(m, ((width - m.width) // 2, 0))
    return canvas


def compare(ref: Image.Image, mod: Image.Image) -> dict:
    a, b = normalise(ref), normalise(mod)
    width = max(a.width, b.width) + 20
    a, b = centre(a, width), centre(b, width)
    pa, pb = a.load(), b.load()
    inter = union = 0
    for y in range(NORM_H):
        for x in range(width):
            ia, ib = pa[x, y] > 0, pb[x, y] > 0
            inter += ia and ib
            union += ia or ib
    prof = []
    for y in range(0, NORM_H, NORM_H // 50):
        wa = sum(1 for x in range(width) if pa[x, y] > 0)
        wb = sum(1 for x in range(width) if pb[x, y] > 0)
        prof.append(abs(wa - wb) / NORM_H)
    return {"iou": round(inter / union, 4) if union else 0.0, "width_profile_error": round(sum(prof) / len(prof), 4),
            "aspect_reference": round(normalise(ref).width / NORM_H, 4), "aspect_model": round(normalise(mod).width / NORM_H, 4),
            "area_ratio_model_over_reference": round(sum(1 for y in range(NORM_H) for x in range(width) if pb[x, y] > 0) / max(1, sum(1 for y in range(NORM_H) for x in range(width) if pa[x, y] > 0)), 4),
            "_pair": (a, b)}


def main() -> int:
    refs = reference_masks(REF)
    report, tiles = {}, []
    for v in VIEWS:
        path = OUT / f"model_{v}.png"
        if not path.exists():
            raise SystemExit(f"Falta {path}: ejecuta primero scripts/render_bones_silhouette.py dentro de Blender")
        res = compare(refs[v], model_mask(path))
        a, b = res.pop("_pair")
        report[v] = res
        tile = Image.new("L", (a.width * 2 + 10, NORM_H), 255)
        tile.paste(a.point(lambda p: 255 - p), (0, 0))
        tile.paste(b.point(lambda p: 255 - p), (a.width + 10, 0))
        tiles.append(tile)
    sheet = Image.new("L", (sum(t.width for t in tiles) + 20 * (len(tiles) - 1), NORM_H), 255)
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width + 20
    sheet.save(OUT / "compare_reference.png")
    report["mean_iou"] = round(sum(report[v]["iou"] for v in VIEWS) / len(VIEWS), 4)
    (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
